import os
import re
from typing import Any, TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QEvent
from PyQt6.QtGui import QIcon, QMouseEvent, QKeyEvent
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox, QWidget, QLineEdit, QTextEdit, QPlainTextEdit

from src.core.settings_port import SettingsPort
from src.presenters.main_presenter import MainPresenter
from src.resources.translations import set_language, tr
from src.shared_toolkit.ui.managers.font_manager import FontManager
from src.ui.layout_manager import LayoutManager
from src.shared_toolkit.ui.managers.theme_manager import ThemeManager
from src.ui.main_window_ui import Ui_MainWindow
from src.shared_toolkit.ui.widgets.atomic import MinimalistScrollBar
from src.shared_toolkit.utils.paths import resource_path

if TYPE_CHECKING:
    from src.core.application.anonymizer_service import AnonymizerService
    from src.core.application.analysis_service import AnalysisService
    from src.core.application.calendar_service import CalendarService
    from src.core.application.chat_memory_service import ChatMemoryService
    from src.core.application.chat_service import ChatService
    from src.core.application.chart_service import ChartService
    from src.core.application.conversion_service import ConversionService
    from src.core.application.tokenizer_service import TokenizerService
    from src.presenters.preview_service import PreviewService

MAX_LOG_MESSAGES = 200

class MainWindow(QWidget):
    config_changed = pyqtSignal(str, object)
    save_button_clicked = pyqtSignal()
    quick_save_button_clicked = pyqtSignal()
    settings_button_clicked = pyqtSignal()
    anonymization_button_clicked = pyqtSignal()
    install_manager_button_clicked = pyqtSignal()
    recalculate_clicked = pyqtSignal()
    calendar_button_clicked = pyqtSignal()
    diagram_button_clicked = pyqtSignal()
    help_button_clicked = pyqtSignal()

    def __init__(
        self,
        initial_theme: str,
        settings_manager: SettingsPort,
        theme_manager: ThemeManager,
        font_manager: FontManager,
        chat_service: "ChatService",
        conversion_service: "ConversionService",
        analysis_service: "AnalysisService",
        calendar_service: "CalendarService",
        tokenizer_service: "TokenizerService",
        anonymizer_service: "AnonymizerService",
        preview_service: "PreviewService",
        chart_service: "ChartService",
        chat_memory_service: "ChatMemoryService",
        parent=None,
    ):
        super().__init__(parent)

        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setAutoFillBackground(True)

        self._log_messages: list[tuple[str, str, dict]] = []
        self._initial_sizing_done = False

        self.settings_manager = settings_manager

        ui_settings = self.settings_manager.load_ui_settings()

        if not ui_settings.get("my_name"):
            ui_settings["my_name"] = tr("Me")

        ui_settings.setdefault("anonymization", self.settings_manager.load_anonymization_settings())
        ui_settings.setdefault("profile", "group")
        ui_settings.setdefault("auto_detect_profile", True)
        ui_settings.setdefault("auto_recalc", False)
        ui_settings.setdefault("analysis_unit", "tokens")

        self.settings_manager.save_ui_settings(ui_settings)

        set_language(self.settings_manager.load_language())

        self.theme_manager = theme_manager
        self.font_manager = font_manager
        self.font_manager.font_changed.connect(self._on_font_changed)

        self.font_manager.apply_from_settings(self.settings_manager)

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        log_scrollbar = MinimalistScrollBar(Qt.Orientation.Vertical, self.ui.log_output)
        self.ui.log_output.setVerticalScrollBar(log_scrollbar)
        self.ui.log_output.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        preview_scrollbar = MinimalistScrollBar(Qt.Orientation.Vertical, self.ui.preview_text_edit)
        self.ui.preview_text_edit.setVerticalScrollBar(preview_scrollbar)
        self.ui.preview_text_edit.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.setWindowTitle(tr("app.name"))

        self.setMinimumSize(800, 500)
        self.resize(1000, 600)

        icon_path = resource_path("resources/icons/icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.presenter = MainPresenter(
            view=self,
            settings_manager=self.settings_manager,
            theme_manager=self.theme_manager,
            font_manager=self.font_manager,
            app_instance=QApplication.instance(),
            initial_theme=initial_theme,
            initial_config=ui_settings,
            chat_service=chat_service,
            conversion_service=conversion_service,
            analysis_service=analysis_service,
            tokenizer_service=tokenizer_service,
            anonymizer_service=anonymizer_service,
            preview_service=preview_service,
            chart_service=chart_service,
            calendar_service=calendar_service,
            chat_memory_service=chat_memory_service,
        )

        self._connect_presenter_signals()

        self.theme_manager.theme_changed.connect(self._on_app_theme_changed)

        self.layout_manager = LayoutManager(self)

        left_min = int(self.layout_manager.calculate_left_column_width())
        middle_min = int(self.layout_manager.calculate_middle_column_width())
        right_min = int(self.layout_manager.calculate_right_column_width())

        self.layout_manager.load_splitter_sizes()

        self.ui.left_column.setMinimumWidth(left_min)
        self.ui.middle_column.setMinimumWidth(middle_min)
        self.ui.right_column.setMinimumWidth(right_min)

        self.ui.left_column.setMaximumWidth(16777215)
        self.ui.middle_column.setMaximumWidth(16777215)
        self.ui.right_column.setMaximumWidth(16777215)

        self.updateGeometry()
        self.update()

        self._update_ui_from_model()
        self._connect_ui_signals()
        self._initial_ui_setup()
        self._update_terminal_styles()
        self._update_preview_styles()
        self._setup_automatic_sizing()

        saved_geometry = self.settings_manager.load_main_window_geometry()
        if saved_geometry:
            self.restoreGeometry(saved_geometry)

    def _on_font_changed(self):
        try:
            if hasattr(self, 'layout_manager'):
                self.layout_manager.handle_language_change()

            self._invalidate_adaptive_widgets_cache()
            self.update()
            self.updateGeometry()

        except Exception as e:
            pass

    def _rebuild_terminal_content(self):

        self.ui.log_output.blockSignals(True)
        self.ui.log_output.clear()
        for css_class, message, format_args in self._log_messages:
            display_message = self._translate_log_message(message, format_args)
            self.ui.log_output.append(f'<span class="{css_class}">{display_message}</span>')
        self.ui.log_output.ensureCursorVisible()
        self.ui.log_output.blockSignals(False)

    def _translate_log_message(self, message_or_key: str, format_args: dict) -> str:

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
            display_message = message_or_key
        return display_message

    def _update_terminal_styles(self):
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
        self._update_terminal_styles()
        self._update_preview_styles()

    def closeEvent(self, event):
        self._save_state()

        self.layout_manager.save_splitter_sizes()
        super().closeEvent(event)

    def _save_state(self):
        self.presenter.save_ui_state()
        try:
            geom = self.saveGeometry()
            if geom and not geom.isEmpty():
                self.settings_manager.save_main_window_geometry(geom)
        except Exception:
            pass

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
        anon_config = config.get("anonymization") or self.settings_manager.load_anonymization_settings()
        self.ui.switch_anonymization.setChecked(anon_config.get("enabled", False))
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

        if is_personal:

            partner_name = self.presenter.get_config_value("partner_name")
            if partner_name and partner_name != tr("Partner"):
                self.ui.line_edit_partner_name.setText(partner_name)

            my_name = self.presenter.get_config_value("my_name")
            if my_name and my_name != tr("Me"):
                self.ui.line_edit_my_name.setText(my_name)

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
        self.setWindowTitle(tr("app.name"))

        if hasattr(self.ui, "retranslate_ui"):
            self.ui.retranslate_ui()

        self._rebuild_terminal_content()

        self._invalidate_adaptive_widgets_cache()

        self.presenter.refresh_preview()

        self.retranslate_dynamic_ui()

        self._update_analysis_display()

        self._update_control_alignment()
        self.layout_manager.handle_language_change()

        self.updateGeometry()
        self.update()

    def _update_control_alignment(self):
        ref_switch = self.ui.switch_show_markdown
        self.ui.right_part_container.setFixedWidth(ref_switch.sizeHint().width())

    def _initial_ui_setup(self):

        self.ui.personal_names_group.hide()

        self._update_ui_from_model()

        self.ui.token_count_label.hide()
        self.ui.filtered_token_count_label.hide()

        self.set_analysis_unit(self.presenter.get_analysis_unit())

        self._update_analysis_display()

        self._handle_reactions_visibility_change(
            self.ui.switch_show_reactions.isChecked()
        )
        self._handle_optimization_visibility_change(
            self.ui.switch_show_optimization.isChecked()
        )

        self.presenter.refresh_preview()

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
        self.ui.line_edit_my_name.editingFinished.connect(
            self._handle_my_name_change
        )
        self.ui.line_edit_my_name.returnPressed.connect(
            self._handle_my_name_change
        )
        self.ui.line_edit_partner_name.editingFinished.connect(
            self._handle_partner_name_change
        )
        self.ui.line_edit_partner_name.returnPressed.connect(
            self._handle_partner_name_change
        )
        self.ui.switch_show_optimization.checkedChanged.connect(
            self._handle_optimization_switch_change
        )
        self.ui.line_edit_streak_break_time.editingFinished.connect(
            self._handle_streak_break_time_change
        )
        self.ui.line_edit_streak_break_time.returnPressed.connect(
            self._handle_streak_break_time_change
        )
        self.ui.save_button.clicked.connect(self.save_button_clicked)
        self.ui.quick_save_button.clicked.connect(self._on_quick_save_clicked)
        self.ui.settings_button.clicked.connect(self.settings_button_clicked)
        self.ui.anonymization_button.clicked.connect(self.anonymization_button_clicked)
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
        self.ui.switch_anonymization.checkedChanged.connect(
            self._handle_anonymization_switch_change
        )

        self.ui.recalculate_button.clicked.connect(self.recalculate_clicked)

        self.ui.calendar_button.clicked.connect(self.calendar_button_clicked)
        self.ui.diagram_button.clicked.connect(self.diagram_button_clicked)
        self.ui.help_button.clicked.connect(self.help_button_clicked)

    def _connect_presenter_signals(self):
        self.presenter.chat_loaded.connect(self.on_chat_loaded)
        self.presenter.profile_auto_detected.connect(self.set_profile_in_ui)
        self.presenter.preview_updated.connect(self.on_preview_updated)
        self.presenter.analysis_unit_changed.connect(self.set_analysis_unit)
        self.presenter.save_completed.connect(self.on_save_completed)
        self.presenter.analysis_count_updated.connect(self.on_analysis_count_updated)

        self.presenter.analysis_completed.connect(self._on_analysis_completed_update)
        self.presenter.disabled_nodes_changed.connect(self._update_analysis_display)

        self.presenter.language_changed.connect(self._on_language_changed)

        self.presenter.config_changed.connect(self.on_config_changed)

        self.ui.drop_zone.file_dropped.connect(self.presenter.on_file_dropped)
        self.ui.drop_zone.drop_zone_hover_state_changed.connect(self.presenter.on_drop_zone_hover_state_changed)
        self.ui.drop_zone.drop_zone_drag_active.connect(self.presenter.on_drop_zone_drag_active)

        self.presenter.set_drop_zone_style_command.connect(self.set_drop_zone_style)

    def on_chat_loaded(self, success: bool, message: str, chat_name: str):

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
            self.show_status(message, is_error=True)

    def on_preview_updated(self, raw_text: str, title: str):

        self.ui.set_preview_title(title)

        html_text = self.presenter.render_preview_html(raw_text)

        self.ui.preview_text_edit.setHtml(html_text)

        QTimer.singleShot(100, lambda: self.ui.preview_text_edit.verticalScrollBar().setValue(0))

    def on_save_completed(self, success: bool, path_or_error: str):
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

    def on_analysis_count_updated(self, count: int, unit: str, force_show_in_log: bool = False):
        self._update_analysis_display()

        if count > 0 and (force_show_in_log or not self.presenter.is_analysis_count_log_suppressed()):
            message_key = self.presenter.get_analysis_message_key(unit)

            self.show_status(
                tr(message_key).format(count=f"{count:,}"),
                message_key=message_key,
                format_args={"count": f"{count:,}"}
            )

    def _on_analysis_completed_update(self, tree_node):
        self._update_analysis_display()

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
        self.ui.drop_zone.setStyleSheet(style_sheet_str)

    def update_example_preview(self, text: str):
        self.ui.preview_text_edit.setHtml(text)

        QTimer.singleShot(100, lambda: self.ui.preview_text_edit.verticalScrollBar().setValue(0))

    def _update_analysis_display(self):
        display_model = self.presenter.get_analysis_display_model()
        self.ui.tokens_label.setText(tr(display_model["label_key"]))

        if display_model["total_text"] == "N/A":
            self.ui.token_count_label.setText(tr("N/A"))
            self.ui.filtered_token_count_label.hide()
            return

        self.ui.token_count_label.setText(display_model["total_text"])
        if display_model["show_filtered"]:
            self.ui.filtered_token_count_label.setText(display_model["filtered_text"])
            self.ui.filtered_token_count_label.show()
        else:
            self.ui.filtered_token_count_label.hide()

        self.ui.token_count_label.show()

    def refresh_analysis_display(self):
        self._update_analysis_display()

    def _handle_show_time_change(self, is_checked: bool):
        self.config_changed.emit("show_time", is_checked)

    def _handle_show_markdown_change(self, is_checked: bool):
        self.config_changed.emit("show_markdown", is_checked)

    def _handle_show_reaction_authors_change(self, is_checked: bool):
        self.config_changed.emit("show_reaction_authors", is_checked)

    def _handle_my_name_change(self):
        text = self.ui.line_edit_my_name.text()
        self.config_changed.emit("my_name", text)

    def _handle_partner_name_change(self):
        text = self.ui.line_edit_partner_name.text()
        self.config_changed.emit("partner_name", text)

    def on_config_changed(self, key: str, value: Any):
        if key == "partner_name":
            self.ui.line_edit_partner_name.setText(str(value))
            self.ui.line_edit_partner_name.setCursorPosition(0)

        elif key == "my_name":
            self.ui.line_edit_my_name.setText(str(value))

        elif key == "profile":
            is_personal = (value == "personal")
            self.ui.personal_names_group.setVisible(is_personal)
            if is_personal:
                current_partner = self.presenter.get_config_value("partner_name")
                self.ui.line_edit_partner_name.setText(str(current_partner))

        elif key == "anonymization" and isinstance(value, dict):
            self.ui.switch_anonymization.blockSignals(True)
            self.ui.switch_anonymization.setChecked(value.get("enabled", False))
            self.ui.switch_anonymization.blockSignals(False)

    def _handle_streak_break_time_change(self):
        text = self.ui.line_edit_streak_break_time.text()
        self.config_changed.emit("streak_break_time", text)

    def _handle_show_links_change(self, is_checked: bool):
        self.config_changed.emit("show_links", is_checked)

    def _handle_show_tech_info_change(self, is_checked: bool):
        self.config_changed.emit("show_tech_info", is_checked)

    def _handle_show_service_notifications_change(self, is_checked: bool):
        self.config_changed.emit("show_service_notifications", is_checked)

    def _handle_anonymization_switch_change(self, is_checked: bool):
        anon_config = self.presenter.get_config_value("anonymization") or self.settings_manager.load_anonymization_settings()
        anon_config = dict(anon_config)
        anon_config["enabled"] = is_checked
        self.settings_manager.save_anonymization_settings(anon_config)
        self.config_changed.emit("anonymization", anon_config)

    def retranslate_dynamic_ui(self):
        self._update_analysis_display()
        self._update_switch_translations()

    def _update_switch_translations(self):
        switches = [
            self.ui.switch_show_time,
            self.ui.switch_show_markdown,
            self.ui.switch_show_reactions,
            self.ui.switch_reaction_authors,
            self.ui.switch_show_optimization,
            self.ui.switch_show_links,
            self.ui.switch_show_tech_info,
            self.ui.switch_show_service_notifications,
            self.ui.switch_anonymization,
        ]

        for switch in switches:
            if hasattr(switch, 'update_translations'):
                switch.update_translations()

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
        try:
            min_size = self.layout_manager.calculate_minimum_window_size()
            self.setMinimumSize(min_size)

            w = max(self.size().width(), min_size.width(), 1000)
            h = max(self.size().height(), min_size.height(), 600)
            self.resize(w, h)
        except Exception:
            self.resize(1000, 600)

    def _invalidate_adaptive_widgets_cache(self):
        try:
            from src.shared_toolkit.ui.widgets.atomic.text_labels import AdaptiveLabel, CompactLabel

            for widget in self.findChildren(AdaptiveLabel):
                if hasattr(widget, "invalidate_size_cache"):
                    widget.invalidate_size_cache()

            for widget in self.findChildren(CompactLabel):
                if hasattr(widget, "invalidate_size_cache"):
                    widget.invalidate_size_cache()

        except Exception as e:
            pass

    def _update_preview_styles(self):
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
        return self.presenter.render_preview_html(text)

    def retranslate_ui(self):
        try:
            self.setWindowTitle(tr("app.name"))
            if hasattr(self.ui, "retranslate_ui"):
                self.ui.retranslate_ui()
        except Exception as e:
            pass

    def update_language(self, _lang_code: str | None = None):
        self._on_language_changed()

    def show_message_box(self, title: str, text: str, icon_type: QMessageBox.Icon = QMessageBox.Icon.Information):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setIcon(icon_type)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        self.theme_manager.apply_theme_to_dialog(msg_box)
        msg_box.exec()

    def refresh_theme_styles(self):
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        self.updateGeometry()

        if hasattr(self.ui, 'refresh_icons_for_current_theme'):
            self.ui.refresh_icons_for_current_theme()

    def apply_app_theme(self, new_palette):
        self.setPalette(new_palette)
        self.refresh_theme_styles()

    def create_anonymization_dialog(
        self,
        current_config: dict,
        known_names: list[str],
        known_domains: list[str],
    ):
        """Создаёт окно настроек анонимизации (немодальное, как прочие окна)."""
        from src.ui.dialogs.anonymization_settings_dialog import AnonymizationSettingsDialog

        dialog = AnonymizationSettingsDialog(
            current_config=current_config,
            settings_manager=self.settings_manager,
            known_names=known_names,
            known_domains=known_domains,
            parent=None,
        )
        self.theme_manager.apply_theme_to_dialog(dialog)
        return dialog

    def exec_export_dialog(
        self,
        suggested_filename: str,
        get_unique_path_func,
    ):
        """Executes export dialog and returns options on accept."""
        from src.ui.dialogs.export_dialog import ExportDialog

        dialog = ExportDialog(
            settings_manager=self.settings_manager,
            parent=self,
            suggested_filename=suggested_filename,
            get_unique_path_func=get_unique_path_func,
        )
        self.theme_manager.apply_theme_to_dialog(dialog)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_export_options()
        return None

    def create_export_dialog(self, suggested_filename: str, get_unique_path_func):
        from src.ui.dialogs.export_dialog import ExportDialog

        dialog = ExportDialog(
            settings_manager=self.settings_manager,
            parent=self,
            suggested_filename=suggested_filename,
            get_unique_path_func=get_unique_path_func,
        )
        self.theme_manager.apply_theme_to_dialog(dialog)
        return dialog

    def create_settings_dialog(self, **kwargs):
        from src.ui.dialogs.settings_dialog import SettingsDialog

        dialog = SettingsDialog(parent=self, **kwargs)
        self.theme_manager.apply_theme_to_dialog(dialog)
        return dialog

    def create_help_dialog(self, sections, current_language: str, app_name: str):
        from src.shared_toolkit.ui.dialogs.help_dialog import HelpDialog

        dialog = HelpDialog(sections, current_language, app_name, parent=self)
        self.theme_manager.apply_theme_to_dialog(dialog)
        return dialog

    def create_install_dialog(self, **kwargs):
        from src.ui.dialogs.install_dialog import InstallDialog

        dialog = InstallDialog(parent=self, **kwargs)
        self.theme_manager.apply_theme_to_dialog(dialog)
        return dialog

    def create_analysis_dialog(self, presenter, theme_manager, chart_service):
        from src.ui.dialogs.analysis.analysis_dialog import AnalysisDialog

        return AnalysisDialog(
            presenter=presenter,
            theme_manager=theme_manager,
            chart_service=chart_service,
            parent=self,
        )

    def create_calendar_dialog(
        self,
        presenter,
        messages: list,
        config: dict,
        theme_manager,
        root_node,
        initial_disabled_nodes,
        token_hierarchy,
        chat_id=None,
    ):
        """Creates and themes calendar dialog instance."""
        from src.ui.dialogs.calendar.calendar_dialog import CalendarDialog

        dialog = CalendarDialog(
            presenter=presenter,
            messages=messages,
            config=config,
            theme_manager=theme_manager,
            root_node=root_node,
            initial_disabled_nodes=initial_disabled_nodes,
            token_hierarchy=token_hierarchy,
            chat_id=chat_id,
            parent=self,
        )
        self.theme_manager.apply_theme_to_dialog(dialog)
        return dialog

    def bring_dialog_to_front(self, dialog: QDialog, dialog_name: str):
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
            pass

    def _force_dialog_focus(self, dialog: QDialog, dialog_name: str):
        try:
            if dialog and not dialog.isActiveWindow():

                from PyQt6.QtCore import QTimer
                QTimer.singleShot(10, lambda: self._delayed_dialog_focus(dialog))
        except Exception as e:
            pass

    def _delayed_dialog_focus(self, dialog: QDialog):
        try:
            if dialog and not dialog.isActiveWindow():
                dialog.setFocus()
                dialog.repaint()

                if not dialog.isActiveWindow():
                    dialog.show()
                    dialog.raise_()
                    dialog.activateWindow()
        except Exception as e:
            pass

    def showEvent(self, event):
        super().showEvent(event)

        if not self._initial_sizing_done:
            try:
                longest_preview_html = self.presenter.get_longest_preview_html()
                if longest_preview_html:
                    self.layout_manager.calculate_and_set_preview_height(longest_preview_html)

                self._initial_sizing_done = True
                self.layout_manager.set_window_visible()

                self.presenter.refresh_preview()
            except Exception:
                pass

    def mousePressEvent(self, event: QMouseEvent):
        self.clear_input_focus()
        super().mousePressEvent(event)

    def clear_input_focus(self):
        focused_widget = self.focusWidget()
        if not focused_widget:
            return

        is_my_name = focused_widget == self.ui.line_edit_my_name
        is_partner_name = focused_widget == self.ui.line_edit_partner_name
        is_streak_time = (focused_widget == self.ui.line_edit_streak_break_time or
                          focused_widget.parent() == self.ui.line_edit_streak_break_time)

        if is_my_name or is_partner_name or is_streak_time:
            focused_widget.clearFocus()

    def keyPressEvent(self, event: QKeyEvent):

        focused_widget = self.focusWidget()
        if focused_widget and isinstance(focused_widget, (QLineEdit, QTextEdit, QPlainTextEdit)):

            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key.Key_S and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if not event.isAutoRepeat():
                self.quick_save_button_clicked.emit()
            event.accept()
            return
        elif event.key() == Qt.Key.Key_S and event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            if not event.isAutoRepeat():
                self.save_button_clicked.emit()
            event.accept()
            return

        super().keyPressEvent(event)

    def _on_quick_save_clicked(self):
        self.quick_save_button_clicked.emit()
