from collections import defaultdict
from datetime import datetime
from html import escape
from typing import Set

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QWheelEvent
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.analysis.tree_analyzer import TreeNode
from core.application.calendar_service import CalendarService
from core.conversion.context import ConversionContext
from core.conversion.message_formatter import format_message
from core.conversion.utils import markdown_to_html_for_preview
from resources.translations import tr
from ui.dialogs.dialog_builder import auto_size_dialog, setup_dialog_scaffold, setup_dialog_icon
from ui.dialogs.calendar.services.calendar_rendering_service import CalendarRenderingService
from presenters.calendar_presenter import CalendarPresenter
from core.view_models import CalendarViewModel
from ui.theme import ThemeManager
from ui.widgets.atomic.custom_button import CustomButton
from ui.widgets.atomic.minimalist_scrollbar import MinimalistScrollBar

class NonPropagatingTextEdit(QTextEdit):
    """A QTextEdit that stops wheel events from propagating when at scroll limits."""
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

    def __init__(
        self,
        presenter,
        messages: list,
        config: dict,
        theme_manager: ThemeManager,
        root_node: TreeNode | None = None,
        initial_disabled_nodes: Set[TreeNode] | None = None,
        token_hierarchy: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.theme_manager = theme_manager

        self.messages = messages

        calendar_service = CalendarService()
        self.presenter = CalendarPresenter(calendar_service)
        self.rendering_service = CalendarRenderingService(self.theme_manager)

        self.setWindowTitle(tr("Calendar"))
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
            config=config
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
        self.date_label = QLabel(tr("Date"))
        self.date_label.setStyleSheet("font-weight: bold; padding-bottom: 5px;")

        self.text_view = NonPropagatingTextEdit()
        self.text_view.setReadOnly(True)

        self.text_view.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.text_view.viewport().setCursor(Qt.CursorShape.ArrowCursor)

        self.text_view.setVerticalScrollBar(MinimalistScrollBar(self.text_view))

        right_panel_layout.addWidget(self.date_label)
        right_panel_layout.addWidget(self.text_view, 1)

        main_layout.addWidget(left_panel_widget, 2)
        main_layout.addWidget(right_panel_widget, 3)
        layout.addWidget(main_widget, 1)

        setup_dialog_scaffold(self, layout, ok_text=tr("Save"), cancel_text=tr("Close"))
        auto_size_dialog(self, min_width=800, min_height=600)

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
        self.text_view.document().setDefaultStyleSheet(stylesheet)

        if self.text_view.toPlainText():
            self.text_view.setHtml(self.text_view.toHtml())

    def _connect_signals(self):
        self.presenter.view_model_updated.connect(self.update_ui)
        self.presenter.messages_for_date_updated.connect(self._update_message_view)

        self.rendering_service.date_clicked.connect(self.presenter.select_date)
        self.rendering_service.month_selected.connect(self.presenter.select_month)
        self.rendering_service.year_selected.connect(self.presenter.select_year)

        self.rendering_service.date_context_menu.connect(self.presenter.toggle_filter_for_date)
        self.rendering_service.month_context_menu.connect(self.presenter.toggle_filter_for_month)
        self.rendering_service.year_context_menu.connect(self.presenter.toggle_filter_for_year)

        self.prev_button.clicked.connect(self.presenter.navigate_previous)
        self.next_button.clicked.connect(self.presenter.navigate_next)
        self.title_button.clicked.connect(self._on_title_clicked)

    def get_disabled_nodes(self) -> set:
        """Returns current set of disabled nodes from presenter."""
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

    def _update_message_view(self, formatted_text: str):
        """Updates message display for selected date."""

        if self.presenter and self.presenter.last_valid_selection:
            self.date_label.setText(self.presenter.last_valid_selection.toString(Qt.DateFormat.ISODate))
        else:
            self.date_label.setText(tr("Date"))

        html_text = markdown_to_html_for_preview(formatted_text)
        self.text_view.setHtml(html_text)

    def accept(self):

        final_disabled_nodes = self.presenter.get_disabled_nodes()
        self.presenter.filter_changed.emit(final_disabled_nodes)
        super().accept()

    def retranslate_ui(self):
        """Updates all texts in dialog when language changes."""
        self.setWindowTitle(tr("Calendar"))
        self.date_label.setText(tr("Date"))
        self.ok_button.setText(tr("Save"))
        self.cancel_button.setText(tr("Close"))

        self.rendering_service.retranslate_ui()

        if self.presenter:
            self.presenter._update_view_model()

        if self.presenter and self.presenter.last_valid_selection:

            formatted_text = self.presenter._format_messages_for_date(self.presenter.last_valid_selection)
            self._update_message_view(formatted_text)
        elif self.text_view.toPlainText() == "No messages on this date.":
             self.text_view.setPlainText(tr("No messages on this date."))

    def refresh_theme_styles(self):
        """Forces dialog styles to update."""
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
