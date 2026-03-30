from pathlib import Path

from tests.asset_generator import GeneratedAssets
from tracer.services.file_scanner import FileScanner


def test_file_scanner_detects_supported_png_and_jpg(generated_assets: GeneratedAssets) -> None:
    scanner = FileScanner()
    results = scanner.scan(generated_assets.black_circle_png.parent)

    result_paths = {item.path for item in results}
    assert generated_assets.black_circle_png in result_paths
    assert generated_assets.black_circle_jpg in result_paths
