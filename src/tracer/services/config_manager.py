from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from tracer.models.app_settings import AppSettings
from tracer.models.trace_settings import TraceSettings
from tracer.models.window_settings import WindowSettings
from tracer.utils.paths import config_file_path

CONFIG_VERSION = 2


class ConfigManager:
    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or self._default_config_path()

    def load(self) -> tuple[AppSettings, TraceSettings, WindowSettings]:
        if not self.config_path.exists():
            return AppSettings(), TraceSettings(), WindowSettings()

        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppSettings(), TraceSettings(), WindowSettings()

        if not isinstance(payload, dict):
            return AppSettings(), TraceSettings(), WindowSettings()

        version = payload.get("version", 0)
        if not isinstance(version, int) or version < 1:
            return AppSettings(), TraceSettings(), WindowSettings()

        app_settings = AppSettings.from_dict(_safe_mapping(payload.get("app_settings")))
        window_settings = WindowSettings.from_dict(_safe_mapping(payload.get("window_settings")))
        if version < CONFIG_VERSION:
            trace_settings = TraceSettings()
        else:
            trace_settings = TraceSettings.from_dict(_safe_mapping(payload.get("trace_settings")))
        return app_settings, trace_settings, window_settings

    def save(
        self,
        app_settings: AppSettings,
        trace_settings: TraceSettings,
        window_settings: WindowSettings,
    ) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": CONFIG_VERSION,
            "app_settings": app_settings.to_dict(),
            "trace_settings": trace_settings.to_dict(),
            "window_settings": window_settings.to_dict(),
        }
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=self.config_path.parent,
            suffix=".tmp",
        ) as handle:
            handle.write(json.dumps(payload, indent=2))
            temp_path = Path(handle.name)
        temp_path.replace(self.config_path)

    def reset(self) -> tuple[AppSettings, TraceSettings, WindowSettings]:
        defaults = (AppSettings(), TraceSettings(), WindowSettings())
        self.save(*defaults)
        return defaults

    @staticmethod
    def _default_config_path() -> Path:
        return config_file_path()


def _safe_mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}
