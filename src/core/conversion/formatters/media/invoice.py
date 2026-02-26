from src.core.conversion.context import ConversionContext
from src.resources.translations import tr

def format_invoice(invoice_data: dict, context: ConversionContext) -> str:
    title = invoice_data.get("title", tr("No title"))
    description = invoice_data.get("description", "")
    amount = invoice_data.get("amount", 0)
    currency = invoice_data.get("currency", "")

    formatted_amount = f"{amount / 100.0:.2f}"

    parts = [tr("[Payment invoice]"), f"{tr('Title')}: {title}"]
    if description:
        parts.append(f"{tr('Description')}: {description}")
    parts.append(f"{tr('Amount')}: {formatted_amount} {currency}")

    return "\n".join(parts)
