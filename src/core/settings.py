import os
import sys
import json
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QByteArray, QLocale, QSettings
from src.core.settings_port import SettingsPort

def _get_app_config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", "")
        if not base:
            base = Path.home() / "AppData" / "Roaming"
        return Path(base) / "Tkonverter"
    return Path.home() / ".config" / "Tkonverter"

class SettingsManager(SettingsPort):
    def __init__(
        self,
        organization_name: str,
        application_name: str,
        anonymizer_service=None,
        anonymizer_presets_dir: str | Path | None = None,
    ):
        config_dir = _get_app_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "settings.ini"
        self.settings = QSettings(str(config_file), QSettings.Format.IniFormat)
        self._migrate_from_registry_if_needed(organization_name, application_name)
        self._anonymizer_service = anonymizer_service
        self._anonymizer_presets_dir = (
            Path(anonymizer_presets_dir).expanduser()
            if anonymizer_presets_dir is not None
            else None
        )

    def _migrate_from_registry_if_needed(self, organization_name: str, application_name: str) -> None:
        try:
            all_keys = self.settings.allKeys()
            if all_keys:
                return
            legacy = QSettings(organization_name, application_name)
            legacy_keys = legacy.allKeys()
            if not legacy_keys:
                return
            for key in legacy_keys:
                val = legacy.value(key)
                if val is not None:
                    self.settings.setValue(key, val)
            self.settings.sync()
        except Exception:
            pass

    def _get_anonymizer_service(self):
        if self._anonymizer_service is None:
            raise RuntimeError(
                "AnonymizerService is required for preset operations. "
                "Pass anonymizer_service to SettingsManager."
            )
        return self._anonymizer_service

    def _get_anonymizer_presets_dir(self) -> Path:
        if self._anonymizer_presets_dir is not None:
            target_dir = self._anonymizer_presets_dir
        else:
            config_path = ""
            try:
                config_path = str(self.settings.fileName() or "")
            except Exception:
                config_path = ""
            base_dir = Path(config_path).expanduser().parent if config_path else Path.home() / ".config" / "Tkonverter"
            target_dir = base_dir / "anonymizer_presets"
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    @staticmethod
    def _preset_file_name(preset_id: str) -> str:
        safe_id = "".join(ch for ch in str(preset_id) if ch.isalnum() or ch in ("-", "_")).strip()
        return f"{safe_id or 'preset'}.json"

    def _preset_file_path(self, preset_id: str) -> Path:
        return self._get_anonymizer_presets_dir() / self._preset_file_name(preset_id)

    def _load_presets_from_files(self) -> list[dict[str, Any]]:
        presets_dir = self._get_anonymizer_presets_dir()
        presets: list[dict[str, Any]] = []
        for path in sorted(presets_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    presets.append(data)
            except Exception:
                continue
        return presets

    def _migrate_presets_from_qsettings_if_needed(self):
        presets_dir = self._get_anonymizer_presets_dir()
        if any(presets_dir.glob("*.json")):
            return
        legacy = self.settings.value("anonymizer/presets", [], type=list) or []
        if not legacy:
            return
        service = self._get_anonymizer_service()
        normalized = service.normalize_presets(legacy)
        for preset in normalized:
            preset_id = str(preset.get("id", "")).strip()
            if not preset_id:
                continue
            self._preset_file_path(preset_id).write_text(
                json.dumps(preset, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def load_theme(self) -> str:
        theme = self.settings.value("theme", "auto", type=str)
        return theme

    def save_theme(self, theme: str):
        self.settings.setValue("theme", theme)
        self.settings.sync()

    def load_language(self) -> str:

        saved_lang = self.settings.value("language", None, type=str)
        if saved_lang in ["en", "ru"]:
            return saved_lang

        try:
            system_locale = QLocale.system().name()
            lang_code = system_locale.split('_')[0].lower()

            if lang_code in ["en", "ru"]:
                return lang_code
        except Exception as e:
            pass
        return "ru"

    def save_language(self, lang_code: str):
        self.settings.setValue("language", lang_code)
        self.settings.sync()

    def load_debug_mode(self) -> bool:
        return self.settings.value("debug/enabled", False, type=bool)

    def save_debug_mode(self, enabled: bool):
        self.settings.setValue("debug/enabled", enabled)
        self.settings.sync()

    def load_export_settings(self) -> dict:
        return {
            "use_default_dir": self.settings.value(
                "export_use_default_dir", True, type=bool
            ),
            "default_dir": self.settings.value("export_default_dir", "", type=str),
            "favorite_dir": self.settings.value("export_favorite_dir", "", type=str),
        }

    def get_export_default_dir(self) -> str:
        return self.settings.value("export_default_dir", "", type=str)

    def save_export_default_dir(self, use_default_dir: bool, default_dir: str) -> None:
        self.settings.setValue("export_use_default_dir", use_default_dir)
        if use_default_dir:
            self.settings.setValue("export_default_dir", default_dir)
        self.settings.sync()

    def load_export_favorite_dir(self) -> str:
        return self.settings.value("export_favorite_dir", "", type=str)

    def save_export_favorite_dir(self, favorite_dir: str) -> None:
        self.settings.setValue("export_favorite_dir", favorite_dir)
        self.settings.sync()

    def load_ui_settings(self) -> dict:
        settings = {
            "profile": self.settings.value("ui/profile", "group", type=str),
            "auto_detect_profile": self.settings.value("ui/auto_detect_profile", True, type=bool),
            "auto_recalc": self.settings.value("ui/auto_recalc", False, type=bool),
            "show_time": self.settings.value("ui/show_time", True, type=bool),
            "show_reactions": self.settings.value("ui/show_reactions", True, type=bool),
            "show_reaction_authors": self.settings.value(
                "ui/show_reaction_authors", False, type=bool
            ),
            "my_name": self.settings.value("ui/my_name", "", type=str),
            "partner_name": self.settings.value("ui/partner_name", "", type=str),
            "show_optimization": self.settings.value(
                "ui/show_optimization", False, type=bool
            ),
            "streak_break_time": self.settings.value(
                "ui/streak_break_time", "20:00", type=str
            ),
            "show_markdown": self.settings.value("ui/show_markdown", True, type=bool),
            "show_links": self.settings.value("ui/show_links", True, type=bool),
            "show_tech_info": self.settings.value("ui/show_tech_info", True, type=bool),
            "show_service_notifications": self.settings.value(
                "ui/show_service_notifications", True, type=bool
            ),
            "truncate_name_length": self.settings.value(
                "ui/truncate_name_length", 20, type=int
            ),
            "truncate_quote_length": self.settings.value(
                "ui/truncate_quote_length", 50, type=int
            ),
            "anonymizer_enabled": self.settings.value(
                "ui/anonymizer_enabled", False, type=bool
            ),
            "anonymizer_preset_id": self.settings.value(
                "ui/anonymizer_preset_id", "default", type=str
            ),
            "show_activity_analysis": self.settings.value(
                "ui/show_activity_analysis", False, type=bool
            ),
            "analysis_unit": self.settings.value(
                "ui/analysis_unit", "tokens", type=str
            ),
        }
        return settings

    def save_ui_settings(self, config: dict):
        self.settings.setValue("ui/profile", config.get("profile", "group"))
        self.settings.setValue("ui/auto_detect_profile", config.get("auto_detect_profile", True))
        self.settings.setValue("ui/auto_recalc", config.get("auto_recalc", False))
        self.settings.setValue("ui/show_time", config.get("show_time", True))
        self.settings.setValue("ui/show_reactions", config.get("show_reactions", True))
        self.settings.setValue(
            "ui/show_reaction_authors", config.get("show_reaction_authors", False)
        )
        self.settings.setValue("ui/my_name", config.get("my_name", ""))
        self.settings.setValue("ui/partner_name", config.get("partner_name", ""))
        self.settings.setValue(
            "ui/show_optimization", config.get("show_optimization", False)
        )
        self.settings.setValue(
            "ui/streak_break_time", config.get("streak_break_time", "20:00")
        )
        self.settings.setValue("ui/show_markdown", config.get("show_markdown", True))
        self.settings.setValue("ui/show_links", config.get("show_links", True))
        self.settings.setValue("ui/show_tech_info", config.get("show_tech_info", True))
        self.settings.setValue(
            "ui/show_service_notifications",
            config.get("show_service_notifications", True),
        )
        self.settings.setValue(
            "ui/truncate_name_length", config.get("truncate_name_length", 20)
        )
        self.settings.setValue(
            "ui/truncate_quote_length", config.get("truncate_quote_length", 50)
        )
        self.settings.setValue(
            "ui/anonymizer_enabled", config.get("anonymizer_enabled", False)
        )
        self.settings.setValue(
            "ui/anonymizer_preset_id", config.get("anonymizer_preset_id", "default")
        )
        self.settings.setValue(
            "ui/show_activity_analysis", config.get("show_activity_analysis", False)
        )
        self.settings.setValue(
            "ui/analysis_unit", config.get("analysis_unit", "tokens")
        )
        self.settings.sync()

    def load_anonymizer_presets(self) -> list[dict[str, Any]]:
        self._migrate_presets_from_qsettings_if_needed()
        raw_presets = self._load_presets_from_files()
        service = self._get_anonymizer_service()
        return service.normalize_presets(raw_presets)

    def save_anonymizer_presets(self, presets: list[dict[str, Any]]):
        service = self._get_anonymizer_service()
        normalized = service.normalize_presets(presets)
        presets_dir = self._get_anonymizer_presets_dir()
        expected_files: set[Path] = set()
        for preset in normalized:
            preset_id = str(preset.get("id", "")).strip()
            if not preset_id:
                continue
            path = self._preset_file_path(preset_id)
            expected_files.add(path)
            path.write_text(json.dumps(preset, ensure_ascii=False, indent=2), encoding="utf-8")

        for existing in presets_dir.glob("*.json"):
            if existing not in expected_files:
                try:
                    existing.unlink()
                except Exception:
                    pass

        self.settings.setValue("anonymizer/presets", normalized)
        self.settings.sync()

    def add_anonymizer_preset(self, name: str) -> dict[str, Any]:
        service = self._get_anonymizer_service()
        presets = self.load_anonymizer_presets()
        preset = service.create_preset(name=name)
        presets.append(preset)
        self.save_anonymizer_presets(presets)
        return preset

    def update_anonymizer_preset(self, preset_id: str, updates: dict[str, Any]) -> bool:
        service = self._get_anonymizer_service()
        presets = self.load_anonymizer_presets()
        updated = False
        for idx, preset in enumerate(presets):
            if preset.get("id") == preset_id:
                merged = dict(preset)
                merged.update(updates or {})
                presets[idx] = merged
                updated = True
                break
        if updated:
            self.save_anonymizer_presets(service.normalize_presets(presets))
        return updated

    def delete_anonymizer_preset(self, preset_id: str) -> bool:
        if preset_id == "default":
            return False

        presets = self.load_anonymizer_presets()
        filtered = [preset for preset in presets if preset.get("id") != preset_id]
        if len(filtered) == len(presets):
            return False

        self.save_anonymizer_presets(filtered)
        try:
            self._preset_file_path(preset_id).unlink(missing_ok=True)
        except Exception:
            pass
        current_id = self.settings.value("ui/anonymizer_preset_id", "default", type=str)
        if current_id == preset_id:
            self.settings.setValue("ui/anonymizer_preset_id", "default")
            self.settings.sync()
        return True

    def load_ai_settings(self) -> dict:
        return {
            "load_on_startup": self.settings.value(
                "ai/load_on_startup", False, type=bool
            ),
            "tokenizer_model": self.settings.value(
                "ai/tokenizer_model", "google/gemma-2b", type=str
            ),
            "hf_token": self.settings.value("ai/hf_token", "", type=str) or "",
        }

    def save_ai_settings(self, config: dict):
        self.settings.setValue(
            "ai/load_on_startup", config.get("load_on_startup", False)
        )
        self.settings.setValue(
            "ai/tokenizer_model", config.get("tokenizer_model", "google/gemma-2b")
        )
        self.settings.setValue("ai/hf_token", config.get("hf_token", "") or "")
        self.settings.sync()

    def get_default_tokenizer_model(self) -> str:
        return "google/gemma-2b"

    def load_ui_font_mode(self) -> str:
        return self.settings.value("ui/font_mode", "builtin", type=str)

    def save_ui_font_mode(self, mode: str):
        self.settings.setValue("ui/font_mode", mode)
        self.settings.sync()

    def load_ui_font_family(self) -> str:
        return self.settings.value("ui/font_family", "", type=str)

    def save_ui_font_family(self, family: str):
        self.settings.setValue("ui/font_family", family)
        self.settings.sync()

    def save_ui_font_settings(self, mode: str, family: str = ""):
        self.save_ui_font_mode(mode)
        self.save_ui_font_family(family)

    def save_splitter_sizes(self, splitter_name: str, sizes: list):
        self.settings.setValue(f"layout/{splitter_name}_sizes", sizes)
        self.settings.sync()

    def load_splitter_sizes(self, splitter_name: str, default_sizes: list) -> list:
        return self.settings.value(f"layout/{splitter_name}_sizes", default_sizes, type=list)

    def load_main_window_geometry(self) -> QByteArray | None:
        raw = self.settings.value("main_window/geometry", None)
        if raw is None:
            return None
        if isinstance(raw, QByteArray) and not raw.isEmpty():
            return raw
        if isinstance(raw, (bytes, bytearray)):
            arr = QByteArray(raw)
            return arr if not arr.isEmpty() else None
        return None

    def save_main_window_geometry(self, geometry: QByteArray) -> None:
        if geometry.isEmpty():
            return
        self.settings.setValue("main_window/geometry", geometry)
        self.settings.sync()

    def _load_json_list(self, key: str, default: list) -> list:
        raw = self.settings.value(key, None)
        if raw is None:
            return default
        if isinstance(raw, list):
            return raw
        if isinstance(raw, str):
            try:
                decoded = json.loads(raw)
                return decoded if isinstance(decoded, list) else default
            except (TypeError, ValueError):
                pass
        return default

    def load_anonymization_settings(self) -> dict:
        def _bool(key: str, default: bool = False) -> bool:
            v = self.settings.value(key, default, type=bool)
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.strip().lower() in ("1", "true", "yes")
            return bool(v)

        return {
            "enabled": _bool("anonymization/enabled", False),
            "hide_links": _bool("anonymization/hide_links", False),
            "hide_names": _bool("anonymization/hide_names", False),
            "name_mask_format": self.settings.value(
                "anonymization/name_mask_format", "[ИМЯ {index}]", type=str
            ),
            "link_mask_mode": self.settings.value("anonymization/link_mask_mode", "simple"),
            "link_mask_format": self.settings.value("anonymization/link_mask_format", "[ССЫЛКА {index}]"),
            "active_preset": self.settings.value("anonymization/active_preset", None),
            "custom_filters": self._load_json_list("anonymization/custom_filters", []),
            "custom_names": self._load_json_list("anonymization/custom_names", []),
        }

    def save_anonymization_settings(self, config: dict):
        self.settings.setValue("anonymization/enabled", config.get("enabled", False))
        self.settings.setValue("anonymization/hide_links", config.get("hide_links", False))
        self.settings.setValue("anonymization/hide_names", config.get("hide_names", False))
        self.settings.setValue(
            "anonymization/name_mask_format",
            config.get("name_mask_format", "[ИМЯ {index}]"),
        )
        self.settings.setValue("anonymization/link_mask_mode", config.get("link_mask_mode", "simple"))
        self.settings.setValue("anonymization/link_mask_format", config.get("link_mask_format", "[ССЫЛКА {index}]"))
        self.settings.setValue("anonymization/active_preset", config.get("active_preset"))
        custom_filters = config.get("custom_filters", [])
        custom_names = config.get("custom_names", [])
        self.settings.setValue("anonymization/custom_filters", json.dumps(custom_filters, ensure_ascii=False))
        self.settings.setValue("anonymization/custom_names", json.dumps(custom_names, ensure_ascii=False))
        self.settings.sync()
