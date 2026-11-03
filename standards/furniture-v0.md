# Chuẩn trình bày bản vẽ nội thất — bản v0 (dự án cad-guard)

Trạng thái: **BẢN NHÁP ĐỀ XUẤT** (02/11/2026). Chưa phải chuẩn của công ty nào cho tới khi CEO + trưởng phòng kỹ thuật duyệt mục 5.
Nguồn: nghiên cứu tiêu chuẩn ngày 02/11/2026 (ISO/TCVN, AutoCAD CAD Standards, AWS của Woodwork Institute, tài liệu Mozaik/WoodWOP, cộng đồng nghề). Các số liệu từ nguồn thứ cấp được ghi rõ độ tin cậy ở mục 6.
Dùng cùng: `plans/cad-guard.md` (kế hoạch dự án), `guides/cad-guard-bootstrap.md` (tạo dự án + nối MCA).

## 0. Cách dùng tài liệu này

Công ty chưa có chuẩn bản vẽ viết ra giấy. Hướng đã chọn: lấy thực hành tốt nhất của ngành làm **bản v0**, đưa vào vận hành, rồi cải tiến liên tục theo dữ liệu thật (lỗi bị bắt, cảnh báo sai, phản hồi của các phòng ban). Vì vậy:

- Mục 1–4 là **nội dung chuẩn** (giá trị mặc định đề xuất).
- Mục 5 là danh sách **luật máy kiểm được** (mỗi luật có mã, mức độ, nguồn, rủi ro cảnh báo sai).
- Mục 6 là **những điều công ty phải tự quyết** — không thể lấy từ tiêu chuẩn.
- Mỗi luật nằm trong file luật của cad-guard (`standards/furniture-v0.yaml`), có phiên bản; đổi luật = tạo phiên bản mới, không sửa đè.

## 1. Cơ sở áp dụng

1. Nền: loạt ISO 128 / TCVN 8 (nét vẽ, hình chiếu, hình cắt), ISO 5457 / TCVN 7285 (khổ giấy, khung), ISO 5455 / TCVN 7286 (tỉ lệ), ISO 7200 / TCVN 3821 (khung tên), ISO 7573 / TCVN 3824 (bảng kê vật tư), ISO 3098 (chữ), ISO 2768 / TCVN 7294 (dung sai chung), ISO 129-1 (ghi kích thước).
2. Thực hành xưởng mộc: nội dung bản vẽ chế tạo theo tinh thần Architectural Woodwork Standards (AWS): phải thể hiện phương pháp cấu tạo, vật liệu chính xác, hoàn thiện, liên kết/mộng, ở tỉ lệ đủ rõ để chứng minh cấp chất lượng yêu cầu.
3. Cơ chế ép chuẩn trong AutoCAD: file mẫu `.dwt` + file chuẩn `.dws` (kiểm layer, kiểu chữ, kiểu đường, kiểu kích thước, multileader). Trình kiểm chuẩn có sẵn của AutoCAD **chỉ báo và sửa tên đối tượng, không kiểm hình học hay nội dung nên không đủ**; cad-guard bổ sung các luật còn lại.
4. Khi chuẩn công ty khác ISO/TCVN thì **chuẩn công ty thắng**, ghi rõ trong luật.

Ghi chú về tiêu chuẩn Việt Nam (đối chiếu từ trang văn bản, trạng thái hiệu lực chưa kiểm được): TCVN 8-1:2015 (= ISO 128-1:2003), TCVN 8-20/21/22/24/30/34/40/44/50, TCVN 7285:2003 (khổ giấy, nội dung khớp ISO 5457), TCVN 7286:2003 (tỉ lệ), TCVN 3821:2008 (= ISO 7200:2004), TCVN 3824:2008 (= ISO 7573:1983), TCVN 7287:2003 (ký hiệu vị trí chi tiết), TCVN 5705:1993 (ghi kích thước, **chưa có bản chuyển ISO 129-1:2018**), TCVN 7294 (dung sai chung, = ISO 2768). **Không tìm thấy TCVN riêng cho bản vẽ nội thất/mộc.**

## 2. Giá trị mặc định đề xuất (v0)

1. **Đơn vị và mô hình.** Milimét, 1 đơn vị vẽ = 1 mm (`INSUNITS = 4`). Vẽ đúng kích thước thật (1:1) trong Model; tỉ lệ chỉ áp ở khung nhìn (viewport) trong Layout. Chiếu góc thứ nhất trừ khi công ty quyết khác (chưa kiểm được tập quán Việt Nam); ký hiệu hình chiếu đặt trong khung tên.
2. **Khổ giấy.** A4 cho chi tiết và bảng cắt, **A3 mặc định**, A2/A1 cho dãy bếp và văn phòng. Lề trái 20 mm, các lề còn lại 10 mm; khung nét 0,7 mm; khung tên góc dưới bên phải, vùng thông tin chính rộng tối đa 170 mm. Tuỳ chọn: dấu giữa cạnh, lưới toạ độ (chữ 3,5 mm, ô 50 mm).
3. **Khung tên** (khối có thuộc tính, tên thẻ cố định): công ty (chủ sở hữu pháp lý), mã bản vẽ, tên bản vẽ, dự án/khách hàng, hạng mục/chi tiết, tờ n/N, tỉ lệ, ký hiệu hình chiếu, đơn vị, người vẽ/kiểm/duyệt, ngày, phiên bản (revision), trạng thái (WIP / FOR REVIEW / FOR PRODUCTION), tóm tắt vật liệu, ghi chú dung sai chung, ghi chú dán cạnh mặc định. Danh sách trường theo ISO 7200 **chưa đối chiếu được với văn bản trả phí** — kiểm lại trước khi công bố.
4. **Bảng phiên bản.** Cột: revision (A, B, C…), ngày, nội dung thay đổi, người sửa. Chỗ sửa có đám mây hoặc tam giác đánh dấu. Bản xuống xưởng phải có revision và đã có người kiểm.
5. **Tỉ lệ ưu tiên (TCVN 7286):** 1:1, 1:2, 1:5, 1:10, 1:20, 1:50, 1:100; phóng 2:1, 5:1, 10:1 cho chi tiết nhỏ. Gợi ý: mặt bằng 1:20 hoặc 1:50; mặt đứng 1:10 hoặc 1:20; mặt cắt 1:5 hoặc 1:2; chi tiết liên kết 1:1 hoặc 1:2. Tỉ lệ ngoài danh sách (1:25, 1:15, 1:30) chỉ dùng khi công ty chủ động chấp nhận. Không "co giãn cho vừa khung".
6. **Nét vẽ.** Cặp 0,25 mm (mảnh) / 0,5 mm (đậm), 0,7 mm chỉ cho khung và đường bao mặt cắt; tỉ lệ đậm:mảnh ≥ 2:1. Nét liền đậm = đường bao thấy; nét đứt mảnh = khuất; nét chấm gạch mảnh = tâm; nét chấm gạch đậm = vết mặt phẳng cắt; nét liền mảnh = kích thước, gạch mặt cắt, đường dẫn. **Chỉ một cơ chế gán độ dày: theo layer hoặc theo file kiểu in CTB/STB, không trộn.**
7. **Chữ.** Một font hỗ trợ tiếng Việt có dấu (cần thử thật), thẳng đứng, chỉ hai kiểu chữ `STD` và `TITLE`. Chiều cao trên giấy: 2,5 mm thường; 3,5 mm tiêu đề nhỏ; 5 mm tên hình; 7 mm tên bản vẽ trong khung tên; sàn tối thiểu 1,8 mm. Chiều cao trong Model = chiều cao trên giấy × mẫu số tỉ lệ (2,5 mm ở 1:20 = 50 mm). Chọn một trong hai: kiểu chữ annotative hoặc quy tắc theo viewport; không dùng lẫn.
8. **Kích thước.** Mỗi họ tỉ lệ một kiểu kích thước, đặt tên `FN-20`… Chữ 2,5 mm; mũi tên đặc kín ~2,5 mm; khe ~1 mm; đường gióng vượt ~2 mm; khoảng cách đường kích thước 7–10 mm; không số thập phân thừa; ghi vào mép chi tiết, không ghi vào nét khuất; không sửa chữ số kích thước bằng tay; kích thước kết hợp (associative). Các số này là **thông lệ**, chưa đọc được từ văn bản ISO 129-1.
9. **Dung sai chung.** Ghi một câu dung sai chung trên mọi tờ. ISO 2768-m là mặc định của cơ khí; **dung sai gỗ do công ty quyết** (mục 6).
10. **Layer** (rút gọn theo ISO 13567 / AIA): `FN-<NHÓM>-<PHẦN TỬ>[-<TRẠNG THÁI>]`, chữ hoa, gạch ngang. Trạng thái theo AIA: N mới, E hiện hữu, D phá dỡ, T tạm. Layer lõi: `FN-PART-OUTL` (đường bao tấm), `FN-PART-HIDD`, `FN-PART-CNTR`, `FN-SECT-CUT`, `FN-SECT-HATC`, `FN-HARD-SYMB` (phụ kiện), `FN-EDGE-BAND`, `FN-GRAIN-ARRW`, `FN-ANNO-DIMS`, `FN-ANNO-TEXT`, `FN-ANNO-LEAD`, `FN-ANNO-TAGS`, `FN-SHT-FRAM`, `FN-SHT-TTLB`, `FN-VPRT` (không in; **ngoại lệ**: chỉ hai phần, không theo mẫu `FN-<NHÓM>-<PHẦN TỬ>`, nên `layer_extra_patterns` của chuẩn phải liệt kê riêng), `FN-CNC-<thao tác>` (tên do phần mềm CNC đích quy định). Layer `0` và `DEFPOINTS` để dành.
11. **Hình chiếu/cắt.** Mỗi tủ: mặt đứng, mặt bằng, ít nhất một mặt cắt dọc qua thân tủ, một mặt cắt qua cánh/hộc kéo, chi tiết hậu nếu có. Mỗi hình có tên, ký hiệu và nhãn tỉ lệ. Mũi tên cắt trỏ tới hình cắt có nhãn. Dãy bếp/tủ áo: mặt bằng có kích thước ràng buộc với tường.
12. **Ghi chú chế tạo.**
    - Vật liệu và độ dày trên **mọi tấm**: `MFC 18`, `MDF 18`, `HDF 3`.
    - Dán cạnh: không có ký hiệu chuẩn chung; dùng một ghi chú chung ("mọi cạnh lộ dán cùng màu, PVC 1 mm trừ khi ghi khác") cộng mã `EB1`/`EB2` hoặc đường dẫn trong mặt cắt.
    - Vân gỗ: mũi tên hai đầu trên mặt tấm hoặc ghi "grain:".
    - Phụ kiện: nhãn loại + mã, tham chiếu tới bảng phụ kiện; bản lề ghi khoảng cách chén và độ trùm; ray hộc kéo ghi khe hở mỗi bên.
    - Khe hở, độ lộ (reveal) có kích thước.
    - Liên kết/mộng: ghi trong chi tiết.
13. **Chi tiết và bảng kê.** Mỗi chi tiết có số vị trí (bong bóng/nhãn) khớp bảng kê theo TCVN 3824: STT, mô tả, số lượng, tham chiếu, vật liệu, ghi chú; thêm dài × rộng × dày và mã dán cạnh từng cạnh.

## 3. Mã phiên bản và vòng cải tiến

- Chuẩn có số phiên bản (`furniture-v0`, `v0.1`…); mỗi bản vẽ ghi phiên bản chuẩn đã dùng trong khung tên (trường `STD_VER`).
- Mỗi luật có `id` ổn định. Tắt/hạ mức độ/sửa ngưỡng của một luật tạo bản chuẩn mới, có lý do và dữ liệu đi kèm.
- Dữ liệu cải tiến lấy từ: tỉ lệ cảnh báo sai theo luật, tỉ lệ thợ vẽ chấp nhận gợi ý, lỗi lọt xuống xưởng, phản hồi các phòng ban (thiết kế sản xuất, xưởng, lắp đặt). Luật có tỉ lệ cảnh báo sai cao bị hạ xuống "chỉ báo cáo" hoặc tắt; luật bắt đúng lỗi đắt thì nâng lên "lỗi".
- Không bao giờ chạy cảnh báo thời gian thực cho luật chưa có độ chính xác đã đo.

## 4. Quy ước đánh dấu để luật kiểm được

Phần lớn luật "heuristic" ở mục 5 chỉ tin cậy khi bản vẽ có **cấu trúc**. Hai việc quyết định chất lượng của cả hệ thống:

- Mỗi tấm có **thẻ vị trí** là khối có thuộc tính cố định (`PART_ID`, `MAT`, `THK`, `L`, `W`, `EB_TOP/BOTTOM/LEFT/RIGHT`, `GRAIN`).
- Khung tên và bảng phiên bản là khối có thuộc tính, không phải chữ rời.

Có cấu trúc này, nhiều luật chuyển từ "ước đoán" sang "tất định".

## 5. Danh mục luật máy kiểm được (58 luật)

Ký hiệu: Tất định = đọc dữ liệu là biết đúng/sai; Ước đoán = phụ thuộc cách đánh dấu. Mức: **E** lỗi, **W** cảnh báo, **I** thông tin. CSS = rủi ro cảnh báo sai (thấp/vừa/cao). Nguồn "CT" = quy ước công ty đề xuất ở mục 2.

### Khổ giấy và khung tên

| Mã | Mô tả | Đọc từ | Loại | Mức | CSS | Nguồn |
|---|---|---|---|---|---|---|
| SH-01 | Mỗi layout có khung khổ A-series nhận diện được | khổ giấy layout, polyline khung | Tất định | E | thấp | TCVN 7285 |
| SH-02 | Lề khung 20 mm trái, 10 mm các cạnh còn lại | đỉnh polyline khung | Tất định | W | vừa | TCVN 7285 |
| SH-03 | Nét khung 0,7 mm | độ dày nét | Tất định | W | thấp | TCVN 7285 |
| SH-04 | Có đúng một khối khung tên chuẩn trên mỗi layout đã dùng (bỏ qua layout trống mặc định của CAD) | INSERT, tên khối | Tất định | E | thấp | ISO 7200 |
| SH-05 | Mọi thuộc tính bắt buộc đều có giá trị | ATTRIB | Tất định | E | thấp | ISO 7200 |
| SH-06 | Mã bản vẽ đúng mẫu công ty | giá trị ATTRIB, regex | Tất định | E | thấp | CT |
| SH-07 | Số tờ n/N nhất quán trong file | ATTRIB nhiều layout | Tất định | W | thấp | CT |
| SH-08 | Revision trong khung tên = dòng mới nhất bảng phiên bản | ATTRIB, bảng | Tất định | E | vừa | CT |
| SH-09 | Không để "WIP" trên tờ đã đánh dấu xuống xưởng | ATTRIB | Tất định | E | thấp | CT |
| SH-10 | Tỉ lệ khung tên khớp tỉ lệ viewport chính | ATTRIB, VIEWPORT | Ước đoán | W | vừa | TCVN 7286 |

### Layer và thuộc tính

| Mã | Mô tả | Đọc từ | Loại | Mức | CSS | Nguồn |
|---|---|---|---|---|---|---|
| LY-01 | Tên layer đúng sơ đồ đặt tên | bảng LAYER | Tất định | E | thấp | CT |
| LY-02 | Màu/kiểu đường/độ dày layer khớp bảng chuẩn | thuộc tính layer | Tất định | W | thấp | DWS |
| LY-03 | Không có đối tượng nằm trên layer 0 (trừ định nghĩa khối) | layer đối tượng | Tất định | W | thấp | CT |
| LY-04 | Không có đối tượng trên layer chưa định nghĩa hoặc đang đóng băng | layer, cờ | Tất định | E | thấp | CT |
| LY-05 | Không ghi đè màu/kiểu đường/độ dày khi yêu cầu ByLayer | mã nhóm 62/6/370 | Tất định | W | vừa | CT |
| LY-06 | Kiểu đường nằm trong bộ chuẩn | bảng LTYPE | Tất định | W | thấp | DWS |
| LY-07 | Layer khuất dùng nét đứt, layer tâm dùng nét chấm gạch | LAYER, LTYPE | Tất định | W | thấp | ISO 128 |
| LY-08 | Layer `FN-VPRT` đặt không in | cờ in (mã 290) | Tất định | E | thấp | CT |
| LY-09 | Layer rỗng (không có đối tượng) | LAYER, đối tượng | Tất định | I | thấp | CT |

### Chữ và kích thước

| Mã | Mô tả | Đọc từ | Loại | Mức | CSS | Nguồn |
|---|---|---|---|---|---|---|
| TX-01 | Kiểu chữ thuộc tập cho phép | bảng STYLE | Tất định | W | thấp | DWS |
| TX-02 | Chiều cao chữ = giá trị chuẩn × tỉ lệ viewport | TEXT/MTEXT, tỉ lệ | Ước đoán | W | vừa | ISO 3098 |
| TX-03 | Không có chữ dưới 1,8 mm trên giấy | TEXT/MTEXT | Ước đoán | E | vừa | ISO 3098 |
| TX-04 | Font có trên máy hoặc có font thay thế | font của STYLE | Tất định | E | thấp | CT |
| TX-05 | Chữ không bị lật/ngược | góc xoay, cờ | Tất định | W | thấp | CT |
| TX-06 | Kiểu kích thước thuộc tập cho phép | bảng DIMSTYLE | Tất định | W | thấp | DWS |
| TX-07 | Biến kích thước khớp chuẩn (chữ, mũi tên, khe) | giá trị DIMSTYLE | Tất định | W | thấp | DWS |
| TX-08 | Kích thước không bị sửa chữ bằng tay | DIMENSION (mã 1) | Tất định | W | vừa | ISO 129-1 |
| TX-09 | Giá trị kích thước = số đo hình học | DIMENSION, hình học | Tất định | E | thấp | ISO 129-1 |
| TX-10 | Không có kích thước trùng/chồng | điểm định nghĩa DIMENSION | Ước đoán | W | vừa | ISO 129-1 |

### Hình chiếu và tỉ lệ

| Mã | Mô tả | Đọc từ | Loại | Mức | CSS | Nguồn |
|---|---|---|---|---|---|---|
| VW-01 | Tỉ lệ viewport nằm trong danh sách ưu tiên | VIEWPORT | Tất định | W | thấp | TCVN 7286 |
| VW-02 | Tỉ lệ viewport đã khoá và viewport nằm trong khung | cờ, biên | Tất định | W | thấp | CT |
| VW-03 | Model vẽ đúng 1:1 (không co giãn hình học) | kích thước đo vs danh nghĩa | Ước đoán | W | vừa | CT |
| VW-04 | Mỗi viewport có tên hình kèm tỉ lệ | chữ gần viewport | Ước đoán | W | cao | CT |
| VW-05 | Mỗi ký hiệu cắt có hình cắt tương ứng | cặp thuộc tính khối | Ước đoán | W | vừa | ISO 128-40 |
| VW-06 | Kích thước tổng ở mặt bằng và mặt đứng khớp nhau | giá trị kích thước | Ước đoán | E | cao | CT |

### Ghi chú đặc thù nội thất

| Mã | Mô tả | Đọc từ | Loại | Mức | CSS | Nguồn |
|---|---|---|---|---|---|---|
| FN-01 | Mọi tấm có vật liệu và độ dày | thẻ vị trí | Ước đoán | E | vừa | AWS |
| FN-02 | Độ dày ghi chú = độ dày trong mặt cắt | ghi chú vs hình cắt | Ước đoán | W | cao | CT |
| FN-03 | Có mũi tên vân trên tấm nhạy vân | `FN-GRAIN-ARRW` theo tấm | Ước đoán | W | vừa | CT |
| FN-04 | Có mã dán cạnh cho mọi cạnh (hoặc ghi chú chung) | chữ, ATTRIB | Ước đoán | W | cao | CT |
| FN-05 | Mã phụ kiện có trong bảng phụ kiện | nhãn vs bảng | Tất định | E | thấp | AWS |
| FN-06 | Có kích thước khe hở bản lề/ray trong mặt cắt liên quan | kích thước gần khối phụ kiện | Ước đoán | W | cao | CT |
| FN-07 | Có kích thước tổng R × C × S trên mặt đứng | chuỗi kích thước | Ước đoán | W | vừa | CT |

### Vệ sinh dữ liệu

| Mã | Mô tả | Đọc từ | Loại | Mức | CSS | Nguồn |
|---|---|---|---|---|---|---|
| DH-01 | Không có đối tượng chồng trùng | hình học | Tất định | W | thấp | CT |
| DH-02 | Không có đoạn dài 0 hoặc polyline diện tích 0 | LINE, LWPOLYLINE | Tất định | W | thấp | CT |
| DH-03 | Đường bao tấm khép kín và nối liền | cờ khép, khe hở đầu mút | Tất định | E | thấp | Mozaik |
| DH-04 | Hatch không có biên hở | HATCH | Tất định | W | vừa | CT |
| DH-05 | Không có khối/kiểu chữ/kiểu đường không dùng | bảng vs sử dụng | Tất định | I | thấp | CT |
| DH-06 | Không có xref mất đường dẫn hoặc đường dẫn tuyệt đối | đường dẫn XREF | Tất định | E | thấp | CT |
| DH-07 | Không có đối tượng proxy/không xác định | loại đối tượng | Tất định | W | thấp | CT |
| DH-08 | Định nghĩa khối nằm layer 0 và ByBlock | BLOCK | Tất định | W | vừa | CT |
| DH-09 | Đơn vị vẽ là mm | `INSUNITS` | Tất định | E | thấp | CT |
| DH-10 | Đối tượng nằm trên mặt phẳng z = 0 | toạ độ z | Tất định | W | thấp | Mozaik |

### Bàn giao sản xuất

| Mã | Mô tả | Đọc từ | Loại | Mức | CSS | Nguồn |
|---|---|---|---|---|---|---|
| PR-01 | Mỗi thẻ vị trí có trong bảng kê và ngược lại | ATTRIB vs bảng | Tất định | E | thấp | TCVN 3824 |
| PR-02 | Thẻ vị trí không trùng | ATTRIB | Tất định | E | thấp | CT |
| PR-03 | Số lượng bảng kê khớp số thẻ trên bản vẽ | đếm ATTRIB | Ước đoán | W | vừa | TCVN 3824 |
| PR-04 | Kích thước tấm trong bảng kê = hình học | bảng vs đường bao | Ước đoán | E | cao | CT |
| PR-05 | Layer CNC dùng đúng tên phần mềm đích, tham số hợp lệ | tên layer | Tất định | E | thấp | WoodWOP/Mozaik |
| PR-06 | Bản vẽ đánh dấu xuống xưởng có revision, người kiểm, người duyệt | ATTRIB | Tất định | E | thấp | CT |

**Thứ tự triển khai luật:** làm trước các luật Tất định + CSS thấp (khoảng 30 luật, mục tiêu phase P1). Luật Ước đoán chỉ bật sau khi mẫu bản vẽ có cấu trúc (mục 4) và đã đo độ chính xác trên bộ bản vẽ thật. Luật CSS cao không bao giờ vào cảnh báo thời gian thực.

## 6. Công ty phải tự quyết (không lấy được từ tiêu chuẩn)

1. Chiếu góc thứ nhất hay thứ ba; khổ giấy thực sự in.
2. Danh sách layer cuối cùng, màu, và độ dày nét lấy từ layer hay từ CTB/STB.
3. Cặp độ dày nét (0,25/0,5 hay 0,35/0,7) và font hỗ trợ tiếng Việt.
4. Số liệu kiểu kích thước ở mục 2.8 (thông lệ, chưa có trong tiêu chuẩn đọc được).
5. Dung sai chung cho gỗ (khác ISO 2768-m nếu cần), dung sai lắp ráp, lỗ, kích thước tấm.
6. Mã dán cạnh, ký hiệu vân, quy ước đặt tên tấm (`PART-NNN`).
7. Cách đánh mã bản vẽ và phiên bản; bản xuống xưởng có cần người kiểm ký không.
8. **Phần mềm đích của xưởng** (Imos, Cabinet Vision, Microvellum, Mozaik, Polyboard, WoodWOP…) — quyết định tên layer DXF cho CNC và cách xuất bảng cắt.
9. Danh mục phụ kiện và giá trị khe hở chuẩn.
10. Kích thước chuẩn tủ bếp/tủ áo (EN 1116 chỉ là tham khảo, không bắt buộc ở Việt Nam).
11. Dùng bộ `.dwt` + `.dws` của AutoCAD, hay bộ kiểm riêng của cad-guard, hay cả hai.

## 7. Điều cần thận trọng về độ tin cậy nguồn

- Không đọc được nội dung trả phí của ISO 128-2:2022, ISO 129-1:2018, ISO 3098, ISO 7200. Độ dày nét, chiều cao chữ, số liệu kích thước và danh sách trường khung tên đến từ nguồn thứ cấp hoặc là thông lệ → **kiểm lại trước khi công bố chuẩn**.
- ISO 128-2:2020 đã bị thay bằng ISO 128-2:2022; chưa đọc được bản 2022.
- Các cặp ISO–TCVN ghi "suy ra" dựa trên nội dung hoặc số hiệu, không phải trang nào cũng nói rõ tương đương. Trạng thái hiệu lực TCVN chưa kiểm được.
- Thực hành xưởng mộc dựa phần lớn vào AWS (ấn bản 2), blog nhà cung cấp và diễn đàn → mức bằng chứng "kinh nghiệm". Chưa kiểm được yêu cầu dữ liệu của Imos, Cabinet Vision, Polyboard; Microvellum ghi chép rất ít; WoodWOP/Mozaik đến từ trang cộng đồng/hỗ trợ, có thể cũ.
- Danh sách lỗi hay gặp lấy từ blog và diễn đàn; chưa có nghiên cứu hệ thống. **Dữ liệu lỗi thật của công ty (P0) quan trọng hơn mọi danh sách ở đây.**
- Giới hạn dữ liệu DXF: tỉ lệ annotative, tỉ lệ viewport và một số biến DIMSTYLE đọc được, nhưng khối động và đối tượng proxy có thể không đọc được tuỳ thư viện.
