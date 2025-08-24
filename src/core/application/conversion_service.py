"""
Service for converting chats to text format.

Handles conversion of domain chat objects to readable text
using configured formatters and conversion strategies.
"""

import logging
from typing import Any, Dict, Optional, Set

from core.analysis.tree_analyzer import TreeNode
from core.conversion.context import ConversionContext
from core.conversion.domain_adapters import (
    chat_to_dict,
    create_message_map,
    detect_user_ids_for_personal_chat,
    get_main_post_id,
)
from core.conversion.formatters.service_formatter import format_service_message
from core.conversion.main_converter import generate_plain_text
from core.conversion.message_formatter import format_message
from core.domain.models import Chat, Message, ServiceMessage

logger = logging.getLogger(__name__)

class ConversionService:
    """Service for converting chats to text."""

    def __init__(self, use_modern_formatters: bool = True):
        """
        Initializes conversion service.

        Args:
            use_modern_formatters: Use modern formatters (True)
                                 or old ones via domain_adapters (False)
        """
        self._use_modern_formatters = use_modern_formatters
        self._modern_converter = None

        if use_modern_formatters:
            try:
                from core.conversion.formatters.modern.main_converter import (
                    ModernChatConverter,
                )
                self._modern_converter = ModernChatConverter()

            except ImportError as e:
                logger.warning(f"ConversionService: Modern formatters not available, falling back to legacy: {e}")
                self._use_modern_formatters = False

    def convert_to_text(
        self,
        chat: Chat,
        config: Dict[str, Any],
        html_mode: bool = False,
        disabled_nodes: Optional[Set[TreeNode]] = None,
    ) -> str:
        """
        Converts chat to text format.

        Args:
            chat: Chat to convert
            config: Conversion configuration
            html_mode: HTML generation mode (for preview)
            disabled_nodes: Set of disabled TreeNode objects (for date filtering)

        Returns:
            str: Converted text
        """
        if not chat.messages:
            return ""

        if self._use_modern_formatters and self._modern_converter:

            return self._modern_converter.convert_to_text(
                chat, config, html_mode=html_mode, disabled_nodes=disabled_nodes
            )
        else:
            chat_dict = chat_to_dict(chat)
            return generate_plain_text(
                chat_dict, config, html_mode=html_mode, disabled_nodes=disabled_nodes
            )

    def convert_message_to_text(
        self,
        message: Message,
        previous_message: Optional[Message],
        config: Dict[str, Any],
        chat: Chat,
        html_mode: bool = False,
    ) -> str:
        """
        Converts individual message to text.

        Args:
            message: Message to convert
            previous_message: Previous message (for context)
            config: Conversion configuration
            chat: Chat that the message belongs to
            html_mode: HTML generation mode

        Returns:
            str: Converted message text
        """

        context = self._create_conversion_context(chat, config)

        from core.conversion.domain_adapters import message_to_dict

        msg_dict = message_to_dict(message)
        prev_msg_dict = message_to_dict(previous_message) if previous_message else None

        return format_message(msg_dict, prev_msg_dict, context, html_mode)

    def convert_service_message_to_text(
        self, service_message: ServiceMessage, config: Dict[str, Any], chat: Chat
    ) -> str:
        """
        Converts service message to text.

        Args:
            service_message: Service message
            config: Conversion configuration
            chat: Chat that the message belongs to

        Returns:
            str: Converted text or empty string if not to be shown
        """
        context = self._create_conversion_context(chat, config)

        from core.conversion.domain_adapters import service_message_to_dict

        service_dict = service_message_to_dict(service_message)

        result = format_service_message(service_dict, context)
        return result or ""

    def generate_preview(self, config: Dict[str, Any]) -> tuple[str, str]:
        """
        Generates preview for given configuration.

        Args:
            config: Configuration for preview

        Returns:
            tuple[str, str]: (html_text, preview_title)
        """

        from resources.translations import tr
        return f"<p>{tr('Preview is generated from loaded chat.')}</p>", tr("Preview")

    def _create_conversion_context(
        self, chat: Chat, config: Dict[str, Any]
    ) -> ConversionContext:
        """
        Creates conversion context for chat.

        Args:
            chat: Chat
            config: Configuration

        Returns:
            ConversionContext: Context for formatters
        """

        message_map = create_message_map(chat)

        main_post_id = get_main_post_id(chat)
        my_id, partner_id = detect_user_ids_for_personal_chat(chat)

        context = ConversionContext(config=config)
        context.message_map = message_map

        if main_post_id:
            context.main_post_id = main_post_id

        if my_id:
            context.my_id = my_id
        if partner_id:
            context.partner_id = partner_id

        return context

    def get_supported_profiles(self) -> list[str]:
        """Returns list of supported conversion profiles."""
        return ["group", "personal", "posts", "channel"]

    def validate_config(self, config: Dict[str, Any]) -> list[str]:
        """
        Validates conversion configuration.

        Args:
            config: Configuration to check

        Returns:
            list[str]: List of found issues
        """
        issues = []

        required_fields = ["profile", "show_time", "show_reactions"]
        for field in required_fields:
            if field not in config:
                issues.append(f"Missing required field: {field}")

        profile = config.get("profile")
        if profile not in self.get_supported_profiles():
            issues.append(f"Unsupported profile: {profile}")

        boolean_fields = [
            "show_time",
            "show_reactions",
            "show_reaction_authors",
            "show_optimization",
            "show_markdown",
            "show_links",
            "show_tech_info",
            "show_service_notifications",
        ]
        for field in boolean_fields:
            if field in config and not isinstance(config[field], bool):
                issues.append(f"Field {field} must be boolean")

        string_fields = ["my_name", "partner_name", "streak_break_time"]
        for field in string_fields:
            if field in config and not isinstance(config[field], str):
                issues.append(f"Field {field} must be string")

        streak_time = config.get("streak_break_time", "")
        if streak_time:
            import re

            if not re.match(r"^\d{1,2}:\d{2}$", streak_time):
                issues.append("Field streak_break_time must be in HH:MM format")

        return issues

    def get_default_config(self) -> Dict[str, Any]:
        """Returns default configuration."""
        return {
            "profile": "group",
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
        }

