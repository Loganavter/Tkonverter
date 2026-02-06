from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from src.core.conversion.utils import sanitize_forward_name, truncate_name
from src.resources.translations import tr

if TYPE_CHECKING:
    from src.core.application.anonymizer_service import AnonymizerService

@dataclass
class ConversionContext:
    config: dict
    message_map: dict[int, dict] = field(default_factory=dict)
    my_id: str | None = None
    main_post_id: int | None = None
    partner_id: str | None = None
    chat_name: str = tr("Unknown Chat")
    my_full_name: str | None = None
    partner_full_name: str | None = None
    anonymizer: Optional["AnonymizerService"] = None

    def get_author_name(self, msg: dict) -> str:
        author_id = msg.get("from_id", "unknown")
        profile = self.config.get("profile", "group")

        if profile == "personal":
            if author_id == self.my_id:
                original_name = self.config["my_name"]
            elif author_id == self.partner_id:
                original_name = self.config["partner_name"]
            else:
                original_name = truncate_name(msg.get("from", tr("User")), context=self)
        elif profile == "posts":
            raw_name = msg.get("forwarded_from", msg.get("from", tr("User")))
            original_name = truncate_name(sanitize_forward_name(raw_name), context=self)
        else:
            original_name = truncate_name(msg.get("from", tr("User")), context=self)

        if self.anonymizer:
            return self.anonymizer.get_anonymized_name(author_id, original_name)

        return original_name
