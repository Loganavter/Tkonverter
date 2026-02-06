from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict

@dataclass
class ChatSession:
    """
    Сессия общения — непрерывный поток сообщений.
    Новая сессия начинается, если пауза между сообщениями превышает порог (например, 20 минут).
    """
    start_time: datetime
    end_time: datetime
    message_count: int
    char_count: int
    authors: Dict[str, int]

    @property
    def duration(self) -> timedelta:
        return self.end_time - self.start_time

    @property
    def duration_minutes(self) -> float:
        return self.duration.total_seconds() / 60.0

    @property
    def density(self) -> float:
        """Символов в минуту"""
        if self.duration_minutes == 0:
            return 0.0
        return self.char_count / self.duration_minutes

@dataclass
class GlobalStats:
    total_sessions: int
    avg_session_duration_minutes: float
    longest_session: ChatSession

    engagement_score: float
    sessions_by_date: Dict[str, List[ChatSession]]
