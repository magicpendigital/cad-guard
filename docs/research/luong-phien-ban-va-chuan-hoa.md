# Luồng phiên bản bản vẽ và chuẩn hoá trước khi dựng 3D (11/11/2026)

## 1. Vấn đề quan sát được

- Mỗi lệnh sửa (Chuẩn hoá Unicode, Dịch, Sửa hàng loạt, áp đề xuất) ghi ra **tệp mới** (`… .cg-xxxxxxxx.dxf`,
  `… .zhlayer.dxf`), bản gốc giữ nguyên. Đây là rào an toàn đúng, nhưng người dùng thấy nhiều tệp rời và dễ mở nhầm
  bản gốc chưa chuẩn hoá ở bước sau. Màn "Việc của tôi" còn liệt kê **bản gốc** cho phòng sau: lỗi luồng.
- 3D dựng sai mà người dùng không biết vì sao: phần thiếu chỉ nằm ở cuối màn 3D hoặc màn Bản đồ.
- Mỗi người kỹ thuật trình bày một kiểu (khung tên không có số bản vẽ, thân tủ trên layer "nét thấy", tiêu đề hình
  chép nhầm "BỎ CÁNH", ba hình đặt cạnh nhau dưới một tiêu đề). Luật cứng của code không phủ hết.

## 2. Các phương án lưu phiên bản

| Phương án | Ưu | Nhược | Kết luận |
|---|---|---|---|
| A. Mỗi lệnh một tệp rời (trước đây) | an toàn, đối chiếu được | người dùng phải tự chọn tệp, dễ nhầm | giữ cách lưu, đổi cách **trình bày** |
| B. Sao lưu bản gốc một lần, các lệnh ghi đè lên tệp đang mở | luôn là dữ liệu mới nhất | mất các bước trung gian (không đối chiếu, không hoàn tác từng bước); ghi đè tệp AutoCAD đang mở dễ hỏng/khoá; trái quy tắc "ghi ra tệp mới" | không chọn |
| C. Nhánh như Git | mạnh cho phương án thiết kế A/B | quá nặng với người vẽ (merge, xung đột bản vẽ nhị phân không gộp được) | chỉ giữ nhánh ngầm, không đưa khái niệm Git ra giao diện |
| D. **Dòng phiên bản + "bản đang dùng"** | một bản vẽ có lịch sử; phòng sau tự nhận bản mới nhất; hoàn tác/làm lại không mất tệp | tốn đĩa (mỗi bản ~ dung lượng tệp) | **chọn** |

Cách các hệ quản lý dữ liệu bản vẽ trong ngành (PDM/quản lý hồ sơ của các hãng CAD, phần mềm sản xuất nội thất) thường
làm: phân biệt **phiên bản làm việc** (tự tạo mỗi lần lưu/sửa, người dùng mặc định mở bản mới nhất, bản cũ chỉ đọc) với
**bản phát hành** (revision A, B, C… khi duyệt giao xưởng, ghi lên khung tên). Xưởng chỉ nhận bản đã phát hành. Nhánh
chỉ dùng khi có phương án thiết kế song song, không dùng cho các bước chuẩn hoá.

## 3. Đã làm

- `app/versions.py`: dựng dòng phiên bản từ nhật ký áp dụng (`.cadguard/changesets/*.apply.json`: nguồn → tệp ra,
  thời điểm, thao tác). "Bản đang dùng" mặc định là bản mới nhất còn trên đĩa, lưu ở `.cadguard/versions.json`.
- Hoàn tác / Làm lại ở mức phiên bản: đổi bản đang dùng sang bản cha / bản vừa rời, **không xoá tệp**. Lịch sử phiên
  bản: xem mọi bản (thay đổi gì, lúc nào) và chọn bản đang dùng. Hoàn tác một changeset (xoá tệp ra) vẫn giữ như cũ.
- Danh sách tệp: nhãn "Đang dùng" / "Bản cũ". Mở bản cũ: thông báo ngay "Bạn đang mở một bản CŨ", nút "Mở bản đang
  dùng" / "Dùng bản này". Màn "Việc của tôi" chỉ đưa **bản đang dùng** cho từng phòng.
- Áp lệnh lên một bản cũ tạo nhánh mới (tệp mới); nhánh cũ vẫn trong lịch sử.

## 4. Chuẩn hoá trước khi dựng 3D

Thứ tự: code đọc tất định → code đọc theo cách khác (dự phòng) → AI đọc và đề xuất → người dùng xác nhận.

- Code dự phòng mới (đo trên `test 2.dxf` của phiên Demo, ngoài repo): khung tên không có số bản vẽ thì nhóm hạng mục
  theo tên đồ trong tiêu đề hình; thân tủ trên layer nét thấy thì dùng cả nét thấy; một khung tiêu đề chứa nhiều bản vẽ
  cách nhau bằng khe trống thì chỉ dùng bản vẽ chứa kích thước khớp mặt bằng; hình đặt tiêu đề "bỏ cánh" vẫn nhận cánh
  nếu có ký hiệu mở cánh. Kết quả: tủ áo từ "không dựng được" thành 2 khối, 5 cánh/ngăn kéo; còn thiếu chiều sâu và cao
  trần, hiện rõ để nhập.
- Gợi ý bằng code: chiều sâu thiếu lấy từ kích thước ngang của mặt cắt cùng hạng mục.
- AI đọc bản vẽ (`app/scene_ai.py`): nhận tiêu đề hình, kích thước, chữ có số của hạng mục; được đề xuất **số** cho ô
  phần thiếu nhưng mỗi số phải dẫn handle kích thước/chữ có đúng số đó (harness `scene/proposals.validate`), không thì
  bị loại. Người dùng bấm Xác nhận mới ghi. Ẩn danh (NDA) bật thì chỉ chạy code.
- Màn 3D: thanh cảnh báo màu cam ngay trên khung 3D ("N chỗ CAD Guard chưa đọc được từ bản vẽ"), nói rõ là do bản vẽ
  thiếu/khác mẫu, có ô nhập và hai nút "Gợi ý bằng code" / "Nhờ AI đọc bản vẽ"; khối dùng số tạm tô màu cam trên 3D.

## 5. Bước sau

- "Phát hành" phiên bản giao xưởng (khoá, ghi Rev lên khung tên, xưởng chỉ nhận bản phát hành).
- Dọn bản trung gian: giữ bản gốc + bản phát hành + N bản gần nhất; xoá chỉ khi người dùng xác nhận.
- AI nhìn **ảnh** tờ bản vẽ (không chỉ chữ/kích thước) để đề xuất vùng hình và tiêu đề khi người vẽ đặt sai; vẫn qua
  harness và người xác nhận.
