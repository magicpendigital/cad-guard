"""Chạy bộ luật của một chuẩn trên một Drawing Model. Một luật lỗi không bao giờ làm hỏng cả lần quét."""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import DrawingModel
from .rules import REGISTRY, Ctx, Finding, Skip
from .standard import Standard


@dataclass
class AuditResult:
    findings: list[Finding] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (mã luật, lý do)
    rules_run: int = 0


def audit_model(model: DrawingModel, standard: Standard) -> AuditResult:
    ctx = Ctx(globals=standard.globals)
    res = AuditResult()
    for spec in standard.rules:
        if not spec.enabled:
            continue
        fn = REGISTRY.get(spec.id)
        if not spec.implemented or fn is None:
            continue
        try:
            found = fn(model, ctx)
        except Skip as s:
            res.skipped.append((spec.id, str(s)))
            continue
        except Exception as exc:  # noqa: BLE001 - luật hỏng được báo, không làm sập
            res.skipped.append((spec.id, f"lỗi nội bộ của luật: {type(exc).__name__}: {exc}"))
            continue
        res.rules_run += 1
        for f in found:
            f.severity = spec.severity
            res.findings.append(f)
    return res
