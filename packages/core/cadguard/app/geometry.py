"""Hình 2D ĐƠN GIẢN HOÁ để xem trước bản vẽ (đường dự phòng khi tệp quá lớn hoặc bộ vẽ ezdxf lỗi, xem `preview.py`).

Lấy từ mô hình `cg.drawing/1` đã có (không đọc lại DXF), chỉ không gian mô hình: LINE, LWPOLYLINE, CIRCLE, ARC (đúng
cung khi mô hình có góc), TEXT/MTEXT (điểm chèn + chữ, kèm chiều cao/góc nếu có để giao diện chỉ hiện chữ khi phóng đủ
lớn), INSERT (điểm chèn: chấm nhỏ, không vẽ nội dung khối). Toạ độ đã đổi sang khung nhìn SVG (gốc trên trái, trục y
xuống). Không có kích thước, hatch, nội dung khối: giao diện ghi rõ "Hình đơn giản hoá".

Mục `items`: `[handle, kiểu, dữ liệu]` với kiểu
  L: [x1, y1, x2, y2] · P/Q: [x, y, ...] (Q khép kín) · C: [cx, cy, r] · A: [cx, cy, r, góc đầu, góc cuối] (độ, DXF)
  T: [x, y, chữ, cao, góc] (cao theo đơn vị khung nhìn, 0 = không rõ) · I: [x, y, tên khối]
"""
from __future__ import annotations

from ..model import DrawingModel

MAX_ITEMS = 15000
VIEW_W = 1000.0
MAX_TEXT = 80


def _quantile(sorted_vals: list[float], q: float) -> float:
    i = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[i]


def drawing_geometry(model: DrawingModel, max_items: int = MAX_ITEMS) -> dict:
    ents = [e for e in model.entities if e.space == "Model"]
    raw: list[tuple[str, str, list]] = []  # (handle, kind, data theo toạ độ bản vẽ)
    skipped: dict[str, int] = {}
    for e in ents:
        t = e.type
        if t == "LINE" and e.pts and len(e.pts) >= 2:
            raw.append((e.handle, "L", [e.pts[0], e.pts[1]]))
        elif t == "LWPOLYLINE" and e.pts and len(e.pts) >= 2:
            raw.append((e.handle, "P" if not e.closed else "Q", list(e.pts)))
        elif t == "CIRCLE" and e.pts and e.radius:
            raw.append((e.handle, "C", [e.pts[0], e.radius]))
        elif t == "ARC" and e.arc is not None and e.arc[2]:
            cx, cy, r, a0, a1 = e.arc
            raw.append((e.handle, "A", [(cx, cy), r, a0, a1]))
        elif t in ("TEXT", "MTEXT") and e.pos is not None:
            raw.append((e.handle, "T", [e.pos, (e.text or "")[:MAX_TEXT], e.text_height or 0.0, e.text_rotation or 0.0]))
        elif t == "INSERT" and e.insert is not None:
            raw.append((e.handle, "I", [e.insert, e.block or ""]))
        else:
            skipped[t] = skipped.get(t, 0) + 1
    truncated = len(raw) > max_items
    raw = raw[:max_items]
    xs: list[float] = []
    ys: list[float] = []
    for _h, k, d in raw:
        pts = d if k in ("L", "P", "Q") else [d[0]]
        for x, y in pts:
            xs.append(x)
            ys.append(y)
    base = {"items": [], "viewbox": [0, 0, VIEW_W, VIEW_W * 0.6], "model_entities": len(ents),
            "drawn": 0, "skipped_types": skipped, "truncated": truncated,
            "records_capped": bool(model.stats is not None and model.stats.entity_records_truncated),
            "insunits": model.insunits, "simplified": True}
    if not xs:
        base["empty_reason"] = ("Không có hình trong không gian mô hình để vẽ (LINE/LWPOLYLINE/CIRCLE/ARC/TEXT/INSERT)."
                                if ents else "Bản vẽ không có đối tượng trong không gian mô hình.")
        return base
    sx, sy = sorted(xs), sorted(ys)
    if len(sx) > 40:  # bỏ điểm quá xa (đối tượng lạc) khi tính khung nhìn
        x0, x1, y0, y1 = _quantile(sx, 0.01), _quantile(sx, 0.99), _quantile(sy, 0.01), _quantile(sy, 0.99)
    else:
        x0, x1, y0, y1 = sx[0], sx[-1], sy[0], sy[-1]
    w, h = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    if w < h * 0.05:
        w = h * 0.05
    if h < w * 0.05:
        h = w * 0.05
    pad = 0.04 * max(w, h)
    x0, y0, w, h = x0 - pad, y0 - pad, w + 2 * pad, h + 2 * pad
    k = VIEW_W / max(w, h)
    vw, vh = round(w * k, 2), round(h * k, 2)

    def tx(p) -> list[float]:
        return [round((p[0] - x0) * k, 2), round((y0 + h - p[1]) * k, 2)]

    items = []
    for handle, kind, d in raw:
        if kind in ("L", "P", "Q"):
            pts = [c for p in d for c in tx(p)]
            items.append([handle, kind, pts])
        elif kind == "C":
            items.append([handle, kind, tx(d[0]) + [round(d[1] * k, 3)]])
        elif kind == "A":
            items.append([handle, kind, tx(d[0]) + [round(d[1] * k, 3), d[2], d[3]]])
        elif kind == "T":
            items.append([handle, kind, tx(d[0]) + [d[1], round(d[2] * k, 4), d[3]]])
        else:
            items.append([handle, kind, tx(d[0]) + [d[1]]])
    base.update(items=items, viewbox=[0, 0, vw, vh], drawn=len(items), text_size=round(max(vw, vh) * 0.011, 2),
                units_per_view=round(1 / k, 6),
                # ma trận mô hình -> khung nhìn (như meta "transform" của preview.py): x' = sx*x + tx, y' = sy*y + ty
                transform=[k, -k, -k * x0, k * (y0 + h)])
    return base


__all__ = ["drawing_geometry"]
