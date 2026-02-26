import re
from typing import Any, Dict, Optional, Set

from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QMessageBox

from src.core.analysis.tree_analyzer import TreeNode
from src.core.analysis.tree_identity import TreeNodeIdentity
from src.core.application.analysis_service import AnalysisService
from src.core.application.chart_service import ChartService
from src.core.application.chat_service import ChatService
from src.core.application.conversion_service import ConversionService
from src.core.application.tokenizer_service import TokenizerService
from src.core.conversion.domain_adapters import chat_to_dict
from src.core.settings_port import SettingsPort
from src.presenters.preview_service import PreviewService
from src.presenters.calendar_presenter import CalendarPresenter
from src.presenters.workers import (
    ChatLoadWorker, ConversionWorker, AnalysisWorker,
    TreeBuildWorker, TokenizerLoadWorker, AIInstallerWorker,
    sync_load_chat, sync_convert_chat, sync_analyze_chat,
    sync_build_tree, sync_load_tokenizer
)

from src.core.domain.models import AnalysisResult, Chat
from src.presenters.app_state import AppState
from src.resources.translations import set_language, tr
from src.shared_toolkit.utils.file_utils import get_unique_filepath

class MainPresenter(QObject):

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
        chart_service: ChartService,
        preview_service: PreviewService,
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
        self._chart_service = chart_service
        self._preview_service = preview_service

        self._settings_dialog = None
        self._anonymization_dialog = None
        self._analysis_dialog = None
        self._install_dialog = None
        self._calendar_dialog = None
        self._help_dialog = None

        self._install_process = None
        self._installer_worker = None

        self._connect_signals()

        self._try_load_default_tokenizer()

        self._is_drop_zone_hovered = False
        self._is_drop_zone_drag_active = False
        self._view.show_status(message_key="Ready to work", is_status=True)

    def _connect_signals(self):

        self._view.config_changed.connect(self.on_config_changed)
        self._view.save_button_clicked.connect(self.on_save_clicked)
        self._view.quick_save_button_clicked.connect(self.on_quick_save_clicked)
        self._view.settings_button_clicked.connect(self.on_settings_clicked)
        self._view.anonymization_button_clicked.connect(self.on_anonymization_clicked)
        self._view.install_manager_button_clicked.connect(
            self.on_install_manager_clicked
        )
        self._view.recalculate_clicked.connect(self.on_recalculate_clicked)
        self._view.calendar_button_clicked.connect(self.on_calendar_clicked)
        self._view.diagram_button_clicked.connect(self.on_diagram_clicked)
        self._view.help_button_clicked.connect(self.on_help_clicked)

        self._theme_manager.theme_changed.connect(self._on_app_theme_changed)

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

    def _check_and_update_analysis(self, key: str, value: Any):
        if not self._app_state.has_analysis_data():
            return

        analysis_affecting_keys = [
            "profile", "show_service_notifications", "show_markdown",
            "show_links", "show_time", "show_reactions",
            "show_reaction_authors", "show_tech_info",
            "show_optimization", "streak_break_time",
            "my_name", "partner_name"
        ]

        if key not in analysis_affecting_keys:
            return

        disabled_dates = self._app_state.disabled_dates.copy()

        try:

            result, tree = self._analysis_service.recalculate_with_filters(
                self._app_state.loaded_chat,
                self._app_state.ui_config,
                self._app_state.tokenizer,
                disabled_dates
            )

            self._app_state.set_analysis_result(result)
            self._app_state.set_analysis_tree(tree)

            if self._app_state.has_disabled_nodes():
                restored_disabled_nodes = self._app_state.get_disabled_nodes_from_tree(tree)
                self.disabled_nodes_changed.emit(restored_disabled_nodes)

            self.analysis_completed.emit(tree)
            self.analysis_count_updated.emit(result.total_count, self._app_state.last_analysis_unit)

        except Exception as e:

            import traceback
            traceback.format_exc()

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

            import traceback
            traceback.format_exc()

            error_message = f"Error: {e}"
            self.preview_updated.emit(error_message, "Preview Error")

    def get_longest_preview_html(self) -> str:
        try:
            config = self._app_state.ui_config.copy()
            return self._preview_service.get_longest_preview_html(config)

        except Exception as e:

            import traceback
            traceback.format_exc()
            return ""

    def on_file_dropped(self, path: str):

        if self._app_state.is_processing:

            return

        self.set_processing_state_in_view(True, message_key="Loading file...")

        success, message, result = sync_load_chat(self._chat_service, path)
        self._on_chat_load_finished(success, message, result)

    def _on_chat_load_finished(
        self, success: bool, message: str, result: Optional[Chat]
    ):
        """Handles chat loading completion."""
        self.set_processing_state_in_view(False)

        if success and result:

            auto_detect_enabled = self._app_state.get_config_value("auto_detect_profile", True)

            if auto_detect_enabled:
                detected_profile = self._chat_service.detect_chat_type(result)
                current_profile = self._app_state.get_config_value("profile")

                if detected_profile != current_profile:
                    self._app_state.set_config_value("profile", detected_profile)
                    self.profile_auto_detected.emit(detected_profile)

                    if detected_profile == "personal":
                        self._update_personal_chat_names(result)
                else:

                    if detected_profile == "personal":
                        self._update_personal_chat_names(result)

            file_path = self._chat_service.get_current_file_path()
            self._app_state.set_chat(result, file_path)

            if auto_detect_enabled:
                self._generate_preview()

            chat_name = self._app_state.get_chat_name()

            self.chat_loaded.emit(True, "", chat_name)

            if self._app_state.get_config_value("auto_recalc", False):
                self.on_recalculate_clicked()

        else:
            self.chat_loaded.emit(False, message, "")

    def _update_personal_chat_names(self, chat):

        chat_name = chat.name

        current_partner_name = self._app_state.get_config_value("partner_name")

        if chat_name and chat_name != current_partner_name:
            self._app_state.set_config_value("partner_name", chat_name)

            self.profile_auto_detected.emit("personal")

    def on_config_changed(self, key: str, value: Any):

        old_value = self._app_state.get_config_value(key)

        if old_value != value:

            had_analysis_data_before = self._app_state.has_analysis_data()

            self._app_state.set_config_value(key, value)

            self.config_changed.emit(key, value)

            self._check_and_update_analysis(key, value)

            if not self._app_state.has_analysis_data():

                self.analysis_count_updated.emit(-1, "chars")

                if had_analysis_data_before:
                    unit = self._app_state.get_preferred_analysis_unit()
                    if unit == "tokens":
                        self._view.show_status(message_key="Tokens reset", is_status=True)
                    else:
                        self._view.show_status(message_key="Characters reset", is_status=True)
        else:

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
        from src.shared_toolkit.utils.file_utils import get_unique_filepath
        try:
            options = self._view.exec_export_dialog(
                suggested_filename=sanitized_name,
                get_unique_path_func=get_unique_filepath,
            )
            if not options:
                return
        except Exception:
            return

        output_dir, file_name = options["output_dir"], options["file_name"]
        use_default = options["use_default_dir"]
        self._settings_manager.save_export_default_dir(
            use_default_dir=use_default, default_dir=output_dir
        )
        final_path = get_unique_filepath(output_dir, file_name, ".txt")

        self.set_processing_state_in_view(True, message_key="Saving file...")
        success, path_or_error = sync_convert_chat(
            self._conversion_service,
            self._app_state.loaded_chat,
            self._app_state.ui_config.copy(),
            final_path,
            self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree) if self._app_state.analysis_tree else set(),
        )
        self._on_save_finished(success, path_or_error, None)

    def on_quick_save_clicked(self):
        if self._app_state.is_processing:
            return

        if not self._app_state.has_chat_loaded():
            self._view.show_status(message_key="Please load a JSON file first.", is_error=True)
            return

        import os
        default_dir = self._settings_manager.get_export_default_dir()
        if not default_dir:

            default_dir = os.path.join(os.path.expanduser("~"), "Downloads")

        chat_name = self._app_state.get_chat_name()
        sanitized_name = re.sub(r'[\\/*?:"<>|]', "_", chat_name)[:80]

        final_path = get_unique_filepath(default_dir, sanitized_name, ".txt")

        self.set_processing_state_in_view(True, message_key="Saving file...")

        success, path_or_error = sync_convert_chat(
            self._conversion_service,
            self._app_state.loaded_chat,
            self._app_state.ui_config.copy(),
            final_path,
            self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree) if self._app_state.analysis_tree else set(),
        )

        self.set_processing_state_in_view(False)
        self.save_completed.emit(success, path_or_error)

    def _on_save_finished(self, success: bool, path_or_error: str, result: Any):
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

    def on_recalculate_clicked(self):
        if not self._app_state.has_chat_loaded():
            self._view.show_status(message_key="Please load a JSON file first.", is_error=True)
            return

        self.set_processing_state_in_view(True, message_key="Calculating...")

        success, message, result = sync_analyze_chat(
            self._analysis_service,
            self._app_state.loaded_chat,
            self._app_state.ui_config.copy(),
            self._app_state.tokenizer,
            self._app_state.disabled_dates,
        )
        self._on_analysis_finished(success, message, result)

    def _on_analysis_finished(
        self, success: bool, message: str, result: Optional[AnalysisResult]
    ):
        """Handles analysis completion."""
        self.set_processing_state_in_view(False)

        if success and result:
            self._app_state.set_analysis_result(result)
            tree_success, _, tree = sync_build_tree(
                self._analysis_service,
                result,
                self._app_state.ui_config.copy(),
            )
            if tree_success and tree:
                self._app_state.set_analysis_tree(tree)
            count = self._app_state.get_filtered_count()
            self.analysis_count_updated.emit(count, self._app_state.last_analysis_unit)
        else:
            if message != "Cancelled":

                error_message = f"Analysis error: {message}" if message else "Analysis failed or no data found."
                self._view.show_status(
                    message=error_message,
                    is_error=True
                )
                self.analysis_count_updated.emit(-1, "chars")

    def on_diagram_clicked(self):
        if self._app_state.is_processing:
            return

        if not self._app_state.has_chat_loaded():
            self._view.show_status(message_key="Please load a JSON file first.", is_error=True)
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

            success, message, result = sync_build_tree(
                self._analysis_service,
                self._app_state.analysis_result,
                self._app_state.ui_config.copy(),
            )
            self._on_tree_build_finished(success, message, result)
        else:
            self._show_analysis_dialog()

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
                self.language_changed.connect(self._help_dialog.update_language)
                self._help_dialog.destroyed.connect(self._on_dialog_destroyed)
            except Exception as e:

                self._help_dialog = None

        if getattr(self._help_dialog, 'current_language', None) != self._settings_manager.load_language():
            try:
                if hasattr(self._help_dialog, 'update_language'):
                    self._help_dialog.update_language(self._settings_manager.load_language())
                else:
                    self._help_dialog.current_language = self._settings_manager.load_language()
            except Exception:
                pass

        self._help_dialog.show()

    def _on_tree_build_finished(
        self, success: bool, message: str, result: Optional[TreeNode]
    ):
        """Handles analysis tree building completion."""
        self.set_processing_state_in_view(False)

        if success and result:
            self._app_state.set_analysis_tree(result)

            self._show_analysis_dialog()
        else:
            self._view.show_status(message_key="Failed to build analysis tree", is_error=True)

    def _show_analysis_dialog(self):
        if self._analysis_dialog is not None:
            try:

                self.analysis_completed.disconnect(self._analysis_dialog.update_chart_data)
                self._analysis_dialog.accepted.disconnect(self._handle_analysis_accepted)
                self.disabled_nodes_changed.disconnect(self._analysis_dialog.on_external_update)
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
            self._analysis_dialog.filter_changed.connect(self._handle_filter_changed)

            self.disabled_nodes_changed.connect(self._analysis_dialog.on_external_update)

            self.analysis_completed.connect(self._analysis_dialog.update_chart_data)

            def disconnect_analysis_signals(result_code=None):
                try:
                    if self._analysis_dialog:
                        self.disabled_nodes_changed.disconnect(self._analysis_dialog.on_external_update)
                        self._analysis_dialog.accepted.disconnect(self._handle_analysis_accepted)
                        self._analysis_dialog.filter_changed.disconnect(self._handle_filter_changed)
                        self.analysis_completed.disconnect(self._analysis_dialog.update_chart_data)
                except (TypeError, RuntimeError):
                    pass

            self._analysis_dialog.finished.connect(disconnect_analysis_signals)

            if self._app_state.analysis_tree:

                self._analysis_dialog.load_data_and_show(
                    root_node=self._app_state.analysis_tree,
                    initial_disabled_nodes=self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree) if self._app_state.analysis_tree else set(),
                    unit=self._app_state.last_analysis_unit
                )
            self._analysis_dialog.show()

        except Exception as e:
            pass

    def _handle_filter_changed(self, disabled_nodes: Set[TreeNode]):

        self._app_state.set_disabled_nodes(disabled_nodes)

        self._app_state.disabled_dates.clear()

        dates_added = 0
        for node in disabled_nodes:
            if hasattr(node, 'node_id') and node.node_id:
                parsed = TreeNodeIdentity.parse_id(node.node_id)
                if parsed and parsed.get('type') == 'day':
                    year, month, day = parsed['year'], parsed['month'], parsed['day']
                    self._app_state.disabled_dates.add((year, month, day))
                    dates_added += 1

        self.disabled_nodes_changed.emit(disabled_nodes)

        if hasattr(self._view, "refresh_analysis_display"):
            self._view.refresh_analysis_display()

    def _handle_analysis_accepted(self):
        if self._analysis_dialog:

            final_disabled_nodes = self._analysis_dialog._get_nodes_from_ids(self._analysis_dialog.disabled_node_ids)
            self.update_disabled_nodes(final_disabled_nodes)

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

            success, message, result = sync_build_tree(
                self._analysis_service,
                self._app_state.analysis_result,
                self._app_state.ui_config.copy(),
            )
            self._on_calendar_tree_build_finished(success, message, result)
        else:
            self._show_calendar_dialog()

    def _on_calendar_tree_build_finished(
        self, success: bool, message: str, result: Optional[TreeNode]
    ):
        """Handles calendar tree building completion."""
        self.set_processing_state_in_view(False)

        if success and result:
            self._app_state.set_processing_state(False)
            self._app_state.set_analysis_tree(result)
            self._show_calendar_dialog()
        else:
            self._view.show_status(
                tr("analysis.tree_build_failed"), is_error=True
            )

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
                initial_disabled_nodes=self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree) if self._app_state.analysis_tree else set(),
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

    def on_anonymization_clicked(self):
        try:
            anonymization_config = self._settings_manager.load_anonymization_settings()
            known_names = []
            if self._app_state.has_chat_loaded() and self._app_state.loaded_chat:
                users = self._app_state.loaded_chat.get_users()
                known_names = [u.name for u in users if u.name]

            new_config = self._view.exec_anonymization_dialog(
                current_config=anonymization_config,
                known_names=known_names,
                known_domains=[],
            )
            if new_config is not None:
                self._settings_manager.save_anonymization_settings(new_config)
                self._app_state.set_config_value("anonymization", new_config)
                self._generate_preview()
        except Exception:
            pass

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
                pass

            self._analysis_dialog = None

        elif sender == self._calendar_dialog:
            try:
                if hasattr(self._calendar_dialog, "update_language"):
                    self.language_changed.disconnect(self._calendar_dialog.update_language)
                else:
                    self.language_changed.disconnect(self._calendar_dialog.retranslate_ui)
                self._calendar_dialog.destroyed.disconnect(self._on_dialog_destroyed)
            except (TypeError, RuntimeError) as e:
                pass

            self._calendar_dialog = None
        elif sender == self._help_dialog:
            try:
                self.language_changed.disconnect(self._help_dialog.update_language)
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

        progress_callback = None
        hf_token = ""
        if self._install_dialog:
            progress_callback = lambda msg: self._install_dialog.append_log(f'<span class="info">{msg}</span>')
            hf_token = self._install_dialog.get_settings().get("hf_token", "") or ""

        success, message, tokenizer = sync_load_tokenizer(
            self._tokenizer_service,
            model_name,
            progress_callback,
            hf_token=hf_token,
        )
        self._on_tokenizer_load_finished(success, message, tokenizer)

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
        old_disabled_set = self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree) if self._app_state.analysis_tree else set()
        if old_disabled_set != new_disabled_set:
            self._app_state.set_disabled_nodes(new_disabled_set)
            self.disabled_nodes_changed.emit(new_disabled_set)

            if self._app_state.has_analysis_data():
                filtered_count = self._calculate_filtered_count_from_tree()
                self.analysis_count_updated.emit(filtered_count, self._app_state.last_analysis_unit)

            if hasattr(self._view, "refresh_analysis_display"):
                self._view.refresh_analysis_display()

    def _calculate_filtered_count_from_tree(self) -> int:
        if not self._app_state.analysis_tree:
            return self._app_state.analysis_result.total_count if self._app_state.has_analysis_data() else 0

        disabled_nodes = self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree)
        filtered_value = self._chart_service.calculate_filtered_value(
            self._app_state.analysis_tree,
            disabled_nodes
        )

        return int(filtered_value)

    def on_disabled_dates_changed(self):
        if not self._app_state.has_analysis_data():
            return

        try:
            result, tree = self._analysis_service.recalculate_with_filters(
                self._app_state.loaded_chat,
                self._app_state.ui_config,
                self._app_state.tokenizer,
                self._app_state.disabled_dates
            )

            self._app_state.set_analysis_result(result)
            self._app_state.set_analysis_tree(tree)

            if self._app_state.has_disabled_nodes():
                restored_disabled_nodes = self._app_state.get_disabled_nodes_from_tree(tree)
                self.disabled_nodes_changed.emit(restored_disabled_nodes)

            self.analysis_completed.emit(tree)
            count = self._app_state.get_filtered_count()
            self.analysis_count_updated.emit(count, self._app_state.last_analysis_unit)

        except Exception as e:
            self._view.show_status(message_key="Error recalculating after date change", is_error=True)

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

    def get_current_chat(self) -> Optional[Chat]:
        return self._app_state.loaded_chat

    def get_analysis_result(self) -> Optional[AnalysisResult]:
        return self._app_state.analysis_result

    def get_analysis_tree(self) -> Optional[TreeNode]:
        return self._app_state.analysis_tree

    def get_config(self) -> Dict[str, Any]:
        config = self._app_state.ui_config.copy()

        anonymization_settings = self._settings_manager.load_anonymization_settings()
        if anonymization_settings:
            config["anonymization"] = anonymization_settings
        return config

    def get_disabled_nodes(self) -> Set[TreeNode]:
        return self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree) if self._app_state.analysis_tree else set()

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

            self.set_drop_zone_style_command.emit("border: 2px solid #0078d4; background-color: rgba(0, 120, 212, 0.1); border-radius: 10px; padding: 15px; font-size: 14px;")
        else:

            self.set_drop_zone_style_command.emit("border: 2px dashed #aaa; border-radius: 10px; padding: 15px; font-size: 14px;")
