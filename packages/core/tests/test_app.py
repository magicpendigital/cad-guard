"""Ứng dụng cục bộ `cadguard app`: máy chủ HTTP trong luồng (cổng ngẫu nhiên), DXF tổng hợp, engine GIẢ.

Không gọi mạng ngoài, không chạy mô hình hay CLI thật.
"""
from __future__ import annotations

import http.client
import json
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

import pytest

from cadguard import fixtures
from cadguard.app import AppConfig, CadGuardApp, start_in_thread, url_of
from cadguard.app.server import CSP, STATIC_DIR, TOKEN_HEADER
from cadguard.assistant import Engine, EngineInfo, engine_infos
from cadguard.assistant import events as ev
from cadguard.changeset.diff import sha256_file

@pytest.fixture(autouse=True)
def _private_config_dir(tmp_path, monkeypatch):
    """Cấu hình người dùng của ứng dụng nằm trong thư mục tạm: test không bao giờ đụng %APPDATA% thật."""
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))


REPO = Path(__file__).resolve().parents[3]
STDS = REPO / "standards"
BAD = "hygiene_bad.dxf"
FAKE_KEY = "cgtest-fake-provider-key-0123456789"


# ---------- engine giả ----------

FAKE_INFO = EngineInfo("fake-api", "api", "Engine giả (test)", "Điều khoản giả cho test.")
SLOW_INFO = EngineInfo("fake-slow", "cli", "Engine chậm (test)", "Điều khoản giả.")


class FakeEngine(Engine):
    info = FAKE_INFO

    def __init__(self, calls):
        self.calls = calls

    def run(self, messages, *, workspace, standard=None, profile=None, allow_propose=False, compare_without_profile=False,
            server_options=None, cancel=None):
        self.calls.append({"messages": messages, "workspace": str(workspace), "standard": standard,
                           "allow_propose": allow_propose, "server_options": server_options, "profile": profile})
        yield ev.text("Đang kiểm. ")
        yield ev.Event("tool_call", {"id": "t1", "name": "audit", "arguments": {"file": "F_0123456789"}})
        yield ev.Event("tool_result", {"id": "t1", "name": "audit", "content": '{"counts": {"E": 0}}', "is_error": False})
        yield ev.usage(ev.Usage(input_tokens=120, output_tokens=30, cost_usd=0.0012, cost_estimated=True))
        yield ev.done("Bản vẽ không có lỗi E.")


class SlowEngine(Engine):
    info = SLOW_INFO

    def run(self, messages, *, workspace, cancel=None, **kw):
        yield ev.text("Bắt đầu…")
        for _ in range(200):  # tối đa ~10 giây nếu không ai bấm Dừng
            if cancel is not None and cancel.cancelled:
                yield ev.error("Đã huỷ theo yêu cầu.", "cancelled")
                yield ev.done("")
                return
            time.sleep(0.05)
        yield ev.done("Hết giờ (không bị dừng).")


def make_app(ws: Path, *, calls=None, profile=None, lister=None, anonymize=True) -> CadGuardApp:
    calls = calls if calls is not None else []

    def factory(name, **kw):
        if name == "fake-api":
            return FakeEngine(calls)
        if name == "fake-slow":
            return SlowEngine()
        raise AssertionError("engine thật không được tạo trong test")

    cfg = AppConfig(workspace=ws, profile_path=profile, standards_dir=STDS, anonymize=anonymize)
    return CadGuardApp(cfg, engine_factory=factory, engine_lister=lister or (lambda: [FAKE_INFO, SLOW_INFO]),
                       cli_detect=lambda name: {"installed": True, "version": "1.0", "logged_in": True})


class Client:
    def __init__(self, app: CadGuardApp):
        self.app = app
        self.port = app.port

    def raw(self, method, path, body=None, *, token=True, host=None, headers=None, timeout=60):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        h = {"Host": host if host is not None else f"127.0.0.1:{self.port}"}
        if token:
            h[TOKEN_HEADER] = self.app.token if token is True else token
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        conn.request(method, path, body=data, headers=h)
        return conn, conn.getresponse()

    def call(self, method, path, body=None, **kw):
        conn, resp = self.raw(method, path, body, **kw)
        try:
            data = resp.read()
            return resp.status, dict(resp.getheaders()), json.loads(data.decode("utf-8")) if data else None
        finally:
            conn.close()

    def get(self, path, **params):
        return self.call("GET", path + ("?" + urlencode(params) if params else ""))

    def post(self, path, body=None, **kw):
        return self.call("POST", path, body if body is not None else {}, **kw)


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    fixtures.make_all(root)  # bản sao DXF tổng hợp trong thư mục tạm
    return root


@pytest.fixture
def served(ws):
    calls: list = []
    app = make_app(ws, calls=calls)
    srv, _t = start_in_thread(app)
    client = Client(app)
    client.calls = calls
    yield client
    srv.shutdown()
    srv.server_close()


# ---------- an toàn ----------

def test_listens_on_localhost_random_port_and_url_has_token(served):
    app = served.app
    assert app.port > 0
    assert url_of(app) == f"http://127.0.0.1:{app.port}/?t={app.token}"
    assert len(app.token) >= 32


def test_rejects_missing_or_wrong_token(served):
    status, _h, body = served.call("GET", "/api/session", token=False)
    assert status == 401 and "mã phiên" in body["error"]
    status, _h, _b = served.call("GET", "/api/session", token="sai-ma-phien")
    assert status == 401
    status, _h, body = served.call("GET", "/api/session")
    assert status == 200 and body["anonymize"] is True


def test_rejects_wrong_host_and_foreign_origin(served):
    for host in ("evil.example:80", f"attacker.test:{served.port}", "127.0.0.1:1", ""):
        status, _h, _b = served.call("GET", "/api/session", host=host)
        assert status == 421, host
    status, _h, _b = served.call("GET", "/", token=False, host="rebind.example")
    assert status == 421
    status, _h, _b = served.call("GET", "/api/session", host=f"localhost:{served.port}")
    assert status == 200
    status, _h, _b = served.call("POST", "/api/audit_all", {"standard": "furniture-v0"},
                                 headers={"Origin": "http://evil.example"})
    assert status == 403


def test_no_cors_and_security_headers(served):
    status, h, _b = served.call("OPTIONS", "/api/session", headers={"Origin": "http://evil.example"})
    assert status == 405
    assert not any(k.lower().startswith("access-control-") for k in h)
    for path in ("/", "/app.js", "/app.css"):
        conn, resp = served.raw("GET", path, token=False)
        resp.read()
        conn.close()
        hdr = {k.lower(): v for k, v in resp.getheaders()}
        assert resp.status == 200
        assert hdr["content-security-policy"] == CSP
        assert "default-src 'none'" in CSP and "connect-src 'self'" in CSP
        assert hdr["x-content-type-options"] == "nosniff"
        assert hdr["referrer-policy"] == "no-referrer"
    status, h, _ = served.get("/api/session")
    hdr = {k.lower(): v for k, v in h.items()}
    assert hdr["content-security-policy"] == CSP and hdr["x-content-type-options"] == "nosniff"
    assert not any(k.startswith("access-control-") for k in hdr)


def test_static_files_have_no_external_urls_and_no_unsafe_html():
    for name in ("index.html", "app.css", "app.js"):
        text = (STATIC_DIR / name).read_text(encoding="utf-8")
        assert not re.search(r"https?://", text), name
        assert "//cdn" not in text and "@import" not in text
        assert not text.startswith("\ufeff")
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert "innerHTML" not in js and "insertAdjacentHTML" not in js and "eval(" not in js
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert " style=" not in html and "<script>" not in html  # CSP chặn kiểu/mã nội tuyến
    assert 'lang="vi"' in html and "Luật áp dụng" in html


def test_unknown_static_path_and_traversal_not_served(served):
    for path in ("/../api.py", "/static/app.js", "/%2e%2e/server.py", "/departments.json"):
        conn, resp = served.raw("GET", path, token=False)
        body = resp.read()
        conn.close()
        assert resp.status == 404, path
        assert b"import" not in body


@pytest.mark.parametrize("bad", ["../outside.dxf", "..\\outside.dxf", "sub/../../x.dxf", "C:/Windows/x.dxf",
                                 "C:\\x.dxf", "/etc/passwd", "\\\\server\\share\\a.dxf", "", "khong-co.dxf"])
def test_paths_outside_or_absolute_are_rejected(served, bad):
    status, _h, body = served.post("/api/audit", {"file": bad, "standard": "furniture-v0"})
    assert status in (400, 403) and "error" in body
    assert ":\\" not in body["error"] and "/tmp" not in body["error"]


def test_absolute_path_inside_workspace_is_still_rejected(served, ws):
    status, _h, _b = served.post("/api/audit", {"file": str(ws / BAD), "standard": "design-hygiene-v0"})
    assert status == 403
    status, _h, _b = served.post("/api/changeset/suggest", {"file": str((ws / BAD).as_posix()), "standard": "design-hygiene-v0"})
    assert status == 403


def test_bad_json_and_unknown_api(served):
    def send(data: bytes, ctype: str):
        conn = http.client.HTTPConnection("127.0.0.1", served.port, timeout=30)
        conn.request("POST", "/api/audit", body=data, headers={"Host": f"127.0.0.1:{served.port}",
                                                              TOKEN_HEADER: served.app.token, "Content-Type": ctype})
        resp = conn.getresponse()
        out = resp.status, json.loads(resp.read().decode("utf-8"))
        conn.close()
        return out

    status, body = send(b"{x}", "application/json")
    assert status == 400 and "JSON" in body["error"]
    status, body = send(b"[1]", "application/json")
    assert status == 400
    status, body = send(b"file=a", "application/x-www-form-urlencoded")
    assert status == 415  # không nhận form (chặn yêu cầu "đơn giản" từ trang khác)
    status, _h, body = served.get("/api/khong-co")
    assert status == 404 and body["error"]


# ---------- dữ liệu ----------

def test_session_departments_and_drawings(served):
    status, _h, s = served.get("/api/session")
    assert status == 200
    names = {d["name"]: d["standards"] for d in s["departments"]}
    assert names == {"Thiết kế": ["design-hygiene-v0"], "Kỹ thuật": ["design-hygiene-v0", "furniture-v0"],
                     "Trình bày hồ sơ": ["sheet-layout-v0"], "Thiết kế 3D": [], "Lập trình sản xuất": ["furniture-v0"]}
    tech = next(d for d in s["departments"] if d["id"] == "ky-thuat")
    assert tech["priority"] is True and tech["next"] == ["thiet-ke-3d", "lap-trinh-san-xuat"] and s["default"] == "ky-thuat"
    assert next(d for d in s["departments"] if d["id"] == "thiet-ke-3d")["view"] == "scene"
    assert s["data_mode"].startswith("Ẩn danh Bậc 1") and s["profile"] is None
    assert "ws" == s["workspace_name"] and ":" not in s["workspace_name"]
    status, _h, d = served.get("/api/drawings")
    paths = {x["path"] for x in d["drawings"]}
    assert BAD in paths and "ok_sheet.dxf" in paths
    assert all(not Path(p).is_absolute() for p in paths)


def test_audit_explain_rules_on_synthetic(served):
    status, _h, a = served.post("/api/audit", {"file": BAD, "standard": "design-hygiene-v0"})
    assert status == 200
    rules = {r["rule_id"] for g in a["groups"] for r in g["rules"]}
    assert {"VS-01", "VS-02", "VS-04", "VS-06", "VS-07"} <= rules
    assert [g["severity"] for g in a["groups"]] == ["E", "W", "I"]
    assert a["counts"]["W"] >= 5 and "VS-01" in a["fixable_rules"] and "VS-05" not in a["fixable_rules"]
    vs01 = next(r for g in a["groups"] for r in g["rules"] if r["rule_id"] == "VS-01")
    assert "SYNX1|SYN-TUONG" in vs01["items"][0]["message"]  # người dùng thấy tên thật (không qua mô hình)

    status, _h, ok = served.post("/api/audit", {"file": "ok_sheet.dxf", "standard": "furniture-v0"})
    assert status == 200 and ok["counts"] == {"E": 0, "W": 0, "I": 0}

    status, _h, x = served.get("/api/explain", rule="VS-01", standard="design-hygiene-v0")
    assert status == 200 and x["id"] == "VS-01" and x["title"] and "merge_layers" in x["fix_ops"]
    status, _h, _x = served.get("/api/explain", rule="KHONG-CO", standard="design-hygiene-v0")
    assert status == 404

    status, _h, r = served.get("/api/rules", standard="design-hygiene-v0")
    assert status == 200 and r["read_only"] is False and r["counts"]["total"] == len(r["rules"]) >= 7
    row = next(x for x in r["rules"] if x["id"] == "VS-02")
    assert row["params_default"] == row["params_effective"] and row["params_changed"] == []

    # Sửa luật trên giao diện, không tài khoản: tắt VS-06 cho dự án -> lần quét sau không còn VS-06.
    status, _h, before = served.post("/api/audit", {"file": "hygiene_bad.dxf", "standard": "design-hygiene-v0"})
    assert status == 200 and any(g_rule == "VS-06" for g_rule in _rule_ids(before))
    status, _h, up = served.post("/api/rules/update", {"standard": "design-hygiene-v0", "rule_id": "VS-06",
                                                       "changes": {"enabled": False, "severity": "I"}})
    assert status == 200 and up["rule"] == {"enabled": False, "severity": "I"}
    assert next(x for x in up["table"]["rules"] if x["id"] == "VS-06")["enabled"] is False
    status, _h, after = served.post("/api/audit", {"file": "hygiene_bad.dxf", "standard": "design-hygiene-v0"})
    assert "VS-06" not in _rule_ids(after)
    status, _h, bad = served.post("/api/rules/update", {"standard": "design-hygiene-v0", "rule_id": "VS-06",
                                                        "changes": {"severity": "X"}})
    assert status == 400
    status, _h, rs = served.post("/api/rules/reset", {"standard": "design-hygiene-v0", "rule_id": "VS-06"})
    assert status == 200 and rs["rule"] == {} and len(rs["table"]["log"]) == 2
    status, _h, again = served.post("/api/audit", {"file": "hygiene_bad.dxf", "standard": "design-hygiene-v0"})
    assert "VS-06" in _rule_ids(again)

    status, _h, s = served.post("/api/summary", {"file": BAD})
    assert status == 200 and s["layer_count"] > 0 and s["file"] == BAD

    status, _h, _ = served.get("/api/rules", standard="../standards/x")
    assert status == 400


def test_audit_all_reports_handoff_readiness(served):
    status, _h, r = served.post("/api/audit_all", {"standard": "furniture-v0"})
    assert status == 200
    by = {x["path"]: x for x in r["results"]}
    assert by["ok_sheet.dxf"]["ok"] is True and r["ready"] >= 1 and r["total"] == len(by)


def test_rules_show_profile_overrides(ws):
    app = make_app(ws, profile=STDS / "company-profile.example.yaml")
    srv, _t = start_in_thread(app)
    try:
        c = Client(app)
        status, _h, r = c.get("/api/rules", standard="design-hygiene-v0")
        assert status == 200 and r["profile"]["name"] == "cong-ty-mau"
        row = next(x for x in r["rules"] if x["id"] == "VS-02")
        assert set(row["params_changed"]) == {"max_text_styles", "max_dim_styles"}
        assert row["params_effective"]["max_text_styles"] == 20 and row["params_default"]["max_text_styles"] != 20
        assert "allowed_layer_patterns" in r["globals_changed"]
        status, _h, f = c.get("/api/rules", standard="furniture-v0")
        assert f["profile"] is None and "không áp" in f["profile_note"]
        status, _h, s = c.get("/api/session")
        assert s["profile"]["name"] == "cong-ty-mau"
    finally:
        srv.shutdown()
        srv.server_close()


# ---------- changeset: đề xuất -> xem trước -> áp dụng (xác nhận) -> hoàn tác ----------

def test_changeset_full_flow_requires_confirmation(served, ws):
    src = ws / BAD
    sha_before = sha256_file(src)
    status, _h, s = served.post("/api/changeset/suggest", {"file": BAD, "standard": "design-hygiene-v0"})
    assert status == 200
    kinds = {o["op"]["op"] for o in s["ops"]}
    assert {"set_bylayer", "replace_text_style", "clear_dim_text_override", "purge_unused"} <= kinds
    assert any(n["rule_id"] == "VS-05" for n in s["notes"])  # không có thao tác cho VS-05
    ops = [o["op"] for o in s["ops"] if o["checked"]]

    status, _h, pv = served.post("/api/changeset/propose", {"file": BAD, "standard": "design-hygiene-v0", "ops": ops})
    assert status == 200 and pv["ok"] is True and pv["rules_regressed"] == 0
    cid = pv["changeset_id"]
    assert re.fullmatch(r"cs-[0-9a-f]{12}", cid)
    assert {"VS-04", "VS-06", "VS-07"} <= set(pv["rules"]["resolved"])
    assert not list(ws.glob("*.cg-*.dxf"))  # xem trước không ghi DXF
    assert sha256_file(src) == sha_before

    for confirm in (None, False, "true", 1):
        body = {"changeset_id": cid} if confirm is None else {"changeset_id": cid, "confirm": confirm}
        status, _h, err = served.post("/api/changeset/apply", body)
        assert status == 409 and "xác nhận" in err["error"]
    assert not list(ws.glob("*.cg-*.dxf"))

    status, _h, cl = served.get("/api/changesets")
    assert cl["changesets"][0]["id"] == cid and cl["changesets"][0]["applied"] is None

    status, _h, res = served.post("/api/changeset/apply", {"changeset_id": cid, "confirm": True})
    assert status == 200, res
    out = ws / res["output"]["path"]
    assert out.is_file() and out.name.startswith("hygiene_bad.cg-") and out != src
    assert sha256_file(src) == sha_before  # tệp gốc không đổi mã băm
    assert res["validation"]["ok"] is True

    status, _h, again = served.post("/api/changeset/apply", {"changeset_id": cid, "confirm": True})
    assert status == 409  # mỗi changeset chỉ áp một lần, không ghi đè

    status, _h, d = served.get("/api/drawings")
    assert any(x["path"] == res["output"]["path"] and x["is_output"] for x in d["drawings"])
    status, _h, one = served.get("/api/changeset", id=cid)
    assert one["applied"]["output"]["path"] == res["output"]["path"]

    status, _h, err = served.post("/api/changeset/undo", {"changeset_id": cid})
    assert status == 409 and out.is_file()
    status, _h, u = served.post("/api/changeset/undo", {"changeset_id": cid, "confirm": True})
    assert status == 200 and u["removed"] == res["output"]["path"]
    assert not out.exists() and sha256_file(src) == sha_before


def test_changeset_rejects_bad_input(served):
    status, _h, e = served.post("/api/changeset/propose", {"file": BAD, "standard": "design-hygiene-v0",
                                                          "ops": [{"op": "delete_entities"}]})
    assert status == 400 and "từ vựng" in e["error"]
    status, _h, e = served.post("/api/changeset/propose", {"file": BAD, "standard": "design-hygiene-v0", "ops": []})
    assert status == 400
    for cid in ("../x", "cs-XYZ", "C:/a.json", "cs-0123456789ab/../../x"):
        status, _h, _e = served.post("/api/changeset/apply", {"changeset_id": cid, "confirm": True})
        assert status == 400, cid
    status, _h, _e = served.get("/api/changeset", id="cs-000000000000")
    assert status == 404


# ---------- trò chuyện ----------

def _stream(client, body):
    conn, resp = client.raw("POST", "/api/chat", body)
    assert resp.status == 200, resp.read()
    assert resp.getheader("Content-Type").startswith("application/x-ndjson")
    return conn, resp


def _lines(resp):
    out = []
    while True:
        line = resp.readline()
        if not line:
            return out
        out.append(json.loads(line.decode("utf-8")))


def test_chat_streams_events_from_fake_engine(served, ws):
    msgs = [{"role": "user", "content": "Bản vẽ có lỗi E nào?"}]
    conn, resp = _stream(served, {"engine": "fake-api", "messages": msgs, "standard": "design-hygiene-v0"})
    events = _lines(resp)
    conn.close()
    types = [e["type"] for e in events]
    assert types[0] == "start" and types[-1] == "summary"
    assert types[1:-1] == ["text", "tool_call", "tool_result", "usage", "done"]
    assert events[0]["mode"] == "api" and events[0]["anonymize"] is True and events[0]["allow_propose"] is False
    assert events[2]["name"] == "audit" and events[4]["usage"]["input_tokens"] == 120
    assert events[5]["text"] == "Bản vẽ không có lỗi E."
    assert events[-1]["usage"]["cost_usd"] == pytest.approx(0.0012)
    call = served.calls[-1]
    assert call["allow_propose"] is False and call["server_options"] == {"anonymize": True}
    assert Path(call["workspace"]) == ws.resolve() and call["standard"] == "design-hygiene-v0"


def test_chat_allow_propose_only_when_switch_on(served):
    base = {"engine": "fake-api", "messages": [{"role": "user", "content": "Đề xuất sửa"}], "standard": "design-hygiene-v0"}
    for flag, expected in ((True, True), ("true", False), (None, False)):
        body = dict(base, allow_propose=flag) if flag is not None else base
        conn, resp = _stream(served, body)
        _lines(resp)
        conn.close()
        assert served.calls[-1]["allow_propose"] is expected


def test_chat_rejects_bad_requests(served):
    msgs = [{"role": "user", "content": "x"}]
    for body in ({"engine": "khong-co", "messages": msgs, "standard": "furniture-v0"},
                 {"engine": "fake-api", "messages": [], "standard": "furniture-v0"},
                 {"engine": "fake-api", "messages": msgs, "standard": "../x"},
                 {"engine": "fake-api", "messages": msgs, "standard": "furniture-v0", "model": "a b; rm"},
                 {"engine": "fake-api", "messages": [{"role": "user", "content": "x" * 20001}], "standard": "furniture-v0"}):
        status, _h, e = served.post("/api/chat", body)
        assert status == 400 and e["error"], body


def test_chat_stop_cancels_running_engine(served):
    conn, resp = _stream(served, {"engine": "fake-slow", "messages": [{"role": "user", "content": "chậm"}],
                                  "standard": "furniture-v0"})
    start = json.loads(resp.readline())
    assert start["type"] == "start"
    first = json.loads(resp.readline())
    assert first["type"] == "text"
    t0 = time.monotonic()
    status, _h, r = served.post("/api/chat/stop", {"run_id": start["run_id"]})
    assert status == 200 and r["stopped"] is True
    rest = _lines(resp)
    conn.close()
    assert time.monotonic() - t0 < 5
    types = [e["type"] for e in rest]
    assert "error" in types and "done" in types and types[-1] == "summary"
    assert rest[-1]["cancelled"] is True
    status, _h, r = served.post("/api/chat/stop", {"run_id": start["run_id"]})
    assert r["stopped"] is False  # lượt đã kết thúc


def test_engines_api_never_returns_keys(ws, monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(var, FAKE_KEY + var)
    monkeypatch.delenv("CADGUARD_OPENAI_MODEL", raising=False)
    app = make_app(ws, lister=engine_infos)
    srv, _t = start_in_thread(app)
    try:
        c = Client(app)
        conn, resp = c.raw("GET", "/api/engines")
        raw = resp.read().decode("utf-8")
        conn.close()
        assert FAKE_KEY not in raw and "cgtest" not in raw
        data = json.loads(raw)
        by = {e["name"]: e for e in data["engines"]}
        assert {g["mode"] for g in data["groups"]} == {"cli", "api"}
        assert by["anthropic"]["available"] is True and "có khoá" in by["anthropic"]["status"]
        assert by["openai"]["needs_model"] is True
        assert by["openrouter"]["available"] is False and "--allow-openrouter" in by["openrouter"]["hint"]
        assert by["codex-cli"]["available"] is False and "--experimental" in by["codex-cli"]["reason"]
        assert by["agy-cli"]["available"] is False and "doanh nghiệp" in by["agy-cli"]["reason"]
        assert by["claude-cli"]["available"] is True and by["claude-cli"]["mode"] == "cli"
        assert by["ollama"]["available"] is True
        for e in data["engines"]:
            assert e["terms"]
        status, _h, s = c.get("/api/session")
        assert FAKE_KEY not in json.dumps(s)
    finally:
        srv.shutdown()
        srv.server_close()


def test_engines_without_key_show_hint(ws, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import cadguard.assistant.keys as keys

    monkeypatch.setattr(keys, "_keyring", lambda: None)
    app = make_app(ws, lister=engine_infos)
    data = app.assistant.engines()
    a = next(e for e in data["engines"] if e["name"] == "anthropic")
    assert a["available"] is False and "cadguard keys set anthropic" in a["hint"]


def test_no_anonymize_flag_is_reported_and_passed(ws):
    calls: list = []
    app = make_app(ws, calls=calls, anonymize=False)
    srv, _t = start_in_thread(app)
    try:
        c = Client(app)
        status, _h, s = c.get("/api/session")
        assert s["anonymize"] is False and "Nội bộ" in s["data_mode"]
        conn, resp = _stream(c, {"engine": "fake-api", "messages": [{"role": "user", "content": "x"}],
                                 "standard": "furniture-v0"})
        _lines(resp)
        conn.close()
        assert calls[-1]["server_options"] == {"anonymize": False}
    finally:
        srv.shutdown()
        srv.server_close()


def test_cli_app_command_registered():
    from cadguard.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["app", "--help"])
    assert exc.value.code == 0


def test_cli_app_rejects_missing_workspace(tmp_path, capsys):
    from cadguard.cli import main

    assert main(["app", "--workspace", str(tmp_path / "khong-co"), "--no-browser"]) == 2
    assert "Thư mục làm việc" in capsys.readouterr().err


# =====================================================================================================================
# Giao diện theo bản mẫu: chọn dự án lúc chạy, lịch sử quét, hình xem trước, bàn giao, kết nối AI (khoá, CLI).
# Không mạng ngoài, không mô hình/CLI thật, kho khoá GIẢ, hộp thoại GIẢ.
# =====================================================================================================================

from cadguard.app import connect as app_connect  # noqa: E402
from cadguard.app import project as app_project  # noqa: E402
from cadguard.app.settings import Settings  # noqa: E402
from cadguard.assistant import keys as keys_mod  # noqa: E402

FAKE_KEY2 = "cgtestkey-0123456789abcdefABCDEF"


class FakeKeyring:
    """Kho khoá giả thay `keyring` (không đụng kho khoá thật của máy)."""

    def __init__(self):
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service, user):
        return self.store.get((service, user))

    def set_password(self, service, user, value):
        self.store[(service, user)] = value

    def delete_password(self, service, user):
        if (service, user) not in self.store:
            raise KeyError(user)
        del self.store[(service, user)]


@pytest.fixture
def fake_keyring(monkeypatch):
    kr = FakeKeyring()
    monkeypatch.setattr(keys_mod, "_keyring", lambda: kr)
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    return kr


def make_app2(ws: Path | None, *, dialog=None, popen=None, which=None, key_opener=None, lister=None, factory_log=None):
    """App có thể mở không dự án; ghi lại tham số tạo engine để kiểm cấu hình hiệu lực."""
    calls: list = []
    log = factory_log if factory_log is not None else []

    def factory(name, **kw):
        log.append((name, kw))
        if name == "fake-api":
            return FakeEngine(calls)
        raise AssertionError("engine thật không được tạo trong test")

    cfg = AppConfig(workspace=ws, standards_dir=STDS)
    return CadGuardApp(cfg, engine_factory=factory, engine_lister=lister or (lambda: [FAKE_INFO, SLOW_INFO]),
                       cli_detect=lambda name: {"installed": True, "version": "9.9", "logged_in": False},
                       dialog=dialog or (lambda kind: {"path": None}), popen=popen, which=which, key_opener=key_opener)


@pytest.fixture
def blank(tmp_path):
    """Ứng dụng mở KHÔNG có --workspace (màn chọn dự án)."""
    picks: list = []
    state = {"next": None}

    def dialog(kind):
        picks.append(kind)
        return {"path": state["next"]}

    app = make_app2(None, dialog=dialog)
    srv, _t = start_in_thread(app)
    c = Client(app)
    c.picks, c.dialog_state = picks, state
    yield c
    srv.shutdown()
    srv.server_close()


def _ws2(tmp_path) -> Path:
    root = tmp_path / "du-an-2"
    (root / "sub").mkdir(parents=True)
    fixtures.make_ok_sheet(root / "sub" / "chi-mot-ban.dxf")
    return root


def test_app_starts_without_workspace_and_requires_project(blank):
    status, _h, s = blank.get("/api/session")
    assert status == 200 and s["project"] is None and s["workspace_name"] is None
    assert {d["id"] for d in s["departments"]} >= {"ky-thuat", "thiet-ke-3d"} and s["dialog_available"] is True
    for path in ("/api/drawings", "/api/home", "/api/overview"):
        status, _h, body = blank.get(path)
        assert status == 409 and "Chưa mở dự án" in body["error"], path
    status, _h, body = blank.post("/api/audit", {"file": BAD, "standard": "furniture-v0"})
    assert status == 409
    status, _h, p = blank.get("/api/projects")
    assert p["recent"] == [] and p["current"] is None


def test_pick_and_open_project_at_runtime_then_switch(blank, ws, tmp_path):
    blank.dialog_state["next"] = str(ws)
    status, _h, r = blank.post("/api/project/pick")
    assert status == 200 and r["path"] == str(ws) and blank.picks == ["folder"]
    status, _h, r = blank.post("/api/project/open", {"path": r["path"]})
    assert status == 200 and r["opened"] is True and r["session"]["project"] == {"name": "ws"}
    status, _h, d = blank.get("/api/drawings")
    assert BAD in {x["path"] for x in d["drawings"]}

    ws2 = _ws2(tmp_path)
    status, _h, r = blank.post("/api/project/open", {"path": str(ws2)})
    assert status == 200 and r["session"]["project"]["name"] == "du-an-2"
    status, _h, d = blank.get("/api/drawings")
    assert [x["path"] for x in d["drawings"]] == ["sub/chi-mot-ban.dxf"]
    # Rào đường dẫn áp cho thư mục MỚI: tệp của dự án cũ không còn với tới (tương đối lẫn tuyệt đối).
    for bad in (f"../ws/{BAD}", str(ws / BAD), BAD):
        status, _h, body = blank.post("/api/audit", {"file": bad, "standard": "furniture-v0"})
        assert status in (400, 403), bad
        assert str(tmp_path) not in body["error"]
    status, _h, a = blank.post("/api/audit", {"file": "sub/chi-mot-ban.dxf", "standard": "furniture-v0"})
    assert status == 200 and a["counts"]["E"] == 0

    status, _h, p = blank.get("/api/projects")
    assert [x["name"] for x in p["recent"]] == ["du-an-2", "ws"] and all(x["exists"] for x in p["recent"])
    assert p["current"] == {"name": "du-an-2"}
    status, _h, f = blank.post("/api/project/forget", {"path": str(ws)})
    assert f["removed"] is True
    status, _h, p = blank.get("/api/projects")
    assert [x["name"] for x in p["recent"]] == ["du-an-2"]


def test_recent_projects_saved_in_user_settings_without_secrets(blank, ws, tmp_path):
    blank.post("/api/project/open", {"path": str(ws)})
    cfg_file = tmp_path / "cfg" / "settings.json"
    data = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert data["schema"] == "cg.app-settings/1" and data["recent_projects"][0]["path"] == str(ws.resolve())
    assert set(data["recent_projects"][0]) == {"path", "opened_at"}
    # Một Settings mới (lần mở ứng dụng sau) đọc lại được danh sách.
    again = Settings(cfg_file)
    assert again.recent()[0]["name"] == "ws"


@pytest.mark.parametrize("bad", ["", "   ", "khong/tuyet/doi", "C:\\khong-co-thu-muc-nay-123", "\0x"])
def test_open_rejects_missing_relative_or_invalid_dirs(blank, bad):
    status, _h, body = blank.post("/api/project/open", {"path": bad})
    assert status == 400 and body["error"]
    status, _h, s = blank.get("/api/session")
    assert s["project"] is None


def test_open_rejects_file_instead_of_dir(blank, ws):
    status, _h, body = blank.post("/api/project/open", {"path": str(ws / BAD)})
    assert status == 400 and "không phải thư mục" in body["error"]


def test_open_drive_root_or_home_needs_confirmation(blank, tmp_path, monkeypatch):
    root = Path(tmp_path.anchor)
    status, _h, r = blank.post("/api/project/open", {"path": str(root)})
    assert status == 200 and r["opened"] is False and r["needs_confirm"] is True and "gốc ổ đĩa" in r["warning"]
    status, _h, s = blank.get("/api/session")
    assert s["project"] is None  # chưa xác nhận thì không mở, không quét

    home = tmp_path / "users" / "me"
    home.mkdir(parents=True)
    monkeypatch.setattr(app_project.Path, "home", classmethod(lambda cls: home))
    for p in (home, tmp_path / "users"):
        status, _h, r = blank.post("/api/project/open", {"path": str(p)})
        assert r["needs_confirm"] is True and "thư mục người dùng" in r["warning"], p
    status, _h, r = blank.post("/api/project/open", {"path": str(home), "confirm": True})
    assert r["opened"] is True and r["session"]["project"]["name"] == "me"
    assert app_project.broad_dir_warning(home / "du-an") is None


def test_dialog_unavailable_and_busy(ws, monkeypatch):
    app = make_app2(None, dialog=lambda kind: {"unavailable": True})
    assert app.pick("folder") == {"unavailable": True}

    def busy(kind):
        raise app_project.DialogBusy("Hộp thoại chọn thư mục đang mở")

    app2 = make_app2(None, dialog=busy)
    with pytest.raises(Exception) as exc:
        app2.pick("folder")
    assert getattr(exc.value, "status", None) == 409


def test_run_dialog_runs_tkinter_in_child_process(monkeypatch, tmp_path):
    seen = {}

    class Done:
        stdout = json.dumps({"path": str(tmp_path)}).encode("utf-8")

    def fake_run(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        return Done()

    monkeypatch.setattr(app_project.subprocess, "run", fake_run)
    assert app_project.run_dialog("folder") == {"path": str(tmp_path)}
    assert seen["cmd"][0] == __import__("sys").executable and seen["cmd"][1] == "-I" and seen["cmd"][-1] == "folder"
    assert "askdirectory" in seen["cmd"][3] and seen["kw"]["timeout"] > 0
    Done.stdout = b'{"unavailable": true}'
    assert app_project.run_dialog("profile") == {"unavailable": True}
    Done.stdout = b'{"path": null}'
    assert app_project.run_dialog("folder") == {"path": None}
    with pytest.raises(ValueError):
        app_project.run_dialog("../evil")


def test_company_profile_is_saved_per_project(blank, ws, tmp_path):
    blank.post("/api/project/open", {"path": str(ws)})
    prof = STDS / "company-profile.example.yaml"
    blank.dialog_state["next"] = str(prof)
    status, _h, r = blank.post("/api/project/profile/pick")
    assert r["path"] == str(prof) and blank.picks[-1] == "profile"
    status, _h, r = blank.post("/api/project/profile", {"path": str(prof)})
    assert status == 200 and r["session"]["profile"]["name"] == "cong-ty-mau"
    # Đổi sang dự án khác: không có hồ sơ; quay lại: hồ sơ tự áp lại.
    ws2 = _ws2(tmp_path)
    status, _h, r = blank.post("/api/project/open", {"path": str(ws2)})
    assert r["session"]["profile"] is None
    status, _h, r = blank.post("/api/project/open", {"path": str(ws)})
    assert r["session"]["profile"]["name"] == "cong-ty-mau"
    status, _h, body = blank.post("/api/project/profile", {"path": str(ws / BAD)})
    assert status == 400 and ".yaml" in body["error"]
    status, _h, r = blank.post("/api/project/profile", {"path": None})
    assert r["session"]["profile"] is None


# ---------- lịch sử quét, hình xem trước, bàn giao, 3D ----------

def test_history_records_hashes_and_counts_not_names(served, ws):
    served.post("/api/audit", {"file": BAD, "standard": "design-hygiene-v0", "dept": "ky-thuat"})
    served.post("/api/audit", {"file": BAD, "standard": "furniture-v0", "dept": "ky-thuat"})
    raw = (ws / ".cadguard" / "history.jsonl").read_text(encoding="utf-8")
    lines = [json.loads(x) for x in raw.splitlines()]
    assert len(lines) == 2 and all(x["event"] == "audit" for x in lines)
    e = lines[0]
    assert re.fullmatch(r"[0-9a-f]{12}", e["file"]) and e["dept"] == "ky-thuat" and e["standard"] == "design-hygiene-v0"
    assert e["counts"]["W"] >= 5 and "VS-01" in e["rules"]
    for forbidden in ("hygiene_bad", str(ws), ws.name, ":\\", "/tmp", "SYN-"):
        assert forbidden not in raw, forbidden
    status, _h, d = served.post("/api/audit", {"file": BAD, "standard": "furniture-v0", "dept": "khong-co-phong"})
    assert status == 400

    status, _h, h = served.get("/api/home", dept="ky-thuat")
    assert status == 200 and h["has_history"] is True
    row = next(x for x in h["drawings"] if x["path"] == BAD)
    assert row["scanned_all"] is True and row["errors"] >= 1 and h["drawings"][0]["path"] == BAD  # vừa quét lên đầu
    assert h["recent"][0]["file"] == BAD and h["recent"][0]["event"] == "audit"  # tên đổi lại chỉ trên máy này
    assert any(r["rule_id"] == "VS-01" for r in h["frequent_rules"])
    assert h["pipe"]["ky-thuat"]["in_progress"] == 1
    status, _h, o = served.get("/api/overview")
    assert o["has_data"] is True and o["files_scanned"] == 1 and o["audits"] == 2 and o["top_rules"]
    assert BAD not in json.dumps(o)


def test_handover_requires_clean_scan_and_sends_nothing(served, ws):
    status, _h, e = served.post("/api/handover", {"file": "hygiene_ok.dxf", "dept": "thiet-ke"})
    assert status == 409 and "quét" in e["error"]
    served.post("/api/audit", {"file": BAD, "standard": "design-hygiene-v0", "dept": "thiet-ke"})
    status, _h, e = served.post("/api/handover", {"file": BAD, "dept": "thiet-ke"})
    assert status in (200, 409)
    served.post("/api/audit", {"file": "hygiene_ok.dxf", "standard": "design-hygiene-v0", "dept": "thiet-ke"})
    status, _h, r = served.post("/api/handover", {"file": "hygiene_ok.dxf", "dept": "thiet-ke"})
    assert status == 200 and r["ready"] is True and r["to"] == ["Kỹ thuật"] and "không gửi" in r["note"]
    status, _h, h = served.get("/api/home", dept="ky-thuat")
    assert [x["file"] for x in h["inbox"]] == ["hygiene_ok.dxf"] and h["inbox"][0]["from"] == "Thiết kế"
    status, _h, h2 = served.get("/api/home", dept="thiet-ke")
    row = next(x for x in h2["drawings"] if x["path"] == "hygiene_ok.dxf")
    assert row["handover"]
    status, _h, _e = served.post("/api/handover", {"file": "../x.dxf", "dept": "thiet-ke"})
    assert status == 403


def test_geometry_locates_finding_handles(served):
    status, _h, g = served.post("/api/geometry", {"file": BAD})
    assert status == 200 and g["drawn"] > 0 and len(g["viewbox"]) == 4
    kinds = {it[1] for it in g["items"]}
    assert kinds & {"L", "P", "Q"}
    handles = {it[0] for it in g["items"]}
    status, _h, a = served.post("/api/audit", {"file": BAD, "standard": "design-hygiene-v0"})
    found = {h for gr in a["groups"] for r in gr["rules"] for it in r["items"] for h in it["handles"]}
    assert found & handles  # ít nhất một phát hiện định vị được trên hình
    for it in g["items"]:
        xs = it[2][0:1]
        assert all(-1e6 < x < 1e6 for x in xs)
    status, _h, _g = served.post("/api/geometry", {"file": "../ws/" + BAD})
    assert status == 403


def test_scene_view_only(served):
    status, _h, s = served.post("/api/scene", {"file": "scene/cabinet_views_ok.dxf"})
    assert status == 200 and s["boxes"] and s["counts"]["modules"] + s["counts"]["panels"] >= 1
    assert "scene/cabinet" not in json.dumps(s["boxes"])


def test_scene2_item_gap_proposal_and_glb(served):
    import base64

    f = "scene/company_kitchen.dxf"
    status, _h, s = served.post("/api/scene", {"file": f, "item": "SYN.10"})
    assert status == 200 and s["schema"] == "cg.scene/2" and s["counts"]["modules"] == 2 and not s["gaps"]
    assert {m["w"]["src"] for m in s["modules"]} == {"kích thước"}
    # đề xuất AI: số đo bị loại, ghép/nhãn hợp lệ được lưu chờ xác nhận
    elev = next(lk["elevation"] for lk in s["links"])
    plan = next(lk["plan"] for lk in s["links"])
    status, _h, p = served.post("/api/scene/propose", {"file": f, "item": "SYN.10", "proposals": [
        {"key": "module:M2:d", "value": "400", "reason": "đoán"},
        {"key": "label:M1", "value": "tủ bếp dưới", "reason": "cao 850, chân ở sàn"},
        {"key": f"link:{elev}", "value": plan}]})
    assert status == 200 and len(p["accepted"]) == 2 and p["rejected"][0]["key"] == "module:M2:d"
    assert {x["key"] for x in p["scene"]["proposals"]} == {"label:M1", f"link:{elev}"}
    status, _h, s2 = served.post("/api/scene/set", {"file": f, "item": "SYN.10", "key": "label:M1", "value": "tủ bếp dưới"})
    assert status == 200 and next(m for m in s2["modules"] if m["id"] == "M1")["label"] == "tủ bếp dưới"
    assert all(x["key"] != "label:M1" for x in s2["proposals"])
    status, _h, bad = served.post("/api/scene/set", {"file": f, "item": "SYN.10", "key": "room:ceiling", "value": "abc"})
    assert status == 422
    status, _h, g = served.post("/api/scene/glb", {"file": f, "item": "SYN.10"})
    blob = base64.b64decode(g["b64"])
    assert status == 200 and blob[:4] == b"glTF" and g["scene_hash"] == s2["scene_hash"]
    assert g["scene_hash"].encode() in blob  # xem trước = xuất: cùng mã cảnh trong GLB
    status, _h, pr = served.post("/api/scene/prompt", {"file": f, "item": "SYN.10"})
    assert status == 200 and "company_kitchen" not in json.dumps(pr) and pr["views"]


def test_drawing_list_is_capped(ws, monkeypatch):
    from cadguard.app import api as app_api

    monkeypatch.setattr(app_api, "MAX_DRAWINGS", 3)
    app = make_app(ws)
    d = app_api.list_drawings(app.data)
    assert len(d["drawings"]) == 3 and d["truncated"] is True and d["limit"] == 3


# ---------- Kết nối AI: khoá ----------

def _raw(client, method, path, body=None):
    conn, resp = client.raw(method, path, body)
    try:
        return resp.status, resp.read().decode("utf-8")
    finally:
        conn.close()


def test_api_key_saved_to_os_keyring_and_never_read_back(fake_keyring, ws, tmp_path):
    app = make_app2(ws, lister=engine_infos)
    srv, _t = start_in_thread(app)
    try:
        c = Client(app)
        status, raw = _raw(c, "POST", "/api/ai/key", {"provider": "anthropic", "key": FAKE_KEY2})
        assert status == 200 and FAKE_KEY2 not in raw
        st = json.loads(raw)
        assert st == {"has_key": True, "source": "keyring", "env_var": "ANTHROPIC_API_KEY"}
        assert fake_keyring.store[("cad-guard", "anthropic")] == FAKE_KEY2
        for path in ("/api/ai/settings", "/api/engines", "/api/session", "/api/projects", "/api/engines?" + "refresh=1"):
            status, raw = _raw(c, "GET", path)
            assert status == 200 and FAKE_KEY2 not in raw and "cgtestkey" not in raw, path
        status, raw = _raw(c, "GET", "/api/ai/settings")
        s = json.loads(raw)
        assert s["keys"]["anthropic"] == {"has_key": True, "source": "keyring", "env_var": "ANTHROPIC_API_KEY"}
        assert s["keyring_available"] is True
        # Không có đường GET nào tới khoá.
        for path in ("/api/ai/key", "/api/ai/key?" + "provider=anthropic", "/api/ai/keys"):
            status, raw = _raw(c, "GET", path)
            assert status in (404, 405) and FAKE_KEY2 not in raw
        # Không ghi khoá vào tệp cấu hình hay lịch sử.
        for p in (tmp_path / "cfg").rglob("*"):
            if p.is_file():
                assert FAKE_KEY2 not in p.read_text(encoding="utf-8", errors="replace")
        for p in (ws / ".cadguard").rglob("*") if (ws / ".cadguard").exists() else []:
            if p.is_file():
                assert FAKE_KEY2 not in p.read_text(encoding="utf-8", errors="replace")
        by = {e["name"]: e for e in c.get("/api/engines")[2]["engines"]}
        assert by["anthropic"]["available"] is True and "kho khoá" in by["anthropic"]["status"]

        status, raw = _raw(c, "POST", "/api/ai/key/delete", {"provider": "anthropic"})
        assert status == 200 and json.loads(raw)["removed"] is True and FAKE_KEY2 not in raw
        assert ("cad-guard", "anthropic") not in fake_keyring.store
    finally:
        srv.shutdown()
        srv.server_close()


def test_api_key_endpoint_validates_input(fake_keyring, served):
    for body in ({"provider": "ollama", "key": FAKE_KEY2}, {"provider": "khong-co", "key": FAKE_KEY2},
                 {"provider": "openai", "key": "co khoang trang 123"}, {"provider": "openai", "key": "ngan"},
                 {"provider": "openai", "key": "x" * 600}, {"provider": "openai"}, {"provider": "openai", "key": 123}):
        status, raw = _raw(served, "POST", "/api/ai/key", body)
        assert status == 400, body
        assert FAKE_KEY2 not in raw
    status, raw = _raw(served, "POST", "/api/ai/key", {"provider": "openai", "key": "k" * 5000})
    assert status == 413 and "k" * 50 not in raw
    conn = http.client.HTTPConnection("127.0.0.1", served.port, timeout=30)
    conn.request("POST", "/api/ai/key", body=f"provider=openai&key={FAKE_KEY2}",
                 headers={"Host": f"127.0.0.1:{served.port}", TOKEN_HEADER: served.app.token,
                          "Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    assert resp.status == 415
    conn.close()
    status, _h, _b = served.call("POST", "/api/ai/key", {"provider": "openai", "key": FAKE_KEY2}, token=False)
    assert status == 401
    status, _h, _b = served.call("POST", "/api/ai/key", {"provider": "openai", "key": FAKE_KEY2},
                                 headers={"Origin": "http://evil.example"})
    assert status == 403
    assert fake_keyring.store == {}


def test_api_key_refused_without_keyring(served, monkeypatch):
    monkeypatch.setattr(keys_mod, "_keyring", lambda: None)
    status, raw = _raw(served, "POST", "/api/ai/key", {"provider": "anthropic", "key": FAKE_KEY2})
    assert status == 501 and "pip install cadguard[keyring]" in raw and FAKE_KEY2 not in raw
    status, _h, s = served.get("/api/ai/settings")
    assert s["keyring_available"] is False


class _Resp:
    def __init__(self, body: bytes):
        self.body = body

    def read(self, n=-1):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_key_check_lists_models_only_when_clicked(fake_keyring, ws):
    seen = []

    def opener(req, timeout=None):
        seen.append((req.full_url, req.get_method(), dict(req.header_items()), req.data))
        return _Resp(b'{"data": [{"id": "m1"}, {"id": "m2"}]}')

    app = make_app2(ws, key_opener=opener)
    srv, _t = start_in_thread(app)
    try:
        c = Client(app)
        status, _h, e = c.post("/api/ai/key/test", {"provider": "anthropic"})
        assert status == 400 and "Chưa có khoá" in e["error"] and not seen
        c.post("/api/ai/key", {"provider": "anthropic", "key": FAKE_KEY2})
        assert not seen  # lưu khoá không tự gọi mạng
        status, raw = _raw(c, "POST", "/api/ai/key/test", {"provider": "anthropic"})
        r = json.loads(raw)
        assert status == 200 and r["ok"] is True and "2 mô hình" in r["message"] and "không tốn token" in r["message"].lower()
        assert FAKE_KEY2 not in raw
        url, method, headers, data = seen[-1]
        assert url == "https://api.anthropic.com/v1/models?" + "limit=1" and method == "GET" and data is None
        assert headers.get("X-api-key") == FAKE_KEY2
        c.post("/api/ai/key", {"provider": "openai", "key": FAKE_KEY2})
        c.post("/api/ai/key/test", {"provider": "openai"})
        assert seen[-1][0] == "https://api.openai.com/v1/models" and seen[-1][1] == "GET"
        status, _h, e = c.post("/api/ai/key/test", {"provider": "openrouter"})
        assert status == 400 and "OpenRouter đang tắt" in e["error"]
        status, _h, r = c.post("/api/ai/key/test", {"provider": "ollama"})
        assert r["ok"] is True and seen[-1][0] == "http://localhost:11434/v1/models"
    finally:
        srv.shutdown()
        srv.server_close()


def test_key_check_reports_rejected_key(fake_keyring, ws):
    import urllib.error

    def opener(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "unauthorized", {}, None)

    fake_keyring.store[("cad-guard", "gemini")] = FAKE_KEY2
    r = app_connect.check_key("gemini", {"allow_openrouter": False, "ollama_base_url": "http://localhost:11434/v1"},
                              opener=opener)
    assert r["ok"] is False and "401" in r["message"] and FAKE_KEY2 not in r["message"]


# ---------- Kết nối AI: CLI ----------

def test_cli_login_opens_new_terminal_with_official_command(ws):
    launched = []
    app = make_app2(ws, popen=lambda cmd, **kw: launched.append((cmd, kw)), which=lambda name: f"/opt/bin/{name}")
    srv, _t = start_in_thread(app)
    try:
        c = Client(app)
        status, _h, r = c.post("/api/ai/cli/login", {"engine": "claude-cli"})
        assert status == 200 and r["opened"] is True and r["command"] == "claude auth login"
        status, _h, r = c.post("/api/ai/cli/login", {"engine": "codex-cli"})
        assert r["command"] == "codex login"
        cmds = [cmd for cmd, _kw in launched]
        assert all(cmd[-2:] == ["auth", "login"] or cmd[-1] == "login" for cmd in cmds)
        for cmd, kw in launched:
            assert "stdout" not in kw or kw["stdout"] is not __import__("subprocess").PIPE  # không đọc đầu ra
        status, _h, e = c.post("/api/ai/cli/login", {"engine": "agy-cli"})
        assert status == 400 and "doanh nghiệp" in e["error"] and len(launched) == 2
        c.post("/api/ai/settings", {"agy_account": "business"})
        status, _h, r = c.post("/api/ai/cli/login", {"engine": "agy-cli"})
        assert status == 200 and r["command"] == "agy"
        for bad in ("anthropic", "khong-co", None):
            status, _h, _e = c.post("/api/ai/cli/login", {"engine": bad})
            assert status == 400
    finally:
        srv.shutdown()
        srv.server_close()


def test_cli_login_not_installed_shows_install_text_only(ws):
    launched = []
    app = make_app2(ws, popen=lambda cmd, **kw: launched.append(cmd), which=lambda name: None)
    srv, _t = start_in_thread(app)
    try:
        status, _h, e = Client(app).post("/api/ai/cli/login", {"engine": "claude-cli"})
        assert status == 400 and "Chưa cài" in e["error"] and "code.claude.com" in e["error"] and not launched
        assert "http" not in e["error"]  # chỉ chữ, không link tải
    finally:
        srv.shutdown()
        srv.server_close()


def test_terminal_argv_per_platform():
    cmd, kw = app_connect.terminal_argv(["claude", "auth", "login"], platform="win32")
    assert cmd == ["cmd.exe", "/k", "claude", "auth", "login"] and kw["creationflags"]
    cmd, kw = app_connect.terminal_argv(["codex", "login"], platform="darwin")
    assert cmd[0] == "osascript" and "codex login" in cmd[2] and kw["stdout"] is not None
    cmd, _kw = app_connect.terminal_argv(["agy"], platform="linux", which=lambda n: "/usr/bin/" + n if n == "xterm" else None)
    assert cmd == ["xterm", "-e", "agy"]
    with pytest.raises(app_connect.ConnectError):
        app_connect.terminal_argv(["agy"], platform="linux", which=lambda n: None)


# ---------- Kết nối AI: cấu hình ----------

def test_ai_settings_drive_engines_and_chat(ws, monkeypatch):
    monkeypatch.delenv("CADGUARD_OPENAI_MODEL", raising=False)
    log: list = []
    app = make_app2(ws, lister=lambda: [FAKE_INFO, *engine_infos()], factory_log=log)
    app.assistant.cli_detect = lambda name: {"installed": True, "version": "1.0", "logged_in": True}
    srv, _t = start_in_thread(app)
    try:
        c = Client(app)
        by = {e["name"]: e for e in c.get("/api/engines")[2]["engines"]}
        assert by["codex-cli"]["available"] is False and by["agy-cli"]["available"] is False
        assert by["openrouter"]["available"] is False
        status, _h, s = c.post("/api/ai/settings", {"codex_experimental": True, "agy_account": "business",
                                                    "max_cost_usd": 1.5, "default_engine": "fake-api",
                                                    "models": {"fake-api": "mo-hinh-1", "openai": "gpt-x"}})
        assert status == 200 and s["models"]["fake-api"] == "mo-hinh-1" and s["max_cost_usd"] == 1.5
        by = {e["name"]: e for e in c.get("/api/engines")[2]["engines"]}
        assert by["codex-cli"]["available"] is True and by["agy-cli"]["available"] is True
        assert by["openai"]["model"] == "gpt-x" and by["openai"]["needs_model"] is False
        assert c.get("/api/engines")[2]["default_engine"] == "fake-api"

        conn, resp = _stream(c, {"engine": "fake-api", "messages": [{"role": "user", "content": "x"}],
                                 "standard": "furniture-v0"})
        events = _lines(resp)
        conn.close()
        name, kw = log[-1]
        assert name == "fake-api" and kw["model"] == "mo-hinh-1" and kw["experimental"] is True and kw["account"] == "business"
        assert events[0]["type"] == "start"
        # Engine API thật nhận trần chi phí và địa chỉ Ollama từ cấu hình.
        app.assistant.engine_factory = lambda n, **kw: log.append((n, kw)) or FakeEngine([])
        for eng in ("anthropic", "ollama"):
            conn, resp = _stream(c, {"engine": eng, "messages": [{"role": "user", "content": "x"}], "standard": "furniture-v0"})
            _lines(resp)
            conn.close()
        assert log[-2][1]["max_cost_usd"] == 1.5 and log[-1][1]["base_url"] == "http://localhost:11434/v1"

        for bad in ({"agy_account": "personal"}, {"max_cost_usd": 0}, {"max_cost_usd": "1"}, {"codex_experimental": "yes"},
                    {"ollama_base_url": "http://evil.example:11434/v1"}, {"api_key": FAKE_KEY2},
                    {"connections": [{"id": "a", "engine": "anthropic", "key": FAKE_KEY2}]}, {"models": {"openai": "a b"}}):
            status, raw = _raw(c, "POST", "/api/ai/settings", bad)
            assert status == 400 and FAKE_KEY2 not in raw, bad
    finally:
        srv.shutdown()
        srv.server_close()


def test_settings_connection_profiles_structure(tmp_path):
    s = Settings(tmp_path / "s.json")
    s.update_ai({"models": {"anthropic": "claude-x"}})
    ai = s.ai()
    assert ai["connections"] == [{"id": "anthropic", "engine": "anthropic", "label": "Mặc định", "model": "claude-x",
                                  "key_slot": "anthropic"}]
    # Cấu trúc cho phép nhiều hồ sơ mỗi engine (ví dụ theo phòng); hồ sơ đang dùng chọn qua active_connection.
    s.data["ai"]["connections"].append({"id": "anthropic-ky-thuat", "engine": "anthropic", "label": "Phòng Kỹ thuật",
                                        "model": "claude-y", "key_slot": "anthropic-ky-thuat"})
    s.data["ai"]["active_connection"]["anthropic"] = "anthropic-ky-thuat"
    s.save()
    again = Settings(tmp_path / "s.json")
    from cadguard.app.settings import connection

    assert connection(again.ai(), "anthropic")["model"] == "claude-y"
    assert "key" not in json.dumps(again.ai()["connections"]).replace("key_slot", "")
    (tmp_path / "s.json").write_text("{hỏng", encoding="utf-8")
    assert Settings(tmp_path / "s.json").ai()["max_cost_usd"] == 2.0  # tệp hỏng: dùng mặc định


# ---------- tệp tĩnh ----------

def test_static_files_follow_csp_and_mockup():
    files = sorted(p for p in STATIC_DIR.iterdir() if p.is_file())
    assert {p.name for p in files} == {"index.html", "app.css", "app.js"}
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert not re.search(r"https?://", text), p.name
        assert "//cdn" not in text and "@import" not in text and "url(" not in text, p.name
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert "<style" not in html and not re.search(r"<script(?![^>]*\bsrc=)", html)
    assert not re.search(r"\son[a-z]+\s*=", html) and " style=" not in html and "javascript:" not in html
    for words in ("Việc của tôi", "Tổng quan", "Luật áp dụng", "Kết nối AI", "Mở thư mục…", "Dự án gần đây",
                  "Dùng CLI có sẵn (đăng nhập của bạn)", "Dùng khoá API của công ty", "Mức dữ liệu gửi cho AI",
                  "Trợ lý được và không được làm gì", "Giới hạn chi phí", "Tệp gốc chỉ đọc"):
        assert words in html, words
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    for bad in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function", ".onclick",
                "setAttribute(\"style\"", "localStorage.setItem(\"cg-key"):
        assert bad not in js, bad
    assert 'type: "password"' in js and 'autocomplete: "off"' in js
    css = (STATIC_DIR / "app.css").read_text(encoding="utf-8")
    mock = (REPO / "design" / "ui-mockup.html").read_text(encoding="utf-8")
    mock_css = re.search(r"<style>\n(.*?)</style>", mock, re.S).group(1)
    assert mock_css in css  # CSS của bản mẫu chốt được giữ nguyên văn


def test_cli_app_workspace_is_optional():
    import argparse

    from cadguard.app import add_arguments

    p = argparse.ArgumentParser()
    add_arguments(p)
    assert p.parse_args([]).workspace is None


def _rule_ids(rep: dict) -> set[str]:
    out = set()
    for g in rep.get("groups", []):
        for r in g.get("rules", []):
            out.add(r["rule_id"])
    for f in rep.get("findings", []) or []:
        out.add(f["rule_id"])
    return out
