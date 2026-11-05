"""Màn Kết nối AI: khoá API (kho khoá hệ điều hành), kiểm khoá, mở cửa sổ đăng nhập CLI, cấu hình trợ lý.

An toàn khoá:
- khoá chỉ đi một chiều: trình duyệt -> POST JSON tới 127.0.0.1 (có mã phiên) -> `assistant.keys.set_key` (kho khoá hệ
  điều hành). Không ghi tệp, không log, **không bao giờ trả lại** (mọi phản hồi chỉ có "có/không có khoá" và nguồn);
- không có `keyring` thì từ chối nhận khoá và hướng dẫn cài `pip install cadguard[keyring]`;
- kiểm khoá chỉ khi người dùng bấm: gọi endpoint liệt kê mô hình/thông tin khoá của nhà cung cấp (không sinh token).

Đăng nhập CLI: mở một **cửa sổ terminal mới** chạy lệnh đăng nhập chính thức của CLI; người dùng tự đăng nhập trong
cửa sổ đó. cad-guard không đọc đầu ra, không đọc tệp xác thực, không chạm token.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from ..assistant import keys
from ..assistant.api_engines import ANTHROPIC_VERSION, PROVIDERS, provider_base_url, redact
from .settings import connection

KEY_PROVIDERS = tuple(keys.KEY_ENV)  # anthropic, openai, openrouter, gemini
KEY_MIN, KEY_MAX = 8, 512
_KEY_OK = re.compile(r"^[\x21-\x7e]+$")  # ASCII in được, không khoảng trắng/ký tự điều khiển
KEYRING_HINT = ("Máy này chưa có gói `keyring` nên cad-guard không lưu được khoá vào kho khoá của hệ điều hành "
                "(và không bao giờ ghi khoá ra tệp). Cài bằng: pip install cadguard[keyring] rồi mở lại ứng dụng.")
CHECK_TIMEOUT_S = 15

# Lệnh đăng nhập chính thức (docs/integrations/*.md). agy: chạy `agy` tương tác để đăng nhập.
LOGIN_COMMANDS: dict[str, list[str]] = {
    "claude-cli": ["claude", "auth", "login"],
    "codex-cli": ["codex", "login"],
    "agy-cli": ["agy"],
}
INSTALL_DOCS: dict[str, str] = {
    "claude-cli": "Cài Claude Code theo hướng dẫn chính thức: code.claude.com/docs (mục Setup).",
    "codex-cli": "Cài Codex CLI theo hướng dẫn chính thức của OpenAI: developers.openai.com/codex (mục CLI).",
    "agy-cli": "Cài Antigravity CLI theo hướng dẫn chính thức của Google: antigravity.google/docs/install.",
}


class ConnectError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---------- khoá ----------

def keyring_available() -> bool:
    return keys._keyring() is not None  # noqa: SLF001 — cùng gói, chỉ hỏi có/không


def key_states() -> dict[str, dict]:
    """provider -> {has_key, source: "kho khoá"/"biến môi trường"/None, env_var}. Không bao giờ chứa khoá."""
    out = {}
    for p in KEY_PROVIDERS:
        st = keys.key_status(p)
        src = "env" if st["env"] else ("keyring" if st["keyring"] else None)
        out[p] = {"has_key": src is not None, "source": src, "env_var": st["env_var"]}
    return out


def save_key(provider: object, value: object) -> dict:
    if provider not in KEY_PROVIDERS:
        raise ConnectError("Nhà cung cấp không dùng khoá API (hoặc không có).")
    if not isinstance(value, str):
        raise ConnectError("Thiếu khoá.")
    value = value.strip()
    if not (KEY_MIN <= len(value) <= KEY_MAX) or not _KEY_OK.fullmatch(value):
        raise ConnectError(f"Khoá không đúng dạng (cần {KEY_MIN}–{KEY_MAX} ký tự, không có khoảng trắng).")
    if not keyring_available():
        raise ConnectError(KEYRING_HINT, 501)
    try:
        keys.set_key(provider, value)
    except keys.KeyStoreError as exc:
        raise ConnectError(str(exc), 500) from None
    return key_states()[provider]


def delete_key(provider: object) -> dict:
    if provider not in KEY_PROVIDERS:
        raise ConnectError("Nhà cung cấp không dùng khoá API (hoặc không có).")
    if not keyring_available():
        raise ConnectError(KEYRING_HINT, 501)
    try:
        removed = keys.delete_key(provider)
    except keys.KeyStoreError as exc:
        raise ConnectError(str(exc), 500) from None
    return {**key_states()[provider], "removed": removed}


Opener = Callable[..., object]


def check_key(provider: object, ai: dict, *, opener: Opener | None = None) -> dict:
    """Gọi endpoint rẻ nhất (liệt kê mô hình / thông tin khoá) để xác nhận khoá. Không sinh token."""
    if provider not in PROVIDERS:
        raise ConnectError("Không có nhà cung cấp này.")
    if provider == "openrouter" and not ai.get("allow_openrouter"):
        raise ConnectError("OpenRouter đang tắt (bên trung gian thứ ba). Bật công tắc trước khi kiểm khoá.")
    p = PROVIDERS[provider]
    base = provider_base_url(p, ai.get("ollama_base_url") if provider == "ollama" else None)
    key = keys.get_key(provider) if p.key_env else None
    if p.key_env and not key:
        raise ConnectError("Chưa có khoá cho nhà cung cấp này.")
    if p.kind == "anthropic":
        url = f"{base}/v1/models?" + urllib.parse.urlencode({"limit": 1})
        headers = {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}
    elif provider == "openrouter":
        url, headers = f"{base}/key", {"authorization": f"Bearer {key}"}
    else:
        url, headers = f"{base}/models", ({"authorization": f"Bearer {key}"} if key else {})
    req = urllib.request.Request(url, method="GET", headers=headers)
    open_ = opener or urllib.request.urlopen
    try:
        with open_(req, timeout=CHECK_TIMEOUT_S) as resp:  # noqa: S310 — địa chỉ cố định của nhà cung cấp
            body = resp.read(200_000)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return {"ok": False, "message": f"Nhà cung cấp từ chối khoá (HTTP {exc.code}): khoá sai, hết hạn hoặc không đủ quyền."}
        return {"ok": False, "message": f"Nhà cung cấp trả lỗi HTTP {exc.code}. Thử lại sau."}
    except (urllib.error.URLError, TimeoutError, OSError):
        where = "Ollama trên máy này (đã chạy `ollama serve` chưa?)" if provider == "ollama" else "nhà cung cấp"
        return {"ok": False, "message": f"Không kết nối được tới {where}."}
    count = None
    try:
        data = json.loads(body.decode("utf-8", "replace"))
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            count = len(data["data"])
    except ValueError:
        pass
    msg = "Khoá hợp lệ" if p.key_env else "Kết nối được"
    if count is not None and provider != "openrouter":
        msg += f" · thấy {count} mô hình" + (" (trang đầu)" if p.kind == "anthropic" else "")
    return {"ok": True, "message": redact(msg + ". Không tốn token (chỉ gọi danh sách mô hình/thông tin khoá).", key)}


# ---------- CLI ----------

Popen = Callable[..., object]


def login_command(engine: object) -> list[str]:
    if engine not in LOGIN_COMMANDS:
        raise ConnectError("Engine này không có bước đăng nhập CLI.")
    return list(LOGIN_COMMANDS[engine])


def terminal_argv(argv: list[str], *, platform: str | None = None, which: Callable[[str], str | None] = shutil.which) -> tuple[list[str], dict]:
    """Dòng lệnh mở cửa sổ terminal MỚI chạy `argv`; trả (argv, kwargs cho Popen)."""
    plat = platform or sys.platform
    if plat.startswith("win"):
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10)
        return ["cmd.exe", "/k", *argv], {"creationflags": flags, "close_fds": True}
    quiet = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
             "close_fds": True, "start_new_session": True}
    if plat == "darwin":
        script = " ".join(argv)  # lệnh cố định trong LOGIN_COMMANDS, không chứa dữ liệu người dùng
        return ["osascript", "-e", f'tell application "Terminal" to do script "{script}"',
                "-e", 'tell application "Terminal" to activate'], quiet
    for term, pre in (("x-terminal-emulator", ["-e"]), ("gnome-terminal", ["--"]), ("konsole", ["-e"]), ("xterm", ["-e"])):
        if which(term):
            return [term, *pre, *argv], quiet
    raise ConnectError("Không tìm thấy chương trình terminal để mở. Hãy tự mở terminal và chạy: " + " ".join(argv))


def open_login(engine: object, ai: dict, *, popen: Popen | None = None,
               which: Callable[[str], str | None] = shutil.which, platform: str | None = None) -> dict:
    argv = login_command(engine)
    if engine == "agy-cli" and ai.get("agy_account") != "business":
        raise ConnectError("Antigravity: chỉ đăng nhập bằng tài khoản doanh nghiệp. Chọn loại tài khoản “Doanh nghiệp” "
                           "trước (khoá API thì không cần đăng nhập CLI). Tài khoản Google cá nhân không được phép.")
    if not which(argv[0]):
        raise ConnectError(f"Chưa cài `{argv[0]}` trên máy này. " + INSTALL_DOCS[engine])
    cmd, kw = terminal_argv(argv, platform=platform, which=which)
    run = popen or subprocess.Popen
    try:
        run(cmd, env=dict(os.environ), **kw)
    except OSError:
        raise ConnectError("Không mở được cửa sổ terminal. Hãy tự mở terminal và chạy: " + " ".join(argv), 500) from None
    return {"opened": True, "command": " ".join(argv),
            "note": "Đã mở cửa sổ đăng nhập của CLI. Đăng nhập xong, đóng cửa sổ đó rồi bấm “Kiểm lại”."}


# ---------- cấu hình hiển thị ----------

def ai_view(ai: dict, engine_names: list[str]) -> dict:
    """Cấu hình trợ lý cho giao diện: không có khoá, chỉ trạng thái có/không."""
    return {
        "default_engine": ai.get("default_engine"), "max_cost_usd": ai.get("max_cost_usd"),
        "codex_experimental": ai.get("codex_experimental"), "agy_account": ai.get("agy_account"),
        "allow_openrouter": ai.get("allow_openrouter"), "ollama_base_url": ai.get("ollama_base_url"),
        "models": {n: connection(ai, n).get("model") for n in engine_names},
        "connections": [{k: c.get(k) for k in ("id", "engine", "label", "model", "key_slot")} for c in ai.get("connections") or []],
        "keys": key_states(), "keyring_available": keyring_available(),
        "login_commands": {k: " ".join(v) for k, v in LOGIN_COMMANDS.items()}, "install_docs": INSTALL_DOCS,
    }


__all__ = ["ConnectError", "INSTALL_DOCS", "KEYRING_HINT", "KEY_PROVIDERS", "LOGIN_COMMANDS", "ai_view", "check_key",
           "delete_key", "key_states", "keyring_available", "login_command", "open_login", "save_key", "terminal_argv"]
