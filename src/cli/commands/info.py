"""
Info command for CLI.

Shows information about chat export file without full conversion.
"""

import sys
from typing import Any, Dict

from src.cli.output_formatter import OutputFormatter
from src.core.application.chat_service import ChatService, ChatLoadError
from src.core.dependency_injection import setup_container

class InfoCommand:
    """Command to show information about chat export file."""
    
    def __init__(self):
        """Initialize info command."""
        self.formatter = OutputFormatter()
        self.container = setup_container()
        self.chat_service = self.container.get(ChatService)
    
    def execute(self, args) -> int:
        """
        Execute info command.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            int: Exit code (0 for success, 1 for error)
        """
        try:
            input_file = args.input
            
            self.formatter.print_info(f"Analyzing file: {input_file}")
            
            # Validate file without full loading
            validation_result = self.chat_service.validate_file_before_load(input_file)
            
            if validation_result is None:
                self.formatter.print_error("Failed to validate file")
                return 1
            
            if args.validate_only:
                # Only show validation results
                self.formatter.print_file_validation(validation_result)
                return 0 if validation_result.get("is_valid", False) else 1
            
            if not validation_result.get("is_valid", False):
                self.formatter.print_error("File validation failed. Cannot load chat.")
                self.formatter.print_file_validation(validation_result)
                return 1
            
            # Load chat for detailed information
            try:
                chat = self.chat_service.load_chat_from_file(input_file)
            except ChatLoadError as e:
                self.formatter.print_error(f"Failed to load chat: {e}")
                return 1
            
            # Get chat statistics
            chat_stats = self.chat_service.get_chat_statistics(chat)
            
            # Show validation results
            self.formatter.print_file_validation(validation_result)
            
            # Show chat information
            self.formatter.print_chat_info(chat_stats)
            
            # Show detailed parsing statistics if requested
            if args.detailed:
                parsing_stats = validation_result.get('parsing_stats', {})
                if parsing_stats:
                    self.formatter.print_bold("📊 Detailed Parsing Statistics")
                    print("=" * 40)
                    for key, value in parsing_stats.items():
                        print(f"{key:<25}: {value}")
                    print()
            
            # Show user activity details
            if args.detailed:
                try:
                    user_stats = self.chat_service.get_user_activity_stats(chat)
                    if user_stats and isinstance(user_stats, dict):
                        self.formatter.print_bold("👥 Detailed User Activity")
                        print("=" * 40)
                        
                        # Sort users by message count
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
            
            # Show daily activity if detailed
            if args.detailed:
                try:
                    daily_activity = self.chat_service.get_daily_activity(chat)
                    if daily_activity and isinstance(daily_activity, dict):
                        self.formatter.print_bold("📅 Daily Activity (Top 10 Days)")
                        print("=" * 30)
                        
                        # Sort by message count
                        sorted_days = sorted(daily_activity.items(), 
                                           key=lambda x: x[1], reverse=True)
                        
                        headers = ["Date", "Messages"]
                        rows = [[date, str(count)] for date, count in sorted_days[:10]]
                        
                        self.formatter.print_table(headers, rows)
                except Exception as e:
                    self.formatter.print_warning(f"Could not load daily activity: {e}")
            
            self.formatter.print_success("File analysis completed successfully!")
            return 0
            
        except Exception as e:
            self.formatter.print_error(f"Unexpected error: {e}")
            if args.debug:
                import traceback
                traceback.print_exc()
            return 1
