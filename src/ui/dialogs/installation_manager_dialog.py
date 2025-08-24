import importlib.util

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.settings import SettingsManager
from resources.translations import tr
from ui.dialogs.dialog_builder import auto_size_dialog, setup_dialog_scaffold, setup_dialog_icon
from ui.theme import ThemeManager
from ui.widgets.atomic.custom_button import CustomButton
from ui.widgets.atomic.custom_line_edit import CustomLineEdit
from ui.widgets.atomic.minimalist_scrollbar import MinimalistScrollBar

class InstallationManagerDialog(QDialog):
    install_triggered = pyqtSignal()
    remove_model_triggered = pyqtSignal()
    load_model_triggered = pyqtSignal(str)

    def __init__(
        self,
        is_installed: bool,
        is_loaded: bool,
        loaded_model_name: str | None,
        settings_manager: SettingsManager,
        settings: dict,
        model_in_cache: bool = False,
        theme_manager=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("AI Component Management"))
        setup_dialog_icon(self)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setMinimumSize(500, 450)

        main_layout = QVBoxLayout(self)

        self.loaded_model_name = loaded_model_name
        self.is_installed = is_installed
        self.is_loaded = is_loaded
        self.model_in_cache = model_in_cache
        self._settings_manager = settings_manager
        self._theme_manager = theme_manager or ThemeManager.get_instance()
        self._restart_needed = False
        status_group, status_layout, _ = self._create_styled_group(tr("Status:"))
        status_inner_layout = QVBoxLayout()
        status_inner_layout.setSpacing(2)

        library_status_layout = QHBoxLayout()
        library_status_label = QLabel(tr("Library Status:"))
        self.status_label = QLabel()
        library_status_layout.addWidget(library_status_label)
        library_status_layout.addWidget(self.status_label)
        library_status_layout.addStretch()
        status_inner_layout.addLayout(library_status_layout)

        model_status_layout = QHBoxLayout()
        model_status_label = QLabel(tr("Loaded Model:"))
        self.loaded_model_label = QLabel()
        self.loaded_model_label.setStyleSheet("font-style: italic;")
        model_status_layout.addWidget(model_status_label)
        model_status_layout.addWidget(self.loaded_model_label)
        model_status_layout.addStretch()
        status_inner_layout.addLayout(model_status_layout)

        status_layout.addLayout(status_inner_layout)

        actions_group, actions_layout, _ = self._create_styled_group(tr("Actions"))
        self.install_button = CustomButton(
            None, tr("Install/Update transformers library")
        )
        self.install_button.setToolTip(tr("This action requires restart"))
        self.install_button.clicked.connect(self.install_triggered.emit)
        self.remove_button = CustomButton(None, tr("Remove Model from Cache"))
        self.remove_button.setToolTip(
            tr(
                "Removes the model specified in the configuration from the local cache to free up disk space."
            )
        )
        self.remove_button.clicked.connect(self.remove_model_triggered.emit)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.install_button)
        buttons_layout.addWidget(self.remove_button)
        actions_layout.addLayout(buttons_layout)

        self.load_on_startup_checkbox = QCheckBox(tr("Load AI components on startup"))
        actions_layout.addWidget(self.load_on_startup_checkbox)

        config_group, config_layout, _ = self._create_styled_group(tr("Configuration"))
        model_layout = QHBoxLayout()
        model_label = QLabel(tr("Hugging Face Model:"))
        self.model_name_edit = CustomLineEdit()
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_name_edit)
        config_layout.addLayout(model_layout)

        buttons_layout = QHBoxLayout()
        self.load_model_button = CustomButton(None, tr("Load Model"))
        self.load_model_button.clicked.connect(self._on_load_model_clicked)
        self.reset_button = CustomButton(None, tr("Reset to Default"))
        self.reset_button.clicked.connect(self._reset_model_name)
        buttons_layout.addWidget(self.load_model_button)
        buttons_layout.addWidget(self.reset_button)
        config_layout.addLayout(buttons_layout)

        log_group, log_layout, _ = self._create_styled_group(tr("Terminal Output"))

        log_container = QFrame()
        log_container.setObjectName("logOutputContainer")

        log_container.setStyleSheet("""
            QFrame#logOutputContainer {
                border: 1px solid @dialog.border;
                border-radius: 6px;
                background-color: @dialog.input.background;
            }
        """.replace("@dialog.border", self._theme_manager.get_color("dialog.border").name())
           .replace("@dialog.input.background", self._theme_manager.get_color("dialog.input.background").name()))

        container_layout = QVBoxLayout(log_container)
        container_layout.setContentsMargins(5, 5, 5, 5)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        self.log_output.setStyleSheet("border: none; background: transparent;")

        self.log_output.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.log_output.viewport().setCursor(Qt.CursorShape.ArrowCursor)

        log_scrollbar = MinimalistScrollBar(self.log_output)
        self.log_output.setVerticalScrollBar(log_scrollbar)
        self.log_output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._setup_terminal_styling()

        container_layout.addWidget(self.log_output)

        log_layout.addWidget(log_container)

        main_layout.addWidget(status_group)
        main_layout.addWidget(actions_group)
        main_layout.addWidget(config_group)
        main_layout.addWidget(log_group, 1)

        setup_dialog_scaffold(
            self,
            main_layout,
            ok_text=tr("OK"),
            cancel_text=tr("Close"),
            show_cancel_button=True,
        )
        self.cancel_button.setText(tr("Close"))

        self.load_on_startup_checkbox.setChecked(settings.get("load_on_startup", True))
        self.model_name_edit.setText(
            settings.get(
                "tokenizer_model", self._settings_manager.get_default_tokenizer_model()
            )
        )

        self.model_name_edit.textChanged.connect(self._on_model_name_changed)

        self.set_status(is_installed, is_loaded, model_in_cache=model_in_cache)

        self._update_ui_elements()

        self.repaint()

        auto_size_dialog(self, min_width=500, min_height=450)

    def _reset_model_name(self):
        self.model_name_edit.setText(
            self._settings_manager.get_default_tokenizer_model()
        )

    def set_status(
        self,
        is_installed: bool,
        is_loaded: bool,
        message: str | None = None,
        model_in_cache: bool | None = None,
        loaded_model_name: str | None = None,
    ):
        if model_in_cache is not None:
            self.model_in_cache = model_in_cache

        if loaded_model_name is not None:
            self.loaded_model_name = loaded_model_name

        if message:
            status_text = message
            color = "#FFA500"
        elif is_installed and is_loaded:
            status_text = tr("Installed (active)")
            color = "#00B300"
        elif is_installed and not is_loaded:

            status_text = tr("Installed (model not loaded)")
            color = "#00B300"
        else:
            status_text = tr("Not installed")
            color = "#D70000"

        self.status_label.clear()
        self.status_label.setText(f'<b style="color:{color};">{status_text}</b>')

        self.is_installed = importlib.util.find_spec("transformers") is not None
        self.remove_button.setEnabled(self.is_installed and self.model_in_cache)

        self.loaded_model_label.clear()

        if is_loaded and self.loaded_model_name:
            self.loaded_model_label.setText(
                f'<b style="color:#00B300;">{self.loaded_model_name}</b>'
            )
            self.loaded_model_label.show()
        else:
            model_name = (
                self.model_name_edit.text().strip()
                if hasattr(self, "model_name_edit")
                else ""
            )

            if is_installed and not is_loaded and self.model_in_cache and model_name:
                self.loaded_model_label.setText(
                    f'<b style="color:#00B300;">{model_name} ({tr("in cache")})</b>'
                )
            else:
                self.loaded_model_label.setText(
                    f'<b style="color:#D70000;">{tr("None")}</b>'
                )
            self.loaded_model_label.show()

        self.status_label.repaint()
        self.loaded_model_label.repaint()

    def get_settings(self) -> dict:
        return {
            "load_on_startup": self.load_on_startup_checkbox.isChecked(),
            "tokenizer_model": self.model_name_edit.text().strip(),
        }

    def set_actions_enabled(self, enabled: bool):
        self.install_button.setEnabled(enabled)
        self.remove_button.setEnabled(enabled)
        self.load_model_button.setEnabled(enabled)
        self.ok_button.setEnabled(enabled)

    def _setup_terminal_styling(self):
        """Sets up terminal styling as in main window."""
        try:
            theme_manager = ThemeManager.get_instance()
            info_color = theme_manager.get_color("dialog.text").name()
            error_color = "#D70000" if theme_manager.is_dark() else "#FF0000"
            status_color = "#9E9E9E"

            stylesheet = f"""
            body {{ color: {info_color}; }}
            .info {{ color: {info_color}; }}
            .error {{ color: {error_color}; font-weight: bold; }}
            .status {{ color: {status_color}; }}
            """
            self.log_output.document().setDefaultStyleSheet(stylesheet)

        except Exception:

            stylesheet = """
            body { color: #333; }
            .info { color: #333; }
            .error { color: #FF0000; font-weight: bold; }
            .status { color: #9E9E9E; }
            """
            self.log_output.document().setDefaultStyleSheet(stylesheet)

    def append_log(self, text: str):

        self.log_output.append(text)
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )

    def is_restart_needed(self) -> bool:
        return self._restart_needed

    def on_action_finished(
        self,
        success: bool,
        message: str,
        new_is_installed: bool,
        new_is_loaded: bool,
        model_in_cache: bool = None,
        loaded_model_name: str = None,
    ):

        self.set_status(
            new_is_installed,
            new_is_loaded,
            model_in_cache=model_in_cache,
            loaded_model_name=loaded_model_name,
        )

        self.set_actions_enabled(True)

    def _create_styled_group(self, title_text: str):
        group_widget = QWidget()
        group_widget._title_padding = 15
        group_frame = QFrame(group_widget)
        group_frame.setObjectName("StyledGroupFrame")
        title_label = None
        title_height = 0
        if title_text:
            title_label = QLabel(title_text, group_widget)
            title_label.setObjectName("StyledGroupTitle")
            title_label.adjustSize()
            title_height = title_label.sizeHint().height()
            title_label.move(group_widget._title_padding * 2, 0)

            title_min_width = title_label.width() + group_widget._title_padding * 2 + group_widget._title_padding
            group_widget.setMinimumWidth(title_min_width)
        content_layout = QVBoxLayout(group_frame)
        content_margin_top = int(title_height * 0.8) if title_text else 10
        content_layout.setContentsMargins(10, content_margin_top, 10, 10)
        main_layout = QVBoxLayout(group_widget)
        main_layout.setContentsMargins(group_widget._title_padding, title_height // 2 if title_text else 0, 0, 0)
        main_layout.addWidget(group_frame)
        return group_widget, content_layout, title_label

    def _on_load_model_clicked(self):
        """Handles load model button click."""
        model_name = self.model_name_edit.text().strip()
        if model_name:
            self.load_model_triggered.emit(model_name)
        else:
            self.append_log(tr("Error: Model name cannot be empty"))

    def _on_model_name_changed(self):
        """Handles model name change."""

        self._update_cache_status()

    def _update_cache_status(self):
        """Updates cache status for current model."""
        if not self.is_installed:
            return

        try:
            from core.application.tokenizer_service import TokenizerService

            tokenizer_service = TokenizerService()

            model_name = self.model_name_edit.text().strip()
            if model_name:
                cache_info = tokenizer_service.check_model_cache(model_name)
                model_in_cache = cache_info.get("available", False)
                self.model_in_cache = model_in_cache

                self._update_ui_elements()

                if not self.is_loaded:
                    self.set_status(
                        self.is_installed, self.is_loaded, model_in_cache=model_in_cache
                    )
        except Exception as e:
            pass

    def _update_ui_elements(self):
        """Updates UI elements based on current status."""

        self.remove_button.setEnabled(self.is_installed and self.model_in_cache)

    def mousePressEvent(self, event: QMouseEvent):
        """Removes focus from input fields when clicking on empty area."""
        self.clear_input_focus()
        super().mousePressEvent(event)

    def clear_input_focus(self):
        """Removes focus if it's set on QLineEdit."""
        focused_widget = self.focusWidget()
        if focused_widget and isinstance(focused_widget, QLineEdit):
            focused_widget.clearFocus()

    def refresh_theme_styles(self):
        """Forces dialog styles to update."""
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        self.updateGeometry()
