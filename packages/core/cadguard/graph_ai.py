"""P2: làm giàu đồ thị bản vẽ bằng đề xuất có kiểm chứng (`plans/cad-guard-kg-3d-production.md` mục 3.3).

Bốn "sub-agent", mỗi cái một việc hẹp, mỗi việc có HAI nguồn đề xuất:
- `code`: gợi ý tất định (chạy cả khi không có AI hoặc dự án ẩn danh), vd. tờ tên "MẶT ĐỨNG" chỉ có một hình chưa tiêu đề.
- `llm`: mô hình AI đọc gói ngữ cảnh hẹp của đúng việc đó, trả JSON theo lược đồ `cg.graph-proposals/1`.

| Agent | Việc | Đề xuất |
| --- | --- | --- |
| `views` | Phân loại hình chưa có tiêu đề | `view_kind` {view, kind, title?} |
| `links` | Ghép mặt đứng với mặt bằng khi không có kích thước chung | `link_views` {elevation, plan} |
| `materials` | Gán vật liệu cho bộ phận (thùng, cánh, hậu…) từ ghi chú | `item_material` {item, material, component?} |
| `review` | Soát nhất quán hạng mục (chỉ nhận xét) | `issue` {node, message} |

**Harness** (`check`): mọi đề xuất phải trỏ tới nút có thật, có handle bằng chứng tồn tại đúng chỗ (hình/tờ của hạng mục),
giá trị trong miền cho phép, ghép hình phải cùng hạng mục và khớp chiều ngang trong dung sai (lệch nhiều thì chỉ "cần
xem kỹ"). Không đạt thì bị loại, không bao giờ tới tay người dùng. Đề xuất ĐẠT vẫn chỉ là `proposed`: chỉ thành dữ
liệu khi người dùng bấm Đồng ý (`decide`). Ghép hình đã đồng ý ghi vào phần bổ sung 3D (`.cadguard/scene/`); loại hình
và vật liệu ghi vào `.cadguard/graph/<băm>.overrides.json`. Bản vẽ không bao giờ bị sửa.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from .graph import MIN_VIEW_ENTITIES, _fold, materials_in
from .scene.explain import _sheet_name, _vi
from .scene.views2d import Drawing2D

SCHEMA = "cg.graph-proposals/1"
OVERRIDES_SCHEMA = "cg.graph-overrides/1"
STORE = ".cadguard/graph"
KINDS = ("plan", "elevation", "section", "detail", "ceiling", "image")
COMPONENTS = ("thùng", "hông", "nóc", "đáy", "hậu", "cánh", "ngăn kéo", "đợt", "vách", "mặt", "khung", "chân", "tay nắm",
              "len chân", "ốp", "nẹp")
def _up(s: str) -> str:
    """Chữ HOA giữ dấu (NFC): 'CÁNH' (cửa) khác 'CẠNH' (mép). Cùng độ dài với `_fold` nên vị trí khớp nhau."""
    import unicodedata

    return unicodedata.normalize("NFC", s).upper()


_COMP_FOLD = {c: _up(c) for c in COMPONENTS}  # so khớp bộ phận GIỮ DẤU
MAX_PROPOSALS = 200
LINK_TOL = 0.15  # lệch chiều ngang khung hình mặt đứng/mặt bằng cho phép (tỉ lệ)
AGENTS = ("views", "links", "materials", "review")


class GraphAiError(ValueError):
    pass


# ---------------- lưu trữ ----------------

def _paths(root: Path, file_hash: str) -> tuple[Path, Path]:
    d = root / STORE
    return d / f"{file_hash[:16]}.proposals.json", d / f"{file_hash[:16]}.overrides.json"


def load_overrides(root: Path, file_hash: str) -> dict:
    _, op = _paths(root, file_hash)
    try:
        data = json.loads(op.read_text(encoding="utf-8"))
        if data.get("schema") == OVERRIDES_SCHEMA and data.get("source_hash") == file_hash:
            return data
    except (OSError, ValueError):
        pass
    return {"schema": OVERRIDES_SCHEMA, "source_hash": file_hash, "view_kind": {}, "materials": [], "issues": [], "scope": {}}


def load_proposals(root: Path, file_hash: str) -> dict:
    pp, _ = _paths(root, file_hash)
    try:
        data = json.loads(pp.read_text(encoding="utf-8"))
        if data.get("schema") == SCHEMA and data.get("source_hash") == file_hash:
            return data
    except (OSError, ValueError):
        pass
    return {"schema": SCHEMA, "source_hash": file_hash, "runs": [], "items": [], "rejected": []}


def _write(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def apply_overrides(d: Drawing2D, ov: dict) -> Drawing2D:
    """Loại hình người dùng đã xác nhận: đổi ngay trong Drawing2D để 3D và đồ thị cùng dùng."""
    for v in d.views:
        x = (ov.get("view_kind") or {}).get(v.id)
        if x and x.get("kind") in KINDS:
            v.kind = x["kind"]
            if x.get("title") and not v.title:
                v.title = str(x["title"])[:120]
    return d


# ---------------- gói ngữ cảnh (dùng cho cả gợi ý code và AI) ----------------

def _box_w(v) -> float | None:
    return (v.box[2] - v.box[0]) if v.box else None


def _txt(d: Drawing2D, e) -> str:
    """Chữ đã giải mã theo phông của kiểu chữ (TCVN3/VNI, kể cả phông chữ hoa)."""
    from .textcodec import entity_text

    return (entity_text(e, d.enc or {}, True)[0] or "").strip()


def _texts_in(d: Drawing2D, box, limit: int = 12, pad: float = 0.0) -> list[tuple[str, str]]:
    if not box:
        return []
    x0, y0, x1, y1 = box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad
    out = []
    for h, e in d.entities.items():
        if not e.text:
            continue
        p = e.pos or e.insert
        if p and x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
            out.append((h, _txt(d, e)[:120]))
            if len(out) >= limit:
                break
    return out


def _item_texts(d: Drawing2D, grp: str, limit: int = 80) -> list[tuple[str, str]]:
    sheets = set((d.groups.get(grp) or {}).get("sheets") or [])
    out = []
    for h, e in d.entities.items():
        if e.text and d.structure.sheet_of.get(h) in sheets:
            t = _txt(d, e)
            if len(t) >= 3:
                out.append((h, t[:200]))
                if len(out) >= limit:
                    break
    return out


def _unlinked(d: Drawing2D, supp: dict) -> list[tuple[Any, list]]:
    """(mặt đứng chưa ghép, các mặt bằng cùng hạng mục) theo đúng logic dựng 3D."""
    from .scene.assemble import build_item_scene

    out = []
    for grp in d.groups:
        try:
            sc = build_item_scene(d, grp, supp)
        except Exception:  # noqa: BLE001
            continue
        for g in sc.gaps:
            if g.id.startswith("link:"):
                e = d.view(g.target)
                plans = [v for v in d.views_of(grp, "plan") if v.box]
                if e is not None and plans:
                    out.append((e, plans))
    return out


def context(d: Drawing2D, supp: dict, agent: str) -> dict:
    """Gói ngữ cảnh hẹp cho một agent (chữ đã giải mã; mã hình/handle để trả lời)."""
    if agent == "views":
        vs = [v for v in d.views if v.kind == "untitled" and len(v.handles) >= MIN_VIEW_ENTITIES]
        return {"views": [{"view": v.id, "sheet": _sheet_name(d, v.sheet_id), "item": v.group or None,
                           "entities": len(v.handles), "width_mm": round(_box_w(v) or 0),
                           "height_mm": round((v.box[3] - v.box[1]) if v.box else 0),
                           "texts": [{"handle": h, "text": t} for h, t in _texts_in(d, v.box, pad=200)]} for v in vs[:40]]}
    if agent == "links":
        rows = []
        for e, plans in _unlinked(d, supp)[:30]:
            rows.append({"elevation": e.id, "elevation_title": _vi(e.title), "item": e.group,
                         "elevation_width_mm": round(_box_w(e) or 0),
                         "candidates": [{"plan": p.id, "title": _vi(p.title), "width_mm": round(_box_w(p) or 0),
                                         "sheet": _sheet_name(d, p.sheet_id)} for p in plans]})
        return {"elevations": rows}
    if agent == "materials":
        return {"items": [{"item": g, "name": _vi(str(info.get("name") or g)),
                           "notes": [{"handle": h, "text": t} for h, t in _item_texts(d, g) if materials_in(t)
                                     or any(c in _up(t) for c in _COMP_FOLD.values())][:40]}
                          for g, info in d.groups.items()]}
    if agent == "review":
        from .scene.assemble import build_item_scene

        items = []
        for g, info in d.groups.items():
            try:
                sc = build_item_scene(d, g, supp)
            except Exception:  # noqa: BLE001
                continue
            items.append({"item": g, "name": _vi(str(info.get("name") or g)),
                          "views": {k: len(d.views_of(g, k)) for k in ("plan", "elevation", "section", "detail")},
                          "modules": [{"node": f"module:{g}:{m.id}", "kind": m.kind, "w": round(m.w), "d": round(m.d),
                                       "h": round(m.h), "z0": round(m.z0), "fronts": len(m.fronts), "shelves": m.shelves}
                                      for m in sc.modules]})
        return {"items": items}
    raise GraphAiError("Agent không hợp lệ.")


# ---------------- gợi ý tất định (source = code) ----------------

def _pid(kind: str, target: str, value: Any) -> str:
    return "p-" + hashlib.sha256(json.dumps([kind, target, value], ensure_ascii=False).encode("utf-8")).hexdigest()[:12]


def code_proposals(d: Drawing2D, supp: dict) -> list[dict]:
    out: list[dict] = []
    # views: tờ có tiêu đề kiểu hình và chỉ MỘT hình chưa tiêu đề -> hình đó cùng loại với tiêu đề tờ
    from .scene.views2d import KIND_OF, VIEW_TITLE

    for s in d.structure.sheets:
        un = [v for v in d.views if v.sheet_id == s.id and v.kind == "untitled" and len(v.handles) >= MIN_VIEW_ENTITIES]
        title = _vi(s.title or "")
        m = VIEW_TITLE.match(title.upper()) if title else None
        if len(un) == 1 and m:
            kind = KIND_OF.get(m.group(1))
            if kind in KINDS:
                out.append({"kind": "view_kind", "target": un[0].id, "value": {"kind": kind, "title": title},
                            "evidence": [s.frame_handle] if s.frame_handle else [],
                            "reason": f"Tờ có tiêu đề “{title}” và chỉ có một hình chưa có tiêu đề.", "confidence": 0.75,
                            "agent": "views"})
    # links (1): ký hiệu hướng nhìn/triển khai diện tường trên mặt bằng mang đúng nhãn của mặt đứng (a, b, c…)
    linked: set[str] = set()
    for e, plans in _unlinked(d, supp):
        lab = (e.label or "").strip().casefold()
        if not lab:
            continue
        for pl in plans:
            mk = _key_marker(d, pl, lab)
            if mk is None:
                continue
            we, wp = _box_w(e) or 0, _box_w(pl) or 0
            flags = []
            if wp and we and abs(wp - we) / max(wp, we) > LINK_TOL:
                flags.append(f"Mặt đứng chỉ là một đoạn của mặt bằng ({we:.0f}/{wp:.0f} mm): CAD Guard căn theo mép trái, "
                             "kiểm lại vị trí và chiều sâu ở màn 3D sau khi đồng ý.")
            out.append({"kind": "link_views", "target": e.id, "value": {"plan": pl.id}, "evidence": [mk],
                        "reason": f"Trên mặt bằng “{_vi(pl.title)}” có ký hiệu hướng nhìn mang nhãn “{e.label}”.",
                        "confidence": 0.85, "agent": "links", "flags": flags})
            linked.add(e.id)
            break
    # links (2): mặt bằng cùng hạng mục có chiều ngang khung hình gần nhất
    for e, plans in _unlinked(d, supp):
        we = _box_w(e)
        if not we or e.id in linked:
            continue
        best = min(plans, key=lambda p: abs((_box_w(p) or 0) - we))
        wp = _box_w(best) or 0
        rel = abs(wp - we) / max(wp, we)
        if rel <= LINK_TOL:
            out.append({"kind": "link_views", "target": e.id, "value": {"plan": best.id},
                        "evidence": [h for h in (e.title_handle, best.title_handle) if h],
                        "reason": f"Chiều ngang khung hình gần bằng nhau ({we:.0f} và {wp:.0f} mm, lệch {rel:.0%}).",
                        "confidence": round(0.9 - rel, 2), "agent": "links"})
    # materials: dòng ghi chú có cả bộ phận và vật liệu ("- THÙNG, CÁNH, HẬU TỦ MDF 17MM …")
    for g in d.groups:
        for h, t in _item_texts(d, g):
            for line in re.split(r"[\n;]|\\P", t):
                if not materials_in(line):
                    continue
                note = line.strip(" -")[:120]
                for mat, comps in _clauses(line):
                    out.append({"kind": "item_material", "target": g,
                                "value": {"material": mat, "component": ", ".join(comps) or None, "note": note},
                                "evidence": [h], "reason": f"Ghi chú: “{note[:100]}”.",
                                "confidence": 0.8 if comps else 0.6, "agent": "materials"})
    return out + scope_proposals(d, supp)


def _comps(text: str) -> list[str]:
    u = _up(text)
    return [c for c, cf in _COMP_FOLD.items() if re.search(rf"\b{re.escape(cf)}\b", u)]


def _clauses(line: str) -> list[tuple[str, list[str]]]:
    """Tách ghi chú theo dấu phẩy: mỗi vế có vật liệu thì nhận các bộ phận của vế đó + bộ phận của các vế đứng trước chưa có
    vật liệu. 'THÙNG, CÁNH, HẬU TỦ MDF' -> MDF: thùng, cánh, hậu; 'KHUNG NHÔM, CÁNH KÍNH, TAY NẮM' -> Nhôm: khung;
    Kính: cánh (tay nắm không có vật liệu: bỏ). Vật liệu đầu của vế là vật liệu chính (lớp phủ nằm trong ghi chú)."""
    from .graph import _MAT_RX

    res: dict[str, list[str]] = {}
    pending: list[str] = []
    for part in re.split(r"[,，]", line):
        f = _fold(part)
        u = _up(part)  # bộ phận khớp GIỮ DẤU; vật liệu khớp trên chữ bỏ dấu (cùng độ dài, vị trí so được)
        comps = sorted(((m.start(), c) for c, cf in _COMP_FOLD.items() for m in re.finditer(rf"\b{re.escape(cf)}\b", u)))
        mats = sorted(((m.start(), k) for k, rx in _MAT_RX for m in [rx.search(f)] if m))
        if not mats:
            pending += [c for _p, c in comps if c not in pending]
            continue
        first = mats[0][1]
        res.setdefault(first, [])
        for c in pending:  # bộ phận ở các vế trước chưa có vật liệu: theo vật liệu đầu của vế này
            res[first].append(c)
        pending = []
        for pos, c in comps:  # mỗi bộ phận: vật liệu đứng ngay SAU nó trong vế (không có thì vật liệu gần nhất trước nó)
            after = [k for p, k in mats if p > pos]
            before = [k for p, k in mats if p < pos]
            k = after[0] if after else before[-1]
            res.setdefault(k, []).append(c)
    return [(k, list(dict.fromkeys(v))) for k, v in res.items()]


def _key_marker(d: Drawing2D, plan, label: str) -> str | None:
    """Khối ký hiệu trong khung mặt bằng có một thuộc tính đúng bằng nhãn mặt đứng (không phân biệt hoa thường)."""
    if not plan.box:
        return None
    x0, y0, x1, y1 = plan.box
    px, py = 0.1 * (x1 - x0), 0.1 * (y1 - y0)
    for h, e in d.entities.items():
        if e.type != "INSERT" or not e.insert or not e.attribs:
            continue
        if not (x0 - px <= e.insert[0] <= x1 + px and y0 - py <= e.insert[1] <= y1 + py):
            continue
        if any(isinstance(v, str) and v.strip().casefold() == label for v in e.attribs.values()):
            return h
    return None


ARCH_WIDTH = 10000  # mặt bằng rộng hơn 10 m: mặt bằng kiến trúc (cả tầng), không phải một món đồ


def scope_proposals(d: Drawing2D, supp: dict) -> list[dict]:
    """Hạng mục có vẻ là kiến trúc (mọi mặt bằng > 10 m, không dựng được khối): đề xuất bỏ khỏi dựng 3D/bóc tách."""
    from .scene.assemble import build_item_scene

    out = []
    for g, info in d.groups.items():
        plans = [v for v in d.views_of(g, "plan") if v.box]
        if not plans or min(_box_w(p) or 0 for p in plans) < ARCH_WIDTH:
            continue
        try:
            sc = build_item_scene(d, g, supp)
        except Exception:  # noqa: BLE001
            continue
        if sc.modules:
            continue
        out.append({"kind": "item_scope", "target": g, "value": {"scope": "architecture"},
                    "evidence": [h for h in (plans[0].title_handle,) if h],
                    "reason": f"Mọi mặt bằng của “{_vi(str(info.get('name') or g))}” rộng hơn 10 m (cả tầng) và không có "
                              "khối tủ: có vẻ là hồ sơ kiến trúc/định vị, không phải đồ nội thất.",
                    "confidence": 0.7, "agent": "review"})
    return out


# ---------------- AI (source = llm) ----------------

SYSTEM = """Bạn là kỹ sư hồ sơ bản vẽ nội thất. Nhiệm vụ: {task}
Chỉ dựa vào dữ liệu JSON được cho. Mỗi đề xuất PHẢI có "evidence": danh sách handle lấy đúng từ dữ liệu, và "reason" ngắn
bằng tiếng Việt. Không bịa số, không bịa handle. Không chắc thì không đề xuất.
Trả về DUY NHẤT một đối tượng JSON: {{"proposals": [ ... ]}} theo mẫu: {shape}"""

TASKS = {
    "views": ("phân loại các hình chưa có tiêu đề (mặt bằng/mặt đứng/mặt cắt/chi tiết/trần/ảnh) dựa vào chữ quanh hình, tên tờ, "
              "kích thước khung hình.",
              '{"kind":"view_kind","target":"<view>","value":{"kind":"plan|elevation|section|detail|ceiling|image",'
              '"title":"<tiêu đề gợi ý>"},"evidence":["<handle chữ>"],"reason":"...","confidence":0.0-1.0}'),
    "links": ("với mỗi mặt đứng, chọn mặt bằng tương ứng trong 'candidates' (cùng tủ, nhìn từ trên xuống).",
              '{"kind":"link_views","target":"<elevation>","value":{"plan":"<plan trong candidates>"},"evidence":[],'
              '"reason":"...","confidence":0.0-1.0}'),
    "materials": ("đọc ghi chú và gán vật liệu cho từng bộ phận của hạng mục (thùng, cánh, hậu, mặt, khung…).",
                  '{"kind":"item_material","target":"<item>","value":{"material":"<tên vật liệu>","component":"<bộ phận>",'
                  '"note":"<trích ghi chú>"},"evidence":["<handle ghi chú>"],"reason":"...","confidence":0.0-1.0}'),
    "review": ("soát nhất quán từng hạng mục (thiếu hình, kích thước bất thường cho đồ nội thất, khối thiếu cánh…). Chỉ nhận xét.",
               '{"kind":"issue","target":"<node: item mã hoặc module:...>","value":{"message":"<nhận xét>"},'
               '"evidence":[],"reason":"...","confidence":0.0-1.0}'),
}


def _parse(reply: str) -> list[dict]:
    s = reply.strip()
    m = re.search(r"\{.*\}", s, re.S)
    if not m:
        raise GraphAiError("AI không trả JSON.")
    try:
        data = json.loads(m.group(0))
    except ValueError:
        raise GraphAiError("AI trả JSON hỏng.") from None
    if isinstance(data, dict) and "reply" in data and isinstance(data["reply"], str):  # một số CLI bọc trả lời
        return _parse(data["reply"])
    props = data.get("proposals") if isinstance(data, dict) else None
    if not isinstance(props, list):
        raise GraphAiError("AI trả sai lược đồ (thiếu proposals).")
    return [p for p in props if isinstance(p, dict)][:MAX_PROPOSALS]


def llm_proposals(backend, d: Drawing2D, supp: dict, agent: str) -> list[dict]:
    ctx = context(d, supp, agent)
    if not any(ctx.values()):
        return []
    task, shape = TASKS[agent]
    reply = backend.complete(SYSTEM.format(task=task, shape=shape),
                             [{"role": "user", "content": json.dumps(ctx, ensure_ascii=False)}])
    out = []
    for p in _parse(reply):
        p = {k: p.get(k) for k in ("kind", "target", "value", "evidence", "reason", "confidence")}
        p["agent"] = agent
        out.append(p)
    return out


# ---------------- harness ----------------

def check(p: dict, d: Drawing2D) -> tuple[bool, str, dict]:
    """(đạt, lý do nếu không, đề xuất đã chuẩn hoá). Không đạt = không bao giờ hiện cho người dùng."""
    kind, target, val = p.get("kind"), p.get("target"), p.get("value")
    ev = [str(h).upper() for h in (p.get("evidence") or []) if isinstance(h, (str, int))][:20]
    try:
        conf = max(0.0, min(1.0, float(p.get("confidence") or 0.5)))
    except (TypeError, ValueError):
        conf = 0.5
    reason = str(p.get("reason") or "")[:300]
    if not isinstance(val, dict) or not isinstance(target, str):
        return False, "Thiếu đích hoặc giá trị.", p
    ents = d.entities
    frames = {str(s.frame_handle).upper() for s in d.structure.sheets}
    view_ids = {v.id.upper(): v.id for v in d.views} | {s.id.upper(): s.id for s in d.structure.sheets}
    if any(h not in ents and h not in frames and h not in view_ids for h in ev):
        return False, "Bằng chứng trỏ tới handle không có trong bản vẽ.", p
    ev = [view_ids.get(h, h) for h in ev]
    flags: list[str] = []
    norm: dict[str, Any] = {}
    if kind == "view_kind":
        v = d.view(target)
        if v is None:
            return False, "Hình không tồn tại.", p
        if v.kind != "untitled":
            return False, "Hình đã có loại (code đọc được), không đề xuất đè.", p
        if val.get("kind") not in KINDS:
            return False, "Loại hình ngoài danh sách.", p
        norm = {"kind": val["kind"], "title": str(val.get("title") or "")[:120]}
        sheets = {v.sheet_id}
        if any(ents[h].type in ("TEXT", "MTEXT") and d.structure.sheet_of.get(h) not in sheets for h in ev if h in ents):
            return False, "Chữ làm bằng chứng nằm ở tờ khác.", p
    elif kind == "link_views":
        e, pl = d.view(target), d.view(str(val.get("plan") or ""))
        if e is None or pl is None or e.kind != "elevation" or pl.kind != "plan":
            return False, "Cần đúng một mặt đứng và một mặt bằng có thật.", p
        if e.group != pl.group or not e.group:
            return False, "Mặt đứng và mặt bằng khác hạng mục.", p
        we, wp = _box_w(e), _box_w(pl)
        if not we or not wp:
            return False, "Không đo được khung hình.", p
        rel = abs(we - wp) / max(we, wp)
        if rel > LINK_TOL:
            flags.append(f"Chiều ngang hai hình lệch {rel:.0%}: xem kỹ trước khi đồng ý.")
            conf = min(conf, 0.4)
        norm = {"plan": pl.id}
    elif kind == "item_material":
        if target not in d.groups:
            return False, "Hạng mục không tồn tại.", p
        mat = str(val.get("material") or "").strip()[:60]
        if not mat:
            return False, "Thiếu tên vật liệu.", p
        sheets = set(d.groups[target].get("sheets") or [])
        texts = [_txt(d, ents[h]) for h in ev if h in ents and ents[h].text and d.structure.sheet_of.get(h) in sheets]
        if not texts:
            return False, "Vật liệu phải dẫn chứng bằng ghi chú trên tờ của hạng mục.", p
        tokens = [w for w in re.split(r"[\s/,()]+", _fold(mat)) if len(w) >= 2]
        if tokens and not any(any(w in _fold(t) for w in tokens) for t in texts) and not any(
                k in materials_in(" ".join(texts)) for k in [mat]):
            return False, "Ghi chú dẫn chứng không nhắc tới vật liệu này.", p
        comp = val.get("component")
        norm = {"material": mat, "component": str(comp)[:60] if comp else None, "note": str(val.get("note") or "")[:160]}
    elif kind == "item_scope":
        if target not in d.groups:
            return False, "Hạng mục không tồn tại.", p
        if val.get("scope") not in ("architecture", "furniture"):
            return False, "Phạm vi không hợp lệ.", p
        norm = {"scope": val["scope"]}
    elif kind == "issue":
        node = target
        ok = (node in d.groups) or (node.startswith("module:") and node.split(":")[1] in d.groups) or d.view(node) is not None
        if not ok:
            return False, "Nhận xét không trỏ tới hạng mục/khối/hình có thật.", p
        msg = str(val.get("message") or "").strip()[:300]
        if not msg:
            return False, "Nhận xét rỗng.", p
        norm = {"message": msg}
    else:
        return False, "Loại đề xuất không hợp lệ.", p
    flags = list(dict.fromkeys([*(p.get("flags") or []), *flags]))[:5]
    out = {"id": _pid(kind, target, norm), "kind": kind, "target": target, "value": norm, "evidence": ev,
           "reason": reason, "confidence": round(conf, 2), "flags": flags, "agent": p.get("agent"),
           "sources": [p.get("source") or "llm"], "status": "proposed"}
    return True, "", out


# ---------------- chạy, quyết định ----------------

def run(d: Drawing2D, supp: dict, root: Path, file_hash: str, *, backend=None, agents: tuple[str, ...] = AGENTS,
        progress=None) -> dict:
    """Chạy gợi ý code + AI (nếu có backend), qua harness, gộp vào kho đề xuất (giữ quyết định cũ)."""
    store = load_proposals(root, file_hash)
    old = {x["id"]: x for x in store["items"]}
    raw: list[dict] = [{**p, "source": "code"} for p in code_proposals(d, supp) if p["agent"] in agents]
    runs = [{"agent": "code", "ok": True, "n": len(raw), "at": time.strftime("%Y-%m-%d %H:%M:%S")}]
    if backend is not None:
        for a in agents:
            if progress:
                progress(a)
            try:
                got = llm_proposals(backend, d, supp, a)
                raw += [{**p, "source": "llm"} for p in got]
                runs.append({"agent": a, "ok": True, "n": len(got), "backend": getattr(backend, "name", "llm")})
            except Exception as exc:  # noqa: BLE001 - một agent lỗi không làm hỏng các agent khác
                runs.append({"agent": a, "ok": False, "error": str(exc)[:200], "backend": getattr(backend, "name", "llm")})
    items: dict[str, dict] = {}
    rejected = []
    for p in raw[: MAX_PROPOSALS * 2]:
        ok, why, q = check(p, d)
        if not ok:
            rejected.append({"kind": p.get("kind"), "target": str(p.get("target"))[:60], "why": why,
                             "source": p.get("source")})
            continue
        if q["id"] in items:  # cùng đề xuất từ code và AI: gộp nguồn, lấy độ tin cao hơn
            cur = items[q["id"]]
            cur["sources"] = sorted(set(cur["sources"]) | set(q["sources"]))
            cur["confidence"] = max(cur["confidence"], q["confidence"])
            continue
        prev = old.get(q["id"])
        if prev and prev.get("status") in ("confirmed", "dismissed"):
            q["status"] = prev["status"]
        items[q["id"]] = q
    _merge_materials(items)
    _flag_conflicts(items)
    store["items"] = sorted(items.values(), key=lambda x: (x["status"] != "proposed", -x["confidence"]))[:MAX_PROPOSALS]
    store["rejected"] = rejected[:200]
    store["runs"] = runs
    store["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _write(_paths(root, file_hash)[0], store)
    return store


def _merge_materials(items: dict[str, dict]) -> None:
    """AI và code cùng đọc một ghi chú vật liệu: giữ MỘT thẻ (của code, bộ phận chuẩn hoá), thêm thông số chi tiết AI đọc
    được (`spec`, vd. 'MDF 17MM chống ẩm phủ laminate Formica mã 0871') và nguồn AI."""
    code = [x for x in items.values() if x["kind"] == "item_material" and "code" in x["sources"]]
    for q in [x for x in items.values() if x["kind"] == "item_material" and x["sources"] == ["llm"]]:
        keys = materials_in(q["value"]["material"])
        for c in code:
            if c["target"] == q["target"] and set(c["evidence"]) & set(q["evidence"]) and c["value"]["material"] in keys:
                spec = q["value"]["material"]
                if _fold(spec) != _fold(c["value"]["material"]):
                    c["value"]["spec"] = spec if not c["value"].get("spec") or len(spec) > len(c["value"]["spec"]) else c["value"]["spec"]
                c["sources"] = sorted(set(c["sources"]) | {"llm"})
                c["confidence"] = max(c["confidence"], q["confidence"])
                items.pop(q["id"], None)
                break


def _flag_conflicts(items: dict[str, dict]) -> None:
    """Hai đề xuất khác nhau cho cùng một hình (loại hình, ghép hình) hoặc cùng hạng mục (phạm vi): đánh dấu, hạ độ tin."""
    by: dict[tuple[str, str], list[dict]] = {}
    for x in items.values():
        if x["kind"] in ("view_kind", "link_views", "item_scope") and x["status"] == "proposed":
            by.setdefault((x["kind"], x["target"]), []).append(x)
    for group in by.values():
        if len(group) < 2:
            continue
        for x in group:
            x["flags"] = list(dict.fromkeys([*x.get("flags", []), "Mâu thuẫn: có đề xuất khác cho cùng mục này, chỉ đồng ý một."]))
            x["confidence"] = min(x["confidence"], 0.5)


def decide(model, root: Path, pid: str, accept: bool) -> dict:
    """Người dùng Đồng ý / Bỏ một đề xuất. Đồng ý mới ghi dữ liệu (phần bổ sung 3D hoặc overrides của đồ thị)."""
    fh = model.file_hash
    store = load_proposals(root, fh)
    p = next((x for x in store["items"] if x["id"] == pid), None)
    if p is None:
        raise GraphAiError("Không có đề xuất này (bản vẽ đã đổi?). Bấm 'AI đề xuất bổ sung' lại.")
    if accept:
        if p["kind"] == "link_views":
            from .app import scene_api

            item = (scene_api._drawing(model).view(p["target"]) or None)
            try:
                scene_api.set_value(model, root, item.group if item else None, f"link:{p['target']}", p["value"]["plan"])
            except scene_api.SceneApiError as exc:
                raise GraphAiError(f"Không ghi được ghép hình: {exc}") from None
        else:
            ov = load_overrides(root, fh)
            if p["kind"] == "view_kind":
                ov["view_kind"][p["target"]] = {**p["value"], "proposal": pid}
            elif p["kind"] == "item_material":
                ov["materials"] = [m for m in ov["materials"] if m.get("proposal") != pid] + [
                    {"item": p["target"], **p["value"], "evidence": p["evidence"], "proposal": pid}]
            elif p["kind"] == "item_scope":
                ov.setdefault("scope", {})[p["target"]] = p["value"]["scope"]
            elif p["kind"] == "issue":
                ov["issues"] = [m for m in ov["issues"] if m.get("proposal") != pid] + [
                    {"node": p["target"], **p["value"], "proposal": pid}]
            _write(_paths(root, fh)[1], ov)
    p["status"] = "confirmed" if accept else "dismissed"
    p["decided"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if accept and p["kind"] in ("view_kind", "link_views", "item_scope"):
        for x in store["items"]:
            if x is not p and x["kind"] == p["kind"] and x["target"] == p["target"] and x["status"] == "proposed":
                x["status"], x["decided"] = "dismissed", p["decided"]
    _write(_paths(root, fh)[0], store)
    return p


def overrides_key(root: Path, file_hash: str) -> str:
    ov = load_overrides(root, file_hash)
    return hashlib.sha256(json.dumps(ov, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:8]


__all__ = ["AGENTS", "SCHEMA", "apply_overrides", "check", "code_proposals", "context", "decide", "llm_proposals",
           "load_overrides", "load_proposals", "overrides_key", "run"]
