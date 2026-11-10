"""Sửa hàng loạt: gom mọi thao tác tự sửa được của bản vẽ thành MỘT changeset, xem trước, bắt buộc sao lưu, áp dụng.

Vẫn giữ đủ rào của AGENTS.md: (1) `plan` chỉ chạy khô, trả xem trước; (2) `apply` cần người bấm xác nhận VÀ
`backup=True`: tệp gốc được sao nguyên byte vào `<dự án>/.cadguard/backups/` trước khi làm gì; (3) kết quả ghi ra
TỆP MỚI, kiểm lại (validate_output), hoàn tác được như changeset thường.

Chỉ gom thao tác an toàn: thao tác gợi ý mặc định đã tick (`checked`) và mọi ô chọn đã có giá trị. Thao tác cần người
chọn (layer đích, kiểu chữ đích) hoặc đụng khung tên (template) KHÔNG tự gom: liệt kê ở `skipped` để người làm tiếp.
Chuyển Unicode (nếu bản vẽ có chữ TCVN3/VNI) chạy ĐẦU TIÊN: đổi kiểu chữ trước sẽ làm mất dấu hiệu phông để giải mã.
"""
from __future__ import annotations

import hashlib
import shutil
import time
from typing import Any

BACKUP_DIR = ".cadguard/backups"
PRIMARY_STD = "design-hygiene-v0"
TEMPLATE_OPS = {"replace_title_block", "set_sheet_scale", "fit_sheet", "set_attribs"}


def _ready(o: dict) -> bool:
    op = o["op"]
    return all(op.get(f) for f in (o.get("choices") or {}))


def _base(name: str) -> str:
    """Tên gốc của layer xref, kể cả xref lồng nhiều tầng: phần sau dấu '|' hoặc '$0$' CUỐI cùng."""
    for sep in ("|", "$0$"):
        if sep in name:
            name = name.rsplit(sep, 1)[1]
    return name.strip()


def _auto_target(o: dict, existing: set[str], renamed: set[str] | None = None) -> dict:
    """Layer dư từ xref chưa có layer gốc để gộp: đổi tên về tên gốc (bỏ tiền tố xref) — tất định, không mất đối tượng.
    Tên gốc vừa được thao tác trước đặt (`renamed`) thì gộp vào đó. Tên gốc đã có sẵn thì để người chọn."""
    op = o["op"]
    if op["op"] != "merge_layers" or op.get("target") or len(op.get("sources") or []) != 1:
        return o
    src = op["sources"][0]
    base = _base(src)
    if not base or base == src:
        return o
    if renamed and base.casefold() in renamed:
        return {**o, "op": {**op, "target": base}, "choices": {}, "checked": True,
                "title": f"Gộp layer '{src}' vào '{base}'",
                "description": "Layer dư từ xref trùng tên gốc với layer vừa đổi tên: chuyển đối tượng sang đó."}
    if base.casefold() in existing:
        return o
    return {**o, "op": {"op": "rename_layer", "from": src, "to": base}, "choices": {}, "checked": True,
            "title": f"Đổi tên layer '{src}' thành '{base}'",
            "description": "Layer dư từ xref đã gộp: bỏ tiền tố xref, giữ nguyên mọi đối tượng trên layer."}


def plan(app, rel: Any, standards: list[str], *, unicode: bool = True) -> dict:
    """Gom thao tác từ mọi chuẩn của phòng + Unicode, chạy khô một changeset gộp. Không ghi bản vẽ."""
    from .api import ApiError, propose_changeset, suggest_ops

    if not standards:
        raise ApiError("Phòng này chưa có chuẩn kiểm nên chưa có gì để sửa hàng loạt.")
    picked: list[dict] = []
    skipped: list[dict] = []
    manual: list[dict] = []
    seen: set[str] = set()
    taken: set[str] = set()
    for std in standards:
        s = suggest_ops(app, rel, std)
        layers = {la.name.casefold() for la in app.model(app.resolve(rel)).layers}
        for o in s["ops"]:
            o = _auto_target(o, layers | taken, taken)
            if o["op"]["op"] == "rename_layer":
                taken.add(o["op"]["to"].casefold())
            key = repr(sorted(o["op"].items()))
            if key in seen:
                continue
            seen.add(key)
            if o["op"]["op"] == "convert_unicode":
                (picked if unicode else skipped).append({**o, "why_skipped": None if unicode else "Bạn không chọn chuyển Unicode."})
                continue
            if o["op"]["op"] in TEMPLATE_OPS or o["rule_id"] == "TP-10":
                skipped.append({**o, "why_skipped": "Đụng khung tên: làm riêng ở tab Thay đổi để xem kỹ từng tờ."})
            elif not _ready(o):
                skipped.append({**o, "why_skipped": "Cần bạn chọn giá trị (vd. layer đích) trước khi sửa."})
            elif not o.get("checked"):
                skipped.append({**o, "why_skipped": "Không bật mặc định vì dễ sai; xem và bật tay ở tab Thay đổi."})
            else:
                picked.append(o)
        manual += [n for n in s["notes"] if n not in manual]
    order = {"convert_unicode": 0, "rename_layer": 3, "merge_layers": 4, "purge_unused": 9}
    picked.sort(key=lambda o: order.get(o["op"]["op"], 5))
    if not picked:
        return {"file": rel, "picked": [], "skipped": skipped, "manual": manual, "preview": None}
    std = PRIMARY_STD if PRIMARY_STD in standards else standards[0]
    pv = propose_changeset(app, rel, std, [o["op"] for o in picked])
    return {"file": rel, "standard": std, "picked": picked, "skipped": skipped, "manual": manual, "preview": pv}


def backup_source(app, rel: str) -> dict:
    """Sao nguyên byte tệp gốc vào `.cadguard/backups/<tên>.<thời điểm>.<8 hex>.<đuôi>`; kiểm mã băm bản sao."""
    src = app.resolve(rel)
    d = app.ws.root / BACKUP_DIR
    d.mkdir(parents=True, exist_ok=True)
    data_hash = _sha(src)
    dst = d / f"{src.stem}.{time.strftime('%Y%m%d-%H%M%S')}.{data_hash[:8]}{src.suffix}"
    shutil.copy2(src, dst)
    if _sha(dst) != data_hash:
        dst.unlink(missing_ok=True)
        raise OSError("bản sao lưu không khớp mã băm")
    return {"path": app.rel(dst), "sha256": data_hash, "bytes": dst.stat().st_size}


def _sha(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def apply(app, cid: Any, confirm: Any, backup: Any) -> dict:
    """Sao lưu bắt buộc rồi áp changeset gộp ra tệp mới."""
    from .api import ApiError, apply_changeset, get_changeset

    if confirm is not True:
        raise ApiError("Cần bạn bấm xác nhận trước khi sửa hàng loạt.", 409)
    if backup is not True:
        raise ApiError("Sửa hàng loạt bắt buộc tạo bản sao lưu bản vẽ gốc trước.", 409)
    cs = get_changeset(app, cid)
    try:
        bk = backup_source(app, cs["source"]["path"])
    except OSError as exc:
        raise ApiError(f"Không tạo được bản sao lưu ({type(exc).__name__}); chưa sửa gì.", 500) from None
    res = apply_changeset(app, cid, True)
    return {**res, "backup": bk}


__all__ = ["BACKUP_DIR", "apply", "backup_source", "plan"]
