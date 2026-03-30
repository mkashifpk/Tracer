from __future__ import annotations

from time import monotonic

from PySide6.QtCore import QObject, Signal, Slot

from tracer.models.app_settings import ExportLogFormat
from tracer.models.batch_job import BatchJob, BatchProgress, BatchSummary
from tracer.models.trace_settings import TraceSettings
from tracer.services.batch_processing_manager import BatchProcessingManager


class BatchWorker(QObject):
    PROGRESS_EMIT_INTERVAL_S = 0.12
    JOB_FLUSH_INTERVAL_S = 0.12
    JOB_FLUSH_BATCH_SIZE = 8

    progress_changed = Signal(object)
    jobs_finished = Signal(object)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        batch_manager: BatchProcessingManager,
        jobs: list[BatchJob],
        settings: TraceSettings,
        log_format: ExportLogFormat,
        max_workers: int,
    ) -> None:
        super().__init__()
        self.batch_manager = batch_manager
        self.jobs = jobs
        self.settings = settings
        self.log_format = log_format
        self.max_workers = max_workers
        self._pending_jobs: list[BatchJob] = []
        self._latest_progress: BatchProgress | None = None
        self._last_progress_emit_at = 0.0
        self._last_job_flush_at = 0.0

    @Slot()
    def run(self) -> None:
        try:
            summary = self.batch_manager.process_jobs(
                jobs=self.jobs,
                settings=self.settings,
                on_progress=self._on_progress,
                on_job_finished=self._on_job_finished,
                max_workers=self.max_workers,
            )
            self._emit_progress(force=True)
            self._flush_pending_jobs(force=True)
            if self.log_format != "none":
                try:
                    self.batch_manager.export_summary_log(summary, self.log_format)
                except Exception as exc:  # noqa: BLE001
                    summary.log_export_error = str(exc)
            self.completed.emit(summary)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))

    @Slot()
    def cancel(self) -> None:
        self.batch_manager.cancel()

    def _on_progress(self, progress: BatchProgress) -> None:
        self._latest_progress = progress
        self._emit_progress()

    def _on_job_finished(self, job: BatchJob) -> None:
        self._pending_jobs.append(job)
        self._flush_pending_jobs()

    def _emit_progress(self, force: bool = False) -> None:
        if self._latest_progress is None:
            return
        now = monotonic()
        progress = self._latest_progress
        should_emit = force or (now - self._last_progress_emit_at) >= self.PROGRESS_EMIT_INTERVAL_S
        should_emit = should_emit or progress.completed_jobs >= progress.total_jobs
        if not should_emit:
            return
        self._last_progress_emit_at = now
        self.progress_changed.emit(progress)

    def _flush_pending_jobs(self, force: bool = False) -> None:
        if not self._pending_jobs:
            return
        now = monotonic()
        should_flush = force or len(self._pending_jobs) >= self.JOB_FLUSH_BATCH_SIZE
        should_flush = should_flush or (now - self._last_job_flush_at) >= self.JOB_FLUSH_INTERVAL_S
        if not should_flush:
            return
        pending_jobs = list(self._pending_jobs)
        self._pending_jobs.clear()
        self._last_job_flush_at = now
        self.jobs_finished.emit(pending_jobs)
