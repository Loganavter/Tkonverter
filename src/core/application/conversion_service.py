

from typing import Any, Callable, Dict, Optional, Set

from src.core.analysis.tree_analyzer import TreeNode
from src.core.application.chat_memory_service import ChatMemoryService
from src.core.conversion.context import ConversionContext
from src.core.conversion.domain_adapters import (
    chat_to_dict,
    create_message_map,
    detect_user_ids_for_personal_chat,
    get_main_post_id,
)
from src.core.conversion.formatters.service_formatter import format_service_message
from src.core.conversion.main_converter import generate_plain_text
from src.core.conversion.main_converter import _build_plain_text_segments
from src.core.conversion.main_converter import _initialize_context
from src.core.conversion.message_formatter import format_message
from src.core.domain.models import Chat, Message, ServiceMessage

class ConversionService:

    def __init__(
        self,
        use_modern_formatters: bool = True,
        modern_converter_factory: Callable[[], Any] | None = None,
        chat_memory_service: Optional[ChatMemoryService] = None,
    ):
        """
        Initializes conversion service.

        Args:
            use_modern_formatters: Use modern formatters (True)
                                 or old ones via domain_adapters (False)
        """
        self._use_modern_formatters = use_modern_formatters
        self._modern_converter = None
        self._chat_memory_service = chat_memory_service

        if use_modern_formatters:
            try:
                if modern_converter_factory is not None:
                    self._modern_converter = modern_converter_factory()
                else:
                    self._use_modern_formatters = False
            except ImportError as e:

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
            if (
                not html_mode
                and self._chat_memory_service is not None
                and chat.chat_id is not None
            ):
                memory = self._chat_memory_service.load_memory(chat.chat_id)
                memory_disabled_dates = {
                    str(d) for d in memory.get("disabled_dates", []) if isinstance(d, str)
                }
                if memory_disabled_dates:
                    filtered_messages = []
                    for msg in chat_dict.get("messages", []):
                        msg_date = str(msg.get("date", ""))[:10]
                        if msg_date and msg_date in memory_disabled_dates:
                            continue
                        filtered_messages.append(msg)
                    chat_dict = dict(chat_dict)
                    chat_dict["messages"] = filtered_messages

                day_overrides = memory.get("day_overrides", {}) or {}
                if isinstance(day_overrides, dict) and day_overrides:
                    segments, _ = _build_plain_text_segments(
                        data=chat_dict,
                        config=config,
                        html_mode=False,
                        disabled_nodes=disabled_nodes,
                    )
                    context = _initialize_context(chat_dict, config)
                    merged_parts = []
                    replaced_dates = set()
                    for date_key, part in segments:
                        if (
                            isinstance(date_key, str)
                            and date_key in day_overrides
                            and isinstance(day_overrides.get(date_key), dict)
                        ):
                            if date_key in replaced_dates:
                                continue
                            override_text = str(
                                day_overrides[date_key].get("edited_text", "")
                            ).strip()
                            if override_text and context.anonymizer:
                                override_text = context.anonymizer.process_text(override_text)
                            if override_text:
                                merged_parts.append(override_text + "\n")
                            replaced_dates.add(date_key)
                            continue
                        merged_parts.append(part)
                    return "".join(merged_parts).strip() + "\n"

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

        from src.core.conversion.domain_adapters import message_to_dict

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

        from src.core.conversion.domain_adapters import service_message_to_dict

        service_dict = service_message_to_dict(service_message)

        result = format_service_message(service_dict, context)
        return result or ""

    def generate_preview(self, config: Dict[str, Any]) -> tuple[str, str]:

        from src.resources.translations import tr
        return f"<p>{tr('preview.generated')}</p>", tr("common.preview")

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
        return ["group", "personal", "posts", "channel"]

    def validate_config(self, config: Dict[str, Any]) -> list[str]:
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
            "anonymizer_enabled",
            "show_activity_analysis",
        ]
        for field in boolean_fields:
            if field in config and not isinstance(config[field], bool):
                issues.append(f"Field {field} must be boolean")

        string_fields = [
            "my_name",
            "partner_name",
            "streak_break_time",
            "anonymizer_preset_id",
        ]
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
            "anonymizer_enabled": False,
            "anonymizer_preset_id": "default",
            "show_activity_analysis": False,
        }

