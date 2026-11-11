"""Hướng dẫn khắc phục cho thông báo lỗi của giao diện: lỗi gì, vì sao, làm gì tiếp, nút bấm tương ứng.

Người dùng là người làm thiết kế, không phải lập trình viên: mỗi lỗi máy chủ trả về kèm `hint`
`{"title", "why", "steps": [...], "actions": [{"id", "label"}]}`. Giao diện hiện hướng dẫn trong khung thông báo
KHÔNG tự tắt (khác thông báo ngắn ở cạnh dưới). `actions[].id` là việc giao diện biết làm (`NOTICE_ACTIONS` trong
`static/app.js`; test kiểm khớp).

Khớp theo mẫu câu của thông điệp tiếng Việt. Lỗi chưa có mẫu vẫn có hướng dẫn chung.
"""
from __future__ import annotations

import re
from typing import Any

A_REPROPOSE = {"id": "repropose", "label": "Đề xuất lại"}
A_CONNECT = {"id": "connect", "label": "Mở Kết nối AI"}
A_PROJECT = {"id": "project", "label": "Chọn dự án"}
A_ASK = {"id": "ask_ai", "label": "Hỏi trợ lý AI về lỗi này"}
A_GUIDE3D = {"id": "guide3d", "label": "Xem cách bổ sung cho 3D"}
A_SHEETS = {"id": "sheets", "label": "Chọn tờ trên thanh Tờ"}
A_CHANGES = {"id": "changes", "label": "Mở tab Thay đổi"}
A_SETUP = {"id": "setup", "label": "Mở Cài đặt"}

ACTION_IDS = {"repropose", "connect", "project", "ask_ai", "guide3d", "sheets", "changes", "setup"}

_RULES: list[tuple[re.Pattern, dict[str, Any]]] = [
    (re.compile(r"Kiểm tệp ra KHÔNG ĐẠT"), {
        "title": "Tệp mới chưa được tạo vì bước tự kiểm không đạt",
        "why": "Sau khi sửa, CAD Guard mở lại tệp mới và so với bản gốc. Có thay đổi nằm ngoài phạm vi thao tác nên "
               "hệ thống dừng lại để không giao cho bạn một tệp sai. Bản gốc không bị chạm tới.",
        "steps": ["Bấm 'Đề xuất lại' để chạy lại với bản vẽ hiện tại.",
                  "Nếu vẫn lỗi: bỏ bớt thao tác trong đề xuất (bỏ tick) rồi xem trước từng nhóm để tìm nhóm gây lỗi.",
                  "Gửi nội dung lỗi (nút 'Sao chép') cho bộ phận phụ trách CAD Guard, kèm tên tờ đang làm."],
        "actions": [A_REPROPOSE, A_CHANGES, A_ASK]}),
    (re.compile(r"Tệp gốc đã thay đổi sau khi đề xuất|Tệp gốc thay đổi trong lúc áp dụng"), {
        "title": "Bản vẽ đã được lưu lại sau khi đề xuất",
        "why": "Đề xuất sửa được tính trên phiên bản cũ của tệp; áp dụng lên phiên bản mới có thể làm sai.",
        "steps": ["Bấm 'Đề xuất lại' để tính lại trên bản vẽ hiện tại.", "Xem trước rồi duyệt như bình thường."],
        "actions": [A_REPROPOSE]}),
    (re.compile(r"Tệp ra '.*' (hoặc nhật ký áp dụng của changeset này )?đã có"), {
        "title": "Thay đổi này đã được lưu ra tệp mới từ trước",
        "why": "CAD Guard không bao giờ ghi đè tệp đã có.",
        "steps": ["Xem danh sách tệp bên trái: tệp có đuôi .cg-… hoặc .en…/.zh… là kết quả đã lưu.",
                  "Muốn làm lại: hoàn tác thay đổi cũ trong tab Thay đổi, rồi đề xuất lại."],
        "actions": [A_CHANGES]}),
    (re.compile(r"Changeset viết cho .* chuẩn hiện có là"), {
        "title": "Bộ luật đã đổi phiên bản",
        "why": "Đề xuất được tạo với phiên bản luật cũ.",
        "steps": ["Bấm 'Đề xuất lại' để tạo đề xuất theo phiên bản luật hiện tại."],
        "actions": [A_REPROPOSE]}),
    (re.compile(r"Chưa mở dự án|Chưa chọn dự án|chưa có dự án", re.I), {
        "title": "Chưa chọn thư mục dự án",
        "why": "CAD Guard chỉ làm việc trong một thư mục dự án để không chạm vào tệp khác trên máy.",
        "steps": ["Bấm 'Chọn dự án', chọn thư mục chứa bản vẽ DXF/DWG."],
        "actions": [A_PROJECT]}),
    (re.compile(r"ẩn danh \(NDA\)"), {
        "title": "Dự án đang bật ẩn danh nên không dịch được",
        "why": "Dịch cần gửi nội dung chữ cho mô hình AI; chế độ ẩn danh (NDA) chặn việc này.",
        "steps": ["Nếu hồ sơ không thuộc NDA: bấm công tắc 'Dữ liệu' trên thanh trên cùng, chuyển sang Nội bộ.",
                  "Nếu thuộc NDA: dịch thủ công hoặc dùng bảng thuật ngữ của công ty."],
        "actions": []}),
    (re.compile(r"Quá \d+ chuỗi chữ"), {
        "title": "Bản vẽ quá nhiều chữ để dịch một lần",
        "why": "Dịch cả bản vẽ lớn một lượt dễ quá giờ và tốn lượt AI.",
        "steps": ["Chọn một tờ trên thanh Tờ phía trên bản vẽ.", "Bấm 'Dịch' lại: chỉ tờ đó được dịch."],
        "actions": [A_SHEETS]}),
    (re.compile(r"Bản vẽ đã viết bằng"), {
        "title": "Bản vẽ đã ở ngôn ngữ đích",
        "why": "Ngôn ngữ gốc tự nhận theo nội dung chữ trùng với ngôn ngữ bạn chọn.",
        "steps": ["Chọn ngôn ngữ đích khác ở ô bên cạnh nút Dịch."],
        "actions": []}),
    (re.compile(r"không có hạng mục", re.I), {
        "title": "Không nhận ra hạng mục đồ nội thất để dựng 3D",
        "why": "Dựng 3D theo hạng mục cần khung tên có mã hạng mục và ít nhất một mặt bằng + một mặt đứng của cùng hạng mục.",
        "steps": ["Kiểm khung tên của các tờ có mã hạng mục (vd. FUR-01).",
                  "Tờ mặt bằng và tờ mặt đứng của cùng hạng mục phải ghi cùng mã.",
                  "Xem hướng dẫn chi tiết bằng nút bên dưới."],
        "actions": [A_GUIDE3D]}),
    (re.compile(r"Giá trị phải là số|ngoài khoảng hợp lệ|ngoài danh sách"), {
        "title": "Giá trị nhập chưa hợp lệ",
        "why": "Kích thước nhập theo mm, trong khoảng hợp lý cho đồ nội thất.",
        "steps": ["Nhập số nguyên theo mm (vd. 600), không kèm đơn vị.",
                  "Chọn giá trị trong danh sách nếu ô là danh sách chọn."],
        "actions": []}),
    (re.compile(r"Tờ mẫu phải là khung tên|Không đo được khung bao|Tờ \d+ không có"), {
        "title": "Tờ đã chọn không dùng làm mẫu khung tên được",
        "why": "Học template cần một tờ trong Model có khung tên dạng khối (block).",
        "steps": ["Trên thanh Tờ, chọn tờ có khung tên đẹp, đầy đủ nhất.",
                  "Nếu khung tên vẽ rời bằng nét (không phải khối): trong AutoCAD gom thành block rồi lưu, quét lại."],
        "actions": [A_SHEETS]}),
    (re.compile(r"Không thấy tệp logo"), {
        "title": "Không tìm thấy tệp logo",
        "why": "Đường dẫn logo phải trỏ tới tệp PNG/JPG có thật trên máy.",
        "steps": ["Mở thư mục chứa logo, giữ Shift + chuột phải vào tệp, chọn 'Copy as path', dán lại."],
        "actions": []}),
    (re.compile(r"accoreconsole|\bDWG\b"), {
        "title": "Không đọc/ghi được tệp DWG",
        "why": "CAD Guard dùng AutoCAD đã cài trên máy (accoreconsole) để đổi DWG ↔ DXF.",
        "steps": ["Mở tab Cài đặt kiểm AutoCAD đã được nhận.",
                  "Hoặc trong AutoCAD: Save As → DXF, rồi mở tệp DXF trong CAD Guard."],
        "actions": [A_SETUP]}),
    (re.compile(r"Chưa có trợ lý|khoá API|hết lượt|quota|đăng nhập|credit balance|tín dụng", re.I), {
        "title": "Trợ lý AI chưa dùng được",
        "why": "Tính năng cần AI (dịch, giải thích sâu, đề xuất) phải có một CLI đã đăng nhập hoặc khoá API còn lượt.",
        "steps": ["Mở Kết nối AI, bấm 'Kiểm tra' ở trợ lý đang chọn.", "Đăng nhập lại nếu báo hết phiên/hết lượt."],
        "actions": [A_CONNECT]}),
]

GENERIC = {
    "title": "Chưa thực hiện được",
    "why": "Bản vẽ gốc không bị thay đổi.",
    "steps": ["Thử lại thao tác.",
              "Nếu vẫn lỗi: bấm 'Sao chép' và gửi nội dung cho bộ phận phụ trách, hoặc hỏi trợ lý AI."],
    "actions": [A_ASK],
}


def hint_for(message: str, status: int = 400) -> dict:
    """Hướng dẫn cho một thông điệp lỗi (luôn có, tối thiểu là hướng dẫn chung)."""
    for pat, hint in _RULES:
        if pat.search(message or ""):
            return hint
    if status >= 500:
        return {**GENERIC, "title": "CAD Guard gặp lỗi bên trong",
                "steps": ["Thử lại thao tác.", "Nếu lặp lại: đóng CAD Guard và mở lại bằng lối tắt trên màn hình.",
                          "Vẫn lỗi: bấm 'Sao chép' và gửi cho bộ phận phụ trách."]}
    return GENERIC


def all_hints() -> list[dict]:
    return [h for _p, h in _RULES] + [GENERIC]


__all__ = ["ACTION_IDS", "GENERIC", "all_hints", "hint_for"]
