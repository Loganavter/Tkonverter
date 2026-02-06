from PyQt6.QtCore import Qt, pyqtSignal, QSize, QEvent, QTimer
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.resources.translations import tr
from src.ui.dialogs.dialog_builder import auto_size_dialog, setup_dialog_scaffold, setup_dialog_icon
from src.ui.icon_manager import AppIcon, get_app_icon
from shared_toolkit.ui.widgets.atomic import FluentCheckBox
from shared_toolkit.ui.widgets.atomic import FluentComboBox

from src.core.domain.anonymization import LinkMaskMode
from shared_toolkit.ui.widgets.atomic import CustomGroupBuilder
from shared_toolkit.ui.widgets.atomic import CustomLineEdit
from shared_toolkit.ui.widgets.atomic import MinimalistScrollBar
from shared_toolkit.ui.widgets.atomic.simple_icon_button import SimpleIconButton
from shared_toolkit.ui.widgets.atomic.custom_button import CustomButton

class LinkListItem(QWidget):
    """
    Элемент списка ссылок: Поле + Чекбокс + Удаление.
    """
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
        self.checkbox.setToolTip(tr("Enable rule"))
        layout.addWidget(self.checkbox)

        self.delete_btn = SimpleIconButton(AppIcon.REMOVE, self)
        self.delete_btn.setFixedSize(28, 28)
        self.delete_btn.setIconSize(QSize(16, 16))
        self.delete_btn.setToolTip(tr("Remove"))
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
    """
    Элемент списка имен: Редактируемое поле + Галочка (вкл/выкл) + Кнопка удаления.
    """
    delete_clicked = pyqtSignal()

    def __init__(self, text: str, enabled: bool, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self.input_field = CustomLineEdit()
        self.input_field.setText(text)
        self.input_field.setPlaceholderText(tr("Name"))
        layout.addWidget(self.input_field, 1)

        self.checkbox = FluentCheckBox("")
        self.checkbox.setChecked(enabled)
        self.checkbox.setToolTip(tr("Enable rule"))
        layout.addWidget(self.checkbox)

        self.delete_btn = SimpleIconButton(AppIcon.REMOVE, self)
        self.delete_btn.setFixedSize(28, 28)
        self.delete_btn.setIconSize(QSize(16, 16))
        self.delete_btn.setToolTip(tr("Remove"))
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

        self.chk_enable = FluentCheckBox()
        self.chk_enable.setChecked(current_config.get("enabled", False))
        self.chk_enable.toggled.connect(self._on_enable_toggled)
        self.chk_enable.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        main_layout.addWidget(self.chk_enable)

        link_group, link_layout, self.link_group_title = CustomGroupBuilder.create_styled_group(
            tr("Link Filtering")
        )

        self.chk_hide_links = FluentCheckBox()
        self.chk_hide_links.setChecked(current_config.get("hide_links", False))
        self.chk_hide_links.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        link_layout.addWidget(self.chk_hide_links)

        preset_layout = QHBoxLayout()
        preset_label = QLabel(tr("Preset:"))
        self.combo_presets = FluentComboBox()
        self.combo_presets.addItem(tr("None"), None)
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.combo_presets, 1)
        link_layout.addLayout(preset_layout)

        mode_layout = QHBoxLayout()
        mode_label = QLabel(tr("Replacement format"))
        self.combo_link_mode = FluentComboBox()
        self.combo_link_mode.addItem(tr("Simple Mask"), LinkMaskMode.SIMPLE.value)
        self.combo_link_mode.addItem(tr("Domain only"), LinkMaskMode.DOMAIN_ONLY.value)
        self.combo_link_mode.addItem(tr("Indexed"), LinkMaskMode.INDEXED.value)
        self.combo_link_mode.addItem(tr("Custom"), LinkMaskMode.CUSTOM.value)

        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.combo_link_mode, 1)
        link_layout.addLayout(mode_layout)

        self.custom_link_format_container = QWidget()
        self.custom_link_format_container.setVisible(False)
        custom_format_layout = QHBoxLayout(self.custom_link_format_container)
        custom_format_layout.setContentsMargins(0, 0, 0, 0)
        self.input_link_format = CustomLineEdit()
        self.input_link_format.setPlaceholderText(tr("Use {index} for unique number"))
        custom_format_layout.addWidget(QLabel("  └ "), 0)
        custom_format_layout.addWidget(self.input_link_format, 1)
        link_layout.addWidget(self.custom_link_format_container)

        self.combo_link_mode.currentIndexChanged.connect(self._on_link_mode_changed)

        self.list_links = QListWidget()
        self.list_links.setMaximumHeight(150)
        self.list_links.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_links.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_links.setStyleSheet("QListWidget { outline: none; background: transparent; }")

        self.list_links.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list_links.setVerticalScrollBar(MinimalistScrollBar(Qt.Orientation.Vertical, self.list_links))

        self.list_links.viewport().installEventFilter(self)

        self.btn_add_link = CustomButton(get_app_icon(AppIcon.ADD), tr("Add Pattern"))
        self.btn_add_link.clicked.connect(self._on_add_link_clicked)

        link_layout.addWidget(self.list_links)
        link_layout.addWidget(self.btn_add_link)

        self._clear_links_list()

        self._set_initial_link_values(current_config)

        unique_links = {}

        custom_filters = current_config.get("custom_filters", [])
        for f_dict in custom_filters:
            filter_type = f_dict.get("type", "domain")
            val = f_dict.get("value", "")
            enabled = f_dict.get("enabled", True)

            text_to_show = f"[regex] {val}" if filter_type == "regex" else val
            unique_links[text_to_show] = enabled

        for domain in self.known_domains:
            if domain and domain not in unique_links:
                unique_links[domain] = False

        for text, enabled in unique_links.items():
            self._add_link_item(text, enabled)

        main_layout.addWidget(link_group)

        name_group, name_layout, self.name_group_title = CustomGroupBuilder.create_styled_group(
            tr("Name Anonymization")
        )

        self.chk_hide_names = FluentCheckBox()
        self.chk_hide_names.setChecked(current_config.get("hide_names", False))
        self.chk_hide_names.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.chk_hide_names.toggled.connect(self._update_names_list_state)

        name_layout.addWidget(self.chk_hide_names)

        name_format_layout = QHBoxLayout()
        name_format_label = QLabel(tr("Name format:"))
        self.input_name_format = CustomLineEdit()
        self.input_name_format.setText(current_config.get("name_mask_format", "[ИМЯ {index}]"))
        self.input_name_format.setPlaceholderText("[ИМЯ {index}]")
        name_format_layout.addWidget(name_format_label)
        name_format_layout.addWidget(self.input_name_format, 1)
        name_layout.addLayout(name_format_layout)

        self.list_names = QListWidget()
        self.list_names.setMaximumHeight(150)
        self.list_names.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_names.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_names.setStyleSheet("QListWidget { outline: none; background: transparent; }")

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
        main_layout.addStretch(1)

        setup_dialog_scaffold(self, main_layout, ok_text="", cancel_text="")

        self.retranslate_ui()
        self._on_enable_toggled(self.chk_enable.isChecked())

        auto_size_dialog(self, min_width=500, min_height=500)

    def _update_names_list_state(self, checked: bool):
        """Обновляет состояние доступности элементов списка имен при переключении родительской галочки."""
        self.list_names.setEnabled(checked)
        self.btn_add_name.setEnabled(checked)
        self.input_name_format.setEnabled(checked)

        for i in range(self.list_names.count()):
            item = self.list_names.item(i)
            widget = self.list_names.itemWidget(item)
            if widget:
                widget.setEnabled(checked)

    def eventFilter(self, source, event):
        """Перехват кликов для сброса фокуса при нажатии на пустое место в списке."""
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if source is self.list_links.viewport() or source is self.list_names.viewport():
                list_widget = self.list_links if source is self.list_links.viewport() else self.list_names
                index = list_widget.indexAt(event.pos())
                if not index.isValid():
                    self.clear_input_focus()

        return super().eventFilter(source, event)

    def _clear_names_list(self):
        """Принудительно очищает список имен и все связанные виджеты."""

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
        """Заполняет список имен, объединяя сохраненные и новые из файла."""

        self._clear_names_list()

        saved_names = self.current_config.get("custom_names", [])

        unique_names = {}

        for entry in saved_names:
            val = entry.get("value", "")
            if val:
                unique_names[val] = entry.get("enabled", True)

        for name in self.known_names:
            if name and name not in unique_names:
                unique_names[name] = False

        for name in sorted(unique_names.keys()):
            enabled = unique_names[name]
            self._add_name_item(name, enabled)

    def _on_enable_toggled(self, enabled: bool):
        """Обновляет доступность виджетов в зависимости от состояния."""
        self.chk_hide_links.setEnabled(enabled)
        self.chk_hide_names.setEnabled(enabled)
        self.combo_presets.setEnabled(enabled)
        self.list_links.setEnabled(enabled)
        self.btn_add_link.setEnabled(enabled)

        names_enabled = enabled and self.chk_hide_names.isChecked()
        self._update_names_list_state(names_enabled)

        self.chk_hide_names.setEnabled(enabled)

    def _on_add_link_clicked(self):
        """Добавляет пустой элемент ссылки для редактирования."""
        self._add_link_item("")
        self.list_links.scrollToBottom()
        item = self.list_links.item(self.list_links.count() - 1)
        widget = self.list_links.itemWidget(item)
        if widget:

            QTimer.singleShot(0, lambda: self._focus_and_reset_cursor(widget.input_field))

    def _clear_links_list(self):
        """Принудительно очищает список ссылок и все связанные виджеты."""

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

    def _add_link_item(self, text: str, enabled: bool = True):
        item = QListWidgetItem()
        widget = LinkListItem(text, enabled)
        item.setSizeHint(widget.sizeHint())

        widget.delete_clicked.connect(lambda: self._remove_link_item(item))

        self.list_links.addItem(item)
        self.list_links.setItemWidget(item, widget)

    def _remove_link_item(self, item: QListWidgetItem):
        row = self.list_links.row(item)
        widget = self.list_links.itemWidget(item)
        self.list_links.takeItem(row)

        if widget:
            widget.deleteLater()

    def _on_add_name_clicked(self):
        """Добавляет пустой элемент имени."""
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

        self.list_names.addItem(item)
        self.list_names.setItemWidget(item, widget)

    def _remove_name_item(self, item: QListWidgetItem):
        row = self.list_names.row(item)
        widget = self.list_names.itemWidget(item)
        self.list_names.takeItem(row)

        if widget:
            widget.deleteLater()

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

    def _set_initial_link_values(self, config):
        mode_str = config.get("link_mask_mode", LinkMaskMode.SIMPLE.value)
        self.input_link_format.setText(config.get("link_mask_format", "[ССЫЛКА {index}]"))

        idx = self.combo_link_mode.findData(mode_str)
        if idx != -1:
            self.combo_link_mode.setCurrentIndex(idx)
        self._on_link_mode_changed()

    def get_config(self) -> dict:
        """Собирает данные из виджетов и возвращает словарь конфигурации."""

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

        items_to_process = []
        for i in range(self.list_names.count()):
            item = self.list_names.item(i)
            if item:
                items_to_process.append(item)

        for item in items_to_process:
            widget = self.list_names.itemWidget(item)
            if widget:
                data = widget.get_data()

                if data["enabled"]:
                    custom_names.append(data)

        return {
            "enabled": self.chk_enable.isChecked(),
            "hide_links": self.chk_hide_links.isChecked(),
            "hide_names": self.chk_hide_names.isChecked(),
            "name_mask_format": self.input_name_format.text() or "[ИМЯ {index}]",
            "link_mask_mode": self.combo_link_mode.currentData(),
            "link_mask_format": self.input_link_format.text().strip() or "[ССЫЛКА {index}]",
            "active_preset": self.combo_presets.currentData(),
            "custom_filters": custom_filters,
            "custom_names": custom_names
        }

    def retranslate_ui(self):
        """Обновляет все тексты в диалоге при смене языка."""
        self.setWindowTitle(tr("Anonymization Settings"))
        self.chk_enable.setText(tr("Enable anonymization"))
        self.link_group_title.setText(tr("Link Filtering"))
        self.chk_hide_links.setText(tr("Process links"))
        self.btn_add_link.setText(tr("Add Pattern"))

        self.name_group_title.setText(tr("Name Anonymization"))
        self.chk_hide_names.setText(tr("Hide participant names"))
        self.btn_add_name.setText(tr("Add Name Rule"))

        if hasattr(self, 'ok_button'):
            self.ok_button.setText(tr("OK"))
        if hasattr(self, 'cancel_button'):
            self.cancel_button.setText(tr("Cancel"))

    def mousePressEvent(self, event: QMouseEvent):
        """Убирает фокус с полей ввода при клике на пустую область."""
        self.clear_input_focus()
        super().mousePressEvent(event)

    def clear_input_focus(self):
        """Убирает фокус с любого поля ввода в диалоге."""
        focused_widget = self.focusWidget()
        if focused_widget and isinstance(focused_widget, (QLineEdit, QWidget)):
            focused_widget.clearFocus()
