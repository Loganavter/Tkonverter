"""
Service for filtering dates in calendar.

Responsible for managing disabled nodes and group operations.
"""

from typing import Optional, Set

from PyQt6.QtCore import QDate, QObject, pyqtSignal

from core.analysis.tree_analyzer import TreeNode

from ui.dialogs.calendar.services.calendar_calculation_service import CalendarCalculationService

class DateFilterService(QObject):
    """Service for managing date filtering."""

    filter_changed = pyqtSignal(set)
    statistics_updated = pyqtSignal(dict)

    def __init__(self, calculation_service: CalendarCalculationService):
        super().__init__()
        self._calculation_service = calculation_service
        self._disabled_nodes: Set[TreeNode] = set()
        self._root_node: Optional[TreeNode] = None

    def set_root_node(self, root_node: Optional[TreeNode]):
        """Sets root node of the tree."""
        self._root_node = root_node

    def set_disabled_nodes(self, disabled_nodes: Set[TreeNode]):
        """Sets disabled nodes."""
        old_disabled = self._disabled_nodes.copy()
        self._disabled_nodes = disabled_nodes.copy()

        if old_disabled != self._disabled_nodes:
            self.filter_changed.emit(self._disabled_nodes)
            self._update_statistics()

    def get_disabled_nodes(self) -> Set[TreeNode]:
        """Returns disabled nodes."""
        return self._disabled_nodes.copy()

    def toggle_date(self, date: QDate):
        """Toggles date disable state."""
        node = self._calculation_service.get_node_for_date(date)
        if node:
            if node in self._disabled_nodes:
                self._disabled_nodes.remove(node)
            else:
                self._disabled_nodes.add(node)

            self.filter_changed.emit(self._disabled_nodes)
            self._update_statistics()

    def disable_date(self, date: QDate):
        """Disables date."""
        node = self._calculation_service.get_node_for_date(date)
        if node and node not in self._disabled_nodes:
            self._disabled_nodes.add(node)
            self.filter_changed.emit(self._disabled_nodes)
            self._update_statistics()

    def enable_date(self, date: QDate):
        """Enables date."""
        node = self._calculation_service.get_node_for_date(date)
        if node and node in self._disabled_nodes:
            self._disabled_nodes.remove(node)
            self.filter_changed.emit(self._disabled_nodes)
            self._update_statistics()

    def is_date_disabled(self, date: QDate) -> bool:
        """Checks if date is disabled."""
        node = self._calculation_service.get_node_for_date(date)
        return node is not None and node in self._disabled_nodes

    def disable_all_dates(self):
        """Disables all available dates."""
        if not self._root_node:
            return

        all_date_nodes = set()
        self._collect_date_nodes(self._root_node, all_date_nodes)

        self._disabled_nodes = all_date_nodes
        self.filter_changed.emit(self._disabled_nodes)
        self._update_statistics()

    def enable_all_dates(self):
        """Enables all dates."""
        self._disabled_nodes.clear()
        self.filter_changed.emit(self._disabled_nodes)
        self._update_statistics()

    def disable_month(self, year: int, month: int):
        """Disables all days of the month."""
        if not self._root_node:
            return

        month_nodes = self._find_month_nodes(self._root_node, year, month)
        self._disabled_nodes.update(month_nodes)
        self.filter_changed.emit(self._disabled_nodes)
        self._update_statistics()

    def enable_month(self, year: int, month: int):
        """Enables all days of the month."""
        if not self._root_node:
            return

        month_nodes = self._find_month_nodes(self._root_node, year, month)
        self._disabled_nodes -= month_nodes
        self.filter_changed.emit(self._disabled_nodes)
        self._update_statistics()

    def disable_year(self, year: int):
        """Disables all days of the year."""
        if not self._root_node:
            return

        year_nodes = self._find_year_nodes(self._root_node, year)
        self._disabled_nodes.update(year_nodes)
        self.filter_changed.emit(self._disabled_nodes)
        self._update_statistics()

    def enable_year(self, year: int):
        """Enables all days of the year."""
        if not self._root_node:
            return

        year_nodes = self._find_year_nodes(self._root_node, year)
        self._disabled_nodes -= year_nodes
        self.filter_changed.emit(self._disabled_nodes)
        self._update_statistics()

    def disable_weekends(self):
        """Disables all weekend days."""
        if not self._root_node:
            return

        weekend_nodes = set()
        for date in self._calculation_service._available_dates:

            if date.dayOfWeek() in [6, 7]:
                node = self._calculation_service.get_node_for_date(date)
                if node:
                    weekend_nodes.add(node)

        self._disabled_nodes.update(weekend_nodes)
        self.filter_changed.emit(self._disabled_nodes)
        self._update_statistics()

    def enable_weekends(self):
        """Enables all weekend days."""
        if not self._root_node:
            return

        weekend_nodes = set()
        for date in self._calculation_service._available_dates:
            if date.dayOfWeek() in [6, 7]:
                node = self._calculation_service.get_node_for_date(date)
                if node:
                    weekend_nodes.add(node)

        self._disabled_nodes -= weekend_nodes
        self.filter_changed.emit(self._disabled_nodes)
        self._update_statistics()

    def disable_date_range(self, start_date: QDate, end_date: QDate):
        """Disables date range."""
        current_date = start_date
        while current_date <= end_date:
            node = self._calculation_service.get_node_for_date(current_date)
            if node:
                self._disabled_nodes.add(node)
            current_date = current_date.addDays(1)

        self.filter_changed.emit(self._disabled_nodes)
        self._update_statistics()

    def enable_date_range(self, start_date: QDate, end_date: QDate):
        """Enables date range."""
        current_date = start_date
        while current_date <= end_date:
            node = self._calculation_service.get_node_for_date(current_date)
            if node:
                self._disabled_nodes.discard(node)
            current_date = current_date.addDays(1)

        self.filter_changed.emit(self._disabled_nodes)
        self._update_statistics()

    def _collect_date_nodes(self, node: TreeNode, date_nodes: Set[TreeNode]):
        """Recursively collects all date nodes."""

        if not node.children and self._is_date_node_name(node.name):
            date_nodes.add(node)

        for child in node.children:
            self._collect_date_nodes(child, date_nodes)

    def _find_month_nodes(self, node: TreeNode, year: int, month: int) -> Set[TreeNode]:
        """Finds all day nodes for a given month."""
        month_nodes = set()

        year_node = self._find_child_by_name(node, str(year))
        if year_node:

            month_node = self._find_child_by_name(year_node, f"{month:02d}")
            if month_node:

                self._collect_date_nodes(month_node, month_nodes)

        return month_nodes

    def _find_year_nodes(self, node: TreeNode, year: int) -> Set[TreeNode]:
        """Finds all day nodes for a given year."""
        year_nodes = set()

        year_node = self._find_child_by_name(node, str(year))
        if year_node:

            self._collect_date_nodes(year_node, year_nodes)

        return year_nodes

    def _find_child_by_name(self, node: TreeNode, name: str) -> Optional[TreeNode]:
        """Finds child node by name."""
        for child in node.children:
            if child.name == name:
                return child
        return None

    def _is_date_node_name(self, name: str) -> bool:
        """Checks if node name is a day name."""
        try:
            day = int(name)
            return 1 <= day <= 31
        except ValueError:
            return False

    def _update_statistics(self):
        """Updates statistics."""
        stats = self._calculation_service.get_statistics(self._disabled_nodes)
        self.statistics_updated.emit(stats)
