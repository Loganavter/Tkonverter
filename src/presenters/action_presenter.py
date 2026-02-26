import logging
import re
from typing import Optional, Any

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

from src.shared_toolkit.utils.file_utils import get_unique_filepath
from src.core.application.conversion_service import ConversionService
from src.core.application.tokenizer_service import TokenizerService
from src.core.settings_port import SettingsPort
from src.core.domain.models import Chat
from src.presenters.app_state import AppState
from src.presenters.workers import ConversionWorker, TokenizerLoadWorker, AIInstallerWorker
from src.resources.translations import tr

logger = logging.getLogger(__name__)

class ActionPresenter(QObject):

    save_completed = pyqtSignal(bool, str)
    language_changed = pyqtSignal()
    tokenizer_changed = pyqtSignal()
    analysis_unit_changed = pyqtSignal()

    def __init__(self, view, app_state: AppState, conversion_service: ConversionService,
                 tokenizer_service: TokenizerService, settings_manager: SettingsPort, theme_manager, app_instance,
                 font_manager):
        super().__init__()
        self._view = view
        self._app_state = app_state
        self._conversion_service = conversion_service
        self._tokenizer_service = tokenizer_service
        self._settings_manager = settings_manager
        self._theme_manager = theme_manager
        self._app = app_instance
        self._font_manager = font_manager

        self._threadpool = QThreadPool()
        self._current_workers = []

        self._settings_dialog = None
        self._export_dialog = None
        self._install_dialog = None
        self._help_dialog = None

        self._installer_worker = None

        self._connect_signals()

    def _connect_signals(self):
        self._view.save_button_clicked.connect(self.on_save_clicked)
        self._view.quick_save_button_clicked.connect(self.on_quick_save_clicked)
        self._view.settings_button_clicked.connect(self.on_settings_clicked)
        self._view.install_manager_button_clicked.connect(self.on_install_manager_clicked)
        self._view.help_button_clicked.connect(self.on_help_clicked)

    def apply_theme_to_open_dialogs(self, new_palette):
        for dialog_attr in (
            "_settings_dialog",
            "_export_dialog",
            "_install_dialog",
            "_help_dialog",
        ):
            dialog = getattr(self, dialog_attr, None)
            if not dialog:
                continue
            try:
                if dialog.isVisible():
                    self._theme_manager.apply_theme_to_dialog(dialog)
            except RuntimeError:
                setattr(self, dialog_attr, None)

    def on_save_clicked(self):
        if self._app_state.is_processing:
            return

        if not self._app_state.has_chat_loaded():
            self._view.show_status(message_key="Please load a JSON file first.", is_error=True)
            return

        chat_name = self._app_state.get_chat_name()
        sanitized_name = re.sub(r'[\\/*?:"<>|]', "_", chat_name)[:80]

        if self._export_dialog is not None:
            try:
                self._view.bring_dialog_to_front(self._export_dialog, "export")
                return
            except RuntimeError:
                self._export_dialog = None

        try:
            self._export_dialog = self._view.create_export_dialog(
                suggested_filename=sanitized_name,
                get_unique_path_func=get_unique_filepath,
            )

            if hasattr(self._export_dialog, "update_language"):
                self.language_changed.connect(self._export_dialog.update_language)
            else:
                self.language_changed.connect(self._export_dialog.retranslate_ui)
            self._export_dialog.accepted.connect(self._handle_export_accepted)
            self._export_dialog.destroyed.connect(self._on_dialog_destroyed)
            self._export_dialog.show()
        except Exception as e:

            pass

    def on_quick_save_clicked(self):
        import logging
        logger = logging.getLogger("Tkonverter")
        logger.info("Quick save button clicked")

        if self._app_state.is_processing:
            logger.info("Already processing, ignoring quick save")
            return

        if not self._app_state.has_chat_loaded():
            logger.warning("No chat loaded, showing error")
            self._view.show_status(message_key="Please load a JSON file first.", is_error=True)
            return

        import os
        default_dir = self._settings_manager.get_export_default_dir()
        if not default_dir:

            default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            logger.info(f"Using default Downloads directory: {default_dir}")
        else:
            logger.info(f"Using saved export directory: {default_dir}")

        chat_name = self._app_state.get_chat_name()
        sanitized_name = re.sub(r'[\\/*?:"<>|]', "_", chat_name)[:80]
        logger.info(f"Chat name: {chat_name}, sanitized: {sanitized_name}")

        from src.shared_toolkit.utils.file_utils import get_unique_filepath
        final_path = get_unique_filepath(default_dir, sanitized_name, ".txt")
        logger.info(f"Final export path: {final_path}")

        self._perform_export(final_path)

    def _get_config_with_anonymization(self) -> dict:
        config = self._app_state.ui_config.copy()
        anonymization_settings = self._settings_manager.load_anonymization_settings()
        if anonymization_settings:
            config["anonymization"] = anonymization_settings
        return config

    def _perform_export(self, final_path: str):
        import logging
        logger = logging.getLogger("Tkonverter")

        logger.info(f"Starting quick export to: {final_path}")
        self.set_processing_state_in_view(True, message_key="Saving file...")

        worker = ConversionWorker(
            self._conversion_service,
            self._app_state.loaded_chat,
            self._get_config_with_anonymization(),
            final_path,
            self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree) if self._app_state.analysis_tree else set(),
        )
        worker.signals.finished.connect(
            lambda s, p, r, w=worker: self._on_save_finished(s, p, r, w)
        )

        self._current_workers.append(worker)
        self._threadpool.start(worker)
        logger.info("Export worker started")

    def _handle_export_accepted(self):
        if not self._export_dialog:
            return

        options = self._export_dialog.get_export_options()
        output_dir, file_name = options["output_dir"], options["file_name"]
        use_default = options["use_default_dir"]

        self._settings_manager.save_export_default_dir(
            use_default_dir=use_default, default_dir=output_dir
        )

        final_path = get_unique_filepath(output_dir, file_name, ".txt")

        self._export_dialog.close()
        self._export_dialog = None

        self.set_processing_state_in_view(True, message_key="Saving file...")

        worker = ConversionWorker(
            self._conversion_service,
            self._app_state.loaded_chat,
            self._get_config_with_anonymization(),
            final_path,
            self._app_state.get_disabled_nodes_from_tree(self._app_state.analysis_tree) if self._app_state.analysis_tree else set(),
        )
        worker.signals.finished.connect(
            lambda s, p, r, w=worker: self._on_save_finished(s, p, r, w)
        )

        self._current_workers.append(worker)
        self._threadpool.start(worker)

    def _on_save_finished(
        self, success: bool, path_or_error: str, result: Optional[Any], worker=None
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
                    current_theme=self._theme_manager.get_current_theme(),
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

                if hasattr(self._settings_dialog, "update_language"):
                    self.language_changed.connect(self._settings_dialog.update_language)
                else:
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
            from src.resources.translations import set_language
            set_language(new_lang)
            self.language_changed.emit()

        current_theme = self._theme_manager.get_current_theme()
        if new_theme != current_theme:
            self._settings_manager.save_theme(new_theme)
            self._theme_manager.set_theme(new_theme, self._app)

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
        logger.debug(
            "analysis_unit: from_dialog=%r, current_ui_settings=%r, setting app_state and saving",
            new_analysis_unit,
            current_analysis_unit,
        )
        current_ui_settings["analysis_unit"] = new_analysis_unit
        self._app_state.set_config_value("analysis_unit", new_analysis_unit)
        settings_changed = True
        if current_analysis_unit != new_analysis_unit:
            self.analysis_unit_changed.emit()

        if settings_changed:
            self._settings_manager.save_ui_settings(current_ui_settings)

        config_updated = False
        for key, value in new_trunc_settings.items():
            current_value = self._app_state.get_config_value(key)
            if current_value != value:
                self._app_state.set_config_value(key, value)
                config_updated = True

        if config_updated:

            self.language_changed.emit()

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

        self._install_dialog.install_triggered.connect(self._handle_install_transformers)
        self._install_dialog.remove_model_triggered.connect(self._handle_remove_model)
        self._install_dialog.load_model_triggered.connect(self._handle_ai_model_load)
        self._install_dialog.accepted.connect(self._handle_install_manager_accepted)

        self._install_dialog.destroyed.connect(self._on_dialog_destroyed)

        self._install_dialog.show()

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
            self._install_dialog.append_log(tr("Downloading tokenizer model '{model}'...").format(model=model_name))
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

            self.tokenizer_changed.emit()

            if self._install_dialog:
                self._install_dialog.append_log(
                    tr("Tokenizer '{model}' loaded successfully!").format(model=model_name)
                )
                is_installed = self._tokenizer_service.is_transformers_available()
                is_loaded = self._app_state.has_tokenizer()
                self._install_dialog.set_status(
                    is_installed, is_loaded, model_in_cache=True, loaded_model_name=model_name
                )
        else:

            if self._install_dialog:
                self._install_dialog.append_log(tr("Error loading tokenizer: {error}").format(error=message))

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
            tr("Restart Required"),
            tr("Library installation completed successfully!") + "\n" + tr("Please restart the application for changes to take effect."),
            QMessageBox.Icon.Information
        )

    def _handle_install_manager_accepted(self):
        if not self._install_dialog:
            return

        new_settings = self._install_dialog.get_settings()
        self._settings_manager.save_ai_settings(new_settings)

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

    def _on_dialog_destroyed(self):
        sender = self.sender()

        if sender == self._settings_dialog:
            try:
                if hasattr(self._settings_dialog, "update_language"):
                    self.language_changed.disconnect(self._settings_dialog.update_language)
                else:
                    self.language_changed.disconnect(self._settings_dialog.retranslate_ui)
            except (TypeError, RuntimeError):
                pass
            self._settings_dialog = None
        elif sender == self._export_dialog:
            try:
                if hasattr(self._export_dialog, "update_language"):
                    self.language_changed.disconnect(self._export_dialog.update_language)
                else:
                    self.language_changed.disconnect(self._export_dialog.retranslate_ui)
            except (TypeError, RuntimeError):
                pass
            self._export_dialog = None
        elif sender == self._install_dialog:
            try:
                self.language_changed.disconnect(self._install_dialog.retranslate_ui)
            except (TypeError, RuntimeError) as e:

                pass
            self._install_dialog = None
        elif sender == self._help_dialog:
            try:
                self.language_changed.disconnect(self._help_dialog.update_language)
            except (TypeError, RuntimeError):
                pass
            self._help_dialog = None

    def set_processing_state_in_view(self, is_processing: bool, message: str = "", message_key: str = None, format_args: dict = None):
        if message_key:
            translated_message = tr(message_key)
            self._app_state.set_processing_state(is_processing, translated_message)
        else:
            self._app_state.set_processing_state(is_processing, message)

        if hasattr(self._view, 'set_processing_state'):
            self._view.set_processing_state(is_processing, None, message_key, format_args)
        else:

            pass
