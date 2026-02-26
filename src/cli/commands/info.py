

import sys
from typing import Any, Dict

from src.cli.output_formatter import OutputFormatter
from src.core.application.chat_service import ChatService, ChatLoadError
from src.core.application.statistics_service import StatisticsService

class InfoCommand:

    def __init__(
        self,
        formatter: OutputFormatter | None = None,
        chat_service: ChatService | None = None,
        stats_service: StatisticsService | None = None,
    ):
        """Initialize info command with explicit dependencies."""
        self.formatter = formatter or OutputFormatter()
        if chat_service is None:
            raise ValueError("InfoCommand requires chat_service dependency")
        if stats_service is None:
            raise ValueError("InfoCommand requires stats_service dependency")

        self.chat_service = chat_service
        self.stats_service = stats_service

    def execute(self, args) -> int:
        try:
            input_file = args.input

            self.formatter.print_info(f"Analyzing file: {input_file}")

            validation_result = self.chat_service.validate_file_before_load(input_file)

            if validation_result is None:
                self.formatter.print_error("Failed to validate file")
                return 1

            if args.validate_only:

                self.formatter.print_file_validation(validation_result)
                return 0 if validation_result.get("is_valid", False) else 1

            if not validation_result.get("is_valid", False):
                self.formatter.print_error("File validation failed. Cannot load chat.")
                self.formatter.print_file_validation(validation_result)
                return 1

            try:
                chat = self.chat_service.load_chat_from_file(input_file)
            except ChatLoadError as e:
                self.formatter.print_error(f"Failed to load chat: {e}")
                return 1

            chat_stats = self.chat_service.get_chat_statistics(chat)

            self.formatter.print_file_validation(validation_result)

            self.formatter.print_chat_info(chat_stats)

            if args.detailed:
                parsing_stats = validation_result.get('parsing_stats', {})
                if parsing_stats:
                    self.formatter.print_bold("📊 Detailed Parsing Statistics")
                    print("=" * 40)
                    for key, value in parsing_stats.items():
                        print(f"{key:<25}: {value}")
                    print()

            if args.detailed:
                try:
                    user_stats = self.chat_service.get_user_activity_stats(chat)
                    if user_stats and isinstance(user_stats, dict):
                        self.formatter.print_bold("👥 Detailed User Activity")
                        print("=" * 40)

                        sorted_users = sorted(user_stats.items(),
                                            key=lambda x: x[1]['message_count'],
                                            reverse=True)

                        headers = ["User", "Messages", "Characters", "Reactions", "First Message", "Last Message"]
                        rows = []

                        for user_id, stats in sorted_users:
                            first_msg = stats.get('first_message')
                            last_msg = stats.get('last_message')

                            first_str = first_msg.strftime("%Y-%m-%d") if first_msg else "N/A"
                            last_str = last_msg.strftime("%Y-%m-%d") if last_msg else "N/A"

                            rows.append([
                                stats['name'],
                                str(stats['message_count']),
                                str(stats['character_count']),
                                str(stats['reaction_count']),
                                first_str,
                                last_str
                            ])

                        self.formatter.print_table(headers, rows)
                except Exception as e:
                    self.formatter.print_warning(f"Could not load user activity stats: {e}")

            if args.detailed:
                try:
                    daily_activity = self.chat_service.get_daily_activity(chat)
                    if daily_activity and isinstance(daily_activity, dict):
                        self.formatter.print_bold("📅 Daily Activity (Top 10 Days)")
                        print("=" * 30)

                        sorted_days = sorted(daily_activity.items(),
                                           key=lambda x: x[1], reverse=True)

                        headers = ["Date", "Messages"]
                        rows = [[date, str(count)] for date, count in sorted_days[:10]]

                        self.formatter.print_table(headers, rows)
                except Exception as e:
                    self.formatter.print_warning(f"Could not load daily activity: {e}")

            if args.detailed:
                try:
                    stats = self.stats_service.calculate_stats(chat)
                    self.formatter.print_bold("🧠 Communication Analysis")
                    print("=" * 40)
                    print(f"Total Sessions: {stats.total_sessions}")
                    print(f"Avg Session Duration: {stats.avg_session_duration_minutes:.1f} min")
                    print(f"Engagement Score: {stats.engagement_score} / 100 (Objective Index)")

                    if stats.longest_session:
                        ls = stats.longest_session
                        print(f"Longest Session: {ls.duration_minutes:.1f} min on {ls.start_time.date()}")
                        print(f"  - Messages: {ls.message_count}")
                        print(f"  - Characters: {ls.char_count}")
                except Exception as e:
                    self.formatter.print_warning(f"Could not load communication analysis: {e}")

            self.formatter.print_success("File analysis completed successfully!")
            return 0

        except Exception as e:
            self.formatter.print_error(f"Unexpected error: {e}")
            if args.debug:
                import traceback
                traceback.print_exc()
            return 1
