from __future__ import annotations

from io import BytesIO
import multiprocessing as mp
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from tracer.core.contour_extractor import ContourExtractor
from tracer.core.svg_exporter import SvgExporter
from tracer.core.tracing_engine import ContourTracingEngine, TracingEngine
from tracer.models.trace_settings import QualityPreset, TraceSettings

try:
    import vtracer
except ImportError as exc:  # pragma: no cover - exercised via availability checks
    vtracer = None
    VTRACER_IMPORT_ERROR = exc
else:  # pragma: no cover - trivial branch
    VTRACER_IMPORT_ERROR = None


def _vtracer_subprocess_entry(
    image_bytes: bytes,
    settings_payload: dict,
    colormode: str,
    result_queue: mp.queues.Queue,
) -> None:
    try:
        if vtracer is None:
            raise RuntimeError(
                "VTracer is not installed. Install it with `pip install vtracer` to enable colorful SVG tracing."
            )

        settings = TraceSettings.from_dict(settings_payload)
        with Image.open(BytesIO(image_bytes)) as image:
            prepared = image.convert("RGBA")
        pixels = list(prepared.getdata())

        if colormode == "color":
            options = _resolved_vtracer_options_static(settings)
        else:
            options = {
                "filter_speckle": max(0, settings.min_artifact_area),
                "corner_threshold": _color_corner_threshold_static(settings),
                "length_threshold": _color_length_threshold_static(settings),
                "max_iterations": _color_max_iterations_static(settings),
                "splice_threshold": _color_splice_threshold_static(settings),
                "path_precision": _color_path_precision_static(settings),
            }

        svg_text = vtracer.convert_pixels_to_svg(
            pixels,
            prepared.size,
            colormode=colormode,
            hierarchical="stacked",
            mode="spline",
            **options,
        )
        result_queue.put({"svg_text": svg_text})
    except Exception as exc:  # noqa: BLE001
        result_queue.put({"error": str(exc)})


class VTracerTracingEngine(TracingEngine):
    """Color-capable tracing backend powered by the `vtracer` Python bindings."""

    def __init__(self, svg_exporter: SvgExporter | None = None) -> None:
        self.svg_exporter = svg_exporter or SvgExporter()
        self.contour_engine = ContourTracingEngine(svg_exporter=self.svg_exporter)
        self.contour_extractor = ContourExtractor()

    @property
    def backend_name(self) -> str:
        return "VTracer"

    def is_available(self) -> bool:
        return vtracer is not None

    def trace(self, image_path: Path, settings: TraceSettings) -> str:
        prepared = self.load_prepared_image(image_path, settings)
        try:
            svg_text = self._trace_image_in_child_process(prepared, settings, colormode="color")
        except RuntimeError:
            svg_text = self._trace_image_with_python_fallback(prepared, settings)
        return self.svg_exporter.build_document(svg_text, settings)

    def trace_mask(self, mask: np.ndarray, width: int, height: int, settings: TraceSettings) -> str:
        if mask.ndim != 2:
            raise ValueError("Binary mask must be a single-channel array.")

        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        rgba[:, :, :3] = 255
        rgba[mask > 0, :3] = 0
        rgba[:, :, 3] = np.where(mask > 0, 255, 0).astype(np.uint8)
        image = Image.fromarray(rgba, mode="RGBA")
        try:
            svg_text = self._trace_image_in_child_process(image, settings, colormode="binary")
        except RuntimeError:
            svg_text = self._trace_image_with_python_fallback(image, settings)
        return self.svg_exporter.build_document(svg_text, settings)

    def trace_to_file(self, image_path: Path, output_path: Path, settings: TraceSettings) -> Path:
        svg_text = self.trace(image_path, settings)
        self.svg_exporter.write_svg_text(output_path, svg_text)
        return output_path

    def build_preview_png(self, image_path: Path, settings: TraceSettings) -> bytes:
        prepared = self.load_prepared_image(image_path, settings)
        colors = self._preview_palette_size(settings)
        alpha = prepared.getchannel("A")
        quantized = prepared.convert("RGB").quantize(colors=colors, method=Image.Quantize.FASTOCTREE).convert("RGBA")
        quantized.putalpha(alpha)

        buffer = BytesIO()
        quantized.save(buffer, format="PNG")
        return buffer.getvalue()

    def load_prepared_image(self, image_path: Path, settings: TraceSettings) -> Image.Image:
        with Image.open(image_path) as image:
            rgba = image.convert("RGBA")

        rgba = self._resize_if_needed(rgba, settings)
        if settings.ignore_transparent_pixels:
            rgba = self._sanitize_alpha(rgba)
        return rgba

    def _ensure_available(self) -> None:
        if vtracer is None:
            raise RuntimeError(
                "VTracer is not installed. Install it with `pip install vtracer` to enable colorful SVG tracing."
            ) from VTRACER_IMPORT_ERROR

    def _trace_image_in_child_process(self, image: Image.Image, settings: TraceSettings, colormode: str) -> str:
        self._ensure_available()
        image_bytes = self._encode_image_png(image)
        ctx = mp.get_context("spawn")
        result_queue: mp.Queue = ctx.Queue(maxsize=1)
        process = ctx.Process(
            target=_vtracer_subprocess_entry,
            args=(image_bytes, settings.to_dict(), colormode, result_queue),
        )
        process.start()
        process.join()

        result: dict[str, str] | None = None
        if not result_queue.empty():
            result = result_queue.get()

        if process.exitcode != 0:
            raise RuntimeError(
                "VTracer crashed while tracing this image. Try Potrace/Monochrome mode or lower the tracing complexity."
            )
        if result is None:
            raise RuntimeError("VTracer did not return any SVG output.")
        if result.get("error"):
            raise RuntimeError(result["error"])
        return result["svg_text"]

    def _trace_image_with_python_fallback(self, image: Image.Image, settings: TraceSettings) -> str:
        prepared_image = self._prepare_fallback_image(image, settings)
        rgba = np.array(prepared_image.convert("RGBA"), dtype=np.uint8)
        height, width = rgba.shape[:2]
        alpha = rgba[:, :, 3]
        opaque_mask = alpha > 12
        if not np.any(opaque_mask):
            return (
                '<svg xmlns="http://www.w3.org/2000/svg" '
                f'width="{width}" height="{height}" viewBox="0 0 {width} {height}"></svg>'
            )

        palette_image = prepared_image.convert("RGB").quantize(
            colors=self._fallback_palette_size(settings),
            method=Image.Quantize.FASTOCTREE,
        )
        indexed = np.array(palette_image, dtype=np.uint8)
        palette = np.array(palette_image.getpalette()[: 256 * 3], dtype=np.uint8).reshape(-1, 3)
        total_opaque_area = float(np.count_nonzero(opaque_mask))

        color_regions: list[tuple[str, list[str], float]] = []
        skip_background_index = self._background_palette_index(indexed, palette, opaque_mask)
        resolved = settings.resolve()

        for palette_index in np.unique(indexed[opaque_mask]):
            palette_index_int = int(palette_index)
            if skip_background_index is not None and palette_index_int == skip_background_index:
                continue

            mask = np.where((indexed == palette_index_int) & opaque_mask, 255, 0).astype(np.uint8)
            mask = self._clean_color_mask(mask, settings, resolved.contour_smoothing)
            area = float(np.count_nonzero(mask))
            if area == 0:
                continue

            rgb = palette[palette_index_int]
            if self._should_skip_region(rgb, area, total_opaque_area, settings):
                continue

            contour_data = self.contour_extractor.extract(mask)
            vector_result = self.contour_engine._build_vector_result(  # noqa: SLF001
                contour_data=contour_data,
                width=width,
                height=height,
                resolved=resolved,
            )
            if not vector_result.paths:
                continue

            fill = f"#{int(rgb[0]):02x}{int(rgb[1]):02x}{int(rgb[2]):02x}"
            color_regions.append((fill, vector_result.paths, area))

        color_regions.sort(key=lambda item: item[2], reverse=True)
        path_nodes = []
        for fill, paths, _area in color_regions:
            for path_data in paths:
                path_nodes.append(
                    f'  <path d="{path_data}" fill="{fill}" stroke="none" fill-rule="evenodd" />'
                )

        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
            + "\n".join(path_nodes)
            + ("\n" if path_nodes else "")
            + "</svg>\n"
        )

    def _encode_image_png(self, image: Image.Image) -> bytes:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _prepare_fallback_image(self, image: Image.Image, settings: TraceSettings) -> Image.Image:
        rgba = np.array(image.convert("RGBA"), dtype=np.uint8)
        alpha = rgba[:, :, 3]
        rgb = rgba[:, :, :3]

        # Mean-shift style smoothing is not available in Pillow. A bilateral
        # filter flattens near-identical colors while preserving illustration edges.
        if settings.smoothing_strength >= 20:
            diameter = 7 if settings.smoothing_strength < 60 else 9
            sigma_color = 18 + int(settings.smoothing_strength * 0.35)
            sigma_space = 10 + int(settings.smoothing_strength * 0.18)
            rgb = cv2.bilateralFilter(rgb, diameter, sigma_color, sigma_space)

        if settings.smoothing_strength >= 45:
            rgb = cv2.medianBlur(rgb, 3)

        rgba[:, :, :3] = rgb
        rgba[:, :, 3] = alpha
        return Image.fromarray(rgba, mode="RGBA")

    def _clean_color_mask(self, mask: np.ndarray, settings: TraceSettings, contour_smoothing: int) -> np.ndarray:
        min_region_area = max(settings.min_artifact_area, settings.color_filter_speckle)
        if min_region_area > 0:
            count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
            cleaned = np.zeros_like(mask)
            for label in range(1, count):
                area = stats[label, cv2.CC_STAT_AREA]
                if area >= min_region_area:
                    cleaned[labels == label] = 255
            mask = cleaned

        if contour_smoothing > 12:
            kernel_size = 3 if contour_smoothing < 70 else 5
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            if contour_smoothing >= 30:
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        if contour_smoothing >= 55:
            mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=0.8, sigmaY=0.8)
            _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
        return mask

    def _fallback_palette_size(self, settings: TraceSettings) -> int:
        base = self._color_precision(settings) + 1
        if settings.quality_preset == "low":
            base -= 1
        elif settings.quality_preset == "high":
            base += 1
        if settings.color_layer_difference >= 18:
            base -= 1
        elif settings.color_layer_difference <= 10:
            base += 1
        return max(4, min(12, base))

    def _should_skip_region(
        self,
        rgb: np.ndarray,
        area: float,
        total_opaque_area: float,
        settings: TraceSettings,
    ) -> bool:
        luminance = float((rgb[0] * 0.2126) + (rgb[1] * 0.7152) + (rgb[2] * 0.0722))
        saturation = int(max(rgb) - min(rgb))

        tiny_fraction = area / max(total_opaque_area, 1.0)
        if area <= max(2.0, float(settings.color_filter_speckle)) and tiny_fraction < 0.0025:
            return True

        # Drop anti-aliased white/gray slivers that cause scratch-like over-tracing.
        if luminance >= 242 and saturation <= 24 and tiny_fraction < 0.02:
            return True
        if luminance >= 228 and saturation <= 16 and tiny_fraction < 0.008:
            return True

        return False

    def _background_palette_index(
        self,
        indexed: np.ndarray,
        palette: np.ndarray,
        opaque_mask: np.ndarray,
    ) -> int | None:
        corners = [
            int(indexed[0, 0]),
            int(indexed[0, -1]),
            int(indexed[-1, 0]),
            int(indexed[-1, -1]),
        ]
        dominant_corner_index = max(set(corners), key=corners.count)
        if corners.count(dominant_corner_index) < 3:
            return None

        rgb = palette[dominant_corner_index]
        if int(rgb[0]) < 235 or int(rgb[1]) < 235 or int(rgb[2]) < 235:
            return None

        coverage = float(np.count_nonzero((indexed == dominant_corner_index) & opaque_mask)) / float(np.count_nonzero(opaque_mask))
        if coverage < 0.25:
            return None
        return dominant_corner_index

    def _resize_if_needed(self, image: Image.Image, settings: TraceSettings) -> Image.Image:
        if not settings.resize_before_trace:
            return image

        width, height = image.size
        longest = max(width, height)
        if longest <= settings.resize_max_dimension:
            return image

        scale = settings.resize_max_dimension / float(longest)
        new_size = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
        return image.resize(new_size, Image.Resampling.LANCZOS)

    def _sanitize_alpha(self, image: Image.Image) -> Image.Image:
        rgba = np.array(image)
        alpha = rgba[:, :, 3]
        transparent = alpha <= 12
        rgba[transparent, :3] = 255
        rgba[transparent, 3] = 0
        return Image.fromarray(rgba, mode="RGBA")

    def _resolved_vtracer_options(self, settings: TraceSettings) -> dict[str, int | float]:
        return _resolved_vtracer_options_static(settings)

    def _quality_delta(self, quality_preset: QualityPreset) -> tuple[int, int, int, int, int]:
        if quality_preset == "low":
            return (-1, 6, 2, -2, -10)
        if quality_preset == "high":
            return (1, -4, -1, 2, 8)
        return (0, 0, 0, 0, 0)

    def _color_precision(self, settings: TraceSettings) -> int:
        precision_delta, _, _, _, _ = self._quality_delta(settings.quality_preset)
        precision = settings.color_precision + precision_delta
        return max(2, min(12, precision))

    def _color_layer_difference(self, settings: TraceSettings) -> int:
        _, layer_delta, _, _, _ = self._quality_delta(settings.quality_preset)
        base = settings.color_layer_difference + layer_delta
        return max(4, min(64, base))

    def _color_filter_speckle(self, settings: TraceSettings) -> int:
        _, _, speckle_delta, _, _ = self._quality_delta(settings.quality_preset)
        base = max(settings.color_filter_speckle, settings.min_artifact_area) + speckle_delta
        return max(0, base)

    def _color_corner_threshold(self, settings: TraceSettings) -> int:
        return _color_corner_threshold_static(settings)

    def _color_length_threshold(self, settings: TraceSettings) -> float:
        return _color_length_threshold_static(settings)

    def _color_max_iterations(self, settings: TraceSettings) -> int:
        return _color_max_iterations_static(settings)

    def _color_splice_threshold(self, settings: TraceSettings) -> int:
        return _color_splice_threshold_static(settings)

    def _color_path_precision(self, settings: TraceSettings) -> int:
        return _color_path_precision_static(settings)

    def _preview_palette_size(self, settings: TraceSettings) -> int:
        return max(8, min(48, self._color_precision(settings) * 4))


def _resolved_vtracer_options_static(settings: TraceSettings) -> dict[str, int | float]:
    engine = VTracerTracingEngine()
    return {
        "filter_speckle": engine._color_filter_speckle(settings),
        "color_precision": engine._color_precision(settings),
        "layer_difference": engine._color_layer_difference(settings),
        "corner_threshold": _color_corner_threshold_static(settings),
        "length_threshold": _color_length_threshold_static(settings),
        "max_iterations": _color_max_iterations_static(settings),
        "splice_threshold": _color_splice_threshold_static(settings),
        "path_precision": _color_path_precision_static(settings),
    }


def _color_corner_threshold_static(settings: TraceSettings) -> int:
    base = settings.color_corner_threshold + round((settings.smoothing_strength - 50) * 0.35)
    return max(15, min(170, base))


def _color_length_threshold_static(settings: TraceSettings) -> float:
    value = settings.color_length_threshold + ((settings.path_simplification_tolerance - 1.0) * 1.4)
    return max(3.5, min(10.0, value))


def _color_max_iterations_static(settings: TraceSettings) -> int:
    iteration_delta = 0
    if settings.quality_preset == "low":
        iteration_delta = -2
    elif settings.quality_preset == "high":
        iteration_delta = 2
    base = settings.color_max_iterations + iteration_delta + round((settings.smoothing_strength - 50) / 20.0)
    return max(1, min(32, base))


def _color_splice_threshold_static(settings: TraceSettings) -> int:
    splice_delta = 0
    if settings.quality_preset == "low":
        splice_delta = -10
    elif settings.quality_preset == "high":
        splice_delta = 8
    base = settings.color_splice_threshold + splice_delta + round((settings.smoothing_strength - 50) * 0.25)
    return max(5, min(170, base))


def _color_path_precision_static(settings: TraceSettings) -> int:
    value = settings.color_path_precision + round((1.0 - settings.path_simplification_tolerance) * 2.0)
    return max(1, min(12, value))
