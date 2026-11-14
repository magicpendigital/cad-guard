"""Vệ sinh dữ liệu (DH-*)."""

from __future__ import annotations

from collections import defaultdict

from ..model import DrawingModel
from . import Ctx, Finding, rule, sample


@rule("DH-01")
def dh01(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    groups: dict[str, list[str]] = defaultdict(list)
    for e in model.entities:
        if e.dup_key:
            groups[f"{e.space}|{e.dup_key}"].append(e.handle)
    dup_handles = [h for hs in groups.values() if len(hs) > 1 for h in hs[1:]]
    if not dup_handles:
        return []
    return [Finding("DH-01", f"{len(dup_handles)} đối tượng chồng trùng hoàn toàn lên đối tượng khác (LINE/CIRCLE/ARC)", count=len(dup_handles), handles=sample(dup_handles))]


@rule("DH-02")
def dh02(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    tol = float(ctx.globals.get("zero_tolerance", 1e-6))
    bad = []
    for e in model.entities:
        if e.type == "LINE" and e.length is not None and e.length <= tol:
            bad.append(e.handle)
        elif e.type == "LWPOLYLINE":
            if e.length is not None and e.length <= tol:
                bad.append(e.handle)
            elif e.closed and e.area is not None and e.area <= tol:
                bad.append(e.handle)
    if not bad:
        return []
    return [Finding("DH-02", f"{len(bad)} đoạn dài 0 hoặc polyline diện tích 0", count=len(bad), handles=sample(bad))]


@rule("DH-07")
def dh07(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    bad = [e.handle for e in model.entities if e.is_proxy]
    if not bad:
        return []
    return [Finding("DH-07", f"{len(bad)} đối tượng proxy/không xác định (có thể mất khi qua DXF)", count=len(bad), handles=sample(bad))]


@rule("DH-09")
def dh09(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    expected = int(ctx.globals.get("expected_units", 4))
    if model.insunits is None:
        return [Finding("DH-09", "Không đọc được đơn vị vẽ (INSUNITS)")]
    if model.insunits != expected:
        label = "không đơn vị" if model.insunits == 0 else f"mã {model.insunits}"
        return [Finding("DH-09", f"Đơn vị vẽ là {label}, chuẩn yêu cầu milimét (mã {expected})")]
    return []


@rule("DH-10")
def dh10(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    bad = [e.handle for e in model.entities if e.space == "Model" and e.has_nonzero_z]
    if not bad:
        return []
    return [Finding("DH-10", f"{len(bad)} đối tượng không nằm trên mặt phẳng z = 0", count=len(bad), handles=sample(bad))]
