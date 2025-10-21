from datetime import datetime

from src.core.conversion.context import ConversionContext
from src.core.analysis.tree_identity import TreeNodeIdentity
from src.resources.translations import tr

AGGREGATION_THRESHOLD_PERCENT = 7.5
BASE_MAX_CHILDREN = 35
MIN_VISIBLE_CHILDREN = 5
ROOT_MAX_CHILDREN = 5

class TreeNode:
    """
    Узел древа анализа.

    ВАЖНО: Отключение узлов работает только на уровне leaf-нодов (дней).
    Родительские узлы автоматически пересчитывают значения при отключении дочерних.
    """

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
        """
        Проверяет целостность связей parent/children в древе.

        Returns:
            bool: True если все связи корректны
        """

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
        """
        Получает все leaf-узлы (дни) в поддереве.

        Returns:
            list[TreeNode]: Список всех leaf-узлов
        """
        leaf_nodes = []

        for child in self.children:
            leaf_nodes.extend(child.get_all_leaf_nodes())

        for agg_child in self.aggregated_children:
            leaf_nodes.extend(agg_child.get_all_leaf_nodes())

        if not self.children and not self.aggregated_children:
            leaf_nodes.append(self)

        return leaf_nodes

    def get_descendant_day_nodes(self) -> list:
        """
        Получает все day-узлы в поддереве.

        Returns:
            list[TreeNode]: Список всех узлов с date_level="day"
        """
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

def aggregate_children_for_view(
    node: TreeNode, force_full_detail: bool = False
) -> list[TreeNode]:

    if node.date_level == "others":
        return sorted(node.aggregated_children, key=lambda n: n.value, reverse=True)

    if not node.children or node.value == 0:
        return node.children

    if force_full_detail:
        return sorted(node.children, key=lambda n: n.value, reverse=True)

    if not node.parent:

        dynamic_max_children = ROOT_MAX_CHILDREN
    else:

        share = node.value / node.parent.value if node.parent.value > 0 else 0
        dynamic_max_children = int(
            MIN_VISIBLE_CHILDREN + (BASE_MAX_CHILDREN - MIN_VISIBLE_CHILDREN) * share
        )

    children_sorted = sorted(node.children, key=lambda n: n.value, reverse=True)

    if len(children_sorted) <= dynamic_max_children:
        return children_sorted

    if len(children_sorted) == dynamic_max_children + 1:
        return children_sorted

    num_to_show = dynamic_max_children - 1
    visible_nodes = children_sorted[:num_to_show]
    nodes_to_aggregate = children_sorted[num_to_show:]

    aggregated_value = sum(n.value for n in nodes_to_aggregate)

    if aggregated_value > 0:
        others_name = tr('{count} others').format(count=len(nodes_to_aggregate))
        others_node = TreeNode(others_name, aggregated_value, parent=node, date_level="others",
                             node_id=TreeNodeIdentity.generate_others_id(node.node_id))
        others_node.aggregated_children = nodes_to_aggregate

        return visible_nodes + [others_node]
    else:

        return visible_nodes

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
