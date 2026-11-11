"""Bộ đáp án đo độ chính xác dựng 3D (bước 3 chuẩn hoá): người kỹ thuật ghi kết quả đúng của từng hạng mục, CAD Guard
chấm từng cách đọc (chỉ code / code + gợi ý tự áp / code + AI) để biết cách nào thật sự tốt hơn, bằng số.

- Đáp án `cg.scene-answer/1` lưu trong dự án: `.cadguard/answers/<băm tệp 16>.<mã hạng mục đã làm sạch>.json` (bản vẽ
  thật ngoài repo; đáp án không vào git, không vào telemetry). Tạo từ màn 3D sau khi người kỹ thuật đã sửa mọi số cho đúng
  ("Lưu làm đáp án"): ghi các khối (rộng, sâu, cao, cao độ chân, dạng, số cánh/ngăn kéo) theo thứ tự trái → phải.
- Chấm (`score`): ghép khối dự đoán với khối đáp án theo độ chồng khung (X, Z); một số đo đúng khi lệch ≤ 2 mm; khối đúng
  khi đủ 4 số đúng + đúng dạng + đúng số cánh. Điểm hạng mục = khối đúng / max(số khối đáp án, số khối dự đoán).
- Cách đọc (`PIPELINES`): `code` = bản vẽ + hồ sơ trình bày, không số người nhập; `code+suggest` = tự áp các gợi ý bằng
  code đã qua bộ kiểm (chia khối tại vách, sâu từ mặt cắt); `code+ai` = thêm đề xuất AI đã qua bộ kiểm (cần AI).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

SCHEMA = "cg.scene-answer/1"
DIR = ".cadguard/answers"
TOL = 2.0
DIMS = ("w", "d", "h", "z0")
PIPELINES = ("code", "code+suggest", "code+ai")


def _slug(item: str) -> str:
    return re.sub(r"[^0-9A-Za-z._-]+", "_", item).strip("_")[:40] or "item"


def answer_path(root: Path, file_hash: str, item: str) -> Path:
    return Path(root) / DIR / f"{file_hash[:16]}.{_slug(item)}.json"


def snapshot(sc) -> list[dict]:
    mods = sorted(sc.modules, key=lambda m: (round(m.x), m.z0))
    return [{"x": round(m.x, 1), **{k: round(float(getattr(m, k)), 1) for k in DIMS}, "form": m.form, "fronts": len(m.fronts)}
            for m in mods]


def save_answer(root: Path, model, sc, item_name: str = "", note: str = "", file_rel: str = "") -> dict:
    data = {"schema": SCHEMA, "source_hash": model.file_hash, "file": file_rel, "item": sc.item, "item_name": item_name,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "created_by": "user", "note": str(note)[:300],
            "modules": snapshot(sc)}
    p = answer_path(root, model.file_hash, sc.item)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def load_answers(root: Path) -> list[dict]:
    out = []
    for p in sorted((Path(root) / DIR).glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if d.get("schema") == SCHEMA and d.get("modules"):
            out.append(d)
    return out


def _overlap(a0, a1, b0, b1) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def score(pred: list[dict], ans: list[dict], tol: float = TOL) -> dict:
    """So khối dự đoán với khối đáp án. Gốc X của hai bên có thể khác (đáp án mô phỏng tính từ mép trái hạng mục, bản dựng
    tính từ góc mặt bằng): dời cả hai về mép trái nhỏ nhất trước khi ghép."""
    if pred and ans:
        px, ax = min(p["x"] for p in pred), min(a["x"] for a in ans)
        pred = [{**p, "x": p["x"] - px} for p in pred]
        ans = [{**a, "x": a["x"] - ax} for a in ans]
    pairs, used = [], set()
    for i, a in enumerate(ans):
        best, bj = 0.0, None
        for j, p in enumerate(pred):
            if j in used:
                continue
            ov = _overlap(a["x"], a["x"] + a["w"], p["x"], p["x"] + p["w"]) * _overlap(a["z0"], a["z0"] + a["h"], p["z0"], p["z0"] + p["h"])
            if ov > best:
                best, bj = ov, j
        if bj is not None and best >= 0.3 * a["w"] * a["h"]:
            used.add(bj)
            pairs.append((i, bj))
    dims_ok = {k: 0 for k in DIMS}
    good = 0
    detail = []
    for i, j in pairs:
        a, p = ans[i], pred[j]
        ok = {k: abs(a[k] - p[k]) <= tol for k in DIMS}
        for k in DIMS:
            dims_ok[k] += ok[k]
        full = all(ok.values()) and a.get("form") == p.get("form") and a.get("fronts") == p.get("fronts")
        good += full
        detail.append({"answer": i, "pred": j, "ok": full, "dims": ok, "form": [a.get("form"), p.get("form")],
                       "fronts": [a.get("fronts"), p.get("fronts")]})
    n = max(len(ans), len(pred), 1)
    return {"modules_answer": len(ans), "modules_pred": len(pred), "count_ok": len(ans) == len(pred), "matched": len(pairs),
            "correct": good, "score": round(good / n, 3),
            "dims_pct": {k: round(100 * v / max(len(ans), 1)) for k, v in dims_ok.items()}, "detail": detail}


def _suggest_supp(d, sc, supp: dict, backend=None) -> dict:
    """Áp tự động các đề xuất đã qua bộ kiểm (code; thêm AI nếu có backend). Không ghi tệp nào."""
    from .scene.annotate import accepted, split_proposals
    from .scene.proposals import _parse, code_suggestions, prompt_for, validate

    raw = code_suggestions(d, sc.item, sc) + split_proposals(d, sc, accepted(supp, sc.item))
    if backend is not None:
        ctx = prompt_for(d, sc.item, sc)
        system = ctx.pop("system")
        raw += [{**p, "origin": "llm"} for p in _parse(backend.complete(system, [{"role": "user", "content": json.dumps(ctx, ensure_ascii=False)}]))
                if isinstance(p, dict)]
    ok, _bad = validate(raw, d, sc.item, sc)
    out = dict(supp)
    for p in ok:
        k = p["key"]
        if k.startswith("split:"):
            have = accepted(out, sc.item)
            x = float(p["value"])
            if not any(abs(x - y) <= 25 for y in have):
                out[k] = ";".join(f"{v:.1f}" for v in sorted(have + [x]))
        elif k not in out:
            out[k] = p["value"]
    return out


def run(root: Path, read_model, *, backend=None, pipelines=("code", "code+suggest")) -> dict:
    """Chấm mọi đáp án của dự án. `read_model(file_rel_or_hash) -> model | None`."""
    from . import drafting
    from .scene.assemble import build_item_scene

    rows = []
    for ans in load_answers(root):
        model = read_model(ans)
        if model is None or model.file_hash != ans["source_hash"]:
            rows.append({"item": ans["item"], "item_name": ans.get("item_name", ""), "file": ans.get("file", ""), "skipped": "không tìm thấy đúng tệp bản vẽ (đã sửa sau khi ghi đáp án?)"})
            continue
        d = drafting.read(model, root)
        r = {"item": ans["item"], "item_name": ans.get("item_name", ""), "file": ans.get("file", ""), "scores": {}}
        for pl in pipelines:
            if pl == "code+ai" and backend is None:
                continue
            sc = build_item_scene(d, ans["item"], {})
            if pl != "code":
                sc = build_item_scene(d, ans["item"], _suggest_supp(d, sc, {}, backend if pl == "code+ai" else None))
            r["scores"][pl] = score(snapshot(sc), ans["modules"])
        rows.append(r)
    summary = {}
    for pl in pipelines:
        ss = [r["scores"][pl] for r in rows if "scores" in r and pl in r["scores"]]
        if ss:
            summary[pl] = {"items": len(ss), "score_pct": round(100 * sum(s["score"] for s in ss) / len(ss)),
                           "count_ok_pct": round(100 * sum(s["count_ok"] for s in ss) / len(ss)),
                           "dims_pct": {k: round(sum(s["dims_pct"][k] for s in ss) / len(ss)) for k in DIMS}}
    return {"schema": "cg.bench3d/1", "answers": len(rows), "summary": summary, "rows": rows}


def find_model(root: Path, ans: dict, reader) -> Any:
    """Tìm bản vẽ của đáp án: theo đường dẫn đã ghi, không có thì quét DXF trong dự án theo mã băm."""
    cand = [Path(root) / ans["file"]] if ans.get("file") else []
    cand += sorted(Path(root).glob("**/*.dxf"))[:200]
    for p in cand:
        if p.is_file():
            try:
                m = reader(p)
            except Exception:  # noqa: BLE001
                continue
            if m.file_hash == ans["source_hash"]:
                return m
    return None


__all__ = ["PIPELINES", "SCHEMA", "answer_path", "find_model", "load_answers", "run", "save_answer", "score", "snapshot"]
