# Chuẩn vệ sinh bản vẽ — `design-hygiene-v0` (dự án cad-guard)

Trạng thái: **BẢN NHÁP ĐỀ XUẤT** (04/11/2026). Chưa phải chuẩn của công ty nào cho tới khi CEO và trưởng phòng Thiết kế/Kỹ thuật duyệt ngưỡng ở mục 4.
Tệp máy đọc: `standards/design-hygiene-v0.yaml` (luật, tham số, phiên bản). Mã luật `VS-*` ("vệ sinh").

## 1. Mục đích

Công ty có ba phòng nối tiếp: **Thiết kế → Kỹ thuật → Lập trình sản xuất**. Đầu ra của khâu trước là đầu vào của khâu sau, nên một bản triển khai bẩn (layer rác, phông hỏng tiếng Việt, kích thước sửa tay) sinh lỗi ở khâu sau.
Chuẩn `furniture-v0` viết cho bản vẽ chi tiết đưa xuống sản xuất và hầu như không áp dụng được cho bản vẽ triển khai (xem `docs/real-sample-profile.md` mục 1, 5). Chuẩn này bắt đầu từ những thứ **đo được trên mẫu thật, tất định và ít báo sai**: vệ sinh và nhất quán của bản vẽ.

## 2. Phạm vi

- Áp dụng: bản vẽ DXF của khâu Thiết kế và Kỹ thuật (triển khai không gian, bản vẽ thi công), đọc bằng ezdxf hoặc bộ đọc theo dòng (kết quả hai đường đọc giống nhau, có test).
- Không áp dụng: kiểm nội dung kỹ thuật (kích thước đúng/sai, vật liệu, khớp bảng kê) và bản vẽ cho máy CNC — đó là việc của các chuẩn sau khi có mẫu của khâu 2 và 3.
- Mọi luật là **tất định** (`kind: deterministic`), chỉ đọc Drawing Model `cg.drawing/1`. Thiếu dữ liệu thì luật **bỏ qua có lý do**, không đoán.
- Chưa luật nào đo độ chính xác trên bản vẽ có nhãn: `realtime_ok: false` cho tất cả (theo `AGENTS.md`).
- Chuẩn chỉ **báo**; không tự sửa bản vẽ. Tính năng "dọn bản vẽ" (nếu làm) phải có xem trước, xác nhận, hoàn tác và ghi ra tệp mới.

## 3. Danh mục luật

Nguồn số liệu: 5 bản vẽ thật M1–M5 đã ẩn danh (`docs/real-sample-profile.md` mục 3), n = 5, một công ty, khâu thiết kế/kỹ thuật. **Ngưỡng mặc định là đề xuất**, chọn sao cho chỉ ra được phần "phình"/rác rõ ràng; công ty chỉnh bằng hồ sơ công ty (mục 4).

| Mã | Nội dung | Mức | Tham số (mặc định) | Đọc từ mô hình | Căn cứ ngưỡng |
| --- | --- | --- | --- | --- | --- |
| VS-01 | Không còn layer dư từ xref đã gộp/đính kèm (tên có `\|` hoặc `$0$`, hoặc cờ xref) | W | `max_xref_layers` = 0 | `layers[].xref_dependent` | 6–41 layer dư mỗi tệp ở cả 5 mẫu; sau bind xref thông lệ là đổi tên/PURGE, nên mặc định 0 |
| VS-02 | Số kiểu chữ và số kiểu kích thước không vượt ngưỡng | W | `max_text_styles` = 15, `max_dim_styles` = 10 | `styles` (trừ kiểu hình SHX), `dim_styles` | Mẫu có 23–52 kiểu chữ, 8–26 kiểu kích thước; `furniture-v0` mục 2.7–2.8 chỉ cần vài kiểu |
| VS-03 | Tỉ lệ đối tượng trực tiếp trên layer `0` (mô hình + giấy, **không tính nội dung khối**) ≤ ngưỡng | W | `max_layer0_ratio` = 0,05; `min_entities` = 10 | `stats.modelspace/paperspace.by_layer["0"]`, `.entities` | Mẫu 2,9–22,8%; layer 0 để dành cho nội dung khối. Dưới `min_entities` đối tượng thì bỏ qua |
| VS-04 | Tỉ lệ đối tượng ghi đè màu (mã 62 ≠ 256 hoặc true color) / độ dày nét (mã 370 ∉ {−1, −2, −3}) ≤ ngưỡng | W | `max_color_override_ratio` = 0,10; `max_lineweight_override_ratio` = 0,05; `min_entities` = 10 | `entities[]` (mô hình + giấy) trừ layer khớp `exempt_layer_patterns` | Mẫu: màu 3–77%, độ dày nét 0–40%; `furniture-v0` mục 2.6 (một cơ chế gán độ dày) |
| VS-05 | Số WIPEOUT / IMAGE / OLE (kể cả trong khối) ≤ ngưỡng | W | `max_wipeouts` = 100, `max_images` = 10, `max_ole` = 0 | `stats.*.wipeout/image/ole` | WIPEOUT tới 4.039 trong khối; IMAGE + OLE 2–38 mỗi tệp |
| VS-06 | Không có kích thước bị ghi đè chữ (mã 1 khác rỗng và khác `<>`), kể cả trong khối | **E** | `max_dim_text_overrides` = 0 | `stats.*.dim_text_override` | Mẫu 0,5–6,0% kích thước bị ghi đè; số hiển thị có thể khác số đo thật (mục 4.7). Cùng ý với `TX-08` của `furniture-v0` nhưng tính cả khối |
| VS-07 | Chữ có ký tự ngoài ASCII (tiếng Việt có dấu) không dùng kiểu chữ có phông không Unicode | W | `max_texts` = 0; `legacy_font_patterns` = [`^\.?vn`, `^tcvn`]; `unicode_shx_fonts` = [] | `stats.text_non_ascii_by_style`, `styles[].font` | 54–74% chữ ngoài ASCII; phông VN cũ (vn*, VNI/TCVN) ở cả 5 tệp (mục 4.5) |

Chi tiết cách tính:

- **VS-01**: một layer là "dư xref" nếu cờ 16 (phụ thuộc xref) hoặc tên chứa `|` hay `$0$`. Layer khớp `allowed_layer_patterns` (toàn cục) không bị tính.
- **VS-02**: đếm định nghĩa trong bảng STYLE/DIMSTYLE, không phụ thuộc có được dùng hay không (định nghĩa thừa cũng làm bản vẽ nặng và gây chọn nhầm). Hai vượt ngưỡng báo thành hai phát hiện.
- **VS-03**: định nghĩa khối đặt trên layer 0 là đúng thông lệ, nên chỉ đếm đối tượng trực tiếp trong không gian mô hình và giấy (gồm INSERT đặt trên layer 0).
- **VS-04**: tính trên danh sách đối tượng chi tiết. Với tệp rất lớn đọc theo dòng, danh sách có thể bị cắt ở trần bộ nhớ: luật vẫn tính trên phần đã đọc và ghi rõ trong thông điệp. Màu 0 (ByBlock) trên đối tượng ngoài khối cũng tính là ghi đè.
- **VS-05**: ba bộ đếm riêng, mỗi bộ vượt ngưỡng là một phát hiện. IMAGE là ảnh tham chiếu tệp ngoài (dễ mất khi chuyển tệp), OLE là dữ liệu nhúng (nặng, không mở được ngoài Windows).
- **VS-06**: tính mọi DIMENSION (mô hình, giấy, trong khối). Luật **không** kiểm chữ ghi đè đúng hay sai so với hình học (việc của `TX-09`, chưa làm).
- **VS-07**: một kiểu chữ là "không Unicode" nếu phông là SHX (đuôi `.shx`, hoặc tên không đuôi — bảng STYLE hiểu là SHX, ví dụ `txt`) và không nằm trong `unicode_shx_fonts`; hoặc tên tệp phông khớp `legacy_font_patterns` (phông TCVN3 `.Vn*`, VNI `VNI-*`). Kiểu chữ không tìm thấy hoặc không có tên phông thì không phán. Chỉ xét TEXT và MTEXT (chưa xét ATTRIB/ATTDEF).

## 4. Cấu hình theo công ty (hồ sơ công ty)

Quy ước mỗi công ty khác nhau (mẫu thật: 0% layer theo `FN-*`), nên ngưỡng và mẫu tên layer là **tham số**, không phải hằng. Công ty không sửa tệp chuẩn; thay vào đó viết **hồ sơ công ty** (`cg.company-profile/1`), ví dụ `standards/company-profile.example.yaml`:

```yaml
schema: cg.company-profile/1
name: cong-ty-mau
version: 0.1.0
standard: design-hygiene-v0
standard_version: 0.1.0        # tuỳ chọn; khác phiên bản chuẩn đang nạp thì báo lỗi
layer_patterns:
  allowed: ['^KHUNG-TEN\|']    # thay globals.allowed_layer_patterns (VS-01)
  exempt: ['^TRINH-BAY-']      # thay globals.exempt_layer_patterns (VS-04)
overrides:
  VS-02: {max_text_styles: 20, max_dim_styles: 12}
disabled: []                   # mã luật tắt hẳn
```

Chạy: `python -m cadguard audit <tệp/thư mục> --profile <hồ sơ>.yaml` (không có `--standard` thì dùng chuẩn ghi trong hồ sơ). Báo cáo JSON/HTML ghi tên và phiên bản hồ sơ đã áp.

Kiểm hồ sơ (sai thì báo lỗi tiếng Việt và thoát mã 2, không chạy quét):

- trường lạ hoặc thiếu trường bắt buộc (`schema`, `name`, `version`, `standard`);
- hồ sơ viết cho chuẩn khác, hoặc khác `standard_version`;
- mã luật không có trong chuẩn (`overrides`, `disabled`);
- tham số luật không khai báo trong chuẩn (hồ sơ **không thêm được tham số hay luật mới**);
- sai kiểu so với giá trị mặc định (số nguyên/số/danh sách chuỗi/đúng-sai), số âm, tỉ lệ (`*_ratio`) ngoài 0–1;
- mẫu (`*_patterns`, `layer_patterns`) không phải biểu thức chính quy hợp lệ.

Mẫu tên layer là biểu thức chính quy Python, so khớp kiểu "tìm trong tên", không phân biệt hoa/thường; dùng `^…$` để khớp trọn tên.

Hồ sơ công ty chỉ chỉnh tham số trong khuôn của phiên bản chuẩn. Đổi luật, thêm luật hay đổi giá trị mặc định = **phiên bản chuẩn mới** (`design-hygiene-v0.1`…), không sửa đè. Lớp gắn kết phòng/vị trí/task và luật riêng của dự án (đề xuất 9b trong `plans/cad-guard-agent.md`) chưa làm và không nằm trong tệp hồ sơ này.

## 5. Công ty phải tự quyết

1. Ngưỡng VS-02…VS-05 (mặc định là đề xuất từ 5 mẫu của một công ty).
2. Danh sách phông SHX đã kiểm là hiển thị đúng tiếng Việt Unicode (`unicode_shx_fonts`), và phông tiếng Việt chuẩn của công ty.
3. Layer nào được miễn kiểm ghi đè màu/độ dày nét (ví dụ layer trình bày), layer dạng xref nào được giữ.
4. VS-06 có giữ mức **lỗi (E)** hay hạ xuống cảnh báo cho khâu Thiết kế (mức thuộc phiên bản chuẩn, không thuộc hồ sơ).

## 6. Giới hạn đã biết

- Số liệu nguồn từ DXF do LibreDWG chuyển đổi, độ trung thực chưa kiểm (`docs/real-sample-profile.md` mục 2, 4.8). Chưa đo độ chính xác (cần bản vẽ có nhãn tốt/xấu).
- VS-07 dựa vào tên tệp phông: không đọc được nội dung tệp SHX/TTF để biết có glyph tiếng Việt Unicode hay không. Phông TTF tiếng Việt cũ không có tiền tố `vn`/`tcvn` sẽ bị bỏ sót; khi đó thêm mẫu vào `legacy_font_patterns` qua hồ sơ công ty.
- "Ngoài ASCII" gồm cả chữ tiếng Việt Unicode lẫn mã nhồi của phông cũ; luật không phân biệt hai trường hợp (cả hai đều là vấn đề khi dùng phông không Unicode).
- VS-04 trên tệp rất lớn đọc theo dòng có thể chỉ tính trên phần đầu danh sách đối tượng (có ghi chú trong thông điệp).
