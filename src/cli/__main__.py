"""
Main entry point for CLI.

Handles command routing and global error handling.
"""

import sys
import logging
from typing import Optional

from src.cli.argument_parser import ArgumentParser
from src.cli.output_formatter import OutputFormatter
from src.cli.commands.info import InfoCommand
from src.cli.commands.convert import ConvertCommand
from src.cli.commands.analyze import AnalyzeCommand

def setup_logging(debug: bool = False):
    """
    Setup logging configuration.

    Args:
        debug: Whether to enable debug logging
    """
    level = logging.DEBUG if debug else logging.WARNING

    logging.basicConfig(
        level=level,
        format='%(asctime)s - [%(levelname)s] - (%(filename)s:%(lineno)d) - %(message)s',
        stream=sys.stderr
    )

    logging.getLogger("markdown").setLevel(logging.CRITICAL)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

def main(args: Optional[list] = None) -> int:
    """
    Main CLI entry point.

    Args:
        args: Command line arguments (default: sys.argv[1:])

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    try:

        parser = ArgumentParser()
        parsed_args = parser.parse_args(args)

        setup_logging(parsed_args.debug)

        validation_issues = parser.validate_args(parsed_args)
        if validation_issues:
            formatter = OutputFormatter()
            formatter.print_error("Argument validation failed:")
            for issue in validation_issues:
                formatter.print_error(f"  • {issue}")
            return 1

        command = parsed_args.command

        if command == "info":
            info_cmd = InfoCommand()
            return info_cmd.execute(parsed_args)

        elif command == "convert":
            convert_cmd = ConvertCommand()
            return convert_cmd.execute(parsed_args)

        elif command == "analyze":
            analyze_cmd = AnalyzeCommand()
            return analyze_cmd.execute(parsed_args)

        else:
            formatter = OutputFormatter()
            formatter.print_error(f"Unknown command: {command}")
            formatter.print_info("Available commands: info, convert, analyze")
            return 1

    except KeyboardInterrupt:
        formatter = OutputFormatter()
        formatter.print_warning("\nOperation cancelled by user")
        return 130

    except Exception as e:
        formatter = OutputFormatter()
        formatter.print_error(f"Unexpected error: {e}")

        if "--debug" in (args or sys.argv[1:]):
            import traceback
            traceback.print_exc()

        return 1

if __name__ == "__main__":
    sys.exit(main())
