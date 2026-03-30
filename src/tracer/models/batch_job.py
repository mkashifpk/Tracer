from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

BatchJobStatus = Literal["Queued", "Processing", "Exported", "Skipped", "Failed", "Cancelled"]


@dataclass(slots=True)
class BatchJob:
    source_path: Path
    output_path: Path
    status: BatchJobStatus = "Queued"
    error: str = ""
    warning: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class BatchProgress:
    total_jobs: int
    completed_jobs: int
    exported_jobs: int
    skipped_jobs: int
    failed_jobs: int
    cancelled_jobs: int
    current_file: str = ""

    @property
    def percent(self) -> int:
        if self.total_jobs <= 0:
            return 0
        return int(round((self.completed_jobs / self.total_jobs) * 100))


@dataclass(slots=True)
class BatchSummary:
    total_jobs: int
    exported_jobs: int
    skipped_jobs: int
    failed_jobs: int
    cancelled_jobs: int
    started_at: datetime
    finished_at: datetime
    output_folder: Path
    jobs: list[BatchJob] = field(default_factory=list)
    log_path: Path | None = None
    log_export_error: str = ""

    @property
    def succeeded(self) -> bool:
        return self.failed_jobs == 0 and self.cancelled_jobs == 0
