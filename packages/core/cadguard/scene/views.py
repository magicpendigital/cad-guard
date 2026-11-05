"""Dựng tấm ván từ ba hình chiếu vuông góc (mặt đứng, mặt bên, mặt bằng).

Quy ước ĐỀ XUẤT (chưa vào chuẩn): layer `FN-VIEW-FRONT|TOP|SIDE`; mỗi tấm ván là một hình chữ nhật khép kín.
- Mặt đứng: ngang = X, dọc = Z.  Mặt bên: ngang = chiều sâu Y tính từ mặt trước, dọc = Z.
- Mặt bằng: ngang = X, dọc = chiều sâu Y tính từ mặt trước.
Chiều sâu của tấm: ưu tiên mặt bên (khớp khoảng cao Z), không có thì mặt bằng (khớp khoảng ngang X).
Không có hoặc nhiều khả năng -> `gaps[]`, không đoán. Chỉ dùng phép so khớp, không dùng LLM.
"""

from __future__ import annotations

from ..model import DrawingModel, EntityRec
from .build import Field_, Gap, Panel, Scene

LAYERS = {"front": "FN-VIEW-FRONT", "top": "FN-VIEW-TOP", "side": "FN-VIEW-SIDE"}
TOL = 0.5  # mm


def _bbox(ents: list[EntityRec]):
    pts = [p for e in ents if e.pts for p in e.pts]
    if not pts:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _rects(ents: list[EntityRec]):
    """(x0, y0, x1, y1, handle) của các LWPOLYLINE khép kín là hình chữ nhật song song trục."""
    out = []
    for e in ents:
        if e.type != "LWPOLYLINE" or not e.closed or not e.pts:
            continue
        pts = list(e.pts)
        if len(pts) == 5 and pts[0] == pts[-1]:
            pts = pts[:4]
        if len(pts) != 4:
            continue
        xs, ys = sorted({round(p[0], 3) for p in pts}), sorted({round(p[1], 3) for p in pts})
        if len(xs) == 2 and len(ys) == 2:
            out.append((xs[0], ys[0], xs[1], ys[1], e.handle))
    return out


def _eq(a: float, b: float) -> bool:
    return abs(a - b) <= TOL


def _dedupe(ranges):
    out: list[tuple[float, float]] = []
    for r in ranges:
        if not any(_eq(r[0], o[0]) and _eq(r[1], o[1]) for o in out):
            out.append(r)
    return out


def _parse_depth(raw) -> tuple[float, float] | None:
    s = str(raw).strip().replace(",", ".")
    try:
        if ":" in s:
            a, b = (float(x) for x in s.split(":", 1))
            return (a, b) if b > a else None
        d = float(s)
        return (0.0, d) if d > 0 else None
    except ValueError:
        return None


def _fmt(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def build_panels(model: DrawingModel, sc: Scene, supp: dict, views: dict | None = None) -> None:
    ents = {k: list((views or {}).get(k, [])) for k in LAYERS} if views else {k: [e for e in model.entities if e.space == "Model" and e.layer == lay] for k, lay in LAYERS.items()}
    if not any(ents.values()):
        return
    bb = {k: _bbox(v) for k, v in ents.items()}
    if bb["front"] is None:
        sc.gaps.append(
            Gap(
                id="view:front",
                kind="missing_view",
                target="front",
                message="Thiếu mặt đứng (layer FN-VIEW-FRONT): không dựng được tấm ván. Cung cấp DXF có mặt đứng (--with).",
            )
        )
        return

    fx0, fy0, fx1, fy1 = bb["front"]
    W, H = fx1 - fx0, fy1 - fy0

    # Đối chiếu kích thước tổng thể giữa các hình: lệch = mâu thuẫn trong bản vẽ, phải sửa bản vẽ.
    def conflict(cid: str, msg: str) -> None:
        sc.gaps.append(Gap(id=f"conflict:{cid}", kind="conflict", target=cid, message=msg))

    if bb["top"]:
        tx0, ty0, tx1, ty1 = bb["top"]
        if not _eq(tx1 - tx0, W):
            conflict("width", f"Chiều rộng mặt bằng ({_fmt(tx1 - tx0)}) khác mặt đứng ({_fmt(W)}).")
    if bb["side"]:
        sx0, sy0, sx1, sy1 = bb["side"]
        if not _eq(sy1 - sy0, H):
            conflict("height", f"Chiều cao mặt bên ({_fmt(sy1 - sy0)}) khác mặt đứng ({_fmt(H)}).")
    if bb["top"] and bb["side"] and not _eq(ty1 - ty0, sx1 - sx0):
        conflict("depth", f"Chiều sâu mặt bằng ({_fmt(ty1 - ty0)}) khác mặt bên ({_fmt(sx1 - sx0)}).")

    side_r = [(a - bb["side"][0], b - bb["side"][1], c - bb["side"][0], d - bb["side"][1]) for a, b, c, d, _ in _rects(ents["side"])] if bb["side"] else []
    top_r = [(a - bb["top"][0], b - bb["top"][1], c - bb["top"][0], d - bb["top"][1]) for a, b, c, d, _ in _rects(ents["top"])] if bb["top"] else []

    for a, b, c, d, handle in _rects(ents["front"]):
        x0, x1, z0, z1 = a - fx0, c - fx0, b - fy0, d - fy0
        pid = f"panel:{handle}"
        cands = _dedupe([(r[0], r[2]) for r in side_r if _eq(r[1], z0) and _eq(r[3], z1)])
        src = "mặt bên"
        if not cands:
            cands = _dedupe([(r[1], r[3]) for r in top_r if _eq(r[0], x0) and _eq(r[2], x1)])
            src = "mặt bằng"
        key = f"{pid}:depth"
        chosen = _parse_depth(supp[key]) if key in supp else None
        if chosen is not None:
            sc.panels.append(Panel(id=pid, x0=x0, x1=x1, y0=chosen[0], y1=chosen[1], z0=z0, z1=z1, source="user"))
        elif len(cands) == 1:
            sc.panels.append(Panel(id=pid, x0=x0, x1=x1, y0=cands[0][0], y1=cands[0][1], z0=z0, z1=z1))
        elif len(cands) > 1:
            opts = [f"{c0:.1f}:{c1:.1f}" for c0, c1 in cands]
            sc.gaps.append(
                Gap(
                    id=pid,
                    kind="ambiguous",
                    target=handle,
                    message=f"Tấm {handle}: {src} có {len(cands)} khoảng sâu khớp, chọn một.",
                    fields=[Field_(key=key, label="Khoảng sâu (từ:đến)", kind="choice", options=opts)],
                )
            )
        else:
            sc.gaps.append(
                Gap(
                    id=pid,
                    kind="missing_value",
                    target=handle,
                    message=f"Tấm {handle}: không có hình chiếu nào cho biết chiều sâu (mặt bên/mặt bằng thiếu hoặc không khớp).",
                    fields=[Field_(key=key, label="Chiều sâu (tính từ mặt trước)")],
                )
            )
