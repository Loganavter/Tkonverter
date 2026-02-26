from typing import Optional

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from src.core.application.chat_service import ChatService
from src.core.domain.models import Chat
from src.presenters.app_state import AppState
from src.presenters.workers import ChatLoadWorker

def tr(key: str) -> str:
    return key

class FilePresenter(QObject):

    chat_loaded = pyqtSignal(bool, str, str)
    profile_auto_detected = pyqtSignal(str)
    preview_updated = pyqtSignal(str, str)
    set_drop_zone_style_command = pyqtSignal(str)
    analysis_count_updated = pyqtSignal(int, str)

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
        pass

    def on_file_dropped(self, path: str):
        if self._app_state.is_processing:
            return

        self._app_state.clear_chat()
        self._app_state.clear_analysis()

        if hasattr(self, 'analysis_count_updated'):
            self.analysis_count_updated.emit(-1, "chars")

        self.set_processing_state_in_view(True)

        worker = ChatLoadWorker(self._chat_service, path)
        worker.signals.progress.connect(self._view.show_status)
        worker.signals.finished.connect(
            lambda s, m, r, fp, w=worker: self._on_chat_load_finished(s, m, r, fp, w)
        )

        self._current_workers.append(worker)
        self._threadpool.start(worker)

    def _on_chat_load_finished(
        self,
        success: bool,
        message: str,
        result: Optional[Chat],
        file_path: str = "",
        worker=None,
    ):
        try:
            self.set_processing_state_in_view(False)

            if success and result:
                auto_detect_enabled = self._app_state.get_config_value("auto_detect_profile", True)

                if auto_detect_enabled:
                    detected_profile = self._chat_service.detect_chat_type(result)
                    current_profile = self._app_state.get_config_value("profile")

                    if detected_profile != current_profile:
                        self._app_state.set_config_value("profile", detected_profile)
                        self.profile_auto_detected.emit(detected_profile)

                        if detected_profile == "personal":

                            chat_stats = self._chat_service.get_chat_statistics(result)

                path_for_state = file_path if file_path else self._chat_service.get_current_file_path()
                self._app_state.set_chat(result, path_for_state)

            if auto_detect_enabled:
                self._update_preview()

                chat_name = self._app_state.get_chat_name()
                self.chat_loaded.emit(True, "", chat_name)

            else:
                self.chat_loaded.emit(False, message, "")
        finally:
            if worker is not None:
                try:
                    self._current_workers.remove(worker)
                except ValueError:
                    pass

    def _update_preview(self):
        try:
            config = self._app_state.ui_config
            raw_text, title = self._preview_service.generate_preview_text(config)
            self.preview_updated.emit(raw_text, title)
        except Exception as e:
            error_message = f"Error: {e}"
            self.preview_updated.emit(error_message, "Preview Error")

    def on_drop_zone_hover_state_changed(self, is_hovered: bool):
        if self._is_drop_zone_drag_active:
            self._is_drop_zone_drag_active = False

        self._is_drop_zone_hovered = is_hovered
        self._update_drop_zone_style()

    def on_drop_zone_drag_active(self, is_active: bool):
        self._is_drop_zone_drag_active = is_active
        self._update_drop_zone_style()

    def _update_drop_zone_style(self):
        if self._is_drop_zone_drag_active:
            self.set_drop_zone_style_command.emit(
                "border: 2px solid #0078d4; background-color: rgba(0, 120, 212, 0.1); border-radius: 10px; padding: 15px; font-size: 14px;"
            )
        else:
            self.set_drop_zone_style_command.emit("border: 2px dashed #aaa; border-radius: 10px; padding: 15px; font-size: 14px;")

    def set_processing_state_in_view(self, is_processing: bool, message: str = "", message_key: str = None, format_args: dict = None):
        if message_key:
            from src.resources.translations import tr
            translated_message = tr(message_key)
            self._app_state.set_processing_state(is_processing, translated_message)
        else:
            self._app_state.set_processing_state(is_processing, message)

        if hasattr(self._view, 'set_processing_state'):
            self._view.set_processing_state(is_processing, None, message_key, format_args)
        else:
            pass

    def get_current_file_path(self) -> Optional[str]:
        return self._chat_service.get_current_file_path()

    def has_chat_loaded(self) -> bool:
        return self._app_state.has_chat_loaded()

    def get_current_chat(self) -> Optional[Chat]:
        return self._app_state.loaded_chat
