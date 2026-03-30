from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class WindowSettings:
    width: int = 1460
    height: int = 900
    main_splitter_sizes: list[int] = field(default_factory=lambda: [320, 640, 320])
    left_splitter_sizes: list[int] = field(default_factory=lambda: [540, 220])

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "WindowSettings":
        width = _coerce_int(payload.get("width", 1460), 1460, minimum=900, maximum=4000)
        height = _coerce_int(payload.get("height", 900), 900, minimum=600, maximum=2400)
        main_splitter_sizes = _coerce_int_list(payload.get("main_splitter_sizes"), [320, 640, 320], expected_length=3)
        left_splitter_sizes = _coerce_int_list(payload.get("left_splitter_sizes"), [540, 220], expected_length=2)
        return cls(
            width=width,
            height=height,
            main_splitter_sizes=main_splitter_sizes,
            left_splitter_sizes=left_splitter_sizes,
        )


def _coerce_int(value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, coerced))


def _coerce_int_list(value: object, default: list[int], expected_length: int) -> list[int]:
    if not isinstance(value, list) or len(value) != expected_length:
        return default.copy()

    normalized: list[int] = []
    for item in value:
        try:
            normalized.append(max(50, int(item)))
        except (TypeError, ValueError):
            return default.copy()
    return normalized
