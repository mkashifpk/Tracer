from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from tracer.models.trace_settings import ResolvedTraceSettings, TraceSettings


@dataclass(slots=True)
class PreprocessResult:
    width: int
    height: int
    grayscale: np.ndarray
    binary_mask: np.ndarray
    alpha_mask: np.ndarray | None = None


class ImagePreprocessor:
    """Build a clean binary foreground mask from raster input."""

    def load_image(self, path: Path) -> Image.Image:
        with Image.open(path) as image:
            return image.convert("RGBA")

    def preprocess(self, path: Path, settings: TraceSettings) -> PreprocessResult:
        resolved = settings.resolve()
        rgba = np.array(self.load_image(path))
        rgba = self._resize_rgba_if_needed(rgba, settings)

        grayscale = self.to_grayscale(rgba, settings.ignore_transparent_pixels)
        alpha_mask = self.extract_alpha_mask(rgba, resolved.alpha_cutoff) if settings.ignore_transparent_pixels else None

        binary = self.apply_threshold(grayscale, resolved, settings.invert_colors)
        binary = self.apply_alpha_mask(binary, alpha_mask)
        cleaned = self.remove_small_artifacts(binary, resolved.min_artifact_area)
        cleaned = self.smooth_mask_edges(cleaned, resolved)
        cleaned = self.merge_nearby_shapes(cleaned, settings)
        final_min_artifact_area = 0 if resolved.min_artifact_area == 0 else max(1, resolved.min_artifact_area // 2)
        cleaned = self.remove_small_artifacts(cleaned, final_min_artifact_area)

        return PreprocessResult(
            width=cleaned.shape[1],
            height=cleaned.shape[0],
            grayscale=grayscale,
            binary_mask=cleaned,
            alpha_mask=alpha_mask,
        )

    def to_grayscale(self, rgba: np.ndarray, ignore_transparent_pixels: bool) -> np.ndarray:
        """
        Convert source pixels to luminance.

        When transparency should be ignored, transparent pixels are composited
        over white first so hidden RGB garbage in fully transparent areas does
        not become false foreground.
        """
        grayscale = cv2.cvtColor(rgba, cv2.COLOR_RGBA2GRAY).astype(np.float32)
        if not ignore_transparent_pixels or rgba.shape[2] < 4:
            return grayscale.astype(np.uint8)

        alpha = rgba[:, :, 3].astype(np.float32) / 255.0
        composited = (grayscale * alpha) + (255.0 * (1.0 - alpha))
        return np.clip(composited, 0, 255).astype(np.uint8)

    def extract_alpha_mask(self, rgba: np.ndarray, alpha_cutoff: int) -> np.ndarray | None:
        """Return a binary alpha keep-mask using a small transparency cutoff."""
        if rgba.shape[2] < 4:
            return None
        alpha = rgba[:, :, 3]
        return np.where(alpha > alpha_cutoff, 255, 0).astype(np.uint8)

    def apply_threshold(
        self,
        grayscale: np.ndarray,
        resolved: ResolvedTraceSettings,
        invert_colors: bool,
    ) -> np.ndarray:
        """
        Convert luminance into a white-foreground binary mask.

        Foreground is encoded as 255, background as 0.
        """
        threshold_source = grayscale
        if resolved.blur_amount > 0:
            threshold_source = cv2.GaussianBlur(grayscale, ksize=(0, 0), sigmaX=resolved.blur_amount, sigmaY=resolved.blur_amount)

        _, binary = cv2.threshold(threshold_source, resolved.threshold, 255, cv2.THRESH_BINARY_INV)

        if invert_colors:
            binary = cv2.bitwise_not(binary)
        return binary

    def apply_alpha_mask(self, binary: np.ndarray, alpha_mask: np.ndarray | None) -> np.ndarray:
        """Discard fully transparent pixels from the foreground mask."""
        if alpha_mask is None:
            return binary
        return np.where(alpha_mask > 0, binary, 0).astype(np.uint8)

    def remove_small_artifacts(self, binary: np.ndarray, min_area: int) -> np.ndarray:
        """Remove connected components smaller than the configured area threshold."""
        if min_area <= 0:
            return binary

        count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        cleaned = np.zeros_like(binary)
        for label in range(1, count):
            area = stats[label, cv2.CC_STAT_AREA]
            if area >= min_area:
                cleaned[labels == label] = 255
        return cleaned

    def smooth_mask_edges(self, binary: np.ndarray, resolved: ResolvedTraceSettings) -> np.ndarray:
        """
        Reduce staircase aliasing while keeping silhouettes crisp.

        Strategy:
        - upscale the mask
        - softly blur the enlarged mask
        - threshold back to binary
        - downscale to original size
        - apply a light close/open pass to regularize edges
        """
        strength = max(0, min(100, resolved.contour_smoothing))
        if strength == 0:
            return binary

        height, width = binary.shape[:2]
        upscale = 2 if strength < 70 else 3
        enlarged = cv2.resize(binary, (width * upscale, height * upscale), interpolation=cv2.INTER_CUBIC)

        sigma = max(0.25, resolved.blur_amount * 0.85)
        blurred = cv2.GaussianBlur(enlarged, ksize=(0, 0), sigmaX=sigma, sigmaY=sigma)
        _, enlarged_binary = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY)

        downscaled = cv2.resize(enlarged_binary, (width, height), interpolation=cv2.INTER_AREA)
        _, smoothed = cv2.threshold(downscaled, 127, 255, cv2.THRESH_BINARY)

        kernel_size = 3 if strength < 85 else 5
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        smoothed = cv2.morphologyEx(smoothed, cv2.MORPH_CLOSE, kernel)
        if strength >= 40:
            smoothed = cv2.morphologyEx(smoothed, cv2.MORPH_OPEN, kernel)
        if strength >= 70:
            smoothed = cv2.medianBlur(smoothed, 3)
        return smoothed

    def merge_nearby_shapes(self, binary: np.ndarray, settings: TraceSettings) -> np.ndarray:
        """Optionally bridge tiny gaps between otherwise connected shapes."""
        if not settings.merge_nearby_shapes:
            return binary

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        merged = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        return merged

    def _resize_rgba_if_needed(self, rgba: np.ndarray, settings: TraceSettings) -> np.ndarray:
        if not settings.resize_before_trace:
            return rgba

        height, width = rgba.shape[:2]
        longest = max(height, width)
        if longest <= settings.resize_max_dimension:
            return rgba

        scale = settings.resize_max_dimension / float(longest)
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        return cv2.resize(rgba, new_size, interpolation=cv2.INTER_AREA)
