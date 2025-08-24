import bisect
import logging
import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.colors import hsv_to_rgb, to_rgb
from matplotlib.patches import Wedge
from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from datetime import datetime

from core.analysis.tree_analyzer import TreeNode, aggregate_children_for_view
from resources.translations import tr
from ui.dialogs.dialog_builder import auto_size_dialog, setup_dialog_scaffold, setup_dialog_icon
from ui.theme import ThemeManager
from ui.widgets.atomic.loading_spinner import LoadingSpinner

logger = logging.getLogger(__name__)

CENTER_HOLE_RADIUS, RING_WIDTH, MAX_DEPTH = 0.35, 0.25, 3
YEAR_SATURATION, MONTH_SATURATION, DAY_SATURATION = 0.8, 0.7, 0.55
YEAR_BRIGHTNESS, MONTH_BRIGHTNESS, DAY_BRIGHTNESS = 0.9, 0.8, 0.7
HIGHLIGHT_ALPHA = 0.7
DARKEN_FACTOR = 0.4
RESIZE_DEBOUNCE_MS = 150
INITIAL_FONT_SIZE = 14

class AnalysisDialog(QDialog):
    filter_accepted = pyqtSignal(set)

    def __init__(self, presenter, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.presenter = presenter
        self.root_node: TreeNode | None = None
        self.current_root: TreeNode | None = None
        self.unit = "chars"
        self.unit_label = ""
        self.disabled_nodes = set()
        self._aggregation_cache = {}
        self.theme_manager = theme_manager
        self._needs_plot_after_show = False
        self._is_first_plot = True

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

        self.unit_label = tr("Token Count") if unit == "tokens" else tr("Character Count")

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

    def plot(self):
        if not self.current_root or not self.isVisible() or self.canvas.width() <= 1:
            return

        if self._is_first_plot:
            self._is_first_plot = False

        self.artist_to_node.clear()
        self.sorted_wedges_by_level.clear()
        self.start_angles_by_level.clear()
        self.last_hovered_artist = None
        self._aggregation_cache.clear()

        self.figure.clear()
        self.ax = self.figure.add_axes([0, 0, 1, 1], aspect='equal', frameon=False)
        self.ax.axis("off")
        self.figure.patch.set_facecolor(self.bg_color)

        if self.current_root.children or (hasattr(self.current_root, "aggregated_children") and self.current_root.aggregated_children):
            start_absolute_depth = self._get_node_absolute_depth(self.current_root)
            self.draw_recursive(self.current_root, 0, 360, start_absolute_depth)

        temp_wedges = {}
        for artist, (node, _) in self.artist_to_node.items():
            level = int(round((artist.r - CENTER_HOLE_RADIUS) / RING_WIDTH)) - 1
            if level not in temp_wedges: temp_wedges[level] = []
            temp_wedges[level].append(artist)
        for level, artists in sorted(temp_wedges.items()):
            artists.sort(key=lambda a: a.theta1)
            self.sorted_wedges_by_level[level] = artists
            self.start_angles_by_level[level] = [a.theta1 for a in artists]

        self.draw_center_text()
        max_radius = CENTER_HOLE_RADIUS + (MAX_DEPTH * RING_WIDTH) + 0.05
        self.ax.set_xlim(-max_radius, max_radius); self.ax.set_ylim(-max_radius, max_radius)
        self.canvas.draw_idle()

    def draw_recursive(self, node, start_angle, end_angle, start_absolute_depth):
        total_value = node.value
        if total_value <= 0: return

        current_angle = start_angle
        force_full_detail = self.current_root != self.root_node

        cache_key = (id(node), force_full_detail)
        children_to_display = self._aggregation_cache.get(cache_key)
        if not children_to_display:
            children_to_display = aggregate_children_for_view(node, force_full_detail=force_full_detail)
            self._aggregation_cache[cache_key] = children_to_display

        for child in children_to_display:
            child_absolute_depth = self._get_node_absolute_depth(child)
            relative_depth = child_absolute_depth - start_absolute_depth
            if relative_depth <= 0 or relative_depth > MAX_DEPTH: continue

            outer_radius = CENTER_HOLE_RADIUS + relative_depth * RING_WIDTH
            sweep_angle = (child.value / total_value) * (end_angle - start_angle)
            mid_angle_deg = current_angle + sweep_angle / 2.0
            color = self.get_filelight_color(mid_angle_deg, child_absolute_depth - 1)
            is_disabled = self._is_effectively_disabled(child)
            effective_color = self._darken_color(color) if is_disabled else color

            wedge = Wedge(center=(0, 0), r=outer_radius, theta1=current_angle,
                          theta2=current_angle + sweep_angle, width=RING_WIDTH,
                          facecolor=effective_color, edgecolor=self.bg_color, linewidth=1.2,
                          alpha=HIGHLIGHT_ALPHA)
            self.ax.add_patch(wedge)
            self.artist_to_node[wedge] = (child, child_absolute_depth)

            if child.children or (hasattr(child, "aggregated_children") and child.aggregated_children):
                self.draw_recursive(child, current_angle, current_angle + sweep_angle, start_absolute_depth)

            current_angle += sweep_angle

    def on_external_update(self, new_disabled_set: set):
        """
        Slot for forced state update from outside (from main presenter).
        """
        old_disabled_set = self.disabled_nodes.copy()
        if old_disabled_set != new_disabled_set:
            self.disabled_nodes = new_disabled_set.copy()
            if self.root_node and self.isVisible():
                self.plot()

    def on_click(self, event):
        if event.inaxes != self.ax:
            return

        clicked_node = self._find_node_at_event(event)

        if event.button == 3:
            if clicked_node:
                day_nodes = self._get_descendant_day_nodes(clicked_node)
                if not day_nodes:
                    return

                is_disabled = self._is_effectively_disabled(clicked_node)

                if is_disabled:
                    self.disabled_nodes.difference_update(day_nodes)
                else:
                    self.disabled_nodes.update(day_nodes)

                self.plot()

            return

        if event.button != 1: return

        r = np.sqrt(event.xdata**2 + event.ydata**2)
        if r < CENTER_HOLE_RADIUS and self.current_root.parent:
            self.current_root = self.current_root.parent
            self.plot()
            return

        if not clicked_node: return

        is_zoomable = bool(clicked_node.children) or (hasattr(clicked_node, "aggregated_children") and clicked_node.aggregated_children)
        if is_zoomable:
            if hasattr(clicked_node, "aggregated_children") and clicked_node.aggregated_children:
                 temp_root = TreeNode(clicked_node.name, clicked_node.value, parent=self.current_root)
                 for child in clicked_node.aggregated_children: temp_root.add_child(child)
                 self.current_root = temp_root
            else:
                 self.current_root = clicked_node
            self.plot()

    def on_motion(self, event):
        if event.xdata is None or event.ydata is None:
            self._reset_hover_state()
            return

        hover_artist = None
        r = np.sqrt(event.xdata**2 + event.ydata**2)
        if r > CENTER_HOLE_RADIUS:
            level = int((r - CENTER_HOLE_RADIUS) / RING_WIDTH)
            theta_deg = np.rad2deg(math.atan2(event.ydata, event.xdata)) % 360
            start_angles = self.start_angles_by_level.get(level)
            sorted_wedges = self.sorted_wedges_by_level.get(level)
            if start_angles and sorted_wedges:
                idx = bisect.bisect_right(start_angles, theta_deg) - 1
                if 0 <= idx < len(sorted_wedges):
                    candidate = sorted_wedges[idx]
                    if candidate.theta1 <= theta_deg < candidate.theta2:
                        hover_artist = candidate

        if hover_artist != self.last_hovered_artist:
            if self.last_hovered_artist: self.last_hovered_artist.set_alpha(HIGHLIGHT_ALPHA)
            if hover_artist: hover_artist.set_alpha(1.0)
            self.canvas.draw_idle()
            self.last_hovered_artist = hover_artist

        if hover_artist:
            node, _ = self.artist_to_node[hover_artist]

            translated_name = self._get_translated_node_name(node)

            tooltip_text = f"<b>{translated_name}</b><br>{self.unit_label}: {node.value:,.0f}"

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

    def retranslate_ui(self):
        """Updates all texts in dialog when language changes."""
        self.setWindowTitle(tr("Token Analysis by Date"))
        self.progress_label.setText(tr("Rendering chart..."))

        self.ok_button.setText(tr("Save"))
        self.ok_button.setToolTip(tr("Save filter settings for export"))
        self.cancel_button.setText(tr("Close"))

        old_unit_label = self.unit_label
        self.unit_label = tr("Token Count") if self.unit == "tokens" else tr("Character Count")

        if self.root_node and self.isVisible():
            self.plot()

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

        layout.addWidget(self.loading_widget)
        layout.addWidget(self.canvas)

        setup_dialog_scaffold(self, layout, ok_text=tr("Save"))
        self.ok_button.setToolTip(tr("Save filter settings for export"))
        self.cancel_button.setText(tr("Close"))
        self.ok_button.setEnabled(False)

        auto_size_dialog(self, min_width=600, min_height=650)

        self.artist_to_node = {}
        self.sorted_wedges_by_level = {}
        self.start_angles_by_level = {}
        self.last_hovered_artist = None

        self.tooltip_widget = QLabel(self, Qt.WindowType.ToolTip)
        self.tooltip_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.spinner.start()

    def _connect_signals(self):
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.plot)
        self.canvas.mpl_connect("resize_event", lambda e: self.resize_timer.start(RESIZE_DEBOUNCE_MS))
        self.canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.canvas.mpl_connect("button_press_event", self.on_click)
        self.canvas.mpl_connect("figure_leave_event", self.on_figure_leave)

    def _get_node_absolute_depth(self, node: TreeNode) -> int:
        depth = 0
        current = node
        while current and current.parent:
            depth += 1
            current = current.parent
        return depth

    def _get_descendant_day_nodes(self, node: TreeNode) -> list[TreeNode]:
        nodes = []
        q = [node]
        while q:
            curr = q.pop(0)
            is_leafy = not curr.children and not (hasattr(curr, "aggregated_children") and curr.aggregated_children)
            if is_leafy and curr.name.isdigit():
                nodes.append(curr)
            else:
                children = curr.children[:]
                if hasattr(curr, "aggregated_children") and curr.aggregated_children:
                    children.extend(curr.aggregated_children)
                q.extend(children)

        return nodes

    def _is_effectively_disabled(self, node: TreeNode) -> bool:
        day_nodes = self._get_descendant_day_nodes(node)
        return bool(day_nodes) and all(d in self.disabled_nodes for d in day_nodes)

    def get_filelight_color(self, angle_deg, level):
        hue = (angle_deg % 360) / 360.0
        sats = [YEAR_SATURATION, MONTH_SATURATION, DAY_SATURATION]
        vals = [YEAR_BRIGHTNESS, MONTH_BRIGHTNESS, DAY_BRIGHTNESS]
        return hsv_to_rgb((hue, sats[min(level, len(sats) - 1)], vals[min(level, len(vals) - 1)]))

    def _darken_color(self, color):
        return tuple(c * DARKEN_FACTOR for c in to_rgb(color))

    def _calculate_display_value(self) -> float:
        if not self.current_root: return 0.0
        day_nodes = self._get_descendant_day_nodes(self.current_root)
        if not day_nodes:
            return 0.0 if self._is_effectively_disabled(self.current_root) else self.current_root.value
        return sum(node.value for node in day_nodes if node not in self.disabled_nodes)

    def _get_translated_node_name(self, node: TreeNode) -> str:
        """Returns translated node name for display, based on date_level."""
        if not node:
            return ""

        name = node.name
        date_level = getattr(node, "date_level", None)

        if date_level == "month" and name.isdigit():
            try:
                month_num = int(name)
                month_key = f"month_gen_{month_num}"
                translated = tr(month_key)

                if translated == month_key:
                    return datetime(2000, month_num, 1).strftime("%B")
                return translated
            except (ValueError, IndexError):

                pass

        elif name == "Total":
            return tr("Total")
        elif " others" in name:

            return name

        return name

    def draw_center_text(self):

        original_name = self.current_root.name
        label = self._get_translated_node_name(self.current_root)
        if self.current_root.name == "Total":
            label = self.unit_label

        display_value = self._calculate_display_value()
        self.ax.text(0, 0, f"{label}\n{display_value:,.0f}", ha="center", va="center",
                     fontsize=INITIAL_FONT_SIZE, color=self.text_color, weight="bold")

    def on_figure_leave(self, event): self._reset_hover_state()
    def on_axes_leave(self, event): self._reset_hover_state()

    def _reset_hover_state(self):
        if self.last_hovered_artist:
            self.tooltip_widget.hide()
            self.last_hovered_artist.set_alpha(HIGHLIGHT_ALPHA)
            self.canvas.draw_idle()
            self.last_hovered_artist = None

    def _find_node_at_event(self, event) -> TreeNode | None:
        for artist, (node, _) in reversed(list(self.artist_to_node.items())):
            if artist.contains(event)[0]:
                return node
        return None
