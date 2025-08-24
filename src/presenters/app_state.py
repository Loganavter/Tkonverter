"""
Centralized application state.

Contains application data and provides centralized access
for state management across the application.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

from core.analysis.tree_analyzer import TreeNode
from core.domain.models import AnalysisResult, Chat

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

    disabled_time_nodes: Set[TreeNode] = field(default_factory=set)

    last_analysis_unit: str = "Characters"
    last_analysis_count: int = 0

    is_processing: bool = False
    current_status_message: str = ""

    def __post_init__(self):
        """Initialization after object creation."""
        if "my_name" not in self.ui_config:
            from resources.translations import tr

            self.ui_config["my_name"] = tr("Me")
            self.ui_config["partner_name"] = tr("Partner")

        self.ui_config.setdefault("auto_detect_profile", True)
        self.ui_config.setdefault("auto_recalc", False)

    def has_chat_loaded(self) -> bool:
        """Checks if chat is loaded."""
        return self.loaded_chat is not None

    def clear_chat(self):
        """Clears loaded chat and related data."""
        self.loaded_chat = None
        self.chat_file_path = None
        self.analysis_result = None
        self.analysis_tree = None
        self.disabled_time_nodes.clear()
        self.last_analysis_count = 0

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

        self.analysis_tree = None

    def set_analysis_tree(self, tree: TreeNode):
        """
        Sets analysis tree.

        Args:
            tree: Analysis tree
        """
        self.analysis_tree = tree

    def clear_analysis(self):
        """Clears analysis results."""
        self.analysis_result = None
        self.analysis_tree = None
        self.disabled_time_nodes.clear()
        self.last_analysis_count = 0

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
        import logging
        logger = logging.getLogger("AppState")

        old_value = self.ui_config.get(key)
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
            ]:
                self.clear_analysis()

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
        if any(old_config.get(key) != new_config.get(key) for key in important_keys):
            self.clear_analysis()

    def set_disabled_nodes(self, nodes: Set[TreeNode]):
        """
        Sets disabled nodes.

        Args:
            nodes: Set of disabled nodes
        """
        self.disabled_time_nodes = nodes.copy()

    def add_disabled_node(self, node: TreeNode):
        """
        Adds node to disabled ones.

        Args:
            node: Node to disable
        """
        self.disabled_time_nodes.add(node)

    def remove_disabled_node(self, node: TreeNode):
        """
        Removes node from disabled ones.

        Args:
            node: Node to enable
        """
        self.disabled_time_nodes.discard(node)

    def clear_disabled_nodes(self):
        """Clears all disabled nodes."""
        self.disabled_time_nodes.clear()

    def has_disabled_nodes(self) -> bool:
        """Checks if there are disabled nodes."""
        return len(self.disabled_time_nodes) > 0

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
            "disabled_nodes_count": len(self.disabled_time_nodes),
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
