from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class FileItem:
    path: Path
    extension: str
    width: int = 0
    height: int = 0
    has_alpha: bool = False
    status: str = "Ready"
    message: str = ""

    @property
    def filename(self) -> str:
        return self.path.name
