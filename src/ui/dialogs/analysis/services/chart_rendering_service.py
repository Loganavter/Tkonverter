"""
Service for rendering sunburst chart.

Responsible for matplotlib rendering, styles and animations.
"""

import math
from typing import List, Optional

import matplotlib.patches as patches
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from ui.dialogs.analysis.services.chart_calculation_service import SunburstSegment

class ChartRenderingService:
    """Service for rendering sunburst chart."""

    def __init__(self):
        self.figure = None
        self.axes = None
        self.canvas = None

        self.HIGHLIGHT_ALPHA = 0.7
        self.DARKEN_FACTOR = 0.4
        self.FONT_SIZE = 14

    def create_canvas(
        self, width: int = 4, height: int = 4, dpi: int = 100
    ) -> FigureCanvas:
        """Creates matplotlib canvas."""
        self.figure, self.axes = plt.subplots(figsize=(width, height), dpi=dpi)
        self.canvas = FigureCanvas(self.figure)

        self.axes.set_aspect("equal")
        self.axes.axis("off")

        from core.theme import ThemeManager
        theme_manager = ThemeManager.get_instance()
        bg_color = theme_manager.get_color("dialog.background")
        self.figure.patch.set_facecolor(bg_color.name())

        return self.canvas

    def render_segments(
        self,
        segments: List[SunburstSegment],
        center_x: float,
        center_y: float,
        hovered_segment: Optional[SunburstSegment] = None,
    ):
        """Renders chart segments."""
        if not self.axes:
            return

        self.axes.clear()
        self.axes.set_aspect("equal")
        self.axes.axis("off")

        max_radius = max((s.outer_radius for s in segments), default=100)
        margin = max_radius * 0.1
        self.axes.set_xlim(-max_radius - margin, max_radius + margin)
        self.axes.set_ylim(-max_radius - margin, max_radius + margin)

        for segment in segments:
            self._render_segment(
                segment, center_x, center_y, hovered_segment == segment
            )

        self._render_center_text(center_x, center_y)

        self.canvas.draw()

    def _render_segment(
        self,
        segment: SunburstSegment,
        center_x: float,
        center_y: float,
        is_hovered: bool = False,
    ):
        """Renders one segment."""

        start_angle_deg = math.degrees(segment.start_angle)
        end_angle_deg = math.degrees(segment.end_angle)
        angle_width = end_angle_deg - start_angle_deg

        color = segment.color
        if is_hovered:
            color = self._darken_color(color)

        wedge = patches.Wedge(
            (center_x, center_y),
            segment.outer_radius,
            start_angle_deg,
            start_angle_deg + angle_width,
            width=segment.outer_radius - segment.inner_radius,
            facecolor=color,
            edgecolor="white",
            linewidth=1,
            alpha=self.HIGHLIGHT_ALPHA if is_hovered else 1.0,
        )

        self.axes.add_patch(wedge)

        if angle_width > 10:
            self._render_segment_text(segment, center_x, center_y)

    def _render_segment_text(
        self, segment: SunburstSegment, center_x: float, center_y: float
    ):
        """Renders segment text."""
        import math

        mid_radius = (segment.inner_radius + segment.outer_radius) / 2
        mid_angle = (segment.start_angle + segment.end_angle) / 2

        text_x = center_x + mid_radius * math.cos(mid_angle)
        text_y = center_y + mid_radius * math.sin(mid_angle)

        font_size = self._calculate_font_size(segment)

        text_angle = math.degrees(mid_angle)
        if text_angle > 90 and text_angle < 270:
            text_angle += 180

        self.axes.text(
            text_x,
            text_y,
            segment.text,
            ha="center",
            va="center",
            fontsize=font_size,
            rotation=text_angle,
            color="white" if self._is_dark_color(segment.color) else "black",
            weight="bold",
        )

    def _render_center_text(self, center_x: float, center_y: float):
        """Renders central text."""
        self.axes.text(
            center_x,
            center_y,
            "Analysis",
            ha="center",
            va="center",
            fontsize=self.FONT_SIZE + 2,
            weight="bold",
            color="black",
        )

    def _calculate_font_size(self, segment: SunburstSegment) -> int:
        """Calculates font size for segment."""
        import math

        angle_size = segment.end_angle - segment.start_angle
        radius_size = segment.outer_radius - segment.inner_radius

        base_size = 8
        size_factor = math.sqrt(angle_size * radius_size) * 2

        return max(6, min(base_size + int(size_factor), 16))

    def _darken_color(self, hex_color: str) -> str:
        """Darkens color for hover effect."""
        if hex_color.startswith("#"):
            hex_color = hex_color[1:]

        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        r = int(r * (1 - self.DARKEN_FACTOR))
        g = int(g * (1 - self.DARKEN_FACTOR))
        b = int(b * (1 - self.DARKEN_FACTOR))

        return f"#{r:02x}{g:02x}{b:02x}"

    def _is_dark_color(self, hex_color: str) -> bool:
        """Determines if color is dark."""
        if hex_color.startswith("#"):
            hex_color = hex_color[1:]

        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        brightness = (r * 299 + g * 587 + b * 114) / 1000
        return brightness < 128

    def clear_chart(self):
        """Clears chart."""
        if self.axes:
            self.axes.clear()
            self.axes.set_aspect("equal")
            self.axes.axis("off")

        if self.canvas:
            self.canvas.draw()
