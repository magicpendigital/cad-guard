"""Engine API (cách C) với máy chủ HTTP GIẢ trong luồng (cổng ngẫu nhiên). Không gọi mạng thật, không mô hình thật."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from cadguard import fixtures
from cadguard.assistant import create_engine
from cadguard.assistant.api_engines import ANTHROPIC_VERSION, AnthropicEngine, OpenAICompatEngine
from cadguard.cli import main as cli_main

FAKE_KEY = "test-fake-key-0123456789abcdef"
PRIVATE = ["SYNX1", "SYNX2", "SYN-TUONG", "SYN-CUA", "hygiene_bad"]  # tên thật trong hygiene_bad.dxf


class FakeProvider:
    """Máy chủ giả: `script(request_index, body) -> (status, json)`; ghi lại mọi yêu cầu."""

    def __init__(self, script):
        self.script, self.requests = script, []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                raw = self.rfile.read(int(self.headers.get("content-length", 0))).decode("utf-8")
                body = json.loads(raw)
                outer.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()},
                                       "raw": raw, "body": body})
                status, payload = outer.script(len(outer.requests) - 1, body)
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def ws(tmp_path):
    d = tmp_path / "ws"
    d.mkdir()
    fixtures.ALL["hygiene_bad.dxf"](d / "hygiene_bad.dxf")
    return d


@pytest.fixture
def provider():
    made = []

    def make(script):
        p = FakeProvider(script)
        made.append(p)
        return p

    yield make
    for p in made:
        p.close()


def _last_tool_result_text(body) -> str:
    """Nội dung tool_result cuối cùng trong yêu cầu Anthropic."""
    for msg in reversed(body["messages"]):
        if msg["role"] == "user" and isinstance(msg["content"], list):
            for block in msg["content"]:
                if block.get("type") == "tool_result":
                    return block["content"]
    return ""


def anthropic_script(i, body):
    usage = {"input_tokens": 1000, "output_tokens": 100, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    if i == 0:
        return 200, {"content": [{"type": "thinking", "thinking": "", "signature": "s"},
                                 {"type": "tool_use", "id": "tu1", "name": "list_drawings", "input": {}}],
                     "stop_reason": "tool_use", "usage": usage}
    if i == 1:
        file_id = json.loads(_last_tool_result_text(body))["drawings"][0]["id"]
        return 200, {"content": [{"type": "tool_use", "id": "tu2", "name": "audit",
                                  "input": {"file": file_id, "standard": "design-hygiene-v0"}}],
                     "stop_reason": "tool_use", "usage": usage}
    audit = json.loads(_last_tool_result_text(body))
    return 200, {"content": [{"type": "text", "text": f"Có {audit['counts']['E']} lỗi E."}], "stop_reason": "end_turn",
                 "usage": usage}


def _run(engine, ws, **kw):
    return list(engine.run([{"role": "user", "content": "Kiểm bản vẽ."}], workspace=ws, **kw))


def test_anthropic_tool_loop_uses_cadguard_tools_and_anonymizes(provider, ws):
    p = provider(anthropic_script)
    eng = AnthropicEngine(api_key=FAKE_KEY, base_url=p.url)
    events = _run(eng, ws)
    assert "error" not in [e.type for e in events]
    calls = [e.data["name"] for e in events if e.type == "tool_call"]
    assert calls == ["list_drawings", "audit"]
    results = [e for e in events if e.type == "tool_result"]
    assert all(not r.data["is_error"] for r in results)
    assert json.loads(results[1].data["content"])["standard"] == "design-hygiene-v0"
    assert events[-1].type == "done" and "lỗi E" in events[-1].data["text"]

    assert len(p.requests) == 3
    first = p.requests[0]
    assert first["path"] == "/v1/messages"
    assert first["headers"]["x-api-key"] == FAKE_KEY and first["headers"]["anthropic-version"] == ANTHROPIC_VERSION
    assert first["body"]["model"] == "claude-sonnet-5-5" and "temperature" not in first["body"]
    names = [t["name"] for t in first["body"]["tools"]]
    assert set(names) == {"list_drawings", "audit", "explain_rule", "get_model_summary", "query_model", "diff"}
    assert not [n for n in names if "apply" in n]
    # Khối thinking của lượt trước được gửi lại nguyên vẹn.
    assert p.requests[1]["body"]["messages"][1]["content"][0]["type"] == "thinking"
    # Ẩn danh Bậc 1 mặc định: không tên layer/tệp thật nào của bản vẽ rời máy (ngoài lời nhắc hệ thống cố định,
    # vốn có thể nhắc tên fixture tổng hợp làm ví dụ).
    for req in p.requests:
        sent = json.dumps(req["body"]["messages"], ensure_ascii=False)
        for word in PRIVATE:
            assert word not in sent
    usage = [e.data["usage"] for e in events if e.type == "usage"]
    assert len(usage) == 3 and usage[0].cost_usd == pytest.approx((1000 * 2 + 100 * 10) / 1e6)


PRIVATE_CONTENT = ["PRIVATE_NOTE", "PRIVATE_MTEXT", "PRIVATE_ATTR", "riêng tư", "424242.4242", "454545.4545"]


def _private_content_doc(path):
    """DXF tổng hợp có chữ "riêng tư", giá trị thuộc tính và toạ độ dễ nhận (các trường mới text/pos/pts/insert)."""
    import ezdxf

    doc = ezdxf.new("R2018")
    blk = doc.blocks.new("SYN-KHUNG")
    blk.add_attdef("SYN_TAG", (0, 0))
    msp = doc.modelspace()
    msp.add_text("PRIVATE_NOTE riêng tư", dxfattribs={"insert": (424242.4242, 1)})
    msp.add_mtext("PRIVATE_MTEXT riêng tư", dxfattribs={"insert": (454545.4545, 2)})
    msp.add_line((424242.4242, 0), (454545.4545, 1))
    msp.add_lwpolyline([(424242.4242, 0), (454545.4545, 5), (0, 5)])
    msp.add_circle((454545.4545, 3), 7)
    msp.add_blockref("SYN-KHUNG", (424242.4242, 9)).add_auto_attribs({"SYN_TAG": "PRIVATE_ATTR riêng tư"})
    doc.saveas(path)


def test_anonymized_tool_results_never_carry_drawing_content(provider, ws):
    """Bậc 1 mặc định: chữ, giá trị thuộc tính, toạ độ trong bản vẽ không có trong body gửi API (giả)."""
    _private_content_doc(ws / "noi_dung.dxf")
    import ezdxf

    doc = ezdxf.readfile(ws / "noi_dung.dxf")  # bản sửa: đổi chữ và dời điểm chèn, để diff có thuộc tính đổi
    for e in doc.modelspace():
        if e.dxftype() == "TEXT":
            e.dxf.text = "PRIVATE_NOTE riêng tư sửa"
        if e.dxftype() == "INSERT":
            e.dxf.insert = (454545.4545, 9)
    doc.saveas(ws / "noi_dung_sua.dxf")

    def script(i, body):
        if i == 0:
            return 200, {"content": [{"type": "tool_use", "id": "t0", "name": "list_drawings", "input": {}}],
                         "stop_reason": "tool_use", "usage": {}}
        if i == 1:
            ids = [d["id"] for d in json.loads(_last_tool_result_text(body))["drawings"]]
            calls = [{"type": "tool_use", "id": f"q{k}", "name": n, "input": {"file": f, **extra}}
                     for k, (f, (n, extra)) in enumerate((f, c) for f in ids for c in (
                         ("query_model", {"limit": 500}), ("get_model_summary", {}), ("audit", {})))]
            calls.append({"type": "tool_use", "id": "d0", "name": "diff", "input": {"a": ids[1], "b": ids[2]}})
            calls.append({"type": "tool_use", "id": "d1", "name": "diff", "input": {"a": ids[0], "b": ids[1]}})
            return 200, {"content": calls, "stop_reason": "tool_use", "usage": {}}
        return 200, {"content": [{"type": "text", "text": "xong"}], "stop_reason": "end_turn", "usage": {}}

    p = provider(script)
    events = _run(AnthropicEngine(api_key=FAKE_KEY, base_url=p.url), ws)
    results = [e for e in events if e.type == "tool_result"]
    assert len(results) == 1 + 3 * 3 + 2 and all(not r.data["is_error"] for r in results)
    changed = json.loads(results[-2].data["content"])["entities"]["changed"]
    assert {k for c in changed for k in c["attrs"]} >= {"text", "insert"}  # có đổi, nhưng giá trị bị che
    queried = [json.loads(r.data["content"]) for r in results if '"items"' in r.data["content"]]
    assert queried and all(item["type"] for q in queried for item in q["items"])
    assert any(item["type"] == "TEXT" for q in queried for item in q["items"])
    for req in p.requests:
        sent = req["raw"] + json.dumps(req["body"], ensure_ascii=False)
        for word in PRIVATE_CONTENT:
            assert word not in sent, word
        for key in ('"pts"', '"pos"', '"insert"', '"attribs"', '"dup_key"'):
            assert key not in sent, key


def test_propose_only_when_allowed_never_apply(provider, ws):
    p = provider(lambda i, b: (200, {"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn", "usage": {}}))
    eng = AnthropicEngine(api_key=FAKE_KEY, base_url=p.url)
    _run(eng, ws)
    _run(eng, ws, allow_propose=True)
    without = [t["name"] for t in p.requests[0]["body"]["tools"]]
    with_p = [t["name"] for t in p.requests[1]["body"]["tools"]]
    assert "propose_changeset" not in without and "propose_changeset" in with_p
    assert not [n for n in without + with_p if "apply" in n]


def test_tool_round_cap(provider, ws):
    def loop(i, body):
        return 200, {"content": [{"type": "tool_use", "id": f"t{i}", "name": "list_drawings", "input": {}}],
                     "stop_reason": "tool_use", "usage": {"input_tokens": 1, "output_tokens": 1}}

    p = provider(loop)
    events = _run(AnthropicEngine(api_key=FAKE_KEY, base_url=p.url, max_tool_rounds=2), ws)
    err = [e for e in events if e.type == "error"]
    assert err and err[0].data["code"] == "tool_rounds"
    assert len(p.requests) == 3


def test_cost_and_token_caps(provider, ws):
    def loop(i, body):
        return 200, {"content": [{"type": "tool_use", "id": f"t{i}", "name": "list_drawings", "input": {}}],
                     "stop_reason": "tool_use", "usage": {"input_tokens": 100000, "output_tokens": 1000}}

    p = provider(loop)
    events = _run(AnthropicEngine(api_key=FAKE_KEY, base_url=p.url, max_cost_usd=0.1), ws)
    assert [e.data["code"] for e in events if e.type == "error"] == ["budget"]
    assert len(p.requests) == 1
    p2 = provider(loop)
    events = _run(AnthropicEngine(api_key=FAKE_KEY, base_url=p2.url, max_cost_usd=None, max_session_tokens=150000), ws)
    assert [e.data["code"] for e in events if e.type == "error"] == ["budget"] and len(p2.requests) == 2


@pytest.mark.parametrize("status,code", [(401, "auth"), (400, "http"), (429, "rate_limit"), (500, "server")])
def test_http_errors_never_leak_key(provider, ws, status, code, capsys):
    p = provider(lambda i, b: (status, {"error": {"message": f"Incorrect API key provided: {FAKE_KEY}"}}))
    events = _run(AnthropicEngine(api_key=FAKE_KEY, base_url=p.url), ws)
    err = next(e for e in events if e.type == "error")
    assert err.data["code"] == code and FAKE_KEY not in err.data["message"] and "HTTP" in err.data["message"]
    assert FAKE_KEY not in repr(AnthropicEngine(api_key=FAKE_KEY))
    cap = capsys.readouterr()
    assert FAKE_KEY not in cap.out + cap.err


def test_network_error_is_vietnamese(ws):
    events = _run(AnthropicEngine(api_key=FAKE_KEY, base_url="http://127.0.0.1:9", network_timeout=3), ws)
    err = next(e for e in events if e.type == "error")
    assert err.data["code"] in ("network", "timeout") and FAKE_KEY not in err.data["message"]


def test_missing_key(monkeypatch, ws):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setitem(__import__("sys").modules, "keyring", None)
    events = _run(AnthropicEngine(base_url="http://127.0.0.1:9"), ws)
    assert events[0].data["code"] == "no_key" and "cadguard keys set anthropic" in events[0].data["message"]


def openai_script(i, body):
    usage = {"prompt_tokens": 500, "completion_tokens": 50, "prompt_tokens_details": {"cached_tokens": 100}}
    if i == 0:
        return 200, {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "list_drawings", "arguments": "{}"}}]},
            "finish_reason": "tool_calls"}], "usage": usage}
    if i == 1:
        tool_msg = body["messages"][-1]
        assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "c1"
        file_id = json.loads(tool_msg["content"])["drawings"][0]["id"]
        return 200, {"choices": [{"message": {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {"name": "get_model_summary",
                                                           "arguments": json.dumps({"file": file_id})}}]},
            "finish_reason": "tool_calls"}], "usage": usage}
    return 200, {"choices": [{"message": {"role": "assistant", "content": "Tóm tắt xong."}, "finish_reason": "stop"}],
                 "usage": {**usage, "cost": 0.002}}


def test_openai_compatible_tool_calls(provider, ws):
    p = provider(openai_script)
    eng = OpenAICompatEngine("openai", api_key=FAKE_KEY, base_url=p.url, model="mo-hinh-thu")
    events = _run(eng, ws)
    assert "error" not in [e.type for e in events]
    assert [e.data["name"] for e in events if e.type == "tool_call"] == ["list_drawings", "get_model_summary"]
    assert events[-1].data["text"] == "Tóm tắt xong."
    req = p.requests[0]
    assert req["path"] == "/chat/completions" and req["headers"]["authorization"] == f"Bearer {FAKE_KEY}"
    assert req["body"]["messages"][0]["role"] == "system" and req["body"]["model"] == "mo-hinh-thu"
    assert {t["function"]["name"] for t in req["body"]["tools"]} >= {"audit", "query_model"}
    u = [e.data["usage"] for e in events if e.type == "usage"]
    assert (u[0].input_tokens, u[0].cache_read_tokens, u[0].cost_usd) == (400, 100, None)
    assert u[-1].cost_usd == pytest.approx(0.002)
    for r in p.requests:
        sent = json.dumps(r["body"]["messages"][1:], ensure_ascii=False)  # bỏ lời nhắc hệ thống cố định
        for word in PRIVATE:
            assert word not in sent


def test_ollama_needs_no_key_and_local(provider, ws):
    p = provider(lambda i, b: (200, {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {}}))
    events = _run(create_engine("ollama", model="qwen-thu", base_url=p.url), ws)
    assert "error" not in [e.type for e in events]
    assert "authorization" not in p.requests[0]["headers"]
    assert next(e for e in events if e.type == "usage").data["usage"].cost_usd == 0.0


def test_openrouter_off_by_default(provider, ws, monkeypatch):
    monkeypatch.delenv("CADGUARD_ALLOW_OPENROUTER", raising=False)
    p = provider(lambda i, b: (200, {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {}}))
    events = _run(create_engine("openrouter", model="x/y", api_key=FAKE_KEY, base_url=p.url), ws)
    assert events[0].data["code"] == "disabled" and "trung gian thứ ba" in events[0].data["message"]
    assert p.requests == []
    events = _run(create_engine("openrouter", model="x/y", api_key=FAKE_KEY, base_url=p.url, allow_openrouter=True), ws)
    assert "error" not in [e.type for e in events]
    assert p.requests[0]["body"]["usage"] == {"include": True}


def test_openai_requires_model(monkeypatch, ws):
    monkeypatch.delenv("CADGUARD_OPENAI_MODEL", raising=False)
    events = _run(create_engine("openai", api_key=FAKE_KEY), ws)
    assert events[0].data["code"] == "no_model"


def test_unknown_and_bad_tool_args_go_back_to_model(provider, ws):
    def script(i, body):
        if i == 0:
            return 200, {"content": [{"type": "tool_use", "id": "a", "name": "apply_changeset", "input": {}},
                                     {"type": "tool_use", "id": "b", "name": "audit", "input": {"file": "../ngoai.dxf"}},
                                     {"type": "tool_use", "id": "c", "name": "audit", "input": {"file": "x", "la": 1}}],
                         "stop_reason": "tool_use", "usage": {}}
        return 200, {"content": [{"type": "text", "text": "xong"}], "stop_reason": "end_turn", "usage": {}}

    p = provider(script)
    events = _run(AnthropicEngine(api_key=FAKE_KEY, base_url=p.url), ws)
    res = [e for e in events if e.type == "tool_result"]
    assert [r.data["is_error"] for r in res] == [True, True, True]
    assert "Không có công cụ" in res[0].data["content"] and "đường dẫn" in res[1].data["content"]
    blocks = p.requests[1]["body"]["messages"][-1]["content"]
    assert len(blocks) == 3 and all(b["is_error"] for b in blocks)  # mọi kết quả trong MỘT tin nhắn


def test_profile_compare_tool(provider, ws):
    from pathlib import Path

    prof = Path(__file__).resolve().parents[3] / "bench" / "ho-so" / "cong-ty-bench.yaml"
    p = provider(lambda i, b: (200, {"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn", "usage": {}}))
    _run(AnthropicEngine(api_key=FAKE_KEY, base_url=p.url), ws, profile=prof, compare_without_profile=True)
    assert "audit_khong_ho_so" in [t["name"] for t in p.requests[0]["body"]["tools"]]


def test_cli_ask_json_with_fake_provider(provider, ws, monkeypatch, capsys):
    p = provider(anthropic_script)
    monkeypatch.setenv("CADGUARD_ANTHROPIC_BASE_URL", p.url)
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    rc = cli_main(["ask", "Có bao nhiêu lỗi E?", "--engine", "anthropic", "--workspace", str(ws), "--json"])
    out = capsys.readouterr()
    assert rc == 0 and FAKE_KEY not in out.out + out.err
    data = json.loads(out.out)
    assert "lỗi E" in data["answer"] and data["usage"]["input_tokens"] == 3000 and data["errors"] == []
