

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set

from src.core.application.chat_memory_service import ChatMemoryService
from src.core.conversion.domain_adapters import chat_to_dict
from src.core.conversion.main_converter import (
    _build_plain_text_segments,
    _initialize_context,
)
from src.core.domain.models import Chat

@dataclass
class ExportMetricsResult:
    total_count: int
    date_hierarchy: Dict[str, Dict[str, Dict[str, float]]]
    total_characters: int

class ExportMetricsService:

    def __init__(self, chat_memory_service: Optional[ChatMemoryService] = None):
        self._chat_memory_service = chat_memory_service

    def calculate_character_metrics(
        self,
        chat: Chat,
        config: Dict[str, Any],
        disabled_dates: Optional[Set[Any]] = None,
        include_memory_disabled_dates: bool = True,
    ) -> ExportMetricsResult:
        _, segments, messages = self._build_effective_segments(
            chat=chat,
            config=config,
            disabled_dates=disabled_dates,
            include_memory_disabled_dates=include_memory_disabled_dates,
        )
        exported_text = "".join(part for _, part in segments).strip() + "\n"
        total_chars = len(exported_text)
        first_date_key = self._get_first_valid_date_key(messages)

        hierarchy = self._build_character_hierarchy(
            segments=segments,
            total_chars=total_chars,
            fallback_date_key=first_date_key,
        )
        return ExportMetricsResult(
            total_count=total_chars,
            date_hierarchy=hierarchy,
            total_characters=total_chars,
        )

    def calculate_token_metrics(
        self,
        chat: Chat,
        config: Dict[str, Any],
        tokenizer: Any,
        disabled_dates: Optional[Set[Any]] = None,
        include_memory_disabled_dates: bool = True,
    ) -> ExportMetricsResult:
        _, segments, messages = self._build_effective_segments(
            chat=chat,
            config=config,
            disabled_dates=disabled_dates,
            include_memory_disabled_dates=include_memory_disabled_dates,
        )
        exported_text = "".join(part for _, part in segments).strip() + "\n"
        total_chars = len(exported_text)
        total_tokens = len(tokenizer.encode(exported_text))
        first_date_key = self._get_first_valid_date_key(messages)

        hierarchy = self._build_token_hierarchy(
            tokenizer=tokenizer,
            segments=segments,
            total_tokens=total_tokens,
            fallback_date_key=first_date_key,
        )

        return ExportMetricsResult(
            total_count=total_tokens,
            date_hierarchy=hierarchy,
            total_characters=total_chars,
        )

    def _build_effective_segments(
        self,
        chat: Chat,
        config: Dict[str, Any],
        disabled_dates: Optional[Set[Any]],
        include_memory_disabled_dates: bool = True,
    ) -> tuple[Dict[str, Any], list[tuple[str | None, str]], list[dict]]:
        normalized_disabled_dates = self._normalize_disabled_dates(disabled_dates)
        memory_disabled_dates, day_overrides = self._load_chat_memory(chat.chat_id)
        if include_memory_disabled_dates:
            effective_disabled_dates = normalized_disabled_dates | memory_disabled_dates
        else:
            effective_disabled_dates = normalized_disabled_dates

        filtered_chat_dict = self._filtered_chat_dict(chat, effective_disabled_dates)
        segments, messages = _build_plain_text_segments(
            filtered_chat_dict, config, html_mode=False, disabled_nodes=None
        )
        if day_overrides:
            context = _initialize_context(filtered_chat_dict, config)
            segments = self._apply_day_overrides(segments, day_overrides, context)
        return filtered_chat_dict, segments, messages

    def _load_chat_memory(
        self, chat_id: Optional[int]
    ) -> tuple[Set[str], Dict[str, Dict[str, Any]]]:
        if chat_id is None or self._chat_memory_service is None:
            return set(), {}
        memory = self._chat_memory_service.load_memory(chat_id)
        disabled_dates = {
            str(d)
            for d in memory.get("disabled_dates", [])
            if isinstance(d, str) and self._is_valid_date_key(d)
        }
        raw_overrides = memory.get("day_overrides", {})
        if not isinstance(raw_overrides, dict):
            return disabled_dates, {}
        overrides = {
            k: v
            for k, v in raw_overrides.items()
            if self._is_valid_date_key(k) and isinstance(v, dict)
        }
        return disabled_dates, overrides

    def _apply_day_overrides(
        self,
        segments: list[tuple[str | None, str]],
        day_overrides: Dict[str, Dict[str, Any]],
        context: Any = None,
    ) -> list[tuple[str | None, str]]:
        merged_segments: list[tuple[str | None, str]] = []
        replaced_dates: set[str] = set()
        for date_key, part in segments:
            if (
                isinstance(date_key, str)
                and date_key in day_overrides
                and date_key not in replaced_dates
            ):
                edited_text = str(day_overrides[date_key].get("edited_text", "")).strip()
                if edited_text and context and getattr(context, "anonymizer", None):
                    edited_text = context.anonymizer.process_text(edited_text)
                if edited_text:
                    merged_segments.append((date_key, edited_text + "\n"))
                replaced_dates.add(date_key)
                continue
            if isinstance(date_key, str) and date_key in replaced_dates:
                continue
            merged_segments.append((date_key, part))
        return merged_segments

    def _build_character_hierarchy(
        self,
        segments: list[tuple[str | None, str]],
        total_chars: int,
        fallback_date_key: str | None,
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        per_date_chars = defaultdict(int)
        unattributed_chars = 0

        for date_key, text in segments:
            if not text:
                continue
            piece_len = len(text)
            if self._is_valid_date_key(date_key):
                per_date_chars[date_key] += piece_len
            else:
                unattributed_chars += piece_len

        if fallback_date_key:
            per_date_chars[fallback_date_key] += unattributed_chars

        hierarchy = self._date_values_to_hierarchy(per_date_chars)
        hierarchy_sum = self._hierarchy_sum(hierarchy)
        delta = total_chars - hierarchy_sum
        if delta and fallback_date_key:
            y, m, d = fallback_date_key.split("-")
            hierarchy.setdefault(y, {}).setdefault(m, {})
            hierarchy[y][m][d] = float(hierarchy[y][m].get(d, 0.0) + delta)

        return hierarchy

    def _build_token_hierarchy(
        self,
        tokenizer: Any,
        segments: list[tuple[str | None, str]],
        total_tokens: int,
        fallback_date_key: str | None,
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        per_date_text = defaultdict(str)
        unattributed_text_parts: list[str] = []

        for date_key, text in segments:
            if not text:
                continue
            if self._is_valid_date_key(date_key):
                per_date_text[date_key] += text
            else:
                unattributed_text_parts.append(text)

        if fallback_date_key and unattributed_text_parts:
            per_date_text[fallback_date_key] = "".join(unattributed_text_parts) + per_date_text.get(
                fallback_date_key, ""
            )

        per_date_tokens = defaultdict(int)
        for date_key, text in per_date_text.items():
            if not text:
                continue
            per_date_tokens[date_key] = len(tokenizer.encode(text))

        hierarchy = self._date_values_to_hierarchy(per_date_tokens)
        hierarchy_sum = self._hierarchy_sum(hierarchy)
        delta = total_tokens - hierarchy_sum
        if delta and fallback_date_key:
            y, m, d = fallback_date_key.split("-")
            hierarchy.setdefault(y, {}).setdefault(m, {})
            hierarchy[y][m][d] = float(hierarchy[y][m].get(d, 0.0) + delta)

        return hierarchy

    def _filtered_chat_dict(
        self, chat: Chat, normalized_disabled_dates: Set[str]
    ) -> Dict[str, Any]:
        chat_dict = chat_to_dict(chat)
        if not normalized_disabled_dates:
            return chat_dict

        filtered_messages = []
        for msg in chat_dict.get("messages", []):
            msg_date = str(msg.get("date", ""))[:10]
            if msg_date and msg_date in normalized_disabled_dates:
                continue
            filtered_messages.append(msg)

        filtered_chat_dict = dict(chat_dict)
        filtered_chat_dict["messages"] = filtered_messages
        return filtered_chat_dict

    def _normalize_disabled_dates(
        self, disabled_dates: Optional[Set[Any]]
    ) -> Set[str]:
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

    def _date_values_to_hierarchy(
        self, date_values: Dict[str, int]
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        hierarchy = defaultdict(lambda: defaultdict(dict))
        for date_key, value in date_values.items():
            if not self._is_valid_date_key(date_key):
                continue
            year, month, day = date_key.split("-")
            hierarchy[year][month][day] = float(value)
        return {
            year: {month: dict(days) for month, days in months.items()}
            for year, months in hierarchy.items()
        }

    @staticmethod
    def _is_valid_date_key(date_key: str | None) -> bool:
        if not date_key or len(date_key) != 10:
            return False
        parts = date_key.split("-")
        return len(parts) == 3 and all(part.isdigit() for part in parts)

    @staticmethod
    def _get_first_valid_date_key(messages: list[dict]) -> str | None:
        for msg in messages:
            date_key = str(msg.get("date", ""))[:10]
            if ExportMetricsService._is_valid_date_key(date_key):
                return date_key
        return None

    @staticmethod
    def _hierarchy_sum(hierarchy: Dict[str, Dict[str, Dict[str, float]]]) -> int:
        return int(
            sum(
                value
                for months in hierarchy.values()
                for days in months.values()
                for value in days.values()
            )
        )
