"""
Service for working with charts.

- Mathematical calculations for sunburst charts
- Color schemes and algorithms
- Tree traversal and depth calculations
- Node filtering logic
- Element positioning
"""

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from core.analysis.tree_analyzer import TreeNode, aggregate_children_for_view
from core.view_models import ChartViewModel, SunburstSegment

logger = logging.getLogger(__name__)

YEAR_SATURATION = 0.85
MONTH_SATURATION = 0.70
DAY_SATURATION = 0.60

YEAR_BRIGHTNESS = 0.95
MONTH_BRIGHTNESS = 0.85
DAY_BRIGHTNESS = 0.75

DARKEN_FACTOR = 0.7

DEFAULT_INNER_RADIUS = 30
RING_WIDTH = 70
MIN_ANGLE_FOR_TEXT = 0.1

@dataclass
class ChartGeometry:
    """Geometric parameters of the chart."""

    center_x: float
    center_y: float
    inner_radius: float
    ring_width: float
    total_radius: float

    def get_ring_bounds(self, level: int) -> Tuple[float, float]:
        """Returns inner and outer radius for the level."""
        inner = self.inner_radius + level * self.ring_width
        outer = inner + self.ring_width
        return inner, outer

class ChartService:
    """Service for working with charts."""

    def __init__(self):
        self._current_geometry: Optional[ChartGeometry] = None

    def calculate_sunburst_data(
        self,
        root_node: TreeNode,
        disabled_nodes: Set[TreeNode],
        chart_width: int = 400,
        chart_height: int = 400,
        color_scheme: str = "default",
    ) -> ChartViewModel:
        """
        Calculates chart data in abstract coordinates.
        Returns normalized chart geometry for rendering.
        """

        CENTER_HOLE_RADIUS, RING_WIDTH, MAX_DEPTH = 0.35, 0.25, 3

        segments = []
        start_absolute_depth = self.get_node_absolute_depth(root_node)

        self._build_segments_recursive_normalized(
            node=root_node,
            start_angle=0,
            end_angle=360,
            start_absolute_depth=start_absolute_depth,
            segments=segments,
            disabled_nodes=disabled_nodes,
        )

        unit = self._detect_unit_from_node(root_node)

        geometry = {
            "center_hole_radius": CENTER_HOLE_RADIUS,
            "ring_width": RING_WIDTH,
            "total_radius": CENTER_HOLE_RADIUS + (MAX_DEPTH * RING_WIDTH) + 0.05,
        }

        view_model = ChartViewModel(
            segments=segments,
            unit=unit,
            chart_width=chart_width,
            chart_height=chart_height,
            disabled_nodes=disabled_nodes,
            geometry=geometry
        )
        return view_model

    def _build_segments_recursive(
        self,
        node: TreeNode,
        disabled_nodes: Set[TreeNode],
        start_angle: float,
        end_angle: float,
        level: int,
        geometry: ChartGeometry,
        color_scheme: str,
        segments: List[SunburstSegment],
    ):
        """Recursively builds chart segments."""
        if not node.children and not (
            hasattr(node, "aggregated_children") and node.aggregated_children
        ):
            return

        children = node.children[:]
        if hasattr(node, "aggregated_children") and node.aggregated_children:
            children.extend(node.aggregated_children)

        if not children:
            return

        total_value = sum(child.value for child in children)
        if total_value <= 0:
            return

        inner_radius, outer_radius = geometry.get_ring_bounds(level)

        if outer_radius > geometry.total_radius:
            return

        current_angle = start_angle
        angle_range = end_angle - start_angle

        for i, child in enumerate(children):
            if child.value <= 0:
                continue

            angle_size = (child.value / total_value) * angle_range
            child_end_angle = current_angle + angle_size

            show_text = angle_size >= MIN_ANGLE_FOR_TEXT

            angle_deg = math.degrees((current_angle + child_end_angle) / 2)
            color = self.get_color_for_segment(angle_deg, level, color_scheme)

            is_disabled = self.is_effectively_disabled(child, disabled_nodes)
            if is_disabled:
                color = self.darken_color(color)

            text_position = None
            if show_text:
                text_position = self._calculate_text_position(
                    current_angle, child_end_angle, inner_radius, outer_radius
                )

            segment = SunburstSegment(
                inner_radius=inner_radius,
                outer_radius=outer_radius,
                start_angle=current_angle,
                end_angle=child_end_angle,
                color=color,
                node=child,
                text=child.name if show_text else "",
                text_position=text_position,
                is_disabled=is_disabled,
            )

            segments.append(segment)

            self._build_segments_recursive(
                child,
                disabled_nodes,
                current_angle,
                child_end_angle,
                level + 1,
                geometry,
                color_scheme,
                segments,
            )

            current_angle = child_end_angle

    def _build_segments_recursive_normalized(
        self, node, start_angle, end_angle, start_absolute_depth, segments, disabled_nodes
    ):
        CENTER_HOLE_RADIUS, RING_WIDTH, MAX_DEPTH = 0.35, 0.25, 3
        total_value = node.value
        if total_value <= 0: return

        current_angle = start_angle

        children_to_display = aggregate_children_for_view(node, force_full_detail=(self.get_node_absolute_depth(node) > start_absolute_depth))

        for child in children_to_display:
            child_absolute_depth = self.get_node_absolute_depth(child)
            relative_depth = child_absolute_depth - start_absolute_depth

            if relative_depth <= 0 or relative_depth > MAX_DEPTH: continue

            outer_radius = CENTER_HOLE_RADIUS + relative_depth * RING_WIDTH
            sweep_angle = (child.value / total_value) * (end_angle - start_angle)
            mid_angle_deg = current_angle + sweep_angle / 2.0

            color = self.get_color_for_segment(mid_angle_deg, child_absolute_depth - 1, "default")
            is_disabled = self.is_effectively_disabled(child, disabled_nodes)

            segment = SunburstSegment(
                inner_radius=outer_radius - RING_WIDTH,
                outer_radius=outer_radius,
                start_angle=math.radians(current_angle),
                end_angle=math.radians(current_angle + sweep_angle),
                color=self.darken_color(color) if is_disabled else color,
                node=child,
                text=child.name,
                is_disabled=is_disabled,
            )
            segments.append(segment)

            if (
                (child.children or (hasattr(child, "aggregated_children") and child.aggregated_children))
                and getattr(child, 'date_level', None) != 'others'
            ):
                self._build_segments_recursive_normalized(
                    child, current_angle, current_angle + sweep_angle, start_absolute_depth, segments, disabled_nodes
                )

            current_angle += sweep_angle

    def _calculate_text_position(
        self,
        start_angle: float,
        end_angle: float,
        inner_radius: float,
        outer_radius: float,
    ) -> Tuple[float, float]:
        """Calculates text position in segment."""

        center_angle = (start_angle + end_angle) / 2

        center_radius = (inner_radius + outer_radius) / 2

        if self._current_geometry:
            x = self._current_geometry.center_x + center_radius * math.cos(center_angle)
            y = self._current_geometry.center_y + center_radius * math.sin(center_angle)
            return (x, y)

        return (0, 0)

    def get_color_for_segment(
        self, angle_deg: float, level: int, color_scheme: str = "default"
    ) -> str:
        """
        Calculates segment color based on angle and level.

        Args:
            angle_deg: Angle in degrees
            level: Level in tree (0 = root)
            color_scheme: Color scheme

        Returns:
            str: Color in hex format
        """
        if color_scheme == "default":
            return self._get_filelight_color(angle_deg, level)
        else:

            return self._get_filelight_color(angle_deg, level)

    def _get_filelight_color(self, angle_deg: float, level: int) -> str:
        """KDE Filelight style color algorithm."""
        from matplotlib.colors import hsv_to_rgb

        hue = (angle_deg % 360) / 360.0

        sats = [YEAR_SATURATION, MONTH_SATURATION, DAY_SATURATION]
        vals = [YEAR_BRIGHTNESS, MONTH_BRIGHTNESS, DAY_BRIGHTNESS]

        saturation = sats[min(level, len(sats) - 1)]
        value = vals[min(level, len(vals) - 1)]

        rgb = hsv_to_rgb((hue, saturation, value))

        return "#{:02x}{:02x}{:02x}".format(
            int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255)
        )

    def darken_color(self, color: str) -> str:
        """Darkens the color."""
        from matplotlib.colors import to_rgb

        try:
            rgb = to_rgb(color)
            darkened = tuple(c * DARKEN_FACTOR for c in rgb)
            return "#{:02x}{:02x}{:02x}".format(
                int(darkened[0] * 255), int(darkened[1] * 255), int(darkened[2] * 255)
            )
        except:
            return color

    def get_node_absolute_depth(self, node: TreeNode) -> int:
        """Calculates absolute depth of node in tree."""
        depth = 0
        current = node
        while current and current.parent:
            depth += 1
            current = current.parent
        return depth

    def get_max_relative_depth(self, node: TreeNode, current_depth: int = 0) -> int:
        """Calculates maximum relative depth of subtree."""
        children_to_scan = node.children[:]
        if hasattr(node, "aggregated_children") and node.aggregated_children:
            children_to_scan.extend(node.aggregated_children)

        if not children_to_scan:
            return current_depth

        return max(
            self.get_max_relative_depth(child, current_depth + 1)
            for child in children_to_scan
        )

    def get_descendant_day_nodes(self, node: TreeNode) -> List[TreeNode]:
        """Gets all child day nodes (leaves with numeric names)."""
        day_nodes = []

        def collect_day_nodes(current_node):

            children_to_check = current_node.children[:]
            if (
                hasattr(current_node, "aggregated_children")
                and current_node.aggregated_children
            ):
                children_to_check.extend(current_node.aggregated_children)

            if not children_to_check:

                if current_node.name.isdigit():
                    day_nodes.append(current_node)
            else:

                for child in children_to_check:
                    collect_day_nodes(child)

        collect_day_nodes(node)
        return day_nodes

    def is_effectively_disabled(
        self, node: TreeNode, disabled_nodes: Set[TreeNode]
    ) -> bool:
        """
        Checks if node is effectively disabled.

        A node is considered effectively disabled if:
        1. It itself is in disabled_nodes, OR
        2. All its child day nodes are disabled
        """
        if node in disabled_nodes:
            return True

        day_nodes = self.get_descendant_day_nodes(node)
        if not day_nodes:

            is_leaf_node = not node.children and not (
                hasattr(node, "aggregated_children") and node.aggregated_children
            )
            if is_leaf_node and node.name.isdigit():
                return node in disabled_nodes
            return False

        return all(day_node in disabled_nodes for day_node in day_nodes)

    def calculate_filtered_value(
        self, root_node: TreeNode, disabled_nodes: Set[TreeNode]
    ) -> float:
        """Calculates filtered value (sum of enabled nodes)."""
        day_nodes = self.get_descendant_day_nodes(root_node)

        if not day_nodes:

            return (
                0.0
                if self.is_effectively_disabled(root_node, disabled_nodes)
                else root_node.value
            )

        filtered_sum = sum(
            day_node.value for day_node in day_nodes if day_node not in disabled_nodes
        )

        return filtered_sum

    def _detect_unit_from_node(self, node: TreeNode) -> str:
        """Attempts to determine unit of measurement from tree."""

        if "token" in node.name.lower():
            return "tokens"
        else:
            return "chars"

    def find_segment_at_position(
        self, x: float, y: float, view_model: ChartViewModel
    ) -> Optional[SunburstSegment]:
        """
        Finds segment at specified position.

        Args:
            x: X coordinate
            y: Y coordinate
            view_model: ViewModel with segments

        Returns:
            Optional[SunburstSegment]: Found segment or None
        """

        dx = x - view_model.center_x
        dy = y - view_model.center_y
        radius = math.sqrt(dx * dx + dy * dy)

        if radius == 0:
            return None

        angle = math.atan2(dy, dx)

        if angle < 0:
            angle += 2 * math.pi

        for segment in view_model.segments:
            if (
                segment.inner_radius <= radius <= segment.outer_radius
                and segment.start_angle <= angle <= segment.end_angle
            ):
                return segment

        return None

    def get_segment_tooltip(self, segment: SunburstSegment, unit: str) -> str:
        """Creates tooltip text for segment."""
        value_text = f"{int(segment.node.value):,} {unit}"

        if segment.is_disabled:
            return f"{segment.node.name}: {value_text} (disabled)"
        else:
            return f"{segment.node.name}: {value_text}"

    def toggle_node_selection(
        self, node: TreeNode, disabled_nodes: Set[TreeNode]
    ) -> Set[TreeNode]:
        """
        Toggles node selection and returns new set of disabled nodes.

        Args:
            node: Node to toggle
            disabled_nodes: Current set of disabled nodes

        Returns:
            Set[TreeNode]: New set of disabled nodes
        """
        new_disabled = disabled_nodes.copy()

        if node in new_disabled:
            new_disabled.remove(node)
        else:
            new_disabled.add(node)

        return new_disabled

    def get_chart_statistics(self, view_model: ChartViewModel) -> Dict[str, Any]:
        """Returns chart statistics."""
        total_segments = len(view_model.segments)
        disabled_segments = sum(1 for s in view_model.segments if s.is_disabled)

        return {
            "total_segments": total_segments,
            "enabled_segments": total_segments - disabled_segments,
            "disabled_segments": disabled_segments,
            "total_value": view_model.center_value,
            "filtered_value": view_model.filtered_value,
            "filter_percentage": (
                (1 - view_model.filtered_value / view_model.center_value) * 100
                if view_model.center_value > 0
                else 0
            ),
        }
