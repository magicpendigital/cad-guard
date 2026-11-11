"""App: hồ sơ trình bày (`cadguard/drafting.py`) — xem, đề xuất bằng code/AI (chạy nền), Đồng ý từng mục, lưu, về mặc định.

AI chỉ chạy khi người dùng bấm và dự án KHÔNG bật ẩn danh. Đề xuất qua harness `drafting.check`; chỉ ghi khi Đồng ý.
"""
from __future__ import annotations

import secrets
import threading
import time
from typing import Any

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def view(app, rel: Any = None) -> dict:
    from .. import drafting

    root = app.ws.root
    prof = drafting.effective(root)
    layers = []
    if isinstance(rel, str) and rel:
        model = app.model(app.resolve(rel))
        d = drafting.read(model, root)
        use = drafting._layer_use(d)
        layers = [{"layer": la, "role": d.roles.get(la, "other"), "lines": u["lines"],
                   "origin": prof["origin"].get(f"layer:{la}", "code")}
                  for la, u in sorted(use.items(), key=lambda kv: -kv[1]["lines"])[:40]]
    return {**prof, "meanings": drafting.MEANINGS, "roles": drafting.ROLE_VI, "layers": layers}


def start(app, rel: Any, use_ai: Any, translate_backend: Any, experimental: bool = False, prefer: Any = None) -> dict:
    from .. import drafting
    from .api import ApiError
    from .graph_api import _backend

    path = app.resolve(rel)
    model = app.model(path)
    root = app.ws.root
    ai, note, backend = use_ai is True, None, None
    if ai and app.anonymize:
        ai, note = False, "Dự án đang bật ẩn danh (NDA): chỉ chạy gợi ý bằng code."
    if ai:
        backend = _backend(app, translate_backend, experimental, prefer if isinstance(prefer, str) else None)
        if backend is None:
            ai, note = False, "Chưa có trợ lý AI dùng được (Kết nối AI): chỉ chạy gợi ý bằng code."
    with _LOCK:
        if any(j["state"] == "running" and j["file"] == app.rel(path) for j in _JOBS.values()):
            raise ApiError("Đang đề xuất hồ sơ trình bày cho bản vẽ này; chờ xong.", 409)
        jid = "dp-" + secrets.token_hex(4)
        job = _JOBS[jid] = {"id": jid, "file": app.rel(path), "state": "running", "ai": ai, "note": note,
                            "started": time.time(), "items": [], "rejected": []}

    def run() -> None:
        try:
            prof = drafting.effective(root)
            r = drafting.propose(drafting.read(model, root), prof, backend)
            job["items"], job["rejected"] = r["items"], r["rejected"]
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


def status(jid: Any) -> dict:
    from .api import ApiError

    job = _JOBS.get(jid) if isinstance(jid, str) else None
    if job is None:
        raise ApiError("Không có lượt đề xuất này (ứng dụng đã khởi động lại?).", 404)
    return dict(job)


def save(app, body: dict) -> dict:
    from .. import drafting
    from .api import ApiError

    scope = body.get("scope")
    try:
        if body.get("reset"):
            drafting.reset(app.ws.root, scope)
        else:
            patch = body.get("patch") if isinstance(body.get("patch"), dict) else {}
            drafting.save(app.ws.root, scope, patch)
    except ValueError as exc:
        raise ApiError(str(exc), 422) from None
    return view(app, body.get("file"))


__all__ = ["save", "start", "status", "view"]
