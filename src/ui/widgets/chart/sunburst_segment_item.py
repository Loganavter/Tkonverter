import math
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QObject, QPointF
from PyQt6.QtGui import QColor, QPen, QBrush, QPainterPath, QFont
from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsTextItem

from src.core.view_models import SunburstSegmentViewModel

class SegmentSignals(QObject):
    clicked = pyqtSignal(str, int)
    hover_enter = pyqtSignal(object, QPointF)
    hover_move = pyqtSignal(object, QPointF)
    hover_leave = pyqtSignal()

class SunburstSegmentItem(QGraphicsPathItem):

    SCENE_SCALE = 400.0

    def __init__(self, data: SunburstSegmentViewModel, signals: SegmentSignals, theme_manager):
        super().__init__()
        self.data = data
        self.signals = signals
        self.theme_manager = theme_manager

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable, False)

        self._update_path()
        self._setup_appearance()

        if data.label and data.font_size > 0:
            self._add_label()

    def _update_path(self):
        path = QPainterPath()

        inner_r = self.data.inner_radius * self.SCENE_SCALE
        outer_r = self.data.outer_radius * self.SCENE_SCALE

        start_angle_deg = math.degrees(self.data.start_angle)
        end_angle_deg = math.degrees(self.data.end_angle)
        sweep_angle = end_angle_deg - start_angle_deg

        qt_start_angle = start_angle_deg
        qt_sweep_angle = sweep_angle

        outer_rect = QRectF(-outer_r, -outer_r, outer_r * 2, outer_r * 2)
        inner_rect = QRectF(-inner_r, -inner_r, inner_r * 2, inner_r * 2)

        path.arcMoveTo(outer_rect, qt_start_angle)
        path.arcTo(outer_rect, qt_start_angle, qt_sweep_angle)
        path.arcTo(inner_rect, qt_start_angle + qt_sweep_angle, -qt_sweep_angle)
        path.closeSubpath()
        self.setPath(path)

    def _setup_appearance(self):
        self.base_color = QColor(self.data.color)
        bg_color = self.theme_manager.get_color("dialog.background")
        self.setBrush(QBrush(self.base_color))
        sweep_rad = self.data.end_angle - self.data.start_angle
        full_circle = 2.0 * math.pi
        if sweep_rad >= full_circle - 0.01:
            self.setPen(QPen(Qt.PenStyle.NoPen))
        else:
            self.setPen(QPen(bg_color, 1.0, Qt.PenStyle.SolidLine))

    def _add_label(self):
        text_item = QGraphicsTextItem(self.data.label, self)
        font = QFont()
        font.setPointSize(int(self.data.font_size * 1.5))
        text_item.setFont(font)
        text_item.setDefaultTextColor(QColor(255, 255, 255))
        br = text_item.boundingRect()
        text_item.setTransformOriginPoint(br.width() / 2, br.height() / 2)

        mid_angle_rad = (self.data.start_angle + self.data.end_angle) / 2.0
        center_radius = (self.data.inner_radius + self.data.outer_radius) / 2.0
        label_x = center_radius * math.cos(mid_angle_rad) * self.SCENE_SCALE
        label_y = center_radius * math.sin(mid_angle_rad) * self.SCENE_SCALE

        x = label_x - br.width() / 2
        y = -label_y - br.height() / 2
        text_item.setPos(x, y)

        rotation_deg = math.degrees(mid_angle_rad)
        if 90 < rotation_deg < 270:
            rotation_deg -= 180
        text_item.setRotation(-rotation_deg)
        text_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        text_item.setAcceptHoverEvents(False)

    def hoverEnterEvent(self, event):
        self.setBrush(QBrush(self.base_color.lighter(115)))
        self.signals.hover_enter.emit(self.data, QPointF(event.screenPos()))
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event):
        self.signals.hover_move.emit(self.data, QPointF(event.screenPos()))
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(QBrush(self.base_color))
        self.signals.hover_leave.emit()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.signals.clicked.emit(self.data.node_id, 1)
        elif event.button() == Qt.MouseButton.RightButton:
            self.signals.clicked.emit(self.data.node_id, 3)
        event.accept()
