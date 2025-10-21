import re
from datetime import datetime
from html import escape
from typing import TYPE_CHECKING, Optional

from src.resources.translations import tr

INVALID_FORWARD_SOURCES = {"/dev/null", "null"}

if TYPE_CHECKING:
    from core.conversion.context import ConversionContext

def pluralize_ru(number: int, key_form1: str, key_form2: str, key_form5: str) -> str:
    """
    Selects the correct Russian plural form based on the number.
    """
    num = abs(number)
    if 11 <= num % 100 <= 19:
        return tr(key_form5)
    last_digit = num % 10
    if last_digit == 1:
        return tr(key_form1)
    if 2 <= last_digit <= 4:
        return tr(key_form2)
    return tr(key_form5)

def truncate_name(name: str | None, context: Optional["ConversionContext"] = None) -> str:
    max_len = 20
    if context and "truncate_name_length" in context.config:
        max_len = context.config["truncate_name_length"]

    if not name:
        return ""
    if len(name) > max_len:
        return name[:max_len-3] + "..."
    return name

def format_member_list(members: list[str], max_shown: int = 10, context: Optional["ConversionContext"] = None) -> str:
    total = len(members)
    if not total:
        return ""

    if total > max_shown:
        members_to_list = members[:max_shown]
        remaining_count = total - max_shown
        members_str = ", ".join([truncate_name(m, context) for m in members_to_list])
        members_str += f" and {remaining_count} more"
    else:
        members_str = ", ".join([truncate_name(m, context) for m in members])
    return members_str

def format_ttl_period(seconds: int | None) -> str:
    if not seconds:
        return tr("disabled")
    if seconds == 86400:
        return tr("24 hours")
    if seconds == 604800:
        return tr("7 days")
    if seconds == 2592000:
        return tr("1 month")

    days = seconds // 86400
    if days > 0:
        return tr("{days} d.").format(days=days)

    hours = seconds // 3600
    if hours > 0:
        return tr("{hours} h.").format(hours=hours)

    minutes = seconds // 60
    if minutes > 0:
        return tr("{minutes} min.").format(minutes=minutes)

    return tr("{seconds} sec.").format(seconds=seconds)

def sanitize_forward_name(name: str | None) -> str:
    if not name or name.strip() in INVALID_FORWARD_SOURCES:
        return tr("unknown source")
    return name

def format_date_separator(dt: datetime) -> str:

    month_key = f"month_gen_{dt.month}"
    month_name = tr(month_key)
    if month_name == month_key:
        month_name = dt.strftime("%B")
    return f"--- {dt.day} {month_name} {dt.year} ---"

def format_duration(seconds: int | float | None) -> str:
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "00:00"
    try:
        s = int(seconds)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h > 0:
            result = f"{h:02d}:{m:02d}:{s:02d}"
            return result
        result = f"{m:02d}:{s:02d}"
        return result
    except (TypeError, ValueError) as e:
        return "00:00"

def process_text_to_plain(text_data, context: "ConversionContext") -> str:
    config = context.config
    show_markdown = config.get("show_markdown", True)
    show_links = config.get("show_links", True)

    if isinstance(text_data, str):
        return text_data
    if isinstance(text_data, list):
        parts = []
        for item in text_data:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                text = item["text"]
                item_type = item.get("type")
                if item_type == "spoiler" and text == "\n":
                    text = ""

                if item_type == "bold" and show_markdown:
                    parts.append(f"**{text}**")
                elif item_type == "italic" and show_markdown:
                    parts.append(f"*{text}*")
                elif item_type == "strikethrough" and show_markdown:
                    parts.append(f"~~{text}~~")
                elif item_type == "underline" and show_markdown:
                    parts.append(f"_{text}_")
                elif item_type == "spoiler" and show_markdown:
                    parts.append(f"||{text}||")
                elif item_type == "code" and show_markdown:
                    parts.append(f"`{text}`")
                elif item_type == "bot_command":
                    parts.append(text)
                elif item_type == "custom_emoji":
                    parts.append(text)
                elif item_type == "pre" and show_markdown:
                    lang = item.get("language", "")
                    parts.append(f"\n```{lang}\n{text}\n```\n")
                elif item_type == "text_link":
                    if show_links:
                        href = item.get("href", "")
                        parts.append(f"[{text}]({href})")
                    else:
                        parts.append(text)

                elif item_type == "link":
                    if show_links:
                        parts.append(text)

                elif item_type == "blockquote" and show_markdown:
                    lines = text.split("\n")
                    formatted_lines = [f"> {line}" for line in lines]
                    parts.append("\n".join(formatted_lines))
                else:
                    parts.append(text)
        return "".join(parts)
    return ""

def markdown_to_html_for_preview(text: str) -> str:
    """Converts simple markdown-like text to basic HTML for preview."""

    text = re.sub(r'```(.*?)```', r'<code>\1</code>', text, flags=re.DOTALL)

    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)

    text = re.sub(r'__(.*?)__', r'<u>\1</u>', text)

    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)

    text = re.sub(r'~~(.*?)~~', r'<s>\1</s>', text)

    text = re.sub(r'\|\|(.*?)\|\|', r'<span class="spoiler">\1</span>', text)

    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)

    text = re.sub(r'\[(.*?)\]\((.*?)\)',
                  lambda m: f'<a href="{m.group(2).replace("&amp;", "&")}">{m.group(1)}</a>',
                  text)

    lines = text.split('\n')

    processed_lines = []
    for i, line in enumerate(lines):
        leading_spaces = len(line) - len(line.lstrip(' '))
        processed_line = '&nbsp;' * leading_spaces + line.lstrip(' ')
        processed_lines.append(processed_line)

    text = '<br>'.join(processed_lines)

    return text
