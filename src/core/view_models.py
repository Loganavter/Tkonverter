

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from PyQt6.QtCore import QDate

from src.core.analysis.tree_analyzer import TreeNode

@dataclass
class CalendarDayInfo:
    date: QDate
    message_count: str
    is_available: bool
    is_disabled: bool
    is_selected: bool
    is_in_current_month: bool

@dataclass
class CalendarMonthInfo:
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

    artist: Optional[Any] = None
    text_artist: Optional[Any] = None

@dataclass
class SunburstSegmentViewModel:
    start_angle: float
    end_angle: float
    inner_radius: float
    outer_radius: float
    color: str
    label: str
    label_x: float
    label_y: float
    label_rotation: float
    font_size: int
    node_id: str
    value_text: str
    is_clickable: bool
    is_disabled: bool = False
    date_display: str = ""

@dataclass
class ChartRenderData:
    segments: List[SunburstSegmentViewModel]
    center_text: str
    center_value_text: str
    navigation_depth: int
    can_go_up: bool

@dataclass
class ChartInteractionInfo:

    hovered_segment: Optional[SunburstSegment] = None
    selected_segments: Set[SunburstSegment] = field(default_factory=set)
    tooltip_text: str = ""
    tooltip_position: Optional[tuple[float, float]] = None

    cursor_type: str = "default"

@dataclass
class ChartViewModel:

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
        for segment in self.segments:
            if self._is_point_in_segment(segment, x, y):
                return segment
        return None

    def _is_point_in_segment(self, segment: SunburstSegment, x: float, y: float) -> bool:

        distance = (x ** 2 + y ** 2) ** 0.5
        if not (segment.inner_radius <= distance <= segment.outer_radius):
            return False

        angle = math.atan2(y, x)
        if angle < 0:
            angle += 2 * math.pi

        return segment.start_angle <= angle <= segment.end_angle

    def get_hovered_segment(self) -> Optional[SunburstSegment]:
        return self.interaction_info.hovered_segment

    def set_hovered_segment(self, segment: Optional[SunburstSegment]):
        if self.interaction_info.hovered_segment != segment:
            self.interaction_info.hovered_segment = segment
            if segment:
                self.interaction_info.tooltip_text = f"{segment.text}: {segment.node.value:,.0f}"
            else:
                self.interaction_info.tooltip_text = ""

    def get_tooltip_text(self) -> str:
        return self.interaction_info.tooltip_text

    def get_cursor_type(self) -> str:
        return self.interaction_info.cursor_type

    def set_cursor_type(self, cursor_type: str):
        self.interaction_info.cursor_type = cursor_type

    def get_disabled_nodes(self) -> Set[TreeNode]:
        return {segment.node for segment in self.segments if segment.is_disabled}

    def set_disabled_nodes(self, disabled_nodes: Set[TreeNode]):
        for segment in self.segments:
            segment.is_disabled = segment.node in disabled_nodes

    def get_filtered_value(self) -> float:
        return sum(segment.node.value for segment in self.segments if not segment.is_disabled)

    def update_segment_colors(self, color_scheme: str = "default"):

        pass

    def get_segment_by_node(self, node: TreeNode) -> Optional[SunburstSegment]:
        for segment in self.segments:
            if segment.node == node:
                return segment
        return None

    def add_segment(self, segment: SunburstSegment):
        self.segments.append(segment)

    def clear_segments(self):
        self.segments.clear()

    def get_segments_count(self) -> int:
        return len(self.segments)

    def is_empty(self) -> bool:
        return len(self.segments) == 0

    def get_bounds(self) -> tuple[float, float, float, float]:
        if not self.segments:
            return (0, 0, 0, 0)

        min_x = min(segment.inner_radius for segment in self.segments)
        max_x = max(segment.outer_radius for segment in self.segments)
        min_y = min(segment.inner_radius for segment in self.segments)
        max_y = max(segment.outer_radius for segment in self.segments)

        return (min_x, min_y, max_x, max_y)
