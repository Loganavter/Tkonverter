from core.conversion.context import ConversionContext
from core.conversion.formatters.media_formatter import format_media
from core.conversion.utils import (
    format_duration,
    format_member_list,
    pluralize_ru,
    process_text_to_plain,
    truncate_name,
)
from resources.translations import tr

def format_pin_message(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    pinned_message_id = msg.get("message_id")
    if pinned_message_id and (pinned_msg := context.message_map.get(pinned_message_id)):
        original_text = (
            process_text_to_plain(pinned_msg.get("text", ""), context)
            or format_media(pinned_msg, context)
            or tr("[Media]")
        )
        snippet = original_text.split("\n")[0].strip()
        max_len = context.config.get("truncate_quote_length", 50)
        if len(snippet) > max_len:
            snippet = snippet[:max_len] + "..."
        return f"{actor} {tr('pinned message')}: \"{snippet}\""
    return f"{actor} {tr('pinned message')}"

def format_phone_call(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    duration_sec = msg.get("duration_seconds")
    discard_reason = msg.get("discard_reason")

    is_group_call = msg.get("action") in ("group_call", "conference_call")

    if is_group_call:
        if duration_sec:
            duration_str = format_duration(duration_sec)
            return f"{tr('Video chat ended, duration')}: {duration_str}"
        else:
            return f"{actor} {tr('started video chat')}"

    call_type = (
        tr("Outgoing call")
        if actor == context.config.get("my_name")
        else tr("Incoming call")
    )

    if duration_sec:
        duration_str = format_duration(duration_sec)
        return f"{call_type}, {tr('duration')}: {duration_str}"

    reason_text = ""
    if discard_reason == "missed":
        reason_text = f" ({tr('missed')})"
    elif discard_reason == "busy":
        reason_text = f" ({tr('busy')})"
    elif discard_reason in ("hangup", "disconnect"):
        reason_text = f" ({tr('declined')})"

    return f"{call_type}{reason_text}"

def format_create_group(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    title = msg.get("title", "")
    members = msg.get("members", [])
    invited_members = [member for member in members if member != actor]
    text = f"{actor} {tr('created group')} «{title}»"
    if invited_members:
        invited_list_str = format_member_list(invited_members, context=context)
        text += f" {tr('and invited')} {invited_list_str}"
    return text

def format_add_user(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    members = msg.get("members", [])
    invited_members = [member for member in members if member and member != actor]
    if not invited_members:
        return f"{actor} {tr('joined group')}"
    members_str = format_member_list(invited_members, context=context)
    return f"{actor} {tr('invited')} {members_str}"

def format_join_by_link(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    inviter = truncate_name(msg.get("inviter"), context=context)
    if inviter:
        return f"{actor} {tr('joined group by link from')} {inviter}"
    return f"{actor} {tr('joined group by link')}"

def format_gift_premium(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    months = msg.get("months", 0)
    cost = msg.get("cost", "")
    text = f"{actor} {tr('gifted Telegram Premium')}"
    if months:
        text += f" {tr('for')} {months} {tr('months')}"
    if cost:
        text += f" ({cost})"
    return text

def format_boost(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    boosts = msg.get("boosts", 1)
    if boosts % 10 == 1 and boosts % 100 != 11:
        times_str = tr("time")
    elif 2 <= boosts % 10 <= 4 and (boosts % 100 < 10 or boosts % 100 >= 20):
        times_str = tr("times")
    else:
        times_str = tr("times")
    return f"{actor} {tr('boosted group')} {boosts} {times_str}"

def format_game_score(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    score = msg.get("score", 0)
    game_message_id = msg.get("game_message_id")

    game_title = "..."
    if game_message_id and (game_msg := context.message_map.get(game_message_id)):
        if game_info := game_msg.get("game_information"):
            game_title = game_info.get("game_title", "...")

    return f"{actor} {tr('scored')} {score} {tr('points in game')} «{game_title}»"

def format_payment_sent(msg: dict, context: ConversionContext) -> str:
    amount = msg.get("amount", 0)
    currency = msg.get("currency", "")

    formatted_amount = f"{amount / 100.0:.2f}"
    return f"{tr('Payment for')} {formatted_amount} {currency} {tr('sent')}"

def format_boost_apply(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    boosts = msg.get("boosts", 1)
    times_text = pluralize_ru(boosts, "time_form1", "time_form2", "time_form5")
    return f"{actor} {tr('boosted group')} {boosts} {times_text}"

def format_suggest_photo(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    return f"{actor} {tr('suggested a new profile photo')}"

def format_bot_allowed(msg: dict, context: ConversionContext) -> str:
    if domain := msg.get("domain"):
        return tr("allowed bot to send messages by logging in on") + f' {domain}'
    return tr("allowed bot to send messages")

def format_secure_values(msg: dict, context: ConversionContext) -> str:

    return tr("sent Telegram Passport data")

def format_geo_proximity(msg: dict, context: ConversionContext) -> str:
    from_id = msg.get("from_id")
    to_id = msg.get("to_id")
    distance = msg.get("distance", 0)
    distance_str = f"{distance}m"

    from_name = context.get_author_name({"from_id": from_id}) if from_id else "Someone"
    to_name = context.get_author_name({"from_id": to_id}) if to_id else "someone"

    if from_id == context.my_id:
        return tr("you are now within {distance} of {user}").format(distance=distance_str, user=to_name)
    elif to_id == context.my_id:
        return f"{from_name} " + tr("is now within {distance} of you").format(distance=distance_str)
    else:
        return f"{from_name} " + tr("is now within {distance} of {user}").format(distance=distance_str, user=to_name)

def format_payment_refunded(msg: dict, context: ConversionContext) -> str:
    currency = msg.get("currency", "")
    amount = msg.get("amount", 0) / 100.0
    return tr("payment of {amount} {currency} was refunded").format(amount=f"{amount:.2f}", currency=currency)
