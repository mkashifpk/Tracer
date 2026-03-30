from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw


@dataclass(frozen=True, slots=True)
class GeneratedAssets:
    black_circle_png: Path
    black_text_shape_png: Path
    noisy_speckled_png: Path
    transparent_shape_png: Path
    white_on_black_png: Path
    black_circle_jpg: Path


def generate_test_assets(output_dir: Path) -> GeneratedAssets:
    output_dir.mkdir(parents=True, exist_ok=True)

    black_circle_png = output_dir / "black_circle.png"
    black_text_shape_png = output_dir / "black_text_shape.png"
    noisy_speckled_png = output_dir / "noisy_speckled.png"
    transparent_shape_png = output_dir / "transparent_shape.png"
    white_on_black_png = output_dir / "white_on_black.png"
    black_circle_jpg = output_dir / "black_circle.jpg"

    _create_black_circle(black_circle_png)
    _create_black_text_shape(black_text_shape_png)
    _create_noisy_speckled_image(noisy_speckled_png)
    _create_transparent_shape(transparent_shape_png)
    _create_white_on_black_shape(white_on_black_png)
    _create_black_circle_jpg(black_circle_jpg)

    return GeneratedAssets(
        black_circle_png=black_circle_png,
        black_text_shape_png=black_text_shape_png,
        noisy_speckled_png=noisy_speckled_png,
        transparent_shape_png=transparent_shape_png,
        white_on_black_png=white_on_black_png,
        black_circle_jpg=black_circle_jpg,
    )


def _create_black_circle(path: Path) -> None:
    image = Image.new("RGBA", (160, 160), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((28, 28, 132, 132), fill=(0, 0, 0, 255))
    image.save(path)


def _create_black_text_shape(path: Path) -> None:
    image = Image.new("RGBA", (220, 120), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)

    # A blocky text-like silhouette resembling "HI"
    draw.rectangle((20, 20, 40, 100), fill=(0, 0, 0, 255))
    draw.rectangle((70, 20, 90, 100), fill=(0, 0, 0, 255))
    draw.rectangle((20, 50, 90, 70), fill=(0, 0, 0, 255))
    draw.rectangle((130, 20, 150, 100), fill=(0, 0, 0, 255))
    draw.rectangle((160, 20, 180, 100), fill=(0, 0, 0, 255))
    image.save(path)


def _create_noisy_speckled_image(path: Path) -> None:
    image = Image.new("RGBA", (180, 180), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 140, 140), fill=(0, 0, 0, 255))

    speckles = [
        (8, 8),
        (18, 24),
        (24, 160),
        (154, 14),
        (166, 168),
        (86, 12),
        (12, 92),
        (158, 94),
        (90, 160),
        (30, 150),
    ]
    for x, y in speckles:
        draw.rectangle((x, y, x + 1, y + 1), fill=(0, 0, 0, 255))
    image.save(path)


def _create_transparent_shape(path: Path) -> None:
    image = Image.new("RGBA", (180, 180), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((34, 34, 146, 146), fill=(0, 0, 0, 255))
    draw.ellipse((70, 70, 110, 110), fill=(255, 255, 255, 0))

    # Hidden RGB noise in transparent pixels should be ignored when alpha handling works.
    pixels = image.load()
    for x, y in [(8, 8), (18, 18), (28, 24), (150, 20)]:
        pixels[x, y] = (0, 0, 0, 0)

    image.save(path)


def _create_white_on_black_shape(path: Path) -> None:
    image = Image.new("RGBA", (180, 180), (0, 0, 0, 255))
    draw = ImageDraw.Draw(image)
    draw.polygon([(90, 20), (150, 90), (90, 160), (30, 90)], fill=(255, 255, 255, 255))
    image.save(path)


def _create_black_circle_jpg(path: Path) -> None:
    image = Image.new("RGB", (160, 160), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((30, 30, 130, 130), fill=(0, 0, 0))
    image.save(path, quality=95)


if __name__ == "__main__":
    target = Path.cwd() / "generated_test_assets"
    assets = generate_test_assets(target)
    for path in assets.__dict__.values():
        print(path)
