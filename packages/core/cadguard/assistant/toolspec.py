"""Công cụ cad-guard cho engine API: lược đồ JSON + gọi thẳng hàm trong `cadguard.agent.tools`.

Cùng hành vi với máy chủ MCP (`cadguard mcp`): ẩn danh Bậc 1 mặc định, chỉ đọc; `propose_changeset` chỉ khi
`allow_propose`; KHÔNG BAO GIỜ có công cụ áp dụng (apply). Lỗi trả về là câu tiếng Việt chung.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from ..agent import tools
from ..agent.anonymize import Anonymizer
from ..agent.workspace import PathDenied, Workspace
from ..dxf_stream import DEFAULT_MAX_ENTITY_RECORDS
from ..reader_select import DEFAULT_STREAM_THRESHOLD_MB
from ..standard import ProfileError, find_standards_dir, load_profile
from .base import EngineError

DEFAULT_STANDARD = "furniture-v0"
PATH_DENIED_MSG = "Đường dẫn không được phép: chỉ nhận tệp .dxf nằm trong thư mục làm việc, viết dạng tương đối."
GENERIC_ERROR_MSG = "Không thể thực hiện yêu cầu; hãy kiểm tra dữ liệu và đường dẫn."
BASELINE_TOOL = "audit_khong_ho_so"

_FILE = {"type": "string", "description": "Tệp .dxf: đường dẫn tương đối trong thư mục làm việc hoặc mã tệp (F_…) từ list_drawings."}
_STD = {"type": "string", "description": "Tên chuẩn, vd. furniture-v0 hoặc design-hygiene-v0.", "pattern": "^[a-z0-9][a-z0-9.\\-]*$"}
_STR_OR_LIST = {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


TOOL_SPECS: dict[str, dict] = {
    "list_drawings": {
        "description": "Liệt kê tệp DXF trong thư mục làm việc; trả mã tệp (id) dùng cho công cụ khác và kích thước.",
        "schema": _obj({"dir": {"type": "string", "description": "Thư mục con tương đối; '.' là gốc."}}, []),
    },
    "audit": {
        "description": "Kiểm một bản vẽ theo chuẩn bằng luật tất định: số lỗi theo mức (E/W/I), luật đã chạy/bỏ qua, "
        "phát hiện; 'profile' là hồ sơ công ty đã áp (null nếu không); 'records_capped' = true: dữ liệu bị cắt.",
        "schema": _obj({"file": _FILE, "standard": _STD}, ["file"]),
    },
    "explain_rule": {
        "description": "Giải thích một mã luật (vd. VS-06): tiêu đề, mức, loại, nguồn, tham số, mô tả trong chuẩn.",
        "schema": _obj({"rule_id": {"type": "string", "description": "Mã luật, vd. 'LY-01'."}, "standard": _STD}, ["rule_id"]),
    },
    "get_model_summary": {
        "description": "Tóm tắt mô hình bản vẽ: số layer/khối, đối tượng theo loại và không gian, layout, kiểu chữ, đơn vị, phiên bản DXF.",
        "schema": _obj({"file": _FILE}, ["file"]),
    },
    "query_model": {
        "description": f"Lọc đối tượng theo layer/loại/không gian, có phân trang (tối đa {tools.MAX_QUERY_RECORDS} mục/trang); "
        "còn trang sau thì 'next_cursor' khác null, gửi lại nguyên bộ lọc cùng cursor.",
        "schema": _obj({
            "file": _FILE,
            "filter": {"type": "object", "properties": {"layer": _STR_OR_LIST, "type": _STR_OR_LIST, "space": _STR_OR_LIST},
                       "additionalProperties": False, "description": "Bộ lọc; AND giữa khoá, OR trong danh sách."},
            "limit": {"type": "integer", "minimum": 1, "maximum": tools.MAX_QUERY_RECORDS},
            "cursor": {"type": ["string", "null"]},
        }, ["file"]),
    },
    "diff": {
        "description": "So hai DXF trong thư mục làm việc theo handle: đối tượng thêm/xoá/đổi, định nghĩa thêm/xoá; đã ẩn danh.",
        "schema": _obj({"a": _FILE, "b": _FILE, "max_items": {"type": "integer", "minimum": 1, "maximum": 500}}, ["a", "b"]),
    },
}

PROPOSE_SPEC = {
    "description": "ĐỀ XUẤT sửa bản vẽ (chạy khô trên bản sao trong bộ nhớ) bằng từ vựng thao tác cố định; lưu changeset JSON, "
    "KHÔNG ghi DXF, KHÔNG áp dụng. Người dùng tự áp bằng `cadguard apply <changeset_id>`. Dùng mã phiên (L_…, S_…).",
    "schema": _obj({
        "file": _FILE,
        "ops": {"type": "array", "minItems": 1, "maxItems": 50, "items": {"type": "object"},
                "description": "Danh sách thao tác, mỗi mục có 'op' và tham số."},
        "standard": _STD,
        "protected_layers": {"type": "array", "items": {"type": "string"}},
    }, ["file", "ops"]),
}

BASELINE_SPEC = {
    "description": "Như audit nhưng KHÔNG áp hồ sơ công ty (ngưỡng mặc định của chuẩn), để so trước/sau hồ sơ.",
    "schema": _obj({"file": _FILE, "standard": _STD}, ["file"]),
}


class ToolBox:
    """Bộ công cụ của một phiên engine API: giữ `ToolContext` (ẩn danh ổn định suốt phiên)."""

    def __init__(self, workspace: Path, *, standard: str | None = None, profile: Path | None = None,
                 allow_propose: bool = False, compare_without_profile: bool = False, anonymize: bool = True,
                 stream_threshold_mb: float | None = DEFAULT_STREAM_THRESHOLD_MB,
                 max_entity_records: int = DEFAULT_MAX_ENTITY_RECORDS):
        try:
            prof = load_profile(profile) if profile else None
        except ProfileError as exc:
            raise EngineError(f"Hồ sơ công ty không dùng được: {exc}", "profile") from None
        try:
            ws = Workspace(Path(workspace))
        except PathDenied:
            raise EngineError("Thư mục làm việc không tồn tại hoặc không phải thư mục.", "workspace") from None
        self.ctx = tools.ToolContext(ws, Anonymizer(enabled=anonymize), find_standards_dir(Path(__file__).resolve()),
                                     stream_threshold_mb=stream_threshold_mb, max_entity_records=max_entity_records,
                                     profile=prof)
        self.standard = standard or (prof.standard if prof else DEFAULT_STANDARD)
        self.allow_propose = bool(allow_propose)
        self.compare = bool(compare_without_profile and prof is not None)

    def specs(self) -> list[dict]:
        """[{name, description, schema}] — chỉ đọc; + propose khi bật; + bản không hồ sơ khi so sánh. Không có apply."""
        out = [{"name": n, **s} for n, s in TOOL_SPECS.items()]
        if self.compare:
            out.append({"name": BASELINE_TOOL, **BASELINE_SPEC})
        if self.allow_propose:
            out.append({"name": "propose_changeset", **PROPOSE_SPEC})
        return out

    def names(self) -> list[str]:
        return [s["name"] for s in self.specs()]

    def call(self, name: str, args) -> tuple[str, bool]:
        """Gọi công cụ; trả (nội dung JSON/chuỗi, is_error)."""
        if name not in self.names():
            return f"Không có công cụ '{name}'. Công cụ có: {', '.join(self.names())}.", True
        if not isinstance(args, dict):
            return "Tham số công cụ phải là đối tượng JSON.", True
        allowed = set(next(s for s in self.specs() if s["name"] == name)["schema"]["properties"])
        extra = set(args) - allowed
        if extra:
            return f"Tham số lạ cho {name}: {', '.join(sorted(extra))}.", True
        ctx, std = self.ctx, args.get("standard") or self.standard
        try:
            if name == "list_drawings":
                data = tools.list_drawings(ctx, args.get("dir", "."))
            elif name == "audit":
                data = tools.audit(ctx, args["file"], std)
            elif name == BASELINE_TOOL:
                data = tools.audit(dataclasses.replace(ctx, profile=None), args["file"], std)
            elif name == "explain_rule":
                data = tools.explain_rule(ctx, args["rule_id"], std)
            elif name == "get_model_summary":
                data = tools.get_model_summary(ctx, args["file"])
            elif name == "query_model":
                data = tools.query_model(ctx, args["file"], args.get("filter") or {}, int(args.get("limit", 100)), args.get("cursor"))
            elif name == "diff":
                data = tools.diff(ctx, args["a"], args["b"], int(args.get("max_items", 100)))
            elif name == "propose_changeset" and self.allow_propose:
                data = tools.propose_changeset(ctx, args["file"], args["ops"], args.get("standard") or "design-hygiene-v0",
                                               args.get("protected_layers"))
            else:  # pragma: no cover — đã chặn ở trên
                return GENERIC_ERROR_MSG, True
        except KeyError as exc:
            return f"Thiếu tham số bắt buộc: {exc.args[0]}.", True
        except tools.ToolError as exc:
            return str(exc), True
        except PathDenied:
            return PATH_DENIED_MSG, True
        except Exception:  # noqa: BLE001 — không lộ chi tiết nội bộ
            return GENERIC_ERROR_MSG, True
        return json.dumps(data, ensure_ascii=False), False
