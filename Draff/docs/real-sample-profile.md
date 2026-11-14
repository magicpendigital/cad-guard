# Hồ sơ 5 bản vẽ thật (đợt mẫu 04/11/2026) — số tổng hợp, ẩn danh

Trạng thái: **kết quả đầu tiên trên dữ liệu thật, n = 5, một công ty, khâu thiết kế/kỹ thuật.** Không đủ để kết luận về cả ngành; đủ để sửa vài giả định sai của kế hoạch.
Quy tắc dữ liệu: bản vẽ thật nằm **ngoài repo** (thư mục riêng trên ổ D, do CEO chuyển ra ngày 04/11; thư mục dữ liệu mẫu cũ vẫn bị chặn trong `.gitignore` để phòng khi đặt lại). Tài liệu này chỉ có **con số**: không tên tệp/layer/khối/khách, không nội dung chữ. Các tệp được gọi M1–M5.
Đội MCA và mọi agent **chỉ được đọc tài liệu này** và DXF tổng hợp, không được đọc bản thật (xem `AGENTS.md`).

## 1. Kết luận ngắn

1. **Bối cảnh là một công ty sản xuất có ba phòng nối tiếp nhau: Thiết kế → Kỹ thuật → Lập trình sản xuất (rồi xưởng).** Năm bản mẫu thuộc khâu thiết kế/kỹ thuật (bản vẽ triển khai nội thất công trình: sảnh, khu tiện ích, bản triển khai tổng hợp). Chuẩn `furniture-v0` (khung tên, viewport, thẻ vị trí, bảng kê, dán cạnh) viết cho khâu sau (bản vẽ chi tiết đưa xuống sản xuất) nên **hầu như không áp dụng được cho khâu này**. Chưa có mẫu nào của phòng lập trình sản xuất.
2. **Bản vẽ làm hoàn toàn trong không gian mô hình.** 4/5 tệp có 0 đối tượng trong không gian giấy, 1 tệp có 2. Không có viewport/tỉ lệ khung nhìn để kiểm: nhóm luật VW và phần lớn SH vô nghĩa ở đây.
3. **Phần lớn nội dung nằm trong định nghĩa khối, không ở không gian mô hình** (gấp 9–23 lần ở 4/5 tệp). Bộ đọc và các luật hiện tại chỉ nhìn không gian mô hình: bỏ sót phần lớn bản vẽ.
4. **Tệp rất nặng.** DWG 7–49 MB thành DXF ASCII 77–445 MB. Nạp trọn tệp bằng ezdxf đã dùng hơn 500 MB RAM khi chưa xong ở tệp 78 MB; **ước tính (chưa đo)** là không nổi ở tệp 262–445 MB trên máy 8 GB. Đã làm đường đọc theo dòng: 11–29 giây/tệp.
5. **Quy ước của đơn vị này không giống chuẩn v0** (0% layer theo mẫu `FN-*`). Chuẩn phải **cấu hình theo công ty**, hoặc có chế độ "học quy ước từ bộ bản vẽ" rồi mới kiểm.
6. **Tiếng Việt là việc nghiêm túc:** 54–74% chữ có ký tự ngoài ASCII; nhiều phông tiếng Việt cũ (không Unicode) ở cả 5 tệp.

## 2. Phương pháp và giới hạn

- Chuyển DWG → DXF bằng **LibreDWG 0.14.8761 (bản dựng nightly, pre-release, GPLv3)**, tải từ trang phát hành chính thức, chạy **một lần, cục bộ, chỉ để phân tích nội bộ**, không đóng gói vào sản phẩm. Người dùng đồng ý bằng lời trong phiên (04/11). Tệp zip Windows **không có checksum công bố** (chỉ có cho bản mã nguồn); chỉ kiểm được kích thước khớp API. DXF sinh ra đặt ngoài repo.
- Định dạng DWG đầu vào: 4 tệp AutoCAD 2010–2012 (AC1024), 1 tệp AutoCAD 2007 (AC1021).
- Số liệu lấy bằng bộ đọc theo dòng `cadguard profile --stream` (mới); với M2 đối chiếu thêm bằng ezdxf: các số chính khớp.
- **Độ trung thực của chuyển đổi chưa kiểm được.** Trình chuyển ghi 530–9.566 cảnh báo và 3–700 lỗi mỗi tệp (đối tượng không nhận ra, lớp "không ổn định", tham chiếu thiếu; M1 nhiều nhất). Chưa biết mất bao nhiêu so với bản gốc. Cần ít nhất 1–2 tệp DXF xuất từ chính phần mềm CAD của đơn vị để đối chiếu (việc của P0).
- Chỉ chạy bộ luật hiện có (15 luật) trên **M2**; 4 tệp còn lại chưa chạy vì máy chỉ có 8 GB RAM.
- Không có nhãn "bản vẽ tốt/xấu", không có lịch sử sự cố: **chưa đo được độ chính xác của bất kỳ luật nào.**

## 3. Số liệu

| | M1 | M2 | M3 | M4 | M5 |
| --- | --- | --- | --- | --- | --- |
| DWG gốc (MB) | 49 | 7 | 43 | 34 | 12 |
| DXF ASCII (MB) | 445 | 94 | 321 | 262 | 78 |
| Số layer | 97 | 57 | 123 | 131 | 85 |
| Layer đúng mẫu `FN-*` (v0) | 0 | 0 | 0 | 0 | 0 |
| Layer có dấu `$` hoặc `\|` (xref đã gộp) | 31 | 23 | 40 | 41 | 6 |
| Đối tượng không gian mô hình | 18.722 | 2.064 | 18.720 | 21.810 | 156.214 |
| Đối tượng trong định nghĩa khối | 401.009 | 19.428 | 421.858 | 256.133 | 93.391 |
| Tỉ lệ khối / mô hình | 21 | 9 | 23 | 12 | 0,6 |
| Khối đặt tên / khối ẩn danh | 352 / 7.370 | 48 / 1.054 | 288 / 10.434 | 314 / 12.459 | 114 / 8.972 |
| Đối tượng trong không gian giấy | 0 | 0 | 0 | 0 | 2 |
| DIMENSION | 3.178 | 105 | 1.832 | 2.313 | 8.777 |
| DIMENSION có chữ ghi đè (%) | 2,0 | 2,9 | 6,0 | 5,5 | 0,5 |
| HATCH (mô hình) | 2.088 | 111 | 758 | 1.158 | 1.223 |
| WIPEOUT (mô hình / trong khối) | 22 / 4.039 | 0 / – | 0 / – | 1 / 3.028 | 10 / 137 |
| IMAGE + OLE (mô hình) | 19 | 2 | 19 | 17 | 38 |
| Đối tượng proxy | 0 | 0 | 0 | 0 | 0 |
| Đối tượng có màu ghi đè (không ByLayer) % | 19 | 3 | 16 | 22 | 77 |
| Đối tượng có độ dày nét ghi đè % | 2 | 0 | 40 | 34 | 0,5 |
| LINE có Z khác 0 (mô hình) | 471 | 1.379 | 23 | 44 | 0 |
| Đối tượng trên layer "0" (%) | 22,8 | 6,5 | 10,0 | 12,5 | 2,9 |
| 5 layer lớn nhất chiếm (%) | 68 | 88 | 91 | 80 | 82 |
| Kiểu chữ / kiểu kích thước | 43 / 17 | 25 / 8 | 52 / 20 | 44 / 13 | 23 / 26 |
| Chữ có ký tự ngoài ASCII (%) | 74 | 70 | 60 | 66 | 54 |
| Chuyển DWG→DXF (giây) | 111 | 16 | 78 | 31 | 18 |
| Đọc theo dòng (giây) | 29 | 11 | 29 | 20 | 13 |

Ghi chú: M1–M5 không theo thứ tự ý nghĩa nào. Dấu "–" là không thấy trong 10 loại đối tượng lớn nhất của khối (chưa đếm riêng). Các số "%" là xấp xỉ do bộ đọc theo dòng. "Đối tượng trong khối" gồm khối ẩn danh (kích thước, hatch, khối động). Chiều cao chữ trải rộng ở cả 5 tệp (nhiều nhóm từ ≤ 25 đến > 250 đơn vị bản vẽ), tức không có một cỡ chữ chuẩn trong không gian mô hình.

## 4. Phát hiện và đánh giá

### 4.1 Mẫu thuộc khâu đầu của chuỗi, chưa phải khâu cuối
Kế hoạch `plans/cad-guard.md` viết cho bản vẽ đưa xuống **sản xuất** (cắt, dán cạnh, bảng kê, khung tên). Công ty có ba phòng nối tiếp, mỗi phòng cần một loại kiểm khác:

| Khâu | Phòng | Bản vẽ điển hình | Kiểm gì | Mẫu hiện có |
| --- | --- | --- | --- | --- |
| 1 | Thiết kế | Phương án, triển khai không gian | Nhất quán layer/chữ/kích thước, bản vẽ sạch và nhẹ, đủ thông tin để chuyển tiếp | Có (5 tệp) |
| 2 | Kỹ thuật | Triển khai chi tiết, bản vẽ thi công, bóc tách | Đủ và đúng kích thước, khớp giữa hình và bảng, vật liệu, phụ kiện, ghi chú | Có thể một phần (chưa xác định tệp nào thuộc khâu này) |
| 3 | Lập trình sản xuất | Dữ liệu cho CNC/cắt: tấm, đường bao, khoan, dán cạnh | Đường bao khép kín, layer gia công đúng, đơn vị, gốc toạ độ, không trùng/không đứt | Chưa có |

Hệ quả: (1) đây không phải lựa chọn "thiết kế hay xưởng": cùng một công ty cần các gói luật nối tiếp, và **đầu ra tốt của khâu trước là đầu vào của khâu sau** (một bản triển khai bẩn sinh ra lỗi ở khâu lập trình); (2) bắt đầu từ **vệ sinh và nhất quán** (đo được và đúng với mẫu hiện có), rồi mở dần sang khâu 2 và 3 khi có mẫu; (3) cần mẫu của khâu 2 và 3 trước khi chọn luật cho hai khâu này.

### 4.2 Bộ đọc hiện tại bỏ sót phần lớn nội dung
Ở 4/5 tệp, số đối tượng trong định nghĩa khối gấp 9–23 lần không gian mô hình. Hệ quả: (1) các luật về layer/đối tượng phải quét cả khối (khối lồng, khối ẩn danh); (2) công cụ `query_model` của trợ lý phải trả **tóm tắt và truy vấn theo vùng/layer**, không bao giờ dựng toàn bộ vào ngữ cảnh mô hình ngôn ngữ (một tệp có > 400.000 đối tượng trong khối).

### 4.3 Hiệu năng và kích thước
Mục tiêu "< 2 phút/bản" (`plans/cad-guard.md` mục 2) là đạt được **nếu** đọc theo dòng và luật chạy một lượt. Rất khó đạt nếu nạp trọn tệp bằng ezdxf trên máy 8 GB với tệp 262–445 MB (ước tính, chưa đo). Đường chuyển DWG→DXF tốn thêm 16–111 giây và là điểm tiềm ẩn mất thông tin (4.8). Cần đường đọc luật theo dòng, hoặc đọc theo phần (bảng, khối, thực thể) với bộ nhớ có trần.

### 4.4 Quy ước đặt layer
57–131 layer mỗi tệp; 6–41 layer là phần dư của xref đã gộp (tên có `$`); 0% theo `FN-*`. Chuẩn v0 chạy trên dữ liệu này sẽ báo gần như mọi layer (trên M2: 55/57 theo LY-01) — **nhiễu 100%, người dùng sẽ tắt ngay**. Hai lối ra:
1. **Chuẩn cấu hình theo công ty** (đã định hướng "lõi + cấu hình công ty" ở `plans/cad-guard.md` mục 9): mẫu tên layer là tham số, không phải hằng.
2. **Chế độ học quy ước**: đọc cả bộ, suy ra nhóm tên layer/kiểu chữ/kiểu kích thước phổ biến, đề xuất làm chuẩn; sau đó kiểm độ lệch. Đây là tính năng đáng giá cho khách chưa có chuẩn viết ra.

### 4.5 Tiếng Việt và phông
54–74% chữ có ký tự ngoài ASCII. Phông gồm các phông tiếng Việt cũ (`v*`, `vn*`, kiểu VNI/TCVN) lẫn phông Unicode (Arial…). Với phông cũ, "ký tự ngoài ASCII" có thể là mã nhồi chứ không phải Unicode chuẩn: nếu LLM hoặc trình xem đọc thẳng, sẽ ra chữ hỏng. Hệ quả: (1) luật mới "dùng phông Unicode cho tiếng Việt"; (2) bộ chuyển mã văn bản có kiểm thử trước khi đưa chữ cho trợ lý; (3) trình xem phải có phông thay thế hợp lý.

### 4.6 Vệ sinh bản vẽ (dễ làm, có giá trị, ít báo sai)
Các thứ đo được và thường là vấn đề thật ở bản giao:
- layer rác từ xref đã gộp (6–41 layer);
- 23–52 kiểu chữ và 8–26 kiểu kích thước (phình to);
- đối tượng trên layer "0" (3–23%);
- màu/độ dày nét ghi đè thay vì ByLayer (màu 3–77%, độ dày nét 0–40%);
- WIPEOUT hàng nghìn, IMAGE/OLE nhúng (17–38);
- LINE có Z khác 0 (M2: 98% số LINE).
Nên làm thành luật vệ sinh có **ngưỡng cấu hình**, và là ứng viên đầu cho tính năng "dọn bản vẽ" có xem trước.

### 4.7 Lỗi có tác động thật
Chữ kích thước bị ghi đè tay (0,5–5,9% số kích thước, tức vài chục đến hơn một trăm kích thước mỗi bản) là loại lỗi nguy hiểm vì số hiển thị có thể khác số đo thật. `TX-09` (giá trị kích thước = số đo hình học) vì vậy là luật đáng ưu tiên đo độ chính xác. Chưa kiểm được giá trị ghi đè đúng hay sai (cần so với hình học; chưa làm).

### 4.8 Độ trung thực của đường DWG→DXF
Số cảnh báo/lỗi của trình chuyển rất lớn và có khối "ACDB_BLOCKREPRESENTATION_DATA" (khối động). Không dùng số liệu này để kết luận về lỗi của bản vẽ: có thể do chuyển đổi. Quy tắc: **mọi luật chạy trên DXF chuyển đổi phải được đối chiếu với DXF xuất từ phần mềm gốc ở ít nhất vài tệp** trước khi tin (đúng như P0/P1c đã nêu).

## 5. Chuẩn v0 trên dữ liệu thật (M2, 15 luật chạy)

| Luật | Số phát hiện | Nhận xét |
| --- | --- | --- |
| LY-01 | 55 | Mẫu tên layer không khớp chuẩn v0: nhiễu, cần tham số theo công ty |
| LY-09 | 17 | Layer rỗng: có thật, mức thông tin |
| TX-01 | 5 | Kiểu chữ ngoài tập cho phép: phụ thuộc chuẩn công ty |
| LY-03, LY-04, TX-08, DH-01, DH-02, DH-10 | 1 mỗi luật | Cần xem từng ca; DH-10 (Z khác 0) khớp với số liệu mục 3 |
| PR-02 | bỏ qua | Bảng kê không có: đúng với loại bản vẽ này |

Kết luận: với loại bản vẽ này, **v0 không có luật nào đủ phù hợp để bật nguyên trạng**. Bộ luật vẫn đúng hướng cho khâu cuối (bản vẽ đưa xuống sản xuất); cho khâu thiết kế/kỹ thuật cần "chuẩn triển khai" riêng, bắt đầu từ mục 4.6.

## 6. Hệ quả cho kế hoạch và việc làm tiếp

1. **Mẫu còn thiếu (CEO/phòng kỹ thuật):** bản vẽ của khâu kỹ thuật chi tiết và của phòng lập trình sản xuất (kèm tệp DXF/CNC họ giao cho máy), để chọn luật cho khâu 2 và 3 (4.1).
2. **Lõi:** đọc theo dòng cho `audit` (không chỉ `profile`); duyệt cả khối; chuẩn cấu hình theo công ty; chế độ học quy ước (4.4).
3. **Luật mới** (cần mã trong `standards/` và phiên bản chuẩn mới `furniture-v0.1`, theo quy trình AGENTS.md): vệ sinh layer xref, phình kiểu chữ/kích thước, đối tượng trên layer 0, ghi đè ByLayer, phông tiếng Việt Unicode, kích thước ghi đè chữ, WIPEOUT/OLE.
4. **Trợ lý (A0):** `query_model` trả tóm tắt theo vùng/layer; công cụ "khảo sát bản vẽ" (đếm, thống kê, tìm) vì phòng thiết kế/kỹ thuật làm việc với bản vẽ rất lớn và cần hỏi đáp nhanh trên chúng.
5. **P0 còn thiếu:** DXF xuất từ phần mềm gốc (đối chiếu), danh sách sự cố thật, bản vẽ xưởng, nhãn tốt/xấu để đo độ chính xác.
6. **Pháp lý:** LibreDWG chỉ là công cụ phân tích một lần. Đường đọc DWG cho sản phẩm vẫn là "khách xuất DXF từ phần mềm của họ" (`plans/cad-guard-direction.md`).
