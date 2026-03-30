from __future__ import annotations

from pathlib import Path

from PIL import Image

from tracer.models.file_item import FileItem

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg"}


class FileScanner:
    def scan(self, folder: Path) -> list[FileItem]:
        items: list[FileItem] = []
        if not folder.exists():
            return items

        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            item = FileItem(path=path, extension=path.suffix.lower())
            try:
                with Image.open(path) as image:
                    item.width, item.height = image.size
                    item.has_alpha = "A" in image.getbands()
                    item.status = "Ready"
            except Exception as exc:  # noqa: BLE001
                item.status = "Unsupported"
                item.message = str(exc)
            items.append(item)
        return items
