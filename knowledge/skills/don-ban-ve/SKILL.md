---
name: don-ban-ve
description: Đề xuất dọn bản vẽ theo các luật vệ sinh VS-01..VS-07 của design-hygiene-v0 - liệt kê thao tác đề xuất, ảnh hưởng tới bản vẽ và phòng sau, cách người dùng tự làm trong phần mềm CAD. Dùng khi người dùng hỏi "dọn bản vẽ", "làm sạch", "purge", "sửa lỗi VS-xx thế nào". cad-guard hiện CHỈ ĐỌC, chưa tự sửa.
---

# Đề xuất dọn bản vẽ (VS-*)

**Nói ngay từ đầu với người dùng:** cad-guard hiện **chỉ đọc**, chưa có công cụ sửa bản vẽ. Mọi thứ dưới đây là **đề xuất** để người dùng tự làm trong phần mềm CAD. Khi có công cụ sửa, mọi thay đổi sẽ ghi ra **tệp mới** (không ghi đè bản gốc), có xem trước, xác nhận và hoàn tác.

## Bước làm

1. Gọi `audit(file, "design-hygiene-v0")`. Chỉ đề xuất cho những mã VS-* **có trong `findings`**. Không có phát hiện thì nói "luật không báo, không cần dọn theo chuẩn này".
2. Kiểm `records_capped`, `skipped` như skill `kiem-va-giai-thich-loi` và nói rõ nếu có.
3. Với mỗi mã có phát hiện, lấy số liệu từ `message`/`count`/`handles`; gọi `explain_rule` nếu cần dẫn nguồn.
4. Lập bảng đề xuất theo mẫu: **thao tác → ảnh hưởng → cách tự làm trong CAD → kiểm lại**. Bắt đầu bằng thao tác ít rủi ro nhất.
5. Kết thúc: "Làm xong, lưu thành **tệp mới** (ví dụ thêm hậu tố `_don`), rồi gửi lại để tôi kiểm lại bằng `audit`." Kiểm lại phải cho thấy mã đó biến mất khỏi `findings` và không có mã mới.

## Bảng thao tác theo mã luật

| Mã | Thao tác đề xuất | Ảnh hưởng | Cách tự làm trong CAD (tuỳ phần mềm) |
| --- | --- | --- | --- |
| VS-01 | Gộp hoặc đổi tên layer dư từ xref (tên có `\|`, `$0$`), rồi xoá layer rỗng | Bản vẽ gọn, phòng sau không chọn nhầm layer | Lệnh quản lý layer: gộp layer (LAYMRG) hoặc đổi tên; sau đó PURGE layer rỗng |
| VS-02 | Gộp kiểu chữ/kiểu kích thước trùng ý, xoá kiểu thừa | Ít chọn nhầm kiểu; có thể đổi hình thức chữ/kích thước đang dùng kiểu bị gộp | Đổi đối tượng sang kiểu chuẩn của công ty, rồi PURGE kiểu không dùng |
| VS-03 | Chuyển đối tượng đang nằm trực tiếp trên layer `0` sang layer đúng chức năng | In ấn và tắt/bật layer đúng hơn; **không** đụng nội dung trong khối | Chọn đối tượng trên layer 0 ngoài khối (lọc nhanh theo layer), đổi layer |
| VS-04 | Đặt màu và độ dày nét về ByLayer | Màu/nét in ra có thể đổi, cần xem lại bản in | Chọn đối tượng có màu/nét riêng, đặt về ByLayer (SETBYLAYER nếu có) |
| VS-05 | Giảm WIPEOUT thừa; nhúng hoặc bỏ IMAGE không cần; bỏ OLE | Bản vẽ nhẹ, không mất ảnh khi chuyển tệp; có thể đổi phần che nền | Xoá WIPEOUT thừa (cả trong khối), quản lý ảnh tham chiếu, thay OLE bằng bảng/chữ |
| VS-06 | Trả kích thước bị ghi đè chữ về số đo tự động (`<>`); nếu số đúng phải khác thì sửa hình học, không sửa chữ | **Số in ra có thể đổi**: phải đối chiếu với thiết kế trước khi chuyển | Mở thuộc tính kích thước, xoá chữ ghi đè; dùng `handles` để tìm đúng đối tượng |
| VS-07 | Đổi kiểu chữ dùng phông không Unicode (SHX, TCVN3, VNI) sang phông Unicode của công ty | Chữ tiếng Việt hiện đúng trên máy khác; có thể đổi độ rộng chữ, cần xem lại bố cục | Sửa phông của kiểu chữ trong bảng kiểu chữ; chữ cũ nhập bằng mã TCVN3/VNI có thể cần chuyển mã |

Ghi chú:

- VS-06 là lỗi E: phải xử lý trước bàn giao. Không tự "sửa số cho khớp": hỏi người thiết kế số nào đúng.
- VS-04 và VS-07 có `false_positive_risk` = medium: nhắc người dùng xem lại từng trường hợp (layer trình bày có thể được miễn qua hồ sơ công ty).
- Lệnh CAD trong bảng là gợi ý thông dụng; tên lệnh khác nhau giữa AutoCAD, BricsCAD, ZWCAD… Không chắc thì mô tả thao tác, không bịa tên lệnh.

## Mẫu trình bày

```text
cad-guard hiện chỉ đọc: dưới đây là đề xuất, bạn tự làm trong CAD và lưu thành tệp mới.

1. VS-06 (E) — 1 kích thước ghi đè chữ (handle A1)
   Làm: xoá chữ ghi đè để hiện số đo tự động; nếu số đo sai thì sửa hình.
   Ảnh hưởng: số in ra có thể đổi — đối chiếu với thiết kế.
2. VS-07 (W) — 1 chữ có dấu dùng phông SHX không Unicode
   Làm: đổi phông của kiểu chữ S_… sang phông Unicode của công ty.
...
Làm xong, gửi tệp mới để tôi kiểm lại bằng audit.
```
