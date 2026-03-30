from __future__ import annotations

from tests.asset_generator import GeneratedAssets


def test_asset_generator_creates_requested_files(generated_assets: GeneratedAssets) -> None:
    assert generated_assets.black_circle_png.exists()
    assert generated_assets.black_text_shape_png.exists()
    assert generated_assets.noisy_speckled_png.exists()
    assert generated_assets.transparent_shape_png.exists()
    assert generated_assets.white_on_black_png.exists()
    assert generated_assets.black_circle_jpg.exists()
