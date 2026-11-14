"""`cadguard stats --json`: object phẳng { "<metric id>": số } cho MCA. Chỉ số tổng hợp, không có tên/đường dẫn."""

from __future__ import annotations

from . import telemetry
from .rules import REGISTRY
from .standard import Standard


def rules_implemented(standard: Standard) -> int:
    """Luật có `implemented: true` trong chuẩn VÀ có hàm trong sổ đăng ký (test xanh do CI bảo đảm)."""
    return sum(1 for r in standard.rules if r.implemented and r.id in REGISTRY)


def compute_stats(standard: Standard) -> dict[str, int | float]:
    return {
        "rules_implemented": rules_implemented(standard),
        "drawings_audited_7d": telemetry.drawings_audited(7),
    }
