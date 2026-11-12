# Thiết kế: đọc bản vẽ nội thất theo kiến trúc tổng thể (11/11/2026)

Trạng thái: **đã duyệt 11/11/2026**. P1–P7 xong (§9).

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

**P2 — mô hình tủ chuẩn `cg.cabinet/1` (11/11/2026).** `scene/cabinet.py`:
- `Cabinet` → `Unit` (khối) → cây `Node` (khoang). Phép chia "h" theo tấm ngang chạy suốt khoang, "v" theo vách chạy
  suốt chiều cao. Tấm không chạy suốt ghi ở `loose`.
- Cánh, ngăn kéo và đồ bên trong gắn vào khoang nhỏ nhất che ≥ 85 % diện tích của nó.
- `from_scene` / `to_scene` chuyển hai chiều không mất gì (thứ tự giữ bằng `_o`).
- `summary` cho ra cây khoang gọn, trả kèm màn 3D ở khoá `cabinet`.

Tấm ván, danh sách cắt và kiểm kết cấu (`panels_for`, `structure.check`) nay đọc mô hình này; truyền `Scene2` thì tự
chuyển. `Scene2` vẫn là dạng lưu và trả cho app.

Cổng kiểm trên 102 hạng mục:
- cảnh, tấm ván, danh sách cắt và kiểm kết cấu **giống hệt** trước P2 (cùng mã băm);
- `to_scene(from_scene(cảnh))` bằng đúng cảnh gốc ở cả 102 hạng mục.

Ví dụ tủ áo của ca thật: khoang gốc chia ngang bởi nóc hộc và đợt trên; khoang dưới chia đứng bởi vách giữa hai hộc;
khoang giữa chứa thanh treo và đèn; cặp cánh trên gắn vào khoang trên. Test: `tests/test_cabinet.py`.

**P3 — bộ chấm nhất quán, chế độ chỉ báo (11/11/2026).** `scene/consistency.py` chấm mô hình tủ đã dựng và liệt kê
mâu thuẫn kèm bằng chứng (handle). Bộ chấm **không đổi** cách dựng. Các mã:

- **Kết cấu:**
  - K01 hai mặt trước chồng nhau;
  - K02 mặt trước lòi ra ngoài khối;
  - K03 tấm ngang cắt qua vách;
  - K04 tấm ngang xuyên qua ô thiết bị / hộc trong;
  - K05 nội thất nằm ngoài khối;
  - K06 khoang treo dưới thanh treo thấp hơn 800.
- **Đối chiếu hình:**
  - H01 đường ráp giữa hai hàng cánh cao (≥ 400) không có tấm ngang phía sau;
  - H02 số đo khối là số mặc định.
- **Ghi nhận:** I01 khoang để hở, I02 nội thất đọc ở hình bỏ cánh.

Điểm khối = 1 − 0,3 × số mâu thuẫn − 0,1 × số cần xem; điểm hạng mục là trung bình các khối.

Nơi hiện kết quả:
- màn 3D có mục "Kiểm nhất quán", mỗi dòng có nút "Tới trong AutoCAD";
- bộ chạy luồng có bước "Kiểm nhất quán";
- API trả ở khoá `consistency`.

Kết quả trên 102 hạng mục:
- không mâu thuẫn nào; cảnh báo duy nhất còn lại là H02 (sâu mặc định ở hạng mục thật thiếu số sâu, và ở mẫu mô
  phỏng "sâu chỉ ở mặt cắt" khi chưa áp gợi ý), đúng thực tế;
- tủ áo của ca thật: 100/100;
- cảnh, tấm ván, danh sách cắt, kiểm kết cấu giống hệt trước P3.

Lần chạy đầu có H01 báo nhầm ở ngăn kéo hẹp bị xếp loại "cánh". Đã giới hạn H01 cho cánh cao ≥ 400; việc xếp loại cánh
và ngăn kéo theo tỉ lệ sẽ xem lại ở P4. Các mã còn lại đã thử bằng ca hỏng dựng tay (`tests/test_consistency.py`); chưa
có ca thật nào bộc lộ các mã này.

**P4 — sinh cách hiểu và chọn theo điểm (12/11/2026).** `scene/hypotheses.py`:

- `assemble.build_once` dựng **một** cách hiểu theo khoá bổ sung. `build_item_scene` (mọi nơi gọi: app, CLI, bộ đo,
  trợ lý, bản đồ, cả tầng) nay đi qua `hypotheses.resolve`.
- Mỗi cách hiểu là một bộ khoá bổ sung đã có, nên vẫn tất định:
  - `main:` + `interior:` cho vai trò hình. Giá trị mới của `interior:`: `none` (không có hình bỏ cánh, nét đôi là mép
    cánh) hoặc chính mã hình chính (đọc hình chính như hình bỏ cánh, nét đôi là tấm).
  - `split:` cho chia khối.
- Ba quyết định được dựng thử:
  - `role` — khi có ≥ 2 mặt đứng "sinh đôi": cùng mặt bằng, thân tủ cùng bề rộng (lệch ≤ 10 %) và cùng vị trí (chồng
    ≥ 80 %), và hoặc cùng tiêu đề, hoặc một hình có tiêu đề "bỏ cánh". Hai hướng nhìn khác tiêu đề (hướng A / hướng B của
    quầy) không phải cặp.
  - `board` — nét đôi ở hình chính là tấm hay mép cánh. Chỉ hỏi khi không có hình bỏ cánh riêng mà hình chính có chữ
    nội thất.
  - `split@x` — chia tại vách đề xuất hay giữ một khối (tối đa 3 đề xuất).
- Điểm = 0,35 × nhất quán (P3) + 0,25 × ký hiệu cánh + 0,30 × ghi chú nội thất được giải thích + 0,10 × bề rộng khối có
  kích thước.
  - Ký hiệu cánh: hình dựng cánh nên nhiều ký hiệu cánh nhất. Hình chính có ký hiệu/khung cánh mà cảnh không có mặt
    trước nào thì điểm phần này về 0. Có hình dáng bỏ cánh mà không dùng thì bị phạt.
  - Ghi chú: chữ hộc / thiết bị / thanh treo / đèn / kính / đá ở các hình sinh đôi phải có đồ cùng loại gần đó. Đồ đọc
    sai (hộc cao bất thường) không tính.
- Thêm ràng buộc K07: hộc trong cao > 600 là mâu thuẫn (cả khoang bị đọc thành hộc).
- Cách chọn:
  - phương án nào thêm mâu thuẫn kết cấu so với cách hiểu ban đầu thì bị loại;
  - máy chỉ đổi khi phương án khác hơn ≥ 0,05 điểm;
  - chênh ít hơn mà cảnh khác nhau thì giữ cách ban đầu và hiện thẻ "máy phân vân";
  - tối đa 16 lần dựng mỗi hạng mục.
- Người chọn trên thẻ (`/api/scene/decide`) thì ghi khoá của phương án vào tệp bổ sung, kèm mã quyết định vào
  `decided:<hạng mục>`. Máy không dựng thử lại quyết định đó cho tới khi người bấm "để máy chọn lại".

**Gỡ quy tắc riêng.** `interior.classify` (hai mặt đứng chép trùng tiêu đề thì hình nhiều ký hiệu cánh là hình có cánh)
không còn được gọi khi dựng. Khi đã có hình bỏ cánh riêng, hình chính luôn đọc như hình có cánh.

Cổng kiểm trên 102 hạng mục (bộ 40 tờ thật, các tệp thử phiên Demo, 72 mẫu mô phỏng):
- `build_once` không khoá cho kết quả giống hệt P3 (cùng mã băm);
- qua L4: khối, cánh, nội thất, tấm ván, danh sách cắt, kiểm kết cấu **giống hệt** P3 ở cả 102 hạng mục; chỉ khác
  dòng ghi chú (dòng "Vai trò hình …" / "Máy chọn cách hiểu …" thay dòng của quy tắc cũ);
- ca TESt 2 (tệp gốc): L4 chấm 4 cách hiểu, giữ đúng hình có cánh / hình bỏ cánh, hơn cách kế tiếp 0,24 điểm;
- tệp TEST.dxf của phiên Demo (tủ áo cùng kiểu vẽ, hai hình chép trùng tiêu đề, thứ tự hình ngược): cách dựng một lần
  chọn nhầm hình bỏ cánh làm hình chính; L4 tự chọn lại đúng (0,93 so với 0,53), không cần quy tắc riêng;
- 43 quyết định vai trò hình: 1 máy tự đổi (TEST.dxf), 42 giữ nguyên; 4 quyết định nét đôi: giữ cả 4; chia khối: 5
  phân vân (đã hiện thành đề xuất chia khối, không lặp thẻ), 3 giữ;
- lần thử đầu bị lỗi ở ba chỗ, đã sửa trước khi gộp:
  - quầy bar hai hướng nhìn bị coi là cặp "có cánh / bỏ cánh" → thêm điều kiện tiêu đề;
  - bàn trang điểm: cả khoang bị đọc thành hộc mà vẫn được tính là giải thích ghi chú → K07 và bỏ đồ đọc sai khỏi
    phần ghi chú;
  - kệ TV: phương án "không cánh" thắng vì phần ký hiệu cánh chưa phạt cảnh mất hết mặt trước → thêm luật về 0.

Hiển thị: màn 3D có mục "Cách hiểu bản vẽ" (điểm từng phương án, nút "Chọn cách này", "Tới trong AutoCAD", "để máy
chọn lại"); bước "Kiểm nhất quán" của bộ chạy luồng báo số chỗ phân vân (cần duyệt). Test: `tests/test_hypotheses.py`.

Giới hạn: điểm "ghi chú" và "ký hiệu cánh" mới đo trên các ca hiện có; cần đáp án thật (10–20 hạng mục) để chỉnh trọng
số. Chưa có quyết định "đường khấu hay cánh" và "chiều sâu lấy từ hình nào" (để P5).

**P5 — đối chiếu nhiều hình (12/11/2026).** `scene/sections.py` + bộ chấm nhất quán.

- **Nối mặt cắt ↔ khối:**
  - ký hiệu mặt cắt (nhãn "1-1", "X2"…) nằm trên mặt đứng dựng khối, X trong khoảng khối: cắt mọi khối cùng cột.
    Ký hiệu trỏ tới một hình mà hình đó không phủ dải cao của khối thì thử các mặt cắt cùng nhãn (bộ 40 tờ thật có
    nhiều tờ cùng nhãn "Y1", "Y2");
  - mặt cắt không có ký hiệu nào trỏ tới: nối khi thân tủ trong mặt cắt phủ đúng dải cao của khối (lệch ≤ 30 mm).
    Hai mặt cắt cho hai số sâu khác nhau thì không dùng.
- **Đọc ở dải cao của khối:** sâu = bề ngang thân tủ ở nửa giữa dải cao. Có kích thước ghi đúng đoạn đó thì nguồn là
  kích thước, không thì đo nét. Tấm = chồng nét ngang trong khung đó.
- **Dùng (`Module2.sections` ghi lại mọi mặt cắt đã nối):**
  - sâu cho khối đang mặc định;
  - thay sâu đo nét ở mặt bằng khi mặt cắt nối bằng ký hiệu có kích thước ghi (bằng chứng mạnh hơn);
  - khối không bị cắt: dùng sâu của mặt cắt cùng loại khối khi mặt bằng có mép trước đúng ở khoảng sâu đó tính từ
    tường (hai hình cùng xác nhận);
  - tấm cho khối chưa có tầng/vách nào và không có hình bỏ cánh.
- **Khoang ↔ mặt trước:**
  - ở hình có cánh, chồng nét ngang mà mọi nét đều là mép ngăn kéo thì không phải tấm. Đường ráp hai hàng cánh vẫn giữ,
    vì tủ thật thường có tấm phía sau (ca TESt 2: hình bỏ cánh có tấm ở 1925, sau đường ráp 1890–1915);
  - ≥ 3 mặt trước thấp (< 450) cùng cột là ngăn kéo, dù hẹp. Trước đây máy xếp loại theo tỉ lệ cao/rộng nên gọi nhầm
    là cánh.
- **Mâu thuẫn mới (cần xem):**
  - H03 sâu ở mặt cắt khác sâu đang dùng > 30 mm (một mục mỗi khối);
  - H04 tấm ở mặt cắt (tại vị trí ký hiệu) không có ở hình đứng;
  - H05 vách ở hình bỏ cánh nằm giữa một cánh.
- **Bộ đo** thêm chỉ số **nội thất**: khối có đáp án nội thất đọc đúng số tấm / đợt kính / thanh treo / hộc / vách. Ảnh
  chụp đáp án lưu cả số này. Kiểu mô phỏng "sâu chỉ ở mặt cắt" nay có ký hiệu mặt cắt trên mặt đứng, mỗi nhóm cao một mặt
  cắt, và tấm vẽ trong mặt cắt.

Kết quả (mã P4 trên `main` so với P5, chỉ code):

| Bộ | P4 | P5 |
|---|---|---|
| 72 mẫu có mặt cắt (4 tổ hợp kiểu vẽ × 18) | điểm 40 %, sâu 40 %, nội thất 73/82 | điểm 100 %, sâu 100 %, nội thất 82/82 |
| synth5 (36 mẫu ngẫu nhiên) | điểm 91,7 % | 100 % |
| synth4 (36 mẫu) | 100 %, nội thất 16/16 | 100 %, 16/16 |

Bộ 40 tờ thật và các tệp thử phiên Demo:
- chỉ đổi một khối: tủ treo fur.68 sâu 601 (đo nét mặt bằng) → 350 (kích thước ghi ở mặt cắt Y1);
- TESt 2 giữ nguyên;
- bộ chấm báo thêm H03 ở hai khối mà mặt bằng và mặt cắt lệch (sâu đo nét 1455 so với 558 ở mặt cắt; 595 so với 495)
  và H04 ở một tấm chỉ có ở mặt cắt (tủ treo fur.68, cao 2312), để người xem; không mâu thuẫn kết cấu nào.

Test: `tests/test_sections.py`.

Giới hạn:
- mặt cắt nằm (cắt ngang) chưa đọc;
- ký hiệu mặt cắt đặt ở mặt bằng chưa dùng, mới dùng ký hiệu trên mặt đứng;
- tủ treo ở mặt cắt không có kích thước sàn–trần thì lấy đáy thân tủ làm sàn, nên dải cao có thể lệch;
- tấm đọc ở mặt cắt được trải suốt bề ngang khối (mặt cắt không cho biết bề ngang).

**P6 — tri thức là dữ liệu (12/11/2026).**

- **Thông số đọc nét** (`scene/params.py`): 12 số trước đây là hằng số trong code nay là khoá `params` của hồ sơ trình
  bày. Mỗi số có mặc định và khoảng hợp lệ:
  - khe chồng nét của một tấm, vùng chân/nóc, dày tấm trên mặt đứng;
  - mảnh nhỏ nhất khi tách khối, cánh nhỏ nhất, ký hiệu nhỏ nhất, bán kính vòng chú thích;
  - dày đợt ở hình bỏ cánh, dày kính, khoảng cách ghi chú tới tấm, khoang treo, cột ngăn kéo.

  Code đọc qua `P(tên)`; khi dựng, `build_item_scene` / `build_once` đặt giá trị của hồ sơ (`drafting.read` → `d.params`).
  Hồ sơ không khai gì thì kết quả giống hệt P5 (cùng mã băm trên 102 hạng mục).
- **Đề xuất hồ sơ đi qua L4** (`drafting.impact`, `hypotheses.quality`):
  - mỗi đề xuất (code hoặc AI: vai trò layer, nghĩa ghi chú, nay thêm thông số) được dựng thử: đọc lại bản vẽ với
    hồ sơ + đề xuất, dựng tới 4 hạng mục, so điểm cách hiểu và số khối/cánh/nội thất;
  - màn "Hồ sơ trình bày" hiện "Thử dựng lại N hạng mục: điểm a → b/100". Điểm giảm thì cảnh báo. Chỉ ghi vào hồ sơ
    khi người dùng Đồng ý;
  - đề xuất thông số qua harness: tên có trong danh sách, số trong khoảng, khác giá trị đang dùng, có bằng chứng là
    nét/chữ có thật.
- **Code đề xuất thêm:** layer bị đoán là "kích thước"/"chữ" theo tên mà không chứa kích thước/chữ nào, chỉ có nét vẽ,
  thì đề xuất là thân đồ.
- Màn "Hồ sơ trình bày" có bảng **Thông số đọc nét** (sửa, lưu cả máy / dự án, bỏ về mặc định).

**Tiêu chí P6: thêm một kiểu vẽ mới chỉ bằng hồ sơ.** Kiểu mô phỏng `kieumoi` ("công ty khác"):
- thân tủ trên layer `KT-DOGO`, tên làm code đoán là layer kích thước;
- đợt mica dày 19 mm, ghi chú "MICA" (code mặc định coi kính dày ≤ 14 và chưa biết chữ "MICA").

Trên 18 hạng mục kiểu này (chỉ code):

| Hồ sơ | Điểm | Nội thất |
|---|---|---|
| mặc định | 0 % | 0 % |
| + đề xuất của code (layer → thân đồ; L4: 84 → 100/100) | 100 % | 71 % |
| + từ khoá "MICA" = kính và thông số dày kính 20 (dạng đề xuất AI phải đưa, đã qua harness) | 100 % | 100 % |

Không sửa dòng code nào cho kiểu này. Hồ sơ mẫu: `synth.PROFILE_KIEUMOI`. Test: `tests/test_drafting_params.py`.

Giới hạn:
- code chưa tự đề xuất thông số (chỉ AI và người dùng), vì muốn đề xuất phải dựng thử nhiều giá trị; để sau khi có
  đáp án thật;
- điểm L4 dùng cho đề xuất là điểm cách hiểu (nhất quán + bằng chứng), không phải điểm so với đáp án; hai số này có thể
  khác nhau ở ca lạ;
- hằng số kết cấu (khoang treo tối thiểu ở bộ chấm, nhịp đợt…) vẫn ở hồ sơ kết cấu xưởng / code, không thuộc hồ sơ
  trình bày.

**P7 — chỉ số "đúng không cần sửa" theo tuần / kiểu vẽ (12/11/2026).**

- **Cách đếm.** Màn 3D có nút **Xác nhận dựng đúng**. Lưu làm đáp án cũng tính là một lần xác nhận. Mỗi lần xác nhận
  ghi sự kiện `scene` vào lịch sử dự án (`.cadguard/history.jsonl`):
  - mã băm tệp, mã băm hạng mục, mã băm tên kiểu vẽ;
  - số chỗ người đã sửa theo loại (`scene_api.edit_counts`): số đo khối, chọn hình (mặt đứng chính / hình bỏ cánh /
    ghép mặt bằng), chia khối, chọn ở thẻ máy phân vân, nhãn khối, cao sàn–trần;
  - số thẻ phân vân / tự đổi, % số đo lấy từ kích thước ghi, thời gian dựng.

  "Đúng không cần sửa" là được xác nhận khi chưa có chỗ sửa nào.
- **Theo tuần** (thứ Hai → Chủ nhật, 8 tuần, `history.scene_quality`): mỗi hạng mục chỉ lấy lần xác nhận mới nhất
  trong tuần. Cột "theo đáp án" là lần chấm bộ đáp án cuối tuần (sự kiện `bench`: số hạng mục mà chỉ code đã đúng hoàn
  toàn, kể cả nội thất, và điểm khối).
- **Theo kiểu vẽ:** hồ sơ trình bày có thêm trường `name` (tên kiểu vẽ / công ty). Lịch sử chỉ ghi mã băm của tên; màn
  Tổng quan đổi mã băm về tên bằng hồ sơ và nhật ký hồ sơ trên máy (`drafting.known_names`). Tính trên 28 ngày gần nhất.
  Cùng khoảng đó có thêm "người dùng phải sửa gì nhiều nhất".
- **Chỉ số phụ** (§6): thẻ phân vân / hạng mục, % số đo có nguồn "Ghi", thời gian dựng (trung vị).
- Màn Tổng quan có mục **Dựng 3D đúng không cần sửa**: 4 ô số, bảng theo tuần, bảng theo kiểu vẽ, biểu đồ loại sửa.
  Mục này hiện cả khi tuần đó chưa quét luật nào.

Giới hạn:
- số chỉ có khi người dùng bấm xác nhận. Hạng mục không ai xác nhận thì không được đếm, nên tỉ lệ có thể lệch về
  phía hạng mục dễ;
- chỗ sửa còn nằm trong tệp bổ sung: lần dựng sau, dù code đã tự đúng, vẫn bị tính là đã sửa cho tới khi người dùng
  bỏ giá trị đó;
- chưa tách theo người vẽ, vì bản vẽ chưa có trường người vẽ đọc được chắc chắn.
