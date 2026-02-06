"""
UI компоненты shared_toolkit.

Этот модуль содержит все UI компоненты, используемые в обоих проектах:
- Виджеты (atomic, composite)
- Менеджеры (ThemeManager, FontManager, IconManager)
- Сервисы (IconService)
- Диалоги (HelpDialog)
"""

from .widgets.atomic import (
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
from .managers import ThemeManager, FlyoutManager
from .services import IconService, get_icon_by_name, get_icon_service
from .dialogs import HelpDialog

__all__ = [
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
