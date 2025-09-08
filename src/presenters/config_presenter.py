import logging
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from presenters.app_state import AppState

logger = logging.getLogger(__name__)

class ConfigPresenter(QObject):
    """Presenter for managing configuration panel (Profile, Names, Options)."""

    config_changed = pyqtSignal(str, object)
    profile_auto_detected = pyqtSignal(str)
    analysis_unit_changed = pyqtSignal(str)
    preview_updated = pyqtSignal(str, str)

    def __init__(self, view, app_state: AppState, preview_service):
        super().__init__()
        self._view = view
        self._app_state = app_state
        self._preview_service = preview_service

        self._connect_signals()

    def _connect_signals(self):
        """Connects UI signals to presenter methods."""
        self._view.config_changed.connect(self.on_config_changed)

    def on_config_changed(self, key: str, value: Any):
        """Handles configuration changes."""
        old_value = self._app_state.get_config_value(key)

        if old_value != value:
            had_analysis_data_before = self._app_state.has_analysis_data()

            self._app_state.set_config_value(key, value)

            self.config_changed.emit(key, value)

            if not self._app_state.has_analysis_data():
                if had_analysis_data_before:
                    unit = self._app_state.get_preferred_analysis_unit()
                    if unit == "tokens":
                        self._view.show_status(message_key="Tokens reset", is_status=True)
                    else:
                        self._view.show_status(message_key="Characters reset", is_status=True)

            if key not in ["disabled_nodes"]:
                self._update_preview()

            if (self._app_state.get_config_value("auto_recalc", False) and
                self._app_state.has_chat_loaded() and
                not self._app_state.is_processing and
                key not in ["auto_detect_profile", "auto_recalc", "disabled_nodes"]):

                self.config_changed.emit("auto_recalc_triggered", True)

    def _update_preview(self):
        """Updates preview when configuration changes."""
        try:
            config = self._app_state.ui_config
            raw_text, title = self._preview_service.generate_preview_text(config)
            self.preview_updated.emit(raw_text, title)
        except Exception as e:
            logger.error(f"Error updating preview: {e}")
            error_message = f"Error: {e}"
            self.preview_updated.emit(error_message, "Preview Error")

    def handle_profile_auto_detection(self, detected_profile: str):
        """Handles automatic profile detection."""
        current_profile = self._app_state.get_config_value("profile")

        if detected_profile != current_profile:
            self._app_state.set_config_value("profile", detected_profile)
            self.profile_auto_detected.emit(detected_profile)
            self._update_preview()

    def get_config(self) -> dict:
        """Returns a copy of the current configuration."""
        return self._app_state.ui_config.copy()

    def get_config_value(self, key: str) -> Any:
        """Returns a specific configuration value."""
        return self._app_state.get_config_value(key)

    def set_config_value(self, key: str, value: Any):
        """Sets a specific configuration value."""
        self._app_state.set_config_value(key, value)
        self.config_changed.emit(key, value)
