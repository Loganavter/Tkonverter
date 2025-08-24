"""
Adapters for converting domain objects to format understandable by existing formatters.

This module provides backward compatibility between new domain models
and existing formatters that expect dictionaries.
"""

from typing import Any, Dict
from dataclasses import asdict
from core.domain.models import Chat, MediaInfo, Message, Reaction, ServiceMessage, User

def user_to_dict(user: User) -> Dict[str, str]:
    """Converts User to dictionary."""
    return {"from_id": user.id, "from": user.name}

def reaction_to_dict(reaction: Reaction) -> Dict[str, Any]:
    """Converts Reaction to dictionary."""
    return {
        "emoji": reaction.emoji,
        "count": reaction.count,
        "recent": [user_to_dict(author) for author in reaction.authors],
    }

def media_to_dict_fields(media: MediaInfo) -> Dict[str, Any]:
    """Converts MediaInfo to message dictionary fields."""
    fields = {}

    if media.media_type:
        fields["media_type"] = media.media_type
    if media.file_name:
        fields["file"] = media.file_name
        fields["file_name"] = media.file_name
    if media.file_size is not None:
        fields["file_size"] = media.file_size
    if media.duration_seconds is not None:
        fields["duration_seconds"] = media.duration_seconds
    if media.sticker_emoji:
        fields["sticker_emoji"] = media.sticker_emoji
    if media.width is not None:
        fields["width"] = media.width
    if media.height is not None:
        fields["height"] = media.height

    return fields

def message_to_dict(message: Message) -> Dict[str, Any]:
    """Converts Message to dictionary format for formatters."""
    msg_dict = {
        "id": message.id,
        "type": "message",
        "from_id": message.author.id,
        "from": message.author.name,
        "date": message.date.isoformat(),
        "text": message.text,
    }

    if message.reply_to_id is not None:
        msg_dict["reply_to_message_id"] = message.reply_to_id

    if message.edited:
        msg_dict["edited"] = message.edited.isoformat()

    if message.showForwardedAsOriginal:
        msg_dict["showForwardedAsOriginal"] = True

    if message.forwarded_from:
        msg_dict["forwarded_from"] = message.forwarded_from

    if message.reactions:
        msg_dict["reactions"] = [reaction_to_dict(r) for r in message.reactions]

    if message.media:
        msg_dict.update(media_to_dict_fields(message.media))

    if message.media_spoiler:
        msg_dict["media_spoiler"] = True

    if message.giveaway_info:
        from dataclasses import asdict
        msg_dict["giveaway_information"] = asdict(message.giveaway_info)
    if message.giveaway_results_info:
        from dataclasses import asdict
        msg_dict["giveaway_results_information"] = asdict(message.giveaway_results_info)

    if message.raw_inline_buttons:
        msg_dict["inline_bot_buttons"] = message.raw_inline_buttons

    if message.raw_media:
        msg_dict.update(message.raw_media)

    return msg_dict

def service_message_to_dict(service_msg: ServiceMessage) -> Dict[str, Any]:
    """Converts ServiceMessage to dictionary format for formatters."""
    msg_dict = {
        "id": service_msg.id,
        "type": "service",
        "date": service_msg.date.isoformat(),
        "action": service_msg.action,
    }

    full_dict = asdict(service_msg)
    for key, value in full_dict.items():
        if key not in msg_dict and value is not None:
            if isinstance(value, list) and not value:
                continue
            msg_dict[key] = value

    if service_msg.media:
        msg_dict.update(media_to_dict_fields(service_msg.media))

    return msg_dict

def chat_to_dict(chat: Chat) -> Dict[str, Any]:
    """Converts Chat to dictionary format for existing components."""

    messages_dicts = []
    for msg in chat.messages:
        if isinstance(msg, Message):
            messages_dicts.append(message_to_dict(msg))
        elif isinstance(msg, ServiceMessage):
            messages_dicts.append(service_message_to_dict(msg))

    return {"name": chat.name, "type": chat.type, "messages": messages_dicts}

def create_message_map(chat: Chat) -> Dict[int, Dict[str, Any]]:
    """
    Creates message map for fast lookup by ID.

    Returns dictionary where keys are message IDs, values are message dictionaries.
    This is needed for reply functionality.
    """
    message_map = {}

    for msg in chat.messages:
        if isinstance(msg, Message):
            message_map[msg.id] = message_to_dict(msg)
        elif isinstance(msg, ServiceMessage):
            message_map[msg.id] = service_message_to_dict(msg)

    return message_map

def get_main_post_id(chat: Chat) -> int | None:
    """
    Finds main post ID in 'posts' type chat.

    In 'posts' type chats, usually the first message is the main post,
    and the rest are comments to it.
    """
    if chat.type != "posts":
        return None

    for msg in chat.messages:
        if isinstance(msg, Message):
            return msg.id

    return None

def detect_user_ids_for_personal_chat(chat: Chat) -> tuple[str | None, str | None]:
    """
    Determines user IDs in personal chat.

    Returns tuple (my_id, partner_id), where my_id and partner_id
    can be None if impossible to determine.
    """
    if chat.type != "personal":
        return None, None

    user_ids = []
    for msg in chat.messages:
        if isinstance(msg, Message):
            if msg.author.id not in user_ids:
                user_ids.append(msg.author.id)
                if len(user_ids) >= 2:
                    break

    if len(user_ids) == 2:

        return user_ids[0], user_ids[1]

    return None, None

def get_author_name_from_message_dict(
    msg_dict: Dict[str, Any], config: Dict[str, Any]
) -> str:
    """
    Extracts author name from message with consideration of configuration settings.

    This function replicates logic from ConversionContext.get_author_name()
    for working with domain objects.
    """
    profile = config.get("profile", "group")
    author_name = msg_dict.get("from", "")
    author_id = msg_dict.get("from_id", "")

    if profile == "personal":
        my_name = config.get("my_name", "Me")
        partner_name = config.get("partner_name", "Partner")

        if "me" in author_name.lower() or "i" in author_name.lower():
            return my_name
        else:
            return partner_name

    max_len = config.get("truncate_name_length", 20)
    if author_name and len(author_name) > max_len:
        return author_name[:max_len-3] + "..."
    return author_name if author_name else f"User_{author_id}"
