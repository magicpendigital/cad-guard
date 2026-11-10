# cad-guard — Phản hồi chạy thử 10/11/2026 và kế hoạch hai luồng song song

Trạng thái: **đang triển khai** (10/11/2026). Luồng 1 tiếp tục kế hoạch Đợt A–F (`plans/cad-guard-sheets-presentation.md`);
Luồng 2 đánh giá và làm thử dựng 3D từ bản vẽ kỹ thuật 2D, kèm đánh giá công thái học. Hai luồng chạy song song, mỗi
luồng một worktree riêng tách từ `main`.
Quy tắc dữ liệu: tài liệu này chỉ ghi con số cấu trúc của tệp thật, không tên khách, không nội dung chữ.

## 1. Bảy vấn đề người dùng gặp và cách đã xử lý

| # | Vấn đề | Nguyên nhân | Đã làm |
| --- | --- | --- | --- |
| 1 | Không thấy tab Cài đặt | Trình duyệt đang mở **phiên cũ**: plugin CGBANG (build 09/11) tự chạy `cadguard app` bằng môi trường `AppData\Local\cad-guard\venv` trỏ vào mã của nhánh cũ; trên máy còn 4 phiên như vậy | Gộp mọi thứ vào `main`; `cadguard open` không dùng lại phiên chạy từ mã khác; mở phiên mới từ `main` |
| 2 | `CADGUARD` báo unknown | Chưa gắn CAD Guard vào AutoCAD (nút Cài nằm ở tab không thấy) | Bước "Gắn CAD Guard vào AutoCAD" ở tab Cài đặt: chép LISP + `cadguard-run.cmd`, thêm khối tự nạp vào `acaddoc.lsp` của người dùng. Người dùng bấm (thao tác ghi cấu hình AutoCAD để người dùng tự xác nhận) |
| 3 | `CGBANG` không chạy | Plugin .NET chưa được AutoCAD tự nạp (phải NETLOAD tay) và cấu hình trỏ vào mã cũ | Cùng bước trên: build plugin vào thư mục cài, ghi `cadguard-acad.json` trỏ đúng Python/mã, đăng ký nạp khi AutoCAD khởi động (khoá Applications của người dùng) |
| 4 | Giải thích lỗi chưa đủ hiểu | Chỉ có mô tả luật soạn sẵn | Nút **Giải thích sâu (AI)** trên thẻ lỗi và **Giải thích chuyên sâu bằng AI** trong chi tiết luật: gửi trợ lý câu hỏi có cấu trúc (tầm quan trọng, hậu quả, mức độ thực tế trên bản vẽ qua công cụ audit/query_model, cách sửa, khi nào bỏ qua được) |
| 5 | Trợ lý chỉ chọn được CLI mặc định | Codex CLI đã đăng nhập nhưng bị khoá sau cờ "thử nghiệm" | Menu trợ lý: CLI thử nghiệm đã cài/đăng nhập thì bấm là bật và chọn |
| 6 | Đóng thảo luận rồi không mở lại được | Nút mở lại chỉ là chữ "Thảo luận" nhỏ | Nhãn rõ "Ẩn/Hiện thảo luận", nút **◀ Thảo luận** ở mép phải khi đã đóng, nhớ trạng thái |
| 7 | Không thấy phần dịch | Như (1), và nút Dịch nằm khuất trong thanh Tờ | Thanh công cụ bản vẽ có **Chuyển Unicode**, chọn ngôn ngữ + **Dịch**, **Học template**; xem trước mở thẳng tab Thay đổi |

Còn chờ người dùng: bấm Cài ở "Gắn CAD Guard vào AutoCAD" và "Lối tắt", mở lại AutoCAD, bấm *Always load* lần đầu; đóng các
phiên CAD Guard cũ (hoặc khởi động lại máy).

## 2. Rà soát tính năng "AI đánh giá công thái học"

**Kết luận: tính năng không bị xoá khỏi CAD Guard, vì nó chưa từng ở trong CAD Guard.** Nó nằm trong bản nháp Draff
(ứng dụng Node/TypeScript ở `Draff/`, ngoài repo): `Draff/src/scene3d.ts` hàm `analyzeErgonomics` và bảng
"Đánh giá Công thái học AI" ở `Draff/public/app.js`. Bản rà soát 07/11 (`docs/reviews/2026-11-07-draff/report.md` mục
3 và 5) đã **hoãn** phần này vì:

- ngưỡng viết cứng, gắn nhãn "chuẩn VN" không có nguồn;
- nhiều giá trị **bịa**: thiếu dữ liệu thì tự điền "820 mm (mô phỏng)", khoảng hở tủ trên luôn báo "630 mm" bất kể bản
  vẽ, điểm khởi đầu 96/100; nhánh không có nhận định vẫn gắn "pass";
- cấu kiện tủ tự sinh từ khối bao (vách 18 mm) rồi đánh giá trên chính dữ liệu suy ra đó.

Người dùng thấy nội dung hợp lý vì văn bản được soạn sẵn, không phải vì bản vẽ được đo. Đưa nguyên vào sẽ vi phạm nguyên
tắc "phát hiện bằng code tất định; LLM không bịa số".

### 2.1 Thiết kế lại (làm trong Luồng 2, sau khi có cảnh 3D đo được)

| Tầng | Nội dung | Ai làm |
| --- | --- | --- |
| Dữ liệu tham chiếu | `standards/ergonomics-v0.yaml`: mỗi tiêu chí có mã (ER-xx), đại lượng, khoảng khuyến nghị, **nguồn** (tài liệu công ty duyệt, tiêu chuẩn có số hiệu, sách tham khảo) và đối tượng áp dụng. Không có nguồn thì không đưa vào | Chủ dự án/trưởng phòng thiết kế duyệt bảng; agent soạn bản nháp có trích nguồn |
| Đo tất định | Từ cảnh `cg.scene/1` đã chuẩn hoá: cao mặt bàn, khoảng hở tủ trên–mặt bàn, sâu tủ, khoảng lối đi, vùng quét cánh/ngăn kéo va chạm, tầm với kệ cao nhất, khoảng cách thiết bị (bếp–chậu–tủ lạnh). Mỗi số đo kèm handle nguồn và `source` (bản vẽ / người nhập / mặc định) | Code (luật ER-xx, như luật TP/VS) |
| Nhận xét AI | LLM nhận kết quả đo + ngữ cảnh (loại phòng, người dùng) và viết nhận xét: tác động tới người dùng, đề xuất sửa, câu hỏi cần làm rõ. Đầu ra **có cấu trúc** (JSON schema dưới), gắn nhãn "AI nhận xét" | Trợ lý |
| Kiểm nhận xét | Mỗi mục AI phải trỏ tới ít nhất một số đo có thật (mã đo + handle); mục không có bằng chứng bị loại; số trong lời văn phải khớp số đo | Code (harness) |

Schema đầu ra đề xuất `cg.ergonomics-review/1`:
`{items: [{criterion: "ER-03", measure_ids: ["m12"], refs: ["<handle>"], finding: "...", impact: "...", suggestion: "...",
severity: "info|warn|error", confidence: "low|medium|high"}], questions: ["..."], summary: "..."}`.

Năng lực agent cần:
- **Công cụ** (thêm vào `agent/registry.py`, một sổ cho MCP và engine API): `get_scene` (cảnh đã dựng, chỉ số liệu), `measure`
  (đo khoảng cách/khe hở giữa hai phần tử theo mã), `list_ergonomic_checks` (kết quả ER-xx), cùng `audit`, `query_model`.
- **Đầu ra có cấu trúc**: dùng JSON schema ở engine API (Anthropic/OpenAI hỗ trợ), với CLI thì yêu cầu JSON và kiểm lại.
- **Tác tử con**: (1) *đo đạc*: chỉ gọi công cụ, không viết nhận xét; (2) *đánh giá*: viết nhận xét từ số đo; (3) *phản biện*:
  kiểm từng mục có bằng chứng, số khớp, không vượt phạm vi tiêu chí. Có thể chạy trong một lượt chat bằng ba bước prompt nếu engine
  không hỗ trợ tác tử con.
- **Harness**: bước kiểm tất định sau cùng (mục 2.1 dòng 4), nhật ký đánh giá theo băm bản vẽ, bộ đánh giá bằng fixture có
  đáp án (cao mặt bàn 700/820/950 mm, cánh va tường…) để đo tỉ lệ nhận xét sai.

## 3. Đánh giá năng lực dựng 3D từ bản vẽ 2D

### 3.1 Hiện trạng đo trên tệp phiên thử (10/11/2026)

| Chỉ số | Giá trị |
| --- | --- |
| Bộ dựng `cg.scene/1` hiện có | **0 tường, 0 mô-đun, 0 tấm**: chỉ hiểu quy ước tổng hợp (layer `FN-ROOM-WALL`, khối `FN_MOD*` có W/D/H), bản vẽ công ty không dùng |
| Tờ theo tiêu đề | 9 mặt bằng, 14 mặt đứng/chi tiết, 17 tờ khác (trên 40) |
| Kích thước (DIMENSION) | 2.582, tất cả có số đo |
| Khối ký hiệu trục/mặt cắt có số (liên kết mặt bằng ↔ mặt đứng) | 77 |
| Khối chèn | 115 loại, 689 lần chèn |
| Layer tường | 1 |
| HATCH (vật liệu/vùng) | 237 |

### 3.2 Nhận định

- **Chưa đủ năng lực dựng phối cảnh không gian ngay**: bộ dựng hiện tại là khung tất định cho dữ liệu đã chuẩn hoá theo
  quy ước, chưa đọc được cách công ty vẽ.
- **Đủ nền móng để làm thử có kiểm chứng**: chỉ mục tờ (40 tờ, phân được mặt bằng / mặt đứng), chữ đã giải mã Unicode,
  kích thước có số đo thật, ký hiệu trục/mặt cắt nối mặt bằng với mặt đứng, template khung tên (tên tờ, tỉ lệ).
- Mục tiêu khả thi gần: **một phòng** (vd. phòng khách tầng 7) dựng được tường + trần + sàn + các khối tủ/kệ với kích thước
  lấy từ mặt bằng (dài, sâu, vị trí) và mặt đứng (cao, chia cánh/ngăn), xuất GLB và ảnh phối cảnh. Vật liệu, ánh sáng là
  phần diễn hoạ (Blender hoặc trình xem GLB), không phải dữ liệu sản xuất.
- Rủi ro chính: ghép mặt bằng ↔ mặt đứng (tờ, ký hiệu, tỉ lệ khác nhau), nét vẽ rời không thành khối, chữ ghi đè kích
  thước, phần không thể hiện trên bản vẽ (cao trần, cao tủ trên ở tờ khác). Phần thiếu phải thành `gaps[]` cho người
  nhập, không đoán.
- LLM có ích ở khâu **ghép và gán nhãn** (tờ nào là mặt đứng của cụm nào, cụm nào là tủ gì), luôn qua bước người xác nhận;
  kích thước luôn lấy từ hình học/kích thước tất định.

### 3.3 Lộ trình Luồng 2

| Bước | Nội dung | Tiêu chí nghiệm thu |
| --- | --- | --- |
| 3D-0 Đánh giá | Đo trên tệp phiên thử: tờ mặt bằng/mặt đứng nào nhận được, bao nhiêu cụm đồ nội thất, bao nhiêu cụm có đủ 2 hình chiếu, tỉ lệ kích thước gán được | Báo cáo số liệu `docs/3d-feasibility.md`; quyết định đi tiếp hay dừng có căn cứ |
| 3D-1 Đọc mặt bằng | Tường từ layer học được (như học layer LY-01), phòng (vùng kín), cụm đồ (khối/nét kín) với kích thước từ DIMENSION gần nhất | Fixture tổng hợp kiểu công ty: tường/phòng/cụm đúng 100 %; tệp thử: số tường/cụm khớp người dùng đếm trên 1 tờ |
| 3D-2 Ghép mặt đứng | Liên kết mặt bằng ↔ mặt đứng qua ký hiệu trục/mặt cắt và tiêu đề tờ; cao, chia cánh/ngăn từ mặt đứng; LLM đề xuất ghép, người xác nhận trên giao diện | Fixture: ghép đúng 100 %; tệp thử: ≥ 1 phòng dựng đủ khối với cao lấy từ bản vẽ, phần thiếu thành `gaps[]` |
| 3D-3 Dựng và xem | Cảnh `cg.scene/2` (tường, trần, sàn, mô-đun, cánh), GLB, xem trong App, ảnh phối cảnh (Blender qua MCP nếu có) | Mở được GLB; mọi kích thước có nguồn (bản vẽ / người nhập); xem trước = xuất (cùng băm cảnh) |
| 3D-4 Công thái học | `ergonomics-v0.yaml` có nguồn, luật ER-xx tất định trên cảnh, nhận xét AI có cấu trúc + harness phản biện (mục 2.1) | Fixture có đáp án: 0 nhận xét không bằng chứng; độ phủ tiêu chí đã duyệt |

## 4. Luồng 1: phần còn lại của Đợt A–F

| Việc | Tiêu chí |
| --- | --- |
| Kiểm tay trên AutoCAD 2027: CADGUARD, CGBANG, CGUNICODE, CGDICH, CGTRINHBAY (`docs/autocad.md` mục 8) | 5 bước kiểm tay đạt; ghi kết quả vào `docs/autocad.md` mục 5 |
| Thao tác `replace_title_block`, `set_sheet_scale`, `fit_sheet` (kế hoạch mục 4.4) | Sau áp dụng 0 lỗi TP sửa được; 0 đối tượng hình vẽ/kích thước/chú thích đổi; hoàn tác trả đúng tệp gốc |
| Dịch chế độ `layer` (giữ chữ gốc, thêm chữ dịch trên layer riêng) | Bật/tắt layer xem được hai ngôn ngữ; kiểm tệp ra đạt |
| In PDF hàng loạt theo tờ (accoreconsole) | Đủ số tờ, đúng tên theo template |
| TP-11, gộp Studio vào App | Như kế hoạch gốc |
| Chạy dịch với LLM thật trên tệp thử, đo chất lượng | Tỉ lệ chuỗi có bản dịch, số lỗi giữ chỗ/thuật ngữ, thời gian, chi phí |

Trạng thái 10/11/2026 (nhánh Luồng 1, chưa gộp `main`): đã làm `replace_title_block`/`set_sheet_scale`/`fit_sheet`
(nghiệm thu trên fixture đạt), dịch `layer`, in PDF theo tờ (tệp thử 40/40 tờ), TP-11, đo dịch LLM thật (số ở
`docs/sheets-presentation.md` mục E). Còn: kiểm tay trên AutoCAD có giao diện (`docs/autocad.md` mục 8.1), gộp Studio
vào App.

## 5. Phối hợp hai luồng

- Mỗi luồng một worktree, nhánh riêng tách từ `main`; không push. Gộp vào `main` khi người dùng duyệt.
- Vùng mã chồng nhau dự kiến: `cli.py`, `app/static/*`, `agent/registry.py`. Luồng 2 thêm mã chủ yếu ở `scene/`,
  `standards/ergonomics-v0.yaml`, `rules/ergonomics.py`; Luồng 1 ở `changeset/`, `template.py`, `translate.py`, `autocad/`.
- Bản vẽ thật chỉ đọc ở thư mục ngoài repo (`D:\CadGuardPhien\…`); tài liệu chỉ ghi số cấu trúc.
