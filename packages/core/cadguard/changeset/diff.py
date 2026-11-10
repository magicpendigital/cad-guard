"""So hai bản vẽ DXF theo HANDLE (kiểu `git diff` cho bản vẽ).

- Đối tượng: mọi đối tượng trực tiếp trong không gian mô hình, giấy và định nghĩa khối (kể cả ATTRIB của INSERT),
  trừ nội dung khối hình kích thước `*D…` (sinh lại được từ DIMENSION, chỉ đếm số khối).
- Thuộc tính so theo tên thuộc tính DXF (ezdxf); khác ở dữ liệu không có tên (đỉnh đa tuyến, XDATA…) báo là `data`.
- Định nghĩa: layer, kiểu chữ, kiểu kích thước, khối (thêm/xoá/đổi).
- Đầu ra có cấu trúc + tóm tắt số liệu; danh sách bị cắt ở `max_items` (`truncated` = true), số tổng luôn đủ.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ezdxf.lldxf.tagwriter import TagCollector

from .engine import read_doc

DEFAULT_MAX_ITEMS = 200
MAX_STR = 200
DEF_KINDS = ("layers", "text_styles", "dim_styles", "blocks")


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class EntSnap:
    handle: str
    type: str
    layer: str
    space: str
    attrs: dict[str, Any]
    tags: list


def _tags(e, version) -> list:
    tc = TagCollector(dxfversion=version)
    try:
        e.export_dxf(tc)
    except Exception:  # noqa: BLE001 - đối tượng lạ: so bằng thuộc tính
        return []
    tags = [(t.code, t.value) for t in tc.tags]
    if e.dxftype() == "INSERT":  # ATTRIB/SEQEND theo sau INSERT được so riêng theo handle của chúng
        for i, (code, _v) in enumerate(tags[1:], 1):
            if code == 0:
                return tags[:i]
    return tags


def _attrs(e) -> dict[str, Any]:
    out = {k: v for k, v in e.dxf.all_existing_dxf_attribs().items() if k not in ("handle", "owner")}
    if e.dxftype() == "MTEXT":
        out["text"] = e.text
    return out


def _is_dim_block(name: str) -> bool:
    return name.upper().startswith("*D")


def snapshot(doc) -> dict:
    """Ảnh chụp để so: đối tượng theo handle + định nghĩa theo tên (không phân biệt hoa/thường)."""
    version = doc.dxfversion
    spaces = {}
    for layout in doc.layouts:
        spaces[layout.block_record_name.casefold()] = "Model" if layout.name.lower() == "model" else layout.name
    ents: dict[str, EntSnap] = {}
    dim_blocks = 0
    for br in doc.block_records:
        name = str(br.dxf.name)
        if _is_dim_block(name):
            dim_blocks += 1
            continue
        space = spaces.get(name.casefold(), "block:" + name)
        block = doc.blocks.get(name)
        if block is None:
            continue
        for e in block:
            items = [e] + (list(e.attribs) if e.dxftype() == "INSERT" else [])
            for x in items:
                h = str(x.dxf.get("handle", ""))
                if not h:
                    continue
                ents[h] = EntSnap(h, x.dxftype(), str(x.dxf.get("layer", "0")), space, _attrs(x), _tags(x, version))
    defs: dict[str, dict[str, tuple[str, list]]] = {k: {} for k in DEF_KINDS}
    for kind, table in (("layers", doc.layers), ("text_styles", doc.styles), ("dim_styles", doc.dimstyles)):
        for entry in table:
            name = str(entry.dxf.name)
            tags = [t for t in _tags(entry, version) if t[0] != 5]
            defs[kind][name.casefold()] = (name, tags)
    for br in doc.block_records:
        name = str(br.dxf.name)
        if _is_dim_block(name) or name.casefold() in spaces:
            continue
        defs["blocks"][name.casefold()] = (name, [])
    return {"entities": ents, "defs": defs, "dim_blocks": dim_blocks}


def jsonable(v: Any) -> Any:
    if isinstance(v, (bool, int)) or v is None:
        return v
    if isinstance(v, float):
        return round(v, 9)
    if isinstance(v, str):
        return v if len(v) <= MAX_STR else v[:MAX_STR] + "…"
    try:
        return [jsonable(x) for x in v]
    except TypeError:
        return str(v)[:MAX_STR]


def changed_attrs(a: EntSnap, b: EntSnap) -> dict[str, tuple[Any, Any]]:
    out = {}
    for k in sorted(set(a.attrs) | set(b.attrs)):
        va, vb = a.attrs.get(k), b.attrs.get(k)
        # Vec3 của ezdxf so với None (thuộc tính chỉ có ở một bên, vd. cùng handle khác loại) ném TypeError.
        if (va is None) != (vb is None) or (va is not None and va != vb):
            out[k] = (va, vb)
    if not out and a.tags != b.tags:
        out["data"] = (None, None)
    return out


def _brief(s: EntSnap) -> dict:
    return {"handle": s.handle, "type": s.type, "layer": s.layer, "space": s.space}


def diff_snapshots(a: dict, b: dict, max_items: int | None = DEFAULT_MAX_ITEMS) -> dict:
    ea, eb = a["entities"], b["entities"]
    cap = None if max_items is None else max(0, int(max_items))
    added = [_brief(eb[h]) for h in eb if h not in ea]
    removed = [_brief(ea[h]) for h in ea if h not in eb]
    changed = []
    by_attr: Counter = Counter()
    for h, sa in ea.items():
        sb = eb.get(h)
        if sb is None:
            continue
        attrs = changed_attrs(sa, sb)
        if attrs:
            by_attr.update(attrs.keys())
            changed.append({**_brief(sa), "type_after": sb.type if sb.type != sa.type else None,
                            "attrs": {k: [jsonable(x), jsonable(y)] for k, (x, y) in attrs.items()}})
    defs = {}
    def_summary = {}
    for kind in DEF_KINDS:
        da, db = a["defs"][kind], b["defs"][kind]
        d_add = sorted(db[k][0] for k in db if k not in da)
        d_rem = sorted(da[k][0] for k in da if k not in db)
        d_chg = sorted(da[k][0] for k in da if k in db and da[k][1] != db[k][1])
        defs[kind] = {"added": d_add, "removed": d_rem, "changed": d_chg}
        def_summary[kind] = {"added": len(d_add), "removed": len(d_rem), "changed": len(d_chg)}
    truncated = False
    if cap is not None:
        for lst in (added, removed, changed):
            if len(lst) > cap:
                truncated = True
                del lst[cap:]
        for kind in DEF_KINDS:
            for key in ("added", "removed", "changed"):
                if len(defs[kind][key]) > cap:
                    truncated = True
                    del defs[kind][key][cap:]
    summary = {
        "entities_a": len(ea),
        "entities_b": len(eb),
        "added": sum(1 for h in eb if h not in ea),
        "removed": sum(1 for h in ea if h not in eb),
        "changed": sum(1 for h in ea if h in eb and changed_attrs(ea[h], eb[h])),
        "changed_by_attr": dict(sorted(by_attr.items())),
        "definitions": def_summary,
        "dim_geometry_blocks": [a["dim_blocks"], b["dim_blocks"]],
    }
    return {"summary": summary, "entities": {"added": added, "removed": removed, "changed": changed},
            "definitions": defs, "truncated": truncated, "max_items": cap}


def summary_vi(d: dict) -> str:
    s = d["summary"]
    parts = [f"{s['changed']} đối tượng đổi, {s['added']} thêm, {s['removed']} xoá (trên {s['entities_a']} → {s['entities_b']})"]
    if s["changed_by_attr"]:
        parts.append("thuộc tính đổi: " + ", ".join(f"{k} ×{v}" for k, v in s["changed_by_attr"].items()))
    labels = {"layers": "layer", "text_styles": "kiểu chữ", "dim_styles": "kiểu kích thước", "blocks": "khối"}
    for kind, c in s["definitions"].items():
        bits = [f"{label} {c[key]}" for key, label in (("added", "+"), ("removed", "−"), ("changed", "đổi")) if c[key]]
        if bits:
            parts.append(f"định nghĩa {labels[kind]}: " + " ".join(bits))
    return "; ".join(parts) + "."


def diff_files(a: str | Path, b: str | Path, max_items: int | None = DEFAULT_MAX_ITEMS) -> dict:
    """So hai tệp DXF; chỉ ghi tên tệp (không đường dẫn) và mã băm."""
    sa, sb = snapshot(read_doc(a)), snapshot(read_doc(b))
    out = diff_snapshots(sa, sb, max_items)
    out = {"a": {"name": Path(a).name, "sha256": sha256_file(a)}, "b": {"name": Path(b).name, "sha256": sha256_file(b)}, **out}
    out["summary_vi"] = summary_vi(out)
    return out
