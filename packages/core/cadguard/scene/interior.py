"""Nội thất của khối đọc từ hình "bỏ cánh" + ký hiệu đặc biệt vẽ trên layer nét khuất. Tất định, chỉ đọc nét/chữ.

Ca thật (tủ áo + tủ minibar, 11/11/2026): người vẽ đặt hai mặt đứng cạnh nhau, chép cùng tiêu đề "MẶT ĐỨNG BỎ CÁNH";
hình trái thật ra có cánh (ký hiệu mở cánh), hình phải mới bỏ cánh (thanh treo, hộc tủ, ô tủ lạnh). Mỗi tấm vẽ hai
nét (ván 25, đá 20, kính 10) nên đếm nét ra "6 đợt". Đường khấu bo cong và vòng chú thích "ghép mòi 45°" vẽ trên layer
nét khuất nên bị coi như nét tủ.

- `door_symbol_area`: tổng diện tích ký hiệu mở cánh của một hình → phân biệt hình có cánh / bỏ cánh khi tiêu đề trùng.
- `levels`: tấm ngang = CHỒNG các nét ngang sát nhau (≤ 62 mm) → một tầng (ván, ván + đá, kính), bỏ nóc/đáy/chân.
- `read_interior`: tầng + loại theo ghi chú (hồ sơ trình bày: kính, đá), hộc trong ("HỘC"), thiết bị (ô dấu X +
  "TỦ LẠNH"), thanh treo (hình chữ nhật mảnh nét khuất trên khoang cao), đèn.
- `curve_marks`: polyline 3 điểm nét khuất có hai đầu nằm trên hai cạnh vuông góc, điểm giữa lồi về góc = đường khấu /
  bo cong (KHÔNG phải ký hiệu cánh: ký hiệu cánh có hai đầu cùng một cạnh).
- `callouts`: vòng tròn lớn (r ≥ 50) không thuộc thân tủ = vòng chú thích, gắn chữ gần nhất.
"""
from __future__ import annotations

from .views2d import Drawing2D, View, entity_box, rect_of

STACK_GAP = 62.0  # hai nét ngang cách nhau ≤ mức này là cùng một tấm (ván + đá, hai mặt tấm kính…)
STACK_RATIO = 0.8  # các nét của một tấm dài gần bằng nhau (loại đáy máy hút mùi hình thang…)
EDGE_ZONE = 150.0  # tầng sát đáy/nóc khối: chân, đáy, nóc, phào — không phải đợt
SYMBOL_MIN = 150.0
CALLOUT_R = 50.0
NOTE_DIST = 400.0  # ghi chú cách tầng tối đa để gán loại tầng
GLASS_MAX = 14.0
HANG_MIN = 800.0  # khoang dưới thanh treo cao tối thiểu (treo áo)
BODY = frozenset({"furniture", "cut"})
DRAW_TYPES = ("LINE", "LWPOLYLINE", "POLYLINE")


def _pts(e) -> list[tuple[float, float]]:
    return [(float(p[0]), float(p[1])) for p in (e.pts or [])]


def _text_items(d: Drawing2D, handles) -> list[tuple[float, float, str, str]]:
    from .explain import _vi

    out = []
    for h in handles:
        e = d.entities[h]
        p = e.pos or e.insert
        if e.type in ("TEXT", "MTEXT") and e.text and p:
            out.append((float(p[0]), float(p[1]), _vi(e.text), h))
    return out


def meaning(d: Drawing2D, text: str) -> str | None:
    if not getattr(d, "keywords", None):
        return None
    from ..drafting import meaning_of

    return meaning_of(text, d.keywords)


def has_meaning(d: Drawing2D, text: str, want: str) -> bool:
    """Chữ có chứa từ khoá mang nghĩa `want` (không chỉ nghĩa của từ dài nhất): "GHI CHÚ KHẤU … CHO THOÁT HƠI TỦ LẠNH"."""
    from ..drafting import up

    t = up(text)
    return any(k["meaning"] == want and up(k["text"]) in t for k in (getattr(d, "keywords", None) or []))


# ---------------- ký hiệu trên layer nét khuất ----------------

def is_curve_mark(pts: list[tuple[float, float]], tol: float = 5.0) -> bool:
    """Polyline 3 điểm: hai đầu không cùng cạnh (lệch cả X lẫn Y), điểm giữa nằm trong tam giác (đầu, đầu, góc) = cung
    khấu/bo cong vẽ gãy khúc. Ký hiệu mở cánh/ngăn kéo có hai đầu cùng một cạnh nên không lọt."""
    if len(pts) != 3:
        return False
    (ax, ay), (mx, my), (bx, by) = pts
    if abs(ax - bx) <= tol or abs(ay - by) <= tol or min(abs(ax - bx), abs(ay - by)) < 50:
        return False
    for cx, cy in ((ax, by), (bx, ay)):  # góc vuông tạo bởi hai cạnh chứa hai đầu
        if min(ax, bx) - tol <= mx <= max(ax, bx) + tol and min(ay, by) - tol <= my <= max(ay, by) + tol:
            # điểm giữa phía góc so với dây cung
            side = lambda px, py: (bx - ax) * (py - ay) - (by - ay) * (px - ax)  # noqa: E731
            if side(mx, my) * side(cx, cy) > 0:
                return True
    return False


def is_callout(e, role: str | None) -> bool:
    return e.type == "CIRCLE" and role not in BODY and float(getattr(e, "radius", 0) or 0) >= CALLOUT_R


def door_symbol_area(d: Drawing2D, v: View) -> float:
    """Tổng diện tích khung các ký hiệu mở cánh/ngăn kéo (nét khuất có đoạn chéo ≥ 150 × 150, không kể đường khấu)."""
    tot = 0.0
    for h in v.handles:
        e = d.entities[h]
        if d.roles.get(e.layer) != "hidden" or e.type not in DRAW_TYPES:
            continue
        pts = _pts(e)
        if is_curve_mark(pts):
            continue
        if not any(abs(x1 - x0) >= SYMBOL_MIN and abs(y1 - y0) >= SYMBOL_MIN for (x0, y0), (x1, y1) in zip(pts, pts[1:])):
            continue
        b = entity_box(e, {})
        if b:
            tot += (b[2] - b[0]) * (b[3] - b[1])
    return tot


def interior_score(d: Drawing2D, v: View) -> int:
    """Số dấu hiệu nội thất (chữ hộc, thiết bị, thanh treo, đèn, kính) trên hình."""
    return sum(1 for *_xy, t, _h in _text_items(d, v.handles) if meaning(d, t) in ("drawer", "appliance", "rod", "light", "glass"))


def classify(d: Drawing2D, views: list[View]) -> tuple[View, View, str] | None:
    """Hai+ mặt đứng cùng tiêu đề và cùng cờ (người vẽ chép tiêu đề): hình có nhiều ký hiệu mở cánh nhất là hình có
    cánh, hình ít ký hiệu nhất (và ≤ 1/2) là hình bỏ cánh. Trả (hình có cánh, hình bỏ cánh, lý do) hoặc None."""
    if len(views) < 2 or len({(v.title or "").strip().upper() for v in views}) != 1:
        return None
    sc = sorted(((door_symbol_area(d, v), v) for v in views), key=lambda t: -t[0])
    hi, lo = sc[0], sc[-1]
    sign = "ký hiệu mở cánh"
    if hi[0] <= 0:  # không hình nào có ký hiệu mở: so số hình chữ nhật mặt trước (cánh/ngăn kéo vẽ khung kín)
        sc = sorted(((float(_front_rects(d, v)), v) for v in views), key=lambda t: -t[0])
        hi, lo = sc[0], sc[-1]
        sign = "khung cánh/ngăn kéo"
        if hi[0] - lo[0] < 2:
            return None
    if hi[0] <= 0 or lo[0] > 0.5 * hi[0]:
        return None
    why = (f"Hai mặt đứng cùng tiêu đề \"{hi[1].title}\": hình {hi[1].id} có {sign} nên là hình CÓ CÁNH (dựng khối, "
           f"cánh); hình {lo[1].id} gần như không có nên là hình BỎ CÁNH (đọc đợt, hộc, thanh treo, thiết bị).")
    return hi[1], lo[1], why


def _front_rects(d: Drawing2D, v: View) -> int:
    """Số khung chữ nhật kín ≥ 150 × 150 trên layer thân tủ (đường bao khối + cánh/ngăn kéo vẽ khung kín)."""
    n = 0
    for h in v.handles:
        e = d.entities[h]
        if d.roles.get(e.layer) in ("hidden", "dim", "text", "frame", None):
            continue
        r = rect_of(e)
        if r and (r[2] - r[0]) >= SYMBOL_MIN and (r[3] - r[1]) >= SYMBOL_MIN:
            n += 1
    return n


# ---------------- tầng ngang ----------------

def _hsegs(d: Drawing2D, handles, roles: frozenset[str]) -> list[tuple[float, float, float, str]]:
    """Đoạn ngang (x0, x1, z, handle) của các nét thuộc vai trò `roles`."""
    out = []
    for h in handles:
        e = d.entities[h]
        if d.roles.get(e.layer) not in roles or e.type not in DRAW_TYPES:
            continue
        pts = _pts(e)
        if e.closed and len(pts) > 2:
            pts = pts + [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if abs(y0 - y1) <= 0.5 and abs(x1 - x0) > 1:
                out.append((min(x0, x1), max(x0, x1), (y0 + y1) / 2, h))
    return out


def _vsegs(d: Drawing2D, handles, roles: frozenset[str]) -> list[tuple[float, float, float, str]]:
    out = []
    for h in handles:
        e = d.entities[h]
        if d.roles.get(e.layer) not in roles or e.type not in DRAW_TYPES:
            continue
        pts = _pts(e)
        if e.closed and len(pts) > 2:
            pts = pts + [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if abs(x0 - x1) <= 0.5 and abs(y1 - y0) > 1:
                out.append((min(y0, y1), max(y0, y1), (x0 + x1) / 2, h))
    return out


SUPPORT_TOL = 6.0  # đầu tấm ngang chạm hông/vách (lòng ngăn kéo, đáy máy hút mùi lơ lửng thì không)


def _supported(x: float, z: float, vsegs, x0: float, x1: float) -> bool:
    if abs(x - x0) <= SUPPORT_TOL or abs(x - x1) <= SUPPORT_TOL:
        return True
    # nét đứng đi QUA cao độ tấm (hông, vách); cạnh lòng ngăn kéo/máy hút mùi chỉ mọc lên từ tấm nên không tính
    return any(abs(s[2] - x) <= SUPPORT_TOL and s[0] <= z - 30 and s[1] >= z + 30 for s in vsegs)


def levels(segs: list[tuple[float, float, float, str]], x0: float, x1: float, z0: float, z1: float, vsegs=None) -> list[dict]:
    """Tầng ngang trong khung [x0, x1] × [z0, z1] (toạ độ của hình): chồng nét ngang cách nhau ≤ STACK_GAP. Một nét đơn
    chỉ tính khi dài ≥ 60 % khối (cách vẽ đợt bằng một nét). Bỏ tầng sát đáy/nóc (chân, đáy, nóc, phào). Có `vsegs`
    (nét đứng thân tủ): tấm phải tựa — ít nhất một đầu chạm hông khối hoặc một nét đứng đi qua cao độ tấm (đáy lòng
    ngăn kéo, đáy máy hút mùi không tựa)."""
    w = x1 - x0
    cand = sorted((s for s in segs if s[0] >= x0 - 5 and s[1] <= x1 + 5 and (s[1] - s[0]) >= 150.0
                   and z0 - 1 <= s[2] <= z1 + 1), key=lambda s: (s[2], s[0]))
    stacks: list[list] = []
    for s in cand:
        # cùng tấm: nét ngang ngay trên (≤ STACK_GAP), chồng lên nhau theo X, dài gần bằng nhau
        home = None
        for st in reversed(stacks):
            last = st[-1]
            if s[2] - last[2] > STACK_GAP:
                continue
            ov = min(s[1], last[1]) - max(s[0], last[0])
            ln = (s[1] - s[0], last[1] - last[0])
            if ov >= 0.8 * min(ln) and min(ln) >= STACK_RATIO * max(ln):
                home = st
                break
        if home is not None:
            home.append(s)
        else:
            stacks.append([s])
    out = []
    for st in stacks:
        zs = sorted({round(s[2], 1) for s in st})
        lo, hi = zs[0], zs[-1]
        if lo <= z0 + EDGE_ZONE or hi >= z1 - EDGE_ZONE:
            continue
        if len(zs) == 1 and max(s[1] - s[0] for s in st) < 0.6 * w:
            continue
        if vsegs is not None:
            ends = (min(s[0] for s in st), max(s[1] for s in st))
            if not any(_supported(x, z, vsegs, x0, x1) for x in ends for z in zs):
                continue
        out.append({"z0": lo, "z1": hi if hi > lo else lo + 1.0, "lines": zs, "x0": min(s[0] for s in st), "x1": max(s[1] for s in st),
                    "refs": sorted({s[3] for s in st})})
    return out


def _cell(hs, vs, x: float, z: float, box) -> tuple[float, float, float, float] | None:
    """Ô nhỏ nhất bao điểm (x, z) tạo bởi nét đứng trái/phải và nét ngang dưới/trên."""
    left = [s[2] for s in vs if s[2] < x and s[0] - 2 <= z <= s[1] + 2 and s[2] >= box[0] - 2]
    right = [s[2] for s in vs if s[2] > x and s[0] - 2 <= z <= s[1] + 2 and s[2] <= box[2] + 2]
    below = [s[2] for s in hs if s[2] < z and s[0] - 2 <= x <= s[1] + 2 and s[2] >= box[1] - 2]
    above = [s[2] for s in hs if s[2] > z and s[0] - 2 <= x <= s[1] + 2 and s[2] <= box[3] + 2]
    if not (left and right and below and above):
        return None
    return max(left), min(below), min(right), min(above)


def _xbox(d: Drawing2D, handles, x: float, z: float):
    """Khung có dấu X (hai đường chéo góc-góc) chứa điểm (x, z): ô thiết bị."""
    rects = []
    for h in handles:
        e = d.entities[h]
        r = rect_of(e)
        if r and r[0] <= x <= r[2] and r[1] <= z <= r[3] and (r[2] - r[0]) >= SYMBOL_MIN and (r[3] - r[1]) >= SYMBOL_MIN:
            rects.append((r, h))
    for r, h in sorted(rects, key=lambda t: (t[0][2] - t[0][0]) * (t[0][3] - t[0][1])):
        diag = 0
        for h2 in handles:
            pts = _pts(d.entities[h2])
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                if abs(min(ax, bx) - r[0]) <= 3 and abs(max(ax, bx) - r[2]) <= 3 and abs(min(ay, by) - r[1]) <= 3 and abs(max(ay, by) - r[3]) <= 3:
                    diag += 1
        if diag >= 2:
            return r, h
    return None


def read_interior(d: Drawing2D, v: View, ox: float, floor: float, body: frozenset[str], mod: dict, fronts=(),
                  notes=(), interior: bool = True) -> dict:
    """Nội thất của MỘT khối từ hình `v` (bỏ cánh hoặc chính hình có cánh): toạ độ trả về theo mặt bằng (x + ox) và cao
    độ (z - floor). `mod` = {x0, x1, z0, z1} theo mặt bằng/cao độ. `notes` = chữ trong khung hình
    (cả chữ không được gán vào hình) theo toạ độ hạng mục [(x, z, chữ, handle, nguồn 'v' | 'e')]; 'e' = hình có cánh. Trả {levels, drawers, appliances, rods, lights}."""
    bx0, bx1 = mod["x0"] - ox, mod["x1"] - ox
    bz0, bz1 = mod["z0"] + floor, mod["z1"] + floor
    box = (bx0, bz0, bx1, bz1)
    inside = [h for h in v.handles if (b := entity_box(d.entities[h], {})) is not None
              and b[0] >= bx0 - 5 and b[2] <= bx1 + 5 and b[1] >= bz0 - 5 and b[3] <= bz1 + 5]
    texts = [t for t in _text_items(d, v.handles) if bx0 <= t[0] <= bx1 and bz0 <= t[1] <= bz1]
    seen = {t[3] for t in texts}
    conv = [(x - ox, z + floor, t, h, src) for x, z, t, h, src in notes
            if bx0 <= x - ox <= bx1 and bz0 <= z + floor <= bz1 and h not in seen]
    texts += [c[:4] for c in conv if c[4] == "v"]
    lvl_texts = texts + [c[:4] for c in conv if c[4] == "e"]
    hs, vs = _hsegs(d, inside, body), _vsegs(d, inside, body)
    # hình có cánh: đợt sau cánh (đợt kính sau cánh kính…) vẽ nét khuất -> tính cả nét khuất cho tầng; thanh treo, vách,
    # hộc trong, đèn chỉ đọc ở hình bỏ cánh thật (ở hình có cánh nét đứng đôi là mép cánh/tay nắm)
    lv = levels(hs if interior else hs + _hsegs(d, inside, frozenset({"hidden"})), bx0, bx1, bz0, bz1, vs)
    for L in lv:  # loại tầng theo ghi chú gần nhất (kính, đá)
        L["kind"] = "shelf"
        best = None
        for tx, tz, t, h in lvl_texts:
            mean = meaning(d, t)
            if mean not in ("glass", "stone") or not (L["x0"] - 50 <= tx <= L["x1"] + 50):
                continue
            dist = min(abs(tz - L["z0"]), abs(tz - L["z1"]))
            if dist <= NOTE_DIST and (best is None or dist < best[0]):
                best = (dist, mean, h)
        for other in lv:  # chữ thuộc tầng gần hơn thì không gán cho tầng này
            if best and other is not L:
                tz = next(t[1] for t in lvl_texts if t[3] == best[2])
                if min(abs(tz - other["z0"]), abs(tz - other["z1"])) < best[0]:
                    best = None
        if best:
            if best[1] == "glass" and L["z1"] - L["z0"] <= GLASS_MAX:
                L["kind"], L["note"] = "glass", best[2]
            elif best[1] == "stone" and len(L["lines"]) >= 2:
                L["kind"], L["note"] = "stone", best[2]
    out = {"levels": [], "drawers": [], "appliances": [], "rods": [], "lights": [], "partitions": []}
    # vách đứng vẽ ở hình: hai nét đứng cách nhau 10–60 mm, cao ≥ 150, không sát hông khối
    vv = sorted((s for s in vs if interior and (s[1] - s[0]) >= 150 and bx0 + 40 < s[2] < bx1 - 40), key=lambda s: s[2])
    def _rests(x: float, z: float, end: str) -> bool:  # đầu vách tựa lên tấm ngang / đáy / nóc khối
        if (end == "lo" and z <= bz0 + EDGE_ZONE) or (end == "hi" and z >= bz1 - EDGE_ZONE):
            return True
        return any(s[0] - 5 <= x <= s[1] + 5 and abs(s[2] - z) <= 25 for s in hs)

    for a, b in zip(vv, vv[1:]):
        if 14 <= b[2] - a[2] <= 60 and min(a[1], b[1]) - max(a[0], b[0]) >= 150:
            z0, z1 = max(a[0], b[0]), min(a[1], b[1])
            xm = (a[2] + b[2]) / 2
            if not (_rests(xm, z0, "lo") and _rests(xm, z1, "hi")):
                continue  # cạnh lòng ngăn kéo, khung… không phải vách
            if not any(abs(o["x0"] - (a[2] + ox)) < 5 for o in out["partitions"]):
                out["partitions"].append({"x0": a[2] + ox, "x1": b[2] + ox, "z0": z0 - floor, "z1": z1 - floor, "refs": [a[3], b[3]]})
    for L in lv:
        out["levels"].append({"kind": L["kind"], "x0": L["x0"] + ox, "x1": L["x1"] + ox, "z0": L["z0"] - floor, "z1": L["z1"] - floor,
                              "lines": [z - floor for z in L["lines"]], "refs": L["refs"] + ([L["note"]] if L.get("note") else [])})
    # hộc trong, thiết bị: theo chữ trong ô
    for tx, tz, t, h in texts:
        mean = meaning(d, t)
        if mean == "appliance":
            xb = _xbox(d, inside, tx, tz)
            cell = xb[0] if xb else _cell(hs, vs, tx, tz, box)
            if cell:
                out["appliances"].append({"x0": cell[0] + ox, "x1": cell[2] + ox, "z0": cell[1] - floor, "z1": cell[3] - floor,
                                          "text": t, "refs": [h] + ([xb[1]] if xb else [])})
        elif mean == "drawer" and interior:
            cell = _cell(hs, vs, tx, tz, box)
            if not cell or (cell[2] - cell[0]) < SYMBOL_MIN or (cell[3] - cell[1]) < 80:
                continue
            c = (cell[0] + ox, cell[1] - floor, cell[2] + ox, cell[3] - floor)
            cov = sum(max(0.0, min(f.x1, c[2]) - max(f.x0, c[0])) * max(0.0, min(f.z1, c[3]) - max(f.z0, c[1]))
                      for f in fronts if f.kind == "drawer")
            if cov >= 0.5 * (c[2] - c[0]) * (c[3] - c[1]):
                continue  # ngăn kéo mặt ngoài đã đọc ở hình có cánh
            if not any(abs(o["x0"] - c[0]) < 5 and abs(o["z0"] - c[1]) < 5 for o in out["drawers"]):
                out["drawers"].append({"x0": c[0], "x1": c[2], "z0": c[1], "z1": c[3], "text": t, "refs": [h]})
    # thanh treo: hình chữ nhật mảnh (cao 15–40) nét khuất gần suốt khối, khoang dưới cao ≥ HANG_MIN (hoặc có chữ "thanh treo")
    has_rod_note = any(meaning(d, t) == "rod" for *_xy, t, _h in texts)
    tops = [L["z0"] for L in lv]
    for h in inside:
        e = d.entities[h]
        r = rect_of(e)
        if not r or d.roles.get(e.layer) != "hidden" or not interior:
            continue
        rw, rh = r[2] - r[0], r[3] - r[1]
        if 10 <= rh <= 40 and rw >= 0.6 * (bx1 - bx0):
            below = max([z for z in tops if z < r[1]] + [bz0])
            if has_rod_note or r[1] - below >= HANG_MIN:
                out["rods"].append({"x0": r[0] + ox, "x1": r[2] + ox, "z": (r[1] + r[3]) / 2 - floor, "refs": [h]})
    # đèn: nét khuất ngang đơn gần chữ "ĐÈN"
    hid = _hsegs(d, inside, frozenset({"hidden"}))
    for tx, tz, t, h in texts:
        if meaning(d, t) != "light" or not interior:
            continue
        near = [s for s in hid if s[0] <= tx <= s[1] and abs(s[2] - tz) <= 120 and (s[1] - s[0]) >= 0.5 * (bx1 - bx0)
                and not any(r["refs"][0] == s[3] for r in out["rods"])]
        if near:
            s = min(near, key=lambda s: abs(s[2] - tz))
            out["lights"].append({"x0": s[0] + ox, "x1": s[1] + ox, "z": s[2] - floor, "text": t, "refs": [s[3], h]})
    return out


# ---------------- khấu / bo cong, vòng chú thích ----------------

def curve_marks(d: Drawing2D, v: View, ox: float, floor: float, mod: dict) -> list[dict]:
    """Đường khấu/bo cong của khối (toạ độ mặt bằng/cao độ). `side` = 'l'/'r' khi một đầu nằm trên hông khối."""
    bx0, bx1 = mod["x0"] - ox, mod["x1"] - ox
    bz0, bz1 = mod["z0"] + floor, mod["z1"] + floor
    out = []
    for h in v.handles:
        e = d.entities[h]
        if d.roles.get(e.layer) != "hidden" or e.type not in DRAW_TYPES:
            continue
        pts = _pts(e)
        if not is_curve_mark(pts):
            continue
        b = entity_box(e, {})
        if not b or b[0] < bx0 - 5 or b[2] > bx1 + 5 or b[1] < bz0 - 5 or b[3] > bz1 + 5:
            continue
        side = "r" if abs(b[2] - bx1) <= 25 else ("l" if abs(b[0] - bx0) <= 25 else "")
        out.append({"kind": "curve", "side": side, "x0": round(b[0] + ox, 1), "x1": round(b[2] + ox, 1),
                    "z0": round(b[1] - floor, 1), "z1": round(b[3] - floor, 1), "refs": [h], "view": v.id})
    return out


def callouts(d: Drawing2D, v: View, ox: float, floor: float, mod: dict, sheet_handles=()) -> list[dict]:
    """Vòng chú thích (tròn lớn, không thuộc thân tủ) có tâm trong/sát khối + chữ gần nhất (≤ 1000 mm)."""
    bx0, bx1 = mod["x0"] - ox, mod["x1"] - ox
    bz0, bz1 = mod["z0"] + floor, mod["z1"] + floor
    out = []
    texts = _text_items(d, list(v.handles) + list(sheet_handles))
    for h in v.handles:
        e = d.entities[h]
        if not is_callout(e, d.roles.get(e.layer)) or not e.pts:
            continue
        cx, cy = e.pts[0][0], e.pts[0][1]
        if not (bx0 - 5 <= cx <= bx1 + 5 and bz0 - 5 <= cy <= bz1 + 5):
            continue
        # chữ của vòng chú thích đặt ngoài hình (chữ trong khối là ghi chú của khối, vd. đèn)
        near = sorted(((cx - tx) ** 2 + (cy - tz) ** 2, t, th) for tx, tz, t, th in texts
                      if not (bx0 < tx < bx1 and bz0 < tz < bz1))
        near = [n for n in near if n[0] <= 1000.0 ** 2]
        text, th = (near[0][1], near[0][2]) if near else ("", "")
        out.append({"kind": "callout", "x": round(cx + ox, 1), "z": round(cy - floor, 1), "text": text,
                    "meaning": meaning(d, text) if text else None, "refs": [h] + ([th] if th else []), "view": v.id})
    return out


def curve_details(d: Drawing2D, group: str) -> list[dict]:
    """Hình chi tiết khấu/bo cong trong các tờ của hạng mục: chữ nghĩa "curve" + bán kính cung ở hình gần chữ nhất."""
    info = d.groups.get(group) or {}
    sheets = [s for s in d.structure.sheets if s.id in set(info.get("sheets") or [])]
    out = []
    for s in sheets:
        hs = [h for h in s.handles if h in d.entities]
        for tx, tz, t, h in _text_items(d, hs):
            if not has_meaning(d, t, "curve"):
                continue
            radii = []
            for v in d.views:
                if v.sheet_id != s.id or not v.box:
                    continue
                dx = max(v.box[0] - tx, 0, tx - v.box[2])
                dz = max(v.box[1] - tz, 0, tz - v.box[3])
                if dx <= 300 and dz <= 300:
                    radii += [float(d.entities[a].arc[2]) for a in v.handles
                              if d.entities[a].type == "ARC" and getattr(d.entities[a], "arc", None)]
            out.append({"text": t, "radius": max(radii) if radii else None, "refs": [h]})
    return out


__all__ = ["callouts", "classify", "curve_details", "curve_marks", "door_symbol_area", "is_callout", "is_curve_mark",
           "levels", "read_interior"]
