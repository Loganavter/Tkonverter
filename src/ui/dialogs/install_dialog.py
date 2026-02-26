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

from src.core.settings_port import SettingsPort
from src.resources.translations import tr
from src.ui.dialogs.dialog_builder import auto_size_dialog, setup_dialog_scaffold, setup_dialog_icon
from src.shared_toolkit.ui.managers.theme_manager import ThemeManager
from src.shared_toolkit.ui.widgets.atomic.custom_button import CustomButton
from src.shared_toolkit.ui.widgets.atomic.custom_line_edit import CustomLineEdit
from src.shared_toolkit.ui.widgets.atomic import MinimalistScrollBar

class InstallDialog(QDialog):
    install_triggered = pyqtSignal()
    remove_model_triggered = pyqtSignal()
    load_model_triggered = pyqtSignal(str)

    def __init__(
        self,
        is_installed: bool,
        is_loaded: bool,
        loaded_model_name: str | None,
        settings_manager: SettingsPort,
        settings: dict,
        model_in_cache: bool = False,
        tokenizer_service=None,
        theme_manager=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("install.ai_component_management"))
        setup_dialog_icon(self)
        self.setMinimumSize(500, 450)

        main_layout = QVBoxLayout(self)

        self.loaded_model_name = loaded_model_name
        self.is_installed = is_installed
        self.is_loaded = is_loaded
        self.model_in_cache = model_in_cache
        self._settings_manager = settings_manager
        if theme_manager is None:
            raise ValueError("theme_manager must be provided via dependency injection")
        self._theme_manager = theme_manager
        self._tokenizer_service = tokenizer_service
        self._restart_needed = False
        status_group, status_layout, _ = self._create_styled_group(tr("install.status"))
        status_inner_layout = QVBoxLayout()
        status_inner_layout.setSpacing(2)

        library_status_layout = QHBoxLayout()
        library_status_label = QLabel(tr("install.library_status"))
        self.status_label = QLabel()
        library_status_layout.addWidget(library_status_label)
        library_status_layout.addWidget(self.status_label)
        library_status_layout.addStretch()
        status_inner_layout.addLayout(library_status_layout)

        model_status_layout = QHBoxLayout()
        model_status_label = QLabel(tr("install.loaded_model"))
        self.loaded_model_label = QLabel()
        self.loaded_model_label.setObjectName("loadedModelLabel")
        model_status_layout.addWidget(model_status_label)
        model_status_layout.addWidget(self.loaded_model_label)
        model_status_layout.addStretch()
        status_inner_layout.addLayout(model_status_layout)

        status_layout.addLayout(status_inner_layout)

        actions_group, actions_layout, _ = self._create_styled_group(tr("install.actions"))
        self.install_button = CustomButton(
            None, tr("install.install_transformers")
        )
        self.install_button.setToolTip(tr("install.requires_restart_tooltip"))
        self.install_button.clicked.connect(self.install_triggered.emit)
        self.remove_button = CustomButton(None, tr("install.remove_from_cache"))
        self.remove_button.setToolTip(tr("install.remove_tooltip"))
        self.remove_button.clicked.connect(self.remove_model_triggered.emit)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.install_button)
        buttons_layout.addWidget(self.remove_button)
        actions_layout.addLayout(buttons_layout)

        self.load_on_startup_checkbox = QCheckBox(tr("install.load_on_startup"))
        actions_layout.addWidget(self.load_on_startup_checkbox)

        config_group, config_layout, _ = self._create_styled_group(tr("install.configuration"))
        model_layout = QHBoxLayout()
        model_label = QLabel(tr("install.hugging_face_model"))
        self.model_name_edit = CustomLineEdit()
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_name_edit)
        config_layout.addLayout(model_layout)

        token_layout = QHBoxLayout()
        token_label = QLabel(tr("install.hf_token"))
        self.hf_token_edit = CustomLineEdit()
        self.hf_token_edit.setPlaceholderText(tr("install.hf_token_placeholder"))
        self.hf_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.hf_token_edit.setClearButtonEnabled(True)
        token_layout.addWidget(token_label)
        token_layout.addWidget(self.hf_token_edit)
        config_layout.addLayout(token_layout)
        token_hint = QLabel(tr("install.hf_token_hint"))
        token_hint.setObjectName("captionLabel")
        token_hint.setWordWrap(True)
        config_layout.addWidget(token_hint)

        buttons_layout = QHBoxLayout()
        self.load_model_button = CustomButton(None, tr("install.load_model"))
        self.load_model_button.clicked.connect(self._on_load_model_clicked)
        self.reset_button = CustomButton(None, tr("install.reset_to_default"))
        self.reset_button.clicked.connect(self._reset_model_name)
        buttons_layout.addWidget(self.load_model_button)
        buttons_layout.addWidget(self.reset_button)
        config_layout.addLayout(buttons_layout)

        log_group, log_layout, _ = self._create_styled_group(tr("install.terminal_output"))

        log_container = QFrame()
        log_container.setObjectName("logOutputContainer")

        container_layout = QVBoxLayout(log_container)
        container_layout.setContentsMargins(5, 5, 5, 5)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        self.log_output.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.log_output.viewport().setCursor(Qt.CursorShape.ArrowCursor)

        log_scrollbar = MinimalistScrollBar(Qt.Orientation.Vertical, self.log_output)
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
            ok_text=tr("common.ok"),
            cancel_text=tr("common.close"),
            show_cancel_button=True,
        )
        self.cancel_button.setText(tr("common.close"))

        self.load_on_startup_checkbox.setChecked(settings.get("load_on_startup", True))
        self.model_name_edit.setText(
            settings.get(
                "tokenizer_model", self._settings_manager.get_default_tokenizer_model()
            )
        )
        self.hf_token_edit.setText(settings.get("hf_token", "") or "")

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
            status_text = tr("install.installed_active")
            color = "#00B300"
        elif is_installed and not is_loaded:

            status_text = tr("install.installed_not_loaded")
            color = "#00B300"
        else:
            status_text = tr("install.not_installed")
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
                    f'<b style="color:#00B300;">{model_name} ({tr("install.in_cache")})</b>'
                )
            else:
                self.loaded_model_label.setText(
                    f'<b style="color:#D70000;">{tr("common.none")}</b>'
                )
            self.loaded_model_label.show()

        self.status_label.repaint()
        self.loaded_model_label.repaint()

    def get_settings(self) -> dict:
        return {
            "load_on_startup": self.load_on_startup_checkbox.isChecked(),
            "tokenizer_model": self.model_name_edit.text().strip(),
            "hf_token": self.hf_token_edit.text().strip(),
        }

    def set_actions_enabled(self, enabled: bool):
        self.install_button.setEnabled(enabled)
        self.remove_button.setEnabled(enabled)
        self.load_model_button.setEnabled(enabled)
        self.ok_button.setEnabled(enabled)

    def _setup_terminal_styling(self):
        try:
            info_color = self._theme_manager.get_color("dialog.text").name()
            error_color = "#D70000" if self._theme_manager.is_dark() else "#FF0000"
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
        model_name = self.model_name_edit.text().strip()
        if model_name:
            self.load_model_triggered.emit(model_name)
        else:
            self.append_log(tr("install.model_name_empty"))

    def _on_model_name_changed(self):

        self._update_cache_status()

    def _update_cache_status(self):
        if not self.is_installed or self._tokenizer_service is None:
            return

        try:
            model_name = self.model_name_edit.text().strip()
            if model_name:
                cache_info = self._tokenizer_service.check_model_cache(model_name)
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

        self.remove_button.setEnabled(self.is_installed and self.model_in_cache)

    def mousePressEvent(self, event: QMouseEvent):
        self.clear_input_focus()
        super().mousePressEvent(event)

    def clear_input_focus(self):
        focused_widget = self.focusWidget()
        if focused_widget and isinstance(focused_widget, QLineEdit):
            focused_widget.clearFocus()

    def refresh_theme_styles(self):
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        self.updateGeometry()
