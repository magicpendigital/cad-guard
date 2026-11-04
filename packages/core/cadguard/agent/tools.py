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

from ..dxf_reader import read_dxf
from ..runner import audit_model
from ..standard import find_standards_dir, load_standard
from .anonymize import Anonymizer
from .workspace import Workspace

MAX_QUERY_RECORDS = 500
MAX_QUERY_BYTES = 65536


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
def _cached_model(path: Path, mtime: int, size: int):
    return read_dxf(path)


def load_model(path: Path):
    """Đọc DXF với bộ nhớ đệm nhỏ theo thời gian sửa và kích thước."""
    try:
        path = Path(path)
        stat = path.stat()
        return _cached_model(path, stat.st_mtime_ns, stat.st_size)
    except Exception:
        raise ToolError("Không thể đọc bản vẽ DXF.") from None


def _path(ctx, file):
    return ctx.workspace.resolve(ctx.ids.get(file, file))


def _file_id(ctx, path):
    rel = path.relative_to(ctx.workspace.root).as_posix()
    ident = ctx.anonymizer.token("file", rel)
    ctx.ids[ident] = rel
    return ident


def _model(ctx, file):
    path = _path(ctx, file)
    return path, load_model(path)


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
    return load_standard(name, root)


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
    return {"file": _file_id(ctx, path), "standard": std.name, "version": std.version, "counts": counts, "rules_run": result.rules_run, "skipped": skipped, "findings": findings, "truncated": len(result.findings) > max(0, ctx.max_findings)}


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
    return {**spec.model_dump(include={"id", "title", "severity", "kind", "false_positive_risk", "source", "reads", "implemented"}), "params": params, "description_md": description, "examples": {"good": [], "bad": []}}


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
    result = {"layer_count": len(model.layers), "block_count": len(blocks), "entities_by_type": dict(types.most_common(limit)), "entities_by_space": dict(spaces.most_common(limit)), "layouts": layouts[:limit], "text_styles": dict(styles.most_common(limit)), "insunits": model.insunits, "dxf_version": model.dxf_version, "truncated": any(len(x) > limit for x in (types, spaces, styles, layouts))}
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
        item = e.model_dump(exclude={"attribs", "dim_text", "dup_key"})
        item["layer"] = anon.token("layer", e.layer)
        item["space"] = anon.token("layout", e.space)
        item["block"] = anon.token("block", e.block) if e.block else None
        item["text_style"] = anon.token("style", e.text_style) if e.text_style else None
        item["dim_text_overridden"] = e.dim_text not in (None, "", "<>")
        items.append(item)
    def result():
        next_offset = offset + len(items)
        next_cursor = base64.urlsafe_b64encode(json.dumps({"offset": next_offset, "filter": fingerprint}).encode()).decode() if next_offset < len(matched) else None
        return {"items": items, "next_cursor": next_cursor, "total_matched": len(matched)}
    while _bytes(result()) > MAX_QUERY_BYTES and items:
        items.pop()
    if not items and offset < len(matched): raise ToolError("Một đối tượng vượt trần kích thước trang.")
    return result()
