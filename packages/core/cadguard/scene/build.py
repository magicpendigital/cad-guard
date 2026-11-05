"""DrawingModel -> Scene `cg.scene/1`.

Quy ước ĐỀ XUẤT (chưa vào chuẩn; đổi = tạo phiên bản chuẩn mới):
- Tường: LINE/LWPOLYLINE trên layer `FN-ROOM-WALL` là đường tim tường. Cao/dày mặc định bên dưới.
- Mô-đun (tủ/đồ rời): INSERT có tên khối bắt đầu bằng `FN_MOD`, thuộc tính `W`,`D`,`H` (mm),
  tuỳ chọn `MAT`, `KIND`. Điểm chèn là góc trái-dưới, xoay quanh điểm chèn.
- Tấm ván từ nhiều hình chiếu: xem `views.py`.
- Chiều cao mô-đun KHÔNG có mặc định: thiếu thì tạo mục `gaps[]` (kèm trường để nhập), không đoán.
- Chỉ dựng khi đơn vị bản vẽ là mm (INSUNITS = 4).
- Giá trị bổ sung (`supplement`) là dict {khoá: giá trị} từ tệp `.cgsup.json`; phần nào dùng nó được đánh dấu `source: user`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..model import DrawingModel

SCHEMA = "cg.scene/1"
SUPPLEMENT_SCHEMA = "cg.supplement/1"
WALL_LAYER = "FN-ROOM-WALL"
MODULE_PREFIX = "FN_MOD"
WALL_HEIGHT_MM = 2850.0
WALL_THICKNESS_MM = 120.0


class Wall(BaseModel):
    handle: str
    start: tuple[float, float]
    end: tuple[float, float]
    thickness: float = WALL_THICKNESS_MM
    height: float = WALL_HEIGHT_MM
    height_source: str = "default"


class Module(BaseModel):
    handle: str
    kind: str = "cabinet"
    x: float
    y: float
    rotation: float = 0.0
    w: float
    d: float
    h: float
    material: str = ""
    source: str = "drawing"  # drawing | user


class Panel(BaseModel):
    """Tấm ván dạng hộp song song trục, đơn vị mm (X ngang, Y sâu từ mặt trước, Z cao)."""

    id: str
    x0: float
    x1: float
    y0: float
    y1: float
    z0: float
    z1: float
    source: str = "views"  # views | user


class Skipped(BaseModel):
    handle: str
    reason: str


class Field_(BaseModel):
    key: str
    label: str
    unit: str = "mm"
    kind: str = "number"  # number | choice
    options: list[str] = Field(default_factory=list)


class Gap(BaseModel):
    id: str
    kind: str  # missing_value | ambiguous | missing_view | conflict
    target: str
    message: str
    fields: list[Field_] = Field(default_factory=list)  # rỗng = không nhập tay được (phải sửa/bổ sung bản vẽ)


class Scene(BaseModel):
    schema_id: str = Field(default=SCHEMA, alias="schema")
    source_hash: str = ""
    walls: list[Wall] = Field(default_factory=list)
    modules: list[Module] = Field(default_factory=list)
    panels: list[Panel] = Field(default_factory=list)
    skipped: list[Skipped] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


def _num(raw) -> float | None:
    if raw is None:
        return None
    try:
        v = float(str(raw).strip().replace(",", "."))
    except ValueError:
        return None
    return v if v > 0 else None


LABELS = {"w": "Chiều rộng W", "d": "Chiều sâu D", "h": "Chiều cao H"}


def _modules(model: DrawingModel, sc: Scene, supp: dict) -> None:
    for e in model.entities:
        if e.space != "Model" or e.type != "INSERT" or not (e.block and e.block.startswith(MODULE_PREFIX)):
            continue
        at = e.attribs or {}
        vals: dict[str, float | None] = {k: _num(at.get(k.upper())) for k in "wdh"}
        used_user = False
        missing: list[str] = []
        for k in "wdh":
            if vals[k] is None:
                u = _num(supp.get(f"module:{e.handle}:{k}"))
                if u is None:
                    missing.append(k)
                else:
                    vals[k], used_user = u, True
        if e.insert is None:
            sc.skipped.append(Skipped(handle=e.handle, reason="thiếu điểm chèn"))
        elif (e.xscale not in (None, 1.0)) or (e.yscale not in (None, 1.0)):
            sc.skipped.append(Skipped(handle=e.handle, reason="khối có tỉ lệ khác 1"))
        elif missing:
            names = ", ".join(k.upper() for k in missing)
            sc.gaps.append(
                Gap(
                    id=f"module:{e.handle}",
                    kind="missing_value",
                    target=e.handle,
                    message=f"Mô-đun {e.handle}: thiếu hoặc sai {names}.",
                    fields=[Field_(key=f"module:{e.handle}:{k}", label=LABELS[k]) for k in missing],
                )
            )
        else:
            sc.modules.append(
                Module(
                    handle=e.handle,
                    kind=at.get("KIND", "cabinet") or "cabinet",
                    x=e.insert[0],
                    y=e.insert[1],
                    rotation=e.rotation or 0.0,
                    w=vals["w"],
                    d=vals["d"],
                    h=vals["h"],
                    material=at.get("MAT", ""),
                    source="user" if used_user else "drawing",
                )
            )


def _walls(model: DrawingModel, sc: Scene) -> None:
    for e in model.entities:
        if e.space == "Model" and e.layer == WALL_LAYER and e.type in ("LINE", "LWPOLYLINE"):
            if not e.pts or len(e.pts) < 2:
                sc.skipped.append(Skipped(handle=e.handle, reason="tường thiếu toạ độ"))
                continue
            pts = list(e.pts)
            if e.type == "LWPOLYLINE" and e.closed:
                pts.append(pts[0])
            for a, b in zip(pts, pts[1:]):
                if a != b:
                    sc.walls.append(Wall(handle=e.handle, start=a, end=b))


def build_scene(model: DrawingModel, supplement: dict | None = None, views: dict | None = None) -> Scene:
    """`views`: {"front"|"top"|"side": [EntityRec]} để ghi đè cách chọn hình chiếu theo layer."""
    from .views import build_panels

    sc = Scene(source_hash=model.file_hash)
    if model.insunits != 4:
        sc.notes.append("Đơn vị bản vẽ không phải mm (INSUNITS != 4): không dựng 3D.")
        return sc
    supp = supplement or {}
    _walls(model, sc)
    _modules(model, sc, supp)
    build_panels(model, sc, supp, views)
    if not (sc.walls or sc.modules or sc.panels) and not sc.gaps:
        sc.notes.append("Không có tường, mô-đun hoặc hình chiếu nào dựng được.")
    return sc


def load_supplement(data: dict, source_hash: str) -> tuple[dict, str | None]:
    """Trả về (giá trị, ghi chú). Tệp không khớp mã băm bản vẽ hoặc sai lược đồ thì bỏ qua toàn bộ."""
    if data.get("schema") != SUPPLEMENT_SCHEMA:
        return {}, "Tệp bổ sung sai lược đồ: bỏ qua."
    if data.get("source_hash") != source_hash:
        return {}, "Tệp bổ sung ứng với bản vẽ khác (mã băm không khớp): bỏ qua."
    vals = data.get("values")
    return (dict(vals) if isinstance(vals, dict) else {}), None
