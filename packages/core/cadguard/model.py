"""Drawing Model `cg.drawing/1`: ảnh chụp phẳng của một bản vẽ, đủ để chạy luật.

Mọi luật chỉ đọc mô hình này (không đọc ezdxf trực tiếp), nên cùng một bộ luật chạy được với
mô hình sinh từ DXF hôm nay hoặc từ JSON do một adapter/plugin CAD xuất sau này.
Không chứa đường dẫn tệp hay tên người dùng; `file_hash` chỉ là băm nội dung.
"""

from __future__ import annotations

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

    model_config = {"populate_by_name": True}
