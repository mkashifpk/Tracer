from __future__ import annotations

import cv2

from tests.asset_generator import GeneratedAssets
from tracer.core.contour_extractor import ContourExtractor
from tracer.core.image_preprocessor import ImagePreprocessor
from tracer.models.trace_settings import TraceSettings


def test_contour_extractor_finds_multiple_text_like_components(generated_assets: GeneratedAssets) -> None:
    preprocessor = ImagePreprocessor()
    extractor = ContourExtractor()

    result = preprocessor.preprocess(generated_assets.black_text_shape_png, TraceSettings())
    contour_data = extractor.extract(result.binary_mask)

    outer_contours = 0
    hierarchy = contour_data.hierarchy[0] if contour_data.hierarchy is not None else []
    for index, contour in enumerate(contour_data.contours):
        if hierarchy[index][3] == -1 and cv2.contourArea(contour) > 50:
            outer_contours += 1

    assert outer_contours >= 3


def test_contour_simplification_reduces_point_count(generated_assets: GeneratedAssets) -> None:
    preprocessor = ImagePreprocessor()
    extractor = ContourExtractor()

    result = preprocessor.preprocess(generated_assets.black_circle_png, TraceSettings())
    contour_data = extractor.extract(result.binary_mask)
    contour = max(contour_data.contours, key=cv2.contourArea)
    simplified = extractor.simplify(contour, tolerance=1.0)

    assert len(simplified) < len(contour)
