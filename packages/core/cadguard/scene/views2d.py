"""Đọc bản vẽ kỹ thuật 2D theo cách công ty nội thất vẽ (Luồng 2: 3D-0 đánh giá, 3D-1 đọc mặt bằng).

Tất định, không LLM. Ba tầng:

1. **Vai trò layer** (`layer_roles`): tường, đồ nội thất, nét cắt, nét khuất, kích thước, chữ, ký hiệu… Học từ tên layer
   (từ khoá tiếng Việt/Anh, bỏ dấu) và thống kê loại đối tượng trên layer (như `rule_config.learn_layer_patterns` học
   quy ước có sẵn). Người dùng ghi đè bằng `{layer: vai trò}`.
2. **Hình chiếu trong tờ** (`segment_views`): một tờ (khung tên trong Model, `sheets.py`) thường chứa nhiều hình chiếu,
   mỗi hình có tiêu đề chữ lớn ngay bên dưới ("MẶT BẰNG …", "MẶT ĐỨNG …", "MẶT CẮT X1 …"). Gom đối tượng thành cụm
   theo khoảng hở (tính theo mm trên giấy × hệ số tờ) rồi gán cụm cho tiêu đề gần nhất nằm dưới nó.
3. **Nhóm hạng mục và liên kết** (`read_drawing`): các tờ cùng tiền tố số bản vẽ trong khung tên (vd. `xx.65. 01..04`)
   là một hạng mục đồ (tủ bếp, kệ tivi…). Ký hiệu mặt cắt (khối có thuộc tính nhãn `x1`, `y2`…) trỏ tới hình chiếu
   "MẶT CẮT X1" cùng hạng mục.

Kết quả chứa chữ trong bản vẽ (tiêu đề hình chiếu, tên hạng mục): là dữ liệu cục bộ của người dùng, không đưa vào
telemetry hay kết quả công cụ trợ lý ở chế độ ẩn danh.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field

from ..model import DrawingModel, EntityRec
from ..sheets import Sheet, Structure, _insert_box, build_structure, entity_points
from ..textcodec import decode, drawing_looks_tcvn3, entity_text, style_encodings

ROLES = ("wall", "furniture", "cut", "hidden", "thin", "visible", "door", "dim", "text", "symbol", "hatch", "frame", "other")
# Vai trò dùng làm "thân" hình vẽ đồ/kết cấu (khung bao, hình chữ nhật tấm, cạnh để gắn kích thước).
BODY_ROLES = frozenset({"furniture", "cut", "thin", "visible", "wall", "door"})
# Vai trò của chính đồ nội thất (nét liền ở mặt bằng/mặt đứng, nét cắt ở mặt cắt).
FURNITURE_ROLES_DEFAULT = frozenset({"furniture", "cut"})

# (vai trò, mẫu trên tên layer đã bỏ dấu, chữ thường). Thứ tự quan trọng: mẫu đầu tiên khớp thắng.
ROLE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("frame", r"khung|frame|border|titleblock|title block"),
    ("dim", r"dim|kich ?thuoc|\bktc?\b"),
    ("text", r"text|\bchu\b|ghi ?chu|note|anno"),
    ("symbol", r"ky ?hieu|symbol|\btag\b|\btruc\b|grid|cao ?do|level|section ?mark"),
    ("hatch", r"hatch|\bhas\b|pattern|vat ?lieu"),
    ("wall", r"tuong|wall|\bvach\b|be ?tong|column|\bcot\b"),
    ("cut", r"net ?cat|\bcut\b|section"),
    ("hidden", r"khuat|hidden|hidd"),
    ("door", r"door|window|\bcua\b"),
    ("furniture", r"noi ?that|furn|\bfur\b|a-fur|millwork|cabinet|\bdo ?go\b|\btu\b"),
    ("thin", r"manh|\bthin\b|mong"),
    ("visible", r"\bthay\b|visible"),
)

VIEW_TITLE = re.compile(
    r"^\s*(MẶT BẰNG TRẦN|MẶT TRẦN|MẶT BẰNG|MẶT ĐỨNG|MẶT CẮT|MẶT BÊN|CHI TIẾT|HÌNH ẢNH|PHỐI CẢNH|"
    r"CEILING PLAN|FLOOR PLAN|PLAN|ELEVATION|SECTION|DETAIL)\b\s*(.*)$")
KIND_OF = {"MẶT BẰNG TRẦN": "ceiling", "MẶT TRẦN": "ceiling", "CEILING PLAN": "ceiling", "MẶT BẰNG": "plan",
           "FLOOR PLAN": "plan", "PLAN": "plan", "MẶT ĐỨNG": "elevation", "MẶT BÊN": "elevation",
           "ELEVATION": "elevation", "MẶT CẮT": "section", "SECTION": "section", "CHI TIẾT": "detail",
           "DETAIL": "detail", "HÌNH ẢNH": "image", "PHỐI CẢNH": "image"}
SECTION_LABEL = re.compile(r"^([XY]\s*\d+|\d+\s*-\s*\d+|[A-Z]\s*-\s*[A-Z])\b\s*(.*)$")
DIRECTION = re.compile(r"\bHƯỚNG(?: NHÌN)?\s+([A-Z])\b")
FLAG_WORDS = {"BỎ CÁNH": "no_doors", "CHIA KHOANG": "divisions", "BỎ MẶT ĐÁ": "no_top", "BỐ TRÍ THIẾT BỊ": "equipment"}
MARK_LABEL = re.compile(r"^\s*([xXyY]\s*\d+|\d+\s*-\s*\d+)\s*$")
NUMBER_VALUE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9]*(?:[.\-]\s*[A-Za-z0-9]+)*?)\s*[.\-]\s*(\d+)\s*$")

GAP_PAPER_MM = 5.0  # khoảng hở tối đa (mm trên giấy) giữa hai đối tượng cùng một hình chiếu
MIN_TITLE_PAPER_MM = 2.0  # tiêu đề hình chiếu cao tối thiểu (mm trên giấy)


def fold(s: str) -> str:
    """Bỏ dấu tiếng Việt, chữ thường (đ -> d)."""
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


# ---------------- vai trò layer ----------------

def role_from_name(name: str) -> str | None:
    f = fold(name).replace("_", " ")
    for role, pat in ROLE_PATTERNS:
        if re.search(pat, f):
            return role
    return None


def layer_roles(model: DrawingModel, overrides: dict[str, str] | None = None) -> dict[str, str]:
    """{layer: vai trò}. Tên layer trước; layer không đoán được từ tên thì theo loại đối tượng chiếm đa số."""
    by_layer: dict[str, dict[str, int]] = {}
    for e in model.entities:
        if e.space == "Model":
            d = by_layer.setdefault(e.layer, {})
            d[e.type] = d.get(e.type, 0) + 1
    names = {la.name for la in model.layers} | set(by_layer)
    out: dict[str, str] = {}
    for n in sorted(names):
        role = role_from_name(n)
        if role is None:
            types = by_layer.get(n, {})
            total = sum(types.values())
            if total:
                top, cnt = max(types.items(), key=lambda kv: kv[1])
                if cnt >= 0.6 * total:
                    role = {"DIMENSION": "dim", "TEXT": "text", "MTEXT": "text", "HATCH": "hatch",
                            "MULTILEADER": "text", "LEADER": "text"}.get(top)
        out[n] = role or "other"
    for k, v in (overrides or {}).items():
        if v in ROLES:
            out[k] = v
    return out


# ---------------- hình học ----------------

Box4 = tuple[float, float, float, float]


def _bbox(pts) -> Box4 | None:
    pts = list(pts)
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def entity_box(e: EntityRec, block_ext: dict[str, Box4 | None]) -> Box4 | None:
    if e.type == "INSERT":
        b = _insert_box(e, block_ext.get((e.block or "").casefold()))
        if b is not None:
            return b
    pts = entity_points(e)
    if e.dim_pts:
        pts = pts + list(e.dim_pts)
    return _bbox(pts)


def rect_of(e: EntityRec) -> Box4 | None:
    """Hình chữ nhật thẳng trục khép kín (LWPOLYLINE 4 đỉnh, hoặc 5 đỉnh trùng đầu cuối)."""
    if e.type != "LWPOLYLINE" or not e.pts:
        return None
    pts = list(e.pts)
    if len(pts) == 5 and math.dist(pts[0], pts[-1]) < 1e-6:
        pts = pts[:4]
    if len(pts) != 4 or not (e.closed or len(e.pts) == 5):
        return None
    x0, y0, x1, y1 = _bbox(pts)
    tol = 1e-6 + 1e-4 * max(x1 - x0, y1 - y0)
    for x, y in pts:
        if not ((abs(x - x0) < tol or abs(x - x1) < tol) and (abs(y - y0) < tol or abs(y - y1) < tol)):
            return None
    if x1 - x0 <= 0 or y1 - y0 <= 0:
        return None
    return (x0, y0, x1, y1)


@dataclass
class Dim:
    handle: str
    value: float
    axis: str  # "h" (đo theo X) | "v" (đo theo Y) | "o" (xiên)
    lo: float  # đầu đoạn đo theo trục
    hi: float
    at: float  # vị trí đường kích thước theo trục còn lại
    p1: tuple[float, float]
    p2: tuple[float, float]


def dim_of(e: EntityRec) -> Dim | None:
    if e.type != "DIMENSION" or not e.dim_pts or e.dim_value is None or len(e.dim_pts) < 3:
        return None
    p1, p2, dl = e.dim_pts[0], e.dim_pts[1], e.dim_pts[2]
    if e.dim_kind == 0:
        a = (e.dim_angle or 0.0) % 180.0
    else:
        a = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0])) % 180.0
    if min(a, 180 - a) < 0.5:
        return Dim(e.handle, e.dim_value, "h", min(p1[0], p2[0]), max(p1[0], p2[0]), dl[1], p1, p2)
    if abs(a - 90) < 0.5:
        return Dim(e.handle, e.dim_value, "v", min(p1[1], p2[1]), max(p1[1], p2[1]), dl[0], p1, p2)
    return Dim(e.handle, e.dim_value, "o", 0.0, e.dim_value, 0.0, p1, p2)


# ---------------- hình chiếu ----------------

@dataclass
class View:
    id: str
    sheet_id: str
    kind: str  # plan | elevation | section | detail | ceiling | image | untitled
    title: str = ""
    label: str = ""  # nhãn mặt cắt (X1, Y2, 1-1) hoặc hướng nhìn (A, B)
    subject: str = ""  # phần còn lại của tiêu đề (tên đồ), chữ hoa, gọn khoảng trắng
    flags: list[str] = field(default_factory=list)
    title_handle: str | None = None
    box: Box4 | None = None  # khung bao các đối tượng "thân"
    handles: list[str] = field(default_factory=list)
    factor: float = 1.0  # hệ số tờ (1:20 -> 20)
    group: str = ""  # mã hạng mục (tiền tố số bản vẽ)

    def to_dict(self, ents: dict[str, EntityRec] | None = None) -> dict:
        return {"id": self.id, "sheet": self.sheet_id, "kind": self.kind, "title": self.title, "label": self.label,
                "subject": self.subject, "flags": self.flags, "group": self.group, "box": list(self.box) if self.box else None,
                "entities": len(self.handles), "factor": self.factor}


def parse_title(text: str) -> tuple[str, str, str, list[str]] | None:
    """(kind, label, subject, flags) từ chữ tiêu đề hình chiếu, None nếu không phải tiêu đề."""
    t = " ".join(text.upper().split())
    m = VIEW_TITLE.match(t)
    if not m:
        return None
    kind = KIND_OF[m.group(1)]
    rest = m.group(2).strip()
    label = ""
    flags = []
    for w, f in FLAG_WORDS.items():
        if w in rest:
            flags.append(f)
            rest = rest.replace(w, " ")
    if kind == "section":
        sm = SECTION_LABEL.match(rest)
        if sm:
            label, rest = sm.group(1).replace(" ", ""), sm.group(2)
    d = DIRECTION.search(rest)
    if d:
        label = label or d.group(1)
        rest = DIRECTION.sub(" ", rest)
    subject = " ".join(rest.replace("-", " ").split())
    return kind, label, subject, flags


def _sheet_factor(s: Sheet) -> float:
    return float(s.factor or s.scale or 1.0)


def _clusters(items: list[tuple[str, Box4]], gap: float) -> list[list[int]]:
    """Gom hộp chạm nhau (nới `gap`) bằng hợp-tìm, quét theo trục X."""
    n = len(items)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    order = sorted(range(n), key=lambda i: items[i][1][0])
    active: list[int] = []
    for i in order:
        b = items[i][1]
        active = [j for j in active if items[j][1][2] + gap >= b[0]]
        for j in active:
            c = items[j][1]
            if c[1] - gap <= b[3] and b[1] - gap <= c[3]:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj
        active.append(i)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def _union(boxes) -> Box4 | None:
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


@dataclass
class _Title:
    handle: str
    x: float
    y: float
    w: float
    h: float
    text: str
    parsed: tuple


def segment_views(model: DrawingModel, structure: Structure, roles: dict[str, str]) -> list[View]:
    enc = style_encodings(model)
    texts = [e.text for e in model.entities if e.type in ("TEXT", "MTEXT") and e.text][:5000]
    guess = "drawing" if drawing_looks_tcvn3(texts) else True
    by = {e.handle: e for e in model.entities}
    ext = {b.name.casefold(): b.extents for b in model.blocks if not b.is_layout}
    views: list[View] = []
    for s in structure.sheets:
        if s.kind != "frame":
            continue
        k = _sheet_factor(s)
        members = [by[h] for h in s.handles if h in by and h != s.frame_handle]
        titles: list[_Title] = []
        rest: list[EntityRec] = []
        for e in members:
            if e.type in ("TEXT", "MTEXT") and e.text and e.pos is not None:
                txt, _src = entity_text(e, enc, guess)
                p = parse_title(txt)
                hgt = e.text_height or 0.0
                if p and hgt >= MIN_TITLE_PAPER_MM * k * 0.99:
                    t1 = " ".join(txt.split())
                    titles.append(_Title(e.handle, e.pos[0], e.pos[1], 0.75 * hgt * len(t1), hgt, t1, p))
                    continue
            if roles.get(e.layer) == "frame":
                continue
            rest.append(e)
        items = [(e.handle, b) for e in rest if (b := entity_box(e, ext)) is not None]
        groups = _clusters(items, GAP_PAPER_MM * k)
        assigned: dict[int, list[str]] = {}
        gboxes = [_union(items[i][1] for i in g) for g in groups]
        claimed: dict[int, int] = {}  # cụm -> tiêu đề: tiêu đề nằm TRONG khung cụm (cách đặt tiêu đề bên phải/giữa hình)
        pad = GAP_PAPER_MM * k
        for ti, t in enumerate(titles):
            inside = [(gi, (b[2] - b[0]) * (b[3] - b[1])) for gi, b in enumerate(gboxes)
                      if b[0] - pad <= t.x <= b[2] + pad and b[1] - pad <= t.y <= b[3] + pad and len(groups[gi]) >= 3]
            if inside:
                gi = min(inside, key=lambda x: x[1])[0]
                claimed.setdefault(gi, ti)
        for gi, g in enumerate(groups):
            hs = [items[i][0] for i in g]
            box = gboxes[gi]
            if gi in claimed:
                assigned.setdefault(claimed[gi], []).extend(hs)
                continue
            best = None
            for ti, t in enumerate(titles):
                cx0, cy0, cx1, cy1 = box
                w = cx1 - cx0
                if t.y > cy0 + 0.25 * (cy1 - cy0):  # tiêu đề phải ở dưới (hoặc sát đáy) hình chiếu
                    continue
                if t.x + t.w < cx0 - 0.3 * w or t.x > cx1 + 0.3 * w:
                    continue
                score = abs(cy0 - t.y) + 0.3 * abs((t.x + t.w / 2) - (cx0 + cx1) / 2)
                if best is None or score < best[0]:
                    best = (score, ti)
            key = best[1] if best else -1 - len(assigned)
            assigned.setdefault(key, []).extend(hs)
        n = 0
        for key, hs in sorted(assigned.items(), key=lambda kv: kv[0]):
            body = [by[h] for h in hs if roles.get(by[h].layer) in BODY_ROLES and by[h].type not in ("TEXT", "MTEXT", "DIMENSION")]
            n += 1
            vid = f"V:{s.frame_handle}:{n}"
            if key >= 0:
                t = titles[key]
                kind, label, subject, flags = t.parsed
                views.append(View(vid, s.id, kind, t.text, label, subject, flags, t.handle,
                                  _union(entity_box(e, ext) for e in body), sorted(hs), k))
            else:
                views.append(View(vid, s.id, "untitled", box=_union(entity_box(e, ext) for e in body), handles=sorted(hs), factor=k))
        for ti, t in enumerate(titles):  # tiêu đề không có hình (vd. tiêu đề bộ chi tiết): vẫn ghi để đếm
            if ti not in assigned:
                kind, label, subject, flags = t.parsed
                n += 1
                views.append(View(f"V:{s.frame_handle}:{n}", s.id, kind, t.text, label, subject, flags, t.handle, None, [], k))
    return views


# ---------------- hạng mục (nhóm tờ) ----------------

def frame_number(attribs: dict[str, str] | None, number_tag: str | None = None) -> tuple[str, str] | None:
    """(mã hạng mục, số tờ) từ thuộc tính số bản vẽ của khung tên: 'xx.65. 02' -> ('xx.65', '02')."""
    if not attribs:
        return None
    vals = [attribs.get(number_tag, "")] if number_tag else list(attribs.values())
    for v in vals:
        m = NUMBER_VALUE.match(v or "")
        if m:
            return m.group(1).replace(" ", ""), m.group(2)
    return None


def frame_name(attribs: dict[str, str] | None, guess) -> str:
    """Tên hạng mục: thuộc tính chữ dài nhất không phải số/tỉ lệ (giải mã TCVN3 nếu cần)."""
    best = ""
    for v in (attribs or {}).values():
        v = (v or "").strip()
        if not v or NUMBER_VALUE.match(v) or re.fullmatch(r"[\d/:.\s]+", v):
            continue
        txt, _ = decode(v, None, guess)
        txt = " ".join(txt.split()).upper()
        if sum(c.isalpha() for c in txt) > sum(c.isalpha() for c in best):
            best = txt
    return best


@dataclass
class SectionMark:
    handle: str
    label: str
    sheet_id: str | None
    view_id: str | None  # hình chiếu chứa ký hiệu
    target: str | None = None  # hình chiếu mặt cắt được trỏ tới


@dataclass
class Drawing2D:
    structure: Structure
    roles: dict[str, str]
    views: list[View]
    groups: dict[str, dict]  # mã hạng mục -> {name, sheets[]}
    sheet_group: dict[str, str]
    marks: list[SectionMark]
    entities: dict[str, EntityRec]
    enc: dict = field(default_factory=dict)
    guess: object = True
    keywords: list = field(default_factory=list)  # hồ sơ trình bày: [{text, meaning}] (drafting.py)

    def view(self, vid: str) -> View | None:
        return next((v for v in self.views if v.id == vid), None)

    def views_of(self, group: str, kind: str | None = None) -> list[View]:
        return [v for v in self.views if v.group == group and (kind is None or v.kind == kind)]


def _norm_label(s: str) -> str:
    return re.sub(r"\s+", "", s).upper()


def read_drawing(model: DrawingModel, structure: Structure | None = None, roles: dict[str, str] | None = None,
                 number_tag: str | None = None) -> Drawing2D:
    st = structure or build_structure(model)
    rl = layer_roles(model, roles)
    texts = [e.text for e in model.entities if e.type in ("TEXT", "MTEXT") and e.text][:5000]
    guess = "drawing" if drawing_looks_tcvn3(texts) else True
    by = {e.handle: e for e in model.entities}
    views = segment_views(model, st, rl)
    groups: dict[str, dict] = {}
    sheet_group: dict[str, str] = {}
    for s in st.sheets:
        fr = by.get(s.frame_handle) if s.frame_handle else None
        num = frame_number(fr.attribs if fr else None, number_tag)
        if num:
            g = groups.setdefault(num[0], {"name": frame_name(fr.attribs, guess), "sheets": []})
            g["sheets"].append(s.id)
            sheet_group[s.id] = num[0]
    for v in views:
        v.group = sheet_group.get(v.sheet_id, "")
    # Khung tên không có số bản vẽ (block khung không thuộc tính): nhóm theo tên đồ trong tiêu đề hình
    # ("MẶT ĐỨNG BỎ CÁNH TỦ ÁO" + "MẶT BẰNG BỎ CÁNH TỦ ÁO" -> hạng mục "TỦ ÁO"). Mã nhóm bắt đầu "~" để phân biệt.
    for v in views:
        if v.group or not v.subject or v.kind not in ("plan", "elevation", "section", "detail"):
            continue
        g = "~" + v.subject[:40]
        info = groups.setdefault(g, {"name": v.subject[:60], "sheets": [], "by_title": True})
        if v.sheet_id not in info["sheets"]:
            info["sheets"].append(v.sheet_id)
        v.group = g
    view_of: dict[str, str] = {h: v.id for v in views for h in v.handles}
    marks: list[SectionMark] = []
    for e in model.entities:
        if e.space != "Model" or e.type != "INSERT" or not e.attribs:
            continue
        lab = next((MARK_LABEL.match(v).group(1) for v in e.attribs.values() if v and MARK_LABEL.match(v)), None)
        if lab is None or rl.get(e.layer) not in ("symbol", "dim", "text", "other", "cut"):
            continue
        sid = st.sheet_of.get(e.handle)
        mk = SectionMark(e.handle, _norm_label(lab), sid, view_of.get(e.handle))
        grp = sheet_group.get(sid or "", "")
        if grp:
            cands = [v for v in views if v.group == grp and v.kind == "section" and _norm_label(v.label) == mk.label]
            if len(cands) >= 1:
                # nhiều hình cùng nhãn: chọn hình cùng chủ đề với hình chứa ký hiệu, rồi tờ gần nhất
                src = next((v for v in views if v.id == mk.view_id), None)
                cands.sort(key=lambda v: (not (src and src.subject and v.subject and (src.subject in v.subject or v.subject in src.subject)),
                                          v.subject == "", v.sheet_id != sid))
                mk.target = cands[0].id
        marks.append(mk)
    return Drawing2D(st, rl, views, groups, sheet_group, marks, by, style_encodings(model), guess)


# ---------------- số đo gắn vào hình ----------------

def body_entities(d: Drawing2D, v: View, roles: frozenset[str] = BODY_ROLES) -> list[EntityRec]:
    return [d.entities[h] for h in v.handles
            if d.roles.get(d.entities[h].layer) in roles and d.entities[h].type not in ("TEXT", "MTEXT", "DIMENSION", "INSERT")]


def view_dims(d: Drawing2D, v: View) -> list[Dim]:
    return [x for h in v.handles if (x := dim_of(d.entities[h])) is not None]


def confirm(dims: list[Dim], axis: str, lo: float, hi: float, tol: float) -> Dim | None:
    """Kích thước đo đúng đoạn [lo, hi] theo trục (hai điểm đo trùng hai mép, số đo khớp)."""
    for x in dims:
        if x.axis == axis and abs(x.lo - lo) <= tol and abs(x.hi - hi) <= tol and abs(x.value - (hi - lo)) <= tol:
            return x
    return None


__all__ = ["BODY_ROLES", "FURNITURE_ROLES_DEFAULT", "Dim", "Drawing2D", "ROLES", "SectionMark", "View", "body_entities", "confirm", "dim_of",
           "entity_box", "fold", "frame_name", "frame_number", "layer_roles", "parse_title", "read_drawing", "rect_of",
           "role_from_name", "segment_views", "view_dims"]
