from typing import Any, Dict, Optional, Set

from PyQt6.QtCore import QObject, pyqtSignal

from src.core.analysis.tree_analyzer import TreeNode
from src.core.application.analysis_service import AnalysisService
from src.core.application.chat_service import ChatService
from src.core.application.conversion_service import ConversionService
from src.core.application.tokenizer_service import TokenizerService
from src.core.dependency_injection import DIContainer
from src.core.domain.models import AnalysisResult, Chat
from src.presenters.action_presenter import ActionPresenter
from src.presenters.analysis_presenter_extended import AnalysisPresenterExtended
from src.presenters.app_state import AppState
from src.presenters.config_presenter import ConfigPresenter
from src.presenters.file_presenter import FilePresenter
from src.presenters.preview_service import PreviewService
from src.resources.translations import tr

class MainPresenter(QObject):
    """Main presenter implementing Clean Architecture with service layer as a coordinator."""

    chat_loaded = pyqtSignal(bool, str, str)
    profile_auto_detected = pyqtSignal(str)
    config_changed = pyqtSignal(str, object)
    analysis_unit_changed = pyqtSignal(str)
    preview_updated = pyqtSignal(str, str)
    save_completed = pyqtSignal(bool, str)
    analysis_count_updated = pyqtSignal(int, str)
    analysis_completed = pyqtSignal(TreeNode)
    tokenizer_changed = pyqtSignal()
    tokenizer_loading_started = pyqtSignal(str)
    tokenizer_loaded = pyqtSignal(object, str)
    tokenizer_load_failed = pyqtSignal(str)
    disabled_nodes_changed = pyqtSignal(set)
    language_changed = pyqtSignal()

    set_drop_zone_style_command = pyqtSignal(str)

    def __init__(
        self,
        view,
        settings_manager,
        theme_manager,
        app_instance,
        di_container: DIContainer,
        initial_theme: str,
        initial_config: dict,
    ):
        super().__init__()

        self._view = view
        self._settings_manager = settings_manager
        self._theme_manager = theme_manager
        self._app = app_instance
        self._di_container = di_container

        self._current_session_theme = initial_theme

        self._app_state = AppState(ui_config=initial_config)

        self._chat_service = self._di_container.get(ChatService)
        self._conversion_service = self._di_container.get(ConversionService)
        self._analysis_service = self._di_container.get(AnalysisService)
        self._tokenizer_service = self._di_container.get(TokenizerService)

        self._preview_service = PreviewService()

        self._initialize_child_presenters()

        self._connect_signals()

        self._try_load_default_tokenizer()

        self._view.show_status(message_key="Ready to work", is_status=True)

    def _initialize_child_presenters(self):
        """Initialize all child presenters."""
        self.config_presenter = ConfigPresenter(
            self._view,
            self._app_state,
            self._preview_service
        )

        self.file_presenter = FilePresenter(
            self._view,
            self._app_state,
            self._chat_service,
            self._preview_service
        )

        self.analysis_presenter = AnalysisPresenterExtended(
            self._view,
            self._app_state,
            self._analysis_service,
            self._chat_service,
            self._theme_manager
        )

        self.action_presenter = ActionPresenter(
            self._view,
            self._app_state,
            self._conversion_service,
            self._tokenizer_service,
            self._settings_manager,
            self._theme_manager,
            self._app
        )

    def _connect_signals(self):
        """Connects signals between presenters and main presenter."""

        self.file_presenter.chat_loaded.connect(self.chat_loaded.emit)
        self.file_presenter.profile_auto_detected.connect(self.profile_auto_detected.emit)
        self.file_presenter.preview_updated.connect(self.preview_updated.emit)
        self.file_presenter.set_drop_zone_style_command.connect(self.set_drop_zone_style_command.emit)

        self.config_presenter.config_changed.connect(self.config_changed.emit)
        self.config_presenter.profile_auto_detected.connect(self.profile_auto_detected.emit)
        self.config_presenter.preview_updated.connect(self.preview_updated.emit)

        self.analysis_presenter.analysis_count_updated.connect(self.analysis_count_updated.emit)
        self.analysis_presenter.analysis_completed.connect(self.analysis_completed.emit)
        self.analysis_presenter.disabled_nodes_changed.connect(self.disabled_nodes_changed.emit)

        self.action_presenter.save_completed.connect(self.save_completed.emit)
        self.action_presenter.language_changed.connect(self.language_changed.emit)
        self.action_presenter.tokenizer_changed.connect(lambda: self._update_analysis_unit())
        self.action_presenter.tokenizer_changed.connect(self.tokenizer_changed.emit)

        self.config_presenter.config_changed.connect(self.analysis_presenter.on_config_value_changed_for_update)

        self._theme_manager.theme_changed.connect(self._on_app_theme_changed)

        self.config_presenter.config_changed.connect(self._handle_config_change_for_auto_recalc)

    def _handle_config_change_for_auto_recalc(self, key: str, value: Any):
        """Handles config changes that might trigger auto-recalculation."""
        if (key == "auto_recalc_triggered" and
            self._app_state.get_config_value("auto_recalc", False) and
            self._app_state.has_chat_loaded() and
            not self._app_state.is_processing):

            self.analysis_presenter.on_recalculate_clicked()

    def _try_load_default_tokenizer(self):
        """Attempts to load the default tokenizer ONLY from local cache."""
        if not self._tokenizer_service.is_transformers_available():
            return

        settings = self._settings_manager.load_ai_settings()
        load_on_startup = settings.get("load_on_startup", True)
        if not load_on_startup:
            return

        default_model = self._tokenizer_service.get_default_model_name()

        cache_info = self._tokenizer_service.check_model_cache(default_model)
        if not cache_info.get("available", False):
            return

        try:
            tokenizer = self._tokenizer_service.load_tokenizer(
                default_model, local_only=True, progress_callback=None
            )

            self._app_state.set_tokenizer(tokenizer, default_model)
            self._update_analysis_unit()
            self.tokenizer_changed.emit()

        except Exception as e:

            pass

    def _update_analysis_unit(self):
        """Updates the analysis unit based on tokenizer availability."""
        new_unit = self._app_state.get_preferred_analysis_unit()

        if self._app_state.last_analysis_unit != new_unit:
            self._app_state.last_analysis_unit = new_unit
            self.analysis_unit_changed.emit(new_unit)

    def _on_app_theme_changed(self):
        """Handles global application theme change."""
        new_palette = self._app.palette()

        self._view.setPalette(new_palette)
        self._view.refresh_theme_styles()

        for dialog in [self.action_presenter._settings_dialog,
                      self.action_presenter._export_dialog,
                      self.action_presenter._install_dialog,
                      self.action_presenter._help_dialog]:
            try:
                if dialog and dialog.isVisible():
                    dialog.setPalette(new_palette)

                    if hasattr(dialog, 'refresh_theme_styles'):
                        dialog.refresh_theme_styles()
                    else:
                        self._theme_manager.apply_theme_to_dialog(dialog)
            except RuntimeError as e:

                if dialog == self.action_presenter._settings_dialog:
                    self.action_presenter._settings_dialog = None
                elif dialog == self.action_presenter._export_dialog:
                    self.action_presenter._export_dialog = None
                elif dialog == self.action_presenter._install_dialog:
                    self.action_presenter._install_dialog = None
                elif dialog == self.action_presenter._help_dialog:
                    self.action_presenter._help_dialog = None

        for dialog in [self.analysis_presenter._analysis_dialog,
                      self.analysis_presenter._calendar_dialog]:
            try:
                if dialog and dialog.isVisible():
                    dialog.setPalette(new_palette)

                    if hasattr(dialog, 'refresh_theme_styles'):
                        dialog.refresh_theme_styles()
                    else:
                        self._theme_manager.apply_theme_to_dialog(dialog)
            except RuntimeError as e:
                if dialog == self.analysis_presenter._analysis_dialog:
                    self.analysis_presenter._analysis_dialog = None
                elif dialog == self.analysis_presenter._calendar_dialog:
                    self.analysis_presenter._calendar_dialog = None

        self.language_changed.emit()

    def get_longest_preview_html(self) -> str:
        """Generates HTML for the longest static example ('posts')."""
        return self._preview_service.get_longest_preview_html(self._app_state.ui_config)

    def get_current_chat(self) -> Optional[Chat]:
        """Returns the currently loaded chat."""
        return self._app_state.loaded_chat

    def get_analysis_result(self) -> Optional[AnalysisResult]:
        """Returns the analysis result."""
        return self._app_state.analysis_result

    def get_analysis_tree(self) -> Optional[TreeNode]:
        """Returns the analysis tree."""
        return self._app_state.analysis_tree

    def get_config(self) -> Dict[str, Any]:
        """Returns a copy of the current configuration."""
        return self._app_state.ui_config.copy()

    def get_disabled_nodes(self) -> Set[TreeNode]:
        """Returns a copy of disabled nodes."""
        return self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree) if self._app_state.analysis_tree else set()

    def has_chat_loaded(self) -> bool:
        """Checks if a chat is loaded."""
        return self._app_state.has_chat_loaded()

    def get_app_state(self) -> AppState:
        """Returns the application state (for complex dialogs)."""
        return self._app_state

    def get_current_file_path(self) -> Optional[str]:
        """Returns the path to the currently loaded file."""
        return self._chat_service.get_current_file_path()

    def update_disabled_nodes(self, new_disabled_set: Set[TreeNode]):
        """Updates disabled nodes."""
        self.analysis_presenter.update_disabled_nodes(new_disabled_set)

    def on_file_dropped(self, path: str):
        """Handles file drag-and-drop."""
        self.file_presenter.on_file_dropped(path)

    def on_drop_zone_hover_state_changed(self, is_hovered: bool):
        """Handles drop zone hover state changes."""
        self.file_presenter.on_drop_zone_hover_state_changed(is_hovered)

    def on_drop_zone_drag_active(self, is_active: bool):
        """Handles drop zone drag active state changes."""
        self.file_presenter.on_drop_zone_drag_active(is_active)

    def on_config_changed(self, key: str, value: Any):
        """Handles configuration changes."""
        self.config_presenter.on_config_changed(key, value)

    def handle_profile_auto_detection(self, detected_profile: str):
        """Handles automatic profile detection."""
        self.config_presenter.handle_profile_auto_detection(detected_profile)

    def on_recalculate_clicked(self):
        """Handles recalculate button click."""
        self.analysis_presenter.on_recalculate_clicked()

    def on_calendar_clicked(self):
        """Handles calendar button click."""
        self.analysis_presenter.on_calendar_clicked()

    def on_diagram_clicked(self):
        """Handles diagram button click."""
        self.analysis_presenter.on_diagram_clicked()

    def on_save_clicked(self):
        """Handles save button click."""
        self.action_presenter.on_save_clicked()

    def on_settings_clicked(self):
        """Handles settings button click."""
        self.action_presenter.on_settings_clicked()

    def on_install_manager_clicked(self):
        """Handles install manager button click."""
        self.action_presenter.on_install_manager_clicked()

    def on_help_clicked(self):
        """Handles help button click."""
        self.action_presenter.on_help_clicked()

    def _generate_preview(self):
        """Starts a preview generation using hardcoded data."""
        try:
            config = self._app_state.ui_config
            raw_text, title = self._preview_service.generate_preview_text(config)
            self.preview_updated.emit(raw_text, title)
        except Exception as e:
            error_message = f"Error: {e}"
            self.preview_updated.emit(error_message, "Preview Error")
