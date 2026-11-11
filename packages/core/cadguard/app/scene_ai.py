"""App: chuẩn hoá dữ liệu trước khi dựng 3D — gợi ý số còn thiếu bằng code (mặt cắt) và nhờ AI đọc bản vẽ.

- Code luôn chạy (nhanh): chiều sâu thiếu lấy từ kích thước ngang của mặt cắt cùng hạng mục.
- AI chỉ chạy khi người dùng bấm và dự án KHÔNG bật ẩn danh. AI được đọc tiêu đề hình, kích thước, chữ có số của hạng
  mục; mọi số AI đề xuất phải dẫn handle kích thước/chữ có đúng số đó (`scene/proposals.validate`), không thì bị loại.
- Kết quả là đề xuất "chờ xác nhận" ở màn 3D; chỉ khi người dùng bấm Xác nhận mới ghi vào tệp bổ sung.
"""
from __future__ import annotations

import json
import secrets
import threading
import time
from typing import Any

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def start(app, rel: Any, item: Any, use_ai: Any, translate_backend: Any, experimental: bool = False, prefer: Any = None) -> dict:
    from ..scene.proposals import code_suggestions, prompt_for
    from .api import ApiError
    from .graph_api import _backend
    from . import scene_api

    path = app.resolve(rel)
    model = app.model(path)
    root = app.ws.root
    sc, d, _supp = scene_api.build(model, root, item if isinstance(item, str) else None)
    if sc is None:
        raise ApiError("Không có hạng mục để chuẩn hoá.", 422)
    ai, note, backend = use_ai is True, None, None
    if ai and app.anonymize:
        ai, note = False, "Dự án đang bật ẩn danh (NDA): chỉ chạy gợi ý bằng code, không gửi chữ bản vẽ cho AI."
    if ai:
        backend = _backend(app, translate_backend, experimental, prefer if isinstance(prefer, str) else None)
        if backend is None:
            ai, note = False, "Chưa có trợ lý AI dùng được (Kết nối AI): chỉ chạy gợi ý bằng code."
    with _LOCK:
        if any(j["state"] == "running" and j["file"] == app.rel(path) for j in _JOBS.values()):
            raise ApiError("Đang chuẩn hoá bản vẽ này; chờ xong.", 409)
        jid = "sa-" + secrets.token_hex(4)
        job = _JOBS[jid] = {"id": jid, "file": app.rel(path), "item": sc.item, "state": "running", "ai": ai, "note": note,
                            "started": time.time(), "accepted": 0, "rejected": []}

    def run() -> None:
        try:
            from ..scene.annotate import accepted, split_proposals

            raw = code_suggestions(d, sc.item, sc) + split_proposals(d, sc, accepted(_supp, sc.item))
            if ai and backend is not None:
                ctx = prompt_for(d, sc.item, sc)
                system = ctx.pop("system")
                reply = backend.complete(system, [{"role": "user", "content": json.dumps(ctx, ensure_ascii=False)}])
                from ..scene.proposals import _parse

                raw = _merge(raw, [{**p, "origin": "llm"} for p in _parse(reply) if isinstance(p, dict)], sc.item)
            r = scene_api.add_proposals(model, root, sc.item, raw)
            job["accepted"] = len(r["accepted"])
            job["rejected"] = [{"key": x["key"], "why": x.get("rejected")} for x in r["rejected"]][:20]
            job["state"] = "done"
        except Exception as exc:  # noqa: BLE001
            job["state"] = "error"
            job["error"] = str(exc)[:300]
        job["finished"] = time.time()

    if ai:
        threading.Thread(target=run, name=jid, daemon=True).start()
    else:
        run()
    return dict(job)


def _merge(code: list[dict], llm: list[dict], item: str) -> list[dict]:
    """AI đồng ý với đường chia code đã tìm (lệch ≤ 25 mm) -> một đề xuất nguồn "code+llm" kèm lý do của AI."""
    out = list(code)
    for p in llm:
        if p.get("key") == f"split:{item}":
            try:
                x = float(str(p.get("value")))
            except (TypeError, ValueError):
                out.append(p)
                continue
            same = next((c for c in out if c.get("key") == p["key"] and abs(float(c["value"]) - x) <= 25.0), None)
            if same is not None:
                same["origin"] = "code+llm"
                same["reason"] = (same.get("reason", "") + " AI: " + str(p.get("reason", ""))[:200]).strip()
                continue
        out.append(p)
    return out


def status(jid: Any) -> dict:
    from .api import ApiError

    job = _JOBS.get(jid) if isinstance(jid, str) else None
    if job is None:
        raise ApiError("Không có lượt chuẩn hoá này (ứng dụng đã khởi động lại?).", 404)
    return dict(job)


__all__ = ["start", "status"]
