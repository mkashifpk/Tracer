from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

QualityPreset = Literal["low", "balanced", "high"]
TraceMode = Literal["auto", "monochrome", "color"]


@dataclass(frozen=True, slots=True)
class TracePresetProfile:
    threshold: int
    blur_amount: float
    min_artifact_area: int
    contour_smoothing: int
    simplification_tolerance: float
    alpha_cutoff: int


@dataclass(frozen=True, slots=True)
class ResolvedTraceSettings:
    quality_preset: QualityPreset
    threshold: int
    blur_amount: float
    min_artifact_area: int
    contour_smoothing: int
    simplification_tolerance: float
    alpha_cutoff: int
    corner_angle_threshold: float
    curve_tension: float
    smoothing_iterations: int


TRACE_PRESET_PROFILES: dict[QualityPreset, TracePresetProfile] = {
    "low": TracePresetProfile(
        threshold=124,
        blur_amount=0.0,
        min_artifact_area=4,
        contour_smoothing=8,
        simplification_tolerance=1.20,
        alpha_cutoff=24,
    ),
    "balanced": TracePresetProfile(
        threshold=128,
        blur_amount=0.0,
        min_artifact_area=2,
        contour_smoothing=12,
        simplification_tolerance=1.00,
        alpha_cutoff=16,
    ),
    "high": TracePresetProfile(
        threshold=132,
        blur_amount=0.2,
        min_artifact_area=1,
        contour_smoothing=20,
        simplification_tolerance=0.80,
        alpha_cutoff=10,
    ),
}


def _normalized_quality_preset(value: object) -> QualityPreset:
    if value in {"low", "balanced", "high"}:
        return value
    return "balanced"


def _normalized_trace_mode(value: object) -> TraceMode:
    if value in {"auto", "monochrome", "color"}:
        return value
    return "auto"

@dataclass(slots=True)
class TraceSettings:
    trace_mode: TraceMode = "auto"
    quality_preset: QualityPreset = "balanced"
    threshold: int = 128
    invert_colors: bool = False
    min_artifact_area: int = 2
    smoothing_strength: int = 52
    path_simplification_tolerance: float = 1.0
    resize_before_trace: bool = False
    resize_max_dimension: int = 2048
    ignore_transparent_pixels: bool = True
    merge_nearby_shapes: bool = False
    fill_only_output: bool = True
    stroke_output: bool = False
    stroke_width: float = 1.0
    color_precision: int = 6
    color_layer_difference: int = 16
    color_filter_speckle: int = 4
    color_corner_threshold: int = 60
    color_length_threshold: float = 4.0
    color_max_iterations: int = 10
    color_splice_threshold: int = 45
    color_path_precision: int = 8

    def to_dict(self) -> dict:
        return asdict(self)

    def copy(self) -> "TraceSettings":
        return TraceSettings.from_dict(self.to_dict())

    def resolve(self) -> ResolvedTraceSettings:
        preset = self.quality_preset if self.quality_preset in TRACE_PRESET_PROFILES else "balanced"
        profile = TRACE_PRESET_PROFILES[preset]

        threshold = self._clamp_int(self.threshold, 0, 255)
        blur_amount = max(0.0, profile.blur_amount + ((self.smoothing_strength - 52) * 0.0025))

        artifact_scale = max(self.min_artifact_area, 0) / max(1.0, float(profile.min_artifact_area))
        min_artifact_area = max(0, int(round(profile.min_artifact_area * artifact_scale)))

        contour_smoothing = self._clamp_int(
            profile.contour_smoothing + round((self.smoothing_strength - 52) * 0.25),
            0,
            100,
        )
        simplification_tolerance = max(
            0.15,
            profile.simplification_tolerance * max(self.path_simplification_tolerance, 0.15),
        )

        if contour_smoothing < 25:
            smoothing_iterations = 0
        elif contour_smoothing < 55:
            smoothing_iterations = 1
        elif contour_smoothing < 80:
            smoothing_iterations = 2
        else:
            smoothing_iterations = 3

        corner_angle_threshold = 100.0 + (contour_smoothing * 0.32)
        curve_tension = 0.55 + (contour_smoothing / 100.0) * 0.55

        return ResolvedTraceSettings(
            quality_preset=preset,
            threshold=threshold,
            blur_amount=blur_amount,
            min_artifact_area=min_artifact_area,
            contour_smoothing=contour_smoothing,
            simplification_tolerance=simplification_tolerance,
            alpha_cutoff=profile.alpha_cutoff,
            corner_angle_threshold=corner_angle_threshold,
            curve_tension=curve_tension,
            smoothing_iterations=smoothing_iterations,
        )

    @classmethod
    def from_dict(cls, payload: dict) -> "TraceSettings":
        return cls(
            trace_mode=_normalized_trace_mode(payload.get("trace_mode", "auto")),
            quality_preset=_normalized_quality_preset(payload.get("quality_preset", "balanced")),
            threshold=cls._clamp_int(int(payload.get("threshold", 128)), 0, 255),
            invert_colors=bool(payload.get("invert_colors", False)),
            min_artifact_area=max(0, int(payload.get("min_artifact_area", 2))),
            smoothing_strength=cls._clamp_int(int(payload.get("smoothing_strength", 52)), 0, 100),
            path_simplification_tolerance=max(0.15, float(payload.get("path_simplification_tolerance", 1.0))),
            resize_before_trace=bool(payload.get("resize_before_trace", False)),
            resize_max_dimension=max(64, int(payload.get("resize_max_dimension", 2048))),
            ignore_transparent_pixels=bool(payload.get("ignore_transparent_pixels", True)),
            merge_nearby_shapes=bool(payload.get("merge_nearby_shapes", False)),
            fill_only_output=bool(payload.get("fill_only_output", True)),
            stroke_output=bool(payload.get("stroke_output", False)),
            stroke_width=max(0.1, float(payload.get("stroke_width", 1.0))),
            color_precision=cls._clamp_int(int(payload.get("color_precision", 6)), 1, 12),
            color_layer_difference=cls._clamp_int(int(payload.get("color_layer_difference", 16)), 1, 64),
            color_filter_speckle=max(0, int(payload.get("color_filter_speckle", 4))),
            color_corner_threshold=cls._clamp_int(int(payload.get("color_corner_threshold", 60)), 1, 180),
            color_length_threshold=max(1.0, float(payload.get("color_length_threshold", 4.0))),
            color_max_iterations=cls._clamp_int(int(payload.get("color_max_iterations", 10)), 1, 64),
            color_splice_threshold=cls._clamp_int(int(payload.get("color_splice_threshold", 45)), 1, 180),
            color_path_precision=cls._clamp_int(int(payload.get("color_path_precision", 8)), 1, 12),
        )

    @staticmethod
    def _clamp_int(value: int, minimum: int, maximum: int) -> int:
        return max(minimum, min(maximum, value))
