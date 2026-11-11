"""App: chạy luồng xử lý cho mọi hạng mục của một bản vẽ (`cadguard/pipeline.py`), xem lịch sử chạy từng bước.

Chạy nền (luồng có thể lâu với tệp lớn hoặc khi có AI). AI chỉ khi người dùng bấm "Chạy có AI" và dự án không bật ẩn danh.
"""
from __future__ import annotations

import secrets
import threading
import time
from typing import Any

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def start(app, rel: Any, use_ai: Any, force: Any, translate_backend: Any, experimental: bool = False, prefer: Any = None) -> dict:
    from .. import pipeline
    from .api import ApiError
    from .graph_api import _backend

    path = app.resolve(rel)
    model = app.model(path)
    root = app.ws.root
    ai, note, backend = use_ai is True, None, None
    if ai and app.anonymize:
        ai, note = False, "Dự án đang bật ẩn danh (NDA): chỉ chạy các bước code."
    if ai:
        backend = _backend(app, translate_backend, experimental, prefer if isinstance(prefer, str) else None)
        if backend is None:
            ai, note = False, "Chưa có trợ lý AI dùng được (Kết nối AI): chỉ chạy các bước code."
    with _LOCK:
        if any(j["state"] == "running" and j["file"] == app.rel(path) for j in _JOBS.values()):
            raise ApiError("Luồng xử lý của bản vẽ này đang chạy; chờ xong.", 409)
        jid = "pl-" + secrets.token_hex(4)
        job = _JOBS[jid] = {"id": jid, "file": app.rel(path), "state": "running", "ai": ai, "note": note, "now": None,
                            "started": time.time()}

    def run() -> None:
        try:
            job["result"] = pipeline.run_all(model, root, backend=backend, force=force is True,
                                             progress=lambda item, sid: job.__setitem__("now", [item, sid]))
            job["state"] = "done"
        except Exception as exc:  # noqa: BLE001
            job["state"] = "error"
            job["error"] = str(exc)[:300]
        job["finished"] = time.time()

    threading.Thread(target=run, name=jid, daemon=True).start()
    return {k: v for k, v in job.items() if k != "result"}


def status(jid: Any) -> dict:
    from .api import ApiError

    job = _JOBS.get(jid) if isinstance(jid, str) else None
    if job is None:
        raise ApiError("Không có lượt chạy này (ứng dụng đã khởi động lại?).", 404)
    return dict(job)


def item_history(app, rel: Any, item: Any) -> dict:
    from .. import pipeline

    model = app.model(app.resolve(rel))
    return {"item": item, "runs": pipeline.history(app.ws.root, model.file_hash, str(item or ""))}


__all__ = ["item_history", "start", "status"]
