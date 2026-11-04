"""Engine CLI (cách B) với CLI GIẢ: không gọi mô hình, không mạng, không chạy claude/codex/agy thật."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

from cadguard import fixtures
from cadguard.assistant import CancelToken, create_engine
from cadguard.assistant.base import AUTH_ENV_VARS
from cadguard.assistant.cli_engines import CLAUDE_DENY, AgyCliEngine, ClaudeCliEngine, CodexCliEngine

FAKE_CLI = r'''
import json, os, sys, time
kind, mode = os.environ["FAKE_KIND"], os.environ.get("FAKE_MODE", "ok")
stdin = sys.stdin.read()
with open(os.environ["FAKE_DUMP"], "w", encoding="utf-8") as f:
    json.dump({"argv": sys.argv[1:], "stdin": stdin, "cwd_files": sorted(os.listdir(".")),
               "env": {k: os.environ.get(k) for k in os.environ}}, f)
def out(o):
    print(json.dumps(o, ensure_ascii=False), flush=True)
if kind == "claude":
    status = "failed" if mode == "noconn" else "connected"
    out({"type": "system", "subtype": "init", "mcp_servers": [{"name": "cad-guard", "status": status}]})
    if mode == "sleep":
        time.sleep(30)
    if mode == "notlogged":
        out({"type": "result", "subtype": "success", "is_error": True, "result": "Not logged in · Please run /login"})
        sys.exit(1)
    out({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "mcp__cad-guard__audit",
        "input": {"file": "F_x"}}]}})
    out({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
        "content": [{"type": "text", "text": "{\"counts\": {\"E\": 1}}"}]}]}})
    out({"type": "assistant", "message": {"content": [{"type": "text", "text": "Có 1 lỗi E."}]}})
    out({"type": "result", "subtype": "success", "is_error": False, "result": "Có 1 lỗi E.",
         "usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 5, "cache_creation_input_tokens": 7},
         "total_cost_usd": 0.0123})
elif kind == "codex":
    out({"type": "thread.started", "thread_id": "x"})
    if mode == "noconn":
        out({"type": "error", "message": "MCP client for `cad-guard` failed to start"})
        sys.exit(1)
    out({"type": "item.started", "item": {"id": "i1", "type": "mcp_tool_call", "server": "cad-guard", "tool": "audit",
         "arguments": {"file": "F_x"}, "status": "in_progress"}})
    out({"type": "item.completed", "item": {"id": "i1", "type": "mcp_tool_call", "server": "cad-guard", "tool": "audit",
         "arguments": {"file": "F_x"}, "result": {"content": [{"type": "text", "text": "{}"}]}, "status": "completed"}})
    out({"type": "item.completed", "item": {"id": "i2", "type": "agent_message", "text": "Xong."}})
    out({"type": "turn.completed", "usage": {"input_tokens": 50, "cached_input_tokens": 10, "output_tokens": 5}})
elif kind == "agy":
    tier = "oauth-personal" if mode == "personal" else "enterprise"
    out({"type": "init", "_meta": {"antigravity": {"tier": tier}}})
    out({"type": "step_update", "usage": {"input_tokens": 1}})
    out({"type": "result", "status": "SUCCESS", "response": "Trả lời agy.",
         "usage": {"input_tokens": 30, "output_tokens": 4, "thinking_tokens": 2, "cache_read_tokens": 3}})
'''


@pytest.fixture
def fake(tmp_path, monkeypatch):
    script = tmp_path / "fake_cli.py"
    script.write_text(FAKE_CLI, encoding="utf-8")
    dump = tmp_path / "dump.json"
    monkeypatch.setenv("FAKE_DUMP", str(dump))
    ws = tmp_path / "ws"
    ws.mkdir()
    fixtures.ALL["hygiene_bad.dxf"](ws / "hygiene_bad.dxf")

    def setup(kind, mode="ok"):
        monkeypatch.setenv("FAKE_KIND", kind)
        monkeypatch.setenv("FAKE_MODE", mode)
        return [sys.executable, str(script)]

    setup.ws = ws
    setup.dump = lambda: json.loads(dump.read_text(encoding="utf-8"))
    setup.dump_path = dump
    return setup


def _run(engine, ws, **kw):
    return list(engine.run([{"role": "user", "content": "Có bao nhiêu lỗi?"}], workspace=ws, **kw))


def _types(events):
    return [e.type for e in events]


# ---------- Claude Code ----------


def test_claude_parses_stream_and_usage(fake, monkeypatch):
    for var in AUTH_ENV_VARS:
        monkeypatch.setenv(var, "test-not-a-real-key")
    eng = ClaudeCliEngine(fake("claude"))
    events = _run(eng, fake.ws)
    types = _types(events)
    assert types[-1] == "done" and "error" not in types
    call = next(e for e in events if e.type == "tool_call")
    assert call.data["name"] == "mcp__cad-guard__audit" and call.data["arguments"] == {"file": "F_x"}
    res = next(e for e in events if e.type == "tool_result")
    assert '"E": 1' in res.data["content"] and res.data["is_error"] is False
    u = next(e for e in events if e.type == "usage").data["usage"]
    assert (u.input_tokens, u.output_tokens, u.cache_read_tokens, u.cache_write_tokens) == (100, 20, 5, 7)
    assert u.cost_usd == pytest.approx(0.0123) and u.cost_estimated
    assert events[-1].data["text"] == "Có 1 lỗi E."
    assert [e.data["text"] for e in events if e.type == "text"] == ["Có 1 lỗi E."]  # không lặp chữ của `result`

    d = fake.dump()
    # Không có biến xác thực nào trong môi trường tiến trình con (kể cả khi tiến trình cha có).
    assert not [v for v in AUTH_ENV_VARS if v in d["env"]]
    assert d["env"]["MCP_TIMEOUT"] == "60000"
    # Thư mục làm việc của CLI chỉ chứa tệp cấu hình sinh ra; không có DXF. Đã dọn sau phiên.
    assert d["cwd_files"] == ["mcp.json", "settings.json"]
    assert not eng.last_session_dir.exists()
    msg = json.loads(d["stdin"])
    assert msg["type"] == "user" and "Có bao nhiêu lỗi?" in msg["message"]["content"][0]["text"]


def test_claude_command_line_blocks_tools_and_no_bare(fake, tmp_path):
    eng = ClaudeCliEngine(fake("claude"))
    sess = tmp_path / "sess"
    sess.mkdir()
    cmd, stdin, env = eng.build([{"role": "user", "content": "x"}], workspace=fake.ws, allow_propose=True, session_dir=sess)
    args = cmd[2:]
    assert "--bare" not in args
    for flag in ("-p", "--strict-mcp-config", "--verbose", "--no-session-persistence"):
        assert flag in args
    assert args[args.index("--output-format") + 1] == "stream-json"
    assert args[args.index("--input-format") + 1] == "stream-json"
    assert args[args.index("--tools") + 1] == "Skill"
    assert args[args.index("--permission-mode") + 1] == "dontAsk"
    assert args[args.index("--permission-prompts") + 1] == "none"
    allowed = args[args.index("--allowedTools") + 1:args.index("--disallowedTools")]
    assert allowed == ["mcp__cad-guard__*"]
    denied = args[args.index("--disallowedTools") + 1:args.index("--permission-mode")]
    assert set(denied) == set(CLAUDE_DENY)
    for tool in ("Bash", "PowerShell", "Read", "Write", "Edit", "Glob", "Grep", "WebFetch", "WebSearch", "Agent"):
        assert tool in denied
    prompt = args[args.index("--append-system-prompt") + 1]
    assert "cad-guard" in prompt and "Quy tắc cứng" in prompt
    mcp = json.loads((sess / "mcp.json").read_text(encoding="utf-8"))
    server = mcp["mcpServers"]["cad-guard"]
    assert server["command"] == sys.executable
    assert server["args"][:4] == ["-m", "cadguard", "mcp", "--workspace"]
    assert "--allow-propose" in server["args"] and "--no-anonymize" not in server["args"]
    assert Path(server["env"]["PYTHONPATH"], "cadguard").is_dir()
    settings = json.loads((sess / "settings.json").read_text(encoding="utf-8"))
    assert settings["permissions"]["defaultMode"] == "dontAsk" and "Bash" in settings["permissions"]["deny"]
    assert settings["autoMemoryEnabled"] is False


def test_claude_mcp_not_connected_is_vietnamese_error(fake):
    events = _run(ClaudeCliEngine(fake("claude", "noconn")), fake.ws)
    err = next(e for e in events if e.type == "error")
    assert err.data["code"] == "mcp_not_connected" and "chưa kết nối" in err.data["message"]
    assert not [e for e in events if e.type == "tool_call"]  # dừng ngay, không đọc tiếp
    assert events[-1].type == "done"


def test_claude_not_logged_in(fake):
    events = _run(ClaudeCliEngine(fake("claude", "notlogged")), fake.ws)
    err = [e for e in events if e.type == "error"]
    assert err and err[0].data["code"] == "not_logged_in" and "claude auth login" in err[0].data["message"]


def test_claude_timeout_kills_process(fake):
    eng = ClaudeCliEngine(fake("claude", "sleep"), timeout=2)
    events = _run(eng, fake.ws)
    err = next(e for e in events if e.type == "error")
    assert err.data["code"] == "timeout" and "thời hạn" in err.data["message"]
    assert events[-1].type == "done"


def test_claude_cancel(fake):
    eng = ClaudeCliEngine(fake("claude", "sleep"), timeout=60)
    cancel = CancelToken()
    timer = threading.Timer(1.5, cancel.cancel)
    timer.start()
    t0 = time.monotonic()
    out = list(eng.run([{"role": "user", "content": "x"}], workspace=fake.ws, cancel=cancel))
    assert time.monotonic() - t0 < 25  # không chờ tiến trình ngủ 30 giây
    assert any(e.type == "error" and e.data["code"] == "cancelled" for e in out)
    assert out[-1].type == "done" and not eng.last_session_dir.exists()


def test_profile_compare_adds_baseline_server(fake, tmp_path):
    prof = Path(__file__).resolve().parents[3] / "bench" / "ho-so" / "cong-ty-bench.yaml"
    eng = ClaudeCliEngine(fake("claude"))
    sess = tmp_path / "s2"
    sess.mkdir()
    cmd, _, _ = eng.build([{"role": "user", "content": "x"}], workspace=fake.ws, profile=prof, compare_without_profile=True,
                          server_options={"max_entity_records": 5, "stream_threshold_mb": 0}, session_dir=sess)
    servers = json.loads((sess / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    assert set(servers) == {"cad-guard", "cad-guard-goc"}
    assert "--profile" in servers["cad-guard"]["args"] and "--profile" not in servers["cad-guard-goc"]["args"]
    assert "--max-entity-records" in servers["cad-guard"]["args"]
    allowed = cmd[cmd.index("--allowedTools") + 1:cmd.index("--disallowedTools")]
    assert allowed == ["mcp__cad-guard__*", "mcp__cad-guard-goc__*"]


def test_history_is_flattened_into_prompt(fake):
    eng = ClaudeCliEngine(fake("claude"))
    msgs = [{"role": "user", "content": "câu 1"}, {"role": "assistant", "content": "đáp 1"}, {"role": "user", "content": "câu 2"}]
    list(eng.run(msgs, workspace=fake.ws))
    text = json.loads(fake.dump()["stdin"])["message"]["content"][0]["text"]
    assert text.index("câu 1") < text.index("đáp 1") < text.index("câu 2")


# ---------- Codex ----------


def test_codex_requires_experimental(fake):
    events = _run(CodexCliEngine(fake("codex")), fake.ws)
    assert events[0].type == "error" and events[0].data["code"] == "experimental_required"
    assert "thử nghiệm" in events[0].data["message"].lower() and "OpenAI" in events[0].data["message"]
    assert not fake.dump_path.exists()  # không khởi chạy tiến trình nào


def test_codex_flags_and_events(fake, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    eng = CodexCliEngine(fake("codex"), experimental=True)
    events = _run(eng, fake.ws)
    assert "error" not in _types(events)
    call = next(e for e in events if e.type == "tool_call")
    assert call.data["name"] == "audit"
    assert next(e for e in events if e.type == "tool_result").data["is_error"] is False
    u = next(e for e in events if e.type == "usage").data["usage"]
    assert (u.input_tokens, u.cache_read_tokens, u.output_tokens) == (40, 10, 5) and u.cost_usd is None
    assert events[-1].data["text"] == "Xong."
    d = fake.dump()
    argv = d["argv"]
    assert argv[:1] == ["exec"] and {"--json", "--skip-git-repo-check", "--ephemeral"} <= set(argv)
    assert argv[argv.index("-s") + 1] == "read-only"
    joined = " ".join(argv)
    for frag in ('approval_policy="never"', "features.shell_tool=false", "mcp_servers.cad-guard.command=",
                 "mcp_servers.cad-guard.startup_timeout_sec=60", "mcp_servers.cad-guard.required=true"):
        assert frag in joined
    assert argv[-1] == "-" and "Có bao nhiêu lỗi?" in d["stdin"]
    assert d["env"].get("CODEX_HOME") == os.environ.get("CODEX_HOME")  # không đặt CODEX_HOME riêng
    assert "OPENAI_API_KEY" not in d["env"]
    assert d["cwd_files"] == ["AGENTS.md"]


def test_codex_mcp_failure(fake):
    events = _run(CodexCliEngine(fake("codex", "noconn"), experimental=True), fake.ws)
    assert any(e.type == "error" and e.data["code"] == "mcp_not_connected" for e in events)


# ---------- Antigravity ----------


def test_agy_refuses_without_declared_account(fake):
    events = _run(AgyCliEngine(fake("agy")), fake.ws)
    assert events[0].data["code"] == "personal_account" and "cá nhân" in events[0].data["message"]
    assert not fake.dump_path.exists()


def test_agy_business_flags_and_result(fake, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    events = _run(AgyCliEngine(fake("agy"), account="business"), fake.ws)
    assert "error" not in _types(events) and events[-1].data["text"] == "Trả lời agy."
    u = next(e for e in events if e.type == "usage").data["usage"]
    assert (u.input_tokens, u.output_tokens, u.cache_read_tokens) == (30, 6, 3)
    d = fake.dump()
    argv = d["argv"]
    assert "--sandbox" in argv and "--settings" in argv and argv[argv.index("--output-format") + 1] == "stream-json"
    assert d["env"]["AGY_CLI_DISABLE_AUTO_UPDATE"] == "true"
    assert "GEMINI_API_KEY" not in d["env"]
    assert sorted(d["cwd_files"]) == [".agents", "settings.json"]


def test_agy_api_key_keeps_users_gemini_key(fake, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    _run(AgyCliEngine(fake("agy"), account="api-key"), fake.ws)
    assert fake.dump()["env"]["GEMINI_API_KEY"] == "test-not-a-real-key"  # của người dùng, cad-guard không đặt


def test_agy_detects_personal_tier(fake):
    events = _run(AgyCliEngine(fake("agy", "personal"), account="business"), fake.ws)
    err = next(e for e in events if e.type == "error")
    assert err.data["code"] == "personal_account"
    assert not [e for e in events if e.type == "text"]


# ---------- phát hiện ----------


def test_detect_missing_cli(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    for name in ("claude-cli", "codex-cli", "agy-cli"):
        d = create_engine(name).detect()
        assert d["installed"] is False and "Chưa cài" in d["note"]
    events = list(create_engine("claude-cli").run([{"role": "user", "content": "x"}], workspace="."))
    assert events[0].data["code"] == "not_installed"


def test_detect_installed_fake(fake):
    d = ClaudeCliEngine(fake("claude")).detect()
    assert d["installed"] is True


def test_bad_workspace_is_error(fake, tmp_path):
    events = _run(ClaudeCliEngine(fake("claude")), tmp_path / "khong-co")
    assert events[0].type == "error" and events[0].data["code"] == "workspace"
