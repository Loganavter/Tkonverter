import logging
from typing import Optional, Set, Dict, Any

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

from core.analysis.tree_analyzer import TreeNode
from core.application.analysis_service import AnalysisService
from core.application.chat_service import ChatService
from core.conversion.domain_adapters import chat_to_dict
from core.domain.models import AnalysisResult, Chat
from presenters.app_state import AppState
from presenters.workers import AnalysisWorker, TreeBuildWorker
from resources.translations import tr

logger = logging.getLogger(__name__)

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
        )
        worker.signals.finished.connect(self._on_analysis_finished)

        self._current_workers.append(worker)
        self._threadpool.start(worker)

    def _on_analysis_finished(self, success: bool, message: str, result: Optional[AnalysisResult]):
        """Handles analysis completion."""
        self.set_processing_state_in_view(False)

        if success and result:
            self._app_state.set_analysis_result(result)
            self.analysis_count_updated.emit(result.total_count, result.unit)
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
        from ui.dialogs.analysis.analysis_dialog import AnalysisDialog

        if self._analysis_dialog is not None:
            try:
                self._analysis_dialog.accepted.disconnect(self._handle_analysis_accepted)
                self.disabled_nodes_changed.disconnect(self._analysis_dialog.presenter.view.on_external_update)
            except (TypeError, RuntimeError):
                pass
            try:
                self._analysis_dialog.close()
            except RuntimeError:
                pass
            self._analysis_dialog = None

        try:
            from presenters.analysis_presenter import AnalysisPresenter
            analysis_presenter = AnalysisPresenter()
            self._analysis_dialog = analysis_presenter.get_view(parent=self._view)

            self._analysis_dialog.accepted.connect(self._handle_analysis_accepted)
            self.disabled_nodes_changed.connect(analysis_presenter.view.on_external_update)

            def disconnect_analysis_signals(result_code=None):
                try:
                    if self._analysis_dialog:
                        self.disabled_nodes_changed.disconnect(self._analysis_dialog.on_external_update)
                        self._analysis_dialog.accepted.disconnect(self._handle_analysis_accepted)
                except (TypeError, RuntimeError):
                    pass

            self._analysis_dialog.finished.connect(disconnect_analysis_signals)

            if self._app_state.analysis_tree:
                analysis_presenter.load_analysis_data(
                    root_node=self._app_state.analysis_tree,
                    initial_disabled_nodes=self._app_state.disabled_time_nodes,
                    unit=self._app_state.last_analysis_unit
                )
            self._analysis_dialog.show()

        except Exception as e:
            logger.error(f"Error opening analysis dialog: {e}")

    def _handle_analysis_accepted(self):
        """Handles analysis dialog confirmation."""
        if self._analysis_dialog:
            final_disabled_nodes = self._analysis_dialog.disabled_nodes
            self.update_disabled_nodes(final_disabled_nodes)
        else:
            logger.warning("[AnalysisPresenter] _handle_analysis_accepted called, but _analysis_dialog is None")

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
        from ui.dialogs.calendar import CalendarDialog

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
                presenter=self,
                messages=messages_dict,
                config=self._app_state.ui_config.copy(),
                theme_manager=self._theme_manager,
                root_node=self._app_state.analysis_tree,
                initial_disabled_nodes=self._app_state.disabled_time_nodes,
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
            logger.exception(f"Error opening calendar dialog: {e}")
            self._view.show_status(message_key="Error opening calendar dialog", is_error=True)

    def update_disabled_nodes(self, new_disabled_set: Set[TreeNode]):
        """Updates disabled nodes."""
        old_disabled_set = self._app_state.disabled_time_nodes.copy()
        if old_disabled_set != new_disabled_set:
            self._app_state.set_disabled_nodes(new_disabled_set)
            self.disabled_nodes_changed.emit(new_disabled_set)

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
            logger.warning("View does not have set_processing_state method")

    def get_analysis_stats(self) -> Optional[Dict[str, int]]:
        """Returns analysis statistics considering filtering."""
        if not self._app_state.analysis_result:
            return None

        total_count = self._app_state.analysis_result.total_count

        if self._app_state.analysis_tree and self._app_state.disabled_time_nodes:
            filtered_count = self._calculate_filtered_count()
        else:
            filtered_count = total_count

        return {
            "total_count": total_count,
            "filtered_count": filtered_count,
            "disabled_count": total_count - filtered_count,
        }

    def _calculate_filtered_count(self) -> int:
        """Calculates the number of tokens/characters after filtering."""
        if not self._app_state.analysis_tree:
            return 0

        return self._calculate_tree_value_excluding_disabled(
            self._app_state.analysis_tree
        )

    def _calculate_tree_value_excluding_disabled(self, node) -> int:
        """Recursively calculates the value of the tree, excluding disabled nodes."""
        if not isinstance(node, TreeNode):
            return 0

        if node in self._app_state.disabled_time_nodes:
            return 0

        if node.children:
            total = 0
            for child in node.children:
                total += self._calculate_tree_value_excluding_disabled(child)
            return total
        else:
            return node.value
