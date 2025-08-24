from datetime import datetime

from core.conversion.context import ConversionContext
from core.conversion.utils import pluralize_ru
from resources.translations import tr

def format_giveaway_start(giveaway_data: dict, context: ConversionContext) -> str:
    """Formats giveaway start message."""
    parts = [f"**{tr('Giveaway')}**"]
    quantity = giveaway_data.get("quantity", 1)
    months = giveaway_data.get("months", 0)
    prize_months_text = pluralize_ru(months, "month_form1", "month_form2", "month_form5")
    prize_text = tr("{quantity} Premium subscriptions for {months} {months_text}").format(
        quantity=quantity, months=months, months_text=prize_months_text
    )
    parts.append(f"{tr('Prize:')} {prize_text}")

    if additional_prize := giveaway_data.get("additional_prize"):
        parts.append(f"{tr('Additionally:')} {additional_prize}")

    until_date_str = giveaway_data.get("until_date", "")
    if isinstance(until_date_str, datetime):
        until_date = until_date_str
    else:
        until_date = datetime.fromisoformat(until_date_str) if until_date_str else None
    if until_date:
        parts.append(f"{tr('Until:')} {until_date.strftime('%d %B %Y, %H:%M')}")

    return "\n".join(parts)

def format_giveaway_results(results_data: dict, context: ConversionContext) -> str:
    """Formats giveaway results message."""
    parts = [f"**{tr('Giveaway Results')}**"]
    winners_count = results_data.get("winners_count", 0)
    unclaimed_count = results_data.get("unclaimed_count", 0)
    winners_text = pluralize_ru(winners_count, "winner_form1", "winner_form2", "winner_form5")
    parts.append(f"{tr('Winners:')} {winners_count} {winners_text}")
    if unclaimed_count > 0:
        unclaimed_text = pluralize_ru(unclaimed_count, "unclaimed_form1", "unclaimed_form2", "unclaimed_form5")
        parts.append(f"({unclaimed_count} {unclaimed_text})")

    return "\n".join(parts)
