import os
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidget,
    QStackedWidget,
    QLabel,
    QFrame,
    QListWidgetItem,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFontMetrics, QIcon
import os

from utils.paths import resource_path
from ui.theme import ThemeManager
from resources.translations import tr
from ui.widgets.atomic.minimalist_scrollbar import MinimalistScrollBar

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HelpDialog")
        self.theme_manager = ThemeManager.get_instance()

        self.setWindowTitle(tr("Tkonverter Help"))
        icon_path = resource_path("resources/icons/icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint
        )
        self.setSizeGripEnabled(True)
        self.resize(800, 600)
        self.setMinimumSize(640, 480)

        self._setup_ui()
        self._populate_content()
        self._apply_styles()

        self.theme_manager.theme_changed.connect(self._apply_styles)

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.nav_widget = QListWidget()
        self.nav_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.nav_widget.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.nav_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.nav_widget.setMouseTracking(True)

        self.nav_widget.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.nav_widget.setSelectionBehavior(QListWidget.SelectionBehavior.SelectRows)

        self.nav_widget.setStyleSheet("")
        self.nav_widget.currentRowChanged.connect(self.change_page)

        self.content_stack = QStackedWidget()
        self.content_stack.setFrameShape(QFrame.Shape.NoFrame)

        self.scroll_area = QScrollArea()
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.custom_scrollbar = MinimalistScrollBar(self.scroll_area)
        self.scroll_area.setVerticalScrollBar(self.custom_scrollbar)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.scroll_area.setWidget(self.content_stack)

        main_layout.addWidget(self.nav_widget)
        main_layout.addWidget(self.scroll_area, 1)

    def _update_nav_width(self):
        max_text_width = 0
        for i in range(self.nav_widget.count()):
            item = self.nav_widget.item(i)
            text = item.text()
            text_width = QFontMetrics(self.nav_widget.font()).horizontalAdvance(text)
            max_text_width = max(max_text_width, text_width)
        self.nav_widget.setFixedWidth(max(180, max_text_width + 32))

    def _populate_content(self):
        sections = [
            ("Help Section: Introduction", "help_intro_html"),
            ("Help Section: File Management", "help_files_html"),
            ("Help Section: Conversion Options", "help_conversion_html"),
            ("Help Section: Analysis Tools", "help_analysis_html"),
            ("Help Section: AI Features", "help_ai_html"),
            ("Help Section: Exporting", "help_export_html"),
        ]

        self._content_keys = []
        for title_key, content_key in sections:
            self._add_section(title_key, content_key)
            self._content_keys.append(content_key)

        if self.nav_widget.count() > 0:
            self.nav_widget.setCurrentRow(0)

        self._update_nav_width()

    def _add_section(self, title_key: str, content_key: str):
        title = tr(title_key)
        nav_item = QListWidgetItem(title, self.nav_widget)
        nav_item.setSizeHint(QSize(200, 35))

        content_page = QLabel()
        content_page.setMargin(25)
        content_page.setWordWrap(True)
        content_page.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        content_page.setTextFormat(Qt.TextFormat.RichText)
        content_page.setOpenExternalLinks(True)
        content_page.setText(tr(content_key))
        self.content_stack.addWidget(content_page)

    def change_page(self, index: int):
        self.content_stack.setCurrentIndex(index)

    def _apply_styles(self):

        self.style().unpolish(self)
        self.style().polish(self)

        self.nav_widget.style().unpolish(self.nav_widget)
        self.nav_widget.style().polish(self.nav_widget)

        self.nav_widget.update()
        self.nav_widget.repaint()

        tm = self.theme_manager
        text_color = tm.get_color("dialog.text").name()
        separator_color = tm.get_color("dialog.border").name()
        code_bg_color = tm.get_color("dialog.button.hover").name()
        bold_color = text_color

        content_wrapper_style = f"""
        <style>
            body {{ font-size: 14px; color: {text_color}; }}
            h2 {{ margin-bottom: 8px; border-bottom: 1px solid {separator_color}; padding-bottom: 4px; }}
            h3 {{ margin: 12px 0 6px 0; }}
            ul {{ margin: 0; padding-left: 20px; }}
            li {{ margin-bottom: 5px; }}
            b, strong {{ color: {bold_color}; }}
            code {{ background-color: {code_bg_color}; border-radius: 3px; padding: 1px 3px; font-family: monospace; }}
        </style>
        """
        for i in range(self.content_stack.count()):
            page = self.content_stack.widget(i)
            if isinstance(page, QLabel):
                key = self._content_keys[i]
                page.setText(content_wrapper_style + tr(key))

    def retranslate_ui(self):
        self.setWindowTitle(tr("Tkonverter Help"))
        self.nav_widget.clear()

        while self.content_stack.count() > 0:
            w = self.content_stack.widget(0)
            self.content_stack.removeWidget(w)
            w.deleteLater()

        self._populate_content()
        self._apply_styles()
