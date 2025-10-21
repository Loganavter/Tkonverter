"""
Centralized application state.

Contains application data and provides centralized access
for state management across the application.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set, Tuple

from src.core.analysis.tree_analyzer import TreeNode
from src.core.analysis.tree_identity import TreeNodeIdentity
from src.core.application.chart_service import ChartService
from src.core.domain.models import AnalysisResult, Chat

@dataclass
class AppState:
    """Application state."""

    loaded_chat: Optional[Chat] = None
    chat_file_path: Optional[str] = None

    analysis_result: Optional[AnalysisResult] = None
    analysis_tree: Optional[TreeNode] = None

    tokenizer: Optional[Any] = None
    tokenizer_model_name: Optional[str] = None

    ui_config: Dict[str, Any] = field(
        default_factory=lambda: {
            "profile": "group",
            "auto_detect_profile": True,
            "auto_recalc": False,
            "show_time": True,
            "show_reactions": True,
            "show_reaction_authors": False,
            "my_name": "Me",
            "partner_name": "Partner",
            "show_optimization": False,
            "streak_break_time": "20:00",
            "show_markdown": True,
            "show_links": True,
            "show_tech_info": True,
            "show_service_notifications": True,
            "truncate_name_length": 20,
            "truncate_quote_length": 50,
        }
    )

    disabled_node_ids: Set[str] = field(default_factory=set)

    disabled_dates: Set[Tuple[str, str, str]] = field(default_factory=set)

    last_analysis_unit: str = "Characters"
    last_analysis_count: int = 0

    is_processing: bool = False
    current_status_message: str = ""

    filtered_count_cache: Optional[int] = None
    _cache_valid: bool = False

    _chart_service: Optional[ChartService] = field(default=None, init=False)

    def __post_init__(self):
        """Initialization after object creation."""
        if "my_name" not in self.ui_config:
            from resources.translations import tr

            self.ui_config["my_name"] = tr("Me")
            self.ui_config["partner_name"] = tr("Partner")

        self.ui_config.setdefault("auto_detect_profile", True)
        self.ui_config.setdefault("auto_recalc", False)

        self.migrate_node_ids_to_dates()

        self._chart_service = ChartService()

    def has_chat_loaded(self) -> bool:
        """Checks if chat is loaded."""
        return self.loaded_chat is not None

    def clear_chat(self):
        """Clears loaded chat and related data."""
        self.loaded_chat = None
        self.chat_file_path = None
        self.analysis_result = None
        self.analysis_tree = None
        self.disabled_node_ids.clear()
        self.last_analysis_count = 0
        self.invalidate_cache()

    def set_chat(self, chat: Chat, file_path: str):
        """
        Sets new chat.

        Args:
            chat: Loaded chat
            file_path: Path to chat file
        """
        self.clear_chat()
        self.loaded_chat = chat
        self.chat_file_path = file_path

    def get_chat_name(self) -> str:
        """Returns current chat name or default value."""
        if self.loaded_chat:
            return self.loaded_chat.name
        from resources.translations import tr

        return tr("chat_history")

    def has_analysis_data(self) -> bool:
        """Checks if there are analysis results."""
        return self.analysis_result is not None and self.analysis_result.total_count > 0

    def set_analysis_result(self, result: AnalysisResult):
        """
        Sets analysis result.

        Args:
            result: Analysis result
        """
        self.analysis_result = result
        self.last_analysis_unit = result.unit
        self.last_analysis_count = result.total_count
        self.invalidate_cache()

    def set_analysis_tree(self, tree: TreeNode):
        """
        Sets analysis tree.

        Args:
            tree: Analysis tree
        """
        self.analysis_tree = tree
        self.invalidate_cache()

    def clear_analysis(self):
        """Clears analysis results."""
        self.analysis_result = None
        self.analysis_tree = None
        self.disabled_node_ids.clear()
        self.last_analysis_count = 0
        self.invalidate_cache()

    def has_tokenizer(self) -> bool:
        """Checks if tokenizer is loaded."""
        return self.tokenizer is not None

    def set_tokenizer(self, tokenizer: Any, model_name: str):
        """
        Sets tokenizer.

        Args:
            tokenizer: Tokenizer
            model_name: Model name
        """
        self.tokenizer = tokenizer
        self.tokenizer_model_name = model_name

        if self.analysis_result and self.analysis_result.unit == "tokens":
            self.clear_analysis()

    def clear_tokenizer(self):
        """Clears tokenizer."""
        self.tokenizer = None
        self.tokenizer_model_name = None

        if self.analysis_result and self.analysis_result.unit == "tokens":
            self.clear_analysis()

    def get_preferred_analysis_unit(self) -> str:
        """Returns preferred analysis unit."""
        return "tokens" if self.has_tokenizer() else "Characters"

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Gets value from configuration.

        Args:
            key: Configuration key
            default: Default value

        Returns:
            Any: Configuration value
        """
        return self.ui_config.get(key, default)

    def set_config_value(self, key: str, value: Any):
        """
        Sets value in configuration.

        Args:
            key: Configuration key
            value: New value
        """
        old_value = self.ui_config.get(key)
        if old_value != value:
            self.ui_config[key] = value

    def update_config(self, new_config: Dict[str, Any]):
        """
        Updates configuration.

        Args:
            new_config: New configuration
        """
        old_config = self.ui_config.copy()
        self.ui_config.update(new_config)

        important_keys = [
            "profile",
            "show_service_notifications",
            "show_markdown",
            "show_links",
            "show_time",
            "show_reactions",
            "show_reaction_authors",
            "show_optimization",
            "streak_break_time",
            "show_tech_info",
            "my_name",
            "partner_name",
        ]

    def set_disabled_nodes(self, nodes: Set[TreeNode]):
        """
        Sets disabled nodes by converting them to dates.

        Args:
            nodes: Set of disabled nodes
        """

        self.disabled_node_ids.clear()
        self.disabled_dates.clear()

        for node in nodes:
            date_tuple = self.extract_date_from_node(node)
            if date_tuple:
                year, month, day = date_tuple
                self.disabled_dates.add((year, month, day))

        self.invalidate_cache()

    def add_disabled_node(self, node: TreeNode):
        """
        Adds node to disabled ones.

        Args:
            node: Node to disable
        """
        if hasattr(node, 'node_id') and node.node_id:
            self.disabled_node_ids.add(node.node_id)
            self.invalidate_cache()

    def remove_disabled_node(self, node: TreeNode):
        """
        Removes node from disabled ones.

        Args:
            node: Node to enable
        """
        if hasattr(node, 'node_id') and node.node_id:
            self.disabled_node_ids.discard(node.node_id)
            self.invalidate_cache()

    def clear_disabled_nodes(self):
        """Clears all disabled nodes."""
        self.disabled_node_ids.clear()
        self.disabled_dates.clear()
        self.invalidate_cache()

    def add_disabled_date(self, year: str, month: str, day: str):
        """
        Добавляет дату в список отключённых.

        Args:
            year: Год (например, "2025")
            month: Месяц (например, "09")
            day: День (например, "15")
        """
        self.disabled_dates.add((year, month, day))
        self.invalidate_cache()

    def remove_disabled_date(self, year: str, month: str, day: str):
        """
        Удаляет дату из списка отключённых.

        Args:
            year: Год (например, "2025")
            month: Месяц (например, "09")
            day: День (например, "15")
        """
        self.disabled_dates.discard((year, month, day))
        self.invalidate_cache()

    def is_date_disabled(self, year: str, month: str, day: str) -> bool:
        """
        Проверяет, отключена ли дата.

        Args:
            year: Год
            month: Месяц
            day: День

        Returns:
            bool: True если дата отключена
        """
        return (year, month, day) in self.disabled_dates

    def extract_date_from_node(self, node: TreeNode) -> Optional[Tuple[str, str, str]]:
        """
        Извлекает дату из TreeNode.

        Args:
            node: Узел древа

        Returns:
            Tuple[str, str, str]: (year, month, day) или None
        """
        if not hasattr(node, 'node_id') or not node.node_id:
            return None

        parsed = TreeNodeIdentity.parse_id(node.node_id)
        if parsed and parsed.get('type') == 'day':
            return (parsed['year'], parsed['month'], parsed['day'])

        return None

    def add_disabled_node_by_date(self, node: TreeNode):
        """
        Добавляет узел в отключённые по его дате.

        Args:
            node: Узел для отключения
        """
        date_tuple = self.extract_date_from_node(node)
        if date_tuple:
            year, month, day = date_tuple
            self.add_disabled_date(year, month, day)

    def remove_disabled_node_by_date(self, node: TreeNode):
        """
        Удаляет узел из отключённых по его дате.

        Args:
            node: Узел для включения
        """
        date_tuple = self.extract_date_from_node(node)
        if date_tuple:
            year, month, day = date_tuple
            self.remove_disabled_date(year, month, day)

    def migrate_node_ids_to_dates(self):
        """
        Миграция старых disabled_node_ids в disabled_dates.
        Вызывается при инициализации для обратной совместимости.
        """
        if self.disabled_node_ids and not self.disabled_dates:

            migrated_count = 0
            for node_id in self.disabled_node_ids:
                parsed = TreeNodeIdentity.parse_id(node_id)
                if parsed and parsed.get('type') == 'day':
                    year, month, day = parsed['year'], parsed['month'], parsed['day']
                    self.disabled_dates.add((year, month, day))
                    migrated_count += 1

            self.disabled_node_ids.clear()

    def has_disabled_nodes(self) -> bool:
        """Checks if there are disabled nodes."""
        return len(self.disabled_dates) > 0 or len(self.disabled_node_ids) > 0

    def invalidate_cache(self):
        """Инвалидирует кэш, требует пересчёта"""
        self._cache_valid = False
        self.filtered_count_cache = None

    def get_filtered_count(self) -> int:
        """
        Возвращает отфильтрованный счётчик с учётом disabled_dates.
        """
        if not self.has_analysis_data():
            return 0

        if not self.has_disabled_nodes():
            total_count = int(self.analysis_result.total_count)
            return total_count

        if self.analysis_tree:
            disabled_nodes = self.get_disabled_nodes_from_tree(self.analysis_tree)
            filtered_value = self._chart_service.calculate_filtered_value(self.analysis_tree, disabled_nodes)
            return int(filtered_value)

        total_count = int(self.analysis_result.total_count)
        return total_count

    def _calculate_filtered_count(self) -> int:
        """Рекурсивный расчёт с учётом disabled_node_ids"""
        if not self.analysis_tree:
            return 0

        result = self._calculate_tree_value_excluding_disabled(self.analysis_tree)
        return result

    def _calculate_tree_value_excluding_disabled(self, node: TreeNode) -> int:
        """Recursively calculates the value of the tree, excluding disabled nodes."""

        if not isinstance(node, TreeNode):
            return 0

        if hasattr(node, 'node_id') and node.node_id in self.disabled_node_ids:
            return 0

        if node.children:
            total = 0
            for child in node.children:
                child_value = self._calculate_tree_value_excluding_disabled(child)
                total += child_value
            return total
        else:
            value = int(node.value)
            return value

    def get_disabled_nodes_summary(self) -> dict:
        """
        Возвращает сводку по отключённым узлам для отладки.

        Returns:
            dict: Сводка с количеством и типами отключённых узлов
        """
        if not self.disabled_node_ids:
            return {"total": 0, "by_type": {}, "ids": []}

        by_type = {}
        for node_id in self.disabled_node_ids:
            parsed = TreeNodeIdentity.parse_id(node_id)
            if parsed:
                node_type = parsed.get("type", "unknown")
                by_type[node_type] = by_type.get(node_type, 0) + 1
            else:
                by_type["invalid"] = by_type.get("invalid", 0) + 1

        return {
            "total": len(self.disabled_node_ids),
            "by_type": by_type,
            "ids": sorted(list(self.disabled_node_ids))
        }

    def get_disabled_nodes_from_tree(self, tree: TreeNode) -> Set[TreeNode]:
        """
        Converts disabled dates to TreeNode objects.

        Args:
            tree: Root node of the analysis tree

        Returns:
            Set[TreeNode]: Set of disabled nodes found in the tree
        """
        if not tree:
            return set()

        disabled_nodes = set()

        day_node_ids = set()
        for year, month, day in self.disabled_dates:
            node_id = TreeNodeIdentity.date_to_day_id(year, month, day)
            day_node_ids.add(node_id)

        all_tree_ids = TreeNodeIdentity.collect_all_node_ids(tree)
        day_tree_ids = [node_id for node_id in all_tree_ids if node_id.startswith('day:')]

        for node_id in day_node_ids:
            node = TreeNodeIdentity.find_node_by_id(tree, node_id)
            if node:
                disabled_nodes.add(node)

        if self.disabled_node_ids:
            legacy_nodes = TreeNodeIdentity.convert_ids_to_nodes(tree, self.disabled_node_ids)
            disabled_nodes.update(legacy_nodes)

        return disabled_nodes

    def update_disabled_node_ids_from_tree(self, tree: TreeNode, disabled_nodes: Set[TreeNode]):
        """
        Updates disabled node IDs from a set of TreeNode objects.

        Args:
            tree: Root node of the analysis tree (for validation)
            disabled_nodes: Set of disabled TreeNode objects
        """

        valid_nodes = set()
        for node in disabled_nodes:
            if TreeNodeIdentity.find_node_by_id(tree, node.node_id):
                valid_nodes.add(node)

        self.disabled_node_ids = TreeNodeIdentity.convert_nodes_to_ids(valid_nodes)
        self.invalidate_cache()

    def set_processing_state(self, is_processing: bool, message: str = ""):
        """
        Sets processing state.

        Args:
            is_processing: Processing state flag
            message: Current operation message
        """
        self.is_processing = is_processing
        self.current_status_message = message

    def is_ready_for_operation(self) -> bool:
        """Checks if application is ready for operations."""
        return not self.is_processing and self.has_chat_loaded()

    def get_state_summary(self) -> Dict[str, Any]:
        """
        Returns current state summary.

        Returns:
            Dict[str, Any]: State summary
        """
        return {
            "has_chat": self.has_chat_loaded(),
            "chat_name": self.get_chat_name() if self.has_chat_loaded() else None,
            "message_count": (
                self.loaded_chat.total_message_count if self.has_chat_loaded() else 0
            ),
            "has_tokenizer": self.has_tokenizer(),
            "tokenizer_model": self.tokenizer_model_name,
            "has_analysis": self.has_analysis_data(),
            "analysis_unit": self.last_analysis_unit,
            "analysis_count": self.last_analysis_count,
            "disabled_nodes_count": len(self.disabled_node_ids),
            "is_processing": self.is_processing,
            "current_profile": self.get_config_value("profile", "group"),
        }

    def validate_state(self) -> list[str]:
        """
        Validates current state and returns list of issues.

        Returns:
            list[str]: List of found issues
        """
        issues = []

        if self.has_analysis_data() and not self.has_chat_loaded():
            issues.append("There are analysis results, but no loaded chat")

        if (
            self.analysis_result
            and self.analysis_result.unit == "tokens"
            and not self.has_tokenizer()
        ):
            issues.append("Analysis in tokens, but tokenizer is not loaded")

        if self.has_chat_loaded() and not self.loaded_chat.messages:
            issues.append("Empty chat loaded")

        profile = self.get_config_value("profile")
        if profile not in ["group", "personal", "posts", "channel"]:
            issues.append(f"Incorrect profile: {profile}")

        return issues
