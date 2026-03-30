from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import subprocess

import cv2
import numpy as np
from PIL import Image
from xml.etree import ElementTree as ET

from tracer.core.contour_extractor import ContourExtractor, ContourData
from tracer.core.image_preprocessor import ImagePreprocessor
from tracer.core.svg_exporter import SvgExporter
from tracer.models.trace_settings import ResolvedTraceSettings, TraceMode, TraceSettings
from tracer.utils.resources import optional_potrace_path


@dataclass(slots=True)
class TraceVectorResult:
    """Structured vector output before final SVG serialization."""

    width: int
    height: int
    paths: list[str]


class TracingEngine(ABC):
    @property
    def backend_name(self) -> str:
        """Human-readable backend name for UI and logs."""
        return self.__class__.__name__

    @abstractmethod
    def trace(self, image_path: Path, settings: TraceSettings) -> str:
        """Trace a source image and return SVG markup."""

    @abstractmethod
    def trace_mask(self, mask: np.ndarray, width: int, height: int, settings: TraceSettings) -> str:
        """Trace a precomputed binary mask and return SVG markup."""

    @abstractmethod
    def trace_to_file(self, image_path: Path, output_path: Path, settings: TraceSettings) -> Path:
        """Trace a source image and write the final SVG file."""


class ContourTracingEngine(TracingEngine):
    """
    In-process tracing engine optimized for black-and-white source images.

    Pipeline:
    1. Load source image with alpha support.
    2. Ignore transparent background when configured.
    3. Convert to grayscale.
    4. Threshold to a binary foreground mask.
    5. Optionally invert foreground/background.
    6. Remove tiny connected components.
    7. Smooth mask edges conservatively.
    8. Extract contours with hole support.
    9. Simplify and smooth contour point sets.
    10. Convert contours into closed SVG path data.
    11. Serialize a complete SVG document.
    """

    def __init__(
        self,
        preprocessor: ImagePreprocessor | None = None,
        contour_extractor: ContourExtractor | None = None,
        svg_exporter: SvgExporter | None = None,
    ) -> None:
        self.preprocessor = preprocessor or ImagePreprocessor()
        self.contour_extractor = contour_extractor or ContourExtractor()
        self.svg_exporter = svg_exporter or SvgExporter()

    @property
    def backend_name(self) -> str:
        return "Fallback Contour"

    def trace(self, image_path: Path, settings: TraceSettings) -> str:
        preprocessed = self.preprocessor.preprocess(image_path, settings)
        return self.trace_mask(
            mask=preprocessed.binary_mask,
            width=preprocessed.width,
            height=preprocessed.height,
            settings=settings,
        )

    def trace_mask(self, mask: np.ndarray, width: int, height: int, settings: TraceSettings) -> str:
        if mask.ndim != 2:
            raise ValueError("Binary mask must be a single-channel array.")

        resolved = settings.resolve()
        contour_data = self.contour_extractor.extract(mask)
        vector_result = self._build_vector_result(contour_data, width, height, resolved)
        return self._build_svg_document(vector_result, settings)

    def trace_to_file(self, image_path: Path, output_path: Path, settings: TraceSettings) -> Path:
        svg_text = self.trace(image_path, settings)
        self.svg_exporter.write_svg_text(output_path, svg_text)
        return output_path

    def _build_vector_result(
        self,
        contour_data: ContourData,
        width: int,
        height: int,
        resolved: ResolvedTraceSettings,
    ) -> TraceVectorResult:
        if contour_data.hierarchy is None or not contour_data.contours:
            return TraceVectorResult(width=width, height=height, paths=[])

        hierarchy = contour_data.hierarchy[0]
        paths: list[str] = []

        for index in self._sorted_root_indices(contour_data.contours, hierarchy):
            subpaths: list[str] = []
            outer_path = self._contour_to_svg_subpath(contour_data.contours[index], resolved)
            if outer_path:
                subpaths.append(outer_path)

            for child_index in self._sorted_child_indices(contour_data.contours, hierarchy, index):
                hole_path = self._contour_to_svg_subpath(contour_data.contours[child_index], resolved)
                if hole_path:
                    subpaths.append(hole_path)

            if subpaths:
                paths.append(" ".join(subpaths))

        return TraceVectorResult(width=width, height=height, paths=paths)

    def _contour_to_svg_subpath(self, contour: np.ndarray, resolved: ResolvedTraceSettings) -> str:
        points = self._prepare_contour_points(contour)
        if len(points) < 3:
            return ""

        points = self._simplify_points(points, max(0.15, resolved.simplification_tolerance * 0.55))
        if len(points) < 3:
            return ""

        corner_mask = self._compute_corner_mask(points, resolved.corner_angle_threshold)
        points = self._smooth_contour_points(points, corner_mask, resolved)
        points = self._simplify_points(points, resolved.simplification_tolerance)
        points = self._remove_short_segments(points)
        if len(points) < 3:
            return ""

        corner_mask = self._compute_corner_mask(points, resolved.corner_angle_threshold)
        return self._points_to_svg_path(points, corner_mask, resolved)

    def _prepare_contour_points(self, contour: np.ndarray) -> np.ndarray:
        points = contour.reshape(-1, 2).astype(np.float32)
        if len(points) > 1 and np.allclose(points[0], points[-1]):
            points = points[:-1]
        return self._remove_adjacent_duplicates(points)

    def _remove_adjacent_duplicates(self, points: np.ndarray) -> np.ndarray:
        if len(points) < 2:
            return points

        filtered = [points[0]]
        for point in points[1:]:
            if not np.allclose(point, filtered[-1]):
                filtered.append(point)
        return np.array(filtered, dtype=np.float32)

    def _smooth_contour_points(
        self,
        points: np.ndarray,
        corner_mask: np.ndarray,
        resolved: ResolvedTraceSettings,
    ) -> np.ndarray:
        """
        Smooth contour noise while preserving true corners.

        Only non-corner points are moved. This keeps logos and geometric
        corners intact while organic curves become less jagged.
        """
        smoothed = points
        for _ in range(resolved.smoothing_iterations):
            smoothed = self._corner_preserving_smooth(smoothed, corner_mask)
        return smoothed

    def _corner_preserving_smooth(self, points: np.ndarray, corner_mask: np.ndarray) -> np.ndarray:
        updated = points.copy()
        for index in range(len(points)):
            if corner_mask[index]:
                continue

            previous = points[(index - 1) % len(points)]
            current = points[index]
            next_point = points[(index + 1) % len(points)]
            updated[index] = (previous * 0.20) + (current * 0.60) + (next_point * 0.20)
        return updated

    def _simplify_points(self, points: np.ndarray, tolerance: float) -> np.ndarray:
        contour = points.reshape(-1, 1, 2).astype(np.float32)
        simplified = self.contour_extractor.simplify(contour, tolerance)
        simplified_points = simplified.reshape(-1, 2).astype(np.float32)
        return self._remove_adjacent_duplicates(simplified_points)

    def _remove_short_segments(self, points: np.ndarray, min_length: float = 0.35) -> np.ndarray:
        if len(points) < 3:
            return points

        filtered = [points[0]]
        for point in points[1:]:
            if np.linalg.norm(point - filtered[-1]) >= min_length:
                filtered.append(point)

        if len(filtered) >= 3 and np.linalg.norm(filtered[0] - filtered[-1]) < min_length:
            filtered.pop()
        return np.array(filtered, dtype=np.float32)

    def _compute_corner_mask(self, points: np.ndarray, angle_threshold: float) -> np.ndarray:
        corner_mask = np.zeros(len(points), dtype=bool)
        for index in range(len(points)):
            corner_mask[index] = self._corner_angle(points, index) < angle_threshold
        return corner_mask

    def _points_to_svg_path(
        self,
        points: np.ndarray,
        corner_mask: np.ndarray,
        resolved: ResolvedTraceSettings,
    ) -> str:
        """
        Convert a closed polygon into a smooth SVG path.

        Sharp corners are preserved with straight segments.
        Smooth regions are emitted as cubic Bezier curves using a Catmull-Rom
        style control-point conversion.
        """
        if len(points) < 3:
            return ""

        commands = [f"M {self._fmt(points[0][0])} {self._fmt(points[0][1])}"]

        for index, current in enumerate(points):
            next_point = points[(index + 1) % len(points)]
            previous = points[(index - 1) % len(points)]
            next_next_point = points[(index + 2) % len(points)]

            if corner_mask[index] or corner_mask[(index + 1) % len(points)]:
                commands.append(f"L {self._fmt(next_point[0])} {self._fmt(next_point[1])}")
            else:
                control_1 = current + ((next_point - previous) * resolved.curve_tension / 6.0)
                control_2 = next_point - ((next_next_point - current) * resolved.curve_tension / 6.0)
                commands.append(
                    f"C {self._fmt(control_1[0])} {self._fmt(control_1[1])} "
                    f"{self._fmt(control_2[0])} {self._fmt(control_2[1])} "
                    f"{self._fmt(next_point[0])} {self._fmt(next_point[1])}"
                )

        commands.append("Z")
        return " ".join(commands)

    def _corner_angle(self, points: np.ndarray, index: int) -> float:
        previous = points[(index - 1) % len(points)]
        current = points[index]
        next_point = points[(index + 1) % len(points)]

        vector_a = previous - current
        vector_b = next_point - current

        norm_a = np.linalg.norm(vector_a)
        norm_b = np.linalg.norm(vector_b)
        if norm_a == 0 or norm_b == 0:
            return 180.0

        cosine = float(np.dot(vector_a, vector_b) / (norm_a * norm_b))
        cosine = max(-1.0, min(1.0, cosine))
        return float(np.degrees(np.arccos(cosine)))

    def _sorted_root_indices(self, contours: list[np.ndarray], hierarchy: np.ndarray) -> list[int]:
        root_indices = [index for index in range(len(contours)) if int(hierarchy[index][3]) == -1]
        return sorted(root_indices, key=lambda index: self._contour_sort_key(contours[index]))

    def _sorted_child_indices(self, contours: list[np.ndarray], hierarchy: np.ndarray, parent_index: int) -> list[int]:
        child_indices: list[int] = []
        child_index = int(hierarchy[parent_index][2])
        while child_index != -1:
            child_indices.append(child_index)
            child_index = int(hierarchy[child_index][0])
        return sorted(child_indices, key=lambda index: self._contour_sort_key(contours[index]))

    def _contour_sort_key(self, contour: np.ndarray) -> tuple[int, int, float, float]:
        x, y, width, height = cv2.boundingRect(contour)
        area = abs(cv2.contourArea(contour))
        return (y, x, -area, -(width * height))

    def _build_svg_document(self, result: TraceVectorResult, settings: TraceSettings) -> str:
        fill = "black" if settings.fill_only_output else "none"
        stroke = "black" if settings.stroke_output else "none"
        stroke_width = settings.stroke_width if settings.stroke_output else 0

        path_nodes = "\n".join(
            (
                f'  <path d="{path_data}" fill="{fill}" '
                f'stroke="{stroke}" stroke-width="{self._fmt(stroke_width)}" fill-rule="evenodd" />'
            )
            for path_data in result.paths
        )

        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{result.width}" height="{result.height}" '
            f'viewBox="0 0 {result.width} {result.height}">\n'
            f"{path_nodes}\n"
            "</svg>\n"
        )

    def _fmt(self, value: float) -> str:
        return f"{value:.3f}".rstrip("0").rstrip(".")


class PotraceTracingEngine(TracingEngine):
    """Tracing backend that delegates mask vectorization to the Potrace CLI."""

    def __init__(
        self,
        preprocessor: ImagePreprocessor | None = None,
        svg_exporter: SvgExporter | None = None,
        executable_path: Path | None = None,
        command_runner: Callable[..., subprocess.CompletedProcess[bytes]] | None = None,
    ) -> None:
        self.preprocessor = preprocessor or ImagePreprocessor()
        self.svg_exporter = svg_exporter or SvgExporter()
        self.executable_path = executable_path or optional_potrace_path()
        self.command_runner = command_runner or subprocess.run

    def trace(self, image_path: Path, settings: TraceSettings) -> str:
        preprocessed = self.preprocessor.preprocess(image_path, settings)
        return self.trace_mask(
            mask=preprocessed.binary_mask,
            width=preprocessed.width,
            height=preprocessed.height,
            settings=settings,
        )

    def trace_mask(self, mask: np.ndarray, width: int, height: int, settings: TraceSettings) -> str:
        if mask.ndim != 2:
            raise ValueError("Binary mask must be a single-channel array.")
        if self.executable_path is None:
            raise RuntimeError(
                "Potrace executable was not found. Install potrace.exe or bundle it under tracer/assets/bin/."
            )

        pbm_bytes = self._mask_to_pbm(mask)
        completed = self.command_runner(
            self._build_command(settings),
            input=pbm_bytes,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(stderr or "Potrace failed to generate SVG output.")

        svg_text = completed.stdout.decode("utf-8", errors="replace")
        return self._normalize_svg(svg_text, width, height, settings)

    def trace_to_file(self, image_path: Path, output_path: Path, settings: TraceSettings) -> Path:
        svg_text = self.trace(image_path, settings)
        self.svg_exporter.write_svg_text(output_path, svg_text)
        return output_path

    def is_available(self) -> bool:
        return self.executable_path is not None

    @property
    def backend_name(self) -> str:
        return "Potrace"

    def _build_command(self, settings: TraceSettings) -> list[str]:
        if self.executable_path is None:
            raise RuntimeError("Potrace executable is not configured.")
        resolved = settings.resolve()
        command = [
            str(self.executable_path),
            "--svg",
            "--output",
            "-",
            "--turnpolicy",
            "minority",
            "--turdsize",
            str(max(1, resolved.min_artifact_area)),
            "--alphamax",
            f"{self._alphamax(settings):.3f}",
            "--opttolerance",
            f"{self._opttolerance(settings):.3f}",
            "--unit",
            "10",
            "--group",
        ]
        if settings.path_simplification_tolerance <= 0.7:
            command.append("--longcurve")
        return command

    def _mask_to_pbm(self, mask: np.ndarray) -> bytes:
        binary = (mask > 0).astype(np.uint8)
        packed = np.packbits(binary, axis=1, bitorder="big")
        header = f"P4\n{mask.shape[1]} {mask.shape[0]}\n".encode("ascii")
        return header + packed.tobytes()

    def _normalize_svg(self, svg_text: str, width: int, height: int, settings: TraceSettings) -> str:
        root = self.svg_exporter.validate_svg_text(svg_text)
        root.set("width", str(width))
        root.set("height", str(height))
        root.set("viewBox", f"0 0 {width} {height}")
        normalized_text = ET.tostring(root, encoding="unicode")
        return self.svg_exporter.build_document(normalized_text, settings)

    def _alphamax(self, settings: TraceSettings) -> float:
        return min(1.333, max(0.0, 0.15 + (settings.smoothing_strength / 100.0) * 1.05))

    def _opttolerance(self, settings: TraceSettings) -> float:
        return min(1.0, max(0.05, settings.path_simplification_tolerance * 0.2))


def build_default_tracing_engine() -> TracingEngine:
    return build_monochrome_tracing_engine()


def build_monochrome_tracing_engine() -> TracingEngine:
    potrace_engine = PotraceTracingEngine()
    if potrace_engine.is_available():
        return potrace_engine
    return ContourTracingEngine()


def build_color_tracing_engine() -> TracingEngine:
    from tracer.core.vtracer_engine import VTracerTracingEngine

    return VTracerTracingEngine()


def resolve_trace_mode(settings: TraceSettings, image_path: Path | None = None) -> TraceMode:
    if settings.trace_mode in {"monochrome", "color"}:
        return settings.trace_mode
    if image_path is None:
        return "monochrome"
    return _detect_trace_mode(image_path)


def build_tracing_engine(settings: TraceSettings, image_path: Path | None = None) -> TracingEngine:
    mode = resolve_trace_mode(settings, image_path)
    if mode == "color":
        return build_color_tracing_engine()
    return build_monochrome_tracing_engine()


def describe_backend(settings: TraceSettings, image_path: Path | None = None) -> str:
    mode = resolve_trace_mode(settings, image_path)
    if mode == "color":
        try:
            return build_color_tracing_engine().backend_name
        except Exception:  # noqa: BLE001
            return "VTracer (unavailable)"
    return build_monochrome_tracing_engine().backend_name


def _detect_trace_mode(image_path: Path) -> TraceMode:
    """
    Route simple black/white artwork to Potrace and richer color artwork to VTracer.

    The heuristic intentionally favors monochrome only when the source is close
    to grayscale and has very low tonal variation.
    """
    with Image.open(image_path) as image:
        rgba = image.convert("RGBA")
        rgba.thumbnail((96, 96), Image.Resampling.BILINEAR)
        pixels = np.array(rgba, dtype=np.uint8)

    alpha = pixels[:, :, 3]
    opaque_pixels = pixels[alpha > 12][:, :3]
    if opaque_pixels.size == 0:
        return "monochrome"

    red = opaque_pixels[:, 0].astype(np.int16)
    green = opaque_pixels[:, 1].astype(np.int16)
    blue = opaque_pixels[:, 2].astype(np.int16)
    channel_spread = np.maximum(np.abs(red - green), np.maximum(np.abs(green - blue), np.abs(red - blue)))
    is_near_grayscale = bool(np.percentile(channel_spread, 95) <= 8)

    luminance = ((red * 77) + (green * 150) + (blue * 29)) // 256
    quantized_luminance = (luminance // 12).astype(np.uint8)
    unique_tones = np.unique(quantized_luminance)

    if is_near_grayscale and len(unique_tones) <= 24:
        return "monochrome"
    return "color"


def example_trace_png_to_svg(input_path: str | Path, output_path: str | Path) -> Path:
    """
    Example usage for tracing a single PNG or JPG into SVG.

    This function is intended for scripts, manual smoke tests, and future CLI
    integration.
    """
    settings = TraceSettings(
        trace_mode="monochrome",
        quality_preset="high",
        threshold=128,
        invert_colors=False,
        min_artifact_area=12,
        smoothing_strength=55,
        path_simplification_tolerance=1.2,
        resize_before_trace=False,
        ignore_transparent_pixels=True,
        merge_nearby_shapes=False,
        fill_only_output=True,
        stroke_output=False,
    )
    engine = build_tracing_engine(settings, Path(input_path))
    return engine.trace_to_file(Path(input_path), Path(output_path), settings)
