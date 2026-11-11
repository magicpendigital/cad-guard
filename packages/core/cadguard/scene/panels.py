"""P3: từ khối (cg.scene/2) + hồ sơ kết cấu xưởng (`construction.py`) ra TẤM VÁN, danh sách cắt, dán cạnh, bản lề.

Tất định. Quy ước toạ độ của cảnh: X ngang, Y sâu (mặt trước tủ ở Y nhỏ, tường ở Y lớn), Z cao; mm.
- Thùng: 2 hông, nóc, đáy (liên kết hông trùm hoặc nóc trùm), hậu (bắt vít sau thùng hoặc lọt rãnh), đợt (cách đều).
- Cánh/ngăn kéo: theo mặt trước đã đọc trên mặt đứng, trừ khe cánh; dày cánh đặt trước thùng.
- Danh sách cắt: dài × rộng × dày, số lượng, vật liệu (theo vật liệu người dùng đã xác nhận cho bộ phận, P2), cạnh dán.
- Bản lề: khối lượng cánh = rộng × cao × dày × khối lượng riêng; số bản lề theo bảng hồ sơ (mặc định theo Blum).
Đây là MÔ HÌNH THAM KHẢO để đối chiếu và dự trù, không phải dữ liệu chạy máy CNC.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

PART_VI = {"side_l": "Hông trái", "side_r": "Hông phải", "top": "Nóc", "bottom": "Đáy", "back": "Hậu", "shelf": "Đợt",
           "door": "Cánh", "drawer": "Mặt ngăn kéo", "panel": "Tấm ốp", "filler": "Tấm bù (đo thực tế)",
           "partition": "Vách ngăn", "rail": "Thanh giằng", "glass": "Đợt kính", "stone": "Mặt đá", "counter": "Tấm đỡ mặt đá",
           "drawer_in": "Mặt hộc trong", "rod": "Thanh treo", "appliance": "Thiết bị (không sản xuất)", "light": "Đèn",
           "drawer_box": "Lòng hộc"}
GROUP_OF = {"side_l": "thùng", "side_r": "thùng", "top": "thùng", "bottom": "thùng", "shelf": "đợt", "back": "hậu",
            "door": "cánh", "drawer": "cánh", "panel": "ốp", "filler": "ốp", "partition": "thùng", "rail": "thùng",
            "counter": "thùng", "drawer_in": "cánh"}
# vật liệu cố định (không phải ván), không tính vào diện tích ván/dán cạnh
FIXED_MAT = {"glass": "Kính", "stone": "Đá", "rod": "Phụ kiện (thanh treo)"}
VISUAL_ONLY = {"appliance", "light", "drawer_box"}  # chỉ để hình dung, không vào danh sách cắt
COLORS = {"side_l": (0.80, 0.70, 0.55), "side_r": (0.80, 0.70, 0.55), "top": (0.74, 0.64, 0.50), "bottom": (0.74, 0.64, 0.50),
          "back": (0.62, 0.60, 0.58), "shelf": (0.86, 0.78, 0.62), "door": (0.93, 0.89, 0.80), "drawer": (0.90, 0.84, 0.72),
          "panel": (0.88, 0.82, 0.70), "filler": (0.80, 0.80, 0.78), "partition": (0.70, 0.60, 0.46), "rail": (0.74, 0.64, 0.50),
          "glass": (0.70, 0.86, 0.92), "stone": (0.52, 0.52, 0.55), "counter": (0.74, 0.64, 0.50), "drawer_in": (0.90, 0.84, 0.72),
          "rod": (0.62, 0.62, 0.66), "appliance": (0.86, 0.87, 0.90), "light": (1.0, 0.93, 0.55), "drawer_box": (0.84, 0.76, 0.60)}


@dataclass
class Panel:
    id: str
    module: str
    part: str
    x0: float
    y0: float
    z0: float
    x1: float
    y1: float
    z1: float
    edges: int = 0  # số cạnh dán
    meta: dict = field(default_factory=dict)

    @property
    def dims(self) -> tuple[float, float, float]:
        """(dài, rộng, dày) của tấm: dày = cạnh nhỏ nhất."""
        a = sorted([self.x1 - self.x0, self.y1 - self.y0, self.z1 - self.z0])
        return round(a[2], 1), round(a[1], 1), round(a[0], 1)


def panels_for(scene, c: dict) -> list[Panel]:
    """Tấm ván của hạng mục, đọc từ mô hình tủ chuẩn `cg.cabinet/1` (nhận cả `Scene2`: tự chuyển)."""
    from .cabinet import as_cabinet

    scene = as_cabinet(scene)
    t = float(c["board_thickness"])
    bt = float(c["back_thickness"])
    td = float(c["door_thickness"])
    gap = float(c["door_gap"])
    out: list[Panel] = []
    for m in scene.modules:
        if m.w <= 2 * t or m.h <= 2 * t or m.d <= td + bt:
            continue
        x0, x1, z0, z1 = m.x, m.x + m.w, m.z0, m.z0 + m.h
        if getattr(m, "form", "cabinet") == "filler":  # tấm bù đo thực tế: một tấm mặt trước
            out.append(Panel(f"{m.id}:filler", m.id, "filler", x0, m.y, z0, x1, m.y + t, z1, 2, {}))
            continue
        if getattr(m, "form", "cabinet") == "panel":  # tấm ốp (vách TV…): một tấm mặt trước, không thùng
            out.append(Panel(f"{m.id}:panel", m.id, "panel", x0, m.y, z0, x1, m.y + t, z1, 4, {}))
            continue
        has_front = bool(m.fronts)
        yf = m.y + (td if has_front else 0.0)  # mặt trước thùng (cánh đặt trước thùng)
        yb = m.y + m.d  # mặt sau thùng
        P = lambda part, a, b, cc, dd, e, f, edges, **kw: out.append(  # noqa: E731
            Panel(f"{m.id}:{part}{kw.pop('n', '')}", m.id, part, a, b, cc, dd, e, f, edges, kw))
        if c["back_type"] == "screw":
            yc = yb - bt  # thùng dừng trước hậu
            P("back", x0, yc, z0, x1, yb, z1, 0)
        else:
            yc = yb
            gd = float(c["groove_depth"])
            yk = yb - float(c["back_inset"])
            P("back", x0 + t - gd, yk - bt, z0 + t - gd, x1 - t + gd, yk, z1 - t + gd, 0)
        rails = m.kind == "base" and c.get("base_top", "rails") == "rails"  # tủ dưới đỡ mặt đá: 2 thanh giằng
        rw = float(c.get("rail_width", 100))

        def top(a, b, edges):
            if rails:
                P("rail", a, yf, z1 - t, b, yf + rw, z1, edges, n="_f")
                P("rail", a, yc - rw, z1 - t, b, yc, z1, edges, n="_b")
            else:
                P("top", a, yf, z1 - t, b, yc, z1, edges)

        if c["joint"] == "side_over":
            P("side_l", x0, yf, z0, x0 + t, yc, z1, 1)
            P("side_r", x1 - t, yf, z0, x1, yc, z1, 1)
            top(x0 + t, x1 - t, 1)
            P("bottom", x0 + t, yf, z0, x1 - t, yc, z0 + t, 1)
        else:
            top(x0, x1, 3)
            P("bottom", x0, yf, z0, x1, yc, z0 + t, 3)
            P("side_l", x0, yf, z0 + t, x0 + t, yc, z1 - t, 1)
            P("side_r", x1 - t, yf, z0 + t, x1, yc, z1 - t, 1)
        hinges = hinge_sides(m.fronts, x0, x1)
        from .structure import plan_module

        parts = plan_module(m, hinges, c)  # vách ngăn bắt buộc theo kết cấu (bản lề, ray, nhịp đợt)
        for i, pt in enumerate(parts, 1):
            P("partition", pt["x"] - t / 2, yf, z0 + t, pt["x"] + t / 2, yc, z1 - t, 1, n=i, auto=True, reason=pt["reason"])
        inner = list(getattr(m, "inner", None) or [])
        lvls = [q for q in inner if q.get("kind") in ("shelf", "glass", "stone")]
        n = 0 if lvls else int(m.shelves or 0)  # có tầng đọc từ hình bỏ cánh: đặt đúng cao độ, không chia đều
        if lvls or inner:
            _inner_panels(P, m, c, inner, parts, yf, yb, yc, t, bt)
        _mark_curves(out, m)
        if n > 0:
            inner0, inner1 = z0 + t, z1 - t
            step = (inner1 - inner0) / (n + 1)
            ys = yf + float(c["shelf_setback"])
            yback = (yb - bt) if c["back_type"] == "screw" else (yb - float(c["back_inset"]) - bt)
            walls = [x0 + t] + [v for pt in parts for v in (pt["x"] - t / 2, pt["x"] + t / 2)] + [x1 - t]
            for k, (a, b) in enumerate(zip(walls[::2], walls[1::2]), 1):  # đợt theo từng khoang giữa các vách
                for i in range(1, n + 1):
                    zs = inner0 + i * step - t / 2
                    P("shelf", a, ys, zs, b, yback, zs + t, 1, n=f"{k}.{i}" if len(parts) else i)
        for j, f in enumerate(m.fronts, 1):
            if c["door_overlay"] == "inset":
                fx0, fx1, fz0, fz1 = max(f.x0, x0 + t) + gap / 2, min(f.x1, x1 - t) - gap / 2, max(f.z0, z0 + t) + gap / 2, min(f.z1, z1 - t) - gap / 2
                fy0, fy1 = yf, yf + td
            else:
                fx0, fx1, fz0, fz1 = f.x0 + gap / 2, f.x1 - gap / 2, f.z0 + gap / 2, f.z1 - gap / 2
                fy0, fy1 = m.y, m.y + td
            if fx1 - fx0 > 20 and fz1 - fz0 > 20:
                P(f.kind if f.kind in ("door", "drawer") else "door", fx0, fy0, fz0, fx1, fy1, fz1, 4, n=j, front=f.id,
                  md=m.d, mkind=m.kind, t=t, hinge=hinges.get(f.id, "l"))
    return out


def _inner_panels(P, m, c, inner, parts, yf, yb, yc, t, bt) -> None:
    """Nội thất đọc từ hình bỏ cánh: tầng ngang đúng cao độ (ván, kính, ván đỡ + mặt đá) theo từng khoang giữa các vách,
    hộc trong (mặt hộc + lòng hộc), thanh treo, đèn, thiết bị (chỉ để hình dung)."""
    x0, x1 = m.x, m.x + m.w
    ys = yf + float(c["shelf_setback"])
    yback = (yb - bt) if c["back_type"] == "screw" else (yb - float(c["back_inset"]) - bt)
    drawn = [q for q in inner if q.get("kind") == "partition"]

    def bays_at(z: float) -> list[tuple[float, float]]:  # khoang tại cao độ z: vách tự thêm (suốt) + vách vẽ có mặt ở z
        xs = [(pt["x"] - t / 2, pt["x"] + t / 2) for pt in parts] + [(q["x0"], q["x1"]) for q in drawn if q["z0"] + 1 < z < q["z1"] - 1]
        walls = [x0 + t] + [v for a, b in sorted(xs) for v in (a, b)] + [x1 - t]
        return list(zip(walls[::2], walls[1::2]))

    k = 0
    for q in sorted(inner, key=lambda q: (q["z0"], q["x0"])):
        kind = q.get("kind")
        k += 1
        if kind == "partition":
            P("partition", q["x0"], yf, q["z0"], q["x1"], yc, q["z1"], 1, n=f"v{k}", drawn=True)
        if kind in ("shelf", "glass", "stone"):
            lines = q.get("lines") or [q["z0"], q["z1"]]
            bays = bays_at((q["z0"] + q["z1"]) / 2)  # tấm đặt TRÊN vách thấp thì chạy suốt
            for j, (a, b) in enumerate(bays, 1):
                if min(b, q["x1"]) - max(a, q["x0"]) < 0.5 * (b - a):
                    continue
                n = f"{k}.{j}" if len(bays) > 1 else k
                if kind == "glass":
                    th = max(q["z1"] - q["z0"], 5.0)
                    P("glass", a, ys, q["z0"], b, yback, q["z0"] + th, 0, n=n)
                elif kind == "stone":
                    zs = lines[-2] if len(lines) >= 2 else q["z1"] - 20.0
                    if zs - lines[0] >= 10:
                        P("counter", a, yf, lines[0], b, yc, zs, 1, n=n)
                else:
                    th = q["z1"] - q["z0"]
                    th = th if 10 <= th <= 60 else t
                    P("shelf", a, ys, q["z0"], b, yback, q["z0"] + th, 1, n=n)
            if kind == "stone":  # mặt đá phủ cả bề ngang khối, từ mặt trước thùng tới mặt sau
                zs = lines[-2] if len(lines) >= 2 else q["z1"] - 20.0
                P("stone", x0, m.y, zs, x1, yb, max(q["z1"], zs + 10), 0, n=k)
        elif kind == "drawer":
            a, b = max(q["x0"], x0 + t) + 2, min(q["x1"], x1 - t) - 2
            if b - a > 50 and q["z1"] - q["z0"] > 50:
                yd = yf + 20.0  # mặt hộc lùi sau cánh
                P("drawer_in", a, yd, q["z0"] + 2, b, yd + t, q["z1"] - 2, 4, n=k)
                P("drawer_box", a + t, yd + t, q["z0"] + 12, b - t, yback - 10, q["z0"] + max(0.6 * (q["z1"] - q["z0"]), 60), 0, n=k)
        elif kind == "rod":
            zc = (q["z0"] + q["z1"]) / 2
            yc2 = (yf + yb) / 2
            P("rod", max(q["x0"], x0 + t), yc2 - 12, zc - 12, min(q["x1"], x1 - t), yc2 + 12, zc + 12, 0, n=k)
        elif kind == "light":
            P("light", max(q["x0"], x0 + t), yf + 30, q["z0"], min(q["x1"], x1 - t), yf + 60, q["z1"], 0, n=k)
        elif kind == "appliance":
            P("appliance", q["x0"], yf + 30, q["z0"], q["x1"], yb - 40, q["z1"], 0, n=k)


def _mark_curves(out: list, m) -> None:
    """Đường khấu/bo cong (ký hiệu trên mặt đứng): ghi vào tấm hông tương ứng để danh sách cắt nhắc xem chi tiết."""
    for f in getattr(m, "features", None) or []:
        if f.get("kind") != "curve" or f.get("on") == "drawer" or f.get("side") not in ("l", "r"):
            continue
        part = "side_r" if f["side"] == "r" else "side_l"
        for pn in out:
            if pn.module == m.id and pn.part == part:
                r = f" R{f['radius']:.0f}" if f.get("radius") else ""
                pn.meta["note"] = f"có khấu bo cong{r}, xem chi tiết"


def hinge_sides(fronts, mx0: float, mx1: float) -> dict[str, str]:
    """Bên bản lề của từng cánh trong một khối. Cánh cùng hàng (khoảng cao chồng nhau) xếp trái → phải rồi ghép cặp:
    cặp hai cánh mở đối xứng (trái `l`, phải `r`); hàng một cánh: nằm nửa trái khối thì bản lề trái, nửa phải thì phải
    (giữa/đủ khối: trái); hàng lẻ thì cánh cuối bản lề phải."""
    doors = [f for f in fronts if f.kind != "drawer"]
    out: dict[str, str] = {}
    seen: set[str] = set()
    mc = (mx0 + mx1) / 2
    for f in sorted(doors, key=lambda q: (q.z0, q.x0)):
        if f.id in seen:
            continue
        row = sorted([g for g in doors if g.id not in seen and min(f.z1, g.z1) - max(f.z0, g.z0) > 0.5 * min(f.z1 - f.z0, g.z1 - g.z0)],
                     key=lambda q: q.x0)
        seen.update(g.id for g in row)
        if len(row) == 1:
            out[f.id] = "r" if (f.x0 + f.x1) / 2 > mc + 1.0 else "l"
            continue
        for i, g in enumerate(row):
            out[g.id] = "r" if (i % 2 == 1 or (i == len(row) - 1 and len(row) % 2 == 1)) else "l"
    return out


# --- Đóng/mở cánh trên trình xem (chỉ để hình dung, không vào danh sách cắt) ---
OPEN_DEG = 90.0  # cánh mở tối đa
SLIDE_FRAC = 0.6  # ngăn kéo trượt ra theo tỉ lệ chiều sâu khối
HANDLE_COLOR = (0.30, 0.30, 0.32)
TRAY_COLOR = (0.84, 0.76, 0.60)


def front_motion(kind: str, fx0: float, fy0: float, fx1: float, md: float, hinge: str = "l") -> dict:
    """Cách mở một mặt trước. Cánh: bản lề (`l`/`r`, xem `hinge_sides`) và trục đứng qua (x, y) ở mép bản lề,
    mặt ngoài cánh; xoay ra phía trước (Y giảm) tới `angle` độ. Ngăn kéo: trượt ra phía trước `slide` mm."""
    if kind == "drawer":
        return {"open": "slide", "slide": round(SLIDE_FRAC * md, 1)}
    return {"open": "swing", "hinge": hinge, "pivot": [fx0 if hinge == "l" else fx1, fy0], "angle": OPEN_DEG}


def front_extras(kind: str, motion: dict, fx0: float, fy0: float, fz0: float, fx1: float, fy1: float, fz1: float,
                 mkind: str, md: float, t: float) -> list[tuple[str, tuple[float, float, float, float, float, float]]]:
    """Hộp phụ đi theo mặt trước: tay nắm (để phân biệt từng cánh) và lòng ngăn kéo (thấy khi trượt ra)."""
    w, h = fx1 - fx0, fz1 - fz0
    out: list[tuple[str, tuple]] = []
    if kind == "drawer":
        hw = min(0.4 * w, 320.0)
        zc = fz1 - min(60.0, h / 2)
        xc = (fx0 + fx1) / 2
        out.append(("handle", (xc - hw / 2, fy0 - 25, zc - 8, xc + hw / 2, fy0, zc + 8)))
        ins, th = max(t, 12.0) + 10, 12.0
        tx0, tx1, ty0, ty1 = fx0 + ins, fx1 - ins, fy1, fy1 + max(0.85 * md - (fy1 - fy0), 50.0)
        tz0, tz1 = fz0 + 20, fz0 + 20 + max(0.6 * h, 40.0)
        if tx1 - tx0 > 2 * th and tz1 - tz0 > th:
            out += [("tray", (tx0, ty0, tz0, tx0 + th, ty1, tz1)), ("tray", (tx1 - th, ty0, tz0, tx1, ty1, tz1)),
                    ("tray", (tx0 + th, ty0, tz0, tx1 - th, ty1, tz0 + th)), ("tray", (tx0 + th, ty1 - th, tz0, tx1 - th, ty1, tz1))]
        return out
    ln = min(160.0, 0.3 * h)
    if h < ln + 160:
        zc = (fz0 + fz1) / 2
    elif mkind == "base":
        zc = fz1 - 80 - ln / 2
    elif mkind == "wall":
        zc = fz0 + 80 + ln / 2
    else:
        zc = min(max(1000.0, fz0 + 80 + ln / 2), fz1 - 80 - ln / 2)
    xc = (fx1 - 45) if motion.get("hinge") == "l" else (fx0 + 45)
    if w < 120:
        xc = (fx0 + fx1) / 2
    out.append(("handle", (xc - 8, fy0 - 25, zc - ln / 2, xc + 8, fy0, zc + ln / 2)))
    return out


def _box(x0, y0, z0, x1, y1, z1, color, kind, name, motion=None) -> dict:
    d = {"b": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], "z0": z0, "z1": z1, "c": list(color), "k": kind, "n": name}
    if motion:
        d["m"] = motion
    return d


def _shift(motion: dict, dx: float, dy: float) -> dict:
    if "pivot" not in motion:
        return dict(motion)
    return {**motion, "pivot": [motion["pivot"][0] + dx, motion["pivot"][1] + dy]}


def block_fronts(boxes_: list[dict], scene, gap: float) -> list[dict]:
    """Chế độ Hình khối (`boxes2`): thêm khe giữa các mặt trước, cách mở (`m`), tay nắm và lòng ngăn kéo."""
    by_front = {f.id: (m, f) for m in scene.modules for f in m.fronts}
    sides = {k: v for m in scene.modules for k, v in hinge_sides(m.fronts, m.x, m.x + m.w).items()}
    out: list[dict] = []
    for b in boxes_:
        hit = by_front.get(b["n"]) if str(b.get("k", "")).startswith("front") else None
        if not hit:
            out.append(b)
            continue
        m, f = hit
        kind = "drawer" if f.kind == "drawer" else "door"
        ys = [p[1] for p in b["b"]]
        fx0, fx1, fz0, fz1 = f.x0 + gap / 2, f.x1 - gap / 2, f.z0 + gap / 2, f.z1 - gap / 2
        fy0, fy1 = min(ys), max(ys)
        if fx1 - fx0 <= 20 or fz1 - fz0 <= 20:
            out.append(b)
            continue
        mo = front_motion(kind, fx0, fy0, fx1, m.d, sides.get(f.id, "l"))
        out.append(_box(fx0, fy0, fz0, fx1, fy1, fz1, b["c"], b["k"], b["n"], mo))
        for i, (part, (a, bb, cc, dd, e, g)) in enumerate(front_extras(kind, mo, fx0, fy0, fz0, fx1, fy1, fz1, m.kind, m.d, 17.0)):
            out.append(_box(a, bb, cc, dd, e, g, HANDLE_COLOR if part == "handle" else TRAY_COLOR,
                            f"front-{part}", f"{b['n']}.{part}{i}", mo))
    return out


def hinges_for(p: Panel, c: dict) -> int:
    if p.part != "door":
        return 0
    w, h = p.x1 - p.x0, p.z1 - p.z0
    kg = w * h * (p.y1 - p.y0) * float(c["board_density"]) / 1e9
    n = 2 if kg <= float(c["hinge_2_max_kg"]) else (3 if kg <= float(c["hinge_3_max_kg"]) else 4)
    if h > 1600:  # cánh cao hẹp: tối thiểu 3 (Blum khuyến nghị)
        n = max(n, 3)
    if w > float(c["hinge_wide_door"]):
        n += 1
    return n


def boxes(panels: list[Panel], mode: str = "panel") -> list[dict]:
    """Hộp cho trình xem: `panel` | `explode` (tách lớp theo hướng từ tâm khối) | `xray` (bỏ cánh + hậu để thấy bên trong)."""
    out = []
    by_mod: dict[str, list[Panel]] = {}
    for p in panels:
        by_mod.setdefault(p.module, []).append(p)
    for mid, ps in by_mod.items():
        cx = (min(p.x0 for p in ps) + max(p.x1 for p in ps)) / 2
        cy = (min(p.y0 for p in ps) + max(p.y1 for p in ps)) / 2
        cz = (min(p.z0 for p in ps) + max(p.z1 for p in ps)) / 2
        for p in ps:
            if mode == "xray" and p.part in ("door", "drawer", "back"):
                continue
            dx = dy = dz = 0.0
            if mode == "explode":
                k = 0.45
                px, py, pz = (p.x0 + p.x1) / 2, (p.y0 + p.y1) / 2, (p.z0 + p.z1) / 2
                dims = (p.x1 - p.x0, p.y1 - p.y0, p.z1 - p.z0)
                axis = dims.index(min(dims))  # tách theo pháp tuyến của tấm
                if axis == 0:
                    dx = (px - cx) * k
                elif axis == 1:
                    dy = (py - cy) * k * 2 + (-150 if p.part in ("door", "drawer") else 0)
                else:
                    dz = (pz - cz) * k
            x0, x1, y0, y1 = p.x0 + dx, p.x1 + dx, p.y0 + dy, p.y1 + dy
            mo = None
            base_mo = None
            if p.part in ("door", "drawer") and "md" in p.meta:
                base_mo = front_motion(p.part, p.x0, p.y0, p.x1, p.meta["md"], p.meta.get("hinge", "l"))
                mo = _shift(base_mo, dx, dy)
            out.append(_box(x0, y0, p.z0 + dz, x1, y1, p.z1 + dz, COLORS.get(p.part, (0.8, 0.8, 0.8)), "panel-" + p.part, p.id, mo))
            if mo:
                for i, (part, (a, bb, cc, dd, e, g)) in enumerate(front_extras(
                        p.part, base_mo, p.x0, p.y0, p.z0, p.x1, p.y1, p.z1, p.meta.get("mkind", ""), p.meta["md"], p.meta.get("t", 17.0))):
                    out.append(_box(a + dx, bb + dy, cc + dz, dd + dx, e + dy, g + dz, HANDLE_COLOR if part == "handle" else TRAY_COLOR,
                                    "panel-" + part, f"{p.id}.{part}{i}", mo))
    return out


def _material(part: str, materials: list[dict]) -> str:
    """Vật liệu của bộ phận theo vật liệu người dùng đã xác nhận cho hạng mục (P2): khớp tên bộ phận."""
    if part in FIXED_MAT:
        return FIXED_MAT[part]
    want = GROUP_OF.get(part, "")
    alias = {"thùng": ("thùng", "hông", "nóc", "đáy"), "đợt": ("đợt", "thùng"), "hậu": ("hậu",), "cánh": ("cánh", "ngăn kéo")}
    for m in materials:
        comp = (m.get("component") or "").lower()
        if any(a in comp for a in alias.get(want, (want,))):
            return str(m.get("spec") or m.get("material"))
    return "Chưa gán"


def cutlist(panels: list[Panel], c: dict, materials: list[dict] | None = None) -> dict:
    rows: dict[tuple, dict] = {}
    hinges = 0
    for p in panels:
        if p.part in VISUAL_ONLY:
            continue
        L, W, T = p.dims
        mat = _material(p.part, materials or [])
        label = PART_VI.get(p.part, p.part) + (f" ({p.meta['note']})" if p.meta.get("note") else "")
        key = (label, L, W, T, mat, p.edges)
        r = rows.setdefault(key, {"part": key[0], "length": L, "width": W, "thickness": T, "material": mat,
                                  "edges": p.edges, "qty": 0, "modules": [], "board": p.part not in FIXED_MAT})
        r["qty"] += 1
        if p.module not in r["modules"]:
            r["modules"].append(p.module)
        hinges += hinges_for(p, c)
    items = sorted(rows.values(), key=lambda r: (r["material"], r["part"], -r["length"]))
    boards = [r for r in items if r["board"]]  # diện tích ván, dán cạnh: không tính kính, đá, phụ kiện
    area = sum(r["length"] * r["width"] * r["qty"] for r in boards) / 1e6
    edge_m = sum((2 * (r["length"] + r["width"]) if r["edges"] == 4 else r["length"] * r["edges"]) * r["qty"] for r in boards) / 1000
    return {"rows": items, "panels": len(panels), "area_m2": round(area, 2), "edge_band_m": round(edge_m, 1),
            "hinges": hinges, "hinge_brand": c.get("hinge_brand"), "note": "Mô hình tham khảo, không phải dữ liệu chạy máy."}


def cutlist_csv(cl: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Chi tiết", "Dài (mm)", "Rộng (mm)", "Dày (mm)", "Số lượng", "Vật liệu", "Số cạnh dán", "Khối"])
    for r in cl["rows"]:
        w.writerow([r["part"], r["length"], r["width"], r["thickness"], r["qty"], r["material"], r["edges"], " ".join(r["modules"])])
    w.writerow([])
    w.writerow(["Tổng diện tích ván (m²)", cl["area_m2"]])
    w.writerow(["Tổng dán cạnh (m)", cl["edge_band_m"]])
    w.writerow([f"Bản lề ({cl.get('hinge_brand') or ''})", cl["hinges"]])
    return buf.getvalue()


__all__ = ["Panel", "boxes", "cutlist", "cutlist_csv", "hinges_for", "panels_for"]
