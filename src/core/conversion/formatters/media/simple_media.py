import logging
from core.conversion.context import ConversionContext
from core.conversion.utils import format_duration
from resources.translations import tr

logger = logging.getLogger(__name__)

BAD_FILENAME = "(File not included. Change data exporting settings to download.)"

def format_photo(msg: dict, context: ConversionContext) -> str:
    base_label = tr("[Photo]")
    spoiler_prefix = f"{tr('[SPOILER]')} " if msg.get("media_spoiler") else ""

    if not context.config.get("show_tech_info", True):
        return f"{spoiler_prefix}{base_label}"

    extras = []
    width = msg.get("width")
    height = msg.get("height")

    if width and height:
        dimension_str = f"{width}x{height}"
        extras.append(dimension_str)

    if extras:
        details_str = ", ".join(extras)
        result = f"{spoiler_prefix}{tr('[Photo ({details})]').format(details=details_str)}"
        return result

    return f"{spoiler_prefix}{base_label}"

def format_file(msg: dict, context: ConversionContext) -> str:
    spoiler_prefix = f"{tr('[SPOILER]')} " if msg.get("media_spoiler") else ""
    show_tech_info = context.config.get("show_tech_info", True)

    filename = msg.get("file_name", tr("file"))
    media_type = msg.get("media_type")
    duration_sec = msg.get("duration_seconds")

    if media_type == "audio_file":
        if not show_tech_info:
            return f"{spoiler_prefix}{tr('[Audio]')}"
        performer = msg.get("performer", tr("Unknown performer"))
        title = msg.get("title", filename)
        duration = format_duration(duration_sec)
        return f"{spoiler_prefix}{tr('[Audio: {performer} - {title} ({duration})]').format(performer=performer, title=title, duration=duration)}"

    if media_type == "video_file":
        base_label = tr("[Video]")
        if not show_tech_info:
            return f"{spoiler_prefix}{base_label}"

        extras = []

        if filename and filename != BAD_FILENAME and filename != tr("file"):
            extras.append(filename)

        width = msg.get("width")
        height = msg.get("height")

        if width and height:
            dimension_str = f"{width}x{height}"
            extras.append(dimension_str)

        if duration_sec is not None:
            duration_str = format_duration(duration_sec)
            extras.append(duration_str)

        if extras:
            result = f"{spoiler_prefix}{tr('[Video ({details})]').format(details=', '.join(extras))}"
            return result
        return f"{spoiler_prefix}{base_label}"

    if media_type == "animation":
        base_label = tr("[Animation]")
        if not show_tech_info:
            return f"{spoiler_prefix}{base_label}"

        extras = []

        if filename and filename != BAD_FILENAME and filename != tr("file"):
            extras.append(filename)

        width = msg.get("width")
        height = msg.get("height")

        if width and height:
            dimension_str = f"{width}x{height}"
            extras.append(dimension_str)

        if duration_sec is not None:
            duration_str = format_duration(duration_sec)
            extras.append(duration_str)

        if extras:
            result = f"{spoiler_prefix}{tr('[Animation ({details})]').format(details=', '.join(extras))}"
            return result
        return f"{spoiler_prefix}{base_label}"

    if media_type == "voice_message":
        if not show_tech_info:
            return f"{spoiler_prefix}{tr('[Voice message]')}"
        return f"{spoiler_prefix}{tr('[Voice message ({duration})]').format(duration=format_duration(duration_sec))}"
    if media_type == "video_message":
        if not show_tech_info:
            return f"{spoiler_prefix}{tr('[Video message]')}"
        return f"{spoiler_prefix}{tr('[Video message ({duration})]').format(duration=format_duration(duration_sec))}"
    if media_type == "sticker":
        if not show_tech_info:
            return f"{spoiler_prefix}{tr('[Sticker]')}"
        emoji = msg.get("sticker_emoji", "")
        return f"{spoiler_prefix}{tr('[Sticker {emoji}]').format(emoji=emoji)}"

    if not show_tech_info:
        return f"{spoiler_prefix}{tr('[File]')}"
    return f"{spoiler_prefix}{tr('[File: {filename}]').format(filename=filename)}"

def format_contact(contact_info: dict, context: ConversionContext) -> str:
    name = f"{contact_info.get('first_name', '')} {contact_info.get('last_name', '')}".strip()
    phone = (
        contact_info.get("phone_number", tr("phone not specified"))
        if context.config.get("show_tech_info", True)
        else ""
    )
    return f"{tr('[Contact: {name}, {phone}]').format(name=name, phone=phone)}"

def format_location(location_info: dict, context: ConversionContext) -> str:
    lat = location_info.get("latitude")
    lon = location_info.get("longitude")

    if not context.config.get("show_tech_info", True):
        return f"{tr('[Geoposition]')}"

    return f"{tr('[Geoposition: {lat:.6f}, {lon:.6f}]').format(lat=lat, lon=lon)}"

def format_place(msg: dict, context: ConversionContext) -> str:
    place_name = msg.get("place_name", tr("No title"))
    address = msg.get("address", "")
    show_tech_info = context.config.get("show_tech_info", True)
    location_info = msg.get("location_information")

    if show_tech_info and location_info:
        lat = location_info.get("latitude")
        lon = location_info.get("longitude")
        if lat is not None and lon is not None:
            return f"{tr('[Place: {place}, {address} (Coordinates: {lat:.6f}, {lon:.6f})]').format(place=place_name, address=address, lat=lat, lon=lon)}"

    return f"{tr('[Place: {place}, {address}]').format(place=place_name, address=address)}"

def format_venue(venue_info: dict, context: ConversionContext) -> str:
    title = venue_info.get("title", tr("No title"))
    address = venue_info.get("address", "")
    return f"{tr('[Place: {title}, {address}]').format(title=title, address=address)}"

def format_dice(dice_data: dict, context: ConversionContext) -> str:
    emoji = dice_data.get("emoji", "🎲")
    value = dice_data.get("value", "?")
    return f"{tr('[Dice roll: {emoji} (Result: {value})]').format(emoji=emoji, value=value)}"
