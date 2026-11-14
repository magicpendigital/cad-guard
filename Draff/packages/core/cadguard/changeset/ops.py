"""Từ vựng thao tác CỐ ĐỊNH của changeset `cg.changeset/1` (chọn A trong plans/cad-guard-agent.md mục 3.2).

Mỗi thao tác là một mô hình pydantic có schema rõ (trường lạ = lỗi). KHÔNG có thao tác xoá đối tượng hình học;
`purge_unused` chỉ xoá ĐỊNH NGHĨA không dùng (layer, kiểu chữ, kiểu kích thước, khối).
Lỗi schema được đổi thành câu tiếng Việt (`OpError`).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

MAX_OPS = 50
NAME_MAX = 255


class OpError(ValueError):
    """Thao tác sai (schema, tham chiếu, layer bảo vệ). Thông điệp tiếng Việt."""


Name = Annotated[str, Field(min_length=1, max_length=NAME_MAX)]
NameList = Annotated[list[Name], Field(min_length=1, max_length=500)]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class EntityFilter(_Base):
    """Bộ lọc đối tượng trực tiếp trong không gian mô hình và giấy (không vào nội dung định nghĩa khối).

    Các khoá kết hợp theo AND; danh sách trong một khoá theo OR. Tên so không phân biệt hoa/thường.
    """

    layers: NameList | None = None
    exclude_layers: NameList | None = None
    types: NameList | None = None
    spaces: NameList | None = None  # "Model" hoặc tên layout


class RenameLayer(_Base):
    op: Literal["rename_layer"]
    from_: Name = Field(alias="from")
    to: Name


class MergeLayers(_Base):
    op: Literal["merge_layers"]
    sources: NameList
    target: Name


class MoveToLayer(_Base):
    op: Literal["move_to_layer"]
    filter: EntityFilter = Field(default_factory=EntityFilter)
    target: Name


class SetByLayer(_Base):
    op: Literal["set_bylayer"]
    filter: EntityFilter = Field(default_factory=EntityFilter)
    color: bool = True
    lineweight: bool = True


class ReplaceTextStyle(_Base):
    op: Literal["replace_text_style"]
    filter: EntityFilter = Field(default_factory=EntityFilter)
    from_: NameList | None = Field(default=None, alias="from")
    to: Name


class ReplaceDimStyle(_Base):
    op: Literal["replace_dim_style"]
    filter: EntityFilter = Field(default_factory=EntityFilter)
    from_: NameList | None = Field(default=None, alias="from")
    to: Name
    rerender: bool = True


PurgeKind = Literal["layers", "text_styles", "dim_styles", "blocks"]
PURGE_KINDS: tuple[str, ...] = ("layers", "text_styles", "dim_styles", "blocks")


class PurgeUnused(_Base):
    op: Literal["purge_unused"]
    kinds: Annotated[list[PurgeKind], Field(min_length=1)] = Field(default_factory=lambda: list(PURGE_KINDS))
    names: NameList | None = None  # chỉ xét các tên này (mọi loại); bỏ trống = mọi định nghĩa không dùng


class SetTextHeight(_Base):
    op: Literal["set_text_height"]
    filter: EntityFilter = Field(default_factory=EntityFilter)
    from_height: Annotated[float, Field(gt=0, le=1e6)] | None = None
    to: Annotated[float, Field(gt=0, le=1e6)]


class ClearDimTextOverride(_Base):
    op: Literal["clear_dim_text_override"]
    filter: EntityFilter = Field(default_factory=EntityFilter)
    rerender: bool = True


Op = Annotated[
    Union[RenameLayer, MergeLayers, MoveToLayer, SetByLayer, ReplaceTextStyle, ReplaceDimStyle, PurgeUnused,
          SetTextHeight, ClearDimTextOverride],
    Field(discriminator="op"),
]
OP_TYPES: dict[str, type[_Base]] = {
    "rename_layer": RenameLayer,
    "merge_layers": MergeLayers,
    "move_to_layer": MoveToLayer,
    "set_bylayer": SetByLayer,
    "replace_text_style": ReplaceTextStyle,
    "replace_dim_style": ReplaceDimStyle,
    "purge_unused": PurgeUnused,
    "set_text_height": SetTextHeight,
    "clear_dim_text_override": ClearDimTextOverride,
}
_ADAPTER = TypeAdapter(list[Op])

# Loại đối tượng mà thao tác theo bộ lọc được chạm tới (None = mọi loại trừ VIEWPORT).
OP_ENTITY_TYPES: dict[str, set[str] | None] = {
    "move_to_layer": None,
    "set_bylayer": None,
    "replace_text_style": {"TEXT", "MTEXT"},
    "replace_dim_style": {"DIMENSION"},
    "set_text_height": {"TEXT", "MTEXT"},
    "clear_dim_text_override": {"DIMENSION"},
}

# Thuộc tính DXF mà mỗi thao tác được phép đổi trên đối tượng (validate_output kiểm).
_DIM_RENDER = {"geometry", "text_midpoint"}
ALLOWED_ATTRS: dict[str, set[str]] = {
    "rename_layer": {"layer"},
    "merge_layers": {"layer"},
    "move_to_layer": {"layer"},
    "set_bylayer": {"color", "true_color", "color_name", "lineweight"},
    "replace_text_style": {"style"},
    "replace_dim_style": {"dimstyle"} | _DIM_RENDER,
    "purge_unused": set(),
    "set_text_height": {"height", "char_height"},
    "clear_dim_text_override": {"text"} | _DIM_RENDER,
}

# Mô tả ngắn (tiếng Việt) cho tài liệu, CLI và MCP.
OP_HELP: dict[str, str] = {
    "rename_layer": "đổi tên layer {from, to} (to chưa tồn tại); VS-01",
    "merge_layers": "gộp layer {sources[], target} vào layer đích đã có, xoá định nghĩa layer nguồn; VS-01",
    "move_to_layer": "chuyển đối tượng theo bộ lọc {filter, target} sang layer đích đã có; VS-03",
    "set_bylayer": "đặt màu/độ dày nét về ByLayer {filter, color, lineweight}; VS-04",
    "replace_text_style": "đổi kiểu chữ của TEXT/MTEXT {filter, from[], to} sang kiểu đã có; VS-07, VS-02",
    "replace_dim_style": "đổi kiểu kích thước của DIMENSION {filter, from[], to, rerender}; VS-02",
    "purge_unused": "xoá ĐỊNH NGHĨA không dùng {kinds[], names[]}: layers/text_styles/dim_styles/blocks; VS-01, VS-02",
    "set_text_height": "đổi chiều cao chữ TEXT/MTEXT {filter, from_height, to}",
    "clear_dim_text_override": "trả chữ kích thước về số đo tự động '<>' {filter, rerender}; VS-06",
}


def _loc(loc: tuple) -> str:
    parts = []
    for x in loc:
        if isinstance(x, int):
            parts.append(f"[{x}]")
        elif x in OP_TYPES:  # nhánh của union phân biệt theo 'op': không phải tên trường
            continue
        else:
            parts.append(("." if parts else "") + ("from" if x == "from_" else str(x)))
    return "".join(parts) or "(gốc)"


def _vi_errors(exc: ValidationError) -> str:
    out = []
    for e in exc.errors():
        loc = "thao tác " + _loc(tuple(e.get("loc", ())))
        kind = e.get("type", "")
        if kind == "union_tag_invalid":
            tag = (e.get("ctx") or {}).get("tag", "?")
            out.append(f"{loc}: '{tag}' không có trong từ vựng thao tác (có: {', '.join(OP_TYPES)})")
        elif kind == "union_tag_not_found":
            out.append(f"{loc}: thiếu trường 'op'")
        elif kind == "extra_forbidden":
            out.append(f"{loc}: trường lạ")
        elif kind == "missing":
            out.append(f"{loc}: thiếu trường bắt buộc")
        elif kind in ("too_short", "too_long"):
            out.append(f"{loc}: độ dài không hợp lệ")
        elif kind in ("greater_than", "less_than_equal", "greater_than_equal", "less_than"):
            out.append(f"{loc}: giá trị ngoài khoảng cho phép")
        elif kind == "literal_error":
            out.append(f"{loc}: giá trị không thuộc danh sách cho phép")
        else:
            out.append(f"{loc}: sai kiểu")
        if len(out) >= 10:
            out.append("…")
            break
    return "; ".join(out)


def parse_ops(data: Any) -> list[Any]:
    """Kiểm schema danh sách thao tác. Sai -> OpError tiếng Việt."""
    if isinstance(data, dict) and "ops" in data and set(data) <= {"ops", "protected_layers", "standard"}:
        data = data["ops"]
    if not isinstance(data, list) or not data:
        raise OpError("Danh sách thao tác phải là mảng JSON không rỗng (hoặc {\"ops\": [...]}).")
    if len(data) > MAX_OPS:
        raise OpError(f"Tối đa {MAX_OPS} thao tác mỗi changeset (đang có {len(data)}).")
    try:
        return list(_ADAPTER.validate_python(data))
    except ValidationError as exc:
        raise OpError("Thao tác sai: " + _vi_errors(exc) + ".") from None


def dump_op(op: Any) -> dict:
    return op.model_dump(by_alias=True, exclude_none=True, mode="json")


def dump_ops(ops: list[Any]) -> list[dict]:
    return [dump_op(o) for o in ops]


# Trường chứa tên, theo loại tên: "layer", "style", "dimstyle", "layout", "any" (purge: mọi loại).
def map_names(op: Any, fn: Callable[[str, str], str]) -> Any:
    """Trả BẢN SAO thao tác với mọi tên đã qua `fn(kind, name)` (dùng cho ẩn danh: mã hoá/giải mã)."""
    data = dump_op(op)

    def lst(kind, values):
        return None if values is None else [fn(kind, v) for v in values]

    flt = data.get("filter")
    if isinstance(flt, dict):
        for key, kind in (("layers", "layer"), ("exclude_layers", "layer"), ("spaces", "layout")):
            if key in flt:
                flt[key] = lst(kind, flt[key])
    name = data["op"]
    if name == "rename_layer":
        data["from"], data["to"] = fn("layer", data["from"]), fn("layer", data["to"])
    elif name == "merge_layers":
        data["sources"], data["target"] = lst("layer", data["sources"]), fn("layer", data["target"])
    elif name == "move_to_layer":
        data["target"] = fn("layer", data["target"])
    elif name in ("replace_text_style", "replace_dim_style"):
        kind = "style" if name == "replace_text_style" else "dimstyle"
        if "from" in data:
            data["from"] = lst(kind, data["from"])
        data["to"] = fn(kind, data["to"])
    elif name == "purge_unused" and "names" in data:
        data["names"] = lst("any", data["names"])
    return OP_TYPES[name].model_validate(data)


def allowed_attrs(ops: list[Any]) -> set[str]:
    out: set[str] = set()
    for o in ops:
        out |= ALLOWED_ATTRS[o.op]
    return out
