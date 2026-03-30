from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from tracer.models.app_settings import ExistingOutputMode, ExportLogFormat
from tracer.models.batch_job import BatchProgress, BatchSummary
from tracer.models.trace_preset import TracePreset
from tracer.models.trace_settings import TraceSettings
from tracer.services.preset_manager import PresetManager

CLI_DESCRIPTION = "Process a folder of PNG/JPG images into SVG files without opening the desktop UI."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tracer",
        description=CLI_DESCRIPTION,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--gui", action="store_true", help="Open the desktop UI even when CLI flags are present.")
    parser.add_argument("--input", type=Path, help="Input folder containing PNG/JPG files.")
    parser.add_argument("--output", type=Path, help="Output folder for generated SVG files.")
    parser.add_argument(
        "--preset",
        type=str,
        help="Tracing preset name or preset id. Examples: 'Minimal Smooth Vector' or 'builtin:minimal-smooth-vector'.",
    )
    parser.add_argument(
        "--trace-mode",
        choices=["auto", "monochrome", "color"],
        help="Select the tracing backend route. Auto picks monochrome for near-binary art and color for colorful artwork.",
    )
    parser.add_argument("--threshold", type=int, help="Override threshold from 0 to 255.")
    parser.add_argument("--invert", action="store_true", help="Invert black and white tracing polarity.")
    parser.add_argument("--min-artifact-area", type=int, help="Remove blobs smaller than this pixel area.")
    parser.add_argument("--smoothing-strength", type=int, help="Contour smoothing strength from 0 to 100.")
    parser.add_argument("--simplification", type=float, help="Path simplification tolerance.")
    parser.add_argument("--resize-before-trace", action="store_true", help="Resize oversized images before tracing.")
    parser.add_argument("--resize-max-dimension", type=int, help="Maximum width or height when resize is enabled.")
    parser.add_argument(
        "--ignore-transparency",
        dest="ignore_transparency",
        action="store_true",
        help="Ignore transparent pixels when building the trace mask.",
    )
    parser.add_argument(
        "--keep-transparency",
        dest="ignore_transparency",
        action="store_false",
        help="Include transparent pixels in thresholding instead of masking them out.",
    )
    parser.set_defaults(ignore_transparency=None)
    parser.add_argument("--merge-nearby-shapes", action="store_true", help="Join nearby shapes during preprocessing.")
    parser.add_argument("--fill-only", dest="fill_only_output", action="store_true", help="Write fill-only SVG output.")
    parser.add_argument("--stroke-output", action="store_true", help="Also emit stroke attributes in SVG output.")
    parser.add_argument("--stroke-width", type=float, help="Stroke width used when --stroke-output is enabled.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing SVG files in the output folder.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip SVG files that already exist.")
    parser.add_argument(
        "--log-format",
        choices=["none", "txt", "csv"],
        default="none",
        help="Optional batch summary log format written into the output folder.",
    )
    parser.add_argument("--workers", type=int, help="Number of worker processes for batch tracing.")
    return parser


def should_run_cli(argv: Sequence[str]) -> bool:
    cli_flags = {"--gui", "--input", "--output", "--preset", "--help", "-h"}
    return any(argument in cli_flags or argument.startswith("--") for argument in argv[1:])


def run_cli(argv: Sequence[str] | None = None) -> int:
    from tracer.services.batch_processing_manager import BatchProcessingManager
    from tracer.services.file_scanner import FileScanner
    from tracer.utils.logger import configure_logging, get_logger

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.gui:
        return -1

    configure_logging()
    logger = get_logger(__name__)

    if args.input is None or args.output is None:
        parser.error("--input and --output are required in CLI mode.")

    input_folder = args.input.expanduser().resolve()
    output_folder = args.output.expanduser().resolve()

    validation_error = validate_cli_inputs(input_folder, output_folder, args)
    if validation_error is not None:
        print(f"Error: {validation_error}")
        return 1

    scanner = FileScanner()
    files = scanner.scan(input_folder)
    source_paths = [item.path for item in files if item.status == "Ready"]
    unsupported_count = sum(1 for item in files if item.status != "Ready")

    if not source_paths:
        print(f"No supported PNG/JPG files found in {input_folder}")
        return 1

    output_folder.mkdir(parents=True, exist_ok=True)

    preset_manager = PresetManager()
    preset_manager.load_custom_presets()
    preset = resolve_preset(preset_manager, args.preset)
    if args.preset and preset is None:
        print(f"Error: Preset not found: {args.preset}")
        return 1

    settings = apply_cli_overrides(base_settings=preset.settings if preset is not None else TraceSettings(), args=args)
    existing_output_mode: ExistingOutputMode = "overwrite" if args.overwrite else "skip"
    if args.skip_existing:
        existing_output_mode = "skip"

    manager = BatchProcessingManager()
    jobs = manager.create_jobs(source_paths=source_paths, output_folder=output_folder, existing_output_mode=existing_output_mode)

    print(f"Tracing {len(jobs)} file(s) from {input_folder} to {output_folder}")
    if preset is not None:
        print(f"Preset: {preset.name}")
    if unsupported_count:
        print(f"Skipped unsupported files during scan: {unsupported_count}")

    summary = manager.process_jobs(
        jobs=jobs,
        settings=settings,
        on_progress=_print_progress,
        max_workers=args.workers or 0,
    )
    try:
        log_path = manager.export_summary_log(summary, _normalize_log_format(args.log_format))
    except Exception as exc:  # noqa: BLE001
        summary.log_export_error = str(exc)
        log_path = None

    logger.info(
        "CLI batch completed | total=%s exported=%s skipped=%s failed=%s cancelled=%s",
        summary.total_jobs,
        summary.exported_jobs,
        summary.skipped_jobs,
        summary.failed_jobs,
        summary.cancelled_jobs,
    )
    print_summary(summary, log_path)

    if summary.failed_jobs > 0:
        return 2
    if summary.cancelled_jobs > 0:
        return 3
    return 0


def validate_cli_inputs(input_folder: Path, output_folder: Path, args: argparse.Namespace) -> str | None:
    if not input_folder.exists():
        return f"Input folder does not exist: {input_folder}"
    if not input_folder.is_dir():
        return f"Input path is not a folder: {input_folder}"
    if output_folder.exists() and not output_folder.is_dir():
        return f"Output path is not a folder: {output_folder}"
    if args.overwrite and args.skip_existing:
        return "Use either --overwrite or --skip-existing, not both."
    if args.threshold is not None and not 0 <= args.threshold <= 255:
        return "--threshold must be between 0 and 255."
    if args.trace_mode == "color" and args.invert:
        return "--invert is only supported in monochrome tracing mode."
    if args.smoothing_strength is not None and not 0 <= args.smoothing_strength <= 100:
        return "--smoothing-strength must be between 0 and 100."
    if args.min_artifact_area is not None and args.min_artifact_area < 0:
        return "--min-artifact-area must be 0 or greater."
    if args.simplification is not None and args.simplification <= 0:
        return "--simplification must be greater than 0."
    if args.resize_max_dimension is not None and args.resize_max_dimension < 64:
        return "--resize-max-dimension must be at least 64."
    if args.stroke_width is not None and args.stroke_width <= 0:
        return "--stroke-width must be greater than 0."
    if args.workers is not None and args.workers < 1:
        return "--workers must be at least 1."
    return None


def resolve_preset(preset_manager: PresetManager, preset_name_or_id: str | None) -> TracePreset | None:
    if not preset_name_or_id:
        return None
    needle = preset_name_or_id.strip().casefold()
    for preset in preset_manager.all_presets():
        if preset.preset_id.casefold() == needle or preset.name.casefold() == needle:
            return preset
    return None


def apply_cli_overrides(base_settings: TraceSettings, args: argparse.Namespace) -> TraceSettings:
    settings = base_settings.copy()
    if args.trace_mode is not None:
        settings.trace_mode = args.trace_mode
    if args.threshold is not None:
        settings.threshold = args.threshold
    if args.invert:
        settings.invert_colors = True
    if args.min_artifact_area is not None:
        settings.min_artifact_area = args.min_artifact_area
    if args.smoothing_strength is not None:
        settings.smoothing_strength = args.smoothing_strength
    if args.simplification is not None:
        settings.path_simplification_tolerance = args.simplification
    if args.resize_before_trace:
        settings.resize_before_trace = True
    if args.resize_max_dimension is not None:
        settings.resize_max_dimension = args.resize_max_dimension
    if args.ignore_transparency is not None:
        settings.ignore_transparent_pixels = args.ignore_transparency
    if args.merge_nearby_shapes:
        settings.merge_nearby_shapes = True
    if args.fill_only_output:
        settings.fill_only_output = True
    if args.stroke_output:
        settings.stroke_output = True
        settings.fill_only_output = False
    if args.stroke_width is not None:
        settings.stroke_width = args.stroke_width
    return settings


def print_summary(summary: BatchSummary, log_path: Path | None) -> None:
    print("")
    print("Batch summary")
    print(f"  Total: {summary.total_jobs}")
    print(f"  Exported: {summary.exported_jobs}")
    print(f"  Skipped: {summary.skipped_jobs}")
    print(f"  Failed: {summary.failed_jobs}")
    print(f"  Cancelled: {summary.cancelled_jobs}")
    print(f"  Output: {summary.output_folder}")
    if log_path is not None:
        print(f"  Log: {log_path}")
    if summary.log_export_error:
        print(f"  Log export warning: {summary.log_export_error}")


def _print_progress(progress: BatchProgress) -> None:
    current_file = progress.current_file or "-"
    print(
        f"[{progress.percent:>3}%] "
        f"{progress.completed_jobs}/{progress.total_jobs} "
        f"exported={progress.exported_jobs} skipped={progress.skipped_jobs} "
        f"failed={progress.failed_jobs} current={current_file}"
    )


def _normalize_log_format(value: str) -> ExportLogFormat:
    return value if value in {"none", "txt", "csv"} else "none"
