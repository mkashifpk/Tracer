from __future__ import annotations

import shutil
import sys
from pathlib import Path


def app_base_path() -> Path:
    """Return the runtime base path for source and PyInstaller builds."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def resource_path(*relative_parts: str) -> Path:
    return app_base_path().joinpath(*relative_parts)


def optional_app_icon_path() -> Path | None:
    """
    Return the packaged or source icon path when available.

    Expected location:
    - source: src/tracer/assets/icons/tracer.ico
    - bundled: tracer/assets/icons/tracer.ico
    """
    candidates = [
        resource_path("assets", "icons", "tracer.ico"),
        resource_path("tracer", "assets", "icons", "tracer.ico"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def optional_potrace_path() -> Path | None:
    candidates = [
        resource_path("assets", "bin", "potrace.exe"),
        resource_path("assets", "bin", "potrace"),
        resource_path("tracer", "assets", "bin", "potrace.exe"),
        resource_path("tracer", "assets", "bin", "potrace"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    for executable in ("potrace.exe", "potrace"):
        resolved = shutil.which(executable)
        if resolved:
            return Path(resolved)
    return None
