"""
Service for working with calendar and date filtering.
"""

from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from PyQt6.QtCore import QDate

from src.core.analysis.tree_analyzer import TreeNode

@dataclass
class DateHierarchy:
    """Date hierarchy for calendar."""
    messages_by_date: Dict[QDate, List[Dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))
    months_with_messages: Set[Tuple[int, int]] = field(default_factory=set)
    years_with_messages: Set[int] = field(default_factory=set)
    sorted_months: List[Tuple[int, int]] = field(default_factory=list)
    sorted_years: List[int] = field(default_factory=list)
    date_to_node_map: Dict[QDate, TreeNode] = field(default_factory=dict)
    month_to_node_map: Dict[Tuple[int, int], TreeNode] = field(default_factory=dict)
    year_to_node_map: Dict[int, TreeNode] = field(default_factory=dict)

    def get_date_range(self) -> Tuple[Optional[QDate], Optional[QDate]]:
        if not self.messages_by_date: return None, None
        dates = list(self.messages_by_date.keys())
        return min(dates), max(dates)

class CalendarService:
    """Service for working with calendar."""
    def __init__(self):
        self._current_hierarchy: Optional[DateHierarchy] = None

    def build_date_hierarchy_from_raw_messages(
        self,
        raw_messages: List[Dict[str, Any]],
        analysis_tree: Optional[TreeNode] = None,
    ) -> DateHierarchy:
        """Builds date hierarchy based on raw messages."""
        hierarchy = DateHierarchy()
        self._process_raw_messages(raw_messages, hierarchy)
        if analysis_tree:
            self._build_node_lookup_maps(analysis_tree, hierarchy)
        self._current_hierarchy = hierarchy
        return hierarchy

    def _process_raw_messages(
        self, raw_messages: List[Dict[str, Any]], hierarchy: DateHierarchy
    ):
        """Processes raw messages and populates date hierarchy."""
        for msg in raw_messages:
            if msg.get("type") in ("message", "service") and "date" in msg:
                try:
                    dt = datetime.fromisoformat(msg["date"])
                    qdate = QDate(dt.year, dt.month, dt.day)
                    hierarchy.messages_by_date[qdate].append(msg)
                    hierarchy.months_with_messages.add((dt.year, dt.month))
                    hierarchy.years_with_messages.add(dt.year)
                except (ValueError, KeyError):
                    continue
        hierarchy.sorted_months = sorted(list(hierarchy.months_with_messages))
        hierarchy.sorted_years = sorted(list(hierarchy.years_with_messages))

    def _build_node_lookup_maps(self, root_node: TreeNode, hierarchy: DateHierarchy):
        """
        Builds maps for fast node lookup by dates.
        Expects numeric month names for proper mapping.
        """
        if not root_node: return

        for year_node in root_node.children:
            if len(year_node.name) == 4 and year_node.name.isdigit():
                year_val = int(year_node.name)
                hierarchy.year_to_node_map[year_val] = year_node
                for month_node in year_node.children:

                    if month_node.name.isdigit():
                        month_val = int(month_node.name)
                        month_key = (year_val, month_val)
                        hierarchy.month_to_node_map[month_key] = month_node
                        for day_node in month_node.children:
                            if day_node.name.isdigit():
                                day_val = int(day_node.name)
                                date_key = QDate(year_val, month_val, day_val)
                                hierarchy.date_to_node_map[date_key] = day_node

    def get_message_count_for_date(self, date: QDate, hierarchy: DateHierarchy) -> int:
        """Returns message count for specified date."""
        return len(hierarchy.messages_by_date.get(date, []))

    def has_messages_in_month(self, year: int, month: int, hierarchy: DateHierarchy) -> bool:
        """Checks if there are messages in specified month."""
        return (year, month) in hierarchy.months_with_messages

    def is_date_disabled_for_export(self, date: QDate, disabled_nodes: Set[TreeNode], hierarchy: DateHierarchy) -> bool:
        """Checks if date is disabled for export."""
        node = hierarchy.date_to_node_map.get(date)
        return node is not None and node in disabled_nodes

    def get_dates_in_month(self, year: int, month: int, hierarchy: DateHierarchy) -> List[QDate]:
        """Returns all dates with messages in specified month."""
        return [d for d in hierarchy.messages_by_date if d.year() == year and d.month() == month]

    def get_filtered_dates(self, disabled_nodes: Set[TreeNode], hierarchy: DateHierarchy) -> Set[QDate]:
        """Returns set of dates that are disabled."""
        return {d for d, node in hierarchy.date_to_node_map.items() if node in disabled_nodes}

    def find_adjacent_month(
        self,
        current_date: QDate,
        direction: int,
        hierarchy: DateHierarchy,
    ) -> Optional[QDate]:
        """Finds adjacent month with messages."""
        if not hierarchy.sorted_months: return None

        current_month_tuple = (current_date.year(), current_date.month())
        try:
            current_index = hierarchy.sorted_months.index(current_month_tuple)
        except ValueError:
            current_index = bisect_left(hierarchy.sorted_months, current_month_tuple)
            if direction < 0: current_index -= 1

        new_index = current_index + direction
        if 0 <= new_index < len(hierarchy.sorted_months):
            year, month = hierarchy.sorted_months[new_index]
            return QDate(year, month, 1)
        return None

    def find_adjacent_year(self, current_date: QDate, direction: int, hierarchy: DateHierarchy) -> Optional[QDate]:
        """Finds adjacent year with messages."""
        if not hierarchy.sorted_years: return None

        current_year = current_date.year()
        try:
            current_index = hierarchy.sorted_years.index(current_year)
        except ValueError:
            current_index = bisect_left(hierarchy.sorted_years, current_year)
            if direction < 0: current_index -= 1

        new_index = current_index + direction
        if 0 <= new_index < len(hierarchy.sorted_years):
            year = hierarchy.sorted_years[new_index]
            return QDate(year, 1, 1)
        return None
