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
from ..agent.anonymize import Anonymizer
from ..agent.workspace import PathDenied, Workspace
from ..changeset.apply import ID_RE, STORE_DIR, ChangesetError, apply, load_changeset, propose, undo
from ..changeset.ops import OP_HELP, OpError, parse_ops
from ..reader_select import DEFAULT_STREAM_THRESHOLD_MB
from ..runner import audit_model
from ..standard import CompanyProfile, ProfileError, Standard, find_standards_dir, load_profile, load_standard

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]*$")
SEVERITIES = ("E", "W", "I")
SEVERITY_VI = {"E": "Lỗi", "W": "Cảnh báo", "I": "Thông tin"}
OUTPUT_RE = re.compile(r"\.cg-[0-9a-f]{8}\.dxf$", re.IGNORECASE)
MAX_FINDINGS = 500
DEPARTMENTS_FILE = Path(__file__).with_name("departments.json")


class ApiError(ValueError):
    """Lỗi trả cho trình duyệt: thông điệp tiếng Việt, không đường dẫn tuyệt đối; `status` là mã HTTP."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass
class AppConfig:
    workspace: Path
    profile_path: Path | None = None
    anonymize: bool = True
    experimental: bool = False
    allow_openrouter: bool = False
    account: str | None = None
    stream_threshold_mb: float | None = DEFAULT_STREAM_THRESHOLD_MB
    standards_dir: Path | None = None
    departments_path: Path | None = None


@dataclass
class AppData:
    """Trạng thái dữ liệu của một phiên ứng dụng (một thư mục làm việc, một hồ sơ công ty)."""

    config: AppConfig
    ws: Workspace = field(init=False)
    profile: CompanyProfile | None = field(init=False, default=None)
    standards_dir: Path = field(init=False)
    departments: dict = field(init=False)

    def __post_init__(self) -> None:
        self.ws = Workspace(Path(self.config.workspace))
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
            return load_standard(standard, self.standards_dir, profile=self.profile_for(standard) if with_profile else None)
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
    """Đọc `departments.json`; phòng trỏ tới chuẩn không có vẫn hiện nhưng mang ghi chú."""
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
        std = d.get("standard")
        out.append({"id": d["id"], "name": d["name"], "standard": std if isinstance(std, str) else None,
                    "description": str(d.get("description") or ""), "next": d.get("next"),
                    "standard_ok": isinstance(std, str) and std in standards})
    default = data.get("default") if any(x["id"] == data.get("default") for x in out) else out[0]["id"]
    return {"default": default, "departments": out}


# ---------- bản vẽ, kiểm, giải thích ----------

def list_drawings(app: AppData) -> dict:
    paths = app.ws.list_dxf(".")
    items = []
    for p in paths[:2000]:
        rel = app.rel(p)
        st = p.stat()
        items.append({"path": rel, "name": p.name, "dir": rel.rsplit("/", 1)[0] if "/" in rel else "",
                      "size_bytes": st.st_size, "is_output": bool(OUTPUT_RE.search(p.name))})
    return {"drawings": items, "total": len(paths), "truncated": len(paths) > 2000}


def audit_file(app: AppData, rel: Any, standard: Any) -> dict:
    path = app.resolve(rel)
    std = app.load_std(standard)
    model = app.model(path)
    res = audit_model(model, std)
    counts = Counter(f.severity for f in res.findings)
    groups: dict[str, list[dict]] = {s: [] for s in SEVERITIES}
    by_rule: dict[tuple[str, str], dict] = {}
    for f in res.findings[:MAX_FINDINGS]:
        spec = std.rule(f.rule_id)
        key = (f.severity, f.rule_id)
        g = by_rule.get(key)
        if g is None:
            g = {"rule_id": f.rule_id, "severity": f.severity, "title": spec.title if spec else f.rule_id,
                 "items": [], "count": 0}
            by_rule[key] = g
            groups.setdefault(f.severity, []).append(g)
        g["items"].append({"message": f.message, "layer": f.layer, "layout": f.layout, "count": f.count,
                           "handles": list(f.handles)[:5]})
        g["count"] += max(1, int(f.count or 1))
    fixable = sorted({g["rule_id"] for gs in groups.values() for g in gs} & set(FIXABLE_RULES))
    skipped = [{"rule_id": r, "reason": "Lỗi nội bộ của luật." if r in res.internal_errors else reason}
               for r, reason in res.skipped]
    return {
        "file": app.rel(path), "standard": std.name, "version": std.version, "profile": std.profile,
        "counts": {s: counts.get(s, 0) for s in SEVERITIES}, "rules_run": res.rules_run,
        "groups": [{"severity": s, "label": SEVERITY_VI[s], "rules": groups.get(s, [])} for s in SEVERITIES],
        "skipped": skipped, "truncated": len(res.findings) > MAX_FINDINGS, "fixable_rules": fixable,
        "records_capped": bool(model.stats is not None and model.stats.entity_records_truncated),
    }


def audit_all(app: AppData, standard: Any) -> dict:
    std = app.check_standard(standard)
    out = []
    for item in list_drawings(app)["drawings"][:200]:
        try:
            r = audit_file(app, item["path"], std)
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
    rows = []
    for spec in base.rules:
        e = eff.rule(spec.id) or spec
        changed = sorted(k for k in spec.params if e.params.get(k) != spec.params.get(k))
        rows.append({
            "id": spec.id, "title": spec.title, "severity": spec.severity, "kind": spec.kind,
            "false_positive_risk": spec.false_positive_risk, "source": spec.source, "reads": spec.reads,
            "implemented": spec.implemented, "realtime_ok": spec.realtime_ok,
            "enabled_default": spec.enabled, "enabled": e.enabled,
            "params_default": spec.params, "params_effective": e.params, "params_changed": changed,
            "fix_ops": FIXABLE_RULES.get(spec.id, []),
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
        "read_only": True,
    }


# ---------- gợi ý thao tác sửa từ phát hiện (docs/changeset.md mục 3) ----------

# Luật có thao tác sửa trong từ vựng cố định. VS-05 không có (bớt IMAGE/WIPEOUT là xoá đối tượng).
FIXABLE_RULES: dict[str, list[str]] = {
    "VS-01": ["merge_layers", "purge_unused"],
    "VS-02": ["purge_unused", "replace_text_style", "replace_dim_style"],
    "VS-03": ["move_to_layer"],
    "VS-04": ["set_bylayer"],
    "VS-06": ["clear_dim_text_override"],
    "VS-07": ["replace_text_style"],
}
NO_FIX_NOTE = {
    "VS-05": "Bớt WIPEOUT/IMAGE/OLE là xoá đối tượng, ngoài từ vựng thao tác: hãy xử lý trong phần mềm CAD.",
}
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
        return apply(app.ws, cid, confirm=True, profile=app.profile, standards_dir=app.standards_dir)
    except _cs_errors() as exc:
        raise ApiError(str(exc), 409) from None


def undo_changeset(app: AppData, cid: Any, confirm: Any) -> dict:
    cid = _check_id(cid)
    if confirm is not True:
        raise ApiError("Cần người dùng bấm xác nhận trước khi hoàn tác.", 409)
    try:
        return undo(app.ws, cid, confirm=True)
    except _cs_errors() as exc:
        raise ApiError(str(exc), 409) from None


# ---------- tích hợp Unified Studio: 2D Preview, 3D Scene/Clusters, Review & Handover, WorkspaceState ----------

REVIEW_STORE_FILE = ".cadguard/reviews.json"
MAX_PREVIEW_ENTITIES = 2500


def preview_2d(app: AppData, rel: Any, standard: Any = None) -> dict:
    """Trích xuất hình học 2D, danh sách layer, các cụm hình chiếu (clusters) và toạ độ lỗi cho khung nhìn 2D."""
    from ..studio.clusters import _ebox, clusters_of

    path = app.resolve(rel)
    model = app.model(path)
    cl = clusters_of(model)
    by_handle: dict[str, tuple[float, float, float, float]] = {}
    items: list[dict] = []
    xs: list[float] = []
    ys: list[float] = []

    for e in model.entities:
        if e.space != "Model":
            continue
        eb = _ebox(e)
        if eb:
            by_handle[e.handle] = eb
            xs.extend((eb[0], eb[2]))
            ys.extend((eb[1], eb[3]))
        elif e.pos:
            by_handle[e.handle] = (e.pos[0] - 20.0, e.pos[1] - 10.0, e.pos[0] + 80.0, e.pos[1] + 20.0)
            xs.append(e.pos[0])
            ys.append(e.pos[1])
        elif e.insert:
            by_handle[e.handle] = (e.insert[0] - 30.0, e.insert[1] - 30.0, e.insert[0] + 30.0, e.insert[1] + 30.0)
            xs.append(e.insert[0])
            ys.append(e.insert[1])

        if len(items) >= MAX_PREVIEW_ENTITIES:
            continue
        if e.type in ("LINE", "LWPOLYLINE") and e.pts:
            items.append({
                "h": e.handle,
                "t": e.type,
                "layer": e.layer,
                "pts": [[round(p[0], 1), round(p[1], 1)] for p in e.pts[:64]],
                "closed": bool(e.closed),
            })
        elif e.type in ("CIRCLE", "ARC") and e.pts and e.radius:
            items.append({
                "h": e.handle,
                "t": "CIRCLE",
                "layer": e.layer,
                "c": [round(e.pts[0][0], 1), round(e.pts[0][1], 1)],
                "r": round(float(e.radius), 1),
            })
        elif e.type in ("TEXT", "MTEXT") and e.pos and e.text:
            items.append({
                "h": e.handle,
                "t": "TEXT",
                "layer": e.layer,
                "pos": [round(e.pos[0], 1), round(e.pos[1], 1)],
                "text": e.text[:80],
            })
        elif e.type == "INSERT" and e.insert:
            items.append({
                "h": e.handle,
                "t": "INSERT",
                "layer": e.layer,
                "pos": [round(e.insert[0], 1), round(e.insert[1], 1)],
                "block": e.block or "",
            })

    if xs and ys:
        s_xs = sorted(xs)
        s_ys = sorted(ys)
        if len(s_xs) >= 20:
            lo_x = int(len(s_xs) * 0.02)
            hi_x = max(lo_x, min(len(s_xs) - 1, int(len(s_xs) * 0.98)))
            lo_y = int(len(s_ys) * 0.02)
            hi_y = max(lo_y, min(len(s_ys) - 1, int(len(s_ys) * 0.98)))
            bounds = [round(s_xs[lo_x], 1), round(s_ys[lo_y], 1), round(s_xs[hi_x], 1), round(s_ys[hi_y], 1)]
        else:
            bounds = [round(s_xs[0], 1), round(s_ys[0], 1), round(s_xs[-1], 1), round(s_ys[-1], 1)]
    else:
        bounds = [0.0, 0.0, 1000.0, 700.0]
    layer_counts = Counter(e.layer for e in model.entities if e.space == "Model")
    layers = [{"name": la.name, "color": la.color, "off": la.off, "frozen": la.frozen, "count": layer_counts.get(la.name, 0)}
              for la in model.layers]

    markers: list[dict] = []
    if standard:
        std = app.load_std(standard)
        res = audit_model(model, std)
        for idx, f in enumerate(res.findings[:120], 1):
            box = None
            for h in f.handles or []:
                if h in by_handle:
                    box = by_handle[h]
                    break
            if box is None and f.layer:
                for e in model.entities:
                    if e.layer == f.layer and e.handle in by_handle:
                        box = by_handle[e.handle]
                        break
            if box is not None:
                markers.append({
                    "id": f"M{idx}",
                    "rule_id": f.rule_id,
                    "severity": f.severity,
                    "message": f.message,
                    "layer": f.layer,
                    "handles": list(f.handles)[:5],
                    "bbox": [round(v, 1) for v in box],
                })

    return {
        "file": app.rel(path),
        "dxf_version": model.dxf_version,
        "insunits": model.insunits,
        "bounds": bounds,
        "layers": layers,
        "clusters": [
            {
                "id": c.id,
                "bbox": [round(v, 1) for v in c.bbox],
                "size": [round(c.bbox[2] - c.bbox[0], 1), round(c.bbox[3] - c.bbox[1], 1)],
                "entities": len(c.entities),
            }
            for c in cl
        ],
        "entities": items,
        "markers": markers,
        "truncated": len(model.entities) > MAX_PREVIEW_ENTITIES,
    }


def scene_3d(app: AppData, rel: Any, supplement: Any = None, views: Any = None) -> dict:
    """Dựng cảnh 3D (`cg.scene/1`) và danh sách cụm hình chiếu (`studio/clusters.py`) cho một bản vẽ."""
    from ..scene.build import build_scene
    from ..scene.geometry import boxes
    from ..studio.clusters import clusters_of

    path = app.resolve(rel)
    model = app.model(path)
    cl = clusters_of(model)
    by_id = {c.id: c.entities for c in cl}
    resolved_views = None
    if isinstance(views, dict) and views:
        resolved_views = {k: by_id.get(v, []) for k, v in views.items() if k in ("front", "side", "top") and isinstance(v, str)}
    supp = supplement if isinstance(supplement, dict) else {}
    sc = build_scene(model, supplement=supp, views=resolved_views)
    box_list = [
        {
            "base": [[round(x, 1), round(y, 1)] for x, y in b.base],
            "z0": round(b.z0, 1),
            "z1": round(b.z1, 1),
            "material": b.material,
        }
        for b in boxes(sc)
    ]
    return {
        "file": app.rel(path),
        "scene": sc.model_dump(by_alias=True),
        "boxes": box_list,
        "clusters": [
            {
                "id": c.id,
                "bbox": [round(v, 1) for v in c.bbox],
                "size": [round(c.bbox[2] - c.bbox[0], 1), round(c.bbox[3] - c.bbox[1], 1)],
                "entities": len(c.entities),
                "layers": sorted({e.layer for e in c.entities}),
            }
            for c in cl
        ],
    }


def scene_glb(app: AppData, rel: Any) -> bytes:
    """Xuất tệp nhị phân glTF 2.0 (.glb) từ bản vẽ đang chọn."""
    from ..scene.build import build_scene
    from ..scene.gltf import build_glb

    path = app.resolve(rel)
    model = app.model(path)
    sc = build_scene(model)
    return build_glb(sc)


def studio_state(app: AppData, rel: Any, supplement: Any = None, views: Any = None) -> dict:
    """Trạng thái tích hợp của Studio 3D (clusters + digest + scene + gaps)."""
    from ..scene.build import build_scene
    from ..studio.clusters import clusters_of, digest

    path = app.resolve(rel)
    model = app.model(path)
    cl = clusters_of(model)
    by_id = {c.id: c.entities for c in cl}
    resolved_views = None
    if isinstance(views, dict) and views:
        resolved_views = {k: by_id.get(v, []) for k, v in views.items() if k in ("front", "side", "top") and isinstance(v, str)}
    supp = supplement if isinstance(supplement, dict) else {}
    sc = build_scene(model, supplement=supp, views=resolved_views)
    return {
        "file": app.rel(path),
        "scene": sc.model_dump(by_alias=True),
        "digest": digest(model, sc, cl),
    }


def _load_reviews(app: AppData) -> list[dict]:
    p = app.ws.root / REVIEW_STORE_FILE
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save_reviews(app: AppData, notes: list[dict]) -> None:
    p = app.ws.root / REVIEW_STORE_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")


def list_review_notes(app: AppData, rel: Any = None) -> dict:
    """Liệt kê các ghi chú duyệt & bàn giao (Review Notes) của bản vẽ hoặc cả thư mục."""
    notes = _load_reviews(app)
    if rel:
        target = app.rel(app.resolve(rel))
        notes = [n for n in notes if n.get("file_path") == target]
    return {"notes": notes, "total": len(notes)}


def add_review_note(
    app: AppData,
    rel: Any,
    message: Any,
    *,
    department: Any = "ky-thuat",
    author: Any = "Kỹ thuật",
    severity: Any = "I",
    rule_id: Any = None,
    handle: Any = None,
    pos: Any = None,
) -> dict:
    """Thêm một ghi chú duyệt bản vẽ / bàn giao (lưu cục bộ tại `.cadguard/reviews.json`, không sửa DXF)."""
    from datetime import datetime, timezone

    path = app.resolve(rel)
    if not isinstance(message, str) or not message.strip():
        raise ApiError("Nội dung ghi chú không được để trống.")
    sev = severity if severity in SEVERITIES else "I"
    notes = _load_reviews(app)
    note_id = f"RV-{len(notes) + 1:03d}"
    coords = None
    if isinstance(pos, (list, tuple)) and len(pos) == 2:
        try:
            coords = [round(float(pos[0]), 1), round(float(pos[1]), 1)]
        except (TypeError, ValueError):
            coords = None
    entry = {
        "id": note_id,
        "file_path": app.rel(path),
        "department": str(department or "ky-thuat"),
        "author": str(author or "Kỹ thuật")[:60],
        "severity": sev,
        "message": message.strip()[:1000],
        "rule_id": str(rule_id) if rule_id else None,
        "handle": str(handle) if handle else None,
        "pos": coords,
        "resolved": False,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    notes.append(entry)
    _save_reviews(app, notes)
    return {"note": entry, "notes": [n for n in notes if n.get("file_path") == entry["file_path"]]}


def resolve_review_note(app: AppData, note_id: Any, resolved: Any = True) -> dict:
    """Đánh dấu đã xử lý / mở lại một ghi chú duyệt bản vẽ."""
    if not isinstance(note_id, str) or not note_id:
        raise ApiError("Thiếu mã ghi chú.")
    notes = _load_reviews(app)
    found = None
    for n in notes:
        if n.get("id") == note_id:
            n["resolved"] = bool(resolved)
            found = n
            break
    if found is None:
        raise ApiError("Không tìm thấy ghi chú này.", 404)
    _save_reviews(app, notes)
    return {"note": found}


def handover_package(app: AppData, rel: Any, standard: Any, department: Any = None) -> dict:
    """Tổng hợp gói bàn giao (Handover Package) giữa các phòng ban kèm danh sách kiểm và ghi chú."""
    audit_res = audit_file(app, rel, standard)
    notes = list_review_notes(app, rel)["notes"]
    dept_id = department or app.departments["default"]
    dept_obj = next((d for d in app.departments["departments"] if d["id"] == dept_id), app.departments["departments"][0])
    next_obj = next((d for d in app.departments["departments"] if d["id"] == dept_obj.get("next")), None)
    e_count = audit_res["counts"]["E"]
    w_count = audit_res["counts"]["W"]
    unresolved_notes = sum(1 for n in notes if not n.get("resolved"))
    ready = e_count == 0
    dest_name = next_obj["name"] if next_obj else "Xưởng sản xuất"
    summary_lines = [
        f"BIÊN BẢN BÀN GIAO BẢN VẼ: {audit_res['file']}",
        f"- Phòng bàn giao: {dept_obj['name']} → Nhận bàn giao: {dest_name}",
        f"- Chuẩn kiểm tra: {audit_res['standard']} (v{audit_res['version']})",
        f"- Kết quả kiểm tất định: {e_count} Lỗi (E) · {w_count} Cảnh báo (W) · {audit_res['counts']['I']} Thông tin (I)",
        f"- Ghi chú bàn giao: {len(notes)} ghi chú ({unresolved_notes} mục cần lưu ý)",
        f"- Trạng thái cổng bàn giao: {'ĐẠT — Sẵn sàng chuyển giao' if ready else 'CHẶN — Còn lỗi mức E cần xử lý trước khi bàn giao'}",
    ]
    for n in notes:
        status = "Đã xử lý" if n.get("resolved") else "Cần lưu ý"
        summary_lines.append(f"  * [{n['id']} · {status}] ({n['author']}): {n['message']}")
    return {
        "file": audit_res["file"],
        "department": dept_obj["name"],
        "next_department": dest_name,
        "standard": audit_res["standard"],
        "counts": audit_res["counts"],
        "ready": ready,
        "notes_count": len(notes),
        "unresolved_notes": unresolved_notes,
        "notes": notes,
        "handover_text": "\n".join(summary_lines),
    }


def workspace_state(app: AppData, rel: Any, standard: Any, department: Any = None, mode: Any = "audit") -> dict:
    """Trả về Hợp đồng Dữ liệu Trung tâm `WorkspaceState` (`DrawingSessionSpec`) cho tệp đang mở."""
    from ..contracts import AuditFindingSpec, AuditReportSpec, ReviewNoteSpec, WorkspaceState

    path = app.resolve(rel)
    std_name = app.check_standard(standard)
    audit_res = audit_file(app, rel, std_name)
    sc_res = scene_3d(app, rel)
    raw_notes = list_review_notes(app, rel)["notes"]
    findings: list[AuditFindingSpec] = []
    for g in audit_res["groups"]:
        for r in g["rules"]:
            for it in r["items"]:
                findings.append(
                    AuditFindingSpec(
                        rule_id=r["rule_id"],
                        severity=r["severity"],
                        title=r["title"],
                        message=it["message"],
                        layer=it.get("layer"),
                        layout=it.get("layout"),
                        handles=it.get("handles") or [],
                    )
                )
    report_spec = AuditReportSpec(
        file_path=app.rel(path),
        standard=audit_res["standard"],
        standard_version=str(audit_res["version"]),
        department=str(department or app.departments["default"]),
        counts=audit_res["counts"],
        rules_run=audit_res["rules_run"],
        findings=findings,
        fixable_rules=audit_res["fixable_rules"],
        records_capped=audit_res["records_capped"],
    )
    note_specs = [ReviewNoteSpec(**n) for n in raw_notes]
    ws_state = WorkspaceState(
        workspace_name=app.ws.root.name,
        active_file=app.rel(path),
        active_mode=mode if mode in ("audit", "diff", "scene", "review") else "audit",
        department=str(department or app.departments["default"]),
        standard=std_name,
        anonymize=app.config.anonymize,
        audit_report=report_spec,
        scene_3d=sc_res["scene"],
        review_notes=note_specs,
    )
    return ws_state.model_dump()


__all__ = [
    "ApiError",
    "AppConfig",
    "AppData",
    "FIXABLE_RULES",
    "add_review_note",
    "apply_changeset",
    "audit_all",
    "audit_file",
    "explain",
    "get_changeset",
    "handover_package",
    "list_changesets",
    "list_drawings",
    "list_review_notes",
    "load_departments",
    "preview_2d",
    "propose_changeset",
    "resolve_review_note",
    "rules_table",
    "scene_3d",
    "scene_glb",
    "studio_state",
    "suggest_ops",
    "summary",
    "undo_changeset",
    "workspace_state",
]

