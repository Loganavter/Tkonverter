from datetime import datetime

from src.core.conversion.context import ConversionContext
from src.core.conversion.utils import format_ttl_period, pluralize_ru, truncate_name
from src.resources.translations import tr

def format_channel_create(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    title = msg.get("title", "...")
    return f"{actor} {tr('created channel')} «{title}»"

def format_edit_title(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    title = msg.get("title", "...")
    return f"{actor} {tr('changed group name to')} «{title}»"

def format_edit_photo(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    return f"{actor} {tr('changed group photo')}"

def format_delete_photo(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    return f"{actor} {tr('deleted group photo')}"

def format_history_clear(msg: dict, context: ConversionContext) -> str:
    return tr("History cleared")

def format_migrate_to_supergroup(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    return f"{actor} {tr('converted this group to supergroup')}"

def format_migrate_from_group(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    title = msg.get("title", "...")
    return f"{actor} {tr('converted group')} «{title}» {tr('to this supergroup')}"

def format_set_chat_theme(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    emoji = msg.get("emoticon", "")
    if emoji:
        return f"{actor} {tr('changed chat theme to')} {emoji}"
    return f"{actor} {tr('disabled chat theme')}"

def format_topic_create(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    title = msg.get("title", "...")
    return f"{actor} {tr('created topic')} «{title}»"

def format_topic_edit(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    new_title = msg.get("new_title")
    if new_title:
        return f"{actor} {tr('changed topic name to')} «{new_title}»"
    return f"{actor} {tr('edited topic')}"

def format_delete_user(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    member_kicked = truncate_name(msg.get("members", ["..."])[0], context=context)
    if actor == member_kicked:
        return f"{actor} {tr('left group')}"
    return f"{actor} {tr('removed')} {member_kicked}"

def format_screenshot_taken(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    return f"{actor} {tr('took screenshot')}"

def format_contact_signup(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    return f"{actor} {tr('joined Telegram')}"

def format_set_ttl(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    period = msg.get("period_seconds")
    period_str = format_ttl_period(period)
    if period:
        return f"{actor} {tr('set message auto-delete timer to')} {period_str}"
    else:
        return f"{actor} {tr('disabled message auto-delete timer')}"

def format_group_call_scheduled(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    schedule_date = msg.get("schedule_date")
    if schedule_date:
        dt_obj = datetime.fromisoformat(schedule_date)

        month_key = f"month_gen_{dt_obj.month}"
        month_name = tr(month_key)
        if month_name == month_key:
            month_name = dt_obj.strftime("%B")
        date_str = f"{dt_obj.strftime('%d')} {month_name} {dt_obj.strftime('%Y')}, {dt_obj.strftime('%H:%M')}"
        return f"{actor} {tr('scheduled video chat for')} {date_str}"
    return f"{actor} {tr('scheduled video chat')}"

def format_join_by_request(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    return f"{actor} {tr('joined group by request')}"

def format_webview_data(msg: dict, context: ConversionContext) -> str:
    button_text = msg.get("text", "...")
    return tr("sent data from button") + f' "{button_text}"'

def format_gift_code(msg: dict, context: ConversionContext) -> str:
    months = msg.get("months", 1)
    months_text = pluralize_ru(months, "month_form1", "month_form2", "month_form5")
    return tr("won premium for {months} {months_text}").format(months=months, months_text=months_text)

def format_custom_action(msg: dict, context: ConversionContext) -> str:
    return msg.get("text", tr("Service message"))

def format_star_gift(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    stars = msg.get("stars", 0)
    stars_text = pluralize_ru(stars, "star_form1", "star_form2", "star_form5")
    return f"{actor} {tr('gifted')} {stars} ★ {stars_text}"

def format_set_wallpaper(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    return f"{actor} {tr('changed chat wallpaper')}"
