import hashlib
import http.client
import json
import threading
from pathlib import Path

import pytest

from cadguard.dxf_reader import read_dxf
from cadguard.scene import build_scene
from cadguard.studio.clusters import clusters_of, digest
from cadguard.studio.llm import FakeBackend
from cadguard.studio.protocol import extract_json, parse_reply
from cadguard.studio.session import Session


def _sess(synthetic, name, tmp_path, replies=None, consent=True):
    data = (synthetic / "scene" / name).read_bytes()
    s = Session(data, tmp_path / "work", FakeBackend(replies or []))
    s.consent = consent
    return s


VIEWS = {"reply": "C1 là mặt đứng, C2 mặt bên, C3 mặt bằng.", "proposals": [{"kind": "set_views", "views": {"front": "C1", "side": "C2", "top": "C3"}, "why": "nhãn MAT DUNG/MAT BEN/MAT BANG"}]}


def test_clusters_find_three_views_without_layers(synthetic):
    m = read_dxf(synthetic / "scene" / "cabinet_nolayers.dxf")
    cl = clusters_of(m)
    assert [c.id for c in cl] == ["C1", "C2", "C3"]
    assert build_scene(m).panels == []  # code thuần theo layer không nhận ra hình chiếu nào
    d = digest(m)
    texts = [t["text"] for c in d["clusters"] for t in c["texts"]]
    assert {"MAT DUNG", "MAT BEN", "MAT BANG"} <= set(texts)


def test_llm_mapping_recovers_case_code_missed(synthetic, tmp_path):
    s = _sess(synthetic, "cabinet_nolayers.dxf", tmp_path, [json.dumps(VIEWS)])
    assert not s.scene.panels
    s.ask(None)
    assert len(s.proposals) == 1 and s.proposals[0].status == "pending"
    assert not s.scene.panels  # chưa duyệt thì chưa áp dụng
    assert s.accept("p1")
    assert len(s.scene.panels) == 5 and not s.scene.gaps
    assert s.undo() and not s.scene.panels


def test_invalid_proposals_dropped_with_reason(synthetic, tmp_path):
    bad = {
        "reply": "x",
        "proposals": [
            {"kind": "set_views", "views": {"front": "C9"}},
            {"kind": "set_value", "key": "panel:ZZ:depth", "value": "500"},
            {"kind": "set_attrib", "handle": "NOPE", "tag": "H", "value": "1"},
            {"kind": "change_layer", "handles": ["NOPE"], "layer": "A"},
            {"kind": "delete_everything"},
        ],
    }
    s = _sess(synthetic, "cabinet_nolayers.dxf", tmp_path, [json.dumps(bad)])
    s.ask("hỏi")
    assert s.proposals == [] and sum("bị loại" in n for n in s.notes) == 5


def test_requires_consent_and_no_path_leak(synthetic, tmp_path):
    s = _sess(synthetic, "cabinet_nolayers.dxf", tmp_path, [json.dumps({"reply": "ok"})], consent=False)
    s.ask("hỏi")
    assert not s.backend.calls and any("đồng ý" in n for n in s.notes)
    s.consent = True
    s.ask("hỏi")
    sent = json.dumps(s.backend.calls[0][1], ensure_ascii=False)
    assert str(tmp_path) not in sent and "source.dxf" not in sent and "MAT DUNG" in sent


def test_backend_error_does_not_crash(synthetic, tmp_path):
    class Boom:
        name = "boom"

        def complete(self, system, messages):
            raise RuntimeError("mạng đứt")

    s = _sess(synthetic, "cabinet_nolayers.dxf", tmp_path)
    s.backend = Boom()
    s.ask("hỏi")
    assert any("LLM lỗi" in n for n in s.notes) and s.chat == []


def test_set_attrib_via_llm_then_export_new_file(synthetic, tmp_path):
    s = _sess(synthetic, "room_missing_height.dxf", tmp_path)
    assert len(s.scene.gaps) == 2 and len(s.scene.modules) == 1
    target = next(e for e in s.model.entities if e.type == "INSERT" and not (e.attribs or {}).get("H"))
    reply = {"reply": "đề xuất", "proposals": [{"kind": "set_attrib", "handle": target.handle, "tag": "H", "value": "850", "why": "tủ dưới tiêu chuẩn"}]}
    s.backend = FakeBackend([json.dumps(reply)])
    s.ask("sửa")
    before = hashlib.sha256(s.source.read_bytes()).hexdigest()
    assert s.accept("p1")
    assert any(m.h == 850.0 for m in s.scene.modules)
    out = s.export_dxf()
    assert out != s.source and out.exists()
    assert hashlib.sha256(s.source.read_bytes()).hexdigest() == before  # nguồn không bị ghi đè
    assert any(e.attribs and e.attribs.get("H") == "850" for e in read_dxf(out).entities)
    assert s.undo() and len(s.scene.modules) == 1


def test_change_layer_enables_views_by_convention(synthetic, tmp_path):
    s = _sess(synthetic, "cabinet_nolayers.dxf", tmp_path)
    ops = []
    for cid, lay in (("C1", "FN-VIEW-FRONT"), ("C2", "FN-VIEW-SIDE"), ("C3", "FN-VIEW-TOP")):
        c = next(c for c in s.clusters if c.id == cid)
        ops.append({"kind": "change_layer", "handles": [e.handle for e in c.entities if e.type == "LWPOLYLINE"], "layer": lay, "why": "chuẩn hoá layer"})
    s.backend = FakeBackend([json.dumps({"reply": "chuẩn hoá", "proposals": ops})])
    s.ask("chuẩn hoá layer")
    for p in list(s.proposals):
        assert s.accept(p.id)
    assert len(s.scene.panels) == 5 and s.edits and len(s.edits) == 3


def test_set_value_proposal_fills_gap(synthetic, tmp_path):
    s = _sess(synthetic, "cabinet_views_front_only.dxf", tmp_path)
    key = s.scene.gaps[0].fields[0].key
    s.backend = FakeBackend([json.dumps({"reply": "r", "proposals": [{"kind": "set_value", "key": key, "value": "500", "why": "sâu 500"}]})])
    s.ask("gợi ý")
    assert s.accept("p1") and len(s.scene.panels) == 1 and s.scene.panels[0].source == "user"


def test_parse_reply_robust():
    assert extract_json('Đây:\n```json\n{"reply":"a {b}"}\n```')["reply"] == "a {b}"
    r, err = parse_reply("không phải json")
    assert err and r.proposals == []
    r, err = parse_reply('{"reply":"x","proposals":"sai"}')
    assert err and r.proposals == []


# ---- máy chủ ----------------------------------------------------------------
@pytest.fixture
def server(tmp_path):
    from cadguard.studio.server import StudioServer

    srv = StudioServer(0, FakeBackend([json.dumps(VIEWS)]), tmp_path / "w")
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _req(srv, method, path, body=b"", token=True, host=None):
    c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
    hdr = {"Host": host or f"127.0.0.1:{srv.server_address[1]}"}
    if token:
        hdr["X-CG-Token"] = srv.token
    c.request(method, path, body=body, headers=hdr)
    r = c.getresponse()
    data = r.read()
    return r.status, data


def test_server_auth_and_flow(server, synthetic):
    assert _req(server, "GET", "/api/state", token=False)[0] == 403
    assert _req(server, "GET", "/api/state", host="evil.example.com")[0] == 403
    assert _req(server, "GET", "/api/state")[0] == 404  # chưa mở bản vẽ
    st, page = _req(server, "GET", "/")
    assert st == 200 and b"cad-guard" in page and page.count(b"innerHTML") == 1
    dxf = (synthetic / "scene" / "cabinet_nolayers.dxf").read_bytes()
    st, data = _req(server, "POST", "/api/open", dxf)
    s = json.loads(data)
    assert st == 200 and s["scene"]["panels"] == [] and len(s["clusters"]) == 3
    _req(server, "POST", "/api/consent", b'{"value": true}')
    st, data = _req(server, "POST", "/api/analyze", b"{}")
    s = json.loads(data)
    assert s["proposals"][0]["id"] == "p1"
    st, data = _req(server, "POST", "/api/proposals/p1/accept", b"{}")
    assert len(json.loads(data)["scene"]["panels"]) == 5
    st, glb = _req(server, "GET", "/api/glb")
    assert st == 200 and glb[:4] == b"glTF"
    st, data = _req(server, "POST", "/api/export", b"{}")
    assert Path(json.loads(data)["path"]).exists()
    assert _req(server, "POST", "/api/open", b"khong phai dxf")[0] == 400
    assert _req(server, "POST", "/api/proposals/p9;rm/accept", b"{}")[0] == 404


def test_cli_studio_none_backend_rejects_bad(monkeypatch):
    import sys

    from cadguard.studio import llm

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setitem(sys.modules, "keyring", None)  # khoá còn có thể đến từ kho khoá HĐH (assistant/keys.py): tắt
    with pytest.raises(llm.LlmError, match="cadguard keys set anthropic"):
        llm.AnthropicBackend()


# ---- khoá và đường HTTP của AnthropicBackend (máy chủ giả, không gọi mạng thật) ----------------------------------
FAKE_KEY = "test-fake-studio-key-0123456789"


@pytest.fixture
def fake_anthropic():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    seen: list = []
    status = {"code": 200}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            raw = self.rfile.read(int(self.headers.get("content-length", 0))).decode("utf-8")
            seen.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": json.loads(raw)})
            if status["code"] == 200:
                payload = {"content": [{"type": "text", "text": json.dumps(VIEWS)}], "stop_reason": "end_turn"}
            else:
                payload = {"error": {"message": f"bad key {FAKE_KEY}"}}
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status["code"])
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield {"url": f"http://127.0.0.1:{srv.server_address[1]}", "seen": seen, "status": status}
    srv.shutdown()
    srv.server_close()


def _keyring_with(monkeypatch, value):
    import sys
    import types

    mod = types.ModuleType("keyring")
    mod.get_password = lambda service, user: value if (service, user) == ("cad-guard", "anthropic") else None
    monkeypatch.setitem(sys.modules, "keyring", mod)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_anthropic_backend_key_from_os_keyring_and_http(monkeypatch, fake_anthropic, synthetic, tmp_path):
    """Studio dùng chung kho khoá (assistant/keys.py) và đường HTTP của trợ lý; không cần SDK `anthropic`."""
    from cadguard.studio import llm

    _keyring_with(monkeypatch, FAKE_KEY)
    backend = llm.AnthropicBackend(base_url=fake_anthropic["url"])
    assert FAKE_KEY not in repr(backend)
    s = _sess(synthetic, "cabinet_nolayers.dxf", tmp_path)
    s.backend = backend
    s.ask(None)
    assert [p.kind for p in s.proposals] == ["set_views"]
    req = fake_anthropic["seen"][0]
    assert req["path"] == "/v1/messages" and req["headers"]["x-api-key"] == FAKE_KEY
    assert req["body"]["system"] == llm.SYSTEM_PROMPT and req["body"]["messages"][-1]["role"] == "user"
    sent = json.dumps(req["body"], ensure_ascii=False)
    assert str(tmp_path) not in sent and "source.dxf" not in sent and FAKE_KEY not in sent
    assert not list(tmp_path.rglob("*key*"))  # không ghi khoá ra tệp


def test_anthropic_backend_env_wins_and_errors_hide_key(monkeypatch, fake_anthropic, synthetic, tmp_path):
    from cadguard.studio import llm

    _keyring_with(monkeypatch, "khoa-trong-kho-khong-dung")
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    backend = llm.AnthropicBackend(base_url=fake_anthropic["url"])
    fake_anthropic["status"]["code"] = 500  # máy chủ trả lỗi kèm khoá trong chi tiết
    s = _sess(synthetic, "cabinet_nolayers.dxf", tmp_path)
    s.backend = backend
    s.ask("hỏi")
    assert fake_anthropic["seen"][0]["headers"]["x-api-key"] == FAKE_KEY
    notes = " | ".join(s.notes)
    assert "LLM lỗi" in notes and "HTTP 500" in notes and FAKE_KEY not in notes
    assert FAKE_KEY not in json.dumps(s.state(), ensure_ascii=False)
