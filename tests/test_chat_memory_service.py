import sys
import tempfile
import unittest
from pathlib import Path

from PyQt6.QtCore import QDate

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from src.core.analysis.tree_analyzer import TreeNode
from src.core.application.analysis_service import AnalysisService
from src.core.application.calendar_service import CalendarService
from src.core.application.chat_memory_service import ChatMemoryService
from src.core.application.conversion_service import ConversionService
from src.core.application.export_metrics_service import ExportMetricsService
from src.core.analysis.tree_identity import TreeNodeIdentity
from src.core.parsing.json_parser import parse_chat_from_dict
from src.presenters.calendar_presenter import CalendarPresenter

def _build_day_tree(year: str, month: str, day: str) -> TreeNode:
    root = TreeNode(
        "Total", 0, date_level="root", node_id=TreeNodeIdentity.generate_root_id()
    )
    year_node = TreeNode(
        year,
        0,
        date_level="year",
        node_id=TreeNodeIdentity.generate_year_id(year),
    )
    month_node = TreeNode(
        month,
        0,
        date_level="month",
        node_id=TreeNodeIdentity.generate_month_id(year, month),
    )
    day_node = TreeNode(
        day,
        0,
        date_level="day",
        node_id=TreeNodeIdentity.generate_day_id(year, month, day),
    )
    root.add_child(year_node)
    year_node.add_child(month_node)
    month_node.add_child(day_node)
    return root

class ChatMemoryServiceTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.memory_service = ChatMemoryService(base_dir=Path(self._tmp_dir.name))
        self.calendar_service = CalendarService()
        self.presenter = CalendarPresenter(
            self.calendar_service, self.memory_service
        )
        self.chat_id = 10001
        self.date_key = "2026-02-01"
        self.raw_messages = [
            {
                "id": 1,
                "type": "message",
                "date": "2026-02-01T09:00:00",
                "from": "Me",
                "from_id": "user777000",
                "text": "Current original text",
            }
        ]
        self.config = ConversionService().get_default_config()
        self.tree = _build_day_tree("2026", "02", "01")

    def tearDown(self):
        self._tmp_dir.cleanup()

    def test_memory_roundtrip_for_disabled_dates_and_overrides(self):
        self.memory_service.update_disabled_dates(self.chat_id, {self.date_key})
        self.memory_service.upsert_day_override(
            self.chat_id,
            self.date_key,
            original_text="original",
            edited_text="edited",
        )

        memory = self.memory_service.load_memory(self.chat_id)
        self.assertIn(self.date_key, memory["disabled_dates"])
        self.assertIn(self.date_key, memory["day_overrides"])
        self.assertEqual(memory["day_overrides"][self.date_key]["edited_text"], "edited")

    def test_presenter_applies_saved_disabled_dates(self):
        self.memory_service.update_disabled_dates(self.chat_id, {self.date_key})
        self.presenter.load_calendar_data(
            raw_messages=self.raw_messages,
            analysis_tree=self.tree,
            initial_disabled_nodes=set(),
            token_hierarchy={},
            config=self.config,
            chat_id=self.chat_id,
        )

        disabled_nodes = self.presenter.get_disabled_nodes()
        self.assertEqual(len(disabled_nodes), 1)
        only_node = next(iter(disabled_nodes))
        self.assertEqual(getattr(only_node, "date_level", ""), "day")

    def test_conflict_detection_and_resolution_keep_saved(self):
        self.memory_service.upsert_day_override(
            self.chat_id,
            self.date_key,
            original_text="Old original text",
            edited_text="Saved edited text",
        )

        conflicts = []
        self.presenter.preview_conflict_detected.connect(lambda payload: conflicts.append(payload))
        self.presenter.load_calendar_data(
            raw_messages=self.raw_messages,
            analysis_tree=self.tree,
            initial_disabled_nodes=set(),
            token_hierarchy={},
            config=self.config,
            chat_id=self.chat_id,
        )

        date = QDate(2026, 2, 1)
        effective_text = self.presenter.get_effective_text_for_date(date)
        self.assertIn("Current original text", effective_text)
        self.assertGreaterEqual(len(conflicts), 1)
        self.assertIn("saved_original", conflicts[0]["diff_original"])

        self.presenter.resolve_day_conflict(self.date_key, "keep_saved")
        new_effective = self.presenter.get_effective_text_for_date(date)
        self.assertEqual(new_effective, "Saved edited text")

    def test_persist_chat_memory_saves_disabled_dates(self):
        self.presenter.load_calendar_data(
            raw_messages=self.raw_messages,
            analysis_tree=self.tree,
            initial_disabled_nodes=set(),
            token_hierarchy={},
            config=self.config,
            chat_id=self.chat_id,
        )

        self.presenter.toggle_filter_for_date(QDate(2026, 2, 1))
        self.presenter.persist_chat_memory()

        stored_disabled_dates = self.memory_service.get_disabled_dates(self.chat_id)
        self.assertIn(self.date_key, stored_disabled_dates)

    def test_analysis_counts_include_saved_day_override(self):
        chat = parse_chat_from_dict(
            {
                "id": self.chat_id,
                "name": "Sample",
                "type": "personal_chat",
                "messages": [
                    {
                        "id": 1,
                        "type": "message",
                        "date": "2026-02-01T10:00:00",
                        "from": "A",
                        "from_id": "u1",
                        "text": "abc",
                    }
                ],
            }
        )
        config = ConversionService().get_default_config()
        metrics_service = ExportMetricsService(chat_memory_service=self.memory_service)
        analysis_service = AnalysisService(export_metrics_service=metrics_service)

        before = analysis_service.calculate_character_stats(chat=chat, config=config)
        self.memory_service.upsert_day_override(
            self.chat_id,
            "2026-02-01",
            original_text="abc",
            edited_text="abcdef",
        )
        after = analysis_service.calculate_character_stats(chat=chat, config=config)

        self.assertNotEqual(after.total_count, before.total_count)
        self.assertNotEqual(
            after.date_hierarchy["2026"]["02"]["01"],
            before.date_hierarchy["2026"]["02"]["01"],
        )

if __name__ == "__main__":
    unittest.main()
