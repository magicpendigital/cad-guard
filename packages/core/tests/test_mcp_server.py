"""Test máy chủ MCP stdio (`python -m cadguard mcp`) qua giao thức thật, dùng client của SDK `mcp`.

Chỉ dùng DXF tổng hợp (fixtures.py) và tệp tạo tạm bằng ezdxf. Các test cần SDK tự bỏ qua khi chưa cài
extras [agent]; chạy đủ bằng `python scripts/test.py --extras agent`.
"""

import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import ezdxf
import pytest

import cadguard
from cadguard.agent.tools import MAX_QUERY_BYTES, MAX_QUERY_RECORDS

CORE = Path(cadguard.__file__).resolve().parents[1]
TIMEOUT = 90  # giây cho mỗi phiên/tiến trình con, để test không treo
TOOL_NAMES = {"list_drawings", "audit", "explain_rule", "get_model_summary", "query_model"}
PRIVATE_NAMES = ("PRIVATE_LAYER", "PRIVATE_STYLE", "PRIVATE_BLOCK", "PRIVATE_VALUE", "private_file", "Du_an_PRIVATE")
PRIVATE_REL = "Du_an_PRIVATE/private_file.dxf"

needs_sdk = pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="chưa cài SDK MCP (extras [agent])")


# ---------- môi trường ----------


def _env(home: Path, prefix: list[Path] | None = None, extra: dict | None = None) -> dict:
    paths = [str(p) for p in (prefix or [])] + [str(CORE)]
    env = {"PYTHONPATH": os.pathsep.join(paths), "PYTHONUTF8": "1", "CADGUARD_HOME": str(home)}
    env.update(extra or {})
    return env


def _run_cli(args: list[str], env: dict) -> subprocess.CompletedProcess:
    full = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "CADGUARD_STANDARDS")}
    full.update(env)
    return subprocess.run(
        [sys.executable, "-m", "cadguard", *args], env=full, capture_output=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL
    )


@pytest.fixture(scope="module")
def ws_env(tmp_path_factory):
    """Thư mục làm việc tạm: bản sao vài fixture tổng hợp + tệp 'riêng tư' + tệp nhiều đối tượng."""
    from cadguard import fixtures

    base = tmp_path_factory.mktemp("mcp")
    src = base / "src"
    src.mkdir()
    fixtures.make_all(src)
    ws = base / "ws"
    ws.mkdir()
    for name in ("ok_sheet.dxf", "bad_layers.dxf", "bad_geometry.dxf"):
        shutil.copy(src / name, ws / name)

    doc = ezdxf.new()
    doc.layers.new("PRIVATE_LAYER")
    doc.styles.new("PRIVATE_STYLE")
    block = doc.blocks.new("PRIVATE_BLOCK")
    block.add_attdef("TAG", (0, 0))
    msp = doc.modelspace()
    insert = msp.add_blockref("PRIVATE_BLOCK", (0, 0), dxfattribs={"layer": "PRIVATE_LAYER"})
    insert.add_attrib("TAG", "PRIVATE_VALUE", (0, 0))
    msp.add_text("text", dxfattribs={"style": "PRIVATE_STYLE", "layer": "PRIVATE_LAYER"})
    (ws / "Du_an_PRIVATE").mkdir()
    doc.saveas(ws / PRIVATE_REL)

    many = ezdxf.new()
    for i in range(750):
        many.modelspace().add_line((i, 0), (i, 1))
    many.saveas(ws / "many.dxf")

    (ws / "notes.txt").write_text("không phải DXF", encoding="utf-8")

    outside_dir = base / "outside"
    outside_dir.mkdir()
    ezdxf.new().saveas(outside_dir / "outside.dxf")

    home = base / "home"
    home.mkdir()
    return {"ws": ws, "base": base, "outside": outside_dir / "outside.dxf", "home": home}


# ---------- phiên MCP qua stdio thật ----------


def _session(ws_env, body, args=(), prefix=None, extra_env=None, errlog_name="server.err"):
    """Khởi `python -m cadguard mcp --workspace <ws>` làm tiến trình con, chạy `body(session)` qua client SDK."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "cadguard", "mcp", "--workspace", str(ws_env["ws"]), *args],
        env=_env(ws_env["home"], prefix, extra_env),
        cwd=str(ws_env["base"]),
    )
    errlog_path = ws_env["base"] / errlog_name

    async def main():
        with errlog_path.open("w", encoding="utf-8") as errlog:
            async with stdio_client(params, errlog=errlog) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await body(session)

    async def guarded():
        return await asyncio.wait_for(main(), TIMEOUT)

    result = asyncio.run(guarded())
    return result, errlog_path.read_text(encoding="utf-8", errors="replace")


def _data(res) -> dict:
    assert not res.isError, res.content[0].text
    data = json.loads(res.content[0].text)
    assert res.structuredContent == data
    return data


def _error_text(res) -> str:
    assert res.isError
    return res.content[0].text


# ---------- không cần SDK ----------


def test_help_lists_flags_in_vietnamese(tmp_path):
    proc = _run_cli(["mcp", "--help"], _env(tmp_path))
    out = proc.stdout.decode("utf-8")
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    for flag in ("--workspace", "--no-anonymize", "--standard", "BẮT BUỘC", "ẩn danh"):
        assert flag in out


def test_workspace_is_required(tmp_path):
    proc = _run_cli(["mcp"], _env(tmp_path))
    assert proc.returncode == 2
    assert "--workspace" in proc.stderr.decode("utf-8", "replace")
    assert proc.stdout == b""


def test_missing_sdk_exits_2_with_vietnamese_hint(tmp_path):
    fake = tmp_path / "fake_site"
    (fake / "mcp").mkdir(parents=True)
    (fake / "mcp" / "__init__.py").write_text('raise ImportError("giả lập thiếu SDK mcp")\n', encoding="utf-8")
    ws = tmp_path / "ws"
    ws.mkdir()
    proc = _run_cli(["mcp", "--workspace", str(ws)], _env(tmp_path, prefix=[fake]))
    err = proc.stderr.decode("utf-8", "replace")
    assert proc.returncode == 2, err
    assert proc.stdout == b""
    assert "Thiếu SDK MCP" in err and "pip install cadguard[agent]" in err and "--extras agent" in err


# ---------- giao thức (cần SDK) ----------


@needs_sdk
def test_list_tools_exactly_five_read_only(ws_env):
    async def body(s):
        return (await s.list_tools()).tools

    tools, _ = _session(ws_env, body)
    assert {t.name for t in tools} == TOOL_NAMES and len(tools) == 5
    for t in tools:
        assert t.description and t.inputSchema["type"] == "object"
        assert t.annotations is not None and t.annotations.readOnlyHint is True and t.annotations.destructiveHint is False
    by_name = {t.name: t for t in tools}
    q = by_name["query_model"].inputSchema
    assert {"file", "filter", "limit", "cursor"} <= set(q["properties"]) and q["required"] == ["file"]
    assert q["properties"]["limit"]["maximum"] == MAX_QUERY_RECORDS
    assert "file" in by_name["audit"].inputSchema["required"]
    assert by_name["explain_rule"].inputSchema["required"] == ["rule_id"]


@needs_sdk
def test_call_all_five_tools_shapes(ws_env):
    async def body(s):
        listing = _data(await s.call_tool("list_drawings", {}))
        ids = {d["id"] for d in listing["drawings"]}
        first = sorted(ids)[0]
        return {
            "list": listing,
            "list_sub": _data(await s.call_tool("list_drawings", {"dir": "Du_an_PRIVATE"})),
            "audit": _data(await s.call_tool("audit", {"file": "bad_layers.dxf"})),
            "audit_by_id": _data(await s.call_tool("audit", {"file": first})),
            "explain": _data(await s.call_tool("explain_rule", {"rule_id": "LY-01"})),
            "summary": _data(await s.call_tool("get_model_summary", {"file": "ok_sheet.dxf"})),
            "query": _data(await s.call_tool("query_model", {"file": "bad_layers.dxf", "filter": {"type": ["LINE", "TEXT"]}, "limit": 5})),
            "unknown_rule": _error_text(await s.call_tool("explain_rule", {"rule_id": "ZZ-99"})),
            "bbox": (await s.call_tool("query_model", {"file": "bad_layers.dxf", "filter": {"bbox": [0, 0, 1, 1]}})).isError,
        }

    r, _ = _session(ws_env, body)
    assert set(r["list"]) == {"drawings", "total", "truncated"} and r["list"]["total"] == 5 and not r["list"]["truncated"]
    assert all(set(d) == {"id", "size_bytes"} and d["size_bytes"] > 0 for d in r["list"]["drawings"])
    assert r["list_sub"]["total"] == 1

    a = r["audit"]
    assert set(a) >= {"file", "standard", "version", "counts", "rules_run", "skipped", "findings", "truncated"}
    assert a["standard"] == "furniture-v0" and a["rules_run"] > 0 and a["findings"]
    assert set(a["counts"]) == {"E", "W", "I"} and sum(a["counts"].values()) == len(a["findings"])
    assert all({"rule_id", "severity", "message"} <= set(f) for f in a["findings"])
    assert r["audit_by_id"]["rules_run"] > 0

    e = r["explain"]
    assert e["id"] == "LY-01" and e["title"] and e["severity"] in ("E", "W", "I") and e["description_md"]

    m = r["summary"]
    assert m["layer_count"] > 0 and isinstance(m["entities_by_type"], dict) and isinstance(m["layouts"], list)
    assert len(json.dumps(m).encode()) <= 16384

    q = r["query"]
    assert set(q) == {"items", "next_cursor", "total_matched"} and len(q["items"]) <= 5
    assert all(x["type"] in ("LINE", "TEXT") and "handle" in x for x in q["items"])
    assert "Không tìm thấy mã luật" in r["unknown_rule"]
    assert r["bbox"] is True


def _all_outputs(ws_env, args=(), errlog_name="server.err"):
    async def body(s):
        listing = await s.call_tool("list_drawings", {})
        return [
            listing,
            await s.call_tool("audit", {"file": PRIVATE_REL}),
            await s.call_tool("explain_rule", {"rule_id": "LY-01"}),
            await s.call_tool("get_model_summary", {"file": PRIVATE_REL}),
            await s.call_tool("query_model", {"file": PRIVATE_REL}),
        ]

    results, err = _session(ws_env, body, args=args, errlog_name=errlog_name)
    for res in results:
        assert not res.isError, res.content[0].text
    text = "\n".join(res.content[0].text for res in results) + json.dumps([res.structuredContent for res in results])
    return text, err


@needs_sdk
def test_anonymized_by_default(ws_env):
    text, err = _all_outputs(ws_env)
    ws = str(ws_env["ws"])
    for secret in (*PRIVATE_NAMES, ws, json.dumps(ws)[1:-1], ws.replace("\\", "/")):
        assert secret not in text, secret
    assert "CẢNH BÁO" not in err


@needs_sdk
def test_no_anonymize_shows_names_and_warns(ws_env):
    text, err = _all_outputs(ws_env, args=["--no-anonymize"], errlog_name="server_plain.err")
    assert "PRIVATE_LAYER" in text and "private_file.dxf" in text and "PRIVATE_BLOCK" in text
    assert "CẢNH BÁO" in err and "--no-anonymize" in err


@needs_sdk
def test_query_model_pagination_and_caps(ws_env):
    async def body(s):
        pages, cursor = [], None
        while True:
            args = {"file": "many.dxf", "filter": {"type": "LINE"}, "limit": MAX_QUERY_RECORDS}
            if cursor:
                args["cursor"] = cursor
            page = _data(await s.call_tool("query_model", args))
            pages.append(page)
            cursor = page["next_cursor"]
            if cursor is None or len(pages) > 50:
                break
        too_big = await s.call_tool("query_model", {"file": "many.dxf", "limit": MAX_QUERY_RECORDS + 1})
        bad_cursor = await s.call_tool("query_model", {"file": "many.dxf", "cursor": "khong-hop-le"})
        other_filter = await s.call_tool("query_model", {"file": "many.dxf", "filter": {"type": "TEXT"}, "cursor": pages[0]["next_cursor"]})
        return pages, too_big, bad_cursor, other_filter

    (pages, too_big, bad_cursor, other_filter), _ = _session(ws_env, body)
    assert len(pages) >= 2 and pages[0]["next_cursor"]
    handles = []
    for p in pages:
        assert len(p["items"]) <= MAX_QUERY_RECORDS
        assert len(json.dumps(p, ensure_ascii=True).encode()) <= MAX_QUERY_BYTES
        handles += [x["handle"] for x in p["items"]]
    assert len(handles) == len(set(handles)) == pages[-1]["total_matched"] == 750
    assert too_big.isError
    assert "Con trỏ phân trang" in _error_text(bad_cursor)
    assert "Con trỏ phân trang" in _error_text(other_filter)


SITECUSTOMIZE = '''\
"""Chỉ dùng trong test: giả lập đường dẫn phân giải ra ngoài workspace mà không cần quyền tạo symlink."""
import json
import os
from pathlib import Path

_map = json.loads(os.environ.get("CADGUARD_TEST_RESOLVE_MAP") or "{}")
if _map:
    _orig = Path.resolve

    def _resolve(self, *args, **kwargs):
        target = _map.get(str(self))
        return Path(target) if target else _orig(self, *args, **kwargs)

    Path.resolve = _resolve
'''


@needs_sdk
def test_path_denials(ws_env, tmp_path):
    ws = ws_env["ws"].resolve()
    outside = ws_env["outside"].resolve()
    hook = tmp_path / "hook"
    hook.mkdir()
    (hook / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
    resolve_map = {
        str(ws / "escape" / "outside.dxf"): str(outside),  # phân giải ra ngoài workspace → phải bị chặn
        str(ws / "alias" / "ok.dxf"): str(ws / "ok_sheet.dxf"),  # đối chứng: chứng minh hook có hiệu lực
    }
    cases = {
        "cha": "../outside/outside.dxf",
        "tuyet_doi": str(outside),
        "unc": r"\\server\share\x.dxf",
        "nul": "ok_sheet\x00.dxf",
        "duoi_khac": "notes.txt",
        "phan_giai_ra_ngoai": "escape/outside.dxf",
    }

    async def body(s):
        out = {}
        for key, path in cases.items():
            out[key] = (await s.call_tool("audit", {"file": path}), await s.call_tool("query_model", {"file": path}))
        out["dir_cha"] = (await s.call_tool("list_drawings", {"dir": ".."}),)
        control = await s.call_tool("get_model_summary", {"file": "alias/ok.dxf"})
        return out, control

    (out, control), _ = _session(
        ws_env, body, prefix=[hook], extra_env={"CADGUARD_TEST_RESOLVE_MAP": json.dumps(resolve_map)}, errlog_name="server_paths.err"
    )
    assert not control.isError, "hook giả lập phân giải không có hiệu lực"
    assert set(out) == {*cases, "dir_cha"}
    for key, results in out.items():
        for res in results:
            msg = _error_text(res)
            assert "đường dẫn" in msg.lower(), (key, msg)
            for leak in (str(outside), str(ws), str(ws_env["base"]), outside.name, "Traceback"):
                assert leak not in msg, (key, msg)


@needs_sdk
def test_stdout_carries_only_jsonrpc(ws_env):
    """Đọc stdout thô: mọi dòng phải là JSON-RPC; thông báo khởi động nằm ở stderr."""
    full = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "CADGUARD_STANDARDS")}
    full.update(_env(ws_env["home"]))
    proc = subprocess.Popen(
        [sys.executable, "-m", "cadguard", "mcp", "--workspace", str(ws_env["ws"])],
        env=full, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(ws_env["base"]),
    )
    watchdog = threading.Timer(TIMEOUT, proc.kill)
    watchdog.start()
    try:
        def send(msg):
            proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
            proc.stdin.flush()

        def until(msg_id):
            while True:
                line = proc.stdout.readline()
                assert line, "máy chủ đóng stdout trước khi trả lời"
                msg = json.loads(line)
                assert msg["jsonrpc"] == "2.0"
                if msg.get("id") == msg_id:
                    return msg

        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}})
        assert until(1)["result"]["serverInfo"]["name"] == "cad-guard"
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "audit", "arguments": {"file": "bad_layers.dxf"}}})
        reply = until(2)
        assert reply["result"]["isError"] is False
        proc.stdin.close()
        rest, err = proc.stdout.read(), proc.stderr.read()
        assert proc.wait(TIMEOUT) == 0
    finally:
        watchdog.cancel()
        if proc.poll() is None:
            proc.kill()
    for line in rest.decode("utf-8").splitlines():
        if line.strip():
            assert json.loads(line)["jsonrpc"] == "2.0"
    assert "đang phục vụ qua stdio" in err.decode("utf-8", "replace")
