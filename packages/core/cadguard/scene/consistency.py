"""L4 (P3) — BỘ CHẤM NHẤT QUÁN của một cách hiểu bản vẽ (thiết kế `docs/research/kien-truc-doc-ban-ve-tong-the.md`).

Chế độ CHỈ BÁO: chấm mô hình tủ `cg.cabinet/1` đã dựng, liệt kê mâu thuẫn kèm bằng chứng (handle), KHÔNG đổi lựa chọn.
Ở P4, cùng bộ chấm này dùng để so nhiều cách hiểu và chọn cách nhất quán nhất.

Ràng buộc (mỗi mục: mã, mức, khối/khoang, vì sao, gợi ý, `refs`):
- Kết cấu (K):
  - K01 hai mặt trước chồng nhau;
  - K02 mặt trước lòi ra ngoài khối;
  - K03 tấm ngang cắt ngang qua vách;
  - K04 tấm ngang xuyên qua ô thiết bị / hộc trong;
  - K05 đồ bên trong nằm ngoài khối;
  - K06 thanh treo trong khoang thấp (< 800);
  - K07 hộc trong cao bất thường (> 600: thường là cả khoang bị đọc nhầm thành hộc).
- Đối chiếu hình (H):
  - H01 đường ráp hai hàng cánh (hình có cánh) không có tấm ngang phía sau (hình bỏ cánh);
  - H02 số đo khối chưa có nguồn bản vẽ (mặc định).
- Thông tin (I): I01 khoang để hở (không có mặt trước), I02 khối đọc nội thất ở hình bỏ cánh.

Mức: `conflict` (mâu thuẫn — cách hiểu này khó đúng), `warn` (cần xem), `info` (ghi nhận). Điểm khối = 1 − 0,3 × số mâu
thuẫn − 0,1 × số cần xem (≥ 0); điểm hạng mục = trung bình các khối.
"""
from __future__ import annotations

from .cabinet import Cabinet, Node, Unit, as_cabinet

W = {"conflict": 0.3, "warn": 0.1, "info": 0.0}
SEAM_TOL = 60.0  # đường ráp hai hàng cánh cách tấm ngang tối đa
HANG_MIN = 800.0
DOOR_MIN = 400.0
DRAWER_MAX = 600.0  # hộc trong cao hơn mức này: khoang bị đọc nhầm thành hộc


def _ov(a0, a1, b0, b1) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _issue(code, level, u: Unit, title, why, fix, refs=(), node: Node | None = None) -> dict:
    return {"code": code, "level": level, "unit": u.id, "node": node.id if node else "", "title": title, "why": why, "fix": fix,
            "refs": [r for r in refs if r][:20]}


def _unit_issues(u: Unit) -> list[dict]:
    out: list[dict] = []
    if u.form in ("filler", "panel"):
        return out
    fronts = u.fronts
    inner = u.inner
    ux0, ux1, uz0, uz1 = u.x, u.x + u.w, u.z0, u.z0 + u.h
    # K01, K02 — mặt trước
    for i, f in enumerate(fronts):
        if f.x0 < ux0 - 10 or f.x1 > ux1 + 10 or f.z0 < uz0 - 10 or f.z1 > uz1 + 10:
            out.append(_issue("K02", "conflict", u, f"Mặt trước {f.id} lòi ra ngoài khối {u.id}",
                              "Cánh/ngăn kéo phải nằm trong khung khối.", "Kiểm lại chia khối hoặc mặt trước trên mặt đứng.", f.refs))
        for g in fronts[i + 1:]:
            a = _ov(f.x0, f.x1, g.x0, g.x1) * _ov(f.z0, f.z1, g.z0, g.z1)
            if a > 0.05 * min((f.x1 - f.x0) * (f.z1 - f.z0), (g.x1 - g.x0) * (g.z1 - g.z0)):
                out.append(_issue("K01", "conflict", u, f"Hai mặt trước {f.id} và {g.id} chồng nhau",
                                  "Hai cánh/ngăn kéo không thể chiếm cùng một chỗ.",
                                  "Thường do đọc nhầm khung (đường bao, ô thiết bị) thành cánh: xem lại hình có cánh.", f.refs + g.refs))
    levels = [q for q in inner if q.get("kind") in ("shelf", "glass", "stone")]
    parts = [q for q in inner if q.get("kind") == "partition"]
    boxes = [q for q in inner if q.get("kind") in ("drawer", "appliance")]
    # K03 — tấm ngang cắt qua vách (vách đi qua cả trên và dưới tấm)
    for L in levels:
        for p in parts:
            if L["x0"] < p["x0"] - 5 and L["x1"] > p["x1"] + 5 and p["z0"] < L["z0"] - 30 and p["z1"] > L["z1"] + 30:
                out.append(_issue("K03", "conflict", u, f"Tấm ngang cao {L['z0']:.0f} cắt qua vách ở {p['x0'] - u.x:.0f} mm",
                                  "Tấm ngang và vách không thể xuyên qua nhau.", "Một trong hai là nét khác (mép, ký hiệu): xem hình bỏ cánh.",
                                  L.get("refs", []) + p.get("refs", [])))
    # K04 — tấm ngang xuyên qua ô thiết bị / hộc trong
    for L in levels:
        for b in boxes:
            if _ov(L["x0"], L["x1"], b["x0"], b["x1"]) > 50 and b["z0"] + 20 < (L["z0"] + L["z1"]) / 2 < b["z1"] - 20:
                out.append(_issue("K04", "conflict", u, f"Tấm ngang cao {L['z0']:.0f} xuyên qua {'ô thiết bị' if b['kind'] == 'appliance' else 'hộc trong'}",
                                  "Tấm ngang không đi qua hộc/thiết bị.", "Kiểm lại cao độ tấm hoặc ô hộc/thiết bị.", L.get("refs", []) + b.get("refs", [])))
    # K05 — đồ bên trong nằm ngoài khối
    for q in inner:
        if q["x0"] < ux0 - 10 or q["x1"] > ux1 + 10 or q["z0"] < uz0 - 10 or q["z1"] > uz1 + 10:
            out.append(_issue("K05", "conflict", u, f"{q.get('kind')} nằm ngoài khối {u.id}", "Nội thất phải nằm trong thùng tủ.",
                              "Kiểm ghép hình bỏ cánh với mặt bằng (lệch trục X?).", q.get("refs", [])))
    # K06 — thanh treo trong khoang thấp
    for n in u.root.walk():
        for q in n.contents:
            if q.get("kind") == "rod":
                below = n.z0
                space = (q["z0"] + q["z1"]) / 2 - below
                if space < HANG_MIN:
                    out.append(_issue("K06", "warn", u, f"Thanh treo chỉ cách đáy khoang {space:.0f} mm",
                                      f"Khoang treo áo nên cao ≥ {HANG_MIN:.0f} mm dưới thanh treo.",
                                      "Kiểm lại cao độ thanh treo / tấm ngang bên dưới.", q.get("refs", []), n))
    # K07 — hộc trong cao bất thường
    for q in inner:
        if q.get("kind") == "drawer" and q["z1"] - q["z0"] > DRAWER_MAX:
            out.append(_issue("K07", "conflict", u, f"Hộc trong cao {q['z1'] - q['z0']:.0f} mm",
                              f"Hộc kéo bên trong hiếm khi cao quá {DRAWER_MAX:.0f} mm: có thể cả khoang bị đọc thành hộc.",
                              "Kiểm ô có chữ hộc trên hình (thiếu nét chia ô?) hoặc chọn lại hình bỏ cánh.", q.get("refs", [])))
    # H01 — đường ráp giữa hai hàng cánh cần tấm ngang phía sau (khi đã đọc tầng ở hình bỏ cánh)
    if levels and u.interior and u.interior != u.elevation:
        # chỉ cánh bản lề thật (cao ≥ 400): ngăn kéo hẹp xếp chồng có thể bị xếp loại "cánh" nhưng không cần tấm sau đường ráp
        doors = sorted((f for f in fronts if f.kind == "door" and f.z1 - f.z0 >= DOOR_MIN), key=lambda f: f.z0)
        seams = sorted({round((a.z1 + b.z0) / 2, 1) for a in doors for b in doors  # cánh b ngay trên cánh a, cùng cột
                        if a is not b and -10 <= b.z0 - a.z1 <= 60 and _ov(a.x0, a.x1, b.x0, b.x1) > 0.5 * min(a.x1 - a.x0, b.x1 - b.x0)})
        for z in seams:
            if not any(L["z0"] - SEAM_TOL <= z <= L["z1"] + SEAM_TOL for L in levels):
                out.append(_issue("H01", "warn", u, f"Đường ráp hai hàng cánh ở cao {z:.0f} không có tấm ngang phía sau",
                                  "Hình có cánh chia hai hàng cánh, hình bỏ cánh không có tấm ngang tương ứng.",
                                  "Kiểm hình bỏ cánh (thiếu đợt cố định?) hoặc chọn lại hình bỏ cánh.",
                                  [r for f in doors for r in f.refs]))
    # H02 — số đo chưa có nguồn bản vẽ
    for k in ("w", "d", "h"):
        s = u.src.get(k)
        if s is not None and s.kind == "default":
            out.append(_issue("H02", "warn", u, f"{ {'w': 'Rộng', 'd': 'Sâu', 'h': 'Cao'}[k] } khối {u.id} đang là số mặc định",
                              "Không tìm thấy số này trên bản vẽ (mặt bằng, mặt cắt).", "Nhập số hoặc chấp nhận gợi ý có bằng chứng."))
    # I01 — khoang lá để hở (không mặt trước nào che); I02 — nguồn nội thất
    if u.form == "cabinet" and fronts:
        for n in u.compartments():
            area = max(1.0, (n.x1 - n.x0) * (n.z1 - n.z0))
            cov = sum(_ov(f.x0, f.x1, n.x0, n.x1) * _ov(f.z0, f.z1, n.z0, n.z1) for f in fronts) / area
            if cov < 0.3 and (n.z1 - n.z0) >= 150:
                out.append(_issue("I01", "info", u, f"Khoang {n.id} để hở (cao {n.z0 - u.z0:.0f}–{n.z1 - u.z0:.0f})",
                                  "Không có cánh/ngăn kéo che khoang này.", "Đúng nếu là hộc mở; nếu không, kiểm cánh trên hình có cánh.", node=n))
    if u.interior and u.interior != u.elevation:
        out.append(_issue("I02", "info", u, f"Nội thất khối {u.id} đọc ở hình bỏ cánh {u.interior}",
                          "Đợt, vách, hộc, thanh treo lấy từ hình bỏ cánh; cánh lấy từ hình có cánh.", ""))
    return out


def check(scene) -> dict:
    """Chấm một cách hiểu (cảnh `Scene2` hoặc `Cabinet`). Trả {score, units: {id: điểm}, issues, counts}."""
    cab: Cabinet = as_cabinet(scene)
    issues: list[dict] = []
    units: dict[str, float] = {}
    for u in cab.units:
        its = _unit_issues(u)
        issues += its
        units[u.id] = round(max(0.0, 1.0 - sum(W[x["level"]] for x in its)), 3)
    counts = {lv: sum(1 for x in issues if x["level"] == lv) for lv in W}
    score = round(sum(units.values()) / len(units), 3) if units else 1.0
    order = {"conflict": 0, "warn": 1, "info": 2}
    return {"score": score, "units": units, "counts": counts, "issues": sorted(issues, key=lambda x: (order[x["level"]], x["unit"]))}


__all__ = ["check"]
