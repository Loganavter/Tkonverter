import sys
import unittest
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from src.core.application.conversion_service import ConversionService
from src.core.domain.models import Chat, Message, Reaction, User

def _build_chat_for_anonymization() -> Chat:
    alice = User(id="u1", name="Alice")
    bob = User(id="u2", name="Bob")
    message = Message(
        id=1,
        author=alice,
        date=datetime(2026, 1, 1, 10, 0, 0),
        text=[
            "Hi ",
            {"type": "text_link", "text": "site", "href": "https://example.org"},
            " and @bob",
        ],
        reactions=[Reaction(emoji="🔥", count=1, authors=[bob])],
    )
    return Chat(name="Sample Chat", type="group", messages=[message])

class AnonymizationOptionsImpactTests(unittest.TestCase):
    def setUp(self):
        self.service = ConversionService(use_modern_formatters=False)
        self.chat = _build_chat_for_anonymization()
        self.base_config = self.service.get_default_config()
        self.base_config.update(
            {
                "profile": "group",
                "show_links": True,
                "show_markdown": True,
                "show_reactions": True,
                "show_reaction_authors": True,
                "anonymization": {
                    "enabled": True,
                    "hide_links": True,
                    "hide_names": True,
                    "name_mask_format": "[NAME {index}]",
                    "link_mask_mode": "custom",
                    "link_mask_format": "[LINK {index}]",
                    "active_preset": None,
                    "custom_filters": [],
                    "custom_names": [],
                },
            }
        )

    def test_option_variants_do_not_disable_anonymization(self):
        variants = {
            "base": dict(self.base_config),
            "show_links_false": {**self.base_config, "show_links": False},
            "show_markdown_false": {**self.base_config, "show_markdown": False},
            "show_reactions_false": {**self.base_config, "show_reactions": False},
            "show_time_false": {**self.base_config, "show_time": False},
        }

        for variant_name, config in variants.items():
            with self.subTest(variant=variant_name):
                text = self.service.convert_to_text(
                    self.chat, config, html_mode=False, disabled_nodes=set()
                )
                self.assertNotIn("Alice", text)
                self.assertNotIn("Bob", text)
                self.assertNotIn("example.org", text)
                self.assertNotIn("https://", text)
                self.assertNotIn("Sample Chat", text)
                self.assertIn("[NAME", text)

if __name__ == "__main__":
    unittest.main()
