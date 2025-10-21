from typing import Dict, Any

from src.core.conversion.main_converter import generate_plain_text
from src.resources.translations import tr

class PreviewService:
    """Service for generating preview data and HTML."""

    def __init__(self):
        pass

    def generate_preview_data(self, config: dict) -> dict:
        """Generates hardcoded preview data based on configuration."""
        profile = config.get("profile", "group")

        my_name = config.get("my_name", tr("Me"))
        partner_name = config.get("partner_name", tr("Sister"))

        if profile == "group":
            preview_data = {
                "name": tr("Preview: Example Group"),
                "messages": [
                    {
                        "id": 1,
                        "type": "service",
                        "action": "create_group",
                        "actor": tr("Preview: Alaisa"),
                        "title": tr("Preview: Example Group"),
                        "members": [
                            tr("Preview: Alaisa"),
                            tr("Preview: Alice"),
                            tr("Preview: Bob"),
                        ],
                        "date": "2025-04-02T23:57:00",
                    },
                    {
                        "id": 2,
                        "type": "message",
                        "from": tr("Preview: Bob"),
                        "from_id": "user_bob",
                        "date": "2025-04-02T23:58:00",
                        "text": tr("Preview: Hello everyone!"),
                        "reactions": [
                            {
                                "emoji": "👍",
                                "count": 1,
                                "recent": [
                                    {"from": tr("Preview: Alice"), "from_id": "user_alice"}
                                ],
                            }
                        ],
                    },
                    {
                        "id": 3,
                        "type": "message",
                        "from": tr("Preview: Alice"),
                        "from_id": "user_alice",
                        "date": "2025-04-02T23:59:00",
                        "edited": "2025-04-02T23:59:30",
                        "text": [{"type": "italic", "text": tr("Preview: One moment")}],
                    },
                    {
                        "id": 4,
                        "type": "service",
                        "action": "invite_members",
                        "actor": tr("Preview: Alice"),
                        "members": [tr("Preview: Alexander")],
                        "date": "2025-04-02T23:59:50",
                    },
                    {
                        "id": 5,
                        "type": "message",
                        "from": tr("Preview: Alexander"),
                        "from_id": "user_alex",
                        "date": "2025-04-03T00:01:00",
                        "reply_to_message_id": 3,
                        "text": tr("Preview: Thanks"),
                        "media_type": "sticker",
                        "sticker_emoji": "❤",
                        "reactions": [
                            {
                                "emoji": "💯",
                                "count": 1,
                                "recent": [
                                    {"from": tr("Preview: Bob"), "from_id": "user_bob"}
                                ],
                            },
                            {
                                "emoji": "🔥",
                                "count": 2,
                                "recent": [
                                    {"from": tr("Preview: Alice"), "from_id": "user_alice"},
                                    {"from": tr("Preview: Bob"), "from_id": "user_bob"},
                                ],
                            },
                        ],
                    },
                ],
            }

        elif profile == "personal":
            real_my_name = tr("Preview: Misha")
            real_partner_name = tr("Preview: Alice")

            my_alias = config.get("my_name", tr("Me"))
            partner_alias = config.get("partner_name", tr("Sister"))

            preview_data = {
                "name": "Alice",
                "messages": [
                    {
                        "id": 1,
                        "type": "service",
                        "action": "set_messages_ttl",
                        "actor": partner_alias,
                        "period_seconds": 0,
                        "date": "2024-12-31T23:57:00",
                    },
                    {
                        "id": 2,
                        "type": "message",
                        "from": real_my_name,
                        "from_id": "user_misha",
                        "date": "2024-12-31T23:58:00",
                        "text": tr("Preview: Almost midnight..."),
                        "reactions": [
                            {
                                "emoji": "❤️",
                                "count": 1,
                                "recent": [
                                    {"from": partner_alias, "from_id": "user_alice"}
                                ],
                            }
                        ],
                    },
                    {
                        "id": 3,
                        "type": "message",
                        "from": real_partner_name,
                        "from_id": "user_alice",
                        "date": "2025-01-01T00:01:00",
                        "text": tr("Preview: Happy New Year!"),
                        "reactions": [
                            {
                                "emoji": "🔥",
                                "count": 1,
                                "recent": [{"from": my_alias, "from_id": "user_misha"}],
                            }
                        ],
                    },
                ],
            }

        elif profile == "posts":
            editor_name = tr("Preview: Main Editor")
            preview_data = {
                "name": editor_name,
                "messages": [
                    {
                        "id": 10,
                        "type": "message",
                        "from": editor_name,
                        "date": "2025-08-13T13:00:00",
                        "text": [
                            {"type": "bold", "text": tr("Preview: New Telegram Update")},
                            "\n\n",
                            tr("Preview: Update description"),
                            "\n\n",
                            {
                                "type": "text_link",
                                "text": editor_name,
                                "href": "http://t.me/me",
                            },
                        ],
                    },
                    {
                        "id": 11,
                        "type": "message",
                        "from": "Red One",
                        "from_id": "user_red",
                        "date": "2025-08-13T13:02:00",
                        "reply_to_message_id": 10,
                        "text": tr("Preview: Why do we need this?"),
                    },
                    {
                        "id": 12,
                        "type": "message",
                        "from": "Ficction",
                        "from_id": "user_ficc",
                        "date": "2025-08-13T13:04:00",
                        "reply_to_message_id": 11,
                        "text": tr("Preview: If you don't need it..."),
                    },
                ],
            }

        elif profile == "channel":
            preview_data = {
                "name": tr("Preview: Example Channel"),
                "messages": [
                    {
                        "id": 1,
                        "type": "message",
                        "from": tr("Preview: Bob"),
                        "from_id": "user_bob",
                        "date": "2025-04-02T23:58:00",
                        "text": tr("Preview: Hello everyone!"),
                    },
                    {
                        "id": 2,
                        "type": "message",
                        "from": tr("Preview: Bob"),
                        "from_id": "user_bob",
                        "date": "2025-04-02T23:58:30",
                        "text": tr("Preview: This is a second message from me."),
                    },
                    {
                        "id": 3,
                        "type": "message",
                        "from": tr("Preview: Alice"),
                        "from_id": "user_alice",
                        "date": "2025-04-02T23:59:00",
                        "edited": "2020-04-02T23:59:30",
                        "text": [{"type": "italic", "text": tr("Preview: One moment")}],
                    },
                ],
            }

        else:
            preview_data = {}

        return preview_data

    def generate_preview_text(self, config: dict) -> tuple[str, str]:
        """Generates preview text and title based on configuration."""
        try:
            preview_data = self.generate_preview_data(config)
            raw_text = generate_plain_text(preview_data, config, html_mode=True)

            profile = config.get("profile", "group")

            if profile == "group":
                title = tr("Preview: Group example")
            elif profile == "personal":
                title = tr("Preview: Personal example")
            elif profile == "posts":
                title = tr("Preview: Posts example")
            elif profile == "channel":
                title = tr("Preview: Channel example")
            else:
                title = tr("Preview")

            return raw_text, title

        except Exception as e:
            import traceback

            error_message = f"Error: {e}"
            return error_message, "Preview Error"

    def get_longest_preview_html(self, config: dict) -> str:
        """
        Generates HTML for the longest static example ('posts').
        Used to calculate window height initially.
        """
        try:
            config_copy = config.copy()
            config_copy["profile"] = "posts"

            preview_data = self.generate_preview_data(config_copy)
            raw_text = generate_plain_text(preview_data, config_copy, html_mode=True)

            result_html = raw_text.replace("\n", "<br>")
            return result_html

        except Exception as e:
            import traceback
            return ""
