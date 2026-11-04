"""Hồ sơ số liệu của một DXF để khảo sát kho bản vẽ (P0). CHỈ SỐ TỔNG HỢP: không tên layer/khối/tệp, không nội dung chữ, không đường dẫn.

Dùng cho bản vẽ thật của khách: chạy cục bộ, kết quả là các con số, an toàn để ghi vào tài liệu.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

import ezdxf
from ezdxf import recover

LAYER_FN = re.compile(r"^FN-[A-Z0-9]+-[A-Z0-9]+(-[NEDT])?$")
LAYER_DASH = re.compile(r"^[A-Za-z0-9]+[-_][A-Za-z0-9_\- ]+$")
NON_ASCII = re.compile(r"[^\x00-\x7f]")
SOLID3D = {"3DSOLID", "BODY", "REGION", "SURFACE", "MESH", "POLYFACE", "POLYLINE3D"}


def _layer_category(name: str) -> str:
    if LAYER_FN.match(name):
        return "chuan_furniture_v0"
    if "$" in name or "|" in name:
        return "co_tien_to_xref"
    if NON_ASCII.search(name):
        return "co_dau_tieng_viet_hoac_ky_tu_la"
    if LAYER_DASH.match(name):
        return "dang_NHOM-CHI_TIET"
    if name == "0" or name.upper() == "DEFPOINTS":
        return "he_thong"
    return "khac"


def _bucket(v: float | None) -> str:
    if v is None or v <= 0:
        return "khong_ro"
    for lim in (1, 2, 2.5, 3, 3.5, 5, 10, 25, 50, 100, 250):
        if v <= lim:
            return f"<={lim}"
    return ">250"


def profile_dxf_stream(path: str | Path) -> dict:
    """Hồ sơ cho DXF ASCII RẤT LỚN: đọc dòng-từng-dòng, bộ nhớ gần như không đổi (ezdxf cần nhiều GB cho tệp vài trăm MB).

    Chỉ đếm; không giữ nội dung chữ. Số liệu giống `profile_dxf` ở các khoá chính nhưng thô hơn (không tách không gian giấy).
    """
    p = Path(path)
    out: dict = {"file_bytes": p.stat().st_size, "mode": "stream"}
    section = table = cur = None
    expect = None  # đang chờ tên mục/bảng sau SECTION/TABLE
    layer_names: list[str] = []
    layer_flags: list[tuple[int, int]] = []  # (flags70, color62)
    rec: dict = {}
    fonts: Counter = Counter()
    n_style = n_dimstyle = n_ltype = 0
    block_named = block_anon = block_xref = 0
    cur_block_anon = False
    in_block = False
    types_m: Counter = Counter()
    types_b: Counter = Counter()
    layer_use_m: Counter = Counter()
    layer_use_b: Counter = Counter()
    heights: Counter = Counter()
    txt_n = txt_non_ascii = dim_n = dim_override = line_z = line_n = 0
    color_ov = lw_ov = paper_ents = 0
    ent_is_text = False
    ent_checked_text = False

    def flush_table_rec() -> None:
        nonlocal n_style, n_dimstyle, n_ltype
        if table == "LAYER" and cur == "LAYER" and "name" in rec:
            layer_names.append(rec["name"])
            layer_flags.append((rec.get("flags", 0), rec.get("color", 7)))
        elif table == "STYLE" and cur == "STYLE":
            n_style += 1
            fonts[(rec.get("font") or "(trong)").lower()] += 1
        elif table == "DIMSTYLE" and cur == "DIMSTYLE":
            n_dimstyle += 1
        elif table == "LTYPE" and cur == "LTYPE":
            n_ltype += 1

    with open(p, encoding="utf-8", errors="replace", newline="") as fh:
        it = iter(fh)
        for code_line in it:
            val_line = next(it, "")
            code = code_line.strip()
            val = val_line.rstrip("\r\n").strip()
            if code == "0":
                if section == "TABLES":
                    flush_table_rec()
                rec = {}
                ent_checked_text = False
                if val == "SECTION":
                    expect = "section"
                elif val == "ENDSEC":
                    section = table = cur = None
                    in_block = False
                elif val == "TABLE":
                    expect = "table"
                elif val == "ENDTAB":
                    table = None
                    cur = None
                elif val == "ENDBLK":
                    in_block = False
                    cur = None
                else:
                    cur = val
                    if section == "BLOCKS" and val == "BLOCK":
                        in_block = True
                    elif section in ("ENTITIES", "BLOCKS") and not (section == "BLOCKS" and val == "BLOCK"):
                        ent_is_text = val in ("TEXT", "MTEXT")
                        if val in ("ATTRIB", "SEQEND", "VERTEX"):
                            pass  # bản ghi con, không phải đối tượng độc lập
                        elif section == "ENTITIES":
                            types_m[val] += 1
                            if val == "LINE":
                                line_n += 1
                            elif val in ("TEXT", "MTEXT"):
                                txt_n += 1
                            elif val == "DIMENSION":
                                dim_n += 1
                        elif in_block:
                            types_b[val] += 1
                continue
            if expect == "section" and code == "2":
                section, expect = val, None
                continue
            if expect == "table" and code == "2":
                table, expect = val, None
                continue
            if section == "TABLES":
                if code == "2" and "name" not in rec:
                    rec["name"] = val
                elif code == "70" and table == "LAYER":
                    rec["flags"] = int(val or 0)
                elif code == "62" and table == "LAYER":
                    rec["color"] = int(val or 7)
                elif code == "3" and table == "STYLE" and "font" not in rec:
                    rec["font"] = val
            elif section == "BLOCKS" and cur == "BLOCK":
                if code == "2" and "bn" not in rec:
                    rec["bn"] = val
                    nm = val
                    if nm.startswith("*"):
                        if not nm.lower().startswith(("*model_space", "*paper_space")):
                            block_anon += 1
                    else:
                        block_named += 1
                elif code == "70" and (int(val or 0) & 4):
                    block_xref += 1
            elif section in ("ENTITIES", "BLOCKS") and cur and cur not in ("BLOCK", "ENDBLK"):
                if code == "8":
                    (layer_use_m if section == "ENTITIES" else layer_use_b)[val] += 1
                elif code == "67" and section == "ENTITIES" and val == "1":
                    paper_ents += 1
                elif code == "62" and val not in ("256", "") and section == "ENTITIES":
                    color_ov += 1
                elif code == "370" and val not in ("-1", "-2", "-3", "") and section == "ENTITIES":
                    lw_ov += 1
                if section == "ENTITIES":
                    if cur == "LINE" and code in ("30", "31") and not rec.get("z"):
                        try:
                            if abs(float(val)) > 1e-6:
                                rec["z"] = 1
                                line_z += 1
                        except ValueError:
                            pass
                    elif cur in ("TEXT", "MTEXT"):
                        if code == "40" and not rec.get("h"):
                            rec["h"] = 1
                            try:
                                heights[_bucket(float(val))] += 1
                            except ValueError:
                                pass
                        elif code in ("1", "3") and not ent_checked_text and NON_ASCII.search(val):
                            ent_checked_text = True
                            txt_non_ascii += 1
                    elif cur == "DIMENSION" and code == "1" and val not in ("", "<>"):
                        dim_override += 1
        flush_table_rec()

    cats = Counter(_layer_category(n) for n in layer_names)
    total_m = sum(types_m.values())
    out["layers"] = {
        "total": len(layer_names),
        "by_naming": dict(cats),
        "frozen": sum(1 for f, c in layer_flags if f & 1),
        "off": sum(1 for f, c in layer_flags if c < 0),
        "max_name_len": max((len(n) for n in layer_names), default=0),
    }
    out["text_styles"] = {"total": n_style, "fonts": dict(fonts.most_common(12))}
    out["dim_styles"] = n_dimstyle
    out["linetypes"] = n_ltype
    out["blocks"] = {"named": block_named, "anonymous": block_anon, "xref_defs": block_xref}
    out["block_content"] = {
        "entities": sum(types_b.values()),
        "types_top": dict(types_b.most_common(10)),
        "layers_used": len(layer_use_b),
    }
    out["modelspace"] = {
        "entities": total_m,
        "paper_space_entities": paper_ents,
        "types_top": dict(types_m.most_common(14)),
        "proxy_like": sum(v for k, v in types_m.items() if "PROXY" in k),
        "solids3d": sum(v for k, v in types_m.items() if k in SOLID3D),
        "hatch": types_m.get("HATCH", 0),
        "image_ole": types_m.get("IMAGE", 0) + types_m.get("OLE2FRAME", 0),
        "wipeout": types_m.get("WIPEOUT", 0),
        "spline": types_m.get("SPLINE", 0),
        "inserts": types_m.get("INSERT", 0),
        "lines_nonzero_z": line_z,
        "color_override": color_ov,
        "lineweight_override": lw_ov,
        "layers_used": len(layer_use_m),
        "layers_empty": max(len(layer_names) - len(set(layer_use_m) | set(layer_use_b)), 0),
        "top5_layer_share_pct": round(100 * sum(c for _, c in layer_use_m.most_common(5)) / total_m, 1) if total_m else 0,
        "on_layer_0_pct": round(100 * layer_use_m.get("0", 0) / total_m, 1) if total_m else 0,
    }
    out["text"] = {
        "total": txt_n,
        "mtext": types_m.get("MTEXT", 0),
        "with_non_ascii_pct": round(100 * txt_non_ascii / txt_n, 1) if txt_n else 0,
        "height_buckets": dict(sorted(heights.items())),
    }
    out["dimensions"] = {"total": dim_n, "text_override": dim_override}
    return out


def load(path: Path):
    try:
        return ezdxf.readfile(path), False
    except Exception:  # noqa: BLE001 - DXF do bộ chuyển DWG sinh có thể lệch cấu trúc
        doc, _aud = recover.readfile(str(path))
        return doc, True


def profile_dxf(path: str | Path) -> dict:
    p = Path(path)
    doc, recovered = load(p)
    out: dict = {
        "file_bytes": p.stat().st_size,
        "file_hash": hashlib.sha256(p.read_bytes()).hexdigest()[:12],
        "dxf_version": str(doc.dxfversion),
        "recovered": recovered,
    }
    try:
        out["insunits"] = int(doc.header.get("$INSUNITS", 0))
    except Exception:  # noqa: BLE001
        out["insunits"] = None
    try:
        lo, hi = doc.header.get("$EXTMIN"), doc.header.get("$EXTMAX")
        out["extents_span"] = [round(abs(hi[i] - lo[i]), 1) for i in (0, 1)] if lo and hi else None
    except Exception:  # noqa: BLE001
        out["extents_span"] = None

    # --- layer
    layers = list(doc.layers)
    cats = Counter(_layer_category(str(la.dxf.name)) for la in layers)
    out["layers"] = {
        "total": len(layers),
        "by_naming": dict(cats),
        "frozen": sum(1 for la in layers if la.is_frozen()),
        "off": sum(1 for la in layers if la.is_off()),
        "no_plot": sum(1 for la in layers if not la.dxf.get("plot", 1)),
        "max_name_len": max((len(str(la.dxf.name)) for la in layers), default=0),
    }

    # --- style / font
    fonts = Counter()
    for st in doc.styles:
        f = str(st.dxf.get("font", "") or "").lower()
        fonts[f or "(trong)"] += 1
    out["text_styles"] = {"total": len(doc.styles), "fonts": dict(fonts.most_common(12))}
    out["dim_styles"] = len(doc.dimstyles)
    out["linetypes"] = len(doc.linetypes)

    # --- block
    blocks = [b for b in doc.blocks]
    named = [b for b in blocks if not str(b.name).startswith("*")]
    anon = [b for b in blocks if str(b.name).startswith("*") and not str(b.name).lower().startswith(("*model_space", "*paper_space"))]
    xref = [b for b in blocks if getattr(b.block, "dxf", None) is not None and b.block.dxf.get("flags", 0) & 4]
    out["blocks"] = {"named": len(named), "anonymous": len(anon), "xref_defs": len(xref)}
    btypes: Counter = Counter()
    blayers: set[str] = set()
    for b in named + anon:
        for e in b:
            btypes[e.dxftype()] += 1
            blayers.add(str(e.dxf.get("layer", "0")))
    out["block_content"] = {
        "entities": sum(btypes.values()),
        "types_top": dict(btypes.most_common(10)),
        "layers_used": len(blayers),
    }

    # --- layout
    layouts = [lo for lo in doc.layouts if lo.name.lower() != "model"]
    vps = 0
    for lo in layouts:
        vps += sum(1 for e in lo if e.dxftype() == "VIEWPORT") - 1 if len(lo) else 0
    out["layouts"] = {"paper": len(layouts), "viewports": max(vps, 0)}

    # --- không gian mô hình
    types: Counter = Counter()
    layer_use: Counter = Counter()
    heights: Counter = Counter()
    non_ascii_txt = txt_n = 0
    dim_n = dim_override = 0
    z_n = color_override = lw_override = 0
    dup = set()
    dup_n = 0
    ins_attr = ins_n = 0
    for e in doc.modelspace():
        t = e.dxftype()
        types[t] += 1
        lay = str(e.dxf.get("layer", "0"))
        layer_use[lay] += 1
        if e.dxf.get("color", 256) != 256:
            color_override += 1
        if e.dxf.get("lineweight", -1) not in (-1, -2, -3):
            lw_override += 1
        try:
            if t == "LINE":
                a, b = tuple(round(x, 3) for x in e.dxf.start), tuple(round(x, 3) for x in e.dxf.end)
                key = (lay, min(a, b), max(a, b))
                if key in dup:
                    dup_n += 1
                else:
                    dup.add(key)
                if abs(a[2]) > 1e-6 or abs(b[2]) > 1e-6:
                    z_n += 1
            elif t in ("TEXT", "MTEXT"):
                txt_n += 1
                s = e.dxf.get("text", "") if t == "TEXT" else e.text
                if NON_ASCII.search(s or ""):
                    non_ascii_txt += 1
                h = e.dxf.get("height") if t == "TEXT" else e.dxf.get("char_height")
                heights[_bucket(float(h) if h else None)] += 1
            elif t == "DIMENSION":
                dim_n += 1
                if (e.dxf.get("text", "") or "") not in ("", "<>"):
                    dim_override += 1
            elif t == "INSERT":
                ins_n += 1
                if getattr(e, "attribs", None):
                    ins_attr += 1
        except Exception:  # noqa: BLE001
            pass
    total = sum(types.values())
    out["modelspace"] = {
        "entities": total,
        "types_top": dict(types.most_common(14)),
        "proxy_like": sum(v for k, v in types.items() if "PROXY" in k),
        "solids3d": sum(v for k, v in types.items() if k in SOLID3D),
        "hatch": types.get("HATCH", 0),
        "image_ole": types.get("IMAGE", 0) + types.get("OLE2FRAME", 0),
        "wipeout": types.get("WIPEOUT", 0),
        "spline": types.get("SPLINE", 0),
        "inserts": ins_n,
        "inserts_with_attribs": ins_attr,
        "lines_nonzero_z": z_n,
        "duplicate_lines": dup_n,
        "color_override": color_override,
        "lineweight_override": lw_override,
        "layers_used": len(layer_use),
        "layers_empty": max(len(layers) - len(layer_use), 0),
        "top5_layer_share_pct": round(100 * sum(c for _, c in layer_use.most_common(5)) / total, 1) if total else 0,
        "on_layer_0_pct": round(100 * layer_use.get("0", 0) / total, 1) if total else 0,
    }
    out["text"] = {
        "total": txt_n,
        "mtext": types.get("MTEXT", 0),
        "with_non_ascii_pct": round(100 * non_ascii_txt / txt_n, 1) if txt_n else 0,
        "height_buckets": dict(sorted(heights.items())),
    }
    out["dimensions"] = {"total": dim_n, "text_override": dim_override}
    return out
