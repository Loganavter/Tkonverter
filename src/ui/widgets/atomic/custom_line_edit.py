from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QRegion
from PyQt6.QtWidgets import QLineEdit

from ui.theme import ThemeManager
from ui.widgets.helpers.underline_painter import UnderlineConfig, draw_bottom_underline

class CustomLineEdit(QLineEdit):
    RADIUS = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.setProperty("custom-line-edit", True)

        self.setProperty("class", "primary")
        self.theme_manager = ThemeManager.get_instance()
        try:
            self.theme_manager.theme_changed.connect(self.update)
        except Exception:
            pass

    def _style_prefix(self) -> str:
        btn_class = str(self.property("class") or "")
        return "button.primary" if "primary" in btn_class else "button.default"

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self.update()

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self.update()

    def resizeEvent(self, e):
        try:
            w, h = self.width(), self.height()
            if w <= 0 or h <= 0:
                self.clearMask()
            else:
                radius = float(self.RADIUS)
                path = QPainterPath()

                rectf = QRectF(-1.0, 0.0, float(w + 1), float(h))
                path.addRoundedRect(rectf, radius, radius)
                region = QRegion(path.toFillPolygon().toPolygon())
                self.setMask(region)
        except Exception:
            pass
        super().resizeEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            r = self.rect()
            rr = QRectF(r).adjusted(0.5, 0.5, -0.5, -0.5)

            thin_border_color = QColor(
                self.theme_manager.get_color("input.border.thin")
            )
            alpha = max(8, int(thin_border_color.alpha() * 0.66))
            thin_border_color.setAlpha(alpha)
            pen = QPen(thin_border_color)
            pen.setWidthF(0.66)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            painter.setPen(pen)
            painter.drawRoundedRect(rr, self.RADIUS, self.RADIUS)

            if self.hasFocus():
                underline_config = UnderlineConfig(color=self.theme_manager.get_color("accent"), alpha=255, thickness=1.0)
            else:
                underline_config = UnderlineConfig(alpha=120, thickness=1.0)

            draw_bottom_underline(painter, r, self.theme_manager, underline_config)
            painter.end()
        except Exception:
            pass
