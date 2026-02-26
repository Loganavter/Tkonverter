from typing import Any, Dict, Optional, Set

from PyQt6.QtCore import QObject, pyqtSignal

import logging

from src.core.analysis.tree_analyzer import TreeNode
from src.core.application.analysis_service import AnalysisService
from src.core.application.anonymizer_service import AnonymizerService
from src.core.application.chat_service import ChatService
from src.core.application.calendar_service import CalendarService
from src.core.application.chat_memory_service import ChatMemoryService
from src.core.application.conversion_service import ConversionService
from src.core.application.chart_service import ChartService
from src.core.application.tokenizer_service import TokenizerService
from src.core.conversion.utils import markdown_to_html_for_preview
from src.core.domain.models import AnalysisResult, Chat
from src.core.settings_port import SettingsPort
from src.presenters.action_presenter import ActionPresenter
from src.presenters.analysis_presenter import AnalysisPresenter
from src.presenters.app_state import AppState
from src.presenters.config_presenter import ConfigPresenter
from src.presenters.file_presenter import FilePresenter
from src.presenters.preview_service import PreviewService
from src.resources.translations import tr

logger = logging.getLogger(__name__)

class MainPresenter(QObject):

    chat_loaded = pyqtSignal(bool, str, str)
    profile_auto_detected = pyqtSignal(str)
    config_changed = pyqtSignal(str, object)
    analysis_unit_changed = pyqtSignal(str)
    preview_updated = pyqtSignal(str, str)
    save_completed = pyqtSignal(bool, str)
    analysis_count_updated = pyqtSignal(int, str, bool)
    analysis_completed = pyqtSignal(object)
    tokenizer_changed = pyqtSignal()
    tokenizer_loading_started = pyqtSignal(str)
    tokenizer_loaded = pyqtSignal(object, str)
    tokenizer_load_failed = pyqtSignal(str)
    disabled_nodes_changed = pyqtSignal(set)
    language_changed = pyqtSignal()

    set_drop_zone_style_command = pyqtSignal(str)

    def __init__(
        self,
        view,
        settings_manager: SettingsPort,
        theme_manager,
        font_manager,
        app_instance,
        initial_theme: str,
        initial_config: dict,
        chat_service: ChatService,
        conversion_service: ConversionService,
        analysis_service: AnalysisService,
        tokenizer_service: TokenizerService,
        anonymizer_service: AnonymizerService,
        preview_service: PreviewService,
        chart_service: ChartService,
        calendar_service: CalendarService,
        chat_memory_service: ChatMemoryService,
    ):
        super().__init__()

        self._view = view
        self._settings_manager = settings_manager
        self._theme_manager = theme_manager
        self._font_manager = font_manager
        self._app = app_instance

        self._current_session_theme = initial_theme

        initial_config["partner_name"] = ""

        self._app_state = AppState(ui_config=initial_config, chart_service=chart_service)

        self._chat_service = chat_service
        self._conversion_service = conversion_service
        self._analysis_service = analysis_service
        self._tokenizer_service = tokenizer_service
        self._anonymizer_service = anonymizer_service
        self._preview_service = preview_service
        self._chart_service = chart_service
        self._calendar_service = calendar_service
        self._chat_memory_service = chat_memory_service

        self._anonymization_dialog = None

        self._initialize_child_presenters()

        self._connect_signals()

        self._try_load_default_tokenizer()

        self._update_analysis_unit()

        self._view.show_status(message_key="Ready to work", is_status=True)

    def _initialize_child_presenters(self):
        self.config_presenter = ConfigPresenter(
            self._view,
            self._app_state,
            self._preview_service
        )

        self.file_presenter = FilePresenter(
            self._view,
            self._app_state,
            self._chat_service,
            self._preview_service
        )

        self.analysis_presenter = AnalysisPresenter(
            self._view,
            self._app_state,
            self._analysis_service,
            self._chat_service,
            self._theme_manager,
            self._calendar_service,
            self._chart_service,
            self._chat_memory_service,
            self._settings_manager,
            tokenizer_service=self._tokenizer_service,
        )

        self.action_presenter = ActionPresenter(
            self._view,
            self._app_state,
            self._conversion_service,
            self._tokenizer_service,
            self._settings_manager,
            self._theme_manager,
            self._app,
            self._font_manager,
        )

    def _connect_signals(self):
        logger.debug("Connecting signals in MainPresenter...")

        self.file_presenter.chat_loaded.connect(self.chat_loaded.emit)
        self.file_presenter.chat_loaded.connect(self._on_chat_load_finished)
        self.file_presenter.profile_auto_detected.connect(self.profile_auto_detected.emit)
        self.file_presenter.preview_updated.connect(self.preview_updated.emit)
        self.file_presenter.set_drop_zone_style_command.connect(self.set_drop_zone_style_command.emit)

        self.config_presenter.config_changed.connect(self.config_changed.emit)
        self.config_presenter.profile_auto_detected.connect(self.profile_auto_detected.emit)
        self.config_presenter.preview_updated.connect(self.preview_updated.emit)

        self.config_presenter.config_changed.connect(self.analysis_presenter.on_config_value_changed_for_update)

        self.analysis_presenter.analysis_count_updated.connect(
            lambda c, u, f: self.analysis_count_updated.emit(c, u, f)
        )
        self.analysis_presenter.analysis_completed.connect(self.analysis_completed.emit)
        self.analysis_presenter.disabled_nodes_changed.connect(self.disabled_nodes_changed.emit)

        self.action_presenter.save_completed.connect(self.save_completed.emit)
        self.action_presenter.language_changed.connect(self.language_changed.emit)
        self.action_presenter.tokenizer_changed.connect(lambda: self._update_analysis_unit())
        self.action_presenter.tokenizer_changed.connect(self.tokenizer_changed.emit)
        self.action_presenter.analysis_unit_changed.connect(self._update_analysis_unit)

        self._theme_manager.theme_changed.connect(self._on_app_theme_changed)

        self._view.anonymization_button_clicked.connect(self.on_anonymization_clicked)

        self._view.recalculate_clicked.connect(self.on_recalculate_clicked)
        self._view.calendar_button_clicked.connect(self.on_calendar_clicked)
        self._view.diagram_button_clicked.connect(self.on_diagram_clicked)
        self._view.save_button_clicked.connect(self.on_save_clicked)
        self._view.settings_button_clicked.connect(self.on_settings_clicked)
        self._view.install_manager_button_clicked.connect(self.on_install_manager_clicked)
        self._view.help_button_clicked.connect(self.on_help_clicked)

        logger.debug("Signals connected successfully.")

    def is_analysis_count_log_suppressed(self) -> bool:
        return self.analysis_presenter.is_analysis_log_suppressed()

    def _try_load_default_tokenizer(self):
        if not self._tokenizer_service.is_transformers_available():
            return

        settings = self._settings_manager.load_ai_settings()
        load_on_startup = settings.get("load_on_startup", True)
        if not load_on_startup:
            return

        default_model = self._tokenizer_service.get_default_model_name()

        cache_info = self._tokenizer_service.check_model_cache(default_model)
        if not cache_info.get("available", False):
            return

        try:
            tokenizer = self._tokenizer_service.load_tokenizer(
                default_model, local_only=True, progress_callback=None
            )

            self._app_state.set_tokenizer(tokenizer, default_model)
            self._update_analysis_unit()
            self.tokenizer_changed.emit()

        except Exception as e:
            pass

    def _update_analysis_unit(self):
        new_unit = self._app_state.get_preferred_analysis_unit()
        logger.debug(
            "analysis_unit _update_analysis_unit: new_unit=%r, last_analysis_unit=%r",
            new_unit,
            self._app_state.last_analysis_unit,
        )
        if self._app_state.last_analysis_unit != new_unit:
            self._app_state.last_analysis_unit = new_unit

            if self._app_state.has_analysis_data():
                self._app_state.clear_analysis()
                self.analysis_count_updated.emit(-1, "chars", False)
            self.analysis_unit_changed.emit(new_unit)

    def _on_app_theme_changed(self):
        new_palette = self._app.palette()
        if hasattr(self._view, "apply_app_theme"):
            self._view.apply_app_theme(new_palette)

        self.action_presenter.apply_theme_to_open_dialogs(new_palette)
        self.analysis_presenter.apply_theme_to_open_dialogs(new_palette)

        self.language_changed.emit()

    def get_longest_preview_html(self) -> str:
        return self._preview_service.get_longest_preview_html(self._app_state.ui_config)

    def render_preview_html(self, raw_text: str) -> str:
        return markdown_to_html_for_preview(raw_text)

    def get_current_chat(self) -> Optional[Chat]:
        return self._app_state.loaded_chat

    def get_analysis_result(self) -> Optional[AnalysisResult]:
        return self._app_state.analysis_result

    def get_analysis_tree(self) -> Optional[TreeNode]:
        return self._app_state.analysis_tree

    def get_config(self) -> Dict[str, Any]:
        return self._app_state.ui_config.copy()

    def get_config_value(self, key: str, default: Any = None) -> Any:
        return self._app_state.get_config_value(key, default)

    def get_analysis_unit(self) -> str:
        return self._app_state.last_analysis_unit

    def get_analysis_display_model(self) -> Dict[str, Any]:
        unit = self._app_state.last_analysis_unit
        label_key = "Tokens:" if unit == "tokens" else "Characters:"
        if not self._app_state.has_analysis_data():
            return {
                "label_key": label_key,
                "total_text": "N/A",
                "filtered_text": "",
                "show_filtered": False,
            }

        total = self._app_state.analysis_result.total_count
        filtered = self._app_state.get_filtered_count()
        has_filter = self._app_state.has_disabled_nodes() and filtered != total
        return {
            "label_key": label_key,
            "total_text": f"<s>{total:,}</s>" if has_filter else f"{total:,}",
            "filtered_text": f"→ {filtered:,}" if has_filter else "",
            "show_filtered": has_filter,
        }

    def get_analysis_message_key(self, unit: str) -> str:
        return "Tokens calculated: {count}" if unit == "tokens" else "Characters calculated: {count}"

    def get_disabled_nodes(self) -> Set[TreeNode]:
        return self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree) if self._app_state.analysis_tree else set()

    def has_chat_loaded(self) -> bool:
        return self._app_state.has_chat_loaded()

    def get_app_state(self) -> AppState:
        return self._app_state

    def save_ui_state(self) -> None:
        current_config = self.get_config()
        existing_ui_settings = self._settings_manager.load_ui_settings()
        existing_ui_settings.update(current_config)
        self._settings_manager.save_ui_settings(existing_ui_settings)

    def refresh_preview(self) -> None:
        self._generate_preview()

    def get_current_file_path(self) -> Optional[str]:
        return self._chat_service.get_current_file_path()

    def update_disabled_nodes(self, new_disabled_set: Set[TreeNode]):
        self.analysis_presenter.update_disabled_nodes(new_disabled_set)

    def on_file_dropped(self, path: str):
        self.file_presenter.on_file_dropped(path)

    def on_drop_zone_hover_state_changed(self, is_hovered: bool):
        self.file_presenter.on_drop_zone_hover_state_changed(is_hovered)

    def on_drop_zone_drag_active(self, is_active: bool):
        self.file_presenter.on_drop_zone_drag_active(is_active)

    def on_config_changed(self, key: str, value: Any):
        self.config_presenter.on_config_changed(key, value)

    def handle_profile_auto_detection(self, detected_profile: str):
        self.config_presenter.handle_profile_auto_detection(detected_profile)

    def on_recalculate_clicked(self):
        self.analysis_presenter.on_recalculate_clicked()

    def on_calendar_clicked(self):
        self.analysis_presenter.on_calendar_clicked()

    def on_diagram_clicked(self):
        self.analysis_presenter.on_diagram_clicked()

    def on_save_clicked(self):
        self.action_presenter.on_save_clicked()

    def on_settings_clicked(self):
        self.action_presenter.on_settings_clicked()

    def on_install_manager_clicked(self):
        self.action_presenter.on_install_manager_clicked()

    def on_help_clicked(self):
        self.action_presenter.on_help_clicked()

    def _on_chat_load_finished(self, success: bool, message: str, chat_name: str):
        if success:
            try:
                chat_id = getattr(self._app_state.loaded_chat, "chat_id", None)
                if chat_id is not None and self._chat_memory_service:
                    memory_keys = self._chat_memory_service.get_disabled_dates(chat_id)
                    self._app_state.set_disabled_dates_from_memory(memory_keys)
                if self._app_state.has_analysis_data():
                    count = self._app_state.get_filtered_count()
                    self.analysis_count_updated.emit(count, self._app_state.last_analysis_unit, False)

                preset_id = self._app_state.get_config_value("anonymizer_preset_id", "default")
                if preset_id == "default":
                    anon_config = self._settings_manager.load_anonymization_settings()
                    anon_config["custom_filters"] = []
                    anon_config["custom_names"] = []
                    self._settings_manager.save_anonymization_settings(anon_config)
                    self._app_state.ui_config["anonymization"] = anon_config

                if chat_name:

                    self._app_state.ui_config["partner_name"] = "__FORCE_UPDATE__"

                    self._app_state.set_config_value("partner_name", chat_name)
                    self.config_changed.emit("partner_name", chat_name)

                    self._generate_preview()

                if self._app_state.get_config_value("auto_recalc", False):
                    self.on_recalculate_clicked()

            except Exception as e:
                logger.error(f"Error in MainPresenter._on_chat_load_finished: {e}", exc_info=True)

    def on_anonymization_clicked(self):
        try:
            if self._anonymization_dialog is not None and self._anonymization_dialog.isVisible():
                self._view.bring_dialog_to_front(self._anonymization_dialog, "anonymization")
                return

            anonymization_config = self._settings_manager.load_anonymization_settings()
            current_anon = self._app_state.get_config_value("anonymization") or {}
            anonymization_config["enabled"] = current_anon.get(
                "enabled", anonymization_config.get("enabled", False)
            )
            known_names = []
            known_domains = []

            if self._app_state.has_chat_loaded() and self._app_state.loaded_chat:
                chat = self._app_state.loaded_chat
                users = chat.get_users()
                known_names = [u.name for u in users if u.name]
                try:
                    known_domains = self._anonymizer_service.extract_unique_domains(chat)
                except Exception:
                    pass

            dialog = self._view.create_anonymization_dialog(
                current_config=anonymization_config,
                known_names=known_names,
                known_domains=known_domains,
            )
            dialog.accepted.connect(self._on_anonymization_dialog_accepted)
            dialog.destroyed.connect(self._on_anonymization_dialog_destroyed)
            self._anonymization_dialog = dialog
            dialog.show()

        except Exception as e:
            logger.exception("CRITICAL ERROR opening anonymization dialog")
            self._view.show_status(message="Error opening anonymization settings", is_error=True)

    def _on_anonymization_dialog_accepted(self):
        if self._anonymization_dialog is None:
            return
        try:
            new_config = self._anonymization_dialog.get_config()
            self._settings_manager.save_anonymization_settings(new_config)
            self.config_presenter.on_config_changed("anonymization", new_config)
        except Exception as e:
            logger.exception("Error applying anonymization settings: %s", e)
            self._view.show_status(message="Error applying anonymization settings", is_error=True)

    def _on_anonymization_dialog_destroyed(self):
        self._anonymization_dialog = None

    def _generate_preview(self):
        try:
            config = self._app_state.ui_config
            raw_text, title = self._preview_service.generate_preview_text(config)
            self.preview_updated.emit(raw_text, title)
        except Exception as e:
            error_message = f"Error: {e}"
            self.preview_updated.emit(error_message, "Preview Error")
