---
name: ghi-chu-ban-giao
description: Soạn ghi chú bàn giao bản vẽ giữa hai phòng (Thiết kế → Kỹ thuật, Kỹ thuật → Lập trình sản xuất) từ dữ liệu có cấu trúc của audit và get_model_summary - còn lỗi E nào, cảnh báo nào đã được chấp nhận, cảnh báo nào còn lại, luật bị bỏ qua, dữ liệu có bị cắt không, ai nhận, việc cần làm, đã sẵn sàng bàn giao chưa. Dùng khi người dùng nói "bàn giao", "chuyển cho Kỹ thuật", "gói bàn giao", "ghi chú cho xưởng".
---

# Ghi chú bàn giao

Ghi chú bàn giao là **dữ liệu có cấu trúc**, lấy từ kết quả công cụ, không viết theo cảm nhận. Mỗi con số phải truy được về một trường của `audit` hoặc `get_model_summary`.

## Bước làm

1. **Xác định hai phòng.** Hỏi nếu chưa rõ: từ phòng nào, sang phòng nào.
   - Thiết kế → Kỹ thuật: chuẩn `design-hygiene-v0`.
   - Kỹ thuật → Lập trình sản xuất: chuẩn `furniture-v0` (có thể kèm `design-hygiene-v0`).
2. **Hỏi cảnh báo nào đã được phòng nhận chấp nhận** (ví dụ "Kỹ thuật đồng ý giữ VS-02"). Không tự cho là đã chấp nhận. Lỗi **E** không có kiểu "chấp nhận" trong ghi chú: phải sửa hoặc ghi là còn tồn.
3. **Lấy dữ liệu**:
   - `audit(file, standard)` → `standard`, `version`, `counts`, `findings`, `skipped`, `records_capped`, `truncated`;
   - `get_model_summary(file)` → `layer_count`, `entities_by_space`, `layouts`, `insunits`, `records_capped` (để ghi phần mô tả bản vẽ).
4. **Điền các trường bắt buộc** (tên trường cố định để phòng sau và bộ chấm đọc được):

| Trường | Lấy từ | Ý nghĩa |
| --- | --- | --- |
| `tu_phong`, `den_phong` | người dùng | "Thiết kế", "Kỹ thuật", "Lập trình sản xuất" |
| `nguoi_nhan` | người dùng | Mặc định "Phòng <den_phong>"; chỉ ghi tên người nếu người dùng tự đưa |
| `ban_ve` | `audit.file` | Mã tệp (ẩn danh thì là `F_…`) |
| `chuan`, `phien_ban_chuan` | `audit.standard`, `audit.version` | |
| `so_loi_e` | `audit.counts.E` | Số phát hiện mức E |
| `ma_loi_e` | `findings` có `severity` = E | Danh sách mã luật, mỗi mã một lần |
| `canh_bao_chap_nhan` | mã W có trong `findings` **và** được phòng nhận chấp nhận | |
| `canh_bao_con_lai` | mã W có trong `findings` chưa được chấp nhận | |
| `luat_bo_qua` | `audit.skipped[].rule_id` | Kèm lý do ở phần văn bản |
| `records_capped` | `audit.records_capped` hoặc `get_model_summary.records_capped` | |
| `san_sang_ban_giao` | tính | Đúng khi `so_loi_e` = 0, `canh_bao_con_lai` rỗng, `records_capped` = false |
| `viec_can_lam` | tính | Mỗi lỗi E và mỗi cảnh báo còn lại thành một việc |

5. **Trình bày** hai phần: bảng JSON (để lưu vào gói bàn giao) và đoạn văn ngắn cho người đọc. Nếu `san_sang_ban_giao` = false thì câu đầu là "Chưa nên chuyển sang <phòng nhận>" kèm lý do.
6. **Nhắc** rằng ghi chú chưa được lưu tự động: cad-guard chỉ đọc. Người dùng tự lưu ghi chú cạnh bản vẽ (tệp mới), không sửa tệp gốc.

## Ví dụ (DXF tổng hợp `hygiene_bad.dxf`, Kỹ thuật đã chấp nhận VS-02, VS-05)

```json
{
  "tu_phong": "Thiết kế",
  "den_phong": "Kỹ thuật",
  "nguoi_nhan": "Phòng Kỹ thuật",
  "ban_ve": "F_3a9c…",
  "chuan": "design-hygiene-v0",
  "phien_ban_chuan": "0.1.0",
  "so_loi_e": 1,
  "ma_loi_e": ["VS-06"],
  "canh_bao_chap_nhan": ["VS-02", "VS-05"],
  "canh_bao_con_lai": ["VS-01", "VS-03", "VS-04", "VS-07"],
  "luat_bo_qua": [],
  "records_capped": false,
  "san_sang_ban_giao": false,
  "viec_can_lam": [
    "Sửa VS-06 (1 phát hiện) trước khi chuyển",
    "Xử lý hoặc xin Kỹ thuật chấp nhận cảnh báo VS-01"
  ]
}
```

```text
Chưa nên chuyển sang Kỹ thuật: còn 1 lỗi E (VS-06, kích thước ghi đè chữ) và 4 cảnh báo chưa được chấp nhận.
Đã chấp nhận: VS-02, VS-05. Không luật nào bị bỏ qua; dữ liệu đầy đủ.
Kiểm theo design-hygiene-v0 0.1.0 bằng luật tất định của cad-guard.
```

## Không được

- Không chuyển lỗi E thành "chấp nhận".
- Không đòi tên thật của tệp, layer hay người vẽ khi đang ẩn danh.
- Không bỏ trường: thiếu dữ liệu thì ghi `null` hoặc danh sách rỗng và nói vì sao.
