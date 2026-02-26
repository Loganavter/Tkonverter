

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

@dataclass
class TodoListItem:
    text: Union[str, List[Dict[str, Any]]]
    id: int

@dataclass
class TodoList:
    title: Union[str, List[Dict[str, Any]]]
    items: List[TodoListItem] = field(default_factory=list)

@dataclass
class PaidMedia:
    paid_stars_amount: int

@dataclass
class GiveawayInfo:
    quantity: int
    months: int
    until_date: datetime
    channels: List[int] = field(default_factory=list)
    countries: List[str] = field(default_factory=list)
    additional_prize: Optional[str] = None

@dataclass
class GiveawayResultsInfo:
    winners_count: int
    unclaimed_count: int
    months: int
    launch_message_id: int

@dataclass
class User:

    id: str
    name: str

    def __post_init__(self):
        if not self.id:
            raise ValueError("User ID cannot be empty")
        if not self.name:
            raise ValueError("User name cannot be empty")

@dataclass
class Reaction:

    emoji: str
    count: int
    authors: List[User] = field(default_factory=list)

    def __post_init__(self):
        if self.count < 0:
            raise ValueError("Reaction count cannot be negative")

@dataclass
class MediaInfo:

    media_type: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    duration_seconds: Optional[int] = None
    sticker_emoji: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

@dataclass
class Message:

    id: int
    author: User
    date: datetime
    text: Union[str, List[Dict[str, Any]]]
    reactions: List[Reaction] = field(default_factory=list)
    reply_to_id: Optional[int] = None
    edited: Optional[datetime] = None
    media: Optional[MediaInfo] = None
    forwarded_from: Optional[str] = None
    raw_media: Optional[Dict[str, Any]] = field(default_factory=dict)
    media_spoiler: bool = False
    giveaway_info: Optional[GiveawayInfo] = None
    giveaway_results_info: Optional[GiveawayResultsInfo] = None
    showForwardedAsOriginal: bool = False
    todo_list: Optional[TodoList] = None
    paid_media: Optional[PaidMedia] = None
    raw_inline_buttons: Optional[List[Any]] = field(default_factory=list)

    def __post_init__(self):
        pass

    @property
    def is_edited(self) -> bool:
        return self.edited is not None

    @property
    def has_media(self) -> bool:
        return self.media is not None

    @property
    def has_reactions(self) -> bool:
        return len(self.reactions) > 0

@dataclass
class ServiceMessage:

    id: int
    date: datetime
    action: str
    actor: Optional[str] = None
    title: Optional[str] = None
    members: List[str] = field(default_factory=list)
    period_seconds: Optional[int] = None
    media: Optional[MediaInfo] = None
    extra_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):

        if not self.action:
            raise ValueError("Service message action cannot be empty")

@dataclass
class Chat:

    name: str
    type: str
    messages: List[Union[Message, ServiceMessage]]
    chat_id: Optional[int] = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("Chat name cannot be empty")
        if self.type not in ["group", "personal", "posts", "channel"]:
            raise ValueError(f"Unknown chat type: {self.type}")

    @property
    def message_count(self) -> int:
        return sum(1 for msg in self.messages if isinstance(msg, Message))

    @property
    def service_message_count(self) -> int:
        return sum(1 for msg in self.messages if isinstance(msg, ServiceMessage))

    @property
    def total_message_count(self) -> int:
        return len(self.messages)

    def get_users(self) -> List[User]:
        users = {}
        for msg in self.messages:
            if isinstance(msg, Message):
                users[msg.author.id] = msg.author
        return list(users.values())

    def get_messages_by_user(self, user_id: str) -> List[Message]:
        return [
            msg
            for msg in self.messages
            if isinstance(msg, Message) and msg.author.id == user_id
        ]

    def get_date_range(self) -> tuple[datetime, datetime]:
        if not self.messages:
            raise ValueError("Chat contains no messages")

        dates = [msg.date for msg in self.messages]
        return min(dates), max(dates)

@dataclass
class AnalysisResult:

    total_count: int
    unit: str
    date_hierarchy: Dict[str, Dict[str, Dict[str, float]]]
    total_characters: Optional[int] = None
    average_message_length: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.total_count < 0:
            raise ValueError("Total count cannot be negative")
        if self.unit not in ["chars", "Characters", "tokens"]:
            raise ValueError(f"Unknown unit: {self.unit}")
