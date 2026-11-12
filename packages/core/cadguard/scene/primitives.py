"""L1 — NGUYÊN TỐ HÌNH HỌC của bản vẽ nội thất (thiết kế `docs/research/kien-truc-doc-ban-ve-tong-the.md`, P1).

Mọi cách vẽ được tách thành cùng một bộ "mẩu", trước khi hiểu là tủ gì:

- Tấm (`Board`): chồng nét song song sát nhau (≤ `STACK_GAP`), dài gần bằng nhau — ván 18, ván + đá, hai mặt tấm kính;
  tấm ngang có thể kiểm "tựa" (đầu chạm hông khối hoặc nét đứng đi qua cao độ tấm).
- Khung (`Frame`): khung chữ nhật kín ≥ 150 × 150 (đường bao khối, cánh/ngăn kéo vẽ khung kín, ô thiết bị).
- Ký hiệu (`Symbol`): mở cánh/ngăn kéo (nét khuất chéo), ô dấu X, khấu/bo cong (polyline gãy hai đầu khác cạnh), vòng
  chú thích (tròn lớn không thuộc thân tủ).
- Ghi chú (`Note`): chữ + vị trí + nghĩa theo hồ sơ trình bày (`drafting`); một chữ có thể mang nhiều nghĩa.

Mỗi mẩu mang `refs` (handle: bằng chứng, "Tới trong AutoCAD") và `conf` (độ tin 0–1, dùng cho bước chọn cách hiểu L4).
Layer chỉ là gợi ý vai trò (`Drawing2D.roles`), không quyết định một mình.

Các lớp trên (`interior`, `segment`, `assemble`) dùng hàm ở đây thay cho bản sao riêng; P1 không đổi hành vi.
"""
from __future__ import annotations

from .params import P

from dataclasses import asdict, dataclass, field

from .views2d import Drawing2D, View, entity_box, rect_of

STACK_GAP = 62.0  # hai nét song song cách nhau ≤ mức này là cùng một tấm (ván + đá, hai mặt tấm kính…)
STACK_RATIO = 0.8  # các nét của một tấm dài gần bằng nhau (loại đáy máy hút mùi hình thang…)
EDGE_ZONE = 150.0  # tầng sát đáy/nóc khối: chân, đáy, nóc, phào — không phải đợt
SYMBOL_MIN = 150.0
CALLOUT_R = 50.0
SUPPORT_TOL = 6.0  # đầu tấm ngang chạm hông/vách (lòng ngăn kéo, đáy máy hút mùi lơ lửng thì không)
BODY = frozenset({"furniture", "cut"})
DRAW_TYPES = ("LINE", "LWPOLYLINE", "POLYLINE")

Box = tuple[float, float, float, float]
Seg = tuple[float, float, float, str]  # (đầu, cuối, toạ độ đường, handle): ngang (x0, x1, z) / đứng (z0, z1, x)
Item = tuple[Box, str, str]  # (khung, handle — rỗng nếu là phần nóc chung chia cho khối thứ hai trở đi, vai trò)


# ---------------- kiểu dữ liệu ----------------

@dataclass
class Board:
    axis: str  # "h" tấm ngang | "v" tấm đứng
    lo: float  # đoạn phủ dọc theo tấm (x với tấm ngang, z với tấm đứng)
    hi: float
    at0: float  # mặt dưới / trái
    at1: float  # mặt trên / phải
    lines: list[float] = field(default_factory=list)
    refs: list[str] = field(default_factory=list)
    supported: bool | None = None
    conf: float = 1.0


@dataclass
class Frame:
    box: Box
    refs: list[str]
    conf: float = 1.0


@dataclass
class Symbol:
    kind: str  # opening (mở cánh/ngăn kéo) | xbox (ô dấu X) | curve (khấu/bo cong) | callout (vòng chú thích)
    box: Box
    refs: list[str]
    conf: float = 1.0


@dataclass
class Note:
    x: float
    z: float
    text: str
    meanings: list[str]
    refs: list[str]


@dataclass
class Primitives:
    view: str
    boards: list[Board] = field(default_factory=list)
    frames: list[Frame] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def count(self) -> dict:
        out = {"boards_h": sum(1 for b in self.boards if b.axis == "h"), "boards_v": sum(1 for b in self.boards if b.axis == "v"),
               "frames": len(self.frames), "notes": len(self.notes)}
        for s in self.symbols:
            out[f"symbol_{s.kind}"] = out.get(f"symbol_{s.kind}", 0) + 1
        return out


# ---------------- nét, chữ ----------------

def pts(e) -> list[tuple[float, float]]:
    return [(float(p[0]), float(p[1])) for p in (e.pts or [])]


def items_in(d: Drawing2D, handles, roles: frozenset[str]) -> list[Item]:
    out = []
    for h in handles:
        e = d.entities[h]
        r = d.roles.get(e.layer)
        if r not in roles or e.type in ("TEXT", "MTEXT", "DIMENSION", "INSERT", "HATCH"):
            continue
        b = entity_box(e, {})
        if b is not None:
            out.append((b, h, r))
    return out


def box_of(items: list[Item]) -> Box:
    return (min(i[0][0] for i in items), min(i[0][1] for i in items), max(i[0][2] for i in items), max(i[0][3] for i in items))


def text_items(d: Drawing2D, handles) -> list[tuple[float, float, str, str]]:
    """Chữ (x, y, nội dung đã giải mã, handle)."""
    from .explain import _vi

    out = []
    for h in handles:
        e = d.entities[h]
        p = e.pos or e.insert
        if e.type in ("TEXT", "MTEXT") and e.text and p:
            out.append((float(p[0]), float(p[1]), _vi(e.text), h))
    return out


def meaning(d: Drawing2D, text: str) -> str | None:
    """Nghĩa chính của chữ theo hồ sơ trình bày (từ khoá dài nhất khớp)."""
    if not getattr(d, "keywords", None):
        return None
    from ..drafting import meaning_of

    return meaning_of(text, d.keywords)


def meanings(d: Drawing2D, text: str) -> list[str]:
    """Mọi nghĩa của chữ ("GHI CHÚ KHẤU … CHO THOÁT HƠI TỦ LẠNH" vừa khấu vừa thiết bị)."""
    from ..drafting import up

    t = up(text)
    return sorted({k["meaning"] for k in (getattr(d, "keywords", None) or []) if up(k["text"]) in t})


def has_meaning(d: Drawing2D, text: str, want: str) -> bool:
    return want in meanings(d, text)


def hsegs(d: Drawing2D, handles, roles: frozenset[str]) -> list[Seg]:
    """Đoạn ngang (x0, x1, z, handle) của các nét thuộc vai trò `roles`."""
    out = []
    for h in handles:
        e = d.entities[h]
        if d.roles.get(e.layer) not in roles or e.type not in DRAW_TYPES:
            continue
        p = pts(e)
        if e.closed and len(p) > 2:
            p = p + [p[0]]
        for (x0, y0), (x1, y1) in zip(p, p[1:]):
            if abs(y0 - y1) <= 0.5 and abs(x1 - x0) > 1:
                out.append((min(x0, x1), max(x0, x1), (y0 + y1) / 2, h))
    return out


def vsegs(d: Drawing2D, handles, roles: frozenset[str]) -> list[Seg]:
    """Đoạn đứng (z0, z1, x, handle)."""
    out = []
    for h in handles:
        e = d.entities[h]
        if d.roles.get(e.layer) not in roles or e.type not in DRAW_TYPES:
            continue
        p = pts(e)
        if e.closed and len(p) > 2:
            p = p + [p[0]]
        for (x0, y0), (x1, y1) in zip(p, p[1:]):
            if abs(x0 - x1) <= 0.5 and abs(y1 - y0) > 1:
                out.append((min(y0, y1), max(y0, y1), (x0 + x1) / 2, h))
    return out


# ---------------- ký hiệu ----------------

def is_curve_mark(p: list[tuple[float, float]], tol: float = 5.0) -> bool:
    """Polyline 3 điểm: hai đầu không cùng cạnh (lệch cả X lẫn Y), điểm giữa nằm trong tam giác (đầu, đầu, góc) = cung
    khấu/bo cong vẽ gãy khúc. Ký hiệu mở cánh/ngăn kéo có hai đầu cùng một cạnh nên không lọt."""
    if len(p) != 3:
        return False
    (ax, ay), (mx, my), (bx, by) = p
    if abs(ax - bx) <= tol or abs(ay - by) <= tol or min(abs(ax - bx), abs(ay - by)) < 50:
        return False
    for cx, cy in ((ax, by), (bx, ay)):  # góc vuông tạo bởi hai cạnh chứa hai đầu
        if min(ax, bx) - tol <= mx <= max(ax, bx) + tol and min(ay, by) - tol <= my <= max(ay, by) + tol:
            side = lambda px, py: (bx - ax) * (py - ay) - (by - ay) * (px - ax)  # noqa: E731 — điểm giữa phía góc
            if side(mx, my) * side(cx, cy) > 0:
                return True
    return False


def is_callout(e, role: str | None) -> bool:
    return e.type == "CIRCLE" and role not in BODY and float(getattr(e, "radius", 0) or 0) >= P("callout_r")


def is_annotation(d: Drawing2D, h: str) -> bool:
    """Ký hiệu chú thích (khấu/bo cong, vòng chú thích): không phải nét tủ, không phải ký hiệu cánh."""
    e = d.entities[h]
    return is_curve_mark(pts(e)) or is_callout(e, d.roles.get(e.layer))


def is_opening(d: Drawing2D, h: str) -> bool:
    """Ký hiệu mở cánh/ngăn kéo: nét khuất có đoạn chéo ≥ 150 × 150 (không kể đường khấu)."""
    e = d.entities[h]
    if d.roles.get(e.layer) != "hidden" or e.type not in DRAW_TYPES:
        return False
    p = pts(e)
    if is_curve_mark(p):
        return False
    return any(abs(x1 - x0) >= P("symbol_min") and abs(y1 - y0) >= P("symbol_min") for (x0, y0), (x1, y1) in zip(p, p[1:]))


def door_symbol_area(d: Drawing2D, v: View) -> float:
    """Tổng diện tích khung các ký hiệu mở cánh/ngăn kéo của hình."""
    tot = 0.0
    for h in v.handles:
        if not is_opening(d, h):
            continue
        b = entity_box(d.entities[h], {})
        if b:
            tot += (b[2] - b[0]) * (b[3] - b[1])
    return tot


def front_rects(d: Drawing2D, v: View) -> int:
    """Số khung chữ nhật kín ≥ 150 × 150 trên layer thân tủ (đường bao khối + cánh/ngăn kéo vẽ khung kín)."""
    n = 0
    for h in v.handles:
        e = d.entities[h]
        if d.roles.get(e.layer) in ("hidden", "dim", "text", "frame", None):
            continue
        r = rect_of(e)
        if r and (r[2] - r[0]) >= P("symbol_min") and (r[3] - r[1]) >= P("symbol_min"):
            n += 1
    return n


def xbox(d: Drawing2D, handles, x: float, z: float):
    """Khung có dấu X (hai đường chéo góc-góc) chứa điểm (x, z): ô thiết bị / khoang hở. Trả (khung, handle) hoặc None."""
    rects = []
    for h in handles:
        r = rect_of(d.entities[h])
        if r and r[0] <= x <= r[2] and r[1] <= z <= r[3] and (r[2] - r[0]) >= P("symbol_min") and (r[3] - r[1]) >= P("symbol_min"):
            rects.append((r, h))
    for r, h in sorted(rects, key=lambda t: (t[0][2] - t[0][0]) * (t[0][3] - t[0][1])):
        diag = 0
        for h2 in handles:
            p = pts(d.entities[h2])
            for (ax, ay), (bx, by) in zip(p, p[1:]):
                if abs(min(ax, bx) - r[0]) <= 3 and abs(max(ax, bx) - r[2]) <= 3 and abs(min(ay, by) - r[1]) <= 3 and abs(max(ay, by) - r[3]) <= 3:
                    diag += 1
        if diag >= 2:
            return r, h
    return None


# ---------------- tấm ----------------

def supported(x: float, z: float, vs: list[Seg], x0: float, x1: float) -> bool:
    if abs(x - x0) <= SUPPORT_TOL or abs(x - x1) <= SUPPORT_TOL:
        return True
    # nét đứng đi QUA cao độ tấm (hông, vách); cạnh lòng ngăn kéo/máy hút mùi chỉ mọc lên từ tấm nên không tính
    return any(abs(s[2] - x) <= SUPPORT_TOL and s[0] <= z - 30 and s[1] >= z + 30 for s in vs)


def board_stacks(segs: list[Seg], x0: float, x1: float, z0: float, z1: float, vs: list[Seg] | None = None,
                 edge: float | None = None) -> list[dict]:
    """Tấm NGANG trong khung [x0, x1] × [z0, z1] (toạ độ của hình): chồng nét ngang cách nhau ≤ STACK_GAP. Một nét đơn
    chỉ tính khi dài ≥ 60 % khung (cách vẽ đợt bằng một nét). Bỏ tấm cách đáy/nóc ≤ `edge` (chân, đáy, nóc, phào). Có `vs`
    (nét đứng thân tủ): tấm phải tựa — ít nhất một đầu chạm cạnh khung hoặc một nét đứng đi qua cao độ tấm.
    Trả [{z0, z1, lines, x0, x1, refs, conf}]."""
    edge = P("edge_zone") if edge is None else edge
    w = x1 - x0
    cand = sorted((s for s in segs if s[0] >= x0 - 5 and s[1] <= x1 + 5 and (s[1] - s[0]) >= 150.0
                   and z0 - 1 <= s[2] <= z1 + 1), key=lambda s: (s[2], s[0]))
    stacks: list[list] = []
    for s in cand:
        # cùng tấm: nét ngang ngay trên (≤ STACK_GAP), chồng lên nhau theo X, dài gần bằng nhau
        home = None
        for st in reversed(stacks):
            last = st[-1]
            if s[2] - last[2] > P("stack_gap"):
                continue
            ov = min(s[1], last[1]) - max(s[0], last[0])
            ln = (s[1] - s[0], last[1] - last[0])
            if ov >= 0.8 * min(ln) and min(ln) >= STACK_RATIO * max(ln):
                home = st
                break
        if home is not None:
            home.append(s)
        else:
            stacks.append([s])
    out = []
    for st in stacks:
        zs = sorted({round(s[2], 1) for s in st})
        lo, hi = zs[0], zs[-1]
        if lo <= z0 + edge or hi >= z1 - edge:
            continue
        if len(zs) == 1 and max(s[1] - s[0] for s in st) < 0.6 * w:
            continue
        if vs is not None:
            ends = (min(s[0] for s in st), max(s[1] for s in st))
            if not any(supported(x, z, vs, x0, x1) for x in ends for z in zs):
                continue
        out.append({"z0": lo, "z1": hi if hi > lo else lo + 1.0, "lines": zs, "x0": min(s[0] for s in st), "x1": max(s[1] for s in st),
                    "refs": sorted({s[3] for s in st}), "conf": 1.0 if len(zs) >= 2 else 0.7})
    return out


def vertical_boards(vs: list[Seg], hs: list[Seg], box: Box, edge: float | None = None) -> list[dict]:
    """Tấm ĐỨNG (vách) trong khung: hai nét đứng cách nhau 14–60 mm, cao ≥ 150, không sát cạnh khung (40 mm), hai đầu tựa
    lên tấm ngang hoặc đáy/nóc khung (cạnh lòng ngăn kéo, khung cánh thì không). Trả [{x0, x1, z0, z1, refs}]."""
    edge = P("edge_zone") if edge is None else edge
    bx0, bz0, bx1, bz1 = box
    vv = sorted((s for s in vs if (s[1] - s[0]) >= 150 and bx0 + 40 < s[2] < bx1 - 40), key=lambda s: s[2])

    def rests(x: float, z: float, end: str) -> bool:
        if (end == "lo" and z <= bz0 + edge) or (end == "hi" and z >= bz1 - edge):
            return True
        return any(s[0] - 5 <= x <= s[1] + 5 and abs(s[2] - z) <= 25 for s in hs)

    out: list[dict] = []
    for a, b in zip(vv, vv[1:]):
        if 14 <= b[2] - a[2] <= 60 and min(a[1], b[1]) - max(a[0], b[0]) >= 150:
            z0, z1 = max(a[0], b[0]), min(a[1], b[1])
            xm = (a[2] + b[2]) / 2
            if not (rests(xm, z0, "lo") and rests(xm, z1, "hi")):
                continue
            if not any(abs(o["x0"] - a[2]) < 5 for o in out):
                out.append({"x0": a[2], "x1": b[2], "z0": z0, "z1": z1, "refs": [a[3], b[3]]})
    return out


def cell(hs: list[Seg], vs: list[Seg], x: float, z: float, box: Box) -> Box | None:
    """Ô nhỏ nhất bao điểm (x, z) tạo bởi nét đứng trái/phải và nét ngang dưới/trên."""
    left = [s[2] for s in vs if s[2] < x and s[0] - 2 <= z <= s[1] + 2 and s[2] >= box[0] - 2]
    right = [s[2] for s in vs if s[2] > x and s[0] - 2 <= z <= s[1] + 2 and s[2] <= box[2] + 2]
    below = [s[2] for s in hs if s[2] < z and s[0] - 2 <= x <= s[1] + 2 and s[2] >= box[1] - 2]
    above = [s[2] for s in hs if s[2] > z and s[0] - 2 <= x <= s[1] + 2 and s[2] <= box[3] + 2]
    if not (left and right and below and above):
        return None
    return max(left), min(below), min(right), min(above)


# ---------------- trích cả hình ----------------

def extract(d: Drawing2D, v: View, body: frozenset[str] = BODY) -> Primitives:
    """Mọi nguyên tố của một hình (toạ độ của hình). Dùng để xem/đo (L1), và là đầu vào chung cho các lớp trên."""
    out = Primitives(view=v.id)
    if not v.box:
        return out
    hs, vs = hsegs(d, v.handles, body), vsegs(d, v.handles, body)
    for b in board_stacks(hs, v.box[0], v.box[2], v.box[1], v.box[3], vs, edge=0.0):
        out.boards.append(Board("h", b["x0"], b["x1"], b["z0"], b["z1"], b["lines"], b["refs"], True, b["conf"]))
    for b in vertical_boards(vs, hs, v.box, edge=0.0):
        out.boards.append(Board("v", b["z0"], b["z1"], b["x0"], b["x1"], [b["x0"], b["x1"]], b["refs"], True, 1.0))
    for h in v.handles:
        e = d.entities[h]
        role = d.roles.get(e.layer)
        b = entity_box(e, {})
        if b is None:
            continue
        r = rect_of(e)
        if r and role not in ("hidden", "dim", "text", "frame", None) and (r[2] - r[0]) >= P("symbol_min") and (r[3] - r[1]) >= P("symbol_min"):
            out.frames.append(Frame(r, [h]))
        if is_callout(e, role):
            out.symbols.append(Symbol("callout", b, [h]))
        elif role == "hidden" and is_curve_mark(pts(e)):
            out.symbols.append(Symbol("curve", b, [h]))
        elif is_opening(d, h):
            out.symbols.append(Symbol("opening", b, [h]))
    for fr in list(out.frames):
        cx, cz = (fr.box[0] + fr.box[2]) / 2, (fr.box[1] + fr.box[3]) / 2
        xb = xbox(d, v.handles, cx, cz)
        if xb and xb[0] == fr.box:
            out.symbols.append(Symbol("xbox", fr.box, [xb[1]]))
    for x, z, t, h in text_items(d, v.handles):
        out.notes.append(Note(x, z, t, meanings(d, t), [h]))
    return out


__all__ = ["BODY", "Board", "EDGE_ZONE", "Frame", "Note", "Primitives", "STACK_GAP", "Symbol", "board_stacks", "box_of", "cell",
           "door_symbol_area", "extract", "front_rects", "has_meaning", "hsegs", "is_annotation", "is_callout", "is_curve_mark",
           "is_opening", "items_in", "meaning", "meanings", "pts", "supported", "text_items", "vertical_boards", "vsegs", "xbox"]
