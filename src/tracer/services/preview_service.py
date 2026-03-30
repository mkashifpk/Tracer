from __future__ import annotations

from pathlib import Path

from tracer.models.preview_result import PreviewResult
from tracer.models.trace_settings import TraceSettings
from tracer.services.tracing_service import TracingService


class PreviewService:
    def __init__(self, tracing_service: TracingService | None = None) -> None:
        self.tracing_service = tracing_service or TracingService()

    def render_preview(self, image_path: Path, settings: TraceSettings) -> PreviewResult:
        return self.tracing_service.build_preview(image_path, settings)

    def backend_name(self, settings: TraceSettings, image_path: Path | None = None) -> str:
        return self.tracing_service.backend_name(settings, image_path)
