import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from src.core.application.analysis_service import AnalysisService
from src.core.application.chat_service import ChatService
from src.core.application.conversion_service import ConversionService

EXAMPLE_BASELINES = {
    "result.json": {
        "total_count": 5053,
        "total_characters": 5053,
        "average_message_length": 17.727272727272727,
        "years": {"2025", "2026", "2027"},
        "months": {"2025": {"12"}, "2026": {"02", "03"}, "2027": {"01"}},
        "days": {
            "2025": {"12": {"31"}},
            "2026": {"02": {"01"}, "03": {"15"}},
            "2027": {"01": {"02"}},
        },
    },
    "result_group.json": {
        "total_count": 3354,
        "total_characters": 3354,
        "average_message_length": 20.68421052631579,
        "years": {"2025", "2026", "2027"},
        "months": {"2025": {"11"}, "2026": {"02"}, "2027": {"01"}},
        "days": {
            "2025": {"11": {"05"}},
            "2026": {"02": {"01", "02"}},
            "2027": {"01": {"10"}},
        },
    },
}

def _load_example_chat(file_name: str):
    return ChatService().load_chat_from_file(str(PROJECT_ROOT / "examples" / file_name))

class CharacterCountingFromExampleTests(unittest.TestCase):
    def test_character_count_matches_example_baselines(self):
        config = ConversionService().get_default_config()

        for file_name, expected in EXAMPLE_BASELINES.items():
            with self.subTest(file_name=file_name):
                chat = _load_example_chat(file_name)
                result = AnalysisService().calculate_character_stats(chat=chat, config=config)

                self.assertEqual(result.unit, "Characters")
                self.assertEqual(result.total_count, expected["total_count"])
                self.assertEqual(result.total_characters, expected["total_characters"])
                self.assertAlmostEqual(
                    result.average_message_length,
                    expected["average_message_length"],
                    places=8,
                )
                self.assertSetEqual(set(result.date_hierarchy.keys()), expected["years"])
                for year, expected_months in expected["months"].items():
                    self.assertIn(year, result.date_hierarchy)
                    self.assertSetEqual(
                        set(result.date_hierarchy[year].keys()), expected_months
                    )
                for year, months in expected["days"].items():
                    for month, expected_days in months.items():
                        self.assertSetEqual(
                            set(result.date_hierarchy[year][month].keys()), expected_days
                        )

    def test_character_count_respects_disabled_dates(self):
        chat = _load_example_chat("result_group.json")
        config = ConversionService().get_default_config()

        full_result = AnalysisService().calculate_character_stats(chat=chat, config=config)
        filtered_result = AnalysisService().calculate_character_stats(
            chat=chat,
            config=config,
            disabled_dates={("2026", "02", "01")},
        )

        self.assertLess(filtered_result.total_count, full_result.total_count)

    def test_character_counting_runs_for_all_result_examples_without_errors(self):
        config = ConversionService().get_default_config()
        example_files = sorted((PROJECT_ROOT / "examples").glob("result*.json"))
        self.assertGreaterEqual(len(example_files), 1)

        for example_file in example_files:
            with self.subTest(example_file=example_file.name):
                chat = _load_example_chat(example_file.name)
                result = AnalysisService().calculate_character_stats(chat=chat, config=config)
                self.assertGreaterEqual(result.total_count, 0)
                self.assertEqual(result.total_count, result.total_characters)

if __name__ == "__main__":
    unittest.main()
