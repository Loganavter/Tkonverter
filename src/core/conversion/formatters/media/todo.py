from core.conversion.context import ConversionContext
from core.conversion.utils import process_text_to_plain
from resources.translations import tr

def format_todo_list(todo_data: dict, context: ConversionContext) -> str:
    """Formats a to-do list."""
    lines = [f"**{tr('To-Do List')}**"]

    title = process_text_to_plain(todo_data.get('title', ''), context)
    if title:
        lines.append(f"{tr('Title')}: {title}")

    for item in todo_data.get("items", []):
        text = process_text_to_plain(item.get('text', ''), context)
        lines.append(f"- [ ] {text}")

    return "\n".join(lines)
