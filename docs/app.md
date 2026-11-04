# Giao diện cục bộ `cadguard app`

Ngày viết: 04/11/2026. Mã: `packages/core/cadguard/app/` (máy chủ `server.py`, dữ liệu `api.py`, trợ lý `chat.py`, cấu hình phòng `departments.json`, giao diện `static/`). Test: `packages/core/tests/test_app.py`. Bố cục và màu theo bản mẫu `design/ui-mockup.html` (đã bỏ dữ liệu minh hoạ, nối dữ liệu thật).

Ứng dụng web chạy **trên máy người dùng**, chỉ dùng thư viện chuẩn của Python (`http.server`, `json`) và HTML/CSS/JS thuần (không CDN, không framework, chạy offline). Không thêm phụ thuộc nào.

## 1. Cách mở

```text
cadguard app --workspace <thư mục bản vẽ> [--profile ho-so.yaml] [--port 0] [--no-browser]
             [--no-anonymize] [--experimental] [--allow-openrouter] [--account business|api-key] [--no-detect]
```

- Lệnh in địa chỉ dạng `http://127.0.0.1:<cổng>/?t=<mã phiên>` và tự mở trình duyệt (trừ khi `--no-browser`). Mã phiên là mật khẩu của phiên đó: không gửi cho người khác. Dừng bằng Ctrl+C.
- `--workspace`: thư mục chứa DXF của phiên. Mọi tệp đọc/ghi nằm trong thư mục này (tệp mới do áp dụng sửa ghi cạnh tệp gốc; changeset và nhật ký ở `.cadguard/changesets/`).
- `--profile`: hồ sơ công ty (`cg.company-profile/1`); chỉ áp khi chuẩn đang chọn trùng chuẩn của hồ sơ.
- `--port 0` (mặc định): cổng ngẫu nhiên.
- `--no-anonymize`, `--experimental`, `--allow-openrouter`, `--account`: như `cadguard ask` (xem `docs/assistant.md`); chỉ đặt được khi khởi động, giao diện không có nút bật/tắt.
- `--no-detect`: không chạy `claude`/`codex`/`agy` để kiểm đã cài/đăng nhập (engine CLI hiện "chưa kiểm").

Trong repo (không cài gói): `python scripts/test.py --run -m cadguard app --workspace <thư mục>`.

QC nhanh trên dữ liệu tổng hợp:

```text
python -m cadguard fixtures D:\Tam\ws-qc
python -m cadguard app --workspace D:\Tam\ws-qc --profile standards\company-profile.example.yaml --no-detect
```

## 2. Các phần giao diện

| Phần | Nội dung |
| --- | --- |
| Thanh trên | Ba màn: **Bản vẽ**, **Luật áp dụng**, **Kết nối AI**. Nhãn **Dữ liệu** (Ẩn danh Bậc 1 hoặc cảnh báo đỏ khi `--no-anonymize`), **Hồ sơ** công ty đang áp, chọn **Phòng**, đổi sáng/tối |
| Phòng | Thiết kế → `design-hygiene-v0`; Kỹ thuật và Lập trình sản xuất → `furniture-v0`. Đổi trong `packages/core/cadguard/app/departments.json` (`standard` là tên tệp trong `standards/`, `next` là phòng nhận bàn giao) |
| Cột trái | Danh sách DXF (tệp `.cg-….dxf` do cad-guard tạo có nhãn "bản mới"), chuẩn và hồ sơ của phòng, **Quét cả thư mục** (đếm E/W/I từng tệp; "x/y bản không có lỗi mức E — sẵn sàng bàn giao sang phòng kế") |
| Giữa: Lỗi | Kết quả kiểm nhóm theo mức E/W/I, theo mã luật, có số chỗ, thông điệp, layer, handle mẫu; luật bị bỏ qua (thiếu dữ liệu) thu gọn; bấm mã luật để xem **giải thích** (tham số đang áp, nguồn, đoạn trong tài liệu chuẩn) |
| Giữa: Đề xuất sửa | Từ phát hiện → thao tác gợi ý theo từ vựng cố định (`docs/changeset.md` mục 3), tick chọn, chọn layer/kiểu chữ đích khi cần → **Xem trước** (chạy khô: số đối tượng đổi theo thao tác, diff số liệu, định nghĩa xoá, luật hết/giảm/xuất hiện mới, các mục kiểm) → **Áp dụng (ghi ra tệp mới)** có hộp xác nhận → kết quả kiểm tệp ra + **Hoàn tác (xoá tệp mới)** |
| Giữa: Thay đổi | Mọi changeset trong thư mục làm việc (bạn hoặc trợ lý đề xuất), trạng thái chưa áp/đã áp/đã hoàn tác; mở lại xem trước để áp dụng hoặc hoàn tác |
| Giữa: Tóm tắt | Tóm tắt mô hình bản vẽ (phiên bản DXF, đơn vị, số layer, đối tượng theo loại/không gian, kiểu chữ, layout) |
| Cột phải: Trợ lý | Chọn engine theo hai nhóm **Dùng hạn mức tài khoản (CLI)** và **Dùng API (khoá của bạn)**; engine không dùng được thì mờ kèm lý do (chưa cài, chưa đăng nhập, chưa có khoá, cần `--experimental`, chỉ tài khoản doanh nghiệp, mặc định tắt). Thẻ engine: cách dùng, trạng thái, chi phí tính vào đâu, điều khoản tóm tắt. Ô mô hình (bắt buộc khi engine chưa có mô hình mặc định), công tắc **Cho phép trợ lý đề xuất sửa**, luồng trả lời, thẻ lời gọi công cụ thu gọn, dòng token/chi phí (lượt và cả phiên), nút **Dừng** |
| Luật áp dụng | Chỉ đọc. Luật của chuẩn đang chọn: mã, tên, mức, tình trạng (đang chạy, tắt bởi hồ sơ, chưa cài code), tham số **mặc định → đang áp** (tô màu chỗ hồ sơ ghi đè), tham số chung đã chỉnh; tìm và lọc. Sửa luật theo `plans/cad-guard-agent.md` mục 9b là đề xuất, chưa làm |
| Kết nối AI | Thẻ từng engine (trạng thái, lý do, cách bật, điều khoản), nút **Kiểm lại**, dữ liệu đi đâu, trợ lý được/không được làm gì |

Bàn phím: Tab đi qua mọi nút; mũi tên trái/phải chuyển tab; Enter gửi câu hỏi (Shift+Enter xuống dòng); Esc đóng hộp thoại/ngăn giải thích; hộp xác nhận giữ tiêu điểm trong hai nút.

## 3. An toàn

- **Chỉ máy này**: nghe `127.0.0.1`, cổng ngẫu nhiên. Không CORS (yêu cầu `OPTIONS` bị từ chối, không có header `Access-Control-*`).
- **Mã phiên**: 32 byte ngẫu nhiên mỗi lần chạy; mọi `/api/*` cần header `X-CadGuard-Token` khớp (so sánh hằng thời gian). Giao diện đọc mã từ địa chỉ một lần rồi xoá khỏi thanh địa chỉ (giữ trong `sessionStorage` của thẻ). Máy chủ không ghi nhật ký truy cập.
- **Chống DNS rebinding**: `Host` phải là `127.0.0.1:<cổng>` hoặc `localhost:<cổng>`; `Origin` (nếu có) phải cùng nguồn. API chỉ nhận `Content-Type: application/json`.
- **Header**: `Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self' …` (không tải tài nguyên ngoài, không mã/kiểu nội tuyến), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Cache-Control: no-store`.
- **Đường dẫn**: trình duyệt chỉ gửi đường dẫn **tương đối**; mọi đường dẫn qua `agent/workspace.py` (từ chối `..`, tuyệt đối, ổ đĩa, UNC, ra ngoài thư mục, không phải `.dxf`). Tệp tĩnh theo danh sách cố định. Thông báo lỗi không chứa đường dẫn tuyệt đối.
- **Chống XSS**: dữ liệu chèn bằng `textContent`/`createElement`, không chèn chuỗi HTML; CSP chặn mã nội tuyến.
- **Khoá API không đi qua trình duyệt**: không có ô nhập khoá. Giao diện chỉ thấy "có khoá (biến môi trường / kho khoá hệ điều hành)" hoặc "chưa có khoá" và hướng dẫn `cadguard keys set <nhà cung cấp>`. API không bao giờ trả khoá (test kiểm khi biến môi trường có khoá).
- **Áp dụng cần người bấm xác nhận**: `/api/changeset/apply` chỉ chạy khi thân yêu cầu có `confirm: true` (đúng kiểu boolean) kèm mã changeset; giao diện chỉ gửi sau hộp xác nhận. Tệp mới tạo độc quyền (không ghi đè), tệp gốc không đổi mã băm, kiểm tệp ra không đạt thì không tạo tệp; hoàn tác chỉ xoá đúng tệp mới khi mã băm còn khớp. Mỗi changeset áp một lần.
- **Trợ lý**: chỉ có `propose_changeset` khi bật công tắc "Cho phép trợ lý đề xuất sửa" (gửi `allow_propose: true`); không bao giờ có công cụ áp dụng. Changeset trợ lý đề xuất hiện ở tab Thay đổi, người xem trước và tự áp.
- **Ẩn danh**: mặc định Bậc 1 — trợ lý chỉ thấy mã băm (`F_…`, `L_…`, `B_…`, `S_…`, `Y_…`), không thấy tên layer/tệp/chữ. Tắt chỉ bằng `--no-anonymize` lúc khởi động; giao diện hiện cảnh báo đỏ, không có nút tắt. Màn hình của người dùng (lỗi, xem trước) dùng tên thật vì dữ liệu không rời máy.
- Lịch sử trò chuyện chỉ nằm trong bộ nhớ trang; không ghi ra đĩa. Dừng gửi `CancelToken` cho engine; đóng trang giữa chừng cũng huỷ lượt đang chạy.

## 4. API (cho nhà phát triển)

Mọi API trả JSON tiếng Việt (`{"error": "…"}` khi lỗi) và cần header mã phiên.

| Phương thức | Đường | Việc |
| --- | --- | --- |
| GET | `/api/session` | tên thư mục (không đường dẫn), hồ sơ, chế độ dữ liệu, cờ khởi động, phòng, chuẩn |
| GET | `/api/drawings` | danh sách DXF (đường dẫn tương đối) |
| POST | `/api/audit` | `{file, standard}` → kết quả nhóm theo E/W/I |
| POST | `/api/audit_all` | `{standard}` → đếm từng tệp, số bản sẵn sàng bàn giao |
| GET | `/api/explain` | tham số `rule`, `standard` |
| POST | `/api/summary` | `{file}` |
| GET | `/api/rules` | tham số `standard` → luật, tham số mặc định/đang áp, bật/tắt |
| POST | `/api/changeset/suggest` | `{file, standard}` → thao tác gợi ý (không ghi) |
| POST | `/api/changeset/propose` | `{file, standard, ops, protected_layers?}` → xem trước + mã changeset (ghi JSON changeset, không ghi DXF) |
| GET | `/api/changeset`, `/api/changesets` | một changeset (tham số `id`) / danh sách |
| POST | `/api/changeset/apply` | `{changeset_id, confirm: true}` |
| POST | `/api/changeset/undo` | `{changeset_id, confirm: true}` |
| GET | `/api/engines` | engine + trạng thái (không khoá); tham số `refresh=1` kiểm lại CLI |
| POST | `/api/chat` | `{engine, model?, messages, standard, allow_propose}` → luồng NDJSON: `start`, `text`, `tool_call`, `tool_result`, `usage`, `error`, `done`, (`stopped`), `summary` |
| POST | `/api/chat/stop` | `{run_id}` |

## 5. Giới hạn

- Chưa có trình xem hình bản vẽ (khung giữa là danh sách lỗi/xem trước dạng số liệu); chưa có "gói bàn giao" đầy đủ như bản mẫu, chỉ đếm bản sạch lỗi E khi quét thư mục.
- Thao tác gợi ý chỉ cho luật `VS-*` có trong từ vựng (`VS-01`, `VS-02`, `VS-03`, `VS-04`, `VS-06`, `VS-07`); `VS-05` và các luật `furniture-v0` phải sửa trong phần mềm CAD. Gợi ý `VS-03` không được tick sẵn (người dùng phải chọn đúng layer đích); gộp layer dư `VS-01` còn đối tượng chỉ tick sẵn khi có layer cùng tên gốc.
- Tab Luật áp dụng chỉ đọc; sửa luật/ngưỡng là sửa hồ sơ công ty hoặc tạo phiên bản chuẩn mới rồi khởi động lại.
- Một phiên = một thư mục làm việc và một hồ sơ; đổi thì khởi động lại. Máy chủ một người dùng, không đăng nhập nhiều người.
- Kiểm CLI (`claude --version`, `claude auth status`…) chạy khi mở màn và khi bấm Kiểm lại, có thể mất vài giây; `--no-detect` để bỏ.
- Engine CLI chạy mỗi lượt một tiến trình mới (giới hạn và điều khoản như `docs/assistant.md`); chi phí hiển thị là số engine báo hoặc cad-guard ước tính, không phải hoá đơn.
- Đã kiểm bằng test (engine giả) và bằng mắt trong trình duyệt với engine giả; **chưa** chạy với mô hình thật trong giao diện.
