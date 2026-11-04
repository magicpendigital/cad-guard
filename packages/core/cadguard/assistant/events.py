"""Sự kiện chung của mọi engine trợ lý AI và số đo token/chi phí."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

EVENT_TYPES = ("text", "tool_call", "tool_result", "usage", "error", "done")


@dataclass
class Usage:
    """Token và chi phí của một lượt (hoặc cộng dồn cả phiên).

    `cost_usd` None = không biết giá. `cost_estimated` True = số do máy khách/cad-guard ước tính (không phải hoá đơn).
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float | None = None
    cost_estimated: bool = True

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_read_tokens + self.cache_write_tokens

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens
        if other.cost_usd is not None:
            self.cost_usd = (self.cost_usd or 0.0) + other.cost_usd
        self.cost_estimated = self.cost_estimated or other.cost_estimated

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_tokens"] = self.total_tokens
        return d


@dataclass
class Event:
    """Một sự kiện trong luồng trả lời.

    - `text`: data = {"text": str}
    - `tool_call`: data = {"id", "name", "arguments"}
    - `tool_result`: data = {"id", "name", "content": str, "is_error": bool}
    - `usage`: data = {"usage": Usage}
    - `error`: data = {"message": str (tiếng Việt, không khoá/đường dẫn tuyệt đối), "code": str}
    - `done`: data = {"text": câu trả lời cuối}
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in EVENT_TYPES:
            raise ValueError(f"kiểu sự kiện lạ: {self.type}")

    @property
    def text(self) -> str:
        return str(self.data.get("text") or self.data.get("message") or "")

    def to_dict(self) -> dict:
        data = dict(self.data)
        if isinstance(data.get("usage"), Usage):
            data["usage"] = data["usage"].to_dict()
        return {"type": self.type, **data}


def text(t: str) -> Event:
    return Event("text", {"text": t})


def error(message: str, code: str = "error") -> Event:
    return Event("error", {"message": message, "code": code})


def usage(u: Usage) -> Event:
    return Event("usage", {"usage": u})


def done(t: str = "") -> Event:
    return Event("done", {"text": t})
