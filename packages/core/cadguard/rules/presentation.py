"""Trình bày tờ theo template công ty (TP-*, chuẩn `sheet-layout-v0`). Đọc chỉ mục tờ (`sheets.py`) + template
(`template.py`, được `rule_config.effective_standard` đưa vào `globals.template`). Không có template thì Skip."""

from __future__ import annotations

import re
from collections import defaultdict

from ..model import DrawingModel
from ..sheets import build_structure, entity_points
from ..textcodec import style_encodings
from . import Ctx, Finding, Skip, rule, sample

_CACHE: dict[tuple, object] = {}


def _structure(model: DrawingModel):
    key = (id(model), model.file_hash, len(model.entities))
    st = _CACHE.get(key)
    if st is None:
        if len(_CACHE) > 4:
            _CACHE.clear()
        st = _CACHE[key] = build_structure(model)
    return st


def _tpl(ctx: Ctx) -> dict:
    tpl = ctx.globals.get("template")
    if not isinstance(tpl, dict) or not tpl.get("frame"):
        raise Skip("chưa có template trình bày của công ty (cadguard template learn)")
    return tpl


def _frames(model: DrawingModel, ctx: Ctx):
    st = _structure(model)
    frames = [s for s in st.sheets if s.kind == "frame"]
    if not frames:
        raise Skip("bản vẽ không có tờ dạng khung tên trong Model")
    return st, frames


def _attribs(model: DrawingModel, handle: str) -> dict[str, str]:
    e = next((x for x in model.entities if x.handle == handle), None)
    return {k.upper(): (v or "").strip() for k, v in ((e.attribs if e else None) or {}).items()}


@rule("TP-01")
def tp01(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    tpl = _tpl(ctx)
    _st, frames = _frames(model, ctx)
    want = tpl["frame"]["block"]
    bad = [s for s in frames if s.block != want]
    return [Finding("TP-01", f"{s.name}: khung '{s.block or 'vẽ bằng nét rời'}' không phải khung tên template '{want}'",
                    handles=[s.frame_handle]) for s in bad]


@rule("TP-02")
def tp02(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    from ..template import block_signature

    tpl = _tpl(ctx)
    want = tpl["frame"].get("signature")
    if not want:
        raise Skip("template không có chữ ký khối")
    got = block_signature(model, tpl["frame"]["block"])
    if got is None:
        return []
    diff = [k for k in ("entity_count", "types", "extents") if got.get(k) != want.get(k)]
    if not diff:
        return []
    return [Finding("TP-02", f"Định nghĩa khối khung tên '{tpl['frame']['block']}' khác template ({', '.join(diff)}): "
                             "có thể đã bị sửa, phá khối hoặc sai phiên bản")]


@rule("TP-03")
def tp03(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    tpl = _tpl(ctx)
    _st, frames = _frames(model, ctx)
    fixed = {f["tag"]: f.get("value", "") for f in tpl.get("fields", []) if f.get("kind") == "fixed"}
    if not fixed:
        raise Skip("template không có trường cố định")
    out = []
    for s in frames:
        if s.block != tpl["frame"]["block"]:
            continue
        a = _attribs(model, s.frame_handle)
        wrong = [t for t, v in fixed.items() if t in a and a[t] != v]
        if wrong:
            out.append(Finding("TP-03", f"{s.name}: thông tin cố định khác template ({', '.join(wrong)})",
                               handles=[s.frame_handle]))
    return out


@rule("TP-04")
def tp04(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    tpl = _tpl(ctx)
    _st, frames = _frames(model, ctx)
    req = [f for f in tpl.get("fields", []) if f.get("required")]
    out = []
    for s in frames:
        if s.block != tpl["frame"]["block"]:
            continue
        a = _attribs(model, s.frame_handle)
        missing = [f["tag"] for f in req if not a.get(f["tag"])]
        badpat = [f["tag"] for f in req if f.get("pattern") and a.get(f["tag"]) and not re.match(f["pattern"], a[f["tag"]])]
        if missing or badpat:
            msg = "; ".join(x for x in (f"thiếu {', '.join(missing)}" if missing else "",
                                        f"sai mẫu {', '.join(badpat)}" if badpat else "") if x)
            out.append(Finding("TP-04", f"{s.name}: khung tên {msg}", handles=[s.frame_handle]))
    return out


@rule("TP-05")
def tp05(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    tpl = _tpl(ctx)
    _st, frames = _frames(model, ctx)
    allowed = [float(x) for x in tpl.get("rules", {}).get("allowed_scales", [])]
    out = []
    for s in frames:
        if s.factor is None:
            continue
        if not s.uniform:
            out.append(Finding("TP-05", f"{s.name}: khung phóng không đều (X ≠ Y)", handles=[s.frame_handle]))
        elif allowed and not any(abs(s.factor - a) <= 0.001 * a for a in allowed):
            out.append(Finding("TP-05", f"{s.name}: hệ số khung {s.factor:g} không thuộc tỉ lệ cho phép "
                                        f"({', '.join(f'1:{a:g}' for a in allowed)})", handles=[s.frame_handle]))
    return out


@rule("TP-06")
def tp06(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    from ..template import scale_value

    tpl = _tpl(ctx)
    _st, frames = _frames(model, ctx)
    fld = next((f for f in tpl.get("fields", []) if f.get("role") == "scale"), None)
    if fld is None:
        raise Skip("template không có trường tỉ lệ")
    tag = fld["tag"]
    out = []
    for s in frames:
        if s.block != tpl["frame"]["block"] or not s.factor:
            continue
        val = scale_value(_attribs(model, s.frame_handle).get(tag, ""), bool(fld.get("bare")))
        if val is None:
            continue
        if abs(val - s.factor) > 0.01 * s.factor:
            out.append(Finding("TP-06", f"{s.name}: khung tên ghi tỉ lệ 1:{val:g} nhưng khung phóng {s.factor:g}",
                               handles=[s.frame_handle]))
    return out


def _to_block(s, p, tpl):
    """Đổi điểm mô hình sang toạ độ khối khung tên (khung không xoay)."""
    x0, y0, _x1, _y1 = s.windows[0]
    bx0, by0 = tpl["frame"]["extents"][0], tpl["frame"]["extents"][1]
    k = s.factor or 1.0
    return (p[0] - x0) / k + bx0, (p[1] - y0) / k + by0


@rule("TP-07")
def tp07(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    tpl = _tpl(ctx)
    st, frames = _frames(model, ctx)
    area = tpl["frame"].get("drawing_area")
    if not area:
        raise Skip("template không có vùng vẽ")
    tol = 0.003 * (area[2] - area[0])
    by_handle = {e.handle: e for e in model.entities}
    out = []
    for s in frames:
        if s.block != tpl["frame"]["block"] or not s.factor:
            continue
        over = []
        for h in s.handles:
            e = by_handle.get(h)
            if e is None or h == s.frame_handle or e.type in ("DIMENSION",):
                continue
            pts = entity_points(e)
            if any(not (area[0] - tol <= bx <= area[2] + tol and area[1] - tol <= by <= area[3] + tol)
                   for bx, by in (_to_block(s, p, tpl) for p in pts)):
                over.append(h)
        if over:
            out.append(Finding("TP-07", f"{s.name}: {len(over)} đối tượng tràn ra ngoài vùng vẽ hoặc đè dải khung tên",
                               count=len(over), handles=sample(over)))
    return out


@rule("TP-08")
def tp08(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    st = _structure(model)
    if not st.sheets:
        raise Skip("bản vẽ chưa nhận ra tờ nào")
    if not st.outside:
        return []
    return [Finding("TP-08", f"{len(st.outside)} đối tượng nằm ngoài mọi tờ (không được in)", count=len(st.outside),
                    handles=sample(st.outside))]


@rule("TP-09")
def tp09(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    tpl = _tpl(ctx)
    _st, frames = _frames(model, ctx)
    mn = float(tpl.get("rules", {}).get("min_text_mm", 0) or 0)
    if mn <= 0:
        raise Skip("template không có cỡ chữ in tối thiểu")
    by_handle = {e.handle: e for e in model.entities}
    out = []
    for s in frames:
        if not s.factor:
            continue
        small = [h for h in s.handles if (e := by_handle.get(h)) is not None and e.type in ("TEXT", "MTEXT")
                 and e.text_height and e.text_height / s.factor < mn - 0.05]
        if small:
            out.append(Finding("TP-09", f"{s.name}: {len(small)} chữ in ra nhỏ hơn {mn:g} mm", count=len(small),
                               handles=sample(small)))
    return out


@rule("TP-10")
def tp10(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    tpl = _tpl(ctx)
    _st, frames = _frames(model, ctx)
    tag = next((f["tag"] for f in tpl.get("fields", []) if f.get("role") == "number"), None)
    if tag is None:
        raise Skip("template không có trường số bản vẽ")
    seen: dict[str, list] = defaultdict(list)
    nums = []
    for s in frames:
        if s.block != tpl["frame"]["block"]:
            continue
        v = _attribs(model, s.frame_handle).get(tag, "")
        if v:
            seen[v].append(s)
            m = re.search(r"(\d+)\D*$", v)
            nums.append(int(m.group(1)) if m else None)
    out = [Finding("TP-10", f"Số bản vẽ '{v}' trùng ở {', '.join(x.name for x in ss)}", count=len(ss),
                   handles=[x.frame_handle for x in ss][:5]) for v, ss in seen.items() if len(ss) > 1]
    seq = [n for n in nums if n is not None]
    if seq and seq != sorted(seq):
        out.append(Finding("TP-10", "Thứ tự số bản vẽ không khớp thứ tự tờ (trái sang phải, trên xuống dưới)"))
    return out


@rule("TP-12")
def tp12(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    st, frames = _frames(model, ctx)
    enc = style_encodings(model)
    if not enc:
        return []
    by_handle = {e.handle: e for e in model.entities}
    legacy = defaultdict(int)
    for s in frames:
        for h in s.handles:
            e = by_handle.get(h)
            if e is not None and e.type in ("TEXT", "MTEXT") and (e.text_style or "").lower() in enc:
                legacy[e.text_style] += 1
    return [Finding("TP-12", f"{n} chữ trong tờ dùng kiểu chữ '{name}' phông mã cũ (chưa Unicode): dùng "
                             "'Chuyển chữ sang Unicode'", count=n) for name, n in sorted(legacy.items())]
