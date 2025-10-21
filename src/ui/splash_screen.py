from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from src.resources.translations import tr
from src.shared_toolkit.ui.managers.theme_manager import ThemeManager
from src.ui.widgets.atomic.loading_spinner import LoadingSpinner

class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()

        self.setObjectName("SplashScreen")

        self.setWindowFlags(
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setMinimumSize(300, 200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.logo_placeholder = QLabel("Tkonverter")
        self.logo_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_placeholder.setStyleSheet("font-size: 24px; font-weight: bold;")

        self.spinner = LoadingSpinner(self)

        self.status_label = QLabel(tr("Preparing to launch"), self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)

        layout.addStretch()
        layout.addWidget(self.logo_placeholder)
        layout.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.spinner.start()

        screen_geometry = QApplication.primaryScreen().geometry()
        self.move(screen_geometry.center() - self.rect().center())

    def update_status(self, text: str):
        self.status_label.setText(text)
        QApplication.processEvents()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        theme_manager = ThemeManager.get_instance()
        bg_color = theme_manager.get_color("dialog.background")
        border_color = theme_manager.get_color("dialog.border")

        painter.setBrush(QBrush(bg_color))

        painter.setPen(QPen(border_color, 1))

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawRoundedRect(rect, 8.0, 8.0)

        super().paintEvent(event)
