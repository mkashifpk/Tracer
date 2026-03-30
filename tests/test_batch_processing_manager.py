from __future__ import annotations

from pathlib import Path

from tests.asset_generator import GeneratedAssets
from tracer.core.tracing_engine import TracingEngine
from tracer.models.trace_settings import TraceSettings
from tracer.services.batch_processing_manager import BatchProcessingManager


class FakeTracingEngine(TracingEngine):
    def trace(self, image_path: Path, settings: TraceSettings) -> str:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0 0L10 0L10 10Z"/></svg>'

    def trace_mask(self, mask, width: int, height: int, settings: TraceSettings) -> str:  # noqa: ANN001
        return self.trace(Path("mask"), settings)

    def trace_to_file(self, image_path: Path, output_path: Path, settings: TraceSettings) -> Path:
        output_path.write_text(self.trace(image_path, settings), encoding="utf-8")
        return output_path


def test_create_jobs_sanitizes_and_deduplicates_names(tmp_path: Path) -> None:
    manager = BatchProcessingManager(tracing_engine=FakeTracingEngine())
    source_a = tmp_path / "logo?.png"
    source_b = tmp_path / "logo*.jpg"

    output_folder = tmp_path / "out"
    jobs = manager.create_jobs([source_a, source_b], output_folder)

    assert jobs[0].output_path.name == "logo_.svg"
    assert jobs[1].output_path.name == "logo__2.svg"


def test_process_jobs_skips_existing_output_and_exports_log(tmp_path: Path) -> None:
    manager = BatchProcessingManager(tracing_engine=FakeTracingEngine())
    source = tmp_path / "icon.png"
    source.write_text("x", encoding="utf-8")

    output_folder = tmp_path / "out"
    output_folder.mkdir()
    existing_output = output_folder / "icon.svg"
    existing_output.write_text("<svg/>", encoding="utf-8")

    jobs = manager.create_jobs([source], output_folder, existing_output_mode="skip")
    summary = manager.process_jobs(jobs, TraceSettings())
    log_path = manager.export_summary_log(summary, "csv")

    assert summary.skipped_jobs == 1
    assert summary.exported_jobs == 0
    assert log_path is not None
    assert log_path.exists()


def test_process_jobs_exports_realistic_assets_with_duplicate_names(
    generated_assets: GeneratedAssets,
    tmp_path: Path,
) -> None:
    manager = BatchProcessingManager(tracing_engine=FakeTracingEngine())
    nested = tmp_path / "input"
    nested.mkdir()

    source_a = nested / "badge.png"
    source_b = nested / "badge.jpg"
    source_a.write_bytes(generated_assets.black_circle_png.read_bytes())
    source_b.write_bytes(generated_assets.black_circle_jpg.read_bytes())

    output_folder = tmp_path / "out"
    jobs = manager.create_jobs([source_a, source_b], output_folder, existing_output_mode="overwrite")
    summary = manager.process_jobs(jobs, TraceSettings())

    assert summary.exported_jobs == 2
    assert jobs[0].output_path.exists()
    assert jobs[1].output_path.exists()
    assert jobs[0].output_path.name != jobs[1].output_path.name
