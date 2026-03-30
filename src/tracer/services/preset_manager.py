from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from tracer.models.trace_preset import PRESET_SCHEMA_VERSION, TracePreset
from tracer.models.trace_settings import TraceSettings
from tracer.utils.paths import preset_file_path

PRESET_FILE_VERSION = 1


class PresetManager:
    def __init__(self, preset_path: Path | None = None) -> None:
        self.preset_path = preset_path or self._default_preset_path()
        self._custom_presets: dict[str, TracePreset] = {}

    def load_custom_presets(self) -> list[TracePreset]:
        self._custom_presets = {}
        if not self.preset_path.exists():
            return []

        try:
            payload = json.loads(self.preset_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        if not isinstance(payload, dict):
            return []
        version = payload.get("version", 0)
        if not isinstance(version, int) or version < 1:
            return []

        entries = payload.get("presets", [])
        if not isinstance(entries, list):
            return []

        for entry in entries:
            preset = self._parse_stored_preset(entry)
            if preset is not None:
                self._custom_presets[preset.preset_id] = preset
        return self.custom_presets()

    def save_custom_preset(
        self,
        name: str,
        settings: TraceSettings,
        description: str = "",
    ) -> TracePreset:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Preset name is required.")

        preset_id = self._make_unique_custom_id(clean_name)
        preset = TracePreset(
            preset_id=preset_id,
            name=clean_name,
            description=description.strip(),
            settings=settings.copy(),
            is_builtin=False,
        )
        self._custom_presets[preset.preset_id] = preset
        self._persist_custom_presets()
        return preset

    def import_preset(self, source_path: Path) -> TracePreset:
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not read preset file: {exc}") from exc

        preset = self._parse_imported_preset(payload)
        if preset is None:
            raise ValueError("Preset JSON is invalid or incomplete.")

        preset = TracePreset(
            preset_id=self._make_unique_custom_id(preset.name),
            name=preset.name,
            description=preset.description,
            settings=preset.settings.copy(),
            is_builtin=False,
        )
        self._custom_presets[preset.preset_id] = preset
        self._persist_custom_presets()
        return preset

    def export_preset(self, preset_id: str, target_path: Path) -> None:
        preset = self.get_preset(preset_id)
        if preset is None:
            raise ValueError("Preset was not found.")
        if preset.is_builtin:
            raise ValueError("Built-in presets cannot be exported as custom presets.")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=target_path.parent,
            suffix=".tmp",
        ) as handle:
            handle.write(json.dumps(preset.to_export_dict(), indent=2))
            temp_path = Path(handle.name)
        temp_path.replace(target_path)

    def get_preset(self, preset_id: str | None) -> TracePreset | None:
        if not preset_id:
            return None
        for preset in self.builtin_presets():
            if preset.preset_id == preset_id:
                return preset
        preset = self._custom_presets.get(preset_id)
        return preset.copy() if preset is not None else None

    def all_presets(self) -> list[TracePreset]:
        return [*self.builtin_presets(), *self.custom_presets()]

    def custom_presets(self) -> list[TracePreset]:
        return [preset.copy() for preset in sorted(self._custom_presets.values(), key=lambda preset: preset.name.lower())]

    def match_preset_id(self, settings: TraceSettings) -> str | None:
        for preset in self.all_presets():
            if preset.settings == settings:
                return preset.preset_id
        return None

    def builtin_presets(self) -> list[TracePreset]:
        return [preset.copy() for preset in BUILTIN_TRACE_PRESETS]

    @staticmethod
    def _default_preset_path() -> Path:
        return preset_file_path()

    def _persist_custom_presets(self) -> None:
        self.preset_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": PRESET_FILE_VERSION,
            "presets": [
                {
                    "preset_id": preset.preset_id,
                    "name": preset.name,
                    "description": preset.description,
                    "settings": preset.settings.to_dict(),
                }
                for preset in self.custom_presets()
            ],
        }
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=self.preset_path.parent,
            suffix=".tmp",
        ) as handle:
            handle.write(json.dumps(payload, indent=2))
            temp_path = Path(handle.name)
        temp_path.replace(self.preset_path)

    def _make_unique_custom_id(self, name: str) -> str:
        base_slug = _slugify(name) or "preset"
        candidate = f"custom:{base_slug}"
        counter = 2
        while self.get_preset(candidate) is not None:
            candidate = f"custom:{base_slug}-{counter}"
            counter += 1
        return candidate

    def _parse_stored_preset(self, payload: object) -> TracePreset | None:
        if not isinstance(payload, dict):
            return None
        preset_id = str(payload.get("preset_id", "")).strip()
        name = str(payload.get("name", "")).strip()
        if not preset_id or not name:
            return None
        settings_payload = payload.get("settings")
        if not isinstance(settings_payload, dict):
            return None
        return TracePreset(
            preset_id=preset_id,
            name=name,
            description=str(payload.get("description", "")).strip(),
            settings=TraceSettings.from_dict(settings_payload),
            is_builtin=False,
        )

    def _parse_imported_preset(self, payload: object) -> TracePreset | None:
        if not isinstance(payload, dict):
            return None
        version = payload.get("version", 0)
        if not isinstance(version, int) or version < PRESET_SCHEMA_VERSION:
            return None
        name = str(payload.get("name", "")).strip()
        settings_payload = payload.get("settings")
        if not name or not isinstance(settings_payload, dict):
            return None
        return TracePreset(
            preset_id="",
            name=name,
            description=str(payload.get("description", "")).strip(),
            settings=TraceSettings.from_dict(settings_payload),
            is_builtin=False,
        )


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


BUILTIN_TRACE_PRESETS: list[TracePreset] = [
    TracePreset(
        preset_id="builtin:figma-tracer-default",
        name="Figma Tracer Default",
        description="Potrace-style monochrome tracing tuned to preserve interior texture and line detail with threshold 128, turd size 2, minority turn policy, alpha max about 0.7, and optimization tolerance about 0.2.",
        settings=TraceSettings(
            trace_mode="monochrome",
            quality_preset="balanced",
            threshold=128,
            invert_colors=False,
            min_artifact_area=2,
            smoothing_strength=52,
            path_simplification_tolerance=1.0,
            resize_before_trace=False,
            resize_max_dimension=2048,
            ignore_transparent_pixels=True,
            merge_nearby_shapes=False,
            fill_only_output=True,
            stroke_output=False,
            stroke_width=1.0,
        ),
        is_builtin=True,
    ),
    TracePreset(
        preset_id="builtin:color-illustration-trace",
        name="Color Illustration Trace",
        description="Tuned for flat colorful illustrations with stronger anti-alias cleanup, fewer accidental light-edge regions, and cleaner layered SVG output.",
        settings=TraceSettings(
            trace_mode="color",
            quality_preset="balanced",
            threshold=128,
            invert_colors=False,
            min_artifact_area=6,
            smoothing_strength=64,
            path_simplification_tolerance=0.92,
            resize_before_trace=False,
            resize_max_dimension=2048,
            ignore_transparent_pixels=True,
            merge_nearby_shapes=False,
            fill_only_output=True,
            stroke_output=False,
            stroke_width=1.0,
            color_precision=5,
            color_layer_difference=22,
            color_filter_speckle=6,
            color_corner_threshold=62,
            color_length_threshold=4.3,
            color_max_iterations=12,
            color_splice_threshold=48,
            color_path_precision=7,
        ),
        is_builtin=True,
    ),
    TracePreset(
        preset_id="builtin:clean-logo-trace",
        name="Clean Logo Trace",
        description="Crisp silhouette cleanup for logos, symbols, and bold icon work.",
        settings=TraceSettings(
            trace_mode="monochrome",
            quality_preset="high",
            threshold=146,
            invert_colors=False,
            min_artifact_area=8,
            smoothing_strength=72,
            path_simplification_tolerance=0.70,
            resize_before_trace=False,
            resize_max_dimension=2048,
            ignore_transparent_pixels=True,
            merge_nearby_shapes=False,
            fill_only_output=True,
            stroke_output=False,
            stroke_width=1.0,
        ),
        is_builtin=True,
    ),
    TracePreset(
        preset_id="builtin:organic-ink-shape",
        name="Organic Ink Shape",
        description="Smoothes hand-drawn fills while preserving broader organic bends and bulges.",
        settings=TraceSettings(
            trace_mode="monochrome",
            quality_preset="high",
            threshold=138,
            invert_colors=False,
            min_artifact_area=10,
            smoothing_strength=80,
            path_simplification_tolerance=0.82,
            resize_before_trace=False,
            resize_max_dimension=2048,
            ignore_transparent_pixels=True,
            merge_nearby_shapes=True,
            fill_only_output=True,
            stroke_output=False,
            stroke_width=1.0,
        ),
        is_builtin=True,
    ),
    TracePreset(
        preset_id="builtin:texture-silhouette",
        name="Texture Silhouette",
        description="Suppresses dust aggressively while keeping the main silhouette readable and compact.",
        settings=TraceSettings(
            trace_mode="monochrome",
            quality_preset="balanced",
            threshold=132,
            invert_colors=False,
            min_artifact_area=20,
            smoothing_strength=46,
            path_simplification_tolerance=1.08,
            resize_before_trace=False,
            resize_max_dimension=2048,
            ignore_transparent_pixels=True,
            merge_nearby_shapes=False,
            fill_only_output=True,
            stroke_output=False,
            stroke_width=1.0,
        ),
        is_builtin=True,
    ),
    TracePreset(
        preset_id="builtin:minimal-smooth-vector",
        name="Minimal Smooth Vector",
        description="Produces the fewest, smoothest paths for clean vector-ready output.",
        settings=TraceSettings(
            trace_mode="monochrome",
            quality_preset="high",
            threshold=150,
            invert_colors=False,
            min_artifact_area=16,
            smoothing_strength=88,
            path_simplification_tolerance=1.18,
            resize_before_trace=False,
            resize_max_dimension=2048,
            ignore_transparent_pixels=True,
            merge_nearby_shapes=True,
            fill_only_output=True,
            stroke_output=False,
            stroke_width=1.0,
        ),
        is_builtin=True,
    ),
    TracePreset(
        preset_id="builtin:fine-detail-preserve",
        name="Fine Detail Preserve",
        description="Keeps smaller interior cuts and tight contour changes where source quality is strong.",
        settings=TraceSettings(
            trace_mode="monochrome",
            quality_preset="high",
            threshold=140,
            invert_colors=False,
            min_artifact_area=4,
            smoothing_strength=62,
            path_simplification_tolerance=0.55,
            resize_before_trace=False,
            resize_max_dimension=2048,
            ignore_transparent_pixels=True,
            merge_nearby_shapes=False,
            fill_only_output=True,
            stroke_output=False,
            stroke_width=1.0,
        ),
        is_builtin=True,
    ),
]
