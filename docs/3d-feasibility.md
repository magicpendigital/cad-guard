# Đánh giá khả năng dựng 3D từ bản vẽ kỹ thuật 2D (3D-0, Luồng 2)

Ngày đo: 10/11/2026. Tệp: bản vẽ nội thất của phiên chạy thử 01 (DXF ~50 MB, 40 tờ A3 trong Model, đã có template khung
tên). Tệp nằm ngoài repo, chỉ đọc. Tài liệu này **chỉ ghi số cấu trúc** (đếm, tỉ lệ), không chữ, không tên khách, không
toạ độ. Số liệu sinh lại được bằng `cadguard scene-assess <dxf> --json` (`cadguard/scene/feasibility.py`, lược đồ
`cg.scene-feasibility/1`).

## 1. Cách đo

Bộ đọc mới `scene/views2d.py` + `scene/plan.py`, tất định, không LLM:

1. **Vai trò layer** học từ tên (từ khoá tiếng Việt/Anh, bỏ dấu: tường, nội thất, nét cắt, nét khuất, kích thước, chữ,
   ký hiệu…) và từ loại đối tượng chiếm đa số trên layer. Người dùng ghi đè được.
2. **Hình chiếu trong tờ**: mỗi tờ chứa nhiều hình chiếu, mỗi hình có tiêu đề chữ lớn ("MẶT BẰNG…", "MẶT ĐỨNG…",
   "MẶT CẮT X1…"). Gom đối tượng thành cụm theo khoảng hở 5 mm trên giấy × hệ số tờ, gán cụm cho tiêu đề nằm trong
   khung cụm (cách công ty đặt tiêu đề bên phải hình), không có thì tiêu đề gần nhất bên dưới.
3. **Hạng mục** = các tờ cùng tiền tố số bản vẽ trong khung tên (`<mã>.<hạng mục>. <tờ>`).
4. **Ký hiệu mặt cắt**: khối có thuộc tính nhãn dạng `x1`, `y2`, `1-1` trỏ tới hình "MẶT CẮT X1" cùng hạng mục.
5. **Kích thước gắn hình**: DIMENSION thẳng có hai điểm đo trùng toạ độ đỉnh của nét hình (sai số 1 đơn vị). Để đo được,
   mô hình `cg.drawing/1` thêm trường tuỳ chọn `dim_pts`, `dim_angle`, `dim_kind` (cả hai bộ đọc, có test so khớp).

## 2. Số đo

| Chỉ số | Giá trị |
| --- | --- |
| Tờ nhận được | 40 / 40 (khung tên trong Model) |
| Layer | 47; nhận vai trò từ tên: 31, chưa rõ ("other"): 16 |
| Hình chiếu có tiêu đề | 121: mặt bằng 16, mặt đứng 36, mặt cắt 50, chi tiết 12, ảnh minh hoạ 7 |
| Hình chiếu có hình học | mặt bằng 16, mặt đứng 28, mặt cắt 36, chi tiết 10; cụm không tiêu đề có nội dung: 4 |
| Hạng mục (nhóm tờ theo số bản vẽ) | 11; tờ đơn không có số theo mẫu: 1 (mặt bằng nội thất tầng) |
| Hạng mục có cả mặt bằng và mặt đứng | 8 / 11 |
| … trong đó căn được trục X mặt bằng ↔ mặt đứng bằng một kích thước ngang chung (cùng số đo) | 7 / 8 |
| Hạng mục có mặt cắt | 10 / 11 |
| Ký hiệu mặt cắt | 67; trỏ tới đúng nhãn hình mặt cắt cùng hạng mục: 55 (82,1 %) |
| DIMENSION trong Model | 2.582; thẳng có điểm đo: 2.565 |
| Kích thước ngang/dọc nằm trong hình chiếu | 2.494; **hai điểm đo trùng đỉnh hình: 2.211 (88,7 %)** |
| Mặt đứng có kích thước sàn–trần (kích thước dọc lớn nhất chạm đáy hình) | 26 / 28 (92,9 %) |
| Cụm đồ ở mặt bằng hạng mục (nét nội thất/nét cắt chạm nhau, ≥ 200 mm) | 33; rộng có kích thước: 8; rộng + sâu có kích thước: 7 (21,2 %) |
| Cụm đồ ở mặt đứng hạng mục | 22; rộng có kích thước: 11; rộng + cao có kích thước: 7 (31,8 %) |
| Mặt bằng tầng: đoạn tường đọc được trên layer tường | 12, trong đó 10 chỉ là một mặt tường (chưa biết dày) |
| Mặt bằng tầng: phòng (tường đôi khép kín) | 0 |
| Bộ dựng `cg.scene/1` cũ trên tệp này | 0 tường, 0 mô-đun |
| Thời gian đọc + phân tích | ~4,5 s đọc DXF, ~0,3 s phân tích |

## 3. Nhận định

- **Mức hạng mục đồ (tủ bếp, kệ, tủ sảnh…) khả thi.** Cách công ty vẽ rất đều: mỗi hạng mục có mặt bằng + mặt đứng
  (+ mặt đứng bỏ cánh) + mặt cắt, kích thước gắn đúng đỉnh hình gần 9/10, kích thước tổng xuất hiện ở cả mặt bằng và
  mặt đứng nên căn được hai hình tất định (7/8), cao sàn–trần có kích thước ở hầu hết mặt đứng. Đủ để dựng khối tủ
  (rộng/sâu từ mặt bằng, cao/cao độ từ mặt đứng, chia cánh từ hình chữ nhật cánh) và tường sau + sàn + trần.
- **Kích thước cấp cụm còn thấp (21–32 %)** vì nét tủ là nhiều tấm rời, cụm gom theo nét chạm nhau chưa trùng đúng
  khung có kích thước tổng (kích thước tổng đo từ mép tường/mép tấm). Bộ dựng dùng kích thước tổng chung của hai hình để
  căn và lấy rộng; phần không có kích thước vẫn là số đo trên hình (`source: geometry`), không phải số đoán.
- **Mức phòng từ mặt bằng tầng: chưa khả thi trên tệp này.** Mặt bằng tầng gần như không có tường trên layer tường
  (tường nằm trong khối xref/nét cắt chung), 0 phòng khép kín. Cần người dùng gán layer tường cho mặt bằng tầng hoặc
  tệp kiến trúc riêng. Tạm thời "phòng" = vùng hạng mục: tường từ mặt bằng/mặt đứng hạng mục, cao trần từ kích thước.
- Ghép mặt bằng ↔ mặt đứng ↔ mặt cắt đã tất định ở phần lớn trường hợp; phần còn lại (1/8 hạng mục, 12/67 ký hiệu)
  để LLM **đề xuất** và người xác nhận, kích thước luôn từ hình học/kích thước.
- Rủi ro: hướng nhìn mặt đứng (A/B/C) với dải tủ chữ L chưa biết quay vào cạnh nào của mặt bằng (mới hỗ trợ dải thẳng);
  tủ trên ở mặt bằng thường vẽ nét khuất, có hạng mục không vẽ thì chiều sâu tủ trên thành `gaps[]`.

## 4. Khuyến nghị

**Đi tiếp, phạm vi hạng mục** (3D-1 → 3D-4), mục tiêu tối thiểu một hạng mục bếp của tệp thử dựng đủ khối với cao lấy
từ bản vẽ. **Hoãn** dựng cả phòng từ mặt bằng tầng cho tới khi có layer tường (người dùng gán) hoặc tệp kiến trúc.
Chỉ tiêu theo dõi khi làm tiếp: tỉ lệ khối có cả ba chiều từ bản vẽ (không `default`), số `gaps[]` mỗi hạng mục, thời gian
người dùng xác nhận ghép.

## 5. Kết quả làm thử 3D-1 → 3D-4 (10/11/2026, cùng tệp)

Bộ dựng `cg.scene/2` (`scene/assemble.py`) chạy trên 11 hạng mục, không người nhập, không LLM:

| Chỉ số | Giá trị |
| --- | --- |
| Hạng mục dựng được ít nhất 1 khối | 6 / 11 (5 hạng mục còn lại: không có mặt bằng hoặc không có mặt đứng có hình) |
| Khối tủ dựng được | 13; cánh/ngăn kéo nhận được: 34; đợt (từ mặt đứng bỏ cánh): 52 |
| Kích thước khối (rộng/sâu/cao, 39 số) | từ DIMENSION: 12 (31 %); đo trên nét hình: 27 (69 %); **mặc định/đoán: 0** |
| Cao sàn–trần | 7 hạng mục, đều từ kích thước ghi trên bản vẽ |
| Phần thiếu `gaps[]` | 2 chiều sâu tủ treo (mặt bằng không vẽ nét khuất), 13 mặt đứng/hạng mục chưa ghép được (khác hướng nhìn, thiếu hình) |
| Tường trong cảnh hạng mục | 1 (mặt bằng hạng mục ít khi vẽ tường trên layer tường) |
| Mục tiêu tối thiểu "1 phòng" | Đạt ở mức hạng mục bếp khô: 4 khối (tủ dưới, tủ cao, hai cụm tủ trên/kệ), 8 mặt cánh/ngăn kéo, cao trần 2885 từ kích thước, 1 `gap` sâu tủ treo phải; GLB + trang xem cùng mã cảnh |
| Ảnh phối cảnh | Trình xem HTML/canvas sẵn có và GLB (mở được bằng trình xem glTF bất kỳ). Blender MCP không chạy trong phiên đo nên chưa có ảnh render |

Nhận xét: khối hộp và cánh đúng vị trí tương đối, nhưng phần lớn kích thước khối là "đo trên nét" chứ chưa bám kích thước ghi
(kích thước ghi thường đo từng ô/cánh, không đo hộp tủ). Tách khối dựa trên nhóm cánh nên cụm thiết bị không có cánh (lò,
tủ lạnh) có thể thành khối thấp lạ (vd. một khối cao 289): cần người xác nhận nhãn trên App trước khi đánh giá công thái học.

Công thái học (3D-4, `standards/ergonomics-v0.yaml`, `cadguard/ergonomics.py`): 8 tiêu chí ER-01…ER-08, **mọi khoảng
khuyến nghị để trống, trạng thái "chờ duyệt"** (chỉ ghi tài liệu nên tra: EN 1116, ISO 3055, QCVN 10, số liệu nhân trắc
học người Việt… người duyệt phải kiểm số hiệu và chép khoảng). Trên tệp thử: các tiêu chí có số đo đều báo "chờ duyệt"
(chỉ hiện số đo), ER-06 vùng quét cánh "đạt" ở 3 hạng mục có cánh. Bộ fixture có đáp án: cao mặt bàn 850/700 (đạt/không đạt
với khoảng thử), cánh 596 quét vào lối đi 450 (va 146 mm); harness loại 100 % mục nhận xét không có số đo làm bằng chứng
hoặc có số bịa (test `tests/test_ergonomics.py`).

## 6. Việc tiếp theo đề xuất

1. Người duyệt điền khoảng ER-xx có nguồn (tạo `ergonomics-v0.1`), rồi mới bật kết luận đạt/không đạt.
2. Ghép mặt đứng hướng B/C với dải tủ chữ L (quay trục theo ký hiệu hướng nhìn trên mặt bằng).
3. Bám mép khối vào kích thước ghi gần nhất (tăng tỉ lệ `dimension` từ 31 %), nhận diện thiết bị (lò, chậu, bếp) cho ER-08.
4. Gọi LLM thật để đề xuất ghép/nhãn (đã có dữ liệu gửi `/api/scene/prompt` và mã kiểm `/api/scene/propose`; chưa nối engine).
5. Render phối cảnh bằng Blender khi có Blender + MCP trên máy (GLB đã sẵn).
