from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.resources.translations import tr
from src.ui.icon_manager import AppIcon, get_app_icon
from src.ui.widgets.atomic.adaptive_label import AdaptiveLabel, CompactLabel
from src.ui.widgets.atomic.drop_zone_label import DropZoneLabel
from src.shared_toolkit.ui.widgets.atomic.custom_button import CustomButton
from src.shared_toolkit.ui.widgets.atomic.custom_group_widget import CustomGroupBuilder
from src.shared_toolkit.ui.widgets.atomic.custom_line_edit import CustomLineEdit
from src.shared_toolkit.ui.widgets.atomic.fluent_radio import FluentRadioButton
from src.shared_toolkit.ui.widgets.atomic.fluent_switch import FluentSwitch
from src.ui.widgets.atomic.time_line_edit import TimeLineEdit

class Ui_TkonverterMainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("TkonverterMainWindow")

        main_layout = QHBoxLayout(MainWindow)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.left_column = QWidget()
        left_layout = QVBoxLayout(self.left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        # Set proper size policy for left column
        self.left_column.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self.middle_column = QWidget()
        middle_layout = QVBoxLayout(self.middle_column)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(10)
        # Set proper size policy for middle column
        self.middle_column.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self.right_column = QWidget()
        right_layout = QVBoxLayout(self.right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        # Set proper size policy for right column
        self.right_column.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self.profile_group, profile_layout, self.profile_group_title = (
            CustomGroupBuilder.create_styled_group(tr("Profile"))
        )
        self.radio_group = FluentRadioButton(tr("Group Chat"))
        self.radio_group.setChecked(True)
        self.radio_channel = FluentRadioButton(tr("Channel"))
        self.radio_posts = FluentRadioButton(tr("Posts and Comments"))
        self.radio_personal = FluentRadioButton(tr("Personal Chat"))
        profile_layout.addWidget(self.radio_group)
        profile_layout.addWidget(self.radio_channel)
        profile_layout.addWidget(self.radio_posts)
        profile_layout.addWidget(self.radio_personal)

        self.personal_names_group, names_layout, self.personal_names_title = (
            CustomGroupBuilder.create_styled_group(tr("Names for Personal Chat"))
        )
        names_layout.setSpacing(6)
        self.my_name_label = CompactLabel(tr("Your name (in chat):"))
        self.line_edit_my_name = CustomLineEdit(tr("Me"))
        self.partner_name_label = CompactLabel(tr("Partner's name:"))
        self.line_edit_partner_name = CustomLineEdit(tr("Partner"))
        names_layout.addWidget(self.my_name_label)
        names_layout.addWidget(self.line_edit_my_name)
        names_layout.addWidget(self.partner_name_label)
        names_layout.addWidget(self.line_edit_partner_name)
        profile_layout.addWidget(self.personal_names_group)

        left_layout.addWidget(self.profile_group)

        left_layout.addStretch(1)

        self.options_group, options_layout, self.options_group_title = (
            CustomGroupBuilder.create_styled_group(tr("Options"))
        )
        options_layout.setSpacing(8)

        h_layout_time = QHBoxLayout()
        self.label_show_time = CompactLabel(tr("Show message time"))
        self.switch_show_time = FluentSwitch()
        self.switch_show_time.setChecked(True)

        h_layout_reactions = QHBoxLayout()
        self.label_show_reactions = CompactLabel(tr("Show reactions"))
        self.switch_show_reactions = FluentSwitch()
        self.switch_show_reactions.setChecked(True)

        h_layout_react_authors = QHBoxLayout()
        self.label_reaction_authors = CompactLabel(tr("Show reaction authors"))
        self.switch_reaction_authors = FluentSwitch()
        self.switch_reaction_authors.setChecked(False)

        h_layout_optimization = QHBoxLayout()
        self.label_show_optimization = CompactLabel(tr("Optimization"))
        self.switch_show_optimization = FluentSwitch()
        self.switch_show_optimization.setChecked(False)

        self.streak_time_container = QWidget()
        h_layout_streak_time = QHBoxLayout(self.streak_time_container)
        h_layout_streak_time.setContentsMargins(0, 0, 0, 0)
        self.label_streak_break_time = CompactLabel(tr("Streak break time:"))
        self.line_edit_streak_break_time = TimeLineEdit("20:00")

        h_layout_markdown = QHBoxLayout()
        self.label_show_markdown = CompactLabel(tr("Show Markdown"))
        self.switch_show_markdown = FluentSwitch()
        self.switch_show_markdown.setChecked(True)

        self.links_container = QWidget()
        h_layout_links = QHBoxLayout(self.links_container)
        h_layout_links.setContentsMargins(0, 0, 0, 0)
        self.label_show_links = CompactLabel(tr("Show links"))
        self.switch_show_links = FluentSwitch()
        self.switch_show_links.setChecked(True)

        h_layout_tech_info = QHBoxLayout()
        self.label_show_tech_info = CompactLabel(tr("Show technical information"))
        self.switch_show_tech_info = FluentSwitch()
        self.switch_show_tech_info.setChecked(True)

        h_layout_service = QHBoxLayout()
        self.label_show_service_notifications = CompactLabel(
            tr("Show service notifications")
        )
        self.switch_show_service_notifications = FluentSwitch()
        self.switch_show_service_notifications.setChecked(True)

        h_layout_time.addWidget(self.label_show_time)
        h_layout_time.addStretch()
        h_layout_time.addWidget(self.switch_show_time)

        h_layout_reactions.addWidget(self.label_show_reactions)
        h_layout_reactions.addStretch()
        h_layout_reactions.addWidget(self.switch_show_reactions)

        h_layout_react_authors.addWidget(self.label_reaction_authors)
        h_layout_react_authors.addStretch()
        h_layout_react_authors.addWidget(self.switch_reaction_authors)

        h_layout_optimization.addWidget(self.label_show_optimization)
        h_layout_optimization.addStretch()
        h_layout_optimization.addWidget(self.switch_show_optimization)

        self.right_part_container = QWidget()

        ref_switch = self.switch_show_markdown

        self.right_part_container.setFixedWidth(ref_switch.sizeHint().width())

        right_part_layout = QHBoxLayout(self.right_part_container)
        right_part_layout.setContentsMargins(0, 0, 0, 0)
        right_part_layout.setSpacing(0)

        self.line_edit_streak_break_time.setFixedWidth(ref_switch.TRACK_WIDTH)

        right_part_layout.addWidget(self.line_edit_streak_break_time)
        right_part_layout.addStretch(1)

        h_layout_streak_time.addWidget(self.label_streak_break_time)
        h_layout_streak_time.addStretch(1)

        h_layout_streak_time.addWidget(self.right_part_container)

        h_layout_markdown.addWidget(self.label_show_markdown)
        h_layout_markdown.addStretch()
        h_layout_markdown.addWidget(self.switch_show_markdown)

        h_layout_links.addWidget(self.label_show_links)
        h_layout_links.addStretch()
        h_layout_links.addWidget(self.switch_show_links)

        h_layout_tech_info.addWidget(self.label_show_tech_info)
        h_layout_tech_info.addStretch()
        h_layout_tech_info.addWidget(self.switch_show_tech_info)

        h_layout_service.addWidget(self.label_show_service_notifications)
        h_layout_service.addStretch()
        h_layout_service.addWidget(self.switch_show_service_notifications)

        options_layout.addLayout(h_layout_time)
        options_layout.addLayout(h_layout_reactions)
        options_layout.addLayout(h_layout_react_authors)
        options_layout.addLayout(h_layout_optimization)
        options_layout.addWidget(self.streak_time_container)
        options_layout.addLayout(h_layout_markdown)
        options_layout.addWidget(self.links_container)
        options_layout.addLayout(h_layout_tech_info)
        options_layout.addLayout(h_layout_service)

        middle_layout.addWidget(self.options_group)

        self.ai_group, ai_layout, self.ai_group_title = (
            CustomGroupBuilder.create_styled_group(tr("Analysis"))
        )
        ai_layout.setSpacing(6)

        tokens_layout = QHBoxLayout()
        self.tokens_label = CompactLabel(tr("Tokens:"))

        token_values_layout = QVBoxLayout()
        token_values_layout.setSpacing(0)
        self.token_count_label = AdaptiveLabel(tr("N/A"))
        self.token_count_label.setStyleSheet("font-weight: bold;")
        self.filtered_token_count_label = AdaptiveLabel("")
        self.filtered_token_count_label.setStyleSheet("font-weight: bold; color: #888;")
        token_values_layout.addWidget(self.token_count_label)
        token_values_layout.addWidget(self.filtered_token_count_label)
        tokens_layout.addWidget(self.tokens_label)
        tokens_layout.addLayout(token_values_layout)
        tokens_layout.addStretch()
        ai_layout.addLayout(tokens_layout)

        ai_buttons_layout = QHBoxLayout()
        self.recalculate_button = CustomButton(None, tr("Calculate"))
        self.calendar_button = CustomButton(get_app_icon(AppIcon.CALENDAR), "")
        self.calendar_button.setToolTip(tr("Calendar View"))
        self.diagram_button = CustomButton(get_app_icon(AppIcon.CHART), "")
        self.diagram_button.setToolTip(tr("Token Analysis"))
        ai_buttons_layout.addStretch()
        ai_buttons_layout.addWidget(self.recalculate_button)
        ai_buttons_layout.addWidget(self.calendar_button)
        ai_buttons_layout.addWidget(self.diagram_button)
        ai_layout.addLayout(ai_buttons_layout)

        middle_layout.addWidget(self.ai_group)

        self.left_part = QWidget()
        left_part_layout = QVBoxLayout(self.left_part)
        left_part_layout.setContentsMargins(0, 0, 0, 0)
        left_part_layout.setSpacing(10)

        columns_container = QWidget()
        columns_layout = QHBoxLayout(columns_container)
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(10)
        columns_layout.addWidget(self.left_column)
        columns_layout.addWidget(self.middle_column)

        left_part_layout.addWidget(columns_container)

        self.drop_zone = DropZoneLabel(tr("Drag and drop result.json file here"))
        self.drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_zone.setStyleSheet(
            "border: 2px dashed #aaa; border-radius: 10px; padding: 15px; font-size: 14px;"
        )
        self.drop_zone.setMinimumHeight(80)
        self.drop_zone.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        left_part_layout.addWidget(self.drop_zone, 1)

        self.right_splitter = QSplitter(Qt.Orientation.Vertical)

        (
            self.preview_group,
            preview_layout,
            self.preview_group_title_label,
        ) = CustomGroupBuilder.create_styled_group(tr("Preview"))

        self.preview_group.setFixedHeight(450)
        self.preview_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.preview_text_edit = QTextEdit()
        self.preview_text_edit.setObjectName("previewTextEdit")
        self.preview_text_edit.setReadOnly(True)

        self.preview_text_edit.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.preview_text_edit.viewport().setCursor(Qt.CursorShape.ArrowCursor)

        preview_layout.addWidget(self.preview_text_edit)

        self.terminal_group, terminal_layout, self.terminal_group_title = (
            CustomGroupBuilder.create_styled_group(tr("Terminal"))
        )

        self.log_output = QTextEdit()
        self.log_output.setObjectName("logOutput")
        self.log_output.setReadOnly(True)
        self.log_output.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )
        self.log_output.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        terminal_layout.addWidget(self.log_output)

        self.terminal_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.right_splitter.addWidget(self.preview_group)
        self.right_splitter.addWidget(self.terminal_group)

        self.right_splitter.setSizes([450, 200])
        self.right_splitter.setStretchFactor(0, 0)
        self.right_splitter.setStretchFactor(1, 1)
        self.right_splitter.setCollapsible(0, False)
        self.right_splitter.setCollapsible(1, True)

        bottom_layout = QHBoxLayout()

        button_container = QWidget()
        button_container_layout = QHBoxLayout(button_container)
        button_container_layout.setContentsMargins(0, 0, 0, 0)
        button_container_layout.setSpacing(6)

        self.install_manager_button = CustomButton(get_app_icon(AppIcon.DOWNLOAD), "")
        self.install_manager_button.setToolTip(tr("Installation Manager"))
        self.settings_button = CustomButton(get_app_icon(AppIcon.SETTINGS), "")
        self.settings_button.setToolTip(tr("Settings"))
        self.help_button = CustomButton(get_app_icon(AppIcon.HELP), "")
        self.help_button.setToolTip(tr("Help"))
        self.save_button = CustomButton(get_app_icon(AppIcon.SAVE), tr("Save to file..."))
        self.save_button.setProperty("class", "primary")

        button_container_layout.addWidget(self.install_manager_button)
        button_container_layout.addWidget(self.settings_button)
        button_container_layout.addWidget(self.help_button)
        button_container_layout.addWidget(self.save_button)

        bottom_layout.addStretch()
        bottom_layout.addWidget(button_container)

        right_layout.addWidget(self.right_splitter)
        right_layout.addLayout(bottom_layout)

        self.main_splitter.addWidget(self.left_part)
        self.main_splitter.addWidget(self.right_column)

        self.main_splitter.setSizes([450, 900])

        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)

        self.main_splitter.setCollapsible(0, False)
        self.main_splitter.setCollapsible(1, True)

        main_layout.addWidget(self.main_splitter)

    def set_preview_title(self, title: str):
        """Sets preview title and updates sizes."""
        if self.preview_group_title_label:
            self.preview_group_title_label.setText(title)

    def update_group_titles_on_language_change(self):
        """Updates sizes of all groups when language changes."""

        pass

    def retranslate_ui(self):
        """Updates all translatable strings in UI."""

        if hasattr(self, "profile_group_title") and self.profile_group_title:
            self.profile_group_title.setText(tr("Profile"))
        if hasattr(self, "personal_names_title") and self.personal_names_title:
            self.personal_names_title.setText(tr("Names for Personal Chat"))
        if hasattr(self, "options_group_title") and self.options_group_title:
            self.options_group_title.setText(tr("Options"))
        if hasattr(self, "ai_group_title") and self.ai_group_title:
            self.ai_group_title.setText(tr("Analysis"))
        if hasattr(self, "terminal_group_title") and self.terminal_group_title:
            self.terminal_group_title.setText(tr("Terminal"))
        if (
            hasattr(self, "preview_group_title_label")
            and self.preview_group_title_label
        ):
            self.preview_group_title_label.setText(tr("Preview"))

        if hasattr(self, "my_name_label"):
            self.my_name_label.setText(tr("Your name (in chat):"))
        if hasattr(self, "partner_name_label"):
            self.partner_name_label.setText(tr("Partner's name:"))
        if hasattr(self, "label_show_time"):
            self.label_show_time.setText(tr("Show message time"))
        if hasattr(self, "label_show_reactions"):
            self.label_show_reactions.setText(tr("Show reactions"))
        if hasattr(self, "label_reaction_authors"):
            self.label_reaction_authors.setText(tr("Show reaction authors"))
        if hasattr(self, "label_show_optimization"):
            self.label_show_optimization.setText(tr("Optimization"))
        if hasattr(self, "label_streak_break_time"):
            self.label_streak_break_time.setText(tr("Streak break time:"))
        if hasattr(self, "label_show_markdown"):
            self.label_show_markdown.setText(tr("Show Markdown"))
        if hasattr(self, "label_show_links"):
            self.label_show_links.setText(tr("Show links"))
        if hasattr(self, "label_show_tech_info"):
            self.label_show_tech_info.setText(tr("Show technical information"))
        if hasattr(self, "label_show_service_notifications"):
            self.label_show_service_notifications.setText(
                tr("Show service notifications")
            )
        if hasattr(self, "drop_zone"):
            self.drop_zone.setText(tr("Drag and drop result.json file here"))

        if hasattr(self, "radio_group"):
            self.radio_group.setText(tr("Group Chat"))
        if hasattr(self, "radio_channel"):
            self.radio_channel.setText(tr("Channel"))
        if hasattr(self, "radio_posts"):
            self.radio_posts.setText(tr("Posts and Comments"))
        if hasattr(self, "radio_personal"):
            self.radio_personal.setText(tr("Personal Chat"))

        if hasattr(self, "recalculate_button"):
            self.recalculate_button.setText(tr("Calculate"))
        if hasattr(self, "save_button"):
            self.save_button.setText(tr("Save to file..."))

        if hasattr(self, "calendar_button"):
            self.calendar_button.setToolTip(tr("Calendar View"))
        if hasattr(self, "diagram_button"):
            self.diagram_button.setToolTip(tr("Token Analysis"))
        if hasattr(self, "install_manager_button"):
            self.install_manager_button.setToolTip(tr("Installation Manager"))
        if hasattr(self, "settings_button"):
            self.settings_button.setToolTip(tr("Settings"))

        self.update_group_titles_on_language_change()
