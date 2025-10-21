"""
Service for chat analysis.

Responsible for counting tokens/characters, building analysis tree
and other chat analytics.
"""

from collections import defaultdict
from typing import Any, Dict, Optional, Set, Tuple

from src.core.analysis.tree_analyzer import TokenAnalyzer, TreeNode
from src.core.analysis.tree_identity import TreeNodeIdentity
from src.core.conversion.context import ConversionContext
from src.core.conversion.domain_adapters import chat_to_dict, service_message_to_dict
from src.core.conversion.formatters.service_formatter import format_service_message
from src.core.conversion.main_converter import generate_plain_text
from src.core.conversion.utils import process_text_to_plain
from src.core.domain.models import AnalysisResult, Chat, Message, ServiceMessage

class AnalysisService:
    """Service for chat analysis."""

    def __init__(self):
        pass

    def calculate_character_stats(
        self,
        chat: Chat,
        config: Dict[str, Any],
        disabled_dates: Set[Tuple[str, str, str]] = None
    ) -> AnalysisResult:
        """
        Calculates character statistics in chat.

        ИСПРАВЛЕНО: Считаем символы по сообщениям с учётом оптимизации,
        но без дополнительных заголовков экспорта.
        """
        if not chat.messages:
            return AnalysisResult(total_count=0, unit="Characters", date_hierarchy={})

        disabled_dates = disabled_dates or set()

        context = ConversionContext(config=config)
        date_hierarchy = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        total_char_count = 0
        message_char_lengths = []

        prev_msg_dict = None
        for msg_idx, msg in enumerate(chat.messages):
            try:

                year = str(msg.date.year)
                month = f"{msg.date.month:02d}"
                day = f"{msg.date.day:02d}"
                date_tuple = (year, month, day)

                if date_tuple in disabled_dates:
                    continue

                msg_dict = self._message_to_dict(msg)

                char_count = self._count_message_chars_simple(msg_dict, prev_msg_dict, context)

                if char_count > 0:
                    date_hierarchy[year][month][day] += char_count
                    message_char_lengths.append(char_count)
                    total_char_count += char_count

                prev_msg_dict = msg_dict

            except Exception as e:

                continue

        avg_message_length = (
            sum(message_char_lengths) / len(message_char_lengths)
            if message_char_lengths
            else 0
        )

        most_active_user = self._find_most_active_user(chat)

        result = AnalysisResult(
            total_count=total_char_count,
            unit="Characters",
            date_hierarchy=dict(date_hierarchy),
            total_characters=total_char_count,
            average_message_length=avg_message_length,
            most_active_user=most_active_user,
        )

        return result

    def _count_message_chars_simple(self, msg_dict: dict, prev_msg_dict: dict, context: ConversionContext) -> int:
        """
        Простой подсчёт символов с базовой оптимизацией.
        Оптимизация = не печатать заголовки от одного автора подряд.
        """
        from src.core.conversion.utils import process_text_to_plain
        from src.resources.translations import tr

        char_count = 0

        print_header = self._should_print_header_simple(msg_dict, prev_msg_dict, context)

        if print_header:

            author = context.get_author_name(msg_dict)
            time_str = ""
            if context.config.get("show_time", True):
                try:
                    from datetime import datetime
                    is_edited = "edited" in msg_dict
                    date_key = "edited" if is_edited else "date"
                    dt = datetime.fromisoformat(msg_dict[date_key])
                    time_part = dt.strftime("%H:%M")
                    edited_part = tr(" (edited)") if is_edited else ""
                    time_str = f" ({time_part}{edited_part})"
                except (ValueError, KeyError):
                    pass
            char_count += len(f"{author}{time_str}:\n")

        if msg_dict.get("type") == "message":
            content = process_text_to_plain(msg_dict.get("text", ""), context)
            if content:
                char_count += len(content)
        else:

            char_count += len(f"[Service message: {msg_dict.get('action', 'unknown')}]")

        return char_count

    def _should_print_header_simple(self, msg_dict: dict, prev_msg_dict: dict, context: ConversionContext) -> bool:
        """
        Простая логика оптимизации: не печатать заголовок если:
        1. Нет предыдущего сообщения
        2. Разные авторы
        3. Оптимизация выключена
        4. Разные даты
        """
        if not prev_msg_dict:
            return True

        try:
            from datetime import datetime
            current_dt = datetime.fromisoformat(msg_dict["date"])
            prev_dt = datetime.fromisoformat(prev_msg_dict["date"])
            if current_dt.date() != prev_dt.date():
                return True
        except (ValueError, KeyError):
            return True

        current_author = context.get_author_name(msg_dict)
        prev_author = context.get_author_name(prev_msg_dict)
        if current_author != prev_author:
            return True

        show_optimization = context.config.get("show_optimization", False)
        if not show_optimization:
            return True

        return False

    def calculate_token_stats(
        self,
        chat: Chat,
        config: Dict[str, Any],
        tokenizer: Any,
        disabled_dates: Set[Tuple[str, str, str]] = None
    ) -> AnalysisResult:
        """
        Calculates token statistics in chat.

        Добавлена фильтрация по disabled_dates.

        Args:
            chat: Chat to analyze
            config: Analysis configuration
            tokenizer: Tokenizer (e.g., from transformers)
            disabled_dates: Set of disabled dates (year, month, day) to exclude

        Returns:
            AnalysisResult: Analysis result with date hierarchy
        """

        if not chat.messages or not tokenizer:
            return AnalysisResult(total_count=0, unit="tokens", date_hierarchy={})

        disabled_dates = disabled_dates or set()

        context = ConversionContext(config=config)
        total_tokens = 0
        total_char_count = 0
        message_char_lengths = []

        prev_msg_dict = None
        skipped_messages = 0
        for msg_idx, msg in enumerate(chat.messages):
            try:

                year = str(msg.date.year)
                month = f"{msg.date.month:02d}"
                day = f"{msg.date.day:02d}"
                date_tuple = (year, month, day)

                if date_tuple in disabled_dates:
                    continue

                msg_dict = self._message_to_dict(msg)

                if prev_msg_dict and not self._should_count_message(msg_dict, prev_msg_dict, context, config.get("profile", "group")):
                    skipped_messages += 1
                    prev_msg_dict = msg_dict
                    continue

                if isinstance(msg, Message) and msg.text:
                    plain_text_msg = process_text_to_plain(msg.text, context)
                    char_len = len(plain_text_msg)
                    if char_len > 0:
                        message_char_lengths.append({"date": msg.date, "length": char_len})
                        total_char_count += char_len

                elif isinstance(msg, ServiceMessage):
                    msg_dict = service_message_to_dict(msg)
                    formatted_message = format_service_message(msg_dict, context)
                    if formatted_message:
                        char_len = len(formatted_message)
                        if char_len > 0:
                            message_char_lengths.append({"date": msg.date, "length": char_len})
                            total_char_count += char_len

                prev_msg_dict = msg_dict

            except Exception as e:

                continue

        if total_char_count == 0:
            return AnalysisResult(total_count=0, unit="tokens", date_hierarchy={})

        try:

            all_text_parts = []
            prev_msg_dict = None
            for msg in chat.messages:
                year = str(msg.date.year)
                month = f"{msg.date.month:02d}"
                day = f"{msg.date.day:02d}"
                date_tuple = (year, month, day)

                if date_tuple in disabled_dates:
                    continue

                msg_dict = self._message_to_dict(msg)

                if prev_msg_dict and not self._should_count_message(msg_dict, prev_msg_dict, context, config.get("profile", "group")):
                    skipped_messages += 1
                    prev_msg_dict = msg_dict
                    continue

                if isinstance(msg, Message) and msg.text:
                    plain_text_msg = process_text_to_plain(msg.text, context)
                    if plain_text_msg:
                        all_text_parts.append(plain_text_msg)
                elif isinstance(msg, ServiceMessage):
                    msg_dict = service_message_to_dict(msg)
                    formatted_message = format_service_message(msg_dict, context)
                    if formatted_message:
                        all_text_parts.append(formatted_message)

                prev_msg_dict = msg_dict

            full_text = "\n".join(all_text_parts)
            total_tokens = len(tokenizer.encode(full_text))

        except Exception as e:

            return AnalysisResult(total_count=0, unit="tokens", date_hierarchy={})

        if total_tokens <= 0:
            return AnalysisResult(total_count=0, unit="tokens", date_hierarchy={})

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

        result = AnalysisResult(
            total_count=total_tokens,
            unit="tokens",
            date_hierarchy=dict(date_hierarchy),
            total_characters=total_char_count,
            most_active_user=most_active_user,
        )

        return result

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
            from src.resources.translations import tr

            return TreeNode(tr("No Data"), 0)

        try:
            analyzer = TokenAnalyzer(
                date_hierarchy=analysis_result.date_hierarchy,
                config=config,
                unit=analysis_result.unit,
            )

            return analyzer.build_analysis_tree(total_count=analysis_result.total_count)

        except Exception as e:

            from src.resources.translations import tr

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

    def update_tree_values(self, tree_root: TreeNode, new_analysis_result: AnalysisResult) -> TreeNode:
        """
        Recursively updates the values of an existing TreeNode structure
        based on a new date hierarchy, preserving ALL existing nodes.
        """
        new_hierarchy = new_analysis_result.date_hierarchy

        def update_node_values(node: TreeNode):

            if node.children:
                new_node_total = 0
                for child in node.children:
                    new_node_total += update_node_values(child)
                node.value = float(new_node_total)
                return node.value

            if node.date_level == "day" and node.parent and node.parent.parent:
                year = node.parent.parent.name
                month = node.parent.name
                day = node.name

                new_value = new_hierarchy.get(year, {}).get(month, {}).get(day, 0.0)
                node.value = float(new_value)
                return node.value

            return float(node.value)

        update_node_values(tree_root)

        tree_root.value = float(new_analysis_result.total_count)

        return tree_root

    def recalculate_with_filters(
        self,
        chat: Chat,
        config: Dict[str, Any],
        tokenizer: Optional[Any],
        disabled_dates: Set[Tuple[str, str, str]]
    ) -> Tuple[AnalysisResult, TreeNode]:
        """
        Полный пересчёт с фильтрацией по датам.

        Args:
            chat: Chat для анализа
            config: Конфигурация
            tokenizer: Токенизатор (опционально)
            disabled_dates: Отключённые даты (year, month, day)

        Returns:
            Tuple[AnalysisResult, TreeNode]: Результат анализа и построенное древо
        """

        try:

            if tokenizer:
                result = self.calculate_token_stats(chat, config, tokenizer, disabled_dates=set())
            else:
                result = self.calculate_character_stats(chat, config, disabled_dates=set())

            tree = self.build_analysis_tree(result, config)

            return result, tree

        except Exception as e:
            from src.resources.translations import tr
            error_result = AnalysisResult(total_count=0, unit="chars", date_hierarchy={})
            error_tree = TreeNode(tr("Error"), 0, node_id=TreeNodeIdentity.generate_root_id())
            return error_result, error_tree

    def _should_count_message(self, msg_dict: dict, prev_msg_dict: dict, context: ConversionContext, profile: str) -> bool:
        """
        Determines if a message should be counted based on optimization settings.
        Uses the same logic as _should_print_header from message_formatter.py
        """
        from datetime import datetime

        try:
            current_dt = datetime.fromisoformat(msg_dict["date"])
            prev_dt = datetime.fromisoformat(prev_msg_dict["date"])
            if current_dt.date() != prev_dt.date():
                return True
        except (ValueError, KeyError):
            return True

        show_optimization = context.config.get("show_optimization", False)

        if not show_optimization:
            return True

        current_author = context.get_author_name(msg_dict)
        prev_author = context.get_author_name(prev_msg_dict)

        if current_author != prev_author:
            return True

        show_service = context.config.get("show_service_notifications", True)
        if show_service and prev_msg_dict.get("type") != "message":
            return True

        if show_optimization:
            if profile == "channel":
                streak_break_str = context.config.get("streak_break_time", "20:00")
                break_seconds = self._parse_time_to_seconds(streak_break_str)

                if break_seconds > 0:
                    time_diff = (current_dt - prev_dt).total_seconds()
                    if time_diff >= break_seconds:
                        return True

                if "reactions" in prev_msg_dict:
                    return True
                if "inline_bot_buttons" in prev_msg_dict or "reply_markup" in prev_msg_dict:
                    return True
                if msg_dict.get("reply_to_message_id") != prev_msg_dict.get("reply_to_message_id"):
                    return True
                if msg_dict.get("forwarded_from") != prev_msg_dict.get("forwarded_from"):
                    return True

                return False
            else:
                if "reactions" in prev_msg_dict:
                    return True
                return False

        if profile != "channel":
            return True

        return True

    def _count_message_chars_like_export(self, msg_dict: dict, prev_msg_dict: dict, context: ConversionContext, msg_idx: int) -> int:
        """
        Считает символы сообщения точно так же, как в экспорте.
        Учитывает оптимизацию - если заголовок не печатается, то считаем только содержимое.
        """
        from src.core.conversion.message_formatter import _should_print_header, _format_header, _format_reply
        from src.core.conversion.formatters.service_formatter import format_service_message
        from src.core.conversion.utils import process_text_to_plain
        from src.resources.translations import tr

        print_header = _should_print_header(msg_dict, prev_msg_dict, context)

        if msg_idx < 5:
            pass

        char_count = 0

        if print_header:
            if prev_msg_dict:
                char_count += 1

            header = _format_header(msg_dict, context)
            char_count += len(header)

            if msg_dict.get("via_bot_id"):
                char_count += len(f"  ({tr('via bot')} {msg_dict['via_bot_id']})\n")

            if msg_dict.get("forwarded_from") and not msg_dict.get("showForwardedAsOriginal"):
                if context.config.get("profile", "group") != "posts":
                    char_count += len(f"  [{tr('forwarded from')} {msg_dict['forwarded_from']}]\n")

            reply = _format_reply(msg_dict, context)
            char_count += len(reply)

        if msg_dict.get("type") == "message":
            content = process_text_to_plain(msg_dict.get("text", ""), context)
            if content:
                char_count += len(content)
        else:

            formatted_message = format_service_message(msg_dict, context)
            if formatted_message:
                char_count += len(formatted_message)

        if not msg_dict.get("text") and not msg_dict.get("reactions"):
            if print_header:
                char_count += len(tr("[Mini-game]"))
            else:
                char_count += len(tr("[Empty message]"))

        return char_count

    def _convert_disabled_dates_to_nodes(self, disabled_dates: Set[Tuple[str, str, str]]) -> Set:
        """Конвертирует disabled_dates в disabled_nodes для экспортёра."""
        disabled_nodes = set()
        for year, month, day in disabled_dates:

            from src.core.analysis.tree_analyzer import TreeNode
            from src.core.analysis.tree_identity import TreeNodeIdentity

            node_id = TreeNodeIdentity.date_to_day_id(year, month, day)
            node = TreeNode(f"{day}-{month}-{year}", 0, node_id=node_id)
            disabled_nodes.add(node)

        return disabled_nodes

    def _parse_time_to_seconds(self, time_str: str) -> int:
        """Parse time string like '20:00' to seconds."""
        try:
            parts = time_str.split(":")
            if len(parts) == 2:
                hours, minutes = map(int, parts)
                return hours * 3600 + minutes * 60
        except ValueError:
            pass
        return 0

    def _message_to_dict(self, msg) -> dict:
        """Конвертирует сообщение в dict для проверки оптимизации."""
        if isinstance(msg, Message):
            return {
                "type": "message",
                "date": msg.date.isoformat(),
                "from_id": getattr(msg, 'from_id', None),
                "text": msg.text,
                "reply_to_message_id": getattr(msg, 'reply_to_message_id', None),
                "forwarded_from": getattr(msg, 'forwarded_from', None),
                "reactions": getattr(msg, 'reactions', None),
                "inline_bot_buttons": getattr(msg, 'inline_bot_buttons', None),
                "reply_markup": getattr(msg, 'reply_markup', None),
            }
        elif isinstance(msg, ServiceMessage):
            return {
                "type": "service",
                "date": msg.date.isoformat(),
                "action": getattr(msg, 'action', None),
            }
        else:
            return {
                "type": "unknown",
                "date": msg.date.isoformat(),
            }
