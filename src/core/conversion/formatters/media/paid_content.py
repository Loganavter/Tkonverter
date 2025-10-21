from src.core.conversion.context import ConversionContext
from src.resources.translations import tr

def format_paid_media(msg: dict, context: ConversionContext) -> str:
    """Formats paid media message."""
    stars = msg.get("paid_stars_amount", 0)

    return f"[{tr('Paid Content')}: {stars} ★]"
