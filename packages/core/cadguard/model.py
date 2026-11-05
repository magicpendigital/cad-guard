"""Drawing Model `cg.drawing/1`: ảnh chụp phẳng của một bản vẽ, đủ để chạy luật.

Mọi luật chỉ đọc mô hình này (không đọc ezdxf trực tiếp), nên cùng một bộ luật chạy được với
mô hình sinh từ DXF hôm nay hoặc từ JSON do một adapter/plugin CAD xuất sau này.
Không chứa đường dẫn tệp hay tên người dùng; `file_hash` chỉ là băm nội dung.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SCHEMA = "cg.drawing/1"


class LayerRec(BaseModel):
    name: str
    color: int | None = None
    linetype: str | None = None
    lineweight: int | None = None
    frozen: bool = False
    off: bool = False
    plot: bool = True
    xref_dependent: bool = False
    xref_name: str | None = None


class EntityRec(BaseModel):
    handle: str
    type: str
    layer: str
    space: str = "Model"  # "Model" hoặc tên layout
    length: float | None = None  # LINE, hoặc tổng chiều dài LWPOLYLINE
    area: float | None = None  # chỉ LWPOLYLINE khép kín
    closed: bool | None = None
    has_nonzero_z: bool = False
    dup_key: str | None = None  # khoá trùng lặp cho LINE/CIRCLE/ARC
    text_style: str | None = None  # TEXT/MTEXT
    dim_text: str | None = None  # DIMENSION: chữ ghi đè ("" hoặc "<>" = tự động)
    block: str | None = None  # INSERT
    attribs: dict[str, str] | None = None  # INSERT: {tag: giá trị}
    is_proxy: bool = False
    color: int | None = None
    lineweight: int | None = None
    true_color: int | None = None
    # Hình học (tuỳ chọn, thêm ở 3D tầng A; mô hình cũ không có các trường này vẫn hợp lệ)
    pts: list[tuple[float, float]] | None = None  # LINE: 2 điểm; LWPOLYLINE: các đỉnh (xy)
    insert: tuple[float, float] | None = None  # INSERT: điểm chèn (xy)
    rotation: float | None = None  # INSERT: độ
    xscale: float | None = None  # INSERT
    yscale: float | None = None  # INSERT
    # Nội dung để LLM đọc (thêm cho studio): chữ, số đo, đường tròn
    text: str | None = None  # TEXT/MTEXT (cắt tối đa 300 ký tự)
    pos: tuple[float, float] | None = None  # TEXT/MTEXT: điểm chèn
    dim_value: float | None = None  # DIMENSION: số đo thật
    radius: float | None = None  # CIRCLE/ARC (tâm ở `pts[0]`)
    # Cho hình xem trước đơn giản hoá của `cadguard app` (thêm sau; mô hình cũ không có vẫn hợp lệ)
    text_height: float | None = None  # TEXT/MTEXT: chiều cao chữ (đơn vị bản vẽ)
    text_rotation: float | None = None  # TEXT/MTEXT: góc xoay (độ)
    arc: tuple[float, float, float, float, float] | None = None  # ARC: (tâm x, tâm y, bán kính, góc đầu, góc cuối) độ


class StyleRec(BaseModel):
    """Kiểu chữ và phân loại phông theo phần mở rộng."""
    name: str
    font: str = ""
    bigfont: str = ""
    font_kind: Literal["shx", "ttf", "other", "none"] = "none"


class BlockRec(BaseModel):
    """Định nghĩa khối và số đối tượng trực tiếp trong khối."""
    name: str
    kind: Literal["named", "anon_U", "anon_D", "anon_X", "anon_A", "anon_other"]
    is_xref: bool = False
    is_layout: bool = False
    entity_count: int = 0
    types: dict[str, int] = Field(default_factory=dict)
    layers: dict[str, int] = Field(default_factory=dict)
    child_blocks: dict[str, int] = Field(default_factory=dict)
    depth: int = 0


class SpaceStats(BaseModel):
    """Số liệu đối tượng trực tiếp trong một phạm vi."""
    entities: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_layer: dict[str, int] = Field(default_factory=dict)
    color_override: int = 0
    lineweight_override: int = 0
    true_color: int = 0
    dim_total: int = 0
    dim_text_override: int = 0
    wipeout: int = 0
    image: int = 0
    ole: int = 0
    proxy: int = 0


class ModelStats(BaseModel):
    """Số liệu tổng hợp và nguồn của bộ đọc."""
    source: Literal["ezdxf", "stream"]
    modelspace: SpaceStats
    paperspace: SpaceStats
    blocks: SpaceStats
    blocks_named: int = 0
    blocks_anonymous: int = 0
    blocks_xref: int = 0
    max_block_depth: int = 0
    layers_xref_dependent: int = 0
    shape_styles: int = 0
    entity_records_truncated: bool = False
    # TEXT/MTEXT có ký tự ngoài ASCII (thường là tiếng Việt có dấu, hoặc mã \U+/\M+), đếm theo tên kiểu chữ
    # của đối tượng, gồm cả không gian mô hình, giấy và định nghĩa khối. Mới thêm, mặc định rỗng (tương thích ngược).
    text_non_ascii_by_style: dict[str, int] = Field(default_factory=dict)


class ViewportRec(BaseModel):
    layout: str
    id: int
    scale: float | None = None  # tờ giấy / mô hình (1:20 -> 0.05)


class LayoutRec(BaseModel):
    name: str
    paper_w_mm: float | None = None
    paper_h_mm: float | None = None
    viewports: list[ViewportRec] = Field(default_factory=list)


class DrawingModel(BaseModel):
    schema_id: str = Field(default=SCHEMA, alias="schema")
    file_hash: str = ""  # sha256 rút gọn của nội dung tệp
    dxf_version: str | None = None
    insunits: int | None = None  # 0 = không đơn vị, 4 = mm
    layers: list[LayerRec] = Field(default_factory=list)
    block_layers: list[str] = Field(default_factory=list)  # layer được dùng trong định nghĩa khối
    entities: list[EntityRec] = Field(default_factory=list)
    layouts: list[LayoutRec] = Field(default_factory=list)
    styles: list[StyleRec] = Field(default_factory=list)
    dim_styles: list[str] = Field(default_factory=list)
    blocks: list[BlockRec] = Field(default_factory=list)
    stats: ModelStats | None = None

    model_config = {"populate_by_name": True}
