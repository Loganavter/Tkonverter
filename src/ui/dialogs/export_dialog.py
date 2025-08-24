import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QMouseEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from resources.translations import tr
from ui.dialogs.dialog_builder import auto_size_dialog, setup_dialog_scaffold, setup_dialog_icon
from ui.icon_manager import AppIcon
from ui.widgets.atomic.custom_button import CustomButton
from ui.widgets.atomic.custom_line_edit import CustomLineEdit
from utils.paths import resource_path

class ExportDialog(QDialog):

    def __init__(
        self,
        settings_manager,
        parent=None,
        suggested_filename: str = "",
        get_unique_path_func=None,
    ):
        super().__init__(parent)

        self.setObjectName("ExportDialog")
        self.settings_manager = settings_manager
        self.suggested_filename = suggested_filename

        self.get_unique_path_func = get_unique_path_func
        self._is_updating_name = False

        setup_dialog_icon(self)
        self.setWindowTitle(tr("Export Chat"))

        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setSizeGripEnabled(True)
        self.setMinimumWidth(450)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        dir_label = QLabel(tr("Folder to save:"))
        dir_label.setObjectName("dir_label")
        self.edit_dir = CustomLineEdit()
        self.btn_browse_dir = CustomButton(AppIcon.FOLDER_OPEN, tr("Browse..."))
        self.btn_browse_dir.clicked.connect(self._choose_directory)

        dir_row = QHBoxLayout()
        dir_row.addWidget(self.edit_dir, 1)
        dir_row.addWidget(self.btn_browse_dir)

        fav_row = QHBoxLayout()
        fav_row.setContentsMargins(0, 0, 0, 0)
        self.checkbox_use_default_dir = QCheckBox(tr("Use as default folder"))

        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)

        self.btn_set_favorite = CustomButton(None, tr("To Favorites"))
        self.btn_use_favorite = CustomButton(None, tr("From Favorites"))
        self.btn_set_favorite.clicked.connect(self._set_favorite_from_current)
        self.btn_use_favorite.clicked.connect(self._use_favorite_dir)

        button_layout.addWidget(self.btn_set_favorite)
        button_layout.addWidget(self.btn_use_favorite)

        fav_row.addWidget(self.checkbox_use_default_dir, stretch=2)
        fav_row.addWidget(button_container, stretch=0)

        name_label = QLabel(tr("File name (without extension):"))
        name_label.setObjectName("name_label")
        self.edit_name = CustomLineEdit()

        main_layout.addWidget(dir_label)
        main_layout.addLayout(dir_row)
        main_layout.addLayout(fav_row)
        main_layout.addSpacing(10)
        main_layout.addWidget(name_label)
        main_layout.addWidget(self.edit_name)

        setup_dialog_scaffold(self, main_layout, ok_text=tr("Save"))

        auto_size_dialog(self, min_width=450, min_height=200)

        self._populate_from_state()

        self.edit_dir.textChanged.connect(self._update_final_filename_preview)

        self.edit_name.textChanged.connect(self._update_final_filename_preview)

        initial_name = self.suggested_filename or tr("chat_history")
        self.edit_name.setText(initial_name)

        self._update_final_filename_preview()

    def _populate_from_state(self):

        use_default = self.settings_manager.settings.value(
            "export_use_default_dir", True, type=bool
        )

        self.checkbox_use_default_dir.setChecked(use_default)

        out_dir = (
            self.settings_manager.settings.value("export_default_dir", "", type=str)
            if use_default
            else ""
        )

        if not out_dir or not os.path.isdir(out_dir):
            out_dir = self._get_os_default_downloads()

        self.edit_dir.setText(out_dir)

        self._update_final_filename_preview()

    def _update_final_filename_preview(self):

        if self._is_updating_name:
            return

        if not self.get_unique_path_func:
            return

        directory = self.edit_dir.text().strip()
        base_name = self.edit_name.text().strip()

        if not directory or not base_name or not os.path.isdir(directory):
            return

        try:
            unique_path = self.get_unique_path_func(directory, base_name, ".txt")

            final_name, _ = os.path.splitext(os.path.basename(unique_path))

            if final_name != base_name:
                self._is_updating_name = True
                self.edit_name.setText(final_name)
                self._is_updating_name = False
        except Exception:
            pass

    def _choose_directory(self):
        start_dir = self.edit_dir.text() or self._get_os_default_downloads()

        chosen = QFileDialog.getExistingDirectory(self, tr("Choose folder"), start_dir)

        if chosen:
            self.edit_dir.setText(chosen)

            self._update_final_filename_preview()

    def _set_favorite_from_current(self):
        path = self.edit_dir.text().strip()
        if path:
            self.settings_manager.settings.setValue("export_favorite_dir", path)

    def _use_favorite_dir(self):
        path = self.settings_manager.settings.value("export_favorite_dir", "", type=str)

        if path:
            self.edit_dir.setText(path)

            self._update_final_filename_preview()

    def _get_os_default_downloads(self) -> str:
        return os.path.join(os.path.expanduser("~"), "Downloads")

    def get_export_options(self) -> dict:
        return {
            "output_dir": self.edit_dir.text().strip(),
            "file_name": self.edit_name.text().strip(),
            "use_default_dir": self.checkbox_use_default_dir.isChecked(),
        }

    def retranslate_ui(self):
        """Updates all texts in dialog when language changes."""
        self.setWindowTitle(tr("Export Chat"))
        self.findChild(QLabel, "dir_label").setText(tr("Folder to save:"))
        self.btn_browse_dir.setText(tr("Browse..."))
        self.checkbox_use_default_dir.setText(tr("Use as default folder"))
        self.btn_set_favorite.setText(tr("To Favorites"))
        self.btn_use_favorite.setText(tr("From Favorites"))
        self.findChild(QLabel, "name_label").setText(tr("File name (without extension):"))

        if hasattr(self, 'ok_button'):
            self.ok_button.setText(tr("Save"))
        if hasattr(self, 'cancel_button'):
            self.cancel_button.setText(tr("Cancel"))

    def refresh_theme_styles(self):
        """Forces dialog styles to update."""
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        self.updateGeometry()

    def mousePressEvent(self, event: QMouseEvent):
        """Removes focus from input fields when clicking on empty area."""
        self.clear_input_focus()
        super().mousePressEvent(event)

    def clear_input_focus(self):
        """Removes focus if it's set on QLineEdit."""
        focused_widget = self.focusWidget()
        if focused_widget and isinstance(focused_widget, QLineEdit):
            focused_widget.clearFocus()

    def showEvent(self, event):
        self._update_final_filename_preview()

        super().showEvent(event)
