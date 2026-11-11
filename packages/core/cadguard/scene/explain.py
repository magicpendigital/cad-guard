"""Lời giải thích cho người làm thiết kế: phần thiếu của cảnh 3D, tên hình/tờ dễ đọc, mức sẵn sàng của hạng mục.

Dùng chung cho màn 3D (`app/scene_api.py`) và đồ thị tri thức bản vẽ (`graph.py`). Tên lấy từ khung tên có thể còn
mã TCVN3/VNI: giải mã để hiển thị.
"""
from __future__ import annotations

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
    sn = _sheet_name(d, v.sheet_id)
    where = sn if sn.lower().startswith("tờ") else f"tờ {sn}"  # tên tờ đã có chữ "Tờ": không lặp
    return f"{KIND_VI.get(v.kind, 'Hình')} “{v.title or v.label or v.id}” ({where})"


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
        return {"where": f"Khối {m} của hạng mục " + _vi(str((d.groups.get(sc.item) or {}).get("name") or sc.item)), "title": "Thiếu chiều sâu tủ",
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
