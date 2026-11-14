---
name: khao-sat-ban-ve
description: Khảo sát nhanh một hoặc nhiều bản vẽ DXF trước khi kiểm lỗi - tóm tắt mô hình (layer, khối, đối tượng theo loại và không gian, layout, kiểu chữ, đơn vị, phiên bản DXF), thống kê và chỉ ra điểm bất thường. Dùng khi người dùng hỏi "bản vẽ này có gì", "nặng vì sao", "có bao nhiêu ...", hoặc khi mới nhận bản vẽ từ phòng khác.
---

# Khảo sát bản vẽ

Mục tiêu: cho người dùng một bức tranh số liệu về bản vẽ, **không** phán đúng/sai. Điểm bất thường chỉ là gợi ý xem kỹ; kết luận lỗi phải qua skill `kiem-va-giai-thich-loi`.

## Bước làm

1. **Liệt kê bản vẽ**: gọi `list_drawings` (mặc định `dir = "."`).
   - Đọc `drawings[].id` (mã tệp `F_…` khi ẩn danh), `size_bytes`, `total`, `truncated`.
   - `truncated` = true: báo "chỉ liệt kê được một phần".
   - Nhiều bản vẽ: hỏi người dùng muốn khảo sát bản nào, hoặc khảo sát lần lượt (tối đa vài bản mỗi lượt cho gọn).
2. **Tóm tắt mô hình**: gọi `get_model_summary(file = <mã tệp>)`. Đọc:
   - `layer_count`, `block_count`;
   - `entities_by_type` (đếm theo loại: LINE, LWPOLYLINE, TEXT, MTEXT, DIMENSION, INSERT, IMAGE, WIPEOUT…);
   - `entities_by_space` (`Model` và các layout `Y_…`);
   - `layouts[]` (khổ giấy `paper_w_mm` × `paper_h_mm`, `viewport_count`);
   - `text_styles` (số chữ theo kiểu chữ), `insunits`, `dxf_version`;
   - `truncated`, `records_capped`.
3. **Khi cần chi tiết**: gọi `query_model(file, filter, limit, cursor)`.
   - Ví dụ đếm kích thước: `filter = {"type": "DIMENSION"}`; mỗi mục có `dim_text_overridden`.
   - Ví dụ đối tượng trên layer 0: `filter = {"layer": "0"}`.
   - Đọc `total_matched`; nếu `next_cursor` khác null thì gọi lại **nguyên bộ lọc** kèm `cursor` để lấy trang sau. Chỉ lấy hết trang khi thật cần đếm chính xác.
4. **Tìm điểm bất thường** (chỉ là gợi ý, ghi "nên kiểm"):
   - `insunits` khác 4 (mm) với bản vẽ nội thất;
   - nhiều `IMAGE`, `WIPEOUT`, OLE trong `entities_by_type`;
   - nhiều kiểu chữ trong `text_styles`;
   - nhiều đối tượng trực tiếp trên layer `0` (dùng `query_model` với `{"layer": "0"}`);
   - layout không có viewport (`viewport_count` = 0);
   - kích thước có `dim_text_overridden` = true.
5. **Trình bày** (mẫu bên dưới). Kết thúc bằng gợi ý bước tiếp: "Chạy kiểm theo `design-hygiene-v0`?" hoặc "Chạy kiểm theo `furniture-v0`?".

## Lưu ý bắt buộc

- `records_capped` = true: viết ngay dòng đầu "Bản vẽ rất lớn: danh sách đối tượng đã bị cắt ở trần bộ nhớ, số đếm có thể thiếu."
- Đang ẩn danh thì dùng mã phiên (`L_…`, `S_…`, `Y_…`), không đòi tên thật.
- Không tự đọc tệp DXF hay chạy lệnh ngoài; chỉ dùng công cụ cad-guard.

## Mẫu trình bày

```text
Bản vẽ F_3a9c… (1,2 MB, DXF AC1032, đơn vị mm)
- 8 layer, 1 khối, 32 đối tượng (Model: 32), 1 layout A3 (420 × 297 mm, chưa có viewport)
- Loại nhiều nhất: IMAGE 11, LINE 10, INSERT 3, CIRCLE 3, TEXT 2, DIMENSION 2, MTEXT 1
- Kiểu chữ đang dùng: 2

Nên kiểm thêm:
- 11 ảnh IMAGE: dễ mất khi chuyển tệp (VS-05 sẽ kiểm).
- 1/2 kích thước bị ghi đè chữ (VS-06 sẽ kiểm).

Bước tiếp: chạy kiểm theo design-hygiene-v0?
```
