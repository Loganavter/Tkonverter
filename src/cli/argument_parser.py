"""
Argument parser for CLI.

Handles parsing of command line arguments for all CLI commands.
"""

import argparse
import sys
from typing import Any, Dict, List, Optional

class ArgumentParser:
    """Parses command line arguments for CLI commands."""
    
    def __init__(self):
        """Initialize argument parser."""
        self.parser = argparse.ArgumentParser(
            prog="tkonverter-cli",
            description="Tkonverter CLI - Convert and analyze Telegram chat exports",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Simple conversion
  tkonverter-cli convert -i result.json -o output.txt
  
  # Convert with custom settings
  tkonverter-cli convert -i result.json -o output.txt --profile personal --no-time
  
  # Convert with config file
  tkonverter-cli convert -i result.json -o output.txt --config config.json
  
  # Analyze tokens
  tkonverter-cli analyze -i result.json --tokenizer google/gemma-2b
  
  # Show file information
  tkonverter-cli info -i result.json
            """
        )
        
        # Global options
        self.parser.add_argument(
            "--debug", "-d",
            action="store_true",
            help="Enable debug logging"
        )
        self.parser.add_argument(
            "--version", "-v",
            action="version",
            version="Tkonverter CLI 1.0.0"
        )
        
        # Subcommands
        subparsers = self.parser.add_subparsers(
            dest="command",
            help="Available commands",
            required=True
        )
        
        # Convert command
        self._setup_convert_parser(subparsers)
        
        # Analyze command
        self._setup_analyze_parser(subparsers)
        
        # Info command
        self._setup_info_parser(subparsers)
    
    def _setup_convert_parser(self, subparsers):
        """Setup convert command parser."""
        convert_parser = subparsers.add_parser(
            "convert",
            help="Convert Telegram chat export to text format"
        )
        
        # Required arguments
        convert_parser.add_argument(
            "-i", "--input",
            required=True,
            help="Input JSON file path"
        )
        convert_parser.add_argument(
            "-o", "--output",
            required=True,
            help="Output text file path"
        )
        
        # Configuration options
        self._add_config_options(convert_parser)
        
        # Additional convert options
        convert_parser.add_argument(
            "--html-mode",
            action="store_true",
            help="Generate HTML output instead of plain text"
        )
        convert_parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Overwrite output file if it exists"
        )
    
    def _setup_analyze_parser(self, subparsers):
        """Setup analyze command parser."""
        analyze_parser = subparsers.add_parser(
            "analyze",
            help="Analyze chat statistics and token counts"
        )
        
        # Required arguments
        analyze_parser.add_argument(
            "-i", "--input",
            required=True,
            help="Input JSON file path"
        )
        
        # Analysis options
        analyze_parser.add_argument(
            "--tokenizer",
            help="Tokenizer model name (e.g., google/gemma-2b)"
        )
        analyze_parser.add_argument(
            "--chars-only",
            action="store_true",
            help="Analyze characters only (skip tokenization)"
        )
        analyze_parser.add_argument(
            "--output",
            help="Save analysis results to file"
        )
        
        # Configuration options
        self._add_config_options(analyze_parser)
        
        # Date filtering
        self._add_date_filter_options(analyze_parser)
    
    def _setup_info_parser(self, subparsers):
        """Setup info command parser."""
        info_parser = subparsers.add_parser(
            "info",
            help="Show information about chat export file"
        )
        
        # Required arguments
        info_parser.add_argument(
            "-i", "--input",
            required=True,
            help="Input JSON file path"
        )
        
        # Info options
        info_parser.add_argument(
            "--detailed",
            action="store_true",
            help="Show detailed parsing statistics"
        )
        info_parser.add_argument(
            "--validate-only",
            action="store_true",
            help="Only validate file without loading full chat"
        )
    
    def _add_config_options(self, parser):
        """Add configuration options to parser."""
        config_group = parser.add_argument_group("Configuration Options")
        
        # Profile
        config_group.add_argument(
            "--profile",
            choices=["group", "personal", "posts", "channel"],
            help="Chat profile type"
        )
        
        # Config file
        config_group.add_argument(
            "--config", "-c",
            help="Path to configuration file"
        )
        
        # Time options
        time_group = config_group.add_mutually_exclusive_group()
        time_group.add_argument(
            "--show-time",
            action="store_true",
            help="Show timestamps"
        )
        time_group.add_argument(
            "--no-time",
            action="store_true",
            help="Hide timestamps"
        )
        
        # Reaction options
        reaction_group = config_group.add_mutually_exclusive_group()
        reaction_group.add_argument(
            "--show-reactions",
            action="store_true",
            help="Show reactions"
        )
        reaction_group.add_argument(
            "--no-reactions",
            action="store_true",
            help="Hide reactions"
        )
        
        reaction_authors_group = config_group.add_mutually_exclusive_group()
        reaction_authors_group.add_argument(
            "--show-reaction-authors",
            action="store_true",
            help="Show reaction authors"
        )
        reaction_authors_group.add_argument(
            "--no-reaction-authors",
            action="store_true",
            help="Hide reaction authors"
        )
        
        # Optimization options
        optimization_group = config_group.add_mutually_exclusive_group()
        optimization_group.add_argument(
            "--show-optimization",
            action="store_true",
            help="Enable message optimization"
        )
        optimization_group.add_argument(
            "--no-optimization",
            action="store_true",
            help="Disable message optimization"
        )
        
        # Markdown options
        markdown_group = config_group.add_mutually_exclusive_group()
        markdown_group.add_argument(
            "--show-markdown",
            action="store_true",
            help="Show markdown formatting"
        )
        markdown_group.add_argument(
            "--no-markdown",
            action="store_true",
            help="Hide markdown formatting"
        )
        
        # Links options
        links_group = config_group.add_mutually_exclusive_group()
        links_group.add_argument(
            "--show-links",
            action="store_true",
            help="Show links"
        )
        links_group.add_argument(
            "--no-links",
            action="store_true",
            help="Hide links"
        )
        
        # Tech info options
        tech_group = config_group.add_mutually_exclusive_group()
        tech_group.add_argument(
            "--show-tech-info",
            action="store_true",
            help="Show technical information"
        )
        tech_group.add_argument(
            "--no-tech-info",
            action="store_true",
            help="Hide technical information"
        )
        
        # Service notifications options
        service_group = config_group.add_mutually_exclusive_group()
        service_group.add_argument(
            "--show-service-notifications",
            action="store_true",
            help="Show service notifications"
        )
        service_group.add_argument(
            "--no-service-notifications",
            action="store_true",
            help="Hide service notifications"
        )
        
        # Names
        config_group.add_argument(
            "--my-name",
            help="Your name in personal chats"
        )
        config_group.add_argument(
            "--partner-name",
            help="Partner name in personal chats"
        )
        config_group.add_argument(
            "--streak-break-time",
            help="Streak break time in HH:MM format"
        )
    
    def _add_date_filter_options(self, parser):
        """Add date filtering options to parser."""
        date_group = parser.add_argument_group("Date Filtering")
        
        date_group.add_argument(
            "--from-date",
            help="Start date (YYYY-MM-DD)"
        )
        date_group.add_argument(
            "--to-date",
            help="End date (YYYY-MM-DD)"
        )
        date_group.add_argument(
            "--exclude-dates",
            nargs="+",
            help="Dates to exclude (YYYY-MM-DD)"
        )
    
    def parse_args(self, args: Optional[List[str]] = None) -> argparse.Namespace:
        """
        Parse command line arguments.
        
        Args:
            args: Arguments to parse (default: sys.argv[1:])
            
        Returns:
            argparse.Namespace: Parsed arguments
        """
        if args is None:
            args = sys.argv[1:]
        
        return self.parser.parse_args(args)
    
    def get_help_text(self) -> str:
        """Get help text for the parser."""
        return self.parser.format_help()
    
    def get_command_help(self, command: str) -> str:
        """
        Get help text for specific command.
        
        Args:
            command: Command name
            
        Returns:
            str: Command help text
        """
        for action in self.parser._subparsers._actions:
            if hasattr(action, 'choices') and command in action.choices:
                return action.choices[command].format_help()
        return f"No help available for command: {command}"
    
    def validate_args(self, args: argparse.Namespace) -> List[str]:
        """
        Validate parsed arguments.
        
        Args:
            args: Parsed arguments
            
        Returns:
            List[str]: List of validation issues
        """
        issues = []
        
        # Check input file exists for commands that need it
        if hasattr(args, 'input') and args.input:
            import os
            if not os.path.exists(args.input):
                issues.append(f"Input file does not exist: {args.input}")
        
        # Check output file for convert command
        if args.command == "convert" and hasattr(args, 'output'):
            if not args.output:
                issues.append("Output file path is required for convert command")
            elif os.path.exists(args.output) and not getattr(args, 'overwrite', False):
                issues.append(f"Output file already exists: {args.output}. Use --overwrite to overwrite")
        
        # Validate date formats
        if hasattr(args, 'from_date') and args.from_date:
            if not self._validate_date_format(args.from_date):
                issues.append(f"Invalid from-date format: {args.from_date}. Use YYYY-MM-DD")
        
        if hasattr(args, 'to_date') and args.to_date:
            if not self._validate_date_format(args.to_date):
                issues.append(f"Invalid to-date format: {args.to_date}. Use YYYY-MM-DD")
        
        if hasattr(args, 'exclude_dates') and args.exclude_dates:
            for date in args.exclude_dates:
                if not self._validate_date_format(date):
                    issues.append(f"Invalid exclude-date format: {date}. Use YYYY-MM-DD")
        
        return issues
    
    def _validate_date_format(self, date_str: str) -> bool:
        """Validate date format YYYY-MM-DD."""
        import re
        pattern = r"^\d{4}-\d{2}-\d{2}$"
        if not re.match(pattern, date_str):
            return False
        
        try:
            from datetime import datetime
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False
