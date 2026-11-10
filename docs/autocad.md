# CAD Guard trong AutoCAD

## Bắt đầu nhanh (người dùng thiết kế, không cần biết lệnh)

**Cài một lần trên mỗi máy**

1. Bấm đúp lối tắt **CAD Guard** trên màn hình (lần đầu do người phụ trách IT chạy `cadguard setup --all` hoặc mở
   CAD Guard rồi vào màn **Cài đặt**).
2. Trong CAD Guard, màn **Cài đặt**: bấm **Cài** ở ba mục: *Phông Be Vietnam Pro*, *Gắn CAD Guard vào AutoCAD*,
   *Lối tắt CAD Guard trên màn hình*.
3. Mở lại AutoCAD. Lần đầu AutoCAD có thể hỏi có nạp `cadguard.lsp` không: bấm **Always load**.

**Dùng hằng ngày: một lệnh**

- Mở bản vẽ, gõ **`CADGUARD`** rồi Enter. CAD Guard tự xuất bản sao DXF (kể cả phần chưa lưu; bản vẽ không bị lưu hay đổi) vào thư mục
  `CADGuard` cạnh bản vẽ, mở trình duyệt và kiểm ngay bản vẽ đó. Bản DWG không bị đổi.
- Mọi việc tiếp theo là **nút bấm** trong CAD Guard: xem lỗi theo tờ, *Tới trong AutoCAD*, *Chuyển chữ sang Unicode*,
  *Dịch* (Tiếng Anh / Tiếng Trung), *Học template từ tờ này*, các thao tác sửa ở tab **Thay đổi** (xem trước → Áp dụng →
  tệp mới, Hoàn tác được).

Các mục dưới đây dành cho người dùng nâng cao và người phụ trách kỹ thuật.

---

## Nâng cao: kiến trúc theo tệp (M1 + M2 duyệt 07/11/2026; M3 + hướng D mở cổng 09/11/2026)

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

## 8. Sửa trong bản vẽ đang mở: CGKIEM, CGUNICODE, CGDICH, CGTRINHBAY (Đợt F, 10/11/2026)

Cần AutoCAD bản đầy đủ (COM). `cadguard autocad --copy-to <thư mục tin cậy>` chép `cadguard.lsp` và ghi
`cadguard-run.cmd` cạnh nó; APPLOAD tệp LSP. Lần đầu, nếu AutoCAD không tự thấy `cadguard-run.cmd`, lệnh sẽ hỏi chọn tệp.

Mỗi lệnh: SAVE → gõ lệnh → CGXUAT tự chạy → cửa sổ cad-guard hiện xem trước → gõ `c` để áp. Áp trong một nhóm undo
(gõ U để trả lại), bản DWG đã lưu được chép vào `<thư mục làm việc>/.cadguard/backup/` trước khi sửa, bản vẽ không tự
lưu. Nếu chữ trong bản vẽ đã khác lúc xem trước, không đổi gì. Chi tiết: `docs/sheets-presentation.md` mục F.

### 8.1 Danh sách kiểm tay

**Trạng thái 10/11/2026: CHƯA chạy trên AutoCAD 2027 có giao diện.** Phiên Luồng 1 chỉ chạy `accoreconsole` (không
giao diện) để in PDF theo tờ (`cadguard sheets --pdf`, 40/40 tờ trên bản sao tệp phiên thử) và test với COM giả. Bước
chuẩn bị A ghi cấu hình AutoCAD của người dùng (`acaddoc.lsp`, khoá Applications) nên để người dùng tự bấm. Ghi kết quả
vào mục 5 (ngày, bản AutoCAD, mục đạt/không đạt, ghi chú).

Chuẩn bị (một lần):

- A. `cadguard app` → tab **Cài đặt** → *Gắn CAD Guard vào AutoCAD* → Cài. Kiểm: `%APPDATA%\Autodesk\AutoCAD 2027\<hồ sơ>\Support\acaddoc.lsp` có khối đánh dấu CAD Guard; thư mục cài có `cadguard.lsp`, `cadguard-run.cmd`,
  `cadguard-acad.json` trỏ đúng Python và mã của `main` (không phải nhánh/worktree cũ).
- B. Đóng hết phiên CAD Guard cũ (hoặc khởi động lại máy), mở lại AutoCAD; lần đầu chọn *Always load* ở hộp thoại bảo mật.
- C. Bản vẽ thử: `cadguard fixtures <thư mục>` → mở `sheets/model_sheets.dxf` → SAVEAS DWG 2018 vào thư mục thử
  (không dùng bản vẽ khách cho các bước sửa). Chuẩn bị template: `cadguard template learn <tệp>.dxf --sheet 1`.

CADGUARD (lệnh một bước, LISP):

1. Bản vẽ chưa đặt tên (Drawing1): `CADGUARD` → hộp thoại "hãy lưu bản vẽ…", không tạo thư mục, không mở trình duyệt.
2. Bản vẽ đã lưu: `CADGUARD` → tạo `<thư mục bản vẽ>\CADGuard\`, có `<tên>.dxf` (CGXUAT), trình duyệt mở CAD Guard
   đúng bản vẽ đó (không phải phiên cũ); thanh tiêu đề AutoCAD vẫn là `.dwg`, bản DWG không đổi (so ngày sửa).
3. Gõ `CADGUARD` lần hai: dùng lại phiên đang chạy (không mở thêm cửa sổ/cổng mới), tự chuyển sang bản vẽ.
4. Đổi bản vẽ chưa lưu (vẽ thêm một đường, không SAVE) → `CADGUARD`: bản xuất có đường mới (DXFOUT xuất trạng thái đang
   mở); AutoCAD không tự lưu.
5. Chưa gắn CAD Guard (gỡ ở tab Cài đặt, mở lại AutoCAD): `CADGUARD` báo "chưa được cài… Cài đặt > Gắn CAD Guard".

CGBANG (plugin .NET, bảng neo):

6. Sau bước A + B, mở AutoCAD **không** NETLOAD tay: `CGBANG` chạy được (plugin tự nạp qua khoá Applications,
   `LOADCTRLS` = 2); dòng lệnh có `[cad-guard] Đã nạp plugin…` đúng dấu tiếng Việt.
7. `CGBANG`: bảng neo phải hiện CAD Guard, tự mở đúng bản vẽ đang mở, quét được; tab Cài đặt hiện trong bảng (không phải
   giao diện phiên cũ). Bảng hẹp không bị cắt mép.
8. Trong bảng, thẻ lỗi → **Tới trong AutoCAD**: AutoCAD phóng tới và chọn đúng đối tượng (kiểm bằng `LIST`).
9. `CGGHIM`: ghim số trên bản vẽ giữ cỡ cố định khi phóng to/thu nhỏ; gõ lại để tắt.
10. Đóng/mở lại bảng nhiều lần, chuyển sang bản vẽ khác: bảng theo bản vẽ đang hoạt động, không treo AutoCAD.

Sửa trong bản vẽ đang mở (Đợt F):

11. CGUNICODE trên một bản vẽ có chữ `.VnTime`: chữ hiện đúng tiếng Việt (sau khi cài phông Be Vietnam Pro); U trả lại.
12. CGDICH → en: chữ đổi sang tiếng Anh, số/kích thước giữ nguyên; U trả lại. (Chế độ song ngữ `layer` chỉ đi đường tệp:
    `cadguard translate --mode layer`, mở `<tên>.enlayer.dxf`, bật/tắt layer `CG-DICH-EN`.)
13. CGTRINHBAY: thuộc tính khung tên đổi theo template; hình vẽ không đổi. Thay khung/đổi hệ số/dời khung không làm
    trong AutoCAD: CGTRINHBAY in "Không tự làm…"; dùng `cadguard template apply` ra tệp mới.
14. Sửa một chữ sau CGXUAT rồi xác nhận áp: phải bị từ chối ("đã khác lúc xem trước").
15. Bản vẽ có thay đổi chưa lưu: lệnh báo SAVE trước.
16. Sau mỗi lần áp: `<thư mục làm việc>\.cadguardackup\` có bản DWG sao lưu; U trả đúng trạng thái trước.
