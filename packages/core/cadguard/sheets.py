"""Chỉ mục cấu trúc bản vẽ `cg.structure/1`: TỜ (trang in), đối tượng thuộc tờ nào, ứng viên rác. Không sửa bản vẽ.

Tờ là đơn vị làm việc: người thiết kế, khách hàng, bóc tách và báo giá đều chốt theo trang in. Nhận diện tất định:

- **Layout** (không gian giấy) có khung nhìn: vùng mô hình mỗi khung nhìn nhìn tới (`ViewportRec.view_*`).
- **Khung tờ trong không gian mô hình** (cách nhiều công ty Việt Nam vẽ: đặt khung tên ngay trong Model, nhiều
  khung cạnh nhau): khối khung tên (INSERT) hoặc hình chữ nhật đóng (LWPOLYLINE) có tỉ lệ khổ giấy ISO (√2) và
  - tên khối giống khung (KHUNG, FRAME, TITLE, A3…), hoặc
  - kích thước đúng khổ A0–A4 nhân một tỉ lệ chuẩn (1:20, 1:50…), hoặc
  - nhiều khung cùng cỡ (bộ tờ).

Mỗi đối tượng không gian mô hình được gán vào tờ chứa tâm của nó (tờ nhỏ nhất nếu lồng nhau). Đối tượng không thuộc
tờ nào (khi đã có tờ) là "ngoài tờ" (không được in). Ứng viên rác chỉ là GỢI Ý để người dùng xem, không tự xoá.

Kết quả là dữ liệu cục bộ của NGƯỜI dùng (tên layout, tiêu đề tờ là chữ trong bản vẽ): không đưa vào kết quả công
cụ trợ lý (ẩn danh Bậc 1) hay telemetry.
"""
from __future__ import annotations

import bisect
import hashlib
import math
import re
from dataclasses import dataclass, field

from .model import DrawingModel, EntityRec
from .textcodec import drawing_looks_tcvn3, entity_text, style_encodings

SCHEMA = "cg.structure/1"
PAPERS = {"A0": (1189.0, 841.0), "A1": (841.0, 594.0), "A2": (594.0, 420.0), "A3": (420.0, 297.0), "A4": (297.0, 210.0)}
SCALES = (1, 2, 2.5, 5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200, 250, 300, 400, 500, 1000)
RATIO = math.sqrt(2)
RATIO_TOL = 0.035  # lệch tỉ lệ √2 cho phép (khung vẽ tay thường lệch vài mm)
SCALE_TOL = 0.012  # lệch kích thước so với khổ × tỉ lệ chuẩn
FRAME_NAME = re.compile(r"khung|frame|border|title|ten[-_ ]?ban|tieu[-_ ]?de|\bkt\b|^a[0-4](\b|[-_ ])|[-_ ]a[0-4]$", re.I)
TITLE_TAG = re.compile(r"ten|title|name|banve|ban_ve|tieu", re.I)
SCALE_TEXT = re.compile(r"^\s*(?:TL|TỈ LỆ|TỶ LỆ|SCALE)?\s*:?\s*1\s*[/:]\s*(\d{1,4})\s*$", re.I)
MIN_CONTENT = 5
MAX_HANDLES = 500  # trần số handle liệt kê cho mỗi nhóm rác (số đếm vẫn đầy đủ)


@dataclass
class Sheet:
    id: str
    kind: str  # "layout" | "frame"
    name: str
    windows: list[tuple[float, float, float, float]] = field(default_factory=list)  # vùng mô hình (x0, y0, x1, y1)
    paper: str | None = None
    scale: float | None = None
    title: str | None = None
    title_source: str | None = None  # "attrib" | "text" | "text-decoded"
    scale_label: str | None = None
    frame_handle: str | None = None
    handles: list[str] = field(default_factory=list)
    content_hash: str = ""

    def to_dict(self) -> dict:
        w = self.windows
        box = None
        if w:
            box = [min(b[0] for b in w), min(b[1] for b in w), max(b[2] for b in w), max(b[3] for b in w)]
        return {"id": self.id, "kind": self.kind, "name": self.name, "title": self.title, "title_source": self.title_source,
                "paper": self.paper, "scale": self.scale, "scale_label": self.scale_label, "frame_handle": self.frame_handle,
                "window": box, "windows": [list(b) for b in w], "entity_count": len(self.handles),
                "content_hash": self.content_hash}


@dataclass
class Structure:
    file_hash: str
    sheets: list[Sheet]
    sheet_of: dict[str, str]  # handle -> id tờ
    outside: list[str]  # đối tượng mô hình có toạ độ nhưng không thuộc tờ nào
    no_position: int  # đối tượng không có toạ độ trong mô hình (HATCH, …): không gán được
    stray: list[str]  # đối tượng nằm xa vùng vẽ chính
    empty_layers: list[str]
    unused_blocks: list[str]
    encoding: dict
    insunits: int | None

    def to_dict(self, include_map: bool = False) -> dict:
        def grp(hs: list[str], model_by_layer: dict[str, int] | None = None) -> dict:
            out = {"count": len(hs), "handles": hs[:MAX_HANDLES], "truncated": len(hs) > MAX_HANDLES}
            if model_by_layer is not None:
                out["by_layer"] = dict(sorted(model_by_layer.items(), key=lambda kv: -kv[1])[:30])
            return out

        d = {"schema": SCHEMA, "file_hash": self.file_hash, "insunits": self.insunits,
             "sheets": [s.to_dict() for s in self.sheets],
             "junk": {"outside": grp(self.outside), "stray": grp(self.stray),
                      "empty_layers": self.empty_layers, "unused_blocks": self.unused_blocks},
             "no_position": self.no_position, "text_encoding": self.encoding}
        if include_map:
            d["sheet_of"] = self.sheet_of
        return d

    def sheets_for(self, handles) -> list[str]:
        seen: list[str] = []
        for h in handles or ():
            sid = self.sheet_of.get(h)
            if sid and sid not in seen:
                seen.append(sid)
        return seen


# ---------- hình học ----------

def entity_points(e: EntityRec) -> list[tuple[float, float]]:
    pts = list(e.pts or [])
    if e.arc is not None:
        cx, cy, r = e.arc[0], e.arc[1], e.arc[2]
        pts += [(cx - r, cy - r), (cx + r, cy + r)]
    elif e.radius is not None and e.pts:
        cx, cy = e.pts[0]
        pts += [(cx - e.radius, cy - e.radius), (cx + e.radius, cy + e.radius)]
    for p in (e.insert, e.pos):
        if p is not None:
            pts.append(p)
    return pts


def entity_center(e: EntityRec) -> tuple[float, float] | None:
    pts = entity_points(e)
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)


def _insert_box(e: EntityRec, ext) -> tuple[float, float, float, float] | None:
    if ext is None or e.insert is None:
        return None
    rot = (e.rotation or 0.0) % 360
    if min(abs(rot - a) for a in (0, 90, 180, 270, 360)) > 0.5:
        return None  # khung xoay xiên: bỏ qua
    sx, sy = e.xscale or 1.0, e.yscale or 1.0
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    xs, ys = [], []
    for x in (ext[0], ext[2]):
        for y in (ext[1], ext[3]):
            px, py = x * sx, y * sy
            xs.append(e.insert[0] + px * c - py * s)
            ys.append(e.insert[1] + px * s + py * c)
    return (min(xs), min(ys), max(xs), max(ys))


def _rect_box(e: EntityRec) -> tuple[float, float, float, float] | None:
    pts = e.pts or []
    if len(pts) == 5 and math.dist(pts[0], pts[-1]) < 1e-6:
        pts = pts[:4]
    if len(pts) != 4 or not (e.closed or len(e.pts or []) == 5):
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    tol = 1e-6 + 1e-4 * max(x1 - x0, y1 - y0)
    for x, y in pts:  # mọi đỉnh nằm ở góc: hình chữ nhật thẳng trục
        if not ((abs(x - x0) < tol or abs(x - x1) < tol) and (abs(y - y0) < tol or abs(y - y1) < tol)):
            return None
    return (x0, y0, x1, y1)


def paper_match(w: float, h: float) -> tuple[str | None, float | None, bool]:
    """(khổ, tỉ lệ, khớp_chặt) cho khung kích thước w × h (đơn vị bản vẽ, giả định mm)."""
    big, small = max(w, h), min(w, h)
    if small <= 0 or abs(big / small - RATIO) / RATIO > RATIO_TOL:
        return None, None, False
    best = None
    for name, (pw, ph) in PAPERS.items():
        for sc in SCALES:
            err = abs(big - pw * sc) / (pw * sc)
            if best is None or err < best[0] - 1e-9:
                best = (err, name, sc)
    if best and best[0] <= SCALE_TOL:
        return best[1], float(best[2]), True
    return None, None, False


class _Grid:
    """Tâm đối tượng sắp theo x để đếm/gán nhanh theo khung."""

    def __init__(self, items: list[tuple[float, float, str]]):
        self.items = sorted(items)
        self.xs = [it[0] for it in self.items]

    def inside(self, box) -> list[str]:
        x0, y0, x1, y1 = box
        i, j = bisect.bisect_left(self.xs, x0), bisect.bisect_right(self.xs, x1)
        return [h for x, y, h in self.items[i:j] if y0 <= y <= y1]


def _iou_contains(a, b, slack: float = 0.0) -> bool:
    return a[0] - slack <= b[0] and a[1] - slack <= b[1] and a[2] + slack >= b[2] and a[3] + slack >= b[3]


def _area(b) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


# ---------- nhận diện tờ ----------

def _frame_candidates(model: DrawingModel, ents: list[EntityRec], span: float) -> list[dict]:
    ext = {b.name.casefold(): b.extents for b in model.blocks if not b.is_layout}
    min_size = 0.004 * span  # bản vẽ nhiều tờ trong Model: 40 tờ 1:10…1:70 trải rộng; khung nhỏ vẫn phải đủ MIN_CONTENT
    out = []
    for e in ents:
        box = None
        named = False
        if e.type == "INSERT" and e.block:
            box = _insert_box(e, ext.get(e.block.casefold()))
            named = bool(FRAME_NAME.search(e.block))
        elif e.type == "LWPOLYLINE":
            box = _rect_box(e)
        if box is None:
            continue
        w, h = box[2] - box[0], box[3] - box[1]
        if max(w, h) < min_size:
            continue
        paper, scale, exact = paper_match(w, h)
        big, small = max(w, h), min(w, h)
        if small <= 0 or abs(big / small - RATIO) / RATIO > RATIO_TOL:
            continue
        out.append({"box": box, "handle": e.handle, "insert": e if e.type == "INSERT" else None, "named": named,
                    "paper": paper, "scale": scale, "exact": exact, "w": w, "h": h})
    return out


def _accept_frames(cands: list[dict], grid: _Grid) -> list[dict]:
    for c in cands:
        c["content"] = len(grid.inside(c["box"]))
    # cùng một khối khung tên có thuộc tính chèn nhiều lần: là bộ tờ, kể cả tờ còn trống (tờ chờ vẽ vẫn được đếm)
    block_uses: dict[str, int] = {}
    for c in cands:
        ins = c.get("insert")
        if ins is not None and ins.attribs:
            block_uses[ins.block.casefold()] = block_uses.get(ins.block.casefold(), 0) + 1

    def _titled_set(c) -> bool:
        ins = c.get("insert")
        return ins is not None and bool(ins.attribs) and block_uses.get(ins.block.casefold(), 0) >= 3

    cands = [c for c in cands if c["content"] >= MIN_CONTENT or _titled_set(c)]
    # nhóm cùng cỡ (± 1 %): bộ tờ
    for c in cands:
        c["peers"] = sum(1 for d in cands if abs(d["w"] - c["w"]) <= 0.01 * c["w"] and abs(d["h"] - c["h"]) <= 0.01 * c["h"])
        if _titled_set(c):
            c["peers"] = max(c["peers"], block_uses[c["insert"].block.casefold()])
    ok = [c for c in cands if c["named"] or c["exact"] or c["peers"] >= 2]
    # bỏ khung nằm trong khung đã nhận (viền trong của cùng khung tên, khung tên phụ), ưu tiên khối có tên khung
    ok.sort(key=lambda c: (-_area(c["box"]), not c["named"]))
    kept: list[dict] = []
    for c in ok:
        slack = 0.02 * max(c["w"], c["h"])
        if any(_iou_contains(k["box"], c["box"], slack) for k in kept):
            continue
        kept.append(c)
    return kept


def _title_for(frame: dict, ents_by_handle: dict[str, EntityRec], inside: list[str], enc: dict, guess) -> tuple:
    attrib_title = None
    ins = frame.get("insert")
    if ins is not None and ins.attribs:
        for tag, val in ins.attribs.items():
            if TITLE_TAG.search(tag) and val and val.strip():
                attrib_title = val.strip()[:120]
                break
    x0, y0, x1, y1 = frame["box"]
    best = None
    scale_label = None
    for h in inside:
        e = ents_by_handle.get(h)
        if e is None or e.type not in ("TEXT", "MTEXT") or not e.text or e.pos is None:
            continue
        txt, src = entity_text(e, enc, guess)
        txt = " ".join(txt.split())
        if not txt:
            continue
        if SCALE_TEXT.match(txt):
            scale_label = txt
            continue
        in_title_band = e.pos[1] <= y0 + 0.3 * (y1 - y0)  # khung tên thường ở dải dưới
        score = (in_title_band, e.text_height or 0.0, -len(txt))
        if len(txt) >= 3 and (best is None or score > best[0]):
            best = (score, txt, src)
    if attrib_title:
        return attrib_title, "attrib", scale_label
    if best is None:
        return None, None, scale_label
    return best[1][:120], "text-decoded" if best[2] else "text", scale_label


def _order_frames(frames: list[dict]) -> list[dict]:
    """Thứ tự đọc: hàng từ trên xuống (y lớn trước), trong hàng từ trái sang phải."""
    rows: list[list[dict]] = []
    for f in sorted(frames, key=lambda f: -f["box"][3]):
        for row in rows:
            r = row[0]["box"]
            if min(r[3], f["box"][3]) - max(r[1], f["box"][1]) > 0.5 * min(r[3] - r[1], f["box"][3] - f["box"][1]):
                row.append(f)
                break
        else:
            rows.append([f])
    return [f for row in rows for f in sorted(row, key=lambda f: f["box"][0])]


def _viewport_window(vp) -> tuple[float, float, float, float] | None:
    if vp.view_center is None or not vp.view_height or not vp.width or not vp.height:
        return None
    h = vp.view_height
    w = h * vp.width / vp.height
    cx, cy = vp.view_center
    if vp.twist and abs(vp.twist % 360) > 0.01:  # xoay: lấy khung bao của hình chữ nhật xoay
        a = math.radians(vp.twist)
        c, s = abs(math.cos(a)), abs(math.sin(a))
        w, h = w * c + h * s, w * s + h * c
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def _content_hash(ents: list[EntityRec]) -> str:
    h = hashlib.sha256()
    for e in sorted(ents, key=lambda e: e.handle):
        h.update(repr((e.handle, e.type, e.layer, e.pts, e.insert, e.pos, e.arc, e.radius, e.text, e.dim_text,
                       e.dim_value, e.block, e.attribs, e.rotation, e.xscale, e.yscale, e.text_height)).encode("utf-8"))
    return h.hexdigest()[:16]


def _stray(centers: list[tuple[float, float, str]]) -> list[str]:
    if len(centers) < 40:
        return []
    xs = sorted(c[0] for c in centers)
    ys = sorted(c[1] for c in centers)

    def q(a, p):
        return a[min(len(a) - 1, max(0, int(round(p * (len(a) - 1)))))]

    x0, x1, y0, y1 = q(xs, 0.01), q(xs, 0.99), q(ys, 0.01), q(ys, 0.99)
    mx, my = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
    m = max(mx, my)
    return [h for x, y, h in centers if x < x0 - m or x > x1 + m or y < y0 - m or y > y1 + m]


def build_structure(model: DrawingModel) -> Structure:
    enc = style_encodings(model)
    texts = [e.text for e in model.entities if e.type in ("TEXT", "MTEXT") and e.text][:5000]
    guess = "drawing" if drawing_looks_tcvn3(texts) else True
    model_ents = [e for e in model.entities if e.space == "Model"]
    by_handle = {e.handle: e for e in model.entities}
    centers: list[tuple[float, float, str]] = []
    no_pos = 0
    for e in model_ents:
        c = entity_center(e)
        if c is None:
            no_pos += 1
        else:
            centers.append((c[0], c[1], e.handle))
    grid = _Grid(centers)
    stray = _stray(centers)
    stray_set = set(stray)
    core = [c for c in centers if c[2] not in stray_set]
    span = 0.0
    if core:
        span = max(max(c[0] for c in core) - min(c[0] for c in core), max(c[1] for c in core) - min(c[1] for c in core))

    sheets: list[Sheet] = []
    layout_sheets: list[Sheet] = []
    # 1) layout có khung nhìn hoặc có nội dung trên giấy
    paper_count: dict[str, int] = {}
    for e in model.entities:
        if e.space != "Model":
            paper_count[e.space] = paper_count.get(e.space, 0) + 1
    for lo in model.layouts:
        wins = [w for w in (_viewport_window(vp) for vp in lo.viewports) if w is not None]
        if not wins and not lo.viewports and not paper_count.get(lo.name):
            continue  # layout trống mặc định của CAD
        paper = None
        if lo.paper_w_mm and lo.paper_h_mm:
            paper, _sc, _ok = paper_match(lo.paper_w_mm, lo.paper_h_mm)
        scales = [vp.scale for vp in lo.viewports if vp.scale]
        layout_sheets.append(Sheet(id="L:" + lo.name, kind="layout", name=lo.name, windows=wins, paper=paper,
                            scale=round(1 / scales[0], 2) if len(set(scales)) == 1 and scales[0] else None))
    # 2) khung tờ trong không gian mô hình
    frames = _order_frames(_accept_frames(_frame_candidates(model, model_ents, span), grid)) if span > 0 else []
    for i, f in enumerate(frames, 1):
        inside = grid.inside(f["box"])
        title, src, scale_label = _title_for(f, by_handle, inside, enc, guess)
        sheets.append(Sheet(id="F:" + f["handle"], kind="frame", name=f"Tờ {i}", windows=[f["box"]], paper=f["paper"],
                            scale=f["scale"], title=title, title_source=src, scale_label=scale_label,
                            frame_handle=f["handle"]))
    sheets += layout_sheets

    # 3) gán đối tượng vào tờ (tờ nhỏ nhất chứa tâm)
    sheet_of: dict[str, str] = {}
    order = sorted(((min(_area(w) for w in s.windows), s) for s in sheets if s.windows), key=lambda t: t[0])
    for _a, s in order:
        for w in s.windows:
            for h in grid.inside(w):
                sheet_of.setdefault(h, s.id)
    layout_ids = {s.id for s in sheets if s.kind == "layout"}
    for e in model.entities:  # đối tượng trên giấy thuộc tờ layout của nó
        if e.space != "Model" and "L:" + e.space in layout_ids:
            sheet_of[e.handle] = "L:" + e.space
    members: dict[str, list[EntityRec]] = {s.id: [] for s in sheets}
    for h, sid in sheet_of.items():
        e = by_handle.get(h)
        if e is not None:
            members[sid].append(e)
    for s in sheets:
        s.handles = sorted(e.handle for e in members[s.id])
        s.content_hash = _content_hash(members[s.id])
    outside = [h for _x, _y, h in centers if h not in sheet_of and h not in stray_set] if sheets else []

    # 4) ứng viên rác khác
    used_layers: set[str] = {e.layer.casefold() for e in model.entities} | {n.casefold() for n in model.block_layers}
    empty_layers = sorted(la.name for la in model.layers
                          if la.name.casefold() not in used_layers and la.name.casefold() not in ("0", "defpoints")
                          and not la.xref_dependent)
    inserted = {e.block.casefold() for e in model.entities if e.block}
    for b in model.blocks:
        inserted |= {c.casefold() for c in b.child_blocks}
    unused_blocks = sorted(b.name for b in model.blocks
                           if b.kind == "named" and not b.is_layout and not b.is_xref and not b.name.startswith("_")
                           and b.name.casefold() not in inserted)  # "_…": khối mũi tên kích thước của CAD
    encoding = {"styles": {k: v for k, v in sorted(enc.items())}, "guessed_tcvn3": guess == "drawing"}
    return Structure(file_hash=model.file_hash, sheets=sheets, sheet_of=sheet_of, outside=outside, no_position=no_pos,
                     stray=stray, empty_layers=empty_layers, unused_blocks=unused_blocks, encoding=encoding,
                     insunits=model.insunits)


__all__ = ["SCHEMA", "Sheet", "Structure", "build_structure", "entity_center", "paper_match"]
