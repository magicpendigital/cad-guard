"""Các lớp nối LLM. Mỗi lớp chỉ có `complete(system, messages) -> str` (văn bản, kỳ vọng là JSON).

- AnthropicBackend: Messages API qua `assistant.api_engines.post_json` (thư viện chuẩn, không cần SDK `anthropic`);
  khoá lấy bằng `assistant.keys.get_key("anthropic")`: biến môi trường ANTHROPIC_API_KEY, rồi kho khoá hệ điều hành
  (`cadguard keys set anthropic`). Không ghi khoá ra tệp; lỗi HTTP đã che khoá.
- ClaudeCliBackend: chạy nguyên bản CLI `claude -p` trong thư mục rỗng, TẮT mọi công cụ file/shell; người dùng tự đăng nhập.
- FakeBackend: cho test, trả kịch bản có sẵn.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from typing import Protocol

from ..agent.tools import PROPOSE_SPEC, TOOL_SPECS
from ..assistant.api_engines import ANTHROPIC_VERSION, PROVIDERS, HttpError, post_json, provider_base_url
from ..assistant.keys import get_key

DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_OUTPUT_TOKENS = 4096
NETWORK_TIMEOUT = 300.0
STUDIO_SHARED_TOOLS = tuple(s["name"] for s in (*TOOL_SPECS, PROPOSE_SPEC))


class Backend(Protocol):
    name: str

    def complete(self, system: str, messages: list[dict]) -> str: ...


class LlmError(RuntimeError):
    pass


class FakeBackend:
    name = "fake"

    def __init__(self, replies: list[str] | None = None) -> None:
        self.replies = list(replies or [])
        self.calls: list[tuple[str, list[dict]]] = []

    def complete(self, system: str, messages: list[dict]) -> str:
        self.calls.append((system, messages))
        return self.replies.pop(0) if self.replies else '{"reply": "(không có kịch bản)"}'


class AnthropicBackend:
    """Gọi Anthropic Messages API bằng khoá của người dùng; dùng chung đường HTTP và kho khoá với trợ lý (`assistant/`)."""

    name = "anthropic-api"

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        key = get_key("anthropic")
        if not key:
            raise LlmError("Chưa có khoá API Anthropic: đặt biến môi trường ANTHROPIC_API_KEY hoặc chạy "
                           "`cadguard keys set anthropic` (lưu trong kho khoá hệ điều hành, không ghi ra tệp).")
        self._key = key
        self.model = (model or os.environ.get("CADGUARD_MODEL") or os.environ.get("CADGUARD_ANTHROPIC_MODEL")
                      or DEFAULT_MODEL)
        self.base_url = provider_base_url(PROVIDERS["anthropic"], base_url)

    def __repr__(self) -> str:  # không bao giờ in khoá
        return f"<AnthropicBackend model={self.model}>"

    def complete(self, system: str, messages: list[dict]) -> str:
        body = {"model": self.model, "max_tokens": MAX_OUTPUT_TOKENS, "system": system, "messages": messages}
        headers = {"x-api-key": self._key, "anthropic-version": ANTHROPIC_VERSION}
        try:
            resp = post_json(f"{self.base_url}/v1/messages", body, headers, NETWORK_TIMEOUT, self._key)
        except HttpError as exc:  # thông điệp tiếng Việt, đã che khoá
            raise LlmError(str(exc)) from None
        return "".join(b.get("text", "") for b in resp.get("content") or [] if isinstance(b, dict) and b.get("type") == "text")


class ClaudeCliBackend:
    name = "claude-cli"

    def __init__(self, model: str | None = None) -> None:
        self.exe = shutil.which("claude")
        if not self.exe:
            raise LlmError("Không tìm thấy lệnh `claude` trong PATH.")
        self.model = model or os.environ.get("CADGUARD_MODEL")

    def complete(self, system: str, messages: list[dict]) -> str:
        convo = "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in messages)
        cmd = [self.exe, "-p", "--output-format", "json", "--tools", "", "--no-session-persistence", "--system-prompt", system]
        if self.model:
            cmd += ["--model", self.model]
        with tempfile.TemporaryDirectory(prefix="cadguard-llm-") as empty:  # thư mục rỗng: CLI không có gì khác để đọc
            p = subprocess.run(cmd, input=convo, capture_output=True, text=True, encoding="utf-8", cwd=empty, timeout=300)
        if p.returncode != 0:
            raise LlmError(f"CLI claude lỗi (mã {p.returncode}): {p.stderr.strip()[:300]}")
        try:
            return str(json.loads(p.stdout).get("result", ""))
        except json.JSONDecodeError:
            return p.stdout


def auto_backend() -> Backend | None:
    """Ưu tiên khoá API; không có thì CLI; không có nữa thì None (ứng dụng vẫn chạy, không chat)."""
    for factory in (AnthropicBackend, ClaudeCliBackend):
        try:
            return factory()
        except LlmError:
            continue
    return None


SYSTEM_PROMPT = """Bạn là kỹ sư thẩm tra bản vẽ kỹ thuật nội thất, làm việc cùng thợ vẽ/kỹ sư của một xưởng sản xuất. Trả lời bằng tiếng Việt.

Bạn nhận BẢN TÓM TẮT bản vẽ (JSON do mã trích ra từ DXF: layer, cụm hình học C1.., hình chữ nhật, chữ, số đo, khối INSERT, kết quả dựng 3D, các phần còn thiếu).

QUY TẮC CỨNG:
1. Bạn chỉ ĐỀ XUẤT. Không khẳng định đúng/sai tuyệt đối; điều bạn nhận xét là "gợi ý chưa kiểm" cho đến khi mã tất định hoặc người dùng xác nhận.
2. Mọi con số phải lấy từ bản tóm tắt hoặc người dùng nói. Không bịa kích thước. Không chắc thì đặt vào "questions".
3. Hình chiếu: "front" = mặt đứng (ngang X, dọc Z); "side" = mặt bên (ngang là chiều sâu từ mặt trước, dọc Z); "top" = mặt bằng (ngang X, dọc là chiều sâu từ mặt trước). Dùng mã cụm (C1...) để chỉ hình chiếu.
4. Tìm lỗ hổng/bất hợp lý kỹ thuật: thiếu hình chiếu, kích thước mâu thuẫn giữa các hình, tấm không có chiều sâu, nhịp đợt quá dài so với độ dày, thiếu liên kết/mối ghép, đơn vị lạ, chi tiết trùng, ghi chú mâu thuẫn bản vẽ...
5. Mỗi nhận xét nên kèm "refs" (tay cầm, mã cụm hoặc mã tấm) để người dùng xem chỗ nào.

ĐỊNH DẠNG: chỉ trả MỘT đối tượng JSON, không chữ ngoài:
{"reply": "lời trả lời ngắn cho người dùng",
 "observations": [{"severity": "info|warn|error", "text": "...", "refs": ["..."]}],
 "proposals": [
   {"kind": "set_views", "views": {"front": "C1", "side": "C2", "top": "C3"}, "why": "..."},
   {"kind": "set_value", "key": "<khoá trường thiếu có trong scene.gaps[].fields>", "value": "500", "why": "..."},
   {"kind": "set_attrib", "handle": "<tay cầm INSERT>", "tag": "H", "value": "850", "why": "..."},
   {"kind": "change_layer", "handles": ["..."], "layer": "FN-VIEW-FRONT", "why": "..."}],
 "questions": ["câu hỏi cần người dùng trả lời"]}
Chỉ dùng đúng 4 loại đề xuất trên. Không đề xuất khi thiếu căn cứ; hỏi người dùng."""

ANALYZE_PROMPT = (
    "Hãy phân tích bản vẽ này lần đầu: (1) xác định cụm nào là mặt đứng/mặt bên/mặt bằng nếu chưa dựng được 3D, "
    "(2) liệt kê lỗ hổng và điểm bất hợp lý kỹ thuật, (3) đề xuất cách xử lý các phần thiếu, "
    "(4) nêu câu hỏi cần người dùng làm rõ."
)
