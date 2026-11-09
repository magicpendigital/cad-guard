# Chạy thử cad-guard với AutoCAD (M1 + M2, duyệt 07/11/2026)

Phạm vi đã duyệt (xem `PLAN.md` mục 3): **theo tệp**, không điều khiển AutoCAD trực tiếp.

```text
AutoCAD (bản vẽ DWG đang mở)
  │  CGXUAT: DXFOUT ra <thư mục làm việc>\<tên>.dxf   (DWG giữ nguyên)
  ▼
Thư mục làm việc ──► cadguard watch: tự kiểm, ghi .cadguard\reports\<tên>.html|.json
  │
  └──► cadguard mcp --workspace <thư mục>  ◄── Claude Desktop / Claude Code / Codex (trợ lý AI, chỉ đọc, ẩn danh Bậc 1)
          │ kết quả có handle
          ▼
AutoCAD: CGTOI <handle>  → phóng tới và chọn đúng đối tượng
```

Không có: plugin .NET, điều khiển AutoCAD qua COM, sửa DWG từ trợ lý. Sửa bản vẽ vẫn đi đường `cadguard propose/apply` ra tệp DXF **mới** (`docs/changeset.md`).

## 1. Cài trên máy thử

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1     # cài [dev,agent,keyring], chạy test, quét thử
python -m cadguard doctor --mcp                                    # kiểm môi trường + chạy thử MCP trên DXF tổng hợp
```

`doctor` phải báo "Môi trường sẵn sàng." Mục kho khoá (keyring) chỉ là nên có.

## 2. Thư mục làm việc và theo dõi

1. Tạo một thư mục **rỗng** cho phiên, ví dụ `D:\CadGuardPhien\phien-01`. Chỉ đặt vào đó DXF của phiên (không mở trợ lý ở thư mục chứa mọi bản vẽ của công ty).
2. Chạy theo dõi (để cửa sổ mở trong lúc làm):

   ```powershell
   python -m cadguard watch D:\CadGuardPhien\phien-01            # thêm --profile ho-so.yaml nếu có hồ sơ công ty
   ```

   Tệp mới hoặc vừa đổi được kiểm sau khi đứng yên qua hai lần quét (mặc định 2 giây/lần). Bỏ qua thư mục ẩn và tệp đầu ra changeset `*.cg-<mã>.dxf`.

## 3. Nối trợ lý AI (M1)

In cấu hình đúng Python và đường dẫn của máy (không ghi tệp, không có khoá):

```powershell
python -m cadguard mcp-config claude-desktop --workspace D:\CadGuardPhien\phien-01
python -m cadguard mcp-config claude-code   --workspace D:\CadGuardPhien\phien-01
python -m cadguard mcp-config codex         --workspace D:\CadGuardPhien\phien-01
```

- **Claude Desktop:** Settings → Developer → Edit Config, gộp khối in ra vào `mcpServers`, lưu, thoát hẳn rồi mở lại. Claude Desktop không có công cụ đọc tệp riêng nếu không cài thêm máy chủ MCP khác, nên trợ lý chỉ thấy bản vẽ qua 6 công cụ chỉ đọc của cad-guard. Mẫu: `knowledge/mcp/claude-desktop/claude_desktop_config.json`.
- **Claude Code / Codex:** dùng thêm mẫu chặn công cụ đọc tệp/shell trong `knowledge/mcp/` (README ở đó).

Số đo trên máy phát triển (DXF tổng hợp, `scripts/mcp_smoke.py`, 07/11/2026): khởi động tới `list_tools` 1,6 s; `audit` lần sau 0,04 s; kết quả lớn nhất khoảng 6.300 token; 100 lượt gọi liên tiếp không lỗi. Số liệu đầy đủ: `docs/perf/mcp-smoke-2026-11-07.json`. Trên máy thử chạy lại `python scripts/test.py --extras agent --run ../../scripts/mcp_smoke.py`.

## 4. AutoCAD (M2)

```powershell
python -m cadguard autocad --copy-to D:\CadGuardPhien    # chép cadguard.lsp và in cách nạp
```

Trong AutoCAD: `APPLOAD` → chọn `cadguard.lsp` (nên thêm thư mục vào Trusted Locations; muốn tự nạp thì thêm vào Startup Suite).

| Lệnh | Việc |
| --- | --- |
| `CGTHUMUC` | Đặt thư mục làm việc (lưu trong cấu hình AutoCAD của người dùng) |
| `CGXUAT` | Xuất bản vẽ đang mở ra `<thư mục>\<tên>.dxf` bằng `DXFOUT` (độ chính xác 16, phiên bản DXF mặc định) |
| `CGTOI` | Nhập một hoặc nhiều handle (vd. `2A3F,2A40`) → phóng tới và chọn |
| `CGBAOCAO` | Mở báo cáo HTML của bản vẽ đang mở |

Tệp LISP không dùng ActiveX (`vla-`/`vlax-`), không lưu, không xoá, không sửa đối tượng (có test chặn).

### Danh sách kiểm tay trên AutoCAD dùng thử (bắt buộc trước khi hứa với người dùng)

Dùng bản vẽ tổng hợp (`fixtures/synthetic/*.dxf` mở rồi lưu thành DWG) hoặc mẫu thật để **ngoài repo** theo `docs/samples-intake.md`. Ghi kết quả (bản AutoCAD, đạt/không) vào mục 5.

1. `APPLOAD` nạp được; dòng lệnh hiện "[cad-guard] Đã nạp…" đúng dấu tiếng Việt (nếu lỗi phông: kiểm `LISPSYS` = 1).
2. `CGXUAT` trên bản vẽ đã lưu: có tệp `.dxf` trong thư mục; **thanh tiêu đề vẫn là tên `.dwg`** (DXFOUT không đổi bản vẽ đang mở). Nếu thanh tiêu đề đổi sang `.dxf`: dừng, ghi lại phiên bản, không dùng `CGXUAT` cho tới khi sửa.
3. `cadguard watch` in một dòng kết quả cho tệp vừa xuất trong vài giây.
4. Trong Claude Desktop: "kiểm bản vẽ mới nhất" → trợ lý gọi `list_drawings`/`audit`, nêu mã luật và handle.
5. `CGTOI <handle>` lấy từ báo cáo hoặc trợ lý: phóng tới và chọn **đúng** đối tượng. Đây là phép kiểm "handle giữ nguyên qua DXFOUT"; nếu sai, ghi lại và chỉ dùng báo cáo theo layer.
6. Sửa bản vẽ, `CGXUAT` lại: báo cáo cập nhật, số lỗi đổi đúng.
7. AutoCAD LT (nếu có): lặp 1–5.

## 5. Kết quả kiểm tay

| Ngày | Bản AutoCAD | Mục 1–7 | Ghi chú |
| --- | --- | --- | --- |
| 09/11/2026 | AutoCAD 2027 bản dùng thử (đầy đủ, Windows 11) | 1 đạt; 2 đạt; 3 đạt; 4 chưa kiểm; 5 đạt; 6 đạt; 7 không có LT | Bản vẽ tổng hợp `bad_layers.dxf` → SAVEAS DWG 2018 → `CGXUAT`. Mục 1: `[cad-guard] Đã nạp…` đúng dấu, có hộp thoại bảo mật "Unsigned Executable File" (chọn Load Once; muốn tắt thì thêm thư mục vào Trusted Locations). Mục 2: thanh tiêu đề vẫn `.dwg`. Mục 3: `watch` báo sau ~4 s. Mục 5: handle A2–B7 giống hệt qua DXF → DWG → DXFOUT; `CGTOI B6` chọn đúng LINE (0,0)→(10,10) trên layer 0 (kiểm bằng `LIST`). Mục 6: `CHPROP` B6 sang `FN-PART-OUTL`, `CGXUAT` lại → cảnh báo 1 → 0. `CGBAOCAO` lỗi khi thư mục gõ dạng `D:/…` (Explorer mở Documents); đã sửa (`cg:winpath`), kiểm lại mở đúng báo cáo. |
