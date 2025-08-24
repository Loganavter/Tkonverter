"""
Service for chat analysis.

Responsible for counting tokens/characters, building analysis tree
and other chat analytics.
"""

import logging
from collections import defaultdict
from typing import Any, Dict, Optional

from core.analysis.tree_analyzer import TokenAnalyzer, TreeNode
from core.conversion.context import ConversionContext
from core.conversion.domain_adapters import chat_to_dict
from core.conversion.utils import process_text_to_plain
from core.domain.models import AnalysisResult, Chat, Message

logger = logging.getLogger(__name__)

class AnalysisService:
    """Service for chat analysis."""

    def __init__(self):
        pass

    def calculate_character_stats(
        self, chat: Chat, config: Dict[str, Any]
    ) -> AnalysisResult:
        """
        Calculates character statistics in chat.

        Args:
            chat: Chat to analyze
            config: Analysis configuration

        Returns:
            AnalysisResult: Analysis result with date hierarchy
        """
        if not chat.messages:
            return AnalysisResult(total_count=0, unit="Characters", date_hierarchy={})

        context = ConversionContext(config=config)
        date_hierarchy = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        total_char_count = 0
        message_char_lengths = []

        for msg in chat.messages:
            if not isinstance(msg, Message):
                continue

            try:

                plain_text_msg = process_text_to_plain(msg.text, context)
                char_len = len(plain_text_msg)

                if char_len > 0:
                    year = str(msg.date.year)
                    month = f"{msg.date.month:02d}"
                    day = f"{msg.date.day:02d}"

                    date_hierarchy[year][month][day] += char_len
                    total_char_count += char_len
                    message_char_lengths.append(char_len)

            except (ValueError, AttributeError) as e:
                logger.warning(f"Error processing message {msg.id}: {e}")
                continue

        avg_message_length = (
            sum(message_char_lengths) / len(message_char_lengths)
            if message_char_lengths
            else 0
        )

        most_active_user = self._find_most_active_user(chat)

        return AnalysisResult(
            total_count=total_char_count,
            unit="Characters",
            date_hierarchy=dict(date_hierarchy),
            total_characters=total_char_count,
            average_message_length=avg_message_length,
            most_active_user=most_active_user,
        )

    def calculate_token_stats(
        self, chat: Chat, config: Dict[str, Any], tokenizer: Any
    ) -> AnalysisResult:
        """
        Calculates token statistics in chat.

        Args:
            chat: Chat to analyze
            config: Analysis configuration
            tokenizer: Tokenizer (e.g., from transformers)

        Returns:
            AnalysisResult: Analysis result with date hierarchy
        """
        if not chat.messages or not tokenizer:
            return AnalysisResult(total_count=0, unit="tokens", date_hierarchy={})

        chat_dict = chat_to_dict(chat)
        from core.conversion.main_converter import generate_plain_text

        plain_text = generate_plain_text(chat_dict, config, html_mode=False)

        try:
            total_tokens = len(tokenizer.encode(plain_text))
        except Exception as e:
            logger.error(f"Error tokenizing: {e}")
            return AnalysisResult(total_count=0, unit="tokens", date_hierarchy={})

        if total_tokens <= 0:
            return AnalysisResult(total_count=0, unit="tokens", date_hierarchy={})

        context = ConversionContext(config=config)
        message_char_lengths = []
        total_char_count = 0

        for msg in chat.messages:
            if not isinstance(msg, Message):
                continue

            try:
                plain_text_msg = process_text_to_plain(msg.text, context)
                char_len = len(plain_text_msg)
                if char_len > 0:
                    message_char_lengths.append({"date": msg.date, "length": char_len})
                    total_char_count += char_len
            except Exception as e:
                logger.warning(f"Error processing message {msg.id}: {e}")
                continue

        if total_char_count == 0:
            return AnalysisResult(
                total_count=total_tokens, unit="tokens", date_hierarchy={}
            )

        tokens_per_char = total_tokens / total_char_count
        date_hierarchy = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

        for item in message_char_lengths:
            dt = item["date"]
            year = str(dt.year)
            month = f"{dt.month:02d}"
            day = f"{dt.day:02d}"
            estimated_tokens = item["length"] * tokens_per_char
            date_hierarchy[year][month][day] += estimated_tokens

        most_active_user = self._find_most_active_user(chat)

        return AnalysisResult(
            total_count=total_tokens,
            unit="tokens",
            date_hierarchy=dict(date_hierarchy),
            total_characters=total_char_count,
            most_active_user=most_active_user,
        )

    def build_analysis_tree(
        self, analysis_result: AnalysisResult, config: Dict[str, Any]
    ) -> TreeNode:
        """
        Builds analysis tree based on analysis result.

        Args:
            analysis_result: Analysis result with date hierarchy
            config: Configuration for tree building

        Returns:
            TreeNode: Root node of the analysis tree
        """
        if not analysis_result.date_hierarchy or analysis_result.total_count <= 0:
            from resources.translations import tr

            return TreeNode(tr("No Data"), 0)

        try:
            analyzer = TokenAnalyzer(
                date_hierarchy=analysis_result.date_hierarchy,
                config=config,
                unit=analysis_result.unit,
            )

            return analyzer.build_analysis_tree(total_count=analysis_result.total_count)

        except Exception as e:
            logger.error(f"Error building analysis tree: {e}")
            from resources.translations import tr

            return TreeNode(tr("Error"), 0)

    def _find_most_active_user(self, chat: Chat) -> Optional[Any]:
        """
        Finds the most active user in the chat.

        Args:
            chat: Chat to analyze

        Returns:
            Optional[User]: The most active user or None
        """
        if not chat.messages:
            return None

        user_message_counts = {}

        for msg in chat.messages:
            if isinstance(msg, Message):
                user_id = msg.author.id
                if user_id in user_message_counts:
                    user_message_counts[user_id]["count"] += 1
                else:
                    user_message_counts[user_id] = {"count": 1, "user": msg.author}

        if not user_message_counts:
            return None

        most_active_data = max(user_message_counts.values(), key=lambda x: x["count"])
        return most_active_data["user"]

    def get_chat_summary(self, chat: Chat) -> Dict[str, Any]:
        """
        Returns a brief chat summary.

        Args:
            chat: Chat to analyze

        Returns:
            Dict[str, Any]: Summary with main metrics
        """
        if not chat.messages:
            return {
                "total_messages": 0,
                "regular_messages": 0,
                "service_messages": 0,
                "unique_users": 0,
                "date_range": None,
                "most_active_user": None,
            }

        regular_messages = [msg for msg in chat.messages if isinstance(msg, Message)]
        service_messages = [
            msg for msg in chat.messages if not isinstance(msg, Message)
        ]

        users = chat.get_users()
        most_active_user = self._find_most_active_user(chat)

        try:
            start_date, end_date = chat.get_date_range()
            date_range = {
                "start": start_date,
                "end": end_date,
                "duration_days": (end_date - start_date).days,
            }
        except ValueError:
            date_range = None

        return {
            "total_messages": len(chat.messages),
            "regular_messages": len(regular_messages),
            "service_messages": len(service_messages),
            "unique_users": len(users),
            "date_range": date_range,
            "most_active_user": most_active_user.name if most_active_user else None,
        }

    def calculate_user_activity(self, chat: Chat) -> Dict[str, Dict[str, Any]]:
        """
        Calculates user activity statistics.

        Args:
            chat: Chat to analyze

        Returns:
            Dict[str, Dict[str, Any]]: Statistics by users
        """
        user_stats = {}

        for msg in chat.messages:
            if not isinstance(msg, Message):
                continue

            user_id = msg.author.id
            user_name = msg.author.name

            if user_id not in user_stats:
                user_stats[user_id] = {
                    "name": user_name,
                    "message_count": 0,
                    "character_count": 0,
                    "reaction_count": 0,
                    "first_message": None,
                    "last_message": None,
                }

            stats = user_stats[user_id]
            stats["message_count"] += 1

            if isinstance(msg.text, str):
                stats["character_count"] += len(msg.text)

            stats["reaction_count"] += len(msg.reactions)

            if stats["first_message"] is None or msg.date < stats["first_message"]:
                stats["first_message"] = msg.date
            if stats["last_message"] is None or msg.date > stats["last_message"]:
                stats["last_message"] = msg.date

        return user_stats

    def get_daily_activity(self, chat: Chat) -> Dict[str, int]:
        """
        Returns activity by day.

        Args:
            chat: Chat to analyze

        Returns:
            Dict[str, int]: Dictionary day -> number of messages
        """
        daily_counts = defaultdict(int)

        for msg in chat.messages:
            if isinstance(msg, Message):
                date_str = msg.date.strftime("%Y-%m-%d")
                daily_counts[date_str] += 1

        return dict(daily_counts)

    def get_hourly_activity(self, chat: Chat) -> Dict[int, int]:
        """
        Returns activity by hours of the day.

        Args:
            chat: Chat to analyze

        Returns:
            Dict[int, int]: Dictionary hour (0-23) -> number of messages
        """
        hourly_counts = defaultdict(int)

        for msg in chat.messages:
            if isinstance(msg, Message):
                hour = msg.date.hour
                hourly_counts[hour] += 1

        return dict(hourly_counts)
