"""Trợ lý trong ứng dụng: danh sách engine (không bao giờ trả khoá) và một lượt trò chuyện chạy nền.

- Engine CLI (B): hạn mức tài khoản qua CLI người dùng đã cài và tự đăng nhập. Engine API (C): khoá API của họ.
- Một lượt = `Engine.run(...)` trong luồng nền; sự kiện đi qua hàng đợi tới luồng HTTP (NDJSON). Dừng = `CancelToken`.
- Trợ lý chỉ có `propose_changeset` khi người dùng bật công tắc; áp dụng LUÔN do người bấm trong giao diện.
- Ẩn danh Bậc 1 mặc định (`server_options={"anonymize": True}`); tắt chỉ bằng cờ dòng lệnh `--no-anonymize`.
- Cấu hình hiệu lực = cờ dòng lệnh HOẶC cấu hình trên giao diện (màn Kết nối AI, `settings.py`): bật thử nghiệm Codex,
  OpenRouter, loại tài khoản agy, mô hình mặc định, trần chi phí mỗi phiên (truyền vào engine API).
"""
from __future__ import annotations

import queue
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..assistant import API_ENGINES, CLI_ENGINES, CancelToken, EngineError, create_engine, engine_infos
from ..assistant.events import Usage
from .api import ApiError, AppConfig, AppData
from .settings import DEFAULT_AI, connection

MAX_MESSAGES = 60
MAX_MESSAGE_CHARS = 20000
MAX_TOOL_TEXT = 4000
MODEL_RE = re.compile(r"^[A-Za-z0-9._:/@\-]{1,120}$")
STOP_GRACE_S = 5.0

AGY_HINT = ("Chỉ tài khoản doanh nghiệp hoặc khoá API: chọn loại tài khoản ở màn Kết nối AI "
            "(hoặc khởi động với `cadguard app ... --account business`/api-key).")


def _default_detect(name: str) -> dict:
    return create_engine(name).detect()


@dataclass
class ChatRun:
    run_id: str
    cancel: CancelToken
    events: "queue.Queue[dict | None]" = field(default_factory=queue.Queue)
    stop_requested_at: float | None = None


class Assistant:
    """Engine + lượt trò chuyện của một phiên ứng dụng (dự án có thể đổi lúc chạy: `self.data`)."""

    def __init__(self, data: AppData | None, *, config: AppConfig | None = None,
                 ai_settings: Callable[[], dict] | None = None, engine_factory: Callable[..., Any] | None = None,
                 engine_lister: Callable[[], list] | None = None, cli_detect: Callable[[str], dict] | None = None):
        self.data = data
        self.config = config or (data.config if data is not None else AppConfig())
        self.ai_settings = ai_settings or (lambda: dict(DEFAULT_AI))
        self.engine_factory = engine_factory or create_engine
        self.engine_lister = engine_lister or engine_infos
        self.cli_detect = cli_detect or _default_detect
        self._detect_cache: dict[str, dict] = {}
        self._runs: dict[str, ChatRun] = {}
        self._lock = threading.Lock()

    # ---------- cấu hình hiệu lực ----------

    def effective(self) -> dict:
        cfg, ai = self.config, self.ai_settings()
        return {"experimental": bool(cfg.experimental or ai.get("codex_experimental")),
                "allow_openrouter": bool(cfg.allow_openrouter or ai.get("allow_openrouter")),
                "account": cfg.account or ai.get("agy_account"),
                "max_cost_usd": ai.get("max_cost_usd"), "ollama_base_url": ai.get("ollama_base_url"),
                "default_engine": ai.get("default_engine"), "ai": ai}

    # ---------- danh sách engine ----------

    def engines(self, refresh: bool = False) -> dict:
        from ..assistant.api_engines import PROVIDERS, provider_model
        from ..assistant.keys import key_status

        eff = self.effective()
        out = []
        for info in self.engine_lister():
            row = {"name": info.name, "mode": info.mode, "title": info.title, "terms": info.terms,
                   "experimental": bool(info.experimental), "default_off": bool(info.default_off),
                   "available": True, "reason": "", "status": "", "model": None, "needs_model": False, "hint": "",
                   "installed": None, "logged_in": None, "version": None}
            if info.mode == "cli":
                if refresh or info.name not in self._detect_cache:
                    try:
                        self._detect_cache[info.name] = dict(self.cli_detect(info.name))
                    except Exception:  # noqa: BLE001 — kiểm hỏng: coi như chưa cài
                        self._detect_cache[info.name] = {"installed": False, "version": None, "logged_in": None}
                d = self._detect_cache[info.name]
                row.update(installed=d.get("installed"), logged_in=d.get("logged_in"),
                           version=(str(d.get("version"))[:80] if d.get("version") else None))
                row["model"] = connection(eff["ai"], info.name).get("model")
                if d.get("installed") is None:
                    row.update(available=False, reason="Chưa kiểm CLI (--no-detect).", status="chưa kiểm",
                               hint="Khởi động lại không có --no-detect để cad-guard kiểm CLI đã cài/đăng nhập chưa.")
                elif not d.get("installed"):
                    row.update(available=False, reason="Chưa cài CLI trên máy này.", status="chưa cài")
                else:
                    login = d.get("logged_in")
                    row["status"] = {True: "đã cài, đã đăng nhập", False: "đã cài, CHƯA đăng nhập",
                                     None: "đã cài, không rõ đăng nhập"}[login]
                    if login is False:
                        row.update(available=False, reason="Chưa đăng nhập CLI.",
                                   hint="Bấm “Đăng nhập” ở màn Kết nối AI (mở cửa sổ đăng nhập của chính CLI).")
                if info.name == "codex-cli" and not eff["experimental"]:
                    row.update(available=False,
                               reason="Thử nghiệm: bật ở màn Kết nối AI (hoặc khởi động với --experimental).",
                               hint="Điều khoản dùng đăng nhập ChatGPT cho ứng dụng bên thứ ba chưa rõ.")
                if info.name == "agy-cli" and eff["account"] not in ("business", "api-key"):
                    row.update(available=False, reason="Chỉ tài khoản doanh nghiệp/khoá API.", hint=AGY_HINT)
            else:
                p = PROVIDERS.get(info.name)
                row["model"] = connection(eff["ai"], info.name).get("model") or (provider_model(p, None) if p else None)
                row["needs_model"] = p is not None and not row["model"]
                if p is not None and p.key_env is not None:
                    st = key_status(info.name)
                    has = bool(st["env"] or st["keyring"])
                    src = "biến môi trường" if st["env"] else ("kho khoá hệ điều hành" if st["keyring"] else "")
                    row["status"] = f"có khoá ({src})" if has else "chưa có khoá"
                    if not has:
                        row.update(available=False, reason="Chưa có khoá API.",
                                   hint=f"Nhập khoá ở màn Kết nối AI (hoặc chạy `cadguard keys set {info.name}` "
                                        f"trong terminal, hoặc đặt biến {p.key_env}).")
                elif p is not None:
                    row["status"] = "cục bộ, không cần khoá"
                if info.default_off and not eff["allow_openrouter"]:
                    row.update(available=False, reason="Mặc định tắt (bên trung gian thứ ba).",
                               hint="Chỉ bật khi khách đồng ý: bật công tắc ở màn Kết nối AI "
                                    "(hoặc khởi động với `cadguard app ... --allow-openrouter`).")
            out.append(row)
        groups = [
            {"mode": "cli", "title": "Dùng hạn mức tài khoản (CLI)",
             "note": "CLI bạn đã cài và tự đăng nhập; cad-guard không đọc, không lưu token. Chi phí tính vào gói/tài khoản của bạn."},
            {"mode": "api", "title": "Dùng API (khoá của bạn)",
             "note": "Gọi thẳng nhà cung cấp bằng khoá của bạn; tính cước theo token. Khoá không bao giờ quay lại trình duyệt."},
        ]
        return {"engines": out, "groups": groups, "anonymize": self.config.anonymize,
                "default_engine": eff["default_engine"], "max_cost_usd": eff["max_cost_usd"]}

    # ---------- một lượt trò chuyện ----------

    def start(self, body: dict) -> tuple[ChatRun, dict]:
        if self.data is None:
            raise ApiError("Chưa mở dự án: chọn thư mục dự án trước khi hỏi trợ lý.", 409)
        data = self.data
        name = body.get("engine")
        if not isinstance(name, str) or name not in {i.name for i in self.engine_lister()}:
            raise ApiError("Chưa chọn engine hợp lệ.")
        eff = self.effective()
        model = body.get("model") or connection(eff["ai"], name).get("model") or None
        if model is not None and (not isinstance(model, str) or not MODEL_RE.fullmatch(model)):
            raise ApiError("Tên mô hình không hợp lệ.")
        messages = body.get("messages")
        if not isinstance(messages, list) or not messages or len(messages) > MAX_MESSAGES:
            raise ApiError(f"Lịch sử hội thoại phải có 1–{MAX_MESSAGES} lượt.")
        for m in messages:
            if not isinstance(m, dict) or not isinstance(m.get("content"), str) or len(m["content"]) > MAX_MESSAGE_CHARS:
                raise ApiError(f"Mỗi lượt là một chuỗi tối đa {MAX_MESSAGE_CHARS} ký tự.")
        standard = data.check_standard(body.get("standard"))
        allow_propose = body.get("allow_propose") is True
        cfg = self.config
        kwargs: dict = {"model": model, "experimental": eff["experimental"], "account": eff["account"]}
        if name in API_ENGINES:
            kwargs["allow_openrouter"] = eff["allow_openrouter"]
            if eff["max_cost_usd"] is not None:
                kwargs["max_cost_usd"] = float(eff["max_cost_usd"])
            if name == "ollama" and eff["ollama_base_url"]:
                kwargs["base_url"] = eff["ollama_base_url"]
        try:
            engine = self.engine_factory(name, **kwargs)
        except EngineError as exc:
            raise ApiError(str(exc)) from None
        profile = data.config.profile_path if data.profile_for(standard) is not None else None
        run = ChatRun(secrets.token_hex(8), CancelToken())
        meta = {"type": "start", "run_id": run.run_id, "engine": name,
                "mode": "cli" if name in CLI_ENGINES else ("api" if name in API_ENGINES else getattr(engine.info, "mode", "")),
                "standard": standard, "allow_propose": allow_propose, "anonymize": cfg.anonymize,
                "max_cost_usd": kwargs.get("max_cost_usd"),
                "profile": {"name": data.profile.name, "version": data.profile.version} if profile else None}
        with self._lock:
            self._runs[run.run_id] = run

        def worker() -> None:
            total = Usage(cost_usd=None)
            saw_done = False
            try:
                for ev in engine.run(messages, workspace=data.ws.root, standard=standard, profile=profile,
                                     allow_propose=allow_propose, server_options={"anonymize": cfg.anonymize},
                                     cancel=run.cancel):
                    if ev.type == "usage" and isinstance(ev.data.get("usage"), Usage):
                        total.add(ev.data["usage"])
                    if ev.type == "done":
                        saw_done = True
                    run.events.put(_public(ev.to_dict()))
            except EngineError as exc:
                run.events.put({"type": "error", "message": str(exc), "code": exc.code})
            except Exception:  # noqa: BLE001 — không lộ chi tiết nội bộ ra trình duyệt
                run.events.put({"type": "error", "message": "Trợ lý gặp lỗi nội bộ; lượt này dừng.", "code": "internal"})
            finally:
                if not saw_done:
                    run.events.put({"type": "done", "text": ""})
                run.events.put({"type": "summary", "usage": total.to_dict(), "cancelled": run.cancel.cancelled})
                run.events.put(None)

        threading.Thread(target=worker, name=f"cadguard-chat-{run.run_id}", daemon=True).start()
        return run, meta

    def stop(self, run_id: Any) -> bool:
        with self._lock:
            run = self._runs.get(run_id) if isinstance(run_id, str) else None
        if run is None:
            return False
        run.stop_requested_at = time.monotonic()
        run.cancel.cancel()
        return True

    def stop_all(self) -> int:
        with self._lock:
            runs = list(self._runs.values())
        for r in runs:
            r.stop_requested_at = time.monotonic()
            r.cancel.cancel()
        return len(runs)

    def finish(self, run: ChatRun) -> None:
        with self._lock:
            self._runs.pop(run.run_id, None)

    def next_event(self, run: ChatRun, timeout: float = 0.5) -> tuple[bool, dict | None]:
        """(còn chạy?, sự kiện hoặc None). Sau khi bấm Dừng mà engine không kết thúc trong STOP_GRACE_S giây thì cắt."""
        try:
            item = run.events.get(timeout=timeout)
        except queue.Empty:
            if run.stop_requested_at is not None and time.monotonic() - run.stop_requested_at > STOP_GRACE_S:
                return False, {"type": "stopped", "message": "Đã dừng (engine chưa kịp kết thúc; phần còn lại bị bỏ)."}
            return True, None
        if item is None:
            return False, None
        return True, item


def _public(d: dict) -> dict:
    """Rút gọn sự kiện cho trình duyệt (kết quả công cụ dài bị cắt)."""
    if d.get("type") == "tool_result":
        c = d.get("content")
        if isinstance(c, str) and len(c) > MAX_TOOL_TEXT:
            d["content"] = c[:MAX_TOOL_TEXT] + "…(đã cắt)"
    if d.get("type") == "tool_call":
        d["arguments"] = _clip(d.get("arguments"))
    return d


def _clip(v: Any) -> Any:
    try:
        import json

        s = json.dumps(v, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(v)[:MAX_TOOL_TEXT]
    return v if len(s) <= MAX_TOOL_TEXT else s[:MAX_TOOL_TEXT] + "…(đã cắt)"


__all__ = ["Assistant", "ChatRun"]
