import logging
import math
from typing import Optional, Set, List, TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPointF, QPoint
from PyQt6.QtGui import QPainter, QBrush, QPen, QColor, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsEllipseItem,
)

from src.core.analysis.tree_analyzer import TreeNode, aggregate_children_for_view
from src.core.view_models import SunburstSegment, SunburstSegmentViewModel, ChartRenderData
from src.resources.translations import tr
from src.ui.dialogs.dialog_builder import auto_size_dialog, setup_dialog_scaffold, setup_dialog_icon
from src.shared_toolkit.ui.managers.theme_manager import ThemeManager
from src.ui.widgets.chart.sunburst_segment_item import SunburstSegmentItem, SegmentSignals
from src.ui.widgets.atomic.loading_spinner import LoadingSpinner
from datetime import datetime

if TYPE_CHECKING:
    from src.core.application.chart_service import ChartService

logger = logging.getLogger(__name__)

CENTER_HOLE_PROPORTION = 0.30
RING_WIDTH_PROPORTION = 0.22
MAX_DEPTH = 3
RESIZE_DEBOUNCE_MS = 30
SCENE_SCALE = 400.0
MIN_ANGLE_DEG_FOR_LABEL = 4.0

CENTER_FONT_SCALE_TOTAL = 1.75
CENTER_FONT_SCALE_YEAR = 1.5
CENTER_FONT_SCALE_MONTH = 1.5
CENTER_FONT_SCALE_DAY = 1.5
CENTER_FONT_SCALE_OTHERS = 0.95

CENTER_LINE_HEIGHT_TOTAL = 1.2
CENTER_LINE_HEIGHT_YEAR = 0.9
CENTER_LINE_HEIGHT_MONTH = 0.8
CENTER_LINE_HEIGHT_DAY = 1.0
CENTER_LINE_HEIGHT_OTHERS = 1.0

CENTER_HINT_FONT_SCALE = 0.5
CENTER_HINT_FONT_MIN_PT = 6

class AnalysisDialog(QDialog):
    filter_accepted = pyqtSignal(set)
    filter_changed = pyqtSignal(set)

    def __init__(self, presenter, theme_manager: ThemeManager, chart_service: "ChartService", parent=None):
        super().__init__(parent)
        self.presenter = presenter
        self.root_node: Optional[TreeNode] = None
        self.current_root: Optional[TreeNode] = None
        self.unit = "chars"
        self.disabled_node_ids: Set[str] = set()
        self.theme_manager = theme_manager
        self._needs_plot_after_show = False
        self.chart_service = chart_service
        self.navigation_stack: List[TreeNode] = []

        self.setWindowTitle(tr("dialog.analysis.title"))
        setup_dialog_icon(self)
        self.setMinimumSize(600, 650)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)

        self._setup_ui()
        self._connect_signals()

    def load_data_and_show(self, root_node: TreeNode, initial_disabled_nodes: set, unit: str):
        self.root_node = root_node
        self.current_root = root_node
        self.navigation_stack = [self.root_node]
        self.disabled_node_ids = {
            node.node_id for node in initial_disabled_nodes
            if hasattr(node, "node_id") and node.node_id
        } if initial_disabled_nodes else set()
        self.unit = unit
        self.spinner.stop()
        self.loading_widget.hide()
        self.view.show()
        self.ok_button.setEnabled(True)
        self._needs_plot_after_show = True
        self.show()

    def showEvent(self, event):
        super().showEvent(event)
        if self._needs_plot_after_show:
            QTimer.singleShot(50, self.plot)
            self._needs_plot_after_show = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_timer.start(RESIZE_DEBOUNCE_MS)

    def plot(self):
        if not self.current_root or not self.isVisible():
            return
        if self.view.width() <= 1:
            return
        if not hasattr(self.current_root, "value") or self.current_root.value <= 0:
            return

        try:
            render_data = self._build_render_data()
            self._render_chart(render_data)
        except Exception as e:
            logger.error("Ошибка при отрисовке диаграммы: %s", e, exc_info=True)

    def _build_render_data(self) -> ChartRenderData:
        segments_vm: List[SunburstSegmentViewModel] = []
        force_first_level_full_detail = self.current_root != self.root_node
        use_global_total = self.current_root == self.root_node

        children_at_root = aggregate_children_for_view(
            self.current_root,
            force_full_detail=force_first_level_full_detail,
            use_global_total=use_global_total,
        )
        self._show_day_labels = any(getattr(c, "date_level", None) == "day" for c in children_at_root)

        self._build_segments_recursive(
            node=self.current_root,
            start_angle=0,
            end_angle=360,
            relative_depth=1,
            force_full_detail=force_first_level_full_detail,
            use_global_total=use_global_total,
            center_x=0.0,
            center_y=0.0,
            working_radius=1.0,
            segments_out=segments_vm,
        )

        center_label = self._get_center_label()
        disabled_nodes_set = self._get_nodes_from_ids(self.disabled_node_ids)
        display_value = self.chart_service.calculate_filtered_value(self.current_root, disabled_nodes_set)
        center_value_text = f"{display_value:,.0f}"
        can_go_up = len(self.navigation_stack) > 1

        return ChartRenderData(
            segments=segments_vm,
            center_text=center_label,
            center_value_text=center_value_text,
            navigation_depth=len(self.navigation_stack) - 1,
            can_go_up=can_go_up,
        )

    def _build_segments_recursive(
        self,
        node: TreeNode,
        start_angle: float,
        end_angle: float,
        relative_depth: int,
        force_full_detail: bool,
        use_global_total: bool,
        center_x: float,
        center_y: float,
        working_radius: float,
        segments_out: List[SunburstSegmentViewModel],
    ):
        if relative_depth > MAX_DEPTH:
            return

        children_to_display = aggregate_children_for_view(
            node,
            force_full_detail=force_full_detail,
            use_global_total=use_global_total,
        )
        total_value = sum(c.value for c in children_to_display if c.value > 0)
        if total_value <= 0:
            return

        canvas_height_px = self.view.height()
        current_angle = start_angle

        for child in children_to_display:
            sweep_angle = (child.value / total_value) * (end_angle - start_angle)
            outer_radius_norm = working_radius * (CENTER_HOLE_PROPORTION + relative_depth * RING_WIDTH_PROPORTION)
            ring_width_norm = working_radius * RING_WIDTH_PROPORTION
            inner_radius_norm = outer_radius_norm - ring_width_norm

            mid_angle_deg = current_angle + sweep_angle / 2.0
            child_absolute_depth = self.chart_service.get_node_absolute_depth(child)
            color = self.chart_service.get_color_for_segment(mid_angle_deg, child_absolute_depth - 1)
            is_disabled = self._is_node_effectively_disabled(child)
            effective_color = self.chart_service.darken_color(color) if is_disabled else color

            start_angle_rad = math.radians(current_angle)
            end_angle_rad = math.radians(current_angle + sweep_angle)
            mid_angle_rad = math.radians(mid_angle_deg)
            center_radius_norm = inner_radius_norm + ring_width_norm / 2.0
            label_x = center_radius_norm * math.cos(mid_angle_rad)
            label_y = center_radius_norm * math.sin(mid_angle_rad)
            label_rotation = mid_angle_deg
            if 90 < label_rotation < 270:
                label_rotation -= 180

            segment = SunburstSegment(
                inner_radius=inner_radius_norm,
                outer_radius=outer_radius_norm,
                start_angle=start_angle_rad,
                end_angle=end_angle_rad,
                color=effective_color,
                node=child,
                text=child.name,
                is_disabled=is_disabled,
            )
            font_size = self._calculate_font_size(segment, canvas_height_px, relative_depth)
            date_level = getattr(child, "date_level", None)
            has_children = bool(child.children or (getattr(child, "aggregated_children", None)))

            if date_level == "others":
                label_text = ""
                font_size = 0
            elif date_level == "month":
                label_text = self._get_short_label_for_segment(child)
                font_size = max(font_size, 8)
            elif date_level == "day":
                if getattr(self, "_show_day_labels", False):
                    label_text = self._get_short_label_for_segment(child)
                    font_size = max(font_size, 8)
                else:
                    label_text = ""
                    font_size = 0
            else:
                label_text = self._get_translated_node_name(child) if font_size > 0 else ""

            if sweep_angle < MIN_ANGLE_DEG_FOR_LABEL:
                label_text = ""
                font_size = 0

            is_zoomable = has_children

            date_display = ""
            if date_level in ("year", "month", "day", "others"):
                date_display = self._get_translated_node_name(child)

            vm = SunburstSegmentViewModel(
                start_angle=start_angle_rad,
                end_angle=end_angle_rad,
                inner_radius=inner_radius_norm,
                outer_radius=outer_radius_norm,
                color=effective_color,
                label=label_text,
                label_x=label_x,
                label_y=label_y,
                label_rotation=label_rotation,
                font_size=font_size,
                node_id=getattr(child, "node_id", None) or "",
                value_text=f"{child.value:,.0f}",
                is_clickable=is_zoomable,
                is_disabled=is_disabled,
                date_display=date_display,
            )
            segments_out.append(vm)

            if has_children and date_level != "others":
                self._build_segments_recursive(
                    child, current_angle, current_angle + sweep_angle,
                    relative_depth + 1, False, use_global_total,
                    center_x, center_y, working_radius, segments_out
                )

            current_angle += sweep_angle

    def _render_chart(self, render_data: ChartRenderData):
        self.scene.clear()
        bg_color = self.theme_manager.get_color("dialog.background")
        self.view.setBackgroundBrush(QBrush(bg_color))

        for seg_vm in render_data.segments:
            item = SunburstSegmentItem(seg_vm, self.segment_signals, self.theme_manager)
            self.scene.addItem(item)

        self._draw_center_info(render_data)

        bounds = self.scene.itemsBoundingRect().adjusted(-10, -10, 10, 10)
        self.view.fitInView(bounds, Qt.AspectRatioMode.KeepAspectRatio)

    def _get_center_font_scale(self) -> float:
        if not self.current_root:
            return CENTER_FONT_SCALE_TOTAL
        date_level = getattr(self.current_root, "date_level", None)
        if date_level == "year":
            scale = CENTER_FONT_SCALE_YEAR
        elif date_level == "month":
            scale = CENTER_FONT_SCALE_MONTH
        elif date_level == "day":
            scale = CENTER_FONT_SCALE_DAY
        elif date_level == "others":
            scale = CENTER_FONT_SCALE_OTHERS
        else:
            scale = CENTER_FONT_SCALE_TOTAL

        inside_others = any(getattr(n, "date_level", None) == "others" for n in self.navigation_stack)
        if inside_others:
            scale = max(scale, CENTER_FONT_SCALE_YEAR)
        return scale

    def _get_center_line_height(self) -> float:
        if not self.current_root:
            return CENTER_LINE_HEIGHT_TOTAL
        date_level = getattr(self.current_root, "date_level", None)
        if date_level == "year":
            line_h = CENTER_LINE_HEIGHT_YEAR
        elif date_level == "month":
            line_h = CENTER_LINE_HEIGHT_MONTH
        elif date_level == "day":
            line_h = CENTER_LINE_HEIGHT_DAY
        elif date_level == "others":
            line_h = CENTER_LINE_HEIGHT_OTHERS
        else:
            line_h = CENTER_LINE_HEIGHT_TOTAL

        inside_others = any(getattr(n, "date_level", None) == "others" for n in self.navigation_stack)
        if inside_others:
            line_h = max(line_h, CENTER_LINE_HEIGHT_YEAR)
        return line_h

    def _draw_center_info(self, render_data: ChartRenderData):
        text_color = self.theme_manager.get_color("dialog.text").name()

        view_min = min(self.view.width(), self.view.height())
        scene_diameter = 2.0 * SCENE_SCALE
        scale_after_fit = view_min / scene_diameter if scene_diameter > 0 else 1.0
        target_pt_on_screen = max(7, view_min / 56)
        base_size = max(5, min(18, int(target_pt_on_screen / scale_after_fit))) if scale_after_fit > 0 else 8

        inside_others = any(getattr(n, "date_level", None) == "others" for n in self.navigation_stack)
        if "\n" in render_data.center_text and not inside_others:
            base_size = int(base_size * 0.85)
        base_size = int(base_size * self._get_center_font_scale())
        base_size = min(max(base_size, 8), 50)
        line_height = self._get_center_line_height()

        unit_str = tr("Tokens") if self.unit == "tokens" else tr("Characters")
        html = (
            f"<div style='color:{text_color}; font-family:sans-serif; text-align:center; margin:0; padding:0; line-height:{line_height};'>"
            f"<span style='font-size:{base_size}pt;'>{render_data.center_text}</span><br/>"
            f"<span style='font-size:{int(base_size*1.2)}pt; font-weight:bold;'>{render_data.center_value_text}</span><br/>"
            f"<span style='font-size:{int(base_size*0.8)}pt; opacity:0.8;'>{unit_str}</span>"
            f"</div>"
        )
        text_item = QGraphicsTextItem()
        doc = text_item.document()
        doc.setDocumentMargin(0)
        doc.setDefaultStyleSheet("body { margin: 0; padding: 0; }")
        text_item.setHtml(html)
        text_item.setTextWidth(260)
        br = text_item.boundingRect()
        text_item.setPos(-br.width() / 2.0, -br.height() / 2.0)
        text_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.scene.addItem(text_item)

        if render_data.can_go_up:
            r = CENTER_HOLE_PROPORTION * SCENE_SCALE
            center_ellipse = QGraphicsEllipseItem(-r, -r, r * 2, r * 2)
            center_ellipse.setBrush(QBrush(Qt.GlobalColor.transparent))
            center_ellipse.setPen(QPen(Qt.PenStyle.NoPen))
            center_ellipse.setZValue(10)

            def on_center_click(event):
                if event.button() == Qt.MouseButton.LeftButton and len(self.navigation_stack) > 1:
                    self.navigation_stack.pop()
                    self.current_root = self.navigation_stack[-1]
                    self.plot()

            center_ellipse.mousePressEvent = on_center_click
            self.scene.addItem(center_ellipse)

            hint_text = tr("analysis.click_to_go_up")
            hint = QGraphicsTextItem()
            hint.setPlainText(hint_text)
            hint.setDefaultTextColor(QColor(text_color))
            hint.setOpacity(0.6)
            hint_font = QFont()
            hint_font.setPointSize(max(CENTER_HINT_FONT_MIN_PT, int(base_size * CENTER_HINT_FONT_SCALE)))
            hint.setFont(hint_font)
            h_br = hint.boundingRect()
            hint.setPos(-h_br.width() / 2, br.height() / 2 - 8)
            hint.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.scene.addItem(hint)

    def _handle_segment_click(self, node_id: str, button: int):
        if not node_id:
            return
        node = self._find_node_by_id(node_id)
        if not node:
            return

        if button == 3:
            try:
                day_nodes = self.chart_service.get_descendant_day_nodes(node)
                if not day_nodes:
                    return
                day_node_ids = {n.node_id for n in day_nodes if getattr(n, "node_id", None)}
                all_disabled = all(nid in self.disabled_node_ids for nid in day_node_ids)
                if all_disabled:
                    self.disabled_node_ids -= day_node_ids
                else:
                    self.disabled_node_ids |= day_node_ids
                self.plot()
                self.filter_changed.emit(self._get_nodes_from_ids(self.disabled_node_ids))
            except Exception:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, tr("error.title"), tr("error.chart_right_click"))
            return

        if button == 1:
            has_children = bool(node.children or getattr(node, "aggregated_children", None))
            if has_children:
                self.current_root = node
                self.navigation_stack.append(self.current_root)
                self.plot()

    def _tooltip_text_for_segment(self, data: SunburstSegmentViewModel) -> str:
        unit_str = tr("Tokens") if self.unit == "tokens" else tr("Characters")
        title = data.date_display or data.label
        if title:
            return f"{title}<br>{unit_str}: {data.value_text}"
        return f"{unit_str}: {data.value_text}"

    def _show_segment_tooltip_at(self, data: SunburstSegmentViewModel, screen_pos: QPointF):
        self._tooltip_hide_timer.stop()
        new_text = self._tooltip_text_for_segment(data)

        if getattr(self, "_last_tooltip_text", None) != new_text:
            self._tooltip_label.setText(new_text)
            self._tooltip_label.adjustSize()
            self._last_tooltip_text = new_text
        pt = screen_pos.toPoint() + QPoint(15, 10)
        self._tooltip_label.move(pt)
        if not self._tooltip_label.isVisible():
            self._tooltip_label.show()

    def _handle_segment_hover_enter(self, data: SunburstSegmentViewModel, screen_pos: QPointF):
        self._show_segment_tooltip_at(data, screen_pos)

    def _handle_segment_hover_move(self, data: SunburstSegmentViewModel, screen_pos: QPointF):
        self._show_segment_tooltip_at(data, screen_pos)

    def _handle_segment_hover_leave(self):
        self._tooltip_hide_timer.start(80)

    def _find_node_by_id(self, node_id: str) -> Optional[TreeNode]:
        if not self.root_node or not node_id:
            return None

        def find_in_tree(n: TreeNode):
            if getattr(n, "node_id", None) == node_id:
                return n
            for c in n.children:
                r = find_in_tree(c)
                if r:
                    return r
            for c in getattr(n, "aggregated_children", []) or []:
                r = find_in_tree(c)
                if r:
                    return r
            return None

        r = find_in_tree(self.root_node)
        if r:
            return r
        if node_id.startswith("others:"):
            parent_id = node_id[7:]
            parent = self._find_node_by_id(parent_id) if parent_id else self.root_node
            if not parent:
                return None
            use_global_total = self.current_root == self.root_node
            for child in aggregate_children_for_view(parent, use_global_total=use_global_total):
                if getattr(child, "node_id", None) == node_id:
                    return child
        return None

    def accept(self):
        self.filter_accepted.emit(self._get_nodes_from_ids(self.disabled_node_ids))
        super().accept()

    def on_external_update(self, new_disabled_set: set):
        new_ids = {n.node_id for n in new_disabled_set if getattr(n, "node_id", None)}
        if self.disabled_node_ids != new_ids:
            self.disabled_node_ids = new_ids
            if self.root_node and self.isVisible() and getattr(self.root_node, "value", 0) > 0:
                self.plot()

    def update_chart_data(self, new_root_node: TreeNode):
        try:
            if not new_root_node or not getattr(new_root_node, "value", 0):
                return
            if self.root_node and new_root_node:
                if new_root_node is self.root_node and self.navigation_stack:
                    self.plot()
                    return
                self.root_node = new_root_node
                path_names = [n.name for n in self.navigation_stack]
                cursor = new_root_node
                new_stack = [new_root_node]
                for name in path_names[1:]:
                    child = self._find_child_by_name(cursor, name)
                    if child:
                        cursor = child
                        new_stack.append(cursor)
                    else:
                        new_stack = [new_root_node]
                        cursor = new_root_node
                        break
                self.current_root = cursor
                self.navigation_stack = new_stack
                self.plot()
        except Exception:
            pass

    def retranslate_ui(self):
        self.setWindowTitle(tr("dialog.analysis.title"))
        self.progress_label.setText(tr("analysis.rendering_chart"))
        self.ok_button.setText(tr("common.save"))
        self.ok_button.setToolTip(tr("analysis.save_filter_settings"))
        self.cancel_button.setText(tr("common.close"))
        if self.root_node and self.isVisible():
            self.plot()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.loading_widget = QWidget(self)
        loading_layout = QVBoxLayout(self.loading_widget)
        self.spinner = LoadingSpinner(self)
        self.progress_label = QLabel(tr("analysis.analyzing"), self)
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addStretch()
        loading_layout.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.progress_label)
        loading_layout.addStretch()

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.view.setMinimumSize(0, 0)
        self.view.hide()

        self.segment_signals = SegmentSignals()
        self.segment_signals.clicked.connect(self._handle_segment_click)
        self.segment_signals.hover_enter.connect(self._handle_segment_hover_enter)
        self.segment_signals.hover_move.connect(self._handle_segment_hover_move)
        self.segment_signals.hover_leave.connect(self._handle_segment_hover_leave)

        layout.addWidget(self.loading_widget)
        layout.addWidget(self.view)
        setup_dialog_scaffold(self, layout, ok_text=tr("common.save"))
        self.cancel_button.setText(tr("common.close"))
        self.ok_button.setEnabled(False)
        auto_size_dialog(self, min_width=600, min_height=650)

        self._tooltip_label = QLabel(self)
        self._tooltip_label.setWindowFlags(Qt.WindowType.ToolTip)
        self._tooltip_label.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._tooltip_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._tooltip_label.setStyleSheet(
            "background-color: palette(tooltip-base); color: palette(tooltip-text); "
            "padding: 4px 8px; border: 1px solid palette(mid);"
        )
        self._tooltip_label.setTextFormat(Qt.TextFormat.RichText)
        self._tooltip_label.hide()

        self._tooltip_hide_timer = QTimer(self)
        self._tooltip_hide_timer.setSingleShot(True)
        self._tooltip_hide_timer.timeout.connect(self._tooltip_label.hide)

        self.spinner.start()

    def _connect_signals(self):
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.plot)

    def _get_center_label(self) -> str:
        if not self.current_root:
            return ""
        name = getattr(self.current_root, "name", None)
        if name is None:
            return ""
        date_level = getattr(self.current_root, "date_level", None)
        if date_level == "year":
            return str(name)
        if date_level == "month" and isinstance(name, str) and name.isdigit():
            try:
                return self._month_name_from_number(int(name))
            except (ValueError, TypeError):
                pass
        if date_level == "day":
            return str(name) if name else ""
        if name == "Total":
            return tr("analysis.total")
        if self.current_root.parent is not None:
            parent_label = self._get_short_label_for_center(self.current_root.parent)
            current_label = self._get_short_label_for_center(self.current_root)
            return f"{parent_label}\n{current_label}" if (parent_label and current_label) else (parent_label or current_label)
        return str(name)

    def _get_short_label_for_center(self, node: TreeNode) -> str:
        name = getattr(node, "name", None)
        if name is None:
            return ""
        date_level = getattr(node, "date_level", None)
        if date_level == "year":
            return str(name)
        if date_level == "month" and isinstance(name, str) and name.isdigit():
            try:
                return self._month_name_from_number(int(name))
            except (ValueError, TypeError):
                pass
        if date_level == "day":
            return str(name) if name else ""
        if date_level == "others":
            return tr("analysis.others_short")
        if name == "Total":
            return tr("analysis.total")
        return str(name)

    def _is_node_disabled(self, node: TreeNode) -> bool:
        return bool(getattr(node, "node_id", None) and node.node_id in self.disabled_node_ids)

    def _get_nodes_from_ids(self, node_ids: Set[str]) -> Set[TreeNode]:
        result = set()
        if not self.root_node:
            return result

        def collect(n: TreeNode):
            if getattr(n, "node_id", None) and n.node_id in node_ids:
                result.add(n)
            for c in n.children:
                collect(c)
            for c in getattr(n, "aggregated_children", []) or []:
                collect(c)

        collect(self.root_node)
        return result

    def _is_node_effectively_disabled(self, node: TreeNode) -> bool:
        if self._is_node_disabled(node):
            return True
        day_nodes = self.chart_service.get_descendant_day_nodes(node)
        return bool(day_nodes and all(self._is_node_disabled(d) for d in day_nodes))

    def _find_child_by_name(self, node: TreeNode, name: str) -> Optional[TreeNode]:
        use_global_total = self.current_root == self.root_node
        children = aggregate_children_for_view(node, use_global_total=use_global_total)
        for c in children:
            if c.name == name:
                return c
            agg = getattr(c, "aggregated_children", None)
            if agg:
                for ac in agg:
                    if ac.name == name:
                        return ac
        return None

    def _calculate_font_size(self, segment: SunburstSegment, canvas_height_px: float, relative_depth: int) -> int:
        if relative_depth > 1:
            return 0
        node = segment.node
        date_level = getattr(node, "date_level", None)
        if date_level == "year":
            base = max(5.95, canvas_height_px / 55.0)
        elif date_level in ("month", "day"):
            base = max(4.5, canvas_height_px / 75.0)
        else:
            base = max(5.0, canvas_height_px / 65.0)
        label = self._get_translated_node_name(node)
        if not label:
            return 0
        mid_r = (segment.inner_radius + segment.outer_radius) / 2.0 * (canvas_height_px / 2.2)
        arc_px = (segment.end_angle - segment.start_angle) * mid_r
        if base * len(label) * 0.55 > arc_px * 0.95:
            return 0
        ring_px = (segment.outer_radius - segment.inner_radius) * (canvas_height_px / 2.2)
        if base > ring_px * 0.7:
            return 0
        return int(base)

    def _month_name_from_number(self, month_num: int) -> str:
        key = f"month_{month_num}"
        t = tr(key)
        return t if t != key else datetime(2000, month_num, 1).strftime("%B")

    def _get_short_label_for_segment(self, node: TreeNode) -> str:
        if not node:
            return ""
        name = getattr(node, "name", None)
        if name is None:
            return ""
        date_level = getattr(node, "date_level", None)
        if date_level == "month" and isinstance(name, str) and name.isdigit():
            try:
                return self._month_name_from_number(int(name))
            except (ValueError, TypeError):
                return str(name)
        if date_level == "day" and isinstance(name, str):
            return name.zfill(2) if name.isdigit() else name
        if date_level == "others":
            return ""
        return str(name)

    def _get_translated_node_name(self, node: TreeNode) -> str:
        if not node:
            return ""
        name = getattr(node, "name", None)
        if name is None:
            return ""
        date_level = getattr(node, "date_level", None)
        if date_level == "year":
            return str(name)
        if date_level == "month" and isinstance(name, str) and name.isdigit():
            try:
                parent = getattr(node, "parent", None)
                year = getattr(parent, "name", None) if parent else ""
                month_name = self._month_name_from_number(int(name))
                return f"{year} {month_name}".strip() or month_name
            except (ValueError, IndexError):
                pass
        if date_level == "day" and isinstance(name, str):
            try:
                parent = getattr(node, "parent", None)
                if parent and getattr(parent, "name", None) and getattr(parent, "parent", None):
                    month_num = int(parent.name)
                    year = getattr(parent.parent, "name", None) or ""
                    month_name = self._month_name_from_number(month_num)
                    day_part = name if name.isdigit() else name.zfill(2)
                    return f"{year} {month_name} {day_part}".strip()
            except (ValueError, TypeError, AttributeError):
                pass
        if name == "Total":
            return tr("analysis.total")
        return str(name)

    def update_language(self, _lang_code: str | None = None):
        self.retranslate_ui()
