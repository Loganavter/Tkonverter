from PyQt6.QtCore import Qt, pyqtSignal, QSize, QEvent, QTimer
from PyQt6.QtGui import QIcon, QMouseEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from src.resources.translations import tr
from src.ui.dialogs.dialog_builder import auto_size_dialog, setup_dialog_scaffold, setup_dialog_icon
from src.ui.icon_manager import AppIcon, get_app_icon
from src.shared_toolkit.ui.widgets.atomic import FluentCheckBox
from src.shared_toolkit.ui.widgets.atomic import FluentComboBox

from src.core.domain.anonymization import LinkMaskMode
from src.shared_toolkit.ui.widgets.atomic import CustomGroupBuilder
from src.shared_toolkit.ui.widgets.atomic import CustomLineEdit
from src.shared_toolkit.ui.widgets.atomic import MinimalistScrollBar
from src.shared_toolkit.ui.widgets.atomic.simple_icon_button import SimpleIconButton
from src.shared_toolkit.ui.widgets.atomic.custom_button import CustomButton

class LinkListItem(QWidget):
    delete_clicked = pyqtSignal()

    def __init__(self, text: str, enabled: bool = True, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self.input_field = CustomLineEdit()
        self.input_field.setText(text)
        self.input_field.setPlaceholderText("domain.com")
        layout.addWidget(self.input_field, 1)

        self.checkbox = FluentCheckBox("")
        self.checkbox.setChecked(enabled)
        self.checkbox.setToolTip(tr("anonymization.enable_rule"))
        layout.addWidget(self.checkbox)

        self.delete_btn = SimpleIconButton(AppIcon.REMOVE, self)
        self.delete_btn.setFixedSize(28, 28)
        self.delete_btn.setIconSize(QSize(16, 16))
        self.delete_btn.setToolTip(tr("common.remove"))
        self.delete_btn.setProperty("class", "white-button")
        self.delete_btn.clicked.connect(self.delete_clicked.emit)

        layout.addWidget(self.delete_btn)

    def get_data(self) -> dict:

        return {
            "value": self.input_field.text().strip(),
            "enabled": self.checkbox.isChecked(),
            "is_regex": self.input_field.text().strip().startswith("[regex]")
        }

    def get_text(self) -> str:
        return self.input_field.text().strip()

class NameListItem(QWidget):
    delete_clicked = pyqtSignal()

    def __init__(self, text: str, enabled: bool, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self.input_field = CustomLineEdit()
        self.input_field.setText(text)
        self.input_field.setPlaceholderText(tr("common.name"))
        layout.addWidget(self.input_field, 1)

        self.checkbox = FluentCheckBox("")
        self.checkbox.setChecked(enabled)
        self.checkbox.setToolTip(tr("anonymization.enable_rule"))
        layout.addWidget(self.checkbox)

        self.delete_btn = SimpleIconButton(AppIcon.REMOVE, self)
        self.delete_btn.setFixedSize(28, 28)
        self.delete_btn.setIconSize(QSize(16, 16))
        self.delete_btn.setToolTip(tr("common.remove"))
        self.delete_btn.setProperty("class", "white-button")
        self.delete_btn.clicked.connect(self.delete_clicked.emit)

        layout.addWidget(self.delete_btn)

    def get_data(self) -> dict:
        return {
            "value": self.input_field.text().strip(),
            "enabled": self.checkbox.isChecked()
        }

class AnonymizationSettingsDialog(QDialog):

    def __init__(self, current_config: dict, settings_manager, known_names: list[str] = None, known_domains: list[str] = None, parent=None):
        super().__init__(parent)

        self.settings_manager = settings_manager
        self.current_config = current_config.copy()
        self.known_names = known_names or []
        self.known_domains = known_domains or []
        self._presets: list[dict] = []
        self._selected_preset_id: str | None = None
        self._editing_preset_id: str | None = None
        self._suppress_preset_change_tracking = False

        self.setObjectName("AnonymizationSettingsDialog")
        setup_dialog_icon(self)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setSizeGripEnabled(True)
        self.setMinimumWidth(500)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        self._anonymization_enabled = current_config.get("enabled", False)

        link_group, link_layout, self.link_group_title = CustomGroupBuilder.create_styled_group(
            tr("anonymization.link_filtering")
        )

        self.chk_hide_links = FluentCheckBox()
        self.chk_hide_links.setChecked(current_config.get("hide_links", False))
        self.chk_hide_links.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        link_layout.addWidget(self.chk_hide_links)

        preset_layout = QHBoxLayout()
        preset_label = QLabel(tr("anonymization.preset"))
        self.combo_presets = FluentComboBox()
        self.combo_presets.currentIndexChanged.connect(self._on_preset_combo_changed)
        self.input_preset_name = CustomLineEdit()
        self.input_preset_name.setVisible(False)
        self.input_preset_name.returnPressed.connect(self._save_preset_edit)
        self.btn_edit_preset = QPushButton(tr("common.edit"))
        self.btn_edit_preset.setFixedHeight(28)
        self.btn_edit_preset.setToolTip(tr("anonymization.edit_preset"))
        self.btn_edit_preset.clicked.connect(self._on_edit_preset_clicked)
        self.btn_delete_preset = SimpleIconButton(AppIcon.REMOVE, self)
        self.btn_delete_preset.setFixedSize(28, 28)
        self.btn_delete_preset.setIconSize(QSize(16, 16))
        self.btn_delete_preset.setToolTip(tr("anonymization.delete_preset"))
        self.btn_delete_preset.clicked.connect(self._delete_selected_preset)
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.combo_presets, 1)
        preset_layout.addWidget(self.input_preset_name, 1)
        preset_layout.addWidget(self.btn_edit_preset)
        preset_layout.addWidget(self.btn_delete_preset)
        link_layout.addLayout(preset_layout)

        mode_layout = QHBoxLayout()
        mode_label = QLabel(tr("anonymization.replacement_format"))
        self.combo_link_mode = FluentComboBox()
        self.combo_link_mode.addItem(tr("anonymization.simple_mask"), LinkMaskMode.SIMPLE.value)
        self.combo_link_mode.addItem(tr("anonymization.domain_only"), LinkMaskMode.DOMAIN_ONLY.value)
        self.combo_link_mode.addItem(tr("anonymization.indexed"), LinkMaskMode.INDEXED.value)
        self.combo_link_mode.addItem(tr("settings.font_custom"), LinkMaskMode.CUSTOM.value)

        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.combo_link_mode, 1)
        link_layout.addLayout(mode_layout)

        self.custom_link_format_container = QWidget()
        self.custom_link_format_container.setVisible(False)
        custom_format_layout = QHBoxLayout(self.custom_link_format_container)
        custom_format_layout.setContentsMargins(0, 0, 0, 0)
        self.input_link_format = CustomLineEdit()
        self.input_link_format.setPlaceholderText(tr("anonymization.use_index_placeholder"))
        self.input_link_format.textChanged.connect(self._on_preset_form_changed)
        custom_format_layout.addWidget(QLabel("  └ "), 0)
        custom_format_layout.addWidget(self.input_link_format, 1)
        link_layout.addWidget(self.custom_link_format_container)

        self.combo_link_mode.currentIndexChanged.connect(self._on_link_mode_changed)
        self.combo_link_mode.currentIndexChanged.connect(self._on_preset_form_changed)

        self.list_links = QListWidget()
        self.list_links.setObjectName("listLinks")
        self.list_links.setMaximumHeight(150)
        self.list_links.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_links.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.list_links.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list_links.setVerticalScrollBar(MinimalistScrollBar(Qt.Orientation.Vertical, self.list_links))

        self.list_links.viewport().installEventFilter(self)

        self.btn_add_link = CustomButton(get_app_icon(AppIcon.ADD), tr("Add Pattern"))
        self.btn_add_link.clicked.connect(self._on_add_link_clicked)
        self.btn_import_chat_rules = CustomButton(get_app_icon(AppIcon.ADD), tr("Import from chat"))
        self.btn_import_chat_rules.clicked.connect(self._on_import_chat_rules_clicked)
        self.btn_preset_action = CustomButton(get_app_icon(AppIcon.ADD), tr("Add Preset"))
        self.btn_preset_action.clicked.connect(self._on_preset_action_clicked)

        link_layout.addWidget(self.list_links)
        link_layout.addWidget(self.btn_add_link)

        self._clear_links_list()

        self._set_initial_link_values(current_config)

        self._populate_links_list_from_config(current_config)

        main_layout.addWidget(link_group)

        name_group, name_layout, self.name_group_title = CustomGroupBuilder.create_styled_group(
            tr("Name Anonymization")
        )

        self.chk_hide_names = FluentCheckBox()
        self.chk_hide_names.setChecked(current_config.get("hide_names", False))
        self.chk_hide_names.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.chk_hide_names.toggled.connect(self._update_names_list_state)
        self.chk_hide_links.toggled.connect(self._on_preset_form_changed)
        self.chk_hide_names.toggled.connect(self._on_preset_form_changed)

        name_layout.addWidget(self.chk_hide_names)

        name_format_layout = QHBoxLayout()
        name_format_label = QLabel(tr("Name format:"))
        self.input_name_format = CustomLineEdit()
        self.input_name_format.setText(current_config.get("name_mask_format", "[ИМЯ {index}]"))
        self.input_name_format.setPlaceholderText("[ИМЯ {index}]")
        self.input_name_format.textChanged.connect(self._on_preset_form_changed)
        name_format_layout.addWidget(name_format_label)
        name_format_layout.addWidget(self.input_name_format, 1)
        name_layout.addLayout(name_format_layout)

        self.list_names = QListWidget()
        self.list_names.setObjectName("listNames")
        self.list_names.setMaximumHeight(150)
        self.list_names.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_names.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.list_names.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list_names.setVerticalScrollBar(MinimalistScrollBar(Qt.Orientation.Vertical, self.list_names))

        self.list_names.viewport().installEventFilter(self)

        self.btn_add_name = CustomButton(get_app_icon(AppIcon.ADD), tr("Add Name Rule"))
        self.btn_add_name.clicked.connect(self._on_add_name_clicked)

        name_layout.addWidget(self.list_names)
        name_layout.addWidget(self.btn_add_name)

        self._populate_names_list()

        self._update_names_list_state(self.chk_hide_names.isChecked())

        main_layout.addWidget(name_group)

        preset_actions_group, preset_actions_layout, self.preset_actions_group_title = (
            CustomGroupBuilder.create_styled_group(tr("Preset actions"))
        )
        preset_actions_layout.addWidget(self.btn_import_chat_rules)
        preset_actions_layout.addWidget(self.btn_preset_action)
        main_layout.addWidget(preset_actions_group)

        main_layout.addStretch(1)

        setup_dialog_scaffold(self, main_layout, ok_text="", cancel_text="")

        self.retranslate_ui()
        self._apply_white_button_style()
        self._on_enable_toggled(self._anonymization_enabled)
        self._load_presets()
        self._update_preset_action_button()
        self._update_edit_button_state()

        auto_size_dialog(self, min_width=500, min_height=500)

    def _update_names_list_state(self, checked: bool):
        self.list_names.setEnabled(checked)
        self.btn_add_name.setEnabled(checked)
        self.input_name_format.setEnabled(checked)

        for i in range(self.list_names.count()):
            item = self.list_names.item(i)
            widget = self.list_names.itemWidget(item)
            if widget:
                widget.setEnabled(checked)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if source is self.list_links.viewport() or source is self.list_names.viewport():
                list_widget = self.list_links if source is self.list_links.viewport() else self.list_names
                index = list_widget.indexAt(event.pos())
                if not index.isValid():
                    self.clear_input_focus()

        return super().eventFilter(source, event)

    def _clear_names_list(self):

        while self.list_names.count() > 0:
            item = self.list_names.takeItem(0)
            if item:
                widget = self.list_names.itemWidget(item)
                if widget:
                    widget.deleteLater()
                del item

        self.list_names.clear()
        self.list_names.update()
        self.list_names.repaint()

    def _populate_names_list(self):

        self._clear_names_list()

        saved_names = self.current_config.get("custom_names", [])

        unique_names = {}

        for entry in saved_names:
            val = entry.get("value", "")
            if val:
                unique_names[val] = entry.get("enabled", True)

        for name in sorted(unique_names.keys()):
            enabled = unique_names[name]
            self._add_name_item(name, enabled)

    def _on_enable_toggled(self, enabled: bool):
        self.chk_hide_links.setEnabled(enabled)
        self.chk_hide_names.setEnabled(enabled)
        self._update_edit_button_state()
        self.combo_presets.setEnabled(enabled and self._editing_preset_id is None)
        self.input_preset_name.setEnabled(enabled and self._editing_preset_id is not None)
        self.btn_delete_preset.setEnabled(enabled and self._can_edit_selected_preset())
        self.btn_preset_action.setEnabled(enabled)
        self.list_links.setEnabled(enabled)
        self.btn_add_link.setEnabled(enabled)
        self.btn_import_chat_rules.setEnabled(enabled)

        names_enabled = enabled and self.chk_hide_names.isChecked()
        self._update_names_list_state(names_enabled)

        self.chk_hide_names.setEnabled(enabled)

    def _on_add_link_clicked(self):
        self._add_link_item("")
        self.list_links.scrollToBottom()
        item = self.list_links.item(self.list_links.count() - 1)
        widget = self.list_links.itemWidget(item)
        if widget:

            QTimer.singleShot(0, lambda: self._focus_and_reset_cursor(widget.input_field))

    def _clear_links_list(self):

        while self.list_links.count() > 0:
            item = self.list_links.takeItem(0)
            if item:
                widget = self.list_links.itemWidget(item)
                if widget:
                    widget.deleteLater()
                del item

        self.list_links.clear()
        self.list_links.update()
        self.list_links.repaint()

    def _populate_links_list_from_config(self, config: dict):
        unique_links = {}
        custom_filters = config.get("custom_filters", [])
        for f_dict in custom_filters:
            filter_type = f_dict.get("type", "domain")
            val = f_dict.get("value", "")
            enabled = f_dict.get("enabled", True)
            text_to_show = f"[regex] {val}" if filter_type == "regex" else val
            unique_links[text_to_show] = enabled

        self._clear_links_list()
        for text, enabled in unique_links.items():
            self._add_link_item(text, enabled)
        self._on_preset_form_changed()

    def _on_import_chat_rules_clicked(self):
        self._import_known_domains()
        self._import_known_names()

    def _import_known_domains(self):
        existing: set[str] = set()
        for i in range(self.list_links.count()):
            item = self.list_links.item(i)
            widget = self.list_links.itemWidget(item)
            if not widget:
                continue
            value = widget.get_text()
            if value:
                existing.add(value)

        for domain in self.known_domains:
            domain_value = str(domain).strip()
            if domain_value and domain_value not in existing:
                self._add_link_item(domain_value, enabled=False)
                existing.add(domain_value)

    def _import_known_names(self):
        existing: set[str] = set()
        for i in range(self.list_names.count()):
            item = self.list_names.item(i)
            widget = self.list_names.itemWidget(item)
            if not widget:
                continue
            value = str(widget.get_data().get("value", "")).strip()
            if value:
                existing.add(value)

        for name in self.known_names:
            name_value = str(name).strip()
            if name_value and name_value not in existing:
                self._add_name_item(name_value, enabled=False)
                existing.add(name_value)

    def _add_link_item(self, text: str, enabled: bool = True):
        item = QListWidgetItem()
        widget = LinkListItem(text, enabled)
        item.setSizeHint(widget.sizeHint())

        widget.delete_clicked.connect(lambda: self._remove_link_item(item))
        widget.input_field.textChanged.connect(self._on_preset_form_changed)
        widget.checkbox.toggled.connect(self._on_preset_form_changed)

        self.list_links.addItem(item)
        self.list_links.setItemWidget(item, widget)
        self._on_preset_form_changed()

    def _remove_link_item(self, item: QListWidgetItem):
        row = self.list_links.row(item)
        widget = self.list_links.itemWidget(item)
        self.list_links.takeItem(row)

        if widget:
            widget.deleteLater()
        self._on_preset_form_changed()

    def _on_add_name_clicked(self):
        self._add_name_item("", True)
        self.list_names.scrollToBottom()
        item = self.list_names.item(self.list_names.count() - 1)
        widget = self.list_names.itemWidget(item)
        if widget:

            QTimer.singleShot(0, lambda: self._focus_and_reset_cursor(widget.input_field))

    def _focus_and_reset_cursor(self, line_edit):
        line_edit.setFocus()
        line_edit.setCursorPosition(0)

    def _add_name_item(self, text: str, enabled: bool):
        item = QListWidgetItem()
        widget = NameListItem(text, enabled)

        if not self.chk_hide_names.isChecked():
            widget.setEnabled(False)

        item.setSizeHint(widget.sizeHint())

        widget.delete_clicked.connect(lambda: self._remove_name_item(item))
        widget.input_field.textChanged.connect(self._on_preset_form_changed)
        widget.checkbox.toggled.connect(self._on_preset_form_changed)

        self.list_names.addItem(item)
        self.list_names.setItemWidget(item, widget)
        self._on_preset_form_changed()

    def _remove_name_item(self, item: QListWidgetItem):
        row = self.list_names.row(item)
        widget = self.list_names.itemWidget(item)
        self.list_names.takeItem(row)

        if widget:
            widget.deleteLater()
        self._on_preset_form_changed()

    def _on_link_mode_changed(self):
        mode_str = self.combo_link_mode.currentData()
        try:
            mode = LinkMaskMode(mode_str)
        except ValueError:
            mode = LinkMaskMode.SIMPLE

        is_customizable = mode in [LinkMaskMode.INDEXED, LinkMaskMode.CUSTOM]
        self.custom_link_format_container.setVisible(is_customizable)

        if mode == LinkMaskMode.INDEXED and not self.input_link_format.text():
            self.input_link_format.setText("[ССЫЛКА {index}]")

    def _load_presets(self):
        self._presets = self.settings_manager.load_anonymizer_presets()
        self._selected_preset_id = self.current_config.get("active_preset")
        available_ids = {preset.get("id") for preset in self._presets}
        if self._selected_preset_id not in available_ids:
            self._selected_preset_id = None
        if self._selected_preset_id is None and self._presets:
            self._selected_preset_id = self._presets[0].get("id")
        self._refresh_presets_list()

    def _refresh_presets_list(self):
        self.combo_presets.blockSignals(True)
        self.combo_presets.clear()
        selected_index = -1

        for index, preset in enumerate(self._presets):
            preset_id = preset.get("id")
            self.combo_presets.addItem(str(preset.get("name", "Preset")), preset_id)
            if preset_id == self._selected_preset_id:
                selected_index = index

        if selected_index == -1 and self._presets:
            selected_index = 0
            self._selected_preset_id = self._presets[0].get("id")

        if selected_index != -1:
            self.combo_presets.setCurrentIndex(selected_index)
        self.combo_presets.blockSignals(False)

        self._sync_preset_edit_mode()
        self._update_edit_button_state()
        preset = self._find_preset_by_id(self._selected_preset_id)
        if preset:
            if preset.get("id") == self.current_config.get("active_preset"):
                self._apply_config_to_ui(self.current_config)
            else:
                self._apply_preset_to_ui(preset)

    def _on_preset_combo_changed(self):
        self._selected_preset_id = self.combo_presets.currentData()
        self._sync_preset_edit_mode()
        self._update_edit_button_state()
        preset = self._find_preset_by_id(self._selected_preset_id)
        if preset:
            if preset.get("id") == self.current_config.get("active_preset"):
                self._apply_config_to_ui(self.current_config)
            else:
                self._apply_preset_to_ui(preset)

    def _start_preset_edit(self, preset_id: str):
        if preset_id == "default":
            return
        self._selected_preset_id = preset_id
        self._editing_preset_id = preset_id
        self._sync_preset_edit_mode()
        self._update_preset_action_button()
        self._update_edit_button_state()

    def _start_selected_preset_edit(self):
        if self._selected_preset_id:
            self._start_preset_edit(self._selected_preset_id)

    def _on_edit_preset_clicked(self):
        if self._editing_preset_id:
            return
        if self._has_unsaved_selected_preset_changes():
            self._confirm_selected_preset_edits()
            return
        self._start_selected_preset_edit()

    def _delete_selected_preset(self):
        if not self._can_edit_selected_preset():
            return
        if self._editing_preset_id is not None:
            return
        target_id = self._selected_preset_id
        if not target_id:
            return
        deleted = self.settings_manager.delete_anonymizer_preset(target_id)
        if not deleted:
            return

        self._presets = self.settings_manager.load_anonymizer_presets()
        self._selected_preset_id = "default"
        self._editing_preset_id = None
        self._refresh_presets_list()
        self._update_preset_action_button()
        self._update_edit_button_state()

    def _on_preset_action_clicked(self):
        if self._editing_preset_id:
            self._save_preset_edit()
            return
        self._create_preset_and_start_edit()

    def _update_preset_action_button(self):
        if self._editing_preset_id:
            self.btn_preset_action.setIcon(get_app_icon(AppIcon.SAVE))
            self.btn_preset_action.setText(tr("Save Preset"))
        else:
            self.btn_preset_action.setIcon(get_app_icon(AppIcon.ADD))
            self.btn_preset_action.setText(tr("Add Preset"))

    def _create_preset_and_start_edit(self):
        created = self.settings_manager.add_anonymizer_preset(tr("Preset"))
        preset_id = created.get("id")
        if not preset_id:
            return
        payload = self._collect_preset_payload(created.get("name", tr("Preset")))
        self.settings_manager.update_anonymizer_preset(preset_id, payload)
        self._presets = self.settings_manager.load_anonymizer_presets()
        self._selected_preset_id = preset_id
        self._editing_preset_id = preset_id
        self._refresh_presets_list()
        self._update_preset_action_button()
        self._update_edit_button_state()

    def _save_preset_edit(self):
        if not self._editing_preset_id:
            return

        edited_name = self._get_editing_name() or tr("Preset")
        payload = self._collect_preset_payload(edited_name)
        updated = self.settings_manager.update_anonymizer_preset(self._editing_preset_id, payload)
        if not updated:
            return

        self._presets = self.settings_manager.load_anonymizer_presets()
        self._selected_preset_id = self._editing_preset_id
        self._editing_preset_id = None
        self._refresh_presets_list()
        self._update_preset_action_button()
        self._update_edit_button_state()

    def _get_editing_name(self) -> str:
        return self.input_preset_name.text().strip()

    def _collect_preset_payload(self, name: str) -> dict:
        config = self.get_config()
        return {
            "name": name,
            "hide_links": config.get("hide_links", False),
            "hide_names": config.get("hide_names", False),
            "name_mask_format": config.get("name_mask_format", "[ИМЯ {index}]"),
            "link_mask_mode": config.get("link_mask_mode", LinkMaskMode.SIMPLE.value),
            "link_mask_format": config.get("link_mask_format", "[ССЫЛКА {index}]"),
            "custom_filters": config.get("custom_filters", []),
            "custom_names": config.get("custom_names", []),
        }

    def _find_preset_by_id(self, preset_id: str | None) -> dict | None:
        for preset in self._presets:
            if preset.get("id") == preset_id:
                return preset
        return None

    def _can_edit_selected_preset(self) -> bool:
        return bool(self._selected_preset_id and self._selected_preset_id != "default")

    def _has_unsaved_selected_preset_changes(self) -> bool:
        if self._suppress_preset_change_tracking or self._editing_preset_id is not None:
            return False
        if not self._can_edit_selected_preset():
            return False
        preset = self._find_preset_by_id(self._selected_preset_id)
        if not preset:
            return False
        preset_payload = self._payload_from_preset(preset)
        current_payload = self._collect_preset_payload(str(preset.get("name", "Preset")))
        return preset_payload != current_payload

    def _payload_from_preset(self, preset: dict) -> dict:
        return {
            "name": str(preset.get("name", "Preset")),
            "hide_links": bool(preset.get("hide_links", False)),
            "hide_names": bool(preset.get("hide_names", False)),
            "name_mask_format": str(preset.get("name_mask_format", "[ИМЯ {index}]")) or "[ИМЯ {index}]",
            "link_mask_mode": str(preset.get("link_mask_mode", LinkMaskMode.SIMPLE.value)) or LinkMaskMode.SIMPLE.value,
            "link_mask_format": str(preset.get("link_mask_format", "[ССЫЛКА {index}]")) or "[ССЫЛКА {index}]",
            "custom_filters": list(preset.get("custom_filters", [])),
            "custom_names": list(preset.get("custom_names", [])),
        }

    def _confirm_selected_preset_edits(self):
        if not self._can_edit_selected_preset():
            return
        preset = self._find_preset_by_id(self._selected_preset_id)
        if not preset:
            return
        payload = self._collect_preset_payload(str(preset.get("name", "Preset")))
        updated = self.settings_manager.update_anonymizer_preset(self._selected_preset_id, payload)
        if not updated:
            return
        self._presets = self.settings_manager.load_anonymizer_presets()
        self._refresh_presets_list()
        self._update_edit_button_state()

    def _on_preset_form_changed(self, *args):
        if self._suppress_preset_change_tracking:
            return
        self._update_edit_button_state()

    def _update_edit_button_state(self):
        enabled = self._anonymization_enabled and self._can_edit_selected_preset() and self._editing_preset_id is None
        self.btn_edit_preset.setEnabled(enabled)
        self.btn_delete_preset.setEnabled(enabled)
        if not enabled:
            self.btn_edit_preset.setIcon(QIcon())
            self.btn_edit_preset.setText(tr("Edit"))
            self.btn_edit_preset.setToolTip(tr("anonymization.edit_preset"))
            return

        if self._has_unsaved_selected_preset_changes():
            self.btn_edit_preset.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
            )
            self.btn_edit_preset.setText(tr("Confirm edits").replace(" ", "\n", 1))
            self.btn_edit_preset.setToolTip(tr("Confirm edits"))
        else:
            self.btn_edit_preset.setIcon(QIcon())
            self.btn_edit_preset.setText(tr("Edit"))
            self.btn_edit_preset.setToolTip(tr("anonymization.edit_preset"))

    def _apply_white_button_style(self):
        for btn in (
            self.btn_edit_preset,
            self.btn_delete_preset,
            self.btn_add_link,
            self.btn_import_chat_rules,
            self.btn_add_name,
            self.btn_preset_action,
        ):
            btn.setProperty("class", "white-button")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _sync_preset_edit_mode(self):
        is_editing = self._editing_preset_id is not None
        selected_preset = self._find_preset_by_id(self._selected_preset_id)

        self.combo_presets.setVisible(not is_editing)
        self.input_preset_name.setVisible(is_editing)
        self.btn_edit_preset.setVisible(not is_editing and self._can_edit_selected_preset())
        self.btn_delete_preset.setVisible(not is_editing and self._can_edit_selected_preset())

        if is_editing and selected_preset:
            self.input_preset_name.setText(str(selected_preset.get("name", "Preset")))
            self.input_preset_name.setEnabled(True)
            self.input_preset_name.setReadOnly(False)
            QTimer.singleShot(0, self.input_preset_name.setFocus)
            QTimer.singleShot(0, self.input_preset_name.selectAll)

    def _apply_config_to_ui(self, config: dict):
        self._suppress_preset_change_tracking = True
        try:
            self.chk_hide_links.setChecked(bool(config.get("hide_links", False)))
            self.chk_hide_names.setChecked(bool(config.get("hide_names", False)))
            self.input_name_format.setText(
                str(config.get("name_mask_format", "[ИМЯ {index}]"))
            )
            mode_str = config.get("link_mask_mode", "simple")
            idx = self.combo_link_mode.findData(mode_str)
            if idx != -1:
                self.combo_link_mode.setCurrentIndex(idx)
            self.input_link_format.setText(
                str(config.get("link_mask_format", "[ССЫЛКА {index}]"))
            )
            self._on_link_mode_changed()
            self.current_config["custom_filters"] = list(config.get("custom_filters", []))
            self.current_config["custom_names"] = list(config.get("custom_names", []))
            self._populate_links_list_from_config(self.current_config)
            self._populate_names_list()
            self._update_names_list_state(self.chk_hide_names.isChecked())
        finally:
            self._suppress_preset_change_tracking = False
        self._update_edit_button_state()

    def _apply_preset_to_ui(self, preset: dict):
        self._suppress_preset_change_tracking = True
        try:
            self.chk_hide_links.setChecked(bool(preset.get("hide_links", self.chk_hide_links.isChecked())))
            self.chk_hide_names.setChecked(bool(preset.get("hide_names", self.chk_hide_names.isChecked())))

            self.input_name_format.setText(
                str(preset.get("name_mask_format", self.input_name_format.text()))
            )

            mode_value = preset.get("link_mask_mode", self.combo_link_mode.currentData())
            mode_index = self.combo_link_mode.findData(mode_value)
            if mode_index != -1:
                self.combo_link_mode.setCurrentIndex(mode_index)

            self.input_link_format.setText(
                str(preset.get("link_mask_format", self.input_link_format.text()))
            )
            self._on_link_mode_changed()

            self.current_config["custom_filters"] = list(preset.get("custom_filters", []))
            self.current_config["custom_names"] = list(preset.get("custom_names", []))
            self._populate_links_list_from_config(self.current_config)
            self._populate_names_list()
            self._update_names_list_state(self.chk_hide_names.isChecked())
        finally:
            self._suppress_preset_change_tracking = False
        self._update_edit_button_state()

    def _set_initial_link_values(self, config):
        mode_str = config.get("link_mask_mode", LinkMaskMode.SIMPLE.value)
        self.input_link_format.setText(config.get("link_mask_format", "[ССЫЛКА {index}]"))

        idx = self.combo_link_mode.findData(mode_str)
        if idx != -1:
            self.combo_link_mode.setCurrentIndex(idx)
        self._on_link_mode_changed()

    def get_config(self) -> dict:

        custom_filters = []

        for i in range(self.list_links.count()):
            item = self.list_links.item(i)
            widget = self.list_links.itemWidget(item)
            if widget:
                data = widget.get_data()
                raw_text = data["value"]

                if not raw_text:
                    continue

                if raw_text.startswith("[regex]"):
                    filter_type = "regex"
                    filter_value = raw_text.replace("[regex]", "").strip()
                else:
                    filter_type = "domain"
                    filter_value = raw_text.strip()

                custom_filters.append({
                    "type": filter_type,
                    "value": filter_value,
                    "enabled": data["enabled"]
                })

        custom_names = []
        for i in range(self.list_names.count()):
            item = self.list_names.item(i)
            if not item:
                continue
            widget = self.list_names.itemWidget(item)
            if widget:
                data = widget.get_data()
                if data["value"]:
                    custom_names.append(data)

        return {
            "enabled": self._anonymization_enabled,
            "hide_links": self.chk_hide_links.isChecked(),
            "hide_names": self.chk_hide_names.isChecked(),
            "name_mask_format": self.input_name_format.text() or "[ИМЯ {index}]",
            "link_mask_mode": self.combo_link_mode.currentData(),
            "link_mask_format": self.input_link_format.text().strip() or "[ССЫЛКА {index}]",
            "active_preset": self._selected_preset_id,
            "custom_filters": custom_filters,
            "custom_names": custom_names
        }

    def retranslate_ui(self):
        self.setWindowTitle(tr("Anonymization Settings"))
        self.link_group_title.setText(tr("anonymization.link_filtering"))
        self.chk_hide_links.setText(tr("Process links"))
        self.btn_add_link.setText(tr("Add Pattern"))
        self.btn_import_chat_rules.setText(tr("Import from chat"))

        self.name_group_title.setText(tr("Name Anonymization"))
        self.preset_actions_group_title.setText(tr("Preset actions"))
        self.chk_hide_names.setText(tr("Hide participant names"))
        self.btn_add_name.setText(tr("Add Name Rule"))
        self.btn_delete_preset.setToolTip(tr("anonymization.delete_preset"))
        self._update_preset_action_button()
        self._update_edit_button_state()

        if hasattr(self, 'ok_button'):
            self.ok_button.setText(tr("OK"))
        if hasattr(self, 'cancel_button'):
            self.cancel_button.setText(tr("Cancel"))

    def mousePressEvent(self, event: QMouseEvent):
        self.clear_input_focus()
        super().mousePressEvent(event)

    def clear_input_focus(self):
        focused_widget = self.focusWidget()
        if focused_widget and isinstance(focused_widget, (QLineEdit, QWidget)):
            focused_widget.clearFocus()
