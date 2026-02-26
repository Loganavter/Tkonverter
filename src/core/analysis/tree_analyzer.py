from datetime import datetime
from typing import Optional

from src.core.conversion.context import ConversionContext
from src.core.analysis.tree_identity import TreeNodeIdentity
from src.resources.translations import tr

AGGREGATION_THRESHOLD_PERCENT = 2.0
BASE_MAX_CHILDREN = 35
MIN_VISIBLE_CHILDREN = 5

ROOT_MAX_CHILDREN = 12

MIN_ANGLE_DEG_FROM_ROOT = 2.0

class TreeNode:

    def __init__(self, name, value=0.0, parent=None, date_level=None, node_id=None):
        self.name = name
        self.value = float(value)
        self.parent = parent
        self.children = []
        self.aggregated_children = []

        self.date_level = date_level
        self.node_id = node_id

    def add_child(self, node):
        self.children.append(node)
        node.parent = self

    def validate_tree_integrity(self) -> bool:

        for child in self.children:
            if child.parent != self:
                return False

            if not child.validate_tree_integrity():
                return False

        for agg_child in self.aggregated_children:
            if agg_child.parent != self:
                return False

            if not agg_child.validate_tree_integrity():
                return False

        return True

    def get_all_leaf_nodes(self) -> list:
        leaf_nodes = []

        for child in self.children:
            leaf_nodes.extend(child.get_all_leaf_nodes())

        for agg_child in self.aggregated_children:
            leaf_nodes.extend(agg_child.get_all_leaf_nodes())

        if not self.children and not self.aggregated_children:
            leaf_nodes.append(self)

        return leaf_nodes

    def get_descendant_day_nodes(self) -> list:
        day_nodes = []

        for child in self.children:
            if getattr(child, 'date_level', None) == 'day':
                day_nodes.append(child)
            else:
                day_nodes.extend(child.get_descendant_day_nodes())

        for agg_child in self.aggregated_children:
            if getattr(agg_child, 'date_level', None) == 'day':
                day_nodes.append(agg_child)
            else:
                day_nodes.extend(agg_child.get_descendant_day_nodes())

        return day_nodes

def _get_root_value(node: TreeNode) -> float:
    n = node
    while n.parent is not None:
        n = n.parent
    return float(n.value) if n.value > 0 else 1.0

def aggregate_children_for_view(
    node: TreeNode,
    force_full_detail: bool = False,
    use_global_total: Optional[bool] = None,
) -> list[TreeNode]:
    """
    use_global_total: если True — порог угла и «прочее» от глобального корня (общий вид).
    Если False — от значения текущего узла (вид внутри года/месяца). Если None — как раньше:
    корень от глобального, остальные уровни от node.value.
    """

    if node.date_level == "others":
        return sorted(node.aggregated_children, key=lambda n: n.value, reverse=True)

    if not node.children or node.value == 0:
        return node.children

    if force_full_detail:
        return sorted(node.children, key=lambda n: n.value, reverse=True)

    if use_global_total is True:
        total_for_angle = _get_root_value(node)
    elif use_global_total is False:
        total_for_angle = float(node.value) if node.value > 0 else 1.0
    else:
        if node.parent is None:
            total_for_angle = _get_root_value(node)
        else:
            total_for_angle = float(node.value) if node.value > 0 else 1.0
    children_sorted = sorted(node.children, key=lambda n: n.value, reverse=True)

    angle_from_root = lambda c: (c.value / total_for_angle) * 360.0
    above_threshold = [c for c in children_sorted if angle_from_root(c) >= MIN_ANGLE_DEG_FROM_ROOT]
    below_threshold = [c for c in children_sorted if angle_from_root(c) < MIN_ANGLE_DEG_FROM_ROOT]

    if not node.parent:
        dynamic_max_children = ROOT_MAX_CHILDREN
    else:
        share = node.value / node.parent.value if node.parent.value > 0 else 0
        dynamic_max_children = int(
            MIN_VISIBLE_CHILDREN + (BASE_MAX_CHILDREN - MIN_VISIBLE_CHILDREN) * share
        )

    visible_nodes = list(above_threshold)
    nodes_to_aggregate = list(below_threshold)

    if not nodes_to_aggregate:
        return visible_nodes

    aggregated_value = sum(n.value for n in nodes_to_aggregate)
    if aggregated_value <= 0:
        return visible_nodes

    if not visible_nodes:
        return []

    others_name = tr('{count} others').format(count=len(nodes_to_aggregate))
    others_node = TreeNode(
        others_name,
        aggregated_value,
        parent=node,
        date_level="others",
        node_id=TreeNodeIdentity.generate_others_id(node.node_id),
    )
    others_node.aggregated_children = nodes_to_aggregate
    return visible_nodes + [others_node]

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

        root = TreeNode("Total", float(total_count), date_level="root",
                       node_id=TreeNodeIdentity.generate_root_id())

        for year, months in date_hierarchy.items():
            year_value = sum(sum(d.values()) for d in months.values())
            year_node = TreeNode(str(year), float(year_value), parent=root, date_level="year",
                               node_id=TreeNodeIdentity.generate_year_id(year))
            root.add_child(year_node)

            for month, days in months.items():
                month_value = sum(days.values())

                month_name = f"{int(month):02d}"
                month_node = TreeNode(month_name, float(month_value), parent=year_node, date_level="month",
                                    node_id=TreeNodeIdentity.generate_month_id(year, month_name))
                year_node.add_child(month_node)

                for day, value in days.items():
                    day_node = TreeNode(str(day), float(value), parent=month_node, date_level="day",
                                      node_id=TreeNodeIdentity.generate_day_id(year, month_name, str(day)))
                    month_node.add_child(day_node)

        execution_time = time.time() - start_time
        return root
