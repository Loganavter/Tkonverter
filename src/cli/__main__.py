

import sys
import logging
from typing import Optional

from src.cli.argument_parser import ArgumentParser
from src.cli.output_formatter import OutputFormatter
from src.cli.commands.info import InfoCommand
from src.cli.commands.convert import ConvertCommand
from src.cli.commands.analyze import AnalyzeCommand
from src.core.application.analysis_service import AnalysisService
from src.core.application.chat_service import ChatService
from src.core.application.conversion_service import ConversionService
from src.core.application.statistics_service import StatisticsService
from src.core.application.tokenizer_service import TokenizerService
from src.core.dependency_injection import setup_container

def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.WARNING

    logging.basicConfig(
        level=level,
        format='%(asctime)s - [%(levelname)s] - (%(filename)s:%(lineno)d) - %(message)s',
        stream=sys.stderr
    )

    logging.getLogger("markdown").setLevel(logging.CRITICAL)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

def main(args: Optional[list] = None) -> int:
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
        container = setup_container()
        chat_service = container.get(ChatService)
        stats_service = container.get(StatisticsService)
        conversion_service = container.get(ConversionService)
        analysis_service = container.get(AnalysisService)
        tokenizer_service = container.get(TokenizerService)

        if command == "info":
            info_cmd = InfoCommand(
                chat_service=chat_service,
                stats_service=stats_service,
            )
            return info_cmd.execute(parsed_args)

        elif command == "convert":
            convert_cmd = ConvertCommand(
                chat_service=chat_service,
                conversion_service=conversion_service,
            )
            return convert_cmd.execute(parsed_args)

        elif command == "analyze":
            analyze_cmd = AnalyzeCommand(
                chat_service=chat_service,
                analysis_service=analysis_service,
                tokenizer_service=tokenizer_service,
            )
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
