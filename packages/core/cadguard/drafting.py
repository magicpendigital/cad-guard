"""Hồ sơ trình bày `cg.drafting-profile/1`: cách MỘT công ty / người vẽ trình bày bản vẽ, để code đọc đúng kiểu đó.

Mỗi người kỹ thuật vẽ một kiểu (thân tủ trên layer "nét thấy", khung tên không ghi số bản vẽ, "TẤM FIX" là tấm bù…).
Thay vì viết lại bản vẽ, CAD Guard học CÁCH HIỂU một lần, người dùng duyệt, rồi code dùng cho mọi bản vẽ của kiểu đó.

- `layer_roles`: {layer: vai trò} ghi đè cách đoán theo tên layer (`scene/views2d.ROLES`).
- `number_tag`: thẻ thuộc tính khung tên chứa số bản vẽ (rỗng = tự dò; không có số thì nhóm hạng mục theo tiêu đề hình).
- `keywords`: [{text, meaning}] chữ ghi chú trên mặt đứng và nghĩa (MEANINGS), vd. "TẤM FIX" -> filler (tấm bù, không
  phải tủ). Có bộ mặc định (nguồn "Mặc định"), người dùng thêm/bỏ.

Lưu cả máy (`<config>/drafting.yaml`) hoặc riêng dự án (`.cadguard/drafting.yaml`), có nhật ký. Đề xuất bằng code
(`propose_code`) và bằng AI (`propose_ai` + `check`): mọi đề xuất phải dẫn bằng chứng có thật trong bản vẽ (layer có
tồn tại, chữ có xuất hiện); chỉ khi người dùng Đồng ý mới ghi vào hồ sơ. Bản vẽ không bị sửa.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "cg.drafting-profile/1"
FILE = "drafting.yaml"
MEANINGS = {
    "filler": "Tấm bù / tấm fix đo thực tế (không phải tủ)",
    "appliance": "Thiết bị đặt vào tủ (tủ lạnh, lò, máy rửa bát…)",
    "open": "Khoang hở (không cánh)",
    "drawer": "Ngăn kéo / hộc kéo",
    "glass": "Kính / gương",
    "light": "Đèn",
    "stone": "Đá (mặt đá, đá ốp)",
    "rod": "Thanh treo quần áo",
    "curve": "Khấu / bo cong (cạnh tấm cắt cong, xem chi tiết)",
    "joint": "Mối ghép (ghép mòi 45°…), chỉ là ghi chú",
}
DEFAULT_KEYWORDS = [
    {"text": "TẤM FIX", "meaning": "filler"}, {"text": "TẤM BÙ", "meaning": "filler"},
    {"text": "TỦ LẠNH", "meaning": "appliance"}, {"text": "LÒ VI SÓNG", "meaning": "appliance"},
    {"text": "LÒ NƯỚNG", "meaning": "appliance"}, {"text": "MÁY RỬA BÁT", "meaning": "appliance"},
    {"text": "KHOANG HỞ", "meaning": "open"}, {"text": "NGĂN KÉO", "meaning": "drawer"}, {"text": "HỘC", "meaning": "drawer"},
    {"text": "KÍNH", "meaning": "glass"}, {"text": "GƯƠNG", "meaning": "glass"}, {"text": "ĐÈN", "meaning": "light"},
    {"text": "MẶT ĐÁ", "meaning": "stone"}, {"text": "ĐÁ CĐT", "meaning": "stone"}, {"text": "ĐÁ NHÂN TẠO", "meaning": "stone"},
    {"text": "ĐÁ MARBLE", "meaning": "stone"}, {"text": "ĐÁ GRANITE", "meaning": "stone"}, {"text": "ĐÁ THẠCH ANH", "meaning": "stone"},
    {"text": "THANH TREO", "meaning": "rod"}, {"text": "TREO ĐỒ", "meaning": "rod"}, {"text": "ỐNG TREO", "meaning": "rod"},
    {"text": "KHẤU", "meaning": "curve"}, {"text": "BO CONG", "meaning": "curve"}, {"text": "BO TRÒN", "meaning": "curve"},
    {"text": "GHÉP MÒI", "meaning": "joint"}, {"text": "GHÉP 45", "meaning": "joint"}, {"text": "MÒI 45", "meaning": "joint"},
]
ROLE_VI = {"wall": "tường", "furniture": "thân đồ nội thất", "cut": "nét cắt", "hidden": "nét khuất", "thin": "nét mảnh",
           "visible": "nét thấy", "door": "cửa", "dim": "kích thước", "text": "chữ", "symbol": "ký hiệu", "hatch": "hatch",
           "frame": "khung tên", "other": "khác"}


def up(s: str) -> str:
    """Chữ hoa, gọn khoảng trắng, giữ dấu (so khớp ghi chú tiếng Việt)."""
    return " ".join(unicodedata.normalize("NFC", s or "").upper().split())


# ---------------- lưu / nạp ----------------

def paths(project_root: Path | None) -> dict[str, Path]:
    from .app.settings import config_dir

    out = {"machine": config_dir() / FILE}
    if project_root is not None:
        out["project"] = Path(project_root) / ".cadguard" / FILE
    return out


def _read(p: Path) -> dict:
    try:
        d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return d if isinstance(d, dict) and d.get("schema") == SCHEMA else {}


def effective(project_root: Path | None = None) -> dict:
    """Hồ sơ đang dùng: mặc định ← cả máy ← dự án. `origin` cho biết từng mục lấy từ đâu."""
    p = paths(project_root)
    roles: dict[str, str] = {}
    origin: dict[str, str] = {}
    kws = {up(k["text"]): {**k, "origin": "default"} for k in DEFAULT_KEYWORDS}
    number_tag, removed = "", set()
    for scope in ("machine", "project"):
        if scope not in p:
            continue
        d = _read(p[scope])
        for la, r in (d.get("layer_roles") or {}).items():
            roles[la], origin[f"layer:{la}"] = r, scope
        for k in d.get("keywords") or []:
            if isinstance(k, dict) and k.get("text") and k.get("meaning") in MEANINGS:
                kws[up(k["text"])] = {"text": up(k["text"]), "meaning": k["meaning"], "origin": scope}
        removed |= {up(x) for x in d.get("removed_keywords") or []}
        if d.get("number_tag"):
            number_tag = str(d["number_tag"])
            origin["number_tag"] = scope
    confirmed = any(scope in p and p[scope].is_file() for scope in ("machine", "project"))
    return {"schema": SCHEMA, "layer_roles": roles, "number_tag": number_tag,
            "keywords": [k for t, k in sorted(kws.items()) if t not in removed], "origin": origin, "confirmed": confirmed}


def save(project_root: Path | None, scope: str, patch: dict) -> dict:
    """Ghép `patch` ({layer_roles, keywords, removed_keywords, number_tag}) vào hồ sơ của phạm vi `scope`."""
    from .scene.views2d import ROLES

    if scope not in ("machine", "project") or (scope == "project" and project_root is None):
        raise ValueError("Phạm vi lưu phải là 'machine' (cả máy) hoặc 'project' (dự án đang mở).")
    path = paths(project_root)[scope]
    cur = _read(path) or {"schema": SCHEMA}
    roles = dict(cur.get("layer_roles") or {})
    for la, r in (patch.get("layer_roles") or {}).items():
        if r == "reset":
            roles.pop(la, None)
        elif r in ROLES and isinstance(la, str) and 0 < len(la) <= 255:
            roles[la] = r
        else:
            raise ValueError(f"Vai trò layer không hợp lệ: {r}")
    kws = {up(k["text"]): k for k in cur.get("keywords") or [] if isinstance(k, dict) and k.get("text")}
    for k in patch.get("keywords") or []:
        t = up(str(k.get("text", "")))
        if not t or len(t) > 60 or k.get("meaning") not in MEANINGS:
            raise ValueError("Từ khoá phải có chữ (≤ 60 ký tự) và nghĩa trong danh sách.")
        kws[t] = {"text": t, "meaning": k["meaning"]}
    removed = {up(x) for x in cur.get("removed_keywords") or []} | {up(x) for x in patch.get("removed_keywords") or []}
    removed -= set(kws)
    data = {"schema": SCHEMA, "layer_roles": roles, "keywords": list(kws.values()), "removed_keywords": sorted(removed)}
    tag = patch.get("number_tag", cur.get("number_tag", ""))
    if tag:
        data["number_tag"] = str(tag)[:40]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=True), encoding="utf-8")
    with (path.parent / "drafting-log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "scope": scope, "patch": patch}, ensure_ascii=False) + "\n")
    return effective(project_root)


def reset(project_root: Path | None, scope: str) -> dict:
    p = paths(project_root).get(scope)
    if p is not None and p.is_file():
        p.unlink()
    return effective(project_root)


def read(model, project_root: Path | None = None):
    """Đọc bản vẽ 2D theo hồ sơ trình bày đang dùng (vai trò layer, thẻ số bản vẽ, nghĩa từ khoá)."""
    from .scene.views2d import read_drawing

    prof = effective(project_root)
    d = read_drawing(model, roles=prof["layer_roles"] or None, number_tag=prof["number_tag"] or None)
    d.keywords = prof["keywords"]
    return d


# ---------------- đề xuất ----------------

def _texts(d) -> list[tuple[str, str, str]]:
    """(handle, chữ đã giải mã TCVN3, mã hạng mục) của chữ trong hình mặt đứng/mặt bằng các hạng mục."""
    from .scene.explain import _vi

    out = []
    for v in d.views:
        if not v.group or v.kind not in ("elevation", "plan", "section"):
            continue
        for h in v.handles:
            e = d.entities[h]
            if e.type in ("TEXT", "MTEXT") and e.text:
                out.append((h, up(_vi(e.text)), v.group))
    return out


def _layer_use(d) -> dict[str, dict]:
    """Số nét (LINE/LWPOLYLINE/ARC) của từng layer trong hình mặt đứng/mặt bằng các hạng mục."""
    use: dict[str, dict] = {}
    for v in d.views:
        if not v.group or v.kind not in ("elevation", "plan"):
            continue
        for h in v.handles:
            e = d.entities[h]
            if e.type in ("LINE", "LWPOLYLINE", "ARC", "CIRCLE"):
                u = use.setdefault(e.layer, {"lines": 0, "role": d.roles.get(e.layer, "other"), "sample": h})
                u["lines"] += 1
    return use


def propose_code(d, prof: dict) -> list[dict]:
    """Gợi ý bằng code: layer nét thấy/khác mang phần lớn nét của hình hạng mục mà layer nội thất gần như trống ->
    vai trò thân đồ; chữ ghi chú trên bản vẽ khớp nghĩa đã biết nhưng chưa có trong hồ sơ."""
    out = []
    use = _layer_use(d)
    furn = sum(u["lines"] for u in use.values() if u["role"] in ("furniture", "cut"))
    for la, u in sorted(use.items(), key=lambda kv: -kv[1]["lines"]):
        if u["role"] in ("visible", "other", "thin") and la not in prof["layer_roles"] and u["lines"] >= 8 and u["lines"] > 2 * furn:
            out.append({"kind": "layer_role", "target": la, "value": "furniture", "evidence": [u["sample"]], "origin": "code",
                        "reason": f"Layer “{la}” có {u['lines']} nét trong mặt đứng/mặt bằng các hạng mục, layer nội thất/nét cắt "
                                  f"chỉ có {furn}: nhiều khả năng thân tủ vẽ trên layer này."})
    known = {up(k["text"]) for k in prof["keywords"]}
    seen = set()
    for h, t, _g in _texts(d):
        for k in DEFAULT_KEYWORDS:
            if up(k["text"]) in t and up(k["text"]) not in known and up(k["text"]) not in seen:
                seen.add(up(k["text"]))
                out.append({"kind": "keyword", "target": up(k["text"]), "value": k["meaning"], "evidence": [h], "origin": "code",
                            "reason": f"Bản vẽ có ghi chú “{t[:50]}”."})
    return out


AI_SYSTEM = (
    "Bạn giúp CAD Guard hiểu CÁCH TRÌNH BÀY bản vẽ nội thất của một công ty (mỗi người vẽ một kiểu). Dựa trên danh sách "
    "layer (vai trò code đang đoán, số nét trong hình hạng mục) và ghi chú trên bản vẽ, đề xuất: (1) vai trò đúng cho layer "
    "đoán sai, role thuộc {roles}; (2) từ khoá ghi chú và nghĩa, meaning thuộc {meanings}. Chỉ đề xuất điều có trong dữ liệu; "
    "mỗi đề xuất kèm evidence là handle mẫu đã cho. Trả JSON {{\"proposals\": [{{\"kind\": \"layer_role\"|\"keyword\", "
    "\"target\": \"<tên layer hoặc chữ khoá>\", \"value\": \"<role hoặc meaning>\", \"evidence\": [\"<handle>\"], "
    "\"reason\": \"<ngắn, tiếng Việt>\"}}]}}.")


def ai_context(d, prof: dict) -> dict:
    use = _layer_use(d)
    texts = _texts(d)
    return {"layers": [{"layer": la, "role": u["role"], "lines_in_item_views": u["lines"], "sample_handle": u["sample"]}
                       for la, u in sorted(use.items(), key=lambda kv: -kv[1]["lines"])[:60]],
            "notes": [{"handle": h, "text": t[:80], "item": g} for h, t, g in texts[:200]],
            "known_keywords": prof["keywords"]}


def propose_ai(backend, d, prof: dict) -> list[dict]:
    from .scene.views2d import ROLES

    reply = backend.complete(AI_SYSTEM.format(roles=", ".join(ROLES), meanings=", ".join(MEANINGS)),
                             [{"role": "user", "content": json.dumps(ai_context(d, prof), ensure_ascii=False)}])
    m = re.search(r"\{.*\}", reply or "", re.S)
    try:
        raw = json.loads(m.group(0)).get("proposals", []) if m else []
    except ValueError:
        raw = []
    return [{**p, "origin": "llm"} for p in raw if isinstance(p, dict)][:40]


def check(p: dict, d, prof: dict) -> tuple[bool, str]:
    """Harness: đề xuất chỉ hiện cho người dùng khi bằng chứng có thật trong bản vẽ."""
    from .scene.views2d import ROLES

    kind, target, value = p.get("kind"), p.get("target"), p.get("value")
    ev = [str(h).upper() for h in (p.get("evidence") or []) if isinstance(h, (str, int))]
    if kind == "layer_role":
        if not isinstance(target, str) or target not in d.roles:
            return False, "layer không có trong bản vẽ"
        if value not in ROLES:
            return False, "vai trò không hợp lệ"
        if value == d.roles.get(target) and target not in prof["layer_roles"]:
            return False, "trùng vai trò code đang dùng"
        if not any(h in d.entities and d.entities[h].layer == target for h in ev):
            return False, "bằng chứng không phải nét của layer này"
        return True, ""
    if kind == "keyword":
        t = up(str(target or ""))
        if not t or len(t) > 60 or value not in MEANINGS:
            return False, "từ khoá hoặc nghĩa không hợp lệ"
        texts = {h: tx for h, tx, _g in _texts(d)}
        if not any(h in texts and t in texts[h] for h in ev):
            return False, "chữ này không có trong ghi chú được dẫn"
        return True, ""
    return False, "loại đề xuất không hỗ trợ"


def propose(d, prof: dict, backend=None) -> dict:
    """Chạy code (+ AI nếu có), qua harness, gộp trùng. Trả {items, rejected}."""
    raw = propose_code(d, prof)
    if backend is not None:
        raw += propose_ai(backend, d, prof)
    items, rejected, seen = [], [], set()
    for p in raw:
        ok, why = check(p, d, prof)
        key = (p.get("kind"), up(str(p.get("target"))) if p.get("kind") == "keyword" else p.get("target"))
        if not ok:
            rejected.append({"kind": p.get("kind"), "target": p.get("target"), "why": why, "origin": p.get("origin")})
            continue
        if key in seen:
            continue
        seen.add(key)
        items.append({"id": f"{p['kind']}:{key[1]}", "kind": p["kind"], "target": key[1], "value": p["value"],
                      "reason": str(p.get("reason") or "")[:300], "origin": p.get("origin", "code"),
                      "evidence": [str(h).upper() for h in p.get("evidence") or []][:5]})
    return {"items": items, "rejected": rejected[:30]}


def patch_for(item: dict) -> dict:
    if item["kind"] == "layer_role":
        return {"layer_roles": {item["target"]: item["value"]}}
    return {"keywords": [{"text": item["target"], "meaning": item["value"]}]}


def meaning_of(text: str, keywords: list[dict]) -> str | None:
    t = up(text)
    hits = [k for k in keywords if up(k["text"]) in t]
    return max(hits, key=lambda k: len(k["text"]))["meaning"] if hits else None


__all__ = ["DEFAULT_KEYWORDS", "MEANINGS", "ROLE_VI", "SCHEMA", "check", "effective", "meaning_of", "patch_for", "propose",
           "read", "reset", "save"]
