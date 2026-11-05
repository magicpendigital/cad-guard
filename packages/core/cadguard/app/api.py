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
    history: History = field(init=False)
    previews: PreviewManager = field(init=False)
    _reviews: Any = field(init=False, default=None)

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
    paths = app.ws.list_dxf(".", limit=MAX_DRAWINGS + 1, max_dirs=MAX_SCAN_DIRS)
    items = []
    for p in paths[:MAX_DRAWINGS]:
        rel = app.rel(p)
        st = p.stat()
        items.append({"path": rel, "name": p.name, "dir": rel.rsplit("/", 1)[0] if "/" in rel else "",
                      "size_bytes": st.st_size, "is_output": bool(OUTPUT_RE.search(p.name))})
    return {"drawings": items, "total": min(len(paths), MAX_DRAWINGS), "truncated": len(paths) > MAX_DRAWINGS,
            "limit": MAX_DRAWINGS}


def audit_file(app: AppData, rel: Any, standard: Any, dept: Any = None) -> dict:
    path = app.resolve(rel)
    std = app.load_std(standard)
    dep = check_dept(app, dept)
    model = app.model(path)
    res = audit_model(model, std)
    counts = Counter(f.severity for f in res.findings)
    per_rule: Counter = Counter()
    for f in res.findings:
        per_rule[f.rule_id] += max(1, int(f.count or 1))
    app.history.record("audit", **audit_entry(app.history.file_id(app.rel(path)), model.file_hash,
                                               dep["id"] if dep else None, std.name, std.version, counts, per_rule))
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
                           "handles": list(f.handles)[:20]})
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
        "rules_total": len(std.rules), "rules_enabled": sum(1 for r in std.rules if r.enabled and r.implemented),
        "entity_count": len(model.entities), "dxf_version": model.dxf_version, "insunits": model.insunits,
    }


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


def scene3d(app: AppData, rel: Any) -> dict:
    """Cảnh 3D tất định (`cadguard scene`) ở chế độ chỉ xem: hộp + màu vật liệu, không tên tệp/đường dẫn."""
    from ..scene import build_scene
    from ..scene.geometry import boxes
    from ..scene.gltf import color_for

    path = app.resolve(rel)
    sc = build_scene(app.model(path))
    bx = boxes(sc)
    data = [{"b": [list(p) for p in b.base], "z0": b.z0, "z1": b.z1, "c": list(color_for(b.material)), "k": b.kind}
            for b in bx[:MAX_BOXES]]
    return {"file": app.rel(path), "boxes": data, "truncated": len(bx) > MAX_BOXES,
            "counts": {"walls": len(sc.walls), "modules": len(sc.modules), "panels": len(sc.panels),
                       "gaps": len(sc.gaps), "skipped": len(sc.skipped)},
            "gaps": [g.message for g in sc.gaps[:20]], "notes": list(sc.notes)[:10]}


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
