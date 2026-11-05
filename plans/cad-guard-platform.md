# cad-guard — Nền tảng: tệp nặng, nhiều định dạng, một giao diện hợp nhất

Trạng thái: **ĐÁNH GIÁ + ĐỀ XUẤT, chờ CEO duyệt** (05/11/2026). Bổ sung cho `plans/cad-guard-direction.md` (hướng theo tệp, DXF chung) và `plans/cad-guard-vision-assessment.md` (năm khối, mô hình chi tiết là trục). Bản mẫu giao diện: `design/ui-mockup.html` (theo phòng, đã chọn), `design/ui-unified.html` (tham khảo). Chưa viết code lõi chỉ mục. Cập nhật 05/11/2026: thêm mục 7a (phòng Thiết kế 3D); **ưu tiên phòng Kỹ thuật trước, phần 3D đi sau** theo chỉ đạo CEO.
Quy tắc dữ liệu: các số đo dưới đây lấy từ bản vẽ thật **ở ngoài repo**, bằng kịch bản chỉ in số tổng hợp (kích thước, thời gian, bộ nhớ, số đối tượng). Không có tên tệp, layer, khối hay nội dung chữ.

## 1. Kết luận ngắn

1. **Công nghệ đang chọn (Python + ezdxf) đủ cho lõi luật nhưng không đủ ở cách đang dùng.** Đường "nạp cả tệp bằng `ezdxf.readfile` rồi dựng `DrawingModel` là danh sách đối tượng pydantic" không chịu được tệp vài trăm MB trên máy 8 GB. Đường "đọc theo luồng" đã có trong `profile.py` chịu được về bộ nhớ nhưng chậm (≈ 7 MB/s, tức 1 GB mất hơn 2 phút) và chưa dùng cho `audit`.
2. **Phương án tối ưu: tách "đọc" khỏi "hỏi".** Đọc tệp **một lần** theo luồng và ghi thành **chỉ mục** (SQLite + chỉ mục không gian) theo mã băm tệp; mọi thứ sau đó (luật, trình xem, trợ lý, bóc tách) chỉ hỏi chỉ mục. Lõi luật vẫn là Python; phần tách token DXF chuyển sang Rust khi cần tốc độ (bước 2, có cổng đo). Giao diện không bao giờ chờ: lập chỉ mục chạy nền, có tiến độ và huỷ được.
3. **Đa định dạng là làm được và nên làm, nhưng theo bậc tin cậy, không phải "đọc gì cũng như nhau".** Một mô hình bản vẽ chung, nhiều bộ đọc; mỗi tệp mang **bậc A–D** tuỳ nguồn; luật tự bỏ qua (`Skip`) khi bậc không đủ. DXF là bậc A; DWG đi qua phần mềm CAD của khách (A) hoặc bộ chuyển có giấy phép (B); PDF vector (C); ảnh và PDF quét (D, trích tham số, sinh bản nháp).
4. **Giao diện theo phòng** (`design/ui-mockup.html`, bốn phòng kể từ 05/11): mỗi phòng chỉ thấy việc, công cụ và luật của mình; "Luật áp dụng" và "Kết nối AI" giữ như bản mẫu đó. Khung tác vụ nền và nhãn bậc tin cậy sẽ được thêm vào từng phòng. Chi tiết ở mục 7; phòng Thiết kế 3D ở mục 7a.
5. **Thứ tự (CEO 05/11/2026):** phân tích, soát lỗi, làm sạch cho phòng Kỹ thuật làm trước để đi khảo sát; phòng Thiết kế 3D làm sau, chỉ dựng bản kỹ thuật đã đạt (mục 7a.4).

## 2. Dữ kiện đo được (05/11/2026, máy 8 GB RAM, 4 luồng CPU)

Kho mẫu ngoài repo hiện có: 5 DWG (7–47 MB, tổng 139 MB), 1 DXF ASCII 456 MB (chuyển từ DWG 49 MB, tức DXF ≈ 9 lần DWG), 1 PDF nhỏ, 2 ảnh. "DXF vài trăm MB tới 1 GB" tương đương DWG 50–120 MB: đúng cỡ bản vẽ công trình đầy đủ mà CEO mô tả.

| Đường đọc tệp DXF 456 MB | Thời gian | Bộ nhớ đỉnh | Ghi chú |
| --- | --- | --- | --- |
| `profile_dxf_stream` (đọc từng dòng, tự viết, Python thuần) | 39–65 s (hai lần chạy) | thấp theo thiết kế (chỉ giữ bộ đếm); chưa đo được số chính xác, xem 2.1 | Chỉ đếm; chưa dựng mô hình, chưa chạy luật |
| `ezdxf.addons.iterdxf` (đọc từng đối tượng không gian mô hình) | 41–87 s (hai lần chạy) | thấp theo thiết kế; chưa đo được số chính xác | Chỉ không gian mô hình (18.667 đối tượng, 15 loại); **không** vào định nghĩa khối, mà khối chứa 9–23 lần số đối tượng của mô hình ở 4/5 tệp (`docs/real-sample-profile.md`) |
| `ezdxf.readfile` + `build_model` (đường `audit` hiện tại) | **597 s** (≈ 10 phút; nạp 496 s + dựng mô hình 101 s) | **≥ 1,27 GB** working set quan sát được trong lúc máy chỉ còn ≈ 0,7 GB trống và đang phân trang; nhu cầu thật cao hơn | Xong được, nhưng không dùng được trong thực tế: 10 phút cho một lượt, máy gần như không làm việc khác được; chỉ 18.738 đối tượng không gian mô hình mà `build_model` mất 101 s vì duyệt mọi khối |

Kết luận từ số đo: Python thuần đọc DXF theo luồng ở ≈ 5–11 MB/s (dao động theo trạng thái đĩa/bộ đệm). Với 1 GB, một lượt đọc là 1,5–3,5 phút. Chấp nhận được **nếu chỉ làm một lần** rồi lưu; không chấp nhận được nếu mỗi lần quét, mỗi lần mở, mỗi câu hỏi của trợ lý đều đọc lại. Nạp trọn bằng ezdxf chậm hơn 10–15 lần và chiếm bộ nhớ gấp nhiều lần: loại.

### 2.1 Giới hạn của phép đo

- Thời gian dao động lớn giữa hai lần chạy vì cùng lúc có tiến trình nạp trọn chiếm bộ nhớ và máy phân trang; số nhỏ hơn là gần với điều kiện bình thường hơn.
- Bộ nhớ đỉnh của hai đường luồng chưa đo được bằng số (bộ lấy mẫu working set từ PowerShell trả về 4 MB, không hợp lý); theo thiết kế chúng chỉ giữ bộ đếm và một đối tượng tại một thời điểm. Việc đo lại bằng `psutil` trong chính tiến trình là việc nhỏ ở H1.
- Chỉ một tệp 456 MB; tệp 1 GB là ngoại suy tuyến tính.

## 3. Năng lực của công nghệ đang chọn

| Thành phần | Đủ? | Vì sao |
| --- | --- | --- |
| ezdxf, nạp trọn (`readfile`) | **Không** cho tệp > ~100 MB trên máy 8 GB | ezdxf giữ cấu trúc đầy đủ trong bộ nhớ (tài liệu của chính thư viện nói rõ "giá là bộ nhớ lớn"); mỗi đối tượng là nhiều object Python |
| ezdxf `iterdxf` | Một phần | Bộ nhớ thấp, nhưng chỉ ASCII, chỉ không gian mô hình, không duyệt khối, không giữ tài nguyên; đủ cho một số luật, không đủ cho luật về khối và bố cục |
| Bộ đọc luồng tự viết (`profile.py`) | Một phần | Bộ nhớ thấp; cần mở rộng từ "đếm" sang "ghi chỉ mục"; tốc độ Python thuần là trần |
| `DrawingModel` = danh sách `EntityRec` (pydantic) | **Không** cho hàng triệu đối tượng | Ước 300–800 byte mỗi bản ghi → 2 triệu đối tượng là 1–2 GB chỉ cho mô hình; hợp lệ hoá pydantic tốn thêm thời gian |
| Bộ luật (hàm Python duyệt `model.entities`) | Đủ về logic, cần đổi cách truy cập | Luật nên truy vấn chỉ mục (SQL, bộ lọc theo layer/loại/bbox) thay vì duyệt list; nhiều luật hiện là O(n) đơn giản nên chuyển đổi nhẹ |
| Báo cáo HTML/JSON | Đủ | Không phụ thuộc kích thước tệp |
| Trình xem (chưa có) | Phải thiết kế ngay từ đầu cho tệp lớn | Không được gửi DXF lên trình duyệt; dựng từ chỉ mục theo ô |

Nói ngắn: **giữ Python + ezdxf làm lõi luật và công cụ ghi DXF mới; thay cách nạp dữ liệu.** Không cần đổi ngôn ngữ toàn bộ; chỉ phần tách token, nếu đo thấy cần, mới đưa xuống Rust.

## 4. Phương án tối ưu hiệu năng

### 4.1 Kiến trúc "đọc một lần, hỏi nhiều lần"

```text
Tệp nguồn (chỉ đọc)
   │  (1) Lập chỉ mục: đọc theo luồng, ghi ra chỉ mục; chạy nền, có tiến độ, huỷ được
   ▼
Chỉ mục  <mã băm tệp>.cgidx  = SQLite (WAL) + R-tree bbox + bảng cột cho toạ độ
   │  layers · styles · blocks (định nghĩa 1 lần) · entities (handle, type, layer, bbox, vài thuộc tính) · texts · dims · inserts (ma trận)
   ├──► (2) Bộ luật: truy vấn SQL/bộ lọc; chạy song song theo nhóm luật (process pool); kết quả lưu kèm phiên bản chuẩn
   ├──► (3) Trình xem: lấy đối tượng theo bbox + mức chi tiết; vẽ WebGL trong worker
   ├──► (4) Trợ lý (MCP): query_model trả tóm tắt/truy vấn, không trả thô
   ├──► (5) Mô hình chi tiết (cg.product/1): rút từ chỉ mục + bảng + thuộc tính khối
   └──► (6) Ghi DXF mới: chỉ khi áp dụng thay đổi; đọc lại tệp gốc theo luồng và ghi tệp mới theo luồng (sao chép + vá), không nạp trọn
```

Nguyên tắc: **tệp gốc đọc tối đa hai lần** (lập chỉ mục; ghi bản mới). Mọi tương tác khác chạy trên chỉ mục, kích thước ≈ 10–20% tệp DXF ASCII (ước, chưa đo).

### 4.2 Bốn bước, mỗi bước có số đo để quyết

| Bước | Việc | Mục tiêu đo (tệp 1 GB, máy 8 GB) | Khi nào làm |
| --- | --- | --- | --- |
| **H1** | Mở rộng bộ đọc luồng thành **bộ ghi chỉ mục** (Python); đọc cả BLOCKS và ENTITIES; INSERT giữ ma trận, không bung khối; `audit` chạy trên chỉ mục; `DrawingModel` thành lớp truy vấn, không còn list | Lập chỉ mục ≤ 4 phút; bộ nhớ ≤ 1,5 GB; mở lại ≤ 2 s; chạy 20 luật ≤ 30 s | Ngay (P1a), vì audit hiện không chạy nổi trên mẫu thật |
| **H2** | Song song: tách tệp theo mục (BLOCKS, ENTITIES) và theo khối để lập chỉ mục bằng nhiều tiến trình; luật chạy theo nhóm | Lập chỉ mục ≤ 1,5 phút trên 4 lõi | Sau H1 nếu khách than chậm |
| **H3** | Bộ tách token DXF bằng **Rust** (PyO3), ghi thẳng Arrow/SQLite; Python chỉ điều phối | Lập chỉ mục ≤ 30 s (ước từ tốc độ đọc 100–300 MB/s của tokenizer biên dịch; **chưa đo**) | Khi H2 vẫn không đạt, hoặc khi cần "mở là thấy" |
| **H4** | Trình xem theo ô: WebGL, chỉ tải đối tượng trong khung nhìn từ chỉ mục, mức chi tiết theo tỉ lệ; phân tích trong Web Worker | Khung đầu ≤ 2 s; kéo/thu phóng ≥ 30 fps với 2 triệu đối tượng | Cùng Tầng 1b (trình xem) |

Việc **không** nên làm: nạp trọn bằng ezdxf rồi tối ưu vòng lặp (trần bộ nhớ vẫn còn); tự viết bộ dựng hình native từ đầu; gửi DXF lên trình duyệt để parse phía client (vagran/dxf-viewer làm được stream parse nhưng vẫn là parse lại mỗi lần mở).

### 4.3 Chi tiết đáng chú ý

- **Khối là phần lớn dữ liệu.** Lưu định nghĩa khối một lần, bung khi cần theo INSERT (ma trận). Luật về layer trong khối chạy trên định nghĩa; luật về vị trí chạy trên INSERT đã nhân ma trận cho bbox.
- **DXF nhị phân** nhỏ hơn và tách token nhanh hơn ASCII; nếu phần mềm CAD của khách xuất được nhị phân, ưu tiên (iterdxf không đọc nhị phân, nên bộ đọc riêng phải lo).
- **Mã hoá chữ tiếng Việt** (phông VNI/TCVN cũ) xử lý ở bước lập chỉ mục một lần, ghi cả chuỗi gốc và chuỗi đã chuẩn hoá Unicode.
- **Bộ nhớ đệm chỉ mục** theo mã băm: cùng tệp ở hai máy cho cùng chỉ mục; chỉ mục có thể đặt trên ổ mạng dùng chung cho cả phòng.
- **Chế độ máy chủ phòng** (tuỳ chọn): một máy 16–32 GB lập chỉ mục cho cả phòng, máy thợ vẽ chỉ mở trình xem. Không bắt buộc; kiến trúc cho phép vì giao tiếp đã qua chỉ mục.
- **Cấu hình máy khuyến nghị** cho máy thợ vẽ: 16 GB (8 GB chạy được với lập chỉ mục nền, trình xem sẽ chậm hơn).

## 5. Đa định dạng

### 5.1 Nguyên tắc

- **Một mô hình, nhiều bộ đọc.** Mọi định dạng vào đều thành `cg.drawing/1` (và chỉ mục). Luật không biết tệp gốc là gì.
- **Bậc tin cậy gắn với tệp và với từng trường.** Luật khai báo "cần gì" (layer, khối, kích thước có giá trị đo, bố cục); thiếu thì `Skip("bậc không đủ")` — cơ chế đã có trong AGENTS.md.
- **Không hứa đọc mọi thứ như DXF.** Giao diện nói rõ bậc và lý do; báo cáo ghi bậc.

### 5.2 Từng định dạng

| Định dạng | Đường đọc | Bậc | Giấy phép / chi phí | Ghi chú |
| --- | --- | --- | --- | --- |
| **DXF** ASCII/nhị phân | Bộ đọc luồng riêng (H1) / ezdxf cho tệp nhỏ và để ghi | A | MIT | Định dạng chung đã duyệt |
| **DWG** | (1) Phần mềm CAD của khách xuất DXF bằng tập lệnh "lưu kèm DXF" (LISP ở ZWCAD/GstarCAD/BricsCAD, cần kiểm từng phần mềm) | A | 0 | Đường mặc định, không cần bên thứ ba |
| | (2) Bộ chuyển có giấy phép thương mại: ODA Core (trang giá bản tiếng Nhật ghi 3.000 USD năm đầu, 2.250 USD/năm sau, phân phối tối đa 100 ghế; **cần xác nhận lại trên trang tiếng Anh**), Aspose.CAD (reseller ghi từ 783 USD), RealDWG qua Tech Soft 3D (báo giá) | B | Có phí | Bật khi công ty mua giấy phép; kết quả ghi "có thể do chuyển đổi" |
| | (3) LibreDWG (GPLv3), ODA File Converter (phi thương mại) | — | **Không dùng trong sản phẩm** | Đã loại ở `docs/licenses.md`; chỉ dùng phân tích nội bộ một lần |
| **PDF vector** | Trích đường/chữ bằng pdfplumber (pdfminer.six, MIT); **không** dùng PyMuPDF trừ khi mua giấy phép thương mại (AGPL) | C | MIT | Dùng để kiểm hình thức, so khớp với DXF (bản khách duyệt ≠ bản triển khai), bóc chữ; không có layer/khối, không xuống máy |
| **PDF quét, ảnh, phác thảo** | VLM → bảng tham số → sinh bản nháp từ mẫu ezdxf (xem `cad-guard-vision-assessment.md` 3.1) | D | API theo BYOK | Luôn có người xác nhận; nhãn "bản nháp từ ảnh" |
| **SKP / 3D** (sau) | Nhận glTF/OBJ/IFC để so với mô hình chi tiết | C | glTF mở; SKP cần SDK Trimble (kiểm giấy phép) | Chỉ khi phòng diễn hoạ cần đối chiếu ngược |
| **Ra** | DXF mới (ezdxf), CSV/Excel, glTF/OBJ (mô hình chi tiết), nhãn, `.mpr` theo cấu hình máy | — | — | Không sinh G-code |

### 5.3 Cách tổ chức mã

`cadguard/readers/` với giao diện chung `Reader.index(path, out) -> IndexInfo(tier, caps, warnings)`; `dxf_stream.py`, `pdf_vector.py`, `image_params.py`, `dwg_external.py` (gọi bộ chuyển ngoài nếu có cấu hình). Chuẩn `furniture-v0.yaml` thêm trường `requires: [layers, blocks, dim_measure…]` cho mỗi luật; `runner` so với `caps` của chỉ mục để `Skip`.

## 6. Phương án đề xuất (gộp) và điều chỉnh lộ trình

Chọn: **H1 + bậc tin cậy + giao diện hợp nhất** làm P1 mới; H2/H3/H4 có cổng đo; bộ chuyển DWG thương mại chỉ mua khi P0 cho thấy phòng kỹ thuật không xuất DXF được.

| Giai đoạn | Việc | Kích cỡ | Cổng đi tiếp |
| --- | --- | --- | --- |
| P1a' | Bộ ghi chỉ mục luồng (DXF), `audit` trên chỉ mục, luật hiện có chuyển sang truy vấn, bậc tin cậy + `requires` | L | 5 mẫu thật chạy hết `audit` trong ≤ 4 phút/tệp, ≤ 1,5 GB |
| P1b' | Bộ đọc PDF vector + so khớp PDF↔DXF (chữ, kích thước); tập lệnh "lưu kèm DXF" cho CAD khách | M | Phòng kỹ thuật dùng được không cần hướng dẫn tay |
| P1c | Đo độ chính xác luật (giữ nguyên) | XS | ≥ 10 luật có số |
| P2' | Trình xem theo ô (H4) + ba cột + năm bước (bản mẫu `ui-unified.html`), thay đổi có xem trước ghi tệp mới theo luồng | L | Mở tệp 1 GB đã lập chỉ mục ≤ 2 s |
| P3' | Bóc tách → mô hình chi tiết → đầu ra sản xuất (G1–G2 của `vision-assessment`) | L | Như tài liệu đó |
| Tuỳ | H2/H3 (song song, Rust), ảnh → tham số (bậc D) | M–L | Theo cổng đo và nhu cầu |
| Sau Kỹ thuật | Phòng Thiết kế 3D: V1–V5 (mục 7a.4); render tầng B/C tuỳ chọn | M–L | Chỉ bắt đầu khi khảo sát Kỹ thuật xong và P1a' đạt |

## 7. Giao diện

**Quyết định (CEO, 05/11/2026): giữ hướng giao diện theo phòng của `design/ui-mockup.html`.** Mỗi công đoạn là một phòng, một loại nhân sự; màn hình chỉ đưa thông tin, công cụ và luật mà người làm ở phòng đó cần, để tập trung và giảm nhầm lẫn. Màn "Luật áp dụng" (gắn phòng · vị trí · task, bản nháp, duyệt, phiên bản) và "Kết nối AI" của bản mẫu đó cũng là hướng đúng. Bản `design/ui-unified.html` (một luồng năm bước) **không chọn**, giữ lại chỉ để tham khảo hai thành phần sẽ đưa vào từng phòng: khung "Tác vụ nền" (tiến độ lập chỉ mục, bộ nhớ lõi) và nhãn "bậc tin cậy" của tệp.

Bản mẫu theo phòng đã có **bốn phòng** (05/11): Thiết kế → Kỹ thuật → {Thiết kế 3D, Lập trình sản xuất}. Phòng **Thiết kế 3D** (diễn hoạ) nhận bản kỹ thuật đã chuẩn, dựng 3D từ mô hình chi tiết, kiểm bốn việc (đơn vị, tên vật thể theo mã chi tiết, va chạm giữa tấm, vật liệu cho bề mặt nhìn thấy), đề xuất góc máy và bộ ánh sáng, rồi giao "gói cho render" (glb, góc máy, ánh sáng, bảng vật liệu). Luật `3D-01…06`, vị trí "Hoạ viên 3D", task t9–t11 và cổng "Bàn giao Thiết kế 3D → Render" được thêm vào danh mục luật. Mã luật 3D- là mã minh hoạ. Ánh xạ sang thành phần kỹ thuật, tình trạng và lộ trình: mục 7a.

Những điều cần đưa thêm vào bản mẫu theo phòng ở vòng sau (từ mục 4 và 5): khung tác vụ nền ở cột trái mỗi phòng; nhãn bậc tin cậy cạnh tên tệp; dòng trạng thái ghi số đối tượng, mức chi tiết đang vẽ, kích thước chỉ mục; màn "Hệ thống" cho quản trị (hiệu năng, định dạng, bộ chuyển DWG) tách khỏi "Kết nối AI" hoặc là một thẻ trong đó.

Ghi chú lịch sử: các quyết định dưới đây được viết cho `ui-unified.html` trước khi CEO chọn hướng theo phòng; phần còn áp dụng được đã nêu ở đoạn trên.

- **Một màn làm việc "Dự án" với năm bước trên thanh ngang**, thay cho năm màn riêng: người dùng thấy bản vẽ đang ở đâu và bước nào đang chặn; chuyển phòng chỉ đổi bước mặc định và luật áp dụng, không đổi màn.
- **Ba cột cố định.** Trái: cây tệp (Nguồn chỉ đọc / Sinh ra có phiên bản) và **Tác vụ nền** (tiến độ lập chỉ mục, bộ nhớ lõi). Giữa: khung đổi theo bước (2D theo ô, bảng tấm, 3D, danh sách đầu ra). Phải: Trợ lý / Lỗi / Thay đổi, giữ nguyên từ bản mẫu cũ. Lý do: phần người dùng quen (tệp, trợ lý) không đổi chỗ; chỉ phần việc đổi.
- **Bậc tin cậy là nhãn trạng thái mềm** (A xanh, B/C hổ phách, D xám) đi kèm chữ, không chỉ màu, xuất hiện ở bước Nhận tệp, thanh công cụ và báo cáo.
- **Cổng chặn là dải màu có chữ** (hổ phách khi chặn, xanh khi đạt) ngay trên nội dung bước; nút "Gửi gói" bị vô hiệu kèm lý do, không ẩn.
- **Tệp nặng được thể hiện, không giấu**: dòng trạng thái ghi số đối tượng, mức chi tiết đang vẽ, kích thước chỉ mục; tác vụ nền có phần trăm; giao diện không có trạng thái "đang tải" toàn màn.
- **Màn "Hệ thống"** gom hiệu năng, định dạng và kết nối AI, dành cho quản trị, thay cho màn "Kết nối AI" riêng.
- Giữ nguyên bảng màu, chữ, bo góc, nhãn trạng thái của `ui-mockup.html` (đã kiểm sáng/tối ngày 05/11; ảnh chụp trong phiên làm việc).

Chưa có trong bản mẫu (làm ở vòng sau): kéo thả thật, so khớp PDF↔DXF trực quan, bảng tham số từ ảnh, khác biệt gói sản xuất.

## 7a. Phòng Thiết kế 3D: diễn hoạ

Nhãn dùng trong mục này: **[code]** = đã có code trên nhánh chính, có test; **[mẫu]** = chỉ có trong bản mẫu `design/ui-mockup.html`, dữ liệu minh hoạ; **[đề xuất]** = chưa có, cần duyệt.

**Thứ tự ưu tiên (chỉ đạo CEO 05/11/2026):** làm trước phần phân tích bản vẽ, soát lỗi, làm sạch của **phòng Kỹ thuật** để đưa đi khảo sát người dùng. Phòng Thiết kế 3D đi **sau**, và chỉ dựng 3D cho bản kỹ thuật **đã đạt** luật. Mục này là kế hoạch để khi tới lượt không phải làm lại, không phải việc làm ngay.

### 7a.1 Vị trí trong chuỗi 4 phòng [mẫu]

```text
Thiết kế → Kỹ thuật → ┬ Thiết kế 3D (diễn hoạ) → Render (ảnh cho khách)
                      └ Lập trình sản xuất     → Xưởng
```

| Mục | Nội dung theo bản mẫu |
| --- | --- |
| Nhận từ Kỹ thuật | Bản kỹ thuật đã chuẩn (ví dụ `sanh-A_ky-thuat.dxf`), ghi chú "bảng kê khớp hình", kèm **mô hình chi tiết v1** (tấm, kích thước, vị trí lắp) |
| Người dùng | Vị trí "Hoạ viên 3D" |
| Việc chính | Dựng 3D tự động từ mô hình chi tiết (mỗi tấm là một hộp đúng kích thước, đặt theo vị trí lắp; phụ kiện từ thư viện); kiểm mô hình; chọn góc máy và bộ ánh sáng; giao gói cho render |
| Giao cho Render | "Gói cho Render": `.glb` (tên vật thể theo mã chi tiết, đơn vị mm), 3 góc máy (toạ độ, cao 1,5 m, tiêu cự 24/35/50 mm), bộ ánh sáng "sảnh ban ngày" 5.500 K + một phương án đêm, bảng vật liệu theo mã bảng kê (`.csv`) |
| Cổng chặn | "Bàn giao Thiết kế 3D → Render" (task t11): các luật 3D- gắn task đó phải sạch |

Ghi chú: Kỹ thuật giao **song song** cho Thiết kế 3D và Lập trình sản xuất; hai phòng sau không phụ thuộc nhau.

### 7a.2 Bản mẫu thể hiện gì → thành phần kỹ thuật

Màn làm việc của phòng (giống ba phòng kia): cây tệp, khung giữa là hình 3D (bản mẫu vẽ SVG giả lập góc nhìn iso: tường, quầy lễ tân H-03, camera và mặt trời đề xuất, bảng "Thông số mô hình"), cột phải là Trợ lý / Lỗi / Thay đổi. Hai sửa tự động có xem trước trước/sau và hoàn tác: (a) đổi đơn vị mô hình, (b) đặt tên 142 vật thể theo mã chi tiết. Hai lỗi còn lại "cần người": va chạm (hỏi Kỹ thuật, trợ lý không tự dời tấm) và vật liệu (hoạ viên chọn, trợ lý chỉ gợi ý từ bảng kê). Chuẩn hiển thị là "viz-v0 (nháp)", mã luật 3D- là **mã minh hoạ**.

| Bản mẫu | Thành phần kỹ thuật | Tình trạng |
| --- | --- | --- |
| Dựng 3D từ bản kỹ thuật | Cảnh tất định `cg.scene/1`: tường (`FN-ROOM-WALL`), mô-đun (`FN_MOD*` + thuộc tính W/D/H), tấm ván từ nhiều hình chiếu (`FN-VIEW-FRONT/TOP/SIDE`); thiếu chiều cao → `gaps[]`, không đoán | **[code]** `cadguard/scene/` (`build`, `views`, `geometry`), lệnh `cadguard scene` |
| Dựng từ "mô hình chi tiết v1" | Mô hình chi tiết `cg.product/1` (khối E, `vision-assessment` 3.5) làm đầu vào thay cho đọc hình chiếu | **[đề xuất]**, chưa có; tầng A hiện dựng từ DXF |
| Xuất `.glb` | `scene/gltf.py`, tự ghi glTF, không thư viện ngoài | **[code]**; mỗi **vật liệu** là một nút, chưa phải mỗi tấm |
| Khung xem 3D trong màn phòng | Trình xem canvas 2D tự viết (`scene/viewer.py`), dùng trong `cadguard scene --out .html` và `cadguard studio` | **[code]** cho scene/studio; **chưa** có trong `cadguard app` (màn theo phòng) |
| Bổ sung phần thiếu | Form `.cgsup.json` (`scene/form.py`), studio hỏi đáp LLM đề xuất `set_value`/`set_views` | **[code]**; studio là Bậc 2 (xem 7a.3) |
| 3D-01 đơn vị | Luật trên cảnh: bản vẽ phải `INSUNITS=4` (mm) mới dựng; glTF luôn tính bằng mét nên luật thật là "hệ số khi nhập vào phần mềm render đúng" | Điều kiện mm **[code]** trong `build`; luật 3D-01 **[đề xuất]** |
| 3D-02 tên theo mã chi tiết | Đặt tên nút glTF = mã chi tiết, nhóm theo khối | **[đề xuất]**; cần mã chi tiết trong mô hình (khối E) |
| 3D-03 va chạm tấm | Kiểm giao nhau giữa các hộp (tất định, rẻ) | **[đề xuất]**; nhóm luật mới mà 2D không làm được |
| 3D-04 vật liệu bề mặt nhìn thấy | Vật liệu từ thuộc tính `MAT`/bảng kê; "nhìn thấy" cần góc máy | **[đề xuất]** |
| 3D-05 góc máy, 3D-06 ánh sáng | Khối D: chọn trong **tập mẫu cài sẵn** (3–5 bộ ánh sáng, 3–4 góc máy theo kích thước phòng), xuất `goc-may.json` | **[đề xuất]**; `vision-assessment` 3.4 xếp ưu tiên thấp |
| Render | Tầng B: Blender chạy nền (clay/depth/ID); tầng C: khuếch tán + ControlNet, **tuỳ chọn**, ảnh luôn ghi "ảnh minh hoạ, không dùng để đo" | **[đề xuất]** (`cad-guard-3d.md` mục 4); bản mẫu không vẽ bước render, chỉ giao gói |

Điều kiện dựng (không đổi từ `cad-guard-3d.md`): có chiều cao (thuộc tính khối, mặt đứng hoặc quy ước tường); đơn vị mm; lệch kích thước giữa các hình > 0,5 mm là `conflict` phải sửa bản vẽ.

### 7a.3 Tình trạng, phụ thuộc, rủi ro

**Đã có [code]:** tầng A và A2 của `cad-guard-3d.md` (cảnh `cg.scene/1`, GLB, HTML xem 3D, dựng từ nhiều hình chiếu, form bổ sung), `cadguard studio` (LLM đề xuất thao tác cố định, ghi tệp mới); `tests/test_scene.py` và `tests/test_studio.py` mỗi tệp 13 ca. Dòng "Chưa viết code" ở đầu `cad-guard-3d.md` đã lỗi thời.

**Chưa có:** luật 3D- và chuẩn `viz-v0`; tên nút theo mã chi tiết; đầu vào từ mô hình chi tiết; xem 3D trong `cadguard app`; góc máy/ánh sáng; gói cho Render; tầng B, C. Cảnh 3D hiện đọc bằng `read_dxf` (nạp trọn), nên **chưa chạy được trên tệp lớn** cho tới khi có chỉ mục H1 (mục 4).

**Phụ thuộc phòng Kỹ thuật:** chỉ dựng bản đã qua luật của Kỹ thuật (đơn vị, layer, bảng kê khớp hình, thuộc tính khối đủ). Cổng đề xuất: tệp còn lỗi mức E ở bộ luật Kỹ thuật thì `scene` từ chối, báo lý do. Vì vậy toàn bộ giá trị của phòng 3D đứng sau P1a' và các luật Kỹ thuật.

| Rủi ro | Mức | Giảm thiểu |
| --- | --- | --- |
| Giấy phép trình xem: hiện **không** dùng three.js (canvas tự viết). Nếu chuyển sang three.js (MIT) để xem cảnh lớn | Thấp | Đóng gói sẵn, không CDN, ghi vào `docs/licenses.md` trước khi dùng |
| Blender là GPL: chỉ gọi như chương trình ngoài (`blender -b -P`), không liên kết, không phân phối kèm | Vừa | Xin ý kiến luật sư trước khi đưa vào gói cài; mặc định khách tự cài Blender |
| GPU: tầng C cần ≥ 12 GB VRAM; máy thợ vẽ hiện 8 GB RAM | Cao cho C | Dừng ở A (+B) vẫn có giá trị; C chỉ làm khi đo xong B và có quyết định chạy cục bộ hay dịch vụ |
| Dữ liệu gửi AI: studio gửi **tên layer, tên khối, chữ, toạ độ thật** (Bậc 2, `cad-guard-3d.md` 3c.1); tầng C gửi ảnh nếu dùng dịch vụ ngoài | Cao | Giữ đồng ý theo từng phiên; màn phòng 3D trong `app` mặc định Bậc 1 (ẩn danh); tầng C dịch vụ ngoài là Bậc 2 riêng, cần CEO duyệt |
| Phòng diễn hoạ đã có công cụ quen (SketchUp, 3ds Max, D5, Enscape…) và render có AI riêng | Vừa | Giá trị chính là **khối đúng kích thước, đúng tên, không va chạm**; không cạnh tranh ở render |
| Ảnh minh hoạ bị dùng như hồ sơ | Vừa | Nhãn cố định trên mọi ảnh tầng C; không đưa ảnh vào gói sản xuất |

### 7a.4 Lộ trình bước nhỏ (sau phần Kỹ thuật)

Không bắt đầu V1 trước khi cổng V0 đạt.

| Bước | Việc | Cổng đo được |
| --- | --- | --- |
| V0 (điều kiện vào) | Luật Kỹ thuật chạy trên chỉ mục (P1a'), khảo sát phòng Kỹ thuật xong | P1a' đạt cổng; kết quả khảo sát có; CEO xác nhận mở phần 3D |
| V1 | Hỏi phòng diễn hoạ: phần mềm render, định dạng nhận (glb/obj/fbx/skp), quy ước tên, đơn vị nhập | Bảng trả lời của ≥ 2 hoạ viên; chọn được định dạng chính |
| V2 | `scene` chạy trên chỉ mục (thay `read_dxf`); cổng "bản kỹ thuật đạt" trước khi dựng | Tệp mẫu lớn dựng cảnh ≤ 1 phút sau khi đã lập chỉ mục; bản có lỗi E bị từ chối kèm lý do |
| V3 | GLB mỗi tấm một nút tên theo mã chi tiết; luật 3D-01…03 (đơn vị, tên, va chạm) vào chuẩn `viz-v0` (mã chính thức) | Fixture tổng hợp: 0 mm sai lệch kích thước; ca va chạm dương được bắt; mở GLB trong phần mềm render phòng chọn ở V1 không phải chỉnh tỉ lệ |
| V4 | Màn phòng Thiết kế 3D trong `cadguard app`: xem 3D, lỗi 3D-, gói bàn giao | Hoạ viên dùng được không cần hướng dẫn tay (thử với 1–2 người) |
| V5 | Góc máy + ánh sáng từ tập mẫu (3D-05, 3D-06), xuất `goc-may.json`; bảng vật liệu theo bảng kê (3D-04) | Góc máy nằm trong phòng 100% trên fixture; hoạ viên giữ ≥ 1 trong 3 góc đề xuất |
| V6 (tuỳ) | Tầng B Blender: clay/depth/ID | Đo thời gian/ảnh, độ lệch hình học bằng so depth trên máy thật |
| V7 (tuỳ) | Tầng C khuếch tán | Chỉ khi B đạt và CEO quyết cục bộ hay dịch vụ |

### 7a.5 Điểm cần CEO quyết

| # | Câu hỏi | Đề xuất |
| --- | --- | --- |
| 1 | Xác nhận thứ tự: phòng 3D chỉ bắt đầu sau khi khảo sát phòng Kỹ thuật xong và P1a' đạt | Có |
| 2 | Đầu vào 3D lấy từ mô hình chi tiết (khối E) như bản mẫu, hay tiếp tục từ hình chiếu DXF (tầng A hiện tại) | Hình chiếu DXF trước (đã có code); chuyển sang mô hình chi tiết khi khối E có |
| 3 | Có làm góc máy/ánh sáng (khối D) hay dừng ở "gói khối đúng kích thước + tên + không va chạm" | Dừng ở V4, quyết V5 sau khi hỏi hoạ viên (V1) |
| 4 | Render tầng B/C: làm, và nếu C thì cục bộ (cần GPU) hay dịch vụ ngoài (Bậc 2) | Chưa làm; quyết sau V4 |
| 5 | Cho phép hỏi phòng diễn hoạ của công ty (V1) | Có, khi tới lượt |

## 8. Nguồn

Đã kiểm (tài liệu chính thức):

- ezdxf `iterdxf`: chỉ ASCII, chỉ không gian mô hình, đối tượng không gắn tài liệu; gói chính "giữ cấu trúc với giá là bộ nhớ lớn": [ezdxf.readthedocs.io/addons/iterdxf](https://ezdxf.readthedocs.io/en/stable/addons/iterdxf.html).
- ODA: cấp phép theo site, không theo người dùng; bảng giá: [opendesign.com/pricing (JA)](https://www.opendesign.com/ja/pricing), gói Core: [opendesign.com/core-package](https://www.opendesign.com/core-package.md).
- RealDWG cấp phép qua Tech Soft 3D: [aps.autodesk.com RealDWG OEM](https://aps.autodesk.com/developer/overview/realdwg-oem), [techsoft3d.com](https://www.techsoft3d.com/oem/realdwg).
- Số đo trong repo: `docs/real-sample-profile.md` (04/11) và phép đo 05/11 (mục 2).

Thứ cấp (chưa kiểm độc lập):

- Aspose.CAD giá từ reseller: [componentsource.com](https://www.componentsource.com/product/aspose-cad-for-net/releases/2402796).
- Trình xem web: vagran/dxf-viewer (MPL-2.0, stream parse, worker): [github.com/FileMap/dxf-viewer](https://github.com/FileMap/dxf-viewer); mlightcad/cad-viewer (Three.js, LibreDWG cho DWG, có vấn đề bộ nhớ với DWG lớn): [github.com/mlightcad/cad-viewer](https://gh.r-mj.com/mlightcad/cad-viewer).
- Trích vector PDF: PyMuPDF `get_drawings()` (Artifex, AGPL/thương mại): [artifex.com](https://artifex.com/blog/extracting-and-creating-vector-graphics-in-a-pdf-using-python-pymupdf); pdfplumber dùng cho đường/chữ trong một pipeline mở: [github.com/chandran65/DraftForge](https://github.com/chandran65/DraftForge). Giấy phép MIT của pdfplumber/pdfminer.six là theo hiểu biết chung, **cần kiểm trên PyPI trước khi dùng**.

## 9. Not yet specified

- Kích thước chỉ mục thực tế so với DXF (đo ở H1).
- Tốc độ bộ tách token Rust trên tệp thật (đo ở H3, nếu làm).
- Phần mềm CAD của khách có LISP/tập lệnh xuất DXF không (P0).
- Giấy phép bộ chuyển DWG nào mua, nếu cần (sau P0).
- Thư viện WebGL cho trình xem: tự dựng từ chỉ mục hay dùng lõi của vagran/dxf-viewer (MPL-2.0 cho phép dùng trong sản phẩm đóng nếu giữ nguyên tệp MPL; cần luật sư xem).

## Progress

- 05/11/2026: đo stream/iterdxf/nạp trọn trên DXF 456 MB (mục 2); bản mẫu `ui-unified.html` dựng và kiểm sáng/tối; tài liệu này viết. Chưa commit.
- 05/11/2026: thêm mục 7a (phòng Thiết kế 3D theo bản mẫu bốn phòng), đối chiếu với code `scene/`, `studio/`; ghi thứ tự ưu tiên Kỹ thuật trước. Chưa commit.
