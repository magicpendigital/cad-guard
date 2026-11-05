"""Giao diện chung của cổng khách và quản trị cục bộ; Studio tách theo người/phiên."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import tempfile
import threading
import time
from pathlib import Path

from .store import LOCAL, ReviewError, ReviewStore, text
from ..app.preview import sanitize_svg
from ..standard import load_standard, find_standards_dir, load_profile
from ..studio.session import Session
from ..studio.clusters import digest


class ReviewService:
    def __init__(self, root, standards_dir=None, profile_path=None, backend_factory=None):
        self.store = ReviewStore(Path(root))
        self.standards_dir = standards_dir or find_standards_dir()
        self.profile = load_profile(profile_path) if profile_path else None
        self._sessions = {}
        self._lock = threading.Lock()
        self._backend_factory = backend_factory

    def standards(self):
        return [load_standard(name, self.standards_dir, profile=self.profile if self.profile and self.profile.standard == name else None)
                for name in ("furniture-v0", "design-hygiene-v0")]

    def state(self, actor):
        out = self.store.state(actor)
        if actor == LOCAL:
            from ..app.api import AppConfig, AppData, list_drawings
            data = AppData(AppConfig(workspace=self.store.ws.root, standards_dir=self.standards_dir))
            out["drawings"] = list_drawings(data)["drawings"]
            out["members"] = self.store.members()
            out["gateway_running"] = False
            try:
                import http.client
                conn = http.client.HTTPConnection("127.0.0.1", 8781, timeout=.3)
                try:
                    conn.request("GET", "/internal/status")
                    response = conn.getresponse()
                    health = json.loads(response.read())
                    out["gateway_running"] = response.status == 200 and health.get("service") == "cadguard-review" and health.get("workspace_hash") == hashlib.sha256(str(self.store.ws.root).encode()).hexdigest()
                finally:
                    conn.close()
            except (OSError, ValueError, http.client.HTTPException):
                pass
        return out

    def call(self, actor, action, body):
        self.store.role(actor)
        if action == "get":
            p = self.store.get(actor, body.get("id"))
            p["warnings"] = self.store.warnings(p)
            return p
        if action == "view":
            pid, item = body.get("id"), body.get("item")
            svg = self.store.asset(actor, pid, item, "svg").decode("utf-8")
            meta = json.loads(self.store.asset(actor, pid, item, "meta"))
            return {"svg": sanitize_svg(svg), "meta": meta}
        if action == "member":
            return self.store.member(actor, body.get("login"), body.get("role"), body.get("active"))
        if action == "origin":
            if actor != LOCAL:
                raise ReviewError("Chỉ quản trị cục bộ được cấu hình chia sẻ.", 403)
            return {"origin": self.store.origin(body.get("origin"))}
        if action == "publish":
            if actor != LOCAL:
                # Cổng khách không được đọc đường dẫn workspace. Thiết kế công bố từ app cục bộ.
                raise ReviewError("Công bố phiên bản từ ứng dụng cục bộ.", 403)
            return self.store.publish(actor, body, self.standards())
        if action == "qr":
            import io
            import qrcode
            package = self.store.get(actor, body.get("id"))
            origin = self.store.origin()
            if not origin:
                raise ReviewError("Chưa cấu hình địa chỉ Tailscale.", 409)
            out = io.BytesIO()
            qrcode.make(origin + "/r/" + package["id"]).save(out, format="PNG")
            return {"png": base64.b64encode(out.getvalue()).decode("ascii")}
        if action == "export":
            return {"download": base64.b64encode(self.store.export(actor, body.get("id"))).decode("ascii")}
        if action.startswith("agent-"):
            return self.agent(actor, action, body)
        return self.store.mutate(actor, action, body)

    def _context(self, session, note):
        # Đây chính là dữ liệu sắp được gửi, không có tên/đường dẫn máy chủ.
        return {"drawing": digest(session.model, session.scene, session.clusters),
                "note": {"text": note["text"], "anchor": note["anchor"], "replies": note["replies"]}}

    def agent(self, actor, action, body):
        if self.store.role(actor) not in ("owner", "designer"):
            raise ReviewError("Khách/kỹ thuật không được kích hoạt Agent thiết kế.", 403)
        p = self.store.get(actor, body.get("id"))
        if not p["current"]:
            raise ReviewError("Mở phiên bản mới nhất trước khi hỏi Agent.", 409)
        if action == "agent-open":
            note = next((n for n in p["notes"] if n["id"] == body.get("note")), None)
            if not note:
                raise ReviewError("Không có ghi chú này.", 404)
            index = note["anchor"]["item"] if note["anchor"] else body.get("item", 0)
            data = self.store.asset(actor, p["id"], index, "dxf")
            with self._lock:
                for sid in list(self._sessions):
                    if self._sessions[sid]["expires"] < time.monotonic():
                        self._sessions.pop(sid)["temp"].cleanup()
                if len(self._sessions) >= 8:
                    raise ReviewError("Đã đủ 8 phiên Studio; đóng một phiên trước.", 409)
                tmp = tempfile.TemporaryDirectory(prefix="cadguard-review-studio-")
                session = Session(data, Path(tmp.name), None)
                context = self._context(session, note)
                encoded = json.dumps(context, ensure_ascii=False)
                sid = secrets.token_hex(24)
                self._sessions[sid] = {"actor": actor, "package": p["id"], "version": p["version"],
                    "session": session, "context": context, "digest": hashlib.sha256(encoded.encode()).hexdigest(),
                    "temp": tmp, "expires": time.monotonic() + 1800, "lock": threading.Lock()}
            return {"session": sid, "context": context, "context_hash": self._sessions[sid]["digest"],
                    "consent": False, "note": "Chỉ gửi bản tóm tắt và ghi chú hiển thị ở đây; không gửi ảnh hay tệp DXF."}
        with self._lock:
            entry = self._sessions.get(body.get("session"))
        if not entry or entry["actor"] != actor or entry["package"] != p["id"] or entry["expires"] < time.monotonic():
            raise ReviewError("Phiên Studio hết hạn hoặc không thuộc người này.", 403)
        if action == "agent-consent" and body.get("consent") is False:
            entry["session"].consent = False
            return {"consent": False}
        with entry["lock"]:
            if entry["version"] != p["version"]:
                entry["session"].consent = False
                raise ReviewError("Ghi chú/hồ sơ vừa thay đổi: mở phiên mới để xem lại dữ liệu.", 409)
            session = entry["session"]
            if action == "agent-consent":
                if body.get("consent") is not True or body.get("context_hash") != entry["digest"]:
                    raise ReviewError("Hãy xem trước dữ liệu rồi đồng ý cho phiên này.", 409)
                session.consent = True
                return {"consent": True}
            if action != "agent-ask" or not session.consent:
                raise ReviewError("Chưa đồng ý gửi dữ liệu trong phiên Studio này.", 403)
            message = text(body.get("message"))
            if self._backend_factory:
                backend = self._backend_factory()
            else:
                from ..studio.llm import auto_backend
                backend = auto_backend()
            if backend is None:
                raise ReviewError("Chưa có backend Studio; cấu hình khóa hoặc CLI tại máy chủ.", 409)
            # Chỉ gửi đúng context đã được xem trước; không tự gộp lịch sử/ghi chú khác.
            from ..studio.llm import SYSTEM_PROMPT
            try:
                raw = backend.complete(SYSTEM_PROMPT, [{"role": "user", "content": json.dumps(entry["context"], ensure_ascii=False) + "\nCâu hỏi: " + message}])
            except Exception:
                raise ReviewError("Agent chưa trả lời được; thử lại hoặc kiểm tra cấu hình tại máy chủ.", 502) from None
            from ..studio.protocol import parse_reply
            reply, error = parse_reply(raw)
            return {"reply": reply.reply, "error": error,
                    "note": "Đề xuất nội bộ, chưa kiểm tất định. Muốn chia sẻ với khách: xem lại rồi tự gửi thành phản hồi."}
