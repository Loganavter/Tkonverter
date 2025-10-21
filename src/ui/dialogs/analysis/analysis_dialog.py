

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

from src.core.analysis.tree_analyzer import TreeNode, aggregate_children_for_view
from src.core.analysis.tree_identity import TreeNodeIdentity
from src.core.application.chart_service import ChartService
from src.core.view_models import SunburstSegment
from src.resources.translations import tr
from src.ui.dialogs.dialog_builder import auto_size_dialog, setup_dialog_scaffold, setup_dialog_icon
from src.shared_toolkit.ui.managers.theme_manager import ThemeManager
from src.ui.widgets.atomic.loading_spinner import LoadingSpinner

logger = logging.getLogger(__name__)

CENTER_HOLE_PROPORTION = 0.30
RING_WIDTH_PROPORTION = 0.22
MAX_DEPTH = 3
RESIZE_DEBOUNCE_MS = 30

class AnalysisDialog(QDialog):
    filter_accepted = pyqtSignal(set)
    filter_changed = pyqtSignal(set)

    def __init__(self, presenter, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.presenter = presenter
        self.root_node: Optional[TreeNode] = None
        self.current_root: Optional[TreeNode] = None
        self.unit = "chars"
        self.disabled_node_ids: Set[str] = set()
        self.theme_manager = theme_manager
        self._needs_plot_after_show = False
        self.chart_service = ChartService()
        self.segments: list[SunburstSegment] = []
        self.last_hovered_segment: Optional[SunburstSegment] = None
        self.center_main_artist = None
        self.center_hint_artist = None
        self.navigation_stack = []
        self._artists_created = False

        self.setWindowTitle(tr("Token Analysis by Date"))
        setup_dialog_icon(self)
        self.setMinimumSize(600, 650)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)

        self._setup_ui()
        self._connect_signals()

    def load_data_and_show(self, root_node: TreeNode, initial_disabled_nodes: set, unit: str):
        logger.info(f"DIAGRAM opening with {len(initial_disabled_nodes)} disabled nodes")
        print(f"DIAGRAM DEBUG: Opening with root_node={root_node}, disabled_nodes={len(initial_disabled_nodes)}, unit={unit}")

        self.root_node = root_node
        self.current_root = root_node
        self.navigation_stack = [self.root_node]

        self.disabled_node_ids = {node.node_id for node in initial_disabled_nodes if hasattr(node, 'node_id') and node.node_id} if initial_disabled_nodes else set()
        logger.info(f"DIAGRAM disabled_node_ids: {len(self.disabled_node_ids)} items")
        print(f"DIAGRAM DEBUG: disabled_node_ids count = {len(self.disabled_node_ids)}")

        self.unit = unit
        self.spinner.stop()
        self.loading_widget.hide()
        self.canvas.show()
        self.ok_button.setEnabled(True)
        self._needs_plot_after_show = True
        print("DIAGRAM DEBUG: About to show dialog")
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
        print(f"DIAGRAM DEBUG: plot() called, current_root={self.current_root}")

        if not self.current_root:
            print("DIAGRAM DEBUG: No current_root, returning")
            return

        if not self.isVisible():
            print("DIAGRAM DEBUG: Dialog not visible, returning")
            return

        if self.canvas.width() <= 1:
            print(f"DIAGRAM DEBUG: Canvas width too small ({self.canvas.width()}), returning")
            return

        if not hasattr(self.current_root, 'value') or self.current_root.value <= 0:
            print(f"DIAGRAM DEBUG: Invalid current_root value ({getattr(self.current_root, 'value', 'no value attr')}), returning")
            return

        if self._artists_created:
            print("DIAGRAM DEBUG: Artists already created, updating geometry")
            self._update_plot_geometry()
            return

        print("DIAGRAM DEBUG: Starting plot creation")
        try:
            self.ax.clear()
            self.ax.axis("off")

            self.center_main_artist = None
            self.center_hint_artist = None

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
            print("DIAGRAM DEBUG: Plot creation completed successfully")

        except Exception as e:
            logger.error(f"Ошибка при отрисовке диаграммы: {e}", exc_info=True)
            print(f"DIAGRAM ERROR: {e}")
            import traceback
            traceback.print_exc()
            self._artists_created = False

    def _draw_level_recursive(self, node: TreeNode, start_angle: float, end_angle: float, relative_depth: int, force_full_detail: bool, center_x: float, center_y: float, working_radius: float):
        if relative_depth > MAX_DEPTH:
            return

        children_to_display = aggregate_children_for_view(node, force_full_detail=force_full_detail)
        total_value = node.value

        if total_value <= 0:
            return

        current_angle = start_angle
        segments_created = 0

        for child in children_to_display:
            sweep_angle = (child.value / total_value) * (end_angle - start_angle)

            outer_radius_px = working_radius * (CENTER_HOLE_PROPORTION + relative_depth * RING_WIDTH_PROPORTION)
            ring_width_px = working_radius * RING_WIDTH_PROPORTION

            mid_angle_deg = current_angle + sweep_angle / 2.0
            child_absolute_depth = self.chart_service.get_node_absolute_depth(child)
            color = self.chart_service.get_color_for_segment(mid_angle_deg, child_absolute_depth - 1)
            is_disabled = self._is_node_effectively_disabled(child)
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
            segments_created += 1

            self._update_segment_text(segment, center_x, center_y, working_radius, relative_depth)

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
                new_font_size = self._calculate_font_size(segment, self.canvas.height(), relative_depth)
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

        if event.inaxes != self.ax or event.xdata is None:
            return

        r = np.sqrt(event.xdata**2 + event.ydata**2)

        if r > 1.5:
            return

        if r < CENTER_HOLE_PROPORTION and len(self.navigation_stack) > 1:
            self.navigation_stack.pop()
            self.current_root = self.navigation_stack[-1]
            self._artists_created = False
            self.plot()
            return

        clicked_segment = self._find_segment_at_event(event)
        if not clicked_segment:
            return

        clicked_node = clicked_segment.node

        if event.button == 3:

            try:

                day_nodes = self.chart_service.get_descendant_day_nodes(clicked_node)

                if not day_nodes:
                    return

                day_node_ids = {node.node_id for node in day_nodes if hasattr(node, 'node_id') and node.node_id}
                all_disabled = all(nid in self.disabled_node_ids for nid in day_node_ids)

                if all_disabled:

                    self.disabled_node_ids.difference_update(day_node_ids)
                else:

                    self.disabled_node_ids.update(day_node_ids)

                self._artists_created = False
                self.plot()

                disabled_nodes_set = self._get_nodes_from_ids(self.disabled_node_ids)
                self.filter_changed.emit(disabled_nodes_set)

            except Exception as e:
                import traceback

                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    tr("Ошибка"),
                    tr("Произошла ошибка при обработке правого клика. Попробуйте еще раз.")
                )

            return

        if event.button == 1:
            is_zoomable = bool(clicked_node.children) or (hasattr(clicked_node, "aggregated_children") and clicked_node.aggregated_children)
            if is_zoomable:
                self.current_root = clicked_node
                self.navigation_stack.append(self.current_root)
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

        radius = math.sqrt(event.xdata**2 + event.ydata**2)
        if radius > 1.5:
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
            unit_key = "Tokens" if self.unit == "tokens" else "Characters"
            unit_str = tr(unit_key)
            tooltip_text = f"<b>{self._get_translated_node_name(node)}</b><br>{unit_str}: {node.value:,.0f}"
            self.tooltip_widget.setText(tooltip_text)
            self.tooltip_widget.adjustSize()
            if event.guiEvent:
                self.tooltip_widget.move(self.canvas.mapToGlobal(event.guiEvent.pos()) + QPoint(15, 10))
            self.tooltip_widget.show()
        else:
            self.tooltip_widget.hide()

    def accept(self):
        disabled_nodes_set = self._get_nodes_from_ids(self.disabled_node_ids)
        self.filter_accepted.emit(disabled_nodes_set)
        super().accept()

    def on_external_update(self, new_disabled_set: set):
        """Обрабатывает внешние обновления отключённых узлов."""
        new_disabled_ids = {node.node_id for node in new_disabled_set if hasattr(node, 'node_id') and node.node_id}
        if self.disabled_node_ids != new_disabled_ids:
            self.disabled_node_ids = new_disabled_ids

            if self.root_node and self.isVisible():
                try:
                    if not hasattr(self.root_node, 'value') or self.root_node.value <= 0:
                        return

                    self.plot()
                except Exception as e:
                    self._artists_created = False

    def update_chart_data(self, new_root_node: TreeNode):
        """Updates the chart with new data, preserving the current view."""
        try:
            if not new_root_node:
                return

            if not hasattr(new_root_node, 'value') or new_root_node.value <= 0:
                return

            if self.root_node and new_root_node:
                self.root_node = new_root_node

                current_path = [node.name for node in self.navigation_stack]

                node_cursor = new_root_node
                found = True
                new_nav_stack = [new_root_node]
                for name in current_path[1:]:
                    found_child = next((child for child in aggregate_children_for_view(node_cursor) if child.name == name), None)
                    if found_child:
                        node_cursor = found_child
                        new_nav_stack.append(node_cursor)
                    else:
                        found = False
                        break

                if found:
                    self.current_root = node_cursor
                    self.navigation_stack = new_nav_stack
                else:
                    self.current_root = new_root_node
                    self.navigation_stack = [new_root_node]

                self._artists_created = False
                self.plot()

        except Exception as e:
            self._artists_created = False

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

    def _is_node_disabled(self, node: TreeNode) -> bool:
        """Проверяет отключён ли узел по его node_id"""
        if not hasattr(node, 'node_id') or not node.node_id:
            return False
        return node.node_id in self.disabled_node_ids

    def _get_nodes_from_ids(self, node_ids: Set[str]) -> Set[TreeNode]:
        """Находит TreeNode объекты по их node_id в текущем дереве"""
        result = set()
        if not self.root_node:
            return result

        def collect_nodes(current_node):
            if hasattr(current_node, 'node_id') and current_node.node_id in node_ids:
                result.add(current_node)
            for child in current_node.children:
                collect_nodes(child)
            if hasattr(current_node, 'aggregated_children'):
                for child in current_node.aggregated_children:
                    collect_nodes(child)

        collect_nodes(self.root_node)
        return result

    def _is_node_effectively_disabled(self, node: TreeNode) -> bool:
        """Проверяет эффективно ли отключён узел"""
        if self._is_node_disabled(node):
            return True

        day_nodes = self.chart_service.get_descendant_day_nodes(node)
        if not day_nodes:
            return False

        return all(self._is_node_disabled(dn) for dn in day_nodes)

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

        if self.current_root.name == "Total":
            label = tr(self.unit.capitalize())
        elif self.current_root.parent is not None:
            parent_label = self._get_translated_node_name(self.current_root.parent)
            current_label = self._get_translated_node_name(self.current_root)
            label = f"{parent_label}\n{current_label}"
        else:
            label = self._get_translated_node_name(self.current_root)

        disabled_nodes_set = self._get_nodes_from_ids(self.disabled_node_ids)
        display_value = self.chart_service.calculate_filtered_value(self.current_root, disabled_nodes_set)
        value_str = f"{display_value:,.0f}"
        full_text = f"{label}\n{value_str}"

        canvas_height_px = self.canvas.height()
        base_font_size = max(8.0, canvas_height_px / 35.0)
        if "\n" in label:
            base_font_size *= 0.85
        base_font_size = min(base_font_size, 50)

        if self.current_root.name == "Total":
            y_pos_main = center_y
        else:
            y_pos_main = center_y + (base_font_size / canvas_height_px) * 2.0

        if self.center_main_artist:
            self.center_main_artist.set_text(full_text)
            self.center_main_artist.set_position((center_x, y_pos_main))
            self.center_main_artist.set_fontsize(int(base_font_size))
        else:
            self.center_main_artist = self.ax.text(
                center_x, y_pos_main, full_text,
                ha='center', va='center', fontsize=int(base_font_size),
                color=self.theme_manager.get_color("dialog.text").name(),
                wrap=True, linespacing=1.2
            )

        if self.current_root.parent:

            hint_font_size = int(base_font_size * 0.6)

            y_pos_hint = center_y - CENTER_HOLE_PROPORTION * 0.3

            hint_text = tr("click to go up")
            if self.center_hint_artist:
                self.center_hint_artist.set_text(hint_text)
                self.center_hint_artist.set_position((center_x, y_pos_hint))
                self.center_hint_artist.set_fontsize(hint_font_size)
                self.center_hint_artist.set_visible(True)
            else:
                self.center_hint_artist = self.ax.text(
                    center_x, y_pos_hint, hint_text,
                    ha='center', va='center', fontsize=hint_font_size,
                    color=self.theme_manager.get_color("dialog.text").name(), alpha=0.6
                )
        elif self.center_hint_artist:
            self.center_hint_artist.set_visible(False)

    def _update_segment_text(self, segment: SunburstSegment, center_x: float, center_y: float, working_radius: float, relative_depth: int):
        text_label = self._get_translated_node_name(segment.node)
        font_size = self._calculate_font_size(segment, self.canvas.height(), relative_depth)

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

    def _calculate_font_size(self, segment: SunburstSegment, canvas_height_px: float, relative_depth: int) -> int:
        if relative_depth > 1:
            return 0

        node = segment.node
        date_level = getattr(node, 'date_level', None)

        if date_level == "year":
            base_font_size = max(5.95, canvas_height_px / 55.0)
        elif date_level in ["month", "day"]:
            base_font_size = max(4.5, canvas_height_px / 75.0)
        else:
            base_font_size = max(5.0, canvas_height_px / 65.0)

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

        final_size = int(base_font_size)
        return final_size

    def _find_segment_at_event(self, event) -> Optional[SunburstSegment]:
        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return None

        radius = math.sqrt(x**2 + y**2)

        if radius > 1.5:
            return None

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
