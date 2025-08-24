import logging
from datetime import datetime

from core.conversion.context import ConversionContext
from resources.translations import tr

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

AGGREGATION_THRESHOLD_PERCENT = 7.5
BASE_MAX_CHILDREN = 35
MIN_VISIBLE_CHILDREN = 5

class TreeNode:

    def __init__(self, name, value=0.0, parent=None, date_level=None):
        self.name = name
        self.value = float(value)
        self.parent = parent
        self.children = []
        self.aggregated_children = []

        self.date_level = date_level

    def add_child(self, node):
        self.children.append(node)
        node.parent = self

def aggregate_children_for_view(
    node: TreeNode, force_full_detail: bool = False
) -> list[TreeNode]:

    if not node.children or node.value == 0:
        return node.children

    if force_full_detail:
        return sorted(node.children, key=lambda n: n.value, reverse=True)

    dynamic_max_children = BASE_MAX_CHILDREN
    if node.parent and node.parent.value > 0:
        share = node.value / node.parent.value
        dynamic_max_children = int(
            MIN_VISIBLE_CHILDREN + (BASE_MAX_CHILDREN - MIN_VISIBLE_CHILDREN) * share
        )

    children_copy = sorted(node.children, key=lambda n: n.value, reverse=True)
    threshold = node.value * (AGGREGATION_THRESHOLD_PERCENT / 100.0)

    large_nodes = []
    small_nodes = []
    small_nodes_value = 0

    for i, child in enumerate(children_copy):
        if child.value >= threshold and i < dynamic_max_children:
            large_nodes.append(child)
        else:
            small_nodes.append(child)
            small_nodes_value += child.value

    if small_nodes:

        others_name = tr("{count} others").format(count=len(small_nodes))
        others_node = TreeNode(others_name, small_nodes_value, parent=node, date_level="others")
        others_node.aggregated_children = small_nodes
        return large_nodes + [others_node]

    return large_nodes

class TokenAnalyzer:
    def __init__(self, date_hierarchy: dict, config: dict, unit: str):
        self.date_hierarchy = date_hierarchy
        self.context = ConversionContext(config=config)
        self.unit = unit

    def build_analysis_tree(self, total_count: int) -> TreeNode:
        import time

        start_time = time.time()
        date_hierarchy = self.date_hierarchy

        years_count = len(date_hierarchy)
        months_count = sum(len(months) for months in date_hierarchy.values())
        days_count = sum(
            len(days) for months in date_hierarchy.values() for days in months.values()
        )

        for year, months in date_hierarchy.items():
            year_value = sum(sum(d.values()) for d in months.values())
            year_tokens = int(year_value)
            year_percent = (year_value / total_count) * 100 if total_count > 0 else 0

            for month, days in months.items():
                month_value = sum(days.values())
                month_tokens = int(month_value)
                month_percent = (
                    (month_value / year_value) * 100 if year_value > 0 else 0
                )

                for day, value in days.items():
                    day_tokens = int(value)
                    day_percent = (value / month_value) * 100 if month_value > 0 else 0

        root = TreeNode("Total", float(total_count), date_level="root")

        for year, months in date_hierarchy.items():
            year_value = sum(sum(d.values()) for d in months.values())
            year_node = TreeNode(str(year), float(year_value), parent=root, date_level="year")
            root.add_child(year_node)

            for month, days in months.items():
                month_value = sum(days.values())

                month_name = f"{int(month):02d}"
                month_node = TreeNode(month_name, float(month_value), parent=year_node, date_level="month")
                year_node.add_child(month_node)

                for day, value in days.items():
                    day_node = TreeNode(str(day), float(value), parent=month_node, date_level="day")
                    month_node.add_child(day_node)

        execution_time = time.time() - start_time
        return root
