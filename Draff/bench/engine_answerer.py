"""Người trả lời THẬT cho bộ chấm (bước A1): hỏi một engine trợ lý AI của cad-guard (`cadguard.assistant`).

  python scripts/bench.py --engine claude-cli                  # CLI người dùng đã cài + tự đăng nhập
  python scripts/bench.py --engine anthropic --model claude-sonnet-5-5
  python scripts/bench.py --answerer bench.engine_answerer:answer   # đọc CADGUARD_BENCH_ENGINE / _MODEL

Biến môi trường: CADGUARD_BENCH_ENGINE (bắt buộc khi dùng `answer`), CADGUARD_BENCH_MODEL, CADGUARD_BENCH_ACCOUNT
(agy-cli), CADGUARD_BENCH_EXPERIMENTAL=1 (codex-cli), CADGUARD_BENCH_TIMEOUT (giây/tác vụ).

Mỗi tác vụ: engine được nối với công cụ cad-guard trên thư mục làm việc tạm của tác vụ (đúng các cờ `moi_truong`:
ẩn danh, ngưỡng đọc theo dòng, trần bản ghi, hồ sơ công ty — kèm một bộ công cụ KHÔNG hồ sơ để so trước/sau),
nhận `cau_hoi` + yêu cầu trả JSON theo `tra_loi`, rồi trích JSON từ câu trả lời. `_chi_phi` = token, USD, giây;
`_cong_cu` = tên các công cụ engine đã gọi (từ sự kiện `tool_call`, không tham số) để QC xác nhận chỉ có công cụ
cad-guard.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Callable

TYPE_VI = {
    "so_nguyen": "số nguyên",
    "chuoi": "chuỗi",
    "dung_sai": "true/false",
    "danh_sach": "mảng JSON",
    "doi_tuong": "đối tượng JSON (hoặc null)",
}
PROFILE_FILE = "ho-so.yaml"


def build_prompt(task: dict) -> str:
    fields = "\n".join(f'- "{k}": {TYPE_VI.get(v, v)}' for k, v in task["tra_loi"].items())
    params = task.get("tham_so") or {}
    extra = f"\nTham số của câu hỏi (JSON): {json.dumps(params, ensure_ascii=False)}" if params else ""
    return (
        f"{task['cau_hoi'].strip()}{extra}\n\n"
        "Dùng công cụ cad-guard để lấy số liệu; không đoán. Thư mục làm việc chỉ chứa bản vẽ của tác vụ này.\n"
        "Cuối câu trả lời, in ĐÚNG MỘT khối ```json chứa một đối tượng JSON có các trường sau (đúng kiểu, "
        "mã luật như 'VS-01', mã phiên như trả về từ công cụ):\n" + fields
    )


def extract_json(text: str, keys: list[str] | None = None) -> dict:
    """Lấy đối tượng JSON từ câu trả lời: ưu tiên khối ```json cuối cùng, rồi đối tượng {…} chứa nhiều trường nhất."""
    text = text or ""
    candidates = []
    for block in re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.S):
        try:
            obj = json.loads(block)
            if isinstance(obj, dict):
                candidates.append(obj)
        except json.JSONDecodeError:
            pass
    if not candidates:
        dec = json.JSONDecoder()
        for i, ch in enumerate(text):
            if ch == "{":
                try:
                    obj, _ = dec.raw_decode(text[i:])
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    candidates.append(obj)
    if not candidates:
        raise ValueError("câu trả lời không có đối tượng JSON")
    if keys:
        return max(reversed(candidates), key=lambda o: sum(k in o for k in keys))
    return candidates[-1]


def _server_options(env: dict) -> dict:
    opts = {"anonymize": env.get("an_danh", True)}
    if env.get("stream_threshold_mb") is not None:
        opts["stream_threshold_mb"] = env["stream_threshold_mb"]
    if env.get("max_entity_records") is not None:
        opts["max_entity_records"] = env["max_entity_records"]
    return opts


def make_answerer(engine_factory: Callable[[], object]) -> Callable[[dict, Path], dict]:
    """Tạo hàm `answer(task, workspace)` dùng engine do `engine_factory()` tạo (mỗi tác vụ một engine mới)."""

    def answer(task: dict, workspace: Path) -> dict:
        from cadguard.assistant import Usage

        engine = engine_factory()
        env = task.get("moi_truong") or {}
        ws = Path(workspace)
        profile = ws / PROFILE_FILE if env.get("ho_so") else None
        std = (task.get("tham_so") or {}).get("chuan")
        start = time.perf_counter()
        total, text, errors, tools = Usage(cost_usd=None), "", [], []
        for e in engine.run([{"role": "user", "content": build_prompt(task)}], workspace=ws, standard=std,
                            profile=profile, compare_without_profile=profile is not None,
                            server_options=_server_options(env)):
            if e.type == "usage":
                total.add(e.data["usage"])
            elif e.type == "tool_call":
                tools.append(str(e.data.get("name") or "?"))  # chỉ tên, không tham số
            elif e.type == "error":
                errors.append(e.data["message"])
            elif e.type == "done":
                text = e.data.get("text", "")
        cost = {"tokens": total.total_tokens, "usd": float(total.cost_usd or 0.0),
                "giay": round(time.perf_counter() - start, 3)}
        try:
            result = extract_json(text, list(task["tra_loi"]))
        except ValueError:
            raise RuntimeError("; ".join(errors) or "câu trả lời không có JSON") from None
        result = dict(result)
        result["_chi_phi"] = cost
        result["_cong_cu"] = tools  # theo thứ tự gọi; rỗng = không thấy sự kiện tool_call nào
        return result

    return answer


def _engine_from_env():
    from cadguard.assistant import create_engine

    name = os.environ.get("CADGUARD_BENCH_ENGINE")
    if not name:
        raise RuntimeError("Chưa đặt CADGUARD_BENCH_ENGINE (vd. claude-cli, anthropic).")
    timeout = os.environ.get("CADGUARD_BENCH_TIMEOUT")
    engine = create_engine(name, model=os.environ.get("CADGUARD_BENCH_MODEL") or None,
                         experimental=os.environ.get("CADGUARD_BENCH_EXPERIMENTAL") == "1",
                         account=os.environ.get("CADGUARD_BENCH_ACCOUNT") or None,
                         timeout=float(timeout) if timeout else None,
                         allow_openrouter=os.environ.get("CADGUARD_ALLOW_OPENROUTER") == "1")
    if not _WARNED:
        _WARNED.append(True)
        for warning in getattr(engine, "auth_warnings", lambda: [])():
            print(f"[cảnh báo] {warning}", file=sys.stderr)
    return engine


_WARNED: list = []  # cảnh báo biến khoá API chỉ in một lần mỗi lượt chấm


answer = make_answerer(_engine_from_env)
