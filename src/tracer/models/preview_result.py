from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PreviewResult:
    source_loaded: bool
    mask_available: bool
    svg_available: bool
    processing_label: str = "Processed Mask"
    width: int = 0
    height: int = 0
    mask_png_bytes: bytes = b""
    svg_text: str = ""
    warning: str = ""
    error: str = ""
