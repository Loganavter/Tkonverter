from src.core.conversion.context import ConversionContext
from src.resources.translations import tr

def format_game(game_data: dict, context: ConversionContext) -> str:
    title = game_data.get("game_title")
    description = game_data.get("game_description", "")

    if not title:
        return tr("[Mini-game]")

    parts = [tr("[Game]"), f"{tr('Title')}: {title}"]
    if description:
        parts.append(f"{tr('Description')}: {description}")

    return "\n".join(parts)
