from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

ExistingOutputMode = Literal["skip", "overwrite"]
ExportLogFormat = Literal["none", "txt", "csv"]


@dataclass(slots=True)
class AppSettings:
    input_folder: str = ""
    output_folder: str = ""
    overwrite_existing: bool = False
    existing_output_mode: ExistingOutputMode = "skip"
    export_log_format: ExportLogFormat = "none"
    max_workers: int = 2
    preview_debounce_ms: int = 300
    open_output_after_export: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "AppSettings":
        overwrite_existing = bool(payload.get("overwrite_existing", False))
        existing_output_mode = str(payload.get("existing_output_mode", "overwrite" if overwrite_existing else "skip"))
        if existing_output_mode not in {"skip", "overwrite"}:
            existing_output_mode = "overwrite" if overwrite_existing else "skip"
        export_log_format = str(payload.get("export_log_format", "none"))
        if export_log_format not in {"none", "txt", "csv"}:
            export_log_format = "none"
        cpu_count = os.cpu_count() or 1
        safe_worker_max = max(1, min(cpu_count - 1, 4))
        return cls(
            input_folder=str(payload.get("input_folder", "")),
            output_folder=str(payload.get("output_folder", "")),
            overwrite_existing=overwrite_existing,
            existing_output_mode=existing_output_mode,
            export_log_format=export_log_format,
            max_workers=max(1, min(int(payload.get("max_workers", safe_worker_max)), safe_worker_max)),
            preview_debounce_ms=int(payload.get("preview_debounce_ms", 300)),
            open_output_after_export=bool(payload.get("open_output_after_export", False)),
        )

    @property
    def input_path(self) -> Path | None:
        return Path(self.input_folder) if self.input_folder else None

    @property
    def output_path(self) -> Path | None:
        return Path(self.output_folder) if self.output_folder else None
