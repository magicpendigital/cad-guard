"""Engine CLI (cách B): khởi chạy CLI nguyên bản người dùng đã cài và đã TỰ đăng nhập.

Nguyên tắc (xem docs/integrations/*.md, docs/assistant.md):
- Luôn chạy tệp chạy đã cài trên máy (`shutil.which`), KHÔNG đóng gói kèm, KHÔNG sửa.
- KHÔNG đọc/ghi/chuyển token, KHÔNG đặt biến xác thực; còn gỡ các biến xác thực khỏi môi trường tiến trình con
  (trừ `agy --account api-key`, khi đó giữ nguyên `GEMINI_API_KEY` sẵn có của người dùng).
- Mỗi phiên một thư mục làm việc TẠM chỉ chứa tệp cấu hình sinh ra; MCP trỏ tới
  `python -m cadguard mcp --workspace <ws>` bằng `sys.executable` và PYTHONPATH của cad-guard.
- Chặn công cụ trên DÒNG LỆNH (không chỉ trong tệp); có thời hạn phía cad-guard; huỷ được (giết cả cây tiến trình).
"""
from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Iterator, Sequence

from . import events as ev
from .base import (AUTH_ENV_VARS, CancelToken, Engine, EngineError, EngineInfo, check_server_options, flatten_history,
                   load_system_prompt, normalize_messages, resolve_session)
from .events import Event, Usage

SERVER = "cad-guard"
BASELINE_SERVER = "cad-guard-goc"
DEFAULT_TIMEOUT_S = 600.0
STDERR_KEEP = 16384

# Công cụ dựng sẵn của Claude Code bị gỡ (docs/integrations/claude-code.md mục 2.2).
CLAUDE_DENY = ("Bash", "PowerShell", "Monitor", "Read", "Edit", "Write", "NotebookEdit", "Glob", "Grep", "LSP",
               "WebFetch", "WebSearch", "Agent", "Workflow", "Artifact", "SendUserFile", "RemoteTrigger", "CronCreate",
               "EnterWorktree")
CLAUDE_BUILTIN_TOOLS = "Skill"  # mục 3.2: `--tools "Skill"` — mọi công cụ dựng sẵn khác không tồn tại trong phiên

NOT_LOGGED_IN = re.compile(r"not logged in|please run /login|/login|authentication required|unauthori[sz]ed|"
                           r"invalid api key|no codex credentials|please log ?in|login required|sign in", re.I)


def cadguard_pythonpath() -> str:
    """Thư mục chứa gói `cadguard` (để máy chủ MCP chạy được cả khi cad-guard chạy từ mã nguồn)."""
    return str(Path(__file__).resolve().parents[2])


def mcp_command(workspace: Path, *, profile: Path | None, standard: str | None, allow_propose: bool,
                options: dict | None = None) -> list[str]:
    args = [sys.executable, "-m", "cadguard", "mcp", "--workspace", workspace.as_posix()]
    opts = options or {}
    if opts.get("anonymize") is False:
        args.append("--no-anonymize")
    if opts.get("stream_threshold_mb") is not None:
        args += ["--stream-threshold-mb", f"{float(opts['stream_threshold_mb']):g}"]
    if opts.get("max_entity_records") is not None:
        args += ["--max-entity-records", str(int(opts["max_entity_records"]))]
    if profile is not None:
        args += ["--profile", profile.as_posix()]
    elif standard:
        args += ["--standard", standard]
    if allow_propose:
        args.append("--allow-propose")
    return args


def mcp_env() -> dict:
    pp = cadguard_pythonpath()
    return {"PYTHONPATH": pp.replace("\\", "/"), "PYTHONUTF8": "1"}


def child_env(extra: dict | None = None, keep_auth: Sequence[str] = ()) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in AUTH_ENV_VARS or k in keep_auth}
    env["PYTHONUTF8"] = "1"
    env.update(extra or {})
    return env


def _kill_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=15)
        else:
            proc.kill()
    except Exception:  # noqa: BLE001
        pass
    try:
        proc.kill()
    except Exception:  # noqa: BLE001
        pass


class StreamProcess:
    """Tiến trình con phát JSON theo dòng ra stdout; đọc không chặn, có thời hạn và huỷ."""

    def __init__(self, cmd: list[str], *, cwd: Path, env: dict, stdin_text: str | None):
        kwargs = {}
        if os.name != "nt":
            kwargs["start_new_session"] = True
        try:
            self.proc = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, **kwargs)
        except OSError:
            raise EngineError("Không khởi chạy được CLI (tệp chạy không chạy được trên máy này).", "spawn") from None
        self.lines: queue.Queue = queue.Queue()
        self.stderr_buf = bytearray()
        threading.Thread(target=self._read_out, daemon=True).start()
        threading.Thread(target=self._read_err, daemon=True).start()
        try:
            if stdin_text is not None:
                self.proc.stdin.write(stdin_text.encode("utf-8"))
            self.proc.stdin.close()
        except OSError:
            pass

    def _read_out(self) -> None:
        for raw in iter(self.proc.stdout.readline, b""):
            self.lines.put(raw.decode("utf-8", "replace").rstrip("\r\n"))
        self.lines.put(None)

    def _read_err(self) -> None:
        for raw in iter(self.proc.stderr.readline, b""):
            if len(self.stderr_buf) < STDERR_KEEP:
                self.stderr_buf += raw

    @property
    def stderr(self) -> str:
        return self.stderr_buf.decode("utf-8", "replace")

    def iter_lines(self, deadline: float, cancel: CancelToken | None) -> Iterator[str]:
        """Sinh từng dòng; ném TimeoutError / InterruptedError khi quá hạn / bị huỷ (đã giết tiến trình)."""
        while True:
            if cancel is not None and cancel.cancelled:
                self.kill()
                raise InterruptedError
            if time.monotonic() > deadline:
                self.kill()
                raise TimeoutError
            try:
                line = self.lines.get(timeout=0.1)
            except queue.Empty:
                continue
            if line is None:
                return
            yield line

    def wait(self, timeout: float = 10.0) -> int:
        try:
            return self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.kill()
            return -1

    def kill(self) -> None:
        _kill_tree(self.proc)


def _to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_to_text(c.get("text", "") if isinstance(c, dict) else c) for c in content)
    if isinstance(content, dict):
        if "content" in content:
            return _to_text(content["content"])
        return json.dumps(content, ensure_ascii=False)
    return "" if content is None else str(content)


class CliEngine(Engine):
    """Phần chung của engine CLI. Lớp con dựng dòng lệnh, tệp cấu hình và phân tích luồng JSON."""

    exe_name = ""
    install_hint = ""
    login_hint = ""
    version_args: tuple[str, ...] = ("--version",)
    status_args: tuple[str, ...] | None = None

    def __init__(self, executable: str | Sequence[str] | None = None, *, model: str | None = None,
                 timeout: float = DEFAULT_TIMEOUT_S, keep_session_dir: bool = False, experimental: bool = False):
        self._executable = executable
        self.experimental = bool(experimental)
        self.model = model
        self.timeout = float(timeout)
        self.keep_session_dir = keep_session_dir
        self.last_command: list[str] | None = None
        self.last_env: dict | None = None
        self.last_session_dir: Path | None = None

    # ---------- phát hiện ----------

    def command_prefix(self) -> list[str]:
        if self._executable:
            return [self._executable] if isinstance(self._executable, str) else list(self._executable)
        path = shutil.which(self.exe_name)
        if not path:
            raise EngineError(f"Chưa cài `{self.exe_name}` (không thấy trong PATH). {self.install_hint}", "not_installed")
        return [path]

    def detect(self) -> dict:
        """{installed, version, logged_in (True/False/None = không biết), note}. Không đọc tệp xác thực."""
        try:
            prefix = self.command_prefix()
        except EngineError as exc:
            return {"installed": False, "version": None, "logged_in": None, "note": str(exc)}
        version = None
        try:
            out = subprocess.run([*prefix, *self.version_args], capture_output=True, timeout=30, stdin=subprocess.DEVNULL,
                                 env=child_env(self.extra_env()))
            text = (out.stdout or out.stderr).decode("utf-8", "replace").strip()
            version = text.splitlines()[0] if text else None
        except (OSError, subprocess.TimeoutExpired):
            pass
        logged = None
        if self.status_args:
            try:
                st = subprocess.run([*prefix, *self.status_args], capture_output=True, timeout=30, stdin=subprocess.DEVNULL,
                                    env=child_env(self.extra_env()))
                logged = st.returncode == 0  # chỉ dùng mã thoát, không in/lưu nội dung (có thể có email)
            except (OSError, subprocess.TimeoutExpired):
                logged = None
        note = "" if logged is not False else self.login_hint
        return {"installed": True, "version": version, "logged_in": logged, "note": note}

    # ---------- dành cho lớp con ----------

    def extra_env(self) -> dict:
        return {}

    def keep_auth_env(self) -> tuple[str, ...]:
        return ()

    def check_allowed(self) -> None:
        """Ném EngineError nếu engine không được phép chạy với cấu hình hiện tại."""

    def prepare(self, session_dir: Path, prompt: str, server_cmds: dict[str, list[str]]) -> tuple[list[str], str | None]:
        """Ghi tệp cấu hình vào thư mục phiên, trả (đối số sau tệp chạy, nội dung stdin)."""
        raise NotImplementedError

    def parse(self, obj: dict, state: dict) -> Iterator[Event]:
        raise NotImplementedError

    # ---------- chạy ----------

    def build(self, messages: list[dict], *, workspace, standard=None, profile=None, allow_propose=False,
              compare_without_profile=False, server_options=None, session_dir: Path) -> tuple[list[str], str | None, dict]:
        """Dựng dòng lệnh + stdin + env (không chạy). Dùng cho run() và cho test kiểm dòng lệnh."""
        msgs = normalize_messages(messages)
        ws, prof = resolve_session(workspace, profile)
        opts = check_server_options(server_options)
        servers = {SERVER: mcp_command(ws, profile=prof, standard=standard, allow_propose=allow_propose, options=opts)}
        if compare_without_profile and prof is not None:
            servers[BASELINE_SERVER] = mcp_command(ws, profile=None, standard=None, allow_propose=False, options=opts)
        prompt = flatten_history(msgs)
        if compare_without_profile and prof is not None:
            prompt += (f"\n\n(Máy chủ `{SERVER}` áp hồ sơ công ty; máy chủ `{BASELINE_SERVER}` KHÔNG áp hồ sơ — "
                       "dùng nó để lấy kết quả 'trước khi áp hồ sơ'.)")
        if standard:
            prompt += f"\n\n(Chuẩn người dùng chọn: {standard}.)"
        args, stdin_text = self.prepare(session_dir, prompt, servers)
        env = child_env(self.extra_env(), self.keep_auth_env())
        return [*self.command_prefix(), *args], stdin_text, env

    def run(self, messages, *, workspace, standard=None, profile=None, allow_propose=False,
            compare_without_profile=False, server_options=None, cancel: CancelToken | None = None) -> Iterator[Event]:
        session_dir = Path(tempfile.mkdtemp(prefix="cadguard-ai-"))
        self.last_session_dir = session_dir
        holder: dict = {"proc": None, "final": ""}
        try:
            yield from self._run(messages, session_dir, holder, workspace=workspace, standard=standard, profile=profile,
                                 allow_propose=allow_propose, compare_without_profile=compare_without_profile,
                                 server_options=server_options, cancel=cancel)
        finally:
            # Dọn dẹp cả khi bên gọi dừng giữa chừng (đóng generator): giết tiến trình, xoá thư mục phiên.
            if holder["proc"] is not None:
                holder["proc"].kill()
            if not self.keep_session_dir:
                shutil.rmtree(session_dir, ignore_errors=True)
        yield ev.done(holder["final"])

    def _run(self, messages, session_dir, holder, *, workspace, standard, profile, allow_propose,
             compare_without_profile, server_options, cancel) -> Iterator[Event]:
        try:
            self.check_allowed()
            cmd, stdin_text, env = self.build(messages, workspace=workspace, standard=standard, profile=profile,
                                              allow_propose=allow_propose, compare_without_profile=compare_without_profile,
                                              server_options=server_options, session_dir=session_dir)
            self.last_command, self.last_env = cmd, env
            proc = holder["proc"] = StreamProcess(cmd, cwd=session_dir, env=env, stdin_text=stdin_text)
        except EngineError as exc:
            yield ev.error(str(exc), exc.code)
            return
        state: dict = {"texts": [], "errored": False}
        try:
            for line in proc.iter_lines(time.monotonic() + self.timeout, cancel):
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                for e in self.parse(obj, state):
                    if e.type == "error":
                        state["errored"] = True
                    yield e
                if state.get("abort"):
                    proc.kill()
                    break
        except TimeoutError:
            yield ev.error(f"Quá thời hạn {self.timeout:g} giây; đã dừng {self.exe_name}.", "timeout")
            state["errored"] = True
        except InterruptedError:
            yield ev.error("Đã huỷ theo yêu cầu.", "cancelled")
            state["errored"] = True
        code = proc.wait()
        holder["final"] = final_text = state.get("final") or "\n".join(state["texts"])
        if not state["errored"] and code not in (0, None) and not final_text:
            yield ev.error(self.explain_failure(code, proc.stderr), "exit")
        elif not state["errored"] and not final_text and NOT_LOGGED_IN.search(proc.stderr or ""):
            yield ev.error(self.login_hint, "not_logged_in")

    def explain_failure(self, code: int, stderr: str) -> str:
        if NOT_LOGGED_IN.search(stderr or ""):
            return self.login_hint
        return f"`{self.exe_name}` thoát với mã {code} mà không có câu trả lời. Chạy thử `{self.exe_name}` trong terminal để xem lỗi."


# ====================== Claude Code ======================


class ClaudeCliEngine(CliEngine):
    """`claude -p` stream-json, đăng nhập thuê bao/khoá do người dùng tự cấu hình trong Claude Code. KHÔNG `--bare`."""

    info = EngineInfo(
        "claude-cli", "cli", "Claude Code (đăng nhập của bạn)",
        "Được phép rõ nhất: chạy binary Claude Code không sửa, mỗi người tự đăng nhập bằng tài khoản/khoá của chính họ, "
        "tự chịu cước (Anthropic Legal and compliance). cad-guard không chạm token, không đóng gói kèm. "
        "Hạn mức gói Pro/Max giả định dùng cá nhân thông thường.",
    )
    exe_name = "claude"
    install_hint = "Cài Claude Code bằng bộ cài chính thức của Anthropic rồi chạy `claude auth login`."
    login_hint = "Claude Code chưa đăng nhập. Mở terminal, chạy `claude auth login`, rồi thử lại."
    status_args = ("auth", "status")

    def extra_env(self) -> dict:
        return {"MCP_TIMEOUT": "60000"}  # máy chủ cad-guard khởi động ~9–20 s trên Windows

    def prepare(self, session_dir, prompt, servers):
        mcp = {"mcpServers": {name: {"type": "stdio", "command": cmd[0], "args": cmd[1:], "env": mcp_env()}
                              for name, cmd in servers.items()}}
        (session_dir / "mcp.json").write_text(json.dumps(mcp, ensure_ascii=False, indent=2), encoding="utf-8")
        allow = [f"mcp__{name}__*" for name in servers]
        settings = {  # như mẫu knowledge/mcp/claude-code/.claude/settings.json; chặn chính vẫn nằm trên dòng lệnh
            "allowedMcpServers": [{"serverName": name} for name in servers],
            "autoMemoryEnabled": False,
            "permissions": {"defaultMode": "dontAsk", "disableBypassPermissionsMode": "disable", "disableAutoMode": "disable",
                            "blockReadsOutsideWorkingDirectories": True, "blockWritesOutsideWorkingDirectories": True,
                            "allow": allow, "deny": list(CLAUDE_DENY)},
        }
        (session_dir / "settings.json").write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
        args = ["-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                "--mcp-config", str(session_dir / "mcp.json"), "--strict-mcp-config",
                "--settings", str(session_dir / "settings.json"),
                "--tools", CLAUDE_BUILTIN_TOOLS,
                "--allowedTools", *allow,
                "--disallowedTools", *CLAUDE_DENY,
                "--permission-mode", "dontAsk", "--permission-prompts", "none",
                "--no-session-persistence",
                "--append-system-prompt", load_system_prompt(include_skills=False)]
        if self.model:
            args += ["--model", self.model]
        msg = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": prompt}]}}
        return args, json.dumps(msg, ensure_ascii=False) + "\n"

    def parse(self, obj, state):
        kind = obj.get("type")
        if kind == "system" and obj.get("subtype") == "init":
            servers = {s.get("name"): s.get("status") for s in obj.get("mcp_servers") or [] if isinstance(s, dict)}
            if servers.get(SERVER) != "connected":
                state["abort"] = True
                status = servers.get(SERVER) or "không có trong danh sách"
                yield ev.error(f"Máy chủ cad-guard chưa kết nối với Claude Code (trạng thái: {status}). Kiểm extras "
                               "[agent] (`pip install cadguard[agent]`) và thử lại; máy chậm có thể cần lâu hơn để khởi động.",
                               "mcp_not_connected")
        elif kind == "assistant":
            for block in (obj.get("message") or {}).get("content") or []:
                if block.get("type") == "text" and block.get("text"):
                    state["texts"].append(block["text"])
                    yield ev.text(block["text"])
                elif block.get("type") == "tool_use":
                    yield Event("tool_call", {"id": block.get("id"), "name": block.get("name"), "arguments": block.get("input") or {}})
        elif kind == "user":
            content = (obj.get("message") or {}).get("content")
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    yield Event("tool_result", {"id": block.get("tool_use_id"), "name": None,
                                                "content": _to_text(block.get("content")), "is_error": bool(block.get("is_error"))})
        elif kind == "result":
            u = obj.get("usage") or {}
            usage = Usage(int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0),
                          int(u.get("cache_read_input_tokens") or 0), int(u.get("cache_creation_input_tokens") or 0),
                          obj.get("total_cost_usd"), True)
            yield ev.usage(usage)
            result = obj.get("result")
            if obj.get("is_error") or (obj.get("subtype") and obj.get("subtype") != "success"):
                text = result if isinstance(result, str) else ""
                if NOT_LOGGED_IN.search(text):
                    yield ev.error(self.login_hint, "not_logged_in")
                else:
                    yield ev.error(f"Claude Code báo lỗi ({obj.get('subtype') or 'error'}).", "cli_error")
            elif isinstance(result, str):
                if not state["texts"]:
                    yield ev.text(result)
                state["final"] = result


# ====================== Codex CLI ======================


def _toml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


class CodexCliEngine(CliEngine):
    """`codex exec --json`, THỬ NGHIỆM: điều khoản OpenAI cho ứng dụng bên thứ ba dùng đăng nhập ChatGPT chưa rõ."""

    info = EngineInfo(
        "codex-cli", "cli", "Codex CLI (đăng nhập của bạn) — thử nghiệm",
        "CHƯA RÕ: OpenAI không có văn bản cho/cấm ứng dụng bên thứ ba khởi chạy Codex nguyên bản bằng đăng nhập ChatGPT "
        "của người dùng; đường chính thức cho ứng dụng thương mại là chương trình Sign in with ChatGPT. Chỉ bật khi tự "
        "chấp nhận rủi ro (--experimental); ưu tiên khoá API của tổ chức. Mã Codex: Apache-2.0.",
        experimental=True,
    )
    exe_name = "codex"
    install_hint = "Cài Codex CLI bằng bộ cài chính thức của OpenAI rồi chạy `codex login`."
    login_hint = "Codex chưa đăng nhập. Mở terminal, chạy `codex login`, rồi thử lại."
    status_args = ("login", "status")

    def check_allowed(self):
        if not self.experimental:
            raise EngineError("Engine codex-cli đang ở chế độ THỬ NGHIỆM vì điều khoản của OpenAI cho ứng dụng bên thứ ba "
                              "dùng đăng nhập ChatGPT chưa rõ. Bật bằng --experimental nếu bạn chấp nhận rủi ro, hoặc dùng "
                              "engine API `openai` với khoá của tổ chức.", "experimental_required")

    def prepare(self, session_dir, prompt, servers):
        # Lời nhắc hệ thống: Codex nạp AGENTS.md ở gốc thư mục làm việc (đã kiểm bằng `codex debug prompt-input`).
        (session_dir / "AGENTS.md").write_text(load_system_prompt(include_skills=True), encoding="utf-8")
        args = ["exec", "--json", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config",
                "-C", str(session_dir), "-s", "read-only",
                "-c", 'approval_policy="never"',
                "-c", "features.shell_tool=false", "-c", "features.view_image=false",
                "-c", 'web_search="disabled"']
        for name, cmd in servers.items():
            key = f"mcp_servers.{name}"
            env = ", ".join(f"{k} = {_toml_str(v)}" for k, v in mcp_env().items())
            args += ["-c", f"{key}.command={_toml_str(cmd[0])}",
                     "-c", f"{key}.args=[{', '.join(_toml_str(a) for a in cmd[1:])}]",
                     "-c", f"{key}.env={{ {env} }}",
                     "-c", f"{key}.startup_timeout_sec=60", "-c", f"{key}.tool_timeout_sec=120",
                     "-c", f"{key}.required=true"]
        if self.model:
            args += ["-m", self.model]
        args.append("-")  # đọc lời nhắc từ stdin
        return args, prompt

    def parse(self, obj, state):
        kind = obj.get("type", "")
        item = obj.get("item") or {}
        itype = item.get("type")
        if kind in ("item.started", "item.completed") and itype == "mcp_tool_call":
            name = item.get("tool")
            if kind == "item.started":
                yield Event("tool_call", {"id": item.get("id"), "name": name, "arguments": item.get("arguments") or {}})
            else:
                err = item.get("error")
                content = _to_text((err or {}).get("message") if err else item.get("result"))
                yield Event("tool_result", {"id": item.get("id"), "name": name, "content": content,
                                            "is_error": bool(err) or item.get("status") == "failed"})
        elif kind == "item.completed" and itype == "agent_message" and item.get("text"):
            state["texts"].append(item["text"])
            yield ev.text(item["text"])
        elif kind == "item.completed" and itype in ("command_execution", "file_change"):
            # Không được xảy ra (shell tắt, sandbox read-only) — ghi lại để người dùng thấy.
            yield ev.error("Codex cố dùng công cụ ngoài cad-guard (đã bị chặn bởi cấu hình phiên).", "foreign_tool")
        elif kind == "turn.completed":
            u = obj.get("usage") or {}
            cached = int(u.get("cached_input_tokens") or 0)
            yield ev.usage(Usage(max(0, int(u.get("input_tokens") or 0) - cached), int(u.get("output_tokens") or 0),
                                 cached, 0, None, True))
        elif kind in ("turn.failed", "error"):
            msg = (obj.get("error") or {}).get("message") if isinstance(obj.get("error"), dict) else obj.get("message")
            msg = msg or ""
            if re.search(r"mcp", msg, re.I) and SERVER in msg:
                state["abort"] = True
                yield ev.error("Máy chủ cad-guard chưa kết nối với Codex (khởi động MCP thất bại). Kiểm extras [agent] "
                               "và thử lại.", "mcp_not_connected")
            elif NOT_LOGGED_IN.search(msg):
                yield ev.error(self.login_hint, "not_logged_in")
            else:
                yield ev.error("Codex báo lỗi khi chạy lượt này.", "cli_error")


# ====================== Antigravity CLI ======================

PERSONAL_TIER = re.compile(r"personal|consumer|individual|free|google[-_ ]?one|oauth-personal", re.I)
AGY_ACCOUNTS = ("business", "api-key")


def _find_tier(obj) -> str | None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in ("tier", "auth_method", "authmethod", "account_type") and isinstance(v, str):
                return v
            found = _find_tier(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_tier(v)
            if found:
                return found
    return None


class AgyCliEngine(CliEngine):
    """`agy -p` stream-json. TỪ CHỐI tài khoản Google cá nhân (FAQ Antigravity cấm bọc agy trong ứng dụng bên thứ ba)."""

    info = EngineInfo(
        "agy-cli", "cli", "Antigravity CLI (tài khoản doanh nghiệp/khoá API)",
        "CẤM với tài khoản Google cá nhân: FAQ Antigravity nói bọc `agy` trong ứng dụng bên thứ ba không được hỗ trợ với "
        "gói cá nhân, điều khoản mục 6 có thể dẫn tới khoá tài khoản. Chỉ chạy khi khai báo --account business (quản trị "
        "tổ chức đã đồng ý) hoặc --account api-key. agy là phần mềm độc quyền của Google; không đóng gói kèm.",
    )
    exe_name = "agy"
    install_hint = "Cài Antigravity CLI từ trang chính thức của Google rồi đăng nhập bằng tài khoản doanh nghiệp hoặc khoá API."
    login_hint = "Antigravity CLI chưa đăng nhập ('authentication required'). Chạy `agy` trong terminal để đăng nhập, rồi thử lại."

    def __init__(self, executable=None, *, account: str | None = None, **kwargs):
        super().__init__(executable, **kwargs)
        self.account = account

    def extra_env(self) -> dict:
        return {"AGY_CLI_DISABLE_AUTO_UPDATE": "true"}

    def keep_auth_env(self) -> tuple[str, ...]:
        return ("GEMINI_API_KEY",) if self.account == "api-key" else ()

    def check_allowed(self):
        if self.account not in AGY_ACCOUNTS:
            raise EngineError("Engine agy-cli bị từ chối: Google không cho bọc `agy` trong ứng dụng bên thứ ba với tài khoản "
                              "cá nhân (FAQ Antigravity). Chỉ chạy khi bạn khai báo rõ --account business (tài khoản "
                              "Gemini Enterprise/Google Cloud, quản trị đã đồng ý) hoặc --account api-key.", "personal_account")

    def prepare(self, session_dir, prompt, servers):
        agents = session_dir / ".agents"
        agents.mkdir()
        mcp = {"mcpServers": {name: {"command": cmd[0], "args": cmd[1:], "env": mcp_env(), "timeoutSeconds": 120,
                                     "disabled": False} for name, cmd in servers.items()}}
        (agents / "mcp_config.json").write_text(json.dumps(mcp, ensure_ascii=False, indent=2), encoding="utf-8")
        settings = {
            "toolPermission": "request-review", "agentMode": "", "allowNonWorkspaceAccess": False, "enableTerminalSandbox": True,
            "permissions": {"allow": [f"mcp({name}/*)" for name in servers], "ask": [],
                            "deny": ["read_file(*)", "write_file(*)", "command(*)", "read_url(*)", "execute_url(*)"]},
        }
        if self.account == "api-key":
            settings["modelProvider"] = "gemini"
        (session_dir / "settings.json").write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
        full = load_system_prompt(include_skills=False) + "\n\n---\n\n" + prompt
        args = ["-p", full, "--output-format", "stream-json", "--settings", str(session_dir / "settings.json"),
                "--sandbox", "--print-timeout", f"{int(self.timeout)}s"]
        if self.model:
            args += ["--model", self.model]
        return args, None

    def parse(self, obj, state):
        kind = obj.get("type", "")
        if kind == "init":
            tier = _find_tier(obj)
            if tier and PERSONAL_TIER.search(tier):
                state["abort"] = True
                yield ev.error("Phát hiện tài khoản Google CÁ NHÂN trong agy; cad-guard từ chối chạy (FAQ Antigravity cấm "
                               "bọc agy trong ứng dụng bên thứ ba với gói cá nhân). Đăng nhập tài khoản doanh nghiệp "
                               "hoặc dùng khoá API.", "personal_account")
                return
            servers = obj.get("mcp_servers")
            if isinstance(servers, list):
                status = {s.get("name"): s.get("status") for s in servers if isinstance(s, dict)}
                if status.get(SERVER) not in ("connected", "ready", None) or SERVER not in status:
                    state["abort"] = True
                    yield ev.error("Máy chủ cad-guard chưa kết nối với agy. Kiểm extras [agent] và thử lại.", "mcp_not_connected")
        elif kind in ("tool_call", "tool_use"):
            yield Event("tool_call", {"id": obj.get("id"), "name": obj.get("name") or obj.get("tool"),
                                      "arguments": obj.get("arguments") or obj.get("input") or {}})
        elif kind == "tool_result":
            yield Event("tool_result", {"id": obj.get("id"), "name": obj.get("name") or obj.get("tool"),
                                        "content": _to_text(obj.get("content") or obj.get("result")),
                                        "is_error": bool(obj.get("is_error"))})
        elif kind == "result":
            u = obj.get("usage") or {}
            yield ev.usage(Usage(int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0) + int(u.get("thinking_tokens") or 0),
                                 int(u.get("cache_read_tokens") or 0), 0, None, True))
            status = str(obj.get("status") or "SUCCESS").upper()
            if status != "SUCCESS":
                err = _to_text(obj.get("error"))
                if NOT_LOGGED_IN.search(err):
                    yield ev.error(self.login_hint, "not_logged_in")
                else:
                    yield ev.error(f"agy kết thúc với trạng thái {status}.", "cli_error")
            elif isinstance(obj.get("response"), str):
                state["texts"].append(obj["response"])
                state["final"] = obj["response"]
                yield ev.text(obj["response"])

    def explain_failure(self, code, stderr):
        if "AGY_ERROR" in (stderr or "") and not NOT_LOGGED_IN.search(stderr):
            return "agy báo lỗi mô hình/agent (mã thoát 3). Thử lại sau."
        return super().explain_failure(code, stderr)
