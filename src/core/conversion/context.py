from dataclasses import dataclass, field

from src.core.conversion.utils import sanitize_forward_name, truncate_name
from src.resources.translations import tr

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

    def get_author_name(self, msg: dict) -> str:
        author_id = msg.get("from_id")
        profile = self.config.get("profile", "group")

        if profile == "personal":
            if author_id == self.my_id:
                result = self.config["my_name"]
                return result
            if author_id == self.partner_id:
                result = self.config["partner_name"]
                return result

            result = truncate_name(msg.get("from", tr("User")), context=self)
            return result

        elif profile == "posts":
            raw_name = msg.get("forwarded_from", msg.get("from", tr("User")))
            result = truncate_name(sanitize_forward_name(raw_name), context=self)
            return result

        result = truncate_name(msg.get("from", tr("User")), context=self)
        return result
