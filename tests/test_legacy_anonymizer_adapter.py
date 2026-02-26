import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from src.core.conversion.main_converter import _LegacyAnonymizerAdapter
from src.core.domain.anonymization import AnonymizationConfig, LinkMaskMode

class LegacyAnonymizerAdapterTests(unittest.TestCase):
    def test_get_anonymized_name_uses_registered_user_id(self):
        config = AnonymizationConfig(enabled=True, hide_names=True)
        adapter = _LegacyAnonymizerAdapter(config)

        adapter.register_user(user_id="u-1", name="Alice")
        masked = adapter.get_anonymized_name("u-1", "Alice")

        self.assertIn("1", masked)

    def test_process_text_masks_links_with_index_mode(self):
        config = AnonymizationConfig(
            enabled=True,
            hide_links=True,
            link_mask_mode=LinkMaskMode.INDEXED,
            link_mask_format="[LINK {index}]",
        )
        adapter = _LegacyAnonymizerAdapter(config)

        text = "Visit https://example.com and https://example.org"
        masked = adapter.process_text(text)

        self.assertIn("[LINK 1]", masked)
        self.assertIn("[LINK 2]", masked)

    def test_process_text_masks_mentions_when_name_hiding_enabled(self):
        config = AnonymizationConfig(enabled=True, hide_names=True)
        adapter = _LegacyAnonymizerAdapter(config)

        masked = adapter.process_text("Hello @john_doe")

        self.assertNotIn("@john_doe", masked)
        self.assertIn("1", masked)

    def test_process_text_returns_original_when_anonymization_disabled(self):
        config = AnonymizationConfig(enabled=False, hide_links=True, hide_names=True)
        adapter = _LegacyAnonymizerAdapter(config)
        text = "Ping @name https://example.com"

        self.assertEqual(adapter.process_text(text), text)

if __name__ == "__main__":
    unittest.main()
