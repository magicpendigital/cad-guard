"""Bộ dữ liệu MÔ PHỎNG cho đo độ chính xác dựng 3D khi chưa có người kỹ thuật ghi đáp án.

Ý tưởng: không để AI vẽ rồi tự chấm (vòng luẩn quẩn). "Agent thiết kế" tạo THÔNG SỐ đồ nội thất hợp lý (`cg.furniture-spec/1`,
theo luật kết cấu: cánh ≤ 600, cặp cánh, cột ngăn kéo, tấm bù…), bộ vẽ bằng code dựng bản vẽ DXF từ thông số đó theo nhiều
KIỂU TRÌNH BÀY (mỗi người kỹ thuật một kiểu), và ghi đáp án `cg.scene-answer/1` đúng 100 % vì chính máy vẽ ra.

- Agent thiết kế: `design_specs(n, seed)` bằng code (ngẫu nhiên có hạt giống, lặp lại được); tuỳ chọn `design_specs_ai`
  (AI đề xuất thông số theo yêu cầu bằng lời, qua `validate_spec`; sai luật thì loại).
- Kiểu trình bày (`STYLES`): chuẩn công ty; thân tủ trên layer "THAY"; khung tên không số; ngăn kéo vẽ bằng LINE + nét
  khuất chéo; tủ liền thân (vách đôi); có hình bỏ cánh đi kèm; mặt bằng không vẽ đường bao (chỉ ghi kích thước sâu); một
  tiêu đề chung; sâu chỉ ở mặt cắt; hai mặt đứng chép trùng tiêu đề "BỎ CÁNH"; nội thất chỉ ở hình bỏ cánh (tấm hai nét,
  đợt kính, thanh treo, hộc trong + vách; đáp án có số nội thất); đường khấu + vòng chú thích trên layer nét khuất.
- `generate(out_dir, n, seed)`: mỗi hạng mục một tệp DXF + đáp án trong `<out_dir>/.cadguard/answers/`; chấm bằng
  `cadguard bench3d --workspace <out_dir>`.

Đây là dữ liệu TỔNG HỢP: dùng để đo hồi quy và tìm điểm yếu theo kiểu trình bày; vẫn cần vài đáp án thật để kiểm chéo.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import ezdxf

SPEC = "cg.furniture-spec/1"
T = 18.0  # dày ván vẽ
GAP = 2.0  # khe cánh vẽ
LAYERS = ["SYN_Tuong", "SYN_Noithat", "SYN_Netcat", "SYN_Khuat", "SYN_Dim", "SYN_Text", "SYN_Kyhieu", "THAY"]
STYLES: dict[str, dict[str, Any]] = {
    "chuan": {"label": "Chuẩn công ty (layer nội thất, khung tên có số)"},
    "thay": {"label": "Thân tủ trên layer nét thấy THAY", "body": "THAY"},
    "khongso": {"label": "Khung tên không ghi số bản vẽ", "number": False},
    "ngankeo_line": {"label": "Ngăn kéo vẽ bằng LINE + nét khuất chéo", "drawer_lines": True},
    "lienthan": {"label": "Tủ liền thân, vách đôi giữa các khối", "shared": True},
    "bocanh": {"label": "Có hình mặt đứng bỏ cánh đi kèm", "companion": True},
    "khongbao": {"label": "Mặt bằng không vẽ đường bao, chỉ ghi kích thước sâu", "plan_outline": False},
    "motieude": {"label": "Một tiêu đề chung cho hình có cánh và hình bỏ cánh đặt cạnh", "companion": True, "companion_title": False},
    "sauomatcat": {"label": "Chiều sâu chỉ ghi ở mặt cắt (mặt bằng không có số sâu, không đường bao)", "plan_outline": False,
                   "plan_depth_dim": False, "section": True},
    # ca thật 11/11/2026 (tủ áo + minibar): người vẽ chép tiêu đề, nội thất chỉ có ở hình bỏ cánh, ký hiệu trên layer khuất
    "trungtieude": {"label": "Hai mặt đứng cùng tiêu đề \"BỎ CÁNH\" (hình có cánh bị chép nhầm tiêu đề)", "companion": True,
                    "dup_title": True},
    "noithat": {"label": "Nội thất chỉ vẽ ở hình bỏ cánh: tấm hai nét, đợt kính, thanh treo, hộc trong + vách", "companion": True,
                "interior": True},
    "khuat_chuthich": {"label": "Đường khấu bo cong + vòng chú thích \"ghép mòi 45°\" vẽ trên layer nét khuất", "marks": True},
}
INNER_KINDS = ("shelf", "glass", "rod", "drawer", "partition")


# ---------------- agent thiết kế (code) ----------------

def _split_width(rng: random.Random, total: int, lo: int, hi: int) -> list[int]:
    out, left = [], total
    while left > hi:
        w = rng.choice([x for x in range(lo, hi + 1, 50) if left - x >= lo] or [left])
        out.append(w)
        left -= w
    if left > 0:
        out.append(left)
    return out


def _doors(x0: float, w: float, z0: float, z1: float) -> list[dict]:
    n = 1 if w <= 600 else 2
    step = w / n
    return [{"kind": "door", "x0": x0 + i * step, "x1": x0 + (i + 1) * step, "z0": z0, "z1": z1} for i in range(n)]


def _drawers(x0: float, w: float, z0: float, z1: float, n: int) -> list[dict]:
    hgt = (z1 - z0) / n
    return [{"kind": "drawer", "x0": x0, "x1": x0 + w, "z0": z0 + i * hgt, "z1": z0 + (i + 1) * hgt} for i in range(n)]


def _wardrobe(rng: random.Random, idx: int) -> dict:
    h = rng.choice([2200, 2300, 2400])
    d = rng.choice([550, 580, 600])
    mods = []
    x = 0.0
    if rng.random() < 0.4:  # tấm bù đo thực tế một bên
        fw = rng.choice([50, 80, 100, 150])
        mods.append({"w": fw, "d": d, "h": h, "z0": 0, "form": "filler", "fronts": [], "shelves": 0, "note": "TẤM FIX ĐO THỰC TẾ"})
        x += fw
    r2 = random.Random(1000 + idx)  # nội thất (hình bỏ cánh) theo hạt giống riêng: thông số cũ giữ nguyên
    for kind in rng.sample(["hang", "drawer", "shelf"], k=rng.choice([2, 3])):
        w = rng.choice([900, 1000, 1200]) if kind == "hang" else rng.choice([450, 500, 600])
        fr = _doors(0, w, T, h - T) if kind != "drawer" else (_doors(0, w, 900, h - T) + _drawers(0, w, T, 900, 3))
        mods.append({"w": w, "d": d, "h": h, "z0": 0, "form": "cabinet", "fronts": fr, "shelves": 1 if kind == "hang" else 3,
                     "use": kind, "inner_drawers": r2.choice([0, 2]) if kind == "hang" else 0, "glass": kind == "shelf"})
    return {"schema": SPEC, "id": f"SYN.{20 + idx:02d}", "name": f"TỦ ÁO MẪU {idx + 1}", "kind": "wardrobe", "room_h": 2700, "modules": mods}


def _kitchen(rng: random.Random, idx: int) -> dict:
    total = rng.choice([1800, 2100, 2400, 2700])
    base_h, base_d = rng.choice([800, 850]), rng.choice([560, 600])
    wall_z, wall_h, wall_d = rng.choice([1450, 1500, 1550]), rng.choice([700, 750]), 350
    mods = []
    for w in _split_width(rng, total, 400, 900):
        if rng.random() < 0.35:
            fr = _drawers(0, w, 100, base_h - T, 3)
        else:
            fr = _doors(0, w, 100, base_h - T)
        mods.append({"w": w, "d": base_d, "h": base_h, "z0": 0, "form": "cabinet", "fronts": fr, "shelves": 0})
    row = {"w": total, "d": wall_d, "h": wall_h, "z0": wall_z, "form": "cabinet", "fronts": [], "shelves": 0}
    x = 0.0
    for w in _split_width(rng, total, 600, 1200):
        row["fronts"] += [{**f, "x0": f["x0"] + x, "x1": f["x1"] + x} for f in _doors(0, w, wall_z + 2, wall_z + wall_h - 2)]
        x += w
    for f in row["fronts"]:
        f["z0"], f["z1"] = f["z0"] - wall_z, f["z1"] - wall_z
    mods.append(row)
    return {"schema": SPEC, "id": f"SYN.{40 + idx:02d}", "name": f"TỦ BẾP MẪU {idx + 1}", "kind": "kitchen", "room_h": 2700,
            "modules": mods, "rows": True}


def _tv(rng: random.Random, idx: int) -> dict:
    d = rng.choice([400, 450])
    h = rng.choice([400, 450, 500])
    mods = []
    for w in _split_width(rng, rng.choice([1800, 2000, 2400]), 400, 600):
        mods.append({"w": w, "d": d, "h": h, "z0": 0, "form": "cabinet", "fronts": _drawers(0, w, T, h - T, 1), "shelves": 0})
    return {"schema": SPEC, "id": f"SYN.{60 + idx:02d}", "name": f"KỆ TIVI MẪU {idx + 1}", "kind": "tv", "room_h": 2700, "modules": mods}


def design_specs(n: int, seed: int = 1) -> list[dict]:
    rng = random.Random(seed)
    makers = [_wardrobe, _kitchen, _tv]
    return [makers[i % 3](rng, i) for i in range(n)]


def validate_spec(s: dict) -> list[str]:
    """Luật tối thiểu cho thông số (agent thiết kế phải tuân): cánh ≤ 600, mặt trước nằm trong khối, số đo hợp lý."""
    errs = []
    for i, m in enumerate(s.get("modules") or []):
        if not (100 <= m.get("w", 0) <= 3000 and 200 <= m.get("h", 0) <= 2800 and 200 <= m.get("d", 0) <= 900):
            errs.append(f"khối {i + 1}: số đo ngoài khoảng hợp lý")
        for f in m.get("fronts") or []:
            if f.get("kind") == "door" and f["x1"] - f["x0"] > 601:
                errs.append(f"khối {i + 1}: cánh rộng {f['x1'] - f['x0']:.0f} > 600")
            if f["x0"] < -1 or f["x1"] > m["w"] + 1 or f["z0"] < -1 or f["z1"] > m["h"] + 1:
                errs.append(f"khối {i + 1}: mặt trước nằm ngoài khối")
    if not s.get("modules"):
        errs.append("không có khối nào")
    return errs


DESIGNER_SYSTEM = (
    "Bạn là kỹ sư thiết kế kỹ thuật nội thất (tủ không khung, ván 17–18 mm). Từ yêu cầu bằng lời, tạo THÔNG SỐ đồ nội thất "
    "dạng JSON đúng lược đồ cg.furniture-spec/1: {\"name\", \"kind\": wardrobe|kitchen|tv, \"room_h\", \"modules\": [{\"w\", \"d\", "
    "\"h\", \"z0\", \"form\": cabinet|open|filler, \"fronts\": [{\"kind\": door|drawer, \"x0\", \"x1\", \"z0\", \"z1\"}] (toạ độ trong "
    "khối, mm), \"shelves\"}]}. Luật: cánh bản lề rộng ≤ 600 và cao hơn rộng; khối > 600 dùng cặp 2 cánh; cột ngăn kéo 400–600; tủ "
    "bếp dưới cao 800–850, sâu 560–600; tủ treo sâu 300–350; tủ áo sâu 550–600, cao 2200–2400. Trả JSON {\"specs\": [...]}.")


def design_specs_ai(backend, briefs: list[str], start: int = 80) -> tuple[list[dict], list[dict]]:
    """AI đề xuất thông số theo yêu cầu bằng lời; thông số sai luật bị loại (trả kèm lý do)."""
    reply = backend.complete(DESIGNER_SYSTEM, [{"role": "user", "content": json.dumps({"briefs": briefs}, ensure_ascii=False)}])
    import re

    m = re.search(r"\{.*\}", reply or "", re.S)
    try:
        raw = json.loads(m.group(0)).get("specs", []) if m else []
    except ValueError:
        raw = []
    ok, bad = [], []
    for i, s in enumerate(raw):
        if not isinstance(s, dict):
            continue
        s = {**s, "schema": SPEC, "id": f"SYN.{start + i:02d}"}
        errs = validate_spec(s)
        (bad if errs else ok).append({**s, "errors": errs} if errs else s)
    return ok, bad


# ---------------- bộ vẽ ----------------

def _rect(msp, x0, y0, x1, y1, layer):
    msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs={"layer": layer})


def _dim(msp, p1, p2, base, angle=0):
    msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dxfattribs={"layer": "SYN_Dim"}).render()


def _title(msp, text, at, k=20):
    msp.add_text(text, height=2.5 * k, dxfattribs={"layer": "SYN_Text", "style": "STD", "insert": at})


def _layout(spec: dict) -> list[dict]:
    """Toạ độ X của từng khối trên mặt đứng (khối cùng hàng xếp liền; tủ treo hàng riêng từ x 0)."""
    out, x = [], 0.0
    for m in spec["modules"]:
        if spec.get("rows") and m["z0"] > 0:
            out.append({**m, "x": 0.0})
        else:
            out.append({**m, "x": x})
            x += m["w"]
    return out


def _lines2(msp, x0, x1, z, th, layer):
    """Tấm ngang vẽ hai nét (cách vẽ hay gặp: ván, kính)."""
    for zz in (z, z + th):
        msp.add_line((x0, zz), (x1, zz), dxfattribs={"layer": layer})


def interior_plan(m: dict) -> dict:
    """Nội thất khối tủ áo ở hình bỏ cánh (kiểu "noithat"): cao độ tầng (từ chân khối), thanh treo, hộc trong. Trả cả số
    đếm đáp án theo loại."""
    h, use = m["h"], m.get("use")
    out = {"levels": [], "rod": None, "drawers": 0}
    if use == "hang":
        out["levels"].append(("shelf", h - 400.0))
        out["rod"] = h - 520.0
        if m.get("inner_drawers"):
            out["drawers"] = 2
            out["levels"].append(("shelf", 380.0))
    elif use == "shelf":
        n = int(m.get("shelves") or 0)
        for i in range(1, n + 1):
            z = T + i * (h - 2 * T) / (n + 1)
            out["levels"].append(("glass" if (m.get("glass") and i == (n + 1) // 2) else "shelf", z))
    else:
        n = int(m.get("shelves") or 0)
        for i in range(1, n + 1):
            out["levels"].append(("shelf", T + i * (h - 2 * T) / (n + 1)))
    out["count"] = {"shelf": sum(1 for k, _z in out["levels"] if k == "shelf"), "glass": sum(1 for k, _z in out["levels"] if k == "glass"),
                    "rod": 1 if out["rod"] else 0, "drawer": out["drawers"], "partition": 1 if out["drawers"] else 0}
    return out


def _interior(msp, m, x0, z0, x1, body):
    """Vẽ nội thất một khối ở hình bỏ cánh (kiểu "noithat")."""
    ip = interior_plan(m)
    a, b = x0 + T, x1 - T
    for kind, z in ip["levels"]:
        th = 10.0 if kind == "glass" else T
        _lines2(msp, a, b, z0 + z, th, body)
        if kind == "glass":
            msp.add_text("KÍNH CƯỜNG LỰC 10MM", height=30, dxfattribs={"layer": "SYN_Text", "insert": (a + 20, z0 + z - 80)})
    if ip["rod"]:
        _rect(msp, a, z0 + ip["rod"] - 15, b, z0 + ip["rod"] + 15, "SYN_Khuat")
    if ip["drawers"]:
        xm = (a + b) / 2
        msp.add_line((xm - T / 2, z0 + T), (xm - T / 2, z0 + 380), dxfattribs={"layer": body})
        msp.add_line((xm + T / 2, z0 + T), (xm + T / 2, z0 + 380), dxfattribs={"layer": body})
        for cx in ((a + xm) / 2, (xm + b) / 2):
            msp.add_text("HỘC TỦ", height=30, dxfattribs={"layer": "SYN_Text", "insert": (cx - 60, z0 + 180)})


def _marks(msp, m, x0, z0, x1, z1):
    """Ký hiệu đặc biệt trên layer nét khuất (kiểu "khuat_chuthich"): đường khấu gãy khúc ở cạnh phải khoang trên cùng và
    vòng chú thích ở góc trên phải, chữ đặt ngoài hình."""
    ztop = z1 - T
    msp.add_lwpolyline([(x1 - T, ztop - 500), (x1 - T - 60, ztop - 60), (x1 - T - 250, ztop)], dxfattribs={"layer": "SYN_Khuat"})
    msp.add_circle((x1, z1), 110, dxfattribs={"layer": "SYN_Khuat"})
    msp.add_text("VỊ TRÍ GHÉP MÒI 45 ĐỘ", height=40, dxfattribs={"layer": "SYN_Text", "insert": (x1 + 150, z1 + 350)})


def _elevation(msp, mods, ex, fz, body, style, fronts=True):
    for m in mods:
        x0, z0, x1, z1 = ex + m["x"], fz + m["z0"], ex + m["x"] + m["w"], fz + m["z0"] + m["h"]
        if m["form"] == "filler":
            _rect(msp, x0, z0, x1, z1, body)
            msp.add_text(m.get("note", "TẤM FIX"), height=40, dxfattribs={"layer": "SYN_Text", "insert": (x0 + 5, z0 + m["h"] / 2)})
            continue
        # hồi trái/phải (tấm 18), nóc, đáy: tủ liền thân có vách đôi giữa các khối
        _rect(msp, x0, z0, x0 + T, z1, body)
        _rect(msp, x1 - T, z0, x1, z1, body)
        _rect(msp, x0 + T, z1 - T, x1 - T, z1, body)
        _rect(msp, x0 + T, z0, x1 - T, z0 + T, body)
        if not style.get("shared"):
            _rect(msp, x0, z0, x1, z1, body)  # đường bao khối
        if not fronts and style.get("interior") and m.get("use"):
            _interior(msp, m, x0, z0, x1, body)
            continue
        if not fronts:
            n = int(m.get("shelves") or 0)
            for i in range(1, n + 1):
                zs = z0 + T + i * (m["h"] - 2 * T) / (n + 1)
                _rect(msp, x0 + T, zs, x1 - T, zs + T, body)
            continue
        for f in m["fronts"]:
            a, b = x0 + f["x0"] + GAP, x0 + f["x1"] - GAP
            c, d = z0 + f["z0"] + GAP, z0 + f["z1"] - GAP
            if f["kind"] == "drawer" and style.get("drawer_lines"):
                for y in (c, d):
                    msp.add_line((a, y), (b, y), dxfattribs={"layer": body})
                for xx in (a, b):
                    msp.add_line((xx, c), (xx, d), dxfattribs={"layer": body})
                msp.add_line((a, c), (b, d), dxfattribs={"layer": "SYN_Khuat"})
            else:
                _rect(msp, a, c, b, d, body)
                if f["kind"] == "door":  # ký hiệu mở cánh: tam giác nét khuất đỉnh về phía bản lề
                    hx = a if (f["x0"] + f["x1"]) / 2 < m["w"] / 2 else b
                    ox = b if hx == a else a
                    msp.add_lwpolyline([(ox, c), (hx, (c + d) / 2), (ox, d)], dxfattribs={"layer": "SYN_Khuat"})


def draw(spec: dict, style_keys: list[str], path: Path) -> dict:
    """Vẽ một hạng mục thành DXF (một tờ 1:20). Trả đáp án (khối theo thứ tự trái → phải)."""
    from .fixtures import CO_FRAME, _company_frame

    style: dict[str, Any] = {}
    for k in style_keys:
        style.update(STYLES[k])
    body = style.get("body", "SYN_Noithat")
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    for name in LAYERS:
        doc.layers.add(name)
    doc.layers.get("SYN_Khuat").dxf.linetype = "DASHED"
    _company_frame(doc)
    msp = doc.modelspace()
    k = 20
    ref = msp.add_blockref(CO_FRAME, (0, 0), dxfattribs={"layer": "SYN-KHUNG", "xscale": k, "yscale": k})
    ref.add_auto_attribs({"DU_AN": "DỰ ÁN MÔ PHỎNG", "TEN_BAN_VE": "CHI TIẾT " + spec["name"],
                          "SO_BAN_VE": f"{spec['id']}. 01" if style.get("number", True) else "", "TI_LE": "1/20", "NGAY": "11/11/2026"})
    mods = _layout(spec)
    total = max(m["x"] + m["w"] for m in mods)
    room_h = float(spec.get("room_h") or 2700)
    ex, fz = 600.0, 2300.0  # mặt đứng ở trên, mặt bằng ở dưới; mọi thứ nằm trong khung tờ (viền trong từ 200)
    # tường hai bên + sàn + trần, kích thước sàn – trần
    for a, b in (((ex - 200, fz), (ex + total + 200, fz)), ((ex - 200, fz + room_h), (ex + total + 200, fz + room_h))):
        msp.add_line(a, b, dxfattribs={"layer": "SYN_Tuong"})
    _dim(msp, (ex - 200, fz), (ex - 200, fz + room_h), (ex - 450, fz + room_h / 2), angle=90)
    _elevation(msp, mods, ex, fz, body, style)
    _dim(msp, (ex, fz + room_h), (ex + total, fz + room_h), (ex + total / 2, fz + room_h + 200))
    for m in mods:
        _dim(msp, (ex + m["x"], fz + m["z0"]), (ex + m["x"] + m["w"], fz + m["z0"]), (ex + m["x"] + m["w"] / 2, fz + m["z0"] - 150 if m["z0"] == 0 else fz + m["z0"] - 100))
    seen_h = set()
    for m in mods:
        key = (m["z0"], m["h"])
        if key not in seen_h:
            seen_h.add(key)
            _dim(msp, (ex + total + 100, fz + m["z0"]), (ex + total + 100, fz + m["z0"] + m["h"]),
                 (ex + total + 300 + 150 * len(seen_h), fz + m["z0"] + m["h"] / 2), angle=90)
    if style.get("marks"):
        cab = [m for m in mods if m["form"] == "cabinet" and m["z0"] == 0]
        if cab:
            m = cab[-1]
            _marks(msp, m, ex + m["x"], fz + m["z0"], ex + m["x"] + m["w"], fz + m["z0"] + m["h"])
    _title(msp, f"MẶT ĐỨNG BỎ CÁNH {spec['name']}" if style.get("dup_title") else f"MẶT ĐỨNG {spec['name']}", (ex, fz - 450))
    if style.get("companion"):  # hình bỏ cánh đặt cạnh, tiêu đề riêng
        cx = ex + total + 900
        _elevation(msp, mods, cx, fz, body, style, fronts=False)
        _dim(msp, (cx, fz + room_h), (cx + total, fz + room_h), (cx + total / 2, fz + room_h + 200))
        if style.get("companion_title", True):
            _title(msp, f"MẶT ĐỨNG BỎ CÁNH {spec['name']}", (cx, fz - 450))
    # mặt bằng (trục X trùng mặt đứng), tường phía sau
    py = 700.0
    floor_mods = [m for m in mods if m["z0"] == 0]
    dmax = max(m["d"] for m in floor_mods) if floor_mods else 600
    msp.add_line((ex - 200, py + dmax), (ex + total + 200, py + dmax), dxfattribs={"layer": "SYN_Tuong"})
    for m in mods:
        y0 = py + dmax - m["d"]
        layer = "SYN_Khuat" if m["z0"] > 0 else body
        if style.get("plan_outline", True) or m["z0"] > 0:
            _rect(msp, ex + m["x"], y0, ex + m["x"] + m["w"], py + dmax, layer)
    _dim(msp, (ex, py - 100), (ex + total, py - 100), (ex + total / 2, py - 300))
    depths = sorted({m["d"] for m in floor_mods}) if style.get("plan_depth_dim", True) else []
    for i, dd in enumerate(depths):
        mm = next(m for m in floor_mods if m["d"] == dd)
        xx = ex + mm["x"] + mm["w"] - 50
        _dim(msp, (xx, py + dmax - dd), (xx, py + dmax), (xx + 40, py + dmax - dd / 2), angle=90)
    if not style.get("plan_outline", True):  # đường mép trước mảnh (nét thấy) để biết vị trí, không khép kín theo khối
        msp.add_line((ex, py + dmax - dmax), (ex + total, py + dmax - dmax), dxfattribs={"layer": "SYN_Tuong"})
    _title(msp, f"MẶT BẰNG {spec['name']}", (ex, py - 450))
    if style.get("section"):  # mặt cắt 1-1 qua khối sâu nhất: ngang = chiều sâu, dọc = cao
        mm = max(floor_mods or mods, key=lambda q: q["d"])
        sx, sz = ex + total + 900, 700.0
        _rect(msp, sx, sz, sx + mm["d"], sz + mm["h"], "SYN_Netcat")
        _dim(msp, (sx, sz + mm["h"]), (sx + mm["d"], sz + mm["h"]), (sx + mm["d"] / 2, sz + mm["h"] + 150))
        _title(msp, f"MẶT CẮT 1-1 {spec['name']}", (sx, sz - 450))
    doc.saveas(path)
    inner = bool(style.get("interior") and style.get("companion"))

    def row(m):
        r = {"x": float(m["x"]), "w": float(m["w"]), "d": float(m["d"]), "h": float(m["h"]), "z0": float(m["z0"]),
             "form": m["form"], "fronts": len(m["fronts"])}
        if inner and m.get("use"):  # đáp án nội thất: số tầng/đợt kính/thanh treo/hộc trong/vách đọc từ hình bỏ cánh
            r["inner"] = interior_plan(m)["count"]
        return r

    return {"modules": [row(m) for m in sorted(mods, key=lambda q: (q["x"], q["z0"]))]}


def generate(out_dir: Path, n: int = 12, seed: int = 1, specs: list[dict] | None = None) -> dict:
    """Sinh `n` hạng mục, mỗi hạng mục 1–3 kiểu trình bày ngẫu nhiên (có hạt giống). Ghi DXF + đáp án."""
    from .bench3d import SCHEMA as ANSWER, answer_path
    from .dxf_reader import read_dxf

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed + 7)
    specs = specs if specs is not None else design_specs(n, seed)
    rows = []
    for i, spec in enumerate(specs):
        keys = ["chuan"] + rng.sample([k for k in STYLES if k != "chuan"], k=rng.choice([0, 1, 2]))
        if spec["kind"] == "kitchen" and "lienthan" in keys:
            keys.remove("lienthan")
        name = f"mo-phong-{i + 1:02d}-{spec['kind']}.dxf"
        ans = draw(spec, keys, out_dir / name)
        model = read_dxf(out_dir / name)
        item = ("~" + spec["name"]) if "khongso" in keys else spec["id"]  # khung không số: nhóm theo tên trong tiêu đề hình
        data = {"schema": ANSWER, "source_hash": model.file_hash, "file": name, "item": item, "item_name": spec["name"],
                "created_at": "mô phỏng", "created_by": "synth", "note": "Đáp án mô phỏng: kiểu " + ", ".join(keys),
                "styles": keys, "modules": ans["modules"]}
        p = answer_path(out_dir, model.file_hash, item)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / (name[:-4] + ".spec.json")).write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append({"file": name, "item": item, "styles": keys, "modules": len(ans["modules"])})
    return {"dir": str(out_dir), "items": rows}


__all__ = ["DESIGNER_SYSTEM", "STYLES", "design_specs", "design_specs_ai", "draw", "generate", "validate_spec"]
