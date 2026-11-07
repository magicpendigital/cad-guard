# cad-guard — Dựng 3D và ảnh phối cảnh từ bản vẽ DXF

> Tham chiếu. Trạng thái hiện tại và lộ trình chạy thử: xem `PLAN.md` ở gốc repo (cập nhật 07/11/2026).

Trạng thái: **ĐỀ XUẤT (04/11/2026), chờ CEO duyệt các quyết định ở mục 6. Chưa viết code.**
Bổ sung cho `plans/cad-guard-direction.md` (hướng theo tệp, DXF chung). Không thay đổi hướng đã duyệt; đây là một tầng mới nằm sau tầng kiểm luật.

## 1. Kết luận ngắn

Dựng được 3D từ DXF **nếu có thông tin chiều cao**. Bản vẽ 2D không tự chứa chiều cao, nên nguồn chiều cao phải là: (a) thuộc tính của block (rộng, sâu, cao, vật liệu), (b) mặt đứng/mặt cắt trong cùng bản vẽ, (c) quy ước cố định cho tường/sàn. Thiếu thì **bỏ qua kèm lý do, không đoán**.

Ba tầng, làm tuần tự, tầng sau chỉ làm khi tầng trước đã đạt:

- **A. Cảnh 3D tất định + xem trong báo cáo HTML** (không GPU, không phụ thuộc phần mềm CAD).
- **B. Render clay/depth/ID bằng Blender chạy nền.**
- **C. Ảnh phối cảnh bằng khuếch tán + ControlNet** (tuỳ chọn, chỉ để minh hoạ).

## 2. Nguyên tắc (kế thừa AGENTS.md)

- Hình học do code tất định tạo. AI (tầng C) chỉ tô vật liệu/ánh sáng trên khung đã có, không quyết định kích thước. Ảnh tầng C luôn ghi "ảnh minh hoạ, không dùng để đo".
- Chỉ dựng bản vẽ đã qua luật kiểm (đơn vị, layer, trùng lặp, kích thước). Bản vẽ lỗi nặng: không dựng, báo lý do.
- Test chỉ dùng DXF tổng hợp bằng ezdxf. Không dùng bản vẽ thật của khách trong repo/prompt/worktree.
- Đầu ra luôn là tệp **mới**; không sửa bản vẽ gốc.
- Số tổng hợp xuất ra ngoài (telemetry) không chứa tên tệp/khách.
- Thư viện mới phải kiểm giấy phép trước (xem `docs/licenses.md`); tránh copyleft/phi thương mại.

## 3. Tầng A — chi tiết

Hợp đồng dữ liệu mới `cg.scene/1` (tách khỏi `cg.drawing/1`, giữ tương thích ngược):

- `walls[]`: đoạn thẳng nền + dày + cao (mặc định tham số hoá trong chuẩn: cao 2850 mm, dày 120/240 mm; mọi mặc định ghi trong `standards/`, sửa = tạo phiên bản chuẩn mới).
- `modules[]`: tủ/đồ rời với `kind`, vị trí, góc xoay, `w/d/h`, vật liệu, nguồn chiều cao (`attrib` | `elevation` | `default`).
- `skipped[]`: phần tử không dựng được kèm lý do (đưa vào báo cáo).

Thay đổi mã dự kiến:

1. `model.py` + `dxf_reader.py`: thêm toạ độ (điểm chèn, góc xoay, tỉ lệ cho INSERT; đỉnh cho LWPOLYLINE/LINE). Chỉ thêm trường tuỳ chọn.
2. Gói mới `cadguard/scene/`: `build.py` (DrawingModel → Scene), `gltf.py` (Scene → glTF/GLB, tự ghi bằng JSON + nhị phân, không phụ thuộc thư viện nặng).
3. `report.py`: nhúng khung xem 3D (three.js tải sẵn, không CDN, kiểm giấy phép MIT).
4. `cli.py`: lệnh `python -m cadguard scene <dxf> --out scene.glb`.
5. `fixtures.py`: thêm `room_with_cabinets.dxf` (tổng hợp) và một bản thiếu chiều cao để thử nhánh `Skip`.
6. Test: số khối đúng, bounding box khớp kích thước khai báo, nhánh thiếu chiều cao nằm trong `skipped[]`, `ok_sheet.dxf` vẫn sạch.

Tiêu chí xong tầng A: GLB mở được bằng trình xem glTF bất kỳ; kích thước tủ sai lệch 0 mm so với thuộc tính khai báo; `pytest -q` xanh.

## 3b. Tầng A2 — dựng từ nhiều hình chiếu, báo phần thiếu, form bổ sung (CEO duyệt 05/11/2026)

- Nhận diện hình chiếu theo quy ước layer `FN-VIEW-FRONT` / `FN-VIEW-TOP` / `FN-VIEW-SIDE` (đề xuất, chưa vào chuẩn). Mặt bên: trục ngang là chiều sâu tính từ mặt trước. Mặt bằng: trục dọc là chiều sâu.
- Mỗi hình chữ nhật khép kín ở mặt đứng là một tấm ván. Chiều sâu lấy từ mặt bên (khớp khoảng cao), nếu không có thì từ mặt bằng (khớp khoảng ngang). Nhiều khả năng = mơ hồ, không có = thiếu; cả hai đều thành mục trong `gaps[]`, không đoán.
- Đối chiếu kích thước tổng thể giữa các hình (rộng, cao, sâu); lệch quá 0,5 mm = mục `conflict` (phải sửa bản vẽ, không nhập tay được).
- Phần thiếu của mô-đun (H/W/D) cũng thành `gaps[]` thay vì chỉ bỏ qua.
- `cadguard scene ... --form form.html` sinh form tĩnh (không cần máy chủ); người dùng điền rồi tải `.cgsup.json`; chạy lại với `--supplement`. Tệp bổ sung gắn mã băm bản vẽ, không khớp thì bỏ qua. Giá trị nhập tay đánh dấu `source: user`. Có thể bổ sung hình chiếu còn thiếu bằng `--with khac.dxf`.
- Không sửa tệp gốc. Không dùng LLM trong tầng này; việc nhận diện nhãn mơ hồ để dành cho bước sau.

## 3c. Studio: LLM đọc/phân tích → chuẩn hoá → xem 3D hoặc bổ sung (quyết định 05/11/2026)

Quyết định của người dùng: (1) LLM **được xem toàn bộ nội dung bản vẽ** của phiên đang làm; (2) nhà cung cấp: khoá API Anthropic (biến `ANTHROPIC_API_KEY` hoặc kho khoá hệ điều hành qua `cadguard keys set anthropic`) hoặc CLI `claude` nguyên bản, người dùng tự đăng nhập; (3) giao diện: ứng dụng web cục bộ nhỏ, **đồng bộ với `design/ui-mockup.html`**; (4) LLM chỉ đề xuất **thao tác cố định**, ghi **tệp mới**.

- Vòng làm việc: LLM đọc bản tóm tắt (cụm hình học C1.., hình chữ nhật, chữ, số đo, INSERT, kết quả dựng 3D, phần thiếu) → trả JSON gồm nhận xét + đề xuất + câu hỏi → **mã kiểm từng đề xuất** (cụm/tay cầm/khoá phải tồn tại, giá trị hợp lệ; sai thì loại kèm lý do) → người dùng duyệt → áp dụng → dựng lại 3D → vòng tiếp theo.
- 4 loại đề xuất: `set_views` (gán cụm = mặt đứng/bên/bằng, cho bản vẽ không theo quy ước layer), `set_value` (điền phần thiếu), `set_attrib` (thêm/sửa thuộc tính khối), `change_layer` (chuẩn hoá layer). Hoàn tác được; xuất ra `<mã>-chuan-hoa.dxf` mới, nguồn không bị ghi đè.
- Nhận xét của LLM luôn gắn nhãn "LLM · chưa kiểm"; đúng/sai về kích thước vẫn do mã tất định quyết định (giữ nguyên tắc AGENTS.md).
- Dữ liệu: người dùng phải tích đồng ý **trong từng phiên** (mỗi lần mở bản vẽ là phiên mới, đồng ý trở về tắt) trước khi bất cứ nội dung nào rời máy; không gửi đường dẫn/tên tệp; CLI chạy trong thư mục rỗng với mọi công cụ file/shell tắt.
- Khoá API: đọc bằng `assistant/keys.py` như trợ lý (biến môi trường trước, rồi kho khoá hệ điều hành); không ghi ra tệp, không in trong `repr`/lỗi/ghi chú phiên (lỗi HTTP đi qua `post_json`, đã che khoá). Gọi Messages API bằng thư viện chuẩn (`assistant/api_engines.post_json`), **không cần SDK `anthropic`** (bỏ extras `llm`, xem `docs/licenses.md`). Mô hình: `CADGUARD_MODEL` hoặc `CADGUARD_ANTHROPIC_MODEL`, mặc định `claude-sonnet-5-5`; địa chỉ: `CADGUARD_ANTHROPIC_BASE_URL`.

### 3c.1 Studio gửi gì cho LLM (sau khi đồng ý)

Studio **không** dùng chế độ ẩn danh Bậc 1 của trợ lý (`cadguard mcp`/`ask`/`app`): đây là mức Bậc 2 (`plans/cad-guard-agent.md` mục 5.1), chỉ bật khi người dùng tích đồng ý trong phiên. Mỗi lượt gửi `SYSTEM_PROMPT` cố định + tối đa 10 lượt hội thoại trước + bản tóm tắt `studio/clusters.digest()`:

| Phần | Nội dung |
| --- | --- |
| `units` | đơn vị bản vẽ (`mm` hoặc `INSUNITS=…`) |
| `layers` | **tên layer thật** và số đối tượng |
| `clusters[]` | mã cụm C1…, khung bao và kích thước (toạ độ thật), số đối tượng, tên layer, hình chữ nhật (tay cầm + toạ độ, tối đa `MAX_RECTS`), **chữ TEXT/MTEXT trong cụm** (tay cầm, nội dung, vị trí), số đo DIMENSION |
| `inserts[]` | tay cầm, **tên khối thật**, điểm chèn, góc xoay, **giá trị thuộc tính** (tối đa 300 khối) |
| `scene` | kết quả dựng 3D: số tường/mô-đun, tấm (toạ độ), phần thiếu (`gaps`), phần bỏ qua |
| hội thoại | câu người dùng gõ, câu trả lời trước của LLM |

Không gửi: đường dẫn, tên tệp, mã băm tệp, khoá API, nội dung ngoài phiên. Test: `test_requires_consent_and_no_path_leak`, `test_anthropic_backend_key_from_os_keyring_and_http`, `test_anthropic_backend_env_wins_and_errors_hide_key` (`tests/test_studio.py`).
- Máy chủ chỉ nghe 127.0.0.1, kiểm Host, mã truy cập ngẫu nhiên mỗi lần chạy, không cho bind chồng cổng.
- Chưa làm: thao tác "viết kịch bản ezdxf trong sandbox" (đã quyết để sau), đưa kết quả kiểm luật `audit` vào bản tóm tắt, bộ chấm chất lượng LLM, đo chi phí token (đường API đã có test với máy chủ giả, chưa thử với Anthropic thật).

## 4. Tầng B và C — chỉ phác

- B: Blender chạy nền (`blender -b -P`) nhận GLB, xuất ảnh clay, depth, ID theo vật liệu. Cần kiểm giấy phép (GPL của Blender chỉ áp cho Blender, không lan sang dữ liệu/script chạy ngoài; xác nhận trước khi đóng gói).
- C: ControlNet depth + canny, độ mạnh 0,7–1,0; thử Flux/Qwen kèm ControlNet. Cần ≥12 GB VRAM. Chạy cục bộ hay thuê dịch vụ: quyết sau khi đo.
- Cả B và C đều đo trên máy thật (thời gian/ảnh, VRAM, độ lệch hình học) trước khi hứa với khách.

## 5. Rủi ro

| Rủi ro | Giảm thiểu |
| --- | --- |
| Thợ vẽ không đặt thuộc tính block đủ | Thêm luật kiểm thuộc tính chiều cao (dùng chung cơ chế `@rule`), và `Skip` có lý do |
| Ảnh AI lệch chi tiết/mã hàng | Gắn nhãn minh hoạ; không dùng làm hồ sơ sản xuất; đo độ lệch bằng so depth |
| Không có bản vẽ thật để thử | Fixture tổng hợp; mẫu thật chỉ ở thư mục ngoài repo theo `docs/samples-intake.md` |
| Tầng C quá chậm/đắt | Dừng ở A+B, vẫn có giá trị |

## 6. Quyết định cần CEO

| # | Câu hỏi | Mặc định đề xuất |
| --- | --- | --- |
| 1 | Chiều cao tủ lấy từ đâu trước: thuộc tính block, hay mặt đứng? | Thuộc tính block trước (dễ kiểm); mặt đứng làm sau |
| 2 | Có chấp nhận ảnh phối cảnh AI chỉ là minh hoạ, không phải hồ sơ? | Có |
| 3 | Làm tầng A ngay trước các luật còn lại của P1? | Làm như một nhánh song song nhỏ, không chặn P1 |
| 4 | Tầng C chạy cục bộ hay dịch vụ ngoài? | Chưa quyết; đo ở tầng B xong |

## 7. Not yet specified

- Quy ước tên block/thuộc tính chiều cao của phòng kỹ thuật (cần hỏi, hoặc đề xuất chuẩn mới ở `furniture-v0.1`).
- Thư viện vật liệu/đồ rời dùng để tô màu ở tầng B/C.
- Định dạng bàn giao sang phòng lập trình sản xuất (có cần xuất kèm 3D không).
