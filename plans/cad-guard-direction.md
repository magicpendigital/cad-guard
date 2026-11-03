# cad-guard — Hướng đi: gắn AutoCAD, fork CAD mã nguồn mở, tự xây phần mềm, hay làm theo tệp?

Trạng thái: **CEO ĐÃ DUYỆT hướng C (03/11/2026)**. Nếu hướng theo tệp không giải quyết được bài toán, tiếp tục theo hướng plugin AutoCAD (hướng D, phương án dự phòng đã được CEO đồng ý). Repo: `D:\Projects\cad-guard` (CEO đã tạo thư mục). Bổ sung cho `plans/cad-guard.md` (mục 4 Kiến trúc, mục 8 Lộ trình, mục 10 Decision log). Chưa viết code.
Bối cảnh mới từ CEO (03/11): (1) sẽ dùng AutoCAD bản dùng thử và lấy bản vẽ từ phòng kỹ thuật về chạy rà soát trước; (2) phòng kỹ thuật có thể dùng nhiều phần mềm CAD khác nhau theo bộ phận/vị trí; (3) vì bản quyền, phòng kỹ thuật đang chuyển khỏi AutoCAD; (4) nhu cầu có thể chỉ là một số tính năng đơn giản, cơ bản.

## 1. Kết luận ngắn

**Không fork một CAD mã nguồn mở và không xây một phần mềm CAD. Xây phần "kiểm và rà soát theo tệp", lấy DXF làm định dạng chung, không phụ thuộc phần mềm CAD nào.** Phần mềm gồm: lõi kiểm luật (đã thiết kế ở Tầng 0), một **trình xem và rà soát nhẹ** (mở DXF, đánh dấu lỗi chồng lên bản vẽ, xuất báo cáo và bản vẽ đã chuẩn hoá thành tệp *mới*), và các **adapter mỏng theo từng phần mềm CAD** chỉ làm khi đã biết công ty chốt phần mềm nào. Tầng "thời gian thực trong phần mềm CAD" lùi thành tuỳ chọn, không còn là điểm tựa của sản phẩm.

Lý do chính: giá trị của sản phẩm nằm ở **chuẩn trình bày, bộ luật và dữ liệu vận hành**, không ở việc soạn thảo bản vẽ; thợ vẽ sẽ không đổi công cụ vẽ chỉ để nhận cảnh báo; còn khó nhất của một phần mềm CAD (đọc/ghi DWG chính xác, ổn định) lại là thứ mã nguồn mở chưa làm tốt.

## 2. Dữ kiện đã kiểm (02–03/11/2026)

| Điều | Kết quả | Nguồn |
| --- | --- | --- |
| LibreDWG | Giấy phép **GPLv3+**; đọc DWG r1.2–r2018 (khoảng 99% đặc tả); **ghi mặc định chỉ r2000 trở xuống**, ghi r2004+ còn đang làm và phải vá mã; DXF ASCII do nó sinh ra có tệp AutoCAD nhập lỗi; thiếu PROXY entity | [GNU LibreDWG manual](https://www.gnu.org/software/libredwg/manual/html_node/Overview.html) |
| ezdxf | **MIT**; lõi chỉ xử lý **DXF** (ASCII và nhị phân); DWG chỉ qua add-on `odafc` (giao diện tới ODA File Converter) | [README ezdxf](https://github.com/mozman/ezdxf) |
| ODA File Converter | Chỉ miễn phí cho mục đích phi thương mại nếu không là thành viên ODA, không được phân phối lại (đã kiểm ngày 02/11) | trang FAQ ODA |
| ZWCAD | Có LISP, VBA, ZRX, .NET; nói tương thích DWG; mua vĩnh viễn từ 21,6 triệu đồng (số của chính hãng, **có thể thiên vị**) | [ZWSoft](https://www.zwsoft.com/vn/blog/best-autocad-alternatives) |
| BricsCAD, DraftSight, nanoCAD, QCAD, LibreCAD | Cùng bài trên có bảng giá/nền tảng nhưng **không nêu rõ API** (nanoCAD có "API mở", QCAD có API plugin); LibreCAD đọc DWG/DXF | [ZWSoft](https://www.zwsoft.com/vn/blog/best-autocad-alternatives) |
| Chưa kiểm được | FreeCAD nhập DWG thế nào (trang wiki bị chặn khi truy cập); giấy phép chính xác của LibreCAD/QCAD/FreeCAD; API của GstarCAD/BricsCAD | — |

Đánh giá ("theo tôi", không phải dữ kiện): DXF là định dạng có đặc tả công bố và mọi phần mềm CAD kể trên đều xuất được; DWG thì độc quyền nên mọi đường đọc/ghi DWG ngoài phần mềm gốc đều có đánh đổi về giấy phép hoặc độ tin cậy.

## 3. Bốn hướng, so sánh

| Hướng | Nội dung | Công sức | Rủi ro chính | Hợp với bối cảnh |
| --- | --- | --- | --- | --- |
| A. Fork CAD mã nguồn mở (LibreCAD/QCAD/FreeCAD…) rồi thêm tính năng | Nhận một trình soạn 2D có sẵn, gắn bộ luật vào | Lớn (C++/Qt, bảo trì giao diện CAD) | Ép thợ vẽ đổi công cụ; giấy phép copyleft ràng buộc cách bán; DWG ghi chưa tốt; ta thành người bảo trì một phần mềm CAD | **Thấp** |
| B. Tự xây phần mềm CAD tập trung | Trình soạn riêng cho vài việc cơ bản | Rất lớn | Như A và còn phải làm từ đầu | **Rất thấp** trừ khi nhu cầu thật sự là "vẽ đơn giản" |
| **C. Hướng tệp (đề xuất)** | Lõi luật + trình xem/rà soát + xuất tệp mới; DXF là chung | Vừa, tăng dần | DXF mất một số thứ so với DWG; cảnh báo chỉ "khi lưu/khi quét" | **Cao**: chạy với mọi phần mềm CAD, không bắt ai đổi công cụ |
| D. Plugin theo từng CAD | Cảnh báo ngay khi vẽ trong phần mềm | Mỗi CAD một lần | Nhân số phần mềm × số bản; sập tiến trình CAD | Chỉ sau khi công ty chốt phần mềm chuẩn |

Vì sao C hợp với "nhu cầu chỉ một số tính năng đơn giản": các tính năng đã bàn (kiểm layer/chữ/kích thước/khung tên, báo cáo, ghi chú bàn giao, chuẩn hoá có xem trước) đều là **đọc một tệp, kiểm, ghi báo cáo hoặc một tệp mới** — không cần là một CAD.

Vì sao không phải A/B ngay: (1) phòng kỹ thuật vừa phải đổi phần mềm vì bản quyền, ta đừng thêm một phần mềm vẽ nữa; (2) phần khó và tốn nhất của CAD (nhập/xuất DWG, đối tượng chú thích, khối động, in ấn) là phần không đem lại lợi thế cho ta; (3) ta cần thời gian để biết nhu cầu thật; (4) giấy phép copyleft của nhiều CAD/thư viện DWG mã nguồn mở cần luật sư xem trước khi nhúng vào sản phẩm bán.

Khi nào quay lại cân nhắc A/B: nếu P1c cho thấy thợ vẽ thật sự **muốn cảnh báo ngay lúc vẽ** ở ≥ 2 phần mềm khác nhau mà không có adapter nào khả thi; hoặc phòng kỹ thuật chốt dùng một CAD mã nguồn mở và cần thêm tính năng trong chính nó (khi đó là *plugin/extension* của CAD đó, vẫn không phải fork).

## 4. Điều chỉnh kiến trúc (thay mục 4 của `plans/cad-guard.md`)

```text
Tầng 3  Nối MCA (tuỳ chọn)
Tầng 2  Trợ lý LLM (giải thích, đề xuất, lệnh tự nhiên → thao tác có cấu trúc)
Tầng 1b Trình xem và rà soát (mới)  mở DXF · lỗi chồng lên bản vẽ · báo cáo · xuất tệp chuẩn hoá MỚI
Tầng 1a Đường vào theo từng phần mềm CAD (adapter mỏng)  xuất DXF · thư mục theo dõi · (sau) bảng điều khiển trong CAD
Tầng 0  Lõi (Python + ezdxf)  Drawing Model · bộ luật · CLI — tất định, cục bộ
```

- **DXF là hợp đồng giữa các tầng.** Lõi không biết phần mềm nào đã tạo bản vẽ; chỉ ghi nhận `$ACADVER` và ứng dụng sinh tệp để đo ảnh hưởng.
- **Tầng 1a, đường vào theo thứ tự ưu tiên:** (1) *người dùng/tập lệnh của chính phần mềm CAD xuất DXF* vào thư mục theo dõi — không cần giấy phép đọc DWG của bên thứ ba; (2) lệnh/mẫu xuất hàng loạt bằng lõi dòng lệnh của phần mềm đó nếu có; (3) chỉ khi cần: bộ chuyển DWG→DXF có giấy phép phù hợp (ODA đang bị loại vì phi thương mại; LibreDWG vướng GPLv3 và độ tin cậy). Mẫu số chung thử trước: một đoạn **LISP** nhỏ ("khi lưu thì ghi thêm bản DXF"), vì ZWCAD hỗ trợ LISP (đã thấy trong nguồn) và nhiều CAD khác theo tôi biết cũng chạy LISP — **phải kiểm từng phần mềm, chưa xác nhận**.
- **Tầng 1b, trình xem/rà soát:** ứng dụng web chạy cục bộ hoặc ứng dụng máy tính đơn giản: mở DXF, danh sách lỗi theo mức độ, bấm vào lỗi thì phóng tới đối tượng, ghi chú, "báo sai", xuất PDF/báo cáo, và **xuất tệp DXF chuẩn hoá mới** (P2). Việc dựng hình lấy từ thư viện kết xuất DXF mở sẵn có (cần chọn và kiểm giấy phép ở P1; chưa chọn).
- **Mất gì so với DWG:** đối tượng/khối động, đối tượng proxy và một số đối tượng chú thích có thể mất hoặc đổi khi qua DXF. Ta **đo** thay vì đoán: P0/P1c so sánh kết quả luật trên cùng bản vẽ ở hai đường (DXF xuất từ phần mềm gốc và DXF chuyển từ DWG).
- **Cảnh báo "ngay khi vẽ"**: lùi thành (a) "khi lưu" cho mọi phần mềm qua thư mục theo dõi, (b) bảng điều khiển trong CAD chỉ khi công ty chốt một phần mềm có API đủ tốt.

## 5. P0 điều chỉnh (thay mục "P0" của `plans/cad-guard.md`)

Bạn đã tự đề xuất đúng hướng: lấy bản vẽ về rà soát trước. Sửa P0 thành:

1. **Kiểm kê phần mềm** (1 buổi với phòng kỹ thuật): bảng *bộ phận × vị trí × phần mềm × định dạng đầu ra × người nhận tiếp theo* (xưởng/CNC/mua hàng/diễn họa); phần mềm đang dùng, phần mềm sẽ chuyển sang và thời hạn; có phần mềm chuyên cho đồ gỗ nào không (ghi tên theo lời họ, ta chưa biết); ai đang xuất DXF cho máy CNC.
2. **Thu mẫu:** 30–50 bản đại diện, **lấy cả tệp gốc và DXF nếu họ có**, kèm tên phần mềm/bản đã tạo ra; ẩn danh theo thoả thuận dữ liệu (xem `plans/cad-guard.md` mục 5); lưu ngoài repo.
3. **Dùng AutoCAD dùng thử đúng việc:** (a) mở thử toàn bộ mẫu DWG xem bản nào lỗi/thiếu font; (b) tạo DXF đối chiếu làm "đáp án" cho phép so sánh đường chuyển đổi; (c) đây không phải môi trường đích. Chuẩn bị bộ tệp **trước khi bật** bản dùng thử vì thời hạn có hạn (thường 30 ngày, **kiểm điều khoản bản dùng thử** — gồm việc cho phép dùng với dữ liệu của khách).
4. **Chạy rà soát lõi** (P1a, bắt đầu song song bằng dữ liệu tổng hợp) trên mẫu; bảng so sánh kết quả hai đường DXF; người kỹ thuật rà tay cùng bộ để có độ chính xác thật (P1c).
5. **Ghi vào `docs/discovery.md`** và đưa lại CEO để chốt: phần mềm chuẩn nào (nếu có), tính năng nào thật sự cần.

Câu hỏi để CEO mang tới buổi kiểm kê: phần mềm nào sẽ thay AutoCAD và khi nào; mỗi bộ phận dùng gì; CNC nhận định dạng gì; khâu nào hiện đang bị sai nhiều nhất (đây quyết định luật làm trước).

## 6. Khuyến nghị về phía công ty (chỉ gợi ý, không ép)

Thống nhất **một** phần mềm CAD chuẩn cho phòng kỹ thuật (và một mẫu file/khung tên) làm giảm nhiều lỗi hơn mọi công cụ kiểm. Đó là quyết định kinh doanh của họ; cad-guard chạy được dù họ chọn gì, nhưng adapter "trong phần mềm" chỉ làm được cho phần mềm họ chốt.

## 7. Quyết định cần CEO

| # | Câu hỏi | Đề xuất |
| --- | --- | --- |
| 1 | Chọn hướng C (theo tệp, DXF chung) làm nền; A/B chỉ xét lại ở cổng P1c | **ĐÃ DUYỆT 03/11**; hướng plugin AutoCAD (D) là dự phòng nếu C không đủ |
| 2 | Bản dùng thử AutoCAD dùng theo mục 5.3, không coi là môi trường đích; kiểm điều khoản dùng thử trước khi nạp dữ liệu khách | CEO sẽ đăng ký bản dùng thử và lấy bản vẽ về từ phòng kỹ thuật (03/11) |
| 3 | Thêm Tầng 1b (trình xem/rà soát) vào P1 (sau khi lõi chạy), thay "plugin AutoCAD C#" vốn là P1b | **ĐÃ DUYỆT** (gộp vào quyết định 1); P1b đổi thành "adapter xuất DXF + thư mục theo dõi"; plugin AutoCAD C# chuyển thành bước dự phòng có cổng |
| 4 | Sau P0, nếu công ty chốt một phần mềm CAD chuẩn thì làm adapter bảng điều khiển cho đúng phần mềm đó (P3) | Chờ kết quả P0 |

## 8. Not yet specified

- Thư viện dựng hình DXF cho trình xem (và giấy phép của nó); web hay máy tính để bàn: quyết ở đầu P1b.
- Mức mất thông tin khi DWG→DXF với bản vẽ của họ: đo ở P0/P1c.
- Điều khoản AutoCAD dùng thử với dữ liệu của khách.
- Phần mềm chuyên cho đồ gỗ mà phòng kỹ thuật/xưởng đang dùng và định dạng bàn giao với CNC.
- API thực tế của GstarCAD/BricsCAD/DraftSight/nanoCAD cho adapter (bài đã đọc không nêu rõ).
