"""Công cụ trợ lý cho cảnh 3D `cg.scene/2` và công thái học (khai báo ở `registry.py`).

Chế độ ẩn danh (Bậc 1): KHÔNG trả toạ độ (vị trí x/y của khối, đầu mút tường), mã hạng mục (lấy từ số bản vẽ trong khung
tên) thành mã phiên, lời nhắn phần thiếu bỏ đi (chỉ còn loại và mã). Chỉ còn kích thước vô hướng (rộng/sâu/cao/cao độ),
nguồn số liệu, số đo ER-xx và handle (như kết quả `audit`). Tắt ẩn danh thì trả thêm toạ độ.
"""

from __future__ import annotations

from .tools import ToolContext, ToolError, _file_id, _model, _safe

MAX_MODULES = 200


def _scene(ctx: ToolContext, file: str, item: str | None):
    from ..scene.assemble import best_item, build_item_scene
    from ..scene.views2d import read_drawing
    from ..app.scene_api import read_supplement

    path, model = _model(ctx, file)
    d = read_drawing(model)
    anon = ctx.anonymizer
    groups = {anon.token("item", g): g for g in d.groups} | {g: g for g in d.groups}
    g = groups.get(item) if item else best_item(d)
    if g is None:
        raise ToolError("Không có hạng mục này (dùng get_scene không truyền item để xem danh sách).")
    sc = build_item_scene(d, g, read_supplement(ctx.workspace.root, model.file_hash))
    sc.source_hash = model.file_hash
    sc.scene_hash = sc.compute_hash()
    return path, d, sc, g


def _box(sc, eid: str):
    from ..scene.geometry import _seg_base

    for m in sc.modules:
        if m.id == eid:
            return (m.x, m.y, m.z0, m.x + m.w, m.y + m.d, m.z0 + m.h)
        for f in m.fronts:
            if f.id == eid:
                return (f.x0, m.y - 18.0, f.z0, f.x1, m.y, f.z1)
    for w in sc.walls:
        if w.id == eid:
            b = _seg_base(w.start, w.end, w.thickness, w.side)
            xs, ys = [p[0] for p in b], [p[1] for p in b]
            return (min(xs), min(ys), 0.0, max(xs), max(ys), w.height)
    return None


@_safe
def get_scene(ctx: ToolContext, file: str, item: str | None = None) -> dict:
    from ..scene.assemble import item_summary

    path, d, sc, g = _scene(ctx, file, item)
    anon = ctx.anonymizer
    raw = not anon.enabled
    mods = []
    for m in sc.modules[:MAX_MODULES]:
        x = {"id": m.id, "kind": m.kind, "w": m.w, "d": m.d, "h": m.h, "z0": m.z0, "fronts": len(m.fronts),
             "doors": sum(1 for f in m.fronts if f.kind == "door"), "drawers": sum(1 for f in m.fronts if f.kind == "drawer"),
             "shelves": m.shelves, "src": {k: v.kind for k, v in m.src.items()}, "front_ids": [f.id for f in m.fronts]}
        if raw:
            x |= {"x": m.x, "y": m.y, "label": m.label}
        mods.append(x)
    walls = [{"id": w.id, "thickness": w.thickness, "height": w.height, "src": {k: v.kind for k, v in w.src.items()},
              **({"start": list(w.start), "end": list(w.end)} if raw else {})} for w in sc.walls]
    return {"schema": "cg.scene/2", "file": _file_id(ctx, path), "item": anon.token("item", g), "scene_hash": sc.scene_hash,
            "items": [{**x, "id": anon.token("item", x["id"])} for x in item_summary(d)],
            "room": {"ceiling": sc.room.ceiling, "ceiling_src": sc.room.src["ceiling"].kind if "ceiling" in sc.room.src else None},
            "modules": mods, "walls": walls, "truncated": len(sc.modules) > MAX_MODULES,
            "gaps": [{"id": x.id, "kind": x.kind, **({"message": x.message} if raw else {})} for x in sc.gaps],
            "links": [{"elevation": lk.elevation, "plan": lk.plan, "method": lk.method} for lk in sc.links]}


@_safe
def measure(ctx: ToolContext, file: str, a: str, b: str, item: str | None = None) -> dict:
    """Khe hở giữa hai phần tử của cảnh theo từng trục (mm; âm = chồng nhau) và khoảng cách nhỏ nhất."""
    _path, _d, sc, _g = _scene(ctx, file, item)
    ba, bb = _box(sc, a), _box(sc, b)
    if ba is None or bb is None:
        raise ToolError("Không có phần tử này trong cảnh (dùng mã khối/cánh/tường từ get_scene).")
    gaps = [max(bb[i] - ba[i + 3], ba[i] - bb[i + 3]) for i in range(3)]
    dist = sum(max(0.0, g) ** 2 for g in gaps) ** 0.5
    return {"a": a, "b": b, "unit": "mm", "gap_x": round(gaps[0], 1), "gap_y": round(gaps[1], 1), "gap_z": round(gaps[2], 1),
            "distance": round(dist, 1), "overlap": all(g < 0 for g in gaps), "scene_hash": sc.scene_hash}


@_safe
def list_ergonomic_checks(ctx: ToolContext, file: str, item: str | None = None) -> dict:
    from ..ergonomics import check, load_ergonomics

    _path, _d, sc, g = _scene(ctx, file, item)
    r = check(sc, load_ergonomics(ctx.standards_dir))
    return {**r, "item": ctx.anonymizer.token("item", g)}


__all__ = ["get_scene", "list_ergonomic_checks", "measure"]


@_safe
def get_drawing_graph(ctx: ToolContext, file: str) -> dict:
    """Đồ thị tri thức bản vẽ cg.drawing-graph/1 (P1/P2): tóm tắt, cổng sẵn sàng, hạng mục. Ẩn danh: chỉ số đếm, loại,
    mã phiên; KHÔNG tên tờ/hình/hạng mục, chữ ghi chú, tên vật liệu tự do hay lời giải thích có tên."""
    from ..app.scene_api import read_supplement
    from ..graph import build_graph
    from ..graph_ai import load_overrides

    path, model = _model(ctx, file)
    root = ctx.workspace.root
    g = build_graph(model, supplement=read_supplement(root, model.file_hash), overrides=load_overrides(root, model.file_hash))
    anon = ctx.anonymizer
    out = {"schema": g["schema"], "file": _file_id(ctx, path), "stats": g["stats"]}
    if anon.enabled:
        out["gates"] = [{"id": x["id"], "status": x["status"], "done": x["done"], "total": x["total"],
                         "tasks": [{"title": t["title"], "severity": t["severity"]} for t in x["tasks"][:30]]}
                        for x in g["gates"]]
        out["items"] = [{"id": anon.token("item", r["id"]), "sheets": r["sheets"], "plans": r["plans"],
                         "elevations": r["elevations"], "sections": r["sections"], "modules": r["modules"],
                         "gaps": r["gaps"], "materials": len(r["materials"]), "status": r["status"]} for r in g["items"]]
        return out
    out["gates"] = [{k: x[k] for k in ("id", "title", "status", "done", "total", "note")} |
                    {"tasks": [{k: t[k] for k in ("title", "where", "why", "fix_here", "fix_cad", "severity")}
                               for t in x["tasks"][:30]]} for x in g["gates"]]
    out["items"] = g["items"]
    out["materials"] = [{"name": n["label"], "mentions": n["attrs"].get("mentions", 0), "status": n["status"]}
                        for n in g["nodes"] if n["type"] == "material"]
    return out
