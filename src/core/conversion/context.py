import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from src.core.conversion.utils import sanitize_forward_name, truncate_name
from src.resources.translations import tr

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.core.application.anonymizer_service import AnonymizerService

@dataclass
class ConversionContext:
    config: dict
    message_map: dict[int, dict] = field(default_factory=dict)
    my_id: str | None = None
    main_post_id: int | None = None
    partner_id: str | None = None
    chat_name: str = tr("common.unknown_chat")
    my_full_name: str | None = None
    partner_full_name: str | None = None
    anonymizer: Optional["AnonymizerService"] = None

    def get_author_name(self, msg: dict) -> str:

        display_name = msg.get("from", tr("common.user"))
        author_id = msg.get("from_id")

        profile = self.config.get("profile", "group")

        if profile == "personal":
            if author_id == self.my_id:
                display_name = self.config.get("my_name", display_name)
            elif author_id == self.partner_id:
                display_name = self.config.get("partner_name", display_name)

        elif profile == "posts":
            raw_from = msg.get("forwarded_from", msg.get("from", tr("common.user")))
            display_name = sanitize_forward_name(raw_from)

        if self.anonymizer:
            return self.anonymizer.anonymize_string_name(display_name)

        return truncate_name(display_name, context=self)
