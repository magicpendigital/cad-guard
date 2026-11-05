"""Cấu hình cục bộ của người dùng cho `cadguard app` (một tệp JSON trên máy người dùng, ngoài mọi dự án).

Vị trí: `%APPDATA%\\cad-guard\\settings.json` (Windows), `$XDG_CONFIG_HOME/cad-guard/settings.json` hoặc
`~/.config/cad-guard/settings.json` (macOS/Linux). Biến `CADGUARD_CONFIG_DIR` đổi thư mục (dùng cho test).

Chỉ chứa: dự án gần đây (đường dẫn + thời điểm mở), hồ sơ công ty đã chọn cho từng dự án, cấu hình trợ lý
(engine mặc định, trần chi phí, công tắc thử nghiệm, mô hình mặc định). **Không bao giờ chứa khoá API hay token**:
khoá nằm trong kho khoá hệ điều hành (`assistant/keys.py`), hồ sơ kết nối chỉ ghi *tên ô khoá* (`key_slot`).

Hồ sơ kết nối (`ai.connections`): mỗi engine có thể có nhiều hồ sơ (ví dụ nhiều khoá API theo phòng/dự án).
Hiện giao diện chỉ dùng một hồ sơ mặc định mỗi engine (`id` = tên engine, `key_slot` = tên nhà cung cấp, đúng
ô khoá của `cadguard keys`); cấu trúc đã cho phép thêm hồ sơ khác về sau mà không đổi định dạng tệp.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = "cg.app-settings/1"
MAX_RECENT = 12
MODEL_RE = re.compile(r"^[A-Za-z0-9._:/@\-]{1,120}$")
CONN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]{0,63}$")
AGY_ACCOUNTS = ("business", "api-key")
LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]")
DEFAULT_OLLAMA_URL = "http://localhost:11434/v1"
MAX_COST_RANGE = (0.01, 100.0)

DEFAULT_AI = {
    "default_engine": None,
    "max_cost_usd": 2.0,
    "codex_experimental": False,
    "agy_account": None,
    "allow_openrouter": False,
    "ollama_base_url": DEFAULT_OLLAMA_URL,
    "connections": [],
    "active_connection": {},
}


def config_dir() -> Path:
    if os.environ.get("CADGUARD_CONFIG_DIR"):
        return Path(os.environ["CADGUARD_CONFIG_DIR"])
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "cad-guard"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "cad-guard"


def default_settings_path() -> Path:
    return config_dir() / "settings.json"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def norm_path(p: str | Path) -> str:
    """Khoá so sánh đường dẫn dự án (tuyệt đối, đã resolve; Windows không phân biệt hoa thường)."""
    s = str(Path(p).resolve())
    return s.casefold() if os.name == "nt" else s


class SettingsError(ValueError):
    """Giá trị cấu hình không hợp lệ (thông điệp tiếng Việt)."""


class Settings:
    """Đọc/ghi tệp cấu hình (ghi nguyên tử, khoá luồng). Tệp hỏng thì dùng mặc định, không làm sập ứng dụng."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else default_settings_path()
        self._lock = threading.RLock()
        self.data = self._load()

    # ---------- đọc / ghi ----------

    def _empty(self) -> dict:
        return {"schema": SCHEMA, "recent_projects": [], "projects": {}, "ai": deepcopy(DEFAULT_AI)}

    def _load(self) -> dict:
        data = self._empty()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return data
        if not isinstance(raw, dict):
            return data
        rec = raw.get("recent_projects")
        if isinstance(rec, list):
            data["recent_projects"] = [r for r in rec if isinstance(r, dict) and isinstance(r.get("path"), str)][:MAX_RECENT]
        proj = raw.get("projects")
        if isinstance(proj, dict):
            data["projects"] = {k: v for k, v in proj.items() if isinstance(k, str) and isinstance(v, dict)}
        ai = raw.get("ai")
        if isinstance(ai, dict):
            for k in DEFAULT_AI:
                if k in ai:
                    data["ai"][k] = ai[k]
        try:
            _validate_ai(data["ai"])
        except SettingsError:
            data["ai"] = deepcopy(DEFAULT_AI)
        return data

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            text = json.dumps(self.data, ensure_ascii=False, indent=2)
            fd, tmp = tempfile.mkstemp(prefix=".settings-", suffix=".json", dir=str(self.path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(text)
                os.replace(tmp, self.path)
            except OSError:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise

    # ---------- dự án gần đây ----------

    def recent(self) -> list[dict]:
        with self._lock:
            out = []
            for r in self.data["recent_projects"]:
                p = Path(r["path"])
                out.append({"path": r["path"], "name": p.name or r["path"], "opened_at": r.get("opened_at"),
                            "exists": p.is_dir()})
            return out

    def touch_recent(self, path: Path) -> None:
        with self._lock:
            key = norm_path(path)
            rest = [r for r in self.data["recent_projects"] if norm_path(r["path"]) != key]
            self.data["recent_projects"] = [{"path": str(Path(path).resolve()), "opened_at": now_iso()}] + rest[:MAX_RECENT - 1]
            self.save()

    def forget_recent(self, path: str) -> bool:
        with self._lock:
            key = norm_path(path)
            before = len(self.data["recent_projects"])
            self.data["recent_projects"] = [r for r in self.data["recent_projects"] if norm_path(r["path"]) != key]
            changed = len(self.data["recent_projects"]) != before
            if changed:
                self.save()
            return changed

    # ---------- theo dự án ----------

    def project(self, path: Path) -> dict:
        with self._lock:
            return dict(self.data["projects"].get(norm_path(path)) or {})

    def set_project_profile(self, path: Path, profile: Path | None) -> None:
        with self._lock:
            key = norm_path(path)
            cur = dict(self.data["projects"].get(key) or {})
            cur["profile_path"] = str(Path(profile).resolve()) if profile else None
            self.data["projects"][key] = cur
            self.save()

    # ---------- trợ lý ----------

    def ai(self) -> dict:
        with self._lock:
            return deepcopy(self.data["ai"])

    def update_ai(self, patch: dict) -> dict:
        """Gộp `patch` vào cấu hình trợ lý sau khi kiểm từng khoá; lỗi -> SettingsError, không ghi gì."""
        if not isinstance(patch, dict):
            raise SettingsError("Cấu hình phải là một đối tượng JSON.")
        unknown = set(patch) - (set(DEFAULT_AI) - {"connections", "active_connection"}) - {"models"}
        if unknown:
            raise SettingsError("Khoá cấu hình lạ: " + ", ".join(sorted(unknown)) + ".")
        with self._lock:
            new = deepcopy(self.data["ai"])
            for k, v in patch.items():
                if k == "models":
                    if not isinstance(v, dict):
                        raise SettingsError("models phải là {engine: tên mô hình}.")
                    for eng, model in v.items():
                        set_connection_model(new, eng, model)
                else:
                    new[k] = v
            _validate_ai(new)
            self.data["ai"] = new
            self.save()
            return deepcopy(new)


# ---------- hồ sơ kết nối ----------

def connection(ai: dict, engine: str) -> dict:
    """Hồ sơ kết nối đang dùng của engine (mặc định: id = engine, key_slot = engine)."""
    cid = (ai.get("active_connection") or {}).get(engine) or engine
    for c in ai.get("connections") or []:
        if c.get("id") == cid and c.get("engine") == engine:
            return c
    return {"id": engine, "engine": engine, "label": "Mặc định", "model": None, "key_slot": engine}


def set_connection_model(ai: dict, engine: Any, model: Any) -> None:
    if not isinstance(engine, str) or not CONN_ID_RE.fullmatch(engine):
        raise SettingsError("Tên engine không hợp lệ.")
    if model in ("", None):
        model = None
    elif not isinstance(model, str) or not MODEL_RE.fullmatch(model):
        raise SettingsError("Tên mô hình không hợp lệ (chữ, số và . _ : / @ -; tối đa 120 ký tự).")
    conns = ai.setdefault("connections", [])
    cur = connection(ai, engine)
    for c in conns:
        if c.get("id") == cur["id"] and c.get("engine") == engine:
            c["model"] = model
            return
    conns.append({**cur, "model": model})
    ai.setdefault("active_connection", {})[engine] = cur["id"]


def _validate_ai(ai: dict) -> None:
    de = ai.get("default_engine")
    if de is not None and (not isinstance(de, str) or not CONN_ID_RE.fullmatch(de)):
        raise SettingsError("Engine mặc định không hợp lệ.")
    mc = ai.get("max_cost_usd")
    if isinstance(mc, bool) or not isinstance(mc, (int, float)) or not (MAX_COST_RANGE[0] <= float(mc) <= MAX_COST_RANGE[1]):
        raise SettingsError(f"Trần chi phí mỗi phiên phải từ {MAX_COST_RANGE[0]:g} đến {MAX_COST_RANGE[1]:g} USD.")
    ai["max_cost_usd"] = float(mc)
    for k in ("codex_experimental", "allow_openrouter"):
        if not isinstance(ai.get(k), bool):
            raise SettingsError(f"{k} phải là true/false.")
    if ai.get("agy_account") not in (None, *AGY_ACCOUNTS):
        raise SettingsError("Loại tài khoản Antigravity chỉ nhận: doanh nghiệp (business) hoặc khoá API (api-key). "
                            "Tài khoản Google cá nhân không được phép dùng qua ứng dụng bên thứ ba.")
    url = ai.get("ollama_base_url")
    if not isinstance(url, str) or not is_local_url(url):
        raise SettingsError("Địa chỉ Ollama phải là máy này (http://localhost:… hoặc http://127.0.0.1:…).")
    conns = ai.get("connections")
    if not isinstance(conns, list) or len(conns) > 100:
        raise SettingsError("Danh sách hồ sơ kết nối sai dạng.")
    for c in conns:
        if not isinstance(c, dict) or not isinstance(c.get("id"), str) or not CONN_ID_RE.fullmatch(c["id"]):
            raise SettingsError("Hồ sơ kết nối thiếu id hợp lệ.")
        if not isinstance(c.get("engine"), str) or not CONN_ID_RE.fullmatch(c["engine"]):
            raise SettingsError("Hồ sơ kết nối thiếu engine hợp lệ.")
        if c.get("model") is not None and (not isinstance(c["model"], str) or not MODEL_RE.fullmatch(c["model"])):
            raise SettingsError("Hồ sơ kết nối có tên mô hình không hợp lệ.")
        slot = c.get("key_slot")
        if slot is not None and (not isinstance(slot, str) or not CONN_ID_RE.fullmatch(slot)):
            raise SettingsError("Hồ sơ kết nối có key_slot không hợp lệ.")
        if set(c) - {"id", "engine", "label", "model", "key_slot"}:
            raise SettingsError("Hồ sơ kết nối có trường lạ (khoá không bao giờ được ghi vào cấu hình).")
    act = ai.get("active_connection")
    if not isinstance(act, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in act.items()):
        raise SettingsError("active_connection sai dạng.")


def is_local_url(url: str) -> bool:
    m = re.fullmatch(r"https?://(\[::1\]|[A-Za-z0-9.\-]+)(:\d{1,5})?(/[A-Za-z0-9._~/\-]*)?", url or "")
    return bool(m) and m.group(1).lower() in LOCAL_HOSTS


def is_windows() -> bool:
    return sys.platform.startswith("win")


__all__ = ["DEFAULT_AI", "SCHEMA", "Settings", "SettingsError", "config_dir", "connection", "default_settings_path",
           "is_local_url", "norm_path", "now_iso", "set_connection_model"]
