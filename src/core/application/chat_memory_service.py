

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import unified_diff
from pathlib import Path
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)

@dataclass
class DayOverride:
    original_hash: str
    original_text: str
    edited_text: str
    edited_at: str

class ChatMemoryService:

    def __init__(self, base_dir: Optional[Path] = None):
        root = base_dir or (Path.home() / ".config" / "Tkonverter" / "chat_memory")
        self._base_dir = Path(root).expanduser()
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def load_memory(self, chat_id: int) -> Dict[str, Any]:
        path = self._memory_path(chat_id)
        if not path.exists():
            return self._empty_memory(chat_id)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return self._empty_memory(chat_id)

        if not isinstance(data, dict):
            return self._empty_memory(chat_id)

        memory = self._empty_memory(chat_id)
        memory["updated_at"] = str(data.get("updated_at", ""))

        disabled_dates = data.get("disabled_dates", [])
        if isinstance(disabled_dates, list):
            normalized = []
            for value in disabled_dates:
                if not isinstance(value, str):
                    continue
                key = self._normalize_date_key(value)
                if key:
                    normalized.append(key)
            memory["disabled_dates"] = normalized

        day_overrides = data.get("day_overrides", {})
        if isinstance(day_overrides, dict):
            safe_overrides: Dict[str, Dict[str, str]] = {}
            for date_key, payload in day_overrides.items():
                if not self._is_valid_date_key(date_key) or not isinstance(payload, dict):
                    continue
                original_hash = str(payload.get("original_hash", "")).strip()
                edited_text = str(payload.get("edited_text", ""))
                original_text = str(payload.get("original_text", ""))
                edited_at = str(payload.get("edited_at", ""))
                if not original_hash:
                    continue
                safe_overrides[date_key] = {
                    "original_hash": original_hash,
                    "original_text": original_text,
                    "edited_text": edited_text,
                    "edited_at": edited_at,
                }
            memory["day_overrides"] = safe_overrides

        return memory

    def save_memory(self, chat_id: int, memory: Dict[str, Any]) -> None:
        path = self._memory_path(chat_id)
        payload = self._empty_memory(chat_id)
        payload["updated_at"] = self._utc_now()
        payload["disabled_dates"] = sorted(
            {
                str(value)
                for value in memory.get("disabled_dates", [])
                if isinstance(value, str) and self._is_valid_date_key(value)
            }
        )
        payload["day_overrides"] = memory.get("day_overrides", {})
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_disabled_dates(self, chat_id: int) -> Set[str]:
        memory = self.load_memory(chat_id)
        return set(memory.get("disabled_dates", []))

    def update_disabled_dates(self, chat_id: int, disabled_dates: Set[str]) -> None:
        memory = self.load_memory(chat_id)
        normalized = set()
        for value in disabled_dates:
            if not isinstance(value, str):
                continue
            key = self._normalize_date_key(value)
            if key:
                normalized.add(key)
        memory["disabled_dates"] = sorted(normalized)
        self.save_memory(chat_id, memory)

    def get_day_override(self, chat_id: int, date_key: str) -> Optional[DayOverride]:
        if not self._is_valid_date_key(date_key):
            return None
        memory = self.load_memory(chat_id)
        payload = memory.get("day_overrides", {}).get(date_key)
        if not isinstance(payload, dict):
            return None
        return DayOverride(
            original_hash=str(payload.get("original_hash", "")),
            original_text=str(payload.get("original_text", "")),
            edited_text=str(payload.get("edited_text", "")),
            edited_at=str(payload.get("edited_at", "")),
        )

    def upsert_day_override(
        self,
        chat_id: int,
        date_key: str,
        original_text: str,
        edited_text: str,
    ) -> None:
        if not self._is_valid_date_key(date_key):
            return
        memory = self.load_memory(chat_id)
        day_overrides = dict(memory.get("day_overrides", {}))
        day_overrides[date_key] = {
            "original_hash": self.hash_text(original_text),
            "original_text": original_text,
            "edited_text": edited_text,
            "edited_at": self._utc_now(),
        }
        memory["day_overrides"] = day_overrides
        self.save_memory(chat_id, memory)

    def delete_day_override(self, chat_id: int, date_key: str) -> None:
        memory = self.load_memory(chat_id)
        day_overrides = dict(memory.get("day_overrides", {}))
        day_overrides.pop(date_key, None)
        memory["day_overrides"] = day_overrides
        self.save_memory(chat_id, memory)

    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256((text or "").encode("utf-8")).hexdigest()

    @staticmethod
    def build_diff(old_text: str, new_text: str, old_label: str, new_label: str) -> str:
        return "\n".join(
            unified_diff(
                (old_text or "").splitlines(),
                (new_text or "").splitlines(),
                fromfile=old_label,
                tofile=new_label,
                lineterm="",
            )
        )

    def _memory_path(self, chat_id: int) -> Path:
        return self._base_dir / f"{chat_id}.json"

    @staticmethod
    def _empty_memory(chat_id: int) -> Dict[str, Any]:
        return {
            "chat_id": chat_id,
            "updated_at": "",
            "disabled_dates": [],
            "day_overrides": {},
        }

    @staticmethod
    def _is_valid_date_key(value: str) -> bool:
        if not value or len(value) != 10:
            return False
        parts = value.split("-")
        return len(parts) == 3 and all(part.isdigit() for part in parts)

    @staticmethod
    def _normalize_date_key(value: str) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        parts = value.strip().split("-")
        if len(parts) != 3:
            return None
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            if y < 1900 or y > 2100 or m < 1 or m > 12 or d < 1 or d > 31:
                return None
            return f"{y:04d}-{m:02d}-{d:02d}"
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(tz=timezone.utc).isoformat()
