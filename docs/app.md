# Giao diện cục bộ `cadguard app`

Ngày viết: 05/11/2026 (thay bản 04/11). Mã: `packages/core/cadguard/app/` (máy chủ `server.py`, dữ liệu `api.py`, trợ lý `chat.py`, chọn dự án `project.py`, cấu hình người dùng `settings.py`, lịch sử quét `history.py`, hình xem trước `geometry.py`, kết nối AI `connect.py`, cấu hình phòng `departments.json`, giao diện `static/`). Test: `packages/core/tests/test_app.py`.

Giao diện **bám bản mẫu chốt `design/ui-mockup.html`**: `static/app.css` = CSS nguyên văn của bản mẫu (biến màu, phông, khoảng cách, sáng/tối) + phần bổ sung ở cuối tệp; cùng tên màn, thứ tự khối, chữ tiếng Việt và biểu tượng. Dữ liệu minh hoạ của bản mẫu đã thay bằng dữ liệu thật; chỗ chưa có dữ liệu thì hiện trạng thái rỗng có hướng dẫn. Script/kiểu nội tuyến của bản mẫu đã chuyển thành `app.js`/`app.css`, gắn sự kiện bằng `addEventListener`.

Ứng dụng web chạy **trên máy người dùng**, chỉ dùng thư viện chuẩn của Python (`http.server`, `json`, `tkinter` cho hộp thoại) và HTML/CSS/JS thuần (không CDN, không framework, chạy offline). Không thêm phụ thuộc.

## 1. Cách mở

```text
cadguard app [--workspace <thư mục dự án>] [--profile ho-so.yaml] [--port 0] [--no-browser]
             [--no-anonymize] [--experimental] [--allow-openrouter] [--account business|api-key] [--no-detect]
```

- Lệnh in địa chỉ `http://127.0.0.1:<cổng>/?t=<mã phiên>` và tự mở trình duyệt (trừ khi `--no-browser`). Mã phiên là mật khẩu của phiên: không gửi cho người khác. Dừng bằng Ctrl+C.
- **Không cần `--workspace`**: ứng dụng mở màn **Mở dự án** (mục 2). `--workspace` vẫn dùng được: mở thẳng dự án đó (và ghi vào dự án gần đây).
- `--profile`: hồ sơ công ty cho dự án mở bằng `--workspace` (chỉ phiên này). Chọn hồ sơ trên giao diện thì được lưu theo dự án.
- `--no-anonymize`: tắt ẩn danh Bậc 1 cho trợ lý, **chỉ** bằng cờ này (giao diện không có nút tắt).
- `--experimental`, `--allow-openrouter`, `--account`: như trước; nay cũng bật được trên màn **Kết nối AI** (cấu hình hiệu lực = cờ HOẶC cấu hình giao diện).
- `--no-detect`: không chạy `claude`/`codex`/`agy` để kiểm đã cài/đăng nhập.

Trong repo (không cài gói): `python scripts/test.py --run -m cadguard app`.

QC nhanh trên dữ liệu tổng hợp:

```text
python scripts/test.py --run -m cadguard fixtures D:\Tam\ws-qc
python scripts/test.py --run -m cadguard app --no-detect
```

rồi trong trình duyệt: dán `D:\Tam\ws-qc` vào ô đường dẫn (hoặc **Mở thư mục…**), phòng **Kỹ thuật**, mở `hygiene_bad.dxf`, bấm **Quét bản vẽ này**.

## 2. Chọn dự án (như coding agent)

- Màn **Mở dự án**: nút **Mở thư mục…** mở hộp thoại chọn thư mục của hệ điều hành (`tkinter.filedialog.askdirectory` chạy trong **tiến trình con** `python -I`, không chặn máy chủ; hộp thoại có thể nằm sau cửa sổ trình duyệt). Máy không có tkinter: nút bị tắt, dùng ô dán đường dẫn đầy đủ. Danh sách **Dự án gần đây** (bấm để mở lại, “Bỏ khỏi danh sách”).
- Đổi dự án lúc đang chạy (nút **Dự án** trên thanh trên): máy chủ dựng lại `Workspace` (rào đường dẫn), ngữ cảnh công cụ, hồ sơ và lịch sử cho thư mục mới; lượt trò chuyện đang chạy bị dừng. Mọi đường dẫn từ trình duyệt sau đó chỉ tương đối với thư mục mới (test kiểm tệp của dự án cũ không còn với tới).
- An toàn: chỉ nhận thư mục tồn tại, đường dẫn tuyệt đối; **gốc ổ đĩa** hoặc **thư mục người dùng (hay thư mục chứa nó)** phải xác nhận trong hộp thoại cảnh báo. Số tệp DXF liệt kê có trần (2.000 tệp, duyệt tối đa 20.000 thư mục). API không bao giờ liệt kê thư mục ngoài dự án: chỉ hộp thoại của hệ điều hành duyệt cây thư mục.
- **Hồ sơ công ty** (“Đổi hồ sơ…” ở cột trái màn Bản vẽ): chọn tệp `.yaml` bằng hộp thoại tương tự hoặc dán đường dẫn; kiểm `cg.company-profile/1` trước khi nhận; lưu theo dự án.
- Cấu hình người dùng: `%APPDATA%\cad-guard\settings.json` (Windows) hoặc `$XDG_CONFIG_HOME/cad-guard/settings.json` / `~/.config/cad-guard/settings.json`; biến `CADGUARD_CONFIG_DIR` đổi thư mục. Chứa: dự án gần đây (đường dẫn + thời điểm mở), hồ sơ theo dự án, cấu hình trợ lý. **Không bao giờ chứa khoá/token** (bộ kiểm từ chối trường lạ trong hồ sơ kết nối).
- Hồ sơ kết nối (`ai.connections`, `ai.active_connection`): mỗi engine có thể có nhiều hồ sơ `{id, engine, label, model, key_slot}` (ví dụ khoá theo phòng/dự án). Giao diện hiện dùng một hồ sơ mặc định mỗi engine (`id` = `key_slot` = tên engine, đúng ô khoá của `cadguard keys`); chưa có màn quản lý nhiều hồ sơ.

## 3. Các màn

| Màn | Nội dung (dữ liệu thật) |
| --- | --- |
| Thanh trên | Dự án hiện tại (bấm để đổi), năm màn **Việc của tôi · Bản vẽ · Tổng quan · Luật áp dụng · Kết nối AI**, **Dữ liệu: Bậc 1** (đỏ khi `--no-anonymize`), chọn **Phòng**, chọn **Trợ lý** (engine dùng được/không kèm lý do), sáng/tối |
| Việc của tôi | “Chào buổi …, phòng X”, hỏi nhanh trợ lý, chuỗi 4 phòng (Thiết kế → Kỹ thuật → Thiết kế 3D + Lập trình sản xuất → Render/Xưởng) với số bản đang xử lý/sẵn sàng 7 ngày; **Nhận từ phòng trước** (bản phòng trước đã đánh dấu sẵn sàng); **Bản vẽ của phòng** với danh sách kiểm (đã quét đủ chuẩn, hết lỗi E, đã đánh dấu bàn giao) và nút **Sẵn sàng giao cho …**; **Lỗi tôi hay gặp (30 ngày)**, **Đề xuất của trợ lý** (changeset trợ lý đề xuất đã áp dụng / tổng), **Gần đây** |
| Bản vẽ | Cột trái: bản vẽ (tệp mới `.cg-….dxf` hiện dưới tệp gốc, nhãn “Bản mới”), chuẩn của phòng, luật chạy, hồ sơ, **Quét cả thư mục**. Giữa: **thanh Tờ** (mục 3b), **xem trước bản vẽ** (khung nhìn gọn: bỏ đối tượng lạc xa), viền tờ, ghim lỗi cỡ cố định trên màn (gộp “×n” khi gần nhau, bấm để phóng tới), thu phóng/kéo, **Trước/Sau** sau khi lưu tệp mới. Phải: tab **Trợ lý**, **Lỗi**, **Thay đổi**, **Hướng dẫn** (lệnh AutoCAD, bậc lỗi) |
| Tổng quan | Số tổng hợp 7 ngày từ lịch sử trên máy: bản đã quét, lỗi E đang mở, tỉ lệ đề xuất được áp dụng, bản đánh dấu bàn giao; bàn giao giữa phòng; luật vi phạm nhiều nhất; độ tin cậy luật (“Chưa đo” cho tới khi có đo độ chính xác P1c); **Dựng 3D đúng không cần sửa** theo tuần và theo kiểu vẽ (từ nút “Xác nhận dựng đúng” ở màn 3D, lưu đáp án, chấm đáp án) |
| Luật áp dụng | Chỉ đọc. Luật của mọi chuẩn kèm phòng áp dụng (từ `departments.json`), tham số mặc định → đang áp (hồ sơ), tình trạng; thẻ theo phòng và “Chưa cài code” để lọc; ngăn chi tiết luật; phiên bản đang dùng. Sửa luật (mục 9b) chưa làm |
| Kết nối AI | Mục 5 |

Phòng (`departments.json`, dạng `cg.app-departments/2`): mỗi phòng có `standards` (nhiều chuẩn), `next` (nhiều phòng nhận), `role`, `priority`, `view`. Kỹ thuật = `design-hygiene-v0` + `furniture-v0` (mặc định, ưu tiên khảo sát); Thiết kế = `design-hygiene-v0`; Lập trình sản xuất = `furniture-v0`; Thiết kế 3D = xem 3D (`view: scene`).

## 3b. Tờ (trang in), bậc lỗi, chốt tờ

- **Tờ** do `sheets.py` nhận tất định (`cadguard sheets <dxf>`): layout có khung nhìn, hoặc khung tên/khung tờ khổ ISO
  trong Model (khối tên KHUNG/FRAME/TITLE…, khổ A0–A4 × tỉ lệ chuẩn, hoặc nhiều khung cùng cỡ). Tiêu đề lấy từ thuộc
  tính khung tên hoặc chữ lớn nhất ở dải khung tên; chữ mã TCVN3/VNI được giải mã để hiển thị (`textcodec.py`).
- Chọn tờ (thanh Tờ hoặc ô chọn trong tab Lỗi): hình phóng tới tờ, danh sách lỗi chỉ còn lỗi của tờ đó và lỗi chung
  của cả bản vẽ (nhãn “cả bản vẽ”). **Ứng viên rác** (ngoài tờ, lạc xa, layer rỗng, khối không dùng) chỉ là gợi ý.
- **Bậc** (`gate.py`; hồ sơ công ty khoá `gate:` đổi được): **Chặn** (mặc định đề xuất v0: DH-09, TX-08, VS-06, PR-02)
  phải sửa; **Cảnh báo** bấm Đã xem hoặc Bỏ qua (cần lý do); **Gợi ý** ẩn mặc định.
- **Chốt tờ** khi không còn Chặn và cảnh báo đã xác nhận; máy chủ kiểm lại. Trạng thái và lý do lưu cục bộ
  `.cadguard/sheets/<mã tệp>.json` (không tên người, không tên tệp). Nội dung tờ đổi sau khi chốt → tờ tự mở lại.

## 4. Luồng phòng Kỹ thuật (đã chạy thật trên DXF tổng hợp)

1. Chọn bản vẽ: canvas vẽ LINE, LWPOLYLINE, CIRCLE/ARC (như đường tròn), TEXT/MTEXT (điểm chèn + chữ), INSERT (dấu + tên khối) trong không gian mô hình; khung nhìn bỏ 1% điểm lạc ở mỗi phía; tối đa 15.000 đối tượng. Không có hình thì khung trống kèm lý do.
2. **Quét bản vẽ này**: chạy lần lượt mọi chuẩn của phòng; tab Lỗi gom theo mức E → W → I, mỗi nhóm có số thứ tự; nhóm có handle nằm trên hình được **đánh dấu số trên canvas** (vòng + số, bấm thẻ lỗi thì phóng tới vị trí); nhóm không có vị trí (bảng layer, kiểu chữ, khung tên) ghi rõ. Bấm mã luật → ngăn giải thích (tham số đang áp, nguồn, tài liệu chuẩn). Thẻ có handle hoặc layer có nút **Tới trong AutoCAD**: ghi `.cadguard/goto.txt`, rồi (Windows, AutoCAD bản đầy đủ) đưa thẳng AutoCAD tới và chọn đối tượng qua COM; không được thì gõ `CGDEN` trong AutoCAD (`docs/autocad.md` mục 6; tắt COM bằng `--no-autocad-com`). API: `POST /api/autocad/show` `{file, handles, layers}`.
3. **Làm sạch**: “Sửa các lỗi tự sửa được” → tab Thay đổi liệt kê thao tác VS-* (tick chọn, chọn layer/kiểu chữ đích, dòng − trước / + sau) → **Xem trước** (chạy khô: luật hết/giảm/xuất hiện mới, các mục tự kiểm) → **Duyệt & lưu tệp mới** (hộp xác nhận) → tệp `.cg-….dxf` mới, tệp gốc không đổi mã băm; app quét lại tệp mới, đánh dấu nhóm “Đã sửa” (vòng xanh), bật **Trước/Sau** → **Bỏ bản mới (hoàn tác)** có xác nhận.
4. **Gói bàn giao**: ghi chú bàn giao sinh từ dữ liệu (chuẩn, số lỗi còn lại, luật đã sửa), nút Sao chép; **Đánh dấu sẵn sàng bàn giao** chỉ bật khi đã quét đủ chuẩn của phòng **đúng nội dung tệp hiện tại** và hết lỗi mức E. Đánh dấu chỉ ghi lịch sử cục bộ; **không gửi tệp đi đâu**. Phòng nhận thấy bản đó ở “Nhận từ phòng …”.
5. **Trò chuyện**: nút gợi ý (quét, bản vẽ có gì, giải thích lỗi, sửa, soạn bàn giao) là công cụ cad-guard tất định, ghi rõ “không qua mô hình AI”; câu hỏi tự do đi tới engine thật (ẩn danh Bậc 1), trợ lý chỉ đề xuất changeset khi bật công tắc, áp dụng luôn do người bấm.

Phòng Thiết kế 3D: dựng 3D tất định (`scene`, như `cadguard scene`) ở chế độ **chỉ xem** (kéo xoay, cuộn phóng); tab Lỗi ghi “Luật kiểm 3D đang phát triển”.

## 5. Kết nối AI trên giao diện

- **CLI** (Claude Code, Codex, Antigravity): đã cài? phiên bản, đã đăng nhập? (kiểm bằng `--version`/lệnh trạng thái như cũ, chỉ dùng mã thoát, không đọc tệp xác thực). Nút **Đăng nhập** mở **cửa sổ terminal mới** chạy lệnh đăng nhập chính thức (`claude auth login`, `codex login`, `agy`); người dùng tự đăng nhập, cad-guard không đọc đầu ra/token. Windows: `cmd.exe /k …` với `CREATE_NEW_CONSOLE`; macOS: Terminal qua `osascript`; Linux: `x-terminal-emulator`/`gnome-terminal`/`konsole`/`xterm`. **Kiểm lại** chạy lại phần kiểm. Chưa cài: chỉ hiện hướng dẫn cài dạng chữ (không link tải). Điều khoản tóm tắt từ `engine_infos`.
  - Codex: công tắc **Bật chế độ thử nghiệm** (hộp xác nhận điều khoản), lưu trong cấu hình.
  - Antigravity: chọn loại tài khoản **Doanh nghiệp** / **Khoá API**; chọn “Tài khoản Google cá nhân” bị từ chối kèm lý do (FAQ + điều khoản mục 6). Nút Đăng nhập chỉ bật với tài khoản doanh nghiệp.
- **Khoá API** (Anthropic, OpenAI, Gemini, OpenRouter, Ollama): ô `type=password autocomplete=off`, **Lưu/Đổi**, **Xoá**, **Kiểm tra**, ô **Mô hình** mặc định. OpenRouter mặc định tắt, có công tắc + cảnh báo bên thứ ba (ô khoá tắt khi chưa bật). Ollama: chỉ địa chỉ cục bộ (`localhost`/`127.0.0.1`/`[::1]`), không khoá.
- **Trợ lý mặc định**, **Mức dữ liệu** (hiển thị trạng thái thật: Bậc 1 mặc định; Bậc 2 chỉ bằng `--no-anonymize`; Bậc L = chọn Ollama), **Giới hạn chi phí** mỗi phiên (USD, truyền `max_cost_usd` vào engine API; CLI tự giới hạn theo gói).

## 6. An toàn

- **Chỉ máy này**: nghe `127.0.0.1`, cổng ngẫu nhiên; không CORS (`OPTIONS` bị từ chối).
- **Mã phiên** 32 byte; mọi `/api/*` cần `X-CadGuard-Token` (so sánh hằng thời gian); giao diện đọc mã từ địa chỉ rồi xoá khỏi thanh địa chỉ. Máy chủ không ghi nhật ký truy cập.
- **Chống DNS rebinding**: `Host` phải là `127.0.0.1:<cổng>`/`localhost:<cổng>`; `Origin` (nếu có) cùng nguồn. API chỉ nhận `application/json`.
- **CSP** `default-src 'none'; script-src 'self'; style-src 'self'; …`: không tài nguyên ngoài, không mã/kiểu nội tuyến; `nosniff`, `no-referrer`, `X-Frame-Options: DENY`, `no-store`. Dữ liệu chèn bằng `textContent`/`createElement` (test kiểm không có `innerHTML`, không `on…=`, không `style=`, không URL ngoài).
- **Đường dẫn**: trình duyệt chỉ gửi đường dẫn tương đối; mọi đường dẫn qua `agent/workspace.py` của dự án **hiện tại**. Thông báo lỗi không chứa đường dẫn tuyệt đối. Ngoại lệ có chủ đích: màn chọn dự án hiển thị đường dẫn các dự án gần đây (người dùng tự chọn).
- **Khoá API** chỉ đi một chiều: POST JSON (≤ 4 KB, `provider` + `key`, 8–512 ký tự in được) tới 127.0.0.1 có mã phiên → `assistant/keys.py` → kho khoá hệ điều hành. Ô nhập bị xoá ngay khi gửi. Máy chủ **không bao giờ trả lại khoá** (mọi phản hồi chỉ có “có/không, nguồn”), không ghi tệp/log; không có API GET nào tới khoá (test: GET `/api/ai/settings`, `/api/engines`, `/api/session`… không chứa khoá dù kho khoá có). Không có gói `keyring`: từ chối nhận khoá (HTTP 501) và hướng dẫn `pip install cadguard[keyring]`. Biến môi trường vẫn dùng được và được ưu tiên.
- **Kiểm khoá** chỉ khi người dùng bấm: GET danh sách mô hình (Anthropic `/v1/models` với `limit=1`, OpenAI/Gemini `/models`, Ollama `/v1/models`) hoặc thông tin khoá (OpenRouter `/key`): không sinh token. Lỗi không lặp lại khoá.
- **Áp dụng cần người bấm xác nhận** (`confirm: true` kiểu boolean); tệp mới tạo độc quyền, tệp gốc không đổi mã băm; hoàn tác chỉ xoá đúng tệp mới khi mã băm còn khớp.
- **Ẩn danh** mặc định Bậc 1 cho trợ lý; màn hình người dùng dùng tên thật vì không rời máy.
- **Lịch sử quét** `<dự án>/.cadguard/history.jsonl`: chỉ thời điểm, sự kiện (`audit`/`apply`/`undo`/`handover`), mã băm tệp (băm đường dẫn tương đối với muối ngẫu nhiên riêng của dự án, `.cadguard/history.salt`) và mã băm nội dung, phòng, chuẩn, đếm theo mức và theo luật. Không tên tệp, không tên khách, không chữ, không đường dẫn; tên chỉ được đổi lại trên máy này bằng cách băm lại danh sách tệp. Không gửi đi đâu.

## 7. API (cho nhà phát triển)

Mọi API trả JSON tiếng Việt (`{"error": "…"}` khi lỗi), cần header mã phiên. API dữ liệu trả 409 khi chưa mở dự án.

| Phương thức | Đường | Việc |
| --- | --- | --- |
| GET | `/api/session` | dự án (tên), hồ sơ, chế độ dữ liệu, cờ hiệu lực, phòng, chuẩn, có hộp thoại không |
| GET | `/api/projects` | dự án gần đây + hiện tại |
| POST | `/api/project/pick` | mở hộp thoại chọn thư mục → `{path}` / `{cancelled}` / `{unavailable}` |
| POST | `/api/project/open` | `{path, confirm?}` → `{opened, session}` hoặc `{needs_confirm, warning}` |
| POST | `/api/project/forget` | `{path}` bỏ khỏi dự án gần đây |
| POST | `/api/project/profile/pick`, `/api/project/profile` | chọn tệp hồ sơ; `{path|null}` áp/bỏ hồ sơ cho dự án |
| GET | `/api/drawings` | DXF của dự án (tương đối, có trần) |
| POST | `/api/audit` | `{file, standard, dept?}` → kết quả theo E/W/I (handle mẫu tối đa 20/mục); ghi lịch sử |
| POST | `/api/audit_all` | `{standard, dept?}` |
| POST | `/api/sheets` | `{file}` → chỉ mục tờ `cg.structure/1` + trạng thái chốt từng tờ |
| POST | `/api/sheets/lock`, `/api/sheets/unlock` | `{file, sheet, standards, confirm}` chốt tờ (409 nếu còn Chặn/cảnh báo chưa xác nhận) / mở lại |
| POST | `/api/findings/ack` | `{file, standard, rule_id, sheet|"*", kind: seen|skip, reason, undo?}` xác nhận cảnh báo |
| POST | `/api/geometry` | `{file}` → hình xem trước (toạ độ khung SVG) |
| POST | `/api/scene` | `{file}` → hộp 3D (chỉ xem) |
| POST | `/api/handover` | `{file, dept}` → đánh dấu sẵn sàng bàn giao (409 nếu chưa quét/còn lỗi E) |
| GET | `/api/home` (tham số `dept`), `/api/overview` | số liệu Việc của tôi / Tổng quan từ lịch sử |
| GET | `/api/explain`, `/api/rules` | giải thích luật / bảng luật (chỉ đọc) |
| POST | `/api/summary` | tóm tắt mô hình |
| POST | `/api/changeset/suggest`, `/api/changeset/propose`, `/api/changeset/apply`, `/api/changeset/undo` | như bản trước |
| GET | `/api/changeset`, `/api/changesets` | một / danh sách changeset |
| GET | `/api/engines` | engine + trạng thái (không khoá); `refresh=1` kiểm lại CLI |
| GET/POST | `/api/ai/settings` | cấu hình trợ lý (không khoá) / cập nhật (`default_engine`, `max_cost_usd`, `codex_experimental`, `agy_account`, `allow_openrouter`, `ollama_base_url`, `models`) |
| POST | `/api/ai/key`, `/api/ai/key/delete`, `/api/ai/key/test` | lưu / xoá / kiểm khoá (không bao giờ trả khoá) |
| POST | `/api/ai/cli/login` | `{engine}` → mở cửa sổ đăng nhập CLI |
| POST | `/api/chat`, `/api/chat/stop` | như bản trước (luồng NDJSON) |

## 8. Giới hạn và chỗ chưa chắc

- Xem trước bản vẽ chỉ là bản định vị: không vẽ nội dung khối, kích thước, hatch, chiều cao chữ thật; ARC vẽ thành đường tròn; chỉ không gian mô hình. Lỗi trên tờ (layout) hoặc trong bảng định nghĩa không có vị trí trên hình.
- Thao tác sửa tự động chỉ có cho luật `VS-*` trong từ vựng; luật `furniture-v0` phải sửa trong phần mềm CAD.
- “Trưởng phòng đã duyệt”, “báo luật sai”, độ chính xác luật và sửa luật (mục 9b) trong bản mẫu chưa có dữ liệu thật nên không hiện số; chỗ đó ghi “Chưa đo”/trạng thái rỗng.
- Chỉ một hồ sơ kết nối mỗi engine trên giao diện (cấu trúc đã cho phép nhiều).
- Hộp thoại tkinter trên Windows có thể mở phía sau trình duyệt. Mở terminal đăng nhập trên Linux phụ thuộc chương trình terminal có sẵn.
- Đã kiểm bằng test (engine, kho khoá, hộp thoại, `subprocess` đều giả) và bằng mắt trong trình duyệt trên DXF tổng hợp; **chưa** chạy với mô hình thật, chưa bấm Đăng nhập CLI thật, chưa lưu khoá thật.


## Preview và hồ sơ duyệt

Preview mới dựng SVG bằng ezdxf, có chọn layout, cache, hình dự phòng và bố cục điện thoại. Nút **Hồ sơ duyệt** mở ghi chú hai chiều, phiên bản, chốt thiết kế và duyệt sản xuất. Xem [hướng dẫn hồ sơ/Tailscale](review.md). Không gửi mã phiên quản trị cho khách.


## Toàn bộ ứng dụng trên thiết bị riêng qua Tailscale

Để dùng chính phiên app đang chạy trên máy chủ, chạy gateway riêng (không khởi động app thứ hai):

```powershell
python -m cadguard.app.remote --origin https://<máy>.<tailnet>.ts.net:10000 --login <email-chủ> --upstream 8780 --port 8782
tailscale serve --bg --https=10000 http://127.0.0.1:8782
```

Chọn cổng HTTPS còn trống, giữ các proxy Serve khác. Trên thiết bị khác, đăng nhập Tailscale bằng đúng tài khoản chủ và mở origin trên với `?t=` là mã phiên app in ra terminal. Không ghi mã phiên vào tệp cấu hình. Gateway không chèn token: API vẫn yêu cầu mã phiên gốc. Khởi động lại app làm mã cũ hết hiệu lực.

Đây là quyền đầy đủ của chính chủ, gồm mở dự án, cấu hình AI và thao tác changeset có xác nhận; không gửi link này cho khách. Khách dùng cổng hồ sơ duyệt riêng. Hộp thoại chọn thư mục, nếu được gọi, xuất hiện trên máy chủ; thiết bị từ xa có thể dùng ô nhập đường dẫn dự án trên máy chủ.

Gateway chỉ nghe localhost, kiểm chính xác Host/Origin và `Tailscale-User-Login` do Serve cung cấp, rồi đổi Host/Origin hợp lệ về localhost cho app. Không mở backend ra LAN, không nhận upstream URL tùy ý, không bật CORS hoặc Funnel. Phần mềm khác trên cùng máy chủ thuộc ranh giới tin cậy cục bộ. Chat NDJSON được chuyển tiếp ngay từng đoạn. Khi dừng chia sẻ, dừng gateway và `tailscale serve --https=10000 off` (chỉ cổng dành cho app riêng).

Có thể dùng `python scripts/share_app.py start|status|stop` tại gốc repo để chạy nền ẩn và kiểm tra đúng tiến trình. Mặc định dùng cổng HTTPS 10000, proxy localhost 8782 tới app 8780, chỉ tài khoản Tailscale đang đăng nhập làm chủ. Metadata PID/origin không chứa token; script không đọc bản vẽ.


## Truy cập từ Internet bằng mật khẩu (không cần Tailscale ở thiết bị khách)

Cổng mật khẩu là phương án dành cho chính chủ dùng toàn bộ app. Tailscale chỉ cần cài/đăng nhập ở máy chủ. Máy chủ và app gốc phải tiếp tục chạy. Đây là quyền quản trị đầy đủ; khách hàng thảo luận hồ sơ dùng cổng duyệt riêng.

Cần phụ thuộc tùy chọn `keyring` (`pip install -e .[keyring]`). Mã phiên app hiện tại được lưu qua `assistant/keys.py` vào kho khóa hệ điều hành dưới tên bí mật cục bộ `web-app-token`, tách khỏi nhà cung cấp AI. Không đặt mã phiên hoặc mật khẩu trong đối số lệnh, repo, tệp cấu hình hay nhật ký. Người vận hành cập nhật bí mật này khi khởi động app với mã mới.

Từ gốc repo:

```powershell
python scripts/share_web.py start
# Tự mở http://127.0.0.1:8784 trên máy chủ và đặt mật khẩu.
python scripts/share_web.py publish
python scripts/share_web.py status
python scripts/share_web.py stop
```

`start` chỉ chạy gateway ở localhost 8783 và trang thiết lập ở localhost 8784, chưa bật Funnel. Trang thiết lập là máy chủ riêng không được proxy ra Internet, có kiểm Host, Origin và nonce. Người dùng tự nhập/đổi mật khẩu; verifier PBKDF2-HMAC-SHA256 (salt 32 byte, 600.000 vòng) lưu qua `assistant/keys.py` trong kho khóa Windows. Không lưu mật khẩu gốc. Mật khẩu từ 14 đến 256 ký tự; có thể dùng câu dài dễ nhớ.

`publish` chỉ được chạy khi đã có verifier. Nó đổi cổng 10000 từ Serve riêng của chủ sang Funnel trỏ gateway mật khẩu, giữ các cổng 443/8443 khác. Nếu Tailscale yêu cầu bật quyền Funnel, người dùng tự xác nhận tại trang quản trị Tailscale. Script không tự vượt hộp thoại cấp quyền. Gateway riêng 8782 cũ có thể dừng sau khi kiểm chứng cổng mật khẩu; giữ nó trong thời gian chuẩn bị để có thể quay lại Serve nếu cần.

Link Internet chỉ chứa địa chỉ HTTPS gốc, không cần `?t=`. Sau khi đăng nhập, browser dùng marker `web-session`; gateway chèn mã app thật ở phía máy chủ. Mã app không xuất hiện trong HTML/JS/cookie gửi ra Internet. Token app cũ hay header Tailscale giả không bỏ qua được đăng nhập web.

Cookie opaque có Secure, HttpOnly và SameSite=Strict. Phiên chỉ lưu mã băm trong RAM, tối đa 32 phiên; hết hạn sau 30 phút không hoạt động hoặc 8 giờ tổng cộng. Nút Đăng xuất web thu hồi phiên tại máy chủ. Đổi mật khẩu thu hồi mọi phiên. Khởi động lại gateway yêu cầu đăng nhập lại. Tất cả POST yêu cầu Origin trùng địa chỉ HTTPS; form đăng nhập thêm challenge cookie/CSRF có hạn 5 phút. Tối đa 5 lần thử mỗi địa chỉ/phút và 30 lần toàn cổng/phút; có giới hạn bộ nhớ chống tạo nhiều địa chỉ giả.

Mỗi lần khởi động app gốc với token mới cần cập nhật `web-app-token` trong kho khóa và khởi động lại gateway; không bỏ kiểm token app để chữa lỗi. Không tự mở/quét/công bố bản vẽ khi bật đường truy cập web.

Tham khảo [Tailscale Funnel](https://tailscale.com/docs/features/tailscale-funnel), [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
