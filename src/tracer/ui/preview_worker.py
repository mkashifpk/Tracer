from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from tracer.models.preview_result import PreviewResult
from tracer.models.trace_settings import TraceSettings
from tracer.services.preview_service import PreviewService


class PreviewWorker(QObject):
    completed = Signal(str, object)
    failed = Signal(str, str)

    def __init__(
        self,
        image_path: Path,
        settings: TraceSettings,
        preview_service: PreviewService | None = None,
    ) -> None:
        super().__init__()
        self.image_path = Path(image_path)
        self.settings = settings
        self.preview_service = preview_service or PreviewService()

    @Slot()
    def run(self) -> None:
        try:
            result = self.preview_service.render_preview(self.image_path, self.settings)
            self.completed.emit(str(self.image_path), result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(self.image_path), str(exc))
