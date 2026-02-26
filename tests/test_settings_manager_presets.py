import sys
import tempfile
import json
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from src.core.settings import SettingsManager

class _FakeSettingsStore:
    def __init__(self):
        self._storage = {}
        self.sync_calls = 0

    def value(self, key, default=None, type=None):  # noqa: A002 - Qt-compatible signature
        return self._storage.get(key, default)

    def setValue(self, key, value):
        self._storage[key] = value

    def sync(self):
        self.sync_calls += 1

class _FakeAnonymizerService:
    def normalize_presets(self, presets):
        if not presets:
            return [{"id": "default", "name": "Default"}]
        result = []
        for preset in presets:
            normalized = dict(preset)
            normalized.setdefault("id", "generated")
            normalized["name"] = str(normalized.get("name", "")).strip() or "Preset"
            result.append(normalized)
        return result

    def create_preset(self, name):
        return {"id": "created", "name": name.strip() or "Preset"}

class SettingsManagerPresetTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.presets_dir = Path(self._tmpdir.name) / "presets"

    def tearDown(self):
        self._tmpdir.cleanup()

    def _build_manager(self, anonymizer_service=None):
        manager = SettingsManager(
            "org",
            "app",
            anonymizer_service=anonymizer_service,
            anonymizer_presets_dir=self.presets_dir,
        )
        manager.settings = _FakeSettingsStore()
        return manager

    def test_load_anonymizer_presets_uses_injected_service(self):
        manager = self._build_manager(_FakeAnonymizerService())
        manager.settings.setValue("anonymizer/presets", [{"name": "  Team  "}])

        presets = manager.load_anonymizer_presets()

        self.assertEqual(presets[0]["name"], "Team")

    def test_add_anonymizer_preset_persists_normalized_data(self):
        manager = self._build_manager(_FakeAnonymizerService())

        created = manager.add_anonymizer_preset("  New preset ")
        saved = manager.settings.value("anonymizer/presets", [])

        self.assertEqual(created["id"], "created")
        self.assertIn("New preset", [preset["name"] for preset in saved])
        self.assertGreaterEqual(manager.settings.sync_calls, 1)
        preset_file = self.presets_dir / "created.json"
        self.assertTrue(preset_file.exists())
        payload = json.loads(preset_file.read_text(encoding="utf-8"))
        self.assertEqual(payload.get("name"), "New preset")

    def test_preset_operations_require_anonymizer_service(self):
        manager = self._build_manager(anonymizer_service=None)

        with self.assertRaises(RuntimeError):
            manager.load_anonymizer_presets()

    def test_load_anonymizer_presets_reads_json_folder(self):
        manager = self._build_manager(_FakeAnonymizerService())
        self.presets_dir.mkdir(parents=True, exist_ok=True)
        (self.presets_dir / "abc.json").write_text(
            json.dumps({"id": "abc", "name": "  Saved Name  "}, ensure_ascii=False),
            encoding="utf-8",
        )

        presets = manager.load_anonymizer_presets()

        ids = [p["id"] for p in presets]
        self.assertIn("abc", ids)
        loaded = next(p for p in presets if p["id"] == "abc")
        self.assertEqual(loaded["name"], "Saved Name")

if __name__ == "__main__":
    unittest.main()
