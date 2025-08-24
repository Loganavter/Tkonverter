import logging
import os
import re

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QMouseEvent
from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QWidget

from core.dependency_injection import setup_container
from core.conversion.utils import markdown_to_html_for_preview
from core.settings import SettingsManager
from presenters.modern_presenter import ModernTkonverterPresenter
from resources.translations import set_language, tr
from ui.font_manager import FontManager
from ui.layout_manager import LayoutManager
from ui.theme import ThemeManager
from ui.tkonverter_main_window_ui import Ui_TkonverterMainWindow
from ui.widgets.atomic.minimalist_scrollbar import MinimalistScrollBar
from utils.paths import resource_path

main_window_logger = logging.getLogger("MainWindow")
main_window_logger.setLevel(logging.ERROR)

MAX_LOG_MESSAGES = 200

class TkonverterMainWindow(QWidget):
    config_changed = pyqtSignal(str, object)
    save_button_clicked = pyqtSignal()
    settings_button_clicked = pyqtSignal()
    install_manager_button_clicked = pyqtSignal()
    recalculate_clicked = pyqtSignal()
    calendar_button_clicked = pyqtSignal()
    diagram_button_clicked = pyqtSignal()
    help_button_clicked = pyqtSignal()

    def __init__(self, initial_theme: str, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        self._log_messages: list[tuple[str, str, dict]] = []
        self._initial_sizing_done = False

        self.settings_manager = SettingsManager("tkonverter", "tkonverter")

        ui_settings = self.settings_manager.load_ui_settings()

        if not ui_settings.get("my_name"):
            ui_settings["my_name"] = tr("Me")
        if not ui_settings.get("partner_name"):
            ui_settings["partner_name"] = tr("Partner")

        ui_settings.setdefault("profile", "group")
        ui_settings.setdefault("auto_detect_profile", True)
        ui_settings.setdefault("auto_recalc", False)

        self.settings_manager.save_ui_settings(ui_settings)

        set_language(self.settings_manager.load_language())

        self.theme_manager = ThemeManager.get_instance()

        self.font_manager = FontManager.get_instance()
        self.font_manager.font_changed.connect(self._on_font_changed)

        self.font_manager.apply_from_settings(self.settings_manager)

        self.ui = Ui_TkonverterMainWindow()
        self.ui.setupUi(self)

        log_scrollbar = MinimalistScrollBar(self.ui.log_output)
        self.ui.log_output.setVerticalScrollBar(log_scrollbar)
        self.ui.log_output.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        preview_scrollbar = MinimalistScrollBar(self.ui.preview_text_edit)
        self.ui.preview_text_edit.setVerticalScrollBar(preview_scrollbar)
        self.ui.preview_text_edit.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.setWindowTitle(tr("Tkonverter"))

        icon_path = resource_path("resources/icons/icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        di_container = setup_container()

        self.presenter = ModernTkonverterPresenter(
            view=self,
            settings_manager=self.settings_manager,
            theme_manager=self.theme_manager,
            app_instance=QApplication.instance(),
            di_container=di_container,
            initial_theme=initial_theme,
            initial_config=ui_settings,
        )

        self._connect_presenter_signals()

        self.theme_manager.theme_changed.connect(self._on_app_theme_changed)

        self.layout_manager = LayoutManager(self)

        left_min = int(self.layout_manager.calculate_left_column_width())
        middle_min = int(self.layout_manager.calculate_middle_column_width())
        right_min = int(self.layout_manager.calculate_right_column_width())

        self.ui.left_column.setMinimumWidth(left_min)
        self.ui.middle_column.setMinimumWidth(middle_min)
        self.ui.right_column.setMinimumWidth(right_min)

        self._update_ui_from_model()
        self._connect_ui_signals()
        self._initial_ui_setup()
        self._update_terminal_styles()
        self._update_preview_styles()

    def _on_font_changed(self):
        """Handles font change."""
        try:
            if hasattr(self, 'layout_manager'):
                self.layout_manager.handle_language_change()

            self._invalidate_adaptive_widgets_cache()
            self.update()
            self.updateGeometry()

        except Exception as e:
            main_window_logger.error(f"Error updating font: {e}")

    def _rebuild_terminal_content(self):
        """Rebuilds terminal content with current styles."""

        self.ui.log_output.blockSignals(True)
        self.ui.log_output.clear()
        for css_class, message, format_args in self._log_messages:
            display_message = self._translate_log_message(message, format_args)
            self.ui.log_output.append(f'<span class="{css_class}">{display_message}</span>')
        self.ui.log_output.ensureCursorVisible()
        self.ui.log_output.blockSignals(False)

    def _translate_log_message(self, message_or_key: str, format_args: dict) -> str:
        """Translates and formats log message with argument translation support."""

        TRANSLATABLE_ARG_KEYS = {"unit"}

        display_message = ""
        try:
            translated_text = tr(message_or_key)

            if format_args:
                translated_args = format_args.copy()

                for key, value in translated_args.items():
                    if key in TRANSLATABLE_ARG_KEYS and isinstance(value, str):

                        translated_value = tr(value.capitalize())
                        translated_args[key] = translated_value

                display_message = translated_text.format(**translated_args)
            else:
                display_message = translated_text
        except (KeyError, ValueError, IndexError) as e:
            main_window_logger.error(f"Error translating/formatting log: {e}. Key: '{message_or_key}', Arguments: {format_args}")
            display_message = message_or_key
        return display_message

    def _update_terminal_styles(self):
        """Updates terminal styles and rebuilds its content."""
        info_color = self.theme_manager.get_color("dialog.text").name()
        error_color = "#D70000" if self.theme_manager.is_dark() else "#FF0000"
        status_color = "#9E9E9E"

        stylesheet = f"""
        body {{ color: {info_color}; }}
        .info {{ color: {info_color}; }}
        .error {{ color: {error_color}; font-weight: bold; }}
        .status {{ color: {status_color}; }}
        """
        self.ui.log_output.document().setDefaultStyleSheet(stylesheet)

        self._rebuild_terminal_content()

    def _on_app_theme_changed(self):
        """Handles application theme change."""
        self._update_terminal_styles()
        self._update_preview_styles()

    def closeEvent(self, event):
        self._save_state()
        super().closeEvent(event)

    def _save_state(self):

        current_config = self.presenter.get_config()

        existing_ui_settings = self.settings_manager.load_ui_settings()

        existing_ui_settings.update(current_config)

        self.settings_manager.save_ui_settings(existing_ui_settings)

    def _update_ui_from_model(self):
        config = self.presenter.get_config()

        profile = config.get("profile")

        if profile == "group":
            self.ui.radio_group.setChecked(True)
        elif profile == "channel":
            self.ui.radio_channel.setChecked(True)
        elif profile == "posts":
            self.ui.radio_posts.setChecked(True)
        elif profile == "personal":
            self.ui.radio_personal.setChecked(True)

        self.ui.switch_show_time.setChecked(config.get("show_time", True))
        self.ui.switch_show_reactions.setChecked(config.get("show_reactions", True))
        self.ui.switch_reaction_authors.setChecked(
            config.get("show_reaction_authors", False)
        )
        self.ui.line_edit_my_name.setText(config.get("my_name", tr("Me")))
        self.ui.line_edit_partner_name.setText(
            config.get("partner_name", tr("Partner"))
        )
        self.ui.switch_show_optimization.setChecked(
            config.get("show_optimization", False)
        )
        self.ui.line_edit_streak_break_time.setText(
            config.get("streak_break_time", "20:00")
        )

        self.ui.switch_show_markdown.setChecked(config.get("show_markdown", True))
        self.ui.switch_show_links.setChecked(config.get("show_links", True))
        self.ui.switch_show_tech_info.setChecked(config.get("show_tech_info", True))
        self.ui.switch_show_service_notifications.setChecked(
            config.get("show_service_notifications", True)
        )
        self.ui.personal_names_group.setVisible(profile == "personal")

    def set_profile_in_ui(self, profile: str):
        self.ui.radio_group.blockSignals(True)
        self.ui.radio_channel.blockSignals(True)
        self.ui.radio_posts.blockSignals(True)
        self.ui.radio_personal.blockSignals(True)

        if profile == "group":
            self.ui.radio_group.setChecked(True)
        elif profile == "channel":
            self.ui.radio_channel.setChecked(True)
        elif profile == "posts":
            self.ui.radio_posts.setChecked(True)
        elif profile == "personal":
            self.ui.radio_personal.setChecked(True)

        is_personal = profile == "personal"
        self.ui.personal_names_group.setVisible(is_personal)

        self.ui.radio_group.blockSignals(False)
        self.ui.radio_channel.blockSignals(False)
        self.ui.radio_posts.blockSignals(False)
        self.ui.radio_personal.blockSignals(False)

    def set_analysis_unit(self, unit: str):
        if unit == "tokens":
            self.ui.recalculate_button.setText(tr("Recalculate"))
        else:
            self.ui.recalculate_button.setText(tr("Calculate"))

        self._update_analysis_display()

    def _on_language_changed(self):
        """
        Handles language change.
        This method should be the only point for UI updates after language change.
        """
        self.setWindowTitle(tr("Tkonverter"))

        if hasattr(self.ui, "retranslate_ui"):
            self.ui.retranslate_ui()

        from .widgets.atomic.fluent_switch import FluentSwitch
        for switch in self.findChildren(FluentSwitch):
            switch.retranslate_ui()

        self._rebuild_terminal_content()

        self._invalidate_adaptive_widgets_cache()

        self.presenter._generate_preview()

        self.retranslate_dynamic_ui()

        self._update_control_alignment()
        self.layout_manager.handle_language_change()

        self.updateGeometry()
        self.update()

    def _update_control_alignment(self):
        """Recalculates and sets the fixed width for the TimeLineEdit container to align it."""
        ref_switch = self.ui.switch_show_markdown
        self.ui.right_part_container.setFixedWidth(ref_switch.sizeHint().width())

    def _initial_ui_setup(self):

        self.ui.personal_names_group.hide()

        self._update_ui_from_model()

        self.ui.token_count_label.hide()
        self.ui.filtered_token_count_label.hide()

        app_state = self.presenter.get_app_state()
        self.set_analysis_unit(app_state.last_analysis_unit)

        self._update_analysis_display()

        self._handle_reactions_visibility_change(
            self.ui.switch_show_reactions.isChecked()
        )
        self._handle_optimization_visibility_change(
            self.ui.switch_show_optimization.isChecked()
        )

        self.presenter._generate_preview()

    def _connect_ui_signals(self):

        self.ui.radio_group.toggled.connect(self._handle_profile_change)
        self.ui.radio_channel.toggled.connect(self._handle_profile_change)
        self.ui.radio_posts.toggled.connect(self._handle_profile_change)
        self.ui.radio_personal.toggled.connect(self._handle_profile_change)

        self.ui.switch_show_time.checkedChanged.connect(
            self._handle_show_time_change
        )

        self.ui.switch_show_markdown.checkedChanged.connect(
            self._handle_show_markdown_change
        )
        self.ui.switch_show_reactions.checkedChanged.connect(
            self._handle_reactions_switch_change
        )

        self.ui.switch_reaction_authors.checkedChanged.connect(
            self._handle_show_reaction_authors_change
        )
        self.ui.line_edit_my_name.textChanged.connect(
            self._handle_my_name_change
        )
        self.ui.line_edit_partner_name.textChanged.connect(
            self._handle_partner_name_change
        )
        self.ui.switch_show_optimization.checkedChanged.connect(
            self._handle_optimization_switch_change
        )
        self.ui.line_edit_streak_break_time.textChanged.connect(
            self._handle_streak_break_time_change
        )
        self.ui.save_button.clicked.connect(self.save_button_clicked)
        self.ui.settings_button.clicked.connect(self.settings_button_clicked)
        self.ui.install_manager_button.clicked.connect(
            self.install_manager_button_clicked
        )
        self.ui.switch_show_links.checkedChanged.connect(
            self._handle_show_links_change
        )
        self.ui.switch_show_tech_info.checkedChanged.connect(
            self._handle_show_tech_info_change
        )
        self.ui.switch_show_service_notifications.checkedChanged.connect(
            self._handle_show_service_notifications_change
        )

        self.ui.recalculate_button.clicked.connect(self.recalculate_clicked)

        self.ui.calendar_button.clicked.connect(self.calendar_button_clicked)
        self.ui.diagram_button.clicked.connect(self.diagram_button_clicked)
        self.ui.help_button.clicked.connect(self.help_button_clicked)

    def _connect_presenter_signals(self):
        """Connects signals from presenter to view."""

        self.presenter.chat_loaded.connect(self.on_chat_loaded)
        self.presenter.profile_auto_detected.connect(self.set_profile_in_ui)
        self.presenter.preview_updated.connect(self.on_preview_updated)
        self.presenter.analysis_unit_changed.connect(self.set_analysis_unit)
        self.presenter.save_completed.connect(self.on_save_completed)
        self.presenter.analysis_count_updated.connect(self.on_analysis_count_updated)
        self.presenter.disabled_nodes_changed.connect(self._update_analysis_display)

        self.presenter.language_changed.connect(self._on_language_changed)

        self.ui.drop_zone.file_dropped.connect(self.presenter.on_file_dropped)
        self.ui.drop_zone.drop_zone_hover_state_changed.connect(self.presenter.on_drop_zone_hover_state_changed)
        self.ui.drop_zone.drop_zone_drag_active.connect(self.presenter.on_drop_zone_drag_active)

        self.presenter.set_drop_zone_style_command.connect(self.set_drop_zone_style)

    def on_chat_loaded(self, success: bool, message: str, chat_name: str):
        """Handles chat loading."""

        if success:
            file_path = self.presenter.get_current_file_path()
            if file_path:
                filename = os.path.basename(file_path)
                self.show_status(
                    tr("File loaded: {filename}").format(filename=filename),
                    is_error=False,
                    message_key="File loaded: {filename}",
                    format_args={"filename": filename}
                )

            if chat_name:
                self.show_status(
                    tr("Chat name: {name}").format(name=chat_name),
                    is_error=False,
                    message_key="Chat name: {name}",
                    format_args={"name": chat_name}
                )
        else:
            main_window_logger.error(f"Chat loading error: {message}")
            self.show_status(message, is_error=True)

    def on_preview_updated(self, raw_text: str, title: str):
        """Handles preview update, converting raw_text to HTML."""

        self.ui.set_preview_title(title)

        html_text = self._markdown_to_html(raw_text)

        self.ui.preview_text_edit.setHtml(html_text)

        QTimer.singleShot(100, lambda: self.ui.preview_text_edit.verticalScrollBar().setValue(0))

    def on_save_completed(self, success: bool, path_or_error: str):
        """Handles saving completion."""
        self.set_processing_state(False)
        if success:
            self.show_status(
                tr("File saved: {path}").format(path=path_or_error),
                message_key="File saved: {path}",
                format_args={"path": path_or_error},
            )
        else:
            self.show_status(
                tr("Error saving file: {error}").format(error=path_or_error),
                True,
                message_key="Error saving file: {error}",
                format_args={"error": path_or_error},
            )

    def on_analysis_count_updated(self, count: int, unit: str):
        """Handles analysis count update."""
        self._update_analysis_display()

        if count > 0:

            if unit == "tokens":
                message_key = "Tokens calculated: {count}"
            else:
                message_key = "Characters calculated: {count}"

            self.show_status(
                tr(message_key).format(count=f"{count:,}"),
                message_key=message_key,
                format_args={"count": f"{count:,}"}
            )

    def _show_diagram_placeholder(self):
        QMessageBox.information(
            self,
            tr("Token Analysis"),
            tr("Token analysis feature is under development."),
        )

    def _handle_reactions_switch_change(self, is_checked: bool):
        self.config_changed.emit("show_reactions", is_checked)
        self._handle_reactions_visibility_change(is_checked)

    def _handle_reactions_visibility_change(self, is_reactions_visible: bool):
        self.ui.label_reaction_authors.setVisible(is_reactions_visible)
        self.ui.switch_reaction_authors.setVisible(is_reactions_visible)

        self.layout_manager.handle_visibility_change(
            "reaction_authors", is_reactions_visible
        )

    def _handle_optimization_switch_change(self, is_checked: bool):
        self.config_changed.emit("show_optimization", is_checked)
        self._handle_optimization_visibility_change(is_checked)

    def _handle_optimization_visibility_change(self, is_optimization_visible: bool):
        self.ui.streak_time_container.setVisible(is_optimization_visible)

        self.layout_manager.handle_visibility_change(
            "streak_time_container", is_optimization_visible
        )

    def _handle_profile_change(self):

        is_personal = self.ui.radio_personal.isChecked()

        self.ui.personal_names_group.setVisible(is_personal)

        self.layout_manager.handle_visibility_change(
            "personal_names_group", is_personal
        )

        if self.ui.radio_group.isChecked():
            profile = "group"
        elif self.ui.radio_channel.isChecked():
            profile = "channel"
        elif self.ui.radio_posts.isChecked():
            profile = "posts"
        else:
            profile = "personal"

        self.config_changed.emit("profile", profile)

    def set_drop_zone_style(self, style_sheet_str: str):
        """Sets style for the drop zone (command from Presenter)."""
        self.ui.drop_zone.setStyleSheet(style_sheet_str)

    def update_example_preview(self, text: str):
        self.ui.preview_text_edit.setHtml(text)

        QTimer.singleShot(100, lambda: self.ui.preview_text_edit.verticalScrollBar().setValue(0))

    def _update_analysis_display(self):
        """Updates all widgets related to analysis based on current state."""
        app_state = self.presenter.get_app_state()
        unit = app_state.last_analysis_unit

        label_key = "Tokens:" if unit == "tokens" else "Characters:"
        self.ui.tokens_label.setText(tr(label_key))

        if not app_state.has_analysis_data():
            self.ui.token_count_label.setText(tr("N/A"))
            self.ui.token_count_label.show()
            self.ui.filtered_token_count_label.hide()
            return

        total_count = app_state.analysis_result.total_count
        stats = self.presenter.get_analysis_stats()
        filtered_count = stats.get("filtered_count", total_count) if stats else total_count

        has_filter = app_state.has_disabled_nodes() and int(filtered_count) != total_count

        if has_filter:
            self.ui.token_count_label.setText(f"<s>{total_count:,}</s>")
            self.ui.filtered_token_count_label.setText(f"→ {filtered_count:,.0f}")
            self.ui.filtered_token_count_label.show()
        else:
            self.ui.token_count_label.setText(f"{total_count:,}")
            self.ui.filtered_token_count_label.hide()

        self.ui.token_count_label.show()

    def _handle_show_time_change(self, is_checked: bool):
        """Handles show time option change."""
        self.config_changed.emit("show_time", is_checked)

    def _handle_show_markdown_change(self, is_checked: bool):
        """Handles show markdown option change."""
        self.config_changed.emit("show_markdown", is_checked)

    def _handle_show_reaction_authors_change(self, is_checked: bool):
        """Handles show reaction authors option change."""
        self.config_changed.emit("show_reaction_authors", is_checked)

    def _handle_my_name_change(self, text: str):
        """Handles my name change."""
        self.config_changed.emit("my_name", text)

    def _handle_partner_name_change(self, text: str):
        """Handles partner name change."""
        self.config_changed.emit("partner_name", text)

    def _handle_streak_break_time_change(self, text: str):
        """Handles streak break time change."""
        self.config_changed.emit("streak_break_time", text)

    def _handle_show_links_change(self, is_checked: bool):
        """Handles show links option change."""
        self.config_changed.emit("show_links", is_checked)

    def _handle_show_tech_info_change(self, is_checked: bool):
        """Handles show tech info option change."""
        self.config_changed.emit("show_tech_info", is_checked)

    def _handle_show_service_notifications_change(self, is_checked: bool):
        """Handles show service notifications option change."""
        self.config_changed.emit("show_service_notifications", is_checked)

    def retranslate_dynamic_ui(self):
        """Translates dynamic parts of UI that are not handled by retranslate_ui."""
        self._update_analysis_display()

    def show_status(
        self,
        message: str = "",
        is_error: bool = False,
        message_key: str = None,
        format_args: dict = None,
        is_status: bool = False,
    ):
        """Shows message in terminal, performing translation manually."""
        if is_status:
            css_class = "status"
        else:
            css_class = "error" if is_error else "info"

        if message_key:
            self._log_messages.append((css_class, message_key, format_args or {}))
        else:

            self._log_messages.append((css_class, message, {}))

        self._log_messages = self._log_messages[-MAX_LOG_MESSAGES:]

        display_message = self._translate_log_message(message_key or message, format_args or {})

        self.ui.log_output.append(f'<span class="{css_class}">{display_message}</span>')
        self.ui.log_output.ensureCursorVisible()

    def set_processing_state(self, is_processing: bool, message: str | None = None, message_key: str = None, format_args: dict = None):
        """Sets processing state with translation key support."""

        if is_processing and (message or message_key):
            css_class = "status"

            if message_key:
                self._log_messages.append((css_class, message_key, format_args or {}))
            else:
                self._log_messages.append((css_class, message, {}))
            self._log_messages = self._log_messages[-MAX_LOG_MESSAGES:]

            display_message = self._translate_log_message(message_key or message, format_args or {})

            if display_message:
                self.ui.log_output.append(f'<span class="{css_class}">{display_message}</span>')
                self.ui.log_output.ensureCursorVisible()

    def _setup_automatic_sizing(self):
        """Sets up automatic window sizing."""
        try:
            min_size = self.layout_manager.calculate_minimum_window_size()
            self.setMinimumSize(min_size)

            initial_width = max(min_size.width(), 1000)
            initial_height = max(min_size.height(), 600)
            self.resize(initial_width, initial_height)

        except Exception as e:
            main_window_logger.error(f"Error setting up automatic sizes: {e}")
            import traceback
            main_window_logger.error(f"Traceback: {traceback.format_exc()}")
            self.resize(1000, 600)

    def _invalidate_adaptive_widgets_cache(self):
        """Resets sizes of all adaptive widgets."""
        try:
            from ui.widgets.atomic.adaptive_label import AdaptiveLabel, CompactLabel

            for widget in self.findChildren(AdaptiveLabel):
                if hasattr(widget, "invalidate_size_cache"):
                    widget.invalidate_size_cache()

            for widget in self.findChildren(CompactLabel):
                if hasattr(widget, "invalidate_size_cache"):
                    widget.invalidate_size_cache()

        except Exception as e:
            main_window_logger.error(f"Error resetting adaptive widget caches: {e}")

    def _update_preview_styles(self):
        """Updates CSS styles for the preview QTextEdit."""
        theme = self.theme_manager
        text_color = theme.get_color("dialog.text").name()
        link_color = theme.get_color("accent").name()
        spoiler_bg = theme.get_color("dialog.button.hover").name()
        code_bg = theme.get_color("dialog.button.hover").name()

        stylesheet = f"""
        body {{ color: {text_color}; }}
        a {{ color: {link_color}; text-decoration: none; }}
        .spoiler {{
            background-color: {spoiler_bg};
            color: {spoiler_bg};
            border-radius: 3px;
            padding: 1px 3px;
        }}
        .spoiler:hover {{
            color: {text_color};
        }}
        code {{
            background-color: {code_bg};
            border-radius: 3px;
            font-family: monospace;
            padding: 1px 3px;
        }}
        """
        self.ui.preview_text_edit.document().setDefaultStyleSheet(stylesheet)
        self.ui.preview_text_edit.setHtml(self.ui.preview_text_edit.toHtml())

    def _markdown_to_html(self, text: str) -> str:
        """Converts simple markdown-like text to basic HTML for preview."""
        html_result = markdown_to_html_for_preview(text)
        return html_result

    def retranslate_ui(self):
        """Updates translations in UI."""
        try:
            self.setWindowTitle(tr("Tkonverter"))

            if hasattr(self.ui, "retranslate_ui"):
                self.ui.retranslate_ui()
        except Exception as e:
            main_window_logger.error(f"Error updating translations: {e}")

    def refresh_theme_styles(self):
        """Forces main window styles to update."""
        try:
            self.style().unpolish(self)
            self.style().polish(self)
            self._update_terminal_styles()
            self.update()
            self.updateGeometry()
        except Exception as e:
            main_window_logger.error(f"Error refreshing main window styles: {e}")

    def show_message_box(self, title: str, text: str, icon_type: QMessageBox.Icon = QMessageBox.Icon.Information):
        """Shows message box."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setIcon(icon_type)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        self.theme_manager.apply_theme_to_dialog(msg_box)
        msg_box.exec()

    def bring_dialog_to_front(self, dialog: QDialog, dialog_name: str):
        """Reliably brings dialog to the front (delegating to Presenter)."""
        from PyQt6.QtCore import QTimer

        try:
            if dialog.isMinimized():
                dialog.setWindowState(dialog.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)

            if not dialog.isVisible():
                dialog.show()

            dialog.raise_()
            dialog.activateWindow()

            QTimer.singleShot(50, lambda: self._force_dialog_focus(dialog, dialog_name))

        except Exception as e:
            main_window_logger.error(f"Error bringing up {dialog_name} dialog: {e}")

    def _force_dialog_focus(self, dialog: QDialog, dialog_name: str):
        """Forcibly sets focus on dialog."""
        try:
            if dialog and not dialog.isActiveWindow():
                dialog.setFocus()
                dialog.repaint()

                if not dialog.isActiveWindow():
                    dialog.show()
                    dialog.raise_()
                    dialog.activateWindow()

        except Exception as e:
            main_window_logger.error(f"Error forcing {dialog_name} dialog activation: {e}")

    def showEvent(self, event):
        """Called before the window is shown for the first time."""
        super().showEvent(event)

        if not self._initial_sizing_done:

            try:
                longest_preview_html = self.presenter.get_longest_preview_html()

                if longest_preview_html:
                    self.layout_manager.calculate_and_set_preview_height(longest_preview_html)
                else:
                    main_window_logger.warning("HTML not received, skipping preview height calculation.")

                self._initial_sizing_done = True

                self.presenter._generate_preview()

            except Exception as e:
                main_window_logger.error(f"Error during initial size setup: {e}")
                import traceback
                main_window_logger.error(f"Traceback: {traceback.format_exc()}")
                main_window_logger.warning("Continuing without preview size setup")

    def mousePressEvent(self, event: QMouseEvent):
        """Removes focus from input fields when clicking on empty area."""
        self.clear_input_focus()
        super().mousePressEvent(event)

    def clear_input_focus(self):
        """Removes focus if it's set on QLineEdit or TimeLineEdit."""
        focused_widget = self.focusWidget()
        if not focused_widget:
            return

        is_my_name = focused_widget == self.ui.line_edit_my_name
        is_partner_name = focused_widget == self.ui.line_edit_partner_name
        is_streak_time = (focused_widget == self.ui.line_edit_streak_break_time or
                          focused_widget.parent() == self.ui.line_edit_streak_break_time)

        if is_my_name or is_partner_name or is_streak_time:
            focused_widget.clearFocus()
