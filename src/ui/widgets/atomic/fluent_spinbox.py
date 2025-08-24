from enum import Enum
from PyQt6.QtCore import (
    Qt, QSize, pyqtSignal, QRectF, QPointF
)
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QPolygonF
)
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QSizePolicy
)
from ui.theme import ThemeManager
from ui.widgets.helpers.underline_painter import draw_bottom_underline, UnderlineConfig

class FocusLineEdit(QLineEdit):
    focusChanged = pyqtSignal(bool)
    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focusChanged.emit(True)
    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focusChanged.emit(False)

class _ArrowDirection(Enum):
    UP = 0
    DOWN = 1

class _SpinButton(QWidget):
    clicked = pyqtSignal()
    def __init__(self, direction: _ArrowDirection, parent: QWidget = None):
        super().__init__(parent)
        self.setFixedSize(32, 26)
        self.direction = direction
        self._hovered = False
        self._pressed = False
        self.theme_manager = ThemeManager.get_instance()
        self.theme_manager.theme_changed.connect(self.update)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def enterEvent(self, event): self._hovered = True; self.update()
    def leaveEvent(self, event): self._hovered = False; self.update()
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self._pressed = True; self.update()
    def mouseReleaseEvent(self, event):
        if self._pressed and event.button() == Qt.MouseButton.LeftButton:
            self._pressed = False; self.update()
            if self.rect().contains(event.pos()): self.clicked.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg_color = QColor("transparent")
        if self._pressed: bg_color = self.theme_manager.get_color("button.default.background.pressed")
        elif self._hovered: bg_color = self.theme_manager.get_color("button.default.background.hover")
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(bg_color); painter.drawRoundedRect(self.rect(), 4, 4)
        arrow_color = self.theme_manager.get_color("dialog.text")
        arrow_color.setAlpha(160)
        painter.setPen(QPen(arrow_color, 1.4))
        center = self.rect().center()
        y_offset = 1.0
        draw_center = QPointF(center.x(), center.y() + y_offset)
        w = self.width() * 0.20
        h = w * 0.5
        if self.direction == _ArrowDirection.UP:
            p1 = QPointF(draw_center.x() - w, draw_center.y() + h / 2)
            p2 = QPointF(draw_center.x(), draw_center.y() - h)
            p3 = QPointF(draw_center.x() + w, draw_center.y() + h / 2)
        else:
            p1 = QPointF(draw_center.x() - w, draw_center.y() - h / 2)
            p2 = QPointF(draw_center.x(), draw_center.y() + h)
            p3 = QPointF(draw_center.x() + w, draw_center.y() - h / 2)
        painter.drawPolyline(QPolygonF([p1, p2, p3]))

class FluentSpinBox(QWidget):
    valueChanged = pyqtSignal(int)
    RADIUS = 6

    def __init__(self, parent: QWidget = None, default_value: int = 30):
        super().__init__(parent)
        self.setFixedHeight(33)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.theme_manager = ThemeManager.get_instance()
        self._minimum, self._maximum = 0, 99
        self._value = 0
        self._last_accepted_text = "0"

        self._default_value = default_value

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 0, 4, 0); main_layout.setSpacing(4)

        self.line_edit = FocusLineEdit()
        self.line_edit.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.line_edit.setStyleSheet("border: none; background: transparent; padding: 0; margin: 0;")
        self.line_edit.textChanged.connect(self._on_text_changed)
        self.line_edit.editingFinished.connect(self._on_text_edited)
        self.setFocusProxy(self.line_edit)
        self.line_edit.focusChanged.connect(self.update)

        main_layout.addStretch(1)
        main_layout.addWidget(self.line_edit)

        buttons_container = QWidget()
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(0, 0, 0, 0); buttons_layout.setSpacing(2)
        self.down_button = _SpinButton(_ArrowDirection.DOWN, self)
        self.up_button = _SpinButton(_ArrowDirection.UP, self)
        buttons_layout.addWidget(self.down_button); buttons_layout.addWidget(self.up_button)
        main_layout.addWidget(buttons_container)

        self.up_button.clicked.connect(self._step_up)
        self.down_button.clicked.connect(self._step_down)

        self.theme_manager.theme_changed.connect(self._on_theme_changed)

        self.setValue(0)
        self._on_theme_changed()

    def setDefaultValue(self, value: int):
        """Allows changing default value after widget creation."""
        self._default_value = value

    def _on_text_edited(self):
        """Finalizes value when focus is lost."""
        current_text = self.line_edit.text().strip()

        if not current_text:
            self.setValue(self._default_value)
            return

        try:
            final_value = int(current_text)
            self.setValue(final_value)
        except (ValueError, TypeError):
            self.setValue(self._value)

    def setValue(self, value: int):
        clamped_value = max(self._minimum, min(value, self._maximum))

        if self._value != clamped_value:
             self._value = clamped_value
             self.valueChanged.emit(self._value)

        new_text = str(clamped_value)
        self._last_accepted_text = new_text

        if self.line_edit.text() != new_text:
            self.line_edit.blockSignals(True)
            self.line_edit.setText(new_text)
            self.line_edit.blockSignals(False)

        self.update()

    def value(self) -> int:
        return self._value

    def _on_text_changed(self, text: str):
        if not text or (text == '-' and self._minimum < 0):
            return
        try:
            value = int(text)
            if self._minimum <= value <= self._maximum:
                self._last_accepted_text = text
            else:
                self._revert_text()
        except ValueError:
            self._revert_text()

    def _revert_text(self):
        self.line_edit.blockSignals(True)
        self.line_edit.setText(self._last_accepted_text)
        self.line_edit.blockSignals(False)

    def _step_up(self):
        self.setValue(self.value() + 1)

    def _step_down(self):
        self.setValue(self.value() - 1)

    def setRange(self, min_val, max_val):
        self._minimum, self._maximum = min_val, max_val
        self.setValue(self.value())
        self._update_line_edit_width()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.line_edit.hasFocus():
            self.line_edit.setFocus()
            self.line_edit.selectAll()
        super().mousePressEvent(event)

    def _on_theme_changed(self):
        text_color = self.theme_manager.get_color("dialog.text")
        self.line_edit.setStyleSheet(f"border: none; background: transparent; padding: 0; margin: 0; color: {text_color.name()};")
        self._update_line_edit_width()
        self.update()

    def _update_line_edit_width(self):
        fm = QFontMetrics(self.line_edit.font())
        max_width = fm.horizontalAdvance(str(self._maximum)) + 12
        self.line_edit.setFixedWidth(max_width)

    def focusOutEvent(self, event):
        self._on_text_edited()
        super().focusOutEvent(event)

    def wheelEvent(self, event):
        if not self.isEnabled():
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta > 0: self._step_up()
        elif delta < 0: self._step_down()
        event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg_color = self.theme_manager.get_color("dialog.input.background")
        painter.setBrush(bg_color); painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), self.RADIUS, self.RADIUS)
        r = self.rect(); rr = QRectF(r).adjusted(0.5, 0.5, -0.5, -0.5)
        thin_border_color = QColor(self.theme_manager.get_color("input.border.thin"))
        alpha = max(8, int(thin_border_color.alpha() * 0.66))
        thin_border_color.setAlpha(alpha); pen = QPen(thin_border_color); pen.setWidthF(0.66)
        painter.setPen(pen); painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rr, self.RADIUS, self.RADIUS)
        if self.line_edit.hasFocus():
            underline_config = UnderlineConfig(color=self.theme_manager.get_color("accent"), alpha=255, thickness=1.0)
        else:
            underline_config = UnderlineConfig(alpha=40, thickness=1.0)
        draw_bottom_underline(painter, r, self.theme_manager, underline_config)
