"""Lược đồ phản hồi của LLM và bước kiểm tất định từng đề xuất.

LLM trả JSON; mọi đề xuất qua `validate_proposals`: sai tham chiếu (cụm, tay cầm, khoá) bị loại kèm lý do hiển thị cho người dùng.
Đề xuất hợp lệ vẫn chỉ là đề xuất: chỉ áp dụng sau khi người dùng duyệt.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ValidationError

VIEW_NAMES = ("front", "top", "side")
LAYER_RE = re.compile(r"^[A-Za-z0-9_\-$]{1,64}$")
MAX_OBS = 30
MAX_PROPOSALS = 20


class Observation(BaseModel):
    severity: str = "info"  # info | warn | error
    text: str
    refs: list[str] = Field(default_factory=list)  # tay cầm / mã cụm / mã tấm
    origin: str = "llm"  # luôn "llm": chưa kiểm tất định


class Proposal(BaseModel):
    id: str = ""
    kind: str  # set_views | set_value | set_attrib | change_layer
    why: str = ""
    views: dict[str, str] | None = None  # set_views: {"front": "C1", ...}
    key: str | None = None  # set_value
    value: str | None = None  # set_value / set_attrib
    handle: str | None = None  # set_attrib
    tag: str | None = None  # set_attrib
    handles: list[str] | None = None  # change_layer
    layer: str | None = None  # change_layer
    status: str = "pending"  # pending | accepted | rejected


class LlmReply(BaseModel):
    reply: str = ""
    observations: list[Observation] = Field(default_factory=list)
    proposals: list[Proposal] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


def extract_json(text: str) -> dict | None:
    """Lấy đối tượng JSON đầu tiên (chịu được hàng rào ```json và chữ thừa)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    cand = fence.group(1) if fence else text
    start = cand.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(cand)):
            ch = cand[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(cand[start : i + 1])
                        return obj if isinstance(obj, dict) else None
                    except json.JSONDecodeError:
                        break
        start = cand.find("{", start + 1)
    return None


def parse_reply(text: str) -> tuple[LlmReply, str | None]:
    """Trả về (phản hồi, ghi chú lỗi). Không bao giờ ném: LLM trả rác thì phản hồi rỗng kèm ghi chú."""
    obj = extract_json(text)
    if obj is None:
        return LlmReply(reply=text.strip()[:4000]), "LLM không trả JSON hợp lệ; hiển thị nguyên văn, không có đề xuất."
    try:
        r = LlmReply.model_validate(obj)
    except ValidationError as exc:
        return LlmReply(reply=str(obj.get("reply", ""))[:4000]), f"Phản hồi LLM sai lược đồ: {exc.error_count()} lỗi; bỏ qua đề xuất."
    r.observations = r.observations[:MAX_OBS]
    for o in r.observations:
        o.origin = "llm"
    return r, None


def validate_proposals(
    props: list[Proposal], *, cluster_ids: set[str], handles: dict[str, str], valid_keys: set[str], start_id: int
) -> tuple[list[Proposal], list[str]]:
    """`handles`: tay cầm -> loại đối tượng. `valid_keys`: các khoá trường còn thiếu đang hỏi người dùng."""
    ok: list[Proposal] = []
    dropped: list[str] = []
    n = start_id
    for p in props[:MAX_PROPOSALS]:
        why = None
        if p.kind == "set_views":
            v = p.views or {}
            if not v or any(k not in VIEW_NAMES for k in v):
                why = "set_views: tên hình chiếu phải là front/top/side"
            elif any(c not in cluster_ids for c in v.values()):
                why = "set_views: mã cụm không tồn tại"
            elif len(set(v.values())) != len(v):
                why = "set_views: một cụm không thể là hai hình chiếu"
        elif p.kind == "set_value":
            try:
                ok_num = p.value is not None and (":" in p.value or float(p.value.replace(",", ".")) > 0)
            except ValueError:
                ok_num = False
            if p.key not in valid_keys:
                why = "set_value: khoá không nằm trong các trường đang thiếu"
            elif not ok_num:
                why = "set_value: giá trị phải là số dương hoặc khoảng 'từ:đến'"
        elif p.kind == "set_attrib":
            if handles.get(p.handle or "") != "INSERT":
                why = "set_attrib: tay cầm không phải khối INSERT"
            elif not p.tag or not re.match(r"^[A-Za-z0-9_]{1,32}$", p.tag) or p.value is None or len(p.value) > 200:
                why = "set_attrib: thẻ hoặc giá trị không hợp lệ"
        elif p.kind == "change_layer":
            if not p.handles or any(h not in handles for h in p.handles) or len(p.handles) > 500:
                why = "change_layer: có tay cầm không tồn tại"
            elif not p.layer or not LAYER_RE.match(p.layer):
                why = "change_layer: tên layer không hợp lệ"
        else:
            why = f"loại đề xuất lạ: {p.kind}"
        if why:
            dropped.append(f"Đề xuất bị loại: {why}.")
            continue
        n += 1
        p.id, p.status = f"p{n}", "pending"
        ok.append(p)
    return ok, dropped
