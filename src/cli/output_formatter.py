"""
Output formatter for CLI.

Provides formatted output for console display including tables,
progress bars, and colored text.
"""

import sys
from typing import Any, Dict, List, Optional

try:
    import colorama
    from colorama import Fore, Style
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False
    # Create dummy color objects
    class DummyColor:
        RED = GREEN = YELLOW = CYAN = BLUE = MAGENTA = WHITE = ""
    Fore = DummyColor()
    Style = DummyColor()

class OutputFormatter:
    """Formats output for console display."""
    
    def __init__(self, use_colors: bool = True):
        """
        Initialize formatter.
        
        Args:
            use_colors: Whether to use colored output
        """
        self.use_colors = use_colors and COLORAMA_AVAILABLE
        if self.use_colors:
            colorama.init(autoreset=True)
    
    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled."""
        if self.use_colors and color:
            return f"{color}{text}{Style.RESET_ALL}"
        return text
    
    def success(self, text: str) -> str:
        """Format success message."""
        return self._colorize(text, Fore.GREEN)
    
    def error(self, text: str) -> str:
        """Format error message."""
        return self._colorize(text, Fore.RED)
    
    def warning(self, text: str) -> str:
        """Format warning message."""
        return self._colorize(text, Fore.YELLOW)
    
    def info(self, text: str) -> str:
        """Format info message."""
        return self._colorize(text, Fore.CYAN)
    
    def bold(self, text: str) -> str:
        """Format bold text."""
        if self.use_colors:
            return f"{Style.BRIGHT}{text}{Style.RESET_ALL}"
        return text
    
    def print_success(self, text: str):
        """Print success message."""
        print(self.success(text))
    
    def print_error(self, text: str):
        """Print error message."""
        print(self.error(text), file=sys.stderr)
    
    def print_warning(self, text: str):
        """Print warning message."""
        print(self.warning(text))
    
    def print_info(self, text: str):
        """Print info message."""
        print(self.info(text))
    
    def print_bold(self, text: str):
        """Print bold text."""
        print(self.bold(text))
    
    def print_table(self, headers: List[str], rows: List[List[str]], 
                   title: Optional[str] = None) -> None:
        """
        Print formatted table.
        
        Args:
            headers: Table headers
            rows: Table rows
            title: Optional table title
        """
        if title:
            print()
            print(self.bold(title))
            print()
        
        if not headers or not rows:
            print("No data to display")
            return
        
        # Calculate column widths
        col_widths = [len(header) for header in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # Print header
        header_line = " | ".join(header.ljust(col_widths[i]) 
                               for i, header in enumerate(headers))
        print(self.bold(header_line))
        
        # Print separator
        separator = "-" * len(header_line)
        print(separator)
        
        # Print rows
        for row in rows:
            row_line = " | ".join(str(cell).ljust(col_widths[i]) 
                                for i, cell in enumerate(row))
            print(row_line)
        print()
    
    def print_progress(self, current: int, total: int, 
                      message: str = "Processing...") -> None:
        """
        Print progress bar.
        
        Args:
            current: Current progress
            total: Total items
            message: Progress message
        """
        if total == 0:
            return
        
        percent = (current / total) * 100
        bar_length = 30
        filled_length = int(bar_length * current // total)
        
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        
        print(f"\r{message} |{bar}| {percent:.1f}% ({current}/{total})", 
              end="", flush=True)
        
        if current == total:
            print()  # New line when complete
    
    def print_chat_info(self, chat_stats: Dict[str, Any]) -> None:
        """
        Print chat information in formatted table.
        
        Args:
            chat_stats: Chat statistics dictionary
        """
        print()
        print(self.bold("📊 Chat Information"))
        print("=" * 50)
        
        # Basic info
        basic_info = [
            ["Chat Name", chat_stats.get("chat_name", "Unknown")],
            ["Chat Type", chat_stats.get("chat_type", "Unknown")],
            ["Total Messages", str(chat_stats.get("total_messages", 0))],
            ["Regular Messages", str(chat_stats.get("regular_messages", 0))],
            ["Service Messages", str(chat_stats.get("service_messages", 0))],
            ["Unique Users", str(chat_stats.get("unique_users", 0))],
        ]
        
        if chat_stats.get("most_active_user"):
            basic_info.append(["Most Active User", chat_stats["most_active_user"]])
        
        # Date range
        date_range = chat_stats.get("date_range")
        if date_range:
            if date_range.get("start") and date_range.get("end"):
                basic_info.append(["Date Range", 
                                 f"{date_range['start']} - {date_range['end']}"])
            if date_range.get("duration_days") is not None:
                basic_info.append(["Duration", f"{date_range['duration_days']} days"])
        
        # Print basic info
        for label, value in basic_info:
            print(f"{label:<20}: {value}")
        
        # User activity
        user_counts = chat_stats.get("user_message_counts", {})
        if user_counts:
            print()
            print(self.bold("👥 User Activity"))
            print("-" * 30)
            
            # Sort by message count
            sorted_users = sorted(user_counts.items(), 
                                key=lambda x: x[1], reverse=True)
            
            for user_name, count in sorted_users[:10]:  # Top 10 users
                print(f"{user_name:<25}: {count} messages")
            
            if len(sorted_users) > 10:
                print(f"... and {len(sorted_users) - 10} more users")
        
        print()
    
    def print_analysis_results(self, analysis_result) -> None:
        """
        Print analysis results in formatted table.
        
        Args:
            analysis_result: Analysis result object
        """
        print()
        print(self.bold("📈 Analysis Results"))
        print("=" * 50)
        
        # Basic stats
        print(f"Total {analysis_result.unit}: "
              f"{analysis_result.total_count:,}")
        
        if analysis_result.total_characters:
            print(f"Total Characters: {analysis_result.total_characters:,}")
        
        if analysis_result.average_message_length:
            print(f"Average Message Length: "
                  f"{analysis_result.average_message_length:.1f} characters")
        
        if analysis_result.most_active_user:
            print(f"Most Active User: {analysis_result.most_active_user.name}")
        
        print()
    
    def print_file_validation(self, validation_result: Dict[str, Any]) -> None:
        """
        Print file validation results.
        
        Args:
            validation_result: Validation result dictionary
        """
        print()
        print(self.bold("📁 File Validation"))
        print("=" * 30)
        
        if validation_result.get("is_valid"):
            self.print_success("✅ File is valid")
        else:
            self.print_error("❌ File validation failed")
        
        print(f"File exists: {validation_result.get('file_exists', False)}")
        print(f"File size: {validation_result.get('file_size', 0):,} bytes")
        print(f"Is JSON: {validation_result.get('is_json', False)}")
        
        issues = validation_result.get('issues', [])
        if issues:
            print()
            print(self.warning("Issues found:"))
            for issue in issues:
                print(f"  • {issue}")
        
        parsing_stats = validation_result.get('parsing_stats', {})
        if parsing_stats:
            print()
            print(self.bold("Parsing Statistics:"))
            for key, value in parsing_stats.items():
                print(f"  {key}: {value}")
        
        print()
