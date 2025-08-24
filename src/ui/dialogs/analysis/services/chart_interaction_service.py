"""
Service for handling sunburst chart interactions.

Responsible for handling clicks, hovers, tooltips and selection state.
"""

from typing import Callable, Optional, Set
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

from core.analysis.tree_analyzer import TreeNode
from resources.translations import tr

from ui.dialogs.analysis.services.chart_calculation_service import SunburstSegment

class ChartInteractionService(QObject):
    """Service for handling chart interactions."""

    hover_changed = pyqtSignal(object)
    segment_clicked = pyqtSignal(object)
    tooltip_changed = pyqtSignal(str, int, int)
    cursor_changed = pyqtSignal(str)
    selection_changed = pyqtSignal(set)

    def __init__(self):
        super().__init__()

        self._hovered_segment: Optional[SunburstSegment] = None
        self._disabled_nodes: Set[TreeNode] = set()
        self._segments: list = []

        self._show_tooltips = True
        self._allow_selection = True

    def set_segments(self, segments: list):
        """Sets current segments."""
        self._segments = segments

    def set_disabled_nodes(self, disabled_nodes: Set[TreeNode]):
        """Sets disabled nodes."""
        old_disabled = self._disabled_nodes.copy()
        self._disabled_nodes = disabled_nodes.copy()

        if old_disabled != self._disabled_nodes:
            self.selection_changed.emit(self._disabled_nodes)

    def get_disabled_nodes(self) -> Set[TreeNode]:
        """Returns disabled nodes."""
        return self._disabled_nodes.copy()

    def handle_mouse_move(
        self,
        x: float,
        y: float,
        center_x: float,
        center_y: float,
        find_segment_func: Callable,
    ):
        """Handles mouse movement."""

        segment = find_segment_func(self._segments, x, y, center_x, center_y)

        if segment != self._hovered_segment:
            self._hovered_segment = segment
            self.hover_changed.emit(segment)

            if segment:

                if self._show_tooltips:
                    tooltip_text = self._generate_tooltip_text(segment)
                    self.tooltip_changed.emit(tooltip_text, int(x), int(y))

                self.cursor_changed.emit("pointer")
            else:

                self.tooltip_changed.emit("", 0, 0)
                self.cursor_changed.emit("default")

    def handle_mouse_click(
        self,
        x: float,
        y: float,
        center_x: float,
        center_y: float,
        find_segment_func: Callable,
    ):
        """Handles mouse click."""
        if not self._allow_selection:
            return

        segment = find_segment_func(self._segments, x, y, center_x, center_y)

        if segment:
            self.segment_clicked.emit(segment)
            self._toggle_node_disabled(segment.node)

    def handle_mouse_leave(self):
        """Handles mouse leaving chart area."""
        if self._hovered_segment:
            self._hovered_segment = None
            self.hover_changed.emit(None)
            self.tooltip_changed.emit("", 0, 0)
            self.cursor_changed.emit("default")

    def _toggle_node_disabled(self, node: TreeNode):
        """Toggles node disabled state."""
        if node in self._disabled_nodes:
            self._disabled_nodes.remove(node)
        else:
            self._disabled_nodes.add(node)

        self.selection_changed.emit(self._disabled_nodes)

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

    def _generate_tooltip_text(self, segment: SunburstSegment) -> str:
        """Generates tooltip text."""
        node = segment.node

        unit = "characters"
        translated_name = self._get_translated_node_name(node)

        tooltip_lines = [f"<b>{translated_name}</b>", f"Value: {node.value:,.0f} {unit}"]

        if segment.level == 0:
            tooltip_lines.append(f"Year: {translated_name}")
        elif segment.level == 1:
            tooltip_lines.append(f"Month: {translated_name}")
        elif segment.level == 2:
            tooltip_lines.append(f"Day: {translated_name}")

        if node in self._disabled_nodes:
            tooltip_lines.append("<font color='red'>❌ Disabled for export</font>")
        else:
            tooltip_lines.append("<font color='green'>✅ Enabled for export</font>")

        return "<br/>".join(tooltip_lines)

    def disable_all_nodes(self):
        """Disables all nodes."""
        all_nodes = set()
        for segment in self._segments:
            all_nodes.add(segment.node)

        self._disabled_nodes = all_nodes
        self.selection_changed.emit(self._disabled_nodes)

    def enable_all_nodes(self):
        """Enables all nodes."""
        self._disabled_nodes.clear()
        self.selection_changed.emit(self._disabled_nodes)

    def disable_nodes_by_level(self, level: int):
        """Disables all nodes of specific level."""
        nodes_to_disable = set()
        for segment in self._segments:
            if segment.level == level:
                nodes_to_disable.add(segment.node)

        self._disabled_nodes.update(nodes_to_disable)
        self.selection_changed.emit(self._disabled_nodes)

    def enable_nodes_by_level(self, level: int):
        """Enables all nodes of specific level."""
        nodes_to_enable = set()
        for segment in self._segments:
            if segment.level == level:
                nodes_to_enable.add(segment.node)

        self._disabled_nodes -= nodes_to_enable
        self.selection_changed.emit(self._disabled_nodes)

    def get_statistics(self) -> dict:
        """Returns chart statistics."""
        total_segments = len(self._segments)
        disabled_segments = len(
            [s for s in self._segments if s.node in self._disabled_nodes]
        )
        enabled_segments = total_segments - disabled_segments

        total_value = sum(s.node.value for s in self._segments)
        disabled_value = sum(
            s.node.value for s in self._segments if s.node in self._disabled_nodes
        )
        enabled_value = total_value - disabled_value

        return {
            "total_segments": total_segments,
            "enabled_segments": enabled_segments,
            "disabled_segments": disabled_segments,
            "total_value": total_value,
            "enabled_value": enabled_value,
            "disabled_value": disabled_value,
            "enabled_percentage": (
                (enabled_value / total_value * 100) if total_value > 0 else 0
            ),
        }
