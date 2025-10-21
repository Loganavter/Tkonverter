"""
Layout manager for automatic window size calculation.

Provides adaptive layout functionality including:
- Dynamic minimum window size calculation
- Interface language adaptation
- Content overflow prevention
"""

from typing import Dict, Optional

from PyQt6.QtCore import QSize, QTimer
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import QApplication

from src.resources.translations import tr

class LayoutManager:
    """Layout manager for automatic size calculation."""

    MIN_WINDOW_WIDTH = 800
    MIN_WINDOW_HEIGHT = 500

    MAIN_MARGIN = 10
    SPACING = 10
    GROUP_PADDING = 20

    BUTTON_HEIGHT = 30
    ICON_BUTTON_SIZE = 33
    PREVIEW_HEIGHT = 450
    TERMINAL_MIN_HEIGHT = 200
    DROP_ZONE_MIN_HEIGHT = 80

    LEFT_COLUMN_MIN = 240
    MIDDLE_COLUMN_MIN = 310
    RIGHT_COLUMN_MIN = 390

    def __init__(self, main_window):
        """Initialize layout manager."""
        self.main_window = main_window
        self._cached_sizes: Dict[str, QSize] = {}
        self._size_timer = QTimer()
        self._size_timer.setSingleShot(True)
        self._size_timer.timeout.connect(self._recalculate_window_size)

        self._calculated_preview_height = self.PREVIEW_HEIGHT

    def calculate_minimum_window_size(self) -> QSize:
        """Calculates minimum window size based on content."""
        try:
            left_width = self.calculate_left_column_width()
            middle_width = self.calculate_middle_column_width()
            right_width = self.calculate_right_column_width()

            total_content_width = max(
                left_width + middle_width, self.LEFT_COLUMN_MIN + self.MIDDLE_COLUMN_MIN
            )
            right_content_width = max(right_width, self.RIGHT_COLUMN_MIN)

            min_width = max(
                total_content_width
                + right_content_width
                + self.MAIN_MARGIN * 3
                + self.SPACING,
                self.MIN_WINDOW_WIDTH,
            )

            min_height = self._calculate_window_height()

            calculated_size = QSize(int(min_width), int(min_height))

            return calculated_size

        except Exception as e:
            return QSize(self.MIN_WINDOW_WIDTH, self.MIN_WINDOW_HEIGHT)

    def calculate_left_column_width(self) -> float:
        """Calculates minimum width of left column (Profile group)."""
        try:
            ui = self.main_window.ui
            width = self.LEFT_COLUMN_MIN

            if hasattr(ui, "profile_group"):
                profile_width = self._calculate_group_width(
                    tr("Profile"),
                    [
                        tr("Group Chat"),
                        tr("Channel"),
                        tr("Posts and Comments"),
                        tr("Personal Chat"),
                    ],
                )
                width = max(width, profile_width)

            if hasattr(ui, "personal_names_group"):
                names_width = self._calculate_group_width(
                    tr("Names for Personal Chat"),
                    [tr("Your name (in chat):"), tr("Partner's name:")],
                )
                width = max(width, names_width)

            return width

        except Exception as e:
            return self.LEFT_COLUMN_MIN

    def calculate_middle_column_width(self) -> float:
        """Calculates minimum width of middle column (Options + AI)."""
        try:
            ui = self.main_window.ui
            width = self.MIDDLE_COLUMN_MIN

            option_labels = [
                tr("Show message time"),
                tr("Show reactions"),
                tr("Show reaction authors"),
                tr("Optimization"),
                tr("Streak break time:"),
                tr("Show Markdown"),
                tr("Show links"),
                tr("Show technical information"),
                tr("Show service notifications"),
            ]
            options_width = self._calculate_group_width(tr("Options"), option_labels)
            width = max(width, options_width)

            ai_width = self._calculate_group_width(
                tr("Analysis"), [tr("Tokens:"), tr("Calculate")]
            )
            width = max(width, ai_width)

            return width

        except Exception as e:
            return self.MIDDLE_COLUMN_MIN

    def calculate_right_column_width(self) -> float:
        """Calculates minimum width of right column (Preview + Terminal)."""
        try:
            width = self.RIGHT_COLUMN_MIN

            preview_width = self._calculate_group_width(tr("Preview"), [])
            terminal_width = self._calculate_group_width(tr("Terminal"), [])

            buttons = [
                self.main_window.ui.install_manager_button,
                self.main_window.ui.settings_button,
                self.main_window.ui.save_button,
            ]
            buttons_width = self._calculate_buttons_width(buttons)

            width = max(width, preview_width, terminal_width, buttons_width)

            return width

        except Exception as e:
            return self.RIGHT_COLUMN_MIN

    def _calculate_window_height(self) -> float:
        """Calculates minimum window height."""
        try:
            group_title_height = 20
            control_height = 25

            left_height = (
                group_title_height + 4 * control_height + self.GROUP_PADDING
            ) + (group_title_height + 2 * control_height + self.GROUP_PADDING)

            middle_height = (
                group_title_height + 9 * control_height + self.GROUP_PADDING
            ) + (
                group_title_height
                + 2 * control_height
                + self.BUTTON_HEIGHT
                + self.GROUP_PADDING
            )
            right_height = self.PREVIEW_HEIGHT + self.TERMINAL_MIN_HEIGHT + self.BUTTON_HEIGHT

            drop_zone_height = self.DROP_ZONE_MIN_HEIGHT

            content_height = max(left_height, middle_height) + drop_zone_height
            total_height = max(content_height, right_height, self.MIN_WINDOW_HEIGHT)

            final_height = total_height + self.MAIN_MARGIN * 2

            return final_height

        except Exception as e:
            return self.MIN_WINDOW_HEIGHT

    def _calculate_group_width(self, title: str, content_labels: list) -> float:
        """Calculates minimum width of a group."""
        try:
            font_metrics = QFontMetrics(QApplication.instance().font())

            title_width = font_metrics.horizontalAdvance(title)

            content_width = 0
            for label in content_labels:
                label_width = font_metrics.horizontalAdvance(label)
                content_width = max(content_width, label_width)

            # Increased padding from +100 to +150 to accommodate switches and controls
            group_width = max(title_width + 40, content_width + 150)  # Reduced from 180 to 150

            return group_width

        except Exception as e:
            return 200

    def _calculate_buttons_width(self, buttons: list) -> float:
        """Calculates minimum width for buttons."""
        try:
            total_width = 0
            if not buttons:
                return 200

            for button in buttons:
                total_width += button.sizeHint().width()
            total_width += self.SPACING * (len(buttons) - 1)

            return total_width

        except Exception as e:
            return 200

    def schedule_size_recalculation(self, delay_ms: int = 100):
        """Schedules window size recalculation with delay."""
        self._size_timer.start(delay_ms)

    def _recalculate_window_size(self):
        """Recalculates and applies new window sizes."""
        try:
            new_min_size = self.calculate_minimum_window_size()

            self.main_window.setMinimumSize(new_min_size)

            current_size = self.main_window.size()

            if (
                current_size.width() < new_min_size.width()
                or current_size.height() < new_min_size.height()
            ):
                new_width = max(current_size.width(), new_min_size.width())
                new_height = max(current_size.height(), new_min_size.height())

                self.main_window.resize(new_width, new_height)

        except Exception as e:
            pass

    def handle_language_change(self):
        """Handles language change and recalculates sizes."""
        self._cached_sizes.clear()
        self.schedule_size_recalculation(200)

    def handle_visibility_change(self, widget_name: str, is_visible: bool):
        """Handles widget visibility changes."""
        self.schedule_size_recalculation(50)

    def get_cached_size(self, key: str) -> Optional[QSize]:
        """Gets cached size."""
        return self._cached_sizes.get(key)

    def cache_size(self, key: str, size: QSize):
        """Caches size."""
        self._cached_sizes[key] = size

    def calculate_and_set_preview_height(self, html_content: str):
        """
        Calculates and saves preview widget height based on HTML content.
        Теперь не используется, так как превью имеет фиксированную высоту.
        """

        pass

