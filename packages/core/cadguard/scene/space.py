"""Dựng cả không gian (cả tầng) `cg.space/1` từ mặt bằng tổng + các hạng mục đã dựng (5 bậc, xem
`docs/research/phoi-canh-ca-khong-gian.md`).

Tất định; mọi số có nguồn (`dimension` | `geometry` | `user` | `default`). Chỗ không chắc thành việc cần làm (`tasks`),
không tự đoán.

1. Khung phòng: mặt bằng tổng = hình mặt bằng có nhiều ký hiệu số hạng mục nhất. Tường = đa giác kín nét cắt/nét tường
   (cách vẽ tường dày + cột). Cao tường = trung vị cao sàn–trần ghi trên các mặt đứng hạng mục; không có thì mặc định.
   Phòng = chữ diện tích "S = … m2" + tên ngay phía trên.
2. Đặt hạng mục: ký hiệu số trên mặt bằng tổng (chữ đúng bằng phần số của mã hạng mục, không nằm trong cột chú thích)
   cho biết hạng mục ở đâu; xoay (0/90/180/270) và dời được tính bằng cách khớp đầu mút nét của mặt bằng chi tiết với nét
   mặt bằng tổng quanh ký hiệu (bỏ phiếu). Khớp yếu → việc cần làm; người dùng chọn góc xoay (`place:<mã>`).
3. Đồ rời: block trên layer nội thất ngoài các hạng mục đã đặt → hộp theo khung block, cao theo bảng mặc định.
4. Cửa: block trên layer cửa → cánh cửa + lanh tô phía trên; cao cửa mặc định, người dùng sửa (`space:door_h`).
5. Xuất: hộp cho trình xem + GLB cả tầng (`render_space_glb`).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics

from .assemble import build_item_scene
from .views2d import Drawing2D, View, entity_box

SCHEMA = "cg.space/1"
TAG_H_MIN = 60.0  # chữ ký hiệu nhỏ hơn: số bậc thang, số trục…
DEFAULT_CEILING = 2800.0
DEFAULT_DOOR_H = 2200.0
DOOR_MAX_W = 2400.0  # block cửa rộng hơn: vách kính/cửa trượt nhiều cánh, chưa dựng
WALL_MIN_AREA = 20000.0  # mm²: đa giác nhỏ hơn không phải tường/cột
LOOSE_H = [  # (từ khoá trong tên block, cao mm) — chỉ để xem bố cục; luôn nhãn "Mặc định"
    (("sofa", "sopha"), 800.0), (("bed", "giuong", "giường"), 500.0), (("chair", "ghe", "ghế"), 850.0),
    (("table", "ban", "bàn", "desk"), 750.0), (("fridge", "tulanh", "tủ lạnh", "refrig"), 1800.0),
    (("toilet", "toto", "wc", "lavabo", "basin", "sink"), 800.0), (("hob", "bep", "bếp", "cooker", "elextrulux", "electrolux"), 900.0),
    (("cay", "cây", "plant", "tree"), 1200.0),
]
LOOSE_DEFAULT_H = 750.0


def _f(v: float) -> float:
    return round(float(v), 1)


def tag_number(group: str) -> str | None:
    m = re.search(r"(\d+)\s*$", group or "")
    return m.group(1) if m else None


def _texts(d: Drawing2D, v: View):
    for h in v.handles:
        e = d.entities[h]
        if e.type in ("TEXT", "MTEXT") and e.text and (e.pos or e.insert):
            yield e, (e.pos or e.insert)


def find_tags(d: Drawing2D, v: View) -> dict[str, list[tuple[float, float]]]:
    """Ký hiệu số hạng mục trên một mặt bằng: {mã hạng mục: [vị trí]}. Bỏ cột chú thích (≥ 3 số thẳng hàng dọc)."""
    nums = {tag_number(g): g for g in d.groups if tag_number(g)}
    hits = [(nums[t], p) for e, p in _texts(d, v) if (t := e.text.strip()) in nums and (e.text_height or 0) >= TAG_H_MIN * v.factor / 50]
    out: dict[str, list] = {}
    for g, p in hits:
        column = sum(1 for _g2, q in hits if abs(q[0] - p[0]) <= 80 and abs(q[1] - p[1]) > 1)
        if column >= 2:  # bảng chú thích: các số xếp thẳng cột
            continue
        out.setdefault(g, []).append(p)
    return out


def master_plan(d: Drawing2D) -> View | None:
    best, score = None, (0, 0.0)
    for v in d.views:
        if v.kind != "plan" or not v.box:
            continue
        sc = (len(find_tags(d, v)), (v.box[2] - v.box[0]) * (v.box[3] - v.box[1]))
        if sc[0] and sc > score:
            best, score = v, sc
    return best


# ---------------- bậc 1: tường, phòng ----------------

def _area(pts) -> float:
    return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))) / 2


WALL_MAX_T = 600.0  # bề dày quy đổi 2·diện tích/chu vi: lớn hơn là đường bao phòng/sàn, không phải tường


def _perim(pts) -> float:
    return sum(math.dist(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))


def _signed(pts) -> float:
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))) / 2


def _pip(p, poly) -> bool:
    x, y, inside = p[0], p[1], False
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def _keyhole(outer, inner):
    """Đa giác có lỗ (tường vẽ bằng hai đường bao lồng nhau) -> một đa giác nối bằng khe rộng 0."""
    outer = outer if _signed(outer) > 0 else outer[::-1]
    inner = inner if _signed(inner) < 0 else inner[::-1]
    i, j = min(((i, j) for i in range(len(inner)) for j in range(len(outer))), key=lambda t: math.dist(inner[t[0]], outer[t[1]]))
    ring = inner[i:] + inner[:i] + [inner[i]]
    return outer[:j + 1] + ring + outer[j:]


def walls_of(d: Drawing2D, v: View) -> list[list[tuple[float, float]]]:
    """Tường/cột: đa giác kín nét cắt/nét tường mảnh (bề dày quy đổi ≤ 600). Hai đường bao lồng nhau = một vành tường."""
    polys = []
    for h in v.handles:
        e = d.entities[h]
        if e.type != "LWPOLYLINE" or d.roles.get(e.layer) not in ("cut", "wall") or not e.pts:
            continue
        pts = list(e.pts)
        if len(pts) > 2 and math.dist(pts[0], pts[-1]) < 1e-6:
            pts = pts[:-1]
        if not (e.closed or len(e.pts) > 3 and math.dist(e.pts[0], e.pts[-1]) < 1.0) or len(pts) < 3:
            continue
        if _area(pts) >= WALL_MIN_AREA:
            polys.append(pts)
    polys.sort(key=_area, reverse=True)
    used, out = set(), []
    for i, a in enumerate(polys):
        if i in used:
            continue
        hole = next((j for j in range(i + 1, len(polys)) if j not in used and all(_pip(q, a) for q in polys[j])), None)
        if hole is not None:
            ring_area = _area(a) - _area(polys[hole])
            if 2 * ring_area / (_perim(a) + _perim(polys[hole])) <= WALL_MAX_T:
                used.add(hole)
                out.append(_keyhole(a, polys[hole]))
                continue
        if 2 * _area(a) / _perim(a) <= WALL_MAX_T:
            out.append(a)
    return out + _paired_walls(d, v)


PAIR_MIN, PAIR_MAX = 60.0, 450.0  # khoảng cách hai nét song song của một bức tường


def _paired_walls(d: Drawing2D, v: View) -> list[list[tuple[float, float]]]:
    """Tường vẽ bằng hai nét song song hở (LINE / polyline hở trên layer tường, nét cắt): ghép từng cặp gần nhất
    thành tấm tường theo đoạn chồng nhau."""
    segs = []
    for h in v.handles:
        e = d.entities[h]
        if d.roles.get(e.layer) not in ("cut", "wall") or e.type not in ("LINE", "LWPOLYLINE") or not e.pts:
            continue
        if e.type == "LWPOLYLINE" and (e.closed or len(e.pts) > 3 and math.dist(e.pts[0], e.pts[-1]) < 1.0):
            continue  # đa giác kín đã xét ở trên
        segs += [(a, b) for a, b in zip(e.pts, e.pts[1:]) if math.dist(a, b) >= 300.0]
    used: set[int] = set()
    out = []
    for i, (a, b) in enumerate(segs):
        if i in used:
            continue
        L = math.dist(a, b)
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        best = None
        for j in range(i + 1, len(segs)):
            if j in used:
                continue
            c, e2 = segs[j]
            L2 = math.dist(c, e2)
            vx, vy = (e2[0] - c[0]) / L2, (e2[1] - c[1]) / L2
            if abs(ux * vy - uy * vx) > 0.035:  # không song song (≈ 2°)
                continue
            dist = abs((c[0] - a[0]) * uy - (c[1] - a[1]) * ux)
            if not PAIR_MIN <= dist <= PAIR_MAX:
                continue
            t0, t1 = sorted(((c[0] - a[0]) * ux + (c[1] - a[1]) * uy, (e2[0] - a[0]) * ux + (e2[1] - a[1]) * uy))
            lo, hi = max(0.0, t0), min(L, t1)
            if hi - lo < 0.5 * min(L, L2):
                continue
            if best is None or dist < best[0]:
                best = (dist, j, lo, hi)
        if best is None:
            continue
        dist, j, lo, hi = best
        used |= {i, j}
        c = segs[j][0]
        side = 1.0 if ((c[0] - a[0]) * -uy + (c[1] - a[1]) * ux) > 0 else -1.0
        nx, ny = -uy * side * dist, ux * side * dist
        p0 = (a[0] + ux * lo, a[1] + uy * lo)
        p1 = (a[0] + ux * hi, a[1] + uy * hi)
        out.append([p0, p1, (p1[0] + nx, p1[1] + ny), (p0[0] + nx, p0[1] + ny)])
    return out


def rooms_of(d: Drawing2D, v: View) -> list[dict]:
    from .explain import _vi

    texts = list(_texts(d, v))
    out = []
    for e, p in texts:
        m = re.search(r"S\s*=\s*([\d.,]+)\s*m", _vi(e.text))
        if not m:
            continue
        above = [(q[1] - p[1], e2) for e2, q in texts if e2 is not e and 0 < q[1] - p[1] <= 900 and abs(q[0] - p[0]) <= 1500]
        name = _vi(min(above, key=lambda t: t[0])[1].text).strip() if above else ""
        out.append({"name": name[:40], "area_m2": float(m.group(1).replace(",", ".")), "pos": p})
    return out


# ---------------- bậc 2: đặt hạng mục ----------------

def _endpoints(d: Drawing2D, handles, roles=("furniture", "cut", "thin", "wall", "hidden", "visible")) -> list[tuple[float, float]]:
    pts: set[tuple[float, float]] = set()
    for h in handles:
        e = d.entities[h]
        if d.roles.get(e.layer) in roles and e.type in ("LINE", "LWPOLYLINE") and e.pts:
            for x, y in e.pts:
                pts.add((round(x), round(y)))
    return sorted(pts)


def _rot(p, k):
    x, y = p
    return [(x, y), (-y, x), (-x, -y), (y, -x)][k % 4]


def _segs(d: Drawing2D, handles, roles=("furniture", "cut", "thin", "wall", "visible")) -> list[tuple]:
    out = []
    for h in handles:
        e = d.entities[h]
        if d.roles.get(e.layer) in roles and e.type in ("LINE", "LWPOLYLINE") and e.pts and len(e.pts) >= 2:
            pts = list(e.pts) + ([e.pts[0]] if e.closed else [])
            out += [(a, b) for a, b in zip(pts, pts[1:]) if math.dist(a, b) >= 50.0]
    return out


def _samples(segs, step: float = 60.0) -> list[tuple[float, float]]:
    out = []
    for (x0, y0), (x1, y1) in segs:
        n = max(1, int(math.dist((x0, y0), (x1, y1)) // step))
        out += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n + 1)]
    return out


def _grid(pts, cell: float = 20.0) -> set:
    return {(round(x / cell), round(y / cell)) for x, y in pts}


def _cover(pts, grid, cell: float = 20.0) -> float:
    hit = sum(1 for x, y in pts if any((round(x / cell) + a, round(y / cell) + b) in grid for a in (-1, 0, 1) for b in (-1, 0, 1)))
    return hit / max(len(pts), 1)


def register(src_pts: list, src_samples: list, dst_pts: list, dst_grid: set, ks=(0, 1, 2, 3), center=None, near=None,
             bin_mm: float = 10.0, top: int = 25) -> tuple[float, int, tuple[float, float]]:
    """Khớp nét mặt bằng chi tiết vào mặt bằng tổng: xoay bội 90° + dời. Ứng viên dời lấy từ bỏ phiếu đầu mút; chấm điểm
    bằng tỷ lệ điểm lấy mẫu dọc nét chi tiết nằm trên nét mặt bằng tổng. `center`/`near`: tâm hình chi tiết phải rơi
    trong bán kính `near` quanh ký hiệu. Trả (độ phủ 0..1, k, dời)."""
    best = (0.0, 0, (0.0, 0.0))
    if not src_pts or not dst_pts:
        return best
    for k in ks:
        votes: dict[tuple[int, int], int] = {}
        for p in src_pts:
            rx, ry = _rot(p, k)
            for qx, qy in dst_pts:
                key = (round((qx - rx) / bin_mm), round((qy - ry) / bin_mm))
                votes[key] = votes.get(key, 0) + 1
        for key in sorted(votes, key=votes.get, reverse=True)[:top]:
            t = (key[0] * bin_mm, key[1] * bin_mm)
            if center is not None and near is not None:
                cx, cy = _rot(center[0], k)
                if math.dist((cx + t[0], cy + t[1]), center[1]) > near:
                    continue
            sc = _cover([(_rot(q, k)[0] + t[0], _rot(q, k)[1] + t[1]) for q in src_samples], dst_grid)
            if sc > best[0]:
                best = (sc, k, t)
    return best


COVER_MIN = 0.45  # tỷ lệ nét chi tiết trùng nét mặt bằng tổng để coi là đặt chắc


def _item_plan(sc, d: Drawing2D) -> View | None:
    pid = next((m.plan for m in sc.modules if m.plan), None)
    return d.view(pid) if pid else None


def place_item(d: Drawing2D, sc, master: View, tag: tuple[float, float], user: str | None) -> dict:
    p = _item_plan(sc, d)
    if p is None or not sc.modules:
        return {"placed": False, "reason": "Hạng mục chưa dựng được khối 3D (xem màn 3D của hạng mục)."}
    src = _endpoints(d, p.handles)[:300]
    samples = _samples(_segs(d, p.handles))[:3000]
    span = max(p.box[2] - p.box[0], p.box[3] - p.box[1])
    r = span + 1500.0
    dst = [q for q in _endpoints(d, master.handles) if abs(q[0] - tag[0]) <= r and abs(q[1] - tag[1]) <= r]
    grid = _grid(_samples([sg for sg in _segs(d, master.handles)
                           if min(abs(sg[0][0] - tag[0]), abs(sg[1][0] - tag[0])) <= r + 3000
                           and min(abs(sg[0][1] - tag[1]), abs(sg[1][1] - tag[1])) <= r + 3000], 20.0))
    ks = (0, 1, 2, 3)
    method = "match"
    if user and user.strip() in ("0", "90", "180", "270"):
        ks = (int(user) // 90,)
        method = "user"
    pc = ((p.box[0] + p.box[2]) / 2, (p.box[1] + p.box[3]) / 2)
    cov, k, t = register(src, samples, dst, grid, ks, center=(pc, tag), near=span / 2 + 1500.0)
    if cov < COVER_MIN:
        if method != "user":
            return {"placed": False, "score": round(cov, 2),
                    "reason": f"Chỉ {round(cov * 100)}% nét mặt bằng chi tiết trùng nét mặt bằng tổng quanh ký hiệu số: chưa chắc vị trí."}
        rx, ry = _rot(pc, k)  # người chọn góc xoay: đặt tâm hình vào ký hiệu
        t = (tag[0] - rx, tag[1] - ry)
        method = "user_tag"
    ox, oy = p.box[0], p.box[1]  # gốc toạ độ khối của hạng mục (assemble: origin = góc mặt bằng)
    mods = []
    for m in sc.modules:
        corners = [(ox + m.x, oy + m.y), (ox + m.x + m.w, oy + m.y), (ox + m.x + m.w, oy + m.y + m.d), (ox + m.x, oy + m.y + m.d)]
        base = [(_rot(c, k)[0] + t[0], _rot(c, k)[1] + t[1]) for c in corners]
        mods.append({"id": m.id, "kind": m.kind, "form": m.form, "base": base, "z0": m.z0, "z1": m.z0 + m.h,
                     "src_d": m.src["d"].kind if "d" in m.src else "missing"})
    return {"placed": True, "method": method, "rot": k * 90, "score": round(cov, 2), "modules": mods}


# ---------------- bậc 3, 4: đồ rời, cửa ----------------

def _loose_h(name: str) -> float:
    s = (name or "").casefold()
    for keys, h in LOOSE_H:
        if any(k in s for k in keys):
            return h
    return LOOSE_DEFAULT_H


def _inside_any(b, footprints) -> bool:
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    return any(f[0] <= cx <= f[2] and f[1] <= cy <= f[3] for f in footprints)


def _rect(b):
    return [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])]


# ---------------- dựng ----------------

def build_space(model, d: Drawing2D, supplement_of=None, supp: dict | None = None) -> dict:
    """`supplement_of(item) -> dict`: bổ sung của từng hạng mục (số người nhập ở màn 3D). `supp`: khoá cả tầng
    (`place:<mã>`, `space:ceiling`, `space:door_h`)."""
    supp = supp or {}
    master = master_plan(d)
    out = {"schema": SCHEMA, "source_hash": model.file_hash, "plan": None, "walls": [], "rooms": [], "items": [],
           "loose": [], "doors": [], "tasks": [], "notes": [], "ceiling": None}
    if master is None:
        out["tasks"].append({"id": "space:plan", "title": "Không tìm thấy mặt bằng tổng",
                             "why": "CAD Guard nhận mặt bằng tổng là hình mặt bằng có ký hiệu số của ít nhất hai hạng mục "
                                    "(số trùng phần số của mã hạng mục trong khung tên).",
                             "fix_cad": "Trên mặt bằng bố trí nội thất, ghi số hạng mục (vd. 64) ngay tại vị trí từng hạng mục."})
        return out
    ox, oy = master.box[0], master.box[1]
    loc = lambda p: (_f(p[0] - ox), _f(p[1] - oy))  # noqa: E731
    out["plan"] = {"id": master.id, "title": master.title, "sheet": master.sheet_id}
    tags = find_tags(d, master)

    # bậc 2 trước (cần cao trần từ các hạng mục)
    ceilings, footprints = [], []
    for g, pos in tags.items():
        sc = build_item_scene(d, g, supplement_of(g) if supplement_of else {})
        if sc.room.ceiling and "ceiling" in sc.room.src and sc.room.src["ceiling"].kind in ("dimension", "user"):
            ceilings.append(sc.room.ceiling)
        r = place_item(d, sc, master, pos[0], supp.get(f"place:{g}"))
        name = str((d.groups.get(g) or {}).get("name") or g)
        from .explain import _vi

        item = {"item": g, "name": _vi(name), "tag": loc(pos[0]), **{k: v for k, v in r.items() if k != "modules"}}
        if r.get("placed"):
            item["modules"] = [{**m, "base": [loc(c) for c in m["base"]]} for m in r["modules"]]
            xs = [c[0] for m in r["modules"] for c in m["base"]]
            ys = [c[1] for m in r["modules"] for c in m["base"]]
            footprints.append((min(xs), min(ys), max(xs), max(ys)))
        else:
            out["tasks"].append({"id": f"place:{g}", "item": g, "title": f"Chưa đặt được hạng mục {item['name']}",
                                 "why": r.get("reason", ""), "fix_here": "Chọn góc xoay của hạng mục (0/90/180/270) để đặt theo ký hiệu số.",
                                 "fix_cad": "Vẽ đường bao hạng mục trên mặt bằng tổng giống mặt bằng chi tiết (cùng kích thước)."})
        out["items"].append(item)
    missing = [g for g in d.groups if tag_number(g) and g not in tags and d.views_of(g, "elevation")]
    for g in missing[:20]:
        out["notes"].append(f"Hạng mục {g} không có ký hiệu số trên mặt bằng tổng: không đặt vào cảnh.")

    # bậc 1
    uc = supp.get("space:ceiling")
    if uc and str(uc).replace(".", "", 1).isdigit() and 1800 <= float(uc) <= 6000:
        out["ceiling"] = {"value": float(uc), "src": "user"}
    elif ceilings:
        out["ceiling"] = {"value": float(statistics.median(ceilings)), "src": "dimension", "n": len(ceilings)}
    else:
        out["ceiling"] = {"value": DEFAULT_CEILING, "src": "default"}
        out["tasks"].append({"id": "space:ceiling", "title": "Chưa biết cao sàn – trần",
                             "why": "Không mặt đứng hạng mục nào ghi kích thước sàn – trần.", "fix_here": "Nhập cao sàn – trần (mm)."})
    H = out["ceiling"]["value"]
    for i, pts in enumerate(walls_of(d, master), 1):
        out["walls"].append({"id": f"W{i}", "base": [loc(p) for p in pts], "z0": 0.0, "z1": H})
    if not out["walls"]:
        out["tasks"].append({"id": "space:walls", "title": "Không đọc được tường",
                             "why": "Không thấy đa giác kín nào trên layer nét cắt/tường của mặt bằng tổng.",
                             "fix_cad": "Vẽ tường bằng polyline kín trên layer tường (hoặc nét cắt)."})
    out["rooms"] = [{**r, "pos": loc(r["pos"])} for r in rooms_of(d, master)]

    # bậc 3 + 4
    ext = {b.name.casefold(): b.extents for b in model.blocks if not b.is_layout}
    udh = supp.get("space:door_h")
    door_h = float(udh) if udh and str(udh).replace(".", "", 1).isdigit() and 1500 <= float(udh) <= min(H, 4000) else DEFAULT_DOOR_H
    out["door_h"] = {"value": door_h, "src": "user" if udh and door_h == float(udh) else "default"}
    for h in master.handles:
        e = d.entities[h]
        if e.type != "INSERT":
            continue
        role = d.roles.get(e.layer)
        b = entity_box(e, ext)
        if b is None or (b[2] - b[0]) < 150 or (b[3] - b[1]) < 150 or (b[2] - b[0]) > 6000 or (b[3] - b[1]) > 6000:
            continue
        if role == "door" and max(b[2] - b[0], b[3] - b[1]) > DOOR_MAX_W:
            out["notes"].append(f"Block cửa rộng {max(b[2] - b[0], b[3] - b[1]):.0f} mm (vách kính/cửa trượt lớn): chưa dựng.")
            continue
        lb = (b[0] - ox, b[1] - oy, b[2] - ox, b[3] - oy)
        if role == "door":
            out["doors"].append({"id": f"D{len(out['doors']) + 1}", "base": [loc((x + ox, y + oy)) for x, y in _rect(lb)],
                                 "z0": 0.0, "z1": door_h, "handle": h})
        elif role == "furniture" and not _inside_any(lb, footprints):
            name = e.block or ""
            out["loose"].append({"id": f"L{len(out['loose']) + 1}", "base": [loc((x + ox, y + oy)) for x, y in _rect(lb)],
                                 "z0": 0.0, "z1": _loose_h(name), "src": "default", "handle": h})
    out["counts"] = {"walls": len(out["walls"]), "rooms": len(out["rooms"]), "items": len(out["items"]),
                     "placed": sum(1 for x in out["items"] if x.get("placed")), "loose": len(out["loose"]), "doors": len(out["doors"]),
                     "tasks": len(out["tasks"])}
    out["space_hash"] = hashlib.sha256(json.dumps(out, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:16]
    return out


def space_boxes(sp: dict) -> list[dict]:
    """Hộp cho trình xem/GLB: {b: đáy, z0, z1, k: loại, n: tên, m: vật liệu}."""
    H = (sp.get("ceiling") or {}).get("value") or DEFAULT_CEILING
    out = []
    if sp.get("walls") or sp.get("items"):
        xs = [p[0] for w in sp["walls"] for p in w["base"]] + [p[0] for it in sp["items"] for m in it.get("modules", []) for p in m["base"]]
        ys = [p[1] for w in sp["walls"] for p in w["base"]] + [p[1] for it in sp["items"] for m in it.get("modules", []) for p in m["base"]]
        if xs:
            out.append({"b": _rect((min(xs), min(ys), max(xs), max(ys))), "z0": -30.0, "z1": 0.0, "k": "floor", "n": "floor", "m": "floor"})
    for w in sp.get("walls", []):
        out.append({"b": w["base"], "z0": 0.0, "z1": w["z1"], "k": "wall", "n": w["id"], "m": "wall"})
    for it in sp.get("items", []):
        for m in it.get("modules", []):
            mat = "panel" if m.get("form") == "panel" else f"module-{m['kind']}"
            out.append({"b": m["base"], "z0": m["z0"], "z1": m["z1"], "k": "module", "n": f"{it['item']}:{m['id']}", "m": mat})
    for x in sp.get("loose", []):
        out.append({"b": x["base"], "z0": 0.0, "z1": x["z1"], "k": "loose", "n": x["id"], "m": "loose"})
    for x in sp.get("doors", []):
        out.append({"b": _thin(x["base"], 100.0), "z0": x["z1"], "z1": H, "k": "lintel", "n": x["id"] + ":lanh-to", "m": "wall"})
        out.append({"b": _thin(x["base"]), "z0": 0.0, "z1": x["z1"], "k": "door", "n": x["id"], "m": "front-door"})
    return out


def _thin(base, t: float = 40.0):
    """Tấm mỏng dày `t` dọc cạnh dài của khung block cửa (cánh cửa, lanh tô)."""
    (x0, y0), (x1, _), (_, y1) = base[0], base[1], base[2]
    if (x1 - x0) >= (y1 - y0):
        ym = (y0 + y1) / 2
        return _rect((x0, ym - t / 2, x1, ym + t / 2))
    xm = (x0 + x1) / 2
    return _rect((xm - t / 2, y0, xm + t / 2, y1))


def render_space_glb(sp: dict) -> bytes:
    from .geometry import Box
    from .gltf import glb_from_boxes

    bx = [Box(b["n"], b["k"], b["m"], tuple(tuple(p) for p in _ccw(b["b"])), b["z0"], b["z1"]) for b in space_boxes(sp)]
    return glb_from_boxes(bx, "cadguard cg.space/1", {"schema": SCHEMA, "space_hash": sp.get("space_hash"), "unit": "mm"})


def _ccw(base):
    a = sum(base[i][0] * base[(i + 1) % len(base)][1] - base[(i + 1) % len(base)][0] * base[i][1] for i in range(len(base)))
    return list(reversed(base)) if a < 0 else list(base)


__all__ = ["COVER_MIN", "SCHEMA", "build_space", "find_tags", "master_plan", "register", "render_space_glb", "space_boxes"]
