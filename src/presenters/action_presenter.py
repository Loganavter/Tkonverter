import logging
import re
from typing import Optional

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

from core.application.conversion_service import ConversionService
from core.application.tokenizer_service import TokenizerService
from core.domain.models import Chat
from presenters.app_state import AppState
from presenters.workers import ConversionWorker, TokenizerLoadWorker, AIInstallerWorker
from resources.translations import tr

logger = logging.getLogger(__name__)

class ActionPresenter(QObject):
    """Presenter for managing action buttons (Save, Settings, Install, Help)."""

    save_completed = pyqtSignal(bool, str)
    language_changed = pyqtSignal()

    def __init__(self, view, app_state: AppState, conversion_service: ConversionService,
                 tokenizer_service: TokenizerService, settings_manager, theme_manager, app_instance):
        super().__init__()
        self._view = view
        self._app_state = app_state
        self._conversion_service = conversion_service
        self._tokenizer_service = tokenizer_service
        self._settings_manager = settings_manager
        self._theme_manager = theme_manager
        self._app = app_instance

        self._threadpool = QThreadPool()
        self._current_workers = []

        self._settings_dialog = None
        self._export_dialog = None
        self._install_dialog = None
        self._help_dialog = None

        self._installer_worker = None

        self._connect_signals()

    def _connect_signals(self):
        """Connects UI signals to presenter methods."""
        self._view.save_button_clicked.connect(self.on_save_clicked)
        self._view.settings_button_clicked.connect(self.on_settings_clicked)
        self._view.install_manager_button_clicked.connect(self.on_install_manager_clicked)
        self._view.help_button_clicked.connect(self.on_help_clicked)

    def on_save_clicked(self):
        """Handles save button click."""
        if self._app_state.is_processing:
            return

        if not self._app_state.has_chat_loaded():
            self._view.show_status(message_key="Please load a JSON file first.", is_error=True)
            return

        chat_name = self._app_state.get_chat_name()
        sanitized_name = re.sub(r'[\\/*?:"<>|]', "_", chat_name)[:80]

        from ui.dialogs.export_dialog import ExportDialog
        from utils.file_utils import get_unique_filepath

        if self._export_dialog is not None:
            try:
                self._view.bring_dialog_to_front(self._export_dialog, "export")
                return
            except RuntimeError:
                self._export_dialog = None

        try:
            self._export_dialog = ExportDialog(
                settings_manager=self._settings_manager,
                parent=self._view,
                suggested_filename=sanitized_name,
                get_unique_path_func=get_unique_filepath,
            )

            self._theme_manager.apply_theme_to_dialog(self._export_dialog)

            self.language_changed.connect(self._export_dialog.retranslate_ui)
            self._export_dialog.accepted.connect(self._handle_export_accepted)
            self._export_dialog.destroyed.connect(self._on_dialog_destroyed)
            self._export_dialog.show()
        except Exception as e:
            logger.error(f"Error opening export dialog: {e}")

    def _handle_export_accepted(self):
        """Handles export confirmation."""
        if not self._export_dialog:
            return

        options = self._export_dialog.get_export_options()
        output_dir, file_name = options["output_dir"], options["file_name"]
        use_default = options["use_default_dir"]

        self._settings_manager.settings.setValue("export_use_default_dir", use_default)
        if use_default:
            self._settings_manager.settings.setValue("export_default_dir", output_dir)

        from utils.file_utils import get_unique_filepath

        final_path = get_unique_filepath(output_dir, file_name, ".txt")

        self._export_dialog.close()
        self._export_dialog = None

        self.set_processing_state_in_view(True, message_key="Saving file...")

        worker = ConversionWorker(
            self._conversion_service,
            self._app_state.loaded_chat,
            self._app_state.ui_config.copy(),
            final_path,
            self._app_state.disabled_time_nodes,
        )
        worker.signals.finished.connect(self._on_save_finished)

        self._current_workers.append(worker)
        self._threadpool.start(worker)

    def _on_save_finished(self, success: bool, path_or_error: str, result: Optional[Any]):
        """Handles save completion."""
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

    def on_settings_clicked(self):
        """Handles settings button click."""
        from ui.dialogs.settings_dialog import SettingsDialog

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

                self._settings_dialog = SettingsDialog(
                    current_theme=self._theme_manager.get_current_theme(),
                    current_language=self._settings_manager.load_language(),
                    current_ui_font_mode=self._settings_manager.load_ui_font_mode(),
                    current_ui_font_family=self._settings_manager.load_ui_font_family(),
                    current_truncate_name_length=ui_settings.get("truncate_name_length", 20),
                    current_truncate_quote_length=ui_settings.get("truncate_quote_length", 50),
                    current_auto_detect_profile=ui_settings.get("auto_detect_profile", True),
                    current_auto_recalc=ui_settings.get("auto_recalc", False),
                    parent=self._view,
                )

                self._theme_manager.apply_theme_to_dialog(self._settings_dialog)

                self.language_changed.connect(self._settings_dialog.retranslate_ui)
                self._settings_dialog.accepted.connect(self._apply_settings_from_dialog)
                self._settings_dialog.destroyed.connect(self._on_dialog_destroyed)

                self._settings_dialog.show()

            except Exception as e:
                import traceback
                self._settings_dialog = None

    def _apply_settings_from_dialog(self):
        """Applies settings from dialog."""
        if not self._settings_dialog:
            return

        new_lang = self._settings_dialog.get_language()
        new_theme = self._settings_dialog.get_theme()
        new_font_mode, new_font_family = self._settings_dialog.get_font_settings()

        current_lang = self._settings_manager.load_language()
        if new_lang != current_lang:
            self._settings_manager.save_language(new_lang)
            from resources.translations import set_language
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
            from ui.font_manager import FontManager
            font_manager = FontManager.get_instance()
            font_manager.set_font(new_font_mode, new_font_family)

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
        """Handles install manager button click."""
        from ui.dialogs.installation_manager_dialog import InstallationManagerDialog

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

        self._install_dialog = InstallationManagerDialog(
            is_installed=is_installed,
            is_loaded=is_loaded,
            loaded_model_name=loaded_model_name,
            settings_manager=self._settings_manager,
            settings=self._settings_manager.load_ai_settings(),
            model_in_cache=model_in_cache,
            theme_manager=self._theme_manager,
            parent=self._view,
        )

        self._install_dialog.install_triggered.connect(self._handle_install_transformers)
        self._install_dialog.remove_model_triggered.connect(self._handle_remove_model)
        self._install_dialog.load_model_triggered.connect(self._handle_ai_model_load)
        self._install_dialog.accepted.connect(self._handle_install_manager_accepted)

        self._install_dialog.destroyed.connect(self._on_dialog_destroyed)

        self._install_dialog.show()

    def _handle_install_transformers(self):
        """Handles transformers library installation."""
        self._run_installer_worker("install_deps")

    def _handle_remove_model(self):
        """Handles removing model from cache."""
        settings = self._settings_manager.load_ai_settings()
        model_name = settings.get(
            "tokenizer_model", self._settings_manager.get_default_tokenizer_model()
        )
        if model_name:
            self._run_installer_worker("remove_model", model_name=model_name)

    def _handle_ai_model_load(self, model_name: str):
        """Handles AI model loading."""
        if self._install_dialog:
            self._install_dialog.append_log(tr("Downloading tokenizer model '{model}'...").format(model=model_name))
            self._install_dialog.set_actions_enabled(False)

        worker = TokenizerLoadWorker(self._tokenizer_service, model_name)
        worker.signals.progress.connect(
            lambda msg: self._install_dialog.append_log(f'<span class="info">{msg}</span>') if self._install_dialog else None
        )
        worker.signals.finished.connect(self._on_tokenizer_load_finished)
        self._threadpool.start(worker)

    def _on_tokenizer_load_finished(self, success: bool, message: str, tokenizer: Optional[Any]):
        """Handles tokenizer loading completion."""
        model_name = self._tokenizer_service.get_current_model_name()
        if success and tokenizer:
            self._app_state.set_tokenizer(tokenizer, model_name)

            self.language_changed.emit()

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
            logger.error(f"Failed to load tokenizer {model_name}: {message}")
            if self._install_dialog:
                self._install_dialog.append_log(tr("Error loading tokenizer: {error}").format(error=message))

        if self._install_dialog:
            self._install_dialog.set_actions_enabled(True)

    def _run_installer_worker(self, action: str, model_name: str | None = None):
        """Starts worker for installing/removing AI components."""
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
        """Handles installation progress."""
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
        """Handles installation completion."""
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
                        self.language_changed.emit()

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
        """Shows restart notification."""
        self._view.show_message_box(
            tr("Restart Required"),
            tr("Library installation completed successfully!") + "\n" + tr("Please restart the application for changes to take effect."),
            QMessageBox.Icon.Information
        )

    def _handle_install_manager_accepted(self):
        """Handles install manager dialog confirmation."""
        if not self._install_dialog:
            return

        new_settings = self._install_dialog.get_settings()
        self._settings_manager.save_ai_settings(new_settings)

    def on_help_clicked(self):
        """Handles help button click."""
        from ui.dialogs.help_dialog import HelpDialog

        if self._help_dialog is not None:
            try:
                self._view.bring_dialog_to_front(self._help_dialog, "help")
                return
            except RuntimeError:
                self._help_dialog = None

        if self._help_dialog is None:
            try:
                self._help_dialog = HelpDialog(parent=self._view)
                self._theme_manager.apply_theme_to_dialog(self._help_dialog)
                self.language_changed.connect(self._help_dialog.retranslate_ui)
                self._help_dialog.destroyed.connect(self._on_dialog_destroyed)
                self._help_dialog.show()
            except Exception as e:
                logger.error(f"Error opening help dialog: {e}")
                self._help_dialog = None

    def _on_dialog_destroyed(self):
        """Handles dialog destruction."""
        sender = self.sender()

        if sender == self._settings_dialog:
            self.language_changed.disconnect(self._settings_dialog.retranslate_ui)
            self._settings_dialog = None
        elif sender == self._export_dialog:
            self.language_changed.disconnect(self._export_dialog.retranslate_ui)
            self._export_dialog = None
        elif sender == self._install_dialog:
            try:
                self.language_changed.disconnect(self._install_dialog.retranslate_ui)
            except (TypeError, RuntimeError) as e:
                logger.warning(f"[ActionPresenter] Error disconnecting language_changed for install_dialog: {e}")
            self._install_dialog = None
        elif sender == self._help_dialog:
            try:
                self.language_changed.disconnect(self._help_dialog.retranslate_ui)
            except (TypeError, RuntimeError):
                pass
            self._help_dialog = None

    def set_processing_state_in_view(self, is_processing: bool, message: str = "", message_key: str = None, format_args: dict = None):
        """Proxy method for calling set_processing_state in view."""
        if message_key:
            translated_message = tr(message_key)
            self._app_state.set_processing_state(is_processing, translated_message)
        else:
            self._app_state.set_processing_state(is_processing, message)

        if hasattr(self._view, 'set_processing_state'):
            self._view.set_processing_state(is_processing, None, message_key, format_args)
        else:
            logger.warning("View does not have set_processing_state method")
