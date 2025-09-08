"""
JSON parser for converting Telegram data to domain models.

This module is responsible for parsing Telegram export JSON files
and creating type-safe domain objects.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from core.domain.models import (
    Chat,
    GiveawayInfo,
    GiveawayResultsInfo,
    MediaInfo,
    Message,
    PaidMedia,
    Reaction,
    ServiceMessage,
    TodoList,
    TodoListItem,
    User,
)

logger = logging.getLogger(__name__)

def parse_user_from_dict(user_data: Dict[str, Any]) -> User:
    """Creates User object from dictionary."""
    return User(
        id=str(user_data.get("from_id", "")), name=str(user_data.get("from", ""))
    )

def parse_reaction_from_dict(reaction_data: Dict[str, Any]) -> Reaction:
    """Creates Reaction object from dictionary."""
    authors = []
    for author_data in reaction_data.get("recent", []):
        try:
            author = User(
                id=str(author_data.get("from_id", "")),
                name=str(author_data.get("from", "")),
            )
            authors.append(author)
        except ValueError as e:
            logger.warning(f"Error parsing reaction author: {e}")
            continue

    emoji_text = ""

    if reaction_data.get("type") == "custom_emoji":

        from resources.translations import tr
        emoji_text = f"{tr('Custom')} {tr('Emoji')}"
    else:

        emoji_text = reaction_data.get("emoji", "")

    return Reaction(
        emoji=emoji_text,
        count=reaction_data.get("count", 0),
        authors=authors,
    )

def parse_media_from_dict(msg_data: Dict[str, Any]) -> Optional[MediaInfo]:
    """Creates MediaInfo object from message data."""

    if "photo" in msg_data:
        return MediaInfo(
            media_type="photo",
            file_name=msg_data.get("photo"),
            file_size=msg_data.get("photo_file_size"),
            width=msg_data.get("width"),
            height=msg_data.get("height"),
        )

    media_type = msg_data.get("media_type")
    if not media_type and not msg_data.get("file") and not msg_data.get("photo"):
        return None

    return MediaInfo(
        media_type=media_type,
        file_name=msg_data.get("file_name") or msg_data.get("file"),
        file_size=msg_data.get("file_size"),
        duration_seconds=msg_data.get("duration_seconds"),
        sticker_emoji=msg_data.get("sticker_emoji"),
        width=msg_data.get("width"),
        height=msg_data.get("height"),
    )

def parse_date_string(date_str: str) -> datetime:
    """Parses date string to datetime object."""
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:

        try:
            return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            logger.warning(f"Failed to parse date: {date_str}")
            return datetime.now()

def parse_todo_list_from_dict(todo_data: Dict[str, Any]) -> TodoList:
    """Creates TodoList object from dictionary."""
    items = []
    for item_data in todo_data.get("items", []):
        items.append(
            TodoListItem(
                id=item_data.get("id", 0),
                text=item_data.get("text", "")
            )
        )
    return TodoList(
        title=todo_data.get("title", ""),
        items=items
    )

def parse_paid_media_from_dict(msg_data: Dict[str, Any]) -> PaidMedia:
    """Creates PaidMedia object from dictionary."""
    return PaidMedia(
        paid_stars_amount=msg_data.get("paid_stars_amount", 0)
    )

def parse_message_from_dict(msg_data: Dict[str, Any]) -> Message:
    """Creates Message object from dictionary."""

    author = User(
        id=str(msg_data.get("from_id", "")), name=str(msg_data.get("from", ""))
    )

    date = parse_date_string(msg_data.get("date", ""))

    edited = None
    if "edited" in msg_data:
        edited = parse_date_string(msg_data["edited"])

    reactions = []
    for reaction_data in msg_data.get("reactions", []):
        try:
            reaction = parse_reaction_from_dict(reaction_data)
            reactions.append(reaction)
        except (ValueError, KeyError) as e:
            logger.warning(f"Error parsing reaction: {e}")
            continue

    media = parse_media_from_dict(msg_data)

    raw_media_fields = {}
    for key in [
        "poll",
        "contact_information",
        "location_information",
        "venue",
        "dice",
        "game_information",
        "invoice_information",
        "place_name",
        "address",
    ]:
        if key in msg_data:
            raw_media_fields[key] = msg_data[key]

    giveaway_info = None
    if gi_data := msg_data.get("giveaway_information"):
        giveaway_info = GiveawayInfo(
            quantity=gi_data.get("quantity", 0),
            months=gi_data.get("months", 0),
            until_date=parse_date_string(gi_data.get("until_date", "")),
            channels=gi_data.get("channels", []),
            countries=gi_data.get("countries", []),
            additional_prize=gi_data.get("additional_prize"),
        )

    giveaway_results_info = None
    if gr_data := msg_data.get("giveaway_results"):
        giveaway_results_info = GiveawayResultsInfo(
            winners_count=gr_data.get("winners_count", 0),
            unclaimed_count=gr_data.get("unclaimed_count", 0),
            months=gr_data.get("months", 0),
            launch_message_id=gr_data.get("launch_message_id", 0),
        )

    todo_list = None
    if todo_data := msg_data.get("todo_list"):
        todo_list = parse_todo_list_from_dict(todo_data)

    paid_media = None
    if "paid_stars_amount" in msg_data:
        paid_media = parse_paid_media_from_dict(msg_data)

    return Message(
        id=msg_data.get("id", 0),
        author=author,
        date=date,
        text=msg_data.get("text", ""),
        reactions=reactions,
        reply_to_id=msg_data.get("reply_to_message_id"),
        edited=edited,
        media=media,
        forwarded_from=msg_data.get("forwarded_from"),
        raw_media=raw_media_fields,
        media_spoiler=msg_data.get("media_spoiler", False),
        giveaway_info=giveaway_info,
        giveaway_results_info=giveaway_results_info,
        showForwardedAsOriginal=msg_data.get("showForwardedAsOriginal", False),
        todo_list=todo_list,
        paid_media=paid_media,
        raw_inline_buttons=msg_data.get("inline_bot_buttons"),
    )

def parse_service_message_from_dict(msg_data: Dict[str, Any]) -> ServiceMessage:
    """Creates ServiceMessage object from dictionary."""
    media = None

    if msg_data.get("action") == "suggest_profile_photo" and "photo" in msg_data:
        media = parse_media_from_dict(msg_data)

    return ServiceMessage(
        id=msg_data.get("id", 0),
        date=parse_date_string(msg_data.get("date", "")),
        action=msg_data.get("action", ""),
        actor=msg_data.get("actor"),
        title=msg_data.get("title"),
        members=msg_data.get("members", []),
        period_seconds=msg_data.get("period_seconds"),
        media=media,
    )

def parse_chat_from_dict(data: Dict[str, Any]) -> Chat:
    """
    Main parsing function - converts JSON dictionary to Chat object.

    Args:
        data: Dictionary with chat data from Telegram JSON file

    Returns:
        Chat: Domain chat object

    Raises:
        ValueError: If data is incorrect
        KeyError: If required fields are missing
    """
    if not isinstance(data, dict):
        raise ValueError("Data must be a dictionary")

    if "messages" not in data:
        raise KeyError("Missing 'messages' field")

    messages: List[Union[Message, ServiceMessage]] = []

    for i, msg_data in enumerate(data["messages"]):
        try:
            if not isinstance(msg_data, dict):
                logger.warning(f"Message {i} is not a dictionary, skipping")
                continue

            msg_type = msg_data.get("type", "message")

            if msg_type == "message":
                message = parse_message_from_dict(msg_data)
                messages.append(message)
            elif msg_type == "service":
                service_message = parse_service_message_from_dict(msg_data)
                messages.append(service_message)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
                continue

        except (ValueError, KeyError) as e:
            logger.warning(f"Error parsing message {i}: {e}")
            continue

    chat_type = _detect_chat_type(data, messages)

    return Chat(
        name=data.get("name", "Unnamed Chat"), type=chat_type, messages=messages
    )

def _detect_chat_type(
    data: Dict[str, Any], messages: List[Union[Message, ServiceMessage]]
) -> str:
    """
    Automatically detects chat type based on message analysis.

    Args:
        data: Original chat data
        messages: List of parsed messages

    Returns:
        str: Chat type ('group', 'personal', 'posts', 'channel')
    """
    if not messages:
        return "group"

    author_ids = set()
    first_message = None

    for msg in messages:
        if isinstance(msg, Message):
            if first_message is None:
                first_message = msg
            author_ids.add(msg.author.id)

    num_authors = len(author_ids)

    if num_authors == 2:
        return "personal"
    elif num_authors > 2:
        return "group"
    elif num_authors == 1 and first_message and first_message.forwarded_from:
        return "posts"
    elif num_authors == 1:
        return "channel"
    else:
        return "group"

def validate_chat_data(data: Dict[str, Any]) -> List[str]:
    """
    Validates chat data and returns list of found issues.

    Args:
        data: Chat data for validation

    Returns:
        List[str]: List of found issue descriptions
    """
    issues = []

    if not isinstance(data, dict):
        issues.append("Data is not a dictionary")
        return issues

    if "messages" not in data:
        issues.append("Missing 'messages' field")
    elif not isinstance(data["messages"], list):
        issues.append("'messages' field is not a list")

    if "name" not in data:
        issues.append("Missing chat name")

    return issues

def get_parsing_statistics(data: Dict[str, Any]) -> Dict[str, int]:
    """
    Returns parsing statistics without actually creating objects.

    Args:
        data: Chat data

    Returns:
        Dict[str, int]: Statistics (message count, service messages, etc.)
    """
    stats = {
        "total_messages": 0,
        "regular_messages": 0,
        "service_messages": 0,
        "messages_with_media": 0,
        "messages_with_reactions": 0,
        "unique_authors": 0,
    }

    if not isinstance(data, dict) or "messages" not in data:
        return stats

    authors = set()

    for msg_data in data.get("messages", []):
        if not isinstance(msg_data, dict):
            continue

        stats["total_messages"] += 1

        msg_type = msg_data.get("type", "message")
        if msg_type == "message":
            stats["regular_messages"] += 1

            if msg_data.get("from_id"):
                authors.add(msg_data["from_id"])

            if msg_data.get("media_type"):
                stats["messages_with_media"] += 1

            if msg_data.get("reactions"):
                stats["messages_with_reactions"] += 1

        elif msg_type == "service":
            stats["service_messages"] += 1

    stats["unique_authors"] = len(authors)
    return stats
