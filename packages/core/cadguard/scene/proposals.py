"""Đề xuất của LLM cho dựng 3D (3D-2): chỉ GHÉP hình chiếu và GÁN NHÃN khối, không bao giờ là số đo.

- `prompt_for(d, group, scene)`: dữ liệu gửi LLM (sau khi người dùng đồng ý theo phiên, như Studio): mã hình chiếu, loại,
  tiêu đề, nhãn, số kích thước và vài số đo lớn nhất của từng hình, khối đã dựng, phần thiếu. Không đường dẫn/tên tệp.
- `validate(raw, d, group, scene)`: mã kiểm từng đề xuất; chỉ nhận `link:<mặt đứng>` = `<mặt bằng>` cùng hạng mục và
  `label:<khối>` = nhãn trong danh sách cho phép. Đề xuất số (sâu, cao, trần…) bị loại: số chỉ đến từ bản vẽ hoặc người nhập.
- Đề xuất hợp lệ được lưu "chờ xác nhận"; chỉ khi người dùng bấm xác nhận trên App mới ghi vào tệp bổ sung (`source: user`).
"""

from __future__ import annotations

import json
import re

from .views2d import Drawing2D, view_dims

SCHEMA = "cg.scene-proposals/1"
LABELS = ("tủ bếp dưới", "tủ bếp trên", "tủ cao", "tủ áo", "kệ tivi", "kệ trang trí", "bàn đảo", "quầy bar", "tủ giày",
          "tủ lavabo", "ghế băng", "ốp tường", "ốp trần", "khác")
MAX_PROPOSALS = 50

SYSTEM = (
    "Bạn hỗ trợ dựng 3D từ bản vẽ nội thất 2D. Chỉ được đề xuất hai loại: (1) ghép mặt đứng với mặt bằng cùng hạng mục: "
    '{"key": "link:<mã mặt đứng>", "value": "<mã mặt bằng>"}; (2) gán nhãn khối: {"key": "label:<mã khối>", '
    '"value": "<một nhãn trong danh sách>"}. KHÔNG đề xuất số đo (sâu, cao, rộng, cao trần): số đo chỉ lấy từ bản vẽ hoặc '
    'người dùng nhập. Trả đúng JSON {"proposals": [{"key", "value", "reason"}]}, lý do ngắn bằng tiếng Việt.')


def prompt_for(d: Drawing2D, group: str, scene) -> dict:
    views = []
    for v in d.views_of(group):
        if v.kind not in ("plan", "elevation", "section"):
            continue
        dims = view_dims(d, v)
        hs = sorted((x.value for x in dims if x.axis == "h"), reverse=True)[:5]
        vs = sorted((x.value for x in dims if x.axis == "v"), reverse=True)[:5]
        views.append({"id": v.id, "kind": v.kind, "title": v.title, "label": v.label, "flags": v.flags,
                      "size": [round(v.box[2] - v.box[0]), round(v.box[3] - v.box[1])] if v.box else None,
                      "dims_h_top": hs, "dims_v_top": vs})
    return {"system": SYSTEM, "labels": list(LABELS), "item": group, "views": views,
            "modules": [{"id": m.id, "kind": m.kind, "w": m.w, "d": m.d, "h": m.h, "z0": m.z0, "fronts": len(m.fronts)}
                        for m in scene.modules],
            "gaps": [{"id": g.id, "kind": g.kind, "message": g.message} for g in scene.gaps]}


def _parse(raw) -> list:
    if isinstance(raw, str):
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return []
        try:
            raw = json.loads(m.group(0))
        except ValueError:
            return []
    if isinstance(raw, dict):
        raw = raw.get("proposals", [])
    return raw if isinstance(raw, list) else []


def validate(raw, d: Drawing2D, group: str, scene) -> tuple[list[dict], list[dict]]:
    """(đề xuất hợp lệ, đề xuất bị loại kèm lý do)."""
    plans = {v.id for v in d.views_of(group, "plan") if v.box}
    elevs = {v.id for v in d.views_of(group, "elevation") if v.box}
    mods = {m.id for m in scene.modules} | {g.target for g in scene.gaps if g.id.startswith("module:")}
    ok, bad = [], []
    for p in _parse(raw)[:MAX_PROPOSALS]:
        if not isinstance(p, dict):
            continue
        key, value = str(p.get("key", ""))[:80], p.get("value")
        reason = str(p.get("reason", ""))[:300]
        why = None
        if key.startswith("link:"):
            if key[5:] not in elevs:
                why = "mặt đứng không thuộc hạng mục"
            elif value not in plans:
                why = "mặt bằng không thuộc hạng mục"
        elif key.startswith("label:"):
            if key[6:] not in mods:
                why = "không có khối này"
            elif value not in LABELS:
                why = "nhãn ngoài danh sách"
        else:
            why = "chỉ nhận ghép hình chiếu hoặc gán nhãn; số đo phải lấy từ bản vẽ hoặc người nhập"
        (bad if why else ok).append({"key": key, "value": value, "reason": reason, **({"rejected": why} if why else {"origin": "llm"})})
    return ok, bad


__all__ = ["LABELS", "SCHEMA", "SYSTEM", "prompt_for", "validate"]
