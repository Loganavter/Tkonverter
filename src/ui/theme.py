import logging
import os
import copy

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

theme_logger = logging.getLogger("ThemeManager")

LIGHT_THEME_PALETTE = {
    "Window": QColor("#ffffff"),
    "WindowText": QColor("#1f1f1f"),
    "Base": QColor("#ffffff"),
    "AlternateBase": QColor("#e1e1e1"),
    "ToolTipBase": QColor("#ffffff"),
    "ToolTipText": QColor("#1f1f1f"),
    "Text": QColor("#1f1f1f"),
    "Button": QColor("#e1e1e1"),
    "ButtonText": QColor("#1f1f1f"),
    "BrightText": QColor("#ff0000"),
    "Highlight": QColor("#0078D4"),
    "HighlightedText": QColor("#ffffff"),
    "accent": QColor("#0078D4"),
    "button.default.background": QColor("#ffffff"),
    "button.default.background.hover": QColor("#f8f8f8"),
    "button.default.background.pressed": QColor("#e9e9e9"),
    "button.default.border": QColor("#1E000000"),
    "button.default.bottom.edge": QColor("#32000000"),
    "button.delete.background": QColor("#26D93025"),
    "button.delete.background.hover": QColor("#4CD93025"),
    "button.delete.background.pressed": QColor("#4CD93025"),
    "button.delete.border": QColor("#66D93025"),
    "button.primary.background": QColor("#ffffff"),
    "button.primary.background.hover": QColor("#f8f8f8"),
    "button.primary.background.pressed": QColor("#e9e9e9"),
    "button.primary.border": QColor("#1E000000"),
    "button.primary.bottom.edge": QColor("#32000000"),
    "button.primary.text": QColor("#000000"),
    "input.border.thin": QColor("#2D000000"),
    "dialog.background": QColor("#ffffff"),
    "dialog.text": QColor("#1f1f1f"),
    "dialog.border": QColor("#c0c0c0"),
    "dialog.input.background": QColor("#ffffff"),
    "dialog.button.background": QColor("#e1e1e1"),
    "dialog.button.hover": QColor("#d8d8d8"),
    "dialog.button.ok.background": QColor("#0078D4"),
    "calendar.disabled.background": QColor("#fbe5e5"),

    "calendar.weekend.background": QColor("#f0f8ff"),

    "switch.track.off.border": QColor("#6E000000"),
    "switch.knob.off": QColor("#646464"),
    "switch.knob.on": QColor("#ffffff"),
    "switch.knob.border": QColor("#23000000"),
    "switch.text": QColor("#1f1f1f"),

    "help.nav.background": QColor("#f0f0f0"),
    "help.nav.border": QColor("#e0e0e0"),
    "help.nav.hover": QColor("#e8e8e8"),
    "help.nav.selected": QColor("#0078D4"),
    "help.nav.selected.text": QColor("#ffffff"),
}

DARK_THEME_PALETTE = {
    "Window": QColor("#2b2b2b"),
    "WindowText": QColor("#ffffff"),
    "Base": QColor("#3c3c3c"),
    "AlternateBase": QColor("#313131"),
    "ToolTipBase": QColor("#3c3c3c"),
    "ToolTipText": QColor("#ffffff"),
    "Text": QColor("#ffffff"),
    "Button": QColor("#3c3c3c"),
    "ButtonText": QColor("#ffffff"),
    "BrightText": QColor("#ff0000"),
    "Highlight": QColor("#0096FF"),
    "HighlightedText": QColor("#ffffff"),
    "accent": QColor("#0096FF"),
    "button.default.background": QColor("#3c3c3c"),
    "button.default.background.hover": QColor("#4a4a4a"),
    "button.default.background.pressed": QColor("#555555"),
    "button.default.border": QColor("#26FFFFFF"),
    "button.default.bottom.edge": QColor("#1EFFFFFF"),
    "button.delete.background": QColor("#33D93025"),
    "button.delete.background.hover": QColor("#66D93025"),
    "button.delete.background.pressed": QColor("#66D93025"),
    "button.delete.border": QColor("#80D93025"),
    "button.primary.background": QColor("#3c3c3c"),
    "button.primary.background.hover": QColor("#4a4a4a"),
    "button.primary.background.pressed": QColor("#555555"),
    "button.primary.border": QColor("#26FFFFFF"),
    "button.primary.bottom.edge": QColor("#1EFFFFFF"),
    "button.primary.text": QColor("#dfdfdf"),
    "input.border.thin": QColor("#3CFFFFFF"),
    "dialog.background": QColor("#2b2b2b"),
    "dialog.text": QColor("#ffffff"),
    "dialog.border": QColor("#888888"),
    "dialog.input.background": QColor("#3c3c3c"),
    "dialog.button.background": QColor("#3c3c3c"),
    "dialog.button.hover": QColor("#4f4f4f"),
    "dialog.button.ok.background": QColor("#0096FF"),
    "calendar.disabled.background": QColor("#5a3e3e"),

    "calendar.weekend.background": QColor("#353535"),

    "switch.track.off.border": QColor("#78FFFFFF"),
    "switch.knob.off": QColor("#B4B4B4"),
    "switch.knob.on": QColor("#ffffff"),
    "switch.knob.border": QColor("#5A000000"),
    "switch.text": QColor("#ffffff"),

    "help.nav.background": QColor("#313131"),
    "help.nav.border": QColor("#444"),
    "help.nav.hover": QColor("#404040"),
    "help.nav.selected": QColor("#0096FF"),
    "help.nav.selected.text": QColor("#ffffff"),
}

class ThemeManager(QObject):
    _instance = None
    theme_changed = pyqtSignal()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    def __init__(self):
        if ThemeManager._instance is not None:
            raise RuntimeError("ThemeManager is a singleton, use get_instance()")
        super().__init__()
        self._current_theme = None
        self._qss_template = ""
        self._load_qss_template()

    def _load_qss_template(self):
        from utils.paths import resource_path

        try:
            qss_path = resource_path("resources/styles/base.qss")
            if os.path.exists(qss_path):
                with open(qss_path, "r", encoding="utf-8") as f:
                    self._qss_template = f.read()
            else:
                self._qss_template = ""
        except Exception as e:
            self._qss_template = ""

    def set_theme(self, theme_name: str, app=None):
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QGuiApplication

        app_instance = app or QApplication.instance()

        effective_theme = theme_name
        if effective_theme == "auto":
            try:
                style_hints = QGuiApplication.styleHints()
                color_scheme = style_hints.colorScheme()
                effective_theme = (
                    "dark" if color_scheme == Qt.ColorScheme.Dark else "light"
                )
            except Exception as e:
                effective_theme = "light"

        new_theme = "dark" if effective_theme == "dark" else "light"

        if self._current_theme != new_theme:
            self._current_theme = new_theme
            if app_instance:
                self.apply_theme_to_app(app_instance)
            self.theme_changed.emit()
        elif not app_instance.styleSheet():
            self.apply_theme_to_app(app_instance)

    def apply_theme_to_app(self, app):
        """Applies theme to application."""

        palette_source = DARK_THEME_PALETTE if self.is_dark() else LIGHT_THEME_PALETTE
        palette_data = copy.deepcopy(palette_source)

        q_palette = QPalette()
        color_roles = {
            "Window": QPalette.ColorRole.Window,
            "WindowText": QPalette.ColorRole.WindowText,
            "Base": QPalette.ColorRole.Base,
            "AlternateBase": QPalette.ColorRole.AlternateBase,
            "ToolTipBase": QPalette.ColorRole.ToolTipBase,
            "ToolTipText": QPalette.ColorRole.ToolTipText,
            "Text": QPalette.ColorRole.Text,
            "Button": QPalette.ColorRole.Button,
            "ButtonText": QPalette.ColorRole.ButtonText,
            "BrightText": QPalette.ColorRole.BrightText,
            "Highlight": QPalette.ColorRole.Highlight,
            "HighlightedText": QPalette.ColorRole.HighlightedText,
        }

        for name, role in color_roles.items():
            if name in palette_data:

                color = QColor(palette_data[name])
                q_palette.setColor(role, color)

        app.setPalette(q_palette)

        processed_palette = {
            key: QColor(value) if isinstance(value, QColor) else value
            for key, value in palette_data.items()
        }

        if "accent" in processed_palette:
            accent_color = QColor(processed_palette["accent"])
            hover_color = (
                accent_color.lighter(115)
                if self.is_dark()
                else accent_color.darker(115)
            )
            processed_palette["accent.hover"] = hover_color

        current_qss = self._qss_template

        sorted_keys = sorted(processed_palette.keys(), key=len, reverse=True)

        for key in sorted_keys:
            color = processed_palette.get(key)
            if isinstance(color, QColor):
                placeholder = f"@{key}"
                if placeholder in current_qss:
                    color_hex = color.name(QColor.NameFormat.HexArgb)
                    current_qss = current_qss.replace(placeholder, color_hex)

        app.setStyleSheet(current_qss)

    def is_dark(self) -> bool:
        return self._current_theme == "dark"

    def apply_theme_to_dialog(self, dialog):

        dialog.style().unpolish(dialog)

        dialog.style().polish(dialog)

        dialog.updateGeometry()
        dialog.update()

    def get_color(self, key: str) -> QColor:
        palette = DARK_THEME_PALETTE if self.is_dark() else LIGHT_THEME_PALETTE

        color = QColor(palette.get(key, QColor("magenta")))
        return color
