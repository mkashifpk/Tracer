from __future__ import annotations

from tests.asset_generator import GeneratedAssets
from tracer.core.vtracer_engine import VTracerTracingEngine
from tracer.models.trace_settings import TraceSettings


def test_vtracer_engine_falls_back_to_python_color_vectorizer(
    generated_assets: GeneratedAssets,
    monkeypatch,
) -> None:
    engine = VTracerTracingEngine()

    def fail_child_process(*_args, **_kwargs):  # noqa: ANN001
        raise RuntimeError("synthetic crash")

    monkeypatch.setattr(engine, "_trace_image_in_child_process", fail_child_process)

    svg_text = engine.trace(generated_assets.black_circle_png, TraceSettings(trace_mode="color"))

    assert "viewBox=" in svg_text
    assert "fill=" in svg_text
