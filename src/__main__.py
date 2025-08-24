import os
import sys

base_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_path)

import argparse
import logging

from PyQt6.QtCore import QThreadPool
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from core.settings import SettingsManager, setup_logging
from ui.theme import ThemeManager
from ui.tkonverter_main_window import TkonverterMainWindow
from utils.paths import resource_path

main_logger = logging.getLogger("Main")
main_window = None

def on_initialization_finished(initial_theme: str):
    global main_window
    main_window = TkonverterMainWindow(initial_theme=initial_theme)
    main_window.show()

def main():
    parser = argparse.ArgumentParser(description="Tkonverter - Logging Settings")
    parser.add_argument(
        "--enable-logging", action="store_true", help="Permanently enable logging."
    )
    parser.add_argument(
        "--disable-logging", action="store_true", help="Permanently disable logging."
    )
    args, unknown = parser.parse_known_args()

    settings_manager = SettingsManager("tkonverter", "tkonverter")

    if args.enable_logging or args.disable_logging:
        app_instance = QApplication.instance()
        if not app_instance:
            app_instance = QApplication(sys.argv)
        enabled = args.enable_logging
        settings_manager.save_debug_mode(enabled)
        status = "enabled" if enabled else "disabled"
        print(f"Permanent logging was {status}.")
        sys.exit(0)

    app = QApplication(sys.argv)

    icon_path = resource_path("resources/icons/icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    app.setApplicationName("Tkonverter")
    app.setApplicationDisplayName("Tkonverter")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("tkonverter")
    app.setOrganizationDomain("tkonverter.local")

    session_debug = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")
    permanent_debug = settings_manager.load_debug_mode()
    debug_mode = session_debug or permanent_debug
    log_level = logging.DEBUG if debug_mode else logging.WARNING

    if debug_mode:

        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            handlers=[logging.StreamHandler()]
        )
    else:

        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            handlers=[logging.StreamHandler()]
        )

    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("PyQt6").setLevel(logging.WARNING)
    main_logger.setLevel(log_level)

    try:
        import ctypes
        if sys.platform == "win32":
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("tkonverter.app.1.0.0")
    except (ImportError, AttributeError):
        pass

    theme_manager = ThemeManager.get_instance()

    theme_from_env = os.environ.get("APP_THEME", "").lower()

    if theme_from_env in ("light", "dark", "auto"):
        final_theme_to_apply = theme_from_env
    else:
        final_theme_to_apply = settings_manager.load_theme()

    theme_manager.set_theme(final_theme_to_apply, app)

    on_initialization_finished(initial_theme=final_theme_to_apply)

    def on_quit():
        if not QThreadPool.globalInstance().waitForDone(3000):
            QThreadPool.globalInstance().clear()

    app.aboutToQuit.connect(on_quit)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
