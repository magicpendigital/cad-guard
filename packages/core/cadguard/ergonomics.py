"""3D-4 Công thái học: đo tất định trên cảnh `cg.scene/2` + kiểm nhận xét AI (`cg.ergonomics-review/1`).

- `measures(scene)`: mọi số đo (mã m1, m2…) kèm phần tử, handle nguồn và nguồn số liệu của cảnh.
- `check(scene, std)`: kết quả ER-xx (`cg.ergonomics/1`). Tiêu chí có `range` (đã duyệt, có nguồn) -> đạt/không đạt;
  `range: null` -> chỉ báo số đo, trạng thái "chờ duyệt"; ER-06 (va chạm vùng quét cánh) là hình học, không cần ngưỡng.
- `review_prompt(result)`: dữ liệu + chỉ dẫn cho LLM viết nhận xét có cấu trúc (ba bước: đo đạc / đánh giá / phản biện).
- `validate_review(review, result)`: harness: mục AI phải trỏ tới ≥ 1 số đo có thật của đúng tiêu chí; mọi số trong lời
  văn phải khớp số đo được trỏ hoặc biên khoảng đã duyệt; sai thì loại kèm lý do. Nhận xét AI luôn gắn nhãn riêng.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .scene.assemble import Scene2
from .standard import Standard, load_standard

SCHEMA = "cg.ergonomics/1"
REVIEW_SCHEMA = "cg.ergonomics-review/1"
STANDARD = "ergonomics-v0"
SEVERITIES = ("info", "warn", "error")
CONFIDENCE = ("low", "medium", "high")
NUM_TOL = 0.5


@dataclass
class Measure:
    id: str
    criterion: str
    value: float
    unit: str
    elements: list[str]
    refs: list[str] = field(default_factory=list)  # handle bản vẽ
    sources: list[str] = field(default_factory=list)  # dimension | geometry | user | default
    note: str = ""


def _ovl(a0, a1, b0, b1) -> float:
    return min(a1, b1) - max(a0, b0)


def _src(m, *keys) -> tuple[list[str], list[str]]:
    refs, kinds = [], []
    for k in keys:
        s = m.src.get(k)
        if s:
            refs += s.refs
            kinds.append(s.kind)
    return refs, sorted(set(kinds))


def _wall_boxes(sc: Scene2):
    from .scene.geometry import _seg_base

    out = []
    for w in sc.walls:
        b = _seg_base(w.start, w.end, w.thickness, w.side)
        xs, ys = [p[0] for p in b], [p[1] for p in b]
        out.append((w.id, min(xs), min(ys), max(xs), max(ys)))
    return out


def measures(sc: Scene2) -> list[Measure]:
    out: list[Measure] = []

    def add(crit, value, unit, elements, refs, kinds, note=""):
        out.append(Measure(f"m{len(out) + 1}", crit, round(value, 1), unit, elements, refs, kinds, note))

    base = [m for m in sc.modules if m.kind == "base"]
    wall = [m for m in sc.modules if m.kind == "wall"]
    for m in base:
        r, k = _src(m, "z0", "h")
        add("ER-01", m.z0 + m.h, "mm", [m.id], r, k)
        r, k = _src(m, "d")
        add("ER-03", m.d, "mm", [m.id], r, k)
    for u in wall:
        r, k = _src(u, "d")
        add("ER-04", u.d, "mm", [u.id], r, k)
        for b in base:
            if _ovl(u.x, u.x + u.w, b.x, b.x + b.w) > 0:
                r1, k1 = _src(u, "z0")
                r2, k2 = _src(b, "z0", "h")
                add("ER-02", u.z0 - (b.z0 + b.h), "mm", [u.id, b.id], r1 + r2, sorted(set(k1 + k2)))
    for m in sc.modules:
        if m.kind in ("wall", "tall"):
            r, k = _src(m, "z0", "h")
            add("ER-05", m.z0 + m.h, "mm", [m.id], r, k)
    walls = _wall_boxes(sc)
    for m in sc.modules:
        if m.kind not in ("base", "tall"):
            continue
        # ER-07: từ mặt trước (y nhỏ) tới vật cản gần nhất phía trước, cùng khoảng X
        best = None
        for wid, x0, y0, x1, y1 in walls:
            if _ovl(x0, x1, m.x, m.x + m.w) > 1 and y1 <= m.y + 1:
                gap = m.y - y1
                if best is None or gap < best[0]:
                    best = (gap, wid)
        for o in sc.modules:
            if o is not m and o.kind in ("base", "tall") and _ovl(o.x, o.x + o.w, m.x, m.x + m.w) > 1 and o.y + o.d <= m.y + 1:
                gap = m.y - (o.y + o.d)
                if best is None or gap < best[0]:
                    best = (gap, o.id)
        if best is not None:
            r, k = _src(m, "d")
            add("ER-07", best[0], "mm", [m.id, best[1]], r, k + ["geometry"])
        # ER-06: vùng quét cánh (sâu = rộng cánh) trước mặt tủ, va tường/khối khác?
        for f in m.fronts:
            if f.kind != "door":
                continue
            reach = f.x1 - f.x0
            zone = (f.x0, m.y - reach, f.x1, m.y)
            hits = [wid for wid, x0, y0, x1, y1 in walls if _ovl(x0, x1, zone[0], zone[2]) > 1 and _ovl(y0, y1, zone[1], zone[3]) > 1]
            hits += [o.id for o in sc.modules if o is not m and o.z0 < f.z1 and o.z0 + o.h > f.z0
                     and _ovl(o.x, o.x + o.w, zone[0], zone[2]) > 1 and _ovl(o.y, o.y + o.d, zone[1], zone[3]) > 1]
            free = min([m.y - y1 for wid, x0, y0, x1, y1 in walls if wid in hits]
                       + [m.y - (o.y + o.d) for o in sc.modules if o.id in hits] or [reach])
            add("ER-06", round(reach - free, 1) if hits else 0.0, "mm", [f.id, *hits], f.refs, ["geometry"],
                note=f"cánh rộng {reach:g} quét sâu {reach:g}")
    return out


def load_ergonomics(standards_dir: Path | None = None) -> Standard:
    from .standard import find_standards_dir

    return load_standard(STANDARD, standards_dir or find_standards_dir())


def check(sc: Scene2, std: Standard | None = None) -> dict:
    std = std or load_ergonomics()
    ms = measures(sc)
    results = []
    for r in std.rules:
        p = r.params or {}
        mine = [m for m in ms if m.criterion == r.id]
        rng = p.get("range")
        if not r.enabled:
            status, fails = "tắt", []
        elif r.id == "ER-06":
            fails = [m for m in mine if m.value > 0]
            status = "không đạt" if fails else ("đạt" if mine else "không có dữ liệu")
        elif not mine:
            status, fails = "không có dữ liệu", []
        elif rng is None:
            status, fails = "chờ duyệt", []
        else:
            lo, hi = rng
            fails = [m for m in mine if (lo is not None and m.value < lo) or (hi is not None and m.value > hi)]
            status = "không đạt" if fails else "đạt"
        results.append({"id": r.id, "title": r.title, "severity": r.severity, "status": status, "range": rng,
                        "range_status": p.get("status"), "source": r.source, "measure_ids": [m.id for m in mine],
                        "failed": [m.id for m in fails]})
    return {"schema": SCHEMA, "standard": f"{std.name}@{std.version}", "scene_hash": sc.scene_hash,
            "measures": [asdict(m) for m in ms], "results": results}


# ---------------- nhận xét AI ----------------

REVIEW_SYSTEM = (
    "Bạn nhận xét công thái học cho đồ nội thất dựng từ bản vẽ. Làm ba bước trong đầu: (1) ĐO ĐẠC: chỉ đọc bảng số đo "
    "đã cho, không tự đo hay ước lượng; (2) ĐÁNH GIÁ: viết nhận xét tác động tới người dùng, đề xuất sửa, câu hỏi cần "
    "làm rõ; (3) PHẢN BIỆN: xoá mục không trỏ được tới mã số đo (m1, m2…), số trong lời văn phải đúng số đo được trỏ, không "
    "kết luận đạt/không đạt khi tiêu chí 'chờ duyệt' (chưa có khoảng có nguồn). Trả đúng JSON lược đồ "
    'cg.ergonomics-review/1: {"items": [{"criterion": "ER-xx", "measure_ids": ["m1"], "refs": ["<handle>"], '
    '"finding": "...", "impact": "...", "suggestion": "...", "severity": "info|warn|error", "confidence": '
    '"low|medium|high"}], "questions": ["..."], "summary": "..."}. Tiếng Việt.')


def review_prompt(result: dict, context: dict | None = None) -> dict:
    return {"system": REVIEW_SYSTEM, "context": context or {}, "results": result["results"], "measures": result["measures"]}


_NUM = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w])")


def _numbers(text: str) -> list[float]:
    t = re.sub(r"\b(?:ER|m|M)[-_.]?\d+(?:\.F\d+)?\b", " ", text or "")
    out = []
    for n in _NUM.findall(t):
        try:
            out.append(float(n.replace(",", ".")))
        except ValueError:
            pass
    return out


def validate_review(review, result: dict) -> dict:
    """Harness tất định: trả {schema, items (đã qua), rejected [{item, reason}], questions, summary}."""
    if isinstance(review, str):
        mt = re.search(r"\{.*\}", review, re.S)
        try:
            review = json.loads(mt.group(0)) if mt else {}
        except ValueError:
            review = {}
    if not isinstance(review, dict):
        review = {}
    by_id = {m["id"]: m for m in result["measures"]}
    crits = {r["id"]: r for r in result["results"]}
    kept, rejected = [], []
    for it in (review.get("items") or [])[:100]:
        if not isinstance(it, dict):
            continue
        reason = None
        crit = it.get("criterion")
        mids = [m for m in (it.get("measure_ids") or []) if isinstance(m, str)]
        if crit not in crits:
            reason = "tiêu chí không có trong bảng"
        elif not mids or any(m not in by_id for m in mids):
            reason = "không trỏ tới số đo có thật"
        elif any(by_id[m]["criterion"] != crit for m in mids):
            reason = "số đo không thuộc tiêu chí này"
        elif it.get("severity") not in SEVERITIES or it.get("confidence") not in CONFIDENCE:
            reason = "mức độ hoặc độ tin cậy sai giá trị"
        else:
            allowed = [by_id[m]["value"] for m in mids]
            rng = crits[crit].get("range") or []
            allowed += [v for v in rng if v is not None]
            text = " ".join(str(it.get(k, "")) for k in ("finding", "impact", "suggestion"))
            bad = [n for n in _numbers(text) if n >= 10 and not any(abs(n - a) <= NUM_TOL for a in allowed)]
            if bad:
                reason = f"số trong lời văn không khớp số đo: {', '.join(f'{b:g}' for b in bad[:3])}"
            elif crits[crit]["status"] == "chờ duyệt" and re.search(r"\b(không đạt|đạt chuẩn|vi phạm|sai chuẩn)\b", text, re.I):
                reason = "kết luận đạt/không đạt khi tiêu chí chưa có khoảng được duyệt"
            refs = set(it.get("refs") or [])
            known = {h for m in mids for h in by_id[m]["refs"]}
            if not reason and refs - known:
                reason = "handle không thuộc số đo được trỏ"
        if reason:
            rejected.append({"item": it, "reason": reason})
        else:
            kept.append({k: it.get(k) for k in ("criterion", "measure_ids", "refs", "finding", "impact", "suggestion",
                                                "severity", "confidence")} | {"label": "AI nhận xét"})
    summary = str(review.get("summary") or "")[:2000]
    all_vals = [m["value"] for m in result["measures"]]
    if any(n >= 10 and not any(abs(n - a) <= NUM_TOL for a in all_vals) for n in _numbers(summary)):
        summary = ""  # tóm tắt có số không khớp số đo: bỏ
    questions = [str(q)[:300] for q in (review.get("questions") or [])[:10] if isinstance(q, str)]
    return {"schema": REVIEW_SCHEMA, "scene_hash": result.get("scene_hash"), "items": kept, "rejected": rejected,
            "questions": questions, "summary": summary}


__all__ = ["REVIEW_SCHEMA", "SCHEMA", "Measure", "check", "load_ergonomics", "measures", "review_prompt", "validate_review"]
