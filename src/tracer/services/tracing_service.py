from __future__ import annotations

from pathlib import Path

import cv2

from tracer.core.image_preprocessor import ImagePreprocessor
from tracer.core.tracing_engine import TracingEngine, build_tracing_engine, describe_backend, resolve_trace_mode
from tracer.core.vtracer_engine import VTracerTracingEngine
from tracer.models.preview_result import PreviewResult
from tracer.models.trace_settings import TraceSettings


class TracingService:
    def __init__(
        self,
        preprocessor: ImagePreprocessor | None = None,
        tracing_engine: TracingEngine | None = None,
    ) -> None:
        self.preprocessor = preprocessor or ImagePreprocessor()
        self.tracing_engine = tracing_engine

    def backend_name(self, settings: TraceSettings, image_path: Path | None = None) -> str:
        if self.tracing_engine is not None:
            return self.tracing_engine.backend_name
        return describe_backend(settings, image_path)

    def build_preview(self, image_path: Path, settings: TraceSettings) -> PreviewResult:
        try:
            active_engine = self.tracing_engine or build_tracing_engine(settings, image_path)
            mode = resolve_trace_mode(settings, image_path)
            preprocessed = self.preprocessor.preprocess(image_path, settings)
            if mode == "color":
                svg_text = active_engine.trace(image_path, settings)
                mask_bytes = self._build_color_preview_bytes(active_engine, image_path, settings)
                processing_label = "Color Preparation"
            else:
                svg_text = active_engine.trace_mask(
                    preprocessed.binary_mask,
                    preprocessed.width,
                    preprocessed.height,
                    settings,
                )
                encoded, mask_png = cv2.imencode(".png", preprocessed.binary_mask)
                mask_bytes = mask_png.tobytes() if encoded else b""
                processing_label = "Processed Mask"
            return PreviewResult(
                source_loaded=True,
                mask_available=bool(mask_bytes),
                svg_available=True,
                processing_label=processing_label,
                width=preprocessed.width,
                height=preprocessed.height,
                mask_png_bytes=mask_bytes,
                svg_text=svg_text,
            )
        except Exception as exc:  # noqa: BLE001
            return PreviewResult(
                source_loaded=False,
                mask_available=False,
                svg_available=False,
                error=str(exc),
            )

    def _build_color_preview_bytes(
        self,
        engine: TracingEngine,
        image_path: Path,
        settings: TraceSettings,
    ) -> bytes:
        if isinstance(engine, VTracerTracingEngine):
            return engine.build_preview_png(image_path, settings)
        return b""
