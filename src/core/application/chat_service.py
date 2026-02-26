

import json
import logging
import os
import threading
from typing import Any, Callable, Dict, Optional

from src.core.domain.models import Chat, User, Message

logger = logging.getLogger(__name__)
from src.core.parsing.json_parser import (
    get_parsing_statistics,
    parse_chat_from_dict,
    validate_chat_data,
)

class ChatLoadError(Exception):

    pass

class ChatService:

    def __init__(self):
        self._current_chat: Optional[Chat] = None
        self._chat_file_path: Optional[str] = None
        self._status_listeners: list[Callable[[str], None]] = []
        self._error_listeners: list[Callable[[str], None]] = []
        self._listeners_lock = threading.Lock()

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
                logger.debug("ChatService status listener failed", exc_info=True)

    def _emit_error(self, message: str):
        with self._listeners_lock:
            callbacks = tuple(self._error_listeners)
        for callback in callbacks:
            try:
                callback(message)
            except Exception:
                logger.debug("ChatService error listener failed", exc_info=True)

    def load_chat_from_file(self, file_path: str) -> Chat:
        self._emit_status("Loading file...")

        if not os.path.exists(file_path):
            self._emit_error(f"Файл не найден: {file_path}")
            raise ChatLoadError(f"File not found: {file_path}")

        if os.path.getsize(file_path) == 0:
            self._emit_error(f"Файл пустой: {file_path}")
            raise ChatLoadError(f"File is empty: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except json.JSONDecodeError as e:
            self._emit_error(f"Ошибка парсинга JSON: {e}")
            raise ChatLoadError(f"JSON parsing error: {e}")
        except (IOError, OSError) as e:
            self._emit_error(f"Ошибка чтения файла: {e}")
            raise ChatLoadError(f"File reading error: {e}")

        self._emit_status("Checking chat data structure...")
        validation_issues = validate_chat_data(raw_data)
        if validation_issues:
            issues_str = "; ".join(validation_issues)
            self._emit_error(f"Некорректные данные чата: {issues_str}")
            raise ChatLoadError(f"Invalid chat data: {issues_str}")

        try:
            self._emit_status("Parsing messages...")
            chat = parse_chat_from_dict(raw_data)
            self._current_chat = chat
            self._chat_file_path = file_path

            return chat

        except (ValueError, KeyError) as e:
            self._emit_error(f"Ошибка парсинга чата: {e}")
            raise ChatLoadError(f"Chat parsing error: {e}")

    def get_current_chat(self) -> Optional[Chat]:
        return self._current_chat

    def get_current_file_path(self) -> Optional[str]:
        return self._chat_file_path

    def has_chat_loaded(self) -> bool:
        return self._current_chat is not None

    def clear_current_chat(self):
        self._current_chat = None
        self._chat_file_path = None

    def get_chat_statistics(self, chat: Optional[Chat] = None) -> Dict[str, Any]:
        target_chat = chat or self._current_chat
        if not target_chat:
            return {}

        users = target_chat.get_users()

        user_message_counts = {}
        for user in users:
            user_messages = target_chat.get_messages_by_user(user.id)
            user_message_counts[user.name] = len(user_messages)

        try:
            start_date, end_date = target_chat.get_date_range()
        except ValueError:
            start_date = end_date = None

        return {
            "chat_name": target_chat.name,
            "chat_type": target_chat.type,
            "total_messages": target_chat.total_message_count,
            "regular_messages": target_chat.message_count,
            "service_messages": target_chat.service_message_count,
            "unique_users": len(users),
            "user_message_counts": user_message_counts,
            "date_range": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
        }

    def validate_file_before_load(self, file_path: str) -> Dict[str, Any]:
        result = {
            "is_valid": False,
            "file_exists": False,
            "file_size": 0,
            "is_json": False,
            "parsing_stats": {},
            "issues": [],
        }

        if not os.path.exists(file_path):
            result["issues"].append("File not found")
            return result

        result["file_exists"] = True
        result["file_size"] = os.path.getsize(file_path)

        if result["file_size"] == 0:
            result["issues"].append("File is empty")
            return result

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            result["is_json"] = True
        except json.JSONDecodeError as e:
            result["issues"].append(f"Invalid JSON: {e}")
            return result
        except (IOError, OSError) as e:
            result["issues"].append(f"File reading error: {e}")
            return result

        validation_issues = validate_chat_data(data)
        if validation_issues:
            result["issues"].extend(validation_issues)
            return result

        try:
            result["parsing_stats"] = get_parsing_statistics(data)
            result["is_valid"] = True
        except Exception as e:
            result["issues"].append(f"Data analysis error: {e}")

        return result

    def detect_chat_type(self, chat: Optional[Chat] = None) -> str:
        target_chat = chat or self._current_chat
        if not target_chat:
            return "group"

        detected_type = target_chat.type
        return detected_type

    def get_user_activity_stats(self, chat: Optional[Chat] = None) -> Dict[str, Dict[str, Any]]:
        target_chat = chat or self._current_chat
        if not target_chat:
            return {}

        user_stats = {}

        for msg in target_chat.messages:
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

    def get_daily_activity(self, chat: Optional[Chat] = None) -> Dict[str, int]:
        target_chat = chat or self._current_chat
        if not target_chat:
            return {}

        from collections import defaultdict
        daily_counts = defaultdict(int)

        for msg in target_chat.messages:
            if isinstance(msg, Message):
                date_str = msg.date.strftime("%Y-%m-%d")
                daily_counts[date_str] += 1

        return dict(daily_counts)
