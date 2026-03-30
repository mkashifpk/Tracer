from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pytest

from tracer.core.tracing_engine import PotraceTracingEngine
from tracer.models.trace_settings import TraceSettings


class FakeCompletedProcess:
    def __init__(self, stdout: bytes, stderr: bytes = b"", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_potrace_engine_uses_runner_output() -> None:
    captured_command: list[str] = []
    captured_input = b""

    def fake_runner(command: list[str], **kwargs: object) -> FakeCompletedProcess:
        nonlocal captured_command, captured_input
        captured_command = command
        captured_input = kwargs["input"]  # type: ignore[index]
        return FakeCompletedProcess(
            stdout=b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0L10 0L10 10Z"/></svg>'
        )

    engine = PotraceTracingEngine(
        executable_path=Path("potrace.exe"),
        command_runner=fake_runner,
    )
    mask = np.zeros((8, 8), dtype=np.uint8)
    mask[2:6, 2:6] = 255

    svg_text = engine.trace_mask(mask, width=8, height=8, settings=TraceSettings())

    assert captured_command[0].endswith("potrace.exe")
    assert captured_command[1:5] == ["--svg", "--output", "-", "--turnpolicy"]
    assert captured_input.startswith(b"P4\n8 8\n")
    root = ET.fromstring(svg_text)
    assert root.tag.endswith("svg")
    assert 'width="8"' in svg_text
    assert 'height="8"' in svg_text


def test_potrace_engine_requires_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tracer.core.tracing_engine.optional_potrace_path", lambda: None)
    engine = PotraceTracingEngine(executable_path=None, command_runner=lambda *args, **kwargs: None)
    mask = np.zeros((4, 4), dtype=np.uint8)

    try:
        engine.trace_mask(mask, width=4, height=4, settings=TraceSettings())
    except RuntimeError as exc:
        assert "Potrace executable was not found" in str(exc)
    else:
        raise AssertionError("Expected Potrace backend to require an executable.")
