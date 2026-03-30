from __future__ import annotations

import csv
import os
import re
from collections.abc import Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from tracer.core.svg_exporter import SvgExporter
from tracer.core.tracing_engine import TracingEngine, build_default_tracing_engine, build_tracing_engine, describe_backend
from tracer.models.app_settings import ExistingOutputMode, ExportLogFormat
from tracer.models.batch_job import BatchJob, BatchProgress, BatchSummary
from tracer.models.trace_settings import TraceSettings
from tracer.utils.logger import get_logger

ProgressCallback = Callable[[BatchProgress], None]
JobCallback = Callable[[BatchJob], None]

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1F]+')
RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


@dataclass(frozen=True, slots=True)
class ProcessedJobResult:
    source_path: str
    output_path: str
    status: str
    error: str = ""
    warning: str = ""
    started_at: str = ""
    finished_at: str = ""


def _process_job_in_subprocess(source_path: str, output_path: str, settings_payload: dict) -> ProcessedJobResult:
    started_at = datetime.now()
    try:
        settings = TraceSettings.from_dict(settings_payload)
        engine = build_tracing_engine(settings, Path(source_path))
        engine.trace_to_file(Path(source_path), Path(output_path), settings)
        status = "Exported"
        error = ""
    except Exception as exc:  # noqa: BLE001
        status = "Failed"
        error = str(exc)

    finished_at = datetime.now()
    return ProcessedJobResult(
        source_path=source_path,
        output_path=output_path,
        status=status,
        error=error,
        started_at=started_at.isoformat(timespec="seconds"),
        finished_at=finished_at.isoformat(timespec="seconds"),
    )


class BatchProcessingManager:
    def __init__(
        self,
        tracing_engine: TracingEngine | None = None,
        exporter: SvgExporter | None = None,
    ) -> None:
        self.logger = get_logger(__name__)
        self.tracing_engine = tracing_engine
        self.exporter = exporter or SvgExporter()
        self._cancel_requested = False

    @property
    def backend_name(self) -> str:
        if self.tracing_engine is not None:
            return self.tracing_engine.backend_name
        return build_default_tracing_engine().backend_name

    def backend_name_for_settings(self, settings: TraceSettings, image_path: Path | None = None) -> str:
        if self.tracing_engine is not None:
            return describe_backend(settings, image_path)
        return describe_backend(settings, image_path)

    def cancel(self) -> None:
        self._cancel_requested = True
        self.logger.info("Batch cancel requested")

    def create_jobs(
        self,
        source_paths: Iterable[Path],
        output_folder: Path,
        existing_output_mode: ExistingOutputMode = "skip",
    ) -> list[BatchJob]:
        output_folder.mkdir(parents=True, exist_ok=True)
        jobs: list[BatchJob] = []
        reserved_output_names: set[str] = set()

        for source_path in sorted((Path(path) for path in source_paths), key=lambda path: path.name.lower()):
            output_path = self._build_unique_output_path(source_path, output_folder, reserved_output_names)
            reserved_output_names.add(output_path.name.lower())

            job = BatchJob(
                source_path=source_path,
                output_path=output_path,
                metadata={
                    "source_filename": source_path.name,
                    "sanitized_base_name": output_path.stem,
                    "existing_output_mode": existing_output_mode,
                },
            )

            if output_path.exists() and existing_output_mode == "skip":
                job.status = "Skipped"
                job.warning = "Output SVG already exists"

            jobs.append(job)

        return jobs

    def process_jobs(
        self,
        jobs: list[BatchJob],
        settings: TraceSettings,
        on_progress: ProgressCallback | None = None,
        on_job_finished: JobCallback | None = None,
        max_workers: int = 1,
    ) -> BatchSummary:
        self._cancel_requested = False
        started_at = datetime.now()
        counts = {
            "exported_jobs": 0,
            "skipped_jobs": 0,
            "failed_jobs": 0,
            "cancelled_jobs": 0,
            "completed_jobs": 0,
        }
        total_jobs = len(jobs)

        self._emit_progress(
            on_progress,
            total_jobs=total_jobs,
            current_file="",
            **counts,
        )

        queued_jobs = [job for job in jobs if job.status == "Queued"]
        skipped_jobs = [job for job in jobs if job.status == "Skipped"]

        for job in skipped_jobs:
            job.finished_at = datetime.now()
            counts["skipped_jobs"] += 1
            counts["completed_jobs"] += 1
            self.logger.info("Skipping %s because %s", job.source_path, job.warning)
            self._finalize_job(job, on_job_finished)
            self._emit_progress(
                on_progress,
                total_jobs=total_jobs,
                current_file=job.source_path.name,
                **counts,
            )

        effective_workers = self._resolve_worker_count(max_workers, queued_jobs_count=len(queued_jobs))
        if effective_workers <= 1:
            self._process_jobs_serial(queued_jobs, settings, on_progress, on_job_finished, total_jobs, counts)
        else:
            self._process_jobs_parallel(
                queued_jobs,
                settings,
                on_progress,
                on_job_finished,
                total_jobs,
                counts,
                max_workers=effective_workers,
            )

        finished_at = datetime.now()
        output_folder = jobs[0].output_path.parent if jobs else Path()
        return BatchSummary(
            total_jobs=total_jobs,
            exported_jobs=counts["exported_jobs"],
            skipped_jobs=counts["skipped_jobs"],
            failed_jobs=counts["failed_jobs"],
            cancelled_jobs=counts["cancelled_jobs"],
            started_at=started_at,
            finished_at=finished_at,
            output_folder=output_folder,
            jobs=jobs,
        )

    def export_summary_log(self, summary: BatchSummary, log_format: ExportLogFormat) -> Path | None:
        if log_format == "none":
            return None

        summary.output_folder.mkdir(parents=True, exist_ok=True)
        timestamp = summary.finished_at.strftime("%Y%m%d_%H%M%S")
        log_path = summary.output_folder / f"tracer_batch_{timestamp}.{log_format}"

        try:
            if log_format == "txt":
                self._write_text_log(summary, log_path)
            elif log_format == "csv":
                self._write_csv_log(summary, log_path)
            else:
                raise ValueError(f"Unsupported log format: {log_format}")
        except Exception:  # noqa: BLE001
            self.logger.exception("Failed to export batch log to %s", log_path)
            raise

        summary.log_path = log_path
        self.logger.info("Batch log exported to %s", log_path)
        return log_path

    def _process_jobs_serial(
        self,
        jobs: list[BatchJob],
        settings: TraceSettings,
        on_progress: ProgressCallback | None,
        on_job_finished: JobCallback | None,
        total_jobs: int,
        counts: dict[str, int],
    ) -> None:
        for job in jobs:
            if self._cancel_requested:
                self._cancel_job(job, counts, on_job_finished, on_progress, total_jobs)
                continue

            try:
                job.status = "Processing"
                job.started_at = datetime.now()
                self.logger.info("Tracing %s -> %s", job.source_path, job.output_path)
                active_engine = self.tracing_engine or build_tracing_engine(settings, job.source_path)
                active_engine.trace_to_file(job.source_path, job.output_path, settings)
                job.status = "Exported"
                counts["exported_jobs"] += 1
            except Exception as exc:  # noqa: BLE001
                job.status = "Failed"
                job.error = str(exc)
                counts["failed_jobs"] += 1
                self.logger.exception("Batch job failed for %s", job.source_path)
            finally:
                job.finished_at = datetime.now()
                counts["completed_jobs"] += 1
                self._finalize_job(job, on_job_finished)
                self._emit_progress(
                    on_progress,
                    total_jobs=total_jobs,
                    current_file=job.source_path.name,
                    **counts,
                )

    def _process_jobs_parallel(
        self,
        jobs: list[BatchJob],
        settings: TraceSettings,
        on_progress: ProgressCallback | None,
        on_job_finished: JobCallback | None,
        total_jobs: int,
        counts: dict[str, int],
        max_workers: int,
    ) -> None:
        if not jobs:
            return

        settings_payload = settings.to_dict()
        inflight_limit = max_workers * 2
        pending_jobs = iter(jobs)
        active_futures: dict[Future[ProcessedJobResult], BatchJob] = {}

        with ProcessPoolExecutor(max_workers=max_workers, max_tasks_per_child=100) as executor:
            self._fill_process_pool(executor, active_futures, pending_jobs, settings_payload, inflight_limit)

            while active_futures:
                if self._cancel_requested:
                    for future, job in list(active_futures.items()):
                        if future.cancel():
                            self._cancel_job(job, counts, on_job_finished, on_progress, total_jobs)
                            del active_futures[future]

                done, _ = wait(active_futures.keys(), timeout=0.2, return_when=FIRST_COMPLETED)
                if not done:
                    if self._cancel_requested:
                        self._cancel_remaining_jobs(pending_jobs, counts, on_job_finished, on_progress, total_jobs)
                    continue

                for future in done:
                    job = active_futures.pop(future)
                    try:
                        result = future.result()
                    except Exception as exc:  # noqa: BLE001
                        job.status = "Failed"
                        job.error = str(exc)
                        job.finished_at = datetime.now()
                        counts["failed_jobs"] += 1
                        counts["completed_jobs"] += 1
                        self.logger.exception("Parallel batch job failed for %s", job.source_path)
                    else:
                        self._apply_processed_result(job, result, counts)

                    self._finalize_job(job, on_job_finished)
                    self._emit_progress(
                        on_progress,
                        total_jobs=total_jobs,
                        current_file=job.source_path.name,
                        **counts,
                    )

                if self._cancel_requested:
                    self._cancel_remaining_jobs(pending_jobs, counts, on_job_finished, on_progress, total_jobs)
                else:
                    self._fill_process_pool(executor, active_futures, pending_jobs, settings_payload, inflight_limit)

    def _fill_process_pool(
        self,
        executor: ProcessPoolExecutor,
        active_futures: dict[Future[ProcessedJobResult], BatchJob],
        pending_jobs: Iterable[BatchJob],
        settings_payload: dict,
        inflight_limit: int,
    ) -> None:
        while len(active_futures) < inflight_limit and not self._cancel_requested:
            try:
                job = next(pending_jobs)
            except StopIteration:
                break
            job.status = "Processing"
            job.started_at = datetime.now()
            future = executor.submit(
                _process_job_in_subprocess,
                str(job.source_path),
                str(job.output_path),
                settings_payload,
            )
            active_futures[future] = job

    def _cancel_remaining_jobs(
        self,
        pending_jobs: Iterable[BatchJob],
        counts: dict[str, int],
        on_job_finished: JobCallback | None,
        on_progress: ProgressCallback | None,
        total_jobs: int,
    ) -> None:
        for job in pending_jobs:
            self._cancel_job(job, counts, on_job_finished, on_progress, total_jobs)

    def _cancel_job(
        self,
        job: BatchJob,
        counts: dict[str, int],
        on_job_finished: JobCallback | None,
        on_progress: ProgressCallback | None,
        total_jobs: int,
    ) -> None:
        job.status = "Cancelled"
        job.warning = "Batch cancelled before this file was processed"
        job.finished_at = datetime.now()
        counts["cancelled_jobs"] += 1
        counts["completed_jobs"] += 1
        self._finalize_job(job, on_job_finished)
        self._emit_progress(
            on_progress,
            total_jobs=total_jobs,
            current_file=job.source_path.name,
            **counts,
        )

    def _apply_processed_result(self, job: BatchJob, result: ProcessedJobResult, counts: dict[str, int]) -> None:
        job.status = result.status
        job.error = result.error
        job.warning = result.warning
        job.started_at = datetime.fromisoformat(result.started_at) if result.started_at else job.started_at
        job.finished_at = datetime.fromisoformat(result.finished_at) if result.finished_at else datetime.now()

        if result.status == "Exported":
            counts["exported_jobs"] += 1
        elif result.status == "Failed":
            counts["failed_jobs"] += 1
        elif result.status == "Cancelled":
            counts["cancelled_jobs"] += 1
        counts["completed_jobs"] += 1

    def _resolve_worker_count(self, max_workers: int, queued_jobs_count: int) -> int:
        if queued_jobs_count <= 1:
            return 1

        cpu_count = os.cpu_count() or 1
        safe_default = max(1, min(cpu_count - 1, 4))
        requested = max_workers if max_workers > 0 else safe_default
        return max(1, min(requested, queued_jobs_count, safe_default))

    def _write_text_log(self, summary: BatchSummary, log_path: Path) -> None:
        duration = summary.finished_at - summary.started_at
        lines = [
            "Tracer Batch Export Log",
            f"Started: {summary.started_at.isoformat(timespec='seconds')}",
            f"Finished: {summary.finished_at.isoformat(timespec='seconds')}",
            f"Duration: {duration}",
            f"Output folder: {summary.output_folder}",
            f"Total jobs: {summary.total_jobs}",
            f"Exported: {summary.exported_jobs}",
            f"Skipped: {summary.skipped_jobs}",
            f"Failed: {summary.failed_jobs}",
            f"Cancelled: {summary.cancelled_jobs}",
            "",
            "Files:",
        ]

        for job in summary.jobs:
            lines.append(
                " | ".join(
                    [
                        job.status,
                        job.source_path.name,
                        str(job.output_path.name),
                        job.warning or job.error or "OK",
                    ]
                )
            )

        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_csv_log(self, summary: BatchSummary, log_path: Path) -> None:
        with log_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "source_file",
                    "output_file",
                    "status",
                    "warning",
                    "error",
                    "started_at",
                    "finished_at",
                ]
            )
            for job in summary.jobs:
                writer.writerow(
                    [
                        job.source_path.name,
                        job.output_path.name,
                        job.status,
                        job.warning,
                        job.error,
                        job.started_at.isoformat(timespec="seconds") if job.started_at else "",
                        job.finished_at.isoformat(timespec="seconds") if job.finished_at else "",
                    ]
                )

    def _build_unique_output_path(
        self,
        source_path: Path,
        output_folder: Path,
        reserved_output_names: set[str],
    ) -> Path:
        base_name = self._sanitize_filename(source_path.stem)
        candidate_name = f"{base_name}.svg"
        suffix = 2

        while candidate_name.lower() in reserved_output_names:
            candidate_name = f"{base_name}_{suffix}.svg"
            suffix += 1

        return output_folder / candidate_name

    def _sanitize_filename(self, filename: str) -> str:
        sanitized = INVALID_FILENAME_CHARS.sub("_", filename).strip(" .")
        sanitized = re.sub(r"_+", "_", sanitized)
        if not sanitized:
            sanitized = "file"
        if sanitized.upper() in RESERVED_WINDOWS_NAMES:
            sanitized = f"{sanitized}_file"
        return sanitized

    def _finalize_job(self, job: BatchJob, on_job_finished: JobCallback | None) -> None:
        if on_job_finished is not None:
            on_job_finished(job)

    def _emit_progress(
        self,
        on_progress: ProgressCallback | None,
        total_jobs: int,
        completed_jobs: int,
        exported_jobs: int,
        skipped_jobs: int,
        failed_jobs: int,
        cancelled_jobs: int,
        current_file: str,
    ) -> None:
        if on_progress is None:
            return

        on_progress(
            BatchProgress(
                total_jobs=total_jobs,
                completed_jobs=completed_jobs,
                exported_jobs=exported_jobs,
                skipped_jobs=skipped_jobs,
                failed_jobs=failed_jobs,
                cancelled_jobs=cancelled_jobs,
                current_file=current_file,
            )
        )
