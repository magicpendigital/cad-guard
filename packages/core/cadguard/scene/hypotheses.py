"""L4 (P4) — SINH CÁCH HIỂU VÀ CHỌN THEO ĐIỂM (thiết kế `docs/research/kien-truc-doc-ban-ve-tong-the.md`).

Ở chỗ bản vẽ mơ hồ, máy không chọn ngay bằng một quy tắc mà dựng thử vài cách hiểu, chấm từng cách bằng ràng buộc
(`consistency.check`) + bằng chứng trên bản vẽ, rồi chọn. Mỗi cách hiểu là một BỘ KHOÁ BỔ SUNG đã có (người dùng chọn
cũng ghi đúng các khoá này), nên dựng vẫn tất định và lặp lại được:

- `role` — vai trò hình: khi có ≥ 2 mặt đứng "sinh đôi" (cùng mặt bằng, cùng bề rộng, cùng vị trí): hình nào dựng
  khối/cánh (`main:<hạng mục>`), hình nào đọc nội thất (`interior:<hạng mục>`, hoặc `none`).
- `board` — nét đôi ở hình chính là TẤM (đọc hình chính như hình bỏ cánh: `interior:` = mã hình chính) hay MÉP CÁNH
  (`interior:` = `none`); chỉ hỏi khi không có hình bỏ cánh riêng mà hình chính có chữ nội thất.
- `split@<x>` — chia khối tại vách đề xuất (`split:<hạng mục>`) hay giữ một khối.

Điểm một cách hiểu (0..1) = 0,35 × nhất quán + 0,25 × ký hiệu cánh + 0,30 × ghi chú được giải thích + 0,10 × bề rộng
khối có kích thước. Cách hiểu đang dựng (không thêm khoá) là phương án 0. Máy chỉ đổi khi phương án khác hơn ≥ `MARGIN`;
chênh nhỏ hơn mà cảnh khác nhau thì giữ phương án 0 và tạo thẻ "máy phân vân". Quyết định người dùng đã chọn (khoá đã có,
hoặc mã trong `decided:<hạng mục>`) không dựng lại. Giới hạn `MAX_BUILDS` lần dựng mỗi hạng mục.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter

from . import primitives as prim
from .assemble import NONE_VIEW, Scene2, _links, build_once
from .feasibility import room_height_dim
from .views2d import Drawing2D, View

MARGIN = 0.05
MAX_BUILDS = 16
W = {"cons": 0.35, "door": 0.25, "notes": 0.30, "dims": 0.10}
TWIN_W = 0.10  # hai mặt đứng "sinh đôi": bề rộng lệch ≤ 10 %
TWIN_OV = 0.80  # và chồng ≥ 80 % trên trục X của mặt bằng
NOTE_KINDS = {"drawer": ("drawer",), "appliance": ("appliance",), "rod": ("rod",), "light": ("light",), "glass": ("glass",),
              "stone": ("stone",)}
INNER_NOTE = ("drawer", "appliance", "rod", "light")
NOTE_DX, NOTE_DZ = 150.0, 400.0


def decided(supp: dict, item: str) -> set[str]:
    return {x for x in str(supp.get(f"decided:{item}", "") or "").split(";") if x}


def _sig(sc: Scene2) -> str:
    data = sc.model_dump(by_alias=True, exclude={"scene_hash", "notes"})
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:16]


# ---------------- đặc trưng bản vẽ (tính một lần mỗi hạng mục) ----------------

class Ctx:
    def __init__(self, d: Drawing2D, group: str, base: Scene2):
        self.d, self.group = d, group
        plans = [v for v in d.views_of(group, "plan") if v.box]
        elevs = [v for v in d.views_of(group, "elevation") if v.box]
        self.links = _links(d, plans, elevs, {}, Scene2(item=group)) if plans and elevs else {}
        self.main = base._mode.get("main") or (Counter(m.elevation for m in base.modules if m.elevation).most_common(1) or [("", 0)])[0][0]
        self.twins = self._twins()
        self.door = {vid: prim.door_symbol_area(self.d, self.links[vid][0]) for vid in self.twins}
        if not any(self.door.values()):
            self.door = {vid: float(prim.front_rects(self.d, self.links[vid][0])) for vid in self.twins}
        self.notes = self._notes(base)

    def _span(self, vid: str) -> tuple[float, float]:
        """Bề ngang THÂN TỦ của hình trên trục X mặt bằng (khung hình còn chứa kích thước, ghi chú nên không dùng)."""
        e, _p, ox, _r, _m = self.links[vid]
        items = prim.items_in(self.d, e.handles, prim.BODY | {"visible"}) or prim.items_in(self.d, e.handles, prim.BODY)
        b = prim.box_of(items) if items else e.box
        return b[0] + ox, b[2] + ox

    def _twins(self) -> list[str]:
        """Mặt đứng cùng mặt bằng, cùng bề rộng và vị trí với hình chính, và là một cặp "có cánh / bỏ cánh": cùng tiêu đề
        (người vẽ chép tiêu đề) hoặc một trong hai có tiêu đề "bỏ cánh". Hai hướng nhìn khác tiêu đề (hướng A / hướng B
        của quầy đảo) là hai mặt khác nhau, không phải cặp."""
        if self.main not in self.links:
            return [self.main] if self.main else []
        a0, a1 = self._span(self.main)
        me = self.links[self.main][0]
        out = [self.main]
        for vid, lk in sorted(self.links.items()):
            if vid == self.main or lk[1].id != self.links[self.main][1].id:
                continue
            same_title = (lk[0].title or "").strip().upper() == (me.title or "").strip().upper()
            if not (same_title or "no_doors" in lk[0].flags or "no_doors" in me.flags):
                continue
            b0, b1 = self._span(vid)
            wa, wb = a1 - a0, b1 - b0
            ov = max(0.0, min(a1, b1) - max(a0, b0))
            if wa > 0 and wb > 0 and abs(wa - wb) <= TWIN_W * max(wa, wb) and ov >= TWIN_OV * min(wa, wb):
                out.append(vid)
        return out

    def _notes(self, base: Scene2) -> list[tuple[float, float, str, str]]:
        """Chữ có nghĩa nội thất (hộc, thiết bị, thanh treo, đèn, kính, đá) ở các hình sinh đôi, theo toạ độ hạng mục."""
        if not self.links or self.main not in self.links:
            return []
        origin = self.links[self.main][1].box[0]
        mods = [m for m in base.modules if m.form not in ("filler", "panel")]
        if not mods:
            return []
        x0, x1 = min(m.x for m in mods) - 50, max(m.x + m.w for m in mods) + 50
        out, seen = [], set()
        for vid in self.twins:
            v: View = self.links[vid][0]
            ox = self.links[vid][2] - origin
            rh = room_height_dim(self.d, v)
            fl = rh.lo if rh else v.box[1]
            sheet_hs = [h for s in self.d.structure.sheets if s.id == v.sheet_id for h in s.handles if h in self.d.entities]
            b = v.box
            for x, z, t, h in prim.text_items(self.d, sheet_hs):
                if h in seen or not (b[0] - 5 <= x <= b[2] + 5 and b[1] - 5 <= z <= b[3] + 5):
                    continue
                mean = prim.meaning(self.d, t)
                if mean in NOTE_KINDS and x0 <= x + ox <= x1:
                    seen.add(h)
                    out.append((x + ox, z - fl, mean, h))
        return out

    def inner_notes_on(self, vid: str) -> int:
        """Số chữ nội thất (hộc, thiết bị, thanh treo, đèn) nằm trên hình `vid`."""
        if vid not in self.links:
            return 0
        v = self.links[vid][0]
        return sum(1 for *_xy, t, _h in prim.text_items(self.d, v.handles) if prim.meaning(self.d, t) in INNER_NOTE)


# ---------------- chấm điểm ----------------

def _doorness(ctx: Ctx, vid: str) -> float:
    return ctx.door.get(vid, 0.0)


def _is_inner_view(ctx: Ctx, vid: str, main: str) -> bool:
    """Hình `vid` có dáng hình bỏ cánh so với hình chính: tiêu đề ghi "bỏ cánh" mà hình chính không ghi, hoặc ít hơn nửa
    ký hiệu cánh (hình bỏ cánh vẫn có thể giữ ký hiệu ngăn kéo)."""
    if vid not in ctx.links or vid == main:
        return False
    if "no_doors" in ctx.links[vid][0].flags and "no_doors" not in (ctx.links[main][0].flags if main in ctx.links else ()):
        return True
    dm, di = _doorness(ctx, main), _doorness(ctx, vid)
    return dm > 0 and di < 0.5 * dm


def _door_term(ctx: Ctx, sc: Scene2) -> float:
    """Hình dựng cánh nên là hình nhiều ký hiệu cánh nhất (a); nội thất nên đọc ở hình có dáng bỏ cánh nếu có (b)."""
    main, inter, mode = sc._mode.get("main", ""), sc._mode.get("interior", ""), sc._mode.get("interior_mode", False)
    top = max(ctx.door.values() or [0.0])
    if top > 0:
        a = _doorness(ctx, main) / top if main in ctx.door else 1.0
    else:  # không hình nào có ký hiệu cánh: tiêu đề "bỏ cánh" ở hình chính là dấu hiệu ngược
        flagged = main in ctx.links and "no_doors" in ctx.links[main][0].flags
        a = 0.5 if flagged and any("no_doors" not in ctx.links[t][0].flags for t in ctx.twins if t in ctx.links) else 1.0
    if _doorness(ctx, main) > 0 and not any(m.fronts for m in sc.modules):
        a = 0.0  # hình chính có ký hiệu / khung cánh mà cảnh không có mặt trước nào: cánh bị bỏ sót
    if inter and inter != main:
        b = 1.0 if _is_inner_view(ctx, inter, main) else (0.0 if _doorness(ctx, inter) > _doorness(ctx, main) else 0.5)
    elif mode:  # đọc hình chính như hình bỏ cánh: phạt theo ký hiệu cánh trên hình chính
        v = ctx.links[main][0] if main in ctx.links else None
        area = max((v.box[2] - v.box[0]) * (v.box[3] - v.box[1]), 1.0) if v is not None else 1.0
        b = 1.0 - min(1.0, (prim.door_symbol_area(ctx.d, v) if v is not None else 0.0) / (0.1 * area))
    else:  # không đọc hình bỏ cánh: phạt khi có hình bỏ cánh mà không dùng
        b = 0.25 if any(_is_inner_view(ctx, t, main) for t in ctx.twins) else 0.75
    return (a + b) / 2


def _notes_term(ctx: Ctx, sc: Scene2) -> float:
    if not ctx.notes:
        return 1.0
    from .consistency import DRAWER_MAX

    things = []
    for m in sc.modules:  # đồ đọc sai (hộc cao bất thường) không giải thích được ghi chú
        things += [(q["kind"], q["x0"], q["x1"], q["z0"], q["z1"], q.get("refs", [])) for q in m.inner
                   if not (q["kind"] == "drawer" and q["z1"] - q["z0"] > DRAWER_MAX)]
        things += [(f.kind, f.x0, f.x1, f.z0, f.z1, f.refs) for f in m.fronts if f.kind == "drawer"]
    ok = 0
    for x, z, mean, h in ctx.notes:
        kinds = NOTE_KINDS[mean]
        if any(k in kinds and (h in refs or (x0 - NOTE_DX <= x <= x1 + NOTE_DX and z0 - NOTE_DZ <= z <= z1 + NOTE_DZ))
               for k, x0, x1, z0, z1, refs in things):
            ok += 1
    return ok / len(ctx.notes)


def _dims_term(sc: Scene2) -> float:
    mods = [m for m in sc.modules if m.form not in ("filler", "panel")]
    if not mods:
        return 1.0
    return sum(1 for m in mods if "w" in m.src and m.src["w"].kind in ("dimension", "user")) / len(mods)


def score(ctx: Ctx, sc: Scene2) -> dict:
    from .consistency import check

    cons = check(sc)
    parts = {"cons": cons["score"], "door": _door_term(ctx, sc), "notes": _notes_term(ctx, sc), "dims": _dims_term(sc)}
    total = round(sum(W[k] * v for k, v in parts.items()), 4)
    return {"total": total, "parts": {k: round(v, 3) for k, v in parts.items()}, "conflicts": cons["counts"]["conflict"]}


# ---------------- quyết định + phương án ----------------

def _view_label(ctx: Ctx, vid: str) -> str:
    v = ctx.links[vid][0] if vid in ctx.links else ctx.d.view(vid)
    t = (getattr(v, "title", "") or "").strip()
    return f"{vid}" + (f" ({t[:40]})" if t else "")


def decisions(ctx: Ctx, supp: dict, base: Scene2) -> list[dict]:
    """Chỗ mơ hồ của hạng mục và các phương án (phương án 0 = cách đang dựng, không thêm khoá)."""
    g, done = ctx.group, decided(supp, ctx.group)
    out = []
    pinned_role = f"main:{g}" in supp or f"interior:{g}" in supp
    if len(ctx.twins) >= 2 and not pinned_role and "role" not in done:
        opts = []
        for m in ctx.twins:
            for i in [x for x in ctx.twins if x != m] + [NONE_VIEW]:
                why = (f"Hình {_view_label(ctx, m)} dựng khối và cánh; "
                       + (f"hình {_view_label(ctx, i)} đọc nội thất." if i != NONE_VIEW else "không có hình bỏ cánh riêng."))
                opts.append({"keys": {f"main:{g}": m, f"interior:{g}": i}, "label": why})
        out.append({"id": "role", "title": "Vai trò các mặt đứng cùng một bức tường (hình có cánh / hình bỏ cánh)",
                    "options": opts[:MAX_BUILDS // 2]})
    main, inter = base._mode.get("main", ""), base._mode.get("interior", "")
    if (not pinned_role and "board" not in done and main and inter == main and len(ctx.twins) < 2
            and ctx.inner_notes_on(main) > 0):
        out.append({"id": "board", "title": "Nét đôi trên mặt đứng chính là tấm ván hay mép cánh",
                    "options": [{"keys": {f"interior:{g}": main}, "label": "Nét đôi là TẤM (đợt, vách): đọc nội thất ngay trên hình chính."},
                                {"keys": {f"interior:{g}": NONE_VIEW}, "label": "Nét đôi là MÉP CÁNH / tay nắm: chỉ đọc tầng, không đọc vách."}]})
    from .annotate import accepted, split_proposals

    have = accepted(supp, g)
    try:
        props = split_proposals(ctx.d, base, have)
    except Exception:  # noqa: BLE001 — gợi ý phụ
        props = []
    for pr in props[:3]:
        did = f"split@{float(pr['value']):.0f}"
        if did in done:
            continue
        val = ";".join(f"{x:.1f}" for x in sorted(have + [float(pr["value"])]))
        out.append({"id": did, "title": f"Chia khối {pr.get('module', '')} tại x = {float(pr['value']):.0f}",
                    "options": [{"keys": {f"split:{g}": val}, "label": pr["reason"], "refs": pr.get("evidence", [])}]})
    return out


def _refs(sc: Scene2, cap: int = 60) -> list[str]:
    out = []
    for m in sc.modules:
        for f in m.fronts:
            out += f.refs
        for q in m.inner:
            out += q.get("refs", [])
    return [r for r in dict.fromkeys(out) if r][:cap]


def resolve(d: Drawing2D, group: str, supp: dict) -> Scene2:
    """Dựng cách hiểu tốt nhất của hạng mục. Báo cáo ở `sc._choice` = {decisions: [...], builds}."""
    base = build_once(d, group, supp)
    try:
        ctx = Ctx(d, group, base)
        decs = decisions(ctx, supp, base)
    except Exception:  # noqa: BLE001 — L4 không được làm hỏng cách dựng một lần
        return base
    if not decs:
        return base
    cache: dict[str, tuple[Scene2, dict]] = {}
    builds = [0]

    def ev(keys: dict) -> tuple[Scene2, dict]:
        k = json.dumps(keys, sort_keys=True)
        if k not in cache:
            if keys:
                builds[0] += 1
                sc = build_once(d, group, {**supp, **keys})
            else:
                sc = base
            cache[k] = (sc, score(ctx, sc))
        return cache[k]

    chosen: dict = {}
    report = []
    for dec in decs:
        if builds[0] >= MAX_BUILDS:
            break
        cur_sc, cur_s = ev(dict(chosen))
        rows = [{"label": "Cách hiểu ban đầu.", "keys": {}, "sc": cur_sc, "s": cur_s, "refs": []}]
        sigs = {_sig(cur_sc)}
        for o in dec["options"]:
            if builds[0] >= MAX_BUILDS:
                break
            sc, s = ev({**chosen, **o["keys"]})
            sig = _sig(sc)
            if sig in sigs:  # cùng cảnh với một phương án đã có: không phải cách hiểu khác
                continue
            sigs.add(sig)
            rows.append({"label": o["label"], "keys": o["keys"], "sc": sc, "s": s, "refs": o.get("refs", [])})
        if len(rows) < 2:
            continue
        rows[0]["label"] = "Cách hiểu ban đầu: " + _describe(ctx, rows[0]["sc"], dec["id"])
        base_c = rows[0]["s"]["conflicts"]
        ok = [r for r in rows[1:] if r["s"]["conflicts"] <= base_c]  # thêm mâu thuẫn kết cấu = loại (ràng buộc cứng)
        best = max(ok or rows[1:], key=lambda r: r["s"]["total"])
        gap = round(best["s"]["total"] - rows[0]["s"]["total"], 4)
        if not ok:
            status, pick = "kept", rows[0]
        elif gap >= MARGIN:
            status, pick = "auto", best
            chosen.update(best["keys"])
        elif abs(gap) < MARGIN:
            status, pick = "unsure", rows[0]
        else:
            status, pick = "kept", rows[0]
        report.append({"id": dec["id"], "title": dec["title"], "status": status, "gap": gap,
                       "options": [{"label": r["label"], "keys": r["keys"], "score": r["s"]["total"], "parts": r["s"]["parts"],
                                    "conflicts": r["s"]["conflicts"], "chosen": r is pick,
                                    "refs": (r["refs"] or _refs(r["sc"]))[:60]} for r in rows]})
    final, _s = ev(dict(chosen))
    mode = dict(final._mode)
    final = final.model_copy(deep=True)  # cảnh trong bộ đệm giữ nguyên; ghi chú chỉ thêm vào bản trả về
    final._mode = mode
    for r in report:
        opt = next(o for o in r["options"] if o["chosen"])
        others = sorted((o["score"] for o in r["options"] if not o["chosen"]), reverse=True)
        if r["status"] == "auto":
            final.notes.insert(1, f"Máy chọn cách hiểu ({r['title'].lower()}): {opt['label']} "
                                  f"Điểm {opt['score']:.2f} so với {r['options'][0]['score']:.2f} của cách hiểu ban đầu.")
        elif r["id"] == "role":
            final.notes.insert(1, f"Vai trò hình (máy chấm {len(r['options'])} cách hiểu): {_describe(ctx, final, 'role')} "
                                  f"Điểm {opt['score']:.2f}; cách hiểu kế tiếp {others[0]:.2f}"
                                  + (" — chênh ít, xem thẻ \"máy phân vân\"." if r["status"] == "unsure" else "."))
    final.scene_hash = final.compute_hash()
    final._choice = {"decisions": report, "builds": builds[0], "keys": chosen}
    return final


def _describe(ctx: Ctx, sc: Scene2, did: str) -> str:
    m, i, mode = sc._mode.get("main", ""), sc._mode.get("interior", ""), sc._mode.get("interior_mode", False)
    if did == "role" or did == "board":
        if i and i != m:
            return f"hình {_view_label(ctx, m)} dựng khối và cánh, hình {_view_label(ctx, i)} đọc nội thất."
        return f"hình {_view_label(ctx, m)} dựng cánh; nét đôi trên hình này là {'tấm' if mode else 'mép cánh'}."
    return "không chia khối ở đây."


def cards(sc: Scene2) -> list[dict]:
    """Thẻ cho màn 3D: quyết định máy đã đổi (auto) hoặc còn phân vân (unsure)."""
    ch = getattr(sc, "_choice", None) or {}
    # chia khối còn phân vân đã hiện thành đề xuất chia khối (chú giải hạng mục): không lặp thẻ
    return [r for r in ch.get("decisions", []) if r["status"] == "auto" or (r["status"] == "unsure" and not r["id"].startswith("split@"))]


__all__ = ["MARGIN", "cards", "decided", "decisions", "resolve", "score"]
