from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from xml.etree import ElementTree as ET

from tracer.models.trace_settings import TraceSettings


class SvgExporter:
    def validate_svg_text(self, svg_text: str) -> ET.Element:
        try:
            root = ET.fromstring(svg_text)
        except ET.ParseError as exc:
            raise ValueError(f"Invalid SVG markup: {exc}") from exc

        if not root.tag.endswith("svg"):
            raise ValueError("SVG document root must be <svg>.")
        return root

    def build_document(self, svg_text: str, settings: TraceSettings) -> str:
        root = self.validate_svg_text(svg_text)

        if settings.fill_only_output:
            for node in root.iter():
                if node.tag.endswith("path"):
                    if settings.trace_mode != "color":
                        node.set("fill", "black")
                    if not settings.stroke_output:
                        node.set("stroke", "none")

        if settings.stroke_output:
            for node in root.iter():
                if node.tag.endswith("path"):
                    if settings.trace_mode != "color":
                        node.set("stroke", "black")
                    node.set("stroke-width", str(settings.stroke_width))

        return ET.tostring(root, encoding="unicode")

    def export(self, output_path: Path, svg_text: str, settings: TraceSettings) -> None:
        final_svg = self.build_document(svg_text, settings)
        self.write_svg_text(output_path, final_svg)

    def write_svg_text(self, output_path: Path, svg_text: str) -> None:
        self.validate_svg_text(svg_text)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=output_path.parent, suffix=".tmp") as handle:
            handle.write(svg_text if svg_text.endswith("\n") else f"{svg_text}\n")
            temp_path = Path(handle.name)

        temp_path.replace(output_path)
