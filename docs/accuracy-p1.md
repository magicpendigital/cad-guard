# Độ chính xác luật (P1c) — bảng đo

Trạng thái: **CHƯA ĐO**. Điền sau khi người kỹ thuật rà thủ công cùng bộ bản vẽ mẫu với cadguard.

Cách đo, mỗi luật trên cả bộ mẫu:

- **Đúng**: luật báo, người rà xác nhận là lỗi thật.
- **Sai (báo nhầm)**: luật báo, người rà nói không phải lỗi.
- **Bỏ sót**: người rà thấy lỗi thuộc luật đó nhưng luật không báo.
- Độ chính xác = Đúng / (Đúng + Sai). Tỉ lệ báo sai = 1 − độ chính xác.
- Luật được đánh dấu `realtime_ok: true` trong chuẩn **chỉ khi** độ chính xác đạt ngưỡng đã đặt trước và có đủ mẫu.

Ngưỡng đặt trước (CEO quyết, đề xuất khởi điểm): độ chính xác ≥ 90%, ≥ 30 phát hiện đã xét, không có lần nào hỏng bản vẽ. Ghi lại ngưỡng đã chọn: ______

| Luật | Đúng | Sai | Bỏ sót | Độ chính xác | Quyết định (giữ mức / hạ xuống chỉ báo cáo / tắt / thời gian thực) |
| --- | --- | --- | --- | --- | --- |
| SH-04 |  |  |  |  |  |
| SH-05 |  |  |  |  |  |
| LY-01 |  |  |  |  |  |
| LY-03 |  |  |  |  |  |
| LY-04 |  |  |  |  |  |
| LY-08 |  |  |  |  |  |
| LY-09 |  |  |  |  |  |
| TX-01 |  |  |  |  |  |
| TX-08 |  |  |  |  |  |
| VW-01 |  |  |  |  |  |
| DH-01 |  |  |  |  |  |
| DH-02 |  |  |  |  |  |
| DH-07 |  |  |  |  |  |
| DH-09 |  |  |  |  |  |
| DH-10 |  |  |  |  |  |
| PR-02 |  |  |  |  |  |

## So sánh hai đường chuyển đổi (DXF gốc vs DWG→DXF)

| Bản vẽ (mã) | Luật khác kết quả giữa hai đường | Nguyên nhân (nếu biết) |
| --- | --- | --- |
|  |  |  |

## Chuẩn v0 → phiên bản mới

Mỗi thay đổi ngưỡng/mức/luật ghi: lý do + số liệu + phiên bản mới của chuẩn.
