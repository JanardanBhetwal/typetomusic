#!/usr/bin/env python3
"""
TypeToMusic - A Linux desktop app that turns keystrokes into music.
Entry point for the application.
"""

import sys
import os
import logging
import signal

# Ensure the package is importable when running from source
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typetomusic.app import TypeToMusicApp
from typetomusic.config import AppConfig


def setup_logging(config: AppConfig) -> None:
    """Configure application-wide logging."""
    log_dir = os.path.expanduser("~/.local/share/typetomusic")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "typetomusic.log")

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger("typetomusic").info("TypeToMusic starting up...")


def main() -> int:
    """Application entry point. Returns exit code."""
    config = AppConfig.load()
    setup_logging(config)

    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt

    # High-DPI support
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("TypeToMusic")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("TypeToMusic")

    # Handle Ctrl+C gracefully in terminal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    window = TypeToMusicApp(config)
    window.show()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
