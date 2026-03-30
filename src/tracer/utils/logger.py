from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from tracer.utils.paths import log_directory_path


def configure_logging() -> None:
    log_dir = log_directory_path()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "tracer.log"

    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
