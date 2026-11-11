"""Tách khối tủ trên mặt đứng bằng cắt XY đệ quy (recursive XY-cut) + nhận mặt trước từ ký hiệu mở cánh.

Tất định, chỉ đọc nét. Dùng cho `assemble.build_item_scene`.

- Khối: chia khung cụm nét theo đường cắt thẳng (dọc rồi ngang) không đi xuyên nét nào. Mảnh mỏng (< 150 mm: hông,
  nóc, chân) nhập vào mảnh bên cạnh. Không cắt được thì thử bỏ tấm nóc/đáy chạy suốt (nóc trùm chung) rồi cắt dọc;
  chỉ nhận khi đợt hai bên không cùng cao độ (cùng cao độ = một tủ có vách chia).
- Mặt trước: hình chữ nhật kín ≥ 150 mm sát mép khối/tấm/cánh khác; hoặc ô có ký hiệu mở cánh/ngăn kéo (nét khuất
  chéo) mà bốn cạnh ô có nét thân tủ (cách vẽ cánh bằng LINE).
- Dạng khối: `cabinet` (có mặt trước), `open` (kệ mở), `panel` (một tấm phủ gần hết khối, vd. ốp tường TV).
"""
from __future__ import annotations

from .primitives import box_of, items_in  # noqa: F401 — lớp nguyên tố L1 (tên cũ giữ cho nơi gọi)
from .views2d import Drawing2D, rect_of

PIECE_MIN = 150.0  # mảnh nhỏ hơn: tấm hông/nóc/chân, nhập vào mảnh bên cạnh
BAY_MIN = 300.0  # bỏ nóc chung để tách: mỗi bên ít nhất bấy nhiêu
BOARD_MAX = 60.0  # dày tấm ván trên mặt đứng
FRONT_MIN = 150.0
EDGE_TOL = 40.0
EPS = 0.5

Box = tuple[float, float, float, float]
from .primitives import Item  # noqa: E402,F401


def _cuts(items: list[Item], axis: int, keep: tuple = ()) -> list[list[Item]]:
    """Chia theo trục (0: đường cắt dọc, 1: đường cắt ngang) ở chỗ không nét nào đi qua; gộp mảnh mỏng."""
    iv = sorted(items, key=lambda t: (t[0][axis], t[0][axis + 2]))
    pieces: list[list[Item]] = [[iv[0]]]
    end = iv[0][0][axis + 2]
    for it in iv[1:]:
        if it[0][axis] >= end - EPS:
            pieces.append([it])
        else:
            pieces[-1].append(it)
        end = max(end, it[0][axis + 2])
    # chỉ cắt ở ranh giới thân tủ: có khe hở, hoặc có tấm ván (hông/nóc/đáy) chạy dọc đường cắt. Hai cánh sát nhau
    # (đường ráp cánh) không phải ranh giới khối.
    whole = box_of(items)
    across = (whole[3] - whole[1]) if axis == 0 else (whole[2] - whole[0])
    a2 = 1 - axis

    def board_at(p, pos):
        return any((b[axis + 2] - b[axis]) <= BOARD_MAX and (b[a2 + 2] - b[a2]) >= 0.5 * across
                   and (abs(b[axis] - pos) <= EPS or abs(b[axis + 2] - pos) <= EPS) for b, _h, _r in p)

    merged = [pieces[0]]
    for nxt in pieces[1:]:
        cur = merged[-1]
        hi, lo = box_of(cur)[axis + 2], box_of(nxt)[axis]
        if lo - hi >= 5.0 or board_at(cur, hi) or board_at(nxt, lo):
            merged.append(nxt)
        else:
            merged[-1] = cur + nxt
    pieces = merged

    def size(p):
        b = box_of(p)
        return b[axis + 2] - b[axis]

    i = 0
    while len(pieces) > 1 and i < len(pieces):
        pb = box_of(pieces[i])
        kept = axis == 0 and any(pb[0] - 1 <= x <= pb[2] + 1 for x in keep)  # có ghi chú "tấm fix": tấm bù hẹp, không gộp
        if size(pieces[i]) < PIECE_MIN and not kept:
            thin = pieces.pop(i)  # tấm mỏng nhập vào mảnh trước (hông phải của tủ trái); mảnh đầu nhập mảnh sau
            pieces[i - 1 if i > 0 else 0] += thin
            i = 0
            continue
        i += 1
    return pieces


def board_levels(items: list[Item]) -> list[float]:
    """Cao độ các tấm ngang (đợt, vách ngang) chạy gần hết bề ngang, không kể nóc/đáy."""
    b0 = box_of(items)
    w = b0[2] - b0[0]
    return sorted(round((b[1] + b[3]) / 2) for b, _h, _r in items
                  if (b[3] - b[1]) <= BOARD_MAX and (b[2] - b[0]) >= 0.6 * w and b[1] > b0[1] + BOARD_MAX and b[3] < b0[3] - BOARD_MAX)


def _same_levels(a: list[float], b: list[float]) -> bool:
    return bool(a) and len(a) == len(b) and all(abs(x - y) <= 5.0 for x, y in zip(a, b))


def split_blocks(items: list[Item], depth: int = 0, keep: tuple = ()) -> list[list[Item]]:
    """Cắt XY đệ quy. Trả các nhóm nét, mỗi nhóm một khối."""
    if depth > 12 or len(items) < 2:
        return [items]
    for axis in (0, 1):
        ps = _cuts(items, axis, keep)
        if len(ps) > 1:
            return [leaf for p in ps for leaf in split_blocks(p, depth + 1, keep)]
    box = box_of(items)
    w = box[2] - box[0]
    caps = [it for it in items if (it[0][3] - it[0][1]) <= BOARD_MAX and (it[0][2] - it[0][0]) >= 0.9 * w
            and (it[0][3] >= box[3] - EPS or it[0][1] <= box[1] + EPS)]
    rest = [it for it in items if it not in caps]
    if not caps or len(rest) < 2:
        return [items]
    ps = _cuts(rest, 0)
    if len(ps) < 2 or any(box_of(p)[2] - box_of(p)[0] < BAY_MIN for p in ps):
        return [items]
    lv = [board_levels(p) for p in ps]
    if any(_same_levels(lv[i], lv[i + 1]) for i in range(len(lv) - 1)):
        return [items]  # đợt hai bên cùng cao độ: một tủ có vách chia
    out: list[list[Item]] = []
    for p in ps:
        out += split_blocks(p, depth + 1)
    # nóc/đáy chung: chia cho từng khối theo bề ngang (khung khối kéo tới mép nóc); handle chỉ ghi ở khối đầu
    for c in caps:
        cb = c[0]
        first = True
        for leaf in out:
            lb = box_of(leaf)
            if min(cb[2], lb[2]) - max(cb[0], lb[0]) <= EPS:
                continue
            if abs(lb[3] - cb[1]) <= BOARD_MAX or abs(lb[1] - cb[3]) <= BOARD_MAX:
                leaf.append(((max(cb[0], lb[0]), cb[1], min(cb[2], lb[2]), cb[3]), c[1] if first else "", c[2]))
                first = False
    return out


def _near(v: float, refs: list[float], tol: float = EDGE_TOL) -> bool:
    return any(abs(v - r) <= tol for r in refs)


def _segments(d: Drawing2D, items: list[Item]) -> list[Box]:
    segs = []
    for _b, h, _r in items:
        if not h:
            continue
        e = d.entities[h]
        pts = list(e.pts or [])
        if e.type == "LWPOLYLINE" and e.closed and len(pts) > 2:
            pts = pts + [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if abs(x0 - x1) <= 0.5 or abs(y0 - y1) <= 0.5:
                segs.append((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
    return segs


def _covered(segs: list[Box], along: str, c: float, lo: float, hi: float, tol: float = 3.0) -> float:
    """Tỷ lệ đoạn [lo, hi] trên đường x = c (`along` 'x') hoặc z = c ('z') có nét phủ."""
    iv = []
    for x0, y0, x1, y1 in segs:
        if along == "x" and abs(x0 - c) <= tol and abs(x1 - c) <= tol:
            iv.append((max(y0, lo), min(y1, hi)))
        elif along == "z" and abs(y0 - c) <= tol and abs(y1 - c) <= tol:
            iv.append((max(x0, lo), min(x1, hi)))
    tot, cur = 0.0, lo
    for a, b in sorted(i for i in iv if i[1] > i[0]):
        a = max(a, cur)
        if b > a:
            tot += b - a
            cur = b
    return tot / max(hi - lo, 1e-9)


def _same(a: Box, b: Box, tol: float = 3.0) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def fronts(d: Drawing2D, body: list[Item], marks: list[Item], box: Box, symbols_only: bool = False) -> list[tuple[Box, str]]:
    """Mặt trước (cánh, ngăn kéo) của một khối: [(khung, handle)]."""
    rects = [(r, h) for _b, h, _r in body if h and (r := rect_of(d.entities[h]))]
    boards = [r for r, _h in rects if min(r[2] - r[0], r[3] - r[1]) <= BOARD_MAX]
    # loại đường bao trùng khung khối (lệch ≤ 5 mm); cánh/ngăn kéo đơn phủ gần hết mặt khối vẫn là mặt trước
    cands = [(r, h) for r, h in rects if (r[2] - r[0]) >= FRONT_MIN and (r[3] - r[1]) >= FRONT_MIN and not _same(r, box, 5.0)]
    segs = _segments(d, body)
    if symbols_only:  # hình "bỏ cánh": hình chữ nhật là khoang/ngăn trong, chỉ nhận ô có ký hiệu mở cánh
        cands = []
    # dấu X (hai đường chéo góc-góc ngược chiều) = khoang hở/thiết bị, không phải cánh; một đường chéo = ngăn kéo
    slopes: dict[tuple, set] = {}
    for b, h, _r in marks:
        pts = list(d.entities[h].pts or [])
        if d.entities[h].type == "LINE" and len(pts) == 2 and _same((min(pts[0][0], pts[1][0]), min(pts[0][1], pts[1][1]),
                                                                       max(pts[0][0], pts[1][0]), max(pts[0][1], pts[1][1])), b, 0.5):
            key = tuple(round(v / 3) for v in b)
            slopes.setdefault(key, set()).add((pts[1][0] - pts[0][0]) * (pts[1][1] - pts[0][1]) > 0)
    open_cells = [k for k, v in slopes.items() if len(v) == 2]
    cands = [(r, h) for r, h in cands if tuple(round(v / 3) for v in r) not in open_cells]
    for b, h, _r in marks:  # ô vẽ bằng LINE có ký hiệu mở (đoạn chéo nét khuất)
        if tuple(round(v / 3) for v in b) in open_cells:
            continue
        pts = list(d.entities[h].pts or [])
        if not any(abs(x0 - x1) > 1 and abs(y0 - y1) > 1 for (x0, y0), (x1, y1) in zip(pts, pts[1:])):
            continue
        if (b[2] - b[0]) < FRONT_MIN or (b[3] - b[1]) < FRONT_MIN or b[0] < box[0] - 1 or b[2] > box[2] + 1 or b[1] < box[1] - 1 or b[3] > box[3] + 1:
            continue
        cov = (_covered(segs, "x", b[0], b[1], b[3]), _covered(segs, "x", b[2], b[1], b[3]),
               _covered(segs, "z", b[1], b[0], b[2]), _covered(segs, "z", b[3], b[0], b[2]))
        if min(cov) >= 0.8 and not any(_same(r, b) for r, _h in cands):
            cands.append((b, h))
    inner = [(r, h) for r, h in cands if not any(not _same(o, r, 0.5) and o[0] <= r[0] + 0.5 and o[1] <= r[1] + 0.5
                                                    and o[2] >= r[2] - 0.5 and o[3] >= r[3] - 0.5 for o, _h in cands)]
    out = []
    for r, h in inner:  # sát mép khối / tấm / mặt trước khác ở ≥ 3 cạnh: loại khung TV, tranh giữa tấm ốp
        others = [o for o, _ in inner if o is not r]
        xs = [box[0], box[2]] + [v for b in boards + others for v in (b[0], b[2])]
        zs = [box[1], box[3]] + [v for b in boards + others for v in (b[1], b[3])]
        if sum((_near(r[0], xs), _near(r[2], xs), _near(r[1], zs, 120.0), _near(r[3], zs, 120.0))) >= 3:
            out.append((r, h))
    return out


def form_of(d: Drawing2D, body: list[Item], box: Box, fr: list) -> str:
    if fr:
        return "cabinet"
    area = (box[2] - box[0]) * (box[3] - box[1])
    for _b, h, _r in body:
        r = rect_of(d.entities[h]) if h else None
        if r and (r[2] - r[0]) * (r[3] - r[1]) >= 0.85 * area:
            return "panel"
    return "open"


__all__ = ["board_levels", "box_of", "form_of", "fronts", "items_in", "split_blocks"]
