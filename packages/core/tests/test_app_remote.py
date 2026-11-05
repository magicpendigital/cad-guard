"""Cổng toàn bộ app: danh tính Tailscale, token gốc, Host/Origin và proxy cố định."""
import http.client
import json
import threading

import pytest
from cadguard.app import AppConfig, CadGuardApp, start_in_thread
from cadguard.app.remote import OwnerProxy

ORIGIN = "https://synthetic.example.ts.net:10000"
OWNER = "owner@example.test"


@pytest.fixture
def gateway(tmp_path):
    app = CadGuardApp(AppConfig(), settings_path=tmp_path / "settings.json", engine_lister=lambda: [],
                      cli_detect=lambda name: {"installed": False})
    upstream, _ = start_in_thread(app)
    proxy = OwnerProxy(ORIGIN, OWNER, app.port, 0)
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    yield app, proxy
    proxy.shutdown(); proxy.server_close()
    upstream.shutdown(); upstream.server_close()


def req(gateway, path="/", body=None, owner=OWNER, token=None, origin=None, host=None, method=None):
    app, proxy = gateway
    conn = http.client.HTTPConnection("127.0.0.1", proxy.server_address[1], timeout=5)
    headers = {"Host": host or "synthetic.example.ts.net:10000", "Tailscale-User-Login": owner}
    if token is not None:
        headers["X-CadGuard-Token"] = token
    if origin is not None:
        headers["Origin"] = origin
    if body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(body)
    conn.request(method or ("POST" if body is not None else "GET"), path, body, headers)
    response = conn.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    conn.close()
    return result


def test_owner_can_open_same_ui_and_api_keeps_original_token(gateway):
    app, _ = gateway
    assert req(gateway)[0] == 200
    assert req(gateway, "/app.js")[0] == 200
    assert req(gateway, "/api/session")[0] == 401
    assert req(gateway, "/api/session", token="wrong")[0] == 401
    status, headers, data = req(gateway, "/api/session", token=app.token)
    assert status == 200 and json.loads(data)["project"] is None
    assert headers["Referrer-Policy"] == "no-referrer"
    assert "default-src" in headers["Content-Security-Policy"]
    assert req(gateway, "/", method="HEAD")[2] == b""


def test_identity_host_and_origin_are_required(gateway):
    app, _ = gateway
    for actor in ("", "guest@example.test"):
        assert req(gateway, owner=actor, token=app.token)[0] == 403
    assert req(gateway, host="evil.test", token=app.token)[0] == 403
    assert req(gateway, "/api/session", token=app.token, origin="https://evil.test")[0] == 403
    assert req(gateway, "/api/session", token=app.token, origin=ORIGIN)[0] == 200
    assert req(gateway, "/api/project/open", body={"path":"not-an-absolute-path"}, token=app.token, origin=ORIGIN)[0] == 400
    assert req(gateway, "/api/project/open", body={}, token=app.token, origin="https://evil.test")[0] == 403


def test_proxy_is_fixed_and_upstream_offline_is_502(gateway):
    app, proxy = gateway
    assert proxy.server_address[0] == "127.0.0.1"
    assert req(gateway, "//evil.test/", token=app.token)[0] == 400
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        proxy.upstream = sock.getsockname()[1]
    assert req(gateway)[0] == 502
