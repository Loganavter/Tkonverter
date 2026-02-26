

from enum import Enum
from PyQt6.QtGui import QIcon

from src.shared_toolkit.ui.services import get_icon_service

class AppIcon(Enum):
    SETTINGS = "settings.svg"
    SAVE = "save.svg"
    QUICK_SAVE = "quick_save.svg"
    FOLDER_OPEN = "folder_open.svg"
    CHART = "chart.svg"
    DOWNLOAD = "download.svg"
    CALENDAR = "calendar.svg"
    HELP = "help.svg"
    ANONYMIZATION = "incognito.svg"
    ADD = "add.svg"
    REMOVE = "remove.svg"

def get_app_icon(icon: AppIcon) -> QIcon:
    service = get_icon_service("Tkonverter")
    return service.get_icon(icon.value)
