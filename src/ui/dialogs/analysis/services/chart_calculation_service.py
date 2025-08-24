"""
Service for sunburst chart calculations.

Responsible for mathematical calculations, geometry and positioning.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple
from datetime import datetime

from core.analysis.tree_analyzer import TreeNode
from resources.translations import tr

@dataclass
class SunburstSegment:
    """Sunburst chart segment."""

    inner_radius: float
    outer_radius: float
    start_angle: float
    end_angle: float
    color: str
    node: TreeNode
    text: str
    level: int

class ChartCalculationService:
    """Service for sunburst chart calculations."""

    def __init__(self):

        self.CENTER_HOLE_RADIUS = 0.35
        self.RING_WIDTH = 0.25
        self.MAX_DEPTH = 3

        self.YEAR_SATURATION = 0.8
        self.MONTH_SATURATION = 0.7
        self.DAY_SATURATION = 0.55

        self.YEAR_BRIGHTNESS = 0.9
        self.MONTH_BRIGHTNESS = 0.8
        self.DAY_BRIGHTNESS = 0.7

    def calculate_segments(
        self,
        root_node: TreeNode,
        disabled_nodes: Set[TreeNode],
        canvas_size: Tuple[int, int],
    ) -> List[SunburstSegment]:
        """
        Calculates sunburst chart segments.

        Args:
            root_node: Root tree node
            disabled_nodes: Disabled nodes
            canvas_size: Canvas size (width, height)

        Returns:
            List of segments for rendering
        """
        if not root_node or not root_node.children:
            return []

        segments = []
        canvas_width, canvas_height = canvas_size
        center_x = canvas_width / 2
        center_y = canvas_height / 2

        max_radius = min(center_x, center_y) * 0.9

        self._calculate_level_segments(
            root_node.children,
            disabled_nodes,
            segments,
            level=0,
            start_angle=0,
            end_angle=2 * math.pi,
            max_radius=max_radius,
        )

        return segments

    def _get_translated_node_name(self, node: TreeNode) -> str:
        """Returns translated node name for display."""
        if not node:
            return ""

        name = node.name

        if tr(" others") in name:
            return name

        if name == "Total":
            return tr("Total")

        if getattr(node, "date_level", None) == "month" and name.isdigit():
            try:
                month_num = int(name)
                month_key = f"month_gen_{month_num}"
                translated = tr(month_key)

                if translated == month_key:
                    return datetime(2000, month_num, 1).strftime("%B")
                return translated
            except ValueError:
                pass

        is_month = False
        if node.parent and node.parent.name.isdigit() and len(node.parent.name) == 4:
            is_month = True
        elif name.isdigit() and len(name) == 2 and 1 <= int(name) <= 12:
            is_month = True
        if is_month and name.isdigit():
            try:
                month_num = int(name)
                month_key = f"month_gen_{month_num}"
                translated = tr(month_key)
                if translated == month_key:
                    return datetime(2000, month_num, 1).strftime("%B")
                return translated
            except ValueError:
                pass

        return name

    def _calculate_level_segments(
        self,
        nodes: List[TreeNode],
        disabled_nodes: Set[TreeNode],
        segments: List[SunburstSegment],
        level: int,
        start_angle: float,
        end_angle: float,
        max_radius: float,
    ):
        """Recursively calculates segments for level."""
        if level >= self.MAX_DEPTH:
            return

        inner_radius = self.CENTER_HOLE_RADIUS + level * self.RING_WIDTH
        outer_radius = inner_radius + self.RING_WIDTH

        inner_radius *= max_radius
        outer_radius *= max_radius

        total_value = sum(node.value for node in nodes if node not in disabled_nodes)

        if total_value == 0:
            return

        current_angle = start_angle
        angle_range = end_angle - start_angle

        for node in nodes:
            if node in disabled_nodes:
                continue

            node_angle = (node.value / total_value) * angle_range
            segment_end_angle = current_angle + node_angle

            color = self._calculate_color(node, level)
            translated_name = self._get_translated_node_name(node)
            segment = SunburstSegment(
                inner_radius=inner_radius,
                outer_radius=outer_radius,
                start_angle=current_angle,
                end_angle=segment_end_angle,
                color=color,
                node=node,
                text=translated_name,
                level=level,
            )
            segments.append(segment)

            children_to_process = []
            if node.children:
                children_to_process.extend(node.children)
            if hasattr(node, "aggregated_children") and node.aggregated_children:
                children_to_process.extend(node.aggregated_children)

            if children_to_process and level < self.MAX_DEPTH - 1:
                self._calculate_level_segments(
                    children_to_process,
                    disabled_nodes,
                    segments,
                    level + 1,
                    current_angle,
                    segment_end_angle,
                    max_radius,
                )

            current_angle = segment_end_angle

    def _calculate_color(self, node: TreeNode, level: int) -> str:
        """Calculates segment color."""

        if level == 0:
            saturation = self.YEAR_SATURATION
            brightness = self.YEAR_BRIGHTNESS
        elif level == 1:
            saturation = self.MONTH_SATURATION
            brightness = self.MONTH_BRIGHTNESS
        else:
            saturation = self.DAY_SATURATION
            brightness = self.DAY_BRIGHTNESS

        name_hash = hash(node.name) % 360
        hue = name_hash / 360.0

        return self._hsv_to_hex(hue, saturation, brightness)

    def _hsv_to_hex(self, h: float, s: float, v: float) -> str:
        """Converts HSV to HEX."""
        import colorsys

        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

    def calculate_text_position(self, segment: SunburstSegment) -> Tuple[float, float]:
        """Calculates text position for segment."""

        mid_radius = (segment.inner_radius + segment.outer_radius) / 2

        mid_angle = (segment.start_angle + segment.end_angle) / 2

        x = mid_radius * math.cos(mid_angle)
        y = mid_radius * math.sin(mid_angle)

        return x, y

    def find_segment_at_position(
        self,
        segments: List[SunburstSegment],
        x: float,
        y: float,
        center_x: float,
        center_y: float,
    ) -> Optional[SunburstSegment]:
        """Finds segment at specified position."""

        dx = x - center_x
        dy = y - center_y
        radius = math.sqrt(dx * dx + dy * dy)
        angle = math.atan2(dy, dx)

        if angle < 0:
            angle += 2 * math.pi

        for segment in segments:
            if (
                segment.inner_radius <= radius <= segment.outer_radius
                and segment.start_angle <= angle <= segment.end_angle
            ):
                return segment

        return None
