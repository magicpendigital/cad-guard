"""App: đề xuất bổ sung đồ thị bản vẽ (P2) — chạy nền, xem, Đồng ý/Bỏ. Lõi ở `cadguard/graph_ai.py`.

- Gợi ý bằng code luôn chạy. AI chỉ chạy khi người dùng bấm và dự án KHÔNG bật ẩn danh (AI phải đọc chữ của bản vẽ).
- Đề xuất chỉ thành dữ liệu khi người dùng bấm Đồng ý; bản vẽ không bị sửa.
"""
from __future__ import annotations

import secrets
import threading
import time
from typing import Any

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def _backend(app, translate_backend: Any, app_experimental: bool = False, prefer: str | None = None):
    """Cùng cách chọn AI như Dịch: đối tượng có complete() (test) | "none" | "auto"."""
    if translate_backend is not None and not isinstance(translate_backend, str):
        return translate_backend
    if translate_backend == "none":
        return None
    from ..studio.llm import all_backends

    # Codex CLI chỉ khi người dùng đã bật thử nghiệm Codex (như trợ lý chat); một AI hết tín dụng thì sang AI khác.
    return all_backends(allow_codex=bool(app_experimental), prefer=prefer)


def start(app, rel: Any, use_ai: Any, translate_backend: Any, experimental: bool = False, prefer: Any = None) -> dict:
    from .. import graph_ai
    from .api import ApiError
    from . import scene_api

    path = app.resolve(rel)
    model = app.model(path)
    root = app.ws.root
    ai = use_ai is True
    note = None
    backend = None
    if ai and app.anonymize:
        ai, note = False, "Dự án đang bật ẩn danh (NDA): chỉ chạy gợi ý bằng code, không gửi chữ bản vẽ cho AI."
    if ai:
        backend = _backend(app, translate_backend, experimental, prefer if isinstance(prefer, str) else None)
        if backend is None:
            ai, note = False, "Chưa có trợ lý AI dùng được (Kết nối AI): chỉ chạy gợi ý bằng code."
    with _LOCK:
        if any(j["state"] == "running" and j["file"] == app.rel(path) for j in _JOBS.values()):
            raise ApiError("Đang chạy đề xuất cho bản vẽ này; chờ xong.", 409)
        jid = "gs-" + secrets.token_hex(4)
        job = _JOBS[jid] = {"id": jid, "file": app.rel(path), "state": "running", "ai": ai, "note": note,
                            "agent": None, "started": time.time()}

    def run() -> None:
        try:
            from ..scene.views2d import read_drawing

            from ..drafting import read as read_drafting

            d = graph_ai.apply_overrides(read_drafting(model, root), graph_ai.load_overrides(root, model.file_hash))
            supp = scene_api.read_supplement(root, model.file_hash)
            graph_ai.run(d, supp, root, model.file_hash, backend=backend,
                         progress=lambda a: job.__setitem__("agent", a))
            job["state"] = "done"
        except Exception as exc:  # noqa: BLE001
            job["state"] = "error"
            job["error"] = str(exc)[:300]
        job["finished"] = time.time()

    if ai:
        threading.Thread(target=run, name=jid, daemon=True).start()
    else:
        run()  # chỉ code: nhanh, chạy luôn
    return dict(job)


def status(jid: Any) -> dict:
    from .api import ApiError

    job = _JOBS.get(jid) if isinstance(jid, str) else None
    if job is None:
        raise ApiError("Không có lượt đề xuất này (ứng dụng đã khởi động lại?).", 404)
    return dict(job)


def proposals(app, rel: Any) -> dict:
    from .. import graph_ai

    path = app.resolve(rel)
    model = app.model(path)
    st = graph_ai.load_proposals(app.ws.root, model.file_hash)
    from ..scene.views2d import read_drawing
    from ..scene.explain import _view_vi, _vi

    d = read_drawing(model)
    names = {g: _vi(str(i.get("name") or g)) for g, i in d.groups.items()}
    items = []
    for p in st["items"]:
        q = dict(p)
        t = p["target"]
        q["target_label"] = names.get(t) or (_view_vi(d, t) if d.view(t) else t)
        if p["kind"] == "link_views":
            q["value_label"] = _view_vi(d, p["value"]["plan"])
        items.append(q)
    return {"file": app.rel(path), "items": items, "rejected": st.get("rejected", []), "runs": st.get("runs", []),
            "updated": st.get("updated"),
            "counts": {k: sum(1 for x in st["items"] if x["status"] == k) for k in ("proposed", "confirmed", "dismissed")}}


def decide(app, rel: Any, pid: Any, accept: Any) -> dict:
    from .. import graph_ai
    from .api import ApiError

    if not isinstance(pid, str) or not pid.startswith("p-"):
        raise ApiError("Mã đề xuất không hợp lệ.")
    path = app.resolve(rel)
    try:
        p = graph_ai.decide(app.model(path), app.ws.root, pid, accept is True)
    except graph_ai.GraphAiError as exc:
        raise ApiError(str(exc), 409) from None
    return {"proposal": p}


__all__ = ["decide", "proposals", "start", "status"]
