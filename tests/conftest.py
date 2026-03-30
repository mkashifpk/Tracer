from __future__ import annotations

from pathlib import Path

import pytest

from tests.asset_generator import GeneratedAssets, generate_test_assets


@pytest.fixture()
def generated_assets(tmp_path: Path) -> GeneratedAssets:
    return generate_test_assets(tmp_path / "assets")


@pytest.fixture()
def sample_png(generated_assets: GeneratedAssets) -> Path:
    return generated_assets.transparent_shape_png
