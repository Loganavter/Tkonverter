from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.ui.icon_manager import AppIcon, get_app_icon
from src.shared_toolkit.ui.managers.theme_manager import ThemeManager

class IconButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, icon: AppIcon, parent: QWidget = None):
        super().__init__(parent)

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.setProperty("class", "icon-button")
        self.setProperty("variant", "default")

        self.setFixedSize(36, 36)

        self._icon_size = QSize(22, 22)
        self._icon = icon
        self._flyout_is_open = False

        self.theme_manager = ThemeManager.get_instance()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.icon_label = QLabel(self)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        self.setProperty("state", "normal")

        self._update_icon()

        self.theme_manager.theme_changed.connect(self._update_icon)

        self.style().polish(self)

    def setFlyoutOpen(self, is_open: bool):
        if self._flyout_is_open != is_open:
            self._flyout_is_open = is_open
            if not is_open:
                should_be_hovered = self.rect().contains(
                    self.mapFromGlobal(self.cursor().pos())
                )
                new_state = "hover" if should_be_hovered else "normal"
                self.setProperty("state", new_state)
            else:
                self.setProperty("state", "normal")
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()

    def setIconSize(self, size: QSize):
        self._icon_size = size
        self._update_icon()

    def _update_icon(self):
        pixmap = get_app_icon(self._icon).pixmap(self._icon_size)
        self.icon_label.setPixmap(pixmap)

    def enterEvent(self, event):
        if not self._flyout_is_open and self.underMouse():
            self.setProperty("state", "hover")
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._flyout_is_open:
            self.setProperty("state", "normal")
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if not self._flyout_is_open:
            self.setProperty("state", "pressed")
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if not self._flyout_is_open:
            is_hovered = self.rect().contains(event.pos())
            self.setProperty("state", "hover" if is_hovered else "normal")
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()
            if is_hovered and event.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit()
        super().mouseReleaseEvent(event)
