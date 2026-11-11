"""Phần dữ liệu của ứng dụng cục bộ `cadguard app` (không phụ thuộc HTTP, test được trực tiếp).

Người dùng của ứng dụng là NGƯỜI trên máy của họ, nên kết quả ở đây dùng tên thật (layer, tệp tương đối).
Ẩn danh Bậc 1 chỉ áp cho TRỢ LÝ (engine nhận `server_options={"anonymize": ...}`), xem `chat.py`.
Mọi đường dẫn từ trình duyệt đi qua `agent.workspace.Workspace` (chỉ nhận đường dẫn tương đối, không `..`).
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..agent import tools
from .. import privacy, rule_config
from ..rule_config import effective_standard
from ..agent.anonymize import Anonymizer
from ..agent.workspace import PathDenied, Workspace
from ..changeset.apply import ID_RE, STORE_DIR, ChangesetError, apply, load_changeset, propose, undo
from ..changeset.ops import OP_HELP, OpError, parse_ops
from ..reader_select import DEFAULT_STREAM_THRESHOLD_MB
from ..contracts import FIXABLE_RULES, NO_FIX_NOTE, audit_report
from .. import gate as gatemod
from ..sheet_state import SheetState
from ..sheets import Structure, build_structure
from ..runner import audit_model
from ..standard import CompanyProfile, ProfileError, Standard, find_standards_dir, load_profile, load_standard
from .geometry import drawing_geometry
from .preview import PreviewManager
from .history import History, audit_entry

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]*$")
SEVERITIES = ("E", "W", "I")
SEVERITY_VI = {"E": "Lỗi", "W": "Cảnh báo", "I": "Thông tin"}
OUTPUT_RE = re.compile(r"\.cg-[0-9a-f]{8}\.dxf$", re.IGNORECASE)
MAX_FINDINGS = 500
MAX_DRAWINGS = 2000  # trần số tệp DXF liệt kê (thư mục quá rộng như gốc ổ đĩa)
MAX_SCAN_DIRS = 20000  # trần số thư mục duyệt khi tìm DXF
DEPARTMENTS_FILE = Path(__file__).with_name("departments.json")


class ApiError(ValueError):
    """Lỗi trả cho trình duyệt: thông điệp tiếng Việt, không đường dẫn tuyệt đối; `status` là mã HTTP."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass
class AppConfig:
    workspace: Path | None = None  # None = mở ứng dụng chưa chọn dự án (màn chọn dự án)
    profile_path: Path | None = None
    anonymize: bool | None = None  # None = theo công tắc của dự án (.cadguard/project.yaml), mặc định nội bộ
    experimental: bool = False
    allow_openrouter: bool = False
    account: str | None = None
    stream_threshold_mb: float | None = DEFAULT_STREAM_THRESHOLD_MB
    standards_dir: Path | None = None
    departments_path: Path | None = None
    autocad_com: bool = True  # M3: nút "Tới trong AutoCAD" đưa thẳng AutoCAD tới đối tượng (tắt: --no-autocad-com)


@dataclass
class AppData:
    """Trạng thái dữ liệu của một phiên ứng dụng (một thư mục làm việc, một hồ sơ công ty)."""

    config: AppConfig
    ws: Workspace = field(init=False)
    profile: CompanyProfile | None = field(init=False, default=None)
    standards_dir: Path = field(init=False)
    departments: dict = field(init=False)
    history: History = field(init=False)
    anonymize: bool = field(init=False, default=False)
    previews: PreviewManager = field(init=False)
    _reviews: Any = field(init=False, default=None)
    _structs: dict = field(init=False, default_factory=dict)

    def structure(self, model) -> Structure:
        """Chỉ mục tờ (sheets.py) theo băm nội dung tệp; giữ tối đa 8 bản vẽ gần nhất."""
        st = self._structs.get(model.file_hash)
        if st is None:
            st = build_structure(model)
            if len(self._structs) >= 8:
                self._structs.pop(next(iter(self._structs)))
            self._structs[model.file_hash] = st
        return st

    def reviews(self):
        if self._reviews is None:
            from ..review.service import ReviewService
            self._reviews = ReviewService(self.ws.root, self.standards_dir, self.config.profile_path)
        return self._reviews

    def __post_init__(self) -> None:
        try:
            self.ws = Workspace(Path(self.config.workspace))
        except PathDenied:
            raise ApiError("Thư mục dự án không tồn tại hoặc không đọc được.") from None
        self.history = History(self.ws.root)
        self.anonymize = privacy.effective(self.ws.root, self.config.anonymize)
        self.previews = PreviewManager(self.ws.root)
        self.standards_dir = Path(self.config.standards_dir or find_standards_dir(Path(__file__).resolve())).resolve()
        if self.config.profile_path:
            self.profile = load_profile(self.config.profile_path)  # ProfileError -> lệnh dừng với thông điệp tiếng Việt
        self.departments = load_departments(self.config.departments_path or DEPARTMENTS_FILE, self.standard_names())

    # ---------- chuẩn ----------

    def standard_names(self) -> list[str]:
        return sorted(p.stem for p in self.standards_dir.glob("*.yaml")
                      if NAME_RE.fullmatch(p.stem) and not p.stem.startswith("company-profile"))

    def check_standard(self, name: Any) -> str:
        if not isinstance(name, str) or not NAME_RE.fullmatch(name) or name not in self.standard_names():
            raise ApiError("Không có chuẩn này trong thư mục standards/.")
        return name

    def profile_for(self, standard: str) -> CompanyProfile | None:
        return self.profile if self.profile is not None and self.profile.standard == standard else None

    def load_std(self, standard: str, with_profile: bool = True) -> Standard:
        standard = self.check_standard(standard)
        try:
            return effective_standard(standard, self.standards_dir,
                                      profile=self.profile_for(standard) if with_profile else None,
                                      workspace=self.ws.root, use_settings=with_profile)
        except ProfileError as exc:
            raise ApiError(str(exc)) from None

    # ---------- đường dẫn ----------

    def resolve(self, rel: Any) -> Path:
        if not isinstance(rel, str) or len(rel) > 1024:
            raise ApiError("Thiếu tệp bản vẽ (đường dẫn tương đối trong thư mục làm việc).")
        try:
            return self.ws.resolve(rel)
        except PathDenied:
            raise ApiError("Đường dẫn không được phép: chỉ nhận tệp .dxf nằm trong thư mục làm việc, viết dạng tương đối.",
                           403) from None

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.ws.root).as_posix()

    def model(self, path: Path):
        try:
            return tools.load_model(path, self.config.stream_threshold_mb)
        except tools.ToolError as exc:
            raise ApiError(str(exc), 422) from None


def load_departments(path: Path, standards: list[str]) -> dict:
    """Đọc `departments.json`. Mỗi phòng có thể có nhiều chuẩn (`standards`) và nhiều phòng nhận (`next`).

    Dạng cũ (`standard`: một tên, `next`: một id hoặc null) vẫn đọc được. Chuẩn không có trong standards/ vẫn hiện
    nhưng bị bỏ khỏi danh sách chạy (`standards_missing`).
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        items = data["departments"]
        if not isinstance(items, list) or not items:
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise ApiError("Tệp cấu hình phòng (departments.json) hỏng hoặc sai dạng.", 500) from None
    out = []
    for d in items:
        if not isinstance(d, dict) or not isinstance(d.get("id"), str) or not isinstance(d.get("name"), str):
            raise ApiError("departments.json: mỗi phòng cần 'id' và 'name'.", 500)
        stds = d.get("standards")
        if stds is None:
            stds = [d["standard"]] if isinstance(d.get("standard"), str) else []
        if not isinstance(stds, list) or not all(isinstance(x, str) for x in stds):
            raise ApiError("departments.json: 'standards' phải là danh sách tên chuẩn.", 500)
        nxt = d.get("next")
        nxt = [nxt] if isinstance(nxt, str) else (nxt if isinstance(nxt, list) else [])
        ok = [x for x in stds if x in standards]
        out.append({"id": d["id"], "name": d["name"], "standards": ok,
                    "standards_missing": [x for x in stds if x not in standards],
                    "standard": ok[0] if ok else None, "standard_ok": bool(ok),
                    "description": str(d.get("description") or ""), "role": str(d.get("role") or ""),
                    "next": [x for x in nxt if isinstance(x, str)],
                    "view": d.get("view") if d.get("view") in ("scene",) else None,
                    "priority": bool(d.get("priority"))})
    default = data.get("default") if any(x["id"] == data.get("default") for x in out) else out[0]["id"]
    return {"default": default, "departments": out}


def check_dept(app: "AppData", dept: Any) -> dict | None:
    if dept is None:
        return None
    for d in app.departments["departments"]:
        if d["id"] == dept:
            return d
    raise ApiError("Không có phòng này.")


# ---------- bản vẽ, kiểm, giải thích ----------

def list_drawings(app: AppData) -> dict:
    from .versions import overview

    paths = app.ws.list_dxf(".", limit=MAX_DRAWINGS + 1, max_dirs=MAX_SCAN_DIRS)
    vers = overview(app.ws.root)
    items = []
    for p in paths[:MAX_DRAWINGS]:
        rel = app.rel(p)
        st = p.stat()
        items.append({"path": rel, "name": p.name, "dir": rel.rsplit("/", 1)[0] if "/" in rel else "",
                      "size_bytes": st.st_size, "is_output": bool(OUTPUT_RE.search(p.name)),
                      **({"version": vers[rel]} if rel in vers else {})})
    return {"drawings": items, "total": min(len(paths), MAX_DRAWINGS), "truncated": len(paths) > MAX_DRAWINGS,
            "limit": MAX_DRAWINGS}


def _item_sheets(struct: Structure, f) -> list[str]:
    """Tờ của một phát hiện: theo handle; không có handle mà gắn một layout có tờ thì là tờ layout đó."""
    out = struct.sheets_for(f.handles)
    if not out and f.layout and f.layout != "Model" and any(s.id == "L:" + f.layout for s in struct.sheets):
        out = ["L:" + f.layout]
    return out


def audit_file(app: AppData, rel: Any, standard: Any, dept: Any = None, record: bool = True) -> dict:
    path = app.resolve(rel)
    std = app.load_std(standard)
    dep = check_dept(app, dept)
    model = app.model(path)
    rep = audit_report(model, std)  # hợp đồng cg.audit/1 dùng chung với CLI/trợ lý; ở đây chỉ nhóm để hiển thị
    struct = app.structure(model)
    per_rule: Counter = Counter()
    for f in rep.findings:
        per_rule[f.rule_id] += max(1, int(f.count or 1))
    if record:
        app.history.record("audit", **audit_entry(app.history.file_id(app.rel(path)), model.file_hash,
                                                   dep["id"] if dep else None, std.name, std.version, rep.counts, per_rule))
    groups: dict[str, list[dict]] = {s: [] for s in SEVERITIES}
    by_rule: dict[tuple[str, str], dict] = {}
    for f in rep.findings[:MAX_FINDINGS]:
        spec = std.rule(f.rule_id)
        key = (f.severity, f.rule_id)
        g = by_rule.get(key)
        if g is None:
            tier = gatemod.tier_of(std, f.rule_id, f.severity)
            g = {"rule_id": f.rule_id, "severity": f.severity, "title": spec.title if spec else f.rule_id,
                 "items": [], "count": 0, "tier": tier, "tier_label": gatemod.TIER_VI[tier]}
            by_rule[key] = g
            groups.setdefault(f.severity, []).append(g)
        g["items"].append({"message": f.message, "layer": f.layer, "layout": f.layout, "count": f.count,
                           "handles": list(f.handles)[:20], "bbox": f.bbox, "sheets": _item_sheets(struct, f)})
        g["count"] += max(1, int(f.count or 1))
    fixable = sorted({g["rule_id"] for gs in groups.values() for g in gs} & set(FIXABLE_RULES))
    state = SheetState(app.ws.root, app.rel(path))
    all_groups = [g for gs in groups.values() for g in gs]
    acks = {k: v for k, v in state.acks.items() if k.startswith(std.name + "|")}
    skipped = [{"rule_id": s.rule_id, "reason": s.reason} for s in rep.skipped]
    counts = rep.counts
    return {
        "file": app.rel(path), "standard": std.name, "version": std.version, "profile": std.profile,
        "schema": rep.schema_id, "counts": {s: counts.get(s, 0) for s in SEVERITIES}, "rules_run": rep.rules_run,
        "groups": [{"severity": s, "label": SEVERITY_VI[s], "rules": groups.get(s, [])} for s in SEVERITIES],
        "skipped": skipped, "truncated": len(rep.findings) > MAX_FINDINGS, "fixable_rules": fixable,
        "records_capped": rep.records_capped,
        "rules_total": len(std.rules), "rules_enabled": sum(1 for r in std.rules if r.enabled and r.implemented),
        "entity_count": len(model.entities), "dxf_version": model.dxf_version, "insunits": model.insunits,
        "gate": gatemod.evaluate(all_groups, None, acks, std), "acks": acks, "gate_require_ack": std.gate_require_ack,
    }


def show_in_autocad(app: AppData, rel: Any, handles: Any = None, layers: Any = None) -> dict:
    """Nút "Tới trong AutoCAD": ghi `.cadguard/goto.txt` (người dùng gõ CGDEN) và, nếu bật, đưa thẳng AutoCAD tới
    đối tượng qua COM (M3, chỉ điều hướng). Xem `cadguard.autocad.bridge`."""
    from ..autocad.bridge import BridgeError, show

    path = app.resolve(rel)
    try:
        return show(app.ws.root, app.rel(path), handles, layers, com=app.config.autocad_com)
    except BridgeError as exc:
        raise ApiError(str(exc)) from None


# ---------- tờ (trang in): chỉ mục, chốt, xác nhận cảnh báo ----------

def sheets_info(app: AppData, rel: Any) -> dict:
    """Chỉ mục tờ của bản vẽ + trạng thái chốt từng tờ (dữ liệu cục bộ của người dùng, có tên thật)."""
    path = app.resolve(rel)
    model = app.model(path)
    st = app.structure(model)
    state = SheetState(app.ws.root, app.rel(path))
    out = st.to_dict()
    for s, d in zip(st.sheets, out["sheets"]):
        d.update(state.status(s.id, s.content_hash))
    out["file"] = app.rel(path)
    out["locked"] = sum(1 for d in out["sheets"] if d["status"] == "locked")
    return out


def _sheet(app: AppData, path: Path, sheet: Any):
    st = app.structure(app.model(path))
    for s in st.sheets:
        if s.id == sheet:
            return s
    raise ApiError("Không có tờ này trong bản vẽ (bản vẽ đã đổi? mở lại danh sách tờ).", 404)


def lock_sheet(app: AppData, rel: Any, sheet: Any, standards: Any, confirm: Any = False) -> dict:
    """Chốt tờ: chỉ khi không còn lỗi bậc Chặn và (nếu hồ sơ yêu cầu) mọi cảnh báo đã được xác nhận."""
    path = app.resolve(rel)
    s = _sheet(app, path, sheet)
    if not isinstance(standards, list) or not standards or len(standards) > 10:
        raise ApiError("Thiếu danh sách chuẩn dùng để chốt tờ.")
    if confirm is not True:
        raise ApiError("Cần xác nhận chốt tờ (confirm = true).")
    state = SheetState(app.ws.root, app.rel(path))
    per_std = []
    for name in standards:
        r = audit_file(app, rel, name, record=False)
        std = app.load_std(name)
        all_groups = [g for grp in r["groups"] for g in grp["rules"]]
        ev = gatemod.evaluate(all_groups, s.id, state.acks, std)
        per_std.append({"standard": name, **ev})
    blocked = [x for x in per_std if not x["can_lock"]]
    if blocked:
        b = sum(x["block"] for x in blocked)
        w = sum(x["warn_open"] for x in blocked)
        parts = []
        if b:
            parts.append(f"{b} lỗi bậc Chặn")
        if w:
            parts.append(f"{w} cảnh báo chưa xác nhận")
        raise ApiError("Chưa chốt được tờ: còn " + " và ".join(parts) + ".", 409)
    state.lock(s.id, s.content_hash, list(standards))
    return {"sheet": s.id, **state.status(s.id, s.content_hash), "checks": per_std}


def unlock_sheet(app: AppData, rel: Any, sheet: Any) -> dict:
    path = app.resolve(rel)
    s = _sheet(app, path, sheet)
    state = SheetState(app.ws.root, app.rel(path))
    state.unlock(s.id)
    return {"sheet": s.id, **state.status(s.id, s.content_hash)}


def ack_finding(app: AppData, rel: Any, standard: Any, rule_id: Any, sheet: Any, kind: Any, reason: Any = "",
                undo: bool = False) -> dict:
    """Xác nhận một cảnh báo cho một tờ ("*" = cả bản vẽ): "seen" (Đã xem) hoặc "skip" (Bỏ qua, cần lý do)."""
    path = app.resolve(rel)
    std = app.load_std(standard)
    if not isinstance(rule_id, str) or std.rule(rule_id) is None:
        raise ApiError("Không có luật này trong chuẩn.")
    if sheet != "*":
        sheet = _sheet(app, path, sheet).id
    state = SheetState(app.ws.root, app.rel(path))
    key = gatemod.ack_key(std.name, rule_id, sheet)
    if undo:
        state.unack(key)
        return {"key": key, "acked": False}
    if kind not in ("seen", "skip"):
        raise ApiError("Kiểu xác nhận phải là 'seen' (Đã xem) hoặc 'skip' (Bỏ qua).")
    reason = reason.strip() if isinstance(reason, str) else ""
    if kind == "skip" and len(reason) < 3:
        raise ApiError("Bỏ qua cảnh báo cần ghi lý do (ít nhất 3 ký tự).")
    if gatemod.tier_of(std, rule_id, std.rule(rule_id).severity) == "block":
        raise ApiError("Lỗi bậc Chặn không bỏ qua được: phải sửa bản vẽ (hoặc trưởng phòng đổi bậc trong hồ sơ công ty).",
                       409)
    state.ack(key, kind, reason)
    return {"key": key, "acked": True, "kind": kind}


def audit_all(app: AppData, standard: Any, dept: Any = None) -> dict:
    std = app.check_standard(standard)
    out = []
    for item in list_drawings(app)["drawings"][:200]:
        if item["is_output"]:
            continue
        try:
            r = audit_file(app, item["path"], std, dept)
            out.append({"path": item["path"], "counts": r["counts"], "ok": r["counts"]["E"] == 0})
        except ApiError as exc:
            out.append({"path": item["path"], "error": str(exc)})
    ready = sum(1 for x in out if x.get("ok"))
    return {"standard": std, "results": out, "ready": ready, "total": len(out)}


def _ctx(app: AppData) -> tools.ToolContext:
    # Ngữ cảnh công cụ cho NGƯỜI dùng: không ẩn danh (dữ liệu không rời máy, không qua mô hình).
    return tools.ToolContext(app.ws, Anonymizer(enabled=False), app.standards_dir,
                             stream_threshold_mb=app.config.stream_threshold_mb, profile=app.profile)


def explain(app: AppData, rule_id: Any, standard: Any) -> dict:
    std = app.check_standard(standard)
    if not isinstance(rule_id, str) or not re.fullmatch(r"[A-Za-z0-9.\-]{1,32}", rule_id):
        raise ApiError("Mã luật không hợp lệ.")
    try:
        out = tools.explain_rule(_ctx(app), rule_id, std)
    except tools.ToolError as exc:
        raise ApiError(str(exc), 404) from None
    out["fix_ops"] = FIXABLE_RULES.get(rule_id, [])
    return out


def summary(app: AppData, rel: Any) -> dict:
    path = app.resolve(rel)
    try:
        out = tools.get_model_summary(_ctx(app), app.rel(path))
    except tools.ToolError as exc:
        raise ApiError(str(exc), 422) from None
    out["file"] = app.rel(path)
    return out


def rules_table(app: AppData, standard: Any) -> dict:
    """Tab Luật áp dụng (chỉ đọc): luật của chuẩn, tham số mặc định và đang áp (hồ sơ công ty), bật/tắt."""
    base = app.load_std(standard, with_profile=False)
    eff = app.load_std(standard, with_profile=True)
    proj = rule_config.scope_settings(base.name, "project", app.ws.root)
    mach = rule_config.scope_settings(base.name, "machine", None)
    rows = []
    for spec in base.rules:
        e = eff.rule(spec.id) or spec
        changed = sorted(k for k in spec.params if e.params.get(k) != spec.params.get(k))
        rows.append({
            "id": spec.id, "title": spec.title, "severity": e.severity, "severity_default": spec.severity,
            "kind": spec.kind,
            "false_positive_risk": spec.false_positive_risk, "source": spec.source, "reads": spec.reads,
            "implemented": spec.implemented, "realtime_ok": spec.realtime_ok,
            "enabled_default": spec.enabled, "enabled": e.enabled,
            "params_default": spec.params, "params_effective": e.params, "params_changed": changed,
            "fix_ops": FIXABLE_RULES.get(spec.id, []),
            "settings": {"project": proj.get(spec.id) or {}, "machine": mach.get(spec.id) or {}},
            "measured": spec.realtime_ok,
        })
    globals_changed = sorted(k for k in base.globals if eff.globals.get(k) != base.globals.get(k))
    prof = app.profile
    return {
        "standard": base.name, "version": base.version, "description": base.description,
        "profile": eff.profile,
        "profile_note": None if prof is None or eff.profile is not None else
        f"Hồ sơ công ty '{prof.name}' viết cho chuẩn {prof.standard}, không áp cho chuẩn này.",
        "globals_default": base.globals, "globals_effective": eff.globals, "globals_changed": globals_changed,
        "rules": rows,
        "counts": {"total": len(rows), "implemented": sum(r["implemented"] for r in rows),
                   "running": sum(r["implemented"] and r["enabled"] for r in rows),
                   "disabled_by_profile": sum(r["enabled_default"] and not r["enabled"] for r in rows),
                   "params_changed": sum(bool(r["params_changed"]) for r in rows)},
        "read_only": False,
        "log": rule_config.read_log("project", app.ws.root, 30),
    }


def update_rule(app: AppData, standard: Any, rule_id: Any, changes: Any, scope: Any = "project") -> dict:
    """Sửa một luật (bật/tắt, mức độ, tham số) ở phạm vi dự án hoặc máy; có hiệu lực ở lần quét sau."""
    std = app.check_standard(standard)
    if not isinstance(rule_id, str) or not re.fullmatch(r"[A-Za-z0-9.\-]{1,32}", rule_id):
        raise ApiError("Mã luật không hợp lệ.")
    try:
        out = rule_config.update_rule(std, rule_id, changes, scope=scope if isinstance(scope, str) else "",
                                      workspace=app.ws.root, standards_dir=app.standards_dir)
    except rule_config.RuleSettingsError as exc:
        raise ApiError(str(exc)) from None
    return {**out, "table": rules_table(app, std)}


def learn_layers(app: AppData, rel: Any, standard: Any, scope: Any = "project") -> dict:
    """Học quy ước layer của công ty từ bản vẽ đang mở; LY-01 coi các layer này là đúng quy ước."""
    std = app.check_standard(standard)
    model = app.model(app.resolve(rel))
    try:
        out = rule_config.learn_layers(std, [la.name for la in model.layers], scope=scope if isinstance(scope, str) else "",
                                       workspace=app.ws.root, standards_dir=app.standards_dir)
    except rule_config.RuleSettingsError as exc:
        raise ApiError(str(exc)) from None
    return {**out, "table": rules_table(app, std)}


def translate_drawing(app: AppData, rel: Any, to: Any, sheet: Any = None, backend: Any = "auto", mode: Any = "copy",
                      prefer: Any = None, experimental: bool = False) -> dict:
    """Dịch bản vẽ (hoặc một tờ) sang Tiếng Anh/Tiếng Trung: đề xuất changeset, trả xem trước + báo cáo dịch."""
    from ..studio.llm import all_backends
    from ..translate import TARGETS, TranslateError, build

    path = app.resolve(rel)
    if to not in TARGETS:
        raise ApiError("Chọn ngôn ngữ đích: en (Tiếng Anh) hoặc zh (Tiếng Trung).")
    if mode not in ("copy", "layer"):
        raise ApiError("Cách dịch: copy (thay chữ) hoặc layer (song ngữ, thêm chữ dịch trên layer riêng).")
    handles = None
    if sheet is not None:
        st = app.structure(app.model(path))
        s = next((x for x in st.sheets if x.id == sheet), None)
        if s is None:
            raise ApiError("Không có tờ này.")
        handles = set(s.handles)
    # AI theo trợ lý người dùng đã chọn (vd. Codex CLI) trước; AI khác chỉ là dự phòng khi cái đó lỗi/hết lượt
    be = backend if backend is not None and not isinstance(backend, str) else (
        all_backends(allow_codex=experimental, prefer=prefer if isinstance(prefer, str) else None) if backend != "none" else None)
    try:
        res = build(path, to, workspace=app.ws.root, handles=handles, backend=be, mode=mode)
    except TranslateError as exc:
        raise ApiError(str(exc)) from None
    rep = {k: v for k, v in res["report"].items() if k != "rows"}
    rep["rows"] = res["report"]["rows"][:300]
    if not res["ops"]:
        return {"report": rep, "preview": None}
    try:
        cs, pv = propose(app.ws, app.rel(path), None, ops=parse_ops(res["ops"]), standard="design-hygiene-v0",
                         standards_dir=app.standards_dir, profile=app.profile, created_by="user",
                         output_tag=to + ("layer" if mode == "layer" else ""))
    except _cs_errors() as exc:
        raise ApiError(str(exc)) from None
    return {"report": rep, "preview": {**pv, "created_by": cs.created_by, "created_at": cs.created_at, "ops_input": cs.ops}}


def template_info(app: AppData) -> dict:
    from ..template import TemplateError, find_template, load_template

    tp = find_template(app.ws.root)
    if tp is None:
        return {"template": None}
    try:
        tpl = load_template(tp)
    except TemplateError as exc:
        return {"template": None, "error": str(exc)}
    scope = "project" if tp.is_relative_to(app.ws.root) else "machine"
    return {"template": {k: tpl.get(k) for k in ("name", "company", "version", "frame", "fields", "rules", "logo", "source")},
            "scope": scope}


def template_learn(app: AppData, rel: Any, sheet: Any, logo: Any = None, name: Any = None) -> dict:
    """Học template từ một tờ của bản vẽ đang mở; lưu vào <dự án>/.cadguard/template."""
    from ..template import TemplateError, learn

    path = app.resolve(rel)
    if not isinstance(sheet, int) or sheet < 1:
        raise ApiError("Chọn một tờ (số thứ tự từ 1).")
    lp = None
    if logo:
        if not isinstance(logo, str) or len(logo) > 1024:
            raise ApiError("Đường dẫn logo không hợp lệ.")
        lp = Path(logo)
        if lp.suffix.lower() not in (".png", ".jpg", ".jpeg", ".bmp") or not lp.is_file():
            raise ApiError("Logo phải là tệp ảnh PNG/JPG có thật trên máy.")
    try:
        learn(path, sheet, app.ws.root / ".cadguard" / "template", logo=lp, name=name if isinstance(name, str) else "")
    except TemplateError as exc:
        raise ApiError(str(exc)) from None
    return template_info(app)


def reset_rule(app: AppData, standard: Any, rule_id: Any, scope: Any = "project") -> dict:
    std = app.check_standard(standard)
    if not isinstance(rule_id, str) or not re.fullmatch(r"[A-Za-z0-9.\-]{1,32}", rule_id):
        raise ApiError("Mã luật không hợp lệ.")
    try:
        out = rule_config.reset_rule(std, rule_id, scope=scope if isinstance(scope, str) else "",
                                     workspace=app.ws.root, standards_dir=app.standards_dir)
    except rule_config.RuleSettingsError as exc:
        raise ApiError(str(exc)) from None
    return {**out, "table": rules_table(app, std)}


# ---------- gợi ý thao tác sửa từ phát hiện (docs/changeset.md mục 3) ----------

# Luật có thao tác sửa: một nguồn ở `contracts.FIXABLE_RULES` (dẫn lại ở đây cho mã cũ).
_VS07_STYLE = re.compile(r"kiểu chữ '([^']+)' với phông")
_SPECIAL_LAYERS = {"0", "defpoints"}


def _rx(patterns) -> list[re.Pattern]:
    out = []
    for p in patterns or []:
        try:
            out.append(re.compile(str(p), re.IGNORECASE))
        except re.error:
            continue
    return out


def _xref_base(name: str) -> str:
    if "|" in name:
        return name.rsplit("|", 1)[1]
    if "$0$" in name:
        return name.split("$0$", 1)[1]
    return name


def suggest_ops(app: AppData, rel: Any, standard: Any) -> dict:
    """Từ phát hiện của bản vẽ -> danh sách thao tác gợi ý (người dùng tick chọn). Không ghi gì."""
    path = app.resolve(rel)
    std = app.load_std(standard)
    model = app.model(path)
    res = audit_model(model, std)
    rule_ids = {f.rule_id for f in res.findings}
    protected = _rx(getattr(app.profile.layer_patterns, "protected", None) if app.profile else None)

    def is_protected(name: str) -> bool:
        return any(p.search(name) for p in protected)

    used = Counter(e.layer for e in model.entities)
    used_any = set(used) | set(model.block_layers)
    layer_names = [la.name for la in model.layers]
    normal_layers = [n for n in layer_names
                     if n.casefold() not in _SPECIAL_LAYERS and not is_protected(n)
                     and not any(la.name == n and la.xref_dependent for la in model.layers)]
    by_use = sorted(normal_layers, key=lambda n: (-used.get(n, 0), n))
    ops: list[dict] = []
    notes: list[dict] = []

    def add(rule_id, op, title, desc, *, checked=True, choices=None):
        ops.append({"key": f"op{len(ops) + 1}", "rule_id": rule_id, "op": op, "title": title, "description": desc,
                    "checked": checked, "choices": choices or {}, "help": OP_HELP.get(op["op"], "")})

    purge_names: list[str] = []
    purge_kinds: list[str] = []  # chỉ "layers" (VS-01); VS-02 có thao tác dọn riêng ở cuối
    if "VS-01" in rule_ids:
        allowed = _rx(std.globals.get("allowed_layer_patterns"))
        residue = [la.name for la in model.layers if la.xref_dependent and not any(p.search(la.name) for p in allowed)
                   and not is_protected(la.name)]
        lower = {n.casefold(): n for n in normal_layers}
        for name in residue[:30]:
            if name not in used_any:
                purge_names.append(name)
                continue
            base = lower.get(_xref_base(name).casefold())
            add("VS-01", {"op": "merge_layers", "sources": [name], "target": base or ""},
                f"Gộp layer '{name}' vào layer khác",
                "Đối tượng trên layer dư được chuyển sang layer đích; định nghĩa layer dư bị xoá.",
                checked=bool(base), choices={"target": by_use[:200]})
        if purge_names:
            purge_kinds.append("layers")
    if "VS-03" in rule_ids and by_use:
        add("VS-03", {"op": "move_to_layer", "filter": {"layers": ["0"], "spaces": ["Model"]}, "target": by_use[0]},
            "Chuyển đối tượng trên layer 0 (không gian mô hình) sang layer khác",
            "Chỉ đối tượng trực tiếp trong không gian mô hình; nội dung khối giữ nguyên trên layer 0. Hãy chọn đúng layer đích.",
            checked=False, choices={"target": by_use[:200]})
    if "VS-04" in rule_ids:
        exempt = _rx(std.globals.get("exempt_layer_patterns"))
        flt: dict = {}
        excl = [n for n in layer_names if any(p.search(n) for p in exempt)]
        if excl:
            flt["exclude_layers"] = excl[:500]
        add("VS-04", {"op": "set_bylayer", "filter": flt, "color": True, "lineweight": True},
            "Đặt màu và độ dày nét về ByLayer",
            "Đối tượng trực tiếp trong không gian mô hình/giấy" + (f", trừ {len(excl)} layer được miễn" if excl else "") + ".")
    if "VS-07" in rule_ids:
        bad = sorted({m.group(1) for f in res.findings if f.rule_id == "VS-07" for m in [_VS07_STYLE.search(f.message)] if m})
        good = [s.name for s in model.styles if s.font_kind == "ttf" and s.name not in bad]
        if bad:
            add("VS-07", {"op": "replace_text_style", "from": bad, "to": good[0] if good else ""},
                "Đổi kiểu chữ dùng phông không Unicode sang kiểu chữ phông TrueType",
                f"Kiểu chữ cũ: {', '.join(bad)}. Chỉ TEXT/MTEXT trực tiếp trong không gian mô hình/giấy.",
                checked=bool(good), choices={"to": good[:200]})
    if "VS-06" in rule_ids:
        add("VS-06", {"op": "clear_dim_text_override", "filter": {}, "rerender": True},
            "Trả chữ kích thước về số đo tự động",
            "Chữ ghi đè trên DIMENSION được thay bằng '<>' (số đo thật); khối hình kích thước được vẽ lại.")
    if purge_kinds:
        add("VS-01", {"op": "purge_unused", "kinds": ["layers"], "names": purge_names},
            f"Xoá {len(purge_names)} layer dư từ xref không còn dùng",
            "Chỉ xoá định nghĩa layer không được tham chiếu: " + ", ".join(purge_names[:5])
            + (f" và {len(purge_names) - 5} layer khác" if len(purge_names) > 5 else "") + ".")
    if "VS-02" in rule_ids:
        add("VS-02", {"op": "purge_unused", "kinds": ["text_styles", "dim_styles"]},
            "Xoá kiểu chữ và kiểu kích thước không dùng",
            "Chỉ xoá định nghĩa không được tham chiếu; không xoá đối tượng hình học. Đặt cuối để dọn cả kiểu vừa được "
            "giải phóng bởi thao tác đổi kiểu chữ.")
    from ..template import TemplateError, apply_ops, find_template, load_template

    tp = find_template(app.ws.root)
    if tp is not None:
        try:
            tpl = load_template(tp)
            fill, notes_t = apply_ops(model, tpl, renumber=False, template_dir=tp.parent)
            renum, _n = apply_ops(model, tpl, renumber=True, fill_scale=False, fixed=False, frames=False)
        except TemplateError:
            fill, renum, notes_t = [], [], []
        frame_titles = {
            "replace_title_block": ("TP-01", "Thay khung tên cũ bằng khung template",
                                    "khung tên cũ được thay bằng khối template tại cùng vị trí, giữ hệ số; giá trị thẻ cũ "
                                    "chuyển sang thẻ mới (xem ghi chú). Không đụng hình vẽ, kích thước, chú thích."),
            "set_sheet_scale": ("TP-05", "Đưa hệ số khung về tỉ lệ cho phép",
                                "khung được phóng về tỉ lệ cho phép gần nhất, giữ tâm vùng vẽ; chỉ khi nội dung vẫn nằm "
                                "trong vùng vẽ. Nội dung tờ không đổi."),
            "fit_sheet": ("TP-07", "Dời khung cho nội dung vào giữa vùng vẽ",
                          "chỉ dời khung tên (và thuộc tính), không dời hình vẽ."),
            "set_attribs": ("TP-06", "Điền khung tên theo template (thông tin cố định, tỉ lệ theo hệ số khung)",
                            "khung tên được điền lại; chỉ đổi giá trị thuộc tính, không đụng hình vẽ."),
        }
        for op in fill:
            rid, title, desc = frame_titles[op["op"]]
            add(rid, op, title, f"{len(op['items'])} {desc}", checked=False)
        if renum:
            add("TP-10", renum[0], "Đánh số bản vẽ lại theo thứ tự tờ",
                f"{len(renum[0]['items'])} khung tên đổi số theo mẫu của template (trái sang phải, trên xuống dưới).",
                checked=False)
        for n in notes_t[:20]:
            notes.append({"rule_id": "TP-05", "message": n})
    enc = app.structure(model).encoding
    if enc.get("styles") or enc.get("guessed_tcvn3"):
        add("VS-07", {"op": "convert_unicode"}, "Chuyển chữ TCVN3/VNI sang Unicode (phông Be Vietnam Pro)",
            "Chữ tiếng Việt mã cũ được đổi sang Unicode, kiểu chữ phông cũ trỏ sang Be Vietnam Pro; chuỗi không chắc "
            "bảng mã giữ nguyên và được liệt kê. Chỉ chạy khi bạn chọn; ra tệp mới, hoàn tác được.", checked=False)
    for rid in sorted(rule_ids):
        if rid in NO_FIX_NOTE:
            notes.append({"rule_id": rid, "message": NO_FIX_NOTE[rid]})
        elif rid not in FIXABLE_RULES:
            notes.append({"rule_id": rid, "message": "Chưa có thao tác sửa tự động cho luật này; hãy sửa trong phần mềm CAD."})
    return {"file": app.rel(path), "standard": std.name, "ops": ops, "notes": notes,
            "protected_patterns": len(protected)}


# ---------- changeset: đề xuất -> xem trước -> áp dụng (người xác nhận) -> hoàn tác ----------

def _cs_errors():
    return (ChangesetError, OpError, PathDenied, ProfileError)


def _check_id(cid: Any) -> str:
    if not isinstance(cid, str) or not ID_RE.fullmatch(cid):
        raise ApiError("Mã changeset không hợp lệ (dạng cs- và 12 ký tự hex).")
    return cid


def propose_changeset(app: AppData, rel: Any, standard: Any, ops: Any, protected_layers: Any = None) -> dict:
    path = app.resolve(rel)
    std = app.check_standard(standard)
    if not isinstance(ops, list) or not ops:
        raise ApiError("Chưa chọn thao tác nào.")
    if protected_layers is not None and (not isinstance(protected_layers, list)
                                         or not all(isinstance(x, str) for x in protected_layers)):
        raise ApiError("protected_layers phải là danh sách tên layer.")
    try:
        parsed = parse_ops(ops)
        cs, pv = propose(app.ws, app.rel(path), None, ops=parsed, standard=std, standards_dir=app.standards_dir,
                         profile=app.profile, protected_layers=protected_layers or [], created_by="user")
    except _cs_errors() as exc:
        raise ApiError(str(exc)) from None
    return {**pv, "created_by": cs.created_by, "created_at": cs.created_at, "ops_input": cs.ops}


def get_changeset(app: AppData, cid: Any) -> dict:
    cid = _check_id(cid)
    path = app.ws.root / STORE_DIR / f"{cid}.json"
    if not path.is_file():
        raise ApiError("Không tìm thấy changeset.", 404)
    try:
        cs = load_changeset(path)
    except ChangesetError as exc:
        raise ApiError(str(exc)) from None
    log = _apply_log(app, cid)
    return {"id": cs.id, "source": cs.source.model_dump(), "standard": cs.standard, "created_by": cs.created_by,
            "created_at": cs.created_at, "ops": cs.ops, "preview": cs.preview, "applied": log}


def _apply_log(app: AppData, cid: str) -> dict | None:
    p = app.ws.root / STORE_DIR / f"{cid}.apply.json"
    try:
        log = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {"output": log.get("output"), "applied_at": log.get("applied_at"), "undone_at": log.get("undone_at"),
            "validation": log.get("validation")}


def list_changesets(app: AppData) -> dict:
    d = app.ws.root / STORE_DIR
    items = []
    if d.is_dir():
        for p in sorted(d.glob("cs-*.json")):
            if not ID_RE.fullmatch(p.stem):
                continue
            try:
                cs = load_changeset(p)
            except ChangesetError:
                continue
            pv = cs.preview or {}
            items.append({"id": cs.id, "source": cs.source.path, "standard": cs.standard, "created_by": cs.created_by,
                          "created_at": cs.created_at, "ops": len(cs.ops), "ok": pv.get("ok"),
                          "summary_vi": pv.get("summary_vi"), "applied": _apply_log(app, cs.id)})
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return {"changesets": items[:200]}


def apply_changeset(app: AppData, cid: Any, confirm: Any) -> dict:
    cid = _check_id(cid)
    if confirm is not True:
        raise ApiError("Cần người dùng bấm xác nhận trong giao diện trước khi áp dụng changeset.", 409)
    try:
        res = apply(app.ws, cid, confirm=True, profile=app.profile, standards_dir=app.standards_dir)
    except _cs_errors() as exc:
        raise ApiError(str(exc), 409) from None
    h = app.history
    h.record("apply", file=h.file_id(res["source"]["path"]), out=h.file_id(res["output"]["path"]), changeset=cid,
             ok=bool((res.get("validation") or {}).get("ok")))
    return res


def undo_changeset(app: AppData, cid: Any, confirm: Any) -> dict:
    cid = _check_id(cid)
    if confirm is not True:
        raise ApiError("Cần người dùng bấm xác nhận trước khi hoàn tác.", 409)
    try:
        res = undo(app.ws, cid, confirm=True)
    except _cs_errors() as exc:
        raise ApiError(str(exc), 409) from None
    app.history.record("undo", out=app.history.file_id(res["removed"]), changeset=cid)
    return res


# ---------- xem trước hình, 3D, bàn giao ----------

def geometry(app: AppData, rel: Any) -> dict:
    path = app.resolve(rel)
    out = drawing_geometry(app.model(path))
    out["file"] = app.rel(path)
    return out


def preview(app: AppData, rel: Any, wait: Any = None, layout: Any = "Model") -> dict:
    """Xem trước chính xác (bộ vẽ ezdxf, dựng nền + cache theo băm nội dung).

    `status`: `ready` (kèm `svg` đã lọc, `viewbox`, `boxes` theo handle), `pending` (đang dựng: hỏi lại sau) hoặc
    `fallback` (kèm `reason`: giao diện dùng `/api/geometry` — hình đơn giản hoá).
    """
    path = app.resolve(rel)
    w = float(wait) if isinstance(wait, (int, float)) and not isinstance(wait, bool) else 0.0
    if not isinstance(layout, str) or not 1 <= len(layout) <= 255:
        raise ApiError("Layout không hợp lệ.")
    out = app.previews.status(path, wait=min(max(w, 0.0), 5.0), layout_name=layout)
    out["file"] = app.rel(path)
    return out


MAX_BOXES = 5000


def scene3d(app: AppData, rel: Any, item: Any = None) -> dict:
    """Cảnh 3D tất định ở chế độ chỉ xem: hộp + màu vật liệu, không tên tệp/đường dẫn.

    Bản vẽ kiểu công ty (hạng mục có mặt bằng + mặt đứng): cảnh `cg.scene/2` theo hạng mục (`app/scene_api.py`);
    còn lại: cảnh `cg.scene/1` theo quy ước layer/khối."""
    from ..scene import build_scene
    from ..scene.geometry import boxes
    from ..scene.gltf import color_for
    from . import scene_api

    path = app.resolve(rel)
    model = app.model(path)
    if item or scene_api.has_items(model):
        try:
            return {"file": app.rel(path), **scene_api.view(model, app.ws.root, item)}
        except scene_api.SceneApiError as exc:
            raise ApiError(str(exc), 422) from None
    sc = build_scene(model)
    bx = boxes(sc)
    data = [{"b": [list(p) for p in b.base], "z0": b.z0, "z1": b.z1, "c": list(color_for(b.material)), "k": b.kind}
            for b in bx[:MAX_BOXES]]
    return {"file": app.rel(path), "boxes": data, "truncated": len(bx) > MAX_BOXES,
            "counts": {"walls": len(sc.walls), "modules": len(sc.modules), "panels": len(sc.panels),
                       "gaps": len(sc.gaps), "skipped": len(sc.skipped)},
            "gaps": [g.message for g in sc.gaps[:20]], "notes": list(sc.notes)[:10]}


def construction_get(app: AppData) -> dict:
    from ..construction import describe, effective

    return {**effective(app.ws.root), "fields": describe()}


def construction_save(app: AppData, scope: Any, values: Any, reset: Any = False) -> dict:
    from .. import construction as cons

    if reset is True:
        return {**cons.reset(app.ws.root, str(scope)), "fields": cons.describe()}
    if not isinstance(values, dict):
        raise ApiError("Thiếu thông số.")
    try:
        return {**cons.save(app.ws.root, str(scope), values), "fields": cons.describe()}
    except ValueError as exc:
        raise ApiError(str(exc)) from None


GRAPH_DIR = ".cadguard/graph"


def _construction_key(root) -> str:
    import hashlib

    from ..construction import effective

    e = effective(root)
    return hashlib.sha256(json.dumps([e["values"], e["confirmed"]], sort_keys=True).encode("utf-8")).hexdigest()[:6]


def drawing_graph(app: AppData, rel: Any, refresh: Any = False) -> dict:
    """Đồ thị tri thức bản vẽ + cổng sẵn sàng. Lưu `.cadguard/graph/<băm>.json` theo nội dung tệp (dùng lại khi tệp
    và phần bổ sung 3D chưa đổi). Bản vẽ không bị sửa."""
    import hashlib

    from ..graph import SCHEMA as GRAPH_SCHEMA
    from ..graph import build_graph
    from . import scene_api

    path = app.resolve(rel)
    model = app.model(path)
    from ..graph_ai import load_overrides, overrides_key

    supp = scene_api.read_supplement(app.ws.root, model.file_hash)
    key = (model.file_hash[:16] + "-" + hashlib.sha256(json.dumps(supp, sort_keys=True).encode("utf-8")).hexdigest()[:8]
           + overrides_key(app.ws.root, model.file_hash)
           + _construction_key(app.ws.root))
    cache = app.ws.root / GRAPH_DIR / f"{key}.json"
    if refresh is not True and cache.is_file():
        try:
            g = json.loads(cache.read_text(encoding="utf-8"))
            if g.get("schema") == GRAPH_SCHEMA:
                return {"file": app.rel(path), "cached": True, **g}
        except (OSError, ValueError):
            pass
    from ..construction import effective as construction_effective

    g = build_graph(model, supplement=supp, overrides=load_overrides(app.ws.root, model.file_hash),
                    profile={"construction": construction_effective(app.ws.root)["confirmed"]})
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(g, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return {"file": app.rel(path), "cached": False, **g}


def scene_action(app: AppData, rel: Any, action: str, body: dict) -> dict:
    """Nhập phần thiếu / xác nhận đề xuất (`set`), lưu đề xuất cần xác nhận (`propose`), dữ liệu gửi LLM (`prompt`),
    tải GLB (`glb`). Chỉ ghi tệp bổ sung trong `.cadguard/scene/`; bản vẽ không bị sửa."""
    from . import scene_api

    path = app.resolve(rel)
    model = app.model(path)
    root = app.ws.root
    try:
        if action == "set":
            return {"file": app.rel(path), **scene_api.set_value(model, root, body.get("item"), body.get("key"), body.get("value"))}
        if action == "propose":
            return scene_api.add_proposals(model, root, body.get("item"), body.get("proposals"))
        if action == "prompt":
            return scene_api.prompt(model, root, body.get("item"))
        if action == "glb":
            return scene_api.glb(model, root, body.get("item"))
        if action == "cutlist":
            return scene_api.cutlist_file(model, root, body.get("item"))
        if action == "source":
            return scene_api.source_geometry(model, root, body.get("item"), body.get("view"))
        if action == "space":
            return {"file": app.rel(path), **scene_api.space_view(model, root)}
        if action == "space_set":
            return {"file": app.rel(path), **scene_api.space_set(model, root, body.get("key"), body.get("value"))}
        if action == "space_glb":
            return scene_api.space_glb(model, root)
    except scene_api.SceneApiError as exc:
        raise ApiError(str(exc), 422) from None
    raise ApiError("Thao tác 3D không hợp lệ.")


def handover(app: AppData, rel: Any, dept: Any) -> dict:
    """Đánh dấu bản vẽ sẵn sàng bàn giao cho phòng kế. Chỉ ghi lịch sử cục bộ; KHÔNG gửi gì đi đâu.

    Điều kiện: đã quét theo mọi chuẩn của phòng (đúng nội dung tệp hiện tại) và không còn lỗi mức E.
    """
    from .history import latest_audits

    path = app.resolve(rel)
    dep = check_dept(app, dept)
    if dep is None:
        raise ApiError("Thiếu phòng.")
    if not dep["standards"]:
        raise ApiError("Phòng này chưa có chuẩn kiểm nên chưa đánh dấu bàn giao được.")
    model = app.model(path)
    fid = app.history.file_id(app.rel(path))
    lat = latest_audits(app.history.read(), dep["id"])
    missing, errors = [], 0
    for std in dep["standards"]:
        e = lat.get((fid, std))
        if e is None or (e.get("sha") and model.file_hash and e["sha"] != model.file_hash[:16]):
            missing.append(std)
        else:
            errors += int(e["counts"].get("E", 0))
    if missing:
        raise ApiError("Hãy quét bản vẽ (bản hiện tại) theo " + ", ".join(missing) + " trước khi bàn giao.", 409)
    if errors:
        raise ApiError(f"Còn {errors} lỗi mức E: chưa thể bàn giao. Sửa hết lỗi E rồi quét lại.", 409)
    app.history.record("handover", file=fid, dept=dep["id"], to=dep["next"], sha=(model.file_hash or "")[:16] or None)
    names = {d["id"]: d["name"] for d in app.departments["departments"]}
    return {"file": app.rel(path), "dept": dep["id"], "to": [names.get(x, x) for x in dep["next"]], "ready": True,
            "note": "Đã đánh dấu sẵn sàng bàn giao (ghi trong lịch sử dự án trên máy này). cad-guard không gửi tệp đi đâu."}


__all__ = ["ApiError", "AppConfig", "AppData", "FIXABLE_RULES", "apply_changeset", "audit_all", "audit_file",
           "check_dept", "explain", "geometry", "get_changeset", "handover", "list_changesets", "list_drawings",
           "load_departments", "preview", "propose_changeset", "rules_table", "scene3d", "suggest_ops", "summary", "undo_changeset"]


def version_action(app: AppData, rel: Any, action: str, target: Any = None) -> dict:
    """Dòng phiên bản: xem (`info`), chọn bản đang dùng (`set`), hoàn tác/làm lại (`undo`/`redo`). Không xoá tệp nào."""
    from . import versions

    path = app.resolve(rel)
    rp = app.rel(path)
    try:
        if action == "info":
            return versions.info(app.ws.root, rp)
        if action == "set":
            app.resolve(target)  # chặn đường dẫn ngoài dự án
            return versions.set_current(app.ws.root, rp, target)
        if action == "undo":
            return versions.undo(app.ws.root, rp)
        if action == "redo":
            return versions.redo(app.ws.root, rp)
    except ValueError as exc:
        raise ApiError(str(exc), 422) from None
    raise ApiError("Thao tác phiên bản không hợp lệ.")
