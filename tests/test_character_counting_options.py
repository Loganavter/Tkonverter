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

from src.core.application.analysis_service import AnalysisService
from src.core.application.conversion_service import ConversionService
from src.core.domain.models import Chat, Message, Reaction, User

def _build_rich_text_chat() -> Chat:
    author = User(id="u1", name="Tester")
    message = Message(
        id=1,
        author=author,
        date=datetime(2026, 2, 1, 12, 0, 0),
        text=[
            "Hello ",
            {"type": "bold", "text": "Bold"},
            " ",
            {"type": "text_link", "text": "site", "href": "https://example.com"},
            " ",
            {"type": "link", "text": "https://t.me/x"},
            " end",
        ],
        reactions=[Reaction(emoji="🔥", count=2, authors=[author])],
    )
    return Chat(name="Options Chat", type="group", messages=[message])

class CharacterCountingOptionsTests(unittest.TestCase):
    def setUp(self):
        self.analysis_service = AnalysisService()
        self.config = ConversionService().get_default_config()
        self.chat = _build_rich_text_chat()

    def test_show_links_option_changes_character_count(self):
        with_links = dict(self.config)
        with_links["show_links"] = True
        with_links["show_markdown"] = True

        without_links = dict(with_links)
        without_links["show_links"] = False

        result_with_links = self.analysis_service.calculate_character_stats(
            chat=self.chat, config=with_links
        )
        result_without_links = self.analysis_service.calculate_character_stats(
            chat=self.chat, config=without_links
        )

        self.assertGreater(result_with_links.total_count, result_without_links.total_count)

    def test_show_markdown_option_changes_character_count(self):
        with_markdown = dict(self.config)
        with_markdown["show_markdown"] = True
        with_markdown["show_links"] = True

        without_markdown = dict(with_markdown)
        without_markdown["show_markdown"] = False

        result_with_markdown = self.analysis_service.calculate_character_stats(
            chat=self.chat, config=with_markdown
        )
        result_without_markdown = self.analysis_service.calculate_character_stats(
            chat=self.chat, config=without_markdown
        )

        self.assertGreater(
            result_with_markdown.total_count, result_without_markdown.total_count
        )

    def test_export_options_change_character_count(self):
        base_config = dict(self.config)
        base_config.update({"show_links": True, "show_markdown": True})
        base_result = self.analysis_service.calculate_character_stats(
            chat=self.chat, config=base_config
        )

        varied_config = dict(base_config)
        varied_config.update(
            {
                "show_reactions": False,
                "show_reaction_authors": True,
                "show_time": False,
                "show_tech_info": False,
                "show_service_notifications": False,
            }
        )
        varied_result = self.analysis_service.calculate_character_stats(
            chat=self.chat, config=varied_config
        )

        self.assertNotEqual(base_result.total_count, varied_result.total_count)

    def test_anonymization_options_affect_character_count(self):
        no_anon = dict(self.config)
        no_anon.update(
            {
                "show_links": True,
                "show_markdown": True,
                "anonymization": {
                    "enabled": False,
                    "hide_links": False,
                    "hide_names": False,
                    "name_mask_format": "[NAME {index}]",
                    "link_mask_mode": "custom",
                    "link_mask_format": "[L]",
                    "active_preset": None,
                    "custom_filters": [],
                    "custom_names": [],
                },
            }
        )

        with_anon = dict(no_anon)
        with_anon["anonymization"] = {
            "enabled": True,
            "hide_links": True,
            "hide_names": True,
            "name_mask_format": "[NAME {index}]",
            "link_mask_mode": "custom",
            "link_mask_format": "[L]",
            "active_preset": None,
            "custom_filters": [],
            "custom_names": [],
        }

        without_anon_result = self.analysis_service.calculate_character_stats(
            chat=self.chat, config=no_anon
        )
        with_anon_result = self.analysis_service.calculate_character_stats(
            chat=self.chat, config=with_anon
        )

        self.assertNotEqual(without_anon_result.total_count, with_anon_result.total_count)

    def test_character_count_matches_export_when_active_preset_is_id(self):
        config = dict(self.config)
        config.update(
            {
                "show_links": True,
                "show_markdown": True,
                "anonymization": {
                    "enabled": True,
                    "hide_links": True,
                    "hide_names": True,
                    "name_mask_format": "[NAME {index}]",
                    "link_mask_mode": "custom",
                    "link_mask_format": "[L]",

                    "active_preset": "preset-123",
                    "custom_filters": [],
                    "custom_names": [],
                },
            }
        )

        analysis_result = self.analysis_service.calculate_character_stats(
            chat=self.chat, config=config
        )
        exported_text = ConversionService().convert_to_text(
            self.chat, config, html_mode=False, disabled_nodes=set()
        )

        self.assertEqual(analysis_result.total_count, len(exported_text))

    def test_character_date_hierarchy_matches_export_total(self):
        config = dict(self.config)
        config.update({"show_links": True, "show_markdown": True})

        result = self.analysis_service.calculate_character_stats(
            chat=self.chat, config=config
        )

        hierarchy_sum = 0.0
        for months in result.date_hierarchy.values():
            for days in months.values():
                hierarchy_sum += sum(days.values())

        self.assertAlmostEqual(hierarchy_sum, float(result.total_count), places=6)

if __name__ == "__main__":
    unittest.main()
