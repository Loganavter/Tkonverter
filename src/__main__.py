import os
import sys
from pathlib import Path

try:

    current_dir = Path(__file__).resolve().parent

    project_dir = current_dir.parent

    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
except Exception:

    pass

from src.core.flatpak_tokenizer_path import (
    ensure_flatpak_tokenizer_path,
    ensure_frozen_windows_tokenizer_path,
    setup_flatpak_hf_cache,
    setup_frozen_windows_hf_cache,
)
ensure_flatpak_tokenizer_path()
ensure_frozen_windows_tokenizer_path()
setup_flatpak_hf_cache()
setup_frozen_windows_hf_cache()

import argparse
import logging

logging.getLogger("markdown").setLevel(logging.CRITICAL)
logging.getLogger("markdown.extensions").setLevel(logging.CRITICAL)

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from src.core.application.anonymizer_service import AnonymizerService
from src.core.application.analysis_service import AnalysisService
from src.core.application.calendar_service import CalendarService
from src.core.application.chat_memory_service import ChatMemoryService
from src.core.application.chat_service import ChatService
from src.core.application.chart_service import ChartService
from src.core.application.conversion_service import ConversionService
from src.core.application.tokenizer_service import TokenizerService
from src.core.dependency_injection import setup_container
from src.core.settings import SettingsManager
from src.core.theme import LIGHT_THEME_PALETTE, DARK_THEME_PALETTE
from src.presenters.preview_service import PreviewService
from src.shared_toolkit.ui.managers.theme_manager import ThemeManager
from src.shared_toolkit.ui.managers.font_manager import FontManager
from src.ui.main_window import MainWindow

from src.shared_toolkit.utils.paths import resource_path
main_window = None

def on_initialization_finished(initial_theme: str):
    global main_window
    container = setup_container()
    anonymizer_service = container.get(AnonymizerService)
    settings_manager = SettingsManager(
        "Tkonverter",
        "Tkonverter",
        anonymizer_service=anonymizer_service,
    )
    theme_manager = ThemeManager.get_instance()
    font_manager = FontManager.get_instance()
    main_window = MainWindow(
        initial_theme=initial_theme,
        settings_manager=settings_manager,
        theme_manager=theme_manager,
        font_manager=font_manager,
        chat_service=container.get(ChatService),
        conversion_service=container.get(ConversionService),
        analysis_service=container.get(AnalysisService),
        calendar_service=container.get(CalendarService),
        tokenizer_service=container.get(TokenizerService),
        anonymizer_service=anonymizer_service,
        preview_service=container.get(PreviewService),
        chart_service=container.get(ChartService),
        chat_memory_service=container.get(ChatMemoryService),
    )

def main():
    parser = argparse.ArgumentParser(description="Tkonverter - Logging Settings")
    parser.add_argument(
        "--enable-logging", action="store_true", help="Permanently enable logging."
    )
    parser.add_argument(
        "--disable-logging", action="store_true", help="Permanently disable logging."
    )
    args, unknown = parser.parse_known_args()

    container = setup_container()
    anonymizer_service = container.get(AnonymizerService)
    settings_manager = SettingsManager(
        "Tkonverter",
        "Tkonverter",
        anonymizer_service=anonymizer_service,
    )

    if args.enable_logging or args.disable_logging:
        app_instance = QApplication.instance()
        if not app_instance:
            app_instance = QApplication(sys.argv)
        enabled = args.enable_logging
        settings_manager.save_debug_mode(enabled)
        status = "enabled" if enabled else "disabled"
        print(f"Permanent logging was {status}.")
        sys.exit(0)

    if sys.platform == "win32":
        try:
            QApplication.setHighDpiScaleFactorRoundingPolicy(
                Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
            )
        except AttributeError:
            pass
    app = QApplication(sys.argv)

    icon_path = resource_path("resources/icons/icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    app.setApplicationName("Tkonverter")
    app.setApplicationDisplayName("Tkonverter")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Tkonverter")
    app.setOrganizationDomain("Tkonverter.local")

    session_debug = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")
    permanent_debug = settings_manager.load_debug_mode()
    debug_mode = session_debug or permanent_debug
    log_level = logging.DEBUG if debug_mode else logging.WARNING

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - [%(levelname)s] - (%(filename)s:%(lineno)d) - %(message)s',
        stream=sys.stdout
    )

    logging.getLogger("PyQt6").setLevel(logging.WARNING)

    main_logger = logging.getLogger("Main")

    try:
        import ctypes
        if sys.platform == "win32":
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Tkonverter.app.1.0.0")
    except (ImportError, AttributeError):
        pass

    theme_manager = ThemeManager.get_instance()

    theme_manager.register_palettes(LIGHT_THEME_PALETTE, DARK_THEME_PALETTE)

    app_qss = resource_path("resources/styles/base.qss")
    theme_manager.register_qss_path(app_qss)

    toolkit_base_qss = resource_path("shared_toolkit/ui/resources/styles/base.qss")
    theme_manager.register_qss_path(toolkit_base_qss)

    toolkit_qss = resource_path("shared_toolkit/ui/resources/styles/widgets.qss")
    theme_manager.register_qss_path(toolkit_qss)

    theme_from_env = os.environ.get("APP_THEME", "").lower()

    if theme_from_env in ("light", "dark", "auto"):
        final_theme_to_apply = theme_from_env
    else:
        final_theme_to_apply = settings_manager.load_theme()

    theme_manager.set_theme(final_theme_to_apply, app)

    on_initialization_finished(initial_theme=final_theme_to_apply)

    def _show_ready():
        app = QApplication.instance()
        main_window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)

        saved = main_window.settings_manager.load_main_window_geometry()
        if saved and not saved.isEmpty():
            main_window.restoreGeometry(saved)
        else:
            screen = app.primaryScreen()
            if screen:
                rect = screen.availableGeometry()
                fr = main_window.frameGeometry()
                fr.moveCenter(rect.center())
                main_window.move(fr.topLeft())
        main_window.setWindowOpacity(0.0)
        main_window.show()

        for _ in range(25):
            app.processEvents()
        main_window.setWindowOpacity(1.0)

        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                DWMWA_TRANSITIONS_FORCEDISABLED = 3
                hwnd = int(main_window.winId())
                value = wintypes.BOOL(True)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    wintypes.HWND(hwnd),
                    wintypes.DWORD(DWMWA_TRANSITIONS_FORCEDISABLED),
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
            except Exception:
                pass
        app.processEvents()
    QTimer.singleShot(0, _show_ready)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
