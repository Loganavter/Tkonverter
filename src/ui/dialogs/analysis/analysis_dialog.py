

import logging
import math
from typing import Optional, Set, Tuple

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.colors import to_rgb
from matplotlib.patches import Wedge
from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal, QRectF
from PyQt6.QtGui import QShowEvent, QResizeEvent
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from datetime import datetime

from core.analysis.tree_analyzer import TreeNode, aggregate_children_for_view
from core.application.chart_service import ChartService
from core.view_models import SunburstSegment
from resources.translations import tr
from ui.dialogs.dialog_builder import auto_size_dialog, setup_dialog_scaffold, setup_dialog_icon
from ui.theme import ThemeManager
from ui.widgets.atomic.loading_spinner import LoadingSpinner

logger = logging.getLogger(__name__)

CENTER_HOLE_PROPORTION = 0.30
RING_WIDTH_PROPORTION = 0.22
MAX_DEPTH = 3
RESIZE_DEBOUNCE_MS = 30

class AnalysisDialog(QDialog):
    filter_accepted = pyqtSignal(set)

    def __init__(self, presenter, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.presenter = presenter
        self.root_node: Optional[TreeNode] = None
        self.current_root: Optional[TreeNode] = None
        self.unit = "chars"
        self.disabled_nodes: Set[TreeNode] = set()
        self.theme_manager = theme_manager
        self._needs_plot_after_show = False
        self.chart_service = ChartService()
        self.segments: list[SunburstSegment] = []
        self.last_hovered_segment: Optional[SunburstSegment] = None
        self.center_text_artist = None
        self._artists_created = False

        self.setWindowTitle(tr("Token Analysis by Date"))
        setup_dialog_icon(self)
        self.setMinimumSize(600, 650)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)

        self._setup_ui()
        self._connect_signals()

    def load_data_and_show(self, root_node: TreeNode, initial_disabled_nodes: set, unit: str):
        self.root_node = root_node
        self.current_root = root_node
        self.disabled_nodes = initial_disabled_nodes.copy()
        self.unit = unit
        self.spinner.stop()
        self.loading_widget.hide()
        self.canvas.show()
        self.ok_button.setEnabled(True)
        self._needs_plot_after_show = True
        self.show()

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if self._needs_plot_after_show:
            QTimer.singleShot(50, self.plot)
            self._needs_plot_after_show = False

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self.resize_timer.start(RESIZE_DEBOUNCE_MS)

    def plot(self):
        if not self.current_root or not self.isVisible() or self.canvas.width() <= 1:
            return

        if self._artists_created:
            self._update_plot_geometry()
            return

        self.ax.clear()
        self.ax.axis("off")

        self.ax.set_xlim(-1.1, 1.1)
        self.ax.set_ylim(-1.1, 1.1)

        self.segments.clear()
        self.last_hovered_segment = None

        force_first_level_full_detail = (self.current_root != self.root_node)

        self._draw_level_recursive(
            node=self.current_root,
            start_angle=0,
            end_angle=360,
            relative_depth=1,
            force_full_detail=force_first_level_full_detail,
            center_x=0.0,
            center_y=0.0,
            working_radius=1.0
        )

        self.draw_center_text(0.0, 0.0, 1.0)

        self.canvas.draw()

    def _draw_level_recursive(self, node: TreeNode, start_angle: float, end_angle: float, relative_depth: int, force_full_detail: bool, center_x: float, center_y: float, working_radius: float):
        if relative_depth > MAX_DEPTH:
            return

        children_to_display = aggregate_children_for_view(node, force_full_detail=force_full_detail)
        total_value = node.value
        if total_value <= 0:
            return

        current_angle = start_angle

        for child in children_to_display:
            sweep_angle = (child.value / total_value) * (end_angle - start_angle)

            outer_radius_px = working_radius * (CENTER_HOLE_PROPORTION + relative_depth * RING_WIDTH_PROPORTION)
            ring_width_px = working_radius * RING_WIDTH_PROPORTION

            mid_angle_deg = current_angle + sweep_angle / 2.0
            child_absolute_depth = self.chart_service.get_node_absolute_depth(child)
            color = self.chart_service.get_color_for_segment(mid_angle_deg, child_absolute_depth - 1)
            is_disabled = self.chart_service.is_effectively_disabled(child, self.disabled_nodes)
            effective_color = self.chart_service.darken_color(color) if is_disabled else color

            wedge = Wedge(
                center=(center_x, center_y), r=outer_radius_px, theta1=current_angle,
                theta2=current_angle + sweep_angle, width=ring_width_px,
                facecolor=effective_color, edgecolor=self.bg_color, linewidth=1.2,
            )
            self.ax.add_patch(wedge)

            segment = SunburstSegment(
                inner_radius=outer_radius_px - ring_width_px,
                outer_radius=outer_radius_px,
                start_angle=math.radians(current_angle),
                end_angle=math.radians(current_angle + sweep_angle),
                color=effective_color, node=child, text=child.name, is_disabled=is_disabled
            )
            segment.artist = wedge
            self.segments.append(segment)

            self._update_segment_text(segment, center_x, center_y, working_radius)

            if getattr(child, 'date_level', None) != 'others' and (child.children or (hasattr(child, 'aggregated_children') and child.aggregated_children)):
                self._draw_level_recursive(
                    child, current_angle, current_angle + sweep_angle,
                    relative_depth + 1, False, center_x, center_y, working_radius
                )

            current_angle += sweep_angle

        if relative_depth == 1 and node == self.current_root:
            self._artists_created = True

    def _update_plot_geometry(self):
        """Быстро обновляет геометрию существующих объектов без их пересоздания."""
        if not self.isVisible() or self.canvas.width() <= 1:
            return

        canvas_width = self.canvas.width()
        canvas_height = self.canvas.height()
        center_x, center_y = canvas_width / 2, canvas_height / 2
        working_radius = min(canvas_width, canvas_height) * 0.45

        self._update_artists_recursive(
            node=self.current_root,
            start_angle=0,
            end_angle=360,
            relative_depth=1,
            center_x=0.0,
            center_y=0.0,
            working_radius=1.0
        )

        self.draw_center_text(0.0, 0.0, 1.0)
        self.canvas.draw_idle()

    def _update_artists_recursive(self, node: TreeNode, start_angle: float, end_angle: float, relative_depth: int, center_x: float, center_y: float, working_radius: float):
        """Рекурсивно обновляет свойства артистов."""
        if relative_depth > MAX_DEPTH:
            return

        force_full_detail = (self.current_root != self.root_node)
        children_to_display = aggregate_children_for_view(node, force_full_detail=force_full_detail)
        total_value = node.value
        if total_value <= 0: return

        current_angle = start_angle

        for child in children_to_display:

            segment = next((s for s in self.segments if s.node == child), None)
            if not segment or not segment.artist: continue

            sweep_angle = (child.value / total_value) * (end_angle - start_angle)

            outer_radius_px = working_radius * (CENTER_HOLE_PROPORTION + relative_depth * RING_WIDTH_PROPORTION)
            ring_width_px = working_radius * RING_WIDTH_PROPORTION

            segment.artist.center = (center_x, center_y)
            segment.artist.r = outer_radius_px
            segment.artist.theta1 = current_angle
            segment.artist.theta2 = current_angle + sweep_angle
            segment.artist.width = ring_width_px

            segment.inner_radius = outer_radius_px - ring_width_px
            segment.outer_radius = outer_radius_px
            segment.start_angle = math.radians(current_angle)
            segment.end_angle = math.radians(current_angle + sweep_angle)

            if segment.text_artist:
                new_font_size = self._calculate_font_size(segment, self.canvas.height())
                if new_font_size > 0:
                    center_angle_rad = segment.start_angle + (segment.end_angle - segment.start_angle) / 2.0
                    center_radius_px = segment.inner_radius + ring_width_px / 2.0
                    x = center_x + center_radius_px * np.cos(center_angle_rad)
                    y = center_y + center_radius_px * np.sin(center_angle_rad)
                    rotation_angle_deg = np.rad2deg(center_angle_rad)
                    if 90 < rotation_angle_deg < 270: rotation_angle_deg -= 180

                    segment.text_artist.set_position((x, y))
                    segment.text_artist.set_fontsize(new_font_size)
                    segment.text_artist.set_rotation(rotation_angle_deg)
                    segment.text_artist.set_visible(True)
                else:
                    segment.text_artist.set_visible(False)

            if getattr(child, 'date_level', None) != 'others' and (child.children or (hasattr(child, 'aggregated_children') and child.aggregated_children)):
                self._update_artists_recursive(
                    child, current_angle, current_angle + sweep_angle,
                    relative_depth + 1, center_x, center_y, working_radius
                )

            current_angle += sweep_angle

    def on_click(self, event):
        if event.inaxes != self.ax or event.xdata is None: return

        r = np.sqrt(event.xdata**2 + event.ydata**2)

        if r < CENTER_HOLE_PROPORTION and self.current_root and self.current_root.parent:

            self.current_root = self.current_root.parent
            self._artists_created = False
            self.plot()
            return

        clicked_segment = self._find_segment_at_event(event)
        if not clicked_segment: return

        clicked_node = clicked_segment.node

        if event.button == 3:
            day_nodes = self.chart_service.get_descendant_day_nodes(clicked_node)
            if not day_nodes: return

            is_currently_disabled = self.chart_service.is_effectively_disabled(clicked_node, self.disabled_nodes)
            if is_currently_disabled:
                self.disabled_nodes.difference_update(day_nodes)
            else:
                self.disabled_nodes.update(day_nodes)
            self.plot()
            return

        if event.button == 1:
            is_zoomable = bool(clicked_node.children) or (hasattr(clicked_node, "aggregated_children") and clicked_node.aggregated_children)
            if is_zoomable:
                self.current_root = clicked_node
                self._artists_created = False
                self.plot()

    def on_motion(self, event):
        if event.xdata is None or event.ydata is None:
            if self.last_hovered_segment is not None:
                self.last_hovered_segment.artist.set_alpha(1.0)
                self.last_hovered_segment = None
                self.tooltip_widget.hide()
                self.canvas.draw_idle()
            return

        hover_segment = self._find_segment_at_event(event)
        if hover_segment != self.last_hovered_segment:
            if self.last_hovered_segment and hasattr(self.last_hovered_segment, 'artist'):
                self.last_hovered_segment.artist.set_alpha(1.0)
            if hover_segment and hasattr(hover_segment, 'artist'):
                hover_segment.artist.set_alpha(0.7)
            self.last_hovered_segment = hover_segment
            self.canvas.draw_idle()

        if hover_segment:
            node = hover_segment.node
            unit_str = tr('tokens') if self.unit == 'tokens' else tr('Characters')
            tooltip_text = f"<b>{self._get_translated_node_name(node)}</b><br>{unit_str}: {node.value:,.0f}"
            self.tooltip_widget.setText(tooltip_text)
            self.tooltip_widget.adjustSize()
            if event.guiEvent:
                self.tooltip_widget.move(self.canvas.mapToGlobal(event.guiEvent.pos()) + QPoint(15, 10))
            self.tooltip_widget.show()
        else:
            self.tooltip_widget.hide()

    def accept(self):
        self.filter_accepted.emit(self.disabled_nodes)
        super().accept()

    def on_external_update(self, new_disabled_set: set):
        if self.disabled_nodes != new_disabled_set:
            self.disabled_nodes = new_disabled_set.copy()
            if self.root_node and self.isVisible():
                self.plot()

    def retranslate_ui(self):
        self.setWindowTitle(tr("Token Analysis by Date"))
        self.progress_label.setText(tr("Rendering chart..."))
        self.ok_button.setText(tr("Save"))
        self.ok_button.setToolTip(tr("Save filter settings for export"))
        self.cancel_button.setText(tr("Close"))
        if self.root_node and self.isVisible(): self.plot()

    def _setup_ui(self):

        layout = QVBoxLayout(self)
        self.loading_widget = QWidget(self)
        loading_layout = QVBoxLayout(self.loading_widget)
        self.spinner = LoadingSpinner(self)
        self.progress_label = QLabel(tr("Analyzing..."), self)
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addStretch()
        loading_layout.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.progress_label)
        loading_layout.addStretch()
        self.bg_color = self.theme_manager.get_color("dialog.background").name()
        self.text_color = self.theme_manager.get_color("dialog.text").name()
        self.figure = plt.figure()
        self.figure.patch.set_facecolor(self.bg_color)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.setMinimumSize(0, 0)
        self.canvas.hide()
        self.ax = self.figure.add_axes([0, 0, 1, 1], frameon=False)
        self.ax.set_aspect('equal', anchor='C')
        self.ax.format_coord = lambda x, y: ""
        self.ax.axis("off")
        layout.addWidget(self.loading_widget)
        layout.addWidget(self.canvas)
        setup_dialog_scaffold(self, layout, ok_text=tr("Save"))
        self.ok_button.setToolTip(tr("Save filter settings for export"))
        self.cancel_button.setText(tr("Close"))
        self.ok_button.setEnabled(False)
        auto_size_dialog(self, min_width=600, min_height=650)
        self.tooltip_widget = QLabel(self, Qt.WindowType.ToolTip)
        self.tooltip_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.spinner.start()

    def _connect_signals(self):
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.plot)
        self.canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.canvas.mpl_connect("button_press_event", self.on_click)
        self.canvas.mpl_connect("figure_leave_event", self.on_figure_leave)

    def draw_center_text(self, center_x: float, center_y: float, working_radius: float):
        if not self.ax or not self.isVisible() or not self.current_root:
            return

        if self.center_text_artist:
            for artist in self.center_text_artist:
                artist.remove()
        self.center_text_artist = []

        if self.current_root.name == "Total":
            label = tr(self.unit.capitalize())
        elif self.current_root.parent is not None:
            parent_label = self._get_translated_node_name(self.current_root.parent)
            current_label = self._get_translated_node_name(self.current_root)
            label = f"{parent_label}\n{current_label}"
        else:
            label = self._get_translated_node_name(self.current_root)

        display_value = self.chart_service.calculate_filtered_value(self.current_root, self.disabled_nodes)
        value_str = f"{display_value:,.0f}"

        canvas_height_px = self.canvas.height()

        base_font_size = max(8.0, canvas_height_px / 35.0)

        if "\n" in label:
            base_font_size *= 0.85

        base_font_size = min(base_font_size, 50)

        y_pos_main = center_y + (base_font_size / canvas_height_px) * 2.0

        main_artist = self.ax.text(
            center_x, y_pos_main, f"{label}\n{value_str}",
            ha='center', va='center', fontsize=int(base_font_size),
            color=self.theme_manager.get_color("dialog.text").name(),
            wrap=True, linespacing=1.2
        )
        self.center_text_artist.append(main_artist)

        if self.current_root.parent:
            hint_font_size = int(base_font_size * 0.65)

            y_pos_hint = center_y - CENTER_HOLE_PROPORTION * 0.6
            hint_artist = self.ax.text(
                center_x, y_pos_hint, tr("click to go up"),
                ha='center', va='center', fontsize=hint_font_size,
                color=self.theme_manager.get_color("dialog.text").name(), alpha=0.6
            )
            self.center_text_artist.append(hint_artist)

    def _update_segment_text(self, segment: SunburstSegment, center_x: float, center_y: float, working_radius: float):
        text_label = self._get_translated_node_name(segment.node)
        font_size = self._calculate_font_size(segment, self.canvas.height())

        if font_size == 0: return

        center_radius_px = segment.inner_radius + (segment.outer_radius - segment.inner_radius) / 2.0
        center_angle_rad = segment.start_angle + (segment.end_angle - segment.start_angle) / 2.0
        x = center_x + center_radius_px * np.cos(center_angle_rad)
        y = center_y + center_radius_px * np.sin(center_angle_rad)
        rotation_angle_deg = np.rad2deg(center_angle_rad)
        if 90 < rotation_angle_deg < 270: rotation_angle_deg -= 180

        text_color_name = 'white'

        text_artist = self.ax.text(x, y, text_label, fontsize=font_size, color=text_color_name,
                     rotation=rotation_angle_deg, ha='center', va='center')
        segment.text_artist = text_artist

    def _calculate_font_size(self, segment: SunburstSegment, canvas_height_px: float) -> int:

        base_font_size = max(6.0, canvas_height_px / 50.0)

        text_label = self._get_translated_node_name(segment.node)
        if not text_label:
            return 0

        mid_radius_px = (segment.inner_radius + segment.outer_radius) / 2.0 * (canvas_height_px / 2.2)
        arc_length_px = (segment.end_angle - segment.start_angle) * mid_radius_px
        text_width_approx = base_font_size * len(text_label) * 0.55

        if text_width_approx > arc_length_px * 0.95:
            return 0

        ring_height_px = (segment.outer_radius - segment.inner_radius) * (canvas_height_px / 2.2)
        if base_font_size > ring_height_px * 0.7:
            return 0

        return int(base_font_size)

    def _find_segment_at_event(self, event) -> Optional[SunburstSegment]:

        x, y = event.xdata, event.ydata
        if x is None or y is None: return None

        radius = math.sqrt(x**2 + y**2)
        angle = math.atan2(y, x)
        if angle < 0:
            angle += 2 * math.pi

        for segment in reversed(self.segments):

            if segment.inner_radius <= radius <= segment.outer_radius and \
               segment.start_angle <= angle <= segment.end_angle:
                return segment
        return None

    def on_figure_leave(self, event):
        if self.last_hovered_segment:
            self.last_hovered_segment.artist.set_alpha(1.0)
            self.last_hovered_segment = None
            self.tooltip_widget.hide()
            self.canvas.draw_idle()

    def _get_translated_node_name(self, node: TreeNode) -> str:
        if not node: return ""
        name = node.name
        date_level = getattr(node, "date_level", None)

        if date_level == "month" and name.isdigit():
            try:
                month_num = int(name)
                month_key = f"month_{month_num}"
                translated = tr(month_key)
                return translated if translated != month_key else datetime(2000, month_num, 1).strftime("%B")
            except (ValueError, IndexError):
                pass
        elif name == "Total":
            return tr("Total")
        return name
