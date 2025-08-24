import os
import logging
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication

from utils.paths import resource_path

logger = logging.getLogger("FontManager")

class FontManager(QObject):
    """Manager for managing application fonts."""

    _instance = None
    font_changed = pyqtSignal()

    @classmethod
    def get_instance(cls):
        """Get the single instance of FontManager."""
        if cls._instance is None:
            cls._instance = FontManager()
        return cls._instance

    def __init__(self):
        if FontManager._instance is not None:
            raise RuntimeError("FontManager is a singleton, use get_instance()")
        super().__init__()

        self._current_mode: str = "builtin"
        self._current_family: str = ""
        self._built_in_font_path = "resources/fonts/SourceSans3-Regular.ttf"
        self._built_in_family_cache: str | None = None

    def apply_from_settings(self, settings_manager):
        """Apply font settings from SettingsManager."""

        try:
            mode = settings_manager.load_ui_font_mode()
            family = settings_manager.load_ui_font_family()

            self.set_font(mode=mode, family=family)
        except Exception as e:
            logger.warning(f"Error applying font settings: {e}")

            self.set_font(mode="builtin", family="")

    def _ensure_builtin_loaded(self) -> str | None:
        """Loads built-in font and returns family name."""
        if self._built_in_family_cache:
            return self._built_in_family_cache

        try:
            path = resource_path(self._built_in_font_path)
            if os.path.exists(path):
                font_id = QFontDatabase.addApplicationFont(path)
                families = QFontDatabase.applicationFontFamilies(font_id) if font_id != -1 else []
                if families:
                    self._built_in_family_cache = families[0]
                    return self._built_in_family_cache
        except Exception as e:
            logger.error(f"Error loading built-in font: {e}")
        return None

    def set_font(self, mode: str, family: str = ""):
        """
        Sets application font.

        Args:
            mode: Font mode ('builtin', 'system_default', 'system_custom')
            family: Font family (for system_custom)
        """

        if mode == "system":
            mode = "system_default"
        if mode not in ("builtin", "system_default", "system_custom"):
            logger.warning(f"Unknown mode '{mode}', using 'builtin'")
            mode = "builtin"

        self._current_mode = mode
        self._current_family = family or ""

        app = QApplication.instance()
        if not app:
            logger.warning("QApplication not found")
            return

        try:
            new_font = None
            if mode == "builtin":
                final_family = self._ensure_builtin_loaded()
                if final_family:
                    new_font = QFont(final_family)
                    app.setFont(new_font)
                else:
                    new_font = QFont()
                    app.setFont(new_font)

            elif mode == "system_default":
                try:
                    new_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
                    app.setFont(new_font)
                except Exception as e:
                    logger.warning(f"Error getting system font: {e}")
                    new_font = QFont()
                    app.setFont(new_font)

            else:
                final_family = self._current_family or ""
                if final_family:
                    new_font = QFont(final_family)
                    app.setFont(new_font)
                else:
                    new_font = QFont()
                    app.setFont(new_font)

            self._force_widget_update(app)
            self.font_changed.emit()

        except Exception as e:
            logger.error(f"Error setting font: {e}")
            fallback_font = QFont()
            app.setFont(fallback_font)

    def _force_widget_update(self, app):
        """Force update all widgets to apply new font."""
        try:
            widgets = app.allWidgets()
            new_app_font = app.font()

            for widget in widgets:
                if widget:
                    try:
                        widget.setFont(new_app_font)
                        widget.style().unpolish(widget)
                        widget.style().polish(widget)
                        widget.update()
                        widget.updateGeometry()
                    except Exception as widget_error:
                        pass
        except Exception as e:
            logger.warning(f"Error during forced widget update: {e}")

    def get_current_mode(self) -> str:
        """Get current font mode."""
        return self._current_mode

    def get_current_family(self) -> str:
        """Get current font family."""
        return self._current_family

    def get_builtin_family(self) -> str | None:
        """Get built-in font name."""
        return self._ensure_builtin_loaded()

    def is_builtin_available(self) -> bool:
        """Check if built-in font is available."""
        return self._ensure_builtin_loaded() is not None
