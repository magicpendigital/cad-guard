"""Truy cập app qua Internet bằng mật khẩu; không phụ thuộc danh tính Tailscale.

Gateway và trang thiết lập dùng hai cổng localhost khác nhau. Chỉ gateway được Funnel proxy.
Mật khẩu không lưu: PBKDF2-HMAC-SHA256, salt ngẫu nhiên, 600k vòng; verifier qua assistant/keys.py.
Cookie opaque Secure/HttpOnly/SameSite=Strict; token chỉ băm trong RAM, hết hạn và logout thu hồi.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import html
import json
import os
import secrets
import threading
import time
from collections import deque
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .remote import OwnerProxy, Handler as ProxyHandler
from ..assistant.keys import get_local_secret, set_local_secret, KeyStoreError

SESSION_COOKIE = "__Host-cg-owner"
CHALLENGE_COOKIE = "__Host-cg-login"
ITERATIONS = 600_000
CSP = "default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"

STYLE = """html{font:16px/1.5 'Segoe UI',system-ui,sans-serif;background:#f6f5f2;color:#1f2421}body{margin:0;padding:24px}main{max-width:440px;margin:8vh auto;background:#fff;padding:28px;border:1px solid #dedad2;border-radius:12px}h1{font-size:24px;margin-top:0}label{display:block;margin:16px 0}input,button{box-sizing:border-box;width:100%;font:inherit;min-height:48px;padding:10px;border:1px solid #c9c4b9;border-radius:7px}button{background:#0f6b62;color:white;font-weight:600;cursor:pointer}.message{color:#8e1b13}.hint{font-size:14px;color:#555c57}a{color:#0f6b62}:focus-visible{outline:3px solid #0f6b62;outline-offset:2px}"""
CONTROLS = """document.addEventListener('DOMContentLoaded',()=>{const header=document.querySelector('.topbar')||document.querySelector('header');if(!header)return;const b=document.createElement('button');b.type='button';b.className='btn-s';b.textContent='Đăng xuất web';b.addEventListener('click',async()=>{const r=await fetch('/auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(r.ok){sessionStorage.removeItem('cg-token');location.replace('/auth/login');}});header.append(b);});"""


def password_hash(password):
    if not isinstance(password, str) or not 14 <= len(password) <= 256:
        raise ValueError("Mật khẩu cần từ 14 đến 256 ký tự; có thể dùng một câu dễ nhớ.")
    salt = secrets.token_bytes(32)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${derived.hex()}"


def check_password(password, encoded):
    try:
        algorithm, rounds, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or not 600_000 <= int(rounds) <= 2_000_000 or len(salt) != 64 or len(expected) != 64:
            return False
        if not isinstance(password,str) or len(password)>256:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError, AttributeError):
        return False


def cookies(header):
    try:
        c = SimpleCookie(); c.load(header or "")
        return {k:v.value for k,v in c.items()}
    except CookieError:
        return {}


class WebAuth:
    def __init__(self, encoded=None, clock=time.monotonic):
        self.encoded = encoded
        self.clock = clock
        self.lock = threading.Lock()
        self.sessions = {}
        self.attempts = {}
        self.global_attempts = deque()
        self.challenge_key = secrets.token_bytes(32)

    def configure(self, encoded):
        with self.lock:
            self.encoded = encoded
            self.sessions.clear()

    def challenge(self):
        value = secrets.token_urlsafe(32) + "." + str(int(self.clock()))
        return value + "." + hmac.new(self.challenge_key,value.encode(),"sha256").hexdigest()

    def valid_challenge(self, field, cookie):
        if not isinstance(field,str) or len(field)>256 or not isinstance(cookie,str) or not hmac.compare_digest(field.encode(),cookie.encode()):
            return False
        try:
            nonce, issued, signature = field.split(".")
            expected = hmac.new(self.challenge_key,f"{nonce}.{issued}".encode(),"sha256").hexdigest()
            return 0 <= self.clock()-int(issued) <= 300 and hmac.compare_digest(signature,expected)
        except (ValueError,TypeError):
            return False

    def login(self, password, address):
        now = self.clock()
        with self.lock:
            while self.global_attempts and self.global_attempts[0] < now-60:
                self.global_attempts.popleft()
            for k in list(self.attempts):
                if not self.attempts[k] or self.attempts[k][-1] < now-60:
                    self.attempts.pop(k)
            if len(self.attempts)>=1024 or len(self.global_attempts)>=30:
                return None,429
            attempts=self.attempts.setdefault(address,deque())
            while attempts and attempts[0]<now-60:
                attempts.popleft()
            if len(attempts)>=5:
                return None,429
            attempts.append(now);self.global_attempts.append(now)
            encoded=self.encoded
        if not encoded:
            return None,503
        if not check_password(password,encoded):
            return None,401
        token=secrets.token_urlsafe(32)
        with self.lock:
            # Mật khẩu đổi khi đang băm: không tạo phiên từ verifier cũ.
            if encoded != self.encoded:
                return None,401
            self._prune(now)
            if len(self.sessions)>=32:
                oldest=min(self.sessions,key=lambda k:self.sessions[k][1]);self.sessions.pop(oldest)
            self.sessions[hashlib.sha256(token.encode()).hexdigest()]=(now,now)
        return token,200

    def _prune(self, now):
        for key,(created,last) in list(self.sessions.items()):
            if now-created>=8*3600 or now-last>=30*60:
                self.sessions.pop(key)

    def valid_session(self, token):
        if not token or len(token)>128:
            return False
        key=hashlib.sha256(token.encode()).hexdigest();now=self.clock()
        with self.lock:
            self._prune(now)
            if key not in self.sessions:
                return False
            created,_=self.sessions[key];self.sessions[key]=(created,now)
            return True

    def logout(self, token):
        if token:
            with self.lock:
                self.sessions.pop(hashlib.sha256(token.encode()).hexdigest(),None)


def page(title, content):
    return f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · CAD Guard</title><link rel="stylesheet" href="/auth/style.css"></head><body><main><h1>{html.escape(title)}</h1>{content}</main></body></html>'.encode("utf-8")


class PasswordProxy(OwnerProxy):
    def __init__(self, origin, app_token, auth, upstream=8780, port=8783):
        if not isinstance(app_token,str) or len(app_token)<32 or not all(c.isalnum() or c in "-_" for c in app_token):
            raise ValueError("Cần mã phiên app hợp lệ trong kho khóa hệ điều hành.")
        self.auth=auth
        self.app_token=app_token
        super().__init__(origin,"password-gateway@local.invalid",upstream,port)
        # OwnerProxy dựng handler mặc định; thay handler trước khi phục vụ.
        self.RequestHandlerClass=WebHandler


class WebHandler(ProxyHandler):
    def output(self, code, data=b"", kind="text/html; charset=utf-8", headers=None):
        if isinstance(data,str):data=data.encode("utf-8")
        self.send_response(code)
        for k,v in {"Content-Type":kind,"Content-Length":str(len(data)),"Cache-Control":"no-store",
                    "Content-Security-Policy":CSP,"X-Content-Type-Options":"nosniff","Referrer-Policy":"same-origin",
                    "X-Frame-Options":"DENY","Cross-Origin-Resource-Policy":"same-origin","Connection":"close"}.items():
            self.send_header(k,v)
        for k,v in (headers or []):self.send_header(k,v)
        self.end_headers()
        if self.command!="HEAD":self.wfile.write(data)

    def login_page(self, message="", code=200):
        challenge=self.server.auth.challenge()
        content='<p class="hint">Truy cập toàn bộ CAD Guard bằng mật khẩu đã thiết lập trên máy chủ.</p>'
        if message:content+=f'<p class="message" role="alert">{html.escape(message)}</p>'
        content+=f'<form method="post" action="/auth/login"><input type="hidden" name="csrf" value="{challenge}"><label>Mật khẩu<input type="password" name="password" autocomplete="current-password" required maxlength="256" autofocus></label><button type="submit">Đăng nhập</button></form><p class="hint">Phiên tự hết hạn sau 30 phút không hoạt động, tối đa 8 giờ.</p>'
        self.output(code,page("Đăng nhập CAD Guard",content),headers=[("Set-Cookie",f"{CHALLENGE_COOKIE}={challenge}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=300")]+([("Retry-After","60")] if code==429 else []))

    def authorized(self):
        cookie=cookies(self.headers.get("Cookie")).get(SESSION_COOKIE)
        if self.server.auth.valid_session(cookie):
            return True
        if self.path.startswith("/api/"):
            self.error(401,"Cần đăng nhập web hoặc phiên đã hết hạn.")
        else:
            self.output(303,headers=[("Location","/auth/login")])
        return False

    def prepare_upstream_headers(self, headers):
        # Browser chỉ dùng marker, mã app thực không xuất hiện trong HTML/JS/URL công khai.
        headers["X-CadGuard-Token"]=self.server.app_token

    def prepare_response(self,response):
        if self.command=="GET" and response.status==200 and response.getheader("Content-Type","").startswith("text/html"):
            data=response.read(1_000_001)
            if len(data)>1_000_000:
                raise OSError("HTML app vượt giới hạn xử lý.")
            return data.replace(b"</head>",b'<script src="/auth/controls.js" defer></script></head>',1)
        return None

    def forward(self):
        srv=self.server
        self._body_read=False
        if self.path=="/internal/web-status" and self.command=="GET" and self.headers.get("Host")==f"127.0.0.1:{srv.server_address[1]}" and not self.headers.get("X-Forwarded-For") and not self.headers.get("Tailscale-User-Login"):
            self.output(200,json.dumps({"service":"cadguard-password-gateway","pid":os.getpid(),"parent_pid":os.getppid(),"origin":srv.origin,"upstream":srv.upstream,"password_ready":bool(srv.auth.encoded)}),"application/json")
            return
        if self.headers.get("Host","").casefold()!=srv.host:
            return self.error(403,"Host không được phép.")
        origin=self.headers.get("Origin")
        if origin is not None and origin!=srv.origin:
            return self.error(403,"Nguồn yêu cầu không được phép.")
        path=urlsplit(self.path).path
        if path=="/auth/style.css" and self.command in ("GET","HEAD"):
            return self.output(200,STYLE,"text/css; charset=utf-8")
        if path=="/auth/login":
            if self.command in ("GET","HEAD"):
                return self.login_page()
            if self.command!="POST" or origin!=srv.origin:
                return self.error(403,"Nguồn đăng nhập không được phép.")
            try:
                if self.headers.get("Transfer-Encoding"):
                    raise ValueError
                n=int(self.headers.get("Content-Length","0"))
                if not 0<n<=4096:raise ValueError
                self.connection.settimeout(10);self._body_read=True
                raw=self.rfile.read(n)
                if len(raw)!=n:raise ValueError
                if self.headers.get("Content-Type","").split(";")[0]!="application/x-www-form-urlencoded":raise ValueError
                fields=parse_qs(raw.decode("utf-8"),max_num_fields=3)
            except (ValueError,UnicodeError,OSError):
                return self.error(400,"Nội dung đăng nhập không hợp lệ.")
            csrf=(fields.get("csrf") or [""])[0]
            if not srv.auth.valid_challenge(csrf,cookies(self.headers.get("Cookie")).get(CHALLENGE_COOKIE,"")):
                return self.error(403,"Trang đăng nhập đã hết hạn; hãy tải lại.")
            address=self.headers.get("X-Forwarded-For",self.client_address[0]).split(",")[0].strip()[:128]
            token,code=srv.auth.login((fields.get("password") or [""])[0],address)
            if code!=200:
                message={401:"Mật khẩu chưa đúng.",429:"Đã thử quá nhiều lần. Vui lòng chờ một phút.",503:"Chưa thiết lập mật khẩu trên máy chủ."}[code]
                return self.login_page(message,code)
            return self.output(303,headers=[("Location","/?t=web-session"),("Set-Cookie",f"{SESSION_COOKIE}={token}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=28800"),("Set-Cookie",f"{CHALLENGE_COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0")])
        if path=="/auth/logout":
            if self.command!="POST" or origin!=srv.origin:
                return self.error(403,"Chỉ đăng xuất bằng yêu cầu cùng nguồn.")
            # Đọc thân nhỏ để Windows không đóng socket bằng RST khi trả phản hồi.
            try:
                n=int(self.headers.get("Content-Length","0"))
                if not 0<=n<=4096:raise ValueError
                self.connection.settimeout(5);self._body_read=True;self.rfile.read(n)
            except (ValueError,OSError):return self.error(400,"Yêu cầu không hợp lệ.")
            srv.auth.logout(cookies(self.headers.get("Cookie")).get(SESSION_COOKIE))
            return self.output(200,'{"ok":true}',"application/json",[("Set-Cookie",f"{SESSION_COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0")])
        if not self.authorized():return
        if path=="/auth/controls.js" and self.command in ("GET","HEAD"):
            return self.output(200,CONTROLS,"text/javascript; charset=utf-8")
        if self.command=="GET" and self.path=="/":
            return self.output(303,headers=[("Location","/?t=web-session")])
        return super().forward()


class SetupServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=False
    def __init__(self, gateway, port=8784, save=None):
        self.gateway=gateway
        self.nonce=secrets.token_urlsafe(32)
        self.lock=threading.Lock()
        self.save=save or (lambda value:set_local_secret("web-password-hash",value))
        super().__init__(("127.0.0.1",port),SetupHandler)


class SetupHandler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def output(self,code,content,kind="text/html; charset=utf-8"):
        if code>=400 and self.command=="POST" and not getattr(self,"_body_read",False):
            try:
                n=int(self.headers.get("Content-Length","0"))
                if 0<n<=4096:
                    self.connection.settimeout(.25);self.rfile.read(n)
            except (ValueError,OSError):pass
            self._body_read=True
        if isinstance(content,str):content=content.encode("utf-8")
        self.send_response(code)
        for k,v in {"Content-Type":kind,"Content-Length":str(len(content)),"Cache-Control":"no-store","Content-Security-Policy":CSP,"X-Frame-Options":"DENY","Referrer-Policy":"same-origin","X-Content-Type-Options":"nosniff","Connection":"close"}.items():self.send_header(k,v)
        self.end_headers();self.wfile.write(content)
    def allowed(self):
        expected=f"127.0.0.1:{self.server.server_address[1]}"
        return self.headers.get("Host")==expected and not self.headers.get("X-Forwarded-For") and self.client_address[0]=="127.0.0.1"
    def do_GET(self):
        if not self.allowed():return self.output(403,"Không được phép.")
        if self.path=="/auth/style.css":return self.output(200,STYLE,"text/css; charset=utf-8")
        if self.path!="/":return self.output(404,"Không có trang này.")
        body=f'<p class="hint">Trang này chỉ mở trên máy chủ. Mật khẩu được lưu dưới dạng mã băm trong kho khóa Windows. Không gửi mật khẩu vào chat.</p><form action="/" method="post"><input type="hidden" name="csrf" value="{self.server.nonce}"><label>Mật khẩu mới (ít nhất 14 ký tự)<input type="password" name="password" minlength="14" maxlength="256" autocomplete="new-password" required></label><label>Nhập lại mật khẩu<input type="password" name="confirm" minlength="14" maxlength="256" autocomplete="new-password" required></label><button>Lưu mật khẩu truy cập web</button></form>'
        self.output(200,page("Thiết lập mật khẩu CAD Guard",body))
    def do_POST(self):
        self._body_read=False
        expected=f"http://127.0.0.1:{self.server.server_address[1]}"
        if not self.allowed() or self.headers.get("Origin")!=expected or self.path!="/":return self.output(403,"Nguồn thiết lập không được phép.")
        try:
            n=int(self.headers.get("Content-Length","0"))
            if self.headers.get("Transfer-Encoding") or not 0<n<=4096:raise ValueError("Yêu cầu không hợp lệ.")
            if self.headers.get("Content-Type","").split(";")[0]!="application/x-www-form-urlencoded":raise ValueError("Chỉ nhận biểu mẫu.")
            self.connection.settimeout(10)
            self._body_read=True
            data=self.rfile.read(n)
            if len(data)!=n:raise ValueError("Thân yêu cầu chưa đầy đủ.")
            fields=parse_qs(data.decode("utf-8"),max_num_fields=3)
            field=lambda name:(fields.get(name) or [""])[0]
            with self.server.lock:
                if not hmac.compare_digest(field("csrf").encode(),self.server.nonce.encode()):raise ValueError("Trang thiết lập hết hạn; tải lại trang.")
                if field("password")!=field("confirm"):raise ValueError("Hai mật khẩu chưa khớp.")
                encoded=password_hash(field("password"))
                self.server.save(encoded)
                self.server.gateway.auth.configure(encoded)
                self.server.nonce=secrets.token_urlsafe(32)
            self.output(200,page("Đã lưu mật khẩu",'<p>Mật khẩu đã được lưu an toàn trong kho khóa Windows.</p><p>Có thể đóng trang này và quay lại chat để tiếp tục bật truy cập web.</p>'))
        except (ValueError,UnicodeError,KeyStoreError) as exc:
            self.output(400,page("Chưa lưu được mật khẩu",f'<p class="message">{html.escape(str(exc))}</p><a href="/">Quay lại thiết lập</a>'))
        except OSError:
            self.output(400,"Chưa nhận đủ yêu cầu; tải lại trang.")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--origin",required=True)
    p.add_argument("--upstream",type=int,default=8780)
    p.add_argument("--port",type=int,default=8783)
    p.add_argument("--setup-port",type=int,default=8784)
    args=p.parse_args()
    app_token=get_local_secret("web-app-token")
    gateway=PasswordProxy(args.origin,app_token,WebAuth(get_local_secret("web-password-hash")),args.upstream,args.port)
    setup=SetupServer(gateway,args.setup_port)
    thread=threading.Thread(target=setup.serve_forever,daemon=True);thread.start()
    print("Thiết lập mật khẩu trên máy chủ: http://127.0.0.1:"+str(args.setup_port),flush=True)
    try:gateway.serve_forever()
    except KeyboardInterrupt:pass
    finally:gateway.server_close();setup.shutdown();setup.server_close()


if __name__=="__main__":main()
