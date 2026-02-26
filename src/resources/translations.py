import json
import logging
import os
from collections.abc import Mapping
from typing import Any

from src.shared_toolkit.utils.paths import resource_path

logger = logging.getLogger("Tkonverter")

class TranslationManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._current_lang = "ru"
            cls._instance._translations_cache: dict[str, dict[str, str]] = {}
            cls._instance._translations: dict[str, str] = {}
            cls._instance._missing_keys_logged: set[tuple[str, str]] = set()
            cls._instance.load_language("ru")
        return cls._instance

    def _flatten_translations(
        self, data: Mapping[str, Any], prefix: str = ""
    ) -> dict[str, str]:
        flat: dict[str, str] = {}
        for key, value in data.items():
            key_str = str(key)
            full_key = f"{prefix}.{key_str}" if prefix else key_str
            if isinstance(value, Mapping):
                flat.update(self._flatten_translations(value, prefix=full_key))
            else:
                flat[full_key] = str(value)
        return flat

    def _load_file_dict(self, lang_code: str) -> dict[str, str]:
        base_path = resource_path("resources/i18n")
        file_path = os.path.join(base_path, f"{lang_code}.json")
        source_lang = lang_code

        if not os.path.exists(file_path):
            logger.warning(
                f"Translation file not found: {file_path}. Falling back to EN."
            )
            source_lang = "en"
            file_path = os.path.join(base_path, "en.json")

        if not os.path.exists(file_path):
            logger.error(f"English translation file also not found: {file_path}")
            return {}

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                loaded = json.load(file)
        except Exception as exc:
            logger.error(
                f"Failed to load translations from {file_path}: {exc}", exc_info=True
            )
            return {}

        if not isinstance(loaded, Mapping):
            logger.error(f"Invalid translation format in {file_path}: expected object")
            return {}

        flat = self._flatten_translations(loaded)
        if source_lang != lang_code:
            logger.info(
                f"Loaded fallback translations for {lang_code} from {source_lang}: {len(flat)} keys"
            )
        return flat

    def _ensure_language_loaded(self, lang_code: str) -> dict[str, str]:
        if lang_code not in self._translations_cache:
            self._translations_cache[lang_code] = self._load_file_dict(lang_code)
        return self._translations_cache[lang_code]

    def load_language(self, lang_code: str):
        lang_dict = self._ensure_language_loaded(lang_code)
        self._current_lang = lang_code
        self._translations = lang_dict
        logger.info(f"Loaded language '{lang_code}' with {len(lang_dict)} translation keys")

    def _resolve_raw(self, key: str, lang_code: str) -> str | None:
        lang_dict = self._ensure_language_loaded(lang_code)
        en_dict = self._ensure_language_loaded("en")

        if key in lang_dict:
            return lang_dict[key]
        if key in en_dict:
            return en_dict[key]

        missing_marker = (lang_code, key)
        if missing_marker not in self._missing_keys_logged:
            self._missing_keys_logged.add(missing_marker)
            logger.warning(f"Missing translation key '{key}' for language '{lang_code}'")
        return None

    def get(self, key: str, lang_code: str, *args, **kwargs) -> str:
        translated = self._resolve_raw(key, lang_code)
        if translated is None:
            translated = key

        if args or kwargs:
            try:
                return translated.format(*args, **kwargs)
            except Exception as exc:
                logger.warning(
                    f"Failed to format translation key '{key}' for lang '{lang_code}': {exc}"
                )
                return translated
        return translated

    def get_current_language(self) -> str:
        return self._current_lang

    def set_language(self, lang_code: str):
        if lang_code != self._current_lang:
            self.load_language(lang_code)

_manager = TranslationManager()

def tr(key: str, language: str | None = None, *args, **kwargs) -> str:
    lang_code = language or _manager.get_current_language()
    return _manager.get(key, lang_code, *args, **kwargs)

def set_language(lang_code: str):
    _manager.set_language(lang_code)

def get_language() -> str:
    return _manager.get_current_language()
