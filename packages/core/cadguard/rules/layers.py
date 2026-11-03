"""Layer (LY-*)."""

from __future__ import annotations

import re
from collections import defaultdict

from ..model import DrawingModel
from . import Ctx, Finding, Skip, rule, sample

RESERVED_DEFAULT = ["0", "DEFPOINTS"]


def _is_xref_layer(name: str) -> bool:
    return "|" in name  # layer phụ thuộc xref: không kiểm


@rule("LY-01")
def ly01(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    pattern = ctx.globals.get("layer_pattern")
    if not pattern:
        raise Skip("chuẩn chưa khai báo layer_pattern")
    patterns = [re.compile(pattern)] + [re.compile(p) for p in ctx.globals.get("layer_extra_patterns", [])]
    reserved = {s.upper() for s in ctx.globals.get("layer_reserved", RESERVED_DEFAULT)}
    out = []
    for layer in model.layers:
        n = layer.name
        if n.upper() in reserved or _is_xref_layer(n):
            continue
        if not any(p.match(n) for p in patterns):
            out.append(Finding("LY-01", f"Tên layer '{n}' không theo sơ đồ đặt tên chuẩn", layer=n))
    return out


@rule("LY-03")
def ly03(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    by_space: dict[str, list[str]] = defaultdict(list)
    for e in model.entities:
        if e.layer == "0" and e.type != "INSERT":
            by_space[e.space].append(e.handle)
    return [
        Finding("LY-03", f"{len(hs)} đối tượng nằm trên layer 0 ({sp})", layer="0", layout=None if sp == "Model" else sp, count=len(hs), handles=sample(hs))
        for sp, hs in by_space.items()
    ]


@rule("LY-04")
def ly04(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    table = {la.name.upper(): la for la in model.layers}
    undefined: dict[str, list[str]] = defaultdict(list)
    frozen: dict[str, list[str]] = defaultdict(list)
    for e in model.entities:
        la = table.get(e.layer.upper())
        if la is None:
            undefined[e.layer].append(e.handle)
        elif la.frozen:
            frozen[e.layer].append(e.handle)
    out = [Finding("LY-04", f"{len(hs)} đối tượng nằm trên layer chưa định nghĩa '{n}'", layer=n, count=len(hs), handles=sample(hs)) for n, hs in undefined.items()]
    out += [Finding("LY-04", f"{len(hs)} đối tượng nằm trên layer đang đóng băng '{n}'", layer=n, count=len(hs), handles=sample(hs)) for n, hs in frozen.items()]
    return out


@rule("LY-08")
def ly08(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    names = {s.upper() for s in ctx.globals.get("not_plotted_layers", ["FN-VPRT"])}
    return [
        Finding("LY-08", f"Layer '{la.name}' phải đặt không in nhưng đang được in", layer=la.name)
        for la in model.layers
        if la.name.upper() in names and la.plot
    ]


@rule("LY-09")
def ly09(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    used = {e.layer.upper() for e in model.entities} | {n.upper() for n in model.block_layers}
    reserved = {s.upper() for s in ctx.globals.get("layer_reserved", RESERVED_DEFAULT)}
    return [
        Finding("LY-09", f"Layer '{la.name}' không có đối tượng nào", layer=la.name)
        for la in model.layers
        if la.name.upper() not in used and la.name.upper() not in reserved and not _is_xref_layer(la.name)
    ]
