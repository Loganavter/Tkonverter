from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFontDatabase, QMouseEvent
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QVBoxLayout, QButtonGroup, QLineEdit, QWidget
)

import logging

from resources.translations import tr
from ui.dialogs.dialog_builder import auto_size_dialog, setup_dialog_scaffold, setup_dialog_icon
from ui.widgets.atomic.fluent_radio import FluentRadioButton
from ui.widgets.atomic.fluent_spinbox import FluentSpinBox
from ui.widgets.atomic.fluent_checkbox import FluentCheckBox
from ui.widgets.atomic.custom_group_widget import CustomGroupBuilder

settings_logger = logging.getLogger("SettingsDialog")

class SettingsDialog(QDialog):

    def __init__(self, current_theme, current_language, parent=None, current_ui_font_mode="builtin", current_ui_font_family="", current_truncate_name_length=20, current_truncate_quote_length=50, current_auto_detect_profile=True, current_auto_recalc=False):
        super().__init__(parent)

        self.setObjectName("SettingsDialog")

        setup_dialog_icon(self)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setSizeGripEnabled(True)
        self.setMinimumWidth(350)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        lang_layout = QHBoxLayout()
        self.lang_label = QLabel()
        self.combo_lang = QComboBox()

        self.combo_lang.addItem("", "ru")
        self.combo_lang.addItem("", "en")
        lang_index_to_set = self.combo_lang.findData(current_language)
        if lang_index_to_set != -1:
            self.combo_lang.setCurrentIndex(lang_index_to_set)
        lang_layout.addWidget(self.lang_label)
        lang_layout.addWidget(self.combo_lang, 1)
        main_layout.addLayout(lang_layout)

        theme_layout = QHBoxLayout()
        self.theme_label = QLabel()
        self.combo_theme = QComboBox()

        self.combo_theme.addItem("", "auto")
        self.combo_theme.addItem("", "light")
        self.combo_theme.addItem("", "dark")

        theme_index_to_set = self.combo_theme.findData(current_theme)
        if theme_index_to_set != -1:
            self.combo_theme.setCurrentIndex(theme_index_to_set)

        theme_layout.addWidget(self.theme_label)
        theme_layout.addWidget(self.combo_theme, 1)
        main_layout.addLayout(theme_layout)

        font_group, font_layout, self.font_group_title = CustomGroupBuilder.create_styled_group(tr("UI Font"))

        self.radio_font_builtin = FluentRadioButton()
        self.radio_font_system_default = FluentRadioButton()
        self.radio_font_system_custom = FluentRadioButton()

        self._font_mode_group = QButtonGroup(self)
        self._font_mode_group.addButton(self.radio_font_builtin)
        self._font_mode_group.addButton(self.radio_font_system_default)
        self._font_mode_group.addButton(self.radio_font_system_custom)

        font_layout.addWidget(self.radio_font_builtin)
        font_layout.addWidget(self.radio_font_system_default)
        font_layout.addWidget(self.radio_font_system_custom)

        self.combo_font_family = QComboBox()
        families = QFontDatabase.families()

        self.combo_font_family.addItem("", "")
        for family in families:
            self.combo_font_family.addItem(family, family)
        font_layout.addWidget(self.combo_font_family)

        main_layout.addWidget(font_group)

        mode = current_ui_font_mode or "builtin"
        if mode == "system_default" or mode == "system":
            self.radio_font_system_default.setChecked(True)
        elif mode == "system_custom":
            self.radio_font_system_custom.setChecked(True)
        else:
            self.radio_font_builtin.setChecked(True)

        idx_family = self.combo_font_family.findData(current_ui_font_family or "")
        if idx_family != -1:
            self.combo_font_family.setCurrentIndex(idx_family)

        def _sync_font_family_visibility():
            is_custom = self.radio_font_system_custom.isChecked()
            self.combo_font_family.setEnabled(is_custom)
            self.combo_font_family.setVisible(is_custom)

        _sync_font_family_visibility()
        self.radio_font_system_custom.toggled.connect(_sync_font_family_visibility)
        self.radio_font_builtin.toggled.connect(_sync_font_family_visibility)
        self.radio_font_system_default.toggled.connect(_sync_font_family_visibility)

        truncation_group, truncation_layout, self.truncation_group_title = CustomGroupBuilder.create_styled_group(tr("Truncation length"))

        name_length_layout = QHBoxLayout()
        self.label_name_length = QLabel()
        self.spin_name_length = FluentSpinBox()
        self.spin_name_length.setRange(1, 100)
        self.spin_name_length.setValue(current_truncate_name_length)
        name_length_layout.addWidget(self.label_name_length)
        name_length_layout.addStretch()
        name_length_layout.addWidget(self.spin_name_length)
        truncation_layout.addLayout(name_length_layout)

        quote_length_layout = QHBoxLayout()
        self.label_quote_length = QLabel()
        self.spin_quote_length = FluentSpinBox()
        self.spin_quote_length.setRange(1, 200)
        self.spin_quote_length.setValue(current_truncate_quote_length)
        quote_length_layout.addWidget(self.label_quote_length)
        quote_length_layout.addStretch()
        quote_length_layout.addWidget(self.spin_quote_length)
        truncation_layout.addLayout(quote_length_layout)

        main_layout.addWidget(truncation_group)

        self.checkbox_auto_detect_profile = FluentCheckBox()
        self.checkbox_auto_detect_profile.setChecked(current_auto_detect_profile)
        main_layout.addWidget(self.checkbox_auto_detect_profile)

        self.checkbox_auto_recalc = FluentCheckBox()
        self.checkbox_auto_recalc.setChecked(current_auto_recalc)
        main_layout.addWidget(self.checkbox_auto_recalc)

        main_layout.addStretch(1)

        setup_dialog_scaffold(self, main_layout, ok_text="", cancel_text="")

        self.retranslate_ui()

        auto_size_dialog(self, min_width=350, min_height=200)

    def mousePressEvent(self, event: QMouseEvent):
        """Removes focus from input fields when clicking on empty area."""
        self.clear_input_focus()
        super().mousePressEvent(event)

    def get_theme(self):
        theme = self.combo_theme.currentData()
        return theme

    def get_language(self):
        language = self.combo_lang.currentData()
        return language

    def get_font_settings(self):
        """Get font settings."""
        if self.radio_font_system_default.isChecked():
            ui_font_mode = "system_default"
        elif self.radio_font_system_custom.isChecked():
            ui_font_mode = "system_custom"
        else:
            ui_font_mode = "builtin"

        ui_font_family = self.combo_font_family.currentData() or ""

        return ui_font_mode, ui_font_family

    def get_truncation_settings(self):
        """Get truncation settings."""
        return {
            "truncate_name_length": self.spin_name_length.value(),
            "truncate_quote_length": self.spin_quote_length.value(),
        }

    def get_auto_detect_profile(self):
        """Get auto-detect profile setting."""
        return self.checkbox_auto_detect_profile.isChecked()

    def get_auto_recalc(self):
        """Get automatic recalculation setting."""
        return self.checkbox_auto_recalc.isChecked()

    def retranslate_ui(self):
        """Updates all texts in dialog when language changes."""
        self.setWindowTitle(tr("Settings"))
        self.lang_label.setText(tr("Language:"))
        self.combo_lang.setItemText(0, tr("Russian"))
        self.combo_lang.setItemText(1, tr("English"))
        self.theme_label.setText(tr("Theme:"))
        self.combo_theme.setItemText(0, tr("Auto"))
        self.combo_theme.setItemText(1, tr("Light"))
        self.combo_theme.setItemText(2, tr("Dark"))
        self.font_group_title.setText(tr("UI Font"))
        self.radio_font_builtin.setText(tr("Built-in font"))
        self.radio_font_system_default.setText(tr("System default"))
        self.radio_font_system_custom.setText(tr("Custom"))
        self.combo_font_family.setItemText(0, tr("Select font..."))
        self.truncation_group_title.setText(tr("Truncation length"))
        self.label_name_length.setText(tr("Nicknames:"))
        self.label_quote_length.setText(tr("Quotes in replies:"))
        self.checkbox_auto_detect_profile.setText(tr("Auto-detect profile"))
        self.checkbox_auto_recalc.setText(tr("Automatic recalculation"))
        self.ok_button.setText(tr("OK"))
        self.cancel_button.setText(tr("Cancel"))

    def clear_input_focus(self):
        """Removes focus from any input field in dialog."""
        focused_widget = self.focusWidget()
        if focused_widget and isinstance(focused_widget, (QLineEdit, QWidget)) and focused_widget.inherits("QLineEdit"):
            focused_widget.clearFocus()

    def refresh_theme_styles(self):
        """Forces dialog styles to update."""

        self.style().unpolish(self)
        self.style().polish(self)
        self.updateGeometry()
        self.update()

