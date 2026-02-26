

import argparse
import os
import sys
from typing import Any, Dict, List, Optional

HELP_EN: Dict[str, str] = {
    "description": "Tkonverter CLI — convert and analyze Telegram chat exports. Use --help for global options; for command help: tkonverter-cli <command> --help.",
    "epilog": """
Examples:
  # Simple conversion
  tkonverter-cli convert -i result.json -o output.txt

  # Convert with settings
  tkonverter-cli convert -i result.json -o output.txt --profile personal --no-time

  # Convert with config file
  tkonverter-cli convert -i result.json -o output.txt --config config.json

  # Analyze tokens
  tkonverter-cli analyze -i result.json --tokenizer google/gemma-2b

  # File information
  tkonverter-cli info -i result.json

Command-specific help: tkonverter-cli convert --help | analyze --help | info --help
""",
    "debug": "Enable debug messages to stderr",
    "version": "Show version and exit",
    "subparsers": "Command: convert, analyze, info. Use <command> --help for that command's options.",
    "convert_cmd": "Convert Telegram chat export to text or HTML",
    "input": "Input chat export JSON file path",
    "output": "Output text (or HTML) file path",
    "html_mode": "Generate HTML instead of plain text",
    "overwrite": "Overwrite output file if it exists",
    "analyze_cmd": "Analyze chat statistics and character/token counts",
    "tokenizer": "Tokenizer model (e.g. google/gemma-2b); without this and without --chars-only, token count is skipped",
    "chars_only": "Character count only, no tokenization (no transformers required)",
    "output_file": "Save analysis result to file (JSON)",
    "info_cmd": "Show chat export file information",
    "detailed": "Show detailed parse statistics (messages, types, etc.)",
    "validate_only": "Only validate file without loading full chat",
    "config_group": "Configuration Options",
    "config_group_desc": "Display and profile options (for convert/analyze)",
    "profile": "Chat type: group, personal, posts, channel",
    "config": "Path to JSON config file (display, anonymization, etc.)",
    "show_time": "Show message timestamps",
    "no_time": "Hide message timestamps",
    "show_reactions": "Show message reactions",
    "no_reactions": "Hide reactions",
    "show_reaction_authors": "Show reaction authors",
    "no_reaction_authors": "Hide reaction authors",
    "show_optimization": "Enable message text optimization",
    "no_optimization": "Disable message optimization",
    "show_markdown": "Keep markdown in output",
    "no_markdown": "Strip markdown from output",
    "show_links": "Show links",
    "no_links": "Hide links",
    "show_tech_info": "Show technical info (message types, etc.)",
    "no_tech_info": "Hide technical info",
    "show_service_notifications": "Show service notifications (join, title change, etc.)",
    "no_service_notifications": "Hide service notifications",
    "my_name": "Your name in personal chats (how to display in export)",
    "partner_name": "Partner name in personal chats",
    "streak_break_time": "Day boundary for streak count (HH:MM, e.g. 20:00)",
    "date_group": "Date Filtering",
    "date_group_desc": "Filter messages by date (format: YYYY-MM-DD)",
    "from_date": "Start date: only process messages from this date",
    "to_date": "End date: only process messages up to and including this date",
    "exclude_dates": "Dates to exclude (space-separated)",
}

HELP_RU: Dict[str, str] = {
    "description": "Tkonverter CLI — конвертация и анализ экспортов чатов Telegram. Используйте --help для списка общих опций; для справки по команде: tkonverter-cli <команда> --help.",
    "epilog": """
Примеры:
  # Простая конвертация
  tkonverter-cli convert -i result.json -o output.txt

  # Конвертация с настройками
  tkonverter-cli convert -i result.json -o output.txt --profile personal --no-time

  # Конвертация с конфигом
  tkonverter-cli convert -i result.json -o output.txt --config config.json

  # Анализ токенов
  tkonverter-cli analyze -i result.json --tokenizer google/gemma-2b

  # Информация о файле
  tkonverter-cli info -i result.json

Справка по команде: tkonverter-cli convert --help | analyze --help | info --help
""",
    "debug": "Включить отладочные сообщения в stderr",
    "version": "Показать версию и выйти",
    "subparsers": "Команда: convert (конвертация), analyze (анализ), info (информация о файле). Укажите команду и --help для списка её опций.",
    "convert_cmd": "Конвертировать экспорт чата Telegram в текстовый или HTML формат",
    "input": "Путь к входному JSON-файлу экспорта чата",
    "output": "Путь к выходному текстовому (или HTML) файлу",
    "html_mode": "Генерировать HTML вместо обычного текста",
    "overwrite": "Перезаписать выходной файл, если он уже существует",
    "analyze_cmd": "Анализ статистики чата и подсчёт символов/токенов",
    "tokenizer": "Модель токенизатора (например, google/gemma-2b); без неё и без --chars-only подсчёт токенов не выполняется",
    "chars_only": "Только подсчёт символов, без токенизации (не требует библиотеки transformers)",
    "output_file": "Сохранить результат анализа в файл (JSON)",
    "info_cmd": "Показать информацию о файле экспорта чата",
    "detailed": "Показать детальную статистику разбора (сообщения, типы и т.д.)",
    "validate_only": "Только проверить файл без полной загрузки чата",
    "config_group": "Опции конфигурации",
    "config_group_desc": "Опции отображения и профиля (для convert/analyze)",
    "profile": "Тип чата: group (группа), personal (личный), posts (посты), channel (канал)",
    "config": "Путь к JSON-файлу конфигурации (настройки отображения, анонимизация и т.д.)",
    "show_time": "Показывать время сообщений",
    "no_time": "Не показывать время сообщений",
    "show_reactions": "Показывать реакции на сообщения",
    "no_reactions": "Не показывать реакции",
    "show_reaction_authors": "Показывать авторов реакций",
    "no_reaction_authors": "Не показывать авторов реакций",
    "show_optimization": "Включить оптимизацию текста сообщений",
    "no_optimization": "Отключить оптимизацию сообщений",
    "show_markdown": "Сохранять markdown-оформление в выводе",
    "no_markdown": "Убирать markdown из вывода",
    "show_links": "Показывать ссылки",
    "no_links": "Скрывать ссылки",
    "show_tech_info": "Показывать техническую информацию (типы сообщений и т.п.)",
    "no_tech_info": "Скрывать техническую информацию",
    "show_service_notifications": "Показывать служебные уведомления (вход в чат, смена названия и т.д.)",
    "no_service_notifications": "Скрывать служебные уведомления",
    "my_name": "Ваше имя в личных чатах (как отображать в экспорте)",
    "partner_name": "Имя собеседника в личных чатах",
    "streak_break_time": "Время «разрыва» дня для подсчёта серий (формат ЧЧ:ММ, например 20:00)",
    "date_group": "Фильтрация по датам",
    "date_group_desc": "Фильтрация по датам сообщений (формат даты: ГГГГ-ММ-ДД)",
    "from_date": "Начальная дата: обрабатывать только сообщения с этой даты",
    "to_date": "Конечная дата: обрабатывать только сообщения до этой даты включительно",
    "exclude_dates": "Даты для исключения (несколько через пробел)",
}

def _cli_lang() -> str:
    lang = os.environ.get("TKONVERTER_CLI_LANG", "").strip().lower()
    if lang in ("en", "ru"):
        return lang
    for var in ("LANG", "LC_ALL", "LANGUAGE"):
        val = os.environ.get(var, "")
        if not val:
            continue
        val = val.split(":")[0].split(".")[0].lower()
        if val.startswith("ru"):
            return "ru"
        if val.startswith("en"):
            return "en"
    return "en"

class ArgumentParser:

    def __init__(self):
        lang = _cli_lang()
        strings = HELP_RU if lang == "ru" else HELP_EN
        self._t = lambda k: strings.get(k, HELP_EN.get(k, k))

        self.parser = argparse.ArgumentParser(
            prog="tkonverter-cli",
            description=self._t("description"),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=self._t("epilog"),
        )

        self.parser.add_argument(
            "--debug", "-d",
            action="store_true",
            help=self._t("debug"),
        )
        self.parser.add_argument(
            "--version", "-v",
            action="version",
            version="Tkonverter CLI 1.0.0",
            help=self._t("version"),
        )

        subparsers = self.parser.add_subparsers(
            dest="command",
            help=self._t("subparsers"),
            required=True,
        )

        self._setup_convert_parser(subparsers)

        self._setup_analyze_parser(subparsers)

        self._setup_info_parser(subparsers)

    def _setup_convert_parser(self, subparsers):
        t = self._t
        convert_parser = subparsers.add_parser("convert", help=t("convert_cmd"))

        convert_parser.add_argument("-i", "--input", required=True, help=t("input"))
        convert_parser.add_argument("-o", "--output", required=True, help=t("output"))

        self._add_config_options(convert_parser)
        self._add_date_filter_options(convert_parser)

        convert_parser.add_argument("--html-mode", action="store_true", help=t("html_mode"))
        convert_parser.add_argument("--overwrite", action="store_true", help=t("overwrite"))

    def _setup_analyze_parser(self, subparsers):
        t = self._t
        analyze_parser = subparsers.add_parser("analyze", help=t("analyze_cmd"))

        analyze_parser.add_argument("-i", "--input", required=True, help=t("input"))
        analyze_parser.add_argument("--tokenizer", metavar="MODEL", help=t("tokenizer"))
        analyze_parser.add_argument("--chars-only", action="store_true", help=t("chars_only"))
        analyze_parser.add_argument("--output", metavar="FILE", help=t("output_file"))

        self._add_config_options(analyze_parser)
        self._add_date_filter_options(analyze_parser)

    def _setup_info_parser(self, subparsers):
        t = self._t
        info_parser = subparsers.add_parser("info", help=t("info_cmd"))

        info_parser.add_argument("-i", "--input", required=True, help=t("input"))
        info_parser.add_argument("--detailed", action="store_true", help=t("detailed"))
        info_parser.add_argument("--validate-only", action="store_true", help=t("validate_only"))

    def _add_config_options(self, parser):
        t = self._t
        config_group = parser.add_argument_group(t("config_group"), t("config_group_desc"))

        config_group.add_argument("--profile", choices=["group", "personal", "posts", "channel"], help=t("profile"))
        config_group.add_argument("--config", "-c", metavar="FILE", help=t("config"))

        time_group = config_group.add_mutually_exclusive_group()
        time_group.add_argument("--show-time", action="store_true", help=t("show_time"))
        time_group.add_argument("--no-time", action="store_true", help=t("no_time"))

        reaction_group = config_group.add_mutually_exclusive_group()
        reaction_group.add_argument("--show-reactions", action="store_true", help=t("show_reactions"))
        reaction_group.add_argument("--no-reactions", action="store_true", help=t("no_reactions"))

        reaction_authors_group = config_group.add_mutually_exclusive_group()
        reaction_authors_group.add_argument("--show-reaction-authors", action="store_true", help=t("show_reaction_authors"))
        reaction_authors_group.add_argument("--no-reaction-authors", action="store_true", help=t("no_reaction_authors"))

        optimization_group = config_group.add_mutually_exclusive_group()
        optimization_group.add_argument("--show-optimization", action="store_true", help=t("show_optimization"))
        optimization_group.add_argument("--no-optimization", action="store_true", help=t("no_optimization"))

        markdown_group = config_group.add_mutually_exclusive_group()
        markdown_group.add_argument("--show-markdown", action="store_true", help=t("show_markdown"))
        markdown_group.add_argument("--no-markdown", action="store_true", help=t("no_markdown"))

        links_group = config_group.add_mutually_exclusive_group()
        links_group.add_argument("--show-links", action="store_true", help=t("show_links"))
        links_group.add_argument("--no-links", action="store_true", help=t("no_links"))

        tech_group = config_group.add_mutually_exclusive_group()
        tech_group.add_argument("--show-tech-info", action="store_true", help=t("show_tech_info"))
        tech_group.add_argument("--no-tech-info", action="store_true", help=t("no_tech_info"))

        service_group = config_group.add_mutually_exclusive_group()
        service_group.add_argument("--show-service-notifications", action="store_true", help=t("show_service_notifications"))
        service_group.add_argument("--no-service-notifications", action="store_true", help=t("no_service_notifications"))

        config_group.add_argument("--my-name", metavar="NAME", help=t("my_name"))
        config_group.add_argument("--partner-name", metavar="NAME", help=t("partner_name"))
        config_group.add_argument("--streak-break-time", metavar="HH:MM", help=t("streak_break_time"))

    def _add_date_filter_options(self, parser):
        t = self._t
        date_group = parser.add_argument_group(t("date_group"), t("date_group_desc"))

        date_group.add_argument("--from-date", metavar="YYYY-MM-DD", help=t("from_date"))
        date_group.add_argument("--to-date", metavar="YYYY-MM-DD", help=t("to_date"))
        date_group.add_argument("--exclude-dates", nargs="+", metavar="YYYY-MM-DD", help=t("exclude_dates"))

    def parse_args(self, args: Optional[List[str]] = None) -> argparse.Namespace:
        if args is None:
            args = sys.argv[1:]

        return self.parser.parse_args(args)

    def get_help_text(self) -> str:
        return self.parser.format_help()

    def get_command_help(self, command: str) -> str:
        for action in self.parser._subparsers._actions:
            if hasattr(action, 'choices') and command in action.choices:
                return action.choices[command].format_help()
        return f"No help available for command: {command}"

    def validate_args(self, args: argparse.Namespace) -> List[str]:
        issues = []

        if hasattr(args, 'input') and args.input:
            import os
            if not os.path.exists(args.input):
                issues.append(f"Input file does not exist: {args.input}")

        if args.command == "convert" and hasattr(args, 'output'):
            if not args.output:
                issues.append("Output file path is required for convert command")
            elif os.path.exists(args.output) and not getattr(args, 'overwrite', False):
                issues.append(f"Output file already exists: {args.output}. Use --overwrite to overwrite")

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
