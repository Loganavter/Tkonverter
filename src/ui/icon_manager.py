"""
Icon Manager - Менеджер иконок для Tkonverter.

Этот модуль содержит только enum с иконками и простую обертку над общим IconService.
"""

from enum import Enum
from PyQt6.QtGui import QIcon

from src.shared_toolkit.ui.services import get_icon_service

class AppIcon(Enum):
    """Иконки, используемые в Tkonverter."""
    SETTINGS = "settings.svg"
    SAVE = "save.svg"
    FOLDER_OPEN = "folder_open.svg"
    CHART = "chart.svg"
    DOWNLOAD = "download.svg"
    CALENDAR = "calendar.svg"
    HELP = "help.svg"

def get_app_icon(icon: AppIcon) -> QIcon:
    """
    Получить иконку приложения используя общий IconService.

    Args:
        icon: Enum иконки

    Returns:
        QIcon: Обработанная иконка
    """
    service = get_icon_service("Tkonverter")
    return service.get_icon(icon.value)
