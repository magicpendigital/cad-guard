"""Phân bậc chốt tờ: **Chặn** / **Cảnh báo** / **Gợi ý**. Không đổi kết quả luật, chỉ quyết định tờ nào chốt được.

- `block` (Chặn): lỗi ảnh hưởng sản xuất hoặc sử dụng. Còn lỗi thì không chốt được tờ.
- `warn` (Cảnh báo): chốt được sau khi người dùng bấm "Đã xem" hoặc "Bỏ qua" kèm lý do (lưu trên máy, `sheet_state`).
- `hint` (Gợi ý): ẩn mặc định, không ảnh hưởng chốt.

Bậc mặc định dưới đây là ĐỀ XUẤT v0 (chưa được công ty nào duyệt, chưa đo độ chính xác P1c). Trưởng phòng kỹ thuật
chốt danh sách thật trong hồ sơ công ty, khoá `gate:` (`standards/company-profile.example.yaml`).
"""
from __future__ import annotations

from .standard import Standard

TIERS = ("block", "warn", "hint")
TIER_VI = {"block": "Chặn", "warn": "Cảnh báo", "hint": "Gợi ý"}

# Đề xuất v0: chỉ lỗi làm SAI KÍCH THƯỚC hoặc SAI CHI TIẾT khi sản xuất mới chặn.
DEFAULT_TIERS = {
    "DH-09": "block",  # đơn vị vẽ không phải mm: mọi kích thước sản xuất sai tỉ lệ
    "TX-08": "block",  # kích thước bị sửa chữ bằng tay: số ghi khác hình vẽ
    "VS-06": "block",  # (chuẩn vệ sinh) cùng lỗi kích thước ghi đè
    "PR-02": "block",  # thẻ vị trí chi tiết trùng: xưởng làm nhầm chi tiết
    "LY-09": "hint",  # layer rỗng
    "VS-02": "hint",  # số kiểu chữ/kiểu kích thước
    "VS-04": "hint",  # ghi đè màu/độ dày nét
    "VS-05": "hint",  # WIPEOUT/IMAGE/OLE
    "DH-10": "hint",  # z khác 0
}


def tier_of(std: Standard, rule_id: str, severity: str | None = None) -> str:
    t = std.gate.get(rule_id) or DEFAULT_TIERS.get(rule_id)
    if t:
        return t
    return "hint" if severity == "I" else "warn"


def ack_key(standard: str, rule_id: str, sheet: str) -> str:
    return f"{standard}|{rule_id}|{sheet}"


def evaluate(groups: list[dict], sheet: str | None, acks: dict, std: Standard) -> dict:
    """Đếm lỗi theo bậc cho một tờ (`sheet`, None = toàn bản vẽ) từ nhóm luật của `app.api.audit_file`.

    Phát hiện không gắn tờ nào (theo layer, theo cả bản vẽ) tính cho MỌI tờ. Cảnh báo coi như đã xử lý khi có xác
    nhận cho tờ đó hoặc cho cả bản vẽ ("*").
    """
    out = {"block": 0, "warn": 0, "hint": 0, "warn_open": 0, "block_rules": [], "warn_open_rules": []}
    for g in groups:
        n = 0
        for it in g["items"]:
            sh = it.get("sheets") or []
            if sheet is None or not sh or sheet in sh:
                n += max(1, int(it.get("count") or 1))
        if not n:
            continue
        tier = g.get("tier") or tier_of(std, g["rule_id"], g.get("severity"))
        out[tier] += n
        if tier == "block":
            out["block_rules"].append(g["rule_id"])
        elif tier == "warn":
            acked = any(ack_key(std.name, g["rule_id"], s) in acks for s in ("*", sheet or "*"))
            if not acked:
                out["warn_open"] += n
                out["warn_open_rules"].append(g["rule_id"])
    need_ack = std.gate_require_ack
    out["can_lock"] = out["block"] == 0 and (not need_ack or out["warn_open"] == 0)
    out["require_ack"] = need_ack
    return out


__all__ = ["DEFAULT_TIERS", "TIERS", "TIER_VI", "ack_key", "evaluate", "tier_of"]
