# Kế hoạch: lỗi có lối ra, đồ thị tri thức bản vẽ, 3D phục vụ sản xuất (11/11/2026)

Nguồn: phản hồi chạy thử 11/11 trên bản vẽ phiên 01 (40 tờ, 15.183 đối tượng). Nghiên cứu ngành:
`docs/research/3d-san-xuat-noi-that.md` (có nguồn và nhãn độ tin cậy cho từng số).

## 1. Chẩn đoán (đã thao tác trực tiếp trên giao diện, bản sao tệp thật)

| Hiện tượng người dùng thấy | Nguyên nhân thật | Trạng thái |
| --- | --- | --- |
| Chuyển Unicode/Dịch: bấm Duyệt thì báo lỗi ngắn rồi biến mất, không ra tệp | Bước tự kiểm so tệp ra với bản gốc đọc thẳng. Khi lưu, ezdxf chuẩn hoá giá trị mặc định (`const_width` ×6.056, `angle` ×1.306, `extrusion`…). Mọi bản vẽ thật từ AutoCAD đều vấp; DXF tổng hợp trong test thì không, nên test không bắt được | **Đã sửa**: so với bản gốc ghi lại qua cùng thư viện (ghi lại lần hai: 0 khác biệt). Unicode 677 chuỗi, Dịch (thay chữ, song ngữ) ra tệp mới ĐẠT |
| Ở phòng Thiết kế 3D bấm Chuyển Unicode/Dịch "không có gì xảy ra" | Tab Thay đổi của phòng 3D luôn hiện "Không có thay đổi cho xem 3D", nuốt bản xem trước | **Đã sửa** |
| Màn 3D "chưa dựng được" dù mã mới dựng được | Phiên CAD Guard chạy mã cũ (bật trước khi gộp) | **Đã sửa** 10/11: lối tắt tự thay phiên cũ |
| Thông báo lỗi biến mất sau 3,6 giây; đọc không biết sửa gì | Mọi lỗi đi qua `toast`; thông điệp viết cho lập trình viên; lỗi nội bộ bảo "xem cửa sổ dòng lệnh" trong khi ứng dụng chạy ngầm không có cửa sổ | **Đã sửa**: khung thông báo không tự tắt, "Vì sao / Làm gì để chạy được", nút làm ngay (`app/guidance.py`); lỗi nội bộ có mã `E-xxxxxx` + nhật ký `logs/app-errors.log` |
| Phần thiếu 3D ghi mã máy ("Mặt đứng V:A3991:1…") | Thông điệp dựng 3D không nói tờ nào, vì sao, sửa ở đâu | **Đã sửa**: mỗi phần thiếu có tên hình + tờ, lý do, "Sửa nhanh tại đây" và "Sửa gốc trong AutoCAD"; ô chọn mặt bằng hiện tên hình; tên hạng mục giải mã TCVN3; dòng "Sẵn sàng" của hạng mục |
| Quá nhiều lỗi, ngại bắt đầu | Mỗi nhóm lỗi phải tick, chọn, xem trước riêng | **Đã thêm** Sửa hàng loạt (mục 2) |

Số trên bản vẽ phiên 01 sau sửa hàng loạt: 13 thao tác (Unicode + 10 đổi tên layer xref + 1 gộp + dọn kiểu), VS-01 từ 11 về 0,
không luật nào tăng; sao lưu 50 MB + tệp mới trong ~30 s.

## 2. Sửa hàng loạt (đã làm, `app/bulkfix.py`)

- Nút **Sửa hàng loạt** trên thanh công cụ, dùng được ở mọi phòng.
- Bước 1, chạy khô: gom thao tác tự sửa được từ mọi chuẩn của phòng thành MỘT changeset; xem trước ĐẠT/KHÔNG ĐẠT, danh sách
  "Sẽ sửa", "Chưa sửa tự động (lý do)", "Cần người sửa trong CAD".
- Bước 2: **bắt buộc sao lưu**. Ô "Tạo bản sao lưu" luôn bật, không tắt được; máy chủ từ chối nếu thiếu `backup: true`. Bản sao
  nguyên byte vào `.cadguard/backups/<tên>.<thời điểm>.<băm>.dxf`, kiểm mã băm bản sao trước khi sửa.
- Kết quả ra **tệp mới**, tự kiểm, hoàn tác được như changeset thường. Tệp gốc không bao giờ bị ghi.
- Chỉ gom thao tác an toàn: đã tick mặc định, đủ giá trị. Không tự gom: khung tên/template (đụng nhiều tờ), gộp layer cần
  chọn đích (trừ layer rác xref: tự đổi về tên gốc, xref lồng lấy tên cuối, trùng tên thì gộp). Unicode chạy đầu, dọn định
  nghĩa chạy cuối.

Việc còn lại của mục này (P1): khi gộp không đạt, tự chia nhỏ để tìm nhóm gây lỗi và áp phần còn lại; thêm "Sửa hàng loạt cả
thư mục" (mỗi tệp một bản sao lưu + một tệp mới, báo cáo tổng).

## 3. Đồ thị tri thức bản vẽ `cg.drawing-graph/1`: kim chỉ nam cho các bước sau

### 3.1 Vì sao cần

Mỗi bước sau quét (dựng 3D, diễn hoạ, bóc tách vật tư, dữ liệu sản xuất, dịch) đang tự đoán lại cùng một câu hỏi: tờ nào là
gì, hình nào là mặt bằng/mặt đứng của hạng mục nào, khối nào là tủ nào, ghi chú nào là vật liệu của tấm nào. Mỗi bước đoán
một kiểu, đoán sai thì người dùng không biết sửa ở đâu. Đồ thị là **một bản đồ duy nhất**, có nguồn gốc từng ý, người dùng xác
nhận một lần, mọi bước sau đọc chung.

### 3.2 Nút và cạnh

| Nút | Ví dụ | Lấy từ |
| --- | --- | --- |
| Sheet (tờ) | Tờ 19 · MẶT BẰNG BỐ TRÍ THIẾT BỊ BẾP ƯỚT | `sheets.py` (có sẵn) |
| View (hình) | plan / elevation / section / detail / ceiling | `scene/views2d.py` (có sẵn) |
| Item (hạng mục) | Tủ bếp ướt (fur.68) | khung tên + tiêu đề hình (có sẵn) |
| Module (khối/tủ) | M1 tủ treo 1110×680×840 | `scene/assemble.py` (có sẵn) |
| Component (tấm/cánh/ngăn kéo/đợt) | Cánh M1.F2 | P3 (mục 4) |
| Material, Hardware | MFC An Cường 18 mm, bản lề Blum 110° | ghi chú chữ + hồ sơ công ty + LLM |
| Dimension, Label | kích thước 2050, chữ "MFC chống ẩm" | mô hình `cg.drawing/1` |
| Finding | VS-07 trên khung tên tờ 3 | kết quả luật |

Cạnh: `sheet→contains→view`, `view→depicts→item`, `view→shows→module`, `elevation↔plan (same_object, offset_x)`,
`section_mark→cuts→view`, `dimension→measures→module.axis`, `label→names→material|component`, `component→made_of→material`,
`finding→on→node`.

Mỗi nút/cạnh mang **nguồn gốc**: `source` (tất định | llm | người dùng), `confidence`, `refs` (handle trên bản vẽ),
`status` (đề xuất | đã xác nhận). Nút do code tính là sự thật đo được; nút do LLM đề xuất chỉ thành sự thật khi người dùng
xác nhận hoặc khi harness kiểm được bằng hình học (vd. hai hình có kích thước chung đúng số đo).

### 3.3 Vai trò của AI Agent (lớn hơn hiện nay, nhưng có kiểm chứng)

Luồng khi quét một bản vẽ:

1. **Khung tất định** (giây): tờ, hình, hạng mục, khối, kích thước, chữ → đồ thị bản nháp.
2. **Agent làm giàu** (phút, chạy nền, chế độ nội bộ; ẩn danh thì chỉ gửi cấu trúc):
   - Sub-agent *Phân loại tờ/hình*: hình chưa có tiêu đề, tiêu đề lạ, tờ gom nhiều hạng mục.
   - Sub-agent *Ghép hình*: mặt đứng ↔ mặt bằng ↔ mặt cắt khi code không tìm thấy kích thước chung (đúng loại phần thiếu
     đang chặn 3D ở fur.68, fur.99, fur.108).
   - Sub-agent *Vật liệu & ghi chú*: gán chữ ghi chú cho tấm/cánh, chuẩn hoá tên vật liệu theo bảng thuật ngữ công ty.
   - Sub-agent *Nhất quán*: tổng kích thước con ≠ kích thước tổng, hạng mục có mặt đứng mà không có mặt bằng…
   - Công cụ (thêm vào `agent/registry.py`, MCP và engine dùng chung): `graph_query`, `graph_neighbors`, `view_image` (ảnh
     SVG/PNG một hình, đã có `sheet_render.py`), `texts_near`, `dims_of_view`, `propose_graph_edits`.
   - **Đầu ra có cấu trúc** (JSON Schema `cg.graph-proposals/1`): danh sách sửa đồ thị, mỗi mục có lý do + handle bằng chứng.
3. **Harness kiểm** (code): bằng chứng phải tồn tại; ghép hình phải khớp kích thước trong dung sai hoặc gắn "độ tin thấp";
   không đổi nút đo được; vượt ngân sách lượt thì dừng. Đánh giá bằng bộ ca tổng hợp + số liệu cấu trúc phiên thử (không lưu
   bản vẽ thật).
4. **Người dùng xác nhận** trên màn "Bản đồ bản vẽ": thẻ theo hạng mục, mỗi đề xuất một nút Đồng ý/Sửa/Bỏ. Lưu vào
   `.cadguard/graph/<băm>.json`; bản vẽ không bị sửa.

### 3.4 Đồ thị dẫn đường cho tái cấu trúc

Từ đồ thị đã xác nhận sinh changeset chuẩn hoá (dùng thao tác có sẵn, đi qua Sửa hàng loạt):
layer theo vai trò (tường, đồ, nét khuất, kích thước, chữ), tên khối theo hạng mục/mô-đun, đánh số tờ theo hạng mục, gắn mã
hạng mục vào khung tên. Mỗi bước sau có **cổng sẵn sàng** đọc từ đồ thị, hiện thành danh sách việc cần làm:

| Bước | Điều kiện đủ | Thiếu thì người dùng thấy |
| --- | --- | --- |
| Dựng 3D hình khối | hạng mục có ≥1 mặt bằng + ≥1 mặt đứng đã ghép; mỗi khối đủ R/S/C/cao độ | danh sách phần thiếu + nút sửa nhanh (đã có ở mức hạng mục) |
| 3D tấm (sản xuất) | + hồ sơ kết cấu công ty, độ dày ván | "Chưa có hồ sơ kết cấu: chọn mẫu" |
| Bóc tách vật tư | + vật liệu cho mọi tấm/cánh | các tấm chưa có vật liệu |
| Dữ liệu sản xuất | + phụ kiện, kiểu trùm, chiều mở | cánh chưa có chiều mở… |

## 4. 3D phục vụ sản xuất (theo nghiên cứu, thứ tự ưu tiên)

Nguyên tắc: mô hình **tấm** trước, hình đẹp sau; mọi suy luận không chắc có cờ "giả định", sửa được; mặc định lấy từ **hồ sơ
kết cấu công ty** (không có TCVN về kích thước tủ: đây là chỗ thay "chuẩn quốc gia").

| # | Tính năng | Cho ai | Mức tất định |
| --- | --- | --- | --- |
| 1 | Mô hình tấm thay khối hộp: hông/nóc/đáy/hậu/đợt/vách có độ dày, theo kiểu kết cấu công ty (hông trùm/nóc trùm, hậu rãnh/bắt vít, lùi hậu) | Kỹ thuật, xưởng | Cao khi có hồ sơ |
| 2 | Danh sách cắt + dán cạnh từng cạnh (CSV/Excel, cột theo mẫu xưởng) | Xưởng cắt/dán, dự toán | Cao |
| 3 | Tách lớp (exploded), xuyên thấu (X-ray: cánh/hậu trong suốt), mặt cắt tuỳ chọn để nhìn kết cấu bên trong | Xưởng lắp, kỹ thuật, đào tạo | Cao |
| 4 | Đối chiếu 2D ↔ 3D thành phát hiện của luật (tổng ô ≠ khoang, cánh không phủ đủ, khe không đều) | Kỹ thuật kiểm bản vẽ | Cao |
| 5 | Cánh có kiểu trùm, khe, chiều mở (ký hiệu chữ V trên mặt đứng) + hoạt cảnh mở cánh/kéo ngăn | Thiết kế, khách | Trung bình–cao |
| 6 | Bản lề tự động: số lượng theo khối lượng cánh (Blum: 4–6 kg → 2, 6–12 kg → 3; cánh > 600 mm thêm), chén 35, khoảng C | Xưởng khoan, mua hàng | Cao khi chọn hãng |
| 7 | Ngăn kéo theo công thức hệ ray (vd. TANDEMBOX đáy = lọt lòng − 75) | Xưởng, mua hàng | Cao |
| 8 | Kiểm va chạm, khoảng thông thuỷ (cánh đụng tường/tủ cạnh, lối đi < 914/1067 mm) | Thiết kế, kỹ thuật | Trung bình |
| 9 | Công thái học có nguồn, mức `info`, ngưỡng trong hồ sơ công ty (`standards/ergonomics-v0.yaml` đang chờ duyệt số) | Thiết kế | Cao |
| 10 | BOM phụ kiện + bản vẽ khoan tham khảo theo quy ước layer kiểu ABF | Xưởng CNC | Cao về hình học, **rủi ro trách nhiệm cao**: chỉ là bản vẽ tham khảo, không phải tệp chạy máy |

Không làm trong v1: render ảnh thực (vật liệu PBR, ánh sáng), G-code/nesting (để phần mềm CAM/ABF của xưởng).

## 5. Lộ trình

| Đợt | Nội dung | Tiêu chí xong (đo được) |
| --- | --- | --- |
| P0 ✅ 11/11 | Kiểm tệp ra trên bản vẽ thật, xem trước ở phòng 3D, thông báo bền có hướng dẫn, phần thiếu 3D nói rõ cách sửa, Sửa hàng loạt có sao lưu | Unicode/Dịch/Sửa hàng loạt ra tệp mới ĐẠT trên bản sao tệp phiên 01; test chặn hồi quy |
| P1 ✅ 11/11 | Đồ thị khung tất định `cg.drawing-graph/1` + màn "Bản đồ bản vẽ" + cổng sẵn sàng; Sửa hàng loạt cả thư mục, tự chia nhỏ khi không đạt | Đồ thị phiên 01: 40 tờ, 11 hạng mục, ≥ 90 % hình có loại; mỗi cổng có danh sách việc cần làm |
| P2 ✅ 11/11 | Agent làm giàu đồ thị: 4 sub-agent, công cụ đồ thị trong `agent/registry.py`, đầu ra `cg.graph-proposals/1`, harness, màn xác nhận | Trên phiên 01: ghép được ≥ 2/3 mặt đứng đang thiếu ghép; 0 đề xuất không có bằng chứng lọt qua harness |
| P3 | Hồ sơ kết cấu công ty + mô hình tấm + exploded/X-ray/mặt cắt + danh sách cắt/dán cạnh | Mọi khối có tấm; cut list CSV khớp tổng diện tích ván ± 1 % |
| P4 | Cánh/bản lề/ngăn kéo theo bảng hãng có phiên bản, hoạt cảnh mở, va chạm, công thái học `info` | Số bản lề/ray khớp bảng hãng trên bộ ca tổng hợp |
| P5 | Bóc tách vật tư theo vật liệu từ đồ thị; xuất dữ liệu sản xuất tham khảo; tái cấu trúc theo đồ thị qua Sửa hàng loạt | Bảng vật tư theo hạng mục; changeset chuẩn hoá ĐẠT |

## 5b. Kết quả P1 (11/11/2026)

- `cadguard/graph.py` (`cg.drawing-graph/1`), `cadguard graph <dxf>`, nút **Bản đồ** trong ứng dụng, lưu `.cadguard/graph/<băm tệp>-<băm phần bổ sung>.json`.
- Bản vẽ phiên 01 (bản sao ngoài repo): 40 tờ, 123 hình (98 % có loại; 40 cụm 1–2 đối tượng tách riêng là mảnh lẻ), 11 hạng mục, 13 khối,
  10 loại vật liệu được ghi chú, 197 nút / 344 quan hệ, dựng trong 0,3 s.
- Cổng sẵn sàng: Cấu trúc hồ sơ 121/123 (4 việc), Dựng 3D 3/11 (15 việc), Bóc tách 6/11 (6 việc), Sản xuất chưa mở (chờ hồ sơ kết cấu, P3).
  Mỗi việc có nút làm ngay: Chuyển Unicode, Mở 3D hạng mục, Xem tờ (tự chuyển sang phòng có màn tờ).
- Sửa hàng loạt: gộp không đạt thì tự chia đôi tìm nhóm gây lỗi (tối đa 8 lần chạy khô), giữ phần đạt; **Sửa cả thư mục** chạy nền có
  tiến độ, mỗi tệp một bản sao lưu + một tệp mới, tệp lỗi không dừng cả lượt.
- Chưa làm (chuyển P2): công cụ đồ thị cho trợ lý (phải lọc ẩn danh), đề xuất AI + màn xác nhận, gắn phát hiện của luật vào đồ thị trong ứng dụng.

## 5c. Kết quả P2 (11/11/2026)

- `graph_ai.py` (`cg.graph-proposals/1`): 4 agent hẹp — `views` (loại hình chưa tiêu đề), `links` (ghép mặt đứng–mặt bằng),
  `materials` (vật liệu theo bộ phận), `review` (soát nhất quán + hạng mục không phải đồ nội thất). Mỗi agent có gợi ý **code**
  (chạy cả khi không có AI/ẩn danh) và gợi ý **AI** (gói ngữ cảnh hẹp, JSON).
- Gợi ý code đáng chú ý: ký hiệu "triển khai diện tường" trên mặt bằng mang nhãn a/b/c → ghép mặt đứng hướng B/C; tờ tên
  "MẶT ĐỨNG" chỉ có một hình chưa tiêu đề → mặt đứng; mặt bằng > 10 m không có tủ → hồ sơ kiến trúc; ghi chú vật liệu tách theo
  vế ("KHUNG NHÔM, CÁNH KÍNH" → khung: Nhôm, cánh: Kính; so khớp giữ dấu để "CẠNH" ≠ "CÁNH").
- **Harness**: bằng chứng phải là handle/mã hình có thật đúng chỗ; ghép hình phải cùng hạng mục, lệch chiều ngang > 15 % thì gắn
  cảnh báo; vật liệu phải dẫn chứng bằng ghi chú trên tờ của hạng mục; đề xuất trái nhau cho cùng mục bị đánh dấu "mâu thuẫn";
  AI và code cùng ý thì gộp một thẻ (giữ thông số chi tiết AI đọc được).
- Chỉ ghi khi người dùng bấm **Đồng ý** (từng thẻ, hoặc "Đồng ý các đề xuất chắc chắn" tin cậy ≥ 75 % không cảnh báo). Ghép hình →
  phần bổ sung 3D; loại hình, vật liệu, phạm vi → `.cadguard/graph/<băm>.overrides.json`. 3D và Bản đồ cùng đọc.
- AI: `studio/llm.all_backends` thử lần lượt khoá API → CLI claude → CLI Codex (chỉ khi người dùng đã bật thử nghiệm Codex);
  một AI lỗi (hết tín dụng…) thì sang AI sau. Dự án ẩn danh: chỉ chạy gợi ý code. Công cụ trợ lý `get_drawing_graph` (lọc ẩn danh).
- Số đo trên bản sao tệp phiên 01:
  - Chỉ code (0,1 s): 2 loại hình, 2 ghép hình, 1 hạng mục kiến trúc, 33 vật liệu theo bộ phận; 0 bị harness loại.
    Đồng ý hết: hình có loại 98 % → 100 %, việc cần làm của Dựng 3D 15 → 8, hạng mục "d" (định vị cửa cả tầng) ra khỏi đếm.
  - Code + AI thật (CLI claude hết tín dụng → tự chuyển Codex CLI, 114 s cho 4 agent): cả 4 mặt đứng đồ nội thất chưa ghép
    đều có đề xuất (2 code + AI cùng ý; 2 AI thêm, có cảnh báo lệch 20 % và 69 %), 43 thẻ vật liệu (17 gộp code + AI, kèm
    thông số như "MDF 17MM chống ẩm phủ laminate Formica mã 0871"), 1 đề xuất loại hình mâu thuẫn với code (AI: mặt cắt X1
    theo chữ cạnh hình; code: mặt đứng theo tên tờ), 4 đề xuất bị harness loại (bằng chứng không có trong bản vẽ).
- Còn mở: căn vị trí ngang khi mặt đứng chỉ là một đoạn của mặt bằng (đang căn mép trái, có cảnh báo); mặt bên (theo chiều sâu)
  chưa dùng để dựng; agent `review` chưa đưa nhận xét nào trên tệp này.

## 6. Cần khách trả lời trước P3

1. Kiểu kết cấu chuẩn của xưởng: hông trùm hay nóc trùm; hậu rãnh (lùi, dày, sâu rãnh) hay bắt vít; chân tủ/len chân.
2. Hãng/mã bản lề và ray đang dùng (Blum, Hettich, Häfele, hàng nội địa) và khe cánh chuẩn.
3. Mẫu danh sách cắt/nhãn xưởng đang nhận (Excel, ABF, OpenCutList, phần mềm máy cắt/CNC).
4. Quy ước ký hiệu mở cánh, ngăn kéo, đợt di động trên bản vẽ của công ty.
5. Khối lượng riêng ván theo nhà cung cấp (MFC/MDF/plywood) để tính số bản lề.
