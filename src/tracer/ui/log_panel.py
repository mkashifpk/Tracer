from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget


class LogPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = QPlainTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setMaximumBlockCount(1000)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.editor)

    def append_line(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.editor.appendPlainText(f"[{timestamp}] {message}")

    def append_lines(self, messages: list[str]) -> None:
        if not messages:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        payload = "\n".join(f"[{timestamp}] {message}" for message in messages)
        self.editor.appendPlainText(payload)

    def clear(self) -> None:
        self.editor.clear()
