---
name: kiem-va-giai-thich-loi
description: Kiểm một bản vẽ DXF theo chuẩn (design-hygiene-v0 cho khâu Thiết kế/Kỹ thuật, furniture-v0 cho bản vẽ giao xuống Lập trình sản xuất) bằng công cụ audit, nhóm phát hiện theo mức E/W/I, giải thích từng mã luật bằng explain_rule và xếp thứ tự ưu tiên sửa. Dùng khi người dùng hỏi "bản vẽ có lỗi gì", "kiểm giúp", "VS-06 là gì", "sửa cái nào trước".
---

# Kiểm và giải thích lỗi

Đúng/sai do **luật tất định** quyết. Việc của bạn là chạy luật, đọc kết quả, giải thích và xếp ưu tiên. Không thêm lỗi mà luật không báo; không bỏ lỗi mà luật đã báo.

## Bước làm

1. **Chọn bản vẽ và chuẩn.**
   - Bản vẽ: mã tệp từ `list_drawings` hoặc đường dẫn tương đối người dùng đưa.
   - Chuẩn: `design-hygiene-v0` (khâu Thiết kế, nhận vào Kỹ thuật); `furniture-v0` (giao xuống Lập trình sản xuất). Người dùng không nói thì hỏi phòng của họ; vẫn không rõ thì chạy cả hai và trình bày tách riêng.
   - Hồ sơ công ty (ngưỡng riêng): công cụ `audit` hiện **chưa nhận** hồ sơ. Kết quả là theo ngưỡng mặc định của chuẩn; nói rõ điều này nếu người dùng nhắc tới ngưỡng công ty.
2. **Chạy kiểm**: `audit(file, standard)`. Đọc:
   - `standard`, `version`: ghi vào câu trả lời;
   - `counts` = {E, W, I}: số **phát hiện** theo mức;
   - `findings[]`: `rule_id`, `severity`, `message`, `count`, `layer`, `layout`, `handles`;
   - `rules_run`: số luật đã chạy; `skipped[]`: luật bị bỏ qua kèm `reason`;
   - `truncated`: danh sách phát hiện bị cắt bớt; `records_capped`: dữ liệu bản vẽ bị cắt ở trần bộ nhớ.
3. **Kiểm độ tin cậy trước khi kết luận.**
   - `records_capped` = true → dòng đầu: "Bản vẽ rất lớn, dữ liệu bị cắt; phát hiện có thể thiếu."
   - `skipped` khác rỗng → liệt kê từng luật bị bỏ qua và lý do; nói rõ "bị bỏ qua không có nghĩa là đạt".
   - `truncated` = true → "chỉ hiện một phần phát hiện".
4. **Nhóm theo mức**: E (lỗi, chặn bàn giao) → W (cảnh báo) → I (thông tin). Trong mỗi mức, gộp theo `rule_id`.
5. **Giải thích**: với mỗi mã luật xuất hiện (tối đa khoảng 8 mã mỗi lượt), gọi `explain_rule(rule_id, standard)` và dùng `title`, `severity`, `kind`, `false_positive_risk`, `source`, `description_md`. Viết 1–2 câu: luật kiểm gì, vì sao quan trọng với phòng sau. Không bịa ngưỡng: ngưỡng lấy từ `message` hoặc `description_md`.
6. **Xếp ưu tiên sửa**:
   1. Mọi lỗi **E** (ví dụ VS-06 kích thước ghi đè chữ: số in ra có thể khác số đo thật, xưởng cắt sai).
   2. Cảnh báo W ảnh hưởng trực tiếp phòng sau: phông chữ tiếng Việt (VS-07), layer dư xref (VS-01), đối tượng trên layer 0 (VS-03).
   3. Cảnh báo về độ nặng/gọn: kiểu chữ/kích thước thừa (VS-02), ghi đè màu/nét (VS-04), WIPEOUT/IMAGE/OLE (VS-05).
   4. Luật có `false_positive_risk` = medium: nhắc người dùng xem lại trước khi sửa.
7. **Gợi ý bước tiếp**: "Đề xuất cách dọn?" (skill `don-ban-ve`) hoặc "Soạn ghi chú bàn giao?" (skill `ghi-chu-ban-giao`).

## Mẫu trình bày

```text
Kiểm F_3a9c… theo design-hygiene-v0 (0.1.0): 7 luật đã chạy, 0 bỏ qua.
Tổng: 1 lỗi (E), 8 cảnh báo (W).

Lỗi E — cần sửa trước khi bàn giao
- VS-06: 1 kích thước có chữ ghi đè (handle A1). Số hiển thị có thể khác số đo thật.

Cảnh báo W
- VS-07: 1 chữ có dấu dùng kiểu chữ S_… phông SHX không Unicode → chữ tiếng Việt dễ lỗi ở máy khác.
- VS-01: 2 layer dư từ xref.
- VS-03: 3/32 đối tượng (9,4%) nằm trực tiếp trên layer 0, ngưỡng 5%.
- VS-02: 28 kiểu chữ (ngưỡng 15); 12 kiểu kích thước (ngưỡng 10).
- VS-04: 12,5% đối tượng ghi đè màu; 12,5% ghi đè độ dày nét.
- VS-05: 11 IMAGE (ngưỡng 10).

Ưu tiên: VS-06 → VS-07 → VS-01 → VS-03 → VS-02/VS-04/VS-05.
Kết luận theo luật tất định của cad-guard; trợ lý không tự phán thêm.
```

## Không được

- Không nói "bản vẽ đạt" khi còn luật bị bỏ qua hoặc dữ liệu bị cắt.
- Không tự đọc DXF, không chạy lệnh ngoài, không đoán tên thật khi đang ẩn danh.
- Không hứa "cad-guard sẽ tự sửa": hiện công cụ chỉ đọc.
