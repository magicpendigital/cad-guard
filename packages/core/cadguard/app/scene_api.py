"""App: cảnh 3D `cg.scene/2` theo hạng mục, nhập phần thiếu, xác nhận đề xuất ghép/nhãn, tải GLB (cùng mã cảnh).

Lưu cục bộ trong thư mục dự án: `.cadguard/scene/<băm bản vẽ>.cgsup.json` (giá trị người nhập/xác nhận, lược đồ
`cg.supplement/1`, gắn băm bản vẽ) và `.proposals.json` (đề xuất LLM chờ xác nhận). Bản vẽ không bị sửa.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from ..scene.assemble import Scene2, best_item, build_item_scene, item_summary
from ..scene.build import SUPPLEMENT_SCHEMA, load_supplement
from ..scene.geometry import boxes2
from ..scene.gltf import color_for
from ..scene.proposals import SCHEMA as PROPOSALS_SCHEMA
from ..scene.proposals import prompt_for, validate
from ..scene.render2 import SRC_LABEL, build_glb2
from ..scene.explain import _view_vi, _vi, explain_gap, readiness  # noqa: F401 - dùng lại
from ..scene.views2d import read_drawing

STORE = ".cadguard/scene"
MAX_BOXES = 5000


class SceneApiError(ValueError):
    pass


def _paths(root: Path, file_hash: str) -> tuple[Path, Path]:
    d = root / STORE
    return d / f"{file_hash[:16]}.cgsup.json", d / f"{file_hash[:16]}.proposals.json"


SCOPED = ("module:", "label:", "room:")  # khoá theo khối/phòng: mã khối M1… lặp lại giữa các hạng mục -> lưu kèm mã hạng mục


def scoped_key(key: str, item: str) -> str:
    return f"{item}|{key}" if key.startswith(SCOPED) else key


def item_supp(raw: dict, item: str) -> dict:
    """Số bổ sung áp cho một hạng mục: khoá chung (cũ, không kèm mã) rồi khoá riêng của hạng mục đè lên."""
    out = {k: v for k, v in raw.items() if "|" not in k}
    out.update({k.split("|", 1)[1]: v for k, v in raw.items() if k.startswith(item + "|")})
    return out


def read_supplement(root: Path, file_hash: str) -> dict:
    sp, _ = _paths(root, file_hash)
    if not sp.is_file():
        return {}
    vals, _note = load_supplement(json.loads(sp.read_text(encoding="utf-8")), file_hash)
    return vals


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _drawing(model, root: Path | None = None):
    """Đọc bản vẽ theo hồ sơ trình bày của công ty (vai trò layer, thẻ số bản vẽ, nghĩa ghi chú)."""
    from ..drafting import read

    return read(model, root)


def build(model, root: Path, item: str | None):
    from ..graph_ai import apply_overrides, load_overrides

    d = apply_overrides(_drawing(model, root), load_overrides(root, model.file_hash))  # loại hình người dùng đã xác nhận
    raw = read_supplement(root, model.file_hash)
    g = item if item in d.groups else best_item(d)
    if g is None:
        return None, d, raw
    supp = item_supp(raw, g)
    sc = build_item_scene(d, g, supp)
    sc.source_hash = model.file_hash
    sc.scene_hash = sc.compute_hash()
    return sc, d, supp


def has_items(model) -> bool:
    d = _drawing(model)
    return any(x["plans"] and x["elevations"] for x in item_summary(d))


def view(model, root: Path, item: Any = None) -> dict:
    sc, d, supp = build(model, root, item if isinstance(item, str) else None)
    if sc is None:
        raise SceneApiError("Bản vẽ không có hạng mục (khung tên có số bản vẽ) để dựng 3D theo cách mới.")
    _, pp = _paths(root, model.file_hash)
    pending = []
    if pp.is_file():
        data = json.loads(pp.read_text(encoding="utf-8"))
        if data.get("source_hash") == model.file_hash:
            pending = [p for p in data.get("items", []) if p.get("item") == sc.item and supp.get(p.get("key")) != p.get("value")]
    bx = boxes2(sc)
    return {
        "schema": "cg.scene/2", "item": sc.item, "scene_hash": sc.scene_hash,
        "items": [{**x, "name": _vi(str((d.groups.get(x["id"]) or {}).get("name") or "")), "sheet_names": _sheet_names(d, x["id"])}
                  for x in item_summary(d)],
        "readiness": readiness(sc),
        "boxes": [{"b": [list(p) for p in b.base], "z0": b.z0, "z1": b.z1, "c": list(color_for(b.material)), "k": b.kind, "n": b.name}
                  for b in bx[:MAX_BOXES]],
        "truncated": len(bx) > MAX_BOXES,
        "modules": [{"id": m.id, "kind": m.kind, "form": m.form, "type_vi": _type_vi(m), "label": m.label, "fronts": len(m.fronts),
                     "shelves": m.shelves,
                     "x": m.x, "y": m.y,
                     **{k: {"value": getattr(m, k), "src": SRC_LABEL.get(m.src[k].kind, m.src[k].kind) if k in m.src else "?",
                            "kind": m.src[k].kind if k in m.src else "missing"}
                        for k in ("w", "d", "h", "z0")}} for m in sc.modules],
        "room": {"ceiling": sc.room.ceiling, "src": SRC_LABEL.get(sc.room.src["ceiling"].kind) if "ceiling" in sc.room.src else None},
        "links": [lk.model_dump() for lk in sc.links],
        "gaps": [{"id": g.id, "kind": g.kind, "message": g.message,
                  "fields": [{**f.model_dump(), "labels": {o: _view_vi(d, o) for o in (f.options or []) if d.view(o)}}
                             for f in g.fields],
                  "explain": explain_gap(g, d, sc)} for g in sc.gaps],
        "proposals": pending,
        "counts": {"modules": len(sc.modules), "fronts": sum(len(m.fronts) for m in sc.modules), "walls": len(sc.walls),
                   "gaps": len(sc.gaps)},
        "notes": sc.notes[:10],
        "provenance": provenance(sc, d, supp),
        **production(sc, root, model.file_hash),
    }


def production(sc, root: Path, file_hash: str) -> dict:
    """P3: tấm ván (3 kiểu xem), danh sách cắt, bản lề theo hồ sơ kết cấu xưởng (mặc định nếu chưa khai)."""
    from ..construction import effective
    from ..graph_ai import load_overrides
    from ..scene.panels import boxes as panel_boxes
    from ..scene.panels import cutlist, panels_for

    prof = effective(root)
    c = prof["values"]
    ps = panels_for(sc, c)
    mats = [m for m in load_overrides(root, file_hash).get("materials", []) if m.get("item") == sc.item]
    return {"panels": {k: panel_boxes(ps, k)[:MAX_BOXES] for k in ("panel", "explode", "xray")},
            "cutlist": cutlist(ps, c, mats),
            "construction": {"confirmed": prof["confirmed"],
                             "summary": f"ván {c['board_thickness']} mm, hậu {'bắt vít' if c['back_type'] == 'screw' else 'rãnh'} "
                                        f"{c['back_thickness']} mm, cánh {'trùm toàn' if c['door_overlay'] == 'full' else ('trùm nửa' if c['door_overlay'] == 'half' else 'lọt')}, "
                                        f"khe {c['door_gap']} mm"}}


def cutlist_file(model, root: Path, item: Any) -> dict:
    from ..scene.panels import cutlist_csv

    sc, _d, _supp = build(model, root, item if isinstance(item, str) else None)
    if sc is None:
        raise SceneApiError("Không có hạng mục.")
    cl = production(sc, root, model.file_hash)["cutlist"]
    name = f"danh-sach-cat-{sc.item}.csv".replace(":", "-")
    return {"name": name, "csv": chr(0xFEFF) + cutlist_csv(cl)}


def provenance(sc, d, supp: dict) -> dict:
    """Đối chiếu 2D ↔ 3D: dựng từ hình nào, tờ nào; mặt đứng nào chưa dùng; từng số đo của khối lấy từ đâu."""
    used_e = sorted({m.elevation for m in sc.modules if m.elevation})
    used_p = sorted({m.plan for m in sc.modules if m.plan})
    all_e = [v.id for v in d.views_of(sc.item, "elevation") if v.box]
    linked = {lk.elevation for lk in sc.links}
    views = {}
    for vid in set(used_e) | set(used_p) | set(all_e):
        v = d.view(vid)
        if v is not None:
            views[vid] = {"id": vid, "label": _view_vi(d, vid), "kind": v.kind, "sheet": v.sheet_id,
                          "box": [round(x, 1) for x in v.box] if v.box else None,
                          "handles": _body_handles(d, v)}  # "Tới trong AutoCAD": chọn nét của hình để phóng tới
    return {
        "item_name": _vi(str((d.groups.get(sc.item) or {}).get("name") or sc.item)),
        "sheets": [{"id": s, "label": _sheet_label(d, s)} for s in (d.groups.get(sc.item) or {}).get("sheets") or []],
        "used": {"elevations": used_e, "plans": used_p},
        "elevations": [{"id": e, "label": views[e]["label"], "linked": e in linked, "used": e in used_e} for e in all_e if e in views],
        "views": views,
        "main_pick": supp.get(f"main:{sc.item}"),
        "modules": {m.id: {"elevation": m.elevation, "plan": m.plan, "ebox": m.ebox,
                           "refs": {k: (m.src[k].refs if k in m.src else []) for k in ("w", "d", "h", "z0")},
                           "handles": [h for h in m.refs if h][:200],
                           "user": [k for k in ("w", "d", "h", "z0") if f"module:{m.id}:{k}" in supp]} for m in sc.modules},
    }


TYPE_VI = {"base": "Tủ dưới", "wall": "Tủ treo", "tall": "Tủ cao"}
FORM_VI = {"open": "Kệ mở", "panel": "Tấm ốp", "filler": "Tấm bù (đo thực tế)"}


def _type_vi(m) -> str:
    """Loại khối bằng lời: tủ dưới/treo/cao (theo cao độ) hoặc kệ mở/tấm ốp (theo nét trên mặt đứng)."""
    if m.form in FORM_VI:
        return FORM_VI[m.form] + (" treo" if m.kind == "wall" else "")
    return TYPE_VI.get(m.kind, m.kind)


def _sheet_names(d, item: str) -> str:
    """Tên ngắn các tờ của hạng mục, vd. "Tờ 3, 4, 5" (để biết tìm ở đâu trong tệp)."""
    names = []
    for sid in (d.groups.get(item) or {}).get("sheets") or []:
        s = next((x for x in d.structure.sheets if x.id == sid), None)
        names.append((s.name if s and s.name else sid).strip())
    nums = [n[3:].strip() for n in names if n.lower().startswith("tờ ")]
    if names and len(nums) == len(names):
        return "Tờ " + ", ".join(nums)
    return ", ".join(names)


def _body_handles(d, v) -> list[str]:
    roles = {"furniture", "cut", "wall", "hidden", "thin", "visible"}
    return [h for h in v.handles if d.roles.get(d.entities[h].layer) in roles][:400]


def _sheet_label(d, sid: str) -> str:
    from ..scene.explain import _sheet_name

    s = _sheet_name(d, sid)
    return s if len(s) <= 70 else s[:68] + "…"


def source_geometry(model, root: Path, item: Any, view_id: Any) -> dict:
    """Hình 2D của MỘT hình chiếu (mặt đứng/mặt bằng) để xem cạnh 3D: nét, chữ, kích thước, theo toạ độ bản vẽ."""
    sc, d, _supp = build(model, root, item if isinstance(item, str) else None)
    if sc is None:
        raise SceneApiError("Không có hạng mục.")
    v = d.view(view_id) if isinstance(view_id, str) else None
    if v is None or v.group != sc.item or not v.box:
        raise SceneApiError("Hình chiếu không thuộc hạng mục.")
    items = []
    for h in v.handles[:6000]:
        e = d.entities.get(h)
        if e is None:
            continue
        r = lambda q: [round(q[0], 1), round(q[1], 1)]  # noqa: E731
        if e.type == "LINE" and e.pts and len(e.pts) >= 2:
            items.append([h, "L", r(e.pts[0]) + r(e.pts[1])])
        elif e.type == "LWPOLYLINE" and e.pts and len(e.pts) >= 2:
            items.append([h, "Q" if e.closed else "P", [c for q in e.pts for c in r(q)]])
        elif e.type in ("CIRCLE",) and e.pts and e.radius:
            items.append([h, "C", r(e.pts[0]) + [round(e.radius, 1)]])
        elif e.type == "ARC" and e.arc is not None:
            cx, cy, rad, a0, a1 = e.arc
            items.append([h, "A", [round(cx, 1), round(cy, 1), round(rad, 1), round(a0, 1), round(a1, 1)]])
        elif e.type == "DIMENSION" and e.dim_value is not None and e.pos:
            pts = [c for q in (e.dim_pts or [])[:2] for c in r(q)]
            items.append([h, "D", r(e.pos) + [round(float(e.dim_value), 1)] + pts])
        elif e.text and (e.pos or e.insert):
            from ..scene.explain import _vi

            items.append([h, "T", r(e.pos or e.insert) + [_vi(e.text)[:60], round(float(e.text_height or 0), 1)]])
    return {"view": v.id, "label": _view_vi(d, v.id), "box": [round(x, 1) for x in v.box], "items": items,
            "truncated": len(v.handles) > 6000}


def _allowed(sc: Scene2, d, key: str):
    """Ô được phép nhập: khoá của phần thiếu hiện tại, khoá ghép mặt đứng của hạng mục, nhãn khối."""
    for g in sc.gaps:
        for f in g.fields:
            if f.key == key:
                return f
    if key.startswith("link:"):
        if key[5:] in {v.id for v in d.views_of(sc.item, "elevation")}:
            return "link"
    if key.startswith("label:") and key[6:] in {m.id for m in sc.modules}:
        return "label"
    if key == f"main:{sc.item}":
        return "main"
    parts = key.split(":")
    if len(parts) == 3 and parts[0] == "module" and parts[2] in ("w", "d", "h", "z0") and parts[1] in {m.id for m in sc.modules}:
        return "dim"
    return None


def set_value(model, root: Path, item: Any, key: Any, value: Any) -> dict:
    if not isinstance(key, str) or not isinstance(value, (str, int, float)) or len(str(value)) > 80:
        raise SceneApiError("Thiếu khoá hoặc giá trị.")
    sc, d, supp = build(model, root, item if isinstance(item, str) else None)
    if sc is None:
        raise SceneApiError("Không có hạng mục.")
    f = _allowed(sc, d, key)
    if f is None:
        raise SceneApiError("Khoá không thuộc phần thiếu của cảnh hiện tại.")
    sval = str(value).strip()
    if sval == "reset" and f in ("dim", "main"):  # bỏ giá trị người dùng đã sửa: quay về số đo từ bản vẽ
        sp, _ = _paths(root, model.file_hash)
        vals = {k: v for k, v in read_supplement(root, model.file_hash).items() if k not in (key, scoped_key(key, sc.item))}
        _write(sp, {"schema": SUPPLEMENT_SCHEMA, "source_hash": model.file_hash, "origin": "user", "values": vals})
        return view(model, root, sc.item)
    if f == "main":
        if sval not in {lk.elevation for lk in sc.links}:
            raise SceneApiError("Mặt đứng chưa ghép với mặt bằng nên chưa dựng được từ nó.")
    elif f == "dim":
        try:
            num = float(sval.replace(",", "."))
        except ValueError:
            raise SceneApiError("Giá trị phải là số (mm).") from None
        if not (0 <= num < 100000) or (num == 0 and not key.endswith(":z0")):
            raise SceneApiError("Giá trị ngoài khoảng hợp lệ (mm).")
        sval = f"{num:g}"
    elif f == "link":
        if sval not in {v.id for v in d.views_of(sc.item, "plan")}:
            raise SceneApiError("Mặt bằng không thuộc hạng mục.")
    elif f == "label":
        from ..scene.proposals import LABELS

        if sval not in LABELS:
            raise SceneApiError("Nhãn ngoài danh sách.")
    elif f.kind == "choice":
        if sval not in f.options:
            raise SceneApiError("Giá trị ngoài danh sách chọn.")
    else:
        try:
            num = float(sval.replace(",", "."))
        except ValueError:
            raise SceneApiError("Giá trị phải là số (mm).") from None
        if not 0 < num < 100000:
            raise SceneApiError("Giá trị ngoài khoảng hợp lệ (mm).")
        sval = f"{num:g}"
    sp, _ = _paths(root, model.file_hash)
    vals = read_supplement(root, model.file_hash)
    vals.pop(key, None) if key.startswith(SCOPED) else None  # khoá chung cũ: thay bằng khoá riêng của hạng mục
    vals[scoped_key(key, sc.item)] = sval
    _write(sp, {"schema": SUPPLEMENT_SCHEMA, "source_hash": model.file_hash, "origin": "user", "values": vals})
    return view(model, root, sc.item)


def add_proposals(model, root: Path, item: Any, raw: Any) -> dict:
    """Lưu đề xuất (vd. đầu ra LLM) sau khi mã kiểm; trả cả mục bị loại kèm lý do."""
    sc, d, _supp = build(model, root, item if isinstance(item, str) else None)
    if sc is None:
        raise SceneApiError("Không có hạng mục.")
    ok, bad = validate(raw, d, sc.item, sc)
    _, pp = _paths(root, model.file_hash)
    data = {"schema": PROPOSALS_SCHEMA, "source_hash": model.file_hash, "items": []}
    if pp.is_file():
        old = json.loads(pp.read_text(encoding="utf-8"))
        if old.get("source_hash") == model.file_hash:
            data["items"] = [p for p in old.get("items", []) if p.get("item") != sc.item]
    data["items"] += [{**p, "item": sc.item} for p in ok]
    _write(pp, data)
    return {"accepted": ok, "rejected": bad, "scene": view(model, root, sc.item)}


def prompt(model, root: Path, item: Any) -> dict:
    sc, d, _ = build(model, root, item if isinstance(item, str) else None)
    if sc is None:
        raise SceneApiError("Không có hạng mục.")
    return prompt_for(d, sc.item, sc)


def glb(model, root: Path, item: Any) -> dict:
    sc, _d, _ = build(model, root, item if isinstance(item, str) else None)
    if sc is None:
        raise SceneApiError("Không có hạng mục.")
    return {"name": f"canh-{sc.item}-{sc.scene_hash}.glb", "scene_hash": sc.scene_hash,
            "b64": base64.b64encode(build_glb2(sc)).decode("ascii")}


# ---------------- cả tầng (cg.space/1) ----------------

def _space(model, root: Path) -> dict:
    from ..graph_ai import apply_overrides, load_overrides
    from ..scene.space import build_space

    d = apply_overrides(_drawing(model, root), load_overrides(root, model.file_hash))
    raw = read_supplement(root, model.file_hash)
    return build_space(model, d, lambda g: item_supp(raw, g), raw), d


def space_view(model, root: Path) -> dict:
    """Cả tầng: khung phòng + hạng mục đã đặt + đồ rời + cửa; hộp cho trình xem; việc cần làm."""
    from ..scene.space import space_boxes

    sp, d = _space(model, root)
    for it in sp["items"]:
        it["sheet_names"] = _sheet_names(d, it["item"])
    bx = space_boxes(sp)
    plan = sp.get("plan") or {}
    return {**sp, "plan": {**plan, "label": _view_vi(d, plan["id"]) if plan.get("id") else ""},
            "boxes": [{"b": [list(p) for p in b["b"]], "z0": b["z0"], "z1": b["z1"], "c": list(color_for(b["m"])), "k": b["k"], "n": b["n"]}
                      for b in bx[:MAX_BOXES]], "truncated": len(bx) > MAX_BOXES}


def space_set(model, root: Path, key: Any, value: Any) -> dict:
    """Khoá cả tầng: `place:<mã>` = 0|90|180|270|reset (góc xoay hạng mục), `space:ceiling`, `space:door_h` (mm|reset)."""
    if not isinstance(key, str) or not isinstance(value, (str, int, float)) or len(str(value)) > 20:
        raise SceneApiError("Thiếu khoá hoặc giá trị.")
    sval = str(value).strip()
    raw = read_supplement(root, model.file_hash)
    d = _drawing(model, root)
    if key.startswith("place:") and key[6:] in d.groups:
        if sval not in ("0", "90", "180", "270", "reset"):
            raise SceneApiError("Góc xoay phải là 0, 90, 180 hoặc 270.")
    elif key in ("space:ceiling", "space:door_h"):
        if sval != "reset":
            try:
                num = float(sval.replace(",", "."))
            except ValueError:
                raise SceneApiError("Giá trị phải là số (mm).") from None
            if not 1500 <= num <= 6000:
                raise SceneApiError("Giá trị ngoài khoảng hợp lệ (1500–6000 mm).")
            sval = f"{num:g}"
    else:
        raise SceneApiError("Khoá không thuộc cảnh cả tầng.")
    raw.pop(key, None)
    if sval != "reset":
        raw[key] = sval
    sp, _ = _paths(root, model.file_hash)
    _write(sp, {"schema": SUPPLEMENT_SCHEMA, "source_hash": model.file_hash, "origin": "user", "values": raw})
    return space_view(model, root)


def space_glb(model, root: Path) -> dict:
    from ..scene.space import render_space_glb

    sp, _d = _space(model, root)
    return {"name": f"ca-tang-{sp.get('space_hash', '')}.glb", "space_hash": sp.get("space_hash"),
            "b64": base64.b64encode(render_space_glb(sp)).decode("ascii")}


__all__ = ["SceneApiError", "add_proposals", "glb", "has_items", "item_supp", "prompt", "read_supplement", "scoped_key",
           "set_value", "space_glb", "space_set", "space_view", "view"]
