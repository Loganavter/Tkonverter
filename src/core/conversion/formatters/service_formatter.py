from src.core.conversion.context import ConversionContext
from src.core.conversion.formatters.service.atomic import (
    format_custom_action,
    format_channel_create,
    format_contact_signup,
    format_delete_photo,
    format_delete_user,
    format_edit_photo,
    format_edit_title,
    format_gift_code,
    format_group_call_scheduled,
    format_history_clear,
    format_join_by_request,
    format_migrate_from_group,
    format_migrate_to_supergroup,
    format_screenshot_taken,
    format_set_chat_theme,
    format_set_ttl,
    format_topic_create,
    format_topic_edit,
    format_star_gift,
    format_set_wallpaper,
    format_webview_data,
)
from src.core.conversion.formatters.service.complex import (
    format_add_user,
    format_bot_allowed,
    format_boost,
    format_boost_apply,
    format_create_group,
    format_change_creator,
    format_geo_proximity,
    format_game_score,
    format_giveaway_launch,
    format_giveaway_results,
    format_gift_premium,
    format_invite_to_group_call,
    format_join_by_link,
    format_new_creator_pending,
    format_paid_messages_price_change,
    format_paid_messages_refund,
    format_payment_sent,
    format_payment_refunded,
    format_phone_call,
    format_pin_message,
    format_process_suggested_post,
    format_requested_peer,
    format_requested_phone_number,
    format_secure_values,
    format_send_ton_gift,
    format_suggest_birthday,
    format_suggest_photo,
    format_suggested_post_refund,
    format_suggested_post_success,
)
from src.core.conversion.utils import (
    format_duration,
    format_member_list,
    pluralize_ru,
    process_text_to_plain,
    truncate_name,
)
from src.resources.translations import tr

SKIPPED_SERVICE_ACTIONS = set()

def format_service_message(msg: dict, context: ConversionContext) -> str | None:
    if not context.config.get("show_service_notifications", True):
        return None

    if context.config.get("profile") == "posts":
        return None

    action = msg.get("action", "unknown_action")

    if action in SKIPPED_SERVICE_ACTIONS:
        return None

    handlers = {
        "pin_message": format_pin_message,
        "phone_call": format_phone_call,
        "group_call": format_phone_call,
        "conference_call": format_phone_call,
        "create_group": format_create_group,
        "invite_members": format_add_user,
        "join_group_by_link": format_join_by_link,
        "joined_telegram": format_contact_signup,
        "gift_premium": format_gift_premium,
        "send_premium_gift": format_gift_premium,
        "boost_apply": format_boost_apply,
        "game_score": format_game_score,
        "payment_sent": format_payment_sent,
        "channel_create": format_channel_create,
        "create_channel": format_channel_create,
        "edit_group_title": format_edit_title,
        "edit_group_photo": format_edit_photo,
        "delete_group_photo": format_delete_photo,
        "history_clear": format_history_clear,
        "clear_history": format_history_clear,
        "migrate_to_supergroup": format_migrate_to_supergroup,
        "migrate_from_group": format_migrate_from_group,
        "set_chat_theme": format_set_chat_theme,
        "edit_chat_theme": format_set_chat_theme,
        "topic_created": format_topic_create,
        "topic_edit": format_topic_edit,
        "remove_members": format_delete_user,
        "screenshot_taken": format_screenshot_taken,
        "take_screenshot": format_screenshot_taken,
        "contact_signup": format_contact_signup,
        "set_messages_ttl": format_set_ttl,
        "group_call_scheduled": format_group_call_scheduled,
        "send_star_gift": format_star_gift,
        "send_stars_gift": format_star_gift,
        "set_chat_wallpaper": format_set_wallpaper,
        "set_same_chat_wallpaper": format_set_wallpaper,
        "join_group_by_request": format_join_by_request,
        "suggest_profile_photo": format_suggest_photo,
        "allow_sending_messages": format_bot_allowed,
        "attach_menu_bot_allowed": format_bot_allowed,
        "web_app_bot_allowed": format_bot_allowed,
        "send_passport_values": format_secure_values,
        "send_webview_data": format_webview_data,
        "proximity_reached": format_geo_proximity,
        "requested_phone_number": format_requested_phone_number,
        "requested_peer": format_requested_peer,
        "invite_to_group_call": format_invite_to_group_call,
        "gift_code_prize": format_gift_code,
        "giveaway_launch": format_giveaway_launch,
        "giveaway_results": format_giveaway_results,
        "refunded_payment": format_payment_refunded,
        "payment_refunded": format_payment_refunded,
        "send_ton_gift": format_send_ton_gift,
        "paid_messages_refund": format_paid_messages_refund,
        "paid_messages_price_change": format_paid_messages_price_change,
        "process_suggested_post": format_process_suggested_post,
        "suggested_post_success": format_suggested_post_success,
        "suggested_post_refund": format_suggested_post_refund,
        "suggest_birthday": format_suggest_birthday,
        "new_creator_pending": format_new_creator_pending,
        "change_creator": format_change_creator,

        "stars_prize": format_prize_stars,
        "todo_completions": format_todo_completions,
        "todo_append_tasks": format_todo_append_tasks,
        "score_in_game": format_game_score,
        "send_payment": format_payment_sent,
        "custom_action": format_custom_action,

    }

    if handler := handlers.get(action):
        service_text = handler(msg, context)
        result = f"\n--- [{service_text}] ---\n"
        return result

    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    title = msg.get("title", "")
    fallback_result = f"\n--- [{tr('Service message from')} '{actor}': {action} '{title}'] ---\n"
    return fallback_result

def format_prize_stars(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("boost_peer_name", tr("Channel")), context=context)
    stars = msg.get("stars", 0)
    stars_text = pluralize_ru(stars, "star_form1", "star_form2", "star_form5")
    return tr("won_prize_from").format(actor=actor, count=stars, stars_text=stars_text)

def format_todo_completions(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)

    return f"{actor} {tr('updated_tasks_in_list')}"

def format_todo_append_tasks(msg: dict, context: ConversionContext) -> str:
    actor = truncate_name(msg.get("actor", tr("System")), context=context)
    items = msg.get("items", [])
    if not items:
        return f"{actor} {tr('updated_tasks_in_list')}"

    tasks_texts = [
        process_text_to_plain(item.get("text", ""), context)
        for item in items
    ]
    tasks_str = ", ".join(f'"{text}"' for text in tasks_texts if text)
    return f"{actor} {tr('added_tasks')}: {tasks_str}"
