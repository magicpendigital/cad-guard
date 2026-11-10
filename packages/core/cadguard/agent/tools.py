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

from ..limits import DEFAULT_MAX_ENTITY_RECORDS, DEFAULT_STREAM_THRESHOLD_MB
from ..contracts import audit_report
from ..standard import CompanyProfile, find_standards_dir, load_standard
from .anonymize import Anonymizer
from .workspace import Workspace

from .registry import MAX_QUERY_BYTES, MAX_QUERY_RECORDS  # một nguồn với mô tả công cụ
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
    from ..reader_select import read_with

    # Khoá đệm gồm bộ đọc và trần bản ghi: ezdxf và stream (hoặc hai trần khác nhau) không dùng chung mục.
    if reader == "stream":
        return read_with(path, "stream", max_entity_records)
    return read_with(path, "ezdxf")


def load_model(path: Path, stream_threshold_mb: float | None = None, max_entity_records: int = DEFAULT_MAX_ENTITY_RECORDS):
    """Đọc DXF với bộ nhớ đệm nhỏ theo thời gian sửa, kích thước, bộ đọc và trần bản ghi.

    Bộ đọc chọn bằng `reader_select.choose_reader` (như `cadguard audit --reader auto`):
    `stream_threshold_mb` None/âm = luôn ezdxf, 0 = luôn theo dòng, dương = theo dòng khi tệp >= ngưỡng MiB.
    """
    from ..reader_select import choose_reader  # nạp lười: ezdxf chỉ khi đọc bản vẽ thật

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
    from ..rule_config import effective_standard

    return effective_standard(name, root, profile=profile, workspace=ctx.workspace.root)


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
    rep = audit_report(model, std)  # hợp đồng cg.audit/1 dùng chung với CLI/App; ở đây chỉ ẩn danh và cắt bớt
    names = _names(model)
    anon = ctx.anonymizer
    limit = max(0, ctx.max_findings)
    findings = [{"rule_id": f.rule_id, "severity": f.severity, "message": anon.scrub_text(f.message, names),
                 "layout": anon.token("layout", f.layout) if f.layout else None,
                 "layer": anon.token("layer", f.layer) if f.layer else None, "count": f.count, "handles": f.handles,
                 "fix_ops": f.fix_ops}  # không có bbox: toạ độ ngoài Bậc 1
                for f in rep.findings[:limit]]
    skipped = [{"rule_id": s.rule_id, "reason": s.reason if s.internal_error else anon.scrub_text(s.reason, names)}
               for s in rep.skipped]
    return {"schema": rep.schema_id, "file": _file_id(ctx, path), "standard": rep.standard, "version": rep.version,
            "profile": std.profile, "counts": rep.counts, "rules_run": rep.rules_run, "skipped": skipped,
            "findings": findings, "fixable_rules": rep.fixable_rules, "truncated": len(rep.findings) > limit,
            "records_capped": rep.records_capped}


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


@_safe
def show_in_autocad(ctx: ToolContext, file: str, handles=None, layers=None) -> dict:
    """M3: đưa AutoCAD tới đối tượng (chỉ điều hướng). Mã layer L_… được giải mã về tên thật trước khi gửi; kết quả
    trả trợ lý chỉ có số đếm và câu báo chung (không tên bản vẽ/layer)."""
    from ..autocad.bridge import BridgeError, show
    from .anonymize import TokenError

    path = _path(ctx, file)
    real_layers = None
    if layers:
        _, model = _model(ctx, file)
        decode = ctx.anonymizer.decoder(_all_names(model))
        try:
            real_layers = [decode("layer", x) for x in layers]
        except TokenError as exc:
            raise ToolError(str(exc)) from None
    try:
        r = show(ctx.workspace.root, path.relative_to(ctx.workspace.root).as_posix(), handles, real_layers)
    except BridgeError as exc:
        raise ToolError(str(exc)) from None
    return {"file": _file_id(ctx, path), "sent": r["sent"], "handles": r["handles"], "layers": r["layers"],
            "truncated": r["truncated"], "message": r["message"],
            "fallback": "Người dùng gõ CGDEN trong AutoCAD (đã nạp cadguard.lsp) để tới đối tượng."}


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
def propose_translation(ctx: ToolContext, file: str, to: str, translations: list | None = None) -> dict:
    """Dịch bản vẽ do TRỢ LÝ làm người dịch, code kiểm. Bước 1 (không `translations`): trả chuỗi cần dịch (có ký hiệu
    giữ chỗ ⟦n⟧ cho số/đơn vị/mã) + gợi ý thuật ngữ. Bước 2: nhận [{source, text}], kiểm giữ chỗ/thuật ngữ, đề xuất
    changeset (không áp dụng). Bị khoá khi dự án bật ẩn danh."""
    from ..changeset.apply import ChangesetError, propose
    from ..changeset.ops import OpError, parse_ops
    from ..translate import TARGETS, DictBackend, TranslateError, build, glossary_hits, load_glossary

    if ctx.anonymizer.enabled:
        raise ToolError("Dự án đang bật ẩn danh (NDA): chức năng dịch bị khoá.")
    if to not in TARGETS:
        raise ToolError("Ngôn ngữ đích phải là 'en' hoặc 'zh'.")
    path = _path(ctx, file)
    try:
        if not translations:
            res = build(path, to, workspace=ctx.workspace.root, backend=None, update_tm=False)
            rep = res["report"]
            src = rep["source_language"]["language"] or "vi"
            glossary = load_glossary(ctx.workspace.root)
            pending = {}
            for r in rep["rows"]:
                if r["from"] == "" and r["masked"] and r["masked"] not in pending:
                    pending[r["masked"]] = sorted({f"{g[src]} = {g[to]}" for g in glossary_hits(r["source"], glossary, src)
                                                   if g.get(to)})
            items = [{"source": k, "glossary": v} for k, v in list(pending.items())[:300]]
            return {"step": 1, "source_language": rep["source_language"], "target": to, "strings": rep["strings"],
                    "already": rep["translated"], "to_translate": len(pending), "items": items,
                    "truncated": len(pending) > 300,
                    "next": "Gọi lại propose_translation với translations = [{source, text}] (giữ nguyên mọi ⟦n⟧)."}
        if not isinstance(translations, list) or not all(isinstance(x, dict) and isinstance(x.get("source"), str)
                                                          and isinstance(x.get("text"), str) for x in translations):
            raise ToolError("translations phải là danh sách {source, text}.")
        backend = DictBackend({x["source"]: x["text"] for x in translations})
        res = build(path, to, workspace=ctx.workspace.root, backend=backend)
        rep = res["report"]
        if not res["ops"]:
            return {"step": 2, "changeset_id": None, "report": {k: rep[k] for k in ("translated", "untranslated", "issue_count")}}
        cs, pv = propose(ctx.workspace, path.relative_to(ctx.workspace.root).as_posix(), None, ops=parse_ops(res["ops"]),
                         standard="design-hygiene-v0", standards_dir=Path(ctx.standards_dir), profile=ctx.profile,
                         created_by="agent", output_tag=to)
    except (TranslateError, OpError, ChangesetError) as exc:
        raise ToolError(str(exc)) from None
    return {"step": 2, "changeset_id": cs.id, "ok": pv["ok"], "summary_vi": pv["summary_vi"],
            "report": {k: rep[k] for k in ("source_language", "strings", "translated", "untranslated", "issue_count", "by_source")},
            "issues": rep["issues"][:50],
            "apply": f"Trợ lý KHÔNG áp dụng được. Người dùng xem trước rồi chạy: cadguard apply {cs.id} --workspace <thư mục>; "
                     f"ra tệp mới <tên>.{to}.dxf."}


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
