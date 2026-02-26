

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set, Tuple

from src.core.analysis.tree_analyzer import TreeNode

logger = logging.getLogger(__name__)
from src.core.analysis.tree_identity import TreeNodeIdentity
from src.core.application.chart_service import ChartService
from src.core.domain.models import AnalysisResult, Chat

@dataclass
class AppState:

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
            "partner_name": "",
            "show_optimization": False,
            "streak_break_time": "20:00",
            "show_markdown": True,
            "show_links": True,
            "show_tech_info": True,
            "show_service_notifications": True,
            "truncate_name_length": 20,
            "truncate_quote_length": 50,
            "anonymizer_enabled": False,
            "anonymizer_preset_id": "default",
            "show_activity_analysis": False,
            "analysis_unit": "tokens",
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
    chart_service: Optional[ChartService] = None

    def __post_init__(self):
        if "my_name" not in self.ui_config:
            from src.resources.translations import tr

            self.ui_config["my_name"] = tr("common.me")
            self.ui_config["partner_name"] = ""

        self.ui_config.setdefault("auto_detect_profile", True)
        self.ui_config.setdefault("auto_recalc", False)

        self.migrate_node_ids_to_dates()

        self._chart_service = self.chart_service or ChartService()

    def has_chat_loaded(self) -> bool:
        return self.loaded_chat is not None

    def clear_chat(self):
        self.loaded_chat = None
        self.chat_file_path = None
        self.analysis_result = None
        self.analysis_tree = None

        self.disabled_node_ids.clear()
        self.disabled_dates.clear()

        self.last_analysis_count = 0
        self.invalidate_cache()

    def set_chat(self, chat: Chat, file_path: str):
        self.clear_chat()
        self.loaded_chat = chat
        self.chat_file_path = file_path

    def get_chat_name(self) -> str:
        if self.loaded_chat:
            return self.loaded_chat.name
        from src.resources.translations import tr

        return tr("export.chat_history")

    def has_analysis_data(self) -> bool:
        return self.analysis_result is not None and self.analysis_result.total_count > 0

    def set_analysis_result(self, result: AnalysisResult):
        self.analysis_result = result

        self.last_analysis_count = result.total_count
        self.invalidate_cache()

    def set_analysis_tree(self, tree: TreeNode):
        self.analysis_tree = tree
        self.invalidate_cache()

    def clear_analysis(self):
        self.analysis_result = None
        self.analysis_tree = None
        self.disabled_node_ids.clear()
        self.last_analysis_count = 0
        self.invalidate_cache()

    def has_tokenizer(self) -> bool:
        return self.tokenizer is not None

    def set_tokenizer(self, tokenizer: Any, model_name: str):
        self.tokenizer = tokenizer
        self.tokenizer_model_name = model_name

        if self.analysis_result and self.analysis_result.unit == "tokens":
            self.clear_analysis()

    def clear_tokenizer(self):
        self.tokenizer = None
        self.tokenizer_model_name = None

        if self.analysis_result and self.analysis_result.unit == "tokens":
            self.clear_analysis()

    def get_preferred_analysis_unit(self) -> str:
        val = self.ui_config.get("analysis_unit", "tokens") or "tokens"
        out = "Characters" if (val == "Characters") else "tokens"
        logger.debug(
            "analysis_unit get_preferred: ui_config[analysis_unit]=%r -> %r, has_tokenizer=%s",
            val,
            out,
            self.has_tokenizer(),
        )
        return out

    def get_config_value(self, key: str, default: Any = None) -> Any:
        return self.ui_config.get(key, default)

    def set_config_value(self, key: str, value: Any):
        old_value = self.ui_config.get(key)
        if key == "analysis_unit":
            logger.debug("analysis_unit set_config_value: %r -> %r", old_value, value)
        if old_value != value:
            self.ui_config[key] = value

            if key in [
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
                "show_activity_analysis",
                "anonymizer_enabled",
                "anonymizer_preset_id",
                "anonymization",
                "analysis_unit",
            ]:
                self.clear_analysis()

    def update_config(self, new_config: Dict[str, Any]):
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
            "anonymizer_enabled",
            "anonymizer_preset_id",
            "anonymization",
        ]

    def set_disabled_nodes(self, nodes: Set[TreeNode]):

        self.disabled_node_ids.clear()
        self.disabled_dates.clear()

        for node in nodes:
            date_tuple = self.extract_date_from_node(node)
            if date_tuple:
                year, month, day = date_tuple
                self.disabled_dates.add((year, month, day))

        self.invalidate_cache()

    def add_disabled_node(self, node: TreeNode):
        if hasattr(node, 'node_id') and node.node_id:
            self.disabled_node_ids.add(node.node_id)
            self.invalidate_cache()

    def remove_disabled_node(self, node: TreeNode):
        if hasattr(node, 'node_id') and node.node_id:
            self.disabled_node_ids.discard(node.node_id)
            self.invalidate_cache()

    def clear_disabled_nodes(self):
        self.disabled_node_ids.clear()
        self.disabled_dates.clear()
        self.invalidate_cache()

    def add_disabled_date(self, year: str, month: str, day: str):
        self.disabled_dates.add((year, month, day))
        self.invalidate_cache()

    def remove_disabled_date(self, year: str, month: str, day: str):
        self.disabled_dates.discard((year, month, day))
        self.invalidate_cache()

    def set_disabled_dates_from_memory(self, date_keys) -> None:
        self.disabled_dates.clear()
        for key in date_keys or []:
            if not isinstance(key, str) or len(key) != 10:
                continue
            parts = key.strip().split("-")
            if len(parts) != 3:
                continue
            try:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                if 1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31:
                    self.disabled_dates.add((str(y), f"{m:02d}", f"{d:02d}"))
            except (TypeError, ValueError):
                continue
        self.invalidate_cache()

    def is_date_disabled(self, year: str, month: str, day: str) -> bool:
        return (year, month, day) in self.disabled_dates

    def extract_date_from_node(self, node: TreeNode) -> Optional[Tuple[str, str, str]]:
        if not hasattr(node, 'node_id') or not node.node_id:
            return None

        parsed = TreeNodeIdentity.parse_id(node.node_id)
        if parsed and parsed.get('type') == 'day':
            return (parsed['year'], parsed['month'], parsed['day'])

        return None

    def add_disabled_node_by_date(self, node: TreeNode):
        date_tuple = self.extract_date_from_node(node)
        if date_tuple:
            year, month, day = date_tuple
            self.add_disabled_date(year, month, day)

    def remove_disabled_node_by_date(self, node: TreeNode):
        date_tuple = self.extract_date_from_node(node)
        if date_tuple:
            year, month, day = date_tuple
            self.remove_disabled_date(year, month, day)

    def migrate_node_ids_to_dates(self):
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
        return len(self.disabled_dates) > 0 or len(self.disabled_node_ids) > 0

    def invalidate_cache(self):
        self._cache_valid = False
        self.filtered_count_cache = None

    def get_filtered_count(self) -> int:
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
        if not self.analysis_tree:
            return 0

        result = self._calculate_tree_value_excluding_disabled(self.analysis_tree)
        return result

    def _calculate_tree_value_excluding_disabled(self, node: TreeNode) -> int:

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
        if not tree:
            return set()

        disabled_nodes = set()

        day_node_ids = set()
        for year, month, day in self.disabled_dates:
            try:
                y = str(year)
                m = f"{int(month):02d}" if month is not None else "01"
                d = f"{int(day):02d}" if day is not None else "01"
                node_id = TreeNodeIdentity.date_to_day_id(y, m, d)
                day_node_ids.add(node_id)
            except (TypeError, ValueError):
                continue

        for node_id in day_node_ids:
            node = TreeNodeIdentity.find_node_by_id(tree, node_id)
            if node:
                disabled_nodes.add(node)

        if self.disabled_node_ids:
            legacy_nodes = TreeNodeIdentity.convert_ids_to_nodes(tree, self.disabled_node_ids)
            disabled_nodes.update(legacy_nodes)

        return disabled_nodes

    def update_disabled_node_ids_from_tree(self, tree: TreeNode, disabled_nodes: Set[TreeNode]):

        valid_nodes = set()
        for node in disabled_nodes:
            if TreeNodeIdentity.find_node_by_id(tree, node.node_id):
                valid_nodes.add(node)

        self.disabled_node_ids = TreeNodeIdentity.convert_nodes_to_ids(valid_nodes)
        self.invalidate_cache()

    def set_processing_state(self, is_processing: bool, message: str = ""):
        self.is_processing = is_processing
        self.current_status_message = message

    def is_ready_for_operation(self) -> bool:
        return not self.is_processing and self.has_chat_loaded()

    def get_state_summary(self) -> Dict[str, Any]:
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
