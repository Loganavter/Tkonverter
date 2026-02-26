from collections import defaultdict
from datetime import datetime
from html import escape
from typing import Set

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QWheelEvent
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.analysis.tree_analyzer import TreeNode
from src.resources.translations import tr
from src.ui.dialogs.dialog_builder import auto_size_dialog, setup_dialog_scaffold, setup_dialog_icon
from src.ui.dialogs.calendar.calendar_rendering_service import CalendarRenderingService
from src.presenters.calendar_presenter import CalendarPresenter
from src.core.view_models import CalendarViewModel
from src.shared_toolkit.ui.managers.theme_manager import ThemeManager
from src.shared_toolkit.ui.widgets.atomic import CustomButton
from src.shared_toolkit.ui.widgets.atomic import MinimalistScrollBar

class NonPropagatingTextEdit(QTextEdit):
    def wheelEvent(self, event: QWheelEvent):
        scrollbar = self.verticalScrollBar()
        is_at_top = scrollbar.value() == scrollbar.minimum()
        is_at_bottom = scrollbar.value() == scrollbar.maximum()

        scrolling_down = event.angleDelta().y() < 0
        scrolling_up = event.angleDelta().y() > 0

        if (scrolling_up and is_at_top) or (scrolling_down and is_at_bottom):

            event.accept()
        else:

            super().wheelEvent(event)

class CalendarDialog(QDialog):
    filter_accepted = pyqtSignal(set)
    memory_changed = pyqtSignal()

    def __init__(
        self,
        presenter: CalendarPresenter,
        messages: list,
        config: dict,
        theme_manager: ThemeManager,
        root_node: TreeNode | None = None,
        initial_disabled_nodes: Set[TreeNode] | None = None,
        token_hierarchy: dict | None = None,
        chat_id: int | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.theme_manager = theme_manager

        self.messages = messages
        self.presenter = presenter
        self.rendering_service = CalendarRenderingService(self.theme_manager)
        self._is_edit_mode = False
        self._memory_dirty = False
        self._initial_disabled_nodes = set(initial_disabled_nodes or set())

        self.setWindowTitle(tr("dialog.calendar.title"))
        setup_dialog_icon(self)
        self.setMinimumSize(800, 600)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)

        self._setup_ui()
        self._connect_signals()
        self._update_preview_styles()

        self.presenter.load_calendar_data(
            raw_messages=messages,
            analysis_tree=root_node,
            initial_disabled_nodes=initial_disabled_nodes or set(),
            token_hierarchy=token_hierarchy,
            config=config,
            chat_id=chat_id,
        )

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        left_panel_widget = QWidget()
        left_panel_layout = QVBoxLayout(left_panel_widget)
        left_panel_layout.setContentsMargins(0, 0, 0, 0)

        header_layout = QHBoxLayout()
        self.prev_button = CustomButton(None, "<")
        self.title_button = QPushButton()
        self.next_button = CustomButton(None, ">")

        bg_color_obj = self.theme_manager.get_color("dialog.background")
        text_color_obj = self.theme_manager.get_color("dialog.text")
        r, g, b = (int(text_color_obj.red() * 0.8 + bg_color_obj.red() * 0.2),
                   int(text_color_obj.green() * 0.8 + bg_color_obj.green() * 0.2),
                   int(text_color_obj.blue() * 0.8 + bg_color_obj.blue() * 0.2))
        faded_title_color = QColor(r, g, b)
        self.title_button.setStyleSheet(f"""
            QPushButton {{
                border: none; background-color: transparent;
                color: {faded_title_color.name()}; font-weight: bold; font-size: 11pt;
            }}
            QPushButton:hover {{
                background-color: {self.theme_manager.get_color("dialog.button.hover").name()};
            }}
        """)

        header_layout.addWidget(self.prev_button)
        header_layout.addWidget(self.title_button, 1)
        header_layout.addWidget(self.next_button)

        self.view_stack = QStackedWidget()
        self.day_view_widget = self.rendering_service.create_day_view()
        self.month_view_widget = self.rendering_service.create_month_view()
        self.year_view_widget = self.rendering_service.create_year_view()

        self.view_stack.addWidget(self.day_view_widget)
        self.view_stack.addWidget(self.month_view_widget)
        self.view_stack.addWidget(self.year_view_widget)

        left_panel_layout.addLayout(header_layout)
        left_panel_layout.addWidget(self.view_stack, 1)

        right_panel_widget = QWidget()
        right_panel_layout = QVBoxLayout(right_panel_widget)
        self.date_label = QLabel(tr("dialog.calendar.date"))
        self.date_label.setObjectName("calendarDateLabel")

        self.text_view = NonPropagatingTextEdit()
        self.text_view.setReadOnly(True)

        self.text_view.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.text_view.viewport().setCursor(Qt.CursorShape.ArrowCursor)

        self.text_view.setVerticalScrollBar(MinimalistScrollBar(Qt.Orientation.Vertical, self.text_view))

        right_panel_layout.addWidget(self.date_label)
        right_panel_layout.addWidget(self.text_view, 1)

        edit_buttons_layout = QHBoxLayout()
        self.edit_button = QPushButton(tr("common.edit"))
        self.save_preview_button = QPushButton(tr("common.save"))
        self.revert_preview_button = QPushButton(tr("common.revert"))
        for btn in (self.edit_button, self.save_preview_button, self.revert_preview_button):
            btn.setProperty("class", "white-button")
        self.save_preview_button.setEnabled(False)
        self.revert_preview_button.setEnabled(False)
        edit_buttons_layout.addWidget(self.edit_button)
        edit_buttons_layout.addWidget(self.save_preview_button)
        edit_buttons_layout.addWidget(self.revert_preview_button)
        right_panel_layout.addLayout(edit_buttons_layout)

        main_layout.addWidget(left_panel_widget, 2)
        main_layout.addWidget(right_panel_widget, 3)
        layout.addWidget(main_widget, 1)

        setup_dialog_scaffold(
            self,
            layout,
            ok_text=tr("common.save"),
            cancel_text=tr("common.close"),
        )
        auto_size_dialog(self, min_width=800, min_height=600)

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
        self.text_view.document().setDefaultStyleSheet(stylesheet)

        if self.text_view.toPlainText():
            self.text_view.setHtml(self.text_view.toHtml())

    def _connect_signals(self):
        self.presenter.view_model_updated.connect(self.update_ui)
        self.presenter.messages_for_date_updated.connect(self._update_message_view)
        self.presenter.preview_conflict_detected.connect(self._on_preview_conflict)

        self.rendering_service.date_clicked.connect(self.presenter.select_date)
        self.rendering_service.month_selected.connect(self.presenter.select_month)
        self.rendering_service.year_selected.connect(self.presenter.select_year)

        self.rendering_service.date_context_menu.connect(self.presenter.toggle_filter_for_date)
        self.rendering_service.month_context_menu.connect(self.presenter.toggle_filter_for_month)
        self.rendering_service.year_context_menu.connect(self.presenter.toggle_filter_for_year)

        self.prev_button.clicked.connect(self.presenter.navigate_previous)
        self.next_button.clicked.connect(self.presenter.navigate_next)
        self.title_button.clicked.connect(self._on_title_clicked)
        self.edit_button.clicked.connect(self._on_edit_clicked)
        self.save_preview_button.clicked.connect(self._on_save_preview_clicked)
        self.revert_preview_button.clicked.connect(self._on_revert_preview_clicked)

    def get_disabled_nodes(self) -> set:
        return self.presenter.get_disabled_nodes()

    def _on_title_clicked(self):
        vm = self.presenter.get_current_view_model()
        if vm.view_mode == "days": self.presenter.set_view_mode("months")
        elif vm.view_mode == "months": self.presenter.set_view_mode("years")

    def update_ui(self, vm: CalendarViewModel):
        self.title_button.setText(vm.navigation_title)
        self.prev_button.setEnabled(vm.can_go_previous)
        self.next_button.setEnabled(vm.can_go_next)

        if vm.view_mode == "days":
            self.view_stack.setCurrentWidget(self.day_view_widget)
            self.rendering_service.update_day_view(vm)
        elif vm.view_mode == "months":
            self.view_stack.setCurrentWidget(self.month_view_widget)
            self.rendering_service.update_month_view(vm)
        elif vm.view_mode == "years":
            self.view_stack.setCurrentWidget(self.year_view_widget)
            self.rendering_service.update_year_view(vm, self.year_view_widget)

    def _update_message_view(self, html_text: str):

        if self.presenter and self.presenter.last_valid_selection:
            self.date_label.setText(self.presenter.last_valid_selection.toString(Qt.DateFormat.ISODate))
        else:
            self.date_label.setText(tr("dialog.calendar.date"))

        if not self._is_edit_mode:
            self.text_view.setHtml(html_text)

    def accept(self):

        if self._is_edit_mode:
            self._on_save_preview_clicked()

        final_disabled_nodes = self.presenter.get_disabled_nodes()
        self.presenter.filter_changed.emit(final_disabled_nodes)
        self.presenter.persist_chat_memory()
        if final_disabled_nodes != self._initial_disabled_nodes:
            self._memory_dirty = True
        if self._memory_dirty:
            self.memory_changed.emit()
        super().accept()

    def retranslate_ui(self):
        self.setWindowTitle(tr("dialog.calendar.title"))
        self.date_label.setText(tr("dialog.calendar.date"))
        self.ok_button.setText(tr("common.save"))
        self.cancel_button.setText(tr("common.close"))
        self.edit_button.setText(tr("common.edit"))
        self.save_preview_button.setText(tr("common.save"))
        self.revert_preview_button.setText(tr("common.revert"))

        self.rendering_service.retranslate_ui()

        if self.presenter:
            self.presenter._update_view_model()

        if self.presenter and self.presenter.last_valid_selection:

            html_text = self.presenter.get_messages_html_for_date(self.presenter.last_valid_selection)
            self._update_message_view(html_text)
        elif self.text_view.toPlainText() == "No messages on this date.":
             self.text_view.setPlainText(tr("dialog.calendar.no_messages"))

    def refresh_theme_styles(self):
        self.style().unpolish(self)
        self.style().polish(self)
        self._update_preview_styles()
        self.update()
        self.updateGeometry()

    def wheelEvent(self, event: QWheelEvent):
        vm = self.presenter.get_current_view_model()
        if vm.view_mode != "days":
            event.ignore()
            return

        delta = event.angleDelta().y()
        if delta > 0:
            self.presenter.navigate_previous()
        elif delta < 0:
            self.presenter.navigate_next()

        event.accept()

    def _set_edit_mode(self, enabled: bool):
        self._is_edit_mode = enabled
        self.text_view.setReadOnly(not enabled)
        if enabled:
            self.text_view.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
            self.text_view.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        else:
            self.text_view.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self.text_view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.edit_button.setEnabled(not enabled)
        self.save_preview_button.setEnabled(enabled)
        self.revert_preview_button.setEnabled(enabled)

    def _on_edit_clicked(self):
        if not self.presenter or not self.presenter.last_valid_selection:
            return
        date = self.presenter.last_valid_selection
        editable_text = self.presenter.get_editable_text_for_date(date)
        self.text_view.setPlainText(editable_text)
        self._set_edit_mode(True)

    def _on_save_preview_clicked(self):
        if not self.presenter or not self.presenter.last_valid_selection:
            return
        date = self.presenter.last_valid_selection
        edited_text = self.text_view.toPlainText()
        self.presenter.save_day_preview_edit(date, edited_text)
        self._memory_dirty = True
        self._set_edit_mode(False)
        self.presenter.emit_messages_for_date(date)

    def _on_revert_preview_clicked(self):
        if not self.presenter or not self.presenter.last_valid_selection:
            return
        date = self.presenter.last_valid_selection
        self.presenter.clear_day_preview_edit(date)
        self._memory_dirty = True
        self._set_edit_mode(False)
        self.presenter.emit_messages_for_date(date)

    def _on_preview_conflict(self, payload: dict):
        action, merged_text = self._show_preview_conflict_dialog(payload)
        if action is None:
            return

        date_key = payload.get("date_key", "")
        if action == "show_new":
            self.presenter.resolve_day_conflict(date_key, "show_new")
            self._memory_dirty = True
        elif action == "keep_saved":
            self.presenter.resolve_day_conflict(date_key, "keep_saved")
            self._memory_dirty = True
        elif action == "apply_over_new":
            self.presenter.resolve_day_conflict(
                date_key,
                "apply_over_new",
                merged_text=merged_text if merged_text is not None else payload.get("saved_edited", ""),
            )
            self._memory_dirty = True

        if self.presenter and self.presenter.last_valid_selection:
            self.presenter.emit_messages_for_date(self.presenter.last_valid_selection)

    def _show_preview_conflict_dialog(self, payload: dict) -> tuple[str | None, str | None]:
        diff_original = payload.get("diff_original", "")
        diff_edited = payload.get("diff_edited", "")
        details = (
            f"{tr('dialog.preview_conflict.details_mismatch')}\n\n"
            f"[saved_original -> current_original]\n{diff_original}\n\n"
            f"[saved_edited -> current_original]\n{diff_edited}"
        )

        dialog = QDialog(self)
        dialog.setWindowTitle(tr("dialog.preview_conflict.title"))
        setup_dialog_icon(dialog)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
        dialog.setMinimumSize(760, 520)
        dialog.resize(940, 640)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        info_label = QLabel(tr("dialog.preview_conflict.subtitle"))
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        details_view = NonPropagatingTextEdit()
        details_view.setReadOnly(True)
        details_view.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_view.setPlainText(details)
        details_view.setMinimumHeight(220)
        layout.addWidget(details_view, 1)

        merged_label = QLabel(tr("dialog.preview_conflict.edit_resulting_text"))
        merged_label.setWordWrap(True)
        layout.addWidget(merged_label)

        merged_edit = NonPropagatingTextEdit()
        merged_edit.setPlainText(payload.get("saved_edited", ""))
        merged_edit.setMinimumHeight(160)
        layout.addWidget(merged_edit, 1)

        button_box = QDialogButtonBox(Qt.Orientation.Horizontal)
        show_new_btn = button_box.addButton(
            tr("dialog.preview_conflict.show_new"),
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        keep_saved_btn = button_box.addButton(
            tr("dialog.preview_conflict.keep_saved"),
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        apply_btn = button_box.addButton(
            tr("dialog.preview_conflict.apply_over_new"),
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        cancel_btn = button_box.addButton(
            tr("common.cancel"),
            QDialogButtonBox.ButtonRole.RejectRole,
        )

        for button in (show_new_btn, keep_saved_btn, apply_btn, cancel_btn):
            button.setMinimumWidth(button.fontMetrics().horizontalAdvance(button.text()) + 28)

        layout.addWidget(button_box)

        result = {"action": None}

        show_new_btn.clicked.connect(lambda: (result.update({"action": "show_new"}), dialog.accept()))
        keep_saved_btn.clicked.connect(lambda: (result.update({"action": "keep_saved"}), dialog.accept()))
        apply_btn.clicked.connect(lambda: (result.update({"action": "apply_over_new"}), dialog.accept()))
        cancel_btn.clicked.connect(dialog.reject)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None, None
        return result["action"], merged_edit.toPlainText()
