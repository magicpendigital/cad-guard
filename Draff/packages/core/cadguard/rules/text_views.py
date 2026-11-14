"""Chữ, kích thước, khung nhìn (TX-*, VW-*)."""

from __future__ import annotations

from collections import defaultdict

from ..model import DrawingModel
from . import Ctx, Finding, Skip, rule, sample


@rule("TX-01")
def tx01(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    allowed = {str(s).upper() for s in ctx.globals.get("allowed_text_styles", [])}
    if not allowed:
        raise Skip("chuẩn chưa khai báo allowed_text_styles")
    bad: dict[str, list[str]] = defaultdict(list)
    for e in model.entities:
        if e.text_style and e.text_style.upper() not in allowed:
            bad[e.text_style].append(e.handle)
    return [Finding("TX-01", f"{len(hs)} chữ dùng kiểu chữ '{st}' ngoài tập cho phép", count=len(hs), handles=sample(hs)) for st, hs in bad.items()]


@rule("TX-08")
def tx08(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    bad = [e.handle for e in model.entities if e.type == "DIMENSION" and e.dim_text not in (None, "", "<>")]
    if not bad:
        return []
    return [Finding("TX-08", f"{len(bad)} kích thước bị sửa chữ bằng tay (không còn là số đo thật)", count=len(bad), handles=sample(bad))]


@rule("VW-01")
def vw01(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    preferred = [float(s) for s in ctx.globals.get("preferred_scales", [])]
    if not preferred:
        raise Skip("chuẩn chưa khai báo preferred_scales")
    tol = float(ctx.globals.get("scale_tolerance", 0.005))
    out = []
    for lo in model.layouts:
        for vp in lo.viewports:
            if vp.scale is None:
                continue
            if not any(abs(vp.scale - p) <= p * tol for p in preferred):
                shown = f"1:{round(1 / vp.scale, 2):g}" if vp.scale < 1 else f"{round(vp.scale, 2):g}:1"
                out.append(Finding("VW-01", f"Khung nhìn #{vp.id} ở layout '{lo.name}' có tỉ lệ {shown} ngoài danh sách ưu tiên", layout=lo.name))
    return out
