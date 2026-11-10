"""Hợp đồng dữ liệu giữa các tầng của cad-guard. Phụ thuộc MỘT CHIỀU: module này dùng `model`/`runner`/`standard`,
không module lõi nào import ngược lại nó (tránh vòng import như bản thử trước).

Đã có sẵn và có phiên bản — chỉ dẫn lại ở đây, KHÔNG định nghĩa lại (nạp lười để import `contracts` vẫn nhẹ):
- `DrawingModel` `cg.drawing/1` (`model.py`): ảnh chụp bản vẽ do `dxf_reader`/`dxf_stream` tạo.
- `Changeset` `cg.changeset/1` (`changeset/apply.py`): thao tác sửa + xem trước + nhật ký áp dụng.
- `Scene` `cg.scene/1` (`scene/build.py`): cảnh 3D tất định, phần thiếu, phần bỏ qua.

Mới ở đây: `AuditReport` `cg.audit/1` — kết quả kiểm MỘT bản vẽ, nguồn duy nhất cho CLI/báo cáo, App và trợ lý (MCP,
engine API). Mỗi nơi chỉ được ẩn danh/cắt bớt/nhóm lại từ đối tượng này, không tự đếm lại.

- `bbox` (khung bao 2D của các handle mẫu) là TUỲ CHỌN: chỉ có khi mô hình có toạ độ cho các đối tượng đó; luật đếm hoặc
  bộ đọc theo dòng không có toạ độ thì để null, không suy đoán. Trợ lý ẩn danh Bậc 1 không bao giờ nhận `bbox`.
- `fix_ops` chỉ có cho luật có thao tác sửa trong từ vựng cố định (`FIXABLE_RULES`); luật khác để danh sách rỗng.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # chỉ cho kiểu; không import lúc chạy
    from .model import DrawingModel
    from .runner import AuditResult
    from .standard import Standard

AUDIT_SCHEMA = "cg.audit/1"
SEVERITIES = ("E", "W", "I")

# Luật có thao tác sửa trong từ vựng cố định (docs/changeset.md mục 3). VS-05 không có (bớt IMAGE/WIPEOUT là xoá đối tượng).
FIXABLE_RULES: dict[str, list[str]] = {
    "VS-01": ["merge_layers", "purge_unused"],
    "VS-02": ["purge_unused", "replace_text_style", "replace_dim_style"],
    "VS-03": ["move_to_layer"],
    "VS-04": ["set_bylayer"],
    "VS-06": ["clear_dim_text_override"],
    "VS-07": ["replace_text_style"],
    # trình bày tờ theo template (sheet-layout-v0, kế hoạch sheets-presentation mục 4.4)
    "TP-01": ["replace_title_block"],
    "TP-03": ["set_attribs"],
    "TP-04": ["set_attribs"],
    "TP-05": ["set_sheet_scale"],
    "TP-06": ["set_attribs", "set_sheet_scale"],
    "TP-07": ["fit_sheet"],
    "TP-10": ["set_attribs"],
    "TP-12": ["convert_unicode"],
}
NO_FIX_NOTE: dict[str, str] = {
    "VS-05": "Bớt WIPEOUT/IMAGE/OLE là xoá đối tượng, ngoài từ vựng thao tác: hãy xử lý trong phần mềm CAD.",
}
INTERNAL_ERROR_REASON = "Lỗi nội bộ của luật."


class AuditFinding(BaseModel):
    rule_id: str
    severity: Literal["E", "W", "I"]
    message: str
    layer: str | None = None
    layout: str | None = None
    count: int = 1
    handles: list[str] = Field(default_factory=list)
    bbox: tuple[float, float, float, float] | None = None  # (xmin, ymin, xmax, ymax) đơn vị bản vẽ; có thể null
    fix_ops: list[str] = Field(default_factory=list)


class AuditSkip(BaseModel):
    rule_id: str
    reason: str
    internal_error: bool = False


class AuditReport(BaseModel):
    schema_id: str = Field(default=AUDIT_SCHEMA, alias="schema")
    file_hash: str = ""
    standard: str
    version: str
    profile: dict | None = None
    counts: dict[str, int]
    rules_run: int
    skipped: list[AuditSkip] = Field(default_factory=list)
    findings: list[AuditFinding] = Field(default_factory=list)
    fixable_rules: list[str] = Field(default_factory=list)
    records_capped: bool = False

    model_config = {"populate_by_name": True}

    def dump(self) -> dict:
        return self.model_dump(by_alias=True)


def _bbox(model: "DrawingModel | None", handles: list[str]) -> tuple[float, float, float, float] | None:
    """Khung bao từ toạ độ CÓ trong mô hình (pts/insert/pos/arc); thiếu toạ độ thì None, không đoán."""
    if model is None or not handles:
        return None
    want = set(handles)
    xs: list[float] = []
    ys: list[float] = []
    for e in model.entities:
        if e.handle not in want:
            continue
        pts = list(e.pts or [])
        for p in (e.insert, e.pos):
            if p is not None:
                pts.append(p)
        if e.arc is not None:
            cx, cy, r = e.arc[0], e.arc[1], e.arc[2]
            pts += [(cx - r, cy - r), (cx + r, cy + r)]
        elif e.radius is not None and e.pts:
            cx, cy = e.pts[0]
            pts += [(cx - e.radius, cy - e.radius), (cx + e.radius, cy + e.radius)]
        for x, y in pts:
            xs.append(float(x))
            ys.append(float(y))
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def from_result(res: "AuditResult", std: "Standard", model: "DrawingModel | None" = None) -> AuditReport:
    """Đổi `AuditResult` của runner thành `AuditReport`. Truyền `model` để có `file_hash`, `records_capped`, `bbox`."""
    counts = {s: 0 for s in SEVERITIES}
    findings = []
    for f in res.findings:
        sev = f.severity if f.severity in SEVERITIES else "W"
        counts[sev] += 1
        findings.append(AuditFinding(rule_id=f.rule_id, severity=sev, message=f.message, layer=f.layer, layout=f.layout,
                                     count=int(f.count or 1), handles=list(f.handles), bbox=_bbox(model, list(f.handles)),
                                     fix_ops=list(FIXABLE_RULES.get(f.rule_id, []))))
    skipped = [AuditSkip(rule_id=r, reason=INTERNAL_ERROR_REASON if r in res.internal_errors else why,
                         internal_error=r in res.internal_errors) for r, why in res.skipped]
    capped = bool(model is not None and model.stats is not None and model.stats.entity_records_truncated)
    return AuditReport(
        file_hash=model.file_hash if model is not None else "", standard=std.name, version=std.version,
        profile=dict(std.profile) if std.profile else None, counts=counts, rules_run=res.rules_run, skipped=skipped,
        findings=findings, fixable_rules=sorted({f.rule_id for f in findings} & set(FIXABLE_RULES)), records_capped=capped,
    )


def audit_report(model: "DrawingModel", std: "Standard") -> AuditReport:
    """Chạy bộ luật và trả hợp đồng `cg.audit/1` — điểm vào duy nhất cho mọi nơi hiển thị kết quả kiểm."""
    from .runner import audit_model

    return from_result(audit_model(model, std), std, model)


def json_schemas() -> dict[str, dict]:
    """JSON Schema của các hợp đồng (để đối tác/kiểm thử ngoài Python dùng)."""
    from .model import DrawingModel

    return {"cg.audit/1": AuditReport.model_json_schema(by_alias=True),
            "cg.drawing/1": DrawingModel.model_json_schema(by_alias=True)}


_REEXPORT = {"DrawingModel": ("model", "DrawingModel"), "Changeset": ("changeset.apply", "Changeset"),
             "Scene": ("scene.build", "Scene")}


def __getattr__(name: str) -> Any:  # dẫn lại lười: import contracts không kéo ezdxf/changeset/scene
    if name in _REEXPORT:
        import importlib

        mod, attr = _REEXPORT[name]
        return getattr(importlib.import_module(f".{mod}", __name__.rsplit(".", 1)[0]), attr)
    raise AttributeError(name)


__all__ = ["AUDIT_SCHEMA", "FIXABLE_RULES", "INTERNAL_ERROR_REASON", "NO_FIX_NOTE", "SEVERITIES", "AuditFinding",
           "AuditReport", "AuditSkip", "Changeset", "DrawingModel", "Scene", "audit_report", "from_result", "json_schemas"]
