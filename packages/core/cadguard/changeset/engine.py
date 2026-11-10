"""Chạy thao tác của changeset trên một tài liệu ezdxf TRONG BỘ NHỚ (bản sao đọc từ tệp gốc).

- Không hàm nào ở đây ghi tệp; ghi tệp mới do `apply.py` làm sau khi kiểm.
- Không có đường xoá đối tượng hình học. Chỉ `purge_unused` xoá định nghĩa không được tham chiếu,
  và `merge_layers` xoá định nghĩa layer nguồn sau khi đã chuyển hết tham chiếu.
- Layer bảo vệ: thao tác NÊU TÊN layer bảo vệ (bộ lọc, nguồn, đích, purge) bị từ chối (OpError);
  đối tượng trên layer bảo vệ mà bộ lọc rộng quét trúng thì bị bỏ qua và đếm vào `skipped_protected`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ezdxf

from .ops import OP_ENTITY_TYPES, OpError

SYSTEM_LAYERS = {"0", "defpoints"}
ENTITY_SKIP = {"VIEWPORT"}


def read_doc(path: str | Path):
    """Đọc DXF bằng ezdxf (có đường khôi phục cho tệp lệch cấu trúc)."""
    try:
        return ezdxf.readfile(str(path))
    except ezdxf.DXFStructureError:
        from ezdxf import recover

        doc, _auditor = recover.readfile(str(path))
        return doc


@dataclass
class Protection:
    """Layer bảo vệ: tên chính xác (không phân biệt hoa/thường) và mẫu regex (hồ sơ công ty)."""

    layers: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._names = {x.casefold() for x in self.layers}
        try:
            self._pats = [re.compile(p, re.IGNORECASE) for p in self.patterns]
        except re.error as exc:
            raise OpError(f"Mẫu layer bảo vệ không phải biểu thức chính quy hợp lệ ({exc}).") from None

    def is_protected(self, name: str | None) -> bool:
        if name is None:
            return False
        return name.casefold() in self._names or any(p.search(name) for p in self._pats)

    def to_dict(self) -> dict:
        return {"layers": list(self.layers), "patterns": list(self.patterns)}


def _cf(x: str) -> str:
    return x.casefold()


def space_of(doc, layout) -> str:
    return "Model" if layout.name.lower() == "model" else layout.name


def iter_layout_entities(doc):
    """(không gian, đối tượng) trực tiếp trong không gian mô hình và giấy; không gồm VIEWPORT."""
    for layout in doc.layouts:
        space = space_of(doc, layout)
        for e in layout:
            if e.dxftype() in ENTITY_SKIP:
                continue
            yield space, e


def _layer_entry(doc, name: str, what: str):
    if not doc.layers.has_entry(name):
        raise OpError(f"{what}: không có layer '{name}' trong bản vẽ.")
    return doc.layers.get(name)


def _check_not_protected(prot: Protection, name: str, what: str) -> None:
    if prot.is_protected(name):
        raise OpError(f"{what}: layer '{name}' được bảo vệ, thao tác bị từ chối.")


def _select(doc, op, prot: Protection) -> tuple[list[Any], int]:
    """Chọn đối tượng theo bộ lọc của thao tác; trả (đối tượng, số bị bỏ qua vì layer bảo vệ)."""
    flt = op.filter
    allowed_types = OP_ENTITY_TYPES[op.op]
    types = {t.upper() for t in flt.types} if flt.types else None
    if types is not None and allowed_types is not None and not types <= allowed_types:
        bad = ", ".join(sorted(types - allowed_types))
        raise OpError(f"{op.op}: bộ lọc 'types' có loại không áp dụng được ({bad}); chỉ nhận {', '.join(sorted(allowed_types))}.")
    for name in flt.layers or []:
        _check_not_protected(prot, name, f"{op.op}: bộ lọc 'layers'")
    layers = {_cf(x) for x in flt.layers} if flt.layers else None
    exclude = {_cf(x) for x in flt.exclude_layers} if flt.exclude_layers else set()
    spaces = {_cf(x) for x in flt.spaces} if flt.spaces else None
    out, skipped = [], 0
    for space, e in iter_layout_entities(doc):
        t = e.dxftype()
        if allowed_types is not None and t not in allowed_types:
            continue
        if types is not None and t not in types:
            continue
        if spaces is not None and _cf(space) not in spaces:
            continue
        layer = str(e.dxf.get("layer", "0"))
        if layers is not None and _cf(layer) not in layers:
            continue
        if _cf(layer) in exclude:
            continue
        if prot.is_protected(layer):
            skipped += 1
            continue
        out.append(e)
    return out, skipped


def _alive_entities(doc):
    return [e for e in doc.entitydb.values() if e.is_alive]


# ---------- từng thao tác ----------


def _rename_layer(doc, op, prot):
    src = _layer_entry(doc, op.from_, "rename_layer")
    old = str(src.dxf.name)
    _check_not_protected(prot, old, "rename_layer")
    _check_not_protected(prot, op.to, "rename_layer (tên mới)")
    if _cf(old) in SYSTEM_LAYERS:
        raise OpError(f"rename_layer: không đổi tên được layer hệ thống '{old}'.")
    if int(src.dxf.get("flags", 0)) & 16:
        raise OpError(f"rename_layer: layer '{old}' thuộc xref đang đính kèm; hãy gộp (bind) xref trong CAD trước.")
    if doc.layers.has_entry(op.to):
        raise OpError(f"rename_layer: layer '{op.to}' đã có; dùng merge_layers để gộp.")
    n = sum(1 for e in _alive_entities(doc) if e.dxf.hasattr("layer") and _cf(str(e.dxf.layer)) == _cf(old))
    try:
        src.rename(op.to)
    except ValueError:
        raise OpError(f"rename_layer: tên mới '{op.to}' không hợp lệ (không dùng ký tự <>/\\\":;?*|=).") from None
    return {"affected": n, "details": {"renamed_layers": [[old, op.to]]}}


def _merge_layers(doc, op, prot):
    target = _layer_entry(doc, op.target, "merge_layers (đích)")
    tname = str(target.dxf.name)
    _check_not_protected(prot, tname, "merge_layers (đích)")
    sources = []
    for name in op.sources:
        src = _layer_entry(doc, name, "merge_layers (nguồn)")
        sname = str(src.dxf.name)
        _check_not_protected(prot, sname, "merge_layers (nguồn)")
        if _cf(sname) == _cf(tname):
            raise OpError(f"merge_layers: layer nguồn '{sname}' trùng layer đích.")
        if _cf(sname) in SYSTEM_LAYERS:
            raise OpError(f"merge_layers: không gộp được layer hệ thống '{sname}'.")
        if int(src.dxf.get("flags", 0)) & 16:
            raise OpError(f"merge_layers: layer '{sname}' thuộc xref đang đính kèm; hãy gộp (bind) xref trong CAD trước.")
        if sname not in sources:
            sources.append(sname)
    keys = {_cf(x) for x in sources}
    n = 0
    for e in _alive_entities(doc):
        if e.dxf.hasattr("layer") and _cf(str(e.dxf.layer)) in keys:
            e.dxf.layer = tname
            n += 1
    if _cf(str(doc.header.get("$CLAYER", "0"))) in keys:
        doc.header["$CLAYER"] = tname
    for name in sources:
        doc.layers.remove(name)
    return {"affected": n, "details": {"removed_layers": sources, "target": tname}}


def _move_to_layer(doc, op, prot):
    target = _layer_entry(doc, op.target, "move_to_layer (đích)")
    tname = str(target.dxf.name)
    _check_not_protected(prot, tname, "move_to_layer (đích)")
    ents, skipped = _select(doc, op, prot)
    n = 0
    for e in ents:
        if _cf(str(e.dxf.get("layer", "0"))) != _cf(tname):
            e.dxf.layer = tname
            n += 1
    return {"affected": n, "matched": len(ents), "skipped_protected": skipped}


def _set_bylayer(doc, op, prot):
    if not op.color and not op.lineweight:
        raise OpError("set_bylayer: cần ít nhất một trong 'color' hoặc 'lineweight' = true.")
    ents, skipped = _select(doc, op, prot)
    n = 0
    for e in ents:
        changed = False
        if op.color:
            for attr in ("true_color", "color_name"):
                if e.dxf.hasattr(attr):
                    e.dxf.discard(attr)
                    changed = True
            if e.dxf.hasattr("color") and e.dxf.color != 256:
                e.dxf.color = 256
                changed = True
        if op.lineweight and e.dxf.hasattr("lineweight") and e.dxf.lineweight != -1:
            e.dxf.lineweight = -1
            changed = True
        n += changed
    return {"affected": n, "matched": len(ents), "skipped_protected": skipped}


def _style_names(table, names, what):
    out = set()
    for name in names or []:
        if not table.has_entry(name):
            raise OpError(f"{what}: không có '{name}' trong bản vẽ.")
        out.add(_cf(name))
    return out


def _replace_text_style(doc, op, prot):
    if not doc.styles.has_entry(op.to):
        raise OpError(f"replace_text_style: không có kiểu chữ đích '{op.to}' trong bản vẽ (chỉ đổi sang kiểu đã có).")
    target = doc.styles.get(op.to)
    if int(target.dxf.get("flags", 0)) & 1:
        raise OpError(f"replace_text_style: '{op.to}' là kiểu hình (shape), không dùng cho chữ.")
    tname = str(target.dxf.name)
    sources = _style_names(doc.styles, op.from_, "replace_text_style (from)")
    ents, skipped = _select(doc, op, prot)
    n = 0
    for e in ents:
        cur = str(e.dxf.get("style", "Standard"))
        if sources and _cf(cur) not in sources:
            continue
        if _cf(cur) != _cf(tname):
            e.dxf.style = tname
            n += 1
    return {"affected": n, "matched": len(ents), "skipped_protected": skipped}


def _rerender(doc, dims) -> None:
    """Vẽ lại khối hình của kích thước; xoá khối hình cũ (*D) nếu không còn ai tham chiếu."""
    old_blocks = set()
    for d in dims:
        old = d.dxf.get("geometry")
        try:
            d.override().render()
        except Exception as exc:  # noqa: BLE001 - kiểu kích thước lạ: dừng cả changeset, không ghi nửa vời
            raise OpError(f"Không vẽ lại được kích thước handle {d.dxf.handle} ({type(exc).__name__}); "
                          "hãy đặt rerender = false hoặc sửa trong CAD.") from None
        if old and old != d.dxf.get("geometry"):
            old_blocks.add(old)
    if not old_blocks:
        return
    used = {_cf(str(e.dxf.get("geometry", ""))) for e in _alive_entities(doc) if e.dxftype() == "DIMENSION"}
    used |= {_cf(str(e.dxf.get("name", ""))) for e in _alive_entities(doc) if e.dxftype() == "INSERT"}
    for name in old_blocks:
        if name.startswith("*") and _cf(name) not in used and name in doc.blocks:
            doc.blocks.delete_block(name, safe=False)


def _replace_dim_style(doc, op, prot):
    if not doc.dimstyles.has_entry(op.to):
        raise OpError(f"replace_dim_style: không có kiểu kích thước đích '{op.to}' trong bản vẽ (chỉ đổi sang kiểu đã có).")
    tname = str(doc.dimstyles.get(op.to).dxf.name)
    sources = _style_names(doc.dimstyles, op.from_, "replace_dim_style (from)")
    ents, skipped = _select(doc, op, prot)
    changed = []
    for e in ents:
        cur = str(e.dxf.get("dimstyle", "Standard"))
        if sources and _cf(cur) not in sources:
            continue
        if _cf(cur) != _cf(tname):
            e.dxf.dimstyle = tname
            changed.append(e)
    if op.rerender:
        _rerender(doc, changed)
    return {"affected": len(changed), "matched": len(ents), "skipped_protected": skipped}


def _set_text_height(doc, op, prot):
    ents, skipped = _select(doc, op, prot)
    n = 0
    for e in ents:
        attr = "char_height" if e.dxftype() == "MTEXT" else "height"
        cur = float(e.dxf.get(attr, 0.0) or 0.0)
        if op.from_height is not None and abs(cur - op.from_height) > 1e-6 * max(1.0, op.from_height):
            continue
        if abs(cur - op.to) > 1e-9:
            e.dxf.set(attr, float(op.to))
            n += 1
    return {"affected": n, "matched": len(ents), "skipped_protected": skipped}


def _clear_dim_text_override(doc, op, prot):
    ents, skipped = _select(doc, op, prot)
    changed = []
    for e in ents:
        if (e.dxf.get("text", "") or "") not in ("", "<>"):
            e.dxf.text = "<>"
            changed.append(e)
    if op.rerender:
        _rerender(doc, changed)
    return {"affected": len(changed), "matched": len(ents), "skipped_protected": skipped}


# ---------- purge ----------


def _ref_strings(doc, skip_types: set[str]) -> set[str]:
    """Mọi giá trị chuỗi (tên, handle) mà đối tượng/định nghĩa khác tham chiếu tới; bảo thủ: thừa còn hơn thiếu."""
    refs: set[str] = set()
    for e in _alive_entities(doc):
        if e.dxftype() in skip_types:
            continue
        for key, value in e.dxf.all_existing_dxf_attribs().items():
            if key in ("handle", "owner"):
                continue
            if isinstance(value, str):
                refs.add(_cf(value))
        try:
            if e.xdata is not None:
                for _app, tags in e.xdata.data.items():
                    refs.update(_cf(str(t.value)) for t in tags if isinstance(t.value, str))
        except Exception:  # noqa: BLE001
            pass
        if e.dxftype() == "VIEWPORT":
            try:
                refs.update(_cf(str(x)) for x in e.frozen_layers)
            except Exception:  # noqa: BLE001
                pass
    for var in doc.header.varnames():
        value = doc.header.get(var)
        if isinstance(value, str):
            refs.add(_cf(value))
    return refs


def _purge_pass(doc, kinds, names, prot, removed) -> int:
    n = 0
    if "blocks" in kinds:
        refs = _ref_strings(doc, {"BLOCK_RECORD", "BLOCK", "ENDBLK"})
        for br in list(doc.block_records):
            name = str(br.dxf.name)
            if name.startswith("*") or (names and _cf(name) not in names):
                continue
            layout = doc.blocks.get(name)
            if layout is None or int(layout.block.dxf.get("flags", 0)) & (4 | 8 | 16 | 32):
                continue  # xref / overlay / phụ thuộc xref: không đụng
            if _cf(name) in refs or _cf(str(br.dxf.handle)) in refs:
                continue
            doc.blocks.delete_block(name, safe=False)
            removed["blocks"].append(name)
            n += 1
    for kind, table, dxftype, keep in (("dim_styles", doc.dimstyles, "DIMSTYLE", {"standard"}),
                                       ("text_styles", doc.styles, "STYLE", {"standard"}),
                                       ("layers", doc.layers, "LAYER", SYSTEM_LAYERS)):
        if kind not in kinds:
            continue
        refs = _ref_strings(doc, {dxftype})
        for entry in list(table):
            name = str(entry.dxf.name)
            if _cf(name) in keep or (names and _cf(name) not in names):
                continue
            if kind == "text_styles" and int(entry.dxf.get("flags", 0)) & 1:
                continue  # kiểu hình (shape) do kiểu đường dùng: không đụng
            if kind == "layers" and (prot.is_protected(name) or int(entry.dxf.get("flags", 0)) & 16):
                continue
            if _cf(name) in refs or _cf(str(entry.dxf.handle)) in refs:
                continue
            table.remove(name)
            removed[kind].append(name)
            n += 1
    return n


def _purge_unused(doc, op, prot):
    names = {_cf(x) for x in op.names} if op.names else None
    for name in op.names or []:
        if doc.layers.has_entry(name) and prot.is_protected(name):
            raise OpError(f"purge_unused: layer '{name}' được bảo vệ, không xoá.")
    removed: dict[str, list[str]] = {k: [] for k in ("layers", "text_styles", "dim_styles", "blocks")}
    for _ in range(10):  # xoá khối có thể làm layer/kiểu chữ thành không dùng: lặp tới khi ổn định
        if not _purge_pass(doc, set(op.kinds), names, prot, removed):
            break
    return {"affected": sum(len(v) for v in removed.values()), "details": {"removed": removed}}


def _convert_unicode(doc, op, prot):
    from ..unicode_convert import convert_doc

    rep = convert_doc(doc, font_file=op.font, family=op.family, handles=set(op.handles) if op.handles else None,
                      include_blocks=op.include_blocks, is_protected=prot.is_protected)
    return rep.to_dict()


def _entity(doc, handle: str, what: str):
    e = doc.entitydb.get(handle)
    if e is None or not e.is_alive:
        raise OpError(f"{what}: không có đối tượng handle {handle}.")
    return e


def _text_of(e) -> str:
    t = e.dxftype()
    if t == "MTEXT":
        return e.text
    if t == "MULTILEADER":
        m = e.context.mtext
        return m.default_content if m is not None else ""
    return str(e.dxf.get("text", "") or "")


def _set_texts(doc, op, prot):
    n, skipped, dims = 0, 0, []
    for it in op.items:
        e = _entity(doc, it.handle, "set_texts")
        t = e.dxftype()
        if t not in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF", "DIMENSION", "MULTILEADER"):
            raise OpError(f"set_texts: handle {it.handle} là {t}, không phải chữ.")
        if prot.is_protected(str(e.dxf.get("layer", "0"))):
            skipped += 1
            continue
        cur = _text_of(e)
        if it.expect is not None and cur != it.expect:
            raise OpError(f"set_texts: chữ của handle {it.handle} đã khác lúc đề xuất; hãy đề xuất lại.")
        if cur == it.text:
            continue
        if t == "MTEXT":
            e.text = it.text
        elif t == "MULTILEADER":
            if e.context.mtext is None:
                raise OpError(f"set_texts: chú thích handle {it.handle} không có chữ.")
            e.context.mtext.default_content = it.text
        else:
            e.dxf.text = it.text
        if t == "DIMENSION":
            dims.append(e)
        n += 1
    if op.rerender and dims:
        _rerender(doc, dims)
    return {"affected": n, "matched": len(op.items), "skipped_protected": skipped}


def _set_attribs(doc, op, prot):
    n, skipped, missing = 0, 0, []
    for it in op.items:
        ins = _entity(doc, it.insert, "set_attribs")
        if ins.dxftype() != "INSERT":
            raise OpError(f"set_attribs: handle {it.insert} không phải khối chèn (INSERT).")
        by_tag = {str(a.dxf.tag).upper(): a for a in ins.attribs}
        for tag, value in it.values.items():
            a = by_tag.get(tag.upper())
            if a is None:
                missing.append(f"{it.insert}:{tag}")
                continue
            if prot.is_protected(str(a.dxf.get("layer", "0"))):
                skipped += 1
                continue
            if str(a.dxf.get("text", "") or "") != value:
                a.dxf.text = value
                n += 1
    if missing:
        raise OpError("set_attribs: khối không có thẻ " + ", ".join(missing[:10]) + ("…" if len(missing) > 10 else "") + ".")
    return {"affected": n, "matched": len(op.items), "skipped_protected": skipped}


HANDLERS = {
    "convert_unicode": _convert_unicode,
    "set_texts": _set_texts,
    "set_attribs": _set_attribs,
    "rename_layer": _rename_layer,
    "merge_layers": _merge_layers,
    "move_to_layer": _move_to_layer,
    "set_bylayer": _set_bylayer,
    "replace_text_style": _replace_text_style,
    "replace_dim_style": _replace_dim_style,
    "purge_unused": _purge_unused,
    "set_text_height": _set_text_height,
    "clear_dim_text_override": _clear_dim_text_override,
}


def run_ops(doc, ops: list[Any], prot: Protection) -> list[dict]:
    """Áp lần lượt các thao tác lên `doc` (đã là bản sao trong bộ nhớ). Lỗi -> OpError, tài liệu bỏ đi."""
    reports = []
    for i, op in enumerate(ops):
        try:
            rep = HANDLERS[op.op](doc, op, prot)
        except OpError as exc:
            raise OpError(f"Thao tác #{i + 1} ({op.op}): {exc}") from None
        reports.append({"index": i + 1, "op": op.op, "affected": 0, "skipped_protected": 0, **rep})
    return reports
