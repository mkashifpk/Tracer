from __future__ import annotations

from pathlib import Path

import numpy as np

from tests.asset_generator import GeneratedAssets
from tracer.core.image_preprocessor import ImagePreprocessor
from tracer.models.trace_settings import TraceSettings


def test_preprocessor_loads_png_and_jpg_assets(generated_assets: GeneratedAssets) -> None:
    preprocessor = ImagePreprocessor()

    png_result = preprocessor.preprocess(generated_assets.black_circle_png, TraceSettings())
    jpg_result = preprocessor.preprocess(generated_assets.black_circle_jpg, TraceSettings())

    assert png_result.binary_mask.shape == (160, 160)
    assert jpg_result.binary_mask.shape == (160, 160)
    assert np.count_nonzero(png_result.binary_mask) > 0
    assert np.count_nonzero(jpg_result.binary_mask) > 0
    assert set(np.unique(png_result.binary_mask)).issubset({0, 255})
    assert set(np.unique(jpg_result.binary_mask)).issubset({0, 255})


def test_transparent_pixels_are_ignored_when_enabled(generated_assets: GeneratedAssets) -> None:
    preprocessor = ImagePreprocessor()

    result = preprocessor.preprocess(
        generated_assets.transparent_shape_png,
        TraceSettings(ignore_transparent_pixels=True),
    )

    assert result.alpha_mask is not None
    assert result.binary_mask[8, 8] == 0
    assert result.binary_mask[18, 18] == 0
    assert np.count_nonzero(result.binary_mask) > 0


def test_threshold_and_invert_handle_white_shape_on_black_background(generated_assets: GeneratedAssets) -> None:
    preprocessor = ImagePreprocessor()

    without_invert = preprocessor.preprocess(
        generated_assets.white_on_black_png,
        TraceSettings(invert_colors=False),
    )
    with_invert = preprocessor.preprocess(
        generated_assets.white_on_black_png,
        TraceSettings(invert_colors=True),
    )

    assert np.count_nonzero(without_invert.binary_mask) > np.count_nonzero(with_invert.binary_mask)
    assert np.count_nonzero(with_invert.binary_mask) > 0


def test_noise_removal_reduces_micro_speckles(generated_assets: GeneratedAssets) -> None:
    preprocessor = ImagePreprocessor()
    noisy_settings = TraceSettings(min_artifact_area=0, smoothing_strength=0)
    cleaned_settings = TraceSettings(min_artifact_area=10, smoothing_strength=30)

    noisy = preprocessor.preprocess(generated_assets.noisy_speckled_png, noisy_settings)
    cleaned = preprocessor.preprocess(generated_assets.noisy_speckled_png, cleaned_settings)

    assert np.count_nonzero(cleaned.binary_mask) < np.count_nonzero(noisy.binary_mask)
    assert np.count_nonzero(cleaned.binary_mask) > 0
