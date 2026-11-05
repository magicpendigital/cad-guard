"""Cổng Tailscale cho CHÍNH chủ ứng dụng; giữ nguyên phiên app localhost.

Serve xác thực danh tính; gateway chỉ nhận login được cấu hình và Host/Origin chính xác.
Token app vẫn bắt buộc tại upstream, không chèn/lưu token vào cấu hình hay log.
Chỉ lắng nghe localhost: chương trình khác trên cùng máy thuộc ranh giới tin cậy.
"""
from __future__ import annotations

import argparse
import hmac
import http.client
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

MAX_BODY = 1_000_000


class OwnerProxy(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, origin: str, login: str, upstream: int = 8780, port: int = 8782):
        u = urlsplit(origin)
        if u.scheme != "https" or not u.hostname or not u.hostname.endswith(".ts.net") or u.path not in ("", "/") or u.query or u.fragment or u.username or u.password:
            raise ValueError("Cần origin HTTPS .ts.net chính xác.")
        _ = u.port  # từ chối cổng không hợp lệ
        if not login or "@" not in login or not 1 <= upstream <= 65535:
            raise ValueError("Thiếu tài khoản chủ hoặc cổng ứng dụng không hợp lệ.")
        self.origin = origin.rstrip("/")
        self.host = u.netloc.casefold()
        self.login = login.strip().casefold()
        self.upstream = upstream
        super().__init__(("127.0.0.1", port), Handler)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "cadguard-owner-gateway"
    sys_version = ""

    def log_message(self, *args):
        pass  # URL có thể chứa token phiên

    def error(self, code, message):
        if self.command == "POST" and not getattr(self, "_body_read", False):
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if 0 < n <= MAX_BODY:
                    self.connection.settimeout(.25)
                    self.rfile.read(n)
            except (ValueError, OSError):
                pass
            self._body_read = True
        data = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        for k, v in {"Content-Type": "application/json; charset=utf-8", "Content-Length": str(len(data)),
                     "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
                     "Connection": "close"}.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def do_GET(self):
        self.forward()

    def do_HEAD(self):
        self.forward()

    def do_POST(self):
        self.forward()

    def authorized(self):
        login = self.headers.get("Tailscale-User-Login", "").strip().casefold()
        if not login or not hmac.compare_digest(login.encode(), self.server.login.encode()):
            self.error(403, "Cổng toàn bộ ứng dụng chỉ dành cho tài khoản chủ đã cấu hình.")
            return False
        return True

    def prepare_upstream_headers(self, headers):
        pass

    def prepare_response(self, response):
        return None

    def forward(self):
        upstream = None
        headers_sent = False
        self._body_read = False
        try:
            srv = self.server
            if self.path == "/internal/owner-status" and self.command == "GET" and self.headers.get("Host") == f"127.0.0.1:{srv.server_address[1]}" and not self.headers.get("Tailscale-User-Login") and not self.headers.get("X-Forwarded-For"):
                data = json.dumps({"service": "cadguard-owner-gateway", "pid": os.getpid(), "parent_pid": os.getppid(), "upstream": srv.upstream, "origin": srv.origin}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            if self.headers.get("Host", "").casefold() != srv.host:
                return self.error(403, "Host không được phép.")
            if not self.authorized():
                return
            origin = self.headers.get("Origin")
            if origin is not None and origin != srv.origin:
                return self.error(403, "Nguồn yêu cầu không được phép.")
            if self.headers.get("Transfer-Encoding"):
                return self.error(400, "Không hỗ trợ thân yêu cầu theo chunk.")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.error(400, "Kích thước yêu cầu không hợp lệ.")
            if not 0 <= length <= MAX_BODY:
                return self.error(413, "Yêu cầu quá lớn.")
            raw_target = self.requestline.split()[1]
            if not self.path.startswith("/") or raw_target.startswith("//") or "\r" in self.path or "\n" in self.path:
                return self.error(400, "Đường dẫn không hợp lệ.")
            self.connection.settimeout(30)
            self._body_read = True
            body = self.rfile.read(length) if length else None
            if length and len(body) != length:
                return self.error(400, "Thân yêu cầu chưa đầy đủ.")
            headers = {"Host": f"127.0.0.1:{srv.upstream}", "Connection": "close"}
            for name in ("Content-Type", "X-CadGuard-Token", "Accept"):
                value = self.headers.get(name)
                if value is not None:
                    headers[name] = value
            self.prepare_upstream_headers(headers)
            if origin is not None:
                headers["Origin"] = f"http://127.0.0.1:{srv.upstream}"
            if body is not None:
                headers["Content-Length"] = str(len(body))
            upstream = http.client.HTTPConnection("127.0.0.1", srv.upstream, timeout=300)
            upstream.request(self.command, self.path, body=body, headers=headers)
            response = upstream.getresponse()
            payload = self.prepare_response(response)
            self.send_response(response.status)
            allowed = {"content-type", "content-length", "cache-control", "content-security-policy", "x-content-type-options",
                       "referrer-policy", "x-frame-options", "cross-origin-opener-policy", "cross-origin-resource-policy", "content-disposition"}
            for name, value in response.getheaders():
                if name.lower() in allowed and not (payload is not None and name.lower() == "content-length"):
                    self.send_header(name, value)
            if payload is not None:
                self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            headers_sent = True
            if self.command != "HEAD" and payload is not None:
                self.wfile.write(payload)
            elif self.command != "HEAD":
                while data := response.read1(64 * 1024):
                    self.wfile.write(data)
                    self.wfile.flush()  # chat NDJSON chuyển ngay, không đợi hết lượt LLM
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except (OSError, http.client.HTTPException):
            if not headers_sent:
                self.error(502, "Không kết nối được ứng dụng CAD Guard.")
            # Sau khi đã gửi header không gửi thêm phản hồi vào giữa stream.
        finally:
            if upstream is not None:
                upstream.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--origin", required=True)
    p.add_argument("--login", required=True)
    p.add_argument("--upstream", type=int, default=8780)
    p.add_argument("--port", type=int, default=8782)
    args = p.parse_args()
    server = OwnerProxy(args.origin, args.login, args.upstream, args.port)
    print("Cổng ứng dụng riêng: " + server.origin, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
