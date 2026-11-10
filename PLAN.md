# PLAN.md — kim chỉ nam của cad-guard

Cập nhật: 10/11/2026. Đây là **điểm vào duy nhất** để biết dự án đang ở đâu và làm gì tiếp. Chi tiết, lập luận và nhật ký quyết định vẫn nằm ở các tệp trong `plans/` (liệt kê ở mục 5). Khi hai nơi khác nhau, tệp này ghi trạng thái hiện tại; tệp trong `plans/` ghi lý do và lịch sử.

## 1. Hướng đã duyệt (không đổi)

- **Hướng C (CEO duyệt 03/11/2026):** làm theo TỆP, DXF là định dạng chung, không phụ thuộc phần mềm CAD. Plugin AutoCAD (hướng D) là lớp bổ sung; CEO đã mở cổng 09/11/2026 (mục 3).
- **Công cụ nội bộ công ty, chạy cục bộ (chủ dự án quyết định 10/11/2026, `plans/cad-guard-sheets-presentation.md` mục 5).** Đã mở: cổng hướng D (áp dụng thay đổi trong AutoCAD, Đợt F); trợ lý mặc định chế độ **nội bộ** (thấy nội dung thật), ẩn danh Bậc 1 là công tắc theo dự án cho hồ sơ NDA (`privacy.py`); Studio không hỏi đồng ý từng phiên; sửa/bật/tắt luật, mức độ, ngưỡng trực tiếp trên giao diện, không tài khoản (`rule_config.py`, thay quyết định 05/11 về admin theo nhóm luật); người dùng tự bật `realtime_ok` (luật chưa đo hiện nhãn "chưa đo"); agent phát triển được đọc bản vẽ thật ở thư mục ngoài repo để chẩn đoán.
- Phát hiện lỗi bằng luật tất định. LLM được đọc nội dung, nhận xét, đề xuất sửa, dịch; kết quả luật vẫn do code tính, nhận xét của LLM gắn nhãn riêng.
- **Năm rào giữ nguyên (chủ dự án đồng ý 10/11/2026):** mọi thay đổi có xem trước, bản sao lưu và hoàn tác (rút còn một lần bấm xác nhận), ghi ra tệp **mới**; khoá API không ghi ra tệp; bản vẽ thật không commit vào git, test chỉ dùng DXF tổng hợp; mã phiên tự động của app trên 127.0.0.1; telemetry chỉ số tổng hợp, không `git push`.

### Trả lời mục 10 của đề xuất sheets-presentation (10/11/2026)

1. Giữ năm rào "đề xuất giữ" ở mục 5.
2. Ngôn ngữ đích: người dùng chọn **Tiếng Anh** hoặc **Tiếng Trung**; ngôn ngữ nguồn tự nhận theo nội dung bản vẽ.
3. Phông Unicode chuẩn của công ty: **Be Vietnam Pro** (chuyển mã và template).
4. Template khung tên: **học từ tờ mẫu** của tệp phiên thử; logo công ty Grande lấy từ tệp PNG/PDF của công ty (ngoài repo, người dùng chỉ đường dẫn khi chạy `cadguard template learn --logo`).
5. Máy chạy **AutoCAD bản đầy đủ** (có COM và `accoreconsole`).
6. Tệp phiên thử có **40 tờ**; chỉ mục tờ (`sheets.py`) ra đúng 40 sau khi sửa ngưỡng khung tối thiểu và nhận cả tờ trống của bộ khung tên có thuộc tính.

## 2. Trạng thái thật (có bằng chứng trong repo)

| Khối | Có gì | Chưa có / giới hạn |
| --- | --- | --- |
| Lõi đọc DXF | `cg.drawing/1`; `dxf_reader` (ezdxf) và `dxf_stream` (tệp lớn), test khớp nhau trên mọi fixture | Chưa đo trên bộ mẫu thật P0 |
| Luật | `furniture-v0`: 16/58 luật cài đặt; `design-hygiene-v0`: VS-01..VS-07 | Chưa đo độ chính xác (P1c); không luật nào bật `realtime_ok` |
| Sửa an toàn | `cg.changeset/1`: propose/apply/undo/diff/validate | Chỉ các thao tác vệ sinh trong từ vựng cố định |
| Trợ lý | MCP stdio chỉ đọc (6 công cụ, `propose_changeset` khi bật cờ); engine CLI/API; kho khoá hệ điều hành | Chưa thử với người dùng thật (A3) |
| Giao diện | `cadguard app` (cục bộ, mã phiên), `cadguard studio`, `cadguard review` (cổng Tailscale) | Ba server riêng; xem Đợt 4 |
| 3D | `cg.scene/1` tất định, báo phần thiếu, xuất GLB | Diễn hoạ là nhánh phụ |
| AutoCAD | `cadguard.lsp` (CGXUAT/CGTOI/CGDEN/CGBAOCAO/CGHELP), `watch`, `mcp-config`; M3 điều hướng qua COM (`autocad/bridge.py`); plugin .NET `packages/acad-plugin` (CGBANG bảng neo, CGGHIM ghim tạm thời) | Kiểm tay AutoCAD 2027 bản đầy đủ; chưa có LT; plugin chưa có bộ cài tự nạp (.bundle) |
| Tờ + bậc chốt (09/11/2026) | `sheets.py` `cg.structure/1` (layout + khung tờ trong Model, ứng viên rác), `textcodec.py` (TCVN3/VNI), `gate.py` (Chặn/Cảnh báo/Gợi ý, hồ sơ `gate:`), `sheet_state.py` (chốt tờ, xác nhận cảnh báo); app: thanh Tờ, ghim cỡ cố định, chốt tờ | Chỉ thử trên DXF tổng hợp; bậc mặc định là đề xuất v0 chờ trưởng phòng kỹ thuật duyệt; nhận diện khung tờ chưa đo trên bộ mẫu thật P0 |

## 3. Lộ trình chạy thử (duyệt 07/11/2026: phạm vi AutoCAD M1 + M2)

Phạm vi kết nối AutoCAD đã duyệt:

- **M1:** trợ lý AI (Claude Desktop/Code, Codex…) ↔ `cadguard mcp` ↔ DXF xuất từ AutoCAD.
- **M2:** adapter mỏng đúng P1b đã duyệt ("adapter xuất DXF + thư mục theo dõi"): tệp AutoLISP `cadguard.lsp` (`CGXUAT` xuất bản đang mở ra DXF, không đổi DWG; `CGTOI` nhảy tới đối tượng theo handle) và lệnh `cadguard watch`.
- **M3 thu hẹp (người dùng duyệt 09/11/2026): chỉ điều hướng.** Nút "Tới trong AutoCAD" trên `cadguard app` và công cụ MCP `show_in_autocad` (cờ `--allow-autocad`, mặc định tắt) đưa AutoCAD tới đối tượng qua COM. Không sửa/lưu bản vẽ qua COM; mọi chỉnh sửa vẫn đi đường changeset. **CEO mở cổng hướng D (09/11/2026).** Hướng C (theo tệp, DXF) vẫn là đường chính; hướng D bổ sung lớp tương tác trong AutoCAD. Quy tắc giữ nguyên: không sửa/lưu bản vẽ qua COM hay plugin khi chưa có xem trước + xác nhận + hoàn tác và ghi ra tệp mới.

| Đợt | Nội dung | Tiêu chí nghiệm thu |
| --- | --- | --- |
| 0 | venv có SDK `mcp`; `cadguard doctor`; `PLAN.md`; bootstrap cài `[agent,keyring]` | `python scripts/test.py --extras agent` xanh, test MCP không bị bỏ qua |
| 1 | Một sổ khai báo công cụ (`agent/registry.py`) cho MCP và engine API | Test: tên/mô tả/schema MCP trùng `ToolBox`; không có apply; ẩn danh giữ nguyên |
| 2 | Hợp đồng `cg.audit/1` (`contracts.py`) dùng chung cho CLI, App, MCP, báo cáo | Cùng tệp → cùng số lỗi ở mọi nơi; import từng module không vòng |
| 3 | `cadguard watch`, `cadguard.lsp`, `cadguard mcp-config`, `scripts/mcp_smoke.py` | Khởi động MCP tới `list_tools` ≤ 5 s; audit lần sau ≤ 1 s; mỗi kết quả < 10.000 token; 100 lượt gọi không lỗi; kiểm tay trên AutoCAD dùng thử |
| 4 | Gộp Studio vào App; module bảo vệ HTTP dùng chung; Review giữ tiến trình riêng | Không đổi kết quả audit; chặn Host/Origin/mã phiên như cũ |

**Tình trạng 07/11/2026:** Đợt 0–3 đã làm trên nhánh `claude/cadguard-refactor-optimize-8d4a1c` (chưa gộp vào `main`). Bộ test có extras `[agent]`: 683 qua, 2 bỏ qua (tuỳ chọn), 0 lỗi; bench 12/12; `scripts/mcp_smoke.py` đạt cả 4 tiêu chí (khởi động 1,6 s, audit nóng 0,04 s, kết quả lớn nhất ~6.300 token, 100 lượt không lỗi). **Chưa làm:** danh sách kiểm tay trên AutoCAD dùng thử (`docs/autocad.md` mục 4), thử Claude Desktop thật, Đợt 4.

Đợt 4 làm sau buổi chạy thử MCP. Tiếp nhận từ bản Draff chỉ theo `docs/reviews/2026-11-07-draff/report.md` (ở checkout chính), không lấy phần Node/TypeScript.

## 3b. Đợt A–F (đề xuất sheets-presentation, triển khai 10/11/2026, `docs/sheets-presentation.md`)

| Đợt | Đã làm | Còn lại |
| --- | --- | --- |
| A | Sửa/bật/tắt luật, mức độ, ngưỡng trên giao diện + CLI, không tài khoản, nhật ký; chế độ nội bộ mặc định, ẩn danh theo dự án; Studio bỏ hỏi đồng ý từng phiên; AGENTS/PLAN cập nhật | Bỏ phần vai trò khỏi `design/ui-mockup.html` |
| B | Chỉ mục tờ có hệ số thật, độ tin cậy; tệp phiên thử ra 40 tờ; học quy ước layer (LY-01 45 → 0) | Đo trên bộ mẫu P0 |
| C | `convert_unicode` (675 chuỗi tệp thử, 0 không chắc), SVG từng tờ (40 tờ ~15 s), DWG qua `accoreconsole` | Gộp Studio vào App |
| D | `cg.template/1` học từ tờ mẫu (Grande A3 + logo), gói `sheet-layout-v0` TP-01..10, 12; điền khung tên, đánh số | `replace_title_block`, `set_sheet_scale`, `fit_sheet`, TP-11 |
| E | `cadguard translate` en/zh, tự nhận ngôn ngữ, bảng thuật ngữ + bộ nhớ dịch, CSV duyệt, công cụ trợ lý `propose_translation` | Chế độ `layer`; chạy với LLM thật trên tệp thử |
| F | `autocad/executor.py` (COM, một nhóm undo, sao lưu, kiểm chưa đổi), CGKIEM/CGUNICODE/CGDICH/CGTRINHBAY | Kiểm tay trên AutoCAD 2027; in PDF hàng loạt |

## 4. Quyết định còn mở

1. Bản AutoCAD trên máy thử: đã kiểm AutoCAD 2027 bản đầy đủ dùng thử (09/11/2026, `docs/autocad.md` mục 5). Còn mở: AutoCAD LT nếu công ty định mua LT.
2. Handle giữ nguyên qua DXFOUT: đạt trên AutoCAD 2027 với bản vẽ tổng hợp. Còn phải kiểm trên bản vẽ thật có khối/xref (P0) trước khi hứa `CGTOI` với khách.
3. P0: bộ mẫu thật ngoài repo, đồng ý dữ liệu (`docs/samples-intake.md`).
4. P1c: đo độ chính xác cùng kỹ sư rà soát trước khi bật bất kỳ cảnh báo thời gian thực nào.
5. ~~M3~~ Đã chốt 09/11/2026: CEO đồng ý triển khai M3 và mở cổng hướng D (xem mục 3). Còn mở: phạm vi hướng D ngoài điều hướng (bảng lệnh/hướng dẫn trong AutoCAD, khung chat trong AutoCAD) làm theo đề xuất riêng, từng bước có duyệt.

## 5. Tệp tham chiếu trong `plans/`

| Tệp | Vai trò hiện tại |
| --- | --- |
| `plans/cad-guard.md` | Kế hoạch gốc: bài toán, kiến trúc tầng, giai đoạn P0–P4, nhật ký quyết định |
| `plans/cad-guard-direction.md` | Hướng C đã duyệt, P0, dự phòng hướng D |
| `plans/cad-guard-agent.md` | Thiết kế trợ lý: MCP, changeset, engine, tri thức |
| `plans/cad-guard-3d.md` | Dựng 3D tất định và Studio |
| `plans/cad-guard-platform.md` | Tệp nặng, nhiều định dạng, giao diện hợp nhất (đánh giá) |
| `plans/cad-guard-vision-assessment.md` | Đánh giá hướng mở rộng dài hạn (chưa thành kế hoạch) |
| `plans/cad-guard-sheets-presentation.md` | **Đã duyệt và triển khai 10/11/2026 (mục 3b):** mở rào chặn cho dùng nội bộ, sửa luật không tài khoản, chỉ mục tờ, chuyển chữ Unicode, template trình bày, dịch bản vẽ, đánh giá MCP AutoCAD; Đợt A–F |
