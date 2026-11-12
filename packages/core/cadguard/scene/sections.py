"""P5 — ĐỐI CHIẾU MẶT CẮT với khối dựng từ mặt đứng (thiết kế `docs/research/kien-truc-doc-ban-ve-tong-the.md`).

Một mặt cắt cho hai thứ mặt bằng/mặt đứng hay thiếu: CHIỀU SÂU và CAO ĐỘ TẤM của khối mà nó cắt qua.

Nối mặt cắt ↔ khối (tất định):
- `mark`: ký hiệu mặt cắt (INSERT có nhãn "1-1", "X2"… đã nối tới hình mặt cắt, `Drawing2D.marks`) nằm trên mặt đứng
  dựng khối; đường cắt đứng nên cắt MỌI khối có khoảng X chứa vị trí ký hiệu (tủ dưới + tủ treo cùng cột).
- `height`: mặt cắt không có ký hiệu nào trỏ tới: khối được nối khi thân tủ trong mặt cắt phủ đúng dải cao của khối
  (chân và đỉnh lệch ≤ 30 mm). Hai mặt cắt cho hai số sâu khác nhau ở cùng khối thì không dùng (mơ hồ).

Đọc ở dải cao của khối (cao độ tính từ sàn của mặt cắt: chân kích thước sàn–trần, không có thì đáy thân tủ):
- sâu = bề ngang thân tủ ở dải GIỮA khối (bỏ 1/4 trên/dưới để tránh mặt đá đua, khối kề); kích thước ngang đo đúng
  đoạn đó thì nguồn = kích thước (`dimension`), không thì đo nét (`geometry`);
- tấm = chồng nét ngang trong khung đó (`primitives.board_stacks`), bỏ nóc/đáy.

Kết quả ghi ở `Module2.sections`; `assemble` dùng sâu khi mặt bằng không cho, tấm khi khối chưa có tầng nào; bộ chấm
nhất quán đối chiếu (H03 sâu lệch mặt bằng, H04 tấm ở mặt cắt không có ở mặt đứng/hình bỏ cánh).
"""
from __future__ import annotations

from . import primitives as prim
from .feasibility import room_height_dim
from .views2d import Drawing2D, View, confirm, view_dims

Z_TOL = 30.0
DEPTH_MIN, DEPTH_MAX = 150.0, 1200.0


def _body(d: Drawing2D, s: View) -> list:
    items = prim.items_in(d, s.handles, prim.BODY)
    if len(items) < 4:  # mặt cắt vẽ thân tủ bằng nét thấy
        items = prim.items_in(d, s.handles, prim.BODY | {"visible"})
    return items


def _floor(d: Drawing2D, s: View, items: list) -> float:
    rh = room_height_dim(d, s)
    return rh.lo if rh else prim.box_of(items)[1]


def read_at(d: Drawing2D, s: View, z0: float, z1: float) -> dict | None:
    """Sâu + tấm của dải cao [z0, z1] (tính từ sàn) trong mặt cắt `s`. None nếu không đọc được."""
    items = _body(d, s)
    if not items:
        return None
    fl = _floor(d, s, items)
    bz = prim.box_of(items)
    h = z1 - z0
    a, b = fl + z0 + 0.25 * h, fl + z1 - 0.25 * h
    band = [it for it in items if it[0][1] <= b and it[0][3] >= a]
    if not band:
        return None
    lo, hi = min(it[0][0] for it in band), max(it[0][2] for it in band)
    depth = hi - lo
    if not DEPTH_MIN <= depth <= DEPTH_MAX:
        return None
    tol = max(3.0, 0.01 * depth)
    dim = confirm(view_dims(d, s), "h", lo, hi, tol)
    handles = [it[1] for it in items]
    hs = prim.hsegs(d, handles, prim.BODY | {"visible"})
    levels = [{"z0": round(L["z0"] - fl, 1), "z1": round(L["z1"] - fl, 1), "refs": L["refs"][:6]}
              for L in prim.board_stacks(hs, lo, hi, fl + z0, fl + z1)]  # mặt cắt: tấm vẽ giữa hai hông, không xét tựa
    return {"view": s.id, "label": s.label or "", "depth": round(dim.value if dim else depth, 1),
            "depth_src": "dimension" if dim else "geometry", "refs": ([dim.handle] if dim else []) + [it[1] for it in band][:6],
            "levels": levels, "covers": (round(bz[1] - fl, 1), round(bz[3] - fl, 1))}


def link(d: Drawing2D, group: str, sc, e: View) -> None:
    """Gắn mặt cắt của hạng mục vào từng khối (`m.sections`). `e` = mặt đứng dựng khối."""
    from .views2d import _norm_label

    secs = {v.id: v for v in d.views_of(group, "section") if v.box}
    if not secs:
        return
    marked = {mk.target for mk in d.marks if mk.target in secs}
    by_label: dict[str, list[str]] = {}
    for sid, v in secs.items():
        by_label.setdefault(_norm_label(v.label or ""), []).append(sid)
    for m in sc.modules:
        if m.form in ("filler", "panel") or len(m.ebox) != 4:
            continue
        got: list[dict] = []
        any_mark = False
        for mk in d.marks:  # ký hiệu trên chính mặt đứng dựng khối, X trong khoảng khối
            if mk.view_id != e.id or not (mk.target in secs or by_label.get(mk.label)):
                continue
            ins = d.entities[mk.handle].insert or d.entities[mk.handle].pos
            if not ins or not (m.ebox[0] - 1 <= ins[0] <= m.ebox[2] + 1):
                continue
            any_mark = True
            # hình đích của ký hiệu trước, rồi các mặt cắt cùng nhãn (nhiều tờ có cùng nhãn "Y1": ký hiệu có thể trỏ nhầm tờ)
            cands = ([mk.target] if mk.target in secs else []) + [x for x in by_label.get(mk.label, []) if x != mk.target]
            for sid in cands:
                r = read_at(d, secs[sid], m.z0, m.z0 + m.h)
                if r and r["covers"][0] <= m.z0 + Z_TOL and r["covers"][1] >= m.z0 + m.h - Z_TOL:
                    if all(g["view"] != r["view"] for g in got):
                        got.append({**r, "via": "mark", "mark": mk.handle, "x": round(m.x + ins[0] - m.ebox[0], 1)})
                    break
        if not got and not any_mark:
            for sid, s in secs.items():
                if sid in marked:
                    continue
                r = read_at(d, s, m.z0, m.z0 + m.h)
                if r and abs(r["covers"][0] - m.z0) <= Z_TOL and abs(r["covers"][1] - (m.z0 + m.h)) <= Z_TOL:
                    got.append({**r, "via": "height"})
            if len({round(g["depth"]) for g in got}) > 1:
                got = []  # hai mặt cắt cùng dải cao cho hai số sâu: mơ hồ, để người chọn (gợi ý `proposals`)
        for g in got:
            g.pop("covers", None)
        m.sections = got


STRONG = ("dimension", "user")


def _front_line(d: Drawing2D, p: View, x0: float, x1: float, y: float, tol: float = 5.0) -> str | None:
    """Nét ngang ở mặt bằng tại `y` phủ ≥ 80 % khoảng [x0, x1] (mép trước tủ): trả handle một nét, không có thì None."""
    roles = frozenset(r for r in set(d.roles.values()) if r not in ("text", "dim"))
    segs = [sg for sg in prim.hsegs(d, p.handles, roles) if abs(sg[2] - y) <= tol and sg[1] > x0 and sg[0] < x1]
    cov, cur = 0.0, x0
    for a, b, _z, _h in sorted(segs):
        a, b = max(a, cur), min(b, x1)
        if b > a:
            cov, cur = cov + b - a, b
    return segs[0][3] if segs and cov >= 0.8 * (x1 - x0) else None


def apply(sc, notes: list[str], d: Drawing2D | None = None, plan: View | None = None, origin=(0.0, 0.0)) -> None:
    """Dùng mặt cắt:
    - sâu cho khối đang mặc định; hoặc thay sâu ĐO NÉT ở mặt bằng khi mặt cắt nối bằng ký hiệu có KÍCH THƯỚC ghi đúng
      đoạn đó (bằng chứng mạnh hơn); các trường hợp lệch khác để bộ chấm nhất quán báo (H03);
    - tấm cho khối chưa có tầng/vách nào (không có hình bỏ cánh)."""
    from .assemble import Src

    for m in sc.modules:
        if not m.sections:
            continue
        best = sorted(m.sections, key=lambda g: (g["via"] != "mark", g["depth_src"] != "dimension"))[0]
        cur = m.src.get("d")
        default = cur is not None and cur.kind == "default"
        stronger = (cur is not None and cur.kind == "geometry" and best["via"] == "mark" and best["depth_src"] == "dimension"
                    and abs(best["depth"] - m.d) > 10)
        if default or stronger:
            old = m.d
            back = m.y + m.d
            m.d, m.y = best["depth"], round(back - best["depth"], 3)
            m.src["d"] = Src(kind=best["depth_src"], refs=best["refs"][:6])
            best["used"] = True
            sc.gaps = [g for g in sc.gaps if g.id != f"module:{m.id}"]
            why = "theo ký hiệu mặt cắt trên mặt đứng" if best["via"] == "mark" else "mặt cắt phủ đúng dải cao của khối"
            notes.append(f"Khối {m.id}: chiều sâu {best['depth']:.0f} lấy ở mặt cắt {best['label'] or best['view']} ({why})"
                         + (f", thay số {old:.0f} đo nét ở mặt bằng (mặt cắt có kích thước ghi)." if stronger else "."))
        has_levels = any(q.get("kind") in ("shelf", "glass", "stone", "partition") for q in m.inner)
        if not has_levels and best["levels"] and (not m.interior or m.interior == m.elevation):
            for L in best["levels"]:
                m.inner.append({"kind": "shelf", "x0": round(m.x + 18, 1), "x1": round(m.x + m.w - 18, 1), "z0": L["z0"], "z1": L["z1"],
                                "lines": [], "refs": L["refs"], "from": "section"})
            m.shelves = max(m.shelves, len(best["levels"]))
            notes.append(f"Khối {m.id}: {len(best['levels'])} tấm ngang lấy cao độ ở mặt cắt {best['label'] or best['view']} "
                         "(mặt đứng không vẽ tấm).")
    if d is None or plan is None:
        return
    # khối KHÔNG được mặt cắt nào cắt qua: dùng sâu của mặt cắt cùng loại khối khi mặt bằng có mép trước đúng ở khoảng sâu
    # đó tính từ tường (hai hình cùng xác nhận một số)
    known = [(m.kind == "wall", g) for m in sc.modules for g in m.sections if g.get("used")]
    for m in sc.modules:
        if m.form == "panel" or m.sections or m.src.get("d") is None or m.src["d"].kind != "default":
            continue
        back = m.y + m.d + origin[1]
        for _w, g in [k for k in known if k[0] == (m.kind == "wall")]:
            h = _front_line(d, plan, m.x + origin[0], m.x + m.w + origin[0], back - g["depth"])
            if h is None:
                continue
            m.d, m.y = g["depth"], round(m.y + m.d - g["depth"], 3)
            m.src["d"] = Src(kind="geometry", refs=[h] + g["refs"][:4])
            sc.gaps = [x for x in sc.gaps if x.id != f"module:{m.id}"]
            notes.append(f"Khối {m.id}: chiều sâu {g['depth']:.0f} theo mặt cắt {g['label'] or g['view']} của khối cùng hàng, "
                         "mặt bằng có mép trước đúng ở khoảng sâu này.")
            break


__all__ = ["apply", "link", "read_at"]
