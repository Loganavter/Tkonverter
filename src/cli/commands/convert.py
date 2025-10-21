"""
Convert command for CLI.

Converts Telegram chat export to text format.
"""

import os
import sys
from typing import Any, Dict, Optional, Set, Tuple

from src.cli.output_formatter import OutputFormatter
from src.cli.config_loader import ConfigLoader
from src.core.application.chat_service import ChatService, ChatLoadError
from src.core.application.conversion_service import ConversionService
from src.core.dependency_injection import setup_container

class ConvertCommand:
    """Command to convert chat export to text format."""
    
    def __init__(self):
        """Initialize convert command."""
        self.formatter = OutputFormatter()
        self.config_loader = ConfigLoader()
        self.container = setup_container()
        self.chat_service = self.container.get(ChatService)
        self.conversion_service = self.container.get(ConversionService)
    
    def execute(self, args) -> int:
        """
        Execute convert command.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            int: Exit code (0 for success, 1 for error)
        """
        try:
            input_file = args.input
            output_file = args.output
            
            self.formatter.print_info(f"Converting {input_file} to {output_file}")
            
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
            disabled_nodes = self._prepare_date_filtering(args, chat)
            
            # Convert chat to text
            self.formatter.print_info("Converting chat to text...")
            
            html_mode = getattr(args, 'html_mode', False)
            converted_text = self.conversion_service.convert_to_text(
                chat=chat,
                config=config,
                html_mode=html_mode,
                disabled_nodes=disabled_nodes
            )
            
            if not converted_text.strip():
                self.formatter.print_warning("Conversion resulted in empty text")
            
            # Save to file
            self.formatter.print_info(f"Saving to {output_file}...")
            
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(converted_text)
            except IOError as e:
                self.formatter.print_error(f"Failed to save output file: {e}")
                return 1
            
            # Show results
            file_size = os.path.getsize(output_file)
            char_count = len(converted_text)
            
            self.formatter.print_success("Conversion completed successfully!")
            self.formatter.print_info(f"Output file: {output_file}")
            self.formatter.print_info(f"File size: {file_size:,} bytes")
            self.formatter.print_info(f"Character count: {char_count:,}")
            
            if html_mode:
                self.formatter.print_info("Output format: HTML")
            else:
                self.formatter.print_info("Output format: Plain text")
            
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
    
    def _prepare_date_filtering(self, args, chat) -> Optional[Set]:
        """
        Prepare date filtering based on CLI arguments.
        
        Args:
            args: Parsed command line arguments
            chat: Chat object
            
        Returns:
            Optional[Set]: Set of disabled TreeNode objects or None
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
        
        if not disabled_dates:
            return None
        
        # Convert to TreeNode objects
        try:
            from src.core.analysis.tree_analyzer import TreeNode
            from src.core.analysis.tree_identity import TreeNodeIdentity
            
            disabled_nodes = set()
            for year, month, day in disabled_dates:
                node_id = TreeNodeIdentity.date_to_day_id(year, month, day)
                node = TreeNode(f"{day}-{month}-{year}", 0, node_id=node_id)
                disabled_nodes.add(node)
            
            if disabled_nodes:
                self.formatter.print_info(f"Date filtering: {len(disabled_nodes)} dates excluded")
            
            return disabled_nodes
            
        except ImportError:
            self.formatter.print_warning("Could not apply date filtering (analysis module not available)")
            return None
