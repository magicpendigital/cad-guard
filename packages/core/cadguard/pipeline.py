"""Bộ chạy luồng xử lý theo hạng mục (`docs/research/kien-truc-agent-workflow.md`): các bước nhỏ có đầu vào/đầu ra rõ,
code chạy trước, AI chỉ nhận phần code chưa giải được (leo thang), mọi kết quả AI qua bộ kiểm và chờ người duyệt.

Bước (`STEPS`) của mỗi hạng mục:
  read → views (ghép hình) → build (dựng khối) → split (chia khối tại vách) → numbers (số còn thiếu) → ai (leo thang,
  chỉ khi còn phần thiếu/đề xuất và người dùng cho dùng AI) → structure (kiểm kết cấu) → review (chờ người duyệt?)

Mỗi lần chạy ghi `cg.pipeline-run/1` vào `.cadguard/runs/<băm tệp 16>/<mã hạng mục>.json` (lịch sử: 20 lần gần nhất), kèm
khoá đầu vào (băm tệp + số người nhập + hồ sơ trình bày + kết cấu xưởng): khoá không đổi thì dùng lại kết quả, không chạy lại.
Không sửa bản vẽ; đề xuất AI lưu ở chỗ đề xuất 3D như "Nhờ AI đọc bản vẽ".
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable

SCHEMA = "cg.pipeline-run/1"
STEPS = [
    ("read", "Đọc bản vẽ theo hồ sơ trình bày", "code"),
    ("views", "Ghép hình (mặt đứng ↔ mặt bằng ↔ mặt cắt)", "code"),
    ("build", "Dựng khối", "code"),
    ("split", "Chia khối tại vách", "code"),
    ("numbers", "Đọc số còn thiếu (sâu, cao, trần)", "code"),
    ("ai", "AI đọc phần code chưa giải được", "ai"),
    ("structure", "Kiểm kết cấu (hồi, nóc, đáy, hậu, vách, đợt, cánh)", "check"),
    ("consistency", "Kiểm nhất quán (giữa các hình, mô hình tủ)", "check"),
    ("review", "Người duyệt", "human"),
]
KEEP = 20


def _h(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:12]


def input_key(model, root: Path, supp: dict, use_ai: bool) -> str:
    from . import construction, drafting

    dp = drafting.effective(root)
    return _h([model.file_hash, supp, dp["layer_roles"], dp["number_tag"], dp["keywords"], construction.effective(root)["values"], use_ai])


def _dir(root: Path, file_hash: str) -> Path:
    return Path(root) / ".cadguard" / "runs" / file_hash[:16]


def _slug(item: str) -> str:
    import re

    return re.sub(r"[^0-9A-Za-z._-]+", "_", item).strip("_")[:40] or "item"


def history(root: Path, file_hash: str, item: str) -> list[dict]:
    p = _dir(root, file_hash) / f"{_slug(item)}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("runs", [])
    except (OSError, ValueError):
        return []


def _save(root: Path, file_hash: str, item: str, run: dict) -> None:
    p = _dir(root, file_hash) / f"{_slug(item)}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    runs = ([run] + history(root, file_hash, item))[:KEEP]
    p.write_text(json.dumps({"schema": SCHEMA, "item": item, "runs": runs}, ensure_ascii=False, indent=1), encoding="utf-8")


def run_item(model, root: Path, item: str, *, backend=None, force: bool = False,
             progress: Callable[[str, str], None] | None = None) -> dict:
    """Chạy luồng cho một hạng mục. `backend`: AI (có `complete`) hoặc None = không dùng AI."""
    from .app import scene_api
    from .scene.annotate import accepted, split_proposals
    from .scene.panels import hinge_sides
    from .scene.proposals import code_suggestions
    from .scene.structure import check as structure_check

    raw_supp = scene_api.read_supplement(root, model.file_hash)
    supp = scene_api.item_supp(raw_supp, item)
    key = input_key(model, root, supp, backend is not None)
    last = history(root, model.file_hash, item)
    if not force and last and last[0].get("key") == key and last[0].get("state") != "error":
        return {**last[0], "cached": True}
    run = {"schema": SCHEMA, "item": item, "key": key, "started": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": [], "state": "running"}
    ctx: dict = {}

    def step(sid: str, fn):
        label, kind = next((lab, k) for s, lab, k in STEPS if s == sid)
        if progress:
            progress(item, sid)
        t0 = time.time()
        try:
            status, summary, out = fn()
        except Exception as exc:  # noqa: BLE001 — một bước lỗi không làm hỏng cả luồng; ghi lại để xem
            status, summary, out = "error", str(exc)[:200], {}
        run["steps"].append({"id": sid, "label": label, "kind": kind, "status": status, "summary": summary, "out": out,
                             "ms": round(1000 * (time.time() - t0))})
        return status

    def s_read():
        sc, d, _ = scene_api.build(model, root, item)
        ctx["sc"], ctx["d"] = sc, d
        return "ok", f"{len(d.views_of(item))} hình của hạng mục", {"views": len(d.views_of(item))}

    def s_views():
        d, sc = ctx["d"], ctx["sc"]
        pl, el = len(d.views_of(item, "plan")), len(d.views_of(item, "elevation"))
        links = len(sc.links)
        st = "ok" if links else ("needs_review" if pl and el else "warn")
        return st, f"{el} mặt đứng, {pl} mặt bằng, {len(d.views_of(item, 'section'))} mặt cắt · ghép được {links}", \
            {"plans": pl, "elevations": el, "links": links}

    def s_build():
        sc = ctx["sc"]
        st = "ok" if sc.modules else "warn"
        return st, f"{len(sc.modules)} khối, {sum(len(m.fronts) for m in sc.modules)} cánh/ngăn kéo", \
            {"modules": len(sc.modules), "fronts": sum(len(m.fronts) for m in sc.modules)}

    def s_split():
        props = split_proposals(ctx["d"], ctx["sc"], accepted(supp, item))
        ctx["split"] = props
        return ("needs_review" if props else "ok"), (f"{len(props)} đề xuất chia khối chờ duyệt" if props else "không cần chia thêm"), \
            {"proposals": len(props), "accepted": len(accepted(supp, item))}

    def s_numbers():
        sc = ctx["sc"]
        sug = code_suggestions(ctx["d"], item, sc)
        ctx["numbers"] = sug
        gaps = [g.id for g in sc.gaps]
        st = "ok" if not gaps else ("needs_review" if sug else "warn")
        return st, (f"{len(gaps)} chỗ thiếu, code gợi ý {len(sug)}" if gaps else "đủ số đo"), {"gaps": len(gaps), "suggestions": len(sug)}

    def s_ai():
        sc = ctx["sc"]
        if backend is None:
            return "skipped", "không dùng AI (bật 'Chạy có AI' nếu cần)", {}
        if not sc.gaps and not ctx.get("split"):
            return "skipped", "code đã giải xong: không cần AI", {}
        from .scene.proposals import _parse, prompt_for

        c = prompt_for(ctx["d"], item, sc)
        system = c.pop("system")
        reply = backend.complete(system, [{"role": "user", "content": json.dumps(c, ensure_ascii=False)}])
        raw = (ctx.get("numbers") or []) + (ctx.get("split") or []) + [{**p, "origin": "llm"} for p in _parse(reply) if isinstance(p, dict)]
        r = scene_api.add_proposals(model, root, item, raw)
        return ("needs_review" if r["accepted"] else "ok"), f"{len(r['accepted'])} đề xuất qua bộ kiểm, {len(r['rejected'])} bị loại", \
            {"accepted": len(r["accepted"]), "rejected": len(r["rejected"])}

    def s_structure():
        from . import construction

        c = construction.effective(root)["values"]
        issues = structure_check(ctx["sc"], c, lambda m: hinge_sides(m.fronts, m.x, m.x + m.w))
        warn = [x for x in issues if x["level"] == "warn"]
        auto = [x for x in issues if x["level"] == "auto"]
        return ("warn" if warn else "ok"), f"{len(auto)} vách tự thêm, {len(warn)} điểm cần xem", {"auto": len(auto), "warn": len(warn)}

    def s_consistency():
        from .scene.consistency import check as consistency_check

        r = consistency_check(ctx["sc"])
        n = r["counts"]
        st = "warn" if n["conflict"] or n["warn"] else "ok"
        return st, f"điểm {r['score']:.2f}: {n['conflict']} mâu thuẫn, {n['warn']} cần xem", {"score": r["score"], **n}

    def s_review():
        need = [s["id"] for s in run["steps"] if s["status"] in ("needs_review", "warn", "error")]
        return ("needs_review" if need else "ok"), ("cần duyệt: " + ", ".join(need)) if need else "không còn việc chờ người", {"steps": need}

    if step("read", s_read) == "error":
        run["state"] = "error"
    else:
        for sid, fn in (("views", s_views), ("build", s_build), ("split", s_split), ("numbers", s_numbers), ("ai", s_ai),
                        ("structure", s_structure), ("consistency", s_consistency), ("review", s_review)):
            step(sid, fn)
        run["state"] = run["steps"][-1]["status"]
    run["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save(root, model.file_hash, item, run)
    return {**run, "cached": False}


def run_all(model, root: Path, *, backend=None, force: bool = False, progress=None) -> dict:
    """Mọi hạng mục có mặt bằng + mặt đứng. Code chạy tuần tự; mỗi hạng mục một bản ghi."""
    from .app import scene_api
    from .scene.assemble import item_summary

    d = scene_api._drawing(model, root)
    items = [x["id"] for x in item_summary(d) if x["plans"] and x["elevations"]]
    rows = [run_item(model, root, g, backend=backend, force=force, progress=progress) for g in items]
    names = {g: str((d.groups.get(g) or {}).get("name") or g) for g in items}
    from .scene.explain import _vi

    for r in rows:
        r["name"] = _vi(names.get(r["item"], r["item"]))
    return {"schema": "cg.pipeline-summary/1", "items": len(rows), "needs_review": sum(1 for r in rows if r["state"] == "needs_review"),
            "rows": rows, "steps": [{"id": s, "label": lab, "kind": k} for s, lab, k in STEPS]}


__all__ = ["SCHEMA", "STEPS", "history", "run_all", "run_item"]
