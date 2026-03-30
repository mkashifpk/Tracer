from pathlib import Path

import pytest

from tracer.core.svg_exporter import SvgExporter
from tracer.models.trace_settings import TraceSettings


def test_svg_exporter_writes_file(tmp_path: Path) -> None:
    exporter = SvgExporter()
    output = tmp_path / "sample.svg"
    exporter.export(
        output,
        '<svg viewBox="0 0 10 10" xmlns="http://www.w3.org/2000/svg"><path d="M0 0L10 0L10 10Z"/></svg>',
        TraceSettings(),
    )
    assert output.exists()


def test_svg_exporter_rejects_invalid_svg(tmp_path: Path) -> None:
    exporter = SvgExporter()

    with pytest.raises(ValueError):
        exporter.write_svg_text(tmp_path / "bad.svg", "<html></html>")


def test_svg_exporter_preserves_color_fills_for_color_mode() -> None:
    exporter = SvgExporter()

    svg_text = exporter.build_document(
        '<svg viewBox="0 0 10 10" xmlns="http://www.w3.org/2000/svg"><path d="M0 0L10 0L10 10Z" fill="#ff0000" stroke="#0000ff"/></svg>',
        TraceSettings(trace_mode="color", fill_only_output=True, stroke_output=False),
    )

    assert 'fill="#ff0000"' in svg_text
    assert 'stroke="none"' in svg_text
