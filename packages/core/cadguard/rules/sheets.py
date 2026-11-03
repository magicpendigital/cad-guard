"""Khổ giấy, khung tên và bàn giao sản xuất (SH-*, PR-*)."""

from __future__ import annotations

from collections import defaultdict

from ..model import DrawingModel
from . import Ctx, Finding, Skip, rule


def _title_inserts(model: DrawingModel, names: set[str]):
    for e in model.entities:
        if e.type == "INSERT" and e.space != "Model" and (e.block or "").upper() in names:
            yield e


def _names(ctx: Ctx) -> set[str]:
    return {str(n).upper() for n in ctx.globals.get("title_block_names", [])}


@rule("SH-04")
def sh04(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    names = _names(ctx)
    if not names:
        raise Skip("chuẩn chưa khai báo tên khối khung tên (title_block_names)")
    if not model.layouts:
        raise Skip("bản vẽ không có layout (tờ giấy)")
    per_layout: dict[str, list] = defaultdict(list)
    for e in _title_inserts(model, names):
        per_layout[e.space].append(e)
    used = {e.space for e in model.entities}
    out = []
    for lo in model.layouts:
        if lo.name not in used and not lo.viewports:
            continue  # layout trống (mặc định của CAD, chưa dùng): không phải tờ bản vẽ
        n = len(per_layout.get(lo.name, []))
        if n != 1:
            out.append(Finding("SH-04", f"Layout '{lo.name}' có {n} khung tên chuẩn (cần đúng 1)", layout=lo.name))
    return out


@rule("SH-05")
def sh05(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    names = _names(ctx)
    required = [str(a).upper() for a in ctx.globals.get("title_block_required_attribs", [])]
    if not names or not required:
        raise Skip("chuẩn chưa khai báo khung tên hoặc danh sách thuộc tính bắt buộc")
    out = []
    for e in _title_inserts(model, names):
        have = {k.upper(): (v or "").strip() for k, v in (e.attribs or {}).items()}
        missing = [a for a in required if not have.get(a)]
        if missing:
            out.append(Finding("SH-05", f"Khung tên ở layout '{e.space}' thiếu giá trị: {', '.join(missing)}", layout=e.space, handles=[e.handle]))
    return out


@rule("PR-02")
def pr02(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    tag = str(ctx.globals.get("part_tag_attrib", "PART_ID")).upper()
    seen: dict[str, list[str]] = defaultdict(list)
    found_any = False
    for e in model.entities:
        if e.type != "INSERT" or not e.attribs:
            continue
        attrs = {k.upper(): (v or "").strip() for k, v in e.attribs.items()}
        if tag in attrs:
            found_any = True
            if attrs[tag]:
                seen[attrs[tag]].append(e.handle)
    if not found_any:
        raise Skip(f"không có thẻ vị trí nào mang thuộc tính {tag}")
    return [
        Finding("PR-02", f"Mã thẻ vị trí '{pid}' xuất hiện {len(hs)} lần", count=len(hs), handles=hs[:5])
        for pid, hs in seen.items()
        if len(hs) > 1
    ]
