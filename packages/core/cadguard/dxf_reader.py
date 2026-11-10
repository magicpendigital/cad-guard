"""Đọc DXF (ezdxf) -> Drawing Model. Không bao giờ ném lỗi vì một đối tượng lạ: đối tượng đọc không được bị bỏ qua."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import ezdxf
from ezdxf.math import Vec3

from .model import BlockRec, DrawingModel, EntityRec, LayerRec, LayoutRec, ModelStats, SpaceStats, StyleRec, ViewportRec

Z_TOL = 1e-6
PROXY_TYPES = {"ACAD_PROXY_ENTITY", "PROXY", "ACAD_PROXY_OBJECT"}
MAX_PTS = 10000  # LWPOLYLINE nhiều đỉnh hơn: không ghi `pts` (giữ mô hình gọn)
TEXT_MAX = 300  # TEXT/MTEXT: cắt nội dung ở số ký tự này
POINT_ATTRS = ("start", "end", "center", "insert", "location")


def _r(v: float) -> float:
    return round(float(v), 4)


def _pt(p) -> tuple[float, float]:
    v = Vec3(p)
    return (_r(v.x), _r(v.y))


def _has_z(e) -> bool:
    if e.dxftype() == "LWPOLYLINE":
        return abs(float(e.dxf.get("elevation", 0.0) or 0.0)) > Z_TOL
    for name in POINT_ATTRS:
        if e.dxf.hasattr(name) and abs(Vec3(e.dxf.get(name)).z) > Z_TOL:
            return True
    return False


def _polyline_metrics(e) -> tuple[float, float | None, bool]:
    pts = [(float(x), float(y)) for x, y in e.get_points("xy")]
    closed = bool(e.closed)
    length = 0.0
    for a, b in zip(pts, pts[1:]):
        length += ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
    area = None
    if closed and len(pts) >= 3:
        length += ((pts[0][0] - pts[-1][0]) ** 2 + (pts[0][1] - pts[-1][1]) ** 2) ** 0.5
        s = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))
        area = abs(s) / 2.0
    return length, area, closed


def _entity_rec(e, space: str) -> EntityRec:
    t = e.dxftype()
    rec = EntityRec(
        handle=str(e.dxf.get("handle", "")),
        type=t,
        layer=str(e.dxf.get("layer", "0")),
        space=space,
        is_proxy=t in PROXY_TYPES,
        color=e.dxf.get("color", None),
        lineweight=e.dxf.get("lineweight", None),
        true_color=e.dxf.get("true_color", None),
    )
    try:
        rec.has_nonzero_z = _has_z(e)
    except Exception:  # noqa: BLE001 - đối tượng lạ không được làm hỏng cả file
        pass
    try:
        if t == "LINE":
            a, b = Vec3(e.dxf.start), Vec3(e.dxf.end)
            rec.length = float((b - a).magnitude)
            rec.dup_key = f"LINE|{rec.layer}|{sorted([_pt(a), _pt(b)])}"
            rec.pts = [_pt(a), _pt(b)]
        elif t == "LWPOLYLINE":
            rec.length, rec.area, rec.closed = _polyline_metrics(e)
            if len(e) <= MAX_PTS:
                rec.pts = [(_r(x), _r(y)) for x, y in e.get_points("xy")]
        elif t == "CIRCLE":
            rec.dup_key = f"CIRCLE|{rec.layer}|{_pt(e.dxf.center)}|{_r(e.dxf.radius)}"
            rec.pts, rec.radius = [_pt(e.dxf.center)], _r(e.dxf.radius)
        elif t == "ARC":
            rec.dup_key = f"ARC|{rec.layer}|{_pt(e.dxf.center)}|{_r(e.dxf.radius)}|{_r(e.dxf.start_angle)}|{_r(e.dxf.end_angle)}"
            c = _pt(e.dxf.center)
            rec.arc = (c[0], c[1], _r(e.dxf.radius), _r(e.dxf.start_angle), _r(e.dxf.end_angle))
        elif t in ("TEXT", "MTEXT"):
            rec.text_style = str(e.dxf.get("style", "Standard"))
            if t == "MTEXT":
                rec.text_height = _r(e.dxf.get("char_height", 2.5))
                rec.text_rotation = _r(e.get_rotation())
            else:
                rec.text_height = _r(e.dxf.get("height", 2.5))
                rec.text_rotation = _r(e.dxf.get("rotation", 0.0) or 0.0)
            try:
                rec.text = (e.plain_text() if t == "MTEXT" else str(e.dxf.get("text", "")))[:TEXT_MAX]
                rec.pos = _pt(e.dxf.insert)
            except Exception:  # noqa: BLE001
                pass
        elif t == "DIMENSION":
            rec.dim_text = str(e.dxf.get("text", "") or "")
            try:
                rec.dim_value = _r(e.get_measurement())
            except Exception:  # noqa: BLE001
                pass
            try:  # vị trí kích thước (để gán vào Tờ, khoanh vùng lỗi): điểm giữa chữ, thiếu thì điểm định nghĩa
                rec.pos = _pt(e.dxf.text_midpoint if e.dxf.hasattr("text_midpoint") else e.dxf.defpoint)
            except Exception:  # noqa: BLE001
                pass
        elif t == "INSERT":
            rec.block = str(e.dxf.name)
            rec.attribs = {str(a.dxf.tag): str(a.dxf.get("text", "")) for a in e.attribs}
            rec.insert = _pt(e.dxf.insert)
            rec.rotation = _r(e.dxf.get("rotation", 0.0) or 0.0)
            rec.xscale = _r(e.dxf.get("xscale", 1.0))
            rec.yscale = _r(e.dxf.get("yscale", 1.0))
    except Exception:  # noqa: BLE001
        pass
    return rec


def _paper_mm(layout) -> tuple[float | None, float | None]:
    try:
        d = layout.dxf_layout.dxf
        w, h = float(d.paper_width), float(d.paper_height)
        if int(d.get("plot_paper_units", 1)) == 0:  # 0 = inch
            w, h = w * 25.4, h * 25.4
        return (round(w, 2), round(h, 2)) if w > 0 and h > 0 else (None, None)
    except Exception:  # noqa: BLE001
        return (None, None)


def _viewport_rec(layout: str, vid: int, vp) -> ViewportRec:
    rec = ViewportRec(layout=layout, id=vid, scale=_viewport_scale(vp))
    try:
        c, vc = vp.dxf.center, vp.dxf.view_center_point
        rec.center = (_r(c.x), _r(c.y))
        rec.width, rec.height = _r(float(vp.dxf.width)), _r(float(vp.dxf.height))
        rec.view_center = (_r(vc.x), _r(vc.y))
        rec.view_height = _r(float(vp.dxf.view_height))
        rec.twist = _r(float(vp.dxf.get("view_twist_angle", 0.0) or 0.0))
    except Exception:  # noqa: BLE001 - khung nhìn thiếu mã: giữ phần đã đọc được
        pass
    return rec


def grow_extents(ext: list[float] | None, t: str, pts: list[tuple[float, float]], radius: float | None,
                 base: tuple[float, float]) -> list[float] | None:
    """Nới khung bao khối theo một đối tượng (dùng chung cho dxf_reader và dxf_stream để khớp từng bit)."""
    bx, by = base
    if t in ("CIRCLE", "ARC"):
        if not pts or radius is None:
            return ext
        cx, cy = pts[0]
        pts = [(cx - radius, cy - radius), (cx + radius, cy + radius)]
    for x, y in pts:
        x, y = x - bx, y - by
        if ext is None:
            ext = [x, y, x, y]
        else:
            ext[0], ext[1] = min(ext[0], x), min(ext[1], y)
            ext[2], ext[3] = max(ext[2], x), max(ext[3], y)
    return ext


def finish_extents(ext: list[float] | None) -> tuple[float, float, float, float] | None:
    return None if ext is None else (_r(ext[0]), _r(ext[1]), _r(ext[2]), _r(ext[3]))


EXTENT_TYPES = ("LINE", "LWPOLYLINE", "CIRCLE", "ARC", "TEXT", "MTEXT")


def _block_extent_pts(e, t: str) -> tuple[list[tuple[float, float]], float | None]:
    if t == "LINE":
        a, b = e.dxf.start, e.dxf.end
        return [(float(a.x), float(a.y)), (float(b.x), float(b.y))], None
    if t == "LWPOLYLINE":
        return [(float(x), float(y)) for x, y in e.get_points("xy")], None
    if t in ("CIRCLE", "ARC"):
        c = e.dxf.center
        return [(float(c.x), float(c.y))], float(e.dxf.radius)
    p = e.dxf.insert
    return [(float(p.x), float(p.y))], None


def _viewport_scale(vp) -> float | None:
    try:
        vh = float(vp.dxf.view_height)
        ph = float(vp.dxf.height)
        return ph / vh if vh > 0 and ph > 0 else None
    except Exception:  # noqa: BLE001
        return None



def _count_entity(stats: SpaceStats, e) -> None:
    """Đếm bản ghi chính, không bung nội dung INSERT hay đối tượng con."""
    t = e.dxftype()
    if t in {"ATTRIB", "VERTEX", "SEQEND"}:
        return
    layer = str(e.dxf.get("layer", "0"))
    stats.entities += 1
    stats.by_type[t] = stats.by_type.get(t, 0) + 1
    stats.by_layer[layer] = stats.by_layer.get(layer, 0) + 1
    color = e.dxf.get("color", None)
    lw = e.dxf.get("lineweight", None)
    stats.color_override += int(color is not None and color != 256)
    stats.lineweight_override += int(lw is not None and lw not in (-1, -2, -3))
    stats.true_color += int(e.dxf.get("true_color", None) is not None)
    stats.dim_total += int(t == "DIMENSION")
    if t == "DIMENSION":
        stats.dim_text_override += int((e.dxf.get("text", "") or "") not in ("", "<>"))
    stats.wipeout += int(t == "WIPEOUT")
    stats.image += int(t == "IMAGE")
    stats.ole += int(t in ("OLE2FRAME", "OLEFRAME"))
    stats.proxy += int(t == "ACAD_PROXY_ENTITY")


def _block_depth(name: str, blocks: dict[str, BlockRec], visiting: set[str]) -> int:
    # Một cạnh dẫn tới khối đã nằm trên đường đi bị cắt, không tính cạnh đó.
    block = blocks[name]
    visiting = visiting | {name}
    return max((1 + _block_depth(child, blocks, visiting)
                for child in block.child_blocks if child in blocks and child not in visiting), default=0)


TEXT_TYPES = ("TEXT", "MTEXT")


def is_non_ascii_text(s: str) -> bool:
    """Chữ có ký tự ngoài ASCII, hoặc mã Unicode/đa byte kiểu DXF (\\U+xxxx, \\M+nxxxx) chưa giải mã."""
    return not s.isascii() or "\\U+" in s or "\\M+" in s


def _count_text(counter: dict[str, int], e) -> None:
    t = e.dxftype()
    if t not in TEXT_TYPES:
        return
    content = e.text if t == "MTEXT" else str(e.dxf.get("text", "") or "")
    if is_non_ascii_text(content or ""):
        style = str(e.dxf.get("style", "Standard"))
        counter[style] = counter.get(style, 0) + 1


def _font_kind(font: str) -> str:
    ext = Path(font.replace("\\", "/")).suffix.lower()
    return "shx" if ext == ".shx" else "ttf" if ext in (".ttf", ".ttc", ".otf") else "other" if font else "none"

def build_model(doc, file_hash: str = "") -> DrawingModel:
    m = DrawingModel(file_hash=file_hash, dxf_version=str(doc.dxfversion))
    m.stats = ModelStats(source="ezdxf", modelspace=SpaceStats(), paperspace=SpaceStats(), blocks=SpaceStats())
    try:
        m.insunits = int(doc.header.get("$INSUNITS", 0))
    except Exception:  # noqa: BLE001
        m.insunits = None

    for layer in doc.layers:
        d = layer.dxf
        name = str(d.name)
        parts = re.split(r"\||\$0\$", name, maxsplit=1)
        m.layers.append(
            LayerRec(
                name=name,
                xref_dependent=bool(int(d.get("flags", 0)) & 16 or len(parts) > 1),
                xref_name=parts[0] if len(parts) > 1 else None,
                color=int(d.get("color", 7)),
                linetype=str(d.get("linetype", "Continuous")),
                lineweight=int(d.get("lineweight", -3)),
                frozen=bool(layer.is_frozen()),
                off=bool(layer.is_off()),
                plot=bool(d.get("plot", 1)),
            )
        )

    m.stats.layers_xref_dependent = sum(layer.xref_dependent for layer in m.layers)
    for style in doc.styles:
        try:
            if int(style.dxf.get("flags", 0)) & 1:
                m.stats.shape_styles += 1
                continue
            font = str(style.dxf.get("font", "") or "")
            try:
                family = str(style.get_extended_font_data()[0] or "")
            except Exception:  # noqa: BLE001
                family = ""
            m.styles.append(StyleRec(name=str(style.dxf.name), font=font,
                                     bigfont=str(style.dxf.get("bigfont", "") or ""), font_kind=_font_kind(font),
                                     family=family))
        except Exception:  # noqa: BLE001
            continue
    for style in doc.dimstyles:
        try:
            m.dim_styles.append(str(style.dxf.name))
        except Exception:  # noqa: BLE001
            continue

    block_layers: set[str] = set()
    for block in doc.blocks:
        try:
            name = str(block.name)
            is_layout = name.lower().startswith(("*model_space", "*paper_space"))
            kind = "named" if not name.startswith("*") else "anon_" + (name[1:2].upper() if name[1:2].upper() in "UDXA" else "other")
            rec = BlockRec(name=name, kind=kind, is_layout=is_layout,
                           is_xref=bool(int(block.block.dxf.get("flags", 0)) & 4))
            m.blocks.append(rec)
            if is_layout:
                continue
            ext = None
            try:
                bp = block.block.dxf.base_point
                base = (float(bp.x), float(bp.y))
            except Exception:  # noqa: BLE001
                base = (0.0, 0.0)
            for e in block:
                try:
                    t = e.dxftype()
                    if t in EXTENT_TYPES:
                        try:
                            pts, rad = _block_extent_pts(e, t)
                            ext = grow_extents(ext, t, pts, rad, base)
                        except Exception:  # noqa: BLE001
                            pass
                    if not name.startswith("*"):
                        block_layers.add(str(e.dxf.get("layer", "0")))
                    if t in {"ATTRIB", "VERTEX", "SEQEND"}:
                        continue
                    layer = str(e.dxf.get("layer", "0"))
                    rec.entity_count += 1
                    rec.types[t] = rec.types.get(t, 0) + 1
                    rec.layers[layer] = rec.layers.get(layer, 0) + 1
                    if t == "INSERT":
                        child = str(e.dxf.name)
                        rec.child_blocks[child] = rec.child_blocks.get(child, 0) + 1
                    _count_entity(m.stats.blocks, e)
                    _count_text(m.stats.text_non_ascii_by_style, e)
                except Exception:  # noqa: BLE001
                    continue
            rec.extents = finish_extents(ext)
        except Exception:  # noqa: BLE001
            continue
    m.block_layers = sorted(block_layers)
    lookup = {b.name.casefold(): b for b in m.blocks if not b.is_layout}
    # Tên khối trong DXF không phân biệt chữ hoa/thường.
    graph = {key: b.model_copy(update={"child_blocks": {n.casefold(): v for n, v in b.child_blocks.items()}}) for key, b in lookup.items()}
    for key, block in lookup.items():
        block.depth = _block_depth(key, graph, set())
    m.stats.blocks_named = sum(b.kind == "named" for b in lookup.values())
    m.stats.blocks_anonymous = sum(b.kind != "named" for b in lookup.values())
    m.stats.blocks_xref = sum(b.is_xref for b in lookup.values())
    m.stats.max_block_depth = max((b.depth for b in lookup.values()), default=0)

    for layout in doc.layouts:
        is_model = layout.name.lower() == "model"
        space = "Model" if is_model else layout.name
        lrec = None
        if not is_model:
            w, h = _paper_mm(layout)
            lrec = LayoutRec(name=layout.name, paper_w_mm=w, paper_h_mm=h)
            m.layouts.append(lrec)
        for e in layout:
            try:
                _count_entity(m.stats.modelspace if is_model else m.stats.paperspace, e)
                _count_text(m.stats.text_non_ascii_by_style, e)
            except Exception:  # noqa: BLE001
                pass
            if e.dxftype() == "VIEWPORT":
                vid = int(e.dxf.get("id", 0))
                if lrec is not None and vid != 1:  # id 1 = khung tờ giấy, không phải khung nhìn
                    lrec.viewports.append(_viewport_rec(layout.name, vid, e))
                continue
            try:
                m.entities.append(_entity_rec(e, space))
            except Exception:  # noqa: BLE001
                continue
    return m


def read_dxf(path: str | Path) -> DrawingModel:
    p = Path(path)
    data = p.read_bytes()
    h = hashlib.sha256(data).hexdigest()[:16]
    try:
        doc = ezdxf.readfile(p)
    except ezdxf.DXFError:  # DXF do bộ chuyển DWG sinh ra có thể lệch cấu trúc: thử đường khôi phục
        from ezdxf import recover

        doc, _auditor = recover.readfile(str(p))
    return build_model(doc, file_hash=h)
