"""
Service for handling chart interactions.

- Mouse event handling (clicks, hover)
- Selection state management
- Tooltip and cursor logic
- Filter change coordination
"""

import logging
from typing import Callable, Optional, Set

from core.analysis.tree_analyzer import TreeNode
from core.application.chart_service import ChartService
from core.view_models import ChartInteractionInfo, ChartViewModel, SunburstSegment

logger = logging.getLogger(__name__)

class ChartInteractionService:
    """Service for handling chart interactions."""

    def __init__(self, chart_service: ChartService):
        self._chart_service = chart_service
        self._current_view_model: Optional[ChartViewModel] = None
        self._hover_callbacks = []
        self._click_callbacks = []

    def set_current_view_model(self, view_model: ChartViewModel):
        """Sets current ViewModel for interactions."""
        self._current_view_model = view_model

    def add_hover_callback(self, callback: Callable[[Optional[SunburstSegment]], None]):
        """Adds callback for hover events."""
        self._hover_callbacks.append(callback)

    def add_click_callback(self, callback: Callable[[SunburstSegment], None]):
        """Adds callback for click events."""
        self._click_callbacks.append(callback)

    def handle_mouse_move(self, x: float, y: float) -> Optional[str]:
        """
        Handles mouse movement over chart.

        Args:
            x: Mouse X coordinate
            y: Mouse Y coordinate

        Returns:
            Optional[str]: Tooltip text or None
        """
        if not self._current_view_model:
            return None

        segment = self._chart_service.find_segment_at_position(
            x, y, self._current_view_model
        )

        self._update_hover_state(segment)

        for callback in self._hover_callbacks:
            try:
                callback(segment)
            except Exception as e:
                logger.error(f"Error in hover callback: {e}")

        if segment:
            return self._chart_service.get_segment_tooltip(
                segment, self._current_view_model.unit
            )
        else:
            return None

    def handle_mouse_click(self, x: float, y: float) -> bool:
        """
        Handles mouse click on chart.

        Args:
            x: Click X coordinate
            y: Click Y coordinate

        Returns:
            bool: True if click was processed, False otherwise
        """
        if not self._current_view_model:
            return False

        segment = self._chart_service.find_segment_at_position(
            x, y, self._current_view_model
        )

        if not segment:
            return False

        new_disabled_nodes = self._chart_service.toggle_node_selection(
            segment.node, self._current_view_model.disabled_nodes
        )

        self._current_view_model.disabled_nodes = new_disabled_nodes

        if (
            hasattr(self._current_view_model, "segments")
            and self._current_view_model.segments
        ):

            root_node = self._find_root_node()
            if root_node:
                self._current_view_model.filtered_value = (
                    self._chart_service.calculate_filtered_value(
                        root_node, new_disabled_nodes
                    )
                )

        self._update_segment_states()

        for callback in self._click_callbacks:
            try:
                callback(segment)
            except Exception as e:
                logger.error(f"Error in click callback: {e}")

        return True

    def handle_mouse_leave(self):
        """Handles mouse leaving chart area."""
        if self._current_view_model:
            self._update_hover_state(None)

        for callback in self._hover_callbacks:
            try:
                callback(None)
            except Exception as e:
                logger.error(f"Error in hover callback on exit: {e}")

    def get_cursor_type(self, x: float, y: float) -> str:
        """
        Determines cursor type for position.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            str: Cursor type ("default", "pointer", "hand")
        """
        if not self._current_view_model:
            return "default"

        segment = self._chart_service.find_segment_at_position(
            x, y, self._current_view_model
        )

        return "pointer" if segment else "default"

    def get_interaction_info(self) -> Optional[ChartInteractionInfo]:
        """Returns current interaction information."""
        if not self._current_view_model:
            return None

        return self._current_view_model.interaction

    def select_all_segments(self) -> Set[TreeNode]:
        """
        Selects all segments (disables all nodes).

        Returns:
            Set[TreeNode]: New set of disabled nodes
        """
        if not self._current_view_model:
            return set()

        all_nodes = set()
        for segment in self._current_view_model.segments:
            all_nodes.add(segment.node)

        self._current_view_model.disabled_nodes = all_nodes
        self._update_segment_states()

        root_node = self._find_root_node()
        if root_node:
            self._current_view_model.filtered_value = (
                self._chart_service.calculate_filtered_value(root_node, all_nodes)
            )

        return all_nodes

    def clear_all_selections(self) -> Set[TreeNode]:
        """
        Clears all selections (enables all nodes).

        Returns:
            Set[TreeNode]: New set of disabled nodes (empty)
        """
        if not self._current_view_model:
            return set()

        self._current_view_model.disabled_nodes = set()
        self._update_segment_states()

        root_node = self._find_root_node()
        if root_node:
            self._current_view_model.filtered_value = (
                self._chart_service.calculate_filtered_value(root_node, set())
            )

        return set()

    def update_disabled_nodes(self, disabled_nodes: Set[TreeNode]):
        """
        Updates disabled nodes from external source.

        Args:
            disabled_nodes: New set of disabled nodes
        """
        if not self._current_view_model:
            return

        self._current_view_model.disabled_nodes = disabled_nodes.copy()
        self._update_segment_states()

        root_node = self._find_root_node()
        if root_node:
            self._current_view_model.filtered_value = (
                self._chart_service.calculate_filtered_value(root_node, disabled_nodes)
            )

    def get_disabled_nodes(self) -> Set[TreeNode]:
        """Returns current set of disabled nodes."""
        if not self._current_view_model:
            return set()

        return self._current_view_model.disabled_nodes.copy()

    def get_statistics(self) -> dict:
        """Returns interaction statistics."""
        if not self._current_view_model:
            return {}

        return self._chart_service.get_chart_statistics(self._current_view_model)

    def _update_hover_state(self, hovered_segment: Optional[SunburstSegment]):
        """Updates hover state in ViewModel."""
        if not self._current_view_model:
            return

        if self._current_view_model.interaction.hovered_segment:
            self._current_view_model.interaction.hovered_segment.is_hovered = False

        if hovered_segment:
            hovered_segment.is_hovered = True
            self._current_view_model.interaction.hovered_segment = hovered_segment

            tooltip_text = self._chart_service.get_segment_tooltip(
                hovered_segment, self._current_view_model.unit
            )
            self._current_view_model.interaction.tooltip_text = tooltip_text
            self._current_view_model.interaction.cursor_type = "pointer"
        else:
            self._current_view_model.interaction.hovered_segment = None
            self._current_view_model.interaction.tooltip_text = ""
            self._current_view_model.interaction.cursor_type = "default"

    def _update_segment_states(self):
        """Updates states of all segments based on disabled nodes."""
        if not self._current_view_model:
            return

        disabled_nodes = self._current_view_model.disabled_nodes

        for segment in self._current_view_model.segments:

            is_disabled = self._chart_service.is_effectively_disabled(
                segment.node, disabled_nodes
            )

            segment.is_disabled = is_disabled

            if is_disabled and not segment.color.startswith("#"):

                segment.color = self._chart_service.darken_color(segment.color)
            elif not is_disabled and segment.color.startswith("#"):

                pass

    def _find_root_node(self) -> Optional[TreeNode]:
        """Finds root node from segments."""
        if not self._current_view_model or not self._current_view_model.segments:
            return None

        min_depth = float("inf")
        root_candidate = None

        for segment in self._current_view_model.segments:
            depth = self._chart_service.get_node_absolute_depth(segment.node)
            if depth < min_depth:
                min_depth = depth
                root_candidate = segment.node

        if root_candidate:
            while root_candidate.parent:
                root_candidate = root_candidate.parent

        return root_candidate

    def debug_interaction_state(self) -> dict:
        """Returns debug information about interaction state."""
        if not self._current_view_model:
            return {"error": "No view model"}

        interaction = self._current_view_model.interaction

        return {
            "segments_count": len(self._current_view_model.segments),
            "disabled_nodes_count": len(self._current_view_model.disabled_nodes),
            "hovered_segment": (
                interaction.hovered_segment.node.name
                if interaction.hovered_segment
                else None
            ),
            "selected_segments_count": len(interaction.selected_segments),
            "tooltip_text": interaction.tooltip_text,
            "cursor_type": interaction.cursor_type,
            "callbacks_registered": {
                "hover": len(self._hover_callbacks),
                "click": len(self._click_callbacks),
            },
        }
