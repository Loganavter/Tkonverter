"""
Service for working with chats.

Responsible for loading, parsing and validating chat data.
Does not depend on PyQt or other UI frameworks.
"""

import json
import os
from typing import Any, Dict, Optional

from src.core.domain.models import Chat, User, Message
from src.core.parsing.json_parser import (
    get_parsing_statistics,
    parse_chat_from_dict,
    validate_chat_data,
)

class ChatLoadError(Exception):
    """Exception when chat loading error occurs."""

    pass

class ChatService:
    """Service for working with chats."""

    def __init__(self):
        self._current_chat: Optional[Chat] = None
        self._chat_file_path: Optional[str] = None

    def load_chat_from_file(self, file_path: str) -> Chat:
        """
        Loads chat from JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            Chat: Loaded and parsed chat

        Raises:
            ChatLoadError: On loading or parsing error
        """
        if not os.path.exists(file_path):
            raise ChatLoadError(f"File not found: {file_path}")

        if os.path.getsize(file_path) == 0:
            raise ChatLoadError(f"File is empty: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ChatLoadError(f"JSON parsing error: {e}")
        except (IOError, OSError) as e:
            raise ChatLoadError(f"File reading error: {e}")

        validation_issues = validate_chat_data(raw_data)
        if validation_issues:
            issues_str = "; ".join(validation_issues)
            raise ChatLoadError(f"Invalid chat data: {issues_str}")

        try:
            chat = parse_chat_from_dict(raw_data)
            self._current_chat = chat
            self._chat_file_path = file_path

            return chat

        except (ValueError, KeyError) as e:
            raise ChatLoadError(f"Chat parsing error: {e}")

    def get_current_chat(self) -> Optional[Chat]:
        """Returns currently loaded chat."""
        return self._current_chat

    def get_current_file_path(self) -> Optional[str]:
        """Returns path to current chat file."""
        return self._chat_file_path

    def has_chat_loaded(self) -> bool:
        """Checks if chat is loaded."""
        return self._current_chat is not None

    def clear_current_chat(self):
        """Clears current chat."""
        self._current_chat = None
        self._chat_file_path = None

    def get_chat_statistics(self, chat: Optional[Chat] = None) -> Dict[str, Any]:
        """
        Returns chat statistics.

        Args:
            chat: Chat to analyze. If None, current chat is used.

        Returns:
            Dict[str, Any]: Dictionary with statistics
        """
        target_chat = chat or self._current_chat
        if not target_chat:
            return {}

        users = target_chat.get_users()

        user_message_counts = {}
        for user in users:
            user_messages = target_chat.get_messages_by_user(user.id)
            user_message_counts[user.name] = len(user_messages)

        most_active_user = None
        if user_message_counts:

            if target_chat.type == "personal":

                most_active_user = User(id="partner", name=target_chat.name)
            else:

                most_active_user_name = max(
                    user_message_counts, key=user_message_counts.get
                )
                most_active_user = next(
                    (u for u in users if u.name == most_active_user_name), None
                )

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
            "most_active_user": most_active_user.name if most_active_user else None,
            "date_range": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
        }

    def validate_file_before_load(self, file_path: str) -> Dict[str, Any]:
        """
        Validates chat file without full loading.

        Args:
            file_path: Path to file for validation

        Returns:
            Dict[str, Any]: Validation result with file information
        """
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
        """
        Detects chat type.

        Args:
            chat: Chat to analyze. If None, current chat is used.

        Returns:
            str: Chat type ('group', 'personal', 'posts', 'channel')
        """
        target_chat = chat or self._current_chat
        if not target_chat:
            return "group"

        detected_type = target_chat.type
        return detected_type
    
    def get_user_activity_stats(self, chat: Optional[Chat] = None) -> Dict[str, Dict[str, Any]]:
        """
        Returns user activity statistics.
        
        Args:
            chat: Chat to analyze. If None, current chat is used.
            
        Returns:
            Dict[str, Dict[str, Any]]: Statistics by users
        """
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
        """
        Returns activity by day.
        
        Args:
            chat: Chat to analyze. If None, current chat is used.
            
        Returns:
            Dict[str, int]: Dictionary day -> number of messages
        """
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