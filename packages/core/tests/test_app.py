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
    names = {d["name"]: d["standard"] for d in s["departments"]}
    assert names == {"Thiết kế": "design-hygiene-v0", "Kỹ thuật": "furniture-v0", "Lập trình sản xuất": "furniture-v0"}
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
    assert status == 200 and r["read_only"] is True and r["counts"]["total"] == len(r["rules"]) >= 7
    row = next(x for x in r["rules"] if x["id"] == "VS-02")
    assert row["params_default"] == row["params_effective"] and row["params_changed"] == []

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
        assert s["anonymize"] is False and "KHÔNG" in s["data_mode"]
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
