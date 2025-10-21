from src.core.conversion.context import ConversionContext
from src.resources.translations import tr
from src.core.conversion.utils import pluralize_ru

def format_poll(poll_data: dict, context: ConversionContext) -> str:
    lines = [tr("[Poll]")]
    lines.append(f"{tr('Question')}: {poll_data.get('question', tr('No question'))}")
    total_voters = poll_data.get("total_voters", 0)
    for answer in poll_data.get("answers", []):
        text = answer.get("text", tr("No text"))
        voters = answer.get("voters", 0)
        percentage = (voters / total_voters * 100) if total_voters > 0 else 0
        chosen_marker = f" ({tr('Your choice')})" if answer.get("chosen") else ""
        voters_text = pluralize_ru(voters, "people_form1", "people_form2", "people_form5")
        lines.append(
            f'- {text}: {voters} {voters_text} ({percentage:.0f}%){chosen_marker}'
        )
    total_voters_text = pluralize_ru(total_voters, "people_form1", "people_form2", "people_form5")
    lines.append(f"{tr('Total voted')}: {total_voters} {total_voters_text}")
    if poll_data.get("closed", False):
        lines.append(f"({tr('Poll closed')})")
    return "\n".join(lines)
