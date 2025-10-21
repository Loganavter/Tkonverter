"""
Система идентификации узлов древа анализа.

Предоставляет стабильные идентификаторы для узлов древа, которые не зависят
от объектов в памяти и позволяют восстанавливать фильтры после перестройки древа.

ВАЖНО: Отключение узлов работает на уровне leaf-нодов (дней).
При клике ПКМ на месяц "September 2025":
1. Получаем все дочерние дни: ["day:2025-09-01", "day:2025-09-02", ...]
2. Каждый день отключается ИНДИВИДУАЛЬНО
3. При перестройке древа восстанавливаются только существующие ID
4. Родительские узлы (месяц, год) автоматически пересчитывают значения

При отключении узла "day:2025-09-15":
- Узел остаётся в древе, но не учитывается в расчётах
- ID сохраняется в AppState.disabled_node_ids
- При перестройке ID восстанавливается если дата существует в новых данных

Примеры ID:
- root:total - корневой узел
- year:2025 - год 2025
- month:2025-09 - сентябрь 2025
- day:2025-09-15 - 15 сентября 2025
- others:month:2025-09 - узел "прочее" для месяца
"""

from typing import Set, Optional, Tuple

class TreeNodeIdentity:
    """Класс для работы с идентификаторами узлов древа."""

    @staticmethod
    def generate_year_id(year: str) -> str:
        """Генерирует ID для узла года."""
        return f"year:{year}"

    @staticmethod
    def generate_month_id(year: str, month: str) -> str:
        """Генерирует ID для узла месяца."""
        return f"month:{year}-{month}"

    @staticmethod
    def generate_day_id(year: str, month: str, day: str) -> str:
        """Генерирует ID для узла дня."""
        return f"day:{year}-{month}-{day}"

    @staticmethod
    def generate_root_id() -> str:
        """Генерирует ID для корневого узла."""
        return "root:total"

    @staticmethod
    def generate_others_id(parent_id: str) -> str:
        """Генерирует ID для узла 'прочее'."""
        return f"others:{parent_id}"

    @staticmethod
    def parse_id(node_id: str) -> Optional[dict]:
        """
        Парсит ID узла и возвращает информацию о типе и параметрах.

        Args:
            node_id: Идентификатор узла

        Returns:
            dict с полями: type, year, month, day, parent_id (в зависимости от типа)
            None если ID невалидный
        """
        if not node_id or not isinstance(node_id, str):
            return None

        try:
            parts = node_id.split(":", 1)
            if len(parts) != 2:
                return None

            node_type, params = parts

            if node_type == "root":
                return {"type": "root"}

            elif node_type == "year":
                return {"type": "year", "year": params}

            elif node_type == "month":
                year_month = params.split("-")
                if len(year_month) == 2:
                    return {"type": "month", "year": year_month[0], "month": year_month[1]}

            elif node_type == "day":
                year_month_day = params.split("-")
                if len(year_month_day) == 3:
                    return {"type": "day", "year": year_month_day[0],
                           "month": year_month_day[1], "day": year_month_day[2]}

            elif node_type == "others":
                return {"type": "others", "parent_id": params}

        except Exception:
            pass

        return None

    @staticmethod
    def is_valid_id(node_id: str) -> bool:
        """Проверяет валидность ID узла."""
        return TreeNodeIdentity.parse_id(node_id) is not None

    @staticmethod
    def get_node_type(node_id: str) -> Optional[str]:
        """Возвращает тип узла по его ID."""
        parsed = TreeNodeIdentity.parse_id(node_id)
        return parsed.get("type") if parsed else None

    @staticmethod
    def collect_all_node_ids(tree_node) -> Set[str]:
        """
        Собирает все ID узлов из древа рекурсивно.

        Args:
            tree_node: Корневой узел древа (TreeNode)

        Returns:
            Set[str]: Множество всех ID узлов в древе
        """
        node_ids = set()

        if not hasattr(tree_node, 'node_id') or not tree_node.node_id:

            return node_ids

        node_ids.add(tree_node.node_id)

        if hasattr(tree_node, 'children') and tree_node.children:
            for child in tree_node.children:
                node_ids.update(TreeNodeIdentity.collect_all_node_ids(child))

        if hasattr(tree_node, 'aggregated_children') and tree_node.aggregated_children:
            for agg_child in tree_node.aggregated_children:
                node_ids.update(TreeNodeIdentity.collect_all_node_ids(agg_child))

        return node_ids

    @staticmethod
    def find_node_by_id(tree_node, target_id: str):
        """
        Находит узел в древе по его ID.

        Args:
            tree_node: Корневой узел древа
            target_id: ID искомого узла

        Returns:
            TreeNode или None если не найден
        """
        if not hasattr(tree_node, 'node_id'):
            return None

        if tree_node.node_id == target_id:
            return tree_node

        if hasattr(tree_node, 'children') and tree_node.children:
            for child in tree_node.children:
                result = TreeNodeIdentity.find_node_by_id(child, target_id)
                if result:
                    return result

        if hasattr(tree_node, 'aggregated_children') and tree_node.aggregated_children:
            for agg_child in tree_node.aggregated_children:
                result = TreeNodeIdentity.find_node_by_id(agg_child, target_id)
                if result:
                    return result

        return None

    @staticmethod
    def convert_nodes_to_ids(nodes: Set) -> Set[str]:
        """
        Конвертирует множество TreeNode в множество их ID.

        Args:
            nodes: Множество TreeNode

        Returns:
            Set[str]: Множество ID узлов
        """
        node_ids = set()
        for node in nodes:
            if hasattr(node, 'node_id') and node.node_id:
                node_ids.add(node.node_id)
            else:

                pass
        return node_ids

    @staticmethod
    def convert_ids_to_nodes(tree_node, node_ids: Set[str]) -> Set:
        """
        Конвертирует множество ID в множество TreeNode.

        Args:
            tree_node: Корневой узел древа
            node_ids: Множество ID узлов

        Returns:
            Set[TreeNode]: Множество найденных узлов
        """
        nodes = set()
        for node_id in node_ids:
            node = TreeNodeIdentity.find_node_by_id(tree_node, node_id)
            if node:
                nodes.add(node)
        return nodes

    @staticmethod
    def extract_date_from_id(node_id: str) -> Optional[Tuple[str, str, str]]:
        """
        Извлекает дату из node_id.
        "day:2025-09-15" -> ("2025", "09", "15")

        Args:
            node_id: ID узла

        Returns:
            Tuple[str, str, str]: (year, month, day) или None
        """
        parsed = TreeNodeIdentity.parse_id(node_id)
        if parsed and parsed.get('type') == 'day':
            return (parsed['year'], parsed['month'], parsed['day'])
        return None

    @staticmethod
    def date_to_day_id(year: str, month: str, day: str) -> str:
        """
        Конвертирует дату в day node_id.
        ("2025", "09", "15") -> "day:2025-09-15"

        Args:
            year: Год
            month: Месяц
            day: День

        Returns:
            str: node_id для day-узла
        """
        return f"day:{year}-{month}-{day}"
