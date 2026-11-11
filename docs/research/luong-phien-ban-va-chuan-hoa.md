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

## 6. Bước 1 đã làm: hồ sơ trình bày (11/11/2026)

Hướng đã chọn: AI/code **đọc và chú giải** bản vẽ, code kiểm và dựng; không viết lại bản vẽ. Bước 1 là học CÁCH
TRÌNH BÀY của một công ty/người vẽ một lần, người dùng duyệt, code dùng cho mọi bản vẽ kiểu đó.

- `cadguard/drafting.py` (`cg.drafting-profile/1`, `drafting.yaml` cả máy hoặc `.cadguard/drafting.yaml` dự án, nhật ký
  `drafting-log.jsonl`): vai trò layer, thẻ số bản vẽ của khung tên, từ khoá ghi chú và nghĩa (tấm bù, thiết bị, khoang
  hở, ngăn kéo, kính, đèn; có bộ mặc định).
- Đề xuất bằng code (layer nét thấy/khác mang phần lớn nét của hình hạng mục -> thân đồ; ghi chú khớp nghĩa đã biết) và
  bằng AI (danh sách layer + ghi chú của hạng mục); harness `drafting.check`: layer phải có, nét dẫn phải thuộc layer đó,
  chữ khoá phải có trong ghi chú được dẫn. Người dùng Đồng ý mới ghi.
- Mọi chỗ đọc bản vẽ cho 3D/bản đồ dùng `drafting.read` (theo hồ sơ). Ghi chú "TẤM FIX…" trong một khối không cánh ->
  dạng `filler` (tấm bù), dựng thành tấm mỏng.
- App: nút "Hồ sơ trình bày" ở thanh công cụ 3D và trên thanh cảnh báo (`/api/drafting`, `/save`, `/propose`).
- Hai kiểu mẫu: `test 2.dxf` (Demo) -> code đề xuất layer "THAY" là thân đồ, khối 830 nhận đúng là tấm bù; bộ 40 tờ
  phiên 01 -> không có đề xuất (layer đã theo chuẩn), kết quả dựng giữ nguyên.

Bước sau (2): AI chú giải từng hạng mục từ ảnh tờ + nét (chia khối theo hình bỏ cánh, liên kết nhiều hình), bộ kiểm hình
học, màn duyệt; (3) bộ đáp án đo độ chính xác; (4) xuất bản vẽ đã chuẩn hoá ra tệp mới.

## 7. Bước 2 đã làm: chú giải hạng mục — chia khối tại vách thật (11/11/2026)

- `scene/annotate.py`: vách đứng = hai nét song song cách 8–60 mm (hoặc hình chữ nhật mảnh) cao ≥ 60 % khối; đường ráp
  hai cánh (một nét đơn) không phải vách. Hình đi kèm (cụm bản vẽ khác cùng khung tiêu đề, hoặc mặt đứng khác của hạng mục,
  bề ngang ±15 %) căn X bằng bỏ phiếu vị trí vách. Đường chia bám đầu kích thước ngang nếu có.
- Bộ kiểm hình học `check_split`: có vách thật ở vị trí đó (nét dẫn phải là nét của vách), không cắt qua cánh/ngăn kéo,
  hai phần ≥ 150 mm, không chia tấm bù/tấm ốp. Đợt hai bên vách cùng cao độ = vách chia trong cùng tủ: không đề xuất.
- Đề xuất bằng code tự hiện trên thanh cảnh báo màn 3D + đường cam đứt trên hình 2D; "Nhờ AI đọc bản vẽ" gửi các ứng
  viên cho AI phân biệt ranh giới tủ / vách chia trong tủ (AI chỉ chọn trong ứng viên, qua cùng bộ kiểm; AI đồng ý với code
  -> nhãn "Code + AI đồng ý"). Xác nhận -> khoá `split:<hạng mục>`; bộ dựng cắt khung khối, chia nét/cánh theo tâm,
  đếm lại đợt; "Bỏ chia khối" để quay lại.
- Đo: `test 2.dxf` (Demo) tủ áo 1800 -> 1200 (2 cánh) + 600 (cột ngăn kéo), rộng lấy từ kích thước ghi. Bộ 40 tờ: kệ TV
  (khối ngăn kéo 3690 -> 3 đề xuất theo vách khoang hở; kệ mở có vách giữa không bị chia), bếp ướt 2, lò sưởi 2 đề xuất —
  đều chỉ là đề xuất chờ người duyệt.

Chưa làm: AI xem ẢNH tờ bản vẽ (hiện AI đọc nét/chữ/kích thước có cấu trúc); bộ đáp án đo độ chính xác (bước 3);
xuất bản vẽ đã chuẩn hoá (bước 4).
