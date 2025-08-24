"""
ViewModels for charts and calendar.

These classes contain only data for display in UI,
without any business logic.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from PyQt6.QtCore import QDate

from core.analysis.tree_analyzer import TreeNode

@dataclass
class CalendarDayInfo:
    """Information about a day in calendar."""
    date: QDate
    message_count: str
    is_available: bool
    is_disabled: bool
    is_selected: bool
    is_in_current_month: bool

@dataclass
class CalendarMonthInfo:
    """Information about a month or year in calendar."""
    year: int
    month: int
    name: str
    message_count: str
    days: List[CalendarDayInfo]
    is_current: bool

    is_available: bool
    is_disabled: bool

@dataclass
class CalendarViewModel:
    """ViewModel for calendar dialog."""
    current_year: int
    current_month: int
    current_day: int

    view_mode: str = "days"

    days_in_current_month: List[CalendarDayInfo] = field(default_factory=list)
    months_in_current_year: List[CalendarMonthInfo] = field(default_factory=list)

    available_years: List[CalendarMonthInfo] = field(default_factory=list)

    can_go_previous: bool = True
    can_go_next: bool = True
    navigation_title: str = ""

    total_available_dates: int = 0
    total_disabled_dates: int = 0
    selected_dates_count: int = 0

    disabled_dates: Set[QDate] = field(default_factory=set)

    def get_current_date(self) -> QDate:
        return QDate(self.current_year, self.current_month, self.current_day)

    def is_date_disabled(self, date: QDate) -> bool:
        return date in self.disabled_dates

@dataclass
class SunburstSegment:
    """Segment of circular chart (sunburst)."""

    inner_radius: float
    outer_radius: float
    start_angle: float
    end_angle: float
    color: str
    node: TreeNode
    text: str
    text_position: Optional[tuple[float, float]] = None
    is_hovered: bool = False
    is_selected: bool = False
    is_disabled: bool = False

@dataclass
class ChartInteractionInfo:
    """Information about chart interaction."""

    hovered_segment: Optional[SunburstSegment] = None
    selected_segments: Set[SunburstSegment] = field(default_factory=set)
    tooltip_text: str = ""
    tooltip_position: Optional[tuple[float, float]] = None

    cursor_type: str = "default"

@dataclass
class ChartViewModel:
    """ViewModel for analysis chart."""

    segments: List[SunburstSegment] = field(default_factory=list)
    center_text: str = ""
    center_value: float = 0.0
    unit: str = "chars"
    chart_width: int = 400
    chart_height: int = 400
    center_x: float = 200.0
    center_y: float = 200.0
    color_scheme: str = "default"
    disabled_nodes: Set[TreeNode] = field(default_factory=set)
    filtered_value: float = 0.0
    total_value: float = 0.0
    geometry: Optional[Any] = None
    interaction_info: ChartInteractionInfo = field(default_factory=ChartInteractionInfo)

    def get_segment_at_position(self, x: float, y: float) -> Optional[SunburstSegment]:
        """Returns the segment at the specified position."""
        for segment in self.segments:
            if self._is_point_in_segment(segment, x, y):
                return segment
        return None

    def _is_point_in_segment(self, segment: SunburstSegment, x: float, y: float) -> bool:
        """Checks if a point is within a segment."""

        distance = (x ** 2 + y ** 2) ** 0.5
        if not (segment.inner_radius <= distance <= segment.outer_radius):
            return False

        angle = math.atan2(y, x)
        if angle < 0:
            angle += 2 * math.pi

        return segment.start_angle <= angle <= segment.end_angle

    def get_hovered_segment(self) -> Optional[SunburstSegment]:
        """Returns the current hovered segment."""
        return self.interaction_info.hovered_segment

    def set_hovered_segment(self, segment: Optional[SunburstSegment]):
        """Sets the hovered segment."""
        if self.interaction_info.hovered_segment != segment:
            self.interaction_info.hovered_segment = segment
            if segment:
                self.interaction_info.tooltip_text = f"{segment.text}: {segment.node.value:,.0f}"
            else:
                self.interaction_info.tooltip_text = ""

    def get_tooltip_text(self) -> str:
        """Returns text for tooltip."""
        return self.interaction_info.tooltip_text

    def get_cursor_type(self) -> str:
        """Returns cursor type."""
        return self.interaction_info.cursor_type

    def set_cursor_type(self, cursor_type: str):
        """Sets cursor type."""
        self.interaction_info.cursor_type = cursor_type

    def get_disabled_nodes(self) -> Set[TreeNode]:
        """Returns disabled nodes."""
        return {segment.node for segment in self.segments if segment.is_disabled}

    def set_disabled_nodes(self, disabled_nodes: Set[TreeNode]):
        """Sets disabled nodes."""
        for segment in self.segments:
            segment.is_disabled = segment.node in disabled_nodes

    def get_filtered_value(self) -> float:
        """Returns filtered value."""
        return sum(segment.node.value for segment in self.segments if not segment.is_disabled)

    def update_segment_colors(self, color_scheme: str = "default"):
        """Updates segment colors."""

        pass

    def get_segment_by_node(self, node: TreeNode) -> Optional[SunburstSegment]:
        """Returns segment by node."""
        for segment in self.segments:
            if segment.node == node:
                return segment
        return None

    def add_segment(self, segment: SunburstSegment):
        """Adds a segment."""
        self.segments.append(segment)

    def clear_segments(self):
        """Clears all segments."""
        self.segments.clear()

    def get_segments_count(self) -> int:
        """Returns the number of segments."""
        return len(self.segments)

    def is_empty(self) -> bool:
        """Checks if the chart is empty."""
        return len(self.segments) == 0

    def get_bounds(self) -> tuple[float, float, float, float]:
        """Returns the bounds of the chart."""
        if not self.segments:
            return (0, 0, 0, 0)

        min_x = min(segment.inner_radius for segment in self.segments)
        max_x = max(segment.outer_radius for segment in self.segments)
        min_y = min(segment.inner_radius for segment in self.segments)
        max_y = max(segment.outer_radius for segment in self.segments)

        return (min_x, min_y, max_x, max_y)
