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
| Bản vẽ | Cột trái: bản vẽ (tệp mới `.cg-….dxf` hiện dưới tệp gốc, nhãn “Bản mới”), chuẩn của phòng, luật chạy, hồ sơ, **Quét cả thư mục**. Giữa: **xem trước bản vẽ** (SVG từ hình học trong mô hình), thu phóng/kéo, **Trước/Sau** sau khi lưu tệp mới. Phải: tab **Trợ lý**, **Lỗi**, **Thay đổi** |
| Tổng quan | Số tổng hợp 7 ngày từ lịch sử trên máy: bản đã quét, lỗi E đang mở, tỉ lệ đề xuất được áp dụng, bản đánh dấu bàn giao; bàn giao giữa phòng; luật vi phạm nhiều nhất; độ tin cậy luật (“Chưa đo” cho tới khi có đo độ chính xác P1c) |
| Luật áp dụng | Chỉ đọc. Luật của mọi chuẩn kèm phòng áp dụng (từ `departments.json`), tham số mặc định → đang áp (hồ sơ), tình trạng; thẻ theo phòng và “Chưa cài code” để lọc; ngăn chi tiết luật; phiên bản đang dùng. Sửa luật (mục 9b) chưa làm |
| Kết nối AI | Mục 5 |

Phòng (`departments.json`, dạng `cg.app-departments/2`): mỗi phòng có `standards` (nhiều chuẩn), `next` (nhiều phòng nhận), `role`, `priority`, `view`. Kỹ thuật = `design-hygiene-v0` + `furniture-v0` (mặc định, ưu tiên khảo sát); Thiết kế = `design-hygiene-v0`; Lập trình sản xuất = `furniture-v0`; Thiết kế 3D = xem 3D (`view: scene`).

## 4. Luồng phòng Kỹ thuật (đã chạy thật trên DXF tổng hợp)

1. Chọn bản vẽ: canvas vẽ LINE, LWPOLYLINE, CIRCLE/ARC (như đường tròn), TEXT/MTEXT (điểm chèn + chữ), INSERT (dấu + tên khối) trong không gian mô hình; khung nhìn bỏ 1% điểm lạc ở mỗi phía; tối đa 15.000 đối tượng. Không có hình thì khung trống kèm lý do.
2. **Quét bản vẽ này**: chạy lần lượt mọi chuẩn của phòng; tab Lỗi gom theo mức E → W → I, mỗi nhóm có số thứ tự; nhóm có handle nằm trên hình được **đánh dấu số trên canvas** (vòng + số, bấm thẻ lỗi thì phóng tới vị trí); nhóm không có vị trí (bảng layer, kiểu chữ, khung tên) ghi rõ. Bấm mã luật → ngăn giải thích (tham số đang áp, nguồn, tài liệu chuẩn).
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
