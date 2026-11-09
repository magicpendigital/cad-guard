"""Sổ khai báo công cụ trợ lý DUY NHẤT: tên, mô tả, JSON schema, loại (đọc/đề xuất), hàm xử lý, kiểm tham số, xử lý lỗi.

Máy chủ MCP (`cadguard.mcp_server`) và engine API (`cadguard.assistant.toolspec.ToolBox`) đều sinh danh sách công cụ và
gọi công cụ qua đây, nên thêm/sửa công cụ chỉ ở MỘT chỗ. Hàm thật nằm ở `cadguard.agent.tools` (nạp lười, để module này
nhẹ: không kéo ezdxf khi chỉ cần liệt kê công cụ).

Bất biến:
- Không bao giờ có công cụ áp dụng (apply). `propose_changeset` chỉ khi `allow_propose`; `show_in_autocad` chỉ khi
  `allow_autocad` (đưa AutoCAD tới đối tượng, không sửa bản vẽ).
- Lỗi trả cho trợ lý là câu tiếng Việt chung: không đường dẫn tuyệt đối, không giá trị tham số, không ngoại lệ nội bộ.
- Kiểm tham số bằng bộ kiểm nhỏ cho đúng tập con JSON Schema dùng ở đây (không phụ thuộc gói `jsonschema`).
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

DEFAULT_STANDARD = "furniture-v0"
PROPOSE_DEFAULT_STANDARD = "design-hygiene-v0"
MAX_QUERY_RECORDS = 500
MAX_QUERY_BYTES = 65536
MAX_DIFF_ITEMS = 500
MAX_PROPOSE_OPS = 50

READ_TOOLS = ("list_drawings", "audit", "explain_rule", "get_model_summary", "query_model", "diff")
PROPOSE_TOOL = "propose_changeset"
AUTOCAD_TOOL = "show_in_autocad"  # M3: chỉ khi allow_autocad; điều hướng AutoCAD, không sửa bản vẽ
BASELINE_TOOL = "audit_khong_ho_so"
FORBIDDEN_TOOLS = frozenset({"apply_changeset", "apply", "undo", "undo_changeset"})

PATH_DENIED_MSG = "Đường dẫn không được phép: chỉ nhận tệp .dxf nằm trong thư mục làm việc, viết dạng tương đối."
GENERIC_ERROR_MSG = "Không thể thực hiện yêu cầu; hãy kiểm tra dữ liệu và đường dẫn."
STANDARD_PATTERN = r"^[a-z0-9][a-z0-9.\-]*$"


@dataclass(frozen=True)
class SpecOptions:
    """Những gì làm mô tả/schema thay đổi theo phiên: chuẩn mặc định, chuẩn có sẵn, hồ sơ, trần kết quả, cờ bật."""

    default_standard: str = DEFAULT_STANDARD
    standards_available: tuple[str, ...] = ()
    profile_note: str = ""
    max_findings: int = 200
    max_drawings: int = 500
    allow_propose: bool = False
    compare_without_profile: bool = False
    allow_autocad: bool = False


@dataclass(frozen=True)
class ToolDef:
    name: str
    kind: Literal["read", "propose", "navigate"]
    describe: Callable[[SpecOptions], str]
    schema: Callable[[SpecOptions], dict]
    run: Callable[[Any, dict, SpecOptions], dict]  # (ToolContext, tham số đã kiểm, tuỳ chọn) -> dict JSON

    @property
    def read_only(self) -> bool:
        return self.kind == "read"


# ---------- mảnh schema dùng chung ----------

def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


_FILE = {"type": "string", "minLength": 1, "maxLength": 1024,
         "description": "Tệp .dxf: đường dẫn tương đối trong thư mục làm việc (vd. 'a/b.dxf') hoặc mã tệp (F_…) từ list_drawings."}
_STR_OR_LIST = {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}, "maxItems": 200}, {"type": "null"}]}


def _standard_arg(o: SpecOptions, default: str | None = None) -> dict:
    default = default or o.default_standard
    have = ", ".join(o.standards_available) or default
    return {"type": "string", "pattern": STANDARD_PATTERN, "default": default,
            "description": f"Tên chuẩn (mặc định {default}); có: {have}.{o.profile_note}"}


def _std(args: dict, o: SpecOptions) -> str:
    return args.get("standard") or o.default_standard


def _tools():
    from . import tools  # nạp lười: kéo ezdxf/bộ đọc DXF

    return tools


# ---------- khai báo từng công cụ ----------

def _list_drawings() -> ToolDef:
    return ToolDef(
        "list_drawings", "read",
        lambda o: f"Liệt kê tệp DXF trong thư mục làm việc (tối đa {o.max_drawings} mục; 'truncated' báo bị cắt). "
                  "Trả mã tệp (id) dùng cho các công cụ khác, và kích thước.",
        lambda o: _obj({"dir": {"type": "string", "default": ".", "maxLength": 1024,
                                "description": "Thư mục con tương đối trong thư mục làm việc; '.' là gốc."}}, []),
        lambda ctx, a, o: _tools().list_drawings(ctx, a.get("dir") or "."),
    )


def _audit() -> ToolDef:
    return ToolDef(
        "audit", "read",
        lambda o: "Kiểm tra một bản vẽ theo chuẩn bằng luật tất định (vd. furniture-v0, hoặc design-hygiene-v0 cho vệ sinh "
                  "bản vẽ). 'profile' ghi tên/phiên bản hồ sơ công ty đã áp (null nếu không áp). Trả số lỗi theo mức (E/W/I), "
                  f"luật đã chạy/bỏ qua và tối đa {o.max_findings} phát hiện (mỗi phát hiện có 'handles' để người dùng tìm "
                  "đối tượng, vd. lệnh CGTOI trong AutoCAD). 'records_capped' = true nghĩa là danh sách đối tượng bị cắt ở "
                  "trần bộ nhớ (tệp rất lớn), phát hiện có thể thiếu.",
        lambda o: _obj({"file": _FILE, "standard": _standard_arg(o)}, ["file"]),
        lambda ctx, a, o: _tools().audit(ctx, a["file"], _std(a, o)),
    )


def _baseline() -> ToolDef:
    def run(ctx, a, o):
        import dataclasses

        return _tools().audit(dataclasses.replace(ctx, profile=None), a["file"], _std(a, o))

    return ToolDef(
        BASELINE_TOOL, "read",
        lambda o: "Như audit nhưng KHÔNG áp hồ sơ công ty (ngưỡng mặc định của chuẩn), để so trước/sau hồ sơ.",
        lambda o: _obj({"file": _FILE, "standard": _standard_arg(o)}, ["file"]),
        run,
    )


def _explain_rule() -> ToolDef:
    return ToolDef(
        "explain_rule", "read",
        lambda o: "Giải thích một mã luật (vd. LY-01): tiêu đề, mức độ, loại, nguồn, tham số chung và đoạn mô tả trong chuẩn.",
        lambda o: _obj({"rule_id": {"type": "string", "minLength": 1, "maxLength": 32, "description": "Mã luật, vd. 'LY-01'."},
                        "standard": _standard_arg(o)}, ["rule_id"]),
        lambda ctx, a, o: _tools().explain_rule(ctx, a["rule_id"], _std(a, o)),
    )


def _summary() -> ToolDef:
    return ToolDef(
        "get_model_summary", "read",
        lambda o: "Tóm tắt Drawing Model của một bản vẽ: số layer/khối, đối tượng theo loại và không gian, layout, kiểu chữ, "
                  "đơn vị, phiên bản DXF (JSON tối đa 16 KB). 'records_capped' = true: số đếm đối tượng bị cắt ở trần bộ nhớ.",
        lambda o: _obj({"file": _FILE}, ["file"]),
        lambda ctx, a, o: _tools().get_model_summary(ctx, a["file"]),
    )


def _query() -> ToolDef:
    flt = {"anyOf": [_obj({
        "layer": {**_STR_OR_LIST, "description": "Tên layer hoặc mã layer (L_…); một giá trị hoặc danh sách."},
        "type": {**_STR_OR_LIST, "description": "Loại đối tượng DXF, vd. LINE, LWPOLYLINE, TEXT, INSERT, DIMENSION."},
        "space": {**_STR_OR_LIST, "description": "Không gian: 'Model' hoặc tên/mã layout (Y_…)."},
    }, []), {"type": "null"}], "description": "Bộ lọc; bỏ trống = mọi đối tượng. AND giữa khoá, OR trong danh sách."}

    def run(ctx, a, o):
        raw = a.get("filter") or {}
        return _tools().query_model(ctx, a["file"], {k: v for k, v in raw.items() if v is not None},
                                    int(a.get("limit", 100)), a.get("cursor"))

    return ToolDef(
        "query_model", "read",
        lambda o: f"Lọc đối tượng trong bản vẽ theo layer/loại/không gian, có phân trang: mỗi trang tối đa {MAX_QUERY_RECORDS} "
                  f"mục và {MAX_QUERY_BYTES // 1024} KB; còn nữa thì 'next_cursor' khác null, gửi lại nguyên bộ lọc cùng cursor "
                  "để lấy trang sau. 'records_capped' = true: total_matched bị cắt ở trần bộ nhớ.",
        lambda o: _obj({
            "file": _FILE,
            "filter": flt,
            "limit": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_RECORDS, "default": 100,
                      "description": f"Số mục tối đa mỗi trang (1–{MAX_QUERY_RECORDS})."},
            "cursor": {"type": ["string", "null"], "maxLength": 4096,
                       "description": "Giá trị 'next_cursor' của trang trước; bỏ trống ở trang đầu."},
        }, ["file"]),
        run,
    )


def _diff() -> ToolDef:
    return ToolDef(
        "diff", "read",
        lambda o: "So hai bản vẽ DXF trong thư mục làm việc theo handle (như git diff): đối tượng thêm/xoá/đổi (thuộc tính "
                  "nào), định nghĩa layer/kiểu chữ/kiểu kích thước/khối thêm/xoá, tóm tắt số liệu. Đã ẩn danh; chữ trong bản "
                  "vẽ bị che. JSON tối đa 64 KB, 'truncated' báo danh sách bị cắt (số tổng trong 'summary' luôn đủ).",
        lambda o: _obj({
            "a": {**_FILE, "description": "Tệp trước (thường là bản gốc): đường dẫn tương đối hoặc mã tệp."},
            "b": {**_FILE, "description": "Tệp sau (vd. tệp .cg-<mã>.dxf do người dùng áp dụng)."},
            "max_items": {"type": "integer", "minimum": 1, "maximum": MAX_DIFF_ITEMS, "default": 100,
                          "description": f"Số mục tối đa mỗi danh sách (1–{MAX_DIFF_ITEMS})."},
        }, ["a", "b"]),
        lambda ctx, a, o: _tools().diff(ctx, a["a"], a["b"], int(a.get("max_items", 100))),
    )


def _propose() -> ToolDef:
    def describe(o: SpecOptions) -> str:
        from ..changeset.ops import OP_HELP

        ops_doc = "; ".join(f"{k}: {v}" for k, v in OP_HELP.items())
        return ("ĐỀ XUẤT sửa bản vẽ bằng từ vựng thao tác cố định, CHẠY KHÔ trên bản sao trong bộ nhớ: kiểm schema, đếm đối "
                "tượng bị ảnh hưởng, dự báo luật hết/xuất hiện (rules_regressed phải = 0), trả xem trước. Lưu changeset JSON "
                "vào thư mục phiên; KHÔNG ghi DXF và KHÔNG áp dụng — người dùng tự áp bằng `cadguard apply <changeset_id>`. "
                "Không có thao tác xoá đối tượng hình học. Tên layer/kiểu chữ dùng mã phiên (L_…, S_…, D_…, Y_…) như các công "
                f"cụ khác. Thao tác: {ops_doc}. Bộ lọc 'filter': {{layers, exclude_layers, types, spaces}} (AND giữa khoá, OR "
                "trong danh sách).")

    return ToolDef(
        PROPOSE_TOOL, "propose", describe,
        lambda o: _obj({
            "file": _FILE,
            "ops": {"type": "array", "minItems": 1, "maxItems": MAX_PROPOSE_OPS, "items": {"type": "object"},
                    "description": f"Danh sách thao tác, mỗi mục có 'op' và tham số; tối đa {MAX_PROPOSE_OPS}."},
            "standard": {**_standard_arg(o, PROPOSE_DEFAULT_STANDARD),
                         "description": f"Chuẩn dùng để dự báo luật (mặc định {PROPOSE_DEFAULT_STANDARD})."},
            "protected_layers": {"anyOf": [{"type": "array", "items": {"type": "string"}, "maxItems": 200}, {"type": "null"}],
                                 "description": "Layer bảo vệ thêm (tên/mã L_…); thao tác chạm bị từ chối."},
        }, ["file", "ops"]),
        lambda ctx, a, o: _tools().propose_changeset(ctx, a["file"], a["ops"], a.get("standard") or PROPOSE_DEFAULT_STANDARD,
                                                     a.get("protected_layers")),
    )


def _show_in_autocad() -> ToolDef:
    return ToolDef(
        AUTOCAD_TOOL, "navigate",
        lambda o: "Đưa người dùng tới đối tượng trong AutoCAD đang mở: phóng tới và CHỌN các đối tượng theo handle (lấy từ "
                  "audit) hoặc mọi đối tượng trên layer (tên/mã L_…). Chỉ điều hướng, không sửa/lưu bản vẽ. Bản vẽ phải đang mở "
                  "trong AutoCAD; nếu không gửi thẳng được ('sent' = false) thì người dùng gõ CGDEN trong AutoCAD.",
        lambda o: _obj({
            "file": _FILE,
            "handles": {"type": "array", "items": {"type": "string", "pattern": "^[0-9A-Fa-f]{1,16}$"}, "maxItems": 200,
                        "description": "Handle đối tượng (từ audit), vd. ['18E', '3A247']."},
            "layers": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 255}, "maxItems": 100,
                       "description": "Tên hoặc mã layer (L_…): chọn mọi đối tượng trên layer trong tờ đang xem."},
        }, ["file"]),
        lambda ctx, a, o: _tools().show_in_autocad(ctx, a["file"], a.get("handles"), a.get("layers")),
    )


_READ_DEFS: tuple[Callable[[], ToolDef], ...] = (_list_drawings, _audit, _explain_rule, _summary, _query, _diff)


def tool_defs(o: SpecOptions) -> list[ToolDef]:
    """Công cụ của một phiên theo thứ tự cố định: 6 công cụ đọc; + bản không hồ sơ khi so sánh; + propose khi bật."""
    out = [f() for f in _READ_DEFS]
    if o.compare_without_profile:
        out.append(_baseline())
    if o.allow_propose:
        out.append(_propose())
    if o.allow_autocad:
        out.append(_show_in_autocad())
    assert not FORBIDDEN_TOOLS & {d.name for d in out}  # bất biến: không bao giờ có apply
    return out


def specs(o: SpecOptions) -> list[dict]:
    """[{name, description, schema, read_only}] — dạng trung lập; MCP và engine API tự đổi sang khuôn của mình."""
    return [{"name": d.name, "description": d.describe(o), "schema": d.schema(o), "read_only": d.read_only} for d in tool_defs(o)]


def options_for(ctx, default_standard: str | None = None, *, allow_propose: bool = False,
                compare_without_profile: bool = False, allow_autocad: bool = False) -> SpecOptions:
    """Tuỳ chọn mô tả từ một `ToolContext`: chuẩn có trong thư mục chuẩn, ghi chú hồ sơ, trần kết quả."""
    from pathlib import Path

    prof = ctx.profile
    available = tuple(sorted(
        p.stem for p in Path(ctx.standards_dir).glob("*.yaml")
        if re.fullmatch(r"[a-z0-9][a-z0-9.\-]*", p.stem) and not p.stem.startswith("company-profile")
    ))
    note = f" Hồ sơ công ty '{prof.name}' {prof.version} được áp khi chuẩn là {prof.standard}." if prof is not None else ""
    return SpecOptions(
        default_standard=default_standard or (prof.standard if prof is not None else DEFAULT_STANDARD),
        standards_available=available, profile_note=note, max_findings=ctx.max_findings, max_drawings=ctx.max_drawings,
        allow_propose=bool(allow_propose), compare_without_profile=bool(compare_without_profile and prof is not None),
        allow_autocad=bool(allow_autocad),
    )


# ---------- kiểm tham số (tập con JSON Schema đang dùng) ----------

_TYPES: dict[str, Callable[[Any], bool]] = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def check_args(schema: dict, value: Any, where: str = "") -> str | None:
    """Trả câu lỗi tiếng Việt (chỉ nêu TÊN trường, không nêu giá trị) hoặc None nếu hợp lệ."""
    label = where or "tham số"
    if "anyOf" in schema:
        if all(check_args(s, value, where) for s in schema["anyOf"]):
            return f"{label}: kiểu không hợp lệ."
        return None
    types = schema.get("type")
    if types is not None:
        types = [types] if isinstance(types, str) else types
        if not any(_TYPES[t](value) for t in types):
            return f"{label}: phải là {' hoặc '.join(types)}."
    if isinstance(value, dict) and schema.get("type") == "object":
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(props))
            if extra:
                return f"Tham số lạ{' trong ' + where if where else ''}: {', '.join(extra)}."
        for req in schema.get("required", []):
            if req not in value:
                return f"Thiếu tham số bắt buộc: {req}."
        for k, v in value.items():
            if k in props:
                err = check_args(props[k], v, f"{where}.{k}" if where else k)
                if err:
                    return err
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 1 << 30):
            return f"{label}: độ dài không hợp lệ."
        if "pattern" in schema and not re.search(schema["pattern"], value):
            return f"{label}: sai định dạng."
    if _TYPES["number"](value):
        if value < schema.get("minimum", float("-inf")) or value > schema.get("maximum", float("inf")):
            return f"{label}: ngoài khoảng cho phép."
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", 1 << 30):
            return f"{label}: số phần tử không hợp lệ."
        if "items" in schema:
            for i, item in enumerate(value):
                err = check_args(schema["items"], item, f"{label}[{i}]")
                if err:
                    return err
    return None


# ---------- gọi công cụ ----------

@dataclass
class CallResult:
    ok: bool
    data: dict | None = None
    error: str | None = None
    meta: dict = field(default_factory=dict)

    def text(self) -> str:
        return json.dumps(self.data, ensure_ascii=False) if self.ok else str(self.error)


def call(ctx, name: str, args: Any, o: SpecOptions) -> CallResult:
    """Kiểm tham số theo schema rồi gọi hàm thật; mọi lỗi đổi thành câu an toàn."""
    from .workspace import PathDenied

    defs = {d.name: d for d in tool_defs(o)}
    if name not in defs:
        return CallResult(False, error=f"Không có công cụ '{name}'. Công cụ có: {', '.join(defs)}.")
    if not isinstance(args, dict):  # None = engine không đọc được JSON tham số: báo lỗi cho mô hình, không đoán
        return CallResult(False, error="Tham số công cụ phải là đối tượng JSON.")
    d = defs[name]
    err = check_args(d.schema(o), args)
    if err:
        return CallResult(False, error=f"{name}: {err}")
    tools = _tools()
    try:
        data = d.run(ctx, args, o)
    except tools.ToolError as exc:  # thông điệp đã an toàn (tiếng Việt, không đường dẫn)
        return CallResult(False, error=str(exc))
    except PathDenied:
        return CallResult(False, error=PATH_DENIED_MSG)
    except Exception:  # noqa: BLE001 — không lộ chi tiết nội bộ
        return CallResult(False, error=GENERIC_ERROR_MSG)
    return CallResult(True, data=data)


__all__ = ["AUTOCAD_TOOL", "BASELINE_TOOL", "DEFAULT_STANDARD", "FORBIDDEN_TOOLS", "GENERIC_ERROR_MSG", "MAX_QUERY_BYTES",
           "MAX_QUERY_RECORDS", "PATH_DENIED_MSG", "PROPOSE_TOOL", "READ_TOOLS", "CallResult", "SpecOptions", "ToolDef",
           "call", "check_args", "options_for", "specs", "tool_defs"]
