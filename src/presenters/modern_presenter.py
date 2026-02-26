import logging
import re
from typing import Any, Dict, Optional, Set

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

from core.analysis.tree_analyzer import TreeNode
from core.application.anonymizer_service import AnonymizerService
from core.application.analysis_service import AnalysisService
from core.application.chart_service import ChartService
from core.application.chat_service import ChatService
from core.application.conversion_service import ConversionService
from core.application.tokenizer_service import TokenizerService
from core.conversion.domain_adapters import chat_to_dict
from core.settings_port import SettingsPort
from presenters.preview_service import PreviewService
from presenters.calendar_presenter import CalendarPresenter
from presenters.workers import (
    ChatLoadWorker, ConversionWorker, AnalysisWorker,
    TreeBuildWorker, TokenizerLoadWorker, AIInstallerWorker
)
from presenters.task_manager import CancellableTaskManager
from core.domain.models import AnalysisResult, Chat
from presenters.app_state import AppState
from src.resources.translations import set_language, tr

preview_logger = logging.getLogger("Preview")
preview_logger.setLevel(logging.ERROR)

logger = logging.getLogger("ModernPresenter")

if not preview_logger.handlers:
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)
    console_handler.setFormatter(formatter)

    preview_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)

class ModernTkonverterPresenter(QObject):

    chat_loaded = pyqtSignal(bool, str, str)
    profile_auto_detected = pyqtSignal(str)
    config_changed = pyqtSignal(str, object)
    analysis_unit_changed = pyqtSignal(str)
    preview_updated = pyqtSignal(str, str)
    save_completed = pyqtSignal(bool, str)
    analysis_count_updated = pyqtSignal(int, str)
    analysis_completed = pyqtSignal(TreeNode)
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
    ):
        super().__init__()

        self._view = view
        self._settings_manager = settings_manager
        self._theme_manager = theme_manager
        self._font_manager = font_manager
        self._app = app_instance

        self._current_session_theme = initial_theme

        self._app_state = AppState(ui_config=initial_config, chart_service=chart_service)

        self._chat_service = chat_service
        self._conversion_service = conversion_service
        self._analysis_service = analysis_service
        self._tokenizer_service = tokenizer_service
        self._anonymizer_service = anonymizer_service
        self._preview_service = preview_service

        self._settings_dialog = None
        self._analysis_dialog = None
        self._install_dialog = None
        self._calendar_dialog = None
        self._help_dialog = None

        self._install_process = None
        self._installer_worker = None

        self._threadpool = QThreadPool()
        self._current_workers = []

        self.analysis_task_manager = CancellableTaskManager(AnalysisWorker)

        self._connect_signals()

        self._try_load_default_tokenizer()

        self._is_drop_zone_hovered = False
        self._is_drop_zone_drag_active = False
        self._view.show_status(message_key="Ready to work", is_status=True)

    def _connect_signals(self):

        self._view.config_changed.connect(self.on_config_changed)
        self._view.save_button_clicked.connect(self.on_save_clicked)
        self._view.settings_button_clicked.connect(self.on_settings_clicked)
        self._view.install_manager_button_clicked.connect(
            self.on_install_manager_clicked
        )
        self._view.recalculate_clicked.connect(self.on_recalculate_clicked)
        self._view.calendar_button_clicked.connect(self.on_calendar_clicked)
        self._view.diagram_button_clicked.connect(self.on_diagram_clicked)
        self._view.help_button_clicked.connect(self.on_help_clicked)

        self._theme_manager.theme_changed.connect(self._on_app_theme_changed)

        self.analysis_task_manager.finished.connect(self._on_analysis_finished)
        self.analysis_task_manager.progress.connect(self._view.show_status)

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
            logger.warning(f"Failed to load tokenizer {default_model}: {e}")
            pass

    def _update_analysis_unit(self):
        new_unit = self._app_state.get_preferred_analysis_unit()

        if self._app_state.last_analysis_unit != new_unit:
            self._app_state.last_analysis_unit = new_unit
            self.analysis_unit_changed.emit(new_unit)

    def _on_install_dialog_destroyed(self):
        self._install_dialog = None
        self._update_analysis_unit()

    def _generate_preview(self):
        try:
            config = self._app_state.ui_config
            raw_text, title = self._preview_service.generate_preview_text(config)
            self.preview_updated.emit(raw_text, title)

        except Exception as e:
            preview_logger.error(f"=== PREVIEW GENERATION ERROR ===")
            preview_logger.error(f"Error type: {type(e).__name__}")
            preview_logger.error(f"Error message: {e}")
            import traceback
            preview_logger.error(f"Traceback: {traceback.format_exc()}")

            error_message = f"Error: {e}"
            self.preview_updated.emit(error_message, "Preview Error")

    def get_longest_preview_html(self) -> str:
        try:
            config = self._app_state.ui_config.copy()
            return self._preview_service.get_longest_preview_html(config)

        except Exception as e:
            preview_logger.error(f"=== LONGEST PREVIEW GENERATION ERROR ===")
            preview_logger.error(f"Error type: {type(e).__name__}")
            preview_logger.error(f"Error message: {e}")
            import traceback
            preview_logger.error(f"Traceback: {traceback.format_exc()}")
            return ""

    def on_file_dropped(self, path: str):

        if self._app_state.is_processing:
            logger.warning("Application is already processing a file, ignoring new one")
            return

        self.set_processing_state_in_view(True, message_key="Loading file...")

        worker = ChatLoadWorker(self._chat_service, path)
        worker.signals.progress.connect(self._view.show_status)
        worker.signals.finished.connect(
            lambda s, m, r, fp, w=worker: self._on_chat_load_finished(s, m, r, fp, w)
        )

        self._current_workers.append(worker)
        self._threadpool.start(worker)

    def _on_chat_load_finished(
        self,
        success: bool,
        message: str,
        result: Optional[Chat],
        file_path: str = "",
        worker=None,
    ):
        """Handles chat loading completion."""
        try:
            self.set_processing_state_in_view(False)

            if success and result:
                if self._app_state.get_config_value("anonymizer_enabled", False):
                    presets = self._settings_manager.load_anonymizer_presets()
                    preset_id = self._app_state.get_config_value(
                        "anonymizer_preset_id", "default"
                    )
                    selected_preset = self._anonymizer_service.get_preset_by_id(
                        presets, preset_id
                    )
                    result = self._anonymizer_service.anonymize_chat(result, selected_preset)

                auto_detect_enabled = self._app_state.get_config_value("auto_detect_profile", True)

                if auto_detect_enabled:
                    detected_profile = self._chat_service.detect_chat_type(result)

                    current_profile = self._app_state.get_config_value("profile")

                    if detected_profile != current_profile:

                        self._app_state.set_config_value("profile", detected_profile)
                        self.profile_auto_detected.emit(detected_profile)
                else:
                    pass

                path_for_state = file_path if file_path else self._chat_service.get_current_file_path()
                self._app_state.set_chat(result, path_for_state)

                preset_id = self._app_state.get_config_value("anonymizer_preset_id", "default")
                if preset_id == "default":
                    anon_config = self._settings_manager.load_anonymization_settings()
                    anon_config["custom_filters"] = []
                    anon_config["custom_names"] = []
                    self._settings_manager.save_anonymization_settings(anon_config)
                    if "anonymization" in self._app_state.ui_config:
                        self._app_state.ui_config["anonymization"] = anon_config

                if auto_detect_enabled:
                    self._generate_preview()

                chat_name = self._app_state.get_chat_name()

                self.chat_loaded.emit(True, "", chat_name)

                if self._app_state.get_config_value("auto_recalc", False):
                    self.on_recalculate_clicked()

            else:
                self.chat_loaded.emit(False, message, "")
        finally:
            if worker is not None:
                try:
                    self._current_workers.remove(worker)
                except ValueError:
                    pass

    def on_config_changed(self, key: str, value: Any):
        old_value = self._app_state.get_config_value(key)

        if old_value != value:

            had_analysis_data_before = self._app_state.has_analysis_data()

            self._app_state.set_config_value(key, value)

            self.config_changed.emit(key, value)

            if not self._app_state.has_analysis_data():

                self.analysis_count_updated.emit(-1, "chars")

                if had_analysis_data_before:
                    unit = self._app_state.get_preferred_analysis_unit()
                    if unit == "tokens":
                        self._view.show_status(message_key="Tokens reset", is_status=True)
                    else:
                        self._view.show_status(message_key="Characters reset", is_status=True)

            if key not in ["disabled_nodes"]:
                self._generate_preview()

            if (self._app_state.get_config_value("auto_recalc", False) and
                self._app_state.has_chat_loaded() and
                not self._app_state.is_processing and
                key not in ["auto_detect_profile", "auto_recalc", "disabled_nodes"]):

                self.on_recalculate_clicked()

    def on_save_clicked(self):
        if self._app_state.is_processing:
            return

        if not self._app_state.has_chat_loaded():
            self._view.show_status(message_key="Please load a JSON file first.", is_error=True)
            return

        chat_name = self._app_state.get_chat_name()
        sanitized_name = re.sub(r'[\\/*?:"<>|]', "_", chat_name)[:80]
        from utils.file_utils import get_unique_filepath
        try:
            options = self._view.exec_export_dialog(
                suggested_filename=sanitized_name,
                get_unique_path_func=get_unique_filepath,
            )
            if not options:
                return
        except Exception as e:
            logger.error(f"Error opening export dialog: {e}")
            return

        output_dir, file_name = options["output_dir"], options["file_name"]
        use_default = options["use_default_dir"]
        self._settings_manager.save_export_default_dir(
            use_default_dir=use_default, default_dir=output_dir
        )
        final_path = get_unique_filepath(output_dir, file_name, ".txt")

        self.set_processing_state_in_view(True, message_key="Saving file...")
        worker = ConversionWorker(
            self._conversion_service,
            self._app_state.loaded_chat,
            self._app_state.ui_config.copy(),
            final_path,
            self._app_state.disabled_time_nodes,
        )
        worker.signals.finished.connect(
            lambda s, p, r, w=worker: self._on_save_finished(s, p, r, w)
        )
        self._current_workers.append(worker)
        self._threadpool.start(worker)

    def _on_save_finished(
        self, success: bool, path_or_error: str, result: Any, worker=None
    ):
        try:
            self.set_processing_state_in_view(False)

            if success:
                self._view.show_status(
                    message_key="File saved: {path}",
                    format_args={"path": path_or_error},
                )
            else:
                self._view.show_status(
                    is_error=True,
                    message_key="Error saving file: {error}",
                    format_args={"error": path_or_error},
                )
        finally:
            if worker is not None:
                try:
                    self._current_workers.remove(worker)
                except ValueError:
                    pass

    def on_recalculate_clicked(self):
        if not self._app_state.has_chat_loaded():
            self._view.show_status(message_key="Please load a JSON file first.", is_error=True)
            return

        self.set_processing_state_in_view(True, message_key="Calculating...")

        self.analysis_task_manager.submit(
            analysis_service=self._analysis_service,
            chat=self._app_state.loaded_chat,
            config=self._app_state.ui_config.copy(),
            tokenizer=self._app_state.tokenizer,
        )

    def _on_analysis_finished(
        self, success: bool, message: str, result: Optional[AnalysisResult]
    ):
        """Handles analysis completion."""

        if self.analysis_task_manager._pending_args is None:
            self.set_processing_state_in_view(False)

        if success and result:
            self._app_state.set_analysis_result(result)
            self.analysis_count_updated.emit(result.total_count, self._app_state.last_analysis_unit)
        else:

            if message != "Cancelled":
                self._view.show_status(
                    message_key="Analysis failed or no data found.",
                    is_error=True
                )
                self.analysis_count_updated.emit(-1, "chars")

    def on_diagram_clicked(self):
        if self._app_state.is_processing:
            return

        if not self._app_state.has_chat_loaded():
            self._view.show_status(message_key="Please load a JSON file first.", is_error=True)
            return

        if not self._is_personal_activity_allowed():
            self._view.show_status(
                "Анализ активности доступен только для личных чатов.",
                is_error=True,
            )
            return

        if not self._app_state.has_analysis_data():

            self._view.show_message_box(
                tr("analysis.title"),
                tr("analysis.recalc_first"),
                QMessageBox.Icon.Information
            )
            return

        if not self._app_state.analysis_tree:

            self.set_processing_state_in_view(True, message_key="Building analysis tree...")

            worker = TreeBuildWorker(
                self._analysis_service,
                self._app_state.analysis_result,
                self._app_state.ui_config.copy(),
            )
            worker.signals.finished.connect(
                lambda s, m, r, w=worker: self._on_tree_build_finished(s, m, r, w)
            )

            self._current_workers.append(worker)
            self._threadpool.start(worker)
        else:
            self._show_analysis_dialog()

    def _is_personal_activity_allowed(self) -> bool:
        if not self._app_state.has_chat_loaded() or not self._app_state.loaded_chat:
            return False
        profile = self._app_state.get_config_value("profile", "group")
        chat_type = self._chat_service.detect_chat_type(self._app_state.loaded_chat)
        return profile == "personal" and chat_type == "personal"

    def on_help_clicked(self):
        if self._help_dialog is not None:
            try:
                self._view.bring_dialog_to_front(self._help_dialog, "help")
                return
            except RuntimeError:
                self._help_dialog = None

        if self._help_dialog is None:
            try:
                sections = [
                    ("help_introduction", "introduction"),
                    ("help_files", "files"),
                    ("help_conversion", "conversion"),
                    ("help_analysis", "analysis"),
                    ("help_ai", "ai"),
                    ("help_export", "export"),
                ]
                self._help_dialog = self._view.create_help_dialog(
                    sections=sections,
                    current_language=self._settings_manager.load_language(),
                    app_name="Tkonverter",
                )
                self.language_changed.connect(self._help_dialog.retranslate_ui)
                self._help_dialog.destroyed.connect(self._on_dialog_destroyed)
                self._help_dialog.show()
            except Exception as e:
                logger.error(f"Error opening help dialog: {e}")
                self._help_dialog = None

    def _on_tree_build_finished(
        self,
        success: bool,
        message: str,
        result: Optional[TreeNode],
        worker=None,
    ):
        """Handles analysis tree building completion."""
        try:
            self.set_processing_state_in_view(False)

            if success and result:
                self._app_state.set_analysis_tree(result)

                self._show_analysis_dialog()
            else:
                self._view.show_status(message_key="Failed to build analysis tree", is_error=True)
        finally:
            if worker is not None:
                try:
                    self._current_workers.remove(worker)
                except ValueError:
                    pass

    def _show_analysis_dialog(self):
        if self._analysis_dialog is not None:
            try:

                self._analysis_dialog.accepted.disconnect(self._handle_analysis_accepted)
                self.disabled_nodes_changed.disconnect(self._analysis_dialog.presenter.view.on_external_update)
            except (TypeError, RuntimeError):
                pass
            try:
                self._analysis_dialog.close()
            except RuntimeError:
                pass
            self._analysis_dialog = None

        try:
            self._analysis_dialog = self._view.create_analysis_dialog(
                presenter=self,
                theme_manager=self._theme_manager,
            )

            self._analysis_dialog.accepted.connect(self._handle_analysis_accepted)
            self.disabled_nodes_changed.connect(self._analysis_dialog.on_external_update)

            def disconnect_analysis_signals(result_code=None):
                try:
                    if self._analysis_dialog:
                        self.disabled_nodes_changed.disconnect(self._analysis_dialog.on_external_update)
                        self._analysis_dialog.accepted.disconnect(self._handle_analysis_accepted)
                except (TypeError, RuntimeError):
                    pass

            self._analysis_dialog.finished.connect(disconnect_analysis_signals)

            if self._app_state.analysis_tree:
                self._analysis_dialog.load_data_and_show(
                    root_node=self._app_state.analysis_tree,
                    initial_disabled_nodes=self._app_state.disabled_time_nodes,
                    unit=self._app_state.last_analysis_unit
                )
            self._analysis_dialog.show()

        except Exception as e:
            logger.error(f"Error opening analysis dialog: {e}")

    def _handle_analysis_accepted(self):
        if self._analysis_dialog:

            final_disabled_nodes = self._analysis_dialog.disabled_nodes
            self.update_disabled_nodes(final_disabled_nodes)
        else:
            logger.warning("[ModernPresenter] _handle_analysis_accepted called, but _analysis_dialog is None")

    def on_calendar_clicked(self):
        if self._app_state.is_processing:
            return

        if not self._app_state.has_chat_loaded():
            self._view.show_status(message_key="Please load a JSON file first.", is_error=True)
            return

        if not self._app_state.has_analysis_data():

            self._view.show_message_box(
                tr("dialog.calendar.title_short"),
                tr("analysis.recalc_first"),
                QMessageBox.Icon.Information
            )
            return

        if not self._app_state.analysis_tree:

            self.set_processing_state_in_view(True, message_key="Building analysis tree...")

            worker = TreeBuildWorker(
                self._analysis_service,
                self._app_state.analysis_result,
                self._app_state.ui_config.copy(),
            )
            worker.signals.finished.connect(
                lambda s, m, r, w=worker: self._on_calendar_tree_build_finished(s, m, r, w)
            )

            self._current_workers.append(worker)
            self._threadpool.start(worker)
        else:
            self._show_calendar_dialog()

    def _on_calendar_tree_build_finished(
        self,
        success: bool,
        message: str,
        result: Optional[TreeNode],
        worker=None,
    ):
        """Handles calendar tree building completion."""
        try:
            self.set_processing_state_in_view(False)

            if success and result:
                self._app_state.set_processing_state(False)
                self._app_state.set_analysis_tree(result)
                self._show_calendar_dialog()
            else:
                self._view.show_status(
                    tr("analysis.tree_build_failed"), is_error=True
                )
        finally:
            if worker is not None:
                try:
                    self._current_workers.remove(worker)
                except ValueError:
                    pass

    def _show_calendar_dialog(self):
        if self._calendar_dialog is not None:
            try:
                self._calendar_dialog.presenter.filter_changed.disconnect(self.update_disabled_nodes)
                self.disabled_nodes_changed.disconnect(self._calendar_dialog.presenter.set_disabled_nodes)
            except (TypeError, RuntimeError):
                pass
            try:
                self._calendar_dialog.close()
            except RuntimeError:
                pass
            self._calendar_dialog = None

        try:
            chat_as_dict = chat_to_dict(self._app_state.loaded_chat)
            messages_dict = chat_as_dict.get("messages", [])
            chat_id = chat_as_dict.get("id")

            unit = (
                self._app_state.analysis_result.unit
                if self._app_state.analysis_result
                else self._app_state.last_analysis_unit
            )
            token_hierarchy = self._analysis_service.get_full_date_hierarchy_for_calendar(
                chat=self._app_state.loaded_chat,
                config=self._app_state.ui_config.copy(),
                tokenizer=self._app_state.tokenizer,
                unit=unit,
            )

            self._calendar_dialog = self._view.create_calendar_dialog(
                presenter=CalendarPresenter(self._calendar_service),
                messages=messages_dict,
                config=self._app_state.ui_config.copy(),
                theme_manager=self._theme_manager,
                root_node=self._app_state.analysis_tree,
                initial_disabled_nodes=self._app_state.disabled_time_nodes,
                token_hierarchy=token_hierarchy,
                chat_id=chat_id if isinstance(chat_id, int) else None,
            )
            if hasattr(self._calendar_dialog, "update_language"):
                self.language_changed.connect(self._calendar_dialog.update_language)
            else:
                self.language_changed.connect(self._calendar_dialog.retranslate_ui)

            self._calendar_dialog.presenter.filter_changed.connect(self.update_disabled_nodes)

            self.disabled_nodes_changed.connect(self._calendar_dialog.presenter.set_disabled_nodes)
            self._calendar_dialog.memory_changed.connect(self.on_recalculate_clicked)

            def disconnect_calendar_signals(result_code=None):
                try:
                    if self._calendar_dialog:
                        self._calendar_dialog.presenter.filter_changed.disconnect(self.update_disabled_nodes)

                        self.disabled_nodes_changed.disconnect(self._calendar_dialog.presenter.set_disabled_nodes)
                        self._calendar_dialog.memory_changed.disconnect(self.on_recalculate_clicked)
                except (TypeError, RuntimeError):
                    pass

            self._calendar_dialog.finished.connect(disconnect_calendar_signals)

            self._calendar_dialog.show()
        except Exception as e:
            logger.exception(f"Error opening calendar dialog: {e}")
            self._view.show_status(message_key="Error opening calendar dialog", is_error=True)

    def on_settings_clicked(self):
        if self._settings_dialog is not None:
            try:
                if self._settings_dialog.isVisible():
                    self._view.bring_dialog_to_front(self._settings_dialog, "settings")
                    return
                else:
                    self._settings_dialog = None
            except RuntimeError:
                self._settings_dialog = None

        if self._settings_dialog is None:
            try:

                ui_settings = self._settings_manager.load_ui_settings()

                self._settings_dialog = self._view.create_settings_dialog(
                    current_theme=self._current_session_theme,
                    current_language=self._settings_manager.load_language(),
                    current_ui_font_mode=self._settings_manager.load_ui_font_mode(),
                    current_ui_font_family=self._settings_manager.load_ui_font_family(),
                    current_truncate_name_length=ui_settings.get("truncate_name_length", 20),
                    current_truncate_quote_length=ui_settings.get("truncate_quote_length", 50),
                    current_auto_detect_profile=ui_settings.get("auto_detect_profile", True),
                    current_auto_recalc=ui_settings.get("auto_recalc", False),
                    tokenizer_available=self._tokenizer_service.is_transformers_available(),
                    current_analysis_unit=self._app_state.get_config_value("analysis_unit", "tokens"),
                )

                self.language_changed.connect(self._settings_dialog.retranslate_ui)
                self._settings_dialog.accepted.connect(self._apply_settings_from_dialog)
                self._settings_dialog.destroyed.connect(self._on_dialog_destroyed)

                self._settings_dialog.show()

            except Exception as e:
                import traceback
                self._settings_dialog = None

    def _apply_settings_from_dialog(self):
        if not self._settings_dialog:
            return

        new_lang = self._settings_dialog.get_language()
        new_theme = self._settings_dialog.get_theme()
        new_font_mode, new_font_family = self._settings_dialog.get_font_settings()

        current_lang = self._settings_manager.load_language()
        if new_lang != current_lang:
            self._settings_manager.save_language(new_lang)
            set_language(new_lang)
            self.language_changed.emit()

        current_theme = self._current_session_theme
        if new_theme != current_theme:
            self._settings_manager.save_theme(new_theme)
            self._theme_manager.set_theme(new_theme, self._app)
            self._current_session_theme = new_theme

        current_font_mode = self._settings_manager.load_ui_font_mode()
        current_font_family = self._settings_manager.load_ui_font_family()

        if new_font_mode != current_font_mode or new_font_family != current_font_family:
            self._settings_manager.save_ui_font_settings(new_font_mode, new_font_family)
            self._font_manager.set_font(new_font_mode, new_font_family)

        new_trunc_settings = self._settings_dialog.get_truncation_settings()
        new_auto_detect_profile = self._settings_dialog.get_auto_detect_profile()
        new_auto_recalc = self._settings_dialog.get_auto_recalc()

        current_ui_settings = self._settings_manager.load_ui_settings()
        current_auto_detect = current_ui_settings.get("auto_detect_profile", True)
        current_auto_recalc = current_ui_settings.get("auto_recalc", False)

        settings_changed = False

        if current_auto_detect != new_auto_detect_profile:
            current_ui_settings["auto_detect_profile"] = new_auto_detect_profile
            self._app_state.set_config_value("auto_detect_profile", new_auto_detect_profile)
            settings_changed = True

        if current_auto_recalc != new_auto_recalc:
            current_ui_settings["auto_recalc"] = new_auto_recalc
            self._app_state.set_config_value("auto_recalc", new_auto_recalc)
            settings_changed = True

        new_analysis_unit = self._settings_dialog.get_analysis_unit()
        current_analysis_unit = current_ui_settings.get("analysis_unit", "tokens")
        current_ui_settings["analysis_unit"] = new_analysis_unit
        self._app_state.set_config_value("analysis_unit", new_analysis_unit)
        settings_changed = True
        if current_analysis_unit != new_analysis_unit:
            self._update_analysis_unit()

        if settings_changed:
            self._settings_manager.save_ui_settings(current_ui_settings)

        config_updated = False
        for key, value in new_trunc_settings.items():
            current_value = self._app_state.get_config_value(key)
            if current_value != value:
                self._app_state.set_config_value(key, value)
                config_updated = True

        if config_updated:
            self._generate_preview()

    def on_install_manager_clicked(self):
        if self._install_dialog is not None:
            try:

                self._view.bring_dialog_to_front(self._install_dialog, "install_manager")
                return
            except RuntimeError:
                self._install_dialog = None

        is_installed = self._tokenizer_service.is_transformers_available()
        is_loaded = self._app_state.has_tokenizer()
        loaded_model_name = self._app_state.tokenizer_model_name

        model_in_cache = False
        ai_settings = self._settings_manager.load_ai_settings()
        current_model = ai_settings.get(
            "tokenizer_model", self._settings_manager.get_default_tokenizer_model()
        )

        if is_installed:
            cache_info = self._tokenizer_service.check_model_cache(current_model)
            model_in_cache = cache_info.get("available", False)

        self._install_dialog = self._view.create_install_dialog(
            is_installed=is_installed,
            is_loaded=is_loaded,
            loaded_model_name=loaded_model_name,
            settings_manager=self._settings_manager,
            settings=self._settings_manager.load_ai_settings(),
            model_in_cache=model_in_cache,
            tokenizer_service=self._tokenizer_service,
            theme_manager=self._theme_manager,
        )

        self._install_dialog.install_triggered.connect(
            self._handle_install_transformers
        )
        self._install_dialog.remove_model_triggered.connect(self._handle_remove_model)
        self._install_dialog.load_model_triggered.connect(self._handle_ai_model_load)
        self._install_dialog.accepted.connect(self._handle_install_manager_accepted)

        self._install_dialog.destroyed.connect(self._on_install_dialog_destroyed)

        self._install_dialog.show()

    def _on_dialog_destroyed(self):
        sender = self.sender()

        if sender == self._settings_dialog:
            self.language_changed.disconnect(self._settings_dialog.retranslate_ui)
            self._settings_dialog = None
        elif sender == self._analysis_dialog:
            try:
                if hasattr(self._analysis_dialog, "update_language"):
                    self.language_changed.disconnect(self._analysis_dialog.update_language)
                else:
                    self.language_changed.disconnect(self._analysis_dialog.retranslate_ui)
            except (TypeError, RuntimeError) as e:
                logger.warning(f"[ModernPresenter] Error disconnecting language_changed for analysis_dialog: {e}")
            self._analysis_dialog = None

        elif sender == self._calendar_dialog:
            try:
                if hasattr(self._calendar_dialog, "update_language"):
                    self.language_changed.disconnect(self._calendar_dialog.update_language)
                else:
                    self.language_changed.disconnect(self._calendar_dialog.retranslate_ui)
                self._calendar_dialog.destroyed.disconnect(self._on_dialog_destroyed)
            except (TypeError, RuntimeError) as e:
                logger.warning(f"[ModernPresenter] Error disconnecting signals for calendar_dialog: {e}")
            self._calendar_dialog = None
        elif sender == self._help_dialog:
            try:
                self.language_changed.disconnect(self._help_dialog.retranslate_ui)
            except (TypeError, RuntimeError):
                pass
            self._help_dialog = None

    def _handle_install_transformers(self):
        self._run_installer_worker("install_deps")

    def _handle_remove_model(self):
        settings = self._settings_manager.load_ai_settings()
        model_name = settings.get(
            "tokenizer_model", self._settings_manager.get_default_tokenizer_model()
        )
        if model_name:
            self._run_installer_worker("remove_model", model_name=model_name)

    def _handle_ai_model_load(self, model_name: str):
        if self._install_dialog:
            self._install_dialog.append_log(tr("install.downloading_model", model=model_name))
            self._install_dialog.set_actions_enabled(False)

        hf_token = ""
        if self._install_dialog:
            hf_token = self._install_dialog.get_settings().get("hf_token", "") or ""
        worker = TokenizerLoadWorker(self._tokenizer_service, model_name, hf_token=hf_token)
        worker.signals.progress.connect(
            lambda msg: self._install_dialog.append_log(f'<span class="info">{msg}</span>') if self._install_dialog else None
        )
        worker.signals.finished.connect(self._on_tokenizer_load_finished)
        self._threadpool.start(worker)

    def _on_tokenizer_load_finished(self, success: bool, message: str, tokenizer: Optional[Any]):
        model_name = self._tokenizer_service.get_current_model_name()
        if success and tokenizer:
            self._app_state.set_tokenizer(tokenizer, model_name)
            self._update_analysis_unit()
            self.tokenizer_changed.emit()

            if self._install_dialog:
                self._install_dialog.append_log(
                    tr("install.model_loaded", model=model_name)
                )
                is_installed = self._tokenizer_service.is_transformers_available()
                is_loaded = self._app_state.has_tokenizer()
                self._install_dialog.set_status(
                    is_installed, is_loaded, model_in_cache=True, loaded_model_name=model_name
                )
        else:
            logger.error(f"Failed to load tokenizer {model_name}: {message}")
            if self._install_dialog:
                self._install_dialog.append_log(tr("install.error_loading_tokenizer", error=message))
            self.tokenizer_load_failed.emit(message)

        if self._install_dialog:
            self._install_dialog.set_actions_enabled(True)

    def _run_installer_worker(self, action: str, model_name: str | None = None):
        if not self._install_dialog or self._installer_worker is not None:
            return

        self._view.show_status(
            message_key="Executing: {command}",
            format_args={"command": action}
        )
        self._install_dialog.set_actions_enabled(False)
        self._installer_worker = AIInstallerWorker(action, model_name)
        self._installer_worker.signals.progress.connect(self._on_install_progress)
        self._installer_worker.signals.finished.connect(self._on_install_finished)
        QThreadPool.globalInstance().start(self._installer_worker)

    def _on_install_progress(self, message: str):
        if self._install_dialog and not self._install_dialog.isHidden():
            try:

                if any(keyword in message.lower() for keyword in ["error", "failed", "exception"]):
                    log_type = "error"
                elif any(keyword in message.lower() for keyword in ["warning", "warn"]):
                    log_type = "status"
                else:
                    log_type = "info"
                self._install_dialog.append_log(f'<span class="{log_type}">{message}</span>')
            except RuntimeError:
                pass

    def _on_install_finished(self, success: bool, message: str):
        self._view.show_status(message_key="Operation completed.")

        if self._install_dialog and not self._install_dialog.isHidden():
            try:
                action = (
                    self._installer_worker.action
                    if self._installer_worker
                    else "install_deps"
                )

                if success and action == "remove_model":
                    removed_model_name = self._installer_worker.model_name
                    if (
                        self._app_state.tokenizer
                        and self._app_state.tokenizer_model_name == removed_model_name
                    ):
                        self._app_state.clear_tokenizer()
                        self._update_analysis_unit()
                        self.tokenizer_changed.emit()

                is_installed_now = self._tokenizer_service.is_transformers_available()
                is_loaded_now = self._app_state.has_tokenizer()

                model_in_cache = None
                if is_installed_now and not is_loaded_now:
                    ai_settings = self._settings_manager.load_ai_settings()
                    current_model = ai_settings.get(
                        "tokenizer_model",
                        self._settings_manager.get_default_tokenizer_model(),
                    )
                    cache_info = self._tokenizer_service.check_model_cache(
                        current_model
                    )
                    model_in_cache = cache_info.get("available", False)

                loaded_model_name = (
                    self._app_state.tokenizer_model_name if is_loaded_now else None
                )

                self._install_dialog.on_action_finished(
                    success=success,
                    message=message,
                    new_is_installed=is_installed_now,
                    new_is_loaded=is_loaded_now,
                    model_in_cache=model_in_cache,
                    loaded_model_name=loaded_model_name,
                )

                if success and action == "install_deps":
                    self._show_restart_notification()

            except RuntimeError:
                pass

        self._installer_worker = None

    def _show_restart_notification(self):
        self._view.show_message_box(
            tr("install.restart_required"),
            tr("install.library_installed") + "\n" + tr("install.restart_please"),
            QMessageBox.Icon.Information
        )

    def _handle_install_manager_accepted(self):
        if not self._install_dialog:
            return

        new_settings = self._install_dialog.get_settings()
        self._settings_manager.save_ai_settings(new_settings)

    def update_disabled_nodes(self, new_disabled_set: Set[TreeNode]):
        old_disabled_set = self._app_state.disabled_time_nodes.copy()
        if old_disabled_set != new_disabled_set:
            self._app_state.set_disabled_nodes(new_disabled_set)
            self.disabled_nodes_changed.emit(new_disabled_set)

    def _on_app_theme_changed(self):

        new_palette = self._app.palette()
        if hasattr(self._view, "apply_app_theme"):
            self._view.apply_app_theme(new_palette)

        for dialog in [self._settings_dialog, self._analysis_dialog, self._install_dialog, self._calendar_dialog, self._help_dialog]:
            try:
                if dialog and dialog.isVisible():
                    self._theme_manager.apply_theme_to_dialog(dialog)
            except RuntimeError as e:

                if dialog == self._settings_dialog:
                    self._settings_dialog = None
                elif dialog == self._analysis_dialog:
                    self._analysis_dialog = None
                elif dialog == self._install_dialog:
                    self._install_dialog = None
                elif dialog == self._calendar_dialog:
                    self._calendar_dialog = None
                elif dialog == self._help_dialog:
                    self._help_dialog = None

        self.language_changed.emit()

    def get_analysis_stats(self) -> Optional[Dict[str, int]]:
        if not self._app_state.analysis_result:
            return None

        total_count = self._app_state.analysis_result.total_count

        if self._app_state.analysis_tree and self._app_state.disabled_time_nodes:
            filtered_count = self._calculate_filtered_count()
        else:
            filtered_count = total_count

        return {
            "total_count": total_count,
            "filtered_count": filtered_count,
            "disabled_count": total_count - filtered_count,
        }

    def _calculate_filtered_count(self) -> int:
        if not self._app_state.analysis_tree:
            return 0

        return self._calculate_tree_value_excluding_disabled(
            self._app_state.analysis_tree
        )

    def _calculate_tree_value_excluding_disabled(self, node) -> int:
        from core.analysis.tree_analyzer import TreeNode

        if not isinstance(node, TreeNode):
            return 0

        if node in self._app_state.disabled_time_nodes:
            return 0

        if node.children:
            total = 0
            for child in node.children:
                total += self._calculate_tree_value_excluding_disabled(child)
            return total
        else:
            return node.value

    def get_current_chat(self) -> Optional[Chat]:
        return self._app_state.loaded_chat

    def get_analysis_result(self) -> Optional[AnalysisResult]:
        return self._app_state.analysis_result

    def get_analysis_tree(self) -> Optional[TreeNode]:
        return self._app_state.analysis_tree

    def get_config(self) -> Dict[str, Any]:
        return self._app_state.ui_config.copy()

    def get_disabled_nodes(self) -> Set[TreeNode]:
        return self._app_state.disabled_time_nodes.copy()

    def has_chat_loaded(self) -> bool:
        return self._app_state.has_chat_loaded()

    def get_app_state(self) -> AppState:
        return self._app_state

    def get_current_file_path(self) -> Optional[str]:
        return self._chat_service.get_current_file_path()

    def set_processing_state_in_view(self, is_processing: bool, message: str = "", message_key: str = None, format_args: dict = None):
        if message_key:
            translated_message = tr(message_key)
            self._app_state.set_processing_state(is_processing, translated_message)
        else:
            self._app_state.set_processing_state(is_processing, message)

        if hasattr(self._view, 'set_processing_state'):
            self._view.set_processing_state(is_processing, None, message_key, format_args)
        else:
            logger.warning("View does not have set_processing_state method")

    def on_drop_zone_hover_state_changed(self, is_hovered: bool):
        if self._is_drop_zone_drag_active:
            self._is_drop_zone_drag_active = False

        self._is_drop_zone_hovered = is_hovered
        self._update_drop_zone_style()

    def on_drop_zone_drag_active(self, is_active: bool):
        self._is_drop_zone_drag_active = is_active
        self._update_drop_zone_style()

    def _update_drop_zone_style(self):
        if self._is_drop_zone_drag_active:

            self.set_drop_zone_style_command.emit("border: 2px solid #0078d4; background-color: rgba(0, 120, 212, 0.1);")
        else:

            self.set_drop_zone_style_command.emit("border: 2px dashed #aaa;")
