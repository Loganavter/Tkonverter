"""
Presenter for calendar dialog.

Manages communication between CalendarService and UI components,
processes user interactions and maintains ViewModel state.
"""

import logging
from datetime import datetime
from typing import List, Optional, Set, Dict, Any

from PyQt6.QtCore import QDate, QObject, pyqtSignal

logger = logging.getLogger(__name__)

from core.analysis.tree_analyzer import TreeNode
from core.application.calendar_service import CalendarService, DateHierarchy
from core.conversion.context import ConversionContext
from core.conversion.message_formatter import format_message
from resources.translations import tr
from core.view_models import CalendarDayInfo, CalendarMonthInfo, CalendarViewModel

class CalendarPresenter(QObject):
    """Presenter for calendar dialog."""

    view_model_updated = pyqtSignal(object)
    messages_for_date_updated = pyqtSignal(object)
    filter_changed = pyqtSignal(set)

    def __init__(self, calendar_service: CalendarService):
        super().__init__()
        self._calendar_service = calendar_service
        self._current_hierarchy: Optional[DateHierarchy] = None
        self._current_disabled_nodes: Set[TreeNode] = set()
        self._view_model = CalendarViewModel(current_year=2024, current_month=1, current_day=1)
        self.last_valid_selection: Optional[QDate] = None
        self._view_model.view_mode = "days"
        self._token_hierarchy: Dict[str, Dict[str, Dict[str, float]]] = {}

        self._raw_messages: List[Dict[str, Any]] = []
        self._conversion_context: Optional[ConversionContext] = None

    def load_calendar_data(
        self,
        raw_messages: List[dict],
        analysis_tree: Optional[TreeNode],
        initial_disabled_nodes: Set[TreeNode],
        token_hierarchy: dict | None = None,
        config: dict | None = None,
    ):
        self._raw_messages = raw_messages
        self._current_hierarchy = self._calendar_service.build_date_hierarchy_from_raw_messages(
            raw_messages, analysis_tree
        )
        self._current_disabled_nodes = initial_disabled_nodes.copy()
        self._token_hierarchy = token_hierarchy or {}

        if config:
            message_map = {msg["id"]: msg for msg in raw_messages if "id" in msg}
            self._conversion_context = ConversionContext(config=config, message_map=message_map)

        start_date, end_date = self._current_hierarchy.get_date_range()
        initial_date = end_date or start_date
        if initial_date:
            self._view_model.current_year = initial_date.year()
            self._view_model.current_month = initial_date.month()
            self.last_valid_selection = initial_date
        else:
            today = QDate.currentDate()
            self._view_model.current_year = today.year()
            self._view_model.current_month = today.month()
            self.last_valid_selection = None

        self._update_view_model()
        if self.last_valid_selection:
            self.emit_messages_for_date(self.last_valid_selection)

    def emit_messages_for_date(self, date: QDate):
        """Formats and emits messages for specified date."""

        formatted_messages = self._format_messages_for_date(date)
        self.messages_for_date_updated.emit(formatted_messages)

    def _format_messages_for_date(self, date: QDate) -> str:
        """Internal method for formatting messages for a day."""
        if not self._raw_messages or not self._conversion_context:
            return tr("No messages on this date.")

        messages_for_day = [
            msg for msg in self._raw_messages
            if "date" in msg and datetime.fromisoformat(msg["date"]).date() == date.toPyDate()
        ]

        if not messages_for_day:
            return tr("No messages on this date.")

        output_parts = []
        previous_message = None

        sorted_messages = sorted(messages_for_day, key=lambda m: m.get("date", ""))
        for msg in sorted_messages:
            formatted_text = ""
            if msg.get("type") == "message":
                formatted_text = format_message(
                    msg, previous_message, self._conversion_context, html_mode=True
                )
                previous_message = msg
            if formatted_text:
                output_parts.append(formatted_text)

        return "".join(output_parts).strip()

    def set_view_mode(self, mode: str):
        if self._view_model.view_mode != mode:
            self._view_model.view_mode = mode
            self._update_view_model()

    def navigate_previous(self):
        current_date_base = QDate(self._view_model.current_year, self._view_model.current_month, 1)
        if self._view_model.view_mode == "days":
            new_date = self._calendar_service.find_adjacent_month(current_date_base, -1, self._current_hierarchy)
            if new_date:
                self.navigate_to_date(new_date)
        elif self._view_model.view_mode == "months":
            new_date = self._calendar_service.find_adjacent_year(current_date_base, -1, self._current_hierarchy)
            if new_date:
                self.navigate_to_date(new_date)

    def navigate_next(self):
        current_date_base = QDate(self._view_model.current_year, self._view_model.current_month, 1)
        if self._view_model.view_mode == "days":
            new_date = self._calendar_service.find_adjacent_month(current_date_base, 1, self._current_hierarchy)
            if new_date:
                self.navigate_to_date(new_date)
        elif self._view_model.view_mode == "months":
            new_date = self._calendar_service.find_adjacent_year(current_date_base, 1, self._current_hierarchy)
            if new_date:
                self.navigate_to_date(new_date)

    def navigate_to_date(self, date: QDate):
        self._view_model.current_year = date.year()
        self._view_model.current_month = date.month()
        self._update_view_model()

    def select_date(self, date: QDate):
        if self._current_hierarchy and self._calendar_service.get_message_count_for_date(date, self._current_hierarchy) > 0:
            self.last_valid_selection = date
            self._update_view_model()
            self.emit_messages_for_date(date)

    def select_month(self, year: int, month: int):
        self._view_model.current_year = year
        self._view_model.current_month = month
        self.set_view_mode("days")

    def select_year(self, year: int):
        self._view_model.current_year = year
        self.set_view_mode("months")

    def toggle_filter_for_date(self, date: QDate):
        if not self._current_hierarchy: return
        node = self._current_hierarchy.date_to_node_map.get(date)
        if node:
            self.toggle_filter_for_node(node)

    def toggle_filter_for_month(self, year: int, month: int):
        if not self._current_hierarchy: return
        month_key = (year, month)
        node = self._current_hierarchy.month_to_node_map.get(month_key)
        if node:
            self.toggle_filter_for_node(node)

    def toggle_filter_for_year(self, year: int):
        if not self._current_hierarchy: return
        node = self._current_hierarchy.year_to_node_map.get(year)
        if node:
            self.toggle_filter_for_node(node)

    def toggle_filter_for_node(self, node: TreeNode):
        day_nodes = self._get_descendant_day_nodes(node)
        if not day_nodes:
            return

        all_disabled = all(d in self._current_disabled_nodes for d in day_nodes)

        if all_disabled:
            self._current_disabled_nodes.difference_update(day_nodes)
        else:
            self._current_disabled_nodes.update(day_nodes)

        self._update_view_model()

        self._update_view_model()

    def _get_descendant_day_nodes(self, node: TreeNode) -> list[TreeNode]:
        is_leafy = not node.children and not (hasattr(node, "aggregated_children") and node.aggregated_children)
        if is_leafy:
            if node.name.isdigit():
                return [node]
            return []

        day_nodes = []
        children_to_scan = node.children[:]
        if hasattr(node, "aggregated_children") and node.aggregated_children:
            children_to_scan.extend(node.aggregated_children)

        for child in children_to_scan:
            day_nodes.extend(self._get_descendant_day_nodes(child))

        return day_nodes

    def set_disabled_nodes(self, disabled_nodes: Set[TreeNode]):
        old_disabled_nodes = self._current_disabled_nodes.copy()
        if old_disabled_nodes != disabled_nodes:
            self._current_disabled_nodes = disabled_nodes.copy()
            self._update_view_model()

            self.filter_changed.emit(self._current_disabled_nodes)

    def get_disabled_nodes(self) -> Set[TreeNode]:
        return self._current_disabled_nodes.copy()

    def get_current_view_model(self) -> CalendarViewModel:
        return self._view_model

    def _update_view_model(self):
        if not self._current_hierarchy: return

        if self._view_model.view_mode == "days":
            self._update_day_view_model()
        elif self._view_model.view_mode == "months":
            self._update_month_view_model()
        elif self._view_model.view_mode == "years":
            self._update_year_view_model()

        self._update_navigation_state()
        self._update_statistics()
        self.view_model_updated.emit(self._view_model)

    def _update_day_view_model(self):
        year, month = self._view_model.current_year, self._view_model.current_month
        self._view_model.days_in_current_month = []

        first_day_of_month = QDate(year, month, 1)
        start_date = first_day_of_month.addDays(-(first_day_of_month.dayOfWeek() - 1))

        for i in range(42):
            current_date = start_date.addDays(i)

            is_in_month = current_date.month() == month

            message_count = self._calendar_service.get_message_count_for_date(current_date, self._current_hierarchy)

            is_available = message_count > 0

            is_disabled = self._calendar_service.is_date_disabled_for_export(current_date, self._current_disabled_nodes, self._current_hierarchy)

            year_str, month_str, day_str = str(current_date.year()), f"{current_date.month():02d}", f"{current_date.day():02d}"
            token_count = self._token_hierarchy.get(year_str, {}).get(month_str, {}).get(day_str, 0)

            display_value = f"{int(token_count)}" if token_count > 0 else f"{message_count}"

            day_info = CalendarDayInfo(
                date=current_date,
                message_count=display_value,
                is_available=is_available,
                is_disabled=is_disabled,
                is_selected=(self.last_valid_selection and current_date == self.last_valid_selection),
                is_in_current_month=is_in_month
            )
            self._view_model.days_in_current_month.append(day_info)

        self._view_model.navigation_title = f"{tr(f'month_{month}')} {year}"

    def _update_month_view_model(self):
        year = self._view_model.current_year
        self._view_model.months_in_current_year = []

        for month_num in range(1, 13):
            has_messages = self._calendar_service.has_messages_in_month(year, month_num, self._current_hierarchy)

            year_str, month_str = str(year), f"{month_num:02d}"
            month_token_data = self._token_hierarchy.get(year_str, {}).get(month_str, {})
            month_token_count = sum(month_token_data.values())

            message_count = sum(self._calendar_service.get_message_count_for_date(d, self._current_hierarchy) for d in self._calendar_service.get_dates_in_month(year, month_num, self._current_hierarchy))
            display_value = f"{int(month_token_count)}" if month_token_count > 0 else f"{message_count}"

            is_disabled = False
            month_node = self._current_hierarchy.month_to_node_map.get((year, month_num))
            if month_node:
                day_nodes = self._get_descendant_day_nodes(month_node)
                if day_nodes: is_disabled = all(d in self._current_disabled_nodes for d in day_nodes)

            self._view_model.months_in_current_year.append(CalendarMonthInfo(
                year=year, month=month_num, name=tr(f"month_{month_num}"),
                message_count=display_value, days=[], is_current=False,
                is_available=has_messages, is_disabled=is_disabled,
            ))
        self._view_model.navigation_title = str(year)

    def _update_year_view_model(self):
        self._view_model.available_years = []
        if not self._current_hierarchy or not self._current_hierarchy.sorted_years:
            return

        for year in self._current_hierarchy.sorted_years:
            year_str = str(year)
            year_token_data = self._token_hierarchy.get(year_str, {})
            year_token_count = sum(sum(month.values()) for month in year_token_data.values())

            year_msg_count = sum(self._calendar_service.get_message_count_for_date(d, self._current_hierarchy) for d in self._current_hierarchy.messages_by_date if d.year() == year)
            display_value = f"{int(year_token_count)}" if year_token_count > 0 else f"{year_msg_count}"

            is_disabled = False
            year_node = self._current_hierarchy.year_to_node_map.get(year)
            if year_node:
                day_nodes = self._get_descendant_day_nodes(year_node)
                if day_nodes: is_disabled = all(d in self._current_disabled_nodes for d in day_nodes)

            self._view_model.available_years.append(CalendarMonthInfo(
                year=year, month=0, name=str(year), message_count=display_value,
                days=[], is_current=(year == self._view_model.current_year),
                is_available=True, is_disabled=is_disabled,
            ))

        self._view_model.navigation_title = tr("Years")

    def _update_navigation_state(self):
        if not self._current_hierarchy:
            self._view_model.can_go_previous = self._view_model.can_go_next = False
            return

        current_date = QDate(self._view_model.current_year, self._view_model.current_month, 1)
        if self._view_model.view_mode == "days":
            self._view_model.can_go_previous = self._calendar_service.find_adjacent_month(current_date, -1, self._current_hierarchy) is not None
            self._view_model.can_go_next = self._calendar_service.find_adjacent_month(current_date, 1, self._current_hierarchy) is not None
        elif self._view_model.view_mode == "months":
            self._view_model.can_go_previous = self._calendar_service.find_adjacent_year(current_date, -1, self._current_hierarchy) is not None
            self._view_model.can_go_next = self._calendar_service.find_adjacent_year(current_date, 1, self._current_hierarchy) is not None
        else:
            self._view_model.can_go_previous = self._view_model.can_go_next = False

    def _update_statistics(self):
        if not self._current_hierarchy: return

        total_dates = len(self._current_hierarchy.messages_by_date)
        disabled_dates = self._calendar_service.get_filtered_dates(self._current_disabled_nodes, self._current_hierarchy)

        self._view_model.total_available_dates = total_dates
        self._view_model.total_disabled_dates = len(disabled_dates)
        self._view_model.selected_dates_count = total_dates - len(disabled_dates)
