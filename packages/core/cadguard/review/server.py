"""Cổng rà soát riêng: chỉ localhost, tin proxy Tailscale Serve của máy này.

Không có route mở thư mục, kho khóa, chạy shell hay sửa DXF. Dịch vụ khác trên máy chủ thuộc cùng
ranh giới tin cậy; không bind ra LAN vì header danh tính có thể bị giả khi bỏ qua Serve.
"""
from __future__ import annotations

import io
import hashlib
import os
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .service import ReviewService
from .store import ReviewError, principal

STATIC = Path(__file__).with_name("static")
CSP = "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"


class ReviewServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, service, origin, port=8781):
        service.store.origin(origin)
        self.origin = service.store.origin()
        self.host = urlsplit(self.origin).netloc.casefold()
        self.service = service
        self.csrf = {}
        self.csrf_lock = threading.Lock()
        super().__init__(("127.0.0.1", port), Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, content, kind="application/json; charset=utf-8"):
        if code >= 400 and self.command == "POST" and not getattr(self, "_body_consumed", False):
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if 0 < n <= 1_000_000:
                    previous = self.connection.gettimeout()
                    try:
                        self.connection.settimeout(.25)
                        self.rfile.read(n)
                    finally:
                        self.connection.settimeout(previous)
            except (ValueError, OSError):
                pass
            self._body_consumed = True
        if not isinstance(content, bytes):
            content = json.dumps(content, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        for name, value in {"Content-Type": kind, "Content-Length": str(len(content)), "Cache-Control": "no-store",
                            "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
                            "Content-Security-Policy": CSP, "X-Frame-Options": "DENY"}.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        self.handle_request(False)

    def do_POST(self):
        self.handle_request(True)

    def handle_request(self, post):
        self._body_consumed = False
        try:
            srv = self.server
            if not post and self.path == "/internal/status" and not self.headers.get("Tailscale-User-Login") and not self.headers.get("X-Forwarded-For") and self.client_address[0] == "127.0.0.1" and self.headers.get("Host") == f"127.0.0.1:{srv.server_address[1]}":
                return self.send(200, {"service": "cadguard-review", "pid": os.getpid(), "parent_pid": os.getppid(), "origin": srv.origin,
                                       "workspace_hash": hashlib.sha256(str(srv.service.store.ws.root).encode()).hexdigest()})
            if self.headers.get("Host", "").casefold() != srv.host:
                raise ReviewError("Host không được phép.", 403)
            try:
                actor = principal(self.headers.get("Tailscale-User-Login", ""))
            except ReviewError:
                raise ReviewError("Thiếu danh tính Tailscale hợp lệ.", 403) from None
            srv.service.store.role(actor)
            origin = self.headers.get("Origin")
            if (post and origin != srv.origin) or (origin and origin != srv.origin):
                raise ReviewError("Nguồn yêu cầu không được phép.", 403)
            path = urlsplit(self.path).path
            if not post and path == "/api/review/state":
                with srv.csrf_lock:
                    token = srv.csrf.setdefault(actor, secrets.token_urlsafe(32))
                return self.send(200, dict(srv.service.state(actor), csrf=token))
            if not post and path == "/api/review/qr":
                import qrcode
                out = io.BytesIO()
                qrcode.make(srv.origin).save(out, format="PNG")
                return self.send(200, out.getvalue(), "image/png")
            if not post:
                files = {"/review.css": ("review.css", "text/css"), "/review.js": ("review.js", "text/javascript")}
                if path == "/" or (path.startswith("/r/") and len(path.split("/")) == 3):
                    return self.send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
                if path in files:
                    name, kind = files[path]
                    return self.send(200, (STATIC / name).read_bytes(), kind)
                raise ReviewError("Không có trang này.", 404)
            with srv.csrf_lock:
                expected = srv.csrf.get(actor, "")
            if not expected or not secrets.compare_digest(self.headers.get("X-Review-CSRF", ""), expected):
                raise ReviewError("Thiếu hoặc sai mã bảo vệ yêu cầu.", 403)
            if path != "/api/review/action":
                raise ReviewError("Không có API này.", 404)
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ReviewError("Kích thước yêu cầu sai.") from None
            if not 0 < size <= 1_000_000:
                raise ReviewError("Yêu cầu quá lớn hoặc rỗng.", 413)
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ReviewError("Chỉ nhận JSON.", 415)
            self._body_consumed = True
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ReviewError("Nội dung không hợp lệ.")
            result = srv.service.call(actor, body.pop("action", ""), body)
            return self.send(200, result)
        except ReviewError as exc:
            self.send(exc.status, {"error": str(exc)})
        except (ValueError, TypeError, KeyError):
            self.send(400, {"error": "Nội dung yêu cầu không hợp lệ."})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            self.send(500, {"error": "Không xử lý được hồ sơ; kiểm tra tại máy chủ."})


def run(args):
    service = ReviewService(Path(args.workspace), profile_path=Path(args.profile) if args.profile else None)
    origin = args.public_origin or service.store.origin()
    if not origin:
        raise ReviewError("Cần --public-origin HTTPS Tailscale để chạy cổng khách.")
    server = ReviewServer(service, origin, args.port)
    print("Cổng rà soát: " + server.origin, flush=True)
    print("Chỉ khách đã được cấp quyền và đang bật Tailscale mới truy cập được. Máy chủ phải đang chạy.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
