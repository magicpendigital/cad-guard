# Chạy thử cad-guard với AutoCAD (M1 + M2 duyệt 07/11/2026; M3 + hướng D mở cổng 09/11/2026)

Phạm vi đã duyệt (xem `PLAN.md` mục 3): **theo tệp**; ngoài ra M3 chỉ để **điều hướng** (đưa AutoCAD tới đối tượng lỗi qua COM, mục 6), không sửa bản vẽ.

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

Không có: sửa DWG từ trợ lý, qua COM hay qua plugin. COM chỉ dùng để phóng tới và chọn đối tượng (mục 6); plugin .NET (mục 7) chỉ hiện bảng cad-guard và ghim lỗi tạm thời trên màn hình. Sửa bản vẽ vẫn đi đường `cadguard propose/apply` ra tệp DXF **mới** (`docs/changeset.md`).

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
| `CGDEN` | Tới đối tượng/layer vừa bấm **Tới trong AutoCAD** trên `cadguard app` (đọc `<thư mục>\.cadguard\goto.txt`) |
| `CGBAOCAO` | Mở báo cáo HTML của bản vẽ đang mở |

Tệp LISP không dùng ActiveX (`vla-`/`vlax-`), không lưu, không xoá, không sửa đối tượng (có test chặn). `CGXUAT` từ chối khi bản đang mở chính là tệp DXF trong thư mục làm việc (trước đây sẽ xoá rồi ghi đè tệp gốc).

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
| 09/11/2026 | AutoCAD 2027 bản dùng thử (đầy đủ, Windows 11) | Plugin (mục 7) + CGHELP: đạt | Bản vẽ tổng hợp `sheet_set.dxf` mở chỉ đọc, `CGXUAT` → `watch` ghi báo cáo. `NETLOAD` → `[cad-guard] Đã nạp plugin…` đúng dấu. `CGGHIM`: vòng khoanh + số 3 (TX-01), 4 (TX-08, kích thước ghi đè ở Tờ 3), dòng lệnh in chú thích; phóng to cửa sổ 0,3000–6000,6500: số giữ cỡ cố định (lỗi đầu tiên: ghim to theo bản vẽ do so `Document` theo tham chiếu, đã sửa so theo con trỏ gốc). `CGBANG`: bảng neo phải, tự chạy `cadguard app`, tự mở `sheet_set`, quét, 7 phát hiện, ô chọn tờ, thẻ Hướng dẫn; bảng hẹp bị cắt mép (đã sửa CSS chế độ bảng). Nút **Tới trong AutoCAD** trong bảng: `Đã phóng tới và chọn 1 đối tượng`. Chưa kiểm: AutoCAD khởi động lại rồi nạp bản build chính thức (kiểm bằng bản build đổi tên do .NET không gỡ được DLL đã nạp). |
| 09/11/2026 | AutoCAD 2027 bản dùng thử (đầy đủ, Windows 11) | M3 + CGDEN (mục 6): đạt | Bản vẽ tổng hợp `thu_bad_layers.dwg` mở chỉ đọc. `bridge.show` qua COM: cửa sổ AutoCAD lên trước, chọn đúng B6; theo layer `0` chọn 1 đối tượng, layer không có báo `layer:…`. Yêu cầu dành cho bản vẽ khác: báo "không phải bản đang mở", không chọn gì. `CGDEN` khi thư mục làm việc khác: báo "Chưa có yêu cầu". Nút **Tới trong AutoCAD** trên `cadguard app` (LY-01, 3 layer): toast "Đã chuyển sang AutoCAD…", AutoCAD chọn đúng. cadguard.lsp tự nạp qua COM khi chưa có `cg:den`, không thấy hộp thoại bảo mật. |

## 6. Tới đối tượng lỗi từ giao diện (CGDEN + M3)

Trong `cadguard app`, mỗi thẻ lỗi có handle hoặc layer có nút **Tới trong AutoCAD**:

1. Giao diện ghi `<thư mục làm việc>\.cadguard\goto.txt` (dòng `F <bản vẽ>`, `H <handle>`, `L <layer>`; tối đa 200 handle, 100 layer).
2. **M3 (Windows, AutoCAD bản đầy đủ, pywin32 — extras `[autocad]`, đã có sẵn khi cài `[agent]`):** cad-guard tìm bản vẽ cùng tên đang mở trong AutoCAD, chuyển sang tab đó, đưa cửa sổ lên trước và gửi đúng một biểu thức cố định `(cg:den "<tệp yêu cầu>")` (tự nạp `cadguard.lsp` đi kèm gói nếu chưa nạp). Không gửi lệnh nào khác, không đọc/ghi đối tượng qua COM, không lưu. AutoCAD đang chạy lệnh (`CMDACTIVE`) hoặc mở hộp thoại thì không gửi và báo lý do.
3. **Không có COM (AutoCAD LT, máy không cài pywin32, hoặc `cadguard app --no-autocad-com`):** chuyển sang AutoCAD và gõ `CGDEN`. Thư mục `CGTHUMUC` phải trùng thư mục của `cadguard app`.

`CGDEN`/`cg:den` kiểm tên bản vẽ trong yêu cầu khớp bản đang mở; lỗi theo layer (vd. LY-01) chọn mọi đối tượng trên layer trong tờ đang xem.

Trợ lý AI: `cadguard mcp --allow-autocad` (hoặc `mcp-config … --allow-autocad`) thêm công cụ `show_in_autocad` (mặc định TẮT). Trợ lý gửi handle/mã layer (L_…); máy chủ giải mã về tên thật chỉ để ghi tệp yêu cầu, kết quả trả trợ lý không có tên thật.

## 7. Plugin .NET: bảng cad-guard (CGBANG) và ghim lỗi (CGGHIM)

Hướng D (CEO mở cổng 09/11/2026). Chỉ AutoCAD bản đầy đủ (LT không nạp .NET). Không sửa, không lưu bản vẽ.

Build (một lần, cần .NET SDK cùng đời AutoCAD; AutoCAD 2027 = .NET 10):

```powershell
python scripts/build_acad_plugin.py            # tự tìm AutoCAD qua registry; thêm --acad-dir "<thư mục>" nếu cần
```

Kết quả: `packages/acad-plugin/bin/plugin/CadGuard.Acad.dll` + `cadguard-acad.json` (đường dẫn Python và PYTHONPATH để
chạy `python -m cadguard app`; KHÔNG có mã phiên hay khoá). Chép cả hai tệp vào một thư mục trong Trusted Locations,
rồi trong AutoCAD: `NETLOAD` → chọn `CadGuard.Acad.dll` (muốn tự nạp mỗi lần mở AutoCAD: dùng bộ cài .bundle, chưa làm).

| Lệnh | Việc |
| --- | --- |
| `CGBANG` | Mở/ẩn bảng cad-guard neo cạnh màn hình cho bản vẽ đang mở: Lỗi (lọc theo tờ, chốt tờ, Đã xem/Bỏ qua), Trợ lý, Hướng dẫn. Plugin tự chạy `cadguard app` cho thư mục `CGTHUMUC` (chỉ 127.0.0.1) và đọc địa chỉ có mã phiên từ đầu ra tiến trình, không ghi mã phiên ra tệp. Bảng tự mở DXF trùng tên bản vẽ (chạy `CGXUAT` trước). Đổi bản vẽ: gõ `CGBANG` lại. |
| `CGGHIM` | Hiện/ẩn ghim số lỗi từ báo cáo `watch` (`.cadguard/reports/<tên>.json`). Ghim là đồ hoạ tạm thời (TransientManager): không thêm đối tượng, không lưu vào DWG, biến mất khi tắt. Vòng khoanh + số tính theo điểm ảnh nên giữ cùng cỡ khi phóng/kéo; ghim gần nhau gộp thành "×n"; số đánh theo mức (Lỗi, Cảnh báo, Gợi ý) như giao diện. Dòng lệnh in bảng số → mã luật. |
| `CGHELP` | (trong `cadguard.lsp`) danh sách mọi lệnh CG… và hướng dẫn chi tiết; thẻ **Hướng dẫn** trong bảng có cùng nội dung. |

Giới hạn: plugin đọc biến `CadGuardFolder` của `CGTHUMUC`; tiến trình `cadguard app` của plugin dừng khi đóng AutoCAD.
Ghim dùng khung bao đối tượng trong WCS (UCS xoay/khung nhìn xoắn chưa xét). Mã nguồn: `packages/acad-plugin/`.
