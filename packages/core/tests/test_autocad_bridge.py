"""Cầu nối AutoCAD theo tệp (M1 + M2): `cadguard watch`, báo cáo có lệnh CGTOI, `cadguard.lsp`, `mcp-config`, `doctor`,
đo MCP qua stdio. Chỉ DXF tổng hợp; không cần AutoCAD (phần chạy trong AutoCAD kiểm tay theo docs/autocad.md)."""
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import cadguard
from cadguard import contracts, fixtures, watch
from cadguard.agent import registry
from cadguard.agent.tools import load_model
from cadguard.mcp_config import render, server_entry
from cadguard.standard import load_standard

CORE = Path(cadguard.__file__).resolve().parents[1]
STDS = CORE.parents[1] / "standards"
LSP = CORE / "cadguard" / "autocad" / "cadguard.lsp"
needs_sdk = pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="chưa cài SDK MCP (extras [agent])")


@pytest.fixture
def ws(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    fixtures.make_all(src)
    d = tmp_path / "phien"
    d.mkdir()
    for name in ("ok_sheet.dxf", "bad_layers.dxf", "hygiene_bad.dxf"):
        shutil.copy(src / name, d / name)
    return d


# ---------- cadguard watch ----------

def test_watch_once_writes_reports_matching_contract(ws):
    std = load_standard("furniture-v0", STDS)
    (ws / "bad_layers.cg-0123abcd.dxf").write_bytes((ws / "bad_layers.dxf").read_bytes())  # tệp ra của changeset: bỏ qua
    (ws / ".cadguard").mkdir()
    shutil.copy(ws / "ok_sheet.dxf", ws / ".cadguard" / "an.dxf")  # thư mục ẩn: bỏ qua
    events = watch.Watcher(ws, std).poll(settle=False)
    assert sorted(e.rel for e in events) == ["bad_layers.dxf", "hygiene_bad.dxf", "ok_sheet.dxf"]
    for e in events:
        assert e.ok and e.html.is_file()
        html, js = watch.report_paths(ws, e.rel)
        rep = json.loads(js.read_text(encoding="utf-8"))
        expect = contracts.audit_report(load_model(ws / e.rel), std)
        assert rep["files"][0]["counts"] == expect.counts == e.counts
    bad_html = watch.report_paths(ws, "bad_layers.dxf")[0].read_text(encoding="utf-8")
    assert "CGTOI " in bad_html  # người dùng gõ được lệnh phóng tới đối tượng trong AutoCAD


def test_watch_waits_until_file_is_stable_and_reaudits_on_change(ws, tmp_path):
    std = load_standard("furniture-v0", STDS)
    seen = []
    w = watch.Watcher(ws, std, on_event=seen.append)
    w.poll(settle=False)
    seen.clear()
    assert w.poll() == []  # không đổi gì: không kiểm lại
    new = ws / "sub" / "moi.dxf"
    new.parent.mkdir()
    shutil.copy(ws / "bad_layers.dxf", new)
    assert w.poll() == []  # lần đầu thấy: chờ đứng yên
    ev = w.poll()
    assert [e.rel for e in ev] == ["sub/moi.dxf"] and ev[0].ok
    assert watch.report_paths(ws, "sub/moi.dxf")[0].name == "sub__moi.html"
    shutil.copy(ws / "ok_sheet.dxf", new)
    os.utime(new, ns=(new.stat().st_atime_ns, new.stat().st_mtime_ns + 5_000_000_000))
    assert w.poll() == []
    assert [e.rel for e in w.poll()] == ["sub/moi.dxf"]


def test_watch_survives_broken_dxf(ws):
    (ws / "hong.dxf").write_text("KHÔNG PHẢI DXF", encoding="utf-8")
    events = watch.Watcher(ws, load_standard("furniture-v0", STDS)).poll(settle=False)
    broken = [e for e in events if e.rel == "hong.dxf"]
    assert broken and not broken[0].ok and "Không đọc được" in broken[0].error
    assert all(e.ok for e in events if e.rel != "hong.dxf")


def test_watch_cli_once(ws):
    env = dict(os.environ, PYTHONPATH=str(CORE), PYTHONUTF8="1", CADGUARD_HOME=str(ws.parent / "home"))
    r = subprocess.run([sys.executable, "-m", "cadguard", "watch", str(ws), "--once"], env=env, capture_output=True,
                       text=True, encoding="utf-8", timeout=180)
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("lỗi,") == 3 and "luật" in r.stdout


# ---------- cadguard.lsp ----------

def _strip_lisp(src: str) -> str:
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == ";":
            while i < n and src[i] != "\n":
                i += 1
        elif c == '"':
            i += 1
            while i < n and src[i] != '"':
                i += 2 if src[i] == "\\" else 1
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def test_lisp_defines_commands_and_never_modifies_drawing():
    src = LSP.read_text(encoding="utf-8")
    code = _strip_lisp(src)
    depth = 0
    for ch in code:
        depth += {"(": 1, ")": -1}.get(ch, 0)
        assert depth >= 0
    assert depth == 0
    for cmd in ("CGTHUMUC", "CGXUAT", "CGTOI", "CGDEN", "CGBAOCAO"):
        assert re.search(rf"\(defun c:{cmd}\b", code)
    # Lệnh AutoCAD nằm trong chuỗi ("_.DXFOUT"), nên kiểm trên mã đã bỏ chú thích nhưng GIỮ chuỗi.
    no_comments = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith(";"))
    low = no_comments.lower()
    assert "vla-" not in low and "vlax-" not in low  # không ActiveX: chạy được trên AutoCAD LT 2024+
    for forbidden in ("saveas", "qsave", "_.save", "erase", "entmod", "entdel", "entmake", "_.purge", "_.close", "_.u\""):
        assert forbidden not in low, forbidden
    assert '"_.DXFOUT"' in no_comments and "(handent " in no_comments
    # Kiểm tay AutoCAD 2027 (09/11/2026): thư mục gõ dạng D:/... làm CGBAOCAO mở Documents thay vì báo cáo.
    assert re.search(r'\(defun cg:join .*?\(cg:winpath', no_comments, re.S)
    # CGXUAT không xoá-rồi-ghi-đè khi bản đang mở chính là tệp DXF trong thư mục làm việc.
    xuat = no_comments[no_comments.index("(defun c:CGXUAT"):no_comments.index("(defun cg:split")]
    assert xuat.index('"DWGPREFIX"') < xuat.index("vl-file-delete")
    # cg:den (M2 gõ CGDEN, M3 gọi qua COM) đọc tệp yêu cầu UTF-8 và kiểm đúng bản vẽ trước khi chọn.
    den = no_comments[no_comments.index("(defun cg:den"):no_comments.index("(defun c:CGDEN")]
    assert '(open path "r" "utf8")' in den and "(cg:base)" in den and "(close fd)" in den


def test_lisp_help_covers_every_command():
    """CGHELP liệt kê mọi lệnh c:CG… của tệp LSP (và lệnh của plugin .NET), mỗi lệnh có hướng dẫn chi tiết."""
    src = LSP.read_text(encoding="utf-8")
    code = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith(";"))
    defined = set(re.findall(r"\(defun c:(CG[A-Z]+)\b", code))
    assert "CGHELP" in defined
    helped = set(re.findall(r'\(list "(CG[A-Z]+)" "', code))
    assert defined <= helped, defined - helped
    plugin_cs = CORE.parent / "acad-plugin" / "CadGuardPlugin.cs"
    if plugin_cs.exists():
        net_cmds = set(re.findall(r'\[CommandMethod\("(CG[A-Z]+)"', plugin_cs.read_text(encoding="utf-8")))
        assert net_cmds and net_cmds <= helped, net_cmds - helped
    assert "Gõ CGHELP" in code


def test_autocad_command_copies_lisp(tmp_path):
    env = dict(os.environ, PYTHONPATH=str(CORE), PYTHONUTF8="1")
    r = subprocess.run([sys.executable, "-m", "cadguard", "autocad", "--copy-to", str(tmp_path)], env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "cadguard.lsp").read_bytes() == LSP.read_bytes() and "CGTOI" in r.stdout


# ---------- mcp-config ----------

def test_mcp_config_outputs(ws, tmp_path):
    desk, note = render("claude-desktop", ws, python="C:/Py/python.exe")
    entry = json.loads(desk)["mcpServers"]["cad-guard"]
    assert entry["command"] == "C:/Py/python.exe" and entry["args"][:4] == ["-m", "cadguard", "mcp", "--workspace"]
    assert Path(entry["args"][4]) == ws.resolve() and "--allow-propose" not in entry["args"]
    assert "khoá" in note
    code, _ = render("claude-code", ws, python="C:/Py/python.exe")
    assert code.startswith("claude mcp add cad-guard -s project")
    if " -e " in code:  # tên máy chủ phải đứng trước -e (bẫy đã gặp)
        assert code.index("cad-guard") < code.index(" -e ")
    toml, _ = render("codex", ws, python="C:/Py/python.exe", allow_propose=True)
    tools = json.loads(re.search(r"enabled_tools = (\[.*\])", toml).group(1))
    assert tools == [*registry.READ_TOOLS, registry.PROPOSE_TOOL]
    assert "--allow-propose" in toml
    with pytest.raises(ValueError):
        server_entry(tmp_path / "khong-co")
    with pytest.raises(ValueError):
        server_entry(ws, profile=tmp_path / "khong-co.yaml")
    for text in (desk, code, toml):
        assert not re.search(r"(api[_-]?key|token|sk-)", text, re.IGNORECASE)


def test_mcp_config_prefers_project_venv_over_system_python(tmp_path, monkeypatch):
    """Bẫy đã gặp: chạy `python -m cadguard mcp-config` bằng Python hệ thống trong packages/core in ra Python không có
    cadguard (thấy gói chỉ nhờ thư mục hiện tại) → máy khách MCP không kết nối được."""
    from cadguard import mcp_config

    core = tmp_path / "core"
    venv_py = core / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("", encoding="utf-8")
    monkeypatch.setattr(mcp_config, "CORE", core)
    monkeypatch.setattr(mcp_config, "_in_venv", lambda: False)
    entry = mcp_config.server_entry(tmp_path)
    assert entry["command"] == venv_py.as_posix() and "env" not in entry
    venv_py.unlink()  # không có .venv: dùng Python đang chạy + PYTHONPATH
    entry = mcp_config.server_entry(tmp_path)
    assert entry["command"] == Path(sys.executable).as_posix() and entry["env"] == {"PYTHONPATH": core.as_posix()}
    monkeypatch.setattr(mcp_config, "_in_venv", lambda: True)  # đang chạy trong venv: giữ nguyên Python đó
    assert mcp_config.server_entry(tmp_path)["command"] == Path(sys.executable).as_posix()
    assert mcp_config.server_entry(tmp_path, python="C:/X/python.exe")["command"] == "C:/X/python.exe"


# ---------- doctor + đo MCP ----------

def test_doctor_reports_required_items():
    from cadguard.doctor import checks

    res = checks(probe_mcp=False)
    names = {c["name"] for c in res}
    assert {"Python 3.10–3.14", "Thư viện ezdxf", "SDK MCP (extras [agent])", "Tệp AutoLISP cadguard.lsp",
            "Nạp máy chủ MCP"} <= names
    assert next(c for c in res if c["name"] == "Tệp AutoLISP cadguard.lsp")["ok"]
    json.dumps(res, ensure_ascii=False)


@needs_sdk
def test_mcp_probe_over_real_stdio(ws):
    from cadguard.mcp_probe import evaluate, probe

    m = probe(ws, calls=12, timeout=240)
    assert m["tools"] == list(registry.READ_TOOLS) and m["drawings"] == 3
    assert m["errors"] == 0 and m["calls"] == 12
    assert m["startup_s"] < 30 and m["est_tokens"] < 10_000  # thời gian chặt (≤ 5 s) đo bằng scripts/mcp_smoke.py
    assert len(evaluate(m)) == 4


# ---------- tới đối tượng trong AutoCAD: tệp yêu cầu (M2) + COM (M3) ----------

from cadguard.autocad import bridge  # noqa: E402


def test_goto_request_validates_and_writes_utf8(tmp_path):
    req = bridge.make_request("sub/Bản vẽ.dxf", ["18e", "18E", "3A247"], ["Tường-01", "KYHIEU"])
    assert req.drawing == "Bản vẽ" and req.handles == ["18E", "3A247"] and req.toi_command() == "CGTOI 18E,3A247"
    p = bridge.write_goto(tmp_path, req)
    assert p == tmp_path.resolve() / ".cadguard" / "goto.txt"
    want = ["F Bản vẽ", "H 18E", "H 3A247", "L Tường-01", "L KYHIEU", ""]
    assert p.read_bytes() == chr(10).join(want).encode("utf-8")  # UTF-8 không BOM, xuống dòng LF
    for bad in ({"handles": ["18G"]}, {"handles": ["(command)"]}, {"layers": ["a" + chr(10) + "H 1"]}, {"layers": [""]}, {}):
        with pytest.raises(bridge.BridgeError):
            bridge.make_request("a.dxf", **bad)
    big = bridge.make_request("a.dxf", [format(i, "X") for i in range(1, 300)])
    assert len(big.handles) == bridge.MAX_HANDLES and big.truncated


def test_lisp_call_is_single_fixed_expression(tmp_path):
    call = bridge.lisp_call(tmp_path / ".cadguard" / "goto.txt")
    assert call.startswith("(progn ") and call.endswith(chr(10)) and call.count(chr(10)) == 1  # một dòng = một lệnh
    assert '(cg:den "' in call and chr(92) + chr(92) not in call  # đường dẫn dạng /
    for forbidden in ("(command", "save", "erase", "entmod", "entdel", "vla-"):
        assert forbidden not in call.lower()


class FakeDoc:
    def __init__(self, name, busy=0):
        self.Name, self.busy, self.sent, self.activated = name, busy, [], False

    def GetVariable(self, name):
        assert name == "CMDACTIVE"
        return self.busy

    def Activate(self):
        self.activated = True

    def SendCommand(self, text):
        self.sent.append(text)


class FakeAcad:
    HWND = 1234

    def __init__(self, *docs):
        self.Documents = list(docs)
        self.ActiveDocument = docs[0]


def test_show_sends_one_expression_to_matching_open_drawing(tmp_path):
    other, target = FakeDoc("khac.dwg"), FakeDoc("BAD_LAYERS.dxf")
    acad, raised = FakeAcad(other, target), []
    r = bridge.show(tmp_path, "bad_layers.dxf", ["B6"], connect=lambda: acad, foreground=raised.append)
    assert r["sent"] and r["toi_command"] == "CGTOI B6" and raised == [1234]
    assert target.activated and other.sent == [] and target.sent == [bridge.lisp_call(bridge.goto_path(tmp_path))]


def test_show_falls_back_to_cgden_when_autocad_unavailable(tmp_path):
    def none():
        raise bridge.BridgeError("Không thấy AutoCAD đang chạy. Gõ CGDEN trong AutoCAD.")

    r = bridge.show(tmp_path, "a.dxf", layers=["0"], connect=none)
    assert not r["sent"] and "CGDEN" in r["message"] and bridge.goto_path(tmp_path).is_file()
    r = bridge.show(tmp_path, "a.dxf", ["1F"], connect=lambda: FakeAcad(FakeDoc("khac.dwg")))
    assert not r["sent"] and "chưa mở" in r["message"]
    busy = FakeDoc("a.dwg", busy=1)
    r = bridge.show(tmp_path, "a.dxf", ["1F"], connect=lambda: FakeAcad(busy), foreground=lambda h: None)
    assert not r["sent"] and "Esc" in r["message"] and busy.sent == []

    class Broken(FakeDoc):
        def SendCommand(self, text):
            raise OSError("RPC_E_CALL_REJECTED C:/bi-mat")

    r = bridge.show(tmp_path, "a.dxf", ["1F"], connect=lambda: FakeAcad(Broken("a.dwg")), foreground=lambda h: None)
    assert not r["sent"] and "bi-mat" not in r["message"]
    r = bridge.show(tmp_path, "a.dxf", ["1F"], com=False)
    assert not r["sent"] and "CGDEN" in r["message"]


def test_app_show_in_autocad_writes_request(ws):
    from cadguard.app.api import ApiError, AppConfig, AppData, show_in_autocad

    app = AppData(AppConfig(workspace=ws, autocad_com=False, standards_dir=STDS))
    r = show_in_autocad(app, "bad_layers.dxf", ["B6"], None)
    assert r["written"] and not r["sent"]
    assert (ws / ".cadguard" / "goto.txt").read_text(encoding="utf-8").splitlines() == ["F bad_layers", "H B6"]
    with pytest.raises(ApiError):
        show_in_autocad(app, "../ngoai.dxf", ["B6"], None)
    with pytest.raises(ApiError):
        show_in_autocad(app, "bad_layers.dxf", None, None)


def test_show_in_autocad_tool_is_opt_in_and_anonymized(ws, monkeypatch):
    from cadguard.agent.anonymize import Anonymizer
    from cadguard.agent.tools import ToolContext
    from cadguard.agent.workspace import Workspace

    assert registry.AUTOCAD_TOOL not in {d.name for d in registry.tool_defs(registry.SpecOptions())}
    opts = registry.SpecOptions(allow_autocad=True)
    d = {x.name: x for x in registry.tool_defs(opts)}[registry.AUTOCAD_TOOL]
    assert d.kind == "navigate" and not d.read_only
    ctx = ToolContext(Workspace(ws), Anonymizer(enabled=True), STDS)
    sent = []
    monkeypatch.setattr(bridge, "send_via_com", lambda drawing, path, **k: sent.append(drawing))
    assert registry.call(ctx, "list_drawings", {}, opts).ok
    fid = ctx.anonymizer.token("file", "bad_layers.dxf")
    res = registry.call(ctx, registry.AUTOCAD_TOOL, {"file": fid, "layers": [ctx.anonymizer.token("layer", "Wall")],
                                                     "handles": ["B6"]}, opts)
    assert res.ok, res.error
    assert res.data["sent"] and sent == ["bad_layers"] and res.data["file"] == fid
    text = res.text()
    assert "Wall" not in text and "bad_layers" not in text and "goto" not in text  # Bậc 1: không tên thật
    lines = (ws / ".cadguard" / "goto.txt").read_text(encoding="utf-8").splitlines()
    assert lines == ["F bad_layers", "H B6", "L Wall"]  # mã L_… đã giải mã về tên thật cho AutoCAD
    assert not registry.call(ctx, registry.AUTOCAD_TOOL, {"file": fid, "handles": ["(command)"]}, opts).ok
    assert not registry.call(ctx, registry.AUTOCAD_TOOL, {"file": fid, "layers": ["L_0000000000"]}, opts).ok
