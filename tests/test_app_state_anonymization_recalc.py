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

from src.core.domain.models import AnalysisResult, Chat, Message, User
from src.presenters.app_state import AppState

class AppStateAnonymizationRecalcTests(unittest.TestCase):
    def _build_state_with_analysis(self) -> AppState:
        state = AppState(
            ui_config={
                "profile": "group",
                "show_markdown": True,
                "show_links": True,
                "anonymizer_enabled": False,
                "anonymizer_preset_id": "default",
                "anonymization": {"enabled": False},
            }
        )
        chat = Chat(
            name="Chat",
            type="group",
            messages=[
                Message(
                    id=1,
                    author=User(id="u1", name="Alice"),
                    date=datetime(2026, 1, 1, 12, 0, 0),
                    text="hello",
                )
            ],
        )
        state.set_chat(chat, "/tmp/chat.json")
        state.set_analysis_result(
            AnalysisResult(total_count=5, unit="Characters", date_hierarchy={})
        )
        return state

    def test_set_config_value_anonymization_clears_analysis(self):
        state = self._build_state_with_analysis()
        self.assertTrue(state.has_analysis_data())

        state.set_config_value("anonymization", {"enabled": True, "hide_names": True})

        self.assertFalse(state.has_analysis_data())

if __name__ == "__main__":
    unittest.main()
