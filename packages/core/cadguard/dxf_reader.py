"""Đọc DXF (ezdxf) -> Drawing Model. Không bao giờ ném lỗi vì một đối tượng lạ: đối tượng đọc không được bị bỏ qua."""

from __future__ import annotations

import hashlib
from pathlib import Path

import ezdxf
from ezdxf.math import Vec3

from .model import DrawingModel, EntityRec, LayerRec, LayoutRec, ViewportRec

Z_TOL = 1e-6
PROXY_TYPES = {"ACAD_PROXY_ENTITY", "PROXY", "ACAD_PROXY_OBJECT"}
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
        elif t == "LWPOLYLINE":
            rec.length, rec.area, rec.closed = _polyline_metrics(e)
        elif t == "CIRCLE":
            rec.dup_key = f"CIRCLE|{rec.layer}|{_pt(e.dxf.center)}|{_r(e.dxf.radius)}"
        elif t == "ARC":
            rec.dup_key = f"ARC|{rec.layer}|{_pt(e.dxf.center)}|{_r(e.dxf.radius)}|{_r(e.dxf.start_angle)}|{_r(e.dxf.end_angle)}"
        elif t in ("TEXT", "MTEXT"):
            rec.text_style = str(e.dxf.get("style", "Standard"))
        elif t == "DIMENSION":
            rec.dim_text = str(e.dxf.get("text", "") or "")
        elif t == "INSERT":
            rec.block = str(e.dxf.name)
            rec.attribs = {str(a.dxf.tag): str(a.dxf.get("text", "")) for a in e.attribs}
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


def _viewport_scale(vp) -> float | None:
    try:
        vh = float(vp.dxf.view_height)
        ph = float(vp.dxf.height)
        return ph / vh if vh > 0 and ph > 0 else None
    except Exception:  # noqa: BLE001
        return None


def build_model(doc, file_hash: str = "") -> DrawingModel:
    m = DrawingModel(file_hash=file_hash, dxf_version=str(doc.dxfversion))
    try:
        m.insunits = int(doc.header.get("$INSUNITS", 0))
    except Exception:  # noqa: BLE001
        m.insunits = None

    for layer in doc.layers:
        d = layer.dxf
        m.layers.append(
            LayerRec(
                name=str(d.name),
                color=int(d.get("color", 7)),
                linetype=str(d.get("linetype", "Continuous")),
                lineweight=int(d.get("lineweight", -3)),
                frozen=bool(layer.is_frozen()),
                off=bool(layer.is_off()),
                plot=bool(d.get("plot", 1)),
            )
        )

    block_layers: set[str] = set()
    for block in doc.blocks:
        if str(block.name).startswith("*"):
            continue
        for e in block:
            block_layers.add(str(e.dxf.get("layer", "0")))
    m.block_layers = sorted(block_layers)

    for layout in doc.layouts:
        is_model = layout.name.lower() == "model"
        space = "Model" if is_model else layout.name
        lrec = None
        if not is_model:
            w, h = _paper_mm(layout)
            lrec = LayoutRec(name=layout.name, paper_w_mm=w, paper_h_mm=h)
            m.layouts.append(lrec)
        for e in layout:
            if e.dxftype() == "VIEWPORT":
                vid = int(e.dxf.get("id", 0))
                if lrec is not None and vid != 1:  # id 1 = khung tờ giấy, không phải khung nhìn
                    lrec.viewports.append(ViewportRec(layout=layout.name, id=vid, scale=_viewport_scale(e)))
                continue
            m.entities.append(_entity_rec(e, space))
    return m


def read_dxf(path: str | Path) -> DrawingModel:
    p = Path(path)
    data = p.read_bytes()
    h = hashlib.sha256(data).hexdigest()[:16]
    doc = ezdxf.readfile(p)
    return build_model(doc, file_hash=h)
