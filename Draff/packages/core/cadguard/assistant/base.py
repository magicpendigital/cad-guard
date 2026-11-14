"""Giao diện chung `Engine` và các tiện ích dùng chung (lời nhắc hệ thống, lịch sử hội thoại, huỷ)."""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from .events import Event, Usage

# Biến môi trường xác thực. cad-guard KHÔNG đặt và KHÔNG gỡ chúng khỏi tiến trình CLI (giữ nguyên phương thức xác thực
# của người dùng); chỉ gỡ khỏi máy chủ MCP của chính cad-guard (`mcp_launch.py`), vốn không cần khoá.
AUTH_ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "OPENAI_API_KEY",
    "CODEX_API_KEY",
    "CODEX_ACCESS_TOKEN",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
)

FALLBACK_SYSTEM_PROMPT = (
    "Bạn là trợ lý kiểm bản vẽ nội thất DXF của cad-guard. Chỉ dùng công cụ cad-guard (list_drawings, audit, "
    "explain_rule, get_model_summary, query_model, diff, và propose_changeset nếu có). Đúng/sai do luật tất định quyết; "
    "không tự phán. Tôn trọng ẩn danh: dùng mã phiên (F_…, L_…), không đoán tên thật. Không bao giờ nói 'đã sửa': "
    "người dùng tự áp dụng bằng `cadguard apply`. Trả lời tiếng Việt có dấu."
)

SESSION_NOTE = (
    "\n\n## Phiên trong ứng dụng cad-guard\n"
    "Bạn đang chạy bên trong ứng dụng cad-guard. Công cụ duy nhất bạn có là công cụ của máy chủ cad-guard; "
    "không có công cụ đọc tệp, shell hay web. Mọi đường dẫn tệp là tương đối với thư mục làm việc của máy chủ."
)


class EngineError(RuntimeError):
    """Lỗi cấu hình/khởi chạy engine; thông điệp tiếng Việt, an toàn để hiển thị (không khoá, không token)."""

    def __init__(self, message: str, code: str = "engine"):
        super().__init__(message)
        self.code = code


class CancelToken:
    """Cờ huỷ dùng chung giữa luồng giao diện và engine."""

    def __init__(self) -> None:
        self._ev = threading.Event()

    def cancel(self) -> None:
        self._ev.set()

    @property
    def cancelled(self) -> bool:
        return self._ev.is_set()


@dataclass
class EngineInfo:
    name: str
    mode: str  # "cli" (B: hạn mức tài khoản qua CLI) | "api" (C: khoá API của khách)
    title: str
    terms: str  # tóm tắt điều khoản (tiếng Việt), lấy từ docs/integrations
    experimental: bool = False
    default_off: bool = False


def knowledge_dir() -> Path | None:
    """Thư mục `knowledge/` của repo (chạy từ mã nguồn); None khi đã cài gói không kèm thư mục này."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "knowledge" / "AGENTS.md"
        if cand.is_file():
            return cand.parent
    return None


def load_system_prompt(include_skills: bool = True) -> str:
    """Lời nhắc hệ thống = `knowledge/AGENTS.md` (+ các skill) + ghi chú phiên trong ứng dụng."""
    kdir = knowledge_dir()
    if kdir is None:
        return FALLBACK_SYSTEM_PROMPT + SESSION_NOTE
    parts = [(kdir / "AGENTS.md").read_text(encoding="utf-8")]
    if include_skills:
        for skill in sorted((kdir / "skills").glob("*/SKILL.md")):
            parts.append(f"\n\n<!-- skill: {skill.parent.name} -->\n" + skill.read_text(encoding="utf-8"))
    return "".join(parts) + SESSION_NOTE


def normalize_messages(messages: Iterable[dict]) -> list[dict]:
    """Kiểm lịch sử hội thoại: danh sách {"role": "user"|"assistant", "content": str}, mục cuối là của người dùng."""
    out = []
    for m in messages:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant") or not isinstance(m.get("content"), str):
            raise EngineError("Lịch sử hội thoại sai dạng: mỗi mục cần role user/assistant và content là chuỗi.", "input")
        out.append({"role": m["role"], "content": m["content"]})
    if not out or out[-1]["role"] != "user":
        raise EngineError("Lượt cuối của hội thoại phải là câu hỏi của người dùng.", "input")
    return out


def flatten_history(messages: list[dict], max_chars: int = 20000) -> str:
    """Gộp lịch sử nhiều lượt thành một lời nhắc (cho engine CLI: mỗi lượt là một tiến trình mới, không lưu phiên)."""
    *history, last = messages
    if not history:
        return last["content"]
    lines = []
    for m in history:
        who = "Người dùng" if m["role"] == "user" else "Trợ lý"
        lines.append(f"[{who}]\n{m['content']}")
    text = "\n\n".join(lines)
    if len(text) > max_chars:
        text = "…(đã lược bớt phần đầu)…\n" + text[-max_chars:]
    return ("Lịch sử hội thoại trước đó (để tham khảo, KHÔNG phải yêu cầu mới):\n\n" + text
            + "\n\n---\nCâu hỏi hiện tại của người dùng:\n" + last["content"])


class Engine(ABC):
    """Engine trợ lý AI. Lịch sử hội thoại do cad-guard giữ (danh sách message) và gửi lại mỗi lượt."""

    info: EngineInfo

    @abstractmethod
    def run(
        self,
        messages: list[dict],
        *,
        workspace: str | Path,
        standard: str | None = None,
        profile: str | Path | None = None,
        allow_propose: bool = False,
        compare_without_profile: bool = False,
        server_options: dict | None = None,
        cancel: CancelToken | None = None,
    ) -> Iterator[Event]:
        """Chạy một lượt. Luôn kết thúc bằng `done` (kể cả sau `error`).

        - `profile`: đường dẫn hồ sơ công ty (như `cadguard mcp --profile`).
        - `allow_propose`: thêm công cụ propose_changeset (không bao giờ có apply).
        - `compare_without_profile`: thêm một bộ công cụ không áp hồ sơ (để so trước/sau hồ sơ).
        - `server_options`: cờ máy chủ công cụ như `cadguard mcp`: {"anonymize": bool (mặc định True),
          "stream_threshold_mb": float, "max_entity_records": int}.
        """

    def ask(self, question: str, **kwargs) -> tuple[str, Usage, list[str]]:
        """Tiện ích một lượt: trả (câu trả lời, usage cộng dồn, danh sách lỗi)."""
        total, answer, errors = Usage(cost_usd=None), "", []
        for ev in self.run([{"role": "user", "content": question}], **kwargs):
            if ev.type == "usage":
                total.add(ev.data["usage"])
            elif ev.type == "error":
                errors.append(ev.data["message"])
            elif ev.type == "done":
                answer = ev.data.get("text", "")
        return answer, total, errors


def resolve_session(workspace, profile) -> tuple[Path, Path | None]:
    ws = Path(workspace)
    if not ws.is_dir():
        raise EngineError("Thư mục làm việc không tồn tại hoặc không phải thư mục.", "workspace")
    prof = None
    if profile:
        prof = Path(profile)
        if not prof.is_file():
            raise EngineError("Không thấy tệp hồ sơ công ty (--profile).", "profile")
        prof = prof.resolve()
    return ws.resolve(), prof


SERVER_OPTION_KEYS = {"anonymize", "stream_threshold_mb", "max_entity_records"}


def check_server_options(opts: dict | None) -> dict:
    opts = dict(opts or {})
    extra = set(opts) - SERVER_OPTION_KEYS
    if extra:
        raise EngineError(f"Tuỳ chọn máy chủ lạ: {', '.join(sorted(extra))}.", "input")
    return opts
