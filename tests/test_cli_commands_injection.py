import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from src.cli.commands.analyze import AnalyzeCommand
from src.cli.commands.convert import ConvertCommand
from src.cli.commands.info import InfoCommand

class CLIInjectionTests(unittest.TestCase):
    def test_convert_command_uses_injected_services(self):
        chat_service = MagicMock()
        conversion_service = MagicMock()

        cmd = ConvertCommand(
            chat_service=chat_service,
            conversion_service=conversion_service,
        )

        self.assertIs(cmd.chat_service, chat_service)
        self.assertIs(cmd.conversion_service, conversion_service)

    def test_analyze_command_requires_explicit_dependencies(self):
        with self.assertRaisesRegex(
            ValueError, "AnalyzeCommand requires chat_service dependency"
        ):
            AnalyzeCommand()

    def test_info_command_uses_injected_services(self):
        chat_service = MagicMock()
        stats_service = MagicMock()

        cmd = InfoCommand(
            chat_service=chat_service,
            stats_service=stats_service,
        )

        self.assertIs(cmd.chat_service, chat_service)
        self.assertIs(cmd.stats_service, stats_service)

    def test_convert_command_requires_explicit_dependencies(self):
        with self.assertRaisesRegex(
            ValueError, "ConvertCommand requires chat_service dependency"
        ):
            ConvertCommand()

    def test_info_command_requires_explicit_dependencies(self):
        with self.assertRaisesRegex(
            ValueError, "InfoCommand requires chat_service dependency"
        ):
            InfoCommand()

if __name__ == "__main__":
    unittest.main()
