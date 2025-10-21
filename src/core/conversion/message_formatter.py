import re
from datetime import datetime

from src.core.conversion.context import ConversionContext
from src.core.conversion.formatters.media_formatter import format_media
from src.core.conversion.utils import (
    process_text_to_plain,
    sanitize_forward_name,
    truncate_name,
)
from src.resources.translations import tr

def _parse_time_to_seconds(time_str: str) -> int:
    if not re.match(r"^\d{1,2}:\d{2}$", time_str):
        return 0

    try:
        hours, minutes = map(int, time_str.split(":"))

        if (0 <= hours < 24 and 0 <= minutes < 60) or (hours == 24 and minutes == 0):
            return hours * 3600 + minutes * 60
    except ValueError:
        pass

    return 0

def _should_print_header(
    msg: dict, prev_msg: dict | None, context: ConversionContext
) -> bool:
    if not prev_msg:
        return True

    try:
        current_dt = datetime.fromisoformat(msg["date"])
        prev_dt = datetime.fromisoformat(prev_msg["date"])
        if current_dt.date() != prev_dt.date():
            return True
    except (ValueError, KeyError):
        return True

    show_optimization = context.config.get("show_optimization", False)
    current_author = context.get_author_name(msg)
    prev_author = context.get_author_name(prev_msg)
    profile = context.config.get("profile", "group")

    if current_author != prev_author:
        return True

    show_service = context.config.get("show_service_notifications", True)
    if show_service and prev_msg.get("type") != "message":
        return True

    if show_optimization:
        if profile == "channel":

            streak_break_str = context.config.get("streak_break_time", "20:00")
            break_seconds = _parse_time_to_seconds(streak_break_str)

            if break_seconds > 0:
                time_diff = (current_dt - prev_dt).total_seconds()
                if time_diff >= break_seconds:
                    return True

            if "reactions" in prev_msg:
                return True
            if "inline_bot_buttons" in prev_msg or "reply_markup" in prev_msg:
                return True
            if msg.get("reply_to_message_id") != prev_msg.get("reply_to_message_id"):
                return True
            if msg.get("forwarded_from") != prev_msg.get("forwarded_from"):
                return True

            return False
        else:

            if "reactions" in prev_msg:
                return True

            return False

    if profile != "channel":
        return True

    return True

def _format_header(msg: dict, context: ConversionContext) -> str:
    author = context.get_author_name(msg)
    time_str = ""
    if context.config.get("show_time", True):
        try:
            is_edited = "edited" in msg
            date_key = "edited" if is_edited else "date"
            dt = datetime.fromisoformat(msg[date_key])
            time_part = dt.strftime("%H:%M")
            edited_part = tr(" (edited)") if is_edited else ""
            time_str = f" ({time_part}{edited_part})"
        except (ValueError, KeyError):
            pass
    return f"{author}{time_str}:\n"

def _format_reply(msg: dict, context: ConversionContext) -> str:

    if (
        context.config.get("profile") == "posts"
        and msg.get("reply_to_message_id") == context.main_post_id
    ):
        return ""

    if reply_id := msg.get("reply_to_message_id"):
        if original_msg := context.message_map.get(reply_id):
            original_author = context.get_author_name(original_msg)
            original_text = (
                process_text_to_plain(original_msg.get("text", ""), context)
                or format_media(original_msg, context)
                or tr("[Media]")
            )
            snippet = original_text.split("\n")[0].strip()
            max_len = context.config.get("truncate_quote_length", 50)
            if len(snippet) > max_len:
                snippet = snippet[:max_len] + "..."
            return f'  > {original_author}: "{snippet}"\n'
    return ""

def _format_reactions(
    msg: dict, context: ConversionContext, html_mode: bool = False
) -> str:
    if not context.config.get("show_reactions", True):
        return ""

    lines = []
    if reactions := msg.get("reactions"):
        for r in reactions:
            count = r.get("count", 1)
            emoji = r.get("emoji", "👍")
            reaction_text = f"{emoji}" if count == 1 else f"{emoji} {count}"

            if context.config.get("show_reaction_authors", False) and (
                recent := r.get("recent")
            ):
                authors = ", ".join([context.get_author_name(p) for p in recent])
                reaction_text += f" ({tr('from')}: {authors})"

            reaction_marker = ">"
            if (
                context.config["profile"] == "personal"
                and (reactors := r.get("recent"))
                and reactors
            ):
                first_reactor_id = reactors[0].get("from_id")
                if first_reactor_id == context.my_id:
                    reaction_marker = "&gt;&gt;" if html_mode else ">>"
                elif first_reactor_id == context.partner_id:
                    reaction_marker = "&lt;&lt;" if html_mode else "<<"

            lines.append(f"{reaction_marker} {reaction_text}")
    return "\n".join(lines) + "\n" if lines else ""

def _format_reply_markup(msg: dict, context: ConversionContext) -> str:
    rows = msg.get("inline_bot_buttons")

    if not isinstance(rows, list) and (reply_markup := msg.get("reply_markup")):
        rows = reply_markup.get("rows", [])

    if not rows or not isinstance(rows, list):
        return ""

    lines = [tr("[Buttons under message]")]
    for i, row in enumerate(rows):
        if not isinstance(row, list):
            continue

        button_texts = []
        for btn in row:
            if isinstance(btn, dict) and (text := btn.get("text")):
                safe_text = text.replace('"', '\\"')
                button_texts.append(f'"{safe_text}"')

        if button_texts:
            lines.append(f"- [{tr('Row')} {i+1}]: {' | '.join(button_texts)}")

    return "\n".join(lines) + "\n" if len(lines) > 1 else ""

def format_message(
    msg: dict,
    prev_msg: dict | None,
    context: ConversionContext,
    html_mode: bool = False,
) -> str:
    lines = []
    print_header = _should_print_header(msg, prev_msg, context)

    if print_header and prev_msg:
        lines.append("\n")

    if print_header:
        lines.append(_format_header(msg, context))

        if via_bot_id := msg.get("via_bot_id"):
            lines.append(f"  ({tr('via bot')} {via_bot_id})\n")

        forwarded_from_raw = msg.get("forwarded_from")
        if forwarded_from_raw and not msg.get("showForwardedAsOriginal"):
            if context.config["profile"] != "posts":
                clean_name = truncate_name(sanitize_forward_name(forwarded_from_raw), context=context)
                lines.append(f"  [{tr('forwarded from')} {clean_name}]\n")

        lines.append(_format_reply(msg, context))

    content = process_text_to_plain(msg.get("text", ""), context)
    media_info = format_media(msg, context)

    body_parts = []
    if content:
        body_parts.extend(content.split("\n"))
    if media_info:
        body_parts.extend(media_info.split("\n"))

    if not body_parts and not msg.get("reactions"):

        if print_header:
            body_parts.append(tr("[Mini-game]"))
        else:

            body_parts.append(tr("[Empty message]"))

    lines.extend([f"  {line}\n" for line in body_parts])

    if signature := msg.get("signature"):
        lines.append(f"  {tr('Signature')}: {signature}\n")

    lines.append(_format_reactions(msg, context, html_mode))
    lines.append(_format_reply_markup(msg, context))

    return "".join(lines)
