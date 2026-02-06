import json
import os
import logging
from shared_toolkit.utils.paths import resource_path

logger = logging.getLogger("Tkonverter")

class TranslationManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._translations = {}
            cls._instance._current_lang = "ru"

            cls._instance.load_language("ru")
        return cls._instance

    def load_language(self, lang_code):
        if lang_code == self._current_lang and self._translations:
            return

        try:
            base_path = resource_path("resources/i18n")
            file_path = os.path.join(base_path, f"{lang_code}.json")

            if not os.path.exists(file_path):
                logger.warning(f"Translation file not found: {file_path}. Falling back to EN.")
                file_path = os.path.join(base_path, "en.json")
                if not os.path.exists(file_path):
                    logger.error(f"English translation file also not found: {file_path}")
                    logger.error(f"Base path: {base_path}, exists: {os.path.exists(base_path)}")
                    if os.path.exists(base_path):
                        logger.error(f"Files in base_path: {os.listdir(base_path)}")
                    self._translations = {}
                    return

            with open(file_path, 'r', encoding='utf-8') as f:
                self._translations = json.load(f)
                self._current_lang = lang_code
                logger.info(f"Loaded {len(self._translations)} translations from {file_path}")
        except Exception as e:
            logger.error(f"Failed to load translations from {file_path}: {e}", exc_info=True)
            self._translations = {}

    def get(self, text, *args, **kwargs):
        translated = self._translations.get(text, text)

        if args or kwargs:
            try:
                return translated.format(*args, **kwargs)
            except Exception:
                return translated
        return translated

    def get_current_language(self) -> str:
        return self._current_lang

    def set_language(self, lang_code: str):
        self.load_language(lang_code)

_manager = TranslationManager()

def tr(text, language=None, *args, **kwargs):
    if language is None:
        language = _manager.get_current_language()

    _manager.load_language(language)
    return _manager.get(text, *args, **kwargs)

def set_language(lang_code: str):
    """Set the current language for translations."""
    _manager.set_language(lang_code)

def get_language() -> str:
    """Get the current language code."""
    return _manager.get_current_language()
