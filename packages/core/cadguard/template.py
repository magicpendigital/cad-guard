"""Template trình bày của công ty `cg.template/1`, HỌC từ một tờ mẫu (kế hoạch sheets-presentation mục 4).

Một thư mục gồm `template.yaml` (khung, trường, quy tắc tờ), `titleblock.dxf` (định nghĩa khối khung tên chép từ tờ
mẫu) và logo công ty (tệp ảnh người dùng chỉ ra). Mặc định lưu ở `<dự án>/.cadguard/template/`; gói luật
`sheet-layout-v0` (TP-xx) đọc template qua `rule_config.effective_standard`.

Học từ tờ mẫu (`learn`): khối khung tên của tờ, khổ giấy, chữ ký hình học của khối (số đối tượng, loại, khung bao),
dải khung tên dọc bên phải (đường đứng dài nhất trong 30 % bên phải khối), vùng vẽ (lề TCVN 7285: trái 20 mm, còn lại
10 mm, trừ dải khung tên), các thẻ thuộc tính: CỐ ĐỊNH (mọi tờ cùng giá trị) hay THAY ĐỔI, bắt buộc, mẫu; nhận thẻ tỉ lệ
(giá trị dạng 1/NN) và thẻ số bản vẽ (mã có số, khác nhau giữa các tờ); tỉ lệ cho phép (tỉ lệ chuẩn đang dùng); cỡ chữ in
nhỏ nhất của tờ mẫu.
"""
from __future__ import annotations

import hashlib
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from .model import DrawingModel
from .sheets import PAPERS, SCALES, build_structure

SCHEMA = "cg.template/1"
DIR_NAME = Path(".cadguard") / "template"
FILE_NAME = "template.yaml"
SCALE_VALUE = re.compile(r"^\s*(?:TL|TỈ LỆ|TỶ LỆ|SCALE)?\s*:?\s*1\s*[/:]\s*(\d+(?:[.,]\d+)?)\s*$", re.I)
BARE_NUMBER = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*$")
SCALE_TAG = re.compile(r"scale|ti_?le|ty_?le|^tl$", re.I)
NUMBER_VALUE = re.compile(r"\d")
MARGIN_LEFT, MARGIN_OTHER = 20.0, 10.0  # TCVN 7285:2003 (ISO 5457)


class TemplateError(ValueError):
    """Không học/nạp được template (tiếng Việt)."""


def template_dir(workspace: Path | None) -> Path | None:
    return None if workspace is None else Path(workspace) / DIR_NAME


def find_template(workspace: Path | None) -> Path | None:
    """Template của dự án, nếu không có thì của máy (`<thư mục cấu hình>/template`)."""
    cands = []
    if workspace is not None:
        cands.append(Path(workspace) / DIR_NAME / FILE_NAME)
    try:
        from .app.settings import config_dir

        cands.append(config_dir() / "template" / FILE_NAME)
    except Exception:  # noqa: BLE001
        pass
    return next((c for c in cands if c.is_file()), None)


def load_template(path: Path) -> dict:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, UnicodeDecodeError) as exc:
        raise TemplateError(f"Không đọc được template '{Path(path).name}' ({type(exc).__name__}).") from None
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise TemplateError(f"Template '{Path(path).name}' phải có schema {SCHEMA}.")
    return data


# ---------- học ----------

def value_pattern(value: str) -> str:
    """Mẫu regex từ một giá trị mẫu: dãy số -> \\d+, khoảng trắng -> \\s*, phần còn lại giữ nguyên."""
    out = []
    for tok in re.findall(r"\d+|\s+|[^\d\s]+", value.strip()):
        if tok.isdigit():
            out.append(r"\d+")
        elif tok.isspace():
            out.append(r"\s*")
        else:
            out.append(re.escape(tok))
    return "^" + "".join(out) + "$"


def number_format(value: str) -> dict | None:
    """'NT-01' -> {prefix: 'NT-', width: 2, suffix: ''}: dùng để đánh số lại."""
    m = re.match(r"^(.*?)(\d+)(\D*)$", value.strip())
    if not m:
        return None
    return {"prefix": m.group(1), "width": len(m.group(2)), "suffix": m.group(3)}


def format_number(fmt: dict, n: int) -> str:
    return f"{fmt['prefix']}{n:0{fmt['width']}d}{fmt['suffix']}"


def scale_value(value: str, bare: bool = False) -> float | None:
    """Mẫu số tỉ lệ ghi trong khung tên: '1/20' -> 20; số trần '20' chỉ nhận khi `bare` (thẻ tên SCALE/TI_LE)."""
    m = SCALE_VALUE.match(value or "") or (BARE_NUMBER.match(value or "") if bare else None)
    return float(m.group(1).replace(",", ".")) if m else None


def scale_format(value: str) -> str | None:
    """'1/15' -> '1/{n}'; 'TL 1:20' -> 'TL 1:{n}'; '20' -> '{n}'."""
    m = SCALE_VALUE.match(value or "") or BARE_NUMBER.match(value or "")
    if not m:
        return None
    return value[:m.start(1)] + "{n}" + value[m.end(1):]


def block_signature(model: DrawingModel, name: str) -> dict | None:
    b = next((x for x in model.blocks if x.name == name), None)
    if b is None:
        return None
    ext = [round(v, 1) for v in b.extents] if b.extents else None
    return {"entity_count": b.entity_count, "types": dict(sorted(b.types.items())), "extents": ext}


def _band_and_area(doc, block: str, ext: tuple[float, float, float, float], unit_mm: float) -> tuple[list | None, list]:
    """Dải khung tên (x0, y0, x1, y1 trong toạ độ khối) và vùng vẽ (trừ lề + dải)."""
    x0, y0, x1, y1 = ext
    w, h = x1 - x0, y1 - y0
    band = None
    try:
        blk = doc.blocks.get(block)
    except Exception:  # noqa: BLE001
        blk = None
    best = None
    if blk is not None:
        for e in blk:
            segs = []
            if e.dxftype() == "LINE":
                segs.append(((float(e.dxf.start.x), float(e.dxf.start.y)), (float(e.dxf.end.x), float(e.dxf.end.y))))
            elif e.dxftype() == "LWPOLYLINE":
                pts = [(float(p[0]), float(p[1])) for p in e.get_points("xy")]
                segs += list(zip(pts, pts[1:]))
            for (ax, ay), (bx, by) in segs:
                if abs(ax - bx) > 1e-6 * w:
                    continue
                length = abs(ay - by)
                if x0 + 0.7 * w <= ax <= x1 - 0.03 * w and length >= 0.8 * h and (best is None or ax < best):
                    best = float(ax)
    left, other = MARGIN_LEFT / unit_mm, MARGIN_OTHER / unit_mm
    area_x1 = x1 - other
    if best is not None:
        band = [round(best, 3), round(y0 + other, 3), round(x1 - other, 3), round(y1 - other, 3)]
        area_x1 = best
    area = [round(x0 + left, 3), round(y0 + other, 3), round(area_x1, 3), round(y1 - other, 3)]
    return band, area


def learn(path: Path, sheet_index: int, out_dir: Path, *, logo: Path | None = None, name: str = "",
          company: str = "") -> dict:
    """Học template từ tờ thứ `sheet_index` (đánh số từ 1) của bản vẽ `path`. Ghi `out_dir`. Trả dict template."""
    from .changeset.engine import read_doc
    from .dxf_reader import build_model

    doc = read_doc(path)
    model = build_model(doc)
    st = build_structure(model)
    if not 1 <= sheet_index <= len(st.sheets):
        raise TemplateError(f"Tờ {sheet_index} không có (bản vẽ có {len(st.sheets)} tờ).")
    sample = st.sheets[sheet_index - 1]
    if sample.kind != "frame" or not sample.block:
        raise TemplateError("Tờ mẫu phải là khung tên dạng khối trong Model (layout chưa hỗ trợ học template).")
    blk = next(b for b in model.blocks if b.name == sample.block)
    if not blk.extents:
        raise TemplateError("Không đo được khung bao của khối khung tên.")
    by_handle = {e.handle: e for e in model.entities}
    frame = by_handle[sample.frame_handle]
    bx0, by0, bx1, by1 = blk.extents
    bw, bh = bx1 - bx0, by1 - by0
    from .sheets import paper_match

    paper = sample.paper or paper_match(bw, bh)[0] or paper_match(bw, bh)[0]
    if paper is None:
        p1, _s, _e = paper_match(bw * 1.0, bh * 1.0)
        paper = p1
    if paper is None:  # khối vẽ ở 1:1 mm, lệch vài mm so với khổ chuẩn
        big, small = max(bw, bh), min(bw, bh)
        paper = next((n for n, (pw, ph) in PAPERS.items() if abs(big - pw) <= 0.02 * pw and abs(small - ph) <= 0.02 * ph), None)
    unit_mm = (max(bw, bh) / max(PAPERS[paper])) if paper else 1.0
    band, area = _band_and_area(doc, sample.block, blk.extents, unit_mm)

    sheets = [s for s in st.sheets if s.kind == "frame" and s.block == sample.block]
    values: dict[str, list[str]] = {}
    for s in sheets:
        for tag, val in (by_handle[s.frame_handle].attribs or {}).items():
            values.setdefault(tag.upper(), []).append((val or "").strip())
    sample_vals = {k.upper(): (v or "").strip() for k, v in (frame.attribs or {}).items()}
    fields = []
    scale_tag = number_tag = None
    for tag in sample_vals:
        vals = values.get(tag, [])
        nonempty = [v for v in vals if v]
        kind = "fixed" if len(sheets) >= 2 and nonempty and len(set(nonempty)) == 1 and len(nonempty) == len(vals) else "variable"
        f: dict[str, Any] = {"tag": tag, "kind": kind, "required": bool(sample_vals[tag])}
        if kind == "fixed":
            f["value"] = nonempty[0]
        bare = bool(SCALE_TAG.search(tag))
        if scale_tag is None and nonempty and sum(scale_value(v, bare) is not None for v in nonempty) >= max(1, len(nonempty) // 2):
            scale_tag = tag
            f["role"] = "scale"
            f["format"] = scale_format(sample_vals[tag]) or "1/{n}"
            f["bare"] = bare
        elif (number_tag is None and kind == "variable" and nonempty and all(NUMBER_VALUE.search(v) for v in nonempty)
              and len(set(nonempty)) >= 0.8 * len(nonempty) and sample_vals[tag] and len(sample_vals[tag]) <= 24):
            number_tag = tag
            f["role"] = "number"
            # mẫu phổ biến nhất trên mọi tờ (tờ mẫu có thể là tờ đặc biệt, vd. tờ tổng thể)
            common = Counter(value_pattern(v) for v in nonempty).most_common(1)[0][0]
            example = next(v for v in nonempty if value_pattern(v) == common)
            f["pattern"] = common
            f["number_format"] = number_format(example)
        fields.append(f)

    scales = sorted({s.scale for s in sheets if s.scale and s.factor and abs(s.factor - s.scale) <= 0.001 * s.scale})
    # cỡ chữ in nhỏ nhất của tờ mẫu (chữ trong tờ, không tính thuộc tính khung tên)
    printed = []
    for h in sample.handles:
        e = by_handle.get(h)
        if e is not None and e.type in ("TEXT", "MTEXT") and e.text_height and sample.factor:
            printed.append(e.text_height / sample.factor)
    min_text = max(1.0, round(min(printed) - 0.05, 1)) if printed else 1.8
    styles = sorted({str(e.dxf.get("style", "")) for e in doc.blocks.get(sample.block)
                     if e.dxftype() in ("TEXT", "MTEXT", "ATTDEF") and e.dxf.get("style", "")})

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tpl: dict[str, Any] = {
        "schema": SCHEMA, "name": name or sample.block, "version": "1", "company": company,
        "source": {"file_hash": hashlib.sha256(Path(path).read_bytes()).hexdigest(), "sheet": sheet_index},
        "frame": {"block": sample.block, "paper": paper, "unit_mm": round(unit_mm, 6),
                  "extents": [round(v, 3) for v in blk.extents], "band": band, "drawing_area": area,
                  "signature": block_signature(model, sample.block), "text_styles": styles},
        "fields": fields,
        "rules": {"allowed_scales": scales or [float(x) for x in SCALES], "min_text_mm": min_text,
                  "unicode_font": "Be Vietnam Pro"},
        "logo": None,
    }
    if logo is not None:
        lp = Path(logo)
        if not lp.is_file():
            raise TemplateError(f"Không thấy tệp logo '{lp.name}'.")
        dst = out_dir / ("logo" + lp.suffix.lower())
        shutil.copyfile(lp, dst)
        tpl["logo"] = {"file": dst.name, "sha256": hashlib.sha256(dst.read_bytes()).hexdigest()}
    _export_block(doc, sample.block, out_dir / "titleblock.dxf")
    (out_dir / FILE_NAME).write_text(yaml.safe_dump(tpl, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return tpl


def _export_block(doc, block: str, dst: Path) -> None:
    """Chép định nghĩa khối khung tên (kèm kiểu chữ, layer nó dùng) sang một DXF riêng."""
    import ezdxf
    from ezdxf.addons import Importer

    new = ezdxf.new(doc.dxfversion if doc.dxfversion >= "AC1015" else "R2018")
    imp = Importer(doc, new)
    imp.import_block(block)
    imp.finalize()
    new.modelspace().add_blockref(block, (0, 0))
    new.saveas(dst)


# ---------- áp dụng (sinh thao tác changeset) ----------

def apply_ops(model: DrawingModel, tpl: dict, *, renumber: bool = False, fill_scale: bool = True,
              fixed: bool = True) -> tuple[list[dict], list[str]]:
    """Thao tác `set_attribs` đưa khung tên về template: trường cố định, trường tỉ lệ theo hệ số khung, đánh số tờ.
    Không đụng hình vẽ, kích thước, chú thích. Trả (ops, ghi chú việc không tự làm được)."""
    st = build_structure(model)
    by_handle = {e.handle: e for e in model.entities}
    block = tpl["frame"]["block"]
    fields = {f["tag"]: f for f in tpl.get("fields", [])}
    scale_f = next((f for f in fields.values() if f.get("role") == "scale"), None)
    num_f = next((f for f in fields.values() if f.get("role") == "number"), None)
    items, notes = [], []
    seq = 0
    for s in st.sheets:
        if s.kind != "frame" or s.block != block:
            if s.kind == "frame":
                notes.append(f"{s.name}: khung '{s.block or 'nét rời'}' khác template, cần thay khung trong CAD.")
            continue
        seq += 1
        cur = {k.upper(): (v or "").strip() for k, v in (by_handle[s.frame_handle].attribs or {}).items()}
        vals: dict[str, str] = {}
        if fixed:
            for tag, f in fields.items():
                if f.get("kind") == "fixed" and tag in cur and cur[tag] != f.get("value", ""):
                    vals[tag] = f.get("value", "")
        if fill_scale and scale_f and scale_f["tag"] in cur and s.factor:
            allowed = [float(x) for x in tpl["rules"].get("allowed_scales", [])]
            if any(abs(s.factor - a) <= 0.001 * a for a in allowed):
                want = scale_f.get("format", "1/{n}").replace("{n}", f"{s.factor:g}")
                if cur[scale_f["tag"]] != want:
                    vals[scale_f["tag"]] = want
            else:
                notes.append(f"{s.name}: hệ số khung {s.factor:g} không thuộc tỉ lệ cho phép; cần chỉnh khung trong CAD.")
        if renumber and num_f and num_f.get("number_format") and num_f["tag"] in cur:
            want = format_number(num_f["number_format"], seq)
            if cur[num_f["tag"]] != want:
                vals[num_f["tag"]] = want
        if vals:
            items.append({"insert": s.frame_handle, "values": vals})
    ops = [{"op": "set_attribs", "items": items}] if items else []
    return ops, notes


__all__ = ["SCHEMA", "TemplateError", "apply_ops", "find_template", "format_number", "learn", "load_template",
           "number_format", "scale_format", "value_pattern"]
