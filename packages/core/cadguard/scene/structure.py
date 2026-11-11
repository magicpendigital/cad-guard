"""Kết cấu thùng tủ: vách ngăn bắt buộc + kiểm kết cấu, theo nguyên tắc tủ không khung (frameless, hệ 32 mm).

Nguyên tắc (nguồn ghi ở `knowledge/skills/ket-cau-tu/SKILL.md`):
- Thùng gồm hồi (hông) trái/phải, nóc (tủ dưới có mặt đá: 2 thanh giằng trước/sau), đáy, hậu, vách ngăn, đợt.
- Cánh mở bằng bản lề bật phải bắt đế bản lề vào một tấm đứng: hồi hoặc VÁCH NGĂN. Hai cánh cạnh nhau cùng bắt bản lề vào
  đường ráp chung (bản lề quay lưng nhau) thì sau đường ráp phải có vách ngăn; cặp hai cánh mở từ giữa thì không cần.
- Ray ngăn kéo bắt vào hai tấm đứng: cột ngăn kéo hẹp hơn thùng phải có vách hai bên.
- Đợt ván 17–18 mm không nên vượt nhịp ~600–700 mm (võng); khoang rộng hơn cần vách hoặc đợt dày/nẹp.
- Cánh không rộng quá 600 mm và nên cao hơn rộng (Blum); rộng hơn nên chia 2 cánh, hoặc dùng cánh lật/tay nâng.

`plan_module(m, hinges, c)` trả vị trí vách ngăn (toạ độ X của hạng mục) kèm lý do; `check(scene, c, hinges_of)` trả các
lưu ý kết cấu cho màn 3D. Tất định, không sửa bản vẽ; vách tự thêm hiện nhãn "Tự thêm theo kết cấu".
"""
from __future__ import annotations

TOL = 3.0


def _rows(fronts) -> list[list]:
    """Mặt trước xếp theo hàng (khoảng cao chồng nhau > 50 %), mỗi hàng trái → phải."""
    rows: list[list] = []
    for f in sorted(fronts, key=lambda q: (q.z0, q.x0)):
        for r in rows:
            g = r[0]
            if min(f.z1, g.z1) - max(f.z0, g.z0) > 0.5 * min(f.z1 - f.z0, g.z1 - g.z0):
                r.append(f)
                break
        else:
            rows.append([f])
    return [sorted(r, key=lambda q: q.x0) for r in rows]


def plan_module(m, hinges: dict[str, str], c: dict) -> list[dict]:
    """Vách ngăn cần có trong khối `m`: [{x, reason, code}] (x = tâm vách, toạ độ hạng mục)."""
    if not getattr(m, "fronts", None) and not getattr(m, "shelves", 0):
        return []
    if c.get("partition_auto", "auto") != "auto":
        return []
    t = float(c["board_thickness"])
    x0, x1 = m.x, m.x + m.w
    out: list[dict] = []

    drawn = [q for q in (getattr(m, "inner", None) or []) if q.get("kind") == "partition"]

    def add(x: float, reason: str, code: str):
        if any(q["x0"] - 30 <= x <= q["x1"] + 30 for q in drawn):  # bản vẽ đã có vách ở đây (hình bỏ cánh)
            return
        if x0 + t + 50 < x < x1 - t - 50 and not any(abs(x - o["x"]) <= 30 for o in out):
            out.append({"x": round(x, 1), "reason": reason, "code": code})

    for row in _rows(m.fronts):
        for a, b in zip(row, row[1:]):
            xb = (a.x1 + b.x0) / 2
            if a.kind == "door" and hinges.get(a.id) == "r":
                add(xb, f"Cánh {a.id} bắt bản lề vào đường ráp này: cần vách ngăn để bắt đế bản lề.", "hinge")
            elif b.kind == "door" and hinges.get(b.id) == "l":
                add(xb, f"Cánh {b.id} bắt bản lề vào đường ráp này: cần vách ngăn để bắt đế bản lề.", "hinge")
            elif "drawer" in (a.kind, b.kind) and a.kind != b.kind:
                add(xb, "Ray ngăn kéo cần tấm đứng hai bên: thêm vách giữa ngăn kéo và cánh.", "drawer")
    # cột ngăn kéo hẹp hơn thùng: vách hai bên cột
    drawers = [f for f in m.fronts if f.kind == "drawer"]
    if drawers:
        dx0, dx1 = min(f.x0 for f in drawers), max(f.x1 for f in drawers)
        for xe in (dx0, dx1):
            if x0 + t + 50 < xe < x1 - t - 50:
                add(xe, "Ray ngăn kéo bắt vào tấm đứng: cột ngăn kéo cần vách ở cạnh này.", "drawer")
    # nhịp đợt: khoang có đợt rộng hơn nhịp cho phép -> vách tại đường ráp cánh gần giữa khoang
    span = float(c.get("shelf_max_span", 700))
    # có hình bỏ cánh: vách theo bản vẽ, không tự đặt vách vì nhịp đợt (kiểm kết cấu vẫn cảnh báo S06)
    from_drawing = bool(getattr(m, "interior", "")) and getattr(m, "interior", "") != getattr(m, "elevation", "")
    if getattr(m, "shelves", 0) and not from_drawing:
        bounds = sorted({round((a.x1 + b.x0) / 2, 1) for row in _rows(m.fronts) for a, b in zip(row, row[1:])})
        for _ in range(8):
            edges = [x0] + sorted(o["x"] for o in out) + [x1]
            wide = [(a, b) for a, b in zip(edges, edges[1:]) if b - a - t > span]
            if not wide:
                break
            a, b = wide[0]
            cand = [x for x in bounds if a + 150 < x < b - 150]
            if not cand:  # không có đường ráp cánh trong khoang: không đặt vách sau cánh, để kiểm kết cấu cảnh báo
                break
            x = min(cand, key=lambda v: abs(v - (a + b) / 2))
            before = len(out)
            add(x, f"Khoang có đợt rộng {b - a:.0f} mm > nhịp đợt {span:.0f} mm: thêm vách để đợt không võng.", "span")
            if len(out) == before:
                break
    return sorted(out, key=lambda o: o["x"])


def check(scene, c: dict, hinges_of) -> list[dict]:
    """Lưu ý kết cấu từng khối: [{module, code, level, title, why, fix}]. `hinges_of(m)` -> {front id: 'l'|'r'}."""
    out = []
    dmax = float(c.get("door_max_width", 600))
    span = float(c.get("shelf_max_span", 700))
    t = float(c["board_thickness"])
    for m in scene.modules:
        if getattr(m, "form", "cabinet") in ("filler", "panel"):
            continue
        for f in m.fronts:
            w, h = f.x1 - f.x0, f.z1 - f.z0
            if f.kind == "door" and w > dmax + TOL:
                out.append({"module": m.id, "code": "S01", "level": "warn", "title": f"Cánh {f.id} rộng {w:.0f} mm",
                            "why": f"Cánh mở bản lề nên rộng tối đa {dmax:.0f} mm (Blum); rộng hơn dễ xệ, cần thêm bản lề.",
                            "fix": "Chia thành 2 cánh, hoặc thêm bản lề và kiểm tải trọng theo catalogue bản lề."})
            elif f.kind == "door" and w > h + TOL:
                out.append({"module": m.id, "code": "S02", "level": "info", "title": f"Cánh {f.id} rộng hơn cao ({w:.0f} × {h:.0f})",
                            "why": "Cánh mở bản lề nên cao hơn rộng (Blum). Cánh thấp và rộng thường làm cánh lật/tay nâng.",
                            "fix": "Cân nhắc cánh lật (tay nâng) hoặc chia 2 cánh."})
        parts = plan_module(m, hinges_of(m), c)
        for p in parts:
            out.append({"module": m.id, "code": {"hinge": "S03", "drawer": "S04", "span": "S05"}[p["code"]], "level": "auto",
                        "title": f"Tự thêm vách ngăn trong khối {m.id} (cách mép trái {p['x'] - m.x:.0f} mm)", "why": p["reason"],
                        "fix": "Đã thêm vào tấm ván và danh sách cắt. Nếu bản vẽ thiếu vách này, bổ sung trong AutoCAD."})
        if getattr(m, "shelves", 0):
            edges = [m.x] + [p["x"] for p in parts] + [m.x + m.w]
            for a, b in zip(edges, edges[1:]):
                if b - a - t > span + TOL:
                    out.append({"module": m.id, "code": "S06", "level": "warn", "title": f"Khoang rộng {b - a:.0f} mm có đợt",
                                "why": f"Đợt ván {t:.0f} mm vượt nhịp {span:.0f} mm dễ võng.",
                                "fix": "Thêm vách ngăn, dùng đợt dày hơn hoặc nẹp/thanh đỡ dưới đợt."})
    return out


__all__ = ["check", "plan_module"]
