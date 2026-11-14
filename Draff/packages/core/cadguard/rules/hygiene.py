"""Vệ sinh bản vẽ (VS-*) của chuẩn `design-hygiene-v0` — khâu Thiết kế/Kỹ thuật.

Mọi ngưỡng là tham số của luật (`RuleSpec.params`, đọc qua `ctx.param`), công ty ghi đè bằng hồ sơ công ty.
Mẫu tên layer dùng chung đọc từ `ctx.globals` (`allowed_layer_patterns`, `exempt_layer_patterns`).
Luật chỉ đọc DrawingModel; thiếu dữ liệu thì `Skip`.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from ..model import DrawingModel, SpaceStats
from . import Ctx, Finding, Skip, rule, sample


def _patterns(ctx: Ctx, key: str) -> list[re.Pattern]:
    return [re.compile(str(p), re.IGNORECASE) for p in ctx.globals.get(key, []) or []]


def _match(name: str, pats: list[re.Pattern]) -> bool:
    return any(p.search(name) for p in pats)


def _stats(model: DrawingModel):
    if model.stats is None:
        raise Skip("mô hình không có số liệu tổng hợp (stats); cần đọc từ DXF bằng cadguard")
    return model.stats


def _spaces(model: DrawingModel, with_blocks: bool) -> list[SpaceStats]:
    s = _stats(model)
    return [s.modelspace, s.paperspace] + ([s.blocks] if with_blocks else [])


def _pct(x: float) -> str:
    return f"{x * 100:.1f}".replace(".", ",") + "%"


def _names(names: list[str], n: int = 5) -> str:
    shown = ", ".join(f"'{x}'" for x in names[:n])
    return shown + (f" và {len(names) - n} layer khác" if len(names) > n else "")


@rule("VS-01")
def vs01(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    limit = int(ctx.param("max_xref_layers"))
    allowed = _patterns(ctx, "allowed_layer_patterns")
    residue = [la.name for la in model.layers if la.xref_dependent and not _match(la.name, allowed)]
    if len(residue) <= limit:
        return []
    return [Finding("VS-01", f"{len(residue)} layer dư từ xref đã gộp/đính kèm (tên có '|' hoặc '$0$'), ngưỡng {limit}: "
                    f"{_names(residue)}", count=len(residue))]


@rule("VS-02")
def vs02(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    max_text, max_dim = int(ctx.param("max_text_styles")), int(ctx.param("max_dim_styles"))
    out = []
    if len(model.styles) > max_text:
        out.append(Finding("VS-02", f"Bản vẽ có {len(model.styles)} kiểu chữ, ngưỡng {max_text}: nên gộp và xoá kiểu thừa",
                           count=len(model.styles)))
    if len(model.dim_styles) > max_dim:
        out.append(Finding("VS-02", f"Bản vẽ có {len(model.dim_styles)} kiểu kích thước, ngưỡng {max_dim}: nên gộp và xoá kiểu thừa",
                           count=len(model.dim_styles)))
    return out


@rule("VS-03")
def vs03(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    limit, min_n = float(ctx.param("max_layer0_ratio")), int(ctx.param("min_entities"))
    spaces = _spaces(model, with_blocks=False)  # nội dung định nghĩa khối trên layer 0 là đúng thông lệ, không tính
    total = sum(s.entities for s in spaces)
    if total < min_n:
        raise Skip(f"bản vẽ chỉ có {total} đối tượng (dưới {min_n}), tỉ lệ không có ý nghĩa")
    on0 = sum(s.by_layer.get("0", 0) for s in spaces)
    if on0 / total <= limit:
        return []
    return [Finding("VS-03", f"{on0}/{total} đối tượng ({_pct(on0 / total)}) nằm trực tiếp trên layer 0, ngưỡng {_pct(limit)}",
                    layer="0", count=on0)]


def _color_override(e) -> bool:
    return (e.color is not None and e.color != 256) or e.true_color is not None


def _lineweight_override(e) -> bool:
    return e.lineweight is not None and e.lineweight not in (-1, -2, -3)


@rule("VS-04")
def vs04(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    max_color, max_lw = float(ctx.param("max_color_override_ratio")), float(ctx.param("max_lineweight_override_ratio"))
    min_n = int(ctx.param("min_entities"))
    exempt = _patterns(ctx, "exempt_layer_patterns")
    ents = [e for e in model.entities if not _match(e.layer, exempt)]
    if len(ents) < min_n:
        raise Skip(f"chỉ có {len(ents)} đối tượng ngoài layer được miễn (dưới {min_n}), tỉ lệ không có ý nghĩa")
    note = " (danh sách đối tượng đã bị cắt ở trần bộ nhớ: tính trên phần đã đọc)" if (
        model.stats is not None and model.stats.entity_records_truncated) else ""
    out = []
    for label, test, limit in (("màu", _color_override, max_color), ("độ dày nét", _lineweight_override, max_lw)):
        bad = [e.handle for e in ents if test(e)]
        ratio = len(bad) / len(ents)
        if ratio > limit:
            out.append(Finding("VS-04", f"{len(bad)}/{len(ents)} đối tượng ({_pct(ratio)}) ghi đè {label} thay vì ByLayer, "
                               f"ngưỡng {_pct(limit)}{note}", count=len(bad), handles=sample(bad)))
    return out


@rule("VS-05")
def vs05(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    spaces = _spaces(model, with_blocks=True)
    out = []
    for attr, label, param in (("wipeout", "WIPEOUT", "max_wipeouts"),
                               ("image", "IMAGE", "max_images"),
                               ("ole", "OLE", "max_ole")):
        limit = int(ctx.param(param))
        n = sum(getattr(s, attr) for s in spaces)
        if n > limit:
            out.append(Finding("VS-05", f"{n} đối tượng {label} (kể cả trong khối), ngưỡng {limit}: làm nặng và dễ hỏng khi chuyển tệp",
                               count=n))
    return out


@rule("VS-06")
def vs06(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    limit = int(ctx.param("max_dim_text_overrides"))
    n = sum(s.dim_text_override for s in _spaces(model, with_blocks=True))
    if n <= limit:
        return []
    handles = [e.handle for e in model.entities if e.type == "DIMENSION" and e.dim_text not in (None, "", "<>")]
    return [Finding("VS-06", f"{n} kích thước có chữ ghi đè (số hiển thị có thể khác số đo thật), ngưỡng {limit}",
                    count=n, handles=sample(handles))]


def _font_base(font: str) -> str:
    return PurePosixPath(font.replace("\\", "/")).name.casefold()


@rule("VS-07")
def vs07(model: DrawingModel, ctx: Ctx) -> list[Finding]:
    limit = int(ctx.param("max_texts"))
    legacy = [re.compile(str(p), re.IGNORECASE) for p in ctx.param("legacy_font_patterns")]
    unicode_shx = {PurePosixPath(_font_base(str(f))).stem for f in ctx.param("unicode_shx_fonts")}  # so theo tên không đuôi
    counts = _stats(model).text_non_ascii_by_style
    styles = {s.name.casefold(): s for s in model.styles}
    bad: list[tuple[str, str, int]] = []
    for style_name, n in sorted(counts.items()):
        st = styles.get(style_name.casefold())
        if st is None or not st.font:
            continue  # không biết phông: không phán
        base = _font_base(st.font)
        suffix = PurePosixPath(base).suffix
        is_shx = suffix == ".shx" or suffix == ""  # tên phông không đuôi trong bảng STYLE là tệp SHX (vd 'txt')
        if (is_shx and PurePosixPath(base).stem not in unicode_shx) or _match(base, legacy):
            bad.append((st.name, st.font, n))
    total = sum(n for _, _, n in bad)
    if total <= limit:
        return []
    return [Finding("VS-07", f"{n} chữ có dấu/ngoài ASCII dùng kiểu chữ '{name}' với phông '{font}' không phải phông Unicode "
                    "(chữ tiếng Việt dễ hiển thị sai)", count=n) for name, font, n in bad]
