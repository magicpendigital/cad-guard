"""3D-1: đọc mặt bằng (và cụm hình trong mặt đứng) theo hình học + kích thước tất định.

- **Cụm đồ** (`components`): đối tượng cùng nhóm vai trò layer chạm nhau (nới vài mm trên giấy) là một cụm; khung bao
  là kích thước đo từ hình. Mỗi cạnh được **xác nhận** khi có DIMENSION đo đúng đoạn đó (hai điểm đo trùng hai mép,
  số đo khớp): `source = "dimension"` kèm handle; không có thì `source = "geometry"` (vẫn là số đo trên bản vẽ, chưa
  có kích thước ghi).
- **Tường** (`read_walls`): (a) cặp đa tuyến khép kín lồng nhau trên layer tường (tường đôi: ngoài/trong) -> phòng là
  đa giác trong, dày tường = khoảng lệch; (b) hình chữ nhật mảnh trên layer tường -> đoạn tường có dày; (c) đoạn
  thẳng đơn trên layer tường -> mặt tường (chưa biết dày: `thickness_source = "default"`).
- Không đoán: phần không đo được để trống, nơi dùng sẽ tạo `gaps[]`.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field

from ..model import EntityRec
from .views2d import GAP_PAPER_MM, Box4, Dim, Drawing2D, View, _bbox, _clusters, _union, confirm, entity_box, rect_of, view_dims

DEFAULT_WALL_MM = 100.0  # dày tường mặc định khi bản vẽ chỉ có một mặt tường (đánh dấu "default")


@dataclass
class Measured:
    value: float
    source: str  # dimension | geometry | user | default
    refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"value": round(self.value, 3), "source": self.source, "refs": self.refs}


@dataclass
class Component:
    id: str
    view_id: str
    box: Box4
    handles: list[str]
    w: Measured
    h: Measured  # theo trục Y của hình (sâu ở mặt bằng, cao ở mặt đứng)
    rects: list[Box4] = field(default_factory=list)
    parts: list[Box4] = field(default_factory=list)  # khung bao từng nét trong cụm

    def to_dict(self) -> dict:
        return {"id": self.id, "view": self.view_id, "box": [round(v, 3) for v in self.box], "entities": len(self.handles),
                "w": self.w.to_dict(), "h": self.h.to_dict(), "rects": len(self.rects)}


def tol_for(span: float) -> float:
    return max(1.0, 0.0015 * span)


def measure_span(dims: list[Dim], axis: str, lo: float, hi: float) -> Measured:
    d = confirm(dims, axis, lo, hi, tol_for(hi - lo))
    if d is not None:
        return Measured(d.value, "dimension", [d.handle])
    return Measured(hi - lo, "geometry")


def components(d: Drawing2D, v: View, roles: frozenset[str], min_size: float = 50.0, gap_mm: float = 1.0) -> list[Component]:
    """Cụm hình của các vai trò `roles` trong hình chiếu `v` (gap: mm trên giấy)."""
    ents = [d.entities[h] for h in v.handles
            if d.roles.get(d.entities[h].layer) in roles and d.entities[h].type not in ("TEXT", "MTEXT", "DIMENSION", "INSERT", "HATCH")]
    items = [(e.handle, b) for e in ents if (b := entity_box(e, {})) is not None]
    dims = view_dims(d, v)
    out: list[Component] = []
    for g in _clusters(items, gap_mm * v.factor):
        box = _union(items[i][1] for i in g)
        if box is None or (box[2] - box[0]) < min_size or (box[3] - box[1]) < min_size:
            continue
        hs = sorted(items[i][0] for i in g)
        rects = [r for h in hs if (r := rect_of(d.entities[h])) is not None]
        out.append(Component("", v.id, box, hs, measure_span(dims, "h", box[0], box[2]), measure_span(dims, "v", box[1], box[3]), rects,
                             [items[i][1] for i in g]))
    out.sort(key=lambda c: (c.box[0], c.box[1]))
    for i, c in enumerate(out, 1):
        c.id = f"{v.id}:C{i}"
    return out


def attached_dims(d: Drawing2D, v: View, roles: frozenset[str]) -> tuple[int, int]:
    """(số kích thước thẳng ngang/dọc, số kích thước có cả hai điểm đo nằm trên toạ độ đỉnh của hình)."""
    xs: list[float] = []
    ys: list[float] = []
    for h in v.handles:
        e = d.entities[h]
        if d.roles.get(e.layer) in roles and e.pts:
            for x, y in e.pts:
                xs.append(x)
                ys.append(y)
    xs.sort()
    ys.sort()

    def near(arr, val, tol=1.0):
        i = bisect.bisect_left(arr, val - tol)
        return i < len(arr) and arr[i] <= val + tol

    total = ok = 0
    for x in view_dims(d, v):
        if x.axis not in ("h", "v"):
            continue
        total += 1
        arr = xs if x.axis == "h" else ys
        if near(arr, x.lo) and near(arr, x.hi):
            ok += 1
    return total, ok


# ---------------- tường, phòng ----------------

@dataclass
class WallSeg:
    id: str
    start: tuple[float, float]
    end: tuple[float, float]
    thickness: float
    thickness_source: str  # geometry | default | user
    refs: list[str]


@dataclass
class Room:
    id: str
    polygon: list[tuple[float, float]]
    box: Box4
    w: Measured
    d: Measured
    refs: list[str]
    label: str = ""


def _contains(a: Box4, b: Box4, tol: float = 1e-6) -> bool:
    return a[0] - tol <= b[0] and a[1] - tol <= b[1] and a[2] + tol >= b[2] and a[3] + tol >= b[3]


def read_walls(d: Drawing2D, v: View) -> tuple[list[WallSeg], list[Room]]:
    ents = [d.entities[h] for h in v.handles if d.roles.get(d.entities[h].layer) == "wall"]
    dims = view_dims(d, v)
    closed = [(e, _bbox(e.pts)) for e in ents if e.type == "LWPOLYLINE" and e.closed and e.pts and len(e.pts) >= 3]
    walls: list[WallSeg] = []
    rooms: list[Room] = []
    used: set[str] = set()
    # (a) tường đôi: đa giác trong nằm trong đa giác ngoài, lệch đều (± 2 %)
    for inner, ib in sorted(closed, key=lambda t: (t[1][2] - t[1][0]) * (t[1][3] - t[1][1])):
        if inner.handle in used:
            continue
        for outer, ob in closed:
            if outer is inner or outer.handle in used or not _contains(ob, ib) or ob == ib:
                continue
            offs = (ib[0] - ob[0], ib[1] - ob[1], ob[2] - ib[2], ob[3] - ib[3])
            t = min(offs)
            if t <= 0 or max(offs) > t * 1.02 + 1.0 or t > 0.25 * min(ib[2] - ib[0], ib[3] - ib[1]):
                continue
            used |= {inner.handle, outer.handle}
            pts = list(inner.pts)
            if len(pts) > 1 and math.dist(pts[0], pts[-1]) < 1e-6:
                pts = pts[:-1]
            # đoạn tường = cạnh đa giác trong dời ra ngoài nửa dày (đường tim)
            cx, cy = (ib[0] + ib[2]) / 2, (ib[1] + ib[3]) / 2
            for i, (a, b) in enumerate(zip(pts, pts[1:] + pts[:1])):
                dx, dy = b[0] - a[0], b[1] - a[1]
                n = math.hypot(dx, dy) or 1.0
                nx, ny = dy / n, -dx / n
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                if (mx + nx - cx) ** 2 + (my + ny - cy) ** 2 < (mx - cx) ** 2 + (my - cy) ** 2:
                    nx, ny = -nx, -ny
                off = t / 2
                walls.append(WallSeg(f"{v.id}:W{len(walls) + 1}", (a[0] + nx * off, a[1] + ny * off),
                                     (b[0] + nx * off, b[1] + ny * off), t, "geometry", [inner.handle, outer.handle]))
            rooms.append(Room(f"{v.id}:R{len(rooms) + 1}", pts, ib, measure_span(dims, "h", ib[0], ib[2]),
                              measure_span(dims, "v", ib[1], ib[3]), [inner.handle, outer.handle]))
            break
    # (b) hình chữ nhật mảnh trên layer tường
    for e in ents:
        if e.handle in used:
            continue
        r = rect_of(e)
        if r is None:
            continue
        w, h = r[2] - r[0], r[3] - r[1]
        t, ln = min(w, h), max(w, h)
        if 50 <= t <= 600 and ln >= 3 * t:
            used.add(e.handle)
            if w >= h:
                a, b = (r[0], (r[1] + r[3]) / 2), (r[2], (r[1] + r[3]) / 2)
            else:
                a, b = ((r[0] + r[2]) / 2, r[1]), ((r[0] + r[2]) / 2, r[3])
            walls.append(WallSeg(f"{v.id}:W{len(walls) + 1}", a, b, t, "geometry", [e.handle]))
    # (c) đoạn thẳng đơn: mặt tường
    for e in ents:
        if e.handle in used or e.type != "LINE" or not e.pts:
            continue
        a, b = e.pts[0], e.pts[1]
        if math.dist(a, b) < 200:
            continue
        walls.append(WallSeg(f"{v.id}:W{len(walls) + 1}", a, b, DEFAULT_WALL_MM, "default", [e.handle]))
    return walls, rooms


def room_label(d: Drawing2D, v: View, room: Room) -> str:
    """Chữ dài nhất nằm trong phòng (tên phòng). Chữ của bản vẽ: dữ liệu cục bộ."""
    from ..textcodec import entity_text

    best = ""
    for h in v.handles:
        e = d.entities[h]
        if e.type in ("TEXT", "MTEXT") and e.text and e.pos and _contains(room.box, (e.pos[0], e.pos[1], e.pos[0], e.pos[1])):
            t, _ = entity_text(e, d.enc, d.guess)
            t = " ".join(t.split())
            if len(t) > len(best):
                best = t
    return best


__all__ = ["Component", "Measured", "Room", "WallSeg", "attached_dims", "components", "measure_span", "read_walls",
           "room_label", "tol_for"]
