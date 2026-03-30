from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(slots=True)
class ContourData:
    contours: list[np.ndarray]
    hierarchy: np.ndarray | None


class ContourExtractor:
    """Extract and simplify contour geometry from a binary mask."""

    def extract(self, binary_mask: np.ndarray) -> ContourData:
        contours, hierarchy = cv2.findContours(
            binary_mask,
            cv2.RETR_CCOMP,
            cv2.CHAIN_APPROX_TC89_KCOS,
        )
        return ContourData(contours=list(contours), hierarchy=hierarchy)

    def simplify(self, contour: np.ndarray, tolerance: float) -> np.ndarray:
        perimeter = cv2.arcLength(contour, closed=True)
        epsilon = max(0.08, float(tolerance)) * max(0.45, perimeter / 1200.0)
        return cv2.approxPolyDP(contour, epsilon=epsilon, closed=True)
