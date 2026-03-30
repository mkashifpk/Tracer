from pathlib import Path

from tracer.models.trace_settings import TraceSettings
from tracer.services.preset_manager import PresetManager


def test_builtin_presets_are_available() -> None:
    manager = PresetManager()

    names = [preset.name for preset in manager.builtin_presets()]

    assert "Figma Tracer Default" in names
    assert "Color Illustration Trace" in names
    assert "Clean Logo Trace" in names
    assert "Fine Detail Preserve" in names


def test_color_illustration_trace_preset_has_color_source_defaults() -> None:
    manager = PresetManager()

    preset = manager.get_preset("builtin:color-illustration-trace")

    assert preset is not None
    assert preset.name == "Color Illustration Trace"
    assert preset.settings.trace_mode == "color"
    assert preset.settings.min_artifact_area == 6
    assert preset.settings.smoothing_strength == 64
    assert preset.settings.path_simplification_tolerance == 0.92
    assert preset.settings.color_precision == 5


def test_figma_tracer_default_is_monochrome_tuned() -> None:
    manager = PresetManager()

    preset = manager.get_preset("builtin:figma-tracer-default")

    assert preset is not None
    assert preset.name == "Figma Tracer Default"
    assert preset.settings.trace_mode == "monochrome"
    assert preset.settings.threshold == 128


def test_custom_preset_round_trip(tmp_path: Path) -> None:
    manager = PresetManager(preset_path=tmp_path / "presets.json")

    created = manager.save_custom_preset(
        name="My Batch Default",
        description="Saved from tests",
        settings=TraceSettings(threshold=149, smoothing_strength=68),
    )

    reloaded = PresetManager(preset_path=tmp_path / "presets.json")
    presets = reloaded.load_custom_presets()

    assert len(presets) == 1
    assert presets[0].name == created.name
    assert presets[0].settings.threshold == 149


def test_import_and_export_custom_preset(tmp_path: Path) -> None:
    manager = PresetManager(preset_path=tmp_path / "presets.json")
    imported_path = tmp_path / "import.json"
    imported_path.write_text(
        """
{
  "version": 1,
  "name": "Imported Preset",
  "description": "From file",
  "settings": {
    "quality_preset": "high",
    "threshold": 141,
    "invert_colors": false,
    "min_artifact_area": 5,
    "smoothing_strength": 60,
    "path_simplification_tolerance": 0.75,
    "resize_before_trace": false,
    "resize_max_dimension": 2048,
    "ignore_transparent_pixels": true,
    "merge_nearby_shapes": false,
    "fill_only_output": true,
    "stroke_output": false,
    "stroke_width": 1.0
  }
}
""".strip(),
        encoding="utf-8",
    )

    imported = manager.import_preset(imported_path)
    export_path = tmp_path / "exported.json"
    manager.export_preset(imported.preset_id, export_path)

    exported_text = export_path.read_text(encoding="utf-8")

    assert imported.name == "Imported Preset"
    assert "\"name\": \"Imported Preset\"" in exported_text
    assert "\"threshold\": 141" in exported_text
