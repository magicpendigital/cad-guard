"""`cadguard mcp-config <máy khách>`: in cấu hình MCP đúng Python và đường dẫn của máy này (không ghi tệp, không khoá).

- `claude-desktop`: khối `mcpServers` cho `claude_desktop_config.json` (mở bằng Settings → Developer → Edit Config).
- `claude-code`: lệnh `claude mcp add` (tên máy chủ đứng TRƯỚC `-e`, xem docs/integrations/claude-code.md).
- `codex`: khối `[mcp_servers.cad-guard]` có `enabled_tools` lấy từ sổ khai báo công cụ.

Python ghi vào cấu hình chọn bằng `choose_python`: chạy bằng Python hệ thống (không venv) mà có `packages/core/.venv`
thì dùng Python của `.venv`, vì Python hệ thống thường không có cadguard và các thư viện. Không có venv nào thì thêm
`PYTHONPATH` trỏ vào `packages/core` để máy khách tìm thấy gói.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .agent import registry

SERVER = "cad-guard"
CLIENTS = ("claude-desktop", "claude-code", "codex")


def _installed() -> bool:
    try:
        from importlib.metadata import PackageNotFoundError, distribution

        distribution("cadguard")
        return True
    except PackageNotFoundError:
        return False


CORE = Path(__file__).resolve().parents[1]  # packages/core


def _in_venv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def _venv_python() -> Path | None:
    for rel in (("Scripts", "python.exe"), ("bin", "python")):
        p = CORE.joinpath(".venv", *rel)
        if p.is_file():
            return p
    return None


def choose_python(python: str | None = None) -> tuple[str, bool]:
    """Chọn Python cho máy chủ MCP. Trả (đường dẫn, có cần PYTHONPATH không).

    Máy khách MCP khởi động máy chủ ở thư mục khác, nên không được dựa vào "đang đứng trong packages/core".
    Thứ tự: `--python` → Python đang chạy nếu là venv → `packages/core/.venv` (bootstrap.ps1 tạo) → Python đang chạy
    kèm PYTHONPATH (chạy từ mã nguồn).
    """
    if python:
        return Path(python).as_posix(), False
    if _in_venv():
        return Path(sys.executable).as_posix(), not _installed()
    venv = _venv_python()
    if venv is not None:
        return venv.as_posix(), False
    return Path(sys.executable).as_posix(), True


def server_entry(workspace: Path, *, profile: Path | None = None, allow_propose: bool = False,
                 python: str | None = None) -> dict:
    ws = Path(workspace).resolve()
    if not ws.is_dir():
        raise ValueError("Thư mục làm việc (--workspace) không tồn tại.")
    args = ["-m", "cadguard", "mcp", "--workspace", ws.as_posix()]
    if profile is not None:
        prof = Path(profile).resolve()
        if not prof.is_file():
            raise ValueError("Tệp hồ sơ công ty (--profile) không tồn tại.")
        args += ["--profile", prof.as_posix()]
    if allow_propose:
        args.append("--allow-propose")
    command, needs_path = choose_python(python)
    entry: dict = {"command": command, "args": args}
    if needs_path:
        entry["env"] = {"PYTHONPATH": CORE.as_posix()}
    return entry


def _toml_str(s: str) -> str:
    return "'" + s + "'" if "'" not in s else json.dumps(s)


def render(client: str, workspace: Path, *, profile: Path | None = None, allow_propose: bool = False,
           python: str | None = None) -> tuple[str, str]:
    """Trả (nội dung in ra stdout, ghi chú cho người dùng in ra stderr)."""
    if client not in CLIENTS:
        raise ValueError(f"Máy khách chưa hỗ trợ: {client}. Có: {', '.join(CLIENTS)}.")
    e = server_entry(workspace, profile=profile, allow_propose=allow_propose, python=python)
    if client == "claude-desktop":
        text = json.dumps({"mcpServers": {SERVER: e}}, ensure_ascii=False, indent=2)
        note = ("Claude Desktop: Settings → Developer → Edit Config, gộp khối trên vào mục \"mcpServers\", lưu, rồi THOÁT hẳn "
                "và mở lại Claude Desktop. Trong cuộc trò chuyện, biểu tượng công cụ phải có 'cad-guard'. Không đặt khoá/token "
                "vào tệp này.")
    elif client == "claude-code":
        env = "".join(f" -e {k}={v}" for k, v in (e.get("env") or {}).items())
        cmd = " ".join(f'"{a}"' if " " in a else a for a in [e["command"], *e["args"]])
        text = f"claude mcp add {SERVER} -s project{env} -- {cmd}"
        note = ("Claude Code: chạy lệnh trên TRONG thư mục làm việc (ghi .mcp.json). Máy chậm: đặt MCP_TIMEOUT=60000 nếu thấy "
                "'Failed to connect'. Mẫu quyền chặn công cụ đọc tệp/shell: knowledge/mcp/claude-code/.claude/settings.json.")
    else:
        names = [s["name"] for s in registry.specs(registry.SpecOptions(allow_propose=allow_propose))]
        lines = [f"[mcp_servers.{SERVER}]", f"command = {_toml_str(e['command'])}",
                 "args = [" + ", ".join(_toml_str(a) for a in e["args"]) + "]",
                 f"cwd = {_toml_str(Path(workspace).resolve().as_posix())}", "startup_timeout_sec = 60",
                 "tool_timeout_sec = 120", "required = true",
                 "enabled_tools = [" + ", ".join(json.dumps(n) for n in names) + "]"]
        if e.get("env"):
            lines.append("env = { " + ", ".join(f"{k} = {_toml_str(v)}" for k, v in e["env"].items()) + " }")
        text = "\n".join(lines)
        note = "Codex: dán vào hồ sơ cấu hình (xem knowledge/mcp/codex/cadguard.config.toml để có thêm khoá chặn shell/web)."
    return text, note


__all__ = ["CLIENTS", "choose_python", "render", "server_entry"]
