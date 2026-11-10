"""3D-0: đo khả năng dựng 3D từ một bản vẽ 2D thật. Chỉ SỐ CẤU TRÚC (đếm, tỉ lệ): không chữ, không tên, không toạ độ.

Kết quả `cg.scene-feasibility/1` dùng cho `docs/3d-feasibility.md` và lệnh `cadguard scene-assess`.
"""

from __future__ import annotations

from collections import Counter

from ..model import DrawingModel
from .plan import attached_dims, components, read_walls
from .views2d import BODY_ROLES, FURNITURE_ROLES_DEFAULT, Drawing2D, read_drawing, view_dims

SCHEMA = "cg.scene-feasibility/1"
FURNITURE_ROLES = FURNITURE_ROLES_DEFAULT


def _pct(a: int, b: int) -> float | None:
    return round(100.0 * a / b, 1) if b else None


def common_width_dim(d: Drawing2D, plan, elev, tol: float = 1.0):
    """Kích thước ngang có cùng số đo ở cả mặt bằng và mặt đứng (lớn nhất): căn trục X hai hình theo nó."""
    ph = [x for x in view_dims(d, plan) if x.axis == "h"]
    eh = [x for x in view_dims(d, elev) if x.axis == "h"]
    best = None
    for a in ph:
        for b in eh:
            if abs(a.value - b.value) <= tol and (best is None or a.value > best[0].value):
                best = (a, b)
    return best


def room_height_dim(d: Drawing2D, elev):
    """Kích thước dọc lớn nhất của mặt đứng chạm đáy hình (sàn): cao sàn–trần."""
    vs = [x for x in view_dims(d, elev) if x.axis == "v"]
    if not vs or elev.box is None:
        return None
    top = max(vs, key=lambda x: x.value)
    return top if abs(top.lo - elev.box[1]) <= max(2.0, 0.002 * top.value) else None


def assess(model: DrawingModel, d: Drawing2D | None = None) -> dict:
    d = d or read_drawing(model)
    views = d.views
    kinds = Counter(v.kind for v in views)
    with_geo = Counter(v.kind for v in views if v.handles and v.box)
    # hạng mục
    items = {}
    for g in d.groups:
        vs = d.views_of(g)
        items[g] = {"plan": [v for v in vs if v.kind == "plan" and v.box], "elevation": [v for v in vs if v.kind == "elevation" and v.box],
                    "section": [v for v in vs if v.kind == "section" and v.box]}
    both = [g for g, x in items.items() if x["plan"] and x["elevation"]]
    aligned = 0
    for g in both:
        if any(common_width_dim(d, p, e) for p in items[g]["plan"] for e in items[g]["elevation"]):
            aligned += 1
    # kích thước
    dims_total = sum(1 for e in model.entities if e.space == "Model" and e.type == "DIMENSION")
    dims_linear = sum(1 for e in model.entities if e.space == "Model" and e.type == "DIMENSION" and e.dim_pts)
    in_views = att = 0
    for v in views:
        if v.kind in ("plan", "elevation", "section") and v.box:
            t, ok = attached_dims(d, v, BODY_ROLES)
            in_views += t
            att += ok
    # cụm đồ (mặt bằng / mặt đứng hạng mục): khung bao + xác nhận cạnh bằng kích thước
    comp = {"plan": [0, 0, 0], "elevation": [0, 0, 0]}  # [số cụm, rộng có kích thước, rộng+cao/sâu có kích thước]
    for v in views:
        if v.kind in comp and v.box and v.group:
            for c in components(d, v, FURNITURE_ROLES, min_size=200.0):
                comp[v.kind][0] += 1
                comp[v.kind][1] += c.w.source == "dimension"
                comp[v.kind][2] += c.w.source == "dimension" and c.h.source == "dimension"
    elev_h = sum(1 for v in views if v.kind == "elevation" and v.box and room_height_dim(d, v))
    n_elev = with_geo.get("elevation", 0)
    # mặt bằng tổng (tầng): tường, phòng
    walls = rooms = wall_default = 0
    for v in views:
        if v.kind == "plan" and v.box:
            ws, rs = read_walls(d, v)
            walls += len(ws)
            wall_default += sum(1 for w in ws if w.thickness_source == "default")
            rooms += len(rs)
    marks = d.marks
    return {
        "schema": SCHEMA,
        "file_hash": model.file_hash,
        "sheets": {"total": len(d.structure.sheets), "frames": sum(1 for s in d.structure.sheets if s.kind == "frame")},
        "layer_roles": dict(Counter(d.roles.values())),
        "views": {"by_kind": dict(kinds), "with_geometry": dict(with_geo)},
        "items": {"total": len(items), "with_plan_and_elevation": len(both), "with_section": sum(1 for x in items.values() if x["section"]),
                  "plan_elevation_aligned_by_dimension": aligned},
        "section_marks": {"total": len(marks), "resolved": sum(1 for m in marks if m.target),
                          "resolved_pct": _pct(sum(1 for m in marks if m.target), len(marks))},
        "dimensions": {"total": dims_total, "linear_with_points": dims_linear, "in_views_hv": in_views,
                       "attached_to_geometry": att, "attached_pct": _pct(att, in_views)},
        "furniture_components": {
            k: {"count": c[0], "width_dimensioned": c[1], "both_dimensioned": c[2], "both_pct": _pct(c[2], c[0])}
            for k, c in comp.items()},
        "elevations_with_room_height_dim": {"count": elev_h, "of": n_elev, "pct": _pct(elev_h, n_elev)},
        "floor_plan": {"wall_segments": walls, "wall_segments_default_thickness": wall_default, "rooms": rooms},
    }


__all__ = ["SCHEMA", "assess", "common_width_dim", "room_height_dim"]
