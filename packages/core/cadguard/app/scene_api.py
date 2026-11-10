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
from ..scene.views2d import read_drawing

STORE = ".cadguard/scene"
MAX_BOXES = 5000


class SceneApiError(ValueError):
    pass


def _paths(root: Path, file_hash: str) -> tuple[Path, Path]:
    d = root / STORE
    return d / f"{file_hash[:16]}.cgsup.json", d / f"{file_hash[:16]}.proposals.json"


def read_supplement(root: Path, file_hash: str) -> dict:
    sp, _ = _paths(root, file_hash)
    if not sp.is_file():
        return {}
    vals, _note = load_supplement(json.loads(sp.read_text(encoding="utf-8")), file_hash)
    return vals


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _drawing(model):
    return read_drawing(model)


def build(model, root: Path, item: str | None):
    d = _drawing(model)
    supp = read_supplement(root, model.file_hash)
    g = item if item in d.groups else best_item(d)
    if g is None:
        return None, d, supp
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
        "items": [{**x, "name": _vi(str((d.groups.get(x["id"]) or {}).get("name") or ""))} for x in item_summary(d)],
        "readiness": readiness(sc),
        "boxes": [{"b": [list(p) for p in b.base], "z0": b.z0, "z1": b.z1, "c": list(color_for(b.material)), "k": b.kind, "n": b.name}
                  for b in bx[:MAX_BOXES]],
        "truncated": len(bx) > MAX_BOXES,
        "modules": [{"id": m.id, "kind": m.kind, "label": m.label, "fronts": len(m.fronts), "shelves": m.shelves,
                     **{k: {"value": getattr(m, k), "src": SRC_LABEL.get(m.src[k].kind, m.src[k].kind) if k in m.src else "?"}
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
    }


def _vi(s: str) -> str:
    """Tên lấy từ khung tên có thể còn mã TCVN3/VNI: giải mã để hiển thị."""
    from ..textcodec import decode

    if not s or any(ord(c) > 0xFF for c in s) or not any(ord(c) >= 0xA0 for c in s):
        return s
    letters = [c for c in s if c.isalpha() and ord(c) < 0x80]
    upper = bool(letters) and all(c.isupper() for c in letters)  # tên khung tên thường gõ phông hoa (VnAvantH…)
    return decode(s, "tcvn3-upper" if upper else "tcvn3")[0]


KIND_VI = {"plan": "Mặt bằng", "elevation": "Mặt đứng", "section": "Mặt cắt", "detail": "Chi tiết"}


def _sheet_name(d, sheet_id: str) -> str:
    s = next((x for x in d.structure.sheets if x.id == sheet_id), None)
    if s is None:
        return sheet_id
    return " · ".join(x for x in (s.name, s.title) if x) or sheet_id


def _view_vi(d, vid: str) -> str:
    v = d.view(vid)
    if v is None:
        return vid
    return f"{KIND_VI.get(v.kind, 'Hình')} “{v.title or v.label or v.id}” (tờ {_sheet_name(d, v.sheet_id)})"


def explain_gap(g, d, sc) -> dict:
    """Giải thích phần thiếu bằng lời của người làm thiết kế: ở đâu, vì sao, làm gì (trong CAD Guard / trong AutoCAD).

    Mã nội bộ (V:…, M1) chỉ nằm trong `message`; `explain` không bắt người dùng hiểu mã."""
    if g.id.startswith("link:"):
        e = _view_vi(d, g.target)
        if g.kind == "ambiguous":
            return {"where": e, "title": "Có nhiều mặt bằng khớp với mặt đứng này",
                    "why": "CAD Guard tìm thấy hơn một mặt bằng ghi cùng kích thước ngang nên không tự chọn.",
                    "fix_here": "Chọn mặt bằng đúng trong ô bên dưới rồi bấm Lưu.",
                    "fix_cad": "Đặt tiêu đề mặt bằng rõ ràng (vd. 'MẶT BẰNG TỦ BẾP - TẦNG DƯỚI') để phân biệt."}
        return {"where": e, "title": "Chưa đặt được mặt đứng lên mặt bằng",
                "why": "Để biết tủ trên mặt đứng nằm ở đâu trên mặt bằng, CAD Guard cần một kích thước tổng chiều ngang "
                       "ghi ở CẢ hai hình với cùng số đo. Hai hình này không có kích thước chung như vậy.",
                "fix_here": "Chọn mặt bằng tương ứng ở ô bên dưới rồi bấm Lưu: CAD Guard căn theo mép trái hai hình "
                            "(nhanh, có thể lệch nếu hai hình không cùng mép).",
                "fix_cad": "Trong AutoCAD: ghi kích thước tổng chiều ngang tủ ở cả mặt bằng và mặt đứng (cùng một số), "
                           "lưu, rồi quét lại. Cách này chính xác và dùng được cho các bước sau (bóc tách, sản xuất)."}
    if g.id.startswith("module:"):
        m = g.target
        wall = "tủ treo" in g.message
        return {"where": f"Khối {m} của hạng mục {sc.item}", "title": "Thiếu chiều sâu tủ",
                "why": "Chiều sâu lấy từ mặt bằng: CAD Guard tìm nét " + ("KHUẤT (nét đứt, tủ treo phía trên)" if wall else
                       "LIỀN của thân tủ") + " nằm thẳng hàng với khối trên mặt đứng. Không thấy nét như vậy.",
                "fix_here": "Nhập chiều sâu (mm) ở ô bên dưới. Thường gặp: " + ("tủ treo 300–350" if wall else
                            "tủ dưới 560–600, tủ áo 550–600") + ".",
                "fix_cad": "Trong AutoCAD: vẽ đường bao tủ trên mặt bằng đúng loại nét " + ("khuất" if wall else "liền")
                           + " và ghi kích thước chiều sâu, lưu, quét lại."}
    if g.id.startswith("item:"):
        grp = d.groups.get(g.target) or {}
        has = [_view_vi(d, v.id) for v in d.views_of(g.target)][:6]
        missing = "mặt bằng" if "thiếu mặt bằng" in g.message else "mặt đứng"
        return {"where": f"Hạng mục {g.target}" + (f" · {_vi(str(grp.get('name')))}" if grp.get("name") else ""),
                "title": f"Hạng mục chưa có {missing}",
                "why": f"Dựng khối cần ít nhất một mặt bằng và một mặt đứng cùng mã hạng mục. CAD Guard không thấy {missing} "
                       "nào của hạng mục này (nhận theo tiêu đề hình và số bản vẽ trong khung tên).",
                "fix_here": "Chọn hạng mục khác ở ô 'Hạng mục' để xem; hạng mục này tạm bỏ qua.",
                "fix_cad": f"Kiểm tờ có {missing} của hạng mục: tiêu đề hình phải bắt đầu bằng '"
                           + ("MẶT BẰNG" if missing == "mặt bằng" else "MẶT ĐỨNG")
                           + "', và số bản vẽ trong khung tên phải cùng tiền tố mã hạng mục.",
                "views": has}
    if g.id == "room:ceiling":
        return {"where": "Phòng", "title": "Thiếu cao độ sàn – trần",
                "why": "Cao trần lấy từ kích thước đứng trên mặt cắt/mặt đứng (từ sàn tới trần).",
                "fix_here": "Nhập cao sàn–trần (mm) ở ô bên dưới, vd. 2700.",
                "fix_cad": "Ghi kích thước sàn – trần trên mặt cắt hoặc mặt đứng, lưu, quét lại."}
    return {"where": g.target, "title": "Thiếu dữ liệu", "why": g.message,
            "fix_here": "Nhập giá trị ở ô bên dưới nếu có.", "fix_cad": "Bổ sung kích thước còn thiếu trong bản vẽ rồi quét lại."}


def readiness(sc) -> dict:
    """Mức sẵn sàng của hạng mục cho các bước sau (số khối có đủ rộng/sâu/cao/cao độ, nguồn từ kích thước hay đo hình)."""
    total = len(sc.modules)
    full = sum(1 for m in sc.modules if all(k in m.src for k in ("w", "d", "h", "z0")))
    by_dim = sum(1 for m in sc.modules for k in ("w", "d", "h", "z0") if k in m.src and m.src[k].kind == "dimension")
    by_user = sum(1 for m in sc.modules for k in ("w", "d", "h", "z0") if k in m.src and m.src[k].kind == "user")
    n = max(1, total * 4)
    level = "chưa dựng" if not total else ("đủ để xem hình khối" if not sc.gaps else "còn phần thiếu")
    return {"modules": total, "complete": full, "from_dimension_pct": round(100 * by_dim / n),
            "from_user_pct": round(100 * by_user / n), "gaps": len(sc.gaps), "level": level}


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
    if f == "link":
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
    vals = dict(supp)
    vals[key] = sval
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


__all__ = ["SceneApiError", "add_proposals", "glb", "has_items", "prompt", "read_supplement", "set_value", "view"]
