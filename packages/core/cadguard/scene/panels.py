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
           "door": "Cánh", "drawer": "Mặt ngăn kéo", "panel": "Tấm ốp"}
GROUP_OF = {"side_l": "thùng", "side_r": "thùng", "top": "thùng", "bottom": "thùng", "shelf": "đợt", "back": "hậu",
            "door": "cánh", "drawer": "cánh", "panel": "ốp"}
COLORS = {"side_l": (0.80, 0.70, 0.55), "side_r": (0.80, 0.70, 0.55), "top": (0.74, 0.64, 0.50), "bottom": (0.74, 0.64, 0.50),
          "back": (0.62, 0.60, 0.58), "shelf": (0.86, 0.78, 0.62), "door": (0.93, 0.89, 0.80), "drawer": (0.90, 0.84, 0.72),
          "panel": (0.88, 0.82, 0.70)}


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
    t = float(c["board_thickness"])
    bt = float(c["back_thickness"])
    td = float(c["door_thickness"])
    gap = float(c["door_gap"])
    out: list[Panel] = []
    for m in scene.modules:
        if m.w <= 2 * t or m.h <= 2 * t or m.d <= td + bt:
            continue
        x0, x1, z0, z1 = m.x, m.x + m.w, m.z0, m.z0 + m.h
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
        if c["joint"] == "side_over":
            P("side_l", x0, yf, z0, x0 + t, yc, z1, 1)
            P("side_r", x1 - t, yf, z0, x1, yc, z1, 1)
            P("top", x0 + t, yf, z1 - t, x1 - t, yc, z1, 1)
            P("bottom", x0 + t, yf, z0, x1 - t, yc, z0 + t, 1)
        else:
            P("top", x0, yf, z1 - t, x1, yc, z1, 3)
            P("bottom", x0, yf, z0, x1, yc, z0 + t, 3)
            P("side_l", x0, yf, z0 + t, x0 + t, yc, z1 - t, 1)
            P("side_r", x1 - t, yf, z0 + t, x1, yc, z1 - t, 1)
        n = int(m.shelves or 0)
        if n > 0:
            inner0, inner1 = z0 + t, z1 - t
            step = (inner1 - inner0) / (n + 1)
            ys = yf + float(c["shelf_setback"])
            yback = (yb - bt) if c["back_type"] == "screw" else (yb - float(c["back_inset"]) - bt)
            for i in range(1, n + 1):
                zs = inner0 + i * step - t / 2
                P("shelf", x0 + t, ys, zs, x1 - t, yback, zs + t, 1, n=i)
        for j, f in enumerate(m.fronts, 1):
            if c["door_overlay"] == "inset":
                fx0, fx1, fz0, fz1 = max(f.x0, x0 + t) + gap / 2, min(f.x1, x1 - t) - gap / 2, max(f.z0, z0 + t) + gap / 2, min(f.z1, z1 - t) - gap / 2
                fy0, fy1 = yf, yf + td
            else:
                fx0, fx1, fz0, fz1 = f.x0 + gap / 2, f.x1 - gap / 2, f.z0 + gap / 2, f.z1 - gap / 2
                fy0, fy1 = m.y, m.y + td
            if fx1 - fx0 > 20 and fz1 - fz0 > 20:
                P(f.kind if f.kind in ("door", "drawer") else "door", fx0, fy0, fz0, fx1, fy1, fz1, 4, n=j, front=f.id)
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
            out.append({"b": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], "z0": p.z0 + dz, "z1": p.z1 + dz,
                        "c": list(COLORS.get(p.part, (0.8, 0.8, 0.8))), "k": "panel-" + p.part, "n": p.id})
    return out


def _material(part: str, materials: list[dict]) -> str:
    """Vật liệu của bộ phận theo vật liệu người dùng đã xác nhận cho hạng mục (P2): khớp tên bộ phận."""
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
        L, W, T = p.dims
        mat = _material(p.part, materials or [])
        key = (PART_VI.get(p.part, p.part), L, W, T, mat, p.edges)
        r = rows.setdefault(key, {"part": key[0], "length": L, "width": W, "thickness": T, "material": mat,
                                  "edges": p.edges, "qty": 0, "modules": []})
        r["qty"] += 1
        if p.module not in r["modules"]:
            r["modules"].append(p.module)
        hinges += hinges_for(p, c)
    items = sorted(rows.values(), key=lambda r: (r["material"], r["part"], -r["length"]))
    area = sum(r["length"] * r["width"] * r["qty"] for r in items) / 1e6
    edge_m = sum((2 * (r["length"] + r["width"]) if r["edges"] == 4 else r["length"] * r["edges"]) * r["qty"] for r in items) / 1000
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
