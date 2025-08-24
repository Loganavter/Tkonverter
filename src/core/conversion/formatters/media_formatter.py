

import logging
from core.conversion.context import ConversionContext
from core.conversion.formatters.media.game import format_game
from core.conversion.formatters.media.giveaway import (
    format_giveaway_start,
    format_giveaway_results,
)
from core.conversion.formatters.media.invoice import format_invoice
from core.conversion.formatters.media.polls import format_poll
from core.conversion.formatters.media.paid_content import format_paid_media
from core.conversion.formatters.media.todo import format_todo_list
from core.conversion.formatters.media.simple_media import (
    format_contact,
    format_dice,
    format_file,
    format_location,
    format_photo,
    format_place,
    format_venue,
)
from resources.translations import tr

logger = logging.getLogger(__name__)

def _is_file_included(msg: dict) -> bool:
    """Checks if the media file was actually exported."""

    not_included_str = "(File not included. Change data exporting settings to download.)"

    if msg.get("photo") == not_included_str:
        return False
    if msg.get("file") == not_included_str:
        return False

    return True

def format_media(msg: dict, context: ConversionContext) -> str:
    file_included = _is_file_included(msg)

    if poll_data := msg.get("poll"):
        return format_poll(poll_data, context)

    if msg.get("action") == "suggest_profile_photo" and msg.get("photo"):
        return format_photo(msg, context)

    if todo_data := msg.get("todo_list"):
        return format_todo_list(todo_data, context)

    if "paid_stars_amount" in msg:
        return format_paid_media(msg, context)

    if contact_info := msg.get("contact_information"):
        return format_contact(contact_info, context)

    if msg.get("place_name") and msg.get("address") and msg.get("location_information"):
        return format_place(msg, context)
    if venue_info := msg.get("venue"):
        return format_venue(venue_info, context)
    if location_info := msg.get("location_information"):
        return format_location(location_info, context)

    if dice_data := msg.get("dice"):
        return format_dice(dice_data, context)

    if msg.get("media_type") == "photo" or msg.get("photo"):
        return format_photo(msg, context)

    if msg.get("file"):
        return format_file(msg, context)

    if game_data := msg.get("game_information"):
        return format_game(game_data, context)

    if invoice_data := msg.get("invoice_information"):
        return format_invoice(invoice_data, context)

    if giveaway_info := msg.get("giveaway_information"):
        return format_giveaway_start(giveaway_info, context)

    if giveaway_results := msg.get("giveaway_results_information"):
        return format_giveaway_results(giveaway_results, context)

    if "via_bot_id" in msg and not msg.get("text") and not msg.get("file") and not msg.get("photo"):
        return tr("[Mini-game]")

    return ""
