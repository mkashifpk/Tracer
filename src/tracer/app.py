from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyleFactory

from tracer.services.config_manager import ConfigManager
from tracer.ui.main_window import MainWindow
from tracer.ui.theme import app_stylesheet
from tracer.utils.resources import optional_app_icon_path
from tracer.utils.logger import configure_logging, get_logger


def create_application() -> tuple[QApplication, MainWindow]:
    app = QApplication(sys.argv)
    app.setApplicationName("Tracer")
    app.setOrganizationName("Tracer")
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet(app_stylesheet())

    configure_logging()
    logger = get_logger(__name__)
    logger.info("Starting Tracer application")

    icon_path = optional_app_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))

    config_manager = ConfigManager()
    window = MainWindow(config_manager=config_manager)
    return app, window
