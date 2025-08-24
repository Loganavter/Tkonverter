import os
from enum import Enum
from functools import lru_cache

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap

from ui.theme import ThemeManager
from utils.paths import resource_path

class AppIcon(Enum):
    SETTINGS = "settings.svg"
    SAVE = "save.svg"
    FOLDER_OPEN = "folder_open.svg"
    CHART = "chart.svg"
    DOWNLOAD = "download.svg"
    CALENDAR = "calendar.svg"
    HELP = "help.svg"

@lru_cache(maxsize=32)
def _get_cached_icon(icon: AppIcon, is_dark: bool) -> QIcon:
    if not isinstance(icon, AppIcon):
        return QIcon()

    relative_path = os.path.join("resources", "assets", "icons", icon.value)
    full_path = resource_path(relative_path)

    if not os.path.exists(full_path):

        return QIcon()

    source_icon = QIcon(full_path)

    if not is_dark:
        return source_icon

    base_size = source_icon.actualSize(QSize(256, 256))
    if not base_size.isValid():
        base_size = QSize(256, 256)

    source_pixmap = source_icon.pixmap(base_size)
    if source_pixmap.isNull():
        return source_icon

    result_pixmap = QPixmap(source_pixmap.size())
    result_pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result_pixmap)
    painter.drawPixmap(0, 0, source_pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(result_pixmap.rect(), QColor("white"))
    painter.end()

    return QIcon(result_pixmap)

def get_icon(icon: AppIcon) -> QIcon:
    theme_manager = ThemeManager.get_instance()
    return _get_cached_icon(icon, theme_manager.is_dark())
