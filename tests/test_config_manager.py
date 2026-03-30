import json
from pathlib import Path

from tracer.models.app_settings import AppSettings
from tracer.models.trace_settings import TraceSettings
from tracer.models.window_settings import WindowSettings
from tracer.services.config_manager import ConfigManager


def test_config_manager_round_trip(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    manager = ConfigManager(config_path=config_path)

    app_settings = AppSettings(input_folder="in", output_folder="out")
    trace_settings = TraceSettings(threshold=140)
    window_settings = WindowSettings(width=1200, height=800, main_splitter_sizes=[250, 700, 250], left_splitter_sizes=[500, 200])
    manager.save(app_settings, trace_settings, window_settings)

    loaded_app, loaded_trace, loaded_window = manager.load()
    assert loaded_app.input_folder == "in"
    assert loaded_trace.threshold == 140
    assert loaded_window.width == 1200
    assert loaded_window.main_splitter_sizes == [250, 700, 250]


def test_config_manager_migrates_legacy_trace_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "app_settings": {"input_folder": "legacy-in"},
                "trace_settings": {"threshold": 200, "min_artifact_area": 99},
                "window_settings": {"width": 1111, "height": 777},
            }
        ),
        encoding="utf-8",
    )

    manager = ConfigManager(config_path=config_path)
    loaded_app, loaded_trace, loaded_window = manager.load()

    assert loaded_app.input_folder == "legacy-in"
    assert loaded_trace.threshold == 128
    assert loaded_trace.min_artifact_area == 2
    assert loaded_window.width == 1111
