"""3D-2/3D-3: dựng cảnh `cg.scene/2` cho MỘT hạng mục đồ từ mặt bằng + mặt đứng (+ mặt đứng bỏ cánh) của bản vẽ 2D.

Tất định; LLM không quyết định số. Mọi kích thước có `src` = dimension (DIMENSION, kèm handle) | geometry (đo trên nét
hình) | user (người nhập, tệp `.cgsup.json`) | default (mặc định hiển thị, chỉ dùng cho dày tường/cao tường khi bản vẽ
không có). Thiếu thì `gaps[]` kèm ô nhập, không đoán.

Ghép hình:
- Mặt đứng E ↔ mặt bằng P cùng hạng mục khi có **kích thước ngang chung** (cùng số đo): trục X căn theo hai điểm đo
  của kích thước đó (`method = "dimension"`). Người dùng ghép tay bằng khoá `link:<E>` = `<P>` (`method = "user"`).
  LLM chỉ được ĐỀ XUẤT khoá này (`proposals`), không tự ghép.
- Sàn của mặt đứng = chân kích thước dọc lớn nhất chạm đáy hình (kích thước sàn–trần); trần = số đo của nó.
- Khối tủ = cụm nét nội thất chạm nhau trong mặt đứng (tủ dưới, tủ trên, tủ cao tách nhau). Rộng, cao, cao độ chân từ
  mặt đứng; sâu và vị trí theo trục Y từ mặt bằng: tủ chân ở sàn lấy nét liền, tủ treo lấy nét khuất (cách vẽ tủ trên ở
  mặt bằng). Không thấy nét tương ứng -> `gaps[]`.
- Cánh/ngăn kéo = hình chữ nhật ngoài cùng ≥ 150 mm trong khối (mặt đứng có cánh); đợt = tấm ngang mảnh trong mặt đứng
  bỏ cánh.
Quy ước hướng: mặt đứng nhìn vào tường, tường ở phía Y lớn của mặt bằng, mặt trước tủ ở phía Y nhỏ (ghi trong `notes`).
"""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, Field

from .build import Field_, Gap
from .feasibility import common_width_dim, room_height_dim
from .plan import Component, components, measure_span, read_walls, tol_for
from .views2d import Drawing2D, View, rect_of, view_dims

SCHEMA = "cg.scene/2"
FURN = frozenset({"furniture", "cut"})
HIDDEN = frozenset({"hidden"})
UPPER_MIN_Z = 1000.0  # khối có chân cao hơn mức này là tủ treo (lấy sâu từ nét khuất ở mặt bằng)
FRONT_MIN = 150.0
SHELF_MAX = 40.0
SLAB_MM = 20.0
DEFAULT_WALL_H = 2700.0


class Src(BaseModel):
    kind: str  # dimension | geometry | user | default
    refs: list[str] = Field(default_factory=list)


class Front(BaseModel):
    id: str
    kind: str  # door | drawer
    x0: float
    x1: float
    z0: float
    z1: float
    refs: list[str] = Field(default_factory=list)


class Module2(BaseModel):
    id: str
    kind: str  # base | wall | tall
    x: float
    y: float
    z0: float
    w: float
    d: float
    h: float
    src: dict[str, Src] = Field(default_factory=dict)
    fronts: list[Front] = Field(default_factory=list)
    shelves: int = 0
    label: str = ""  # nhãn người xác nhận (tủ bếp dưới, tủ cao…); trống = chưa gán
    refs: list[str] = Field(default_factory=list)


class Wall2(BaseModel):
    id: str
    start: tuple[float, float]
    end: tuple[float, float]
    thickness: float
    height: float
    side: int = 1  # dày tường đặt về phía pháp tuyến trái (+1) hay phải (-1) của đoạn
    src: dict[str, Src] = Field(default_factory=dict)


class Room2(BaseModel):
    floor: list[tuple[float, float]] = Field(default_factory=list)
    ceiling: float | None = None
    src: dict[str, Src] = Field(default_factory=dict)


class Link(BaseModel):
    elevation: str
    plan: str
    method: str  # dimension | user
    offset_x: float
    refs: list[str] = Field(default_factory=list)


class Scene2(BaseModel):
    schema_id: str = Field(default=SCHEMA, alias="schema")
    source_hash: str = ""
    item: str = ""
    unit: str = "mm"
    room: Room2 = Field(default_factory=Room2)
    walls: list[Wall2] = Field(default_factory=list)
    modules: list[Module2] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    scene_hash: str = ""

    model_config = {"populate_by_name": True}

    def compute_hash(self) -> str:
        data = self.model_dump(by_alias=True, exclude={"scene_hash"})
        return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _num(raw) -> float | None:
    try:
        v = float(str(raw).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _src(m) -> Src:
    return Src(kind=m.source, refs=list(m.refs))


def _overlap(a0, a1, b0, b1) -> float:
    return min(a1, b1) - max(a0, b0)


def _links(d: Drawing2D, plans: list[View], elevs: list[View], supp: dict, sc: Scene2) -> dict[str, tuple[View, View, float, list[str], str]]:
    out: dict[str, tuple] = {}
    by_id = {v.id: v for v in plans}
    for e in elevs:
        user = supp.get(f"link:{e.id}")
        if user in by_id:
            p = by_id[user]
            pair = common_width_dim(d, p, e)
            # ghép tay: vẫn cần căn X; có kích thước chung thì dùng, không thì căn mép trái khung hình
            ox = (pair[0].lo - pair[1].lo) if pair else (p.box[0] - e.box[0])
            out[e.id] = (e, p, ox, [x.handle for x in pair] if pair else [], "user")
            continue
        cands = [(p, pr) for p in plans if (pr := common_width_dim(d, p, e))]
        if len(cands) > 1 and sum(1 for p, _ in cands if not p.flags) == 1:  # ưu tiên mặt bằng chính (không "bỏ mặt đá", "chia khoang")
            cands = [(p, pr) for p, pr in cands if not p.flags]
        if len(cands) == 1 or (cands and len({round(pr[0].lo - pr[1].lo, 3) for _p, pr in cands}) == 1 and len({p.id for p, _ in cands}) == 1):
            p, pr = cands[0]
            out[e.id] = (e, p, pr[0].lo - pr[1].lo, [pr[0].handle, pr[1].handle], "dimension")
        else:
            sc.gaps.append(Gap(id=f"link:{e.id}", kind="ambiguous" if cands else "missing_view", target=e.id,
                               message=(f"Mặt đứng {e.id}: {len(cands)} mặt bằng có kích thước chung, chọn một." if cands else
                                        f"Mặt đứng {e.id}: không có mặt bằng cùng hạng mục có kích thước ngang chung để căn trục X."),
                               fields=[Field_(key=f"link:{e.id}", label="Mặt bằng tương ứng", kind="choice", options=[p.id for p in plans])]))
    return out


def _fronts(rects: list[tuple], comp_box) -> list[tuple]:
    area = (comp_box[2] - comp_box[0]) * (comp_box[3] - comp_box[1])
    cands = [r for r in rects if (r[0][2] - r[0][0]) >= FRONT_MIN and (r[0][3] - r[0][1]) >= FRONT_MIN
             and (r[0][2] - r[0][0]) * (r[0][3] - r[0][1]) < 0.9 * area]
    out = []
    for r in cands:
        b = r[0]
        if any(o is not r and o[0][0] <= b[0] + 0.5 and o[0][1] <= b[1] + 0.5 and o[0][2] >= b[2] - 0.5 and o[0][3] >= b[3] - 0.5
               and o[0] != b for o in cands):
            continue
        out.append(r)
    return out


def _edges(d: Drawing2D, c: Component) -> tuple[list[float], list[float]]:
    xs: set[float] = set()
    zs: set[float] = set()
    for h in c.handles:
        e = d.entities[h]
        for x, y in e.pts or []:
            xs.add(x)
            zs.add(y)
    return sorted(xs), sorted(zs)


def _snap(v: float, edges: list[float], direction: int, reach: float) -> float:
    """Bám mép thân tủ gần nhất ra phía ngoài (direction -1: nhỏ hơn, +1: lớn hơn) trong khoảng `reach`."""
    cands = [x for x in edges if 0 <= (x - v) * direction <= reach]
    return max(cands, key=lambda x: (x - v) * direction) if cands else v


def _front_groups(fr: list[tuple]) -> list[list[tuple]]:
    """Nhóm mặt trước thành khối: cánh cao (≥ 1500) là một khối; các mặt còn lại sát nhau (≤ 40 mm) cùng khối."""
    tall = [f for f in fr if (f[0][3] - f[0][1]) >= 1500.0]
    rest = [f for f in fr if f not in tall]
    parent = list(range(len(rest)))

    def find(i):
        while parent[i] != i:
            i = parent[i]
        return i

    for i, (a, _) in enumerate(rest):
        for j in range(i):
            b = rest[j][0]
            near = a[0] - 40 <= b[2] and b[0] - 40 <= a[2] and a[1] - 40 <= b[3] and b[1] - 40 <= a[3]
            side = _overlap(a[1], a[3], b[1], b[3]) >= 0.5 * min(a[3] - a[1], b[3] - b[1])  # cạnh nhau cùng dải cao
            stack = _overlap(a[0], a[2], b[0], b[2]) >= 0.5 * min(a[2] - a[0], b[2] - b[0])  # chồng nhau cùng cột
            if near and (side or stack):
                parent[find(i)] = find(j)
    groups: dict[int, list] = {}
    for i, f in enumerate(rest):
        groups.setdefault(find(i), []).append(f)
    out = list(groups.values())
    # nhóm vắt qua tủ cao (khung bao hình chữ L) -> tách trái / phải / phía trên tủ cao
    for t in tall:
        tb = t[0]
        nxt = []
        for g in out:
            gx0, gx1 = min(b[0] for b, _ in g), max(b[2] for b, _ in g)
            gz0 = min(b[1] for b, _ in g)
            if gx0 < tb[0] and gx1 > tb[2] and gz0 < tb[3]:
                cx = lambda f: (f[0][0] + f[0][2]) / 2  # noqa: E731
                parts = [[f for f in g if cx(f) < tb[0]], [f for f in g if cx(f) > tb[2]], [f for f in g if tb[0] <= cx(f) <= tb[2]]]
                nxt += [x for x in parts if x]
            else:
                nxt.append(g)
        out = nxt
    return [[t] for t in tall] + out


def _add_module(sc, mid, box, hs, fr, e, p, ox, origin, floor, edims, pdims, pf, ph, shelf_rects, supp) -> None:
    x0p, x1p = box[0] + ox, box[2] + ox  # toạ độ X của mặt bằng
    z0, z1 = box[1] - floor, box[3] - floor
    kind = "wall" if z0 >= UPPER_MIN_Z else ("tall" if z1 >= 1800 else "base")
    pool = ph if kind == "wall" else pf
    # sâu: các nét (của cụm mặt bằng cùng loại) có ≥ 50 % bề ngang nằm trong khoảng X của khối
    over = [b for q in pool for b in q.parts if _overlap(b[0], b[2], x0p, x1p) >= 0.5 * max(b[2] - b[0], 1.0) and (b[3] - b[1]) > 1.0]
    w, h = measure_span(edims, "h", box[0], box[2]), measure_span(edims, "v", box[1], box[3])
    m = Module2(id=mid, kind=kind, x=round(x0p - origin[0], 3), y=0.0, z0=round(z0, 3), w=w.value, d=0.0, h=h.value, refs=list(hs)[:50])
    m.src["w"], m.src["h"] = _src(w), _src(h)
    zd = next((x for x in edims if x.axis == "v" and abs(x.lo - floor) <= 1.0 and abs(x.hi - box[1]) <= tol_for(max(z0, 1.0))), None)
    m.src["z0"] = Src(kind="dimension", refs=[zd.handle]) if zd else Src(kind="geometry")
    ud = _num(supp.get(f"module:{mid}:d"))
    if ud:
        back = max((q.box[3] for q in pf), default=p.box[3])
        m.y, m.d, m.src["d"] = round(back - ud - origin[1], 3), ud, Src(kind="user")
    elif over:
        y0 = min(b[1] for b in over)
        y1 = max(b[3] for b in over)
        dm = measure_span(pdims, "v", y0, y1)
        m.y, m.d, m.src["d"] = round(y0 - origin[1], 3), dm.value, _src(dm)
    else:
        sc.gaps.append(Gap(id=f"module:{mid}", kind="missing_value", target=mid,
                           message=(f"Khối {mid} ({'tủ treo' if kind == 'wall' else 'tủ'} rộng {w.value:.0f}, cao {h.value:.0f}): "
                                    f"mặt bằng không có nét {'khuất' if kind == 'wall' else 'liền'} tương ứng để lấy chiều sâu."),
                           fields=[Field_(key=f"module:{mid}:d", label="Chiều sâu")]))
        return
    for j, (b, hf) in enumerate(sorted(fr, key=lambda t: (t[0][0], t[0][1])), 1):
        kindf = "drawer" if (b[3] - b[1]) < 0.6 * (b[2] - b[0]) else "door"
        m.fronts.append(Front(id=f"{mid}.F{j}", kind=kindf, x0=round(b[0] + ox - origin[0], 3), x1=round(b[2] + ox - origin[0], 3),
                              z0=round(b[1] - floor, 3), z1=round(b[3] - floor, 3), refs=[hf]))
    m.shelves = sum(1 for sx0, sx1, sz in shelf_rects if sx0 >= x0p - 1 and sx1 <= x1p + 1 and z0 < sz < z1)
    m.label = str(supp.get(f"label:{mid}", ""))[:60]
    sc.modules.append(m)


def build_item_scene(d: Drawing2D, group: str, supplement: dict | None = None) -> Scene2:
    supp = supplement or {}
    sc = Scene2(item=group)
    sc.notes.append("Quy ước: mặt đứng nhìn vào tường; ở mặt bằng tường phía Y lớn, mặt trước tủ phía Y nhỏ.")
    plans = [v for v in d.views_of(group, "plan") if v.box]
    elevs = [v for v in d.views_of(group, "elevation") if v.box]
    if not plans or not elevs:
        sc.gaps.append(Gap(id=f"item:{group}", kind="missing_view", target=group,
                           message=f"Hạng mục {group}: thiếu {'mặt bằng' if not plans else 'mặt đứng'}; không dựng được khối."))
        return _finish(sc, d)
    links = _links(d, plans, elevs, supp, sc)
    for e, p, ox, refs, method in links.values():
        sc.links.append(Link(elevation=e.id, plan=p.id, method=method, offset_x=round(ox, 3), refs=refs))
    main = [lk for lk in links.values() if "no_doors" not in lk[0].flags] or list(links.values())
    if not main:
        return _finish(sc, d)
    e, p, ox, _refs, _m = main[0]
    shelf_src = next((lk for lk in links.values() if "no_doors" in lk[0].flags and lk[1].id == p.id), None)
    origin = (p.box[0], p.box[1])

    # sàn / trần
    rh = room_height_dim(d, e)
    if rh is not None:
        floor = rh.lo
        sc.room.ceiling = rh.value
        sc.room.src["ceiling"] = Src(kind="dimension", refs=[rh.handle])
    else:
        floor = e.box[1]
        u = _num(supp.get("room:ceiling"))
        if u:
            sc.room.ceiling, sc.room.src["ceiling"] = u, Src(kind="user")
        else:
            sc.gaps.append(Gap(id="room:ceiling", kind="missing_value", target=e.id,
                               message="Không có kích thước sàn–trần ở mặt đứng: nhập cao trần.",
                               fields=[Field_(key="room:ceiling", label="Cao sàn–trần")]))
        sc.room.src["floor"] = Src(kind="geometry")

    pdims = view_dims(d, p)
    edims = view_dims(d, e)
    pf = components(d, p, FURN, min_size=100.0)
    ph = components(d, p, HIDDEN, min_size=100.0)
    shelf_rects: list[tuple] = []
    if shelf_src is not None:
        se, _sp, sox = shelf_src[0], shelf_src[1], shelf_src[2]
        for h in se.handles:
            r = rect_of(d.entities[h])
            if r and d.roles.get(d.entities[h].layer) in FURN and (r[3] - r[1]) <= SHELF_MAX and (r[2] - r[0]) >= 150:
                rh2 = room_height_dim(d, se)
                f2 = rh2.lo if rh2 else se.box[1]
                shelf_rects.append((r[0] + sox, r[2] + sox, r[1] - f2))

    comps: list[Component] = components(d, e, FURN, min_size=200.0)
    blocks: list[tuple] = []  # (khung khối trên mặt đứng, handles, mặt trước [(box, handle)], cụm gốc)
    for c in comps:
        fr = _fronts([(r, h) for h in c.handles if (r := rect_of(d.entities[h]))], c.box) if "no_doors" not in e.flags else []
        if len(fr) < 2:
            blocks.append((c.box, c.handles, fr, c))
            continue
        edges_x, edges_z = _edges(d, c)
        for grp in _front_groups(fr):
            gb = (min(b[0] for b, _ in grp), min(b[1] for b, _ in grp), max(b[2] for b, _ in grp), max(b[3] for b, _ in grp))
            box = (_snap(gb[0], edges_x, -1, 40.0), c.box[1] if gb[1] - c.box[1] <= 200.0 else _snap(gb[1], edges_z, -1, 60.0),
                   _snap(gb[2], edges_x, 1, 40.0), _snap(gb[3], edges_z, 1, 80.0))
            blocks.append((box, [h for _, h in grp], grp, c))
    blocks.sort(key=lambda t: (t[0][0], t[0][1]))
    for i, (box, hs, fr, c) in enumerate(blocks, 1):
        _add_module(sc, f"M{i}", box, hs, fr, e, p, ox, origin, floor, edims, pdims, pf, ph, shelf_rects, supp)

    # tường: nét tường của mặt bằng hạng mục
    walls, _rooms = read_walls(d, p)
    height = sc.room.ceiling
    cx = sum(m.x + m.w / 2 for m in sc.modules) / len(sc.modules) if sc.modules else 0.0
    cy = sum(m.y + m.d / 2 for m in sc.modules) / len(sc.modules) if sc.modules else 0.0
    for w in walls:
        a = (w.start[0] - origin[0], w.start[1] - origin[1])
        b = (w.end[0] - origin[0], w.end[1] - origin[1])
        side = 1
        if w.thickness_source == "default":  # chỉ có một mặt tường: dày đặt về phía không có tủ
            nx, ny = -(b[1] - a[1]), b[0] - a[0]
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            side = -1 if (cx - mx) * nx + (cy - my) * ny > 0 else 1
        wl = Wall2(id=w.id, start=a, end=b, thickness=w.thickness, height=height or DEFAULT_WALL_H, side=side if w.thickness_source == "default" else 0)
        wl.src["thickness"] = Src(kind=w.thickness_source, refs=w.refs)
        wl.src["height"] = sc.room.src.get("ceiling", Src(kind="default")) if height else Src(kind="default")
        sc.walls.append(wl)
    return _finish(sc, d)


def _finish(sc: Scene2, d: Drawing2D) -> Scene2:
    xs = [p for w in sc.walls for p in (w.start[0], w.end[0])] + [v for m in sc.modules for v in (m.x, m.x + m.w)]
    ys = [p for w in sc.walls for p in (w.start[1], w.end[1])] + [v for m in sc.modules for v in (m.y, m.y + m.d)]
    if xs and ys:
        x0, x1, y0, y1 = min(xs), max(xs), min(ys) - 600.0, max(ys)
        sc.room.floor = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        sc.room.src.setdefault("floor", Src(kind="geometry"))
    sc.source_hash = ""
    sc.scene_hash = sc.compute_hash()
    return sc


def build_from_model(model, group: str | None = None, supplement: dict | None = None, roles: dict | None = None) -> tuple[Scene2, Drawing2D]:
    from .views2d import read_drawing

    d = read_drawing(model, roles=roles)
    g = group or best_item(d)
    sc = build_item_scene(d, g or "", supplement)
    sc.source_hash = model.file_hash
    sc.scene_hash = sc.compute_hash()
    return sc, d


def best_item(d: Drawing2D) -> str | None:
    """Hạng mục đầu tiên có mặt bằng + mặt đứng ghép được bằng kích thước (theo thứ tự tờ)."""
    for g in d.groups:
        ps = [v for v in d.views_of(g, "plan") if v.box]
        es = [v for v in d.views_of(g, "elevation") if v.box]
        if any(common_width_dim(d, p, e) for p in ps for e in es):
            return g
    return next(iter(d.groups), None)


def item_summary(d: Drawing2D) -> list[dict]:
    out = []
    for g, info in d.groups.items():
        vs = d.views_of(g)
        ps = [v for v in vs if v.kind == "plan" and v.box]
        es = [v for v in vs if v.kind == "elevation" and v.box]
        out.append({"id": g, "sheets": len(info["sheets"]), "plans": len(ps), "elevations": len(es),
                    "sections": sum(1 for v in vs if v.kind == "section" and v.box),
                    "aligned": sum(1 for e in es if any(common_width_dim(d, p, e) for p in ps))})
    return out


def apply_supplement(data: dict, source_hash: str) -> tuple[dict, str | None]:
    from .build import load_supplement

    return load_supplement(data, source_hash)


__all__ = ["Front", "Link", "Module2", "Room2", "SCHEMA", "Scene2", "Src", "Wall2", "best_item", "build_from_model",
           "build_item_scene", "item_summary"]
