"""
Analyze command for CLI.

Analyzes chat statistics, token counts, and provides detailed analytics.
"""

import json
import os
import sys
from typing import Any, Dict, Optional, Set, Tuple

from src.cli.output_formatter import OutputFormatter
from src.cli.config_loader import ConfigLoader
from src.core.application.chat_service import ChatService, ChatLoadError
from src.core.application.analysis_service import AnalysisService
from src.core.application.tokenizer_service import TokenizerService, TokenizerError
from src.core.dependency_injection import setup_container

class AnalyzeCommand:
    """Command to analyze chat statistics and token counts."""
    
    def __init__(self):
        """Initialize analyze command."""
        self.formatter = OutputFormatter()
        self.config_loader = ConfigLoader()
        self.container = setup_container()
        self.chat_service = self.container.get(ChatService)
        self.analysis_service = self.container.get(AnalysisService)
        self.tokenizer_service = self.container.get(TokenizerService)
    
    def execute(self, args) -> int:
        """
        Execute analyze command.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            int: Exit code (0 for success, 1 for error)
        """
        try:
            input_file = args.input
            
            self.formatter.print_info(f"Analyzing {input_file}")
            
            # Load and merge configuration
            config = self._load_configuration(args)
            
            # Validate configuration
            validation_issues = self.config_loader.validate_config(config)
            if validation_issues:
                self.formatter.print_error("Configuration validation failed:")
                for issue in validation_issues:
                    self.formatter.print_error(f"  • {issue}")
                return 1
            
            # Load chat
            try:
                chat = self.chat_service.load_chat_from_file(input_file)
            except ChatLoadError as e:
                self.formatter.print_error(f"Failed to load chat: {e}")
                return 1
            
            # Show chat info
            chat_stats = self.chat_service.get_chat_statistics(chat)
            self.formatter.print_info(f"Loaded chat: {chat_stats.get('chat_name', 'Unknown')}")
            self.formatter.print_info(f"Messages: {chat_stats.get('total_messages', 0)}")
            
            # Prepare date filtering
            disabled_dates = self._prepare_date_filtering(args, chat)
            
            # Load tokenizer if requested
            tokenizer = None
            if args.tokenizer and not args.chars_only:
                tokenizer = self._load_tokenizer(args.tokenizer)
                if not tokenizer:
                    self.formatter.print_warning("Continuing with character analysis only")
            
            # Perform analysis
            if tokenizer and not args.chars_only:
                self.formatter.print_info("Performing token analysis...")
                analysis_result = self.analysis_service.calculate_token_stats(
                    chat=chat,
                    config=config,
                    tokenizer=tokenizer,
                    disabled_dates=disabled_dates
                )
            else:
                self.formatter.print_info("Performing character analysis...")
                analysis_result = self.analysis_service.calculate_character_stats(
                    chat=chat,
                    config=config,
                    disabled_dates=disabled_dates
                )
            
            # Show analysis results
            self.formatter.print_analysis_results(analysis_result)
            
            # Show detailed statistics
            self._show_detailed_statistics(chat, config, analysis_result)
            
            # Show date hierarchy if available
            if analysis_result.date_hierarchy:
                self._show_date_hierarchy(analysis_result.date_hierarchy)
            
            # Save results to file if requested
            if args.output:
                self._save_analysis_results(args.output, analysis_result, chat_stats)
            
            self.formatter.print_success("Analysis completed successfully!")
            return 0
            
        except Exception as e:
            self.formatter.print_error(f"Unexpected error: {e}")
            if args.debug:
                import traceback
                traceback.print_exc()
            return 1
    
    def _load_configuration(self, args) -> Dict[str, Any]:
        """
        Load and merge configuration from file and CLI arguments.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            Dict[str, Any]: Final configuration
        """
        # Convert args to dict for config loader
        args_dict = vars(args)
        
        config_path = getattr(args, 'config', None)
        
        try:
            config = self.config_loader.load_and_merge_config(config_path, args_dict)
            
            if args.debug:
                self.formatter.print_info("Configuration loaded:")
                for key, value in config.items():
                    self.formatter.print_info(f"  {key}: {value}")
            
            return config
            
        except Exception as e:
            self.formatter.print_error(f"Failed to load configuration: {e}")
            raise
    
    def _load_tokenizer(self, model_name: str):
        """
        Load tokenizer for analysis.
        
        Args:
            model_name: Name of the tokenizer model
            
        Returns:
            Tokenizer object or None if failed
        """
        try:
            self.formatter.print_info(f"Loading tokenizer: {model_name}")
            
            def progress_callback(message: str):
                self.formatter.print_info(f"  {message}")
            
            tokenizer = self.tokenizer_service.load_tokenizer(
                model_name=model_name,
                local_only=True,
                progress_callback=progress_callback
            )
            
            self.formatter.print_success(f"Tokenizer loaded successfully")
            
            # Show tokenizer info
            tokenizer_info = self.tokenizer_service.get_tokenizer_info()
            if tokenizer_info.get('vocab_size'):
                self.formatter.print_info(f"Vocabulary size: {tokenizer_info['vocab_size']:,}")
            if tokenizer_info.get('model_max_length'):
                self.formatter.print_info(f"Max length: {tokenizer_info['model_max_length']:,}")
            
            return tokenizer
            
        except TokenizerError as e:
            self.formatter.print_error(f"Failed to load tokenizer: {e}")
            return None
        except Exception as e:
            self.formatter.print_error(f"Unexpected error loading tokenizer: {e}")
            return None
    
    def _prepare_date_filtering(self, args, chat) -> Optional[Set[Tuple[str, str, str]]]:
        """
        Prepare date filtering based on CLI arguments.
        
        Args:
            args: Parsed command line arguments
            chat: Chat object
            
        Returns:
            Optional[Set[Tuple[str, str, str]]]: Set of disabled dates or None
        """
        disabled_dates = set()
        
        # Parse date range filters
        from_date = getattr(args, 'from_date', None)
        to_date = getattr(args, 'to_date', None)
        exclude_dates = getattr(args, 'exclude_dates', []) or []
        
        if from_date or to_date:
            # Filter messages by date range
            from datetime import datetime
            
            if from_date:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            else:
                from_dt = None
            
            if to_date:
                to_dt = datetime.strptime(to_date, "%Y-%m-%d")
            else:
                to_dt = None
            
            # Find dates to exclude based on range
            for msg in chat.messages:
                msg_date = msg.date.date()
                
                if from_dt and msg_date < from_dt.date():
                    year, month, day = str(msg_date.year), f"{msg_date.month:02d}", f"{msg_date.day:02d}"
                    disabled_dates.add((year, month, day))
                
                if to_dt and msg_date > to_dt.date():
                    year, month, day = str(msg_date.year), f"{msg_date.month:02d}", f"{msg_date.day:02d}"
                    disabled_dates.add((year, month, day))
        
        # Add explicitly excluded dates
        for date_str in exclude_dates:
            try:
                from datetime import datetime
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                year, month, day = str(date_obj.year), f"{date_obj.month:02d}", f"{date_obj.day:02d}"
                disabled_dates.add((year, month, day))
            except ValueError:
                self.formatter.print_warning(f"Invalid date format: {date_str}")
        
        if disabled_dates:
            self.formatter.print_info(f"Date filtering: {len(disabled_dates)} dates excluded")
        
        return disabled_dates if disabled_dates else None
    
    def _show_detailed_statistics(self, chat, config: Dict[str, Any], analysis_result):
        """Show detailed analysis statistics."""
        print()
        self.formatter.print_bold("📊 Detailed Statistics")
        print("=" * 40)
        
        # User activity
        user_stats = self.analysis_service.calculate_user_activity(chat)
        if user_stats:
            print()
            print("Top 10 Most Active Users:")
            print("-" * 30)
            
            # Sort by message count
            sorted_users = sorted(user_stats.items(), 
                                key=lambda x: x[1]['message_count'], 
                                reverse=True)
            
            headers = ["User", "Messages", "Characters", "Reactions"]
            rows = []
            
            for user_id, stats in sorted_users[:10]:
                rows.append([
                    stats['name'],
                    str(stats['message_count']),
                    str(stats['character_count']),
                    str(stats['reaction_count'])
                ])
            
            self.formatter.print_table(headers, rows)
        
        # Daily activity
        daily_activity = self.analysis_service.get_daily_activity(chat)
        if daily_activity:
            print()
            print("Daily Activity (Top 10 Days):")
            print("-" * 30)
            
            # Sort by message count
            sorted_days = sorted(daily_activity.items(), 
                               key=lambda x: x[1], reverse=True)
            
            headers = ["Date", "Messages"]
            rows = [[date, str(count)] for date, count in sorted_days[:10]]
            
            self.formatter.print_table(headers, rows)
        
        # Hourly activity
        hourly_activity = self.analysis_service.get_hourly_activity(chat)
        if hourly_activity:
            print()
            print("Hourly Activity:")
            print("-" * 20)
            
            # Find peak hours
            peak_hours = sorted(hourly_activity.items(), 
                              key=lambda x: x[1], reverse=True)[:5]
            
            for hour, count in peak_hours:
                print(f"{hour:02d}:00 - {count} messages")
    
    def _show_date_hierarchy(self, date_hierarchy: Dict[str, Dict[str, Dict[str, float]]]):
        """Show date hierarchy statistics."""
        print()
        self.formatter.print_bold("📅 Date Hierarchy")
        print("=" * 30)
        
        # Show yearly totals
        yearly_totals = {}
        for year, months in date_hierarchy.items():
            year_total = sum(
                sum(days.values()) for days in months.values()
            )
            yearly_totals[year] = year_total
        
        if yearly_totals:
            print("Yearly Totals:")
            print("-" * 20)
            
            sorted_years = sorted(yearly_totals.items(), 
                                key=lambda x: x[1], reverse=True)
            
            for year, total in sorted_years:
                print(f"{year}: {total:,.0f}")
        
        # Show monthly totals for most active year
        if yearly_totals:
            most_active_year = max(yearly_totals.items(), key=lambda x: x[1])[0]
            months = date_hierarchy.get(most_active_year, {})
            
            if months:
                print()
                print(f"Monthly Totals ({most_active_year}):")
                print("-" * 25)
                
                monthly_totals = {}
                for month, days in months.items():
                    month_total = sum(days.values())
                    monthly_totals[month] = month_total
                
                sorted_months = sorted(monthly_totals.items(), 
                                     key=lambda x: x[1], reverse=True)
                
                for month, total in sorted_months:
                    month_name = self._get_month_name(month)
                    print(f"{month_name}: {total:,.0f}")
    
    def _get_month_name(self, month_str: str) -> str:
        """Get month name from month string."""
        month_names = {
            "01": "January", "02": "February", "03": "March", "04": "April",
            "05": "May", "06": "June", "07": "July", "08": "August",
            "09": "September", "10": "October", "11": "November", "12": "December"
        }
        return month_names.get(month_str, month_str)
    
    def _save_analysis_results(self, output_file: str, analysis_result, chat_stats: Dict[str, Any]):
        """Save analysis results to JSON file."""
        try:
            self.formatter.print_info(f"Saving analysis results to {output_file}")
            
            # Prepare results data
            results_data = {
                "analysis": {
                    "total_count": analysis_result.total_count,
                    "unit": analysis_result.unit,
                    "total_characters": analysis_result.total_characters,
                    "average_message_length": analysis_result.average_message_length,
                    "most_active_user": analysis_result.most_active_user.name if analysis_result.most_active_user else None,
                    "created_at": analysis_result.created_at.isoformat(),
                },
                "chat_info": chat_stats,
                "date_hierarchy": analysis_result.date_hierarchy,
            }
            
            # Add tokenizer info if available
            if self.tokenizer_service.has_tokenizer_loaded():
                tokenizer_info = self.tokenizer_service.get_tokenizer_info()
                results_data["tokenizer"] = tokenizer_info
            
            # Save to file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results_data, f, indent=2, ensure_ascii=False)
            
            self.formatter.print_success(f"Analysis results saved to {output_file}")
            
        except Exception as e:
            self.formatter.print_error(f"Failed to save analysis results: {e}")
