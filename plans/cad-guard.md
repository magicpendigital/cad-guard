# Kế hoạch dự án cad-guard — trợ lý kiểm tra và chuẩn hoá bản vẽ cho doanh nghiệp sản xuất nội thất

> Tham chiếu. Trạng thái hiện tại và lộ trình chạy thử: xem `PLAN.md` ở gốc repo (cập nhật 07/11/2026).

Trạng thái: **ĐỀ XUẤT, chờ CEO duyệt** (02/11/2026). CEO đã đồng ý hướng: làm ở **project riêng**, MCA chỉ giữ giá trị cốt lõi; chuẩn trình bày lấy từ nghiên cứu ngành làm bản v0 rồi cải tiến theo dữ liệu thật.
Tên `cad-guard` là tên tạm. Đây là sản phẩm độc lập, MCA là đội phát triển và là nơi đo tăng trưởng (xem mục 7).
Đọc cùng: `plans/cad-guard-standard-v0.md` (chuẩn trình bày + 58 luật), `guides/cad-guard-bootstrap.md` (tạo dự án, đăng ký MCA, nối `report_signal`), `plans/provider-abilities.md` (Phase Y), `plans/mcp-declare.md` (Phase J).

## 1. Vấn đề

Doanh nghiệp nội thất sản xuất (tủ bếp, tủ áo, văn phòng) có các phòng Kỹ thuật, Thiết kế sản xuất, Diễn họa làm việc quanh AutoCAD và bản vẽ. Lỗi trong bản vẽ chỉ lộ ra ở xưởng hoặc công trình, lúc sửa đã đắt: cắt sai, thiếu ghi chú dán cạnh, lệch phụ kiện, bảng kê không khớp hình. Công ty **chưa có chuẩn bản vẽ viết ra**, nên "đẹp, chuyên nghiệp, ai nhìn cũng hiểu" hiện phụ thuộc từng người.

Ý tưởng: nhân viên AI hỗ trợ trước (rà lỗi, chuẩn hoá, ghi chú cho bộ phận sau, cảnh báo sớm), rồi nhận hẳn một số bước nếu số liệu cho thấy làm tốt.

## 2. Mục tiêu (đo được)

1. Quét một bộ bản vẽ và ra báo cáo lỗi theo chuẩn v0 trong < 2 phút / bản (tầng A).
2. Với bộ luật được bật: **độ chính xác của cảnh báo ≥ 85–90% trên bộ bản vẽ thật** (mức tham chiếu để quyết bật cảnh báo thời gian thực; điều chỉnh sau P1 khi có số liệu).
3. Giảm lượng lỗi lọt xuống xưởng: đo số lần làm lại do bản vẽ mỗi tuần trước và sau (nguồn: xưởng/lắp đặt báo).
4. Thợ vẽ **dùng được mỗi ngày** mà không thấy bị giám sát: nhật ký chỉ nằm trên máy họ, báo cáo cho quản lý chỉ gồm số tổng hợp.
5. Chuẩn trình bày có phiên bản, cải tiến được bằng dữ liệu (mục 6 của chuẩn v0).

## 3. Phạm vi

Trong phạm vi v1: kiểm tra và đề xuất chỉnh sửa bản vẽ 2D (AutoCAD), bảng kê vật tư, ghi chú bàn giao. Máy Windows có AutoCAD của khách.

Ngoài phạm vi v1 (làm sau nếu có tín hiệu): Diễn họa/dựng hình (SketchUp, 3ds Max, D5…) — bài toán khác hẳn, không gộp; đọc bản vẽ quét/ảnh; xuất thẳng sang phần mềm CNC; nhiều khách hàng; bán dạng dịch vụ đám mây.

## 4. Kiến trúc

```text
┌─────────────────────────────────────────────────────────────┐
│ Tầng 3  Nối MCA (tuỳ chọn)  điều lệ dự án · report_signal · số đo qua script │
├─────────────────────────────────────────────────────────────┤
│ Tầng 2  Trợ lý LLM  giải thích lỗi · viết ghi chú · lệnh tự nhiên → thao tác có cấu trúc │
├─────────────────────────────────────────────────────────────┤
│ Tầng 1  Plugin AutoCAD mỏng (C#)  xuất mô hình bản vẽ · bảng điều khiển · bắt sự kiện │
├─────────────────────────────────────────────────────────────┤
│ Tầng 0  Lõi (Python + ezdxf)  Drawing Model · bộ luật · báo cáo · CLI — không cần LLM, chạy cục bộ │
└─────────────────────────────────────────────────────────────┘
```

**Nguyên tắc: phát hiện lỗi bằng code, LLM chỉ giải thích và đề xuất.** Kiểm layer, kích thước, trùng lặp là việc tất định: nhanh, đúng mọi lần, chạy được không cần mạng. Các nguồn tổng hợp 2026 cũng ghi AI đọc tốt bản vẽ sạch nhưng yếu khi cần hiểu ý đồ thiết kế, và công cụ kiểm "gợi ý, không ký duyệt"; benchmark thứ cấp cho thấy đếm ký hiệu chỉ khoảng 0,40–0,55 chính xác. Vì vậy không để mô hình ngôn ngữ/thị giác đọc kích thước từ ảnh để ra quyết định.

### Tầng 0 — Lõi

- Python 3.12, `ezdxf` (MIT), `pydantic`. Đọc DXF hoặc JSON do plugin xuất → **Drawing Model** (layer, kiểu chữ, kiểu kích thước, khối + thuộc tính, layout, viewport, kích thước, đối tượng).
- Luật khai báo trong `standards/*.yaml` (id ổn định, tham số, mức độ, phiên bản) + hàm kiểm theo `id`. 58 luật ở `cad-guard-standard-v0.md`.
- CLI: `cadguard audit <file|thư mục> --standard furniture-v0 --out report.json|html`, `cadguard stats --json` (số đo cho MCA).
- Chọn Python vì ezdxf là thư viện DXF mở tốt nhất; MCA viết bằng TypeScript không ảnh hưởng vì hai bên nói chuyện qua CLI/JSON.

> **Cập nhật 03/11 (đề xuất, chờ duyệt):** Tầng 1 được thiết kế lại theo hướng không phụ thuộc phần mềm CAD (DXF chung, adapter theo từng phần mềm, thêm trình xem/rà soát). Xem `plans/cad-guard-direction.md` mục 4–5. Phần AutoCAD bên dưới giữ làm một adapter trong nhiều adapter.

### Tầng 1 — Đường vào dữ liệu và plugin

| Tình huống | Đường đi | Ghi chú |
| --- | --- | --- |
| AutoCAD đầy đủ (khuyên dùng) | Plugin C# lệnh `CGEXPORT` xuất Drawing Model JSON ngay từ bản DWG đang mở | Không cần đọc DWG bên ngoài; chọn .NET theo bản AutoCAD (bản mới dùng .NET 8, bản cũ .NET Framework — kiểm tài liệu theo bản của khách) |
| Quét hàng loạt đêm | `accoreconsole.exe` (lõi dòng lệnh của AutoCAD đầy đủ) chạy script xuất | **Cần kiểm** trên máy khách; không có trong LT |
| AutoCAD LT | AutoLISP (LT hỗ trợ từ bản 2024; không nạp được chương trình .NET/ObjectARX; chưa rõ reactor) hoặc quy trình "Save as DXF → thư mục theo dõi → báo cáo" | Không có cảnh báo thời gian thực nếu không có reactor; ra báo cáo theo yêu cầu |
| DWG ngoài AutoCAD | **Không dựa vào ở v1** | ODA File Converter chỉ miễn phí cho **mục đích phi thương mại** nếu không là thành viên ODA, và không được phân phối lại → không dùng trong sản phẩm bán; thay thế (Autodesk APS Model Derivative: tính theo token Flex + gửi bản vẽ lên đám mây; LibreDWG: GPL, chưa kiểm) đều có đánh đổi |

Plugin:

- **Mỏng và an toàn:** lỗi trong tiến trình AutoCAD làm sập AutoCAD của thợ vẽ. Plugin chỉ xuất dữ liệu, hiển thị bảng điều khiển, bắt sự kiện; việc nặng chạy ở dịch vụ cục bộ (pipe/localhost).
- **Sự kiện:** .NET API có sự kiện thay đổi đối tượng (`ObjectModified`…) và kết thúc lệnh (`CommandEnded`). Gom theo handle, giảm tần suất (debounce), chỉ kiểm phần đã đổi.
- **Không tự sửa bản vẽ:** mọi chỉnh sửa là đề xuất → xem trước → thợ vẽ chấp nhận → thực hiện trong một giao dịch hoàn tác được; mặc định lưu bản sao.
- **Popup không chặn thao tác:** bóng thông báo/khung bên, có "đã hiểu / báo sai / nhắc sau", mức độ rõ ràng. Cảnh báo sai nhiều thì thợ vẽ tắt đi — đây là rủi ro chính của tầng 3 thời gian thực.

### Tầng 2 — Trợ lý LLM

- Kiểu "thao tác có cấu trúc": mô hình chỉ trả danh sách thao tác (đổi layer, thêm ghi chú, đổi kiểu kích thước…); bộ kiểm duyệt thao tác, xem trước, rồi trình thực thi mới chạm bản vẽ. Layer được bảo vệ (khung tên, phiên bản) kiểm ở cả hai chỗ. Ghi chú thay đổi sinh tất định từ thao tác, không từ văn bản tự do của mô hình. (Mẫu này lấy từ dự án mã nguồn mở `cad-dxf-agent`, Apache-2.0 — chỉ để tham khảo thiết kế, không cần dùng code.)
- Việc LLM làm: giải thích lỗi bằng tiếng Việt kèm cách sửa; soạn ghi chú bổ sung cho bộ phận sau từ dữ liệu có cấu trúc ("dán cạnh 1 mm cạnh lộ, vân dọc"); gợi ý luật mới từ phản hồi; tóm tắt báo cáo bộ bản vẽ; dịch lệnh tự nhiên của thợ vẽ ("đổi hết text 3.5 sang 2.5") thành thao tác.
- **Chỉ gửi trích đoạn Drawing Model đã ẩn tên khách, không gửi cả file.** Chế độ cục bộ (không LLM) vẫn chạy trọn các luật tất định.
- Khoá API do khách tự cấu hình (xem Phase Y, màn Nhà cung cấp); không dùng gói thuê bao cá nhân của CEO để phục vụ nhân viên của khách (vướng điều khoản — kiểm từng nhà cung cấp).

### Tầng 3 — Nối MCA

Xem mục 7 và `guides/cad-guard-bootstrap.md`. Phần mềm tại khách **không gọi MCP**; nó xuất số tổng hợp để MCA đọc bằng nguồn `cmd`/`file`.

## 5. Dữ liệu, bảo mật, pháp lý

- **Bản vẽ của khách là tài sản có thể bị NDA.** Quy tắc cứng: không đưa `.dwg/.dxf` thật vào repo, vào worktree của agent MCA, hay lên LLM đám mây khi chưa có đồng ý bằng văn bản. `.gitignore` chặn `*.dwg`, `*.dxf` trừ thư mục `fixtures/` (chỉ bản tổng hợp/ẩn danh).
- **Agent phát triển (Claude, Codex…) chỉ làm việc trên dữ liệu tổng hợp.** Bản vẽ thật chỉ được xử lý cục bộ bởi lõi tất định trên máy khách; số đo ra khỏi máy là số tổng hợp.
- **Ghi nhật ký:** nhật ký chỉnh sửa/ cảnh báo nằm trên máy thợ vẽ; không gửi lên quản lý theo từng người. Giải thích rõ với đội trước khi triển khai ("trợ lý cá nhân, không phải giám sát").
- **Quyền sử dụng thư viện/phần mềm:** ODA File Converter (phi thương mại với người không là thành viên), FLUX.2 một số trọng số cần giấy phép thương mại, v.v. → mỗi phụ thuộc có dòng giấy phép trong `docs/licenses.md`.
- **Trách nhiệm:** công cụ "gợi ý, không ký duyệt"; kỹ sư vẫn chịu trách nhiệm. Ghi rõ trong tài liệu cho khách.
- **Chi phí LLM của khách:** đặt trần theo lần chạy/ngày; mặc định tắt LLM, bật khi khách cấu hình khoá.

## 6. Dữ liệu và hợp đồng giữa các tầng

```text
Drawing Model (JSON)        { schema: "cg.drawing/1", file_hash, units, layers[], styles{text,dim,line}, blocks[{name,attribs}],
                              layouts[{name,paper,viewports[{scale,locked,bounds}]}], entities_summary, dims[], parts[] }
Finding (JSON)              { id, rule_id, severity, message_vi, location{layout|handle|bbox}, evidence, standard_version, state }
                              state: open | accepted | fixed | dismissed | false_positive   (do thợ vẽ đặt)
Suggestion / ChangeSet      { id, finding_id, ops[{op, target, params}], preview, requires_confirm: true }
Telemetry (SQLite cục bộ)   audit_runs, findings(state, rule_id, ts), suggestions(accepted bool), downstream_reports(rework, drawing_id_hash)
Stats (stdout của cadguard stats --json)   { "drawings_audited_7d": 41, "defects_confirmed_7d": 18, ... }   ← MCA đọc bằng nguồn cmd
```

Mọi mã khách/bản vẽ trong telemetry là băm một chiều; không có đường dẫn, tên khách hay nội dung.

## 7. Nối vào MCA (tóm tắt; chi tiết ở hướng dẫn)

- Đăng ký cad-guard như một **dự án (venture)** trong MCA: phòng `dev` (lõi, plugin), `quality` (chấm, kiểm), sau thêm `research` (tiêu chuẩn, công cụ).
- Chỉ số điều lệ (đề xuất): `confirmed_defects_7d` (north star giai đoạn pilot), `rule_precision_pct`, `false_positive_pct`, `suggestion_accept_pct`, `rework_incidents_7d`, `active_drafters_7d`, `audit_minutes_per_drawing`.
- Nguồn tín hiệu: `cmd: python -m cadguard stats --json`; thả file `.mca/signals/*.md` cho cảnh báo; agent phát triển gọi `report_signal` cho sự kiện phát hành.
- Họp vận hành hằng tuần dùng chính các số này để đề xuất giả thuyết ("hạ mức luật TX-10", "thêm luật FN-04 vì xưởng báo lỗi dán cạnh") và việc cho `dev`.

## 8. Lộ trình

| Giai đoạn | Nội dung | Cổng quyết định (đi tiếp khi…) |
| --- | --- | --- |
| P0 Khảo sát tại khách | 2–3 tuần; số liệu thật | Có ≥ 30 bản vẽ + lịch sử lỗi + biết bản AutoCAD, phần mềm CNC đích, đồng ý dữ liệu |
| P1 Rà soát hàng loạt (chỉ đọc) | lõi + xuất dữ liệu + ~30 luật tất định + báo cáo | Độ chính xác luật đã chọn đạt mức tham chiếu trên bản vẽ thật |
| P2 Đề xuất chỉnh sửa có xem trước | chuẩn hoá layer/chữ/kích thước, ghi chú bàn giao | Thợ vẽ chấp nhận ≥ ngưỡng đặt trước; không lần nào hỏng bản vẽ |
| P3 Cảnh báo thời gian thực | ≤ 10 luật tất định, CSS thấp | Tỉ lệ báo sai thấp; thợ vẽ không tắt |
| P4 Nhận hẳn một bước | ví dụ lập bảng kê tự động có duyệt | Dữ liệu P1–P3 chứng minh, quyết bởi CEO |
| P5 (sau) Thiết kế sản xuất | bóc tách, bảng cắt, khớp phần mềm CNC | Sau khi P1 chạy ổn |

### P0 — Khảo sát tại khách (Size: XS) — BƯỚC CẦN NGƯỜI
- Acceptance criteria:
  - `docs/discovery.md` ghi: bản AutoCAD (đầy đủ hay LT, năm), số thợ vẽ, phần mềm xưởng/CNC đích, mẫu file hiện dùng, thư mục lưu bản vẽ, ai kiểm hiện nay.
  - 30–50 bản vẽ đại diện (ẩn danh) + danh sách ≥ 20 sự cố thật (lỗi gì, ở khâu nào, tốn bao nhiêu) → xếp hạng 10 lỗi đắt nhất.
  - Văn bản đồng ý về dữ liệu: cho phép gì (xử lý cục bộ, gửi trích đoạn lên LLM, lưu fixture ẩn danh).
  - Các quyết định mục 6 của chuẩn v0 được ghi (hoặc ghi "chưa quyết, dùng mặc định v0").
- Verification command: người duyệt đọc `docs/discovery.md`; không có lệnh tự động.
- Blocked by: CEO duyệt kế hoạch.

### P1a — Lõi: Drawing Model, bộ luật, báo cáo (Size: L)
- Acceptance criteria:
  - `cadguard audit` đọc DXF → Drawing Model → chạy ≥ 30 luật Tất định + CSS thấp của chuẩn v0 (nhóm SH, LY, TX tất định, DH, PR tất định) → `report.json` + `report.html` tiếng Việt.
  - Mỗi luật có test với DXF tổng hợp đúng và sai (tạo bằng ezdxf); luật không bao giờ ném lỗi khi dữ liệu thiếu (trả `skipped` kèm lý do).
  - `cadguard stats --json` in số tổng hợp, không có tên/đường dẫn.
  - Chuẩn có phiên bản (`furniture-v0`), báo cáo ghi phiên bản.
- Verification command: `pytest -q` + `python -m cadguard audit fixtures/synthetic --standard furniture-v0`
- Files likely touched: `packages/core/cadguard/{model,rules,report,cli}.py`, `standards/furniture-v0.yaml`, `fixtures/synthetic/*`
- Test seams: DXF dựng bằng ezdxf; không bản vẽ khách thật trong repo
- Blocked by: duyệt plan (có thể bắt đầu song song P0 với dữ liệu tổng hợp)

### P1b — Xuất Drawing Model từ AutoCAD (Size: M)
- Acceptance criteria:
  - Lệnh `CGEXPORT` trong AutoCAD đầy đủ ghi Drawing Model JSON đúng schema `cg.drawing/1` từ DWG đang mở, trên ≥ 3 bản vẽ mẫu; thời gian < 10 giây / bản.
  - Cùng nội dung xuất qua DXF (ezdxf) và qua plugin cho kết quả luật giống nhau (kiểm khác biệt, ghi danh sách khác biệt đã biết).
  - Đường LT/DXF: thư mục theo dõi hoạt động, báo cáo sinh khi có file mới.
- Verification command: bộ kiểm tay trên máy có AutoCAD (bước người) + `dotnet test` cho phần không phụ thuộc AutoCAD
- Blocked by: P0 (biết bản AutoCAD); P1a (schema)

### P1c — Đo độ chính xác với người rà soát (Size: XS) — BƯỚC CẦN NGƯỜI
- Acceptance criteria: người kỹ thuật rà thủ công cùng bộ bản vẽ; bảng so sánh theo luật: đúng/sai/bỏ sót; luật nào đạt ngưỡng thì được đánh dấu `realtime_ok`. Ghi vào `docs/accuracy-p1.md`.

### P2 — Đề xuất chỉnh sửa có xem trước (Size: L)
- Acceptance criteria: ChangeSet cho ≥ 8 loại sửa tất định (đổi layer, kiểu chữ, kiểu kích thước, thêm khung tên thiếu, thêm ghi chú chung…); xem trước; hoàn tác một bước; mặc định lưu bản sao; layer bảo vệ không bị đụng; bản vẽ không bao giờ bị hỏng (kiểm tự động bằng mở lại + so sánh số đối tượng); ghi chú thay đổi tất định.
- Lớp LLM: giải thích lỗi + soạn ghi chú bổ sung; thao tác LLM đề xuất qua bộ kiểm duyệt; chế độ không LLM vẫn dùng được.
- Blocked by: P1c

### P3 — Cảnh báo thời gian thực (Size: L)
- Acceptance criteria: chỉ luật `realtime_ok`; kiểm phần đã đổi trong < 500 ms; không chặn thao tác; có "báo sai" một chạm đưa vào telemetry; có thể tắt từng luật; plugin không làm sập AutoCAD trong bộ kiểm kéo dài (soak test) — ghi kết quả.
- Blocked by: P1c, P2

### P4 — Nhận hẳn một bước (Size: M, theo quyết định CEO)
- Chỉ bắt đầu khi dữ liệu P1–P3 cho thấy một bước (ví dụ bảng kê) có tỉ lệ đúng đủ cao; vẫn có người duyệt trước khi xuống xưởng cho tới khi CEO chấp nhận bỏ.

## 9. Rủi ro

| Rủi ro | Giảm thiểu |
| --- | --- |
| Cảnh báo sai nhiều → thợ vẽ tắt | Chỉ bật thời gian thực cho luật đã đo; nút "báo sai"; theo dõi tỉ lệ báo sai theo luật hằng tuần |
| Thợ vẽ thấy bị giám sát | Nhật ký cục bộ, báo cáo tổng hợp, giải thích trước, không xếp hạng cá nhân |
| Chỉ có AutoCAD LT | Đường DXF/LISP; cảnh báo thời gian thực có thể không làm được → nói rõ từ P0 |
| Chuẩn chưa có → luật tuỳ tiện | Chuẩn v0 từ ngành, mọi luật có phiên bản + lý do, công ty duyệt mục 6 |
| Phụ thuộc ODA/Autodesk cloud | Không dựa vào ở v1; trích xuất từ AutoCAD |
| Autodesk tự ra tính năng kiểm lỗi | Lợi thế là chuẩn riêng của công ty + luật nội thất + nối sản xuất, không cạnh tranh ở tính năng chung |
| Một khách duy nhất → quá khớp | Chuẩn tách "lõi nội thất" và "cấu hình công ty" ngay từ đầu |
| Mô hình thị giác đọc sai kích thước | Không dùng để ra quyết định; bản quét là việc sau, luôn có người duyệt |
| Bản AutoCAD đổi → plugin hỏng | Tách tầng 1 mỏng; ma trận phiên bản trong CI khi có thể |

## 10. Decision log

| Decision | Chosen option | Why |
| --- | --- | --- |
| Tách hay gộp vào MCA | Project riêng; MCA là đội dev + nơi đo tăng trưởng | CEO chọn 02/11: khác cách chạy (đồng bộ trong AutoCAD vs việc bất đồng bộ), khác người dùng, khác công nghệ/giấy phép/dữ liệu |
| Chuẩn trình bày | Nghiên cứu ngành → v0 → cải tiến theo dữ liệu | CEO chọn 02/11 |
| Phát hiện lỗi | Code tất định; LLM chỉ giải thích/đề xuất | Chính xác, rẻ, chạy cục bộ; thị giác LLM chưa tin được với kích thước |
| Ngôn ngữ lõi | Python + ezdxf | Thư viện DXF mở tốt nhất; ghép với MCA qua CLI/JSON |
| Đường vào dữ liệu | Xuất từ chính AutoCAD (plugin), không đọc DWG ngoài | Tránh giấy phép ODA, tránh cloud |
| Sửa bản vẽ | Đề xuất → xem trước → chấp nhận → hoàn tác được | Bản vẽ là tài sản sản xuất |
| Hướng đi phần mềm CAD (03/11, **CEO duyệt**) | Hướng theo tệp, DXF làm chung; không fork CAD mã nguồn mở, không tự xây CAD; chi tiết ở `plans/cad-guard-direction.md` (thay đổi Tầng 1 và P0); dự phòng: plugin AutoCAD nếu hướng theo tệp không giải quyết được | Phòng kỹ thuật dùng nhiều phần mềm và đang rời AutoCAD; giá trị nằm ở luật + dữ liệu |
| Bản vẽ khách thật và agent phát triển | Không đưa vào repo/worktree/LLM đám mây khi chưa đồng ý | NDA, quyền sở hữu |

## 11. Not yet specified
- Mô hình kinh doanh/giá, cách triển khai nhiều khách, hỗ trợ.
- Cách nhận số đo từ máy khách về máy chạy MCA (thư mục đồng bộ, email, kho riêng) — chọn ở P3, ưu tiên cách không gửi bản vẽ.
- Có cần webhook nhận tín hiệu cho MCA (hiện chỉ cmd/file/http_json kéo về) — để sau.
- Hỗ trợ BricsCAD/ZWCAD/GstarCAD (phổ biến ở một số thị trường) — chưa nghiên cứu.
- Đọc bản quét/PDF cũ — sau P2.
- Diễn họa (Phase riêng, công cụ khác).

## 12. Always / Never
- Always: mọi luật có id + phiên bản + nguồn; báo cáo ghi phiên bản chuẩn; mọi chỉnh sửa có xem trước và hoàn tác; số liệu ra khỏi máy khách là tổng hợp; test dùng dữ liệu tổng hợp; thông báo cho người dùng bằng tiếng Việt.
- Never: đưa bản vẽ thật vào repo/worktree/LLM đám mây khi chưa được đồng ý; sửa bản vẽ mà không có xác nhận; gửi nhật ký theo từng thợ vẽ cho quản lý; ghi token/khoá API vào file; chạy cảnh báo thời gian thực cho luật chưa đo độ chính xác; dùng ODA File Converter trong sản phẩm bán khi chưa có giấy phép.

## Progress
| Step | Status |
| --- | --- |
| P0 Khảo sát tại khách | Chưa bắt đầu |
| P1a Lõi + luật | Chưa bắt đầu |
| P1b Xuất từ AutoCAD | Chưa bắt đầu |
| P1c Đo độ chính xác | Chưa bắt đầu |
| P2 Đề xuất chỉnh sửa | Chưa bắt đầu |
| P3 Cảnh báo thời gian thực | Chưa bắt đầu |
| P4 Nhận hẳn một bước | Chưa bắt đầu |
