"""Đề xuất của LLM cho dựng 3D (3D-2): chỉ GHÉP hình chiếu và GÁN NHÃN khối, không bao giờ là số đo.

- `prompt_for(d, group, scene)`: dữ liệu gửi LLM (sau khi người dùng đồng ý theo phiên, như Studio): mã hình chiếu, loại,
  tiêu đề, nhãn, số kích thước và vài số đo lớn nhất của từng hình, khối đã dựng, phần thiếu. Không đường dẫn/tên tệp.
- `validate(raw, d, group, scene)`: mã kiểm từng đề xuất; nhận `link:<mặt đứng>` = `<mặt bằng>` cùng hạng mục,
  `label:<khối>` = nhãn trong danh sách cho phép, và SỐ cho ô phần thiếu (sâu khối, cao trần…) chỉ khi kèm bằng chứng:
  handle một kích thước/chữ thuộc hình của hạng mục mà số đo đúng bằng giá trị đề xuất (AI đọc ra số đã có trên bản vẽ
  nhưng vẽ theo kiểu code chưa hiểu; không bịa số).
- `code_suggestions(d, group, scene)`: gợi ý bằng code cho chiều sâu thiếu từ kích thước ngang của mặt cắt cùng hạng mục.
- Đề xuất hợp lệ được lưu "chờ xác nhận"; chỉ khi người dùng bấm xác nhận trên App mới ghi vào tệp bổ sung (`source: user`).
"""

from __future__ import annotations

import json
import re

from .views2d import Drawing2D, view_dims

SCHEMA = "cg.scene-proposals/1"
LABELS = ("tủ bếp dưới", "tủ bếp trên", "tủ cao", "tủ áo", "kệ tivi", "kệ trang trí", "bàn đảo", "quầy bar", "tủ giày",
          "tủ lavabo", "ghế băng", "ốp tường", "ốp trần", "khác")
MAX_PROPOSALS = 50

SYSTEM = (
    "Bạn hỗ trợ dựng 3D từ bản vẽ nội thất 2D (mỗi người kỹ thuật trình bày một kiểu). Được đề xuất bốn loại: "
    '(1) ghép mặt đứng với mặt bằng cùng hạng mục: {"key": "link:<mã mặt đứng>", "value": "<mã mặt bằng>"}; '
    '(2) gán nhãn khối: {"key": "label:<mã khối>", "value": "<một nhãn trong danh sách>"}; '
    '(3) điền số cho ô phần thiếu (khoá trong "gaps[].fields"): {"key": "<khoá ô>", "value": "<số mm>", "evidence": '
    '["<handle kích thước hoặc chữ trên bản vẽ có đúng số này>"]}. Số PHẢI đọc từ kích thước/chữ có sẵn trong "evidence" '
    "(vd. chiều sâu tủ ghi ở mặt cắt, ghi chú 'sâu 600'); không có bằng chứng thì không đề xuất. "
    '(4) chia khối tại vách: chỉ chọn trong "split.split_candidates", làm theo "split.task". '
    'Trả đúng JSON {"proposals": [{"key", "value", "evidence", "reason"}]}, lý do ngắn bằng tiếng Việt nói rõ số lấy ở hình nào.')
NUM_RE = re.compile(r"(?<![\d.])(\d{2,5}(?:[.,]\d+)?)(?![\d])")


def _evidence_pool(d: Drawing2D, group: str) -> dict[str, dict]:
    """Kích thước + chữ có số trong các hình của hạng mục: {handle: {view, kind, values}} (để AI dẫn và code kiểm)."""
    out: dict[str, dict] = {}
    for v in d.views_of(group):
        for h in v.handles:
            e = d.entities[h]
            vals = []
            if e.type == "DIMENSION" and e.dim_value:
                vals = [round(float(e.dim_value), 1)]
            elif e.type in ("TEXT", "MTEXT") and e.text:
                vals = [float(x.replace(",", ".")) for x in NUM_RE.findall(e.text)]
            if vals:
                out[h] = {"view": v.id, "kind": v.kind, "title": v.title, "values": vals,
                          **({"text": e.text[:60]} if e.type in ("TEXT", "MTEXT") else {})}
    return out


def code_suggestions(d: Drawing2D, group: str, scene) -> list[dict]:
    """Chiều sâu thiếu: kích thước ngang lớn nhất (250–1200 mm) của từng mặt cắt cùng hạng mục; khối treo ưu tiên số nhỏ.
    Chỉ là gợi ý có bằng chứng, người dùng xác nhận."""
    cands = []
    for v in d.views_of(group, "section"):
        hs = [x for x in view_dims(d, v) if x.axis == "h" and 250 <= x.value <= 1200]
        if hs:
            cands.append(max(hs, key=lambda x: x.value))
    out = []
    for g in scene.gaps:
        for f in g.fields:
            if not f.key.startswith("module:") or not f.key.endswith(":d") or not cands:
                continue
            wall = "tủ treo" in g.message
            vals = sorted({round(x.value) for x in cands})
            pick = vals[0] if wall else vals[-1]
            ev = next(x for x in cands if round(x.value) == pick)
            out.append({"key": f.key, "value": str(pick), "evidence": [ev.handle], "origin": "code",
                        "reason": f"Kích thước ngang {pick} mm ở mặt cắt {d.view(next(v.id for v in d.views_of(group, 'section') if ev.handle in v.handles)).title or ''}"
                                  f" ({'số nhỏ nhất: tủ treo' if wall else 'số lớn nhất'} trong {len(vals)} mặt cắt)."})
    return out


def prompt_for(d: Drawing2D, group: str, scene) -> dict:
    views = []
    for v in d.views_of(group):
        if v.kind not in ("plan", "elevation", "section"):
            continue
        dims = view_dims(d, v)
        hs = sorted((x.value for x in dims if x.axis == "h"), reverse=True)[:5]
        vs = sorted((x.value for x in dims if x.axis == "v"), reverse=True)[:5]
        views.append({"id": v.id, "kind": v.kind, "title": v.title, "label": v.label, "flags": v.flags,
                      "size": [round(v.box[2] - v.box[0]), round(v.box[3] - v.box[1])] if v.box else None,
                      "dims_h_top": hs, "dims_v_top": vs})
    pool = _evidence_pool(d, group)
    return {"system": SYSTEM, "labels": list(LABELS), "item": group, "views": views,
            "modules": [{"id": m.id, "kind": m.kind, "w": m.w, "d": m.d, "h": m.h, "z0": m.z0, "fronts": len(m.fronts),
                         "src_d": m.src["d"].kind if "d" in m.src else "missing"} for m in scene.modules],
            "gaps": [{"id": g.id, "kind": g.kind, "message": g.message, "fields": [f.key for f in g.fields]} for g in scene.gaps],
            "evidence": [{"handle": h, **x} for h, x in list(pool.items())[:400]],
            "split": _split_ctx(d, scene)}


def _split_ctx(d: Drawing2D, scene) -> dict:
    from .annotate import llm_context, split_proposals

    cands = split_proposals(d, scene)
    return llm_context(d, scene, cands) if cands else {}


def _parse(raw) -> list:
    if isinstance(raw, str):
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return []
        try:
            raw = json.loads(m.group(0))
        except ValueError:
            return []
    if isinstance(raw, dict):
        raw = raw.get("proposals", [])
    return raw if isinstance(raw, list) else []


def validate(raw, d: Drawing2D, group: str, scene) -> tuple[list[dict], list[dict]]:
    """(đề xuất hợp lệ, đề xuất bị loại kèm lý do)."""
    plans = {v.id for v in d.views_of(group, "plan") if v.box}
    elevs = {v.id for v in d.views_of(group, "elevation") if v.box}
    mods = {m.id for m in scene.modules} | {g.target for g in scene.gaps if g.id.startswith("module:")}
    fields = {f.key: f for g in scene.gaps for f in g.fields}
    pool = None
    ok, bad = [], []
    for p in _parse(raw)[:MAX_PROPOSALS]:
        if not isinstance(p, dict):
            continue
        key, value = str(p.get("key", ""))[:80], p.get("value")
        reason = str(p.get("reason", ""))[:300]
        why = None
        if key.startswith("link:"):
            if key[5:] not in elevs:
                why = "mặt đứng không thuộc hạng mục"
            elif value not in plans:
                why = "mặt bằng không thuộc hạng mục"
        elif key.startswith("label:"):
            if key[6:] not in mods:
                why = "không có khối này"
            elif value not in LABELS:
                why = "nhãn ngoài danh sách"
        elif key == f"split:{group}":
            from .annotate import check_split

            try:
                num = float(str(value).replace(",", "."))
            except ValueError:
                num = None
            ev = [str(h).upper() for h in (p.get("evidence") or []) if isinstance(h, (str, int))][:10]
            if num is None:
                why = "toạ độ chia không phải số"
            else:
                good, msg = check_split(d, scene, num, ev)
                if not good:
                    why = msg
                else:
                    value = f"{num:.1f}"
                    p = {**p, "evidence": ev}
        elif key in fields and fields[key].kind != "choice":
            pool = pool if pool is not None else _evidence_pool(d, group)
            try:
                num = float(str(value).replace(",", "."))
            except ValueError:
                num = None
            ev = [str(h).upper() for h in (p.get("evidence") or []) if isinstance(h, (str, int))][:10]
            if num is None or not 0 < num < 100000:
                why = "giá trị không phải số mm hợp lệ"
            elif not ev:
                why = "thiếu bằng chứng (handle kích thước/chữ trên bản vẽ)"
            elif not any(h in pool and any(abs(x - num) <= 1.0 for x in pool[h]["values"]) for h in ev):
                why = "bằng chứng không thuộc hạng mục hoặc không có đúng số này"
            else:
                value = f"{num:g}"
                p = {**p, "evidence": ev}
        else:
            why = "chỉ nhận ghép hình chiếu, gán nhãn, hoặc số cho ô phần thiếu kèm bằng chứng"
        extra = {"evidence": p["evidence"]} if p.get("evidence") and not why else {}
        (bad if why else ok).append({"key": key, "value": value, "reason": reason, **extra,
                                     **({"rejected": why} if why else {"origin": str(p.get("origin") or "llm")[:8]})})
    return ok, bad


__all__ = ["LABELS", "SCHEMA", "SYSTEM", "code_suggestions", "prompt_for", "validate"]
