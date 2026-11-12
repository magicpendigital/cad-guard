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

from .primitives import (BODY, DRAW_TYPES, EDGE_ZONE, SYMBOL_MIN, board_stacks, door_symbol_area, front_rects,
                         has_meaning, hsegs, is_callout, is_curve_mark, meaning, pts, text_items, vertical_boards, vsegs, xbox)
from .primitives import cell as _cell
from .views2d import Drawing2D, View, entity_box, rect_of

NOTE_DIST = 400.0  # ghi chú cách tầng tối đa để gán loại tầng
GLASS_MAX = 14.0
HANG_MIN = 800.0  # khoang dưới thanh treo cao tối thiểu (treo áo)

# tên cũ (lớp nguyên tố L1 nay ở `primitives.py`)
levels = board_stacks
_text_items, _hsegs, _vsegs, _pts, _xbox, _front_rects = text_items, hsegs, vsegs, pts, xbox, front_rects


def interior_score(d: Drawing2D, v: View) -> int:
    """Số dấu hiệu nội thất (chữ hộc, thiết bị, thanh treo, đèn, kính) trên hình."""
    return sum(1 for *_xy, t, _h in _text_items(d, v.handles) if meaning(d, t) in ("drawer", "appliance", "rod", "light", "glass"))


def classify(d: Drawing2D, views: list[View]) -> tuple[View, View, str] | None:
    """Hai+ mặt đứng cùng tiêu đề và cùng cờ (người vẽ chép tiêu đề): hình có nhiều ký hiệu mở cánh nhất là hình có
    cánh, hình ít ký hiệu nhất (và ≤ 1/2) là hình bỏ cánh. Trả (hình có cánh, hình bỏ cánh, lý do) hoặc None.

    Từ P4 KHÔNG còn gọi khi dựng: vai trò hình do `hypotheses.resolve` chấm các cách hiểu (ký hiệu cánh là một phần điểm)."""
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
    # vách đứng vẽ ở hình (chỉ hình bỏ cánh thật: ở hình có cánh nét đứng đôi là mép cánh/tay nắm)
    if interior:
        for q in vertical_boards(vs, hs, box):
            out["partitions"].append({"x0": q["x0"] + ox, "x1": q["x1"] + ox, "z0": q["z0"] - floor, "z1": q["z1"] - floor, "refs": q["refs"]})
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
