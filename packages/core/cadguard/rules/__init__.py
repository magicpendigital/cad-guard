"""Sổ đăng ký luật. Mỗi luật: hàm (model, ctx) -> danh sách Finding, gắn bằng @rule("<mã>")."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ..model import DrawingModel


class Skip(Exception):
    """Luật không áp dụng được cho bản vẽ này (thiếu dữ liệu). Không phải lỗi."""


@dataclass
class Finding:
    rule_id: str
    message: str
    severity: str = "W"  # runner điền theo chuẩn
    layout: str | None = None
    layer: str | None = None
    count: int = 1
    handles: list[str] = field(default_factory=list)  # tối đa vài mẫu


@dataclass
class Ctx:
    globals: dict
    params: dict = field(default_factory=dict)  # tham số của luật đang chạy (RuleSpec.params, đã áp hồ sơ công ty)

    def param(self, name: str):
        """Tham số của luật; chuẩn không khai báo thì luật không chạy được (Skip), không đoán giá trị."""
        if name not in self.params:
            raise Skip(f"chuẩn chưa khai báo tham số '{name}' cho luật này")
        return self.params[name]


RuleFn = Callable[[DrawingModel, Ctx], list[Finding]]
REGISTRY: dict[str, RuleFn] = {}


def rule(rule_id: str) -> Callable[[RuleFn], RuleFn]:
    def deco(fn: RuleFn) -> RuleFn:
        if rule_id in REGISTRY:
            raise ValueError(f"Luật {rule_id} đăng ký hai lần")
        REGISTRY[rule_id] = fn
        return fn

    return deco


def sample(handles: list[str], n: int = 5) -> list[str]:
    return handles[:n]


# Nạp các module luật để chúng tự đăng ký.
from . import data_hygiene, hygiene, layers, sheets, text_views  # noqa: E402,F401
