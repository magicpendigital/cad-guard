"""Chú giải hạng mục (bước 2 chuẩn hoá): chia khối đúng theo vách thật, liên kết nhiều hình của cùng hạng mục.

Vấn đề: tủ áo "2 cánh + cột ngăn kéo" vẽ liền thân thì cắt XY không thấy khe, gộp thành một khối. Vách ngăn giữa hai
phần là một TẤM VÁN (hai nét song song cách 8–60 mm hoặc hình chữ nhật mảnh) chạy gần suốt chiều cao — khác đường ráp
hai cánh (một nét đơn). Hình "bỏ cánh" đặt cạnh (cùng khung tiêu đề, hoặc một mặt đứng khác của hạng mục) cho thấy vách
rõ hơn vì không có cánh che.

- `split_proposals(d, sc)`: đề xuất bằng code các đường chia khối tại vách (hình chính + hình đi kèm, căn X bằng bỏ phiếu
  vị trí vách), bám đầu kích thước nếu có. Khoá `split:<hạng mục>` = toạ độ X trên mặt đứng chính (toạ độ bản vẽ).
- `check_split(d, sc, x, evidence)`: bộ kiểm hình học — có vách thật (nét dẫn là nét của vách đó) gần x; không cắt qua
  cánh/ngăn kéo; hai phần đều ≥ 150 mm; x nằm trong một khối.
- `llm_context`: dữ liệu cho AI chọn vách nào là ranh giới tủ, vách nào là vách chia trong cùng tủ (AI chỉ chọn trong ứng
  viên đã có; mọi đề xuất AI vẫn qua `check_split`).
- `apply_splits(blocks, xs)`: bộ dựng cắt khung khối tại các x người dùng đã Đồng ý.
"""
from __future__ import annotations

from .views2d import Drawing2D, View, entity_box, rect_of, view_dims

BOARD_MIN, BOARD_MAX = 8.0, 60.0
H_FRAC = 0.6  # vách phải cao ít nhất bấy nhiêu phần chiều cao khối
EDGE_MIN = 150.0
NEAR = 25.0
CLUSTER_GAP = 150.0
BODY = frozenset({"furniture", "cut", "visible", "thin"})


def _vlines(d: Drawing2D, handles, x0, x1, z0, z1) -> list[tuple[float, float, float, str]]:
    """Nét đứng (x, z_dưới, z_trên, handle) trong khung; hình chữ nhật mảnh đứng cho hai cạnh."""
    out = []
    for h in handles:
        e = d.entities[h]
        if d.roles.get(e.layer) not in BODY or e.type not in ("LINE", "LWPOLYLINE") or not e.pts:
            continue
        r = rect_of(e)
        if r is not None:
            if (r[2] - r[0]) <= BOARD_MAX:
                out += [(r[0], r[1], r[3], h), (r[2], r[1], r[3], h)]
            continue
        pts = list(e.pts) + ([e.pts[0]] if e.closed else [])
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            if abs(ax - bx) <= 0.5 and x0 - 1 <= ax <= x1 + 1:
                lo, hi = min(ay, by), max(ay, by)
                if hi > z0 - 1 and lo < z1 + 1:
                    out.append((ax, lo, hi, h))
    return out


def boards(d: Drawing2D, handles, box) -> list[tuple[float, float, str]]:
    """Vách đứng (x_trái, x_phải, handle) trong khung `box`: hai nét song song cách 8–60 mm cùng cao ≥ 60 % khung."""
    x0, z0, x1, z1 = box
    need = H_FRAC * (z1 - z0)
    ls = sorted((x, h) for x, lo, hi, h in _vlines(d, handles, x0, x1, z0, z1) if min(hi, z1) - max(lo, z0) >= need)
    out, i = [], 0
    while i < len(ls):
        j = i + 1
        while j < len(ls) and ls[j][0] - ls[i][0] < BOARD_MIN:
            j += 1
        if j < len(ls) and ls[j][0] - ls[i][0] <= BOARD_MAX:
            out.append((ls[i][0], ls[j][0], ls[i][1]))
            i = j + 1
        else:
            i += 1
    return out


def _clusters(d: Drawing2D, v: View) -> list[tuple[float, float, list[str]]]:
    items = []
    for h in v.handles:
        e = d.entities[h]
        if d.roles.get(e.layer) in BODY | {"hidden"} and e.type not in ("TEXT", "MTEXT", "DIMENSION") and (b := entity_box(e, {})):
            items.append((b[0], b[2], h))
    items.sort()
    out: list[list] = []
    for a, b, h in items:
        if out and a <= out[-1][1] + CLUSTER_GAP:
            out[-1][1] = max(out[-1][1], b)
            out[-1][2].append(h)
        else:
            out.append([a, b, [h]])
    return [(a, b, hs) for a, b, hs in out]


def companions(d: Drawing2D, sc) -> list[dict]:
    """Hình đi kèm của mặt đứng chính: cụm bản vẽ khác trong cùng khung tiêu đề, hoặc mặt đứng khác của hạng mục, có bề
    ngang gần bằng (±15 %). Căn X bằng bỏ phiếu vị trí vách (sai lệch 2 mm), không có vách chung thì căn mép trái."""
    mods = [m for m in sc.modules if m.elevation and len(m.ebox) == 4]
    if not mods:
        return []
    main = d.view(mods[0].elevation)
    mx0, mx1 = min(m.ebox[0] for m in mods), max(m.ebox[2] for m in mods)
    z0, z1 = min(m.ebox[1] for m in mods), max(m.ebox[3] for m in mods)
    width = mx1 - mx0
    cands = [(a, b, hs, main.id) for a, b, hs in _clusters(d, main) if not (a - 1 <= (mx0 + mx1) / 2 <= b + 1)]
    for v in d.views_of(sc.item, "elevation"):
        if v.id != main.id and v.box:
            cands += [(a, b, hs, v.id) for a, b, hs in _clusters(d, v)]
    main_x = [x for x, *_ in _vlines(d, main.handles, mx0, mx1, z0, z1)]
    out = []
    for a, b, hs, vid in cands:
        if not 0.85 * width <= (b - a) <= 1.15 * width:
            continue
        xs = [x for x, *_ in _vlines(d, hs, a, b, -1e12, 1e12)]
        votes: dict[int, int] = {}
        for x in xs:
            for y in main_x:
                k = round((y - x) / 2)
                votes[k] = votes.get(k, 0) + 1
        off = max(votes, key=votes.get) * 2 if votes and max(votes.values()) >= 3 else mx0 - a
        out.append({"view": vid, "handles": hs, "offset": float(off), "box": (a, b)})
    return out


def _all_boards(d: Drawing2D, sc) -> list[dict]:
    """Vách trong các khối, quy về toạ độ mặt đứng chính: [{x0, x1, handle, source}]."""
    mods = [m for m in sc.modules if m.elevation and len(m.ebox) == 4]
    if not mods:
        return []
    main = d.view(mods[0].elevation)
    out = []
    for m in mods:
        for a, b, h in boards(d, main.handles, m.ebox):
            out.append({"x0": a, "x1": b, "handle": h, "source": "main", "module": m.id})
    for c in companions(d, sc):
        zlo, zhi = _zrange(d, c["handles"])
        for m in mods:
            for a, b, h in boards(d, c["handles"], (m.ebox[0] - c["offset"], zlo, m.ebox[2] - c["offset"], zhi)):
                out.append({"x0": a + c["offset"], "x1": b + c["offset"], "handle": h, "source": "companion", "view": c["view"],
                            "module": m.id})
    return out


def _zrange(d: Drawing2D, handles) -> tuple[float, float]:
    zs = [z for h in handles if (b := entity_box(d.entities[h], {})) for z in (b[1], b[3])]
    return (min(zs), max(zs)) if zs else (0.0, 1.0)


def _module_at(sc, x: float):
    return next((m for m in sc.modules if m.elevation and len(m.ebox) == 4 and m.ebox[0] + EDGE_MIN <= x <= m.ebox[2] - EDGE_MIN), None)


def _fronts_draw(m) -> list[tuple[float, float]]:
    return [(f.x0 - m.x + m.ebox[0], f.x1 - m.x + m.ebox[0]) for f in m.fronts]


def _same_shelves(d: Drawing2D, vid: str, box, x: float) -> bool:
    from . import segment as seg

    v = d.view(vid)
    items = seg.items_in(d, v.handles, BODY | {"hidden"})
    left = [it for it in items if box[0] - 1 <= it[0][0] and it[0][2] <= x + 1 and box[1] - 1 <= it[0][1] and it[0][3] <= box[3] + 1]
    right = [it for it in items if x - 1 <= it[0][0] and it[0][2] <= box[2] + 1 and box[1] - 1 <= it[0][1] and it[0][3] <= box[3] + 1]
    if not left or not right:
        return False
    a, b = seg.board_levels(left), seg.board_levels(right)
    return bool(a) and len(a) == len(b) and all(abs(p - q) <= 5.0 for p, q in zip(a, b))


def check_split(d: Drawing2D, sc, x: float, evidence: list[str] | None = None) -> tuple[bool, str]:
    m = _module_at(sc, x)
    if m is None:
        return False, "đường chia không nằm trong khối nào (hoặc sát mép < 150 mm)"
    if m.form in ("filler", "panel"):
        return False, "khối là tấm bù/tấm ốp, không chia"
    for a, b in _fronts_draw(m):
        if a + 5 < x < b - 5:
            return False, "đường chia cắt qua cánh/ngăn kéo"
    # vách phải thuộc chính khối này (chồng theo chiều cao): hồi của tủ dưới không phải vách của tủ treo phía trên
    bs = [b for b in _all_boards(d, sc) if b.get("module") == m.id and b["x0"] - NEAR <= x <= b["x1"] + NEAR]
    if not bs:
        return False, "không có vách đứng (tấm ván cao gần suốt khối) ở vị trí này trên hình chính hoặc hình bỏ cánh"
    ev = {str(h).upper() for h in evidence or []}
    if ev and not any(b["handle"].upper() in ev for b in bs):
        return False, "nét dẫn không phải nét của vách ở vị trí này"
    return True, ""


def split_proposals(d: Drawing2D, sc, existing: list[float] | None = None) -> list[dict]:
    """Đề xuất chia khối bằng code: mỗi vách nằm trong một khối, không cắt qua cánh; bám đầu kích thước ngang nếu có."""
    have = list(existing or [])
    mods = [m for m in sc.modules if m.elevation and len(m.ebox) == 4]
    if not mods:
        return []
    dims = [x for x in view_dims(d, d.view(mods[0].elevation)) if x.axis == "h"]
    ends = sorted({round(v, 1) for x in dims for v in (x.lo, x.hi)})
    out = []
    for b in sorted(_all_boards(d, sc), key=lambda b: (b["source"] != "main", b["x0"])):
        snap = [v for v in ends if b["x0"] - 3 <= v <= b["x1"] + 3]
        x = round(min(snap, key=lambda v: abs(v - (b["x0"] + b["x1"]) / 2)) if snap else (b["x0"] + b["x1"]) / 2, 1)
        if any(abs(x - y) <= NEAR for y in have):
            continue
        ok, _why = check_split(d, sc, x, [b["handle"]])
        if not ok:
            continue
        m = _module_at(sc, x)
        if _same_shelves(d, mods[0].elevation, m.ebox, x):
            continue  # đợt hai bên cùng cao độ: vách chia trong cùng một tủ, không phải ranh giới
        have.append(x)
        where = "hình chính" if b["source"] == "main" else "hình bỏ cánh/hình đi kèm"
        out.append({"key": f"split:{sc.item}", "value": f"{x:.1f}", "evidence": [b["handle"]], "origin": "code", "module": m.id,
                    "reason": f"Khối {m.id} có vách đứng (tấm ván dày {b['x1'] - b['x0']:.0f} mm, cao gần suốt khối) ở {where}, "
                              f"cách mép trái khối {x - m.ebox[0]:.0f} mm{', trùng đầu kích thước' if snap else ''}: chia thành hai khối "
                              f"{x - m.ebox[0]:.0f} + {m.ebox[2] - x:.0f} mm."})
    return out


AI_TASK = (
    "Chia khối: 'split_candidates' là các vách đứng code tìm được trong khối (đã kiểm không cắt qua cánh). Với mỗi ứng viên, "
    "quyết định đó là RANH GIỚI giữa hai tủ/hai phần chức năng khác nhau (vd. tủ 2 cánh | cột ngăn kéo) hay chỉ là VÁCH CHIA "
    "trong cùng một tủ (vd. hai khoang giống nhau). Chỉ đề xuất ranh giới: "
    '{"key": "split:<item>", "value": "<x của ứng viên>", "evidence": ["<handle của ứng viên>"], "reason": "<vì sao>"}.')


def llm_context(d: Drawing2D, sc, cands: list[dict]) -> dict:
    from .explain import _vi

    mods = [m for m in sc.modules if m.elevation and len(m.ebox) == 4]
    texts = []
    if mods:
        main = d.view(mods[0].elevation)
        for h in main.handles:
            e = d.entities[h]
            p = e.pos or e.insert
            if e.type in ("TEXT", "MTEXT") and e.text and p:
                texts.append({"text": _vi(e.text)[:60], "x": round(p[0], 1), "z": round(p[1], 1)})
    return {"task": AI_TASK, "modules": [{"id": m.id, "form": m.form, "x0": m.ebox[0], "x1": m.ebox[2], "z0": m.ebox[1], "z1": m.ebox[3],
                                          "fronts": [[round(a, 1), round(b, 1)] for a, b in _fronts_draw(m)]} for m in mods],
            "split_candidates": [{"x": c["value"], "evidence": c["evidence"], "module": c.get("module"), "code_reason": c["reason"]}
                                 for c in cands],
            "notes": texts[:120]}


def apply_splits(d: Drawing2D, blocks: list[tuple], xs: list[float]) -> list[tuple]:
    """Cắt khung khối tại các x đã duyệt: nét/mặt trước chia theo tâm. blocks: (box, handles, fronts, form, levels)."""
    out = []
    for box, hs, fr, form, levels in blocks:
        cuts = sorted(x for x in xs if box[0] + EDGE_MIN <= x <= box[2] - EDGE_MIN)
        if not cuts or form in ("filler", "panel"):
            out.append((box, hs, fr, form, levels))
            continue
        edges = [box[0]] + cuts + [box[2]]
        for a, b in zip(edges, edges[1:]):
            def inside(bb, a=a, b=b):
                c = (bb[0] + bb[2]) / 2
                return a <= c < b

            sub_h = [h for h in hs if (bb := entity_box(d.entities[h], {})) and inside(bb)]
            sub_f = [(r, h) for r, h in fr if inside(r)]
            sub_form = "cabinet" if sub_f else ("open" if form == "cabinet" else form)
            from . import segment as seg

            sub_items = [it for it in seg.items_in(d, sub_h, BODY | {"hidden"}) if a - 1 <= it[0][0] and it[0][2] <= b + 1]
            sub_lv = len(seg.board_levels(sub_items)) if sub_items else 0  # đợt đếm lại theo từng phần
            out.append(((a, box[1], b, box[3]), sub_h, sub_f, sub_form, sub_lv))
    return out


def accepted(supp: dict, item: str) -> list[float]:
    raw = str(supp.get(f"split:{item}", "") or "")
    out = []
    for p in raw.split(";"):
        try:
            out.append(float(p))
        except ValueError:
            continue
    return out


__all__ = ["accepted", "apply_splits", "boards", "check_split", "companions", "llm_context", "split_proposals"]
