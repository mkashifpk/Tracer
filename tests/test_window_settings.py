from tracer.models.window_settings import WindowSettings


def test_window_settings_invalid_payload_falls_back_to_defaults() -> None:
    settings = WindowSettings.from_dict(
        {
            "width": "bad",
            "height": None,
            "main_splitter_sizes": [1, "oops"],
            "left_splitter_sizes": "bad",
        }
    )

    assert settings.width == 1460
    assert settings.height == 900
    assert settings.main_splitter_sizes == [320, 640, 320]
    assert settings.left_splitter_sizes == [540, 220]
