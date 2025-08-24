from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QScrollBar

from ui.theme import ThemeManager

class MinimalistScrollBar(QScrollBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme_manager = ThemeManager.get_instance()

        self._is_dragging = False
        self._drag_start_offset = 0

        self._idle_thickness = 4
        self._hover_thickness = 6
        self._drag_thickness = 10

        self._idle_color = QColor()
        self._hover_color = QColor()

        self._update_colors()
        self.theme_manager.theme_changed.connect(self._update_colors)

        self.setMouseTracking(True)

    def _update_colors(self):
        if self.theme_manager.is_dark():
            self._idle_color = QColor(255, 255, 255, 60)
            self._hover_color = QColor(255, 255, 255, 90)
        else:
            self._idle_color = QColor(0, 0, 0, 70)
            self._hover_color = QColor(0, 0, 0, 100)
        self.update()

    def paintEvent(self, event):
        if self.minimum() == self.maximum():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        handle_rect = self._get_handle_rect()
        if handle_rect.isEmpty():
            return

        if self._is_dragging:
            current_color = self.theme_manager.get_color("accent")
        elif self.underMouse():
            current_color = self._hover_color
        else:
            current_color = self._idle_color

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(current_color)
        radius = handle_rect.width() / 2.0
        painter.drawRoundedRect(handle_rect, radius, radius)

    def _get_handle_rect(self):
        if self.minimum() == self.maximum():
            return QRect()

        if self._is_dragging:
            current_thickness = self._drag_thickness
        elif self.underMouse():
            current_thickness = self._hover_thickness
        else:
            current_thickness = self._idle_thickness

        v_padding = 8
        groove_height = self.height() - v_padding * 2

        total_range = self.maximum() - self.minimum() + self.pageStep()
        if total_range <= 0 or groove_height <= 0:
            return QRect()

        handle_height = max((self.pageStep() / total_range) * groove_height, 20)
        scroll_range = self.maximum() - self.minimum()

        track_height = groove_height - handle_height

        handle_y_relative = (
            (self.value() - self.minimum()) / scroll_range * track_height
            if scroll_range > 0
            else 0
        )
        handle_y = handle_y_relative + v_padding
        handle_x = (self.width() - current_thickness) // 2

        return QRect(
            int(handle_x), int(handle_y), int(current_thickness), int(handle_height)
        )

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        handle_rect = self._get_handle_rect()

        if handle_rect.contains(event.pos()):
            self._is_dragging = True
            self._drag_start_offset = event.pos().y() - handle_rect.y()
            self.update()
            event.accept()
            return

        v_padding = 8
        handle_height = handle_rect.height()
        track_height = (self.height() - v_padding * 2) - handle_height

        new_y = event.pos().y() - v_padding - (handle_height / 2)

        scroll_range = self.maximum() - self.minimum()
        if track_height > 0:
            new_value = self.minimum() + (new_y / track_height) * scroll_range
            self.setValue(int(new_value))

            self._is_dragging = True
            self._drag_start_offset = handle_height / 2
            self.update()

        event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            v_padding = 8
            handle_height = self._get_handle_rect().height()
            track_height = (self.height() - v_padding * 2) - handle_height

            mouse_pos_in_track = event.pos().y() - v_padding - self._drag_start_offset

            scroll_range = self.maximum() - self.minimum()
            if track_height > 0:
                new_value = (
                    self.minimum() + (mouse_pos_in_track / track_height) * scroll_range
                )
                self.setValue(int(new_value))

        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            self.update()
            event.accept()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)
