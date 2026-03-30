from tracer.models.trace_settings import TraceSettings


def test_quality_presets_resolve_differently() -> None:
    low = TraceSettings(quality_preset="low").resolve()
    balanced = TraceSettings(quality_preset="balanced").resolve()
    high = TraceSettings(quality_preset="high").resolve()

    assert low.alpha_cutoff > balanced.alpha_cutoff > high.alpha_cutoff
    assert low.contour_smoothing < balanced.contour_smoothing < high.contour_smoothing
    assert low.simplification_tolerance > balanced.simplification_tolerance > high.simplification_tolerance
    assert low.smoothing_iterations <= balanced.smoothing_iterations <= high.smoothing_iterations


def test_trace_settings_from_dict_clamps_invalid_values() -> None:
    settings = TraceSettings.from_dict(
        {
            "trace_mode": "invalid",
            "quality_preset": "invalid",
            "threshold": 999,
            "min_artifact_area": -5,
            "smoothing_strength": 999,
            "path_simplification_tolerance": 0,
            "resize_max_dimension": 10,
            "stroke_width": -1,
            "color_precision": 99,
        }
    )

    assert settings.trace_mode == "auto"
    assert settings.quality_preset == "balanced"
    assert settings.threshold == 255
    assert settings.min_artifact_area == 0
    assert settings.smoothing_strength == 100
    assert settings.path_simplification_tolerance == 0.15
    assert settings.resize_max_dimension == 64
    assert settings.stroke_width == 0.1
    assert settings.color_precision == 12
