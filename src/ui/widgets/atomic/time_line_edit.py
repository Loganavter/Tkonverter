from PyQt6.QtCore import QRectF, Qt, QTime, pyqtSignal, QEvent
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QTimeEdit, QWidget

from src.shared_toolkit.ui.managers.theme_manager import ThemeManager
from src.shared_toolkit.ui.widgets.helpers.underline_painter import UnderlineConfig, draw_bottom_underline

class TimeLineEdit(QWidget):
    RADIUS = 6
    textChanged = pyqtSignal(str)
    editingFinished = pyqtSignal()

    def __init__(self, initial_time: str = "00:05", parent=None):
        super().__init__(parent)

        self.theme_manager = ThemeManager.get_instance()
        self.theme_manager.theme_changed.connect(self.update)

        self._time_edit = QTimeEdit(self)

        self._time_edit.setStyleSheet(
            """
            QTimeEdit {
                border: none;
                background: transparent;
                padding: 6px 2px;
                font-size: 10pt;
            }
            QTimeEdit::up-button, QTimeEdit::down-button {
                width: 0px;
                border: none;
            }
        """
        )

        self._time_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._time_edit.setDisplayFormat("HH:mm")

        self._time_edit.setTime(QTime.fromString(initial_time, "HH:mm"))

        self._time_edit.timeChanged.connect(self._on_internal_time_changed)
        self._time_edit.editingFinished.connect(self.editingFinished)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._time_edit)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocusProxy(self._time_edit)

        self._time_edit.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Tracks focus events for internal QTimeEdit."""
        if obj is self._time_edit:
            if event.type() == QEvent.Type.FocusIn or event.type() == QEvent.Type.FocusOut:
                self.update()
        return super().eventFilter(obj, event)

    def _on_internal_time_changed(self, time_obj: QTime):
        """Slot adapter for converting QTime to string."""
        self.textChanged.emit(time_obj.toString("HH:mm"))

    def text(self) -> str:
        """Returns current time as 'HH:mm' string."""
        return self._time_edit.time().toString("HH:mm")

    def setText(self, text: str):
        """Sets time from 'HH:mm' string."""
        time_obj = QTime.fromString(text, "HH:mm")
        if time_obj.isValid():
            self._time_edit.setTime(time_obj)

    def selectAll(self):
        """Selects all text. QTimeEdit does this by sections, we select the first one."""
        self._time_edit.setCurrentSection(QTimeEdit.Section.HourSection)

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_color = self.theme_manager.get_color("dialog.input.background")
        painter.setBrush(bg_color)
        painter.setPen(QColor("transparent"))
        painter.drawRoundedRect(self.rect(), self.RADIUS, self.RADIUS)

        rr = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        thin_border_color = QColor(self.theme_manager.get_color("input.border.thin"))
        alpha = max(8, int(thin_border_color.alpha() * 0.66))
        thin_border_color.setAlpha(alpha)
        pen = QPen(thin_border_color)
        pen.setWidthF(0.66)
        painter.setPen(pen)
        painter.setBrush(QColor("transparent"))
        painter.drawRoundedRect(rr, self.RADIUS, self.RADIUS)

        if self._time_edit.hasFocus():
            underline_config = UnderlineConfig(color=self.theme_manager.get_color("accent"), alpha=255, thickness=1.0)
        else:
            underline_config = UnderlineConfig(alpha=120, thickness=1.0)

        draw_bottom_underline(
            painter, self.rect(), self.theme_manager, underline_config
        )
