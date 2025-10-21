from typing import Optional, Set, Dict, Any

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

from src.core.analysis.tree_analyzer import TreeNode
from src.core.analysis.tree_identity import TreeNodeIdentity
from src.core.application.analysis_service import AnalysisService
from src.core.application.chat_service import ChatService
from src.core.conversion.domain_adapters import chat_to_dict
from src.core.domain.models import AnalysisResult, Chat
from src.presenters.app_state import AppState
from src.presenters.workers import AnalysisWorker, TreeBuildWorker
from src.resources.translations import tr
from src.ui.dialogs.analysis.analysis_dialog import AnalysisDialog

class AnalysisPresenterExtended(QObject):
    """Extended presenter for managing analysis functionality and dialogs."""

    filter_changed = pyqtSignal(set)
    analysis_count_updated = pyqtSignal(int, str)
    analysis_completed = pyqtSignal(TreeNode)
    disabled_nodes_changed = pyqtSignal(set)

    def __init__(self, view, app_state: AppState, analysis_service: AnalysisService, chat_service: ChatService, theme_manager):
        super().__init__()
        self._view = view
        self._app_state = app_state
        self._analysis_service = analysis_service
        self._chat_service = chat_service
        self._theme_manager = theme_manager

        self._threadpool = QThreadPool()
        self._current_workers = []

        self._analysis_dialog = None
        self._calendar_dialog = None

        self._connect_signals()

    def _connect_signals(self):
        """Connects UI signals to presenter methods."""
        self._view.recalculate_clicked.connect(self.on_recalculate_clicked)
        self._view.calendar_button_clicked.connect(self.on_calendar_clicked)
        self._view.diagram_button_clicked.connect(self.on_diagram_clicked)

    def on_recalculate_clicked(self):
        """Handles recalculate button click."""
        if not self._app_state.has_chat_loaded():
            self._view.show_status(message_key="Please load a JSON file first.", is_error=True)
            return

        if self._app_state.is_processing:
            return

        self.set_processing_state_in_view(True, message_key="Calculating...")

        worker = AnalysisWorker(
            self._analysis_service,
            self._app_state.loaded_chat,
            self._app_state.ui_config.copy(),
            self._app_state.tokenizer,
            disabled_dates=set(),
        )
        worker.signals.finished.connect(self._on_analysis_finished)

        self._current_workers.append(worker)
        self._threadpool.start(worker)

    def _on_analysis_finished(self, success: bool, message: str, result: Optional[AnalysisResult]):
        """Handles analysis completion."""
        self.set_processing_state_in_view(False)

        if success and result:
            self._app_state.set_analysis_result(result)

            tree = self._analysis_service.build_analysis_tree(result, self._app_state.ui_config)
            self._app_state.set_analysis_tree(tree)

            self._app_state.clear_disabled_nodes()

            self.analysis_count_updated.emit(result.total_count, result.unit)
            self.analysis_completed.emit(tree)
            self.disabled_nodes_changed.emit(set())
        else:
            self._view.show_status(
                message_key="Analysis failed or no data found.",
                is_error=True
            )
            self.analysis_count_updated.emit(-1, "chars")

    def on_diagram_clicked(self):
        """Handles diagram button click."""
        if self._app_state.is_processing:
            return

        if not self._app_state.has_chat_loaded():
            self._view.show_status(message_key="Please load a JSON file first.", is_error=True)
            return

        if not self._app_state.has_analysis_data():
            self._view.show_message_box(
                tr("Token Analysis"),
                tr("Please calculate total tokens first by clicking 'Recalculate'."),
                QMessageBox.Icon.Information
            )
            return

        if not self._app_state.analysis_tree:
            self.set_processing_state_in_view(True, message_key="Building analysis tree...")

            worker = TreeBuildWorker(
                self._analysis_service,
                self._app_state.analysis_result,
                self._app_state.ui_config.copy(),
            )
            worker.signals.finished.connect(self._on_tree_build_finished)

            self._current_workers.append(worker)
            self._threadpool.start(worker)
        else:
            self._show_analysis_dialog()

    def _on_tree_build_finished(self, success: bool, message: str, result: Optional[TreeNode]):
        """Handles analysis tree building completion."""
        self.set_processing_state_in_view(False)

        if success and result:
            self._app_state.set_analysis_tree(result)
            self._show_analysis_dialog()
        else:
            self._view.show_status(message_key="Failed to build analysis tree", is_error=True)

    def _show_analysis_dialog(self):
        """Shows analysis dialog with bidirectional communication."""
        print(f"ANALYSIS DEBUG: _show_analysis_dialog called, analysis_tree={self._app_state.analysis_tree}")

        if self._analysis_dialog is not None:
            try:
                self.analysis_completed.disconnect(self._analysis_dialog.update_chart_data)
                self._analysis_dialog.accepted.disconnect(self._handle_analysis_accepted)
                self.disabled_nodes_changed.disconnect(self._analysis_dialog.on_external_update)
            except (TypeError, RuntimeError):
                pass
            try:
                self._analysis_dialog.close()
            except RuntimeError:
                pass
            self._analysis_dialog = None

        try:
            print("ANALYSIS DEBUG: Creating AnalysisDialog")
            self._analysis_dialog = AnalysisDialog(
                presenter=self,
                theme_manager=self._theme_manager,
                parent=self._view,
            )
            print("ANALYSIS DEBUG: AnalysisDialog created successfully")

            self._analysis_dialog.accepted.connect(self._handle_analysis_accepted)
            self._analysis_dialog.filter_changed.connect(self.update_disabled_nodes)
            self.disabled_nodes_changed.connect(self._analysis_dialog.on_external_update)
            self.analysis_completed.connect(self._analysis_dialog.update_chart_data)

            def disconnect_analysis_signals(result_code=None):
                try:
                    if self._analysis_dialog:
                        self.disabled_nodes_changed.disconnect(self._analysis_dialog.on_external_update)
                        self._analysis_dialog.accepted.disconnect(self._handle_analysis_accepted)
                        self._analysis_dialog.filter_changed.disconnect(self.update_disabled_nodes)
                        self.analysis_completed.disconnect(self._analysis_dialog.update_chart_data)
                except (TypeError, RuntimeError):
                    pass

            self._analysis_dialog.finished.connect(disconnect_analysis_signals)

            if self._app_state.analysis_tree:
                print(f"ANALYSIS DEBUG: Loading data with tree={self._app_state.analysis_tree}")
                disabled_nodes = self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree)
                print(f"ANALYSIS DEBUG: disabled_nodes count = {len(disabled_nodes)}")
                print(f"ANALYSIS DEBUG: unit = {self._app_state.last_analysis_unit}")

                self._analysis_dialog.load_data_and_show(
                    root_node=self._app_state.analysis_tree,
                    initial_disabled_nodes=disabled_nodes,
                    unit=self._app_state.last_analysis_unit
                )
            print("ANALYSIS DEBUG: About to show dialog")
            self._analysis_dialog.show()
            print("ANALYSIS DEBUG: Dialog show() called")

        except Exception as e:
            print(f"ANALYSIS ERROR: Exception in _show_analysis_dialog: {e}")
            import traceback
            traceback.print_exc()

    def _handle_analysis_accepted(self):
        """Handles analysis dialog confirmation."""
        if self._analysis_dialog:
            final_disabled_nodes = self._analysis_dialog._get_nodes_from_ids(self._analysis_dialog.disabled_node_ids)
            self.update_disabled_nodes(final_disabled_nodes)
        else:
            pass

    def on_calendar_clicked(self):
        """Handles calendar button click."""
        if self._app_state.is_processing:
            return

        if not self._app_state.has_chat_loaded():
            self._view.show_status(message_key="Please load a JSON file first.", is_error=True)
            return

        if not self._app_state.has_analysis_data():
            self._view.show_message_box(
                tr("Calendar"),
                tr("Please calculate total tokens first by clicking 'Recalculate'."),
                QMessageBox.Icon.Information
            )
            return

        if not self._app_state.analysis_tree:
            self.set_processing_state_in_view(True, message_key="Building analysis tree...")

            worker = TreeBuildWorker(
                self._analysis_service,
                self._app_state.analysis_result,
                self._app_state.ui_config.copy(),
            )
            worker.signals.finished.connect(self._on_calendar_tree_build_finished)

            self._current_workers.append(worker)
            self._threadpool.start(worker)
        else:
            self._show_calendar_dialog()

    def _on_calendar_tree_build_finished(self, success: bool, message: str, result: Optional[TreeNode]):
        """Handles calendar tree building completion."""
        self.set_processing_state_in_view(False)

        if success and result:
            self._app_state.set_processing_state(False)
            self._app_state.set_analysis_tree(result)
            self._show_calendar_dialog()
        else:
            self._view.show_status(
                tr("Failed to build analysis tree for calendar"), is_error=True
            )

    def _show_calendar_dialog(self):
        """Shows calendar dialog with bidirectional communication."""
        from src.ui.dialogs.calendar import CalendarDialog

        if self._calendar_dialog is not None:
            try:
                self._calendar_dialog.presenter.filter_changed.disconnect(self.update_disabled_nodes)
                self.disabled_nodes_changed.disconnect(self._calendar_dialog.presenter.set_disabled_nodes)
            except (TypeError, RuntimeError):
                pass
            try:
                self._calendar_dialog.close()
            except RuntimeError:
                pass
            self._calendar_dialog = None

        try:
            chat_as_dict = chat_to_dict(self._app_state.loaded_chat)
            messages_dict = chat_as_dict.get("messages", [])

            self._calendar_dialog = CalendarDialog(
                messages=messages_dict,
                config=self._app_state.ui_config.copy(),
                theme_manager=self._theme_manager,
                root_node=self._app_state.analysis_tree,
                initial_disabled_nodes=self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree),
                token_hierarchy=(
                    self._app_state.analysis_result.date_hierarchy
                    if self._app_state.analysis_result
                    else {}
                ),
                parent=self._view,
            )
            self._theme_manager.apply_theme_to_dialog(self._calendar_dialog)

            self._calendar_dialog.presenter.filter_changed.connect(self.update_disabled_nodes)
            self.disabled_nodes_changed.connect(self._calendar_dialog.presenter.set_disabled_nodes)

            def disconnect_calendar_signals(result_code=None):
                try:
                    if self._calendar_dialog:
                        self._calendar_dialog.presenter.filter_changed.disconnect(self.update_disabled_nodes)
                        self.disabled_nodes_changed.disconnect(self._calendar_dialog.presenter.set_disabled_nodes)
                except (TypeError, RuntimeError):
                    pass

            self._calendar_dialog.finished.connect(disconnect_calendar_signals)

            self._calendar_dialog.show()
        except Exception as e:
            self._view.show_status(message_key="Error opening calendar dialog", is_error=True)

    def update_disabled_nodes(self, new_disabled_set: Set[TreeNode]):
        """Updates disabled nodes."""
        old_disabled_set = self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree) if self._app_state.analysis_tree else set()

        if old_disabled_set != new_disabled_set:
            self._app_state.set_disabled_nodes(new_disabled_set)
            self.disabled_nodes_changed.emit(new_disabled_set)
            self._refresh_all_ui()

    def set_processing_state_in_view(self, is_processing: bool, message: str = "", message_key: str = None, format_args: dict = None):
        """Proxy method for calling set_processing_state in view."""
        if message_key:
            translated_message = tr(message_key)
            self._app_state.set_processing_state(is_processing, translated_message)
        else:
            self._app_state.set_processing_state(is_processing, message)

        if hasattr(self._view, 'set_processing_state'):
            self._view.set_processing_state(is_processing, None, message_key, format_args)
        else:
            pass

    def on_config_value_changed_for_update(self, key: str, value: Any):
        """СИНХРОННОЕ обновление анализа при изменении настроек с гарантией сохранности disabled_dates"""
        if not self._app_state.has_analysis_data():
            return

        analysis_affecting_keys = [
            "profile", "show_service_notifications", "show_markdown",
            "show_links", "show_time", "show_reactions",
            "show_reaction_authors", "show_tech_info",
            "show_optimization", "streak_break_time",
            "my_name", "partner_name"
        ]

        if key not in analysis_affecting_keys:
            return

        try:

            if self._app_state.tokenizer:
                result = self._analysis_service.calculate_token_stats(
                    self._app_state.loaded_chat,
                    self._app_state.ui_config,
                    self._app_state.tokenizer,
                    disabled_dates=set()
                )
            else:
                result = self._analysis_service.calculate_character_stats(
                    self._app_state.loaded_chat,
                    self._app_state.ui_config,
                    disabled_dates=set()
                )

            if self._app_state.analysis_tree:
                extended_result = self._extend_analysis_result_with_existing_tree(result, self._app_state.analysis_tree)
                tree = self._analysis_service.update_tree_values(
                    self._app_state.analysis_tree,
                    extended_result
                )
            else:

                tree = self._analysis_service.build_analysis_tree(result, self._app_state.ui_config)

            self._app_state.set_analysis_result(result)
            self._app_state.set_analysis_tree(tree)

            self._refresh_all_ui_sync()

        except Exception as e:
            self._view.show_status(message_key="Error recalculating analysis", is_error=True)

    def _extend_analysis_result_with_existing_tree(self, new_result: AnalysisResult, existing_tree: TreeNode) -> AnalysisResult:
        """
        Расширяет новый результат анализа, чтобы включить все даты из существующего дерева.
        Это гарантирует, что все узлы дней останутся в дереве, даже если их значения стали 0.
        """
        from collections import defaultdict

        extended_hierarchy = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

        for year, months in new_result.date_hierarchy.items():
            for month, days in months.items():
                for day, value in days.items():
                    extended_hierarchy[year][month][day] = value

        def collect_existing_dates(node: TreeNode):
            if node.date_level == "day" and node.parent and node.parent.parent:
                year = node.parent.parent.name
                month = node.parent.name
                day = node.name

                if year not in extended_hierarchy or \
                   month not in extended_hierarchy.get(year, {}) or \
                   day not in extended_hierarchy.get(year, {}).get(month, {}):
                    extended_hierarchy[year][month][day] = 0.0

            for child in node.children:
                collect_existing_dates(child)
            if hasattr(node, 'aggregated_children') and node.aggregated_children:
                for agg_child in node.aggregated_children:
                    collect_existing_dates(agg_child)

        collect_existing_dates(existing_tree)

        extended_result = AnalysisResult(
            total_count=new_result.total_count,
            unit=new_result.unit,
            date_hierarchy=dict(extended_hierarchy),
            total_characters=new_result.total_characters,
            average_message_length=new_result.average_message_length,
            most_active_user=new_result.most_active_user,
        )
        return extended_result

    def _refresh_all_ui(self):
        """Принудительно обновляет все элементы UI"""
        if not self._app_state.has_analysis_data():
            self.analysis_count_updated.emit(-1, "chars")
            return

        result = self._app_state.analysis_result
        tree = self._app_state.analysis_tree

        self.analysis_completed.emit(tree)

        filtered_count = self._app_state.get_filtered_count()
        self.analysis_count_updated.emit(filtered_count, result.unit)

    def _refresh_all_ui_sync(self):
        """Синхронное обновление UI"""
        if not self._app_state.has_analysis_data():
            self.analysis_count_updated.emit(-1, "chars")
            return

        result = self._app_state.analysis_result
        tree = self._app_state.analysis_tree

        self.analysis_completed.emit(tree)

        filtered_count = self._app_state.get_filtered_count()
        self.analysis_count_updated.emit(filtered_count, result.unit)

    def on_disabled_dates_changed(self):
        """Вызывается при изменении disabled_dates из диаграммы."""
        if not self._app_state.has_analysis_data():
            return

        try:

            self.on_config_value_changed_for_update("disabled_nodes", None)
        except Exception as e:
            self._view.show_status(message_key="Error recalculating after date change", is_error=True)
