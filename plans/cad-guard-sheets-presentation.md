# cad-guard — Kế hoạch đề xuất: chỉ mục tờ, trình bày theo template, dịch bản vẽ, đối chiếu PRD

Trạng thái: **ĐỀ XUẤT bản 2, chờ duyệt** (10/11/2026). Chưa viết code, chưa đổi lộ trình đã duyệt trong `PLAN.md`.
Bản 2 ghi nhận định hướng mới của chủ dự án (10/11/2026): CAD Guard là công cụ **nội bộ công ty**, chạy cục bộ; mở các rào chặn; cho sửa/bật/tắt luật không cần tài khoản; thêm chức năng chuyển chữ TCVN3/VNI sang Unicode; đánh giá các MCP AutoCAD có sẵn. Mục 5–10 là phần mới; mục 1–4 giữ từ bản 1, những chỗ nói "cần quyết định" đã được mục 5 trả lời.
Nguồn: (1) buổi chạy thử thực tế 10/11 trên một tệp DXF của phiên chạy thử (ngoài repo); (2) PRD "Agent-Assisted CAD Design Automation" bản nháp v0.1 ngày 09/11/2026; (3) ba yêu cầu mới của người dùng: sửa phân tích sai, dịch ngôn ngữ trình bày, trình bày theo template công ty.
Quy tắc dữ liệu: tài liệu này chỉ có **con số cấu trúc** của tệp thật (đếm, kích thước, tỉ lệ). Không tên tệp, tên khách, tên layer/khối, nội dung chữ.

## 1. Vì sao CAD Guard phân tích sai tệp thật

### 1.1 Số đo (chạy bằng ezdxf, chỉ in số)

| Chỉ số | Giá trị |
| --- | --- |
| Layout giấy | 1, **rỗng** (0 đối tượng, 0 viewport) |
| Đối tượng trong không gian mô hình | 10.547 |
| Lần chèn của **một** khối có tỉ lệ khổ A3 (425 × 295 đơn vị ở 1:1) và 3 thuộc tính | **40** |
| Hệ số phóng của 40 khung | 15 (25 khung), 20 (9), 66,87 (4), 19,77 (1), 10 (1) |
| Khung xoay / khung lồng nhau | 0 / 0 |
| Đối tượng nằm trong một khung | LINE 99,2%; LWPOLYLINE 100%; DIMENSION 100%; TEXT 99,5%; MTEXT 98,7%; INSERT 90,4% |
| Đối tượng nằm trong hơn một khung (khung kề nhau) | 38 |
| Chữ có ký tự ngoài ASCII / trong đó trông như mã cũ (TCVN3/VNI, chưa phải Unicode) | 309 / 285 |
| Báo cáo `cg.audit/1` hiện có | 15 luật chạy, 50 phát hiện, **45 là LY-01** (tên layer không theo mẫu `FN-*`) |

### 1.2 Nguyên nhân (xếp theo mức ảnh hưởng)

1. **Khái niệm "trang" của CAD Guard chỉ là layout giấy.** `dxf_reader` tạo `LayoutRec` cho mỗi layout khác Model; `SH-04`, `SH-05` chỉ xét `INSERT` có `space != "Model"`. Tệp này (và 5/5 mẫu ở `docs/real-sample-profile.md`) vẽ toàn bộ trong không gian mô hình: mỗi tờ là một khung tên chèn trong Model, phóng theo tỉ lệ bản vẽ. Kết quả: CAD Guard thấy 0–1 trang, người dùng thấy 40 tờ.
2. **Không có quan hệ "đối tượng thuộc tờ nào".** Phát hiện không gom được theo tờ, không lọc được "chỉ tờ này", không biết tỉ lệ của tờ (cỡ chữ in ra = cỡ chữ ÷ hệ số khung, hiện không tính được).
3. **Chuẩn mặc định không khớp quy ước công ty.** 45/50 phát hiện là nhiễu tên layer, đúng như đã dự báo ở `docs/real-sample-profile.md` mục 4.4. Người dùng nhìn báo cáo thấy "sai" vì phần lớn không phải lỗi thật.
4. **Chữ tiếng Việt mã cũ.** 285/309 chuỗi có dấu trông như TCVN3/VNI. Mọi thứ đọc chữ (trợ lý, khung tên, dịch) nhận chuỗi hỏng nếu không giải mã trước. Repo chưa có bộ giải mã.
5. **Khung tên là khối, tên do công ty đặt.** `title_block_names` trong chuẩn là danh sách cố định; không khớp thì toàn bộ nhóm SH bị bỏ qua.

Đây **không** phải lỗi đọc dữ liệu: ezdxf đọc đủ 10.547 đối tượng trong 3,6 giây. Lỗi nằm ở tầng mô hình (thiếu khái niệm tờ) và tầng chuẩn (chưa cấu hình theo công ty).

### 1.3 Có nên thêm thị giác để "nhìn" màn hình AutoCAD?

**Không dùng thị giác để phát hiện; có dùng ảnh dựng theo từng tờ để kiểm chứng và giải thích.**

- Dữ liệu cấu trúc đủ và chính xác hơn ảnh: 40 khung tìm được bằng hình học tất định, không xoay, không lồng, độ phủ ≥ 98,7% với mọi loại đối tượng trừ INSERT. Ảnh chụp màn hình không cho handle, layer, giá trị thuộc tính, và phụ thuộc mức zoom, layer đang tắt, nền, độ phân giải.
- Một tệp có 40 tờ; nhìn bằng ảnh nghĩa là 40 lượt gọi mô hình thị giác cho mỗi lần kiểm, kết quả không lặp lại được, và vi phạm nguyên tắc "phát hiện bằng code tất định".
- Chỗ ảnh có giá trị: (a) **dựng PNG/PDF từng tờ** (ezdxf drawing add-on, chạy không cần AutoCAD) để người dùng xem trước và so trước/sau; (b) trong Studio, sau khi người dùng đồng ý trong phiên, gửi ảnh **một tờ** cho LLM để giải thích hoặc rà bố cục; (c) kiểm chéo: nếu số tờ theo chỉ mục khác số tờ người dùng xác nhận thì hạ độ tin cậy và hỏi lại. PRD cũng chọn hướng này (FR-03: ưu tiên plot/PDF hơn ảnh chụp màn hình).

## 2. Đối chiếu PRD với cad-guard

PRD mô tả: trợ lý lập chỉ mục bản vẽ theo tờ, kiểm theo chuẩn YAML, đề xuất danh sách thay đổi, người duyệt, rồi chạy routine AutoLISP đã duyệt qua MCP trên bản sao trong AutoCAD; có vòng báo lỗi và phát hành chuẩn theo phiên bản.

| Yêu cầu PRD | cad-guard hiện có | Khoảng trống |
| --- | --- | --- |
| FR-01, 02, 04, 05: chỉ mục theo tờ (layout hoặc khung tên trong Model) | Chưa có | **Đợt B** |
| FR-03: dựng PNG mỗi tờ | `app/preview.py` dựng cả tệp | **Đợt C** |
| FR-06: độ tin cậy khi khung chồng/xoay/lồng | Chưa có | Đợt B (trường `confidence`) |
| FR-07, 08: đồ thị tri thức, truy vấn chéo tệp | Chưa có | Để sau (P1/P2 của PRD) |
| FR-10, 11: chuẩn YAML có phiên bản, báo cáo có mã luật + handle | Có (`standards/*.yaml`, `cg.audit/1`) | Thêm gom theo tờ, giá trị hiện tại/mong đợi |
| FR-12, 21, 22, 23: danh sách thay đổi bất biến, làm trên bản sao, hoàn tác, kiểm lại | Có (`cg.changeset/1`: propose/apply/undo/diff/validate) | Thêm ảnh trước/sau |
| FR-13: dùng lại CHECKSTANDARDS/DWS | Không | Không làm: DWS chỉ kiểm layer, kiểu kích thước, kiểu nét, kiểu chữ; cad-guard đã kiểm các mục này không cần AutoCAD |
| FR-20: áp dụng qua MCP gọi LISP đã duyệt trong CAD | **Không, và đang bị chặn có chủ đích**: M3 chỉ điều hướng, mọi sửa đi qua changeset ra tệp DXF mới | Cổng đã mở (mục 5); làm ở **Đợt F** |
| FR-30, 31: lệnh `/check`, `/fix-layers`, `/titleblock`, `/translate`, `/report` | MCP 6 công cụ chỉ đọc + `propose_changeset` | Đợt F: đóng gói thành skill/lệnh |
| FR-32, 33: nhật ký lệnh, `/report` | `history.jsonl`, `review` | Đợt F |
| FR-34–36: phát hành theo phiên bản, hàng đợi, ghế agent dùng chung | Không | Sau khi thí điểm |

Nhận định: PRD và cad-guard trùng khoảng hai phần ba (chuẩn YAML, luật tất định, xem trước → duyệt → bản sao → hoàn tác, MCP). Khác biệt thật sự chỉ có hai: **(i) chỉ mục theo tờ**, là thứ cad-guard đang thiếu và cũng là nguyên nhân phân tích sai; **(ii) nơi thực thi thay đổi** (PRD: trong AutoCAD bằng LISP; cad-guard: ghi DXF mới bằng ezdxf). Không cần viết lại; cần bổ sung (i) và làm (ii) như dưới đây.

Về (ii): ghi DXF mới giữ được nguyên tắc an toàn và không cần giấy phép CAD, nhưng hồ sơ hoàn công cần DWG và bản in. Khi đọc tệp thử, ezdxf cảnh báo bỏ qua đối tượng FIELD 40 lần ở bước sao chép; chưa xác định ảnh hưởng, nhưng đây là dấu hiệu vòng DXF → sửa → DXF có thể làm mất thông tin. Đề xuất: giữ lõi (chỉ mục, kiểm, sinh changeset) chạy theo tệp; thêm **bộ thực thi thứ hai** dịch cùng changeset đó thành lời gọi routine LISP nằm trong danh sách cho phép, chạy trên bản sao DWG. Một changeset, hai nơi thực thi, cùng bước kiểm lại.

## 3. Dịch ngôn ngữ trình bày: công cụ/lệnh hay chat?

**Làm thành công cụ có lệnh riêng; chat chỉ là một cách gọi công cụ đó.** Không để trợ lý tự sửa chữ theo lời chat.

Lý do:

- Dịch bản vẽ là thao tác ghi hàng trăm đối tượng (tệp thử: 555 chuỗi trong Model, cộng 36 chuỗi trong khung tên). Nó phải đi đúng đường changeset: xem trước, xác nhận, tệp mới, hoàn tác. Chat tự do không bảo đảm điều đó.
- Kết quả phải lặp lại được: cùng bảng thuật ngữ thì "MDF chống ẩm", "cánh tủ", "nẹp chỉ" luôn ra cùng một từ. Việc này cần bảng thuật ngữ khoá cứng, không phải trí nhớ của một phiên chat.
- Có các kiểm tra tất định mà chat không làm được: số và đơn vị giữ nguyên, mã vật liệu không bị dịch, chữ dịch không tràn khung, phông đích có đủ ký tự, không còn chuỗi chưa dịch.

Thiết kế:

- Lệnh `cadguard translate <tệp> --to en|zh|ja|ko [--sheets …] [--mode copy|layer]`; công cụ MCP `propose_translation`; nút trong `app`; lệnh AutoLISP `CGDICH` gọi cùng lõi. Người dùng chat "dịch tờ 12 sang tiếng Anh" thì trợ lý gọi công cụ này và trả bản xem trước.
- Chế độ `copy` (mặc định, đúng yêu cầu "tạo bản sao"): ghi tệp mới `<tên>.<ngôn ngữ>.dxf`, chữ được thay tại chỗ. Chế độ `layer` (như PRD): giữ chữ gốc, thêm chữ dịch trên layer riêng để bật/tắt.
- Chuỗi xử lý: giải mã chữ cũ (TCVN3/VNI → Unicode) → tách phần không dịch (số, đơn vị, mã, mã định dạng MTEXT) → tra bảng thuật ngữ → LLM dịch phần còn lại → kiểm tất định → changeset → dựng ảnh trước/sau từng tờ.
- LLM chỉ **đề xuất** bản dịch; đúng/sai về hình thức do code kiểm; người duyệt chịu trách nhiệm nội dung. Phù hợp nguyên tắc hiện có.
- Phạm vi dịch: TEXT, MTEXT, giá trị thuộc tính, chữ trong định nghĩa khối khung tên, chữ ghi đè của DIMENSION, MLEADER. Không dịch tên layer/khối.
- Dịch cần gửi **nội dung chữ** cho LLM. Theo định hướng nội bộ (mục 5) việc này được phép mặc định; dự án có NDA thì bật lại chế độ ẩn danh, khi đó chức năng dịch bị khoá cho dự án đó.

### 3.1 Chuyển chữ TCVN3/VNI sang Unicode (chức năng riêng, chỉ chạy khi người dùng bấm)

Mục đích: bản vẽ mở trên máy không cài phông TCVN3/VNI vẫn hiện đúng tiếng Việt. Không cái nào trong các công cụ đã khảo sát (mục 7) làm việc này.

- Gọi bằng: nút **Chuyển chữ sang Unicode** trong `app`, lệnh `cadguard unicode <tệp> [--sheets …]`, lệnh AutoCAD `CGUNICODE`, và là một tuỳ chọn trong hộp thoại dịch ("chỉ chuyển mã, không dịch"). **Không** tự chạy khi quét, khi mở tệp hay khi dịch.
- Nhận diện bảng mã theo từng chuỗi, theo thứ tự tin cậy: phông của kiểu chữ (`.Vn*`, `VH*` → TCVN3; `VNI-*` → VNI), mã phông nội tuyến `\f` trong MTEXT, rồi mới tới dấu hiệu ký tự. Phông chữ hoa của TCVN3 (đuôi `H`) ánh xạ sang chữ hoa Unicode. Chuỗi không chắc bảng mã thì **không đổi** và liệt kê để người dùng chọn tay.
- Đổi cả nội dung lẫn phông: chuỗi sang Unicode, kiểu chữ trỏ sang phông Unicode do công ty chọn trong template (mặc định một phông TTF có sẵn trên Windows); giữ chiều cao, hệ số rộng, căn lề.
- Phạm vi như mục dịch: TEXT, MTEXT, thuộc tính, chữ trong định nghĩa khối, chữ ghi đè kích thước, MLEADER, ô bảng.
- An toàn: chạy hai lần cho cùng kết quả (chuỗi đã là Unicode thì bỏ qua); đi đường xem trước → áp dụng → hoàn tác; báo chuỗi đổi bề rộng làm tràn khung.
- Bộ giải mã này cũng là nền cho hiển thị ảnh tờ (Đợt C) và cho dịch (Đợt E).

## 4. Trình bày theo template chuẩn của công ty

### 4.1 Research ngắn

- AutoCAD có ba cơ chế liên quan, không cái nào làm đủ việc: **DWT** (tệp mẫu khi tạo bản vẽ mới, không kiểm bản vẽ đã có); **DWS + CHECKSTANDARDS** (chỉ kiểm bốn loại đối tượng có tên: layer, kiểu kích thước, kiểu nét, kiểu chữ; không kiểm khung tên hay bố cục); **Sheet Set Manager** (quản lý tờ và trường khung tên, nhưng yêu cầu làm việc bằng layout giấy, trái với thói quen vẽ trong Model của nhóm người dùng mục tiêu).
- Chuẩn nền: TCVN 7285:2003 (ISO 5457) về khổ giấy và khung bản vẽ (lề trái 20 mm, các lề khác 10 mm); TCVN 3821:2008 (ISO 7200) về các ô dữ liệu trong khung tên. Dùng làm giá trị mặc định; template công ty ghi đè.
- Khoảng trống thị trường: kiểm và sắp lại **khung tên + bố cục tờ cho bản vẽ nhiều tờ trong Model** chưa có công cụ sẵn. Đây là chỗ cad-guard có giá trị riêng.

### 4.2 Template `cg.template/1`

Một thư mục gồm `template.yaml` và `titleblock.dxf` (định nghĩa khối khung tên chuẩn, kèm logo dạng hình vẽ hoặc ảnh).

| Nhóm | Nội dung |
| --- | --- |
| Khổ giấy | A3 ngang…; kích thước khung ở 1:1; lề |
| Vùng | đa giác **vùng vẽ** và **dải khung tên** (như ảnh mẫu: dải dọc bên phải) |
| Nội dung cố định | logo, tên công ty, địa chỉ, nhãn các ô: so khớp theo dấu vân tay hình học + chữ của định nghĩa khối |
| Trường thay đổi | tên dự án, hạng mục, tên bản vẽ, số bản vẽ, tỉ lệ, ngày, người vẽ/kiểm: tên thuộc tính, bắt buộc hay không, mẫu regex |
| Quy tắc tờ | danh sách tỉ lệ cho phép; cỡ chữ in ra (mm) cho tiêu đề/ghi chú/kích thước; quy tắc đánh số tờ; kiểu chữ và phông |
| Xuất bản | kiểu in (CTB/STB), khổ giấy in, quy tắc đặt tên PDF |

Tạo template bằng **học từ một tờ mẫu**: `cadguard template learn <tệp> --sheet <n> --out <thư mục>`. Người dùng chỉ một tờ đã trình bày đúng; công cụ trích định nghĩa khối khung, kích thước, thuộc tính, vùng, rồi mở biểu mẫu trong `app` để người dùng đánh dấu ô nào cố định, ô nào thay đổi. Không bắt người dùng viết YAML.

### 4.3 Kiểm tuân thủ (gói luật mới `sheet-layout-v0`, không sửa đè `furniture-v0`)

| Mã dự kiến | Kiểm | Loại |
| --- | --- | --- |
| TP-01 | Mỗi tờ có đúng một khung thuộc template đã chọn | tất định |
| TP-02 | Định nghĩa khối khung khớp template (không bị phá khối, sửa, sai phiên bản) | tất định |
| TP-03 | Nội dung cố định (logo, tên công ty, nhãn ô) đủ và đúng | tất định |
| TP-04 | Trường bắt buộc có giá trị và đúng mẫu | tất định |
| TP-05 | Hệ số khung thuộc danh sách tỉ lệ cho phép, phóng đều X = Y (tệp thử có 19,77 và 66,87) | tất định |
| TP-06 | Trường "tỉ lệ" trong khung tên khớp hệ số khung | tất định |
| TP-07 | Nội dung nằm trong vùng vẽ: không tràn khung, không đè dải khung tên | tất định |
| TP-08 | Không có đối tượng nằm ngoài mọi tờ (tệp thử: 66 INSERT) | tất định, mức thông tin |
| TP-09 | Cỡ chữ in ra = cỡ chữ ÷ hệ số khung thuộc tập cho phép | tất định |
| TP-10 | Số bản vẽ duy nhất, liên tục, thứ tự khớp vị trí tờ | tất định |
| TP-11 | Các tờ thẳng hàng, khoảng cách đều | tất định, mức thông tin |
| TP-12 | Phông/kiểu chữ trong khung tên đúng template; chữ là Unicode | tất định |

Mã chính thức và ngưỡng chốt khi viết chuẩn; mọi luật theo quy trình "Thêm một luật" của `AGENTS.md`, fixture tổng hợp nhiều tờ trong Model.

### 4.4 Áp dụng ("bấm apply")

Giữ nguyên hình vẽ, kích thước, chú thích; chỉ đổi khung và thông tin cố định. Thao tác changeset mới:

- `replace_title_block`: thay khung cũ bằng khung template tại cùng vị trí, giữ hệ số; chuyển giá trị trường cũ sang trường mới theo bảng ánh xạ (học một lần cho mỗi khung cũ, lưu trong hồ sơ công ty).
- `set_sheet_scale`: đưa hệ số khung về tỉ lệ cho phép gần nhất **chỉ khi** nội dung vẫn nằm trong vùng vẽ; nếu không thì báo, không tự làm.
- `fit_sheet`: dịch khung (không dịch nội dung) để nội dung vào giữa vùng vẽ; nội dung đè dải khung tên thì chỉ báo.
- `set_attribs`, `renumber_sheets`.

Không tự co, kéo, dời hình vẽ hay chú thích: việc đó là quyết định thiết kế. Mỗi lần áp dụng tạo tệp mới, có ảnh trước/sau từng tờ và chạy lại gói TP. Áp dụng thẳng lên bản đang mở trong AutoCAD làm ở Đợt F (cổng hướng D đã mở, mục 5); trước đó người dùng nhận tệp DXF mới và mở bằng `CGBAOCAO`/nút trong `app`.

## 5. Mở rào chặn: mở gì, giữ gì

Chủ dự án quyết định (10/11/2026): công cụ nội bộ, không cần bộ lọc chặt. Bảng dưới áp quyết định đó lên từng rào trong `AGENTS.md` và `PLAN.md`. Năm rào cuối được **đề xuất giữ** vì chúng bảo vệ công việc của chính công ty chứ không lọc gì người dùng; chủ dự án có thể bác.

| Rào hiện tại | Sau khi mở |
| --- | --- |
| Cổng hướng D: không sửa/lưu bản vẽ qua AutoCAD, M3 chỉ điều hướng | **Mở.** Được áp dụng thay đổi trong AutoCAD qua COM và routine LISP của CAD Guard (Đợt F) |
| Trợ lý mặc định ẩn danh Bậc 1 (không tên, chữ, thuộc tính, toạ độ) | **Mở.** Mặc định "nội bộ": trợ lý thấy nội dung thật. Ẩn danh còn là công tắc theo dự án cho hồ sơ có NDA |
| Studio phải xin đồng ý từng phiên trước khi gửi nội dung cho LLM | **Mở.** Một cài đặt chung, hỏi một lần khi cấu hình |
| LLM chỉ giải thích/đề xuất | **Mở một phần.** LLM được đọc nội dung, nhận xét, đề xuất sửa, dịch, tóm tắt yêu cầu khách. Kết quả luật vẫn do code tính; nhận xét của LLM hiện riêng, gắn nhãn "AI nhận xét" |
| Sửa luật/ngưỡng phải tạo phiên bản chuẩn mới; mỗi nhóm luật một tài khoản admin duyệt (quyết định 05/11) | **Mở.** Sửa trực tiếp trên giao diện, không tài khoản (mục 6). Thay quyết định 05/11 |
| Không bật `realtime_ok` khi chưa đo độ chính xác | **Mở.** Người dùng tự bật; luật chưa đo hiện nhãn "chưa đo" |
| Agent phát triển không được đọc bản vẽ thật | **Mở.** Được đọc bản vẽ ở thư mục ngoài repo để chẩn đoán và đo |
| Không dùng thư viện DWG copyleft/phi thương mại | **Mở có điều kiện.** Dùng nội bộ, không phân phối thì được gọi như chương trình ngoài; ghi trong `docs/licenses.md` là "phải gỡ nếu phát hành ra ngoài". Nhận định của tôi, không phải tư vấn pháp lý. Ưu tiên `accoreconsole` của chính AutoCAD đã cài để đọc/ghi DWG, khỏi cần các thư viện này |
| Chỉ sửa trong từ vựng changeset cố định | **Mở rộng dần** theo các đợt (khung tên, chữ, dịch, bố cục tờ) |
| *Giữ:* mọi thay đổi có xem trước, bản sao lưu và hoàn tác | Giữ, rút còn một lần bấm xác nhận. Trong AutoCAD: một nhóm undo + bản sao lưu tự động. Đây là lưới an toàn cho bản vẽ, không phải bộ lọc |
| *Giữ:* khoá API không ghi ra tệp | Giữ. Không ảnh hưởng người dùng |
| *Giữ:* bản vẽ thật không commit vào git; test chỉ dùng DXF tổng hợp | Giữ. Repo nhẹ, test lặp lại được, không lộ hồ sơ khách nếu repo được chia sẻ |
| *Giữ:* mã phiên tự động của app trên 127.0.0.1 | Giữ. Không phải đăng nhập; người dùng không thấy. Chặn trang web lạ gọi vào app |
| *Giữ:* telemetry chỉ số tổng hợp; không `git push` | Giữ nguyên trạng, không đầu tư thêm |

Việc đầu tiên khi được duyệt: sửa `AGENTS.md` và `PLAN.md` mục 1 theo bảng này, kèm dòng nhật ký quyết định.

## 6. Sửa, bật, tắt luật trên giao diện, không tài khoản

Hiện trạng: màn **Luật áp dụng** chỉ đọc. Hồ sơ công ty (`cg.company-profile/1`) đã hỗ trợ ghi đè tham số (`overrides`), tắt luật (`disabled`) và mẫu layer; thiếu giao diện ghi.

- Mỗi luật có công tắc **Bật/Tắt**, ô sửa **tham số** (số, danh sách, mẫu), chọn **mức độ** E/W/I, nút **Về mặc định**. Lưu là có hiệu lực ở lần quét sau.
- Ghi vào hồ sơ công ty của dự án (chưa có thì tạo tự động); tệp chuẩn gốc trong `standards/` không đổi, nên luôn về mặc định được.
- Không vai trò, không duyệt. Mỗi lần sửa thêm một dòng vào nhật ký cục bộ (thời điểm, luật, giá trị cũ → mới) để truy lại khi kết quả quét thay đổi.
- Phạm vi áp dụng chọn được: **dự án này** hoặc **mọi dự án trên máy**.
- Thẻ lỗi có nút **Tắt luật này** và **Sửa ngưỡng** để xử lý ngay luật không phù hợp.
- Luật "chưa cài code" ẩn khỏi danh sách mặc định.
- Bỏ khỏi bản mẫu `design/ui-mockup.html`: ba vai trò, bản nháp → duyệt → phiên bản, admin theo nhóm luật. Phần tài khoản làm sau nếu đưa lên online.

Cần mở rộng `cg.company-profile/1` thêm `severity` theo luật (tương thích ngược).

## 7. MCP AutoCAD có sẵn: kéo về hay chọn lọc?

### 7.1 Kết quả khảo sát (đọc ngày 10/11/2026)

| Công cụ | Giấy phép | Cách nối AutoCAD | Điểm đáng chú ý | Vấn đề |
| --- | --- | --- | --- | --- |
| AUTOM8LABS MCP Connector | **Đóng, thương mại** (bản Pro £10/ghế/tháng); repo công khai chỉ có tệp skill | Plug-in trong AutoCAD + cầu nối stdio | Khoảng 200 công cụ; bản miễn phí chỉ đọc; Pro có `replace_text`, `plot_to_pdf`, `title_block_update`, xử lý cả thư mục, checkpoint/rollback | Không có mã nguồn để tích hợp; không hỗ trợ AutoCAD LT; phụ thuộc nhà cung cấp |
| U-C4N/Autocad-MCP | MIT | **Hai engine sau một hợp đồng**: COM tới AutoCAD đang mở, và ezdxf chạy không cần AutoCAD; DWG qua ODA rồi `accoreconsole` | 257 công cụ; `text_find_replace` có xem trước và chỉ áp khi bản vẽ chưa đổi; transaction/checkpoint; `titleblock_apply` theo ISO 7200; `batch_plot`, xuất PDF; chụp khung nhìn | Mới 6 tháng; chỉ thử thật trên AutoCAD 2026; lệnh chạy LISP/lệnh tuỳ ý **mở mặc định**; lỗi bảo mật #23 (LISP ghi được tệp và registry) chưa sửa; COM không chạy trong CI |
| bimwright/dwg-mcp | Apache-2.0 | Plug-in .NET trong AutoCAD, named pipe/TCP | Quy trình dịch: gom cụm chữ theo vị trí → agent dịch → ghi lại trong một transaction, đổi sang MTEXT; tạo kiểu chữ Unicode thay SHX | Ghi đè tại chỗ; không bảng thuật ngữ; không giải mã TCVN3/VNI; có lệnh chạy C# tuỳ ý mở mặc định; nhiều bản AutoCAD mới ở mức khung |
| ibrahmgarip/cad-translator, etianwang/CAD_translator | MIT | ezdxf, DWG qua ODA | Bảo vệ ký hiệu kỹ thuật bằng regex; bảng thuật ngữ + bộ nhớ dịch; lấy cả chữ ghi đè kích thước và ô bảng; ghi tệp mới có tiền tố ngôn ngữ; bọc phông `{\f…}` cho MTEXT | Dùng DeepL/Google/Azure, không LLM; 0–1 sao; không xử lý phông Việt |
| Kleen "CAD Translator" (Autodesk App Store) | Đóng, 10 USD/tháng | Plug-in trong AutoCAD | DeepL + cơ sở thuật ngữ riêng, nhập/xuất Excel | Không tích hợp được |

"CAD Translator" trong yêu cầu không xác định được chắc là dự án nào; bảng liệt kê các ứng viên tìm thấy. Không công cụ nào xử lý TCVN3/VNI.

### 7.2 Khuyến nghị: **chọn lọc phương pháp, không kéo nguyên MCP về**

Lý do không nhúng nguyên:

- 200–257 công cụ làm ngữ cảnh của trợ lý phình to và chậm; cad-guard đang giữ 6 công cụ, mỗi kết quả dưới 10.000 token. Phần lớn công cụ đó là vẽ hình mới (cơ khí, P&ID, kiến trúc), ngoài mục tiêu kiểm và trình bày.
- Cả hai MCP mã mở đều cho chạy LISP/C# tuỳ ý mặc định; chữ trong bản vẽ của khách có thể chứa câu lệnh gài cho trợ lý. Mở rào nội bộ không có nghĩa nên nhận rủi ro này.
- Không cái nào có chỉ mục tờ trong Model, template khung tên của công ty hay tiếng Việt mã cũ, tức đúng ba thứ đang thiếu.
- Hai sổ công cụ song song trái với nguyên tắc "một sổ `agent/registry.py`" vừa làm xong ở Đợt 1.

Lấy những gì (đưa vào các đợt ở mục 9):

| Phương pháp | Nguồn | Vào đợt |
| --- | --- | --- |
| Một hợp đồng thay đổi, hai engine thực thi (COM trực tiếp + ezdxf theo tệp) | U-C4N | F |
| `accoreconsole` của AutoCAD đã cài để đọc DWG và xuất DXF/PDF không cần mở giao diện | U-C4N | C (đọc DWG), F (in PDF) |
| Áp dụng chỉ khi bản vẽ chưa đổi kể từ lúc xem trước; checkpoint/rollback | U-C4N, AUTOM8LABS | F |
| In hàng loạt ra PDF theo tờ, cập nhật khung tên hàng loạt, sổ đăng ký bản vẽ | AUTOM8LABS, U-C4N | D, F |
| Gom cụm chữ rời theo vị trí trước khi dịch; kiểu chữ Unicode thay SHX | bimwright | C, E |
| Bảo vệ ký hiệu kỹ thuật bằng regex; bảng thuật ngữ + bộ nhớ dịch; tệp mới có tiền tố ngôn ngữ; phạm vi gồm chữ ghi đè kích thước và ô bảng | hai cad-translator | E |

Mã MIT/Apache được phép tham khảo hoặc chép có ghi nguồn trong `docs/licenses.md`. Người dùng nào muốn thử vẽ bằng trợ lý vẫn có thể cài U-C4N **song song** trong Claude Desktop; CAD Guard không phụ thuộc nó.

## 8. Tối ưu và loại bỏ phần đã làm

| Phần | Vấn đề | Đề xuất |
| --- | --- | --- |
| Khái niệm trang = layout giấy; `SH-04/05` | Sai với cách vẽ thật | Thay bằng chỉ mục tờ (Đợt B) |
| `LY-01` mẫu `FN-*` cố định; `title_block_names` cố định | 45/50 phát hiện là nhiễu; nhóm SH bị bỏ qua | Học quy ước từ bản vẽ của công ty; khung tên lấy từ template |
| Mô hình vai trò/tài khoản/duyệt luật trong bản mẫu (9b) | Không còn phù hợp | Bỏ; thay bằng mục 6 |
| Lớp ẩn danh Bậc 1 và các test danh sách trắng | Là mặc định, làm trợ lý không hiểu được bản vẽ | Chuyển thành chế độ tuỳ chọn; giữ test cho chế độ đó; ngừng mở rộng |
| Đồng ý từng phiên của Studio; Studio là server riêng | Thừa bước; ba server | Bỏ bước đồng ý; gộp Studio vào App (Đợt 4 đã duyệt) |
| Ba đường truy cập từ xa (Tailscale Serve, cổng mật khẩu ra Internet, cổng hồ sơ duyệt) | Nhiều mã bảo mật phải nuôi cho công cụ chạy cục bộ; cổng mật khẩu đưa quyền quản trị ra Internet | Đóng băng; giữ cổng hồ sơ duyệt nếu đang dùng với khách; cổng mật khẩu chờ phần tài khoản |
| Hai đường xem trước (`geometry.py` SVG định vị, `preview.py` ezdxf) | Trùng việc, không theo tờ | Gộp thành bộ dựng ảnh theo tờ (Đợt C) |
| `CGXUAT` + `watch`: người dùng phải xuất DXF bằng tay | Thêm bước, dễ quên | Đọc thẳng DWG đang mở qua `accoreconsole`/COM; giữ `CGXUAT` làm dự phòng cho máy không có bản đầy đủ |
| Cầu COM chỉ điều hướng (`autocad/bridge.py`) | Bị giới hạn bởi cổng cũ | Thành nền của bộ thực thi trong AutoCAD (Đợt F) |
| `furniture-v0`: 42/58 luật chưa cài, viết cho khâu sản xuất | Chưa có mẫu của khâu đó | Ngừng cài thêm cho tới khi có mẫu; ưu tiên gói trình bày TP và vệ sinh VS |
| Dựng 3D (`scene`), nhiều engine trợ lý, telemetry cho MCA | Không phục vụ ba vấn đề đang nêu | Giữ nguyên trạng, không đầu tư thêm |
| `dxf_stream` (bộ đọc thứ hai phải khớp bộ đọc chính) | Tốn công nuôi đôi | Giữ vì mẫu thật có tệp 262–445 MB; trường mới của chỉ mục tờ tính ở tầng sau bộ đọc để không phải cài hai lần |

## 9. Lộ trình đề xuất bản 2

Thay cho bảng Đợt 5–9 của bản 1. Thứ tự theo phụ thuộc và theo việc người dùng thấy kết quả sớm.

| Đợt | Nội dung | Tiêu chí nghiệm thu |
| --- | --- | --- |
| **A. Mở rào và sửa luật** | Cập nhật `AGENTS.md`, `PLAN.md` theo mục 5. Chế độ nội bộ là mặc định, ẩn danh thành công tắc theo dự án. Giao diện sửa/bật/tắt luật (mục 6). Ẩn luật chưa cài. Bỏ bước đồng ý phiên. | Sửa ngưỡng hoặc tắt luật trên giao diện → lần quét sau đổi theo, CLI/MCP ra cùng số; về mặc định được; nhật ký có dòng thay đổi; không màn nào đòi tài khoản. Chế độ ẩn danh khi bật vẫn qua bộ test cũ. |
| **B. Chỉ mục tờ** `cg.sheets/1` | Tờ = layout giấy có nội dung hoặc khung tên trong Model; đối tượng thuộc tờ; hệ số; độ tin cậy; phát hiện gom theo tờ. Học quy ước layer và khối khung tên của công ty. | Fixture N khung → N tờ (khung kề nhau, khác tỉ lệ). Tệp phiên thử: số tờ khớp số người dùng đếm (dự kiến 40). LY-01 trên tệp thử còn dưới 5. `ok_sheet.dxf` sạch. |
| **C. Xem theo tờ, Unicode, đọc DWG** | Ảnh PNG/PDF từng tờ, danh sách tờ trong `app`. Bộ giải mã TCVN3/VNI và chức năng **Chuyển chữ sang Unicode** (mục 3.1). Đọc DWG qua `accoreconsole` khi máy có AutoCAD. Gộp Studio vào App. | 40 tờ dựng dưới 60 giây, chữ Việt mã cũ hiện đúng. Chuyển Unicode: bảng ánh xạ đủ 134 ký tự có dấu × 2 bảng mã qua test khứ hồi; chạy hai lần không đổi thêm; chuỗi không chắc không bị đổi; chỉ chạy khi bấm. Mở DWG không cần xuất tay. |
| **D. Template trình bày** | `cg.template/1`, học từ tờ mẫu, gói TP-01…TP-12, thao tác thay khung/điền trường/đánh số, nút Áp dụng. | Như bản 1: sau áp dụng 0 lỗi TP sửa được; 0 đối tượng hình vẽ/kích thước/chú thích đổi; hoàn tác trả đúng tệp gốc. |
| **E. Dịch** | `cadguard translate`, bảng thuật ngữ + bộ nhớ dịch, bảo vệ ký hiệu kỹ thuật, gom cụm chữ, hai chế độ `copy`/`layer`, kiểm tràn khung và phông. | Fixture: 100% chuỗi dịch được có bản dịch; 0 số/đơn vị/mã bị đổi; 0 thuật ngữ lệch bảng; chuỗi tràn khung được báo; hoàn tác được. |
| **F. Thực thi trong AutoCAD** | Bộ thực thi thứ hai: cùng changeset, áp trên bản đang mở qua COM + routine LISP của CAD Guard, một nhóm undo, sao lưu tự động, chỉ áp khi bản vẽ chưa đổi từ lúc xem trước. Lệnh `CGKIEM`, `CGTRINHBAY`, `CGDICH`, `CGUNICODE`. In PDF hàng loạt theo tờ. Lệnh `/check`, `/titleblock`, `/translate`, `/report` cho trợ lý. | Cùng changeset cho kết quả tương đương ở hai bộ thực thi trên fixture; U trong AutoCAD trả lại nguyên trạng; không đường nào chạy LISP do trợ lý tự viết; DWG mở lại sạch; bộ PDF đủ số tờ, đúng tên. |

Đợt A nhỏ và gỡ vướng ngay cho người dùng nên làm trước. Sau B và C, báo cáo đúng số tờ và bản vẽ đọc được trên mọi máy. D là việc người dùng đang làm tay trước khi in hồ sơ hoàn công. Đồ thị tri thức, hàng đợi và ghế agent dùng chung của PRD chưa xếp lịch.

## 10. Còn cần chủ dự án trả lời

1. Năm rào "đề xuất giữ" ở mục 5: đồng ý giữ, hay mở cả?
2. Ngôn ngữ đích ưu tiên và người giữ bảng thuật ngữ.
3. Phông Unicode chuẩn của công ty (dùng cho chuyển mã và template).
4. Tệp khung tên chuẩn: công ty cung cấp, hay học từ một tờ mẫu.
5. Máy người dùng chạy AutoCAD bản đầy đủ hay LT (LT không có COM và `accoreconsole`; Đợt F khi đó phải đi đường LISP + tệp).
6. Số tờ thật của tệp phiên thử để đối chiếu với con số 40.

## 11. Giới hạn của đánh giá này

- Một tệp, một công ty. Khung tên ở đây là khối có thuộc tính, không xoay, không lồng: ca dễ. Tệp có khung vẽ bằng nét rời, khung bị phá khối hoặc tờ nằm trong xref sẽ khó hơn; cần thêm mẫu.
- Chưa xác minh con số 40 với người dùng. Chưa viết và chưa đo bộ giải mã chữ cũ; dấu hiệu "mã cũ" ở mục 1.1 là suy đoán theo dải ký tự.
- PRD được đọc qua ảnh chụp trang; vài đoạn của các mục đồ thị dữ liệu, an toàn và cấp phép có thể chưa đọc hết.
- Ba MCP/công cụ ở mục 7 được đánh giá qua tài liệu, mã nguồn và issue, **chưa cài chạy thử**. Số công cụ, số sao và tình trạng issue là tại ngày đọc.
- Nhận định về giấy phép copyleft khi dùng nội bộ là ý kiến kỹ thuật, không phải tư vấn pháp lý.
