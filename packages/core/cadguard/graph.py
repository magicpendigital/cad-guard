"""Đồ thị tri thức bản vẽ `cg.drawing-graph/1` (P1, `plans/cad-guard-kg-3d-production.md` mục 3).

Một bản đồ duy nhất của bản vẽ cho mọi bước sau (dựng 3D, bóc tách vật tư, dữ liệu sản xuất, dịch, tái cấu trúc):
tờ → hình (mặt bằng/mặt đứng/mặt cắt…) → hạng mục → khối/tủ, vật liệu được ghi chú, phát hiện của luật.

- P1 chỉ có phần **tất định** (`source: "code"`): đọc từ `sheets.py`, `scene/views2d.py`, `scene/assemble.py`, chữ ghi
  chú (giải mã TCVN3/VNI) và kết quả luật. Mỗi nút/cạnh có `source`, `confidence`, `refs` (handle bằng chứng),
  `status` (`measured` = code đo được; P2 thêm `proposed` của AI và `confirmed` của người dùng).
- **Cổng sẵn sàng** (`gates`): mỗi bước sau có điều kiện đủ; thiếu gì thì có danh sách việc cần làm, mỗi việc nói ở
  đâu, vì sao, sửa nhanh trong CAD Guard thế nào, sửa gốc trong AutoCAD thế nào.

Đồ thị chứa chữ của bản vẽ (tiêu đề, ghi chú): dữ liệu cục bộ, không đưa vào telemetry hay công cụ trợ lý ở chế độ
ẩn danh (P2 sẽ thêm công cụ có lọc ẩn danh).
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any

from .model import DrawingModel
from .scene.assemble import build_item_scene
from .scene.explain import KIND_VI, _sheet_name, _vi, explain_gap
from .scene.views2d import Drawing2D, read_drawing
from .textcodec import drawing_looks_tcvn3, entity_text, style_encodings

SCHEMA = "cg.drawing-graph/1"
MAX_TASKS = 60
MIN_VIEW_ENTITIES = 3  # cụm ít hơn: mảnh lẻ (nét/chữ rơi), không phải hình chiếu
REAL_KINDS = ("plan", "elevation", "section", "detail", "ceiling", "image")

# Vật liệu thường ghi chú trên bản vẽ nội thất (khớp trên chữ HOA đã bỏ dấu). Thứ tự: mẫu đầu tiên khớp thắng.
MATERIALS: tuple[tuple[str, str], ...] = (
    ("MFC", r"\bMFC\b|MELAMIN"),
    ("MDF", r"\bMDF\b|\bHDF\b"),
    ("Plywood", r"PLYWOOD|\bPLY\b|VAN EP"),
    ("Veneer", r"VENEER"),
    ("Laminate", r"LAMINATE|\bHPL\b|FORMICA"),
    ("Acrylic", r"ACRYLIC|\bMICA\b"),
    ("Gỗ tự nhiên", r"\bGO (TU NHIEN|SOI|OC CHO|TEAK|THONG|CAO SU|XOAN|DAO|TRAM|ASH|WALNUT|OAK)"),
    ("Kính", r"\bKINH\b|GLASS"),
    ("Gương", r"\bGUONG\b|MIRROR"),
    ("Đá", r"\bDA (GRANITE|MARBLE|NHAN TAO|THACH ANH|TU NHIEN|SOLID)|GRANITE|MARBLE|QUARTZ|SOLID SURFACE"),
    ("Inox", r"\bINOX\b|STAINLESS"),
    ("Nhôm", r"\bNHOM\b|ALUMIN"),
    ("Thép/sắt", r"\bTHEP\b|\bSAT HOP\b|\bSAT\b|STEEL"),
    ("Sơn", r"\bSON (PU|BET|BONG|MAU|TINH DIEN|NUOC|DAU)|\bSON\b \d|PAINT"),
    ("Vải/da/nỉ", r"\bVAI\b|\bNI\b|\bDA (BO|PU|CONG NGHIEP)|FABRIC|LEATHER"),
    ("Đèn LED", r"\bLED\b"),
)
_MAT_RX = [(k, re.compile(p)) for k, p in MATERIALS]


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").upper()


def materials_in(text: str) -> list[str]:
    """Mọi vật liệu được nêu trong một ghi chú (vd. 'MDF 17MM PHỦ LAMINATE' -> MDF, Laminate)."""
    f = _fold(text)
    return [key for key, rx in _MAT_RX if rx.search(f)]


class _G:
    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []

    def node(self, nid: str, ntype: str, label: str, *, refs: list[str] | None = None, confidence: float = 1.0,
             **attrs: Any) -> dict:
        n = self.nodes.get(nid)
        if n is None:
            n = self.nodes[nid] = {"id": nid, "type": ntype, "label": label, "source": "code", "status": "measured",
                                   "confidence": confidence, "refs": list(refs or [])[:20], "attrs": attrs}
        return n

    def edge(self, a: str, b: str, etype: str, *, refs: list[str] | None = None, confidence: float = 1.0,
             **attrs: Any) -> None:
        self.edges.append({"from": a, "to": b, "type": etype, "source": "code", "status": "measured",
                           "confidence": confidence, "refs": list(refs or [])[:20], "attrs": attrs})


def _texts(model: DrawingModel) -> list[tuple[str, str]]:
    """(handle, chữ đã giải mã) của TEXT/MTEXT/ATTRIB/thuộc tính khối trong Model."""
    encs = style_encodings(model)
    raw = [e.text for e in model.entities if e.text]
    guess: bool | str = "drawing" if drawing_looks_tcvn3(raw) else True
    out = []
    for e in model.entities:
        if e.space != "Model":
            continue
        if e.text:
            t, _src = entity_text(e, encs, guess)
            if t and t.strip():
                out.append((e.handle, t.strip()))
        for v in (e.attribs or {}).values():
            if v and isinstance(v, str) and len(v) > 2:
                out.append((e.handle, v))
    return out


def build_graph(model: DrawingModel, *, drawing: Drawing2D | None = None, supplement: dict | None = None,
                findings: list[dict] | None = None, profile: dict | None = None) -> dict:
    """Dựng đồ thị + cổng sẵn sàng. `findings`: [{std, rule_id, severity, count, handles, message}] (tuỳ chọn).
    `profile`: {"construction": bool} — đã có hồ sơ kết cấu công ty chưa (P3)."""
    d = drawing or read_drawing(model)
    st = d.structure
    g = _G()
    sheet_name = {s.id: _sheet_name(d, s.id) for s in st.sheets}

    # --- tờ
    for s in st.sheets:
        g.node(f"sheet:{s.id}", "sheet", sheet_name[s.id], refs=[s.frame_handle] if s.frame_handle else [],
               confidence=float(s.confidence or 1.0) if isinstance(s.confidence, (int, float)) else 1.0,
               kind=s.kind, title=_vi(s.title or ""), paper=s.paper, scale=s.scale_label, item=d.sheet_group.get(s.id))

    # --- hình chiếu (cụm quá nhỏ = mảnh lẻ)
    fragments: list = []
    for v in d.views:
        if v.kind == "untitled" and len(v.handles) < MIN_VIEW_ENTITIES:
            fragments.append(v)
            continue
        label = f"{KIND_VI.get(v.kind, 'Hình chưa có tiêu đề' if v.kind == 'untitled' else 'Hình')}" + (
            f" “{_vi(v.title)}”" if v.title else "")
        g.node(f"view:{v.id}", "view", label, refs=[v.title_handle] if v.title_handle else v.handles[:3],
               confidence=1.0 if v.kind != "untitled" else 0.3, kind=v.kind, entities=len(v.handles),
               flags=list(v.flags), sheet=v.sheet_id, item=v.group or None)
        g.edge(f"sheet:{v.sheet_id}", f"view:{v.id}", "contains")
        if v.group:
            g.edge(f"view:{v.id}", f"item:{v.group}", "depicts")

    # --- hạng mục + khối (dựng tất định như màn 3D)
    supp = supplement or {}
    scenes: dict[str, Any] = {}
    for grp, info in d.groups.items():
        views = [v for v in d.views_of(grp) if len(v.handles) >= MIN_VIEW_ENTITIES or v.kind != "untitled"]
        kinds = Counter(v.kind for v in views)
        g.node(f"item:{grp}", "item", _vi(str(info.get("name") or grp)), code=grp,
               sheets=list(info.get("sheets") or []), plans=kinds.get("plan", 0), elevations=kinds.get("elevation", 0),
               sections=kinds.get("section", 0), details=kinds.get("detail", 0))
        for sid in info.get("sheets") or []:
            g.edge(f"sheet:{sid}", f"item:{grp}", "belongs_to")
        try:
            sc = build_item_scene(d, grp, supp)
        except Exception:  # noqa: BLE001 - một hạng mục lỗi không làm hỏng cả đồ thị
            sc = None
        scenes[grp] = sc
        if sc is None:
            continue
        for lk in sc.links:
            g.edge(f"view:{lk.elevation}", f"view:{lk.plan}", "aligned_with", refs=lk.refs,
                   confidence=1.0 if lk.method == "dimension" else 0.7, method=lk.method, offset_x=lk.offset_x)
        for m in sc.modules:
            mid = f"module:{grp}:{m.id}"
            g.node(mid, "module", f"{m.id} {m.label or m.kind}", kind=m.kind, w=m.w, d=m.d, h=m.h, z0=m.z0,
                   fronts=len(m.fronts), shelves=m.shelves,
                   src={k: m.src[k].kind for k in ("w", "d", "h", "z0") if k in m.src})
            g.edge(f"item:{grp}", mid, "has_module")

    # --- vật liệu được ghi chú (theo tờ -> hạng mục)
    mats: dict[str, dict] = {}
    for h, text in _texts(model):
        sid = st.sheet_of.get(h)
        grp = d.sheet_group.get(sid) if sid else None
        for key in materials_in(text):
            _mention(mats, key, h, text, grp)
    for key, m in mats.items():
        g.node(f"material:{key}", "material", key, refs=m["refs"], confidence=0.8, mentions=m["count"],
               samples=m["samples"])
        for grp, n in m["items"].items():
            g.edge(f"item:{grp}", f"material:{key}", "mentions", confidence=0.8, count=n)

    # --- phát hiện của luật (gắn vào tờ có handle bằng chứng)
    for f in findings or []:
        fid = f"finding:{f.get('std')}:{f['rule_id']}"
        g.node(fid, "finding", f"{f['rule_id']} · {f.get('message', '')[:80]}", severity=f.get("severity"),
               count=f.get("count", 1), std=f.get("std"))
        for sid in sorted({st.sheet_of.get(h) for h in f.get("handles") or []} - {None}):
            g.edge(fid, f"sheet:{sid}", "on")

    gates = _gates(d, g, scenes, fragments, profile or {})
    real = [n for n in g.nodes.values() if n["type"] == "view"]
    typed = [n for n in real if n["attrs"]["kind"] in REAL_KINDS]
    stats = {
        "sheets": len(st.sheets), "views": len(real), "views_typed": len(typed),
        "views_typed_pct": round(100 * len(typed) / len(real)) if real else 0, "fragments": len(fragments),
        "items": len(d.groups), "items_3d": sum(1 for sc in scenes.values() if sc is not None and sc.modules),
        "modules": sum(1 for n in g.nodes.values() if n["type"] == "module"), "materials": len(mats),
        "nodes": len(g.nodes), "edges": len(g.edges),
        "sheets_without_item": sum(1 for s in st.sheets if s.id not in d.sheet_group),
    }
    return {"schema": SCHEMA, "source_hash": model.file_hash, "stats": stats, "gates": gates,
            "nodes": list(g.nodes.values()), "edges": g.edges, "items": _item_rows(g, scenes)}


def _mention(mats: dict, key: str, h: str, text: str, grp: str | None) -> None:
    m = mats.setdefault(key, {"count": 0, "samples": [], "items": Counter(), "refs": []})
    m["count"] += 1
    if len(m["samples"]) < 5 and text[:80] not in m["samples"]:
        m["samples"].append(text[:80])
    if len(m["refs"]) < 20:
        m["refs"].append(h)
    if grp:
        m["items"][grp] += 1


def _task(gate: str, title: str, where: str, why: str, fix_here: str, fix_cad: str, action: dict | None = None,
          severity: str = "W") -> dict:
    return {"gate": gate, "title": title, "where": where, "why": why, "fix_here": fix_here, "fix_cad": fix_cad,
            "action": action, "severity": severity}


def _gate(gid: str, title: str, done: int, total: int, tasks: list[dict], blocked: bool = False, note: str = "") -> dict:
    status = "blocked" if blocked or total == 0 else ("ok" if done >= total and not any(t["severity"] == "E" for t in tasks) else "partial")
    return {"id": gid, "title": title, "status": status, "done": done, "total": total, "note": note,
            "task_count": len(tasks), "tasks": tasks[:MAX_TASKS]}


def _gates(d: Drawing2D, g: _G, scenes: dict, fragments: list, profile: dict) -> list[dict]:
    st = d.structure
    out = []

    # 1. Cấu trúc hồ sơ: tờ đọc được, hình có loại, tờ thuộc hạng mục, chữ Unicode
    t1: list[dict] = []
    enc = st.encoding or {}
    if enc.get("styles") or enc.get("guessed_tcvn3"):
        t1.append(_task("structure", "Chữ tiếng Việt còn mã cũ (TCVN3/VNI)", "Cả bản vẽ",
                        "Chữ mã cũ làm sai dịch, tìm kiếm, bóc tách theo ghi chú và hiển thị trên máy không có phông cũ.",
                        "Bấm Chuyển Unicode (hoặc Sửa hàng loạt).", "Đổi kiểu chữ sang phông Unicode và gõ lại bằng Unicode.",
                        {"id": "unicode"}, "E"))
    for s in st.sheets:
        if s.id not in d.sheet_group:
            t1.append(_task("structure", "Tờ chưa gắn với hạng mục nào", g.nodes[f"sheet:{s.id}"]["label"],
                            "Số bản vẽ trong khung tên không có tiền tố mã hạng mục, nên tờ này không được dùng khi dựng 3D/bóc tách.",
                            "Bỏ qua nếu là tờ chung (bìa, mục lục, mặt bằng tổng).",
                            "Ghi số bản vẽ theo mẫu <mã hạng mục>.<số tờ> trong khung tên.", {"id": "sheet", "sheet": s.id}, "I"))
    real = [n for n in g.nodes.values() if n["type"] == "view"]
    for n in real:
        if n["attrs"]["kind"] == "untitled":
            t1.append(_task("structure", "Hình chưa có tiêu đề", f"{g.nodes[f'sheet:{n['attrs']['sheet']}']['label']}",
                            f"Cụm {n['attrs']['entities']} đối tượng không có tiêu đề MẶT BẰNG/MẶT ĐỨNG/MẶT CẮT… nên không biết là hình gì.",
                            "P2: trợ lý AI đề xuất loại hình để bạn xác nhận.",
                            "Thêm tiêu đề hình ngay dưới hình vẽ (vd. 'MẶT ĐỨNG A TỦ BẾP').", {"id": "sheet", "sheet": n["attrs"]["sheet"]}))
    typed = sum(1 for n in real if n["attrs"]["kind"] in REAL_KINDS)
    out.append(_gate("structure", "Cấu trúc hồ sơ", typed, len(real), t1,
                     note=f"{len(st.sheets)} tờ, {len(real)} hình ({typed} có loại), {len(fragments)} mảnh lẻ bỏ qua."))

    # 2. Dựng 3D hình khối: hạng mục có mặt bằng + mặt đứng, khối đủ số đo, không phần thiếu
    t2: list[dict] = []
    ok3 = 0
    for grp, sc in scenes.items():
        name = g.nodes[f"item:{grp}"]["label"]
        if sc is None:
            t2.append(_task("3d", "Hạng mục lỗi khi dựng", name, "Lỗi bên trong khi dựng khối.", "Mở 3D hạng mục để xem.",
                            "—", {"id": "open3d", "item": grp}, "E"))
            continue
        if sc.modules and not sc.gaps:
            ok3 += 1
        for gp in sc.gaps:
            ex = explain_gap(gp, d, sc)
            t2.append(_task("3d", ex["title"], ex["where"], ex["why"], ex["fix_here"], ex["fix_cad"],
                            {"id": "open3d", "item": grp}, "W" if sc.modules else "E"))
    out.append(_gate("3d", "Dựng 3D hình khối", ok3, len(scenes), t2,
                     note="Hạng mục đủ: có khối và không còn phần thiếu."))

    # 3. Bóc tách vật tư: hạng mục có khối + có ghi chú vật liệu
    t3: list[dict] = []
    has_mat = {e["from"][5:] for e in g.edges if e["type"] == "mentions"}
    ok_boq = 0
    for grp, sc in scenes.items():
        name = g.nodes[f"item:{grp}"]["label"]
        built = sc is not None and bool(sc.modules)
        if built and grp in has_mat:
            ok_boq += 1
            continue
        if not built:
            t3.append(_task("boq", "Chưa có khối để bóc tách", name, "Bóc tách cần kích thước từng khối/tủ (xem cổng Dựng 3D).",
                            "Bổ sung phần thiếu ở màn 3D của hạng mục.", "Bổ sung mặt bằng/mặt đứng có kích thước.",
                            {"id": "open3d", "item": grp}))
        if grp not in has_mat:
            t3.append(_task("boq", "Chưa thấy ghi chú vật liệu", name,
                            "Không có chữ ghi vật liệu (MFC, MDF, Laminate, kính, đá…) trên các tờ của hạng mục.",
                            "P2: trợ lý AI gán vật liệu từ ghi chú/bảng vật liệu để bạn xác nhận.",
                            "Ghi chú vật liệu + mã màu trên mặt đứng/mặt cắt (vd. 'MFC chống ẩm An Cường 18mm').",
                            {"id": "sheet", "sheet": (g.nodes[f'item:{grp}']['attrs']['sheets'] or [None])[0]}))
    out.append(_gate("boq", "Bóc tách vật tư", ok_boq, len(scenes), t3,
                     note="Đủ: hạng mục có khối và có ghi chú vật liệu. Bảng khối lượng chi tiết làm ở P5."))

    # 4. Dữ liệu sản xuất: cần hồ sơ kết cấu công ty (P3) + bóc tách đủ
    t4: list[dict] = []
    if not profile.get("construction"):
        t4.append(_task("production", "Chưa có hồ sơ kết cấu công ty", "Công ty",
                        "Mô hình tấm, danh sách cắt, dán cạnh, bản lề cần biết xưởng làm hông trùm hay nóc trùm, hậu rãnh "
                        "hay bắt vít, độ dày ván, hãng bản lề/ray. Không có chuẩn quốc gia cho các số này.",
                        "P3: chọn mẫu hồ sơ kết cấu và chỉnh theo xưởng.", "—", None, "E"))
    out.append(_gate("production", "Dữ liệu sản xuất", 0, len(scenes), t4, blocked=not profile.get("construction"),
                     note="Mở ở P3 (mô hình tấm, danh sách cắt/dán cạnh)."))
    return out


def _item_rows(g: _G, scenes: dict) -> list[dict]:
    rows = []
    mats: dict[str, list[str]] = {}
    for e in g.edges:
        if e["type"] == "mentions":
            mats.setdefault(e["from"][5:], []).append(g.nodes[e["to"]]["label"])
    for n in g.nodes.values():
        if n["type"] != "item":
            continue
        grp = n["attrs"]["code"]
        sc = scenes.get(grp)
        rows.append({"id": grp, "name": n["label"], "sheets": len(n["attrs"]["sheets"]), "plans": n["attrs"]["plans"],
                     "elevations": n["attrs"]["elevations"], "sections": n["attrs"]["sections"],
                     "modules": len(sc.modules) if sc else 0, "gaps": len(sc.gaps) if sc else None,
                     "materials": sorted(set(mats.get(grp, []))),
                     "status": "lỗi" if sc is None else ("đủ" if sc.modules and not sc.gaps else
                                                        ("còn phần thiếu" if sc.modules else "chưa dựng được"))})
    return rows


def summary_vi(graph: dict) -> str:
    s = graph["stats"]
    lines = [f"Đồ thị bản vẽ: {s['sheets']} tờ, {s['views']} hình ({s['views_typed_pct']}% có loại), "
             f"{s['items']} hạng mục, {s['modules']} khối, {s['materials']} loại vật liệu được ghi chú."]
    icon = {"ok": "ĐỦ", "partial": "CHƯA ĐỦ", "blocked": "CHƯA MỞ"}
    for gt in graph["gates"]:
        lines.append(f"- {gt['title']}: {icon[gt['status']]} {gt['done']}/{gt['total']} · {gt['task_count']} việc cần làm")
    return "\n".join(lines)


__all__ = ["SCHEMA", "build_graph", "materials_in", "summary_vi"]
