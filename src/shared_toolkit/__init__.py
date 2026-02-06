"""
Shared Toolkit - Общая библиотека для проектов Improve-ImgSLI и Tkonverter

Этот модуль содержит общие компоненты, используемые в обоих проектах:
- Утилиты для работы с файлами и путями
- UI компоненты (fluent widgets, менеджеры)
- Общие скрипты и функции
"""

from shared_toolkit.utils import get_unique_filepath, resource_path
from shared_toolkit.ui.widgets.atomic import (
    FluentCheckBox,
    CustomButton,
    CustomLineEdit,
    FluentComboBox,
    FluentRadioButton,
    FluentSwitch,
    FluentSlider,
    FluentSpinBox,
    BodyLabel,
    CaptionLabel,
    AdaptiveLabel,
    CompactLabel,
    GroupTitleLabel,
    CustomGroupWidget,
    CustomGroupBuilder,
    MinimalistScrollBar,
    OverlayScrollArea,
    UnifiedIconButton,
    ButtonMode
)
from shared_toolkit.ui.managers import ThemeManager, FlyoutManager
from shared_toolkit.ui.services import IconService, get_icon_by_name, get_icon_service
from shared_toolkit.ui.dialogs import HelpDialog

__version__ = "1.1.0"
__author__ = "Loganavter"

__all__ = [
    'get_unique_filepath',
    'resource_path',
    'FluentCheckBox',
    'CustomButton',
    'CustomLineEdit',
    'FluentComboBox',
    'FluentRadioButton',
    'FluentSwitch',
    'FluentSlider',
    'FluentSpinBox',
    'BodyLabel',
    'CaptionLabel',
    'AdaptiveLabel',
    'CompactLabel',
    'GroupTitleLabel',
    'CustomGroupWidget',
    'CustomGroupBuilder',
    'MinimalistScrollBar',
    'OverlayScrollArea',
    'UnifiedIconButton',
    'ButtonMode',
    'ThemeManager',
    'FlyoutManager',
    'IconService',
    'get_icon_by_name',
    'get_icon_service',
    'HelpDialog'
]
