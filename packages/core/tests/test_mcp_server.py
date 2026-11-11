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
TOOL_NAMES = {"list_drawings", "audit", "explain_rule", "get_model_summary", "query_model", "diff", "get_scene", "measure",
              "list_ergonomic_checks", "get_drawing_graph"}
PRIVATE_NAMES = ("PRIVATE_LAYER", "PRIVATE_STYLE", "PRIVATE_BLOCK", "PRIVATE_VALUE", "private_file", "Du_an_PRIVATE")
PRIVATE_REL = "Du_an_PRIVATE/private_file.dxf"
# Nội dung bản vẽ (chữ, toạ độ) trong tệp riêng tư: Bậc 1 không được đưa ra cho trợ lý (trường mới text/pos/pts/insert).
PRIVATE_CONTENT = ("PRIVATE_NOTE", "PRIVATE_MTEXT", "riêng tư", "424242.4242", "434343.4343",
                   "454545.4545", "464646.4646")

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
    msp.add_text("PRIVATE_NOTE riêng tư", dxfattribs={"insert": (424242.4242, 434343.4343)})
    msp.add_mtext("PRIVATE_MTEXT riêng tư", dxfattribs={"insert": (454545.4545, 464646.4646)})
    msp.add_line((424242.4242, 0), (454545.4545, 1))
    msp.add_lwpolyline([(434343.4343, 0), (464646.4646, 5), (0, 5)])
    msp.add_blockref("PRIVATE_BLOCK", (464646.4646, 424242.4242), dxfattribs={"rotation": 30})
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
        # Mặc định đã là chế độ nội bộ (quyết định 10/11/2026); các test ở đây kiểm ẩn danh nên bật tường minh.
        args=["-m", "cadguard", "mcp", "--workspace", str(ws_env["ws"]),
              *([] if "--no-anonymize" in args or "--internal-default" in args else ["--anonymize"]),
              *[x for x in args if x != "--internal-default"]],
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
    for flag in ("--workspace", "--no-anonymize", "--standard", "BẮT BUỘC", "ẩn danh", "--stream-threshold-mb", "--max-entity-records", "theo dòng"):
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
def test_list_tools_default_six_read_only_no_write(ws_env):
    async def body(s):
        return (await s.list_tools()).tools

    tools, _ = _session(ws_env, body)
    assert {t.name for t in tools} == TOOL_NAMES and len(tools) == 10
    assert "propose_changeset" not in {t.name for t in tools} and "apply_changeset" not in {t.name for t in tools}
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
    assert set(q) == {"items", "next_cursor", "total_matched", "records_capped"} and len(q["items"]) <= 5
    assert q["records_capped"] is False and a["records_capped"] is False and m["records_capped"] is False
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
def test_anonymized_when_enabled(ws_env):
    text, err = _all_outputs(ws_env)
    ws = str(ws_env["ws"])
    for secret in (*PRIVATE_NAMES, *PRIVATE_CONTENT, ws, json.dumps(ws)[1:-1], ws.replace("\\", "/")):
        assert secret not in text, secret
    assert '"pts"' not in text and '"pos"' not in text and '"insert"' not in text
    assert "CẢNH BÁO" not in err


@needs_sdk
def test_internal_mode_is_default_and_shows_names(ws_env):
    text, err = _all_outputs(ws_env, args=["--internal-default"], errlog_name="server_plain.err")
    assert "PRIVATE_LAYER" in text and "private_file.dxf" in text and "PRIVATE_BLOCK" in text
    assert "PRIVATE_NOTE" in text and "424242.4242" in text  # chế độ nội bộ: thấy cả chữ, toạ độ
    assert "chế độ nội bộ" in err and "--anonymize" in err


def _every_tool_on_every_file(ws_env, args, errlog_name):
    """Gọi 5 công cụ đọc từng tệp (trừ diff) trên mọi DXF của workspace (query_model lấy hết các trang) qua giao thức thật."""

    async def body(s):
        listing = _data(await s.call_tool("list_drawings", {}))
        out = {"list_drawings": listing, "explain_rule": _data(await s.call_tool("explain_rule", {"rule_id": "LY-01"}))}
        for d in sorted(listing["drawings"], key=lambda x: x["id"]):
            pages, cursor = [], None
            while True:
                q = {"file": d["id"], "limit": MAX_QUERY_RECORDS}
                if cursor:
                    q["cursor"] = cursor
                page = _data(await s.call_tool("query_model", q))
                pages.append(page)
                cursor = page["next_cursor"]
                if cursor is None or len(pages) > 50:
                    break
            out[d["id"]] = {
                "audit": _data(await s.call_tool("audit", {"file": d["id"]})),
                "get_model_summary": _data(await s.call_tool("get_model_summary", {"file": d["id"]})),
                "query_model": pages,
            }
        return out

    result, _ = _session(ws_env, body, args=args, errlog_name=errlog_name)
    return result


@needs_sdk
def test_stream_threshold_zero_matches_ezdxf_over_protocol(ws_env):
    """--stream-threshold-mb 0 (luôn theo dòng) cho đúng kết quả như số âm (luôn ezdxf) trên cả 5 công cụ đọc từng tệp (trừ diff)."""
    plain = ["--no-anonymize"]  # mã ẩn danh có muối ngẫu nhiên theo phiên; so tên thật giữa hai tiến trình
    stream = _every_tool_on_every_file(ws_env, [*plain, "--stream-threshold-mb", "0"], "server_stream.err")
    ezdxf_ = _every_tool_on_every_file(ws_env, [*plain, "--stream-threshold-mb", "-1"], "server_ezdxf.err")
    assert len(stream) == 2 + 5
    assert stream == ezdxf_


@needs_sdk
def test_stream_records_capped_and_anonymized_over_protocol(ws_env):
    async def body(s):
        return (
            await s.call_tool("audit", {"file": PRIVATE_REL}),
            await s.call_tool("get_model_summary", {"file": PRIVATE_REL}),
            await s.call_tool("query_model", {"file": PRIVATE_REL}),
            await s.call_tool("query_model", {"file": "many.dxf"}),
        )

    results, _ = _session(
        ws_env, body, args=["--stream-threshold-mb", "0", "--max-entity-records", "1"], errlog_name="server_capped.err"
    )
    data = [_data(r) for r in results]
    assert all(d["records_capped"] is True for d in data)
    assert data[3]["total_matched"] == 1
    text = "\n".join(r.content[0].text for r in results)
    ws = str(ws_env["ws"])
    for secret in (*PRIVATE_NAMES, ws, json.dumps(ws)[1:-1], ws.replace("\\", "/")):
        assert secret not in text, secret


@needs_sdk
def test_anonymized_on_stream_path(ws_env):
    text, _ = _all_outputs(ws_env, args=["--stream-threshold-mb", "0"], errlog_name="server_stream_anon.err")
    ws = str(ws_env["ws"])
    for secret in (*PRIVATE_NAMES, *PRIVATE_CONTENT, ws, json.dumps(ws)[1:-1], ws.replace("\\", "/")):
        assert secret not in text, secret


def test_bad_max_entity_records_rejected(tmp_path):
    proc = _run_cli(["mcp", "--workspace", str(tmp_path), "--max-entity-records", "-3"], _env(tmp_path))
    assert proc.returncode == 2 and proc.stdout == b""
    assert "không âm" in proc.stderr.decode("utf-8", "replace")


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf"])
def test_non_finite_threshold_refuses_to_start(tmp_path, bad):
    proc = _run_cli(["mcp", "--workspace", str(tmp_path), f"--stream-threshold-mb={bad}"], _env(tmp_path))
    err = proc.stderr.decode("utf-8", "replace")
    assert proc.returncode == 2 and proc.stdout == b"", err
    assert "--stream-threshold-mb" in err and "hữu hạn" in err


EXAMPLE_PROFILE = CORE.parents[1] / "standards" / "company-profile.example.yaml"


def _bad_profiles(tmp_path: Path) -> list[Path]:
    base = "schema: cg.company-profile/1\nname: cong-ty-thu\nversion: 0.0.1\nstandard: design-hygiene-v0\n"
    cases = {
        "sai_kieu.yaml": base + "overrides:\n  VS-02:\n    max_text_styles: nhieu\n",
        "luat_la.yaml": base + "overrides:\n  VS-99:\n    x: 1\n",
        "truong_la.yaml": base + "bi_an: 1\n",
        "khong_yaml.yaml": "a: [1,\n",
    }
    out = []
    for name, text in cases.items():
        p = tmp_path / name
        p.write_text(text, encoding="utf-8")
        out.append(p)
    out.append(tmp_path / "khong_co.yaml")
    return out


def test_bad_profile_refuses_to_start(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    for p in _bad_profiles(tmp_path):
        proc = _run_cli(["mcp", "--workspace", str(ws), "--profile", str(p)], _env(tmp_path))
        err = proc.stderr.decode("utf-8", "replace")
        assert proc.returncode == 2 and proc.stdout == b"", (p.name, err)
        assert "Không khởi động máy chủ MCP" in err and "hồ sơ" in err.lower(), (p.name, err)
        assert str(tmp_path) not in err  # chỉ tên tệp, không đường dẫn đầy đủ
    # Hồ sơ đúng nhưng --standard khác chuẩn của hồ sơ
    proc = _run_cli(["mcp", "--workspace", str(ws), "--profile", str(EXAMPLE_PROFILE), "--standard", "furniture-v0"], _env(tmp_path))
    assert proc.returncode == 2 and proc.stdout == b""
    assert "design-hygiene-v0" in proc.stderr.decode("utf-8", "replace")


@needs_sdk
def test_profile_changes_audit_over_protocol(ws_env):
    async def body(s):
        return {
            "hygiene": _data(await s.call_tool("audit", {"file": "bad_layers.dxf", "standard": "design-hygiene-v0"})),
            "default": _data(await s.call_tool("audit", {"file": "bad_layers.dxf"})),
            "furniture": _data(await s.call_tool("audit", {"file": "bad_layers.dxf", "standard": "furniture-v0"})),
            "explain": _data(await s.call_tool("explain_rule", {"rule_id": "VS-02", "standard": "design-hygiene-v0"})),
        }

    plain, _ = _session(ws_env, body, errlog_name="server_noprofile.err")
    prof, err = _session(ws_env, body, args=["--profile", str(EXAMPLE_PROFILE)], errlog_name="server_profile.err")

    # Không hồ sơ: chọn được design-hygiene-v0 qua tham số; mặc định vẫn furniture-v0.
    assert plain["hygiene"]["standard"] == "design-hygiene-v0" and plain["hygiene"]["profile"] is None
    assert plain["default"]["standard"] == "furniture-v0" and plain["default"]["profile"] is None
    # Có hồ sơ: chuẩn mặc định thành chuẩn của hồ sơ, kết quả ghi tên/phiên bản hồ sơ.
    expected = {"name": "cong-ty-mau", "version": "0.1.0"}
    assert prof["hygiene"]["profile"] == expected and prof["default"]["standard"] == "design-hygiene-v0"
    assert prof["default"]["profile"] == expected
    assert prof["hygiene"]["counts"] != plain["hygiene"]["counts"] or prof["hygiene"]["findings"] != plain["hygiene"]["findings"]
    # Chuẩn khác chuẩn của hồ sơ: không áp hồ sơ.
    assert prof["furniture"]["profile"] is None and prof["furniture"]["counts"] == plain["default"]["counts"]
    assert prof["explain"]["profile"] == expected and plain["explain"]["profile"] is None
    assert prof["explain"]["rule_params"]["max_text_styles"] == 20
    assert prof["explain"]["rule_params"] != plain["explain"]["rule_params"]
    # Không lộ đường dẫn hồ sơ.
    text = json.dumps(prof, ensure_ascii=False)
    for leak in (str(EXAMPLE_PROFILE), EXAMPLE_PROFILE.as_posix(), "company-profile.example"):
        assert leak not in text
    assert "cong-ty-mau" in err


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


# ---------- A2: propose_changeset (--allow-propose) và diff ----------


@pytest.fixture
def hyg_env(tmp_path):
    """Thư mục làm việc riêng: hygiene_bad.dxf + một tệp ra do NGƯỜI áp dụng (gọi lõi trong tiến trình test)."""
    from cadguard import fixtures
    from cadguard.agent.workspace import Workspace
    from cadguard.changeset import apply, propose

    ws = tmp_path / "ws"
    ws.mkdir()
    fixtures.make_hygiene_bad(ws / "hygiene_bad.dxf")
    w = Workspace(ws)
    cs, _ = propose(w, "hygiene_bad.dxf", [{"op": "set_bylayer", "filter": {"layers": ["SYN-TUONG"]}}])
    out = apply(w, cs.id, confirm=True)["output"]["path"]
    home = tmp_path / "home"
    home.mkdir()
    return {"ws": ws, "base": tmp_path, "home": home, "out": out}


@needs_sdk
def test_allow_propose_tools_tokens_and_diff(hyg_env):
    import re

    async def body(s):
        tools = (await s.list_tools()).tools
        aud = _data(await s.call_tool("audit", {"file": "hygiene_bad.dxf", "standard": "design-hygiene-v0"}))
        vs07 = next(f for f in aud["findings"] if f["rule_id"] == "VS-07")
        bad_style = re.search(r"S_[0-9a-f]{10}", vs07["message"]).group()
        texts = _data(await s.call_tool("query_model", {"file": "hygiene_bad.dxf", "filter": {"type": "TEXT"}}))["items"]
        good_style = next(t["text_style"] for t in texts if t["text_style"] != bad_style)
        ops = [{"op": "replace_text_style", "from": [bad_style], "to": good_style},
               {"op": "move_to_layer", "filter": {"layers": ["0"], "spaces": ["Model"]}, "target": texts[0]["layer"]}]
        return {
            "tools": tools,
            "propose": await s.call_tool("propose_changeset", {"file": "hygiene_bad.dxf", "ops": ops}),
            "bad_token": await s.call_tool("propose_changeset", {"file": "hygiene_bad.dxf",
                                                                 "ops": [{"op": "move_to_layer", "target": "L_0123456789"}]}),
            "bad_op": await s.call_tool("propose_changeset", {"file": "hygiene_bad.dxf", "ops": [{"op": "delete_all"}]}),
            "diff": await s.call_tool("diff", {"a": "hygiene_bad.dxf", "b": hyg_env["out"]}),
        }

    r, err = _session(hyg_env, body, args=["--allow-propose"], errlog_name="server_propose.err")
    names = {t.name for t in r["tools"]}
    assert names == TOOL_NAMES | {"propose_changeset", "propose_translation"} and "apply_changeset" not in names
    ann = {t.name: t.annotations for t in r["tools"]}
    assert ann["propose_changeset"].readOnlyHint is False and ann["propose_changeset"].destructiveHint is False
    assert ann["diff"].readOnlyHint is True
    assert "đề xuất changeset" in err

    p = _data(r["propose"])
    assert p["ok"] and p["rules_regressed"] == 0 and {"VS-03", "VS-07"} <= set(p["rules"]["resolved"])
    assert p["file"].startswith("F_") and "cadguard apply" in p["apply"]
    d = _data(r["diff"])
    assert d["summary"]["changed"] == 4 and set(d["summary"]["changed_by_attr"]) == {"color", "lineweight"}
    text = r["propose"].content[0].text + r["diff"].content[0].text
    for secret in ("SYN-", "hygiene_bad", str(hyg_env["ws"]), "OpenSans"):
        assert secret not in text, secret
    assert "không khớp tên nào" in _error_text(r["bad_token"])
    assert "không có trong từ vựng" in _error_text(r["bad_op"])

    stored = json.loads((hyg_env["ws"] / ".cadguard" / "changesets" / f"{p['changeset_id']}.json").read_text(encoding="utf-8"))
    assert stored["created_by"] == "agent" and stored["source"]["path"] == "hygiene_bad.dxf"
    assert stored["ops"][0]["from"] == ["SYN-VN-SHX"] and stored["ops"][0]["to"] == "SYN-CHU"
    assert stored["ops"][1]["target"] == "SYN-CHU"
    assert len(list(hyg_env["ws"].glob("*.dxf"))) == 2  # MCP không ghi DXF: chỉ gốc + tệp người dùng đã áp


@needs_sdk
def test_propose_absent_without_flag(hyg_env):
    async def body(s):
        return await s.call_tool("propose_changeset", {"file": "hygiene_bad.dxf", "ops": [{"op": "purge_unused"}]})

    res, _ = _session(hyg_env, body, errlog_name="server_noprop.err")
    assert res.isError
    assert not (hyg_env["ws"] / ".cadguard" / "changesets").exists() or len(list((hyg_env["ws"] / ".cadguard" / "changesets").glob("*.json"))) == 2


# ---------- một nguồn khai báo: MCP và engine API trùng nhau ----------


@needs_sdk
def test_mcp_tools_identical_to_engine_toolbox(ws_env):
    """Tên, mô tả, schema và cờ chỉ đọc của MCP phải trùng hệt `ToolBox` của engine API (cùng `agent.registry`)."""
    from cadguard.assistant.toolspec import ToolBox

    async def body(s):
        return (await s.list_tools()).tools

    for args, allow in (((), False), (("--allow-propose",), True)):
        tools, _ = _session(ws_env, body, args=args, errlog_name=f"server_parity_{allow}.err")
        box = ToolBox(ws_env["ws"], allow_propose=allow)
        mcp_view = [(t.name, t.description, t.inputSchema, t.annotations.readOnlyHint) for t in tools]
        api_view = [(s["name"], s["description"], s["schema"], s["read_only"]) for s in box.specs()]
        assert mcp_view == api_view
        assert not {"apply_changeset", "apply", "undo"} & {t.name for t in tools}


@needs_sdk
def test_bad_arguments_rejected_in_vietnamese_without_echo(ws_env):
    async def body(s):
        return [
            await s.call_tool("audit", {"file": "ok_sheet.dxf", "standard": "BI_MAT/../x"}),
            await s.call_tool("audit", {"file": "ok_sheet.dxf", "la": "BI_MAT"}),
            await s.call_tool("audit", {}),
            await s.call_tool("query_model", {"file": "ok_sheet.dxf", "limit": "BI_MAT"}),
        ]

    results, _ = _session(ws_env, body, errlog_name="server_badargs.err")
    msgs = [_error_text(r) for r in results]
    assert "sai định dạng" in msgs[0] and "Tham số lạ" in msgs[1] and "Thiếu tham số bắt buộc: file" in msgs[2]
    assert "phải là integer" in msgs[3]
    for m in msgs:
        assert "BI_MAT" not in m and "validation" not in m.lower()
