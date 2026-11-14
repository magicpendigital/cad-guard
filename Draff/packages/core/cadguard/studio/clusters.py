"""Gom hình học thành các cụm theo vị trí (tất định) và dựng bản tóm tắt bản vẽ để đưa cho LLM.

Cụm là cách LLM chỉ vào "một nhóm nét vẽ" mà không cần layer đúng quy ước: LLM nói "C1 là mặt đứng",
mã tra ngược ra danh sách đối tượng.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..model import DrawingModel, EntityRec
from ..scene.views import _rects

GAP_MM = 150.0
MAX_RECTS = 200
MAX_TEXTS = 120


@dataclass
class Cluster:
    id: str
    bbox: tuple[float, float, float, float]
    entities: list[EntityRec] = field(default_factory=list)


def _ebox(e: EntityRec):
    if not e.pts:
        return None
    r = e.radius or 0.0
    xs, ys = [p[0] for p in e.pts], [p[1] for p in e.pts]
    return min(xs) - r, min(ys) - r, max(xs) + r, max(ys) + r


def clusters_of(model: DrawingModel) -> list[Cluster]:
    items = [(e, b) for e in model.entities if e.space == "Model" and (b := _ebox(e))]
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    # Hợp nhất theo hộp bao nở GAP_MM. Quét theo trục x để tránh O(n^2) khi bản vẽ lớn.
    order = sorted(range(len(items)), key=lambda i: items[i][1][0])
    active: list[int] = []
    for i in order:
        x0 = items[i][1][0]
        active = [j for j in active if items[j][1][2] + GAP_MM >= x0]
        for j in active:
            a, b = items[i][1], items[j][1]
            if a[0] <= b[2] + GAP_MM and b[0] <= a[2] + GAP_MM and a[1] <= b[3] + GAP_MM and b[1] <= a[3] + GAP_MM:
                parent[find(i)] = find(j)
        active.append(i)

    groups: dict[int, list[int]] = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(i)
    out: list[Cluster] = []
    for idxs in groups.values():
        bs = [items[i][1] for i in idxs]
        out.append(Cluster("", (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)), [items[i][0] for i in idxs]))
    out.sort(key=lambda c: (round(c.bbox[1] / GAP_MM), c.bbox[0]))
    for n, c in enumerate(out, 1):
        c.id = f"C{n}"
    return out


def _r1(v: float) -> float:
    return round(float(v), 1)


def digest(model: DrawingModel, scene=None, cl: list[Cluster] | None = None) -> dict:
    """Bản tóm tắt có cấu trúc, không chứa đường dẫn hay tên tệp. LLM được xem toàn bộ nội dung bản vẽ (quyết định 05/11/2026)."""
    cl = cl if cl is not None else clusters_of(model)
    layer_counts: dict[str, int] = {}
    for e in model.entities:
        layer_counts[e.layer] = layer_counts.get(e.layer, 0) + 1
    out: dict = {
        "units": "mm" if model.insunits == 4 else f"INSUNITS={model.insunits}",
        "layers": [{"name": k, "count": v} for k, v in sorted(layer_counts.items())],
        "clusters": [],
        "inserts": [],
    }
    for c in cl:
        texts = []
        for e in model.entities:
            if e.text and e.pos and c.bbox[0] - GAP_MM <= e.pos[0] <= c.bbox[2] + GAP_MM and c.bbox[1] - GAP_MM <= e.pos[1] <= c.bbox[3] + GAP_MM:
                texts.append({"h": e.handle, "text": e.text, "at": [_r1(e.pos[0]), _r1(e.pos[1])]})
        out["clusters"].append(
            {
                "id": c.id,
                "bbox": [_r1(v) for v in c.bbox],
                "size": [_r1(c.bbox[2] - c.bbox[0]), _r1(c.bbox[3] - c.bbox[1])],
                "entities": len(c.entities),
                "layers": sorted({e.layer for e in c.entities}),
                "rects": [{"h": h, "x": [_r1(a), _r1(cx)], "y": [_r1(b), _r1(d)]} for a, b, cx, d, h in _rects(c.entities)[:MAX_RECTS]],
                "texts": texts[:MAX_TEXTS],
                "dims": [e.dim_value for e in c.entities if e.dim_value is not None][:MAX_TEXTS],
            }
        )
    for e in model.entities:
        if e.type == "INSERT" and e.space == "Model":
            out["inserts"].append({"h": e.handle, "block": e.block, "at": list(e.insert or ()), "rot": e.rotation, "attribs": e.attribs or {}})
    out["inserts"] = out["inserts"][:300]
    if scene is not None:
        out["scene"] = {
            "walls": len(scene.walls),
            "modules": len(scene.modules),
            "panels": [{"id": p.id, "x": [_r1(p.x0), _r1(p.x1)], "y": [_r1(p.y0), _r1(p.y1)], "z": [_r1(p.z0), _r1(p.z1)], "source": p.source} for p in scene.panels],
            "gaps": [{"id": g.id, "kind": g.kind, "message": g.message, "fields": [f.key for f in g.fields]} for g in scene.gaps],
            "skipped": [{"h": s.handle, "reason": s.reason} for s in scene.skipped],
        }
    return out
