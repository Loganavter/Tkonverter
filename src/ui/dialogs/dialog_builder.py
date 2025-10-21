import os
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.resources.translations import tr
from src.shared_toolkit.ui.widgets.atomic.custom_button import CustomButton
from src.shared_toolkit.utils.paths import resource_path

def setup_dialog_scaffold(
    dialog: QDialog,
    main_layout: QVBoxLayout,
    ok_text: str,
    cancel_text: str = tr("Cancel"),
    show_cancel_button: bool = True,
):
    buttons_layout = QHBoxLayout()
    buttons_layout.addStretch()

    dialog.ok_button = CustomButton(None, ok_text)
    dialog.ok_button.setProperty("class", "primary")
    dialog.ok_button.setFixedSize(100, 30)
    dialog.cancel_button = CustomButton(None, cancel_text)
    dialog.cancel_button.setFixedSize(100, 30)

    dialog.ok_button.clicked.connect(dialog.accept)
    dialog.cancel_button.clicked.connect(dialog.reject)

    buttons_layout.addWidget(dialog.ok_button)
    if show_cancel_button:
        buttons_layout.addWidget(dialog.cancel_button)

    main_layout.addLayout(buttons_layout)

def setup_dialog_icon(dialog: QDialog):
    """Sets icon for dialog."""
    icon_path = resource_path("resources/icons/icon.png")
    if os.path.exists(icon_path):
        dialog.setWindowIcon(QIcon(icon_path))

def auto_size_dialog(dialog: QDialog, min_width: int = 300, min_height: int = 200):
    """
    Automatically calculates and sets dialog sizes based on content.

    Args:
        dialog: Dialog to update sizes for
        min_width: Minimum width
        min_height: Minimum height
    """

    def _recalculate_sizes():

        dialog.adjustSize()

        content_size = dialog.sizeHint()

        final_width = max(min_width, content_size.width() + 50)
        final_height = max(min_height, content_size.height() + 30)

        dialog.setMinimumSize(final_width, final_height)

        _update_group_sizes(dialog)

    QTimer.singleShot(0, _recalculate_sizes)

def _update_group_sizes(dialog: QDialog):
    """Updates sizes of styled groups in dialog."""
    for child in dialog.findChildren(QWidget):
        if child.objectName() == "StyledGroupFrame":
            parent_group = child.parent()
            if parent_group:

                content_width = child.sizeHint().width()

                min_width = content_width + 30

                for title_child in parent_group.findChildren(QLabel):
                    if title_child.objectName() == "StyledGroupTitle":
                        title_width = title_child.width() + 40
                        min_width = max(min_width, title_width)
                        break

                parent_group.setMinimumWidth(min_width)
