import os
from pathlib import Path

from PyQt6.QtCore import QLocale, QSettings

class SettingsManager:
    def __init__(self, organization_name: str, application_name: str):
        self.settings = QSettings(organization_name, application_name)

    def load_theme(self) -> str:
        theme = self.settings.value("theme", "auto", type=str)
        return theme

    def save_theme(self, theme: str):
        self.settings.setValue("theme", theme)
        self.settings.sync()

    def load_language(self) -> str:
        """
        Loads the saved language. If not set, autodetects the system language.
        """

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
        """Loads permanent debug mode setting."""
        return self.settings.value("debug/enabled", False, type=bool)

    def save_debug_mode(self, enabled: bool):
        """Saves permanent debug mode setting."""
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
        self.settings.sync()

    def load_ai_settings(self) -> dict:
        return {
            "load_on_startup": self.settings.value(
                "ai/load_on_startup", False, type=bool
            ),
            "tokenizer_model": self.settings.value(
                "ai/tokenizer_model", "google/gemma-2b", type=str
            ),
        }

    def save_ai_settings(self, config: dict):
        self.settings.setValue(
            "ai/load_on_startup", config.get("load_on_startup", False)
        )
        self.settings.setValue(
            "ai/tokenizer_model", config.get("tokenizer_model", "google/gemma-2b")
        )
        self.settings.sync()

    def get_default_tokenizer_model(self) -> str:
        return "google/gemma-2b"

    def load_ui_font_mode(self) -> str:
        """Load UI font mode."""
        return self.settings.value("ui/font_mode", "builtin", type=str)

    def save_ui_font_mode(self, mode: str):
        """Save UI font mode."""
        self.settings.setValue("ui/font_mode", mode)
        self.settings.sync()

    def load_ui_font_family(self) -> str:
        """Load UI font family."""
        return self.settings.value("ui/font_family", "", type=str)

    def save_ui_font_family(self, family: str):
        """Save UI font family."""
        self.settings.setValue("ui/font_family", family)
        self.settings.sync()

    def save_ui_font_settings(self, mode: str, family: str = ""):
        """Save UI font settings."""
        self.save_ui_font_mode(mode)
        self.save_ui_font_family(family)
