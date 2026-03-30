from __future__ import annotations

from dataclasses import dataclass

from tracer.models.trace_settings import TraceSettings

PRESET_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class TracePreset:
    preset_id: str
    name: str
    description: str
    settings: TraceSettings
    is_builtin: bool = False

    def copy(self) -> "TracePreset":
        return TracePreset(
            preset_id=self.preset_id,
            name=self.name,
            description=self.description,
            settings=self.settings.copy(),
            is_builtin=self.is_builtin,
        )

    def to_export_dict(self) -> dict:
        return {
            "version": PRESET_SCHEMA_VERSION,
            "name": self.name,
            "description": self.description,
            "settings": self.settings.to_dict(),
        }
