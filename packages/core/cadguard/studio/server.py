"""Máy chủ HTTP cục bộ cho studio (thư viện chuẩn, chỉ nghe 127.0.0.1).

Bảo vệ: (1) chỉ nhận Host là localhost/127.0.0.1; (2) mọi yêu cầu API cần mã `X-CG-Token` (hoặc `?t=`) sinh ngẫu nhiên khi khởi động,
chỉ có trong URL in ra terminal, để trang web khác trên trình duyệt không gọi được; (3) giới hạn kích thước tệp tải lên.
Khoá API/token của người dùng không bao giờ ghi ra tệp hay log.
"""

from __future__ import annotations

import json
import re
import secrets
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .llm import Backend
from .page import PAGE
from .session import Session

MAX_UPLOAD = 50 * 1024 * 1024
HOST_OK = re.compile(r"^(127\.0\.0\.1|localhost)(:\d+)?$")


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # Windows: SO_REUSEADDR cho phép tiến trình khác bind chồng cổng và nhận yêu cầu

    def __init__(self, port: int, backend: Backend | None, workroot: Path | None = None) -> None:
        super().__init__(("127.0.0.1", port), Handler)
        self.token = secrets.token_urlsafe(24)
        self.backend = backend
        self.workroot = Path(workroot) if workroot else Path(tempfile.mkdtemp(prefix="cadguard-studio-"))
        self.session: Session | None = None
        self.lock = threading.Lock()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/?t={self.token}"


class Handler(BaseHTTPRequestHandler):
    server: StudioServer

    def log_message(self, fmt, *args) -> None:  # không ghi log yêu cầu (có thể chứa mã)
        return

    # ---- tiện ích ---------------------------------------------------------
    def _send(self, code: int, body: bytes, ctype: str = "application/json", extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _err(self, code: int, msg: str) -> None:
        self._json({"error": msg}, code)

    def _authorized(self, query: dict) -> bool:
        if not HOST_OK.match(self.headers.get("Host", "")):
            return False
        tok = self.headers.get("X-CG-Token") or (query.get("t") or [""])[0]
        return secrets.compare_digest(tok, self.server.token)

    def _body(self) -> bytes | None:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_UPLOAD:
            return None
        return self.rfile.read(n)

    # ---- định tuyến -----------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if not self._authorized(q):
            return self._err(403, "Sai mã truy cập hoặc Host")
        s = self.server.session
        if u.path == "/":
            return self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        if u.path == "/api/state":
            return self._json(s.state()) if s else self._err(404, "Chưa mở bản vẽ")
        if u.path == "/api/glb":
            if not s:
                return self._err(404, "Chưa mở bản vẽ")
            return self._send(200, s.glb(), "model/gltf-binary", {"Content-Disposition": "attachment; filename=canh.glb"})
        self._err(404, "Không có")

    def do_POST(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        if not self._authorized(parse_qs(u.query)):
            return self._err(403, "Sai mã truy cập hoặc Host")
        raw = self._body()
        if raw is None:
            return self._err(413, "Tệp quá lớn")
        srv = self.server
        with srv.lock:  # một phiên, xử lý tuần tự
            try:
                if u.path == "/api/open":
                    if not raw[:64].strip():
                        return self._err(400, "Tệp rỗng")
                    try:
                        srv.session = Session(raw, srv.workroot / secrets.token_hex(4), srv.backend)
                    except Exception as exc:  # noqa: BLE001 - tệp hỏng không được làm sập máy chủ
                        return self._err(400, f"Không đọc được DXF: {str(exc)[:200]}")
                    return self._json(srv.session.state())
                s = srv.session
                if s is None:
                    return self._err(404, "Chưa mở bản vẽ")
                data = json.loads(raw.decode("utf-8")) if raw else {}
                if u.path == "/api/consent":
                    s.consent = bool(data.get("value"))
                elif u.path == "/api/analyze":
                    s.ask(None)
                elif u.path == "/api/chat":
                    msg = str(data.get("message", "")).strip()[:4000]
                    if msg:
                        s.ask(msg)
                elif u.path == "/api/values":
                    s.set_values(data.get("values") or {})
                elif u.path == "/api/undo":
                    s.undo()
                elif u.path == "/api/export":
                    return self._json({"path": str(s.export_dxf())})
                else:
                    m = re.match(r"^/api/proposals/(p\d+)/(accept|reject)$", u.path)
                    if not m:
                        return self._err(404, "Không có")
                    (s.accept if m.group(2) == "accept" else s.reject)(m.group(1))
                return self._json(s.state())
            except (json.JSONDecodeError, UnicodeDecodeError):
                return self._err(400, "Nội dung không hợp lệ")


def serve(port: int = 8770, backend: Backend | None = None, open_browser: bool = False) -> None:
    srv = StudioServer(port, backend)
    print(f"cad-guard studio: {srv.url}")
    print(f"LLM: {backend.name if backend else 'chưa có (không có ANTHROPIC_API_KEY, không thấy lệnh claude)'}")
    print("Nhấn Ctrl+C để dừng. Mã truy cập chỉ có trong URL này.")
    if open_browser:
        import webbrowser

        webbrowser.open(srv.url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
