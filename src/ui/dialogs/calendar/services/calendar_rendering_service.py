"""
Calendar rendering service.

Responsible for creating and styling calendar UI elements.
"""

from typing import List, Optional

from PyQt6.QtCore import QDate, QObject, Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from resources.translations import tr
from core.view_models import CalendarViewModel
from ui.theme import ThemeManager
from ui.widgets.atomic.custom_button import CustomButton

class CalendarDayButton(QPushButton):
    """Custom button for a day in calendar."""
    date_clicked = pyqtSignal(QDate)
    date_context_menu = pyqtSignal(QDate)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("day-button", True)
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.clicked.connect(self._on_click)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.date: Optional[QDate] = None

    def set_date(self, date: QDate):
        self.date = date

    def _on_click(self):
        if self.date:
            self.date_clicked.emit(self.date)

    def _on_context_menu(self, pos):
        if self.date:
            self.date_context_menu.emit(self.date)

    def sizeHint(self):
        """Returns preferred size for day button."""
        return QSize(50, 70)

class CalendarRenderingService(QObject):
    date_clicked = pyqtSignal(QDate)
    date_context_menu = pyqtSignal(QDate)
    month_selected = pyqtSignal(int, int)
    year_selected = pyqtSignal(int)
    month_context_menu = pyqtSignal(int, int)
    year_context_menu = pyqtSignal(int)

    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.theme_manager = theme_manager
        self._day_buttons: List[CalendarDayButton] = []
        self._day_labels: List[QLabel] = []
        self._month_buttons: List[CustomButton] = []
        self._month_labels: List[QLabel] = []
        self._year_buttons: List[CustomButton] = []
        self._year_labels: List[QLabel] = []
        self.current_year = QDate.currentDate().year()
        self._weekday_labels = []

    def create_day_view(self) -> QWidget:
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setSpacing(5)

        accent_color = self.theme_manager.get_color("accent").name()
        hover_color = self.theme_manager.get_color("dialog.button.hover").name()
        text_color = self.theme_manager.get_color("dialog.text").name()
        weekend_bg = self.theme_manager.get_color("calendar.weekend.background").name()
        disabled_bg = self.theme_manager.get_color("calendar.disabled.background").name()

        bg_color_obj = self.theme_manager.get_color("dialog.background")
        text_color_obj = self.theme_manager.get_color("dialog.text")
        r, g, b = (int(text_color_obj.red() * 0.6 + bg_color_obj.red() * 0.4),
                   int(text_color_obj.green() * 0.6 + bg_color_obj.green() * 0.4),
                   int(text_color_obj.blue() * 0.6 + bg_color_obj.blue() * 0.4))
        faded_text_color = QColor(r, g, b)

        widget.setStyleSheet(f"""
            QPushButton[day-button="true"] {{
                border: 1px solid transparent; border-radius: 4px; padding: 5px; background-color: transparent;
            }}
            QPushButton[day-button="true"][weekend="true"][checked="false"][disabled_for_export="false"] {{
                background-color: {weekend_bg};
            }}
            QPushButton[day-button="true"][active="true"][checked="false"][disabled_for_export="false"]:hover {{
                background-color: {hover_color};
            }}
            QPushButton[day-button="true"][disabled_for_export="false"]:checked {{
                background-color: {accent_color};
            }}
            QPushButton[day-button="true"][disabled_for_export="true"] {{
                background-color: {disabled_bg};
            }}
            QLabel[day-label="true"] {{
                background-color: transparent; font-size: 11pt; font-weight: 400; color: {faded_text_color.name()};
            }}
            QLabel[day-label="true"][active="true"] {{
                font-weight: 500; color: {text_color};
            }}
            QLabel[day-label="true"][checked="true"][disabled_for_export="false"] {{
                color: white; font-weight: 500;
            }}
            QLabel[day-label="true"][checked="true"][disabled_for_export="true"] {{
                color: {text_color};
            }}
            QLabel[weekday="true"] {{
                font-weight: bold; color: {text_color}; alignment: alignCenter;
            }}
        """)

        weekday_layout = QGridLayout()
        weekday_keys = ["weekday_mon", "weekday_tue", "weekday_wed", "weekday_thu", "weekday_fri", "weekday_sat", "weekday_sun"]
        self._weekday_labels.clear()
        for i, key in enumerate(weekday_keys):
            label = QLabel(tr(key))
            self._weekday_labels.append(label)
            label.setProperty("weekday", True)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            weekday_layout.addWidget(label, 0, i)
        main_layout.addLayout(weekday_layout)

        days_layout = QGridLayout()
        days_layout.setSpacing(2)

        for i in range(42):
            btn = CalendarDayButton()
            btn.date_clicked.connect(self.date_clicked)
            btn.date_context_menu.connect(self.date_context_menu)
            self._day_buttons.append(btn)

            label = QLabel()
            label.setProperty("day-label", True)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._day_labels.append(label)

            days_layout.addWidget(btn, i // 7, i % 7)
            days_layout.addWidget(label, i // 7, i % 7)

        main_layout.addLayout(days_layout)
        return widget

    def update_day_view(self, vm: CalendarViewModel):
        bg_color_obj = self.theme_manager.get_color("dialog.background")
        text_color_obj = self.theme_manager.get_color("dialog.text")
        r, g, b = (int(text_color_obj.red() * 0.5 + bg_color_obj.red() * 0.5),
                   int(text_color_obj.green() * 0.5 + bg_color_obj.green() * 0.5),
                   int(text_color_obj.blue() * 0.5 + bg_color_obj.blue() * 0.5))
        default_small_num_color = QColor(r, g, b).name()

        for i, day_info in enumerate(vm.days_in_current_month):
            if i >= len(self._day_buttons): break

            btn = self._day_buttons[i]
            lbl = self._day_labels[i]

            if day_info.is_in_current_month:
                btn.show()
                lbl.show()
            else:
                btn.hide()
                lbl.hide()
                continue

            is_weekend = day_info.date.dayOfWeek() >= 6
            is_active_for_display = day_info.is_available

            btn.set_date(day_info.date)
            btn.setProperty("weekend", is_weekend)
            btn.setProperty("disabled_for_export", day_info.is_disabled)
            btn.setProperty("active", day_info.is_available)
            btn.setProperty("checked", day_info.is_selected)
            lbl.setProperty("active", is_active_for_display)
            lbl.setProperty("checked", day_info.is_selected)
            lbl.setProperty("disabled_for_export", day_info.is_disabled)

            btn.setEnabled(day_info.is_available)
            btn.setCursor(Qt.CursorShape.PointingHandCursor if day_info.is_available else Qt.CursorShape.ArrowCursor)

            day_num = str(day_info.date.day())
            sub_text_color = "white" if day_info.is_selected and not day_info.is_disabled else default_small_num_color

            if day_info.is_available:
                html_text = f"""<p style="line-height: 1.0; margin: 0; padding: 0;">{day_num}<br>
                               <span style="font-size: 7pt; color: {sub_text_color};">{day_info.message_count}</span></p>"""
            else:
                html_text = f'<p style="line-height: 1.0; margin: 0; padding: 0;">{day_num}</p>'

            if day_info.is_disabled:
                html_text = f"<span style='text-decoration: line-through; font-style: italic;'>{html_text}</span>"

            lbl.setText(html_text)
            btn.blockSignals(True)
            btn.setChecked(day_info.is_selected)
            btn.blockSignals(False)

            btn.style().unpolish(btn); btn.style().polish(btn)
            lbl.style().unpolish(lbl); lbl.style().polish(lbl)
            btn.update(); lbl.update()

    def create_month_view(self) -> QWidget:
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(5)

        for i in range(12):
            btn = CustomButton(None, "")
            btn.setProperty("month", i + 1)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            btn.clicked.connect(lambda checked=False, month=i + 1: self.month_selected.emit(self.current_year, month))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, month=i + 1: self.month_context_menu.emit(self.current_year, month))
            self._month_buttons.append(btn)

            label = QLabel()
            label.setProperty("month-label", True)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._month_labels.append(label)

            layout.addWidget(btn, i // 3, i % 3)
            layout.addWidget(label, i // 3, i % 3)

        for row in range(4):
            layout.setRowStretch(row, 1)
        return widget

    def update_month_view(self, vm: CalendarViewModel):
        self.current_year = vm.current_year
        bg_color_obj = self.theme_manager.get_color("dialog.background")
        text_color_obj = self.theme_manager.get_color("dialog.text")
        r, g, b = (int(text_color_obj.red() * 0.5 + bg_color_obj.red() * 0.5),
                   int(text_color_obj.green() * 0.5 + bg_color_obj.green() * 0.5),
                   int(text_color_obj.blue() * 0.5 + bg_color_obj.blue() * 0.5))
        sub_text_color = QColor(r, g, b).name()
        disabled_bg_color = self.theme_manager.get_color("calendar.disabled.background")

        for month_info in vm.months_in_current_year:
            i = month_info.month - 1
            if i >= len(self._month_buttons): continue

            btn = self._month_buttons[i]
            lbl = self._month_labels[i]

            btn.setProperty("month", month_info.month)
            btn.setEnabled(month_info.is_available)
            btn.setCursor(Qt.CursorShape.PointingHandCursor if month_info.is_available else Qt.CursorShape.ArrowCursor)

            html_text = f"""<p style="line-height: 1.0; margin: 0; padding: 0; text-align: center;">{month_info.name}<br>
                           <span style="font-size: 9pt; color: {sub_text_color};">{month_info.message_count}</span></p>"""

            if month_info.is_disabled:
                btn.set_override_bg_color(disabled_bg_color)
                html_text = f"<span style='text-decoration: line-through; font-style: italic;'>{html_text}</span>"
            else:
                btn.set_override_bg_color(None)

            lbl.setText(html_text)
            btn.style().unpolish(btn); btn.style().polish(btn)
            lbl.style().unpolish(lbl); lbl.style().polish(lbl)
            btn.update(); lbl.update()

    def create_year_view(self) -> QWidget:
        widget = QWidget()
        widget.setLayout(QGridLayout())
        widget.layout().setSpacing(5)
        return widget

    def update_year_view(self, vm: CalendarViewModel, container_widget: QWidget):
        layout = container_widget.layout()

        while item := layout.takeAt(0):
            if widget := item.widget():
                widget.deleteLater()

        bg_color_obj = self.theme_manager.get_color("dialog.background")
        text_color_obj = self.theme_manager.get_color("dialog.text")
        r, g, b = (int(text_color_obj.red() * 0.5 + bg_color_obj.red() * 0.5),
                   int(text_color_obj.green() * 0.5 + bg_color_obj.green() * 0.5),
                   int(text_color_obj.blue() * 0.5 + bg_color_obj.blue() * 0.5))
        sub_text_color = QColor(r, g, b).name()
        disabled_bg_color = self.theme_manager.get_color("calendar.disabled.background")

        self._year_buttons.clear()
        self._year_labels.clear()

        row, col = 0, 0
        for year_info in vm.available_years:
            btn = CustomButton(None, "")
            btn.setProperty("year", year_info.year)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            btn.clicked.connect(lambda checked=False, year=year_info.year: self.year_selected.emit(year))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, year=year_info.year: self.year_context_menu.emit(year))
            self._year_buttons.append(btn)

            label = QLabel()
            label.setProperty("year-label", True)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._year_labels.append(label)

            layout.addWidget(btn, row, col)
            layout.addWidget(label, row, col)

            html_text = f"""<p style="line-height: 1.0; margin: 0; padding: 0; text-align: center;">{year_info.name}<br>
                           <span style="font-size: 9pt; color: {sub_text_color};">{year_info.message_count}</span></p>"""

            if year_info.is_disabled:
                btn.set_override_bg_color(disabled_bg_color)
                html_text = f"<span style='text-decoration: line-through; font-style: italic;'>{html_text}</span>"
            else:
                btn.set_override_bg_color(None)

            label.setText(html_text)
            btn.style().unpolish(btn); btn.style().polish(btn)
            label.style().unpolish(label); label.style().polish(label)
            btn.update(); label.update()

            col += 1
            if col > 2:
                col = 0
                row += 1
        layout.setRowStretch(row + 1, 1)

    def retranslate_ui(self):
        """Updates translations for statically created elements."""
        weekday_keys = ["weekday_mon", "weekday_tue", "weekday_wed", "weekday_thu", "weekday_fri", "weekday_sat", "weekday_sun"]
        for i, label in enumerate(self._weekday_labels):
            if i < len(weekday_keys):
                label.setText(tr(weekday_keys[i]))
