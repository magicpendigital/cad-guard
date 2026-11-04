---
name: don-ban-ve
description: Đề xuất dọn bản vẽ theo các luật vệ sinh VS-01..VS-07 của design-hygiene-v0 - chọn thao tác trong từ vựng cố định, chạy khô bằng propose_changeset (nếu máy chủ bật) để có xem trước, rồi để NGƯỜI DÙNG tự áp dụng ra tệp mới bằng cadguard apply. Dùng khi người dùng hỏi "dọn bản vẽ", "làm sạch", "purge", "sửa lỗi VS-xx thế nào". Trợ lý không bao giờ tự áp dụng.
---

# Đề xuất dọn bản vẽ (VS-*)

**Nói ngay từ đầu với người dùng:** trợ lý chỉ **đề xuất**. Trợ lý chỉ đọc bản vẽ và (nếu máy chủ bật `--allow-propose`) ghi một **changeset** (tệp JSON mô tả thao tác) kèm xem trước; **không** ghi bản vẽ. Người dùng tự xem trước rồi tự áp dụng bằng `cadguard apply`; kết quả ghi ra **tệp mới** `<tên>.cg-<mã>.dxf`, tệp gốc giữ nguyên, hoàn tác bằng `cadguard undo <mã>` (xoá tệp mới).

## Bước làm

1. Gọi `audit(file, "design-hygiene-v0")`. Chỉ đề xuất cho những mã VS-* **có trong `findings`**. Không có phát hiện thì nói "luật không báo, không cần dọn theo chuẩn này".
2. Kiểm `records_capped`, `skipped` như skill `kiem-va-giai-thich-loi` và nói rõ nếu có.
3. Với mỗi mã có phát hiện, lấy số liệu từ `message`/`count`/`handles`. Lấy mã phiên của layer/kiểu chữ cần dùng từ kết quả công cụ (`audit`: `layer` và mã trong `message`; `query_model`: `layer`, `text_style`; `get_model_summary`: `text_styles`). Không đoán tên thật.
4. Chọn thao tác theo bảng dưới (bắt đầu bằng thao tác ít rủi ro nhất). Hỏi người dùng layer nào cần **bảo vệ** (ví dụ khung tên) nếu chưa rõ; đưa vào `protected_layers`.
5. **Nếu có công cụ `propose_changeset`:** gọi `propose_changeset(file, ops, "design-hygiene-v0", protected_layers)` với tên là mã phiên. Đọc kết quả:
   - `ok` = true và `rules_regressed` = 0 mới nên giới thiệu cho người dùng; nếu `ok` = false, đọc `checks` để biết lý do và sửa danh sách thao tác (đề xuất lại), đừng đưa changeset hỏng cho người dùng.
   - Trình bày: từng thao tác và số mục bị ảnh hưởng (`ops_report[].affected`, `skipped_protected`), `diff_summary_vi`, luật hết (`rules.resolved`), luật còn lại (`rules.after`), `summary_vi`.
   - Kết thúc bằng câu lệnh người dùng tự chạy, lấy từ trường `apply`, ví dụ: `cadguard apply cs-2182a1853817 --workspace <thư mục làm việc>`. Nói rõ: lệnh sẽ in lại xem trước và hỏi xác nhận; tệp gốc không bị sửa.
6. **Nếu không có `propose_changeset`** (máy chủ chỉ đọc): đưa bảng đề xuất **thao tác → ảnh hưởng → cách tự làm trong CAD → kiểm lại**, hoặc gợi ý người dùng tự lập changeset bằng `cadguard propose <tệp> --ops ops.json`.
7. Sau khi người dùng áp dụng: gọi `audit` trên tệp mới (`list_drawings` sẽ thấy tệp `.cg-…`) và `diff(gốc, tệp mới)` để xác nhận mã đã biến mất, không có mã mới, chỉ những thuộc tính dự kiến bị đổi.

## Bảng thao tác theo mã luật

| Mã | Thao tác changeset | Ảnh hưởng | Cách tự làm trong CAD (tuỳ phần mềm) |
| --- | --- | --- | --- |
| VS-01 | `merge_layers` {sources: [layer dư], target: layer đúng} hoặc `rename_layer` {from, to}; layer dư rỗng thì `purge_unused` {kinds: ["layers"]} | Bản vẽ gọn, phòng sau không chọn nhầm layer | Gộp layer (LAYMRG) hoặc đổi tên; PURGE layer rỗng |
| VS-02 | `replace_text_style` / `replace_dim_style` về kiểu chuẩn rồi `purge_unused` {kinds: ["text_styles", "dim_styles"]} | Ít chọn nhầm kiểu; hình thức chữ/kích thước dùng kiểu bị gộp có thể đổi | Đổi đối tượng sang kiểu chuẩn, rồi PURGE |
| VS-03 | `move_to_layer` {filter: {layers: ["0"], spaces: ["Model"]}, target: layer đúng chức năng} | In ấn, tắt/bật layer đúng hơn; **không** đụng nội dung khối | Lọc đối tượng trên layer 0 ngoài khối, đổi layer |
| VS-04 | `set_bylayer` {filter: {layers: [...]}} | Màu/nét in ra có thể đổi, cần xem lại bản in | Đặt màu và độ dày nét về ByLayer (SETBYLAYER nếu có) |
| VS-05 | **Không có thao tác**: bớt WIPEOUT/IMAGE/OLE là xoá đối tượng, ngoài từ vựng | — | Người dùng tự xoá WIPEOUT thừa, quản lý ảnh tham chiếu, thay OLE |
| VS-06 | `clear_dim_text_override` {filter: ...} | **Số in ra có thể đổi**: phải đối chiếu với thiết kế trước khi chuyển | Xoá chữ ghi đè của kích thước; dùng `handles` để tìm |
| VS-07 | `replace_text_style` {from: [kiểu phông không Unicode], to: kiểu phông Unicode đã có} | Chữ tiếng Việt hiện đúng trên máy khác; có thể đổi độ rộng chữ | Sửa phông của kiểu chữ; chữ cũ nhập bằng mã TCVN3/VNI có thể cần chuyển mã |

Thao tác khác trong từ vựng: `set_text_height` {filter, from_height, to} (đổi chiều cao chữ, ví dụ loại trừ khung tên bằng `exclude_layers` hoặc `protected_layers`). Không có thao tác xoá đối tượng hình học.

Ghi chú:

- VS-06 là lỗi E: phải xử lý trước bàn giao. Không tự "sửa số cho khớp": hỏi người thiết kế số nào đúng trước khi đề xuất `clear_dim_text_override`.
- VS-04 và VS-07 có `false_positive_risk` = medium: nhắc người dùng xem lại từng trường hợp (layer trình bày có thể được miễn qua hồ sơ công ty).
- Không bao giờ nói "đã sửa xong" khi người dùng chưa chạy `cadguard apply`. Không đưa lệnh `--yes` cho người dùng khi họ chưa xem xem trước.
- Lệnh CAD trong bảng là gợi ý thông dụng; tên lệnh khác nhau giữa AutoCAD, BricsCAD, ZWCAD… Không chắc thì mô tả thao tác, không bịa tên lệnh.

## Mẫu trình bày

```text
Tôi chỉ đề xuất; bạn tự áp dụng, kết quả ghi ra tệp mới, tệp gốc giữ nguyên.

Changeset cs-2182a1853817 (design-hygiene-v0 0.1.0, xem trước: ĐẠT, không luật nào xuất hiện mới)
1. clear_dim_text_override — 1 kích thước (VS-06, E): trả về số đo tự động. Số in ra có thể đổi.
2. replace_text_style S_… → S_… — 1 chữ (VS-07, W).
3. purge_unused — xoá 25 kiểu chữ, 10 kiểu kích thước không dùng (VS-02, W).
Còn lại: VS-05 (11 IMAGE) — cần bạn tự xử lý trong CAD.

Áp dụng (lệnh sẽ in lại xem trước và hỏi xác nhận):
  cadguard apply cs-2182a1853817 --workspace <thư mục làm việc>
Áp xong, báo tôi để kiểm lại tệp mới bằng audit và diff.
```
