from __future__ import annotations

from pathlib import Path


def local_app_data_dir() -> Path:
    return Path.home() / "AppData" / "Local" / "Tracer"


def config_file_path() -> Path:
    return local_app_data_dir() / "config.json"


def preset_file_path() -> Path:
    return local_app_data_dir() / "presets.json"


def log_directory_path() -> Path:
    return local_app_data_dir() / "logs"
