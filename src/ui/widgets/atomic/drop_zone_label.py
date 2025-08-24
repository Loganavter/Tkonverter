from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget

from ui.widgets.atomic.adaptive_label import AdaptiveLabel

class DropZoneLabel(AdaptiveLabel):
    """A specialized label widget that handles Drag-and-Drop operations correctly."""

    file_dropped = pyqtSignal(str)
    drop_zone_drag_active = pyqtSignal(bool)

    drop_zone_hover_state_changed = pyqtSignal(bool)

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)

        self.setAcceptDrops(True)
        self.setMouseTracking(True)

    def dragEnterEvent(self, event):
        """Triggers when dragged object enters the widget."""

        if event.source():
            event.ignore()
            return

        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_zone_drag_active.emit(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Triggers when dragged object leaves the widget."""
        self.drop_zone_drag_active.emit(False)
        event.accept()

    def dropEvent(self, event):
        """Triggers when file is dropped on the widget."""
        self.drop_zone_drag_active.emit(False)

        if event.source():
            event.ignore()
            return

        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                local_path = urls[0].toLocalFile()

                QTimer.singleShot(0, lambda: self.file_dropped.emit(local_path))
            event.acceptProposedAction()
        else:
            event.ignore()

    def enterEvent(self, event):
        """Triggers when cursor enters the widget (without DnD)."""
        self.drop_zone_hover_state_changed.emit(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Triggers when cursor leaves the widget (without DnD)."""
        self.drop_zone_hover_state_changed.emit(False)
        super().leaveEvent(event)
