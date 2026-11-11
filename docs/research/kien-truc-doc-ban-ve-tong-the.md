# Thiết kế: đọc bản vẽ nội thất theo kiến trúc tổng thể (11/11/2026)

Trạng thái: **đã duyệt 11/11/2026**. P1 xong (§9); P2–P7 chưa làm.

## 1. Vấn đề

Cách dựng 3D hiện tại (`scene/assemble.py`, `segment.py`, `interior.py`, `annotate.py`) là một chuỗi quyết định nối tiếp, mỗi
quyết định một ngưỡng hoặc một quy tắc:

- "tiêu đề có BỎ CÁNH" → hình bỏ cánh;
- "nét cách nhau ≤ 62 mm" → cùng một tấm;
- "polyline 3 điểm có hai đầu khác cạnh" → đường khấu.

Mỗi quy tắc áp cho mọi tệp, không riêng một tệp. Nhưng cách tìm ra chúng là **vá theo từng ca**: mỗi thói quen vẽ mới
(của một người, một công ty) lại cần thêm quy tắc. Ba điểm yếu gốc:

1. **Quyết định sớm và cứng.** Bước đầu đoán sai (ví dụ nhận nhầm hình có cánh) thì mọi bước sau sai theo, không bước nào
   quay lại sửa.
2. **Layer và tiêu đề quyết định quá nhiều.** Người vẽ chép tiêu đề, vẽ chú thích lên layer nét khuất, vẽ thân tủ lên
   layer nét thấy… đều làm hỏng kết quả.
3. **Không có mô hình tủ chung để kiểm.** Kết quả là danh sách khối và số đếm. Không có chỗ để hỏi "cách hiểu này có
   thành một cái tủ làm được không?".

Mục tiêu của thiết kế: **một bản vẽ vẽ theo kiểu mới phải được xử lý bằng dữ liệu (hồ sơ trình bày, đáp án) và bộ kiểm
nhất quán, không phải bằng nhánh code mới.**

## 2. Kiến trúc 5 lớp

```
L0 Đọc tệp        DXF → DrawingModel (đã có)
L1 Nguyên tố      nét/chữ → Tấm · Khung · Ký hiệu · Ghi chú · Kích thước (mỗi cái kèm handle + độ tin)
L2 Hình chiếu     vùng hình + VAI TRÒ theo nội dung (có cánh / bỏ cánh / mặt bằng / mặt cắt / chi tiết) + phép đổi toạ độ
L3 Mô hình tủ     cg.cabinet/1: thùng → khoang → tấm, mặt trước, đồ bên trong, ghi chú (mọi thuộc tính có nguồn)
L4 Chọn cách hiểu sinh vài giả thuyết ở chỗ mơ hồ → chấm bằng ràng buộc kết cấu + đối chiếu hình → chọn / hỏi người
L5 Tri thức       hồ sơ trình bày của công ty (dữ liệu), AI phân loại phần mơ hồ (có bằng chứng, qua L4)
```

Tấm ván, danh sách cắt, 3D và kiểm kết cấu **chỉ đọc L3**. Thay cách vẽ thì L1–L2 đổi, phía sau không đổi.

### L1. Nguyên tố hình học

Tách mọi bản vẽ thành cùng một bộ "mẩu", không phụ thuộc layer. Layer chỉ là gợi ý có trọng số.

| Nguyên tố | Nhận ra từ | Thuộc tính |
|---|---|---|
| Tấm (board) | chồng nét song song sát nhau, dài gần bằng nhau; hoặc khung mảnh | hướng (ngang/đứng), dày, đoạn phủ, số nét, có tựa không |
| Khung (frame) | khung kín ≥ 150 × 150 | có chứa khung khác không, các cạnh trùng tấm nào |
| Ký hiệu (symbol) | nét chéo, dấu X, polyline gãy, vòng tròn lớn | loại: mở cánh, ngăn kéo, ô thiết bị/khoang hở, khấu/bo cong, vòng chú thích, đường dẫn |
| Ghi chú (note) | chữ + điểm neo (đường dẫn, vị trí) | nghĩa theo hồ sơ trình bày (có thể nhiều nghĩa) |
| Kích thước (dim) | DIMENSION | trục, số đo, hai điểm đo |

Mỗi nguyên tố mang `handles` (bằng chứng, dùng cho "Tới trong AutoCAD") và `conf` (độ tin 0–1). Mã hiện có chuyển vào
lớp này: chồng nét và "tựa" (`interior.levels`), nhận ký hiệu (`segment.fronts`, `interior.is_curve_mark`,
`is_callout`), nghĩa chữ (`drafting.meaning_of`).

### L2. Hình chiếu và vai trò

- Vùng hình: giữ cách phân vùng hiện có (`views2d`, tách cụm, nhóm theo tiêu đề).
- **Vai trò theo đặc trưng nội dung**, tiêu đề chỉ là một đặc trưng có trọng số. Các đặc trưng:
  - diện tích ký hiệu mở cánh;
  - số khung mặt trước;
  - ghi chú nội thất (hộc, thanh treo, thiết bị);
  - tỉ lệ khung hình;
  - kích thước ngang/dọc;
  - kích thước chung với hình khác.

  Kết quả là xác suất cho từng vai trò, không phải một nhãn.
- Ghép hình (đã có theo kích thước chung) cho ra phép đổi toạ độ của hình về toạ độ hạng mục. Từ đó mọi nguyên tố của mọi
  hình đặt chung một hệ toạ độ.

### L3. Mô hình tủ chuẩn `cg.cabinet/1`

```
Hạng mục
 └─ Khối (thùng): x, y, z0, rộng, sâu, cao, dạng (tủ / kệ mở / tấm ốp / tấm bù)
     └─ Cây khoang: chia bởi tấm đứng (vách) và tấm ngang (đợt, nóc hộc, mặt đá…)
         ├─ Khoang lá: mặt trước (cánh / ngăn kéo / để hở / ô thiết bị)
         └─ Đồ bên trong: thanh treo, hộc trong, đèn, đợt kính…
 └─ Ghi chú gắn khối: khấu/bo cong (cạnh, bán kính, hình chi tiết), mối ghép, vật liệu
```

Mỗi thuộc tính có `src` (kích thước / hình học / người nhập / mặc định), `evidence` (handles) và `conf`. `Scene2` hiện
tại là một "ảnh chiếu" của mô hình này. Có bộ chuyển hai chiều để giữ tương thích (app, bench, supplement không đổi khoá).

### L4. Sinh giả thuyết và chấm bằng ràng buộc

Ở mỗi chỗ mơ hồ, máy sinh 2–4 cách hiểu thay vì chọn ngay:

- vai trò hình;
- khối chia ở đâu;
- nét đôi là tấm hay mép cánh;
- ký hiệu là cánh hay đường khấu;
- chiều sâu lấy từ hình nào.

Mỗi tổ hợp được dựng thành một mô hình L3 và chấm điểm:

| Nhóm ràng buộc | Ví dụ | Loại |
|---|---|---|
| Kết cấu | tấm ngang phải tựa hông/vách; cánh bản lề phải có tấm đứng để bắt; mặt trước lát kín mặt khoang, không chồng nhau; đợt nằm trong khoang | cứng (loại) hoặc phạt |
| Đối chiếu hình | rộng khối ở mặt đứng = ở mặt bằng; cao độ tấm ở mặt đứng = ở mặt cắt; ranh khoang ở hình bỏ cánh khớp ranh cánh ở hình có cánh | phạt theo độ lệch |
| Bằng chứng | số kích thước dẫn tới, ghi chú khớp nghĩa, độ tin nguyên tố | cộng điểm |
| Thói quen công ty | hồ sơ trình bày: "tấm fix" là tấm bù, khoảng hở chân 100… | cộng/phạt nhẹ |

Máy chọn tổ hợp điểm cao nhất. Khi **khoảng cách điểm giữa hai cách hiểu tốt nhất nhỏ**, máy không đoán. Nó tạo thẻ
"máy phân vân" trên màn 3D, kèm hai phương án và bằng chứng của mỗi phương án (khoanh trên hình 2D). Người chọn xong thì
lưu vào supplement như các khoá hiện có. Tìm kiếm có giới hạn (chùm 8–16 tổ hợp mỗi hạng mục), nên vẫn tất định và lặp
lại được.

Các bộ kiểm hiện có trở thành ràng buộc: `structure.check` (S01–S06), `annotate.check_split`, bộ kiểm đề xuất AI.

### L5. Tri thức là dữ liệu

- **Hồ sơ trình bày** (`drafting.py`, đã có) mở rộng thêm:
  - quy ước ký hiệu (vd. "khấu vẽ bằng polyline gãy trên layer khuất");
  - các tham số hiện đang là hằng số trong code: khe chồng nét, vùng chân/nóc, nhịp…

  Mỗi công ty hoặc người vẽ có một hồ sơ. Code và AI đề xuất, người duyệt.
- **AI** chỉ làm việc phân loại hẹp có bằng chứng: nghĩa của một ghi chú lạ, vai trò một hình khó, loại một ký hiệu lạ.
  Kết quả vào L4 như một nguồn điểm, không ghi thẳng vào mô hình.

## 3. Khi gặp một ca mới thì làm gì

1. Lưu đáp án cho ca đó ("Lưu làm đáp án"), hoặc thêm kiểu vẽ tương ứng vào bộ mô phỏng (`synth.STYLES`).
2. Chạy bộ đo. Bảng chấm (§5) cho biết ca sai ở lớp nào.
3. Sửa theo thứ tự ưu tiên:
   - hồ sơ trình bày (dữ liệu);
   - trọng số hoặc ràng buộc L4;
   - nguyên tố L1 mới (ví dụ một loại ký hiệu chưa có).

   Chỉ khi cả ba không đủ mới thêm code đặc thù.
4. Cổng chất lượng trước khi gộp:
   - bộ mô phỏng không giảm điểm ở kiểu nào;
   - bộ 40 tờ thật không đổi kích thước;
   - mọi thay đổi số đếm phải được soát bằng ảnh.

## 4. Đối chiếu với code hiện có

| Lớp | Đã có | Cần làm |
|---|---|---|
| L1 | chồng nét + tựa, ký hiệu cánh/X/khấu/vòng chú thích, nghĩa chữ | gom thành `scene/primitives.py` dùng chung; thêm độ tin; đường dẫn chú thích |
| L2 | phân vùng, nhóm theo tiêu đề, ghép theo kích thước, phân biệt có cánh/bỏ cánh khi tiêu đề trùng | bộ chấm vai trò theo đặc trưng cho mọi hình (không chỉ khi trùng tiêu đề) |
| L3 | `Scene2` + `inner` + `features` | `cg.cabinet/1` có cây khoang; bộ chuyển ↔ `Scene2`; tấm ván đọc từ cây khoang |
| L4 | các bộ kiểm rời (kết cấu, chia khối, đề xuất AI) | sinh giả thuyết + chấm điểm + thẻ "máy phân vân" |
| L5 | hồ sơ trình bày (layer, từ khoá), AI có bằng chứng | đưa hằng số vào hồ sơ; quy ước ký hiệu; AI phân loại ký hiệu/vai trò |

## 5. Lộ trình (mỗi giai đoạn gộp riêng, có cổng đo)

| GĐ | Việc | Xong khi |
|---|---|---|
| P1 | Tách L1 (nguyên tố) khỏi `assemble`/`segment`/`interior`, chưa đổi hành vi | bộ mô phỏng + 40 tờ cho kết quả y hệt |
| P2 | `cg.cabinet/1` + bộ chuyển; tấm ván, danh sách cắt, kiểm kết cấu đọc từ cây khoang | như trên; danh sách cắt không đổi |
| P3 | Bộ chấm ràng buộc chạy ở chế độ "chỉ báo": hiện mâu thuẫn trên màn 3D, chưa đổi lựa chọn | mâu thuẫn hiện đúng trên các ca đã biết |
| P4 | Bật sinh giả thuyết cho 3 quyết định rủi ro nhất: vai trò hình, chia khối, tấm hay mép cánh; thẻ "máy phân vân" | bộ đo không giảm; ca TESt 2 đúng mà không cần quy tắc riêng |
| P5 | Đối chiếu nhiều hình: mặt cắt cho chiều sâu và cao độ tấm; khoang ở hình bỏ cánh ↔ cánh ở hình có cánh | điểm "sâu" và "nội thất" tăng trên bộ đo |
| P6 | Đưa hằng số vào hồ sơ trình bày; AI phân loại ký hiệu/vai trò lạ (qua L4) | thêm một kiểu vẽ mới chỉ bằng hồ sơ, không sửa code |
| P7 | Chỉ số "đúng không cần sửa" theo kiểu vẽ / công ty trên màn Tổng quan | có số theo tuần |

P1–P2 là tái cấu trúc, rủi ro thấp nhờ cổng "kết quả y hệt". P3–P4 là thay đổi lớn nhất. P5–P7 tăng dần.

## 6. Đo lường

- **Chỉ số chính:** % hạng mục dựng đúng hoàn toàn (khối, số đo, cánh, nội thất) mà không cần người sửa. Đo riêng theo
  kiểu vẽ, theo người vẽ, theo công ty.
- **Chỉ số phụ:**
  - số thẻ "máy phân vân" trên mỗi hạng mục (thấp mà vẫn đúng là tốt);
  - % số đo có nguồn "Ghi";
  - thời gian dựng một hạng mục.
- **Nguồn đáp án:** bộ mô phỏng (12 kiểu, tăng dần) và 10–20 hạng mục thật từ ít nhất 3 người vẽ khác nhau. Đáp án thật
  là phần quan trọng nhất và cần người kỹ thuật.

## 7. Rủi ro và giới hạn

- **Phức tạp hơn:** chọn cách hiểu theo điểm khó giải thích hơn một quy tắc. Bù lại, mỗi lựa chọn hiện điểm và bằng chứng
  của các phương án, và thẻ "máy phân vân" cho người quyết định.
- **Tốc độ:** sinh tổ hợp có thể chậm ở hạng mục lớn. Giới hạn chùm và lưu kết quả theo băm nội dung (bộ chạy luồng đã có
  cơ chế này).
- **Không thay được bản vẽ thiếu thông tin:** số không có trên bản vẽ thì vẫn phải hỏi người. Kiến trúc này chỉ giúp hỏi
  đúng chỗ và ít lần hơn.
- **Hình cong (khấu, bo tròn):** mô hình ghi được, nhưng 3D cong cần thêm phần dựng hình. Việc này để sau P5.

## 8. Cần anh/chị quyết

1. Duyệt hướng 5 lớp và thứ tự P1 → P7, hoặc chỉnh thứ tự.
2. Người kỹ thuật nào ghi 10–20 đáp án thật, và từ những người vẽ nào.
3. Công ty / kiểu vẽ nào ưu tiên trước, để hồ sơ trình bày đầu tiên làm theo kiểu đó.

## 9. Đã làm

**P1 — lớp nguyên tố (11/11/2026).** `scene/primitives.py`:
- kiểu dữ liệu `Board`, `Frame`, `Symbol`, `Note`, `Primitives`, mỗi cái kèm `refs` và `conf`;
- hàm dùng chung: chồng nét thành tấm ngang và kiểm tựa, tấm đứng (vách), ô, ô dấu X, ký hiệu mở cánh / khấu / vòng
  chú thích, nghĩa chữ (cả khi một chữ có nhiều nghĩa);
- `extract(d, view)` trích mọi nguyên tố của một hình.

`interior`, `segment` và `assemble` dùng lớp này thay cho bản sao riêng; tên cũ vẫn giữ để nơi gọi không phải sửa.

Cổng kiểm: chụp toàn bộ cảnh, tấm ván và danh sách cắt của 102 hạng mục (bộ 40 tờ thật, 3 tệp thử của phiên Demo, 72
hạng mục mô phỏng) trước và sau khi tách. Hai bản **giống hệt** (cùng mã băm). Test: `tests/test_primitives.py`.
