"""Các công cụ đọc bản vẽ, độc lập với giao thức truyền tải."""
from __future__ import annotations

import base64
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache, wraps
import hashlib
import json
from pathlib import Path
import re

from ..dxf_stream import DEFAULT_MAX_ENTITY_RECORDS
from ..reader_select import DEFAULT_STREAM_THRESHOLD_MB, choose_reader, read_with
from ..runner import audit_model
from ..standard import CompanyProfile, find_standards_dir, load_standard
from .anonymize import Anonymizer
from .workspace import Workspace

MAX_QUERY_RECORDS = 500
MAX_QUERY_BYTES = 65536
# Trường `EntityRec` mà query_model trả về khi bật ẩn danh (Bậc 1): danh sách TRẮNG, nên trường mới thêm vào mô hình
# không tự lọt ra cho trợ lý. Không có nội dung chữ (`text`, `attribs`, `dim_text`), không có toạ độ (`pts`, `pos`,
# `insert`, `dup_key` chứa toạ độ); chỉ số liệu vô hướng. Tắt ẩn danh (--no-anonymize) thì trả mọi trường như trước.
QUERY_FIELDS_ANON = frozenset({"handle", "type", "layer", "space", "length", "area", "closed", "has_nonzero_z",
                               "text_style", "block", "is_proxy", "color", "lineweight", "true_color",
                               "rotation", "xscale", "yscale", "radius", "dim_value"})
QUERY_EXCLUDE = frozenset({"attribs", "dim_text", "dup_key"})


class ToolError(ValueError):
    """Lỗi công cụ an toàn để hiển thị."""


@dataclass
class ToolContext:
    workspace: Workspace
    anonymizer: Anonymizer = field(default_factory=Anonymizer)
    standards_dir: Path = field(default_factory=find_standards_dir)
    max_drawings: int = 500
    max_findings: int = 200
    max_summary_items: int = 50
    # Chọn bộ đọc theo kích thước tệp: None/âm = luôn ezdxf, 0 = luôn theo dòng, dương = theo dòng khi >= ngưỡng MiB.
    stream_threshold_mb: float | None = DEFAULT_STREAM_THRESHOLD_MB
    # Trần bản ghi `entities` của bộ đọc theo dòng; quá trần thì kết quả có `records_capped: true`.
    max_entity_records: int = DEFAULT_MAX_ENTITY_RECORDS
    # Hồ sơ công ty (đã nạp, đã kiểm): chỉ áp khi chuẩn được gọi trùng `profile.standard`.
    profile: CompanyProfile | None = None
    ids: dict[str, str] = field(default_factory=dict)


def _safe(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ToolError:
            raise
        except Exception:
            raise ToolError("Không thể thực hiện yêu cầu; hãy kiểm tra dữ liệu và đường dẫn.") from None
    return wrapper


@lru_cache(maxsize=8)
def _cached_model(path: Path, mtime: int, size: int, reader: str, max_entity_records: int | None):
    # Khoá đệm gồm bộ đọc và trần bản ghi: ezdxf và stream (hoặc hai trần khác nhau) không dùng chung mục.
    if reader == "stream":
        return read_with(path, "stream", max_entity_records)
    return read_with(path, "ezdxf")


def load_model(path: Path, stream_threshold_mb: float | None = None, max_entity_records: int = DEFAULT_MAX_ENTITY_RECORDS):
    """Đọc DXF với bộ nhớ đệm nhỏ theo thời gian sửa, kích thước, bộ đọc và trần bản ghi.

    Bộ đọc chọn bằng `reader_select.choose_reader` (như `cadguard audit --reader auto`):
    `stream_threshold_mb` None/âm = luôn ezdxf, 0 = luôn theo dòng, dương = theo dòng khi tệp >= ngưỡng MiB.
    """
    try:
        path = Path(path)
        stat = path.stat()
        reader = choose_reader(path, "auto", stream_threshold_mb).reader
        cap = max(0, int(max_entity_records)) if reader == "stream" else None
        return _cached_model(path, stat.st_mtime_ns, stat.st_size, reader, cap)
    except Exception:
        raise ToolError("Không thể đọc bản vẽ DXF.") from None


def _records_capped(model) -> bool:
    """True khi danh sách đối tượng bị cắt ở trần bản ghi của bộ đọc theo dòng (thống kê vẫn đủ)."""
    return bool(model.stats is not None and model.stats.entity_records_truncated)


def _path(ctx, file):
    return ctx.workspace.resolve(ctx.ids.get(file, file))


def _file_id(ctx, path):
    rel = path.relative_to(ctx.workspace.root).as_posix()
    ident = ctx.anonymizer.token("file", rel)
    ctx.ids[ident] = rel
    return ident


def _model(ctx, file):
    path = _path(ctx, file)
    return path, load_model(path, ctx.stream_threshold_mb, ctx.max_entity_records)


def _names(model):
    names = [("layer", x.name) for x in model.layers]
    names += [("layer", x) for x in model.block_layers]
    names += [("layout", x.name) for x in model.layouts]
    for e in model.entities:
        names.extend((kind, value) for kind, value in (("layer", e.layer), ("layout", e.space), ("block", e.block), ("style", e.text_style)) if value)
    return names


def _standard(ctx, name):
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9.\-]*", name):
        raise ToolError("Tên chuẩn không hợp lệ.")
    root = Path(ctx.standards_dir).resolve(strict=True)
    path = (root / (name + ".yaml")).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ToolError("Không tìm thấy chuẩn.")
    profile = ctx.profile if ctx.profile is not None and ctx.profile.standard == name else None
    return load_standard(name, root, profile=profile)


def _bytes(value):
    return len(json.dumps(value, ensure_ascii=True).encode("utf-8"))


@_safe
def list_drawings(ctx: ToolContext, dir: str = ".") -> dict:
    """Liệt kê DXF trong thư mục tương đối; tối đa 500 mục theo cấu hình."""
    paths = ctx.workspace.list_dxf(dir)
    return {"drawings": [{"id": _file_id(ctx, p), "size_bytes": p.stat().st_size} for p in paths[:max(0, ctx.max_drawings)]], "total": len(paths), "truncated": len(paths) > max(0, ctx.max_drawings)}


@_safe
def audit(ctx: ToolContext, file: str, standard: str = "furniture-v0") -> dict:
    """Kiểm tra tệp hoặc mã phiên theo chuẩn; giới hạn số phát hiện theo cấu hình."""
    std = _standard(ctx, standard)
    path, model = _model(ctx, file)
    result = audit_model(model, std)
    names = _names(model)
    anon = ctx.anonymizer
    findings = [{"rule_id": f.rule_id, "severity": f.severity, "message": anon.scrub_text(f.message, names), "layout": anon.token("layout", f.layout) if f.layout else None, "layer": anon.token("layer", f.layer) if f.layer else None, "count": f.count, "handles": f.handles} for f in result.findings[:max(0, ctx.max_findings)]]
    counts = {s: sum(f.severity == s for f in result.findings) for s in ("E", "W", "I")}
    skipped = [{"rule_id": rule, "reason": ("Lỗi nội bộ của luật." if rule in result.internal_errors else anon.scrub_text(reason, names))} for rule, reason in result.skipped]
    return {"file": _file_id(ctx, path), "standard": std.name, "version": std.version, "profile": std.profile, "counts": counts, "rules_run": result.rules_run, "skipped": skipped, "findings": findings, "truncated": len(result.findings) > max(0, ctx.max_findings), "records_capped": _records_capped(model)}


@_safe
def explain_rule(ctx: ToolContext, rule_id: str, standard: str = "furniture-v0") -> dict:
    """Giải thích mã luật trong chuẩn; tham số chung được giới hạn 8 KB."""
    std = _standard(ctx, standard)
    spec = std.rule(rule_id)
    if spec is None:
        raise ToolError("Không tìm thấy mã luật.")
    root = Path(ctx.standards_dir).resolve()
    md = (root / (standard + ".md")).resolve()
    lines = md.read_text(encoding="utf-8").splitlines() if md.is_relative_to(root) and md.is_file() else []
    description = "\n".join(line for line in lines if rule_id in line)[:8192]
    params = {}
    for key, value in std.globals.items():
        candidate = {**params, key: value}
        if _bytes(candidate) <= 8192:
            params = candidate
    return {**spec.model_dump(include={"id", "title", "severity", "kind", "false_positive_risk", "source", "reads", "implemented"}), "enabled": spec.enabled, "rule_params": dict(spec.params), "profile": std.profile, "params": params, "description_md": description, "examples": {"good": [], "bad": []}}


@_safe
def get_model_summary(ctx: ToolContext, file: str) -> dict:
    """Tóm tắt tệp hoặc mã phiên; danh sách có trần cấu hình và JSON tối đa 16 KB."""
    _, model = _model(ctx, file)
    anon = ctx.anonymizer
    limit = max(0, ctx.max_summary_items)
    types = Counter(e.type for e in model.entities)
    spaces = Counter(anon.token("layout", e.space) for e in model.entities)
    styles = Counter(anon.token("style", e.text_style) for e in model.entities if e.text_style)
    blocks = {e.block for e in model.entities if e.block}
    layouts = [{"name": anon.token("layout", x.name), "paper_w_mm": x.paper_w_mm, "paper_h_mm": x.paper_h_mm, "viewport_count": len(x.viewports)} for x in model.layouts]
    result = {"layer_count": len(model.layers), "block_count": len(blocks), "entities_by_type": dict(types.most_common(limit)), "entities_by_space": dict(spaces.most_common(limit)), "layouts": layouts[:limit], "text_styles": dict(styles.most_common(limit)), "insunits": model.insunits, "dxf_version": model.dxf_version, "truncated": any(len(x) > limit for x in (types, spaces, styles, layouts)), "records_capped": _records_capped(model)}
    while _bytes(result) > 16384:
        result["truncated"] = True
        for key in ("layouts", "text_styles", "entities_by_space", "entities_by_type"):
            if result[key]:
                if isinstance(result[key], list): result[key].pop()
                else: result[key].pop(next(reversed(result[key])))
                break
        else:
            raise ToolError("Không thể giới hạn kích thước kết quả.")
    return result


@_safe
def query_model(ctx: ToolContext, file: str, filter: dict, limit: int = 100, cursor: str | None = None) -> dict:
    """Lọc đối tượng theo layer, loại và space; tối đa 500 mục và 64 KB mỗi trang."""
    if not isinstance(filter, dict) or set(filter) - {"layer", "type", "bbox", "space"}:
        raise ToolError("Bộ lọc không hợp lệ.")
    if "bbox" in filter:
        raise ToolError("lọc theo vùng chưa hỗ trợ")
    path, model = _model(ctx, file)
    anon = ctx.anonymizer
    def values(key):
        v = filter.get(key)
        if v is None: return None
        if isinstance(v, str): return [v]
        if isinstance(v, list) and all(isinstance(x, str) for x in v): return v
        raise ToolError("Bộ lọc không hợp lệ.")
    layers, types, spaces = values("layer"), values("type"), values("space")
    capped = _records_capped(model)
    fingerprint = hashlib.sha256(json.dumps([path.relative_to(ctx.workspace.root).as_posix(), filter], sort_keys=True, ensure_ascii=True).encode()).hexdigest()[:20]
    offset = 0
    if cursor is not None:
        try:
            payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
            offset = payload["offset"]
            if payload["filter"] != fingerprint or type(offset) is not int or offset < 0: raise ValueError
        except Exception:
            raise ToolError("Con trỏ phân trang không hợp lệ hoặc không khớp bộ lọc.") from None
    matched = [e for e in model.entities if (layers is None or e.layer in layers or anon.token("layer", e.layer) in layers) and (types is None or e.type in types) and (spaces is None or e.space in spaces or anon.token("layout", e.space) in spaces)]
    if offset > len(matched): raise ToolError("Con trỏ phân trang không hợp lệ.")
    limit = max(1, min(MAX_QUERY_RECORDS, int(limit)))
    items = []
    for e in matched[offset:offset + limit]:
        item = e.model_dump(include=set(QUERY_FIELDS_ANON)) if anon.enabled else e.model_dump(exclude=set(QUERY_EXCLUDE))
        item["layer"] = anon.token("layer", e.layer)
        item["space"] = anon.token("layout", e.space)
        item["block"] = anon.token("block", e.block) if e.block else None
        item["text_style"] = anon.token("style", e.text_style) if e.text_style else None
        item["dim_text_overridden"] = e.dim_text not in (None, "", "<>")
        items.append(item)
    def result():
        next_offset = offset + len(items)
        next_cursor = base64.urlsafe_b64encode(json.dumps({"offset": next_offset, "filter": fingerprint}).encode()).decode() if next_offset < len(matched) else None
        return {"items": items, "next_cursor": next_cursor, "total_matched": len(matched), "records_capped": capped}
    while _bytes(result()) > MAX_QUERY_BYTES and items:
        items.pop()
    if not items and offset < len(matched): raise ToolError("Một đối tượng vượt trần kích thước trang.")
    return result()


# ---------- công cụ đề xuất sửa (A2): chỉ ghi changeset JSON, KHÔNG ghi DXF; áp dụng do người qua CLI ----------

DIFF_MAX_BYTES = 65536
_DEF_KIND = {"layers": "layer", "text_styles": "style", "dim_styles": "dimstyle", "blocks": "block"}
_ATTR_KIND = {"layer": "layer", "style": "style", "dimstyle": "dimstyle", "name": "block", "geometry": "block"}
REDACTED = "…ẩn…"


def _all_names(model):
    """Mọi tên đã biết trong bản vẽ (cho giải mã/scrub): layer, kiểu chữ, kiểu kích thước, khối, layout."""
    names = _names(model)
    names += [("style", s.name) for s in model.styles]
    names += [("dimstyle", d) for d in model.dim_styles]
    names += [("block", b.name) for b in model.blocks if not b.is_layout]
    return names


def _space_token(anon, space: str) -> str:
    if space.startswith("block:"):
        return "block:" + anon.token("block", space[6:])
    return anon.token("layout", space)


def _attr_value(anon, attr, value):
    if not anon.enabled:
        return value
    kind = _ATTR_KIND.get(attr)
    if kind and isinstance(value, str):
        return anon.token(kind, value)
    if isinstance(value, (str, list, tuple, dict)):  # chữ và toạ độ (điểm chèn, đỉnh...) bị che; số vô hướng giữ
        return REDACTED
    return value


def _anon_defs(anon, defs: dict) -> dict:
    return {kind: {key: [anon.token(_DEF_KIND[kind], n) for n in names] for key, names in v.items()} for kind, v in defs.items()}


def _anon_report(anon, rep: dict) -> dict:
    out = {k: v for k, v in rep.items() if k != "details"}
    det = rep.get("details")
    if not det:
        return out
    d = {}
    if "removed_layers" in det:
        d["removed_layers"] = [anon.token("layer", x) for x in det["removed_layers"]]
    if "target" in det:
        d["target"] = anon.token("layer", det["target"])
    if "renamed_layers" in det:
        d["renamed_layers"] = [[anon.token("layer", a), anon.token("layer", b)] for a, b in det["renamed_layers"]]
    if "removed" in det:
        d["removed"] = {kind: [anon.token(_DEF_KIND[kind], n) for n in names] for kind, names in det["removed"].items()}
    out["details"] = d
    return out


@_safe
def propose_changeset(ctx: ToolContext, file: str, ops, standard: str = "design-hygiene-v0",
                      protected_layers: list | None = None) -> dict:
    """Chạy khô các thao tác (từ vựng cố định) và lưu changeset vào thư mục phiên; KHÔNG ghi DXF.

    Tên ẩn danh (L_…, S_…, D_…, B_…, Y_…) trong thao tác được giải mã về tên thật trước khi lưu;
    kết quả xem trước trả về đã ẩn danh. Áp dụng chỉ do người dùng qua `cadguard apply`.
    """
    from ..changeset.apply import ChangesetError, propose
    from ..changeset.ops import OpError, dump_ops, map_names, parse_ops
    from .anonymize import TokenError

    path, model = _model(ctx, file)
    anon = ctx.anonymizer
    names = _all_names(model)
    if protected_layers is not None and (not isinstance(protected_layers, list) or not all(isinstance(x, str) for x in protected_layers)):
        raise ToolError("protected_layers phải là danh sách tên/mã layer.")
    try:
        parsed = parse_ops(ops)
        decode = anon.decoder(names)
        real_ops = [map_names(o, decode) for o in parsed]
        protected = [decode("layer", x) for x in protected_layers or []]
        _standard(ctx, standard)
        cs, pv = propose(ctx.workspace, path.relative_to(ctx.workspace.root).as_posix(), None, ops=real_ops,
                         standard=standard, standards_dir=Path(ctx.standards_dir), profile=ctx.profile,
                         protected_layers=protected, created_by="agent")
    except (OpError, TokenError, ChangesetError) as exc:
        raise ToolError(anon.scrub_text(str(exc), names)) from None
    prot = pv["protection"]
    return {
        "changeset_id": cs.id,
        "file": _file_id(ctx, path),
        "standard": pv["standard"],
        "version": pv["standard_version"],
        "profile": pv["profile"],
        "ops": dump_ops(parsed),
        "protection": {"layers": [anon.token("layer", x) for x in prot["layers"]], "patterns_count": len(prot["patterns"])},
        "ops_report": [_anon_report(anon, r) for r in pv["ops"]],
        "diff": pv["diff"],
        "definitions": _anon_defs(anon, pv["definitions"]),
        "rules": pv["rules"],
        "rules_regressed": pv["rules_regressed"],
        "findings_after": [{**f, "message": anon.scrub_text(f["message"], names)} for f in pv["findings_after"][:max(0, ctx.max_findings)]],
        "checks": [{**c, "message": anon.scrub_text(c["message"], names)} for c in pv["checks"]],
        "ok": pv["ok"],
        "summary_vi": pv["summary_vi"],
        "diff_summary_vi": pv["diff_summary_vi"],
        "apply": "Trợ lý KHÔNG áp dụng được. Người dùng xem trước rồi tự chạy: cadguard apply "
                 f"{cs.id} --workspace <thư mục làm việc>; kết quả ghi ra tệp mới, tệp gốc giữ nguyên.",
    }


@_safe
def diff(ctx: ToolContext, a: str, b: str, max_items: int = 100) -> dict:
    """So hai DXF trong thư mục làm việc theo handle; đã ẩn danh; JSON tối đa 64 KB."""
    from ..changeset.diff import diff_files

    pa, pb = _path(ctx, a), _path(ctx, b)
    max_items = max(1, min(500, int(max_items)))
    d = diff_files(pa, pb, max_items)
    anon = ctx.anonymizer

    def ent(e):
        return {**e, "layer": anon.token("layer", e["layer"]), "space": _space_token(anon, e["space"])}

    changed = []
    for e in d["entities"]["changed"]:
        item = ent(e)
        item["attrs"] = {k: [_attr_value(anon, k, v[0]), _attr_value(anon, k, v[1])] for k, v in e["attrs"].items()}
        changed.append(item)
    out = {
        "a": {"id": _file_id(ctx, pa), "sha256": d["a"]["sha256"]},
        "b": {"id": _file_id(ctx, pb), "sha256": d["b"]["sha256"]},
        "summary": d["summary"],
        "summary_vi": d["summary_vi"],
        "entities": {"added": [ent(e) for e in d["entities"]["added"]], "removed": [ent(e) for e in d["entities"]["removed"]],
                     "changed": changed},
        "definitions": _anon_defs(anon, d["definitions"]),
        "truncated": d["truncated"],
    }
    while _bytes(out) > DIFF_MAX_BYTES:
        lists = [out["entities"][k] for k in ("changed", "added", "removed")]
        lists += [v for kind in out["definitions"].values() for v in kind.values()]
        longest = max(lists, key=len)
        if not longest:
            raise ToolError("Không thể giới hạn kích thước kết quả.")
        longest.pop()
        out["truncated"] = True
    return out


# ---------- Nguồn sự thật duy nhất (Single Source of Truth) cho đặc tả & điều phối công cụ AI ----------

BASELINE_TOOL = "audit_khong_ho_so"

TOOL_SPECS: list[dict] = [
    {
        "name": "list_drawings",
        "description": "Liệt kê các tệp DXF trong thư mục làm việc (đã ẩn danh ở Bậc 1).",
        "schema": {
            "type": "object",
            "properties": {"dir": {"type": "string", "default": "."}},
            "additionalProperties": False,
        },
    },
    {
        "name": "audit",
        "description": "Chạy bộ luật tất định trên một bản vẽ. Luôn dùng kết quả này làm nguồn sự thật về lỗi.",
        "schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Mã tệp (F_xxxx) hoặc đường dẫn tương đối từ list_drawings."},
                "standard": {"type": "string", "default": "furniture-v0",
                             "description": "Tên chuẩn: furniture-v0 hoặc design-hygiene-v0."},
            },
            "required": ["file"],
            "additionalProperties": False,
        },
    },
    {
        "name": "explain_rule",
        "description": "Đọc định nghĩa, mức độ, tham số và mục chuẩn của một mã luật.",
        "schema": {
            "type": "object",
            "properties": {
                "rule_id": {"type": "string", "description": "Mã luật, ví dụ VS-01, LY-01, TX-01."},
                "standard": {"type": "string", "default": "furniture-v0"},
            },
            "required": ["rule_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_model_summary",
        "description": "Tóm tắt bản vẽ: phiên bản DXF, đơn vị, số layer/khối/đối tượng theo loại và không gian, kiểu chữ, layout.",
        "schema": {
            "type": "object",
            "properties": {"file": {"type": "string"}},
            "required": ["file"],
            "additionalProperties": False,
        },
    },
    {
        "name": "query_model",
        "description": "Truy vấn danh sách đối tượng trong bản vẽ theo bộ lọc (layer, type, space) có phân trang.",
        "schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string"},
                "filter": {
                    "type": "object",
                    "description": "Bộ lọc tuỳ chọn: layer, type (LINE/TEXT/MTEXT/INSERT/DIMENSION/…), space.",
                    "properties": {
                        "layer": {"type": "string"},
                        "type": {"type": "string"},
                        "space": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "limit": {"type": "integer", "default": 100},
                "cursor": {"type": ["string", "null"], "default": None},
            },
            "required": ["file"],
            "additionalProperties": False,
        },
    },
    {
        "name": "diff",
        "description": "So sánh hai bản vẽ trong thư mục làm việc theo handle (đối tượng thêm/xoá/đổi).",
        "schema": {
            "type": "object",
            "properties": {
                "a": {"type": "string"},
                "b": {"type": "string"},
                "max_items": {"type": "integer", "default": 100},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
    },
]

PROPOSE_SPEC: dict = {
    "name": "propose_changeset",
    "description": (
        "Chạy khô các thao tác sửa (từ vựng cố định) và lưu changeset để người dùng xem trước; "
        "KHÔNG ghi hay sửa tệp DXF. Không có công cụ apply."
    ),
    "schema": {
        "type": "object",
        "properties": {
            "file": {"type": "string"},
            "ops": {"type": "array", "items": {"type": "object"}},
            "standard": {"type": "string", "default": "design-hygiene-v0"},
            "protected_layers": {"type": ["array", "null"], "items": {"type": "string"}},
        },
        "required": ["file", "ops"],
        "additionalProperties": False,
    },
}

BASELINE_SPEC: dict = {
    "name": BASELINE_TOOL,
    "description": (
        "Chạy bộ luật với chuẩn GỐC (không áp hồ sơ công ty) để so sánh trước/sau hồ sơ."
    ),
    "schema": {
        "type": "object",
        "properties": {
            "file": {"type": "string"},
            "standard": {"type": "string", "default": "furniture-v0"},
        },
        "required": ["file"],
        "additionalProperties": False,
    },
}


def _pick_tool_args(args: dict, allowed: tuple[str, ...], *, required: tuple[str, ...] = ()) -> dict:
    for r in required:
        if r not in args or args[r] is None:
            raise ToolError(f"Thiếu tham số bắt buộc: {r}.")
    unknown = set(args) - set(allowed)
    if unknown:
        raise ToolError(f"Tham số không hợp lệ: {', '.join(sorted(unknown))}.")
    return {k: v for k, v in args.items() if k in allowed and v is not None}


def dispatch_tool(
    ctx: ToolContext,
    name: str,
    arguments: dict | None,
    *,
    default_standard: str | None = None,
    allow_propose: bool = False,
    allow_baseline: bool = False,
    baseline_ctx: ToolContext | None = None,
) -> tuple[str, bool]:
    """Điều phối và thực thi lời gọi công cụ từ LLM (API/CLI/Studio). Trả `(chuỗi_json, là_lỗi)`."""
    if arguments is None or not isinstance(arguments, dict):
        return json.dumps({"error": "Tham số công cụ phải là đối tượng JSON hợp lệ."}, ensure_ascii=False), True
    std_fallback = default_standard or (ctx.profile.standard if ctx.profile else None) or "furniture-v0"
    try:
        if name == "list_drawings":
            kw = _pick_tool_args(arguments, ("dir",))
            res = list_drawings(ctx, **kw)
        elif name == "audit":
            kw = _pick_tool_args(arguments, ("file", "standard"), required=("file",))
            kw.setdefault("standard", std_fallback)
            res = audit(ctx, **kw)
        elif name == BASELINE_TOOL and allow_baseline:
            kw = _pick_tool_args(arguments, ("file", "standard"), required=("file",))
            kw.setdefault("standard", std_fallback)
            bctx = baseline_ctx or ToolContext(
                workspace=ctx.workspace,
                anonymizer=ctx.anonymizer,
                standards_dir=ctx.standards_dir,
                stream_threshold_mb=ctx.stream_threshold_mb,
                max_entity_records=ctx.max_entity_records,
                profile=None,
                ids=ctx.ids,
            )
            res = audit(bctx, **kw)
        elif name == "explain_rule":
            kw = _pick_tool_args(arguments, ("rule_id", "standard"), required=("rule_id",))
            kw.setdefault("standard", std_fallback)
            res = explain_rule(ctx, **kw)
        elif name == "get_model_summary":
            kw = _pick_tool_args(arguments, ("file",), required=("file",))
            res = get_model_summary(ctx, **kw)
        elif name == "query_model":
            kw = _pick_tool_args(arguments, ("file", "filter", "limit", "cursor"), required=("file",))
            kw.setdefault("filter", {})
            res = query_model(ctx, **kw)
        elif name == "diff":
            kw = _pick_tool_args(arguments, ("a", "b", "max_items"), required=("a", "b"))
            res = diff(ctx, **kw)
        elif name == "propose_changeset" and allow_propose:
            kw = _pick_tool_args(arguments, ("file", "ops", "standard", "protected_layers"), required=("file", "ops"))
            kw.setdefault("standard", default_standard or (ctx.profile.standard if ctx.profile else None) or "design-hygiene-v0")
            res = propose_changeset(ctx, **kw)
        else:
            return json.dumps({"error": f"Không có công cụ '{name}'."}, ensure_ascii=False), True
        return json.dumps(res, ensure_ascii=False), False
    except ToolError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False), True
    except Exception:
        return json.dumps({"error": "Không thể thực hiện yêu cầu; hãy kiểm tra dữ liệu và đường dẫn."}, ensure_ascii=False), True


class ToolBox:
    """Hộp công cụ chuẩn hoá cho các engine trợ lý (API trực tiếp, CLI, Studio)."""

    def __init__(
        self,
        workspace: str | Path | Workspace,
        *,
        standard: str | None = None,
        profile: str | Path | CompanyProfile | None = None,
        allow_propose: bool = False,
        compare_without_profile: bool = False,
        anonymize: bool = True,
        stream_threshold_mb: float | None = DEFAULT_STREAM_THRESHOLD_MB,
        max_entity_records: int = DEFAULT_MAX_ENTITY_RECORDS,
        standards_dir: Path | None = None,
    ) -> None:
        from ..standard import load_profile

        ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
        sdir = Path(standards_dir) if standards_dir else find_standards_dir()
        prof = profile if isinstance(profile, CompanyProfile) or profile is None else load_profile(Path(profile))
        anon = Anonymizer(enabled=bool(anonymize))
        self.standard = standard
        self.allow_propose = bool(allow_propose)
        self.compare = bool(prof is not None and compare_without_profile)
        self.ctx = ToolContext(
            workspace=ws,
            anonymizer=anon,
            standards_dir=sdir,
            stream_threshold_mb=stream_threshold_mb,
            max_entity_records=max_entity_records,
            profile=prof,
        )
        self._baseline_ctx = (
            ToolContext(
                workspace=ws,
                anonymizer=anon,
                standards_dir=sdir,
                stream_threshold_mb=stream_threshold_mb,
                max_entity_records=max_entity_records,
                profile=None,
                ids=self.ctx.ids,
            )
            if self.compare
            else None
        )

    def specs(self) -> list[dict]:
        out = list(TOOL_SPECS)
        if self.compare:
            out.append(BASELINE_SPEC)
        if self.allow_propose:
            out.append(PROPOSE_SPEC)
        return out

    def call(self, name: str, arguments: dict | None) -> tuple[str, bool]:
        return dispatch_tool(
            self.ctx,
            name,
            arguments,
            default_standard=self.standard,
            allow_propose=self.allow_propose,
            allow_baseline=self.compare,
            baseline_ctx=self._baseline_ctx,
        )

