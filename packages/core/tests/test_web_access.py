"""Đăng nhập web dùng app rỗng và mật khẩu tổng hợp; không chạm kho khóa thật."""
import http.client
import json
import re
import threading
from http.cookies import SimpleCookie
from urllib.parse import urlencode

import pytest
from cadguard.app import AppConfig, CadGuardApp, start_in_thread
from cadguard.app.web_access import (WebAuth, PasswordProxy, SetupServer, password_hash, check_password, SESSION_COOKIE, CHALLENGE_COOKIE)

ORIGIN="https://synthetic.example.ts.net:10000"
PASSWORD="Synthetic-only password 2026!"

@pytest.fixture
def gateway(tmp_path):
    app=CadGuardApp(AppConfig(),settings_path=tmp_path/"config.json",engine_lister=lambda:[],cli_detect=lambda name:{"installed":False})
    upstream,_=start_in_thread(app)
    auth=WebAuth(password_hash(PASSWORD))
    web=PasswordProxy(ORIGIN,app.token,auth,app.port,0)
    thread=threading.Thread(target=web.serve_forever,daemon=True);thread.start()
    yield app,web
    web.shutdown();web.server_close();upstream.shutdown();upstream.server_close()


def request(web,path="/",body=None,cookie="",origin=None,headers=None,method=None):
    conn=http.client.HTTPConnection("127.0.0.1",web.server_address[1],timeout=10)
    h={"Host":"synthetic.example.ts.net:10000","Cookie":cookie}|(headers or {})
    if origin:h["Origin"]=origin
    if body is not None:
        h["Content-Type"]="application/x-www-form-urlencoded";body=urlencode(body)
    conn.request(method or ("POST" if body is not None else "GET"),path,body,h)
    r=conn.getresponse();out=r.status,r.getheaders(),r.read();conn.close();return out


def login(web,password=PASSWORD):
    status,headers,data=request(web,"/auth/login")
    assert status==200
    assert dict(headers)["Referrer-Policy"]=="same-origin"
    cookie=next(v.split(";",1)[0] for k,v in headers if k=="Set-Cookie")
    challenge=re.search(rb'name="csrf" value="([^"]+)"',data).group(1).decode()
    result=request(web,"/auth/login",dict(password=password,csrf=challenge),cookie,ORIGIN)
    return result


def session_cookie(headers):
    return next(v.split(";",1)[0] for k,v in headers if k=="Set-Cookie" and v.startswith(SESSION_COOKIE+"="))


def test_password_hash_and_session_expiry():
    encoded=password_hash(PASSWORD)
    assert PASSWORD not in encoded and check_password(PASSWORD,encoded)
    assert encoded!=password_hash(PASSWORD)
    assert not check_password("wrong",encoded)
    assert not check_password(PASSWORD,"corrupt")
    with pytest.raises(ValueError):password_hash("short")
    clock=[0]
    auth=WebAuth(encoded,clock=lambda:clock[0])
    token,status=auth.login(PASSWORD,"test");assert status==200
    assert token not in auth.sessions and auth.valid_session(token)
    clock[0]=1801;assert not auth.valid_session(token)
    clock[0]=1900;token,_=auth.login(PASSWORD,"test")
    for _ in range(17):clock[0]+=1700;auth.valid_session(token)
    assert not auth.valid_session(token)


def test_unauthenticated_requests_and_old_app_token_are_blocked(gateway):
    app,web=gateway
    assert request(web)[0]==303
    for path in ("/api/session","/api/projects","/app.js","/review.html","/auth/controls.js"):
        assert request(web,path,headers={"X-CadGuard-Token":app.token,"Tailscale-User-Login":"owner@example.test"})[0] in (303,401)
    assert request(web,"/auth/login",headers={"Host":"evil.test"})[0]==403
    assert request(web,"/auth/login",origin="https://evil.test")[0]==403
    assert request(web,"/auth/login",dict(password=PASSWORD,csrf="fake"),origin=ORIGIN)[0]==403


def test_login_cookie_app_compatibility_and_logout(gateway):
    app,web=gateway
    status,headers,data=login(web)
    assert status==303 and data==b""
    value=next(v for k,v in headers if k=="Set-Cookie" and v.startswith(SESSION_COOKIE))
    assert all(flag in value for flag in ("Secure","HttpOnly","SameSite=Strict","Path=/"))
    assert app.token not in str(headers)
    cookie=session_cookie(headers)
    status,_,data=request(web,"/?t=web-session",cookie=cookie)
    assert status==200 and b"/auth/controls.js" in data and app.token.encode() not in data
    status,_,data=request(web,"/api/session",cookie=cookie,origin=ORIGIN,headers={"X-CadGuard-Token":"web-session"})
    assert status==200 and json.loads(data)["project"] is None
    assert request(web,"/api/session",cookie=cookie,origin="https://evil.test")[0]==403
    assert request(web,"/auth/logout",body={},cookie=cookie,origin=ORIGIN)[0]==200
    assert request(web,"/api/session",cookie=cookie)[0]==401


def test_wrong_password_rate_limit_and_password_rotation(gateway):
    _,web=gateway
    for _ in range(5):
        status,_,data=login(web,"wrong")
        assert status==401 and PASSWORD.encode() not in data
    assert login(web,"wrong")[0]==429
    assert len(web.auth.sessions)==0
    auth=WebAuth(password_hash(PASSWORD));token,_=auth.login(PASSWORD,"test")
    auth.configure(password_hash("New synthetic passphrase 2026"))
    assert not auth.valid_session(token)


def test_setup_is_local_only_and_saves_only_verifier(gateway):
    _,web=gateway;saved=[]
    setup=SetupServer(web,0,save=saved.append)
    t=threading.Thread(target=setup.serve_forever,daemon=True);t.start()
    def req(method,path="/",body=None,origin=None,host=None):
        c=http.client.HTTPConnection("127.0.0.1",setup.server_address[1],timeout=5)
        headers={"Host":host or f"127.0.0.1:{setup.server_address[1]}"}
        if origin:headers["Origin"]=origin
        if body is not None:headers["Content-Type"]="application/x-www-form-urlencoded";body=urlencode(body)
        c.request(method,path,body,headers);r=c.getresponse()
        if method=="GET" and r.status==200:
            # Native form POST must retain its Origin; no-referrer makes it null.
            assert r.getheader("Referrer-Policy")=="same-origin"
        result=r.status,r.read();c.close();return result
    try:
        assert req("GET",host="public.example.ts.net")[0]==403
        assert req("GET")[0]==200
        fields=dict(password=PASSWORD,confirm=PASSWORD,csrf=setup.nonce)
        assert req("POST",body=fields)[0]==403
        assert req("POST",body=fields,origin="null")[0]==403
        assert req("POST",body=fields,origin=ORIGIN)[0]==403
        old=setup.nonce
        assert req("POST",body=fields,origin=f"http://127.0.0.1:{setup.server_address[1]}")[0]==200
        assert len(saved)==1 and PASSWORD not in saved[0] and check_password(PASSWORD,saved[0])
        assert setup.nonce!=old
        assert request(web,"/auth/setup")[0]==303
    finally:setup.shutdown();setup.server_close()


def test_local_secret_helpers_do_not_change_provider_keys(monkeypatch):
    from cadguard.assistant import keys
    values={}
    class Fake:
        def get_password(self,service,name):return values.get((service,name))
        def set_password(self,service,name,value):values[(service,name)]=value
    monkeypatch.setattr(keys,"_keyring",lambda:Fake())
    monkeypatch.delenv("CADGUARD_WEB_PASSWORD_HASH",raising=False)
    before=dict(keys.KEY_ENV)
    keys.set_local_secret("web-password-hash","SYN-verifier")
    assert keys.get_local_secret("web-password-hash")=="SYN-verifier" and keys.KEY_ENV==before
    with pytest.raises(keys.KeyStoreError):keys.set_local_secret("other","no")
    monkeypatch.setattr(keys,"_keyring",lambda:None)
    with pytest.raises(keys.KeyStoreError):keys.set_local_secret("web-app-token","synthetic")
