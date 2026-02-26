

import logging
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, Optional, Set

from src.core.analysis.tree_analyzer import TokenAnalyzer, TreeNode
from src.core.application.export_metrics_service import ExportMetricsService
from src.core.conversion.context import ConversionContext
from src.core.conversion.main_converter import _LegacyAnonymizerAdapter
from src.core.conversion.utils import process_text_to_plain
from src.core.domain.anonymization import AnonymizationConfig, LinkMaskMode
from src.core.domain.models import AnalysisResult, Chat, Message, ServiceMessage

logger = logging.getLogger(__name__)

class AnalysisService:

    def __init__(self, export_metrics_service: Optional[ExportMetricsService] = None):
        self._status_listeners: list[Callable[[str], None]] = []
        self._error_listeners: list[Callable[[str], None]] = []
        self._listeners_lock = threading.Lock()
        self._export_metrics_service = export_metrics_service or ExportMetricsService()

    def add_status_listener(self, callback: Callable[[str], None]):
        with self._listeners_lock:
            if callback not in self._status_listeners:
                self._status_listeners.append(callback)

    def remove_status_listener(self, callback: Callable[[str], None]):
        with self._listeners_lock:
            if callback in self._status_listeners:
                self._status_listeners.remove(callback)

    def add_error_listener(self, callback: Callable[[str], None]):
        with self._listeners_lock:
            if callback not in self._error_listeners:
                self._error_listeners.append(callback)

    def remove_error_listener(self, callback: Callable[[str], None]):
        with self._listeners_lock:
            if callback in self._error_listeners:
                self._error_listeners.remove(callback)

    def _emit_status(self, message: str):
        with self._listeners_lock:
            callbacks = tuple(self._status_listeners)
        for callback in callbacks:
            try:
                callback(message)
            except Exception:
                logger.debug("AnalysisService status listener failed", exc_info=True)

    def _emit_error(self, message: str):
        with self._listeners_lock:
            callbacks = tuple(self._error_listeners)
        for callback in callbacks:
            try:
                callback(message)
            except Exception:
                logger.debug("AnalysisService error listener failed", exc_info=True)

    def _build_processing_context(self, chat: Chat, config: Dict[str, Any]) -> ConversionContext:
        context = ConversionContext(config=config)
        anonymization_cfg = config.get("anonymization", {}) or {}
        if not anonymization_cfg.get("enabled", False):
            return context

        name_mask = anonymization_cfg.get("name_mask_format", "[ИМЯ {index}]")
        raw_mode = anonymization_cfg.get("link_mask_mode", "simple")
        try:
            link_mode = LinkMaskMode(raw_mode)
        except ValueError:
            link_mode = LinkMaskMode.SIMPLE

        link_mask_format = anonymization_cfg.get("link_mask_format", "[ССЫЛКА {index}]")
        adapter_config = AnonymizationConfig(
            enabled=True,
            hide_links=anonymization_cfg.get("hide_links", False),
            hide_names=anonymization_cfg.get("hide_names", False),
            name_mask_format=name_mask,
            link_mask_mode=link_mode,
            link_mask_format=link_mask_format,
            custom_names=anonymization_cfg.get("custom_names", []),
        )
        context.anonymizer = _LegacyAnonymizerAdapter(adapter_config)

        for msg in chat.messages:
            if isinstance(msg, Message):
                context.anonymizer.register_user(user_id=msg.author.id, name=msg.author.name)
                if msg.forwarded_from:
                    context.anonymizer.register_user(name=msg.forwarded_from)
                for reaction in msg.reactions:
                    for author in reaction.authors:
                        context.anonymizer.register_user(user_id=author.id, name=author.name)
            elif isinstance(msg, ServiceMessage):
                if msg.actor:
                    context.anonymizer.register_user(name=msg.actor)
                for member in msg.members:
                    context.anonymizer.register_user(name=member)

        context.anonymizer._rebuild_names_regex()
        return context

    def calculate_character_stats(
        self,
        chat: Chat,
        config: Dict[str, Any],
        disabled_dates: Optional[Set[Any]] = None,
        include_memory_disabled_dates: bool = True,
    ) -> AnalysisResult:
        """
        Calculates character statistics in chat.

        Args:
            chat: Chat to analyze
            config: Analysis configuration
            include_memory_disabled_dates: if False, do not exclude dates from chat memory (for full hierarchy/tree)

        Returns:
            AnalysisResult: Analysis result with date hierarchy
        """
        self._emit_status("Подсчет символов...")
        if not chat.messages:
            return AnalysisResult(total_count=0, unit="Characters", date_hierarchy={})

        context = self._build_processing_context(chat, config)
        normalized_disabled_dates = self._normalize_disabled_dates(disabled_dates)
        export_metrics = self._export_metrics_service.calculate_character_metrics(
            chat=chat,
            config=config,
            disabled_dates=normalized_disabled_dates,
            include_memory_disabled_dates=include_memory_disabled_dates,
        )
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
                    if self._is_date_disabled(year, month, day, normalized_disabled_dates):
                        continue

                    message_char_lengths.append(char_len)
            except (ValueError, AttributeError) as e:
                logger.warning(f"Error processing message {msg.id}: {e}")
                continue

        avg_message_length = (
            sum(message_char_lengths) / len(message_char_lengths)
            if message_char_lengths
            else 0
        )

        return AnalysisResult(
            total_count=export_metrics.total_count,
            unit="Characters",
            date_hierarchy=export_metrics.date_hierarchy,
            total_characters=export_metrics.total_characters,
            average_message_length=avg_message_length,
        )

    def calculate_token_stats(
        self,
        chat: Chat,
        config: Dict[str, Any],
        tokenizer: Any,
        disabled_dates: Optional[Set[Any]] = None,
        include_memory_disabled_dates: bool = True,
    ) -> AnalysisResult:
        """
        Calculates token statistics in chat.

        Args:
            chat: Chat to analyze
            config: Analysis configuration
            tokenizer: Tokenizer (e.g., from transformers)
            include_memory_disabled_dates: if False, do not exclude dates from chat memory (for full hierarchy/tree)

        Returns:
            AnalysisResult: Analysis result with date hierarchy
        """
        self._emit_status("Подсчет токенов...")
        if not chat.messages or not tokenizer:
            return AnalysisResult(total_count=0, unit="tokens", date_hierarchy={})

        export_metrics = self._export_metrics_service.calculate_token_metrics(
            chat=chat,
            config=config,
            tokenizer=tokenizer,
            disabled_dates=self._normalize_disabled_dates(disabled_dates),
            include_memory_disabled_dates=include_memory_disabled_dates,
        )

        if export_metrics.total_count == 0:
            return AnalysisResult(
                total_count=0, unit="tokens", date_hierarchy={}
            )

        return AnalysisResult(
            total_count=export_metrics.total_count,
            unit="tokens",
            date_hierarchy=export_metrics.date_hierarchy,
            total_characters=export_metrics.total_characters,
        )

    def get_full_date_hierarchy_for_calendar(
        self,
        chat: Chat,
        config: Dict[str, Any],
        tokenizer: Any = None,
        unit: str = "Characters",
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Returns date hierarchy with all days included (no disabled-date filtering).
        Used by the calendar so that each day shows its real symbol/token count:
        if we used the filtered hierarchy (analysis_result.date_hierarchy), disabled
        days would have 0 and the calendar would fall back to message_count, showing
        e.g. "1" (one message) instead of the actual ~50 characters.
        """
        if not chat.messages:
            return {}
        use_tokens = unit == "tokens" and tokenizer is not None
        if use_tokens:
            result = self._export_metrics_service.calculate_token_metrics(
                chat=chat,
                config=config,
                tokenizer=tokenizer,
                disabled_dates=set(),
                include_memory_disabled_dates=False,
            )
        else:
            result = self._export_metrics_service.calculate_character_metrics(
                chat=chat,
                config=config,
                disabled_dates=set(),
                include_memory_disabled_dates=False,
            )
        return result.date_hierarchy or {}

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
        self._emit_status("Построение дерева анализа...")
        if not analysis_result.date_hierarchy or analysis_result.total_count <= 0:
            from src.resources.translations import tr

            return TreeNode(tr("analysis.no_data"), 0)

        try:
            analyzer = TokenAnalyzer(
                date_hierarchy=analysis_result.date_hierarchy,
                config=config,
                unit=analysis_result.unit,
            )

            return analyzer.build_analysis_tree(total_count=analysis_result.total_count)

        except Exception as e:
            logger.error(f"Error building analysis tree: {e}")
            self._emit_error(f"Ошибка построения дерева анализа: {e}")
            from src.resources.translations import tr

            return TreeNode(tr("common.error"), 0)

    def recalculate_with_filters(
        self,
        chat: Chat,
        config: Dict[str, Any],
        tokenizer: Any,
        disabled_dates: Set[Any],
    ) -> tuple[AnalysisResult, TreeNode]:
        """
        Recalculates with full hierarchy (disabled_dates ignored for hierarchy)
        so the tree contains all days. Returns (result, tree).
        Filtered total is computed by the caller via get_filtered_count().
        """
        from src.resources.translations import tr
        if not chat.messages:
            empty = AnalysisResult(total_count=0, unit="Characters", date_hierarchy={})
            return empty, TreeNode(tr("analysis.no_data"), 0)
        use_tokens = tokenizer is not None
        if use_tokens:
            em = self._export_metrics_service.calculate_token_metrics(
                chat=chat,
                config=config,
                tokenizer=tokenizer,
                disabled_dates=set(),
                include_memory_disabled_dates=False,
            )
            result = AnalysisResult(
                total_count=em.total_count,
                unit="tokens",
                date_hierarchy=em.date_hierarchy,
                total_characters=em.total_characters,
            )
        else:
            em = self._export_metrics_service.calculate_character_metrics(
                chat=chat,
                config=config,
                disabled_dates=set(),
                include_memory_disabled_dates=False,
            )
            result = AnalysisResult(
                total_count=em.total_count,
                unit="Characters",
                date_hierarchy=em.date_hierarchy,
                total_characters=em.total_characters,
            )
        tree = self.build_analysis_tree(result, config)
        return result, tree

    def _find_most_active_user(self, chat: Chat) -> Optional[Any]:
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

    def _normalize_disabled_dates(
        self, disabled_dates: Optional[Set[Any]]
    ) -> Set[str]:
        """
        Converts incoming disabled date representations to YYYY-MM-DD strings.
        Accepts strings, tuples/lists and objects with year/month/day attributes.
        """
        if not disabled_dates:
            return set()

        normalized: Set[str] = set()
        for item in disabled_dates:
            if isinstance(item, str):
                cleaned = item.strip()
                if cleaned:
                    normalized.add(cleaned)
                continue

            if isinstance(item, (tuple, list)) and len(item) >= 3:
                try:
                    y, m, d = int(item[0]), int(item[1]), int(item[2])
                    normalized.add(f"{y:04d}-{m:02d}-{d:02d}")
                except (TypeError, ValueError):
                    continue
                continue

            if all(hasattr(item, attr) for attr in ("year", "month", "day")):
                try:
                    y = int(getattr(item, "year"))
                    m = int(getattr(item, "month"))
                    d = int(getattr(item, "day"))
                    normalized.add(f"{y:04d}-{m:02d}-{d:02d}")
                except (TypeError, ValueError):
                    continue

        return normalized

    def _is_date_disabled(
        self, year: str, month: str, day: str, normalized_disabled_dates: Set[str]
    ) -> bool:
        if not normalized_disabled_dates:
            return False
        return f"{year}-{month}-{day}" in normalized_disabled_dates

    def get_chat_summary(self, chat: Chat) -> Dict[str, Any]:
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
        daily_counts = defaultdict(int)

        for msg in chat.messages:
            if isinstance(msg, Message):
                date_str = msg.date.strftime("%Y-%m-%d")
                daily_counts[date_str] += 1

        return dict(daily_counts)

    def get_hourly_activity(self, chat: Chat) -> Dict[int, int]:
        hourly_counts = defaultdict(int)

        for msg in chat.messages:
            if isinstance(msg, Message):
                hour = msg.date.hour
                hourly_counts[hour] += 1

        return dict(hourly_counts)
