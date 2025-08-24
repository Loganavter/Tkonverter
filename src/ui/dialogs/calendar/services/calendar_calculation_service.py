"""
Calendar calculation service.

Responsible for date processing, statistics and navigation.
"""

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from PyQt6.QtCore import QDate

from core.analysis.tree_analyzer import TreeNode

@dataclass
class CalendarDay:
    """Information about a day in calendar."""

    date: QDate
    has_messages: bool
    message_count: int
    is_disabled: bool
    is_in_current_month: bool

@dataclass
class CalendarMonth:
    """Information about a month in calendar."""

    year: int
    month: int
    name: str
    message_count: int
    days: List[CalendarDay]

class CalendarCalculationService:
    """Calendar calculation service."""

    def __init__(self):
        self._date_to_node_map: Dict[str, TreeNode] = {}
        self._available_dates: Set[QDate] = set()
        self._messages_by_date: Dict[str, int] = defaultdict(int)

    def load_data(self, messages: List[dict], root_node: Optional[TreeNode] = None):
        """Loads message data and builds date map."""
        self._date_to_node_map.clear()
        self._available_dates.clear()
        self._messages_by_date.clear()

        for message in messages:
            date_str = message.get("date", "")
            if date_str:
                try:

                    if isinstance(date_str, str):
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    else:
                        dt = date_str

                    qdate = QDate(dt.year, dt.month, dt.day)
                    self._available_dates.add(qdate)

                    date_key = qdate.toString("yyyy-MM-dd")
                    self._messages_by_date[date_key] += 1

                except (ValueError, TypeError):
                    continue

        if root_node:
            self._build_date_to_node_map(root_node)

    def _build_date_to_node_map(self, node: TreeNode, path: str = ""):
        """Recursively builds date to tree node map."""
        current_path = f"{path}/{node.name}" if path else node.name

        if self._is_date_node(node):
            date = self._parse_date_from_path(current_path)
            if date:
                date_key = date.toString("yyyy-MM-dd")
                self._date_to_node_map[date_key] = node

        for child in node.children:
            self._build_date_to_node_map(child, current_path)

    def _is_date_node(self, node: TreeNode) -> bool:
        """Checks if node is a date node."""

        try:
            day = int(node.name)
            return 1 <= day <= 31 and not node.children
        except ValueError:
            return False

    def _parse_date_from_path(self, path: str) -> Optional[QDate]:
        """Parses date from tree node path."""
        parts = path.split("/")

        if len(parts) >= 3:
            try:
                year = int(parts[-3])
                month = int(parts[-2])
                day = int(parts[-1])

                if QDate.isValid(year, month, day):
                    return QDate(year, month, day)
            except (ValueError, IndexError):
                pass

        return None

    def get_month_data(
        self, year: int, month: int, disabled_nodes: Set[TreeNode]
    ) -> CalendarMonth:
        """Returns month data for display."""

        month_names = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        month_name = month_names[month - 1]

        cal = calendar.monthcalendar(year, month)

        days = []
        total_messages = 0

        first_week = cal[0]
        for day_num in first_week:
            if day_num == 0:

                prev_month_date = QDate(year, month, 1).addDays(-1)
                while prev_month_date.day() != len(first_week) - first_week.index(0):
                    prev_month_date = prev_month_date.addDays(-1)

                prev_month_date = prev_month_date.addDays(first_week.index(0))

                day_info = self._create_day_info(
                    prev_month_date, disabled_nodes, is_in_current_month=False
                )
                days.append(day_info)
            else:
                current_date = QDate(year, month, day_num)
                day_info = self._create_day_info(
                    current_date, disabled_nodes, is_in_current_month=True
                )
                days.append(day_info)
                total_messages += day_info.message_count

        for week in cal[1:]:
            for day_num in week:
                if day_num == 0:

                    next_month_date = (
                        QDate(year, month, 1).addMonths(1).addDays(day_num - 1)
                    )
                    day_info = self._create_day_info(
                        next_month_date, disabled_nodes, is_in_current_month=False
                    )
                    days.append(day_info)
                else:
                    current_date = QDate(year, month, day_num)
                    day_info = self._create_day_info(
                        current_date, disabled_nodes, is_in_current_month=True
                    )
                    days.append(day_info)
                    total_messages += day_info.message_count

        return CalendarMonth(
            year=year,
            month=month,
            name=month_name,
            message_count=total_messages,
            days=days,
        )

    def _create_day_info(
        self,
        date: QDate,
        disabled_nodes: Set[TreeNode],
        is_in_current_month: bool = True,
    ) -> CalendarDay:
        """Creates day information."""
        date_key = date.toString("yyyy-MM-dd")

        has_messages = date in self._available_dates
        message_count = self._messages_by_date.get(date_key, 0)

        node = self._date_to_node_map.get(date_key)
        is_disabled = node is not None and node in disabled_nodes

        return CalendarDay(
            date=date,
            has_messages=has_messages,
            message_count=message_count,
            is_disabled=is_disabled,
            is_in_current_month=is_in_current_month,
        )

    def get_available_years(self) -> List[int]:
        """Returns list of available years."""
        if not self._available_dates:
            return []

        years = set(date.year() for date in self._available_dates)
        return sorted(years)

    def get_available_months(self, year: int) -> List[int]:
        """Returns list of available months for year."""
        months = set()
        for date in self._available_dates:
            if date.year() == year:
                months.add(date.month())

        return sorted(months)

    def get_date_range(self) -> Tuple[Optional[QDate], Optional[QDate]]:
        """Returns range of available dates."""
        if not self._available_dates:
            return None, None

        min_date = min(self._available_dates)
        max_date = max(self._available_dates)

        return min_date, max_date

    def get_node_for_date(self, date: QDate) -> Optional[TreeNode]:
        """Returns tree node for date."""
        date_key = date.toString("yyyy-MM-dd")
        return self._date_to_node_map.get(date_key)

    def get_statistics(self, disabled_nodes: Set[TreeNode]) -> Dict[str, int]:
        """Returns calendar statistics."""
        total_days = len(self._available_dates)
        disabled_days = 0
        disabled_messages = 0
        total_messages = sum(self._messages_by_date.values())

        for date in self._available_dates:
            node = self.get_node_for_date(date)
            if node and node in disabled_nodes:
                disabled_days += 1
                date_key = date.toString("yyyy-MM-dd")
                disabled_messages += self._messages_by_date.get(date_key, 0)

        enabled_days = total_days - disabled_days
        enabled_messages = total_messages - disabled_messages

        return {
            "total_days": total_days,
            "enabled_days": enabled_days,
            "disabled_days": disabled_days,
            "total_messages": total_messages,
            "enabled_messages": enabled_messages,
            "disabled_messages": disabled_messages,
            "enabled_percentage": (
                (enabled_messages / total_messages * 100) if total_messages > 0 else 0
            ),
        }
