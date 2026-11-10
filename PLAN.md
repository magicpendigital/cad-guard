# PLAN.md — kim chỉ nam của cad-guard

Cập nhật: 07/11/2026. Đây là **điểm vào duy nhất** để biết dự án đang ở đâu và làm gì tiếp. Chi tiết, lập luận và nhật ký quyết định vẫn nằm ở các tệp trong `plans/` (liệt kê ở mục 5). Khi hai nơi khác nhau, tệp này ghi trạng thái hiện tại; tệp trong `plans/` ghi lý do và lịch sử.

## 1. Hướng đã duyệt (không đổi)

- **Hướng C (CEO duyệt 03/11/2026):** làm theo TỆP, DXF là định dạng chung, không phụ thuộc phần mềm CAD. Plugin AutoCAD (hướng D) chỉ là dự phòng có cổng.
- Phát hiện lỗi bằng luật tất định; LLM chỉ giải thích và đề xuất.
- Sửa bản vẽ: đề xuất → xem trước → người xác nhận → tệp **mới** → kiểm → hoàn tác.
- Trợ lý mặc định ẩn danh Bậc 1. Studio gửi nội dung bản vẽ cho LLM chỉ khi người dùng đồng ý trong phiên.
- Không đưa bản vẽ thật của khách vào repo, test, telemetry hay worktree của agent phát triển.

## 2. Trạng thái thật (có bằng chứng trong repo)

| Khối | Có gì | Chưa có / giới hạn |
| --- | --- | --- |
| Lõi đọc DXF | `cg.drawing/1`; `dxf_reader` (ezdxf) và `dxf_stream` (tệp lớn), test khớp nhau trên mọi fixture | Chưa đo trên bộ mẫu thật P0 |
| Luật | `furniture-v0`: 16/58 luật cài đặt; `design-hygiene-v0`: VS-01..VS-07 | Chưa đo độ chính xác (P1c); không luật nào bật `realtime_ok` |
| Sửa an toàn | `cg.changeset/1`: propose/apply/undo/diff/validate | Chỉ các thao tác vệ sinh trong từ vựng cố định |
| Trợ lý | MCP stdio chỉ đọc (6 công cụ, `propose_changeset` khi bật cờ); engine CLI/API; kho khoá hệ điều hành | Chưa thử với người dùng thật (A3) |
| Giao diện | `cadguard app` (cục bộ, mã phiên), `cadguard studio`, `cadguard review` (cổng Tailscale) | Ba server riêng; xem Đợt 4 |
| 3D | `cg.scene/1` tất định, báo phần thiếu, xuất GLB | Diễn hoạ là nhánh phụ |
| AutoCAD | `cadguard.lsp` (CGXUAT/CGTOI/CGDEN/CGBAOCAO), `watch`, `mcp-config`; M3 điều hướng qua COM (`autocad/bridge.py`) | Kiểm tay AutoCAD 2027 bản đầy đủ; chưa có LT |

## 3. Lộ trình chạy thử (duyệt 07/11/2026: phạm vi AutoCAD M1 + M2)

Phạm vi kết nối AutoCAD đã duyệt:

- **M1:** trợ lý AI (Claude Desktop/Code, Codex…) ↔ `cadguard mcp` ↔ DXF xuất từ AutoCAD.
- **M2:** adapter mỏng đúng P1b đã duyệt ("adapter xuất DXF + thư mục theo dõi"): tệp AutoLISP `cadguard.lsp` (`CGXUAT` xuất bản đang mở ra DXF, không đổi DWG; `CGTOI` nhảy tới đối tượng theo handle) và lệnh `cadguard watch`.
- **M3 thu hẹp (người dùng duyệt 09/11/2026): chỉ điều hướng.** Nút "Tới trong AutoCAD" trên `cadguard app` và công cụ MCP `show_in_autocad` (cờ `--allow-autocad`, mặc định tắt) đưa AutoCAD tới đối tượng qua COM. Không sửa/lưu bản vẽ qua COM; mọi chỉnh sửa vẫn đi đường changeset. Điều khiển AutoCAD rộng hơn (sửa qua COM, plugin .NET) vẫn cần CEO mở cổng hướng D.

| Đợt | Nội dung | Tiêu chí nghiệm thu |
| --- | --- | --- |
| 0 | venv có SDK `mcp`; `cadguard doctor`; `PLAN.md`; bootstrap cài `[agent,keyring]` | `python scripts/test.py --extras agent` xanh, test MCP không bị bỏ qua |
| 1 | Một sổ khai báo công cụ (`agent/registry.py`) cho MCP và engine API | Test: tên/mô tả/schema MCP trùng `ToolBox`; không có apply; ẩn danh giữ nguyên |
| 2 | Hợp đồng `cg.audit/1` (`contracts.py`) dùng chung cho CLI, App, MCP, báo cáo | Cùng tệp → cùng số lỗi ở mọi nơi; import từng module không vòng |
| 3 | `cadguard watch`, `cadguard.lsp`, `cadguard mcp-config`, `scripts/mcp_smoke.py` | Khởi động MCP tới `list_tools` ≤ 5 s; audit lần sau ≤ 1 s; mỗi kết quả < 10.000 token; 100 lượt gọi không lỗi; kiểm tay trên AutoCAD dùng thử |
| 4 | Gộp Studio vào App; module bảo vệ HTTP dùng chung; Review giữ tiến trình riêng | Không đổi kết quả audit; chặn Host/Origin/mã phiên như cũ |

**Tình trạng 07/11/2026:** Đợt 0–3 đã làm trên nhánh `claude/cadguard-refactor-optimize-8d4a1c` (chưa gộp vào `main`). Bộ test có extras `[agent]`: 683 qua, 2 bỏ qua (tuỳ chọn), 0 lỗi; bench 12/12; `scripts/mcp_smoke.py` đạt cả 4 tiêu chí (khởi động 1,6 s, audit nóng 0,04 s, kết quả lớn nhất ~6.300 token, 100 lượt không lỗi). **Chưa làm:** danh sách kiểm tay trên AutoCAD dùng thử (`docs/autocad.md` mục 4), thử Claude Desktop thật, Đợt 4.

Đợt 4 làm sau buổi chạy thử MCP. Tiếp nhận từ bản Draff chỉ theo `docs/reviews/2026-11-07-draff/report.md` (ở checkout chính), không lấy phần Node/TypeScript.

## 4. Quyết định còn mở

1. Bản AutoCAD trên máy thử: đã kiểm AutoCAD 2027 bản đầy đủ dùng thử (09/11/2026, `docs/autocad.md` mục 5). Còn mở: AutoCAD LT nếu công ty định mua LT.
2. Handle giữ nguyên qua DXFOUT: đạt trên AutoCAD 2027 với bản vẽ tổng hợp. Còn phải kiểm trên bản vẽ thật có khối/xref (P0) trước khi hứa `CGTOI` với khách.
3. P0: bộ mẫu thật ngoài repo, đồng ý dữ liệu (`docs/samples-intake.md`).
4. P1c: đo độ chính xác cùng kỹ sư rà soát trước khi bật bất kỳ cảnh báo thời gian thực nào.
5. M3: người dùng duyệt 09/11/2026 phần **điều hướng**; cần CEO xác nhận lại nếu quy định cổng hướng D áp cả cho phần này.

## 5. Tệp tham chiếu trong `plans/`

| Tệp | Vai trò hiện tại |
| --- | --- |
| `plans/cad-guard.md` | Kế hoạch gốc: bài toán, kiến trúc tầng, giai đoạn P0–P4, nhật ký quyết định |
| `plans/cad-guard-direction.md` | Hướng C đã duyệt, P0, dự phòng hướng D |
| `plans/cad-guard-agent.md` | Thiết kế trợ lý: MCP, changeset, engine, tri thức |
| `plans/cad-guard-3d.md` | Dựng 3D tất định và Studio |
| `plans/cad-guard-platform.md` | Tệp nặng, nhiều định dạng, giao diện hợp nhất (đánh giá) |
| `plans/cad-guard-vision-assessment.md` | Đánh giá hướng mở rộng dài hạn (chưa thành kế hoạch) |
| `plans/cad-guard-sheets-presentation.md` | **Đề xuất chờ duyệt (10/11/2026):** mở rào chặn cho dùng nội bộ, sửa luật không tài khoản, chỉ mục tờ, chuyển chữ Unicode, template trình bày, dịch bản vẽ, đánh giá MCP AutoCAD; Đợt A–F |
