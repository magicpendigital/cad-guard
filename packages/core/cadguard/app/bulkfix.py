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
    pv = _propose(app, rel, std, picked)
    if pv is None or not pv.get("ok"):
        # Gộp không đạt: chia đôi tìm nhóm gây lỗi, giữ phần đạt (ngân sách lượt chạy khô có hạn)
        good, bad = _split(app, rel, std, picked, budget=[SPLIT_BUDGET])
        for o in bad:
            skipped.append({**o, "why_skipped": "Chạy thử riêng không đạt bước tự kiểm: làm tay ở tab Thay đổi."})
        picked = good
        pv = _propose(app, rel, std, picked) if picked else None
    return {"file": rel, "standard": std, "picked": picked, "skipped": skipped, "manual": manual, "preview": pv}


SPLIT_BUDGET = 8  # số lần chạy khô tối đa khi tìm nhóm gây lỗi (bản vẽ lớn ~15 s/lần)


def _propose(app, rel, std, ops: list[dict]) -> dict | None:
    from .api import ApiError, propose_changeset

    try:
        return propose_changeset(app, rel, std, [o["op"] for o in ops])
    except ApiError:
        return None


def _split(app, rel, std, ops: list[dict], budget: list[int]) -> tuple[list[dict], list[dict]]:
    """Chia đôi đệ quy: trả (thao tác đạt, thao tác không đạt). Hết ngân sách thì coi phần chưa thử là không đạt."""
    if not ops:
        return [], []
    if len(ops) == 1:
        if budget[0] <= 0:
            return [], ops
        budget[0] -= 1
        pv = _propose(app, rel, std, ops)
        return (ops, []) if pv and pv.get("ok") else ([], ops)
    half = len(ops) // 2
    out_good, out_bad = [], []
    for part in (ops[:half], ops[half:]):
        if budget[0] <= 0:
            out_bad += part
            continue
        budget[0] -= 1
        pv = _propose(app, rel, std, part)
        if pv and pv.get("ok"):
            out_good += part
        else:
            g, b = _split(app, rel, std, part, budget)
            out_good += g
            out_bad += b
    return out_good, out_bad


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


# ---------- Sửa hàng loạt cả thư mục (chạy nền, báo tiến độ) ----------

_JOBS: dict[str, dict] = {}


def folder_start(app, standards: list[str], confirm: Any, backup: Any, unicode: bool = True) -> dict:
    """Mỗi bản vẽ gốc trong dự án: gom thao tác an toàn, chạy khô; ĐẠT thì sao lưu + ghi tệp mới. Chạy nền."""
    import secrets
    import threading

    from .api import ApiError, list_drawings

    if confirm is not True:
        raise ApiError("Cần bạn bấm xác nhận trước khi sửa hàng loạt cả thư mục.", 409)
    if backup is not True:
        raise ApiError("Sửa hàng loạt bắt buộc tạo bản sao lưu bản vẽ gốc trước.", 409)
    if any(j["state"] == "running" for j in _JOBS.values()):
        raise ApiError("Đang có một lượt sửa cả thư mục chạy; chờ xong rồi chạy tiếp.", 409)
    files = [x["path"] for x in list_drawings(app)["drawings"] if not x["is_output"]]
    jid = "bulk-" + secrets.token_hex(4)
    job = _JOBS[jid] = {"id": jid, "state": "running", "total": len(files), "done": 0, "current": None,
                        "results": [], "started": time.time()}

    def run() -> None:
        for rel in files:
            job["current"] = rel
            r: dict = {"file": rel}
            try:
                p = plan(app, rel, standards, unicode=unicode)
                pv = p["preview"]
                r.update(picked=len(p["picked"]), skipped=len(p["skipped"]), manual=len(p["manual"]))
                if not pv:
                    r["status"] = "không có gì để sửa tự động"
                elif not pv.get("ok"):
                    r["status"] = "xem trước không đạt, bỏ qua"
                else:
                    out = apply(app, pv["changeset_id"], True, True)
                    r.update(status="đã sửa", output=out["output"]["path"], backup=out["backup"]["path"],
                             changeset=out["changeset_id"], resolved=pv["rules"]["resolved"],
                             before=sum(pv["rules"]["before"].values()), after=sum(pv["rules"]["after"].values()))
            except Exception as exc:  # noqa: BLE001 - một tệp lỗi không dừng cả thư mục
                r["status"] = "lỗi"
                r["error"] = str(exc)[:300]
            job["results"].append(r)
            job["done"] += 1
        job["state"] = "done"
        job["current"] = None
        job["finished"] = time.time()

    threading.Thread(target=run, name=jid, daemon=True).start()
    return {k: v for k, v in job.items()}


def folder_status(jid: Any) -> dict:
    from .api import ApiError

    job = _JOBS.get(jid) if isinstance(jid, str) else None
    if job is None:
        raise ApiError("Không có lượt sửa cả thư mục này (ứng dụng đã khởi động lại?).", 404)
    return {k: (list(v) if isinstance(v, list) else v) for k, v in job.items()}


__all__ = ["BACKUP_DIR", "apply", "backup_source", "folder_start", "folder_status", "plan"]
