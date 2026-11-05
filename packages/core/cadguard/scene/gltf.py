"""Ghi cảnh ra GLB (glTF 2.0 nhị phân) bằng thư viện chuẩn; không phụ thuộc gói 3D nào.

Đổi trục: CAD (x, y, z mm, Z lên) -> glTF (x, z, -y) đơn vị mét (Y lên). Phép quay, không đổi chiều mặt.
"""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

from .build import Scene
from .geometry import Box, boxes

PALETTE = [
    (0.86, 0.72, 0.52),
    (0.55, 0.70, 0.62),
    (0.62, 0.66, 0.82),
    (0.82, 0.60, 0.60),
    (0.78, 0.78, 0.60),
    (0.70, 0.60, 0.78),
]
FIXED = {"wall": (0.93, 0.93, 0.91), "floor": (0.60, 0.58, 0.55), "default": (0.80, 0.80, 0.80)}


def color_for(material: str) -> tuple[float, float, float]:
    if material in FIXED:
        return FIXED[material]
    h = int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:8], 16)
    return PALETTE[h % len(PALETTE)]


def _to_gl(x: float, y: float, z: float) -> tuple[float, float, float]:
    return (x / 1000.0, z / 1000.0, -y / 1000.0)


def box_faces(b: Box) -> list[tuple[list[tuple[float, float, float]], tuple[float, float, float]]]:
    """Trả về các mặt (4 đỉnh CAD, pháp tuyến CAD) theo thứ tự ngược chiều kim đồng hồ nhìn từ ngoài."""
    base = list(b.base)
    faces = [([(x, y, b.z1) for x, y in base], (0.0, 0.0, 1.0)), ([(x, y, b.z0) for x, y in reversed(base)], (0.0, 0.0, -1.0))]
    n = len(base)
    for i in range(n):
        (px, py), (qx, qy) = base[i], base[(i + 1) % n]
        ex, ey = qx - px, qy - py
        ln = (ex * ex + ey * ey) ** 0.5 or 1.0
        faces.append(([(px, py, b.z0), (qx, qy, b.z0), (qx, qy, b.z1), (px, py, b.z1)], (ey / ln, -ex / ln, 0.0)))
    return faces


def build_glb(scene: Scene) -> bytes:
    groups: dict[str, list[Box]] = {}
    for b in boxes(scene):
        groups.setdefault(b.material, []).append(b)

    bin_parts: list[bytes] = []
    views, accessors, meshes, materials, nodes = [], [], [], [], []
    offset = 0

    def add_view(data: bytes, target: int) -> int:
        nonlocal offset
        pad = (-len(data)) % 4
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(data), "target": target})
        bin_parts.append(data + b"\0" * pad)
        offset += len(data) + pad
        return len(views) - 1

    for mat, group in sorted(groups.items()):
        pos: list[float] = []
        nor: list[float] = []
        idx: list[int] = []
        for b in group:
            for verts, nrm in box_faces(b):
                start = len(pos) // 3
                gn = _to_gl(nrm[0] * 1000, nrm[1] * 1000, nrm[2] * 1000)
                for v in verts:
                    pos.extend(_to_gl(*v))
                    nor.extend((gn[0] / 1000, gn[1] / 1000, gn[2] / 1000))
                idx.extend((start, start + 1, start + 2, start, start + 2, start + 3))
        count = len(pos) // 3
        mins = [min(pos[i::3]) for i in range(3)]
        maxs = [max(pos[i::3]) for i in range(3)]
        vp = add_view(struct.pack(f"<{len(pos)}f", *pos), 34962)
        vn = add_view(struct.pack(f"<{len(nor)}f", *nor), 34962)
        vi = add_view(struct.pack(f"<{len(idx)}I", *idx), 34963)
        a0 = len(accessors)
        accessors.append({"bufferView": vp, "componentType": 5126, "count": count, "type": "VEC3", "min": mins, "max": maxs})
        accessors.append({"bufferView": vn, "componentType": 5126, "count": count, "type": "VEC3"})
        accessors.append({"bufferView": vi, "componentType": 5125, "count": len(idx), "type": "SCALAR"})
        r, g, bl = color_for(mat)
        materials.append({"name": mat, "pbrMetallicRoughness": {"baseColorFactor": [r, g, bl, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.9}})
        meshes.append({"name": mat, "primitives": [{"attributes": {"POSITION": a0, "NORMAL": a0 + 1}, "indices": a0 + 2, "material": len(materials) - 1}]})
        nodes.append({"mesh": len(meshes) - 1, "name": mat})

    doc = {
        "asset": {"version": "2.0", "generator": "cadguard cg.scene/1"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": offset}],
    }
    js = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    js += b" " * ((-len(js)) % 4)
    blob = b"".join(bin_parts)
    total = 12 + 8 + len(js) + 8 + len(blob)
    return b"glTF" + struct.pack("<II", 2, total) + struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(blob), b"BIN\0") + blob


def write_glb(scene: Scene, path: str | Path) -> Path:
    p = Path(path)
    p.write_bytes(build_glb(scene))
    return p
