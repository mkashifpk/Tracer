from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw

from tests.asset_generator import GeneratedAssets
from tracer.core.tracing_engine import ContourTracingEngine, example_trace_png_to_svg, resolve_trace_mode
from tracer.models.trace_settings import TraceSettings


def test_tracing_engine_generates_svg_for_circle(generated_assets: GeneratedAssets) -> None:
    engine = ContourTracingEngine()

    svg = engine.trace(
        generated_assets.black_circle_png,
        TraceSettings(quality_preset="high"),
    )

    assert "<svg" in svg
    assert "<path" in svg
    assert "viewBox=" in svg
    assert "fill-rule=\"evenodd\"" in svg


def test_tracing_engine_supports_inversion_for_white_on_black(generated_assets: GeneratedAssets) -> None:
    engine = ContourTracingEngine()

    svg = engine.trace(
        generated_assets.white_on_black_png,
        TraceSettings(invert_colors=True, quality_preset="high"),
    )

    assert "<path" in svg
    assert "stroke=\"none\"" in svg or "stroke=\"black\"" in svg


def test_example_trace_png_to_svg_writes_output_file(generated_assets: GeneratedAssets, tmp_path: Path) -> None:
    output_path = tmp_path / "circle.svg"

    written_path = example_trace_png_to_svg(generated_assets.black_circle_png, output_path)

    svg_text = written_path.read_text(encoding="utf-8")
    assert written_path.exists()
    assert "viewBox=" in svg_text
    root = ET.fromstring(svg_text)
    assert any(node.tag.endswith("path") for node in root.iter())


def test_auto_trace_mode_prefers_monochrome_for_binary_art(generated_assets: GeneratedAssets) -> None:
    mode = resolve_trace_mode(TraceSettings(trace_mode="auto"), generated_assets.black_circle_png)

    assert mode == "monochrome"


def test_auto_trace_mode_prefers_color_for_colorful_art(tmp_path: Path) -> None:
    colorful_path = tmp_path / "colorful.png"
    image = Image.new("RGBA", (120, 120), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((12, 12, 58, 108), fill=(255, 70, 70, 255))
    draw.rectangle((62, 12, 108, 108), fill=(70, 120, 255, 255))
    draw.ellipse((24, 24, 96, 96), fill=(255, 215, 0, 255))
    image.save(colorful_path)

    mode = resolve_trace_mode(TraceSettings(trace_mode="auto"), colorful_path)

    assert mode == "color"
