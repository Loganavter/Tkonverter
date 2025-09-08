import logging
from typing import Optional

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from core.application.chat_service import ChatService
from core.domain.models import Chat
from presenters.app_state import AppState
from presenters.workers import ChatLoadWorker

logger = logging.getLogger(__name__)

class FilePresenter(QObject):
    """Presenter for managing file loading and drop zone functionality."""

    chat_loaded = pyqtSignal(bool, str, str)
    profile_auto_detected = pyqtSignal(str)
    preview_updated = pyqtSignal(str, str)
    set_drop_zone_style_command = pyqtSignal(str)

    def __init__(self, view, app_state: AppState, chat_service: ChatService, preview_service):
        super().__init__()
        self._view = view
        self._app_state = app_state
        self._chat_service = chat_service
        self._preview_service = preview_service

        self._threadpool = QThreadPool()
        self._current_workers = []

        self._is_drop_zone_hovered = False
        self._is_drop_zone_drag_active = False

        self._connect_signals()

    def _connect_signals(self):
        """Connects UI signals to presenter methods."""

    def on_file_dropped(self, path: str):
        """Handles file drag-and-drop."""
        if self._app_state.is_processing:
            logger.warning("Application is already processing a file, ignoring new one")
            return

        self.set_processing_state_in_view(True, message_key="Loading file...")

        worker = ChatLoadWorker(self._chat_service, path)
        worker.signals.progress.connect(self._view.show_status)
        worker.signals.finished.connect(self._on_chat_load_finished)

        self._current_workers.append(worker)
        self._threadpool.start(worker)

    def _on_chat_load_finished(self, success: bool, message: str, result: Optional[Chat]):
        """Handles chat loading completion."""
        self.set_processing_state_in_view(False)

        if success and result:
            auto_detect_enabled = self._app_state.get_config_value("auto_detect_profile", True)

            if auto_detect_enabled:
                detected_profile = self._chat_service.detect_chat_type(result)
                current_profile = self._app_state.get_config_value("profile")

                if detected_profile != current_profile:
                    self._app_state.set_config_value("profile", detected_profile)
                    self.profile_auto_detected.emit(detected_profile)

            file_path = self._chat_service.get_current_file_path()
            self._app_state.set_chat(result, file_path)

            if auto_detect_enabled:
                self._update_preview()

            chat_name = self._app_state.get_chat_name()
            self.chat_loaded.emit(True, "", chat_name)

        else:
            self.chat_loaded.emit(False, message, "")

    def _update_preview(self):
        """Updates preview after file loading."""
        try:
            config = self._app_state.ui_config
            raw_text, title = self._preview_service.generate_preview_text(config)
            self.preview_updated.emit(raw_text, title)
        except Exception as e:
            logger.error(f"Error updating preview: {e}")
            error_message = f"Error: {e}"
            self.preview_updated.emit(error_message, "Preview Error")

    def on_drop_zone_hover_state_changed(self, is_hovered: bool):
        """Handles drop zone hover state changes."""
        if self._is_drop_zone_drag_active:
            self._is_drop_zone_drag_active = False

        self._is_drop_zone_hovered = is_hovered
        self._update_drop_zone_style()

    def on_drop_zone_drag_active(self, is_active: bool):
        """Handles drop zone drag active state changes."""
        self._is_drop_zone_drag_active = is_active
        self._update_drop_zone_style()

    def _update_drop_zone_style(self):
        """Updates drop zone style based on state."""
        if self._is_drop_zone_drag_active:
            self.set_drop_zone_style_command.emit(
                "border: 2px solid #0078d4; background-color: rgba(0, 120, 212, 0.1);"
            )
        else:
            self.set_drop_zone_style_command.emit("border: 2px dashed #aaa;")

    def set_processing_state_in_view(self, is_processing: bool, message: str = "", message_key: str = None, format_args: dict = None):
        """Proxy method for calling set_processing_state in view."""
        if message_key:
            from resources.translations import tr
            translated_message = tr(message_key)
            self._app_state.set_processing_state(is_processing, translated_message)
        else:
            self._app_state.set_processing_state(is_processing, message)

        if hasattr(self._view, 'set_processing_state'):
            self._view.set_processing_state(is_processing, None, message_key, format_args)
        else:
            logger.warning("View does not have set_processing_state method")

    def get_current_file_path(self) -> Optional[str]:
        """Returns the path to the currently loaded file."""
        return self._chat_service.get_current_file_path()

    def has_chat_loaded(self) -> bool:
        """Checks if a chat is loaded."""
        return self._app_state.has_chat_loaded()

    def get_current_chat(self) -> Optional[Chat]:
        """Returns the currently loaded chat."""
        return self._app_state.loaded_chat
