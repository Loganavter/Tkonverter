from typing import List, Union
from collections import defaultdict
from datetime import timedelta

from src.core.domain.models import Chat, Message
from src.core.domain.statistics import ChatSession, GlobalStats

class StatisticsService:

    SESSION_GAP_MINUTES = 20

    def calculate_stats(self, chat: Chat) -> GlobalStats:
        messages = [m for m in chat.messages if isinstance(m, Message)]
        if not messages:
            return self._empty_stats()

        sessions: List[ChatSession] = []
        current_msgs: List[Message] = [messages[0]]

        for i in range(1, len(messages)):
            prev_msg = messages[i-1]
            curr_msg = messages[i]

            time_diff = curr_msg.date - prev_msg.date

            if time_diff.total_seconds() / 60 > self.SESSION_GAP_MINUTES:

                sessions.append(self._create_session(current_msgs))
                current_msgs = [curr_msg]
            else:
                current_msgs.append(curr_msg)

        if current_msgs:
            sessions.append(self._create_session(current_msgs))

        return self._aggregate_stats(sessions)

    def _create_session(self, msgs: List[Message]) -> ChatSession:
        start = msgs[0].date
        end = msgs[-1].date
        chars = sum(len(str(m.text)) for m in msgs)

        authors = defaultdict(int)
        for m in msgs:
            authors[m.author.id] += 1

        return ChatSession(
            start_time=start,
            end_time=end,
            message_count=len(msgs),
            char_count=chars,
            authors=dict(authors)
        )

    def _aggregate_stats(self, sessions: List[ChatSession]) -> GlobalStats:
        total_sessions = len(sessions)
        if total_sessions == 0:
            return self._empty_stats()

        total_duration = sum(s.duration_minutes for s in sessions)
        avg_duration = total_duration / total_sessions

        longest = max(sessions, key=lambda s: s.duration_minutes)

        by_date = defaultdict(list)
        for s in sessions:
            date_key = s.start_time.strftime("%Y-%m-%d")
            by_date[date_key].append(s)

        total_chars = sum(s.char_count for s in sessions)
        global_density = total_chars / total_duration if total_duration > 0 else 0

        reciprocity = 1.0
        if len(longest.authors) == 2:
            user_counts = list(longest.authors.values())
            total_msgs = sum(user_counts)
            diff = abs(user_counts[0] - user_counts[1])
            reciprocity = 1.0 - (diff / total_msgs) if total_msgs > 0 else 0

        duration_score = min(avg_duration, 60) * 1.0
        velocity_score = global_density * 0.05
        reciprocity_score = reciprocity * 20

        score = duration_score + velocity_score + reciprocity_score

        return GlobalStats(
            total_sessions=total_sessions,
            avg_session_duration_minutes=avg_duration,
            longest_session=longest,
            engagement_score=round(score, 2),
            sessions_by_date=dict(by_date)
        )

    def _empty_stats(self):

        return GlobalStats(0, 0.0, None, 0.0, {})
