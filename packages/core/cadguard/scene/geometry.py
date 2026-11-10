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


FRONT_MM = 18.0


def _seg_base(a, b, t, side):
    """Đáy hộp tường từ đoạn a-b: side 0 = đoạn là đường tim; +1/-1 = đoạn là mặt tường, dày về pháp tuyến trái/phải."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / n, dx / n
    lo, hi = (-t / 2, t / 2) if side == 0 else ((0.0, t) if side > 0 else (-t, 0.0))
    return ((a[0] + nx * lo, a[1] + ny * lo), (b[0] + nx * lo, b[1] + ny * lo), (b[0] + nx * hi, b[1] + ny * hi), (a[0] + nx * hi, a[1] + ny * hi))


def _norm(base):
    """Đáy ngược chiều kim đồng hồ (để pháp tuyến mặt bên hướng ra ngoài)."""
    area = sum(base[i][0] * base[(i + 1) % len(base)][1] - base[(i + 1) % len(base)][0] * base[i][1] for i in range(len(base)))
    return tuple(reversed(base)) if area < 0 else tuple(base)


def boxes2(scene, ceiling: bool = True) -> list[Box]:
    """Cảnh `cg.scene/2` -> hộp: sàn, trần (tuỳ chọn), tường, thân tủ, cánh (dày 18 mm trước mặt tủ)."""
    out: list[Box] = []
    if scene.room.floor:
        out.append(Box("floor", "floor", "floor", _norm(tuple(scene.room.floor)), -SLAB, 0.0))
        if ceiling and scene.room.ceiling:
            out.append(Box("ceiling", "ceiling", "ceiling", _norm(tuple(scene.room.floor)), scene.room.ceiling, scene.room.ceiling + SLAB))
    for w in scene.walls:
        if w.start != w.end:
            out.append(Box(w.id, "wall", "wall", _norm(_seg_base(w.start, w.end, w.thickness, w.side)), 0.0, w.height))
    for m in scene.modules:
        base = ((m.x, m.y), (m.x + m.w, m.y), (m.x + m.w, m.y + m.d), (m.x, m.y + m.d))
        out.append(Box(m.id, "module", f"module-{m.kind}", base, m.z0, m.z0 + m.h))
        for f in m.fronts:
            fb = ((f.x0, m.y - FRONT_MM), (f.x1, m.y - FRONT_MM), (f.x1, m.y), (f.x0, m.y))
            out.append(Box(f.id, "front", f"front-{f.kind}", fb, f.z0, f.z1))
    return out


SLAB = 20.0
