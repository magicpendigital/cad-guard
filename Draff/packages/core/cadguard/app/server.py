"""Máy chủ HTTP cục bộ của `cadguard app` (chỉ thư viện chuẩn).

An toàn:
- chỉ nghe 127.0.0.1, cổng ngẫu nhiên mặc định;
- mã phiên ngẫu nhiên: mọi `/api/*` cần header `X-CadGuard-Token` khớp (so sánh hằng thời gian);
- `Host` phải là `127.0.0.1:<cổng>` hoặc `localhost:<cổng>` (chống DNS rebinding); `Origin` (nếu có) phải cùng nguồn;
- không CORS; CSP chặt (chỉ tài nguyên của chính máy chủ), `X-Content-Type-Options`, `Referrer-Policy: no-referrer`;
- tệp tĩnh theo danh sách cố định (không nhận đường dẫn tệp từ URL);
- khoá API không bao giờ đi qua HTTP (giao diện chỉ thấy có/chưa).
"""
from __future__ import annotations

import hmac
import json
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

from .. import __version__
from . import api
from .api import ApiError, AppConfig, AppData
from .chat import Assistant

STATIC_DIR = Path(__file__).with_name("static")
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
MAX_BODY = 1_000_000
TOKEN_HEADER = "X-CadGuard-Token"
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; font-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
}


class CadGuardApp:
    """Một phiên ứng dụng: dữ liệu + trợ lý + mã phiên."""

    def __init__(self, config: AppConfig, *, token: str | None = None, **assistant_kwargs):
        self.data = AppData(config)
        self.assistant = Assistant(self.data, **assistant_kwargs)
        self.token = token or secrets.token_urlsafe(32)
        self.port = 0

    def session(self) -> dict:
        prof = self.data.profile
        return {
            "app": "cad-guard", "version": __version__,
            "workspace_name": self.data.ws.root.name,
            "profile": None if prof is None else {"name": prof.name, "version": prof.version, "standard": prof.standard,
                                                  "description": prof.description},
            "anonymize": self.data.config.anonymize,
            "data_mode": "Ẩn danh Bậc 1 (mặc định)" if self.data.config.anonymize else "KHÔNG ẩn danh (--no-anonymize)",
            "flags": {"experimental": self.data.config.experimental, "allow_openrouter": self.data.config.allow_openrouter,
                      "account": self.data.config.account},
            "standards": self.data.standard_names(),
            **self.data.departments,
        }

    # ---------- định tuyến ----------

    def routes(self) -> dict[tuple[str, str], Callable[[dict, dict], Any]]:
        d = self.data
        a = self.assistant

        def q1(q: dict, key: str):
            v = q.get(key)
            return v[0] if v else None

        return {
            ("GET", "/api/session"): lambda q, b: self.session(),
            ("GET", "/api/drawings"): lambda q, b: api.list_drawings(d),
            ("POST", "/api/audit"): lambda q, b: api.audit_file(d, b.get("file"), b.get("standard")),
            ("POST", "/api/audit_all"): lambda q, b: api.audit_all(d, b.get("standard")),
            ("GET", "/api/explain"): lambda q, b: api.explain(d, q1(q, "rule"), q1(q, "standard")),
            ("POST", "/api/summary"): lambda q, b: api.summary(d, b.get("file")),
            ("GET", "/api/rules"): lambda q, b: api.rules_table(d, q1(q, "standard")),
            ("POST", "/api/changeset/suggest"): lambda q, b: api.suggest_ops(d, b.get("file"), b.get("standard")),
            ("POST", "/api/changeset/propose"): lambda q, b: api.propose_changeset(
                d, b.get("file"), b.get("standard"), b.get("ops"), b.get("protected_layers")),
            ("GET", "/api/changeset"): lambda q, b: api.get_changeset(d, q1(q, "id")),
            ("GET", "/api/changesets"): lambda q, b: api.list_changesets(d),
            ("POST", "/api/changeset/apply"): lambda q, b: api.apply_changeset(d, b.get("changeset_id"), b.get("confirm")),
            ("POST", "/api/changeset/undo"): lambda q, b: api.undo_changeset(d, b.get("changeset_id"), b.get("confirm")),
            ("POST", "/api/preview"): lambda q, b: api.preview_2d(d, b.get("file"), b.get("standard")),
            ("POST", "/api/scene"): lambda q, b: api.scene_3d(d, b.get("file"), b.get("supplement"), b.get("views")),
            ("POST", "/api/studio/state"): lambda q, b: api.studio_state(d, b.get("file"), b.get("supplement"), b.get("views")),
            ("GET", "/api/review/notes"): lambda q, b: api.list_review_notes(d, q1(q, "file")),
            ("POST", "/api/review/add"): lambda q, b: api.add_review_note(
                d, b.get("file"), b.get("message"), department=b.get("department"), author=b.get("author"),
                severity=b.get("severity"), rule_id=b.get("rule_id"), handle=b.get("handle"), pos=b.get("pos")),
            ("POST", "/api/review/resolve"): lambda q, b: api.resolve_review_note(d, b.get("id"), b.get("resolved", True)),
            ("POST", "/api/review/handover"): lambda q, b: api.handover_package(
                d, b.get("file"), b.get("standard"), b.get("department")),
            ("POST", "/api/workspace/state"): lambda q, b: api.workspace_state(
                d, b.get("file"), b.get("standard"), b.get("department"), b.get("mode")),
            ("GET", "/api/engines"): lambda q, b: a.engines(refresh=q1(q, "refresh") == "1"),
            ("POST", "/api/chat/stop"): lambda q, b: {"stopped": a.stop(b.get("run_id"))},
        }


def make_handler(app: CadGuardApp):
    routes = app.routes()

    class Handler(BaseHTTPRequestHandler):
        server_version = "cadguard-app"
        sys_version = ""
        protocol_version = "HTTP/1.0"

        def log_message(self, format, *args):  # noqa: A002 — không ghi nhật ký truy cập (URL có thể chứa mã phiên)
            return

        # ----- tiện ích -----

        def _headers(self, status: int, ctype: str, length: int | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            for k, v in SECURITY_HEADERS.items():
                self.send_header(k, v)
            if length is not None:
                self.send_header("Content-Length", str(length))
            self.send_header("Connection", "close")
            self.end_headers()

        def _json(self, status: int, obj: Any) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self._headers(status, "application/json; charset=utf-8", len(body))
            if self.command != "HEAD":
                self.wfile.write(body)

        def _error(self, status: int, message: str) -> None:
            self._json(status, {"error": message})

        def _allowed_hosts(self) -> set[str]:
            port = self.server.server_address[1]
            return {f"127.0.0.1:{port}", f"localhost:{port}"}

        def _host_ok(self) -> bool:
            return (self.headers.get("Host") or "").strip().lower() in self._allowed_hosts()

        def _origin_ok(self) -> bool:
            origin = self.headers.get("Origin")
            if origin is None:
                return True
            return origin.strip().lower() in {f"http://{h}" for h in self._allowed_hosts()}

        def _token_ok(self) -> bool:
            got = self.headers.get(TOKEN_HEADER) or ""
            return hmac.compare_digest(got.encode("utf-8", "replace"), app.token.encode("utf-8"))

        def _body(self) -> dict:
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError("Content-Length sai.") from None
            if n < 0 or n > MAX_BODY:
                raise ApiError("Yêu cầu quá lớn.", 413)
            if n == 0:
                return {}
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if ctype != "application/json":
                raise ApiError("Chỉ nhận JSON (Content-Type: application/json).", 415)
            try:
                data = json.loads(self.rfile.read(n).decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                raise ApiError("JSON không hợp lệ.") from None
            if not isinstance(data, dict):
                raise ApiError("Thân yêu cầu phải là một đối tượng JSON.")
            return data

        # ----- xử lý -----

        def _handle(self, method: str) -> None:
            if not self._host_ok():
                self._error(421, "Host không hợp lệ: chỉ nhận 127.0.0.1 hoặc localhost với đúng cổng của phiên.")
                return
            parts = urlsplit(self.path)
            path = parts.path
            if not path.startswith("/api/"):
                if method in ("GET", "HEAD") and path in STATIC_FILES:
                    name, ctype = STATIC_FILES[path]
                    body = (STATIC_DIR / name).read_bytes()
                    self._headers(200, ctype, len(body))
                    if method != "HEAD":
                        self.wfile.write(body)
                    return
                self._error(404, "Không có trang này.")
                return
            if not self._origin_ok():
                self._error(403, "Nguồn yêu cầu (Origin) không được phép.")
                return
            if not self._token_ok():
                self._error(401, "Thiếu hoặc sai mã phiên. Mở đúng địa chỉ in ra khi chạy `cadguard app`.")
                return
            try:
                body = self._body() if method == "POST" else {}
                if method == "POST" and path == "/api/chat":
                    self._chat(body)
                    return
                if method == "GET" and path == "/api/scene/glb":
                    qs = parse_qs(parts.query)
                    f_arg = qs.get("file", [None])[0]
                    glb = api.scene_glb(app.data, f_arg)
                    self._headers(200, "model/gltf-binary", len(glb))
                    if method != "HEAD":
                        self.wfile.write(glb)
                    return
                fn = routes.get((method, path))
                if fn is None:
                    self._error(404 if not any(p == path for _, p in routes) else 405, "Không có API này.")
                    return
                self._json(200, fn(parse_qs(parts.query), body))
            except ApiError as exc:
                self._error(exc.status, str(exc))
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:  # noqa: BLE001 — không lộ chi tiết nội bộ (đường dẫn) ra trình duyệt
                print("cadguard app: lỗi nội bộ khi xử lý một yêu cầu API.", file=sys.stderr)
                try:
                    self._error(500, "Lỗi nội bộ của cad-guard; xem cửa sổ dòng lệnh.")
                except OSError:
                    pass

        def _chat(self, body: dict) -> None:
            run, meta = app.assistant.start(body)
            self._headers(200, "application/x-ndjson; charset=utf-8")

            def send(obj: dict) -> None:
                self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()

            try:
                send(meta)
                while True:
                    alive, ev = app.assistant.next_event(run)
                    if ev is not None:
                        send(ev)
                    if not alive:
                        break
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                run.cancel.cancel()  # trình duyệt đóng: dừng engine
            finally:
                app.assistant.finish(run)

        def do_GET(self):  # noqa: N802
            self._handle("GET")

        def do_HEAD(self):  # noqa: N802
            self._handle("HEAD")

        def do_POST(self):  # noqa: N802
            self._handle("POST")

        def do_PUT(self):  # noqa: N802
            self._error(405, "Phương thức không được hỗ trợ.")

        do_DELETE = do_PATCH = do_OPTIONS = do_PUT  # không CORS: OPTIONS bị từ chối

    return Handler


class AppServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def create_server(app: CadGuardApp, port: int = 0) -> AppServer:
    """Tạo máy chủ nghe 127.0.0.1 (chưa chạy). `port=0` = cổng ngẫu nhiên."""
    srv = AppServer(("127.0.0.1", int(port)), make_handler(app))
    app.port = srv.server_address[1]
    return srv


def url_of(app: CadGuardApp) -> str:
    return f"http://127.0.0.1:{app.port}/?t={app.token}"


def start_in_thread(app: CadGuardApp, port: int = 0) -> tuple[AppServer, threading.Thread]:
    srv = create_server(app, port)
    t = threading.Thread(target=srv.serve_forever, name="cadguard-app", daemon=True)
    t.start()
    return srv, t


__all__ = ["CSP", "CadGuardApp", "AppServer", "SECURITY_HEADERS", "TOKEN_HEADER", "create_server", "start_in_thread",
           "url_of"]
