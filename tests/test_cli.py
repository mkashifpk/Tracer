from pathlib import Path

from tracer.cli import apply_cli_overrides, build_parser, resolve_preset, validate_cli_inputs
from tracer.models.trace_settings import TraceSettings
from tracer.services.preset_manager import PresetManager


def test_cli_parser_accepts_preset_and_paths() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "--input",
            "C:\\input",
            "--output",
            "C:\\output",
            "--preset",
            "Minimal Smooth Vector",
            "--trace-mode",
            "color",
            "--threshold",
            "140",
        ]
    )

    assert str(args.input) == "C:\\input"
    assert str(args.output) == "C:\\output"
    assert args.preset == "Minimal Smooth Vector"
    assert args.trace_mode == "color"
    assert args.threshold == 140


def test_resolve_preset_matches_name() -> None:
    manager = PresetManager()

    preset = resolve_preset(manager, "Minimal Smooth Vector")

    assert preset is not None
    assert preset.preset_id == "builtin:minimal-smooth-vector"


def test_apply_cli_overrides_updates_settings() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--input",
            "C:\\input",
            "--output",
            "C:\\output",
            "--threshold",
            "150",
            "--trace-mode",
            "color",
            "--invert",
            "--smoothing-strength",
            "80",
            "--simplification",
            "0.7",
            "--stroke-output",
            "--stroke-width",
            "2.5",
        ]
    )

    settings = apply_cli_overrides(TraceSettings(), args)

    assert settings.trace_mode == "color"
    assert settings.threshold == 150
    assert settings.invert_colors is True
    assert settings.smoothing_strength == 80
    assert settings.path_simplification_tolerance == 0.7
    assert settings.stroke_output is True
    assert settings.fill_only_output is False
    assert settings.stroke_width == 2.5


def test_validate_cli_inputs_rejects_conflicting_modes(tmp_path: Path) -> None:
    parser = build_parser()
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    args = parser.parse_args(
        [
            "--input",
            str(input_dir),
            "--output",
            str(tmp_path / "output"),
            "--overwrite",
            "--skip-existing",
        ]
    )

    error = validate_cli_inputs(Path(args.input), Path(args.output), args)

    assert error == "Use either --overwrite or --skip-existing, not both."


def test_validate_cli_inputs_rejects_invert_in_color_mode(tmp_path: Path) -> None:
    parser = build_parser()
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    args = parser.parse_args(
        [
            "--input",
            str(input_dir),
            "--output",
            str(tmp_path / "output"),
            "--trace-mode",
            "color",
            "--invert",
        ]
    )

    error = validate_cli_inputs(Path(args.input), Path(args.output), args)

    assert error == "--invert is only supported in monochrome tracing mode."
