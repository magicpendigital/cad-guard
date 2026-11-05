"""Cảnh -> danh sách khối hộp (đơn vị mm, trục Z hướng lên). Dùng chung cho glTF và trình xem."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .build import Scene


@dataclass(frozen=True)
class Box:
    name: str  # mã tay cầm (handle) hoặc "floor"
    kind: str  # wall | module | floor
    material: str
    base: tuple[tuple[float, float], ...]  # 4 góc đáy, ngược chiều kim đồng hồ
    z0: float
    z1: float


def _wall_base(a, b, t):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    ox, oy = -dy / n * t / 2, dx / n * t / 2
    return ((a[0] - ox, a[1] - oy), (b[0] - ox, b[1] - oy), (b[0] + ox, b[1] + oy), (a[0] + ox, a[1] + oy))


def _module_base(m):
    c, s = math.cos(math.radians(m.rotation)), math.sin(math.radians(m.rotation))
    pts = ((0, 0), (m.w, 0), (m.w, m.d), (0, m.d))
    return tuple((m.x + px * c - py * s, m.y + px * s + py * c) for px, py in pts)


def boxes(scene: Scene, floor: bool = True) -> list[Box]:
    out: list[Box] = []
    for w in scene.walls:
        if w.start != w.end:
            out.append(Box(w.handle, "wall", "wall", _wall_base(w.start, w.end, w.thickness), 0.0, w.height))
    for m in scene.modules:
        out.append(Box(m.handle, "module", m.material or "default", _module_base(m), 0.0, m.h))
    for pn in scene.panels:
        base = ((pn.x0, pn.y0), (pn.x1, pn.y0), (pn.x1, pn.y1), (pn.x0, pn.y1))
        out.append(Box(pn.id, "panel", "panel", base, pn.z0, pn.z1))
    if floor and out:
        xs = [p[0] for b in out for p in b.base]
        ys = [p[1] for b in out for p in b.base]
        x0, x1, y0, y1 = min(xs) - 200, max(xs) + 200, min(ys) - 200, max(ys) + 200
        out.insert(0, Box("floor", "floor", "floor", ((x0, y0), (x1, y0), (x1, y1), (x0, y1)), -20.0, 0.0))
    return out
