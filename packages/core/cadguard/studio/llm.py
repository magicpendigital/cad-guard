"""Các lớp nối LLM. Mỗi lớp chỉ có `complete(system, messages) -> str` (văn bản, kỳ vọng là JSON).

- AnthropicBackend: khoá từ biến môi trường ANTHROPIC_API_KEY (không ghi ra tệp); cần `pip install -e .[llm]`.
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

DEFAULT_MODEL = "claude-sonnet-5-5"


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
    name = "anthropic-api"

    def __init__(self, model: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise LlmError("Chưa cài gói anthropic: pip install -e .[llm]") from exc
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LlmError("Chưa đặt biến môi trường ANTHROPIC_API_KEY.")
        self.client = anthropic.Anthropic(api_key=key)
        self.model = model or os.environ.get("CADGUARD_MODEL", DEFAULT_MODEL)

    def complete(self, system: str, messages: list[dict]) -> str:
        r = self.client.messages.create(model=self.model, max_tokens=4096, system=system, messages=messages)
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")


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
