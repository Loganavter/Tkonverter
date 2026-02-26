from typing import Optional, Set, Dict, Any, TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

import logging
from PyQt6.QtWidgets import QMessageBox

from src.core.analysis.tree_analyzer import TreeNode

if TYPE_CHECKING:
    from src.core.settings_port import SettingsPort
from src.core.analysis.tree_identity import TreeNodeIdentity
from src.core.application.analysis_service import AnalysisService
from src.core.application.calendar_service import CalendarService
from src.core.application.chat_memory_service import ChatMemoryService
from src.core.application.chart_service import ChartService
from src.core.application.chat_service import ChatService
from src.core.conversion.domain_adapters import chat_to_dict
from src.core.domain.models import AnalysisResult, Chat
from src.presenters.app_state import AppState
from src.presenters.calendar_presenter import CalendarPresenter
from src.presenters.workers import AnalysisWorker, TreeBuildWorker
from src.resources.translations import tr

logger = logging.getLogger(__name__)

class AnalysisPresenter(QObject):

    filter_changed = pyqtSignal(set)
    analysis_count_updated = pyqtSignal(int, str, bool)
    analysis_completed = pyqtSignal(object)
    disabled_nodes_changed = pyqtSignal(set)

    def __init__(
        self,
        view,
        app_state: AppState,
        analysis_service: AnalysisService,
        chat_service: ChatService,
        theme_manager,
        calendar_service: CalendarService,
        chart_service: ChartService,
        chat_memory_service: ChatMemoryService,
        settings_port: Optional["SettingsPort"] = None,
        tokenizer_service: Optional[Any] = None,
    ):
        super().__init__()
        self._view = view
        self._app_state = app_state
        self._analysis_service = analysis_service
        self._chat_service = chat_service
        self._theme_manager = theme_manager
        self._calendar_service = calendar_service
        self._chart_service = chart_service
        self._chat_memory_service = chat_memory_service
        self._settings_port = settings_port
        self._tokenizer_service = tokenizer_service

        self._threadpool = QThreadPool()
        self._current_workers = []

        self._analysis_dialog = None
        self._calendar_dialog = None

        self._connect_signals()

    def is_analysis_log_suppressed(self) -> bool:
        if self._calendar_dialog is not None and self._calendar_dialog.isVisible():
            return True
        if self._analysis_dialog is not None and self._analysis_dialog.isVisible():
            return True
        return False

    def _get_config_for_metrics(self) -> Dict[str, Any]:
        config = self._app_state.ui_config.copy()
        if self._settings_port:
            anonymization = self._settings_port.load_anonymization_settings()
            if anonymization:
                config["anonymization"] = anonymization
        return config

    def _connect_signals(self):
        self._view.recalculate_clicked.connect(self.on_recalculate_clicked)
        self._view.calendar_button_clicked.connect(self.on_calendar_clicked)
        self._view.diagram_button_clicked.connect(self.on_diagram_clicked)

    def on_recalculate_clicked(self):
        if not self._app_state.has_chat_loaded():
            self._view.show_status(message_key="Please load a JSON file first.", is_error=True)
            return

        if self._app_state.is_processing:
            return

        self.set_processing_state_in_view(True)

        preferred = self._app_state.get_preferred_analysis_unit()
        if (
            preferred == "tokens"
            and self._app_state.tokenizer is None
            and self._tokenizer_service is not None
        ):
            try:
                tokenizer = self._tokenizer_service.load_default_tokenizer(progress_callback=None)
                if tokenizer is not None:
                    self._app_state.set_tokenizer(
                        tokenizer,
                        self._tokenizer_service.get_default_model_name(),
                    )
                    logger.debug("analysis_unit: loaded default tokenizer for token analysis")
            except Exception:
                pass

        use_tokens = (
            self._app_state.tokenizer is not None
            and preferred == "tokens"
        )
        logger.debug(
            "analysis_unit run_analysis: tokenizer=%s, get_preferred_analysis_unit()=%r -> use_tokens=%s",
            self._app_state.tokenizer is not None,
            preferred,
            use_tokens,
        )
        worker = AnalysisWorker(
            self._analysis_service,
            self._app_state.loaded_chat,
            self._get_config_for_metrics(),
            self._app_state.tokenizer if use_tokens else None,
            disabled_dates=set(),
        )
        worker.signals.finished.connect(
            lambda s, m, r, w=worker: self._on_analysis_finished(s, m, r, w)
        )

        self._current_workers.append(worker)
        self._threadpool.start(worker)

    def _on_analysis_finished(
        self,
        success: bool,
        message: str,
        result: Optional[AnalysisResult],
        worker=None,
    ):
        try:
            self.set_processing_state_in_view(False)

            if success and result:
                self._app_state.set_analysis_result(result)

                tree = self._analysis_service.build_analysis_tree(result, self._app_state.ui_config)
                self._app_state.set_analysis_tree(tree)

                count = self._app_state.get_filtered_count()
                self.analysis_count_updated.emit(count, self._app_state.last_analysis_unit, False)
                self.analysis_completed.emit(tree)
                if self._app_state.has_disabled_nodes():
                    restored = self._app_state.get_disabled_nodes_from_tree(tree)
                    self.disabled_nodes_changed.emit(restored)
                else:
                    self.disabled_nodes_changed.emit(set())
            else:

                error_message = f"Analysis error: {message}" if message else "Analysis failed or no data found."
                self._view.show_status(
                    message=error_message,
                    is_error=True
                )
                self.analysis_count_updated.emit(-1, "chars", False)
        finally:
            if worker is not None:
                try:
                    self._current_workers.remove(worker)
                except ValueError:
                    pass

    def on_diagram_clicked(self):
        if self._app_state.is_processing:
            return

        if not self._app_state.has_chat_loaded():
            self._view.show_status(message_key="Please load a JSON file first.", is_error=True)
            return

        if not self._app_state.has_analysis_data():
            self._view.show_message_box(
                tr("analysis.title"),
                tr("analysis.recalc_first"),
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
            worker.signals.finished.connect(
                lambda s, m, r, w=worker: self._on_tree_build_finished(s, m, r, w)
            )

            self._current_workers.append(worker)
            self._threadpool.start(worker)
        else:
            self._show_analysis_dialog()

    def _on_tree_build_finished(
        self,
        success: bool,
        message: str,
        result: Optional[TreeNode],
        worker=None,
    ):
        try:
            self.set_processing_state_in_view(False)

            if success and result:
                self._app_state.set_analysis_tree(result)
                self._show_analysis_dialog()
            else:
                self._view.show_status(message_key="Failed to build analysis tree", is_error=True)
        finally:
            if worker is not None:
                try:
                    self._current_workers.remove(worker)
                except ValueError:
                    pass

    def _show_analysis_dialog(self):
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
            self._analysis_dialog = self._view.create_analysis_dialog(
                presenter=self,
                theme_manager=self._theme_manager,
                chart_service=self._chart_service,
            )

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
                disabled_nodes = self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree)
                self._analysis_dialog.load_data_and_show(
                    root_node=self._app_state.analysis_tree,
                    initial_disabled_nodes=disabled_nodes,
                    unit=self._app_state.last_analysis_unit
                )
            self._analysis_dialog.show()

        except Exception as e:
            logger.exception("Error in _show_analysis_dialog: %s", e)

    def _handle_analysis_accepted(self):
        if self._analysis_dialog:
            final_disabled_nodes = self._analysis_dialog._get_nodes_from_ids(self._analysis_dialog.disabled_node_ids)
            self.update_disabled_nodes(final_disabled_nodes)
            if self._app_state.has_analysis_data():
                count = self._app_state.get_filtered_count()
                unit = self._app_state.last_analysis_unit
                self.analysis_count_updated.emit(count, unit, True)

    def _handle_calendar_accepted(self):
        if self._app_state.has_analysis_data():
            count = self._app_state.get_filtered_count()
            unit = self._app_state.last_analysis_unit
            self.analysis_count_updated.emit(count, unit, True)

    def on_calendar_clicked(self):
        if self._app_state.is_processing:
            return

        if not self._app_state.has_chat_loaded():
            self._view.show_status(message_key="Please load a JSON file first.", is_error=True)
            return

        if not self._app_state.has_analysis_data():
            self._view.show_message_box(
                tr("dialog.calendar.title_short"),
                tr("analysis.recalc_first"),
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
            worker.signals.finished.connect(
                lambda s, m, r, w=worker: self._on_calendar_tree_build_finished(s, m, r, w)
            )

            self._current_workers.append(worker)
            self._threadpool.start(worker)
        else:
            self._show_calendar_dialog()

    def _on_calendar_tree_build_finished(
        self,
        success: bool,
        message: str,
        result: Optional[TreeNode],
        worker=None,
    ):
        try:
            self.set_processing_state_in_view(False)

            if success and result:
                self._app_state.set_processing_state(False)
                self._app_state.set_analysis_tree(result)
                self._show_calendar_dialog()
            else:
                self._view.show_status(
                    tr("analysis.tree_build_failed"), is_error=True
                )
        finally:
            if worker is not None:
                try:
                    self._current_workers.remove(worker)
                except ValueError:
                    pass

    def _show_calendar_dialog(self):
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
            chat_id = chat_as_dict.get("id")

            config = self._get_config_for_metrics()
            unit = (
                self._app_state.analysis_result.unit
                if self._app_state.analysis_result
                else self._app_state.last_analysis_unit
            )
            token_hierarchy = self._analysis_service.get_full_date_hierarchy_for_calendar(
                chat=self._app_state.loaded_chat,
                config=config,
                tokenizer=self._app_state.tokenizer,
                unit=unit,
            )

            self._calendar_dialog = self._view.create_calendar_dialog(
                presenter=CalendarPresenter(
                    self._calendar_service,
                    self._chat_memory_service,
                ),
                messages=messages_dict,
                config=config,
                theme_manager=self._theme_manager,
                root_node=self._app_state.analysis_tree,
                initial_disabled_nodes=self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree),
                token_hierarchy=token_hierarchy,
                chat_id=chat_id if isinstance(chat_id, int) else None,
            )

            self._calendar_dialog.presenter.filter_changed.connect(self.update_disabled_nodes)
            self.disabled_nodes_changed.connect(self._calendar_dialog.presenter.set_disabled_nodes)
            self._calendar_dialog.memory_changed.connect(self.on_disabled_dates_changed)
            self._calendar_dialog.accepted.connect(self._handle_calendar_accepted)

            def disconnect_calendar_signals(result_code=None):
                try:
                    if self._calendar_dialog:
                        self._calendar_dialog.presenter.filter_changed.disconnect(self.update_disabled_nodes)
                        self.disabled_nodes_changed.disconnect(self._calendar_dialog.presenter.set_disabled_nodes)
                        self._calendar_dialog.memory_changed.disconnect(self.on_disabled_dates_changed)
                        self._calendar_dialog.accepted.disconnect(self._handle_calendar_accepted)
                except (TypeError, RuntimeError):
                    pass

            self._calendar_dialog.finished.connect(disconnect_calendar_signals)

            self._calendar_dialog.show()
        except Exception as e:
            self._view.show_status(message_key="Error opening calendar dialog", is_error=True)

    def update_disabled_nodes(self, new_disabled_set: Set[TreeNode]):
        old_disabled_set = self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree) if self._app_state.analysis_tree else set()

        if old_disabled_set != new_disabled_set:
            self._app_state.set_disabled_nodes(new_disabled_set)
            self.disabled_nodes_changed.emit(new_disabled_set)
            self._refresh_all_ui()

    def set_processing_state_in_view(self, is_processing: bool, message: str = "", message_key: str = None, format_args: dict = None):
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

        if not self._app_state.has_chat_loaded():
            return

        is_auto_recalc = self._app_state.get_config_value("auto_recalc", False)

        analysis_affecting_keys = [
            "profile", "show_service_notifications", "show_markdown",
            "show_links", "show_time", "show_reactions",
            "show_reaction_authors", "show_tech_info",
            "show_optimization", "streak_break_time",
            "my_name", "partner_name", "anonymization",
            "auto_recalc", "analysis_unit",
        ]

        if key not in analysis_affecting_keys:
            return

        if not is_auto_recalc and key != "auto_recalc":
            return

        try:
            preferred = self._app_state.get_preferred_analysis_unit()
            use_tokens = (
                self._app_state.tokenizer is not None
                and preferred == "tokens"
            )
            logger.debug(
                "analysis_unit on_config_value_changed: preferred=%r -> use_tokens=%s",
                preferred,
                use_tokens,
            )
            if use_tokens:
                result = self._analysis_service.calculate_token_stats(
                    self._app_state.loaded_chat,
                    self._get_config_for_metrics(),
                    self._app_state.tokenizer,
                    disabled_dates=set(),
                    include_memory_disabled_dates=False,
                )
            else:
                result = self._analysis_service.calculate_character_stats(
                    self._app_state.loaded_chat,
                    self._get_config_for_metrics(),
                    disabled_dates=set(),
                    include_memory_disabled_dates=False,
                )

            if self._app_state.analysis_tree:
                extended_result = self._extend_analysis_result_with_existing_tree(result, self._app_state.analysis_tree)
                tree = self._analysis_service.build_analysis_tree(
                    extended_result, self._app_state.ui_config
                )
            else:
                tree = self._analysis_service.build_analysis_tree(result, self._app_state.ui_config)

            self._app_state.set_analysis_result(result)
            self._app_state.set_analysis_tree(tree)

            self._refresh_all_ui_sync()

        except Exception as e:
            print(f"Error during auto-recalc: {e}")

    def _extend_analysis_result_with_existing_tree(self, new_result: AnalysisResult, existing_tree: TreeNode) -> AnalysisResult:
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

                if (year not in extended_hierarchy or
                    month not in extended_hierarchy.get(year, {}) or
                    day not in extended_hierarchy.get(year, {}).get(month, {})):
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
        )
        return extended_result

    def _refresh_all_ui(self):
        if not self._app_state.has_analysis_data():
            self.analysis_count_updated.emit(-1, "chars", False)
            return

        result = self._app_state.analysis_result
        tree = self._app_state.analysis_tree

        self.analysis_completed.emit(tree)

        filtered_count = self._app_state.get_filtered_count()
        self.analysis_count_updated.emit(filtered_count, self._app_state.last_analysis_unit, False)

    def _refresh_all_ui_sync(self):
        if not self._app_state.has_analysis_data():
            self.analysis_count_updated.emit(-1, "chars", False)
            return

        result = self._app_state.analysis_result
        tree = self._app_state.analysis_tree

        self.analysis_completed.emit(tree)

        filtered_count = self._app_state.get_filtered_count()
        self.analysis_count_updated.emit(filtered_count, self._app_state.last_analysis_unit, False)

    def on_disabled_dates_changed(self):
        if not self._app_state.has_analysis_data():
            return

        try:
            preferred = self._app_state.get_preferred_analysis_unit()
            use_tokens = (
                self._app_state.tokenizer is not None
                and preferred == "tokens"
            )
            logger.debug(
                "analysis_unit on_disabled_dates_changed: preferred=%r -> use_tokens=%s",
                preferred,
                use_tokens,
            )
            if use_tokens:
                result = self._analysis_service.calculate_token_stats(
                    self._app_state.loaded_chat,
                    self._get_config_for_metrics(),
                    self._app_state.tokenizer,
                    disabled_dates=set(),
                    include_memory_disabled_dates=False,
                )
            else:
                result = self._analysis_service.calculate_character_stats(
                    self._app_state.loaded_chat,
                    self._get_config_for_metrics(),
                    disabled_dates=set(),
                    include_memory_disabled_dates=False,
                )

            if self._app_state.analysis_tree:
                extended_result = self._extend_analysis_result_with_existing_tree(
                    result, self._app_state.analysis_tree
                )
                tree = self._analysis_service.build_analysis_tree(
                    extended_result, self._app_state.ui_config
                )
            else:
                tree = self._analysis_service.build_analysis_tree(
                    result, self._app_state.ui_config
                )

            self._app_state.set_analysis_result(result)
            self._app_state.set_analysis_tree(tree)
            self._refresh_all_ui_sync()
        except Exception as e:
            self._view.show_status(message_key="Error recalculating after date change", is_error=True)

    def apply_theme_to_open_dialogs(self, new_palette):
        for dialog_attr in ("_analysis_dialog", "_calendar_dialog"):
            dialog = getattr(self, dialog_attr, None)
            if not dialog:
                continue
            try:
                if dialog.isVisible():
                    self._theme_manager.apply_theme_to_dialog(dialog)
            except RuntimeError:
                setattr(self, dialog_attr, None)
