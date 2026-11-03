# Các bước tiếp theo (từng bước, cho người mới)

Cập nhật 03/11/2026. Làm theo thứ tự. Mọi lệnh gõ trong **PowerShell** (nhấn phím Windows, gõ `PowerShell`, Enter). Gặp lỗi: copy nguyên thông báo, dừng lại và hỏi; đừng thử lệnh có `--force`.

| # | Việc | Ai | Mất khoảng | Cần xong trước |
| --- | --- | --- | --- | --- |
| 1 | Chạy `bootstrap.ps1` (kiểm lõi chạy được trên Windows) | Bạn | 10 phút | — |
| 2 | Đăng ký cad-guard vào MCA | Bạn + MCA | 20 phút | 1 |
| 3 | Dựng thư mục dữ liệu **ngoài repo**, khảo sát P0, thu bản vẽ mẫu | Bạn + phòng kỹ thuật | 1–2 tuần (song song) | — |
| 4 | Giao 3 brief cho MCA: M4 → J0–J2 → Y0 | Bạn + MCA | mỗi brief vài giờ | 2 (brief 1 cần cad-guard đã đăng ký để kiểm) |

Bước 3 và bước 4 chạy song song được: MCA làm việc trong lúc bạn đi khảo sát.

---

## 1. Chạy `bootstrap.ps1`

Script này cài lõi cad-guard vào một môi trường riêng (`packages\core\.venv`), chạy 31 test, quét 5 bản vẽ DXF tổng hợp và ghi `report.html`. Nó **không** đụng tới bản vẽ thật và không đưa gì lên mạng ngoài việc tải thư viện Python.

### 1.1 Kiểm Python (cần 3.10 trở lên)

```powershell
python --version
```

- Thấy `Python 3.10.x` trở lên: sang 1.2.
- Báo "Python was not found" hoặc **mở Microsoft Store**: cài Python từ `python.org/downloads`, **tick "Add python.exe to PATH"** ở màn hình cài, rồi đóng PowerShell, mở lại, gõ lại lệnh trên. Nếu vẫn mở Store: Settings → Apps → Advanced app settings → App execution aliases → tắt `python.exe` và `python3.exe`.

### 1.2 Chạy

```powershell
cd D:\Projects\cad-guard
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
```

`-ExecutionPolicy Bypass` chỉ áp dụng cho lần chạy này, không đổi cài đặt máy.

### 1.3 Kết quả đúng (theo lần chạy thử của mình trong môi trường cloud)

1. Hiện chữ chạy của `pip` (tải ezdxf, pydantic, pyyaml, pytest). Lần đầu mất 1–3 phút.
2. Dòng chấm và `31 passed`. (Số giây khác nhau tuỳ máy.)
3. `Đã ghi báo cáo: ...\report.html`.
4. `Xong. Mở file report.html ...` (màu xanh).
5. Dòng cuối là JSON: `{"rules_implemented": 16, "drawings_audited_7d": 5}`.

Mở `D:\Projects\cad-guard\report.html` bằng trình duyệt: bạn sẽ thấy các lỗi mà 4 bản vẽ "xấu" được cố ý làm sai (bản `ok_sheet` phải sạch).

> Lệnh `audit` trả mã thoát 1 khi có lỗi mức E. Với bản vẽ tổng hợp "xấu" điều đó là **đúng**, không phải sự cố. Script vẫn chạy tiếp.

### 1.4 Lỗi thường gặp

| Thông báo | Nghĩa là | Cách xử |
| --- | --- | --- |
| `Chưa có Python...` / `Cần Python 3.10 trở lên.` | Xem 1.1 | Cài/nâng Python |
| `SSL: CERTIFICATE_VERIFY_FAILED` hoặc `Could not fetch URL` lúc `pip install` | Mạng công ty chặn hoặc chèn chứng chỉ | Thử mạng khác (4G); không tắt kiểm chứng chứng chỉ |
| `Test không qua` | Có test trượt | Copy phần cuối của kết quả và hỏi |
| `running scripts is disabled` | Chính sách chạy script | Dùng đúng lệnh có `-ExecutionPolicy Bypass` ở 1.2 |
| `.venv` hỏng sau khi nâng Python | Môi trường cũ không còn khớp | Đóng mọi cửa sổ dùng nó, đổi tên thư mục `.venv` thành `.venv-cu`, chạy lại script |

### 1.5 Kiểm repo vẫn sạch

```powershell
git status
```

Phải thấy `nothing to commit, working tree clean`: `.venv`, `report.html` đã nằm trong `.gitignore`. Nếu thấy tệp lạ, **dừng** (xem mục 8 của `docs/guides/github-tu-dau.md`).

---

## 2. Đăng ký cad-guard vào MCA

Đã có sẵn: `scripts\metrics.mjs` trong repo (đọc số thật từ `stats`), `.gitignore` đã chặn `.mca/`. Chi tiết dài nằm ở `docs/guides/cad-guard-bootstrap.md` mục 3–7; dưới đây là đường ngắn nhất.

### 2.1 Kiểm MCA sẵn sàng

```powershell
mca --version
mca doctor
mca org check
```

- Ba lệnh phải chạy được, không báo lỗi bắt buộc.
- Điều lệ cad-guard dùng hai phòng **dev** và **quality**. Phòng `quality` trong sơ đồ mẫu có thể đang tắt: nếu `mca venture check` sau này báo "phòng chưa bật/thiếu trưởng phòng", bật nó ở màn **Nhân viên** trên web, hoặc:

```powershell
mca org build --dept quality "bật phòng chất lượng"
mca org check
```

### 2.2 Đăng ký bằng trò chuyện (Cách A) — dán nguyên văn

```powershell
mca venture init D:\Projects\cad-guard "cad-guard: trợ lý kiểm tra và chuẩn hoá bản vẽ nội thất cho doanh nghiệp sản xuất nội thất (tủ bếp, tủ áo, văn phòng). Định dạng làm việc chung là DXF, không phụ thuộc phần mềm CAD. Khách hàng: phòng kỹ thuật và thiết kế sản xuất của nhà máy nội thất. Giai đoạn: building, đang khảo sát và làm lõi kiểm tra tất định. Chỉ số chính (north star): rules_implemented, mục tiêu 30 luật trước 31/01/2027. Chỉ số phụ: drawings_audited_7d, confirmed_defects_7d, false_positive_pct, rule_precision_pct, suggestion_accept_pct, rework_incidents_7d, active_drafters_7d. Dùng đúng các mã chỉ số này. Nguồn số liệu: lệnh node scripts/metrics.mjs (in JSON từ python -m cadguard stats --json) và thư mục .mca/signals cho tệp thả vào. Phòng tham gia: dev và quality. Ngân sách khoảng 2 triệu token mỗi tuần. Tự chủ mức propose (kế hoạch họp chờ tôi duyệt). Quy tắc cấm: không đưa bản vẽ thật của khách (.dwg/.dxf) vào repo, brief của agent hay prompt; không sửa luật của chuẩn mà không tạo phiên bản chuẩn mới kèm số liệu; không bật cảnh báo thời gian thực cho luật chưa đo độ chính xác; không gửi dữ liệu theo từng thợ vẽ, chỉ số tổng hợp."
```

MCA đọc repo rồi hỏi tối đa 5 câu một lượt. Trả lời ngắn gọn, đúng sự thật; chỗ không biết cứ ghi "chưa biết":

```powershell
mca venture reply <mã phiên> "<câu trả lời của bạn>"
mca venture draft <mã phiên>        # xem bản nháp hồ sơ
```

**Kiểm bản nháp** (đây là bước quan trọng nhất, đọc kỹ trước khi `apply`):

- `id: cad-guard`; phòng `dev` và `quality`; `autonomy: propose`.
- `north_star` là `rules_implemented`, mục tiêu 30, hạn 2027-01-31.
- Hai nguồn: một `cmd` chạy `node scripts/metrics.mjs`, một `file` ở `.mca/signals`.
- Phần cấm (`guardrails`) có đủ 4 ý ở trên. Thiếu thì `mca venture reply` yêu cầu bổ sung.

Hài lòng thì:

```powershell
mca venture apply <mã phiên>
mca venture check cad-guard
```

`check` không còn dòng lỗi là được (cảnh báo thì đọc rồi bỏ qua được). Nếu ra lỗi, copy nguyên văn gửi mình.

> Phương án dự phòng (Cách B): viết tay `D:\Projects\cad-guard\.mca\charter.yaml` rồi `mca venture check/add/migrate` — mẫu đầy đủ ở `docs/guides/cad-guard-bootstrap.md` mục 3. Cách B không tốn token, nhưng phải tự gõ đúng cú pháp.

### 2.3 Kiểm hai đường tín hiệu chạy thật

```powershell
mca signal add cad-guard --metric rules_implemented --value 16
mca signals cad-guard --since 1d
```

Phải thấy dòng `rules_implemented 16 count · manual`. Rồi mở web MCA → **Startup → cad-guard** → bấm **Thu tín hiệu**: nguồn `cadguard-stats` phải sinh số thật (16).

### 2.4 Bật vận hành (làm khi đã chắc ở 2.3)

```powershell
mca daemon
mca venture review cad-guard
mca venture status cad-guard
```

Vì `autonomy: propose`, kế hoạch của cuộc họp **chờ bạn duyệt**: `mca approve <việc gốc>` hoặc `mca reject <việc gốc> "<lý do>"`. Hai tuần đầu cứ để `propose`.

> Lưu ý: nguồn `cmd` hiện chạy với toàn bộ môi trường của daemon (M4 sửa việc này ở bước 4 bên dưới). Vì vậy **không bao giờ** đặt token vào `scripts\metrics.mjs`. Script hiện tại chỉ cần `PATH` nên an toàn.

---

## 3. Thiết lập P0: khảo sát và thu bản vẽ mẫu (ngoài repo)

Nguyên tắc cứng: **bản vẽ thật không bao giờ vào repo, brief của agent hay prompt.** Phần khảo sát có tên khách cũng để ngoài repo.

### 3.1 Dựng thư mục dữ liệu (một lần)

```powershell
New-Item -ItemType Directory -Force D:\CadGuardData\samples\raw, D:\CadGuardData\samples\anon, D:\CadGuardData\reports, D:\CadGuardData\private | Out-Null
Set-Content -Path D:\CadGuardData\samples\index.csv -Encoding utf8 -Value "ma,phan_mem,ban,co_dxf_goc,ghi_chu"
Copy-Item D:\Projects\cad-guard\docs\discovery.md D:\CadGuardData\private\discovery-dien.md
```

| Thư mục | Để gì |
| --- | --- |
| `samples\raw` | Bản gốc nhận từ phòng kỹ thuật, **chưa ẩn danh**. Không cho công cụ nào đọc |
| `samples\anon` | Bản đã ẩn danh, đặt tên `K1-001.dxf`, `K1-002.dxf`… Chỉ thư mục này mới đem đi quét |
| `reports` | Báo cáo `audit` (có tên tệp, nên không đưa vào repo) |
| `private` | Phiếu khảo sát bản **điền thật** (`discovery-dien.md`) và văn bản đồng ý về dữ liệu |

Đừng đặt `D:\CadGuardData` trong thư mục đồng bộ đám mây công khai (Google Drive chia sẻ, OneDrive…). Sao lưu theo quy định của công ty.

### 3.2 Buổi khảo sát với trưởng phòng kỹ thuật (1 buổi, khoảng 1–2 giờ)

Mở `D:\CadGuardData\private\discovery-dien.md` và điền trực tiếp trong buổi gặp:

1. **Mục 1:** bảng kiểm kê phần mềm CAD theo bộ phận (Kỹ thuật, Thiết kế sản xuất, Diễn họa, Xưởng/CNC, Mua hàng) + 7 câu hỏi bổ sung. Hai câu giá trị nhất: *phần mềm nào thay AutoCAD, khi nào* và *xưởng/CNC nhận định dạng gì*.
2. **Mục 3:** ít nhất 20 sự cố thật (lỗi gì, ở khâu nào, ai phát hiện, tốn bao nhiêu giờ/tiền/vật tư). Sau đó xếp hạng 10 lỗi đắt nhất = tần suất × chi phí. Đây quyết định luật nào làm trước.
3. **Mục 4:** xin chữ ký/văn bản đồng ý về dữ liệu (cất trong `private`).

Tin nhắn gợi ý gửi trưởng phòng kỹ thuật để hẹn:

> Anh/chị ơi, em đang thử một công cụ tự động kiểm bản vẽ trước khi xuống xưởng (bắt lỗi layer, khung tên, kích thước…). Em xin 1–2 giờ để nghe anh/chị kể về phần mềm đang dùng và những lỗi bản vẽ tốn kém nhất. Em cũng xin 30–50 bản vẽ đại diện (cả bản tốt lẫn bản từng gây lỗi) — em sẽ ẩn danh trước khi dùng, chỉ xử lý trên máy công ty, không gửi ra ngoài.

### 3.3 Thu bản vẽ mẫu

1. Xin **30–50 bản** đại diện: tủ bếp, tủ áo, văn phòng, chi tiết; cả bản tốt và bản từng gây lỗi. Bỏ vào `samples\raw`.
2. Nếu phần mềm gốc xuất được DXF thì xin **cả hai**: DWG (hoặc định dạng gốc) và DXF xuất từ chính phần mềm đó. Việc so hai đường này nằm ở `docs/accuracy-p1.md`.
3. Ghi mỗi tệp vào `samples\index.csv`: mã (K1…), phần mềm, bản, có DXF gốc không, ghi chú. Mở bằng Excel được.
4. Chỉ nhận bản đã được người có thẩm quyền đồng ý (mục 4 phiếu khảo sát).

### 3.4 Ẩn danh (bắt buộc trước khi quét)

Làm bởi người kỹ thuật biết phần mềm đó (hoặc cùng bạn), trên bản **sao** — không sửa bản gốc. Xoá hoặc thay: tên khách, địa chỉ, số điện thoại, tên dự án thật, tên người vẽ/kiểm/duyệt trong khung tên và thuộc tính, logo, ghi chú có tên riêng, đường dẫn xref tuyệt đối. Đổi tên tệp thành `K1-001.dxf`. **Giữ nguyên** cấu trúc layer, kiểu chữ, kích thước, khối, layout (để luật còn ý nghĩa). Kết quả đặt vào `samples\anon`.

### 3.5 Đổi sang DXF (cad-guard hiện chỉ đọc DXF)

- Phần mềm gốc xuất được DXF: dùng nó (ưu tiên, độ trung thực cao nhất).
- Chỉ có DWG: mở trong AutoCAD (bản dùng thử) rồi lưu thành DXF (lệnh `DXFOUT` hoặc Save As → DXF; mình chưa kiểm menu của bản dùng thử, xem thực tế trên máy bạn). Ghi vào ghi chú những bản mở lỗi hoặc thiếu font.
- **Mẹo:** chỉ bắt đầu bản dùng thử AutoCAD khi `samples\raw` đã đủ bản để mở một lượt — hạn dùng thử chạy từ ngày kích hoạt. Ghi ngày bắt đầu/hết hạn ở mục 6 phiếu khảo sát và đọc điều khoản dùng thử về dữ liệu của khách trước khi mở bản vẽ thật.

### 3.6 Quét thử trên bản đã ẩn danh

```powershell
cd D:\Projects\cad-guard\packages\core
.venv\Scripts\python -m cadguard audit D:\CadGuardData\samples\anon --out D:\CadGuardData\reports\p0.html
```

Mở `p0.html`. Với mỗi lỗi, nhờ người kỹ thuật cho biết: **lỗi thật** hay **báo nhầm**; cái nào họ đã biết hay bỏ sót. Ghi vào `docs/accuracy-p1.md` (bảng "Đúng / Sai / Bỏ sót" — chỉ ghi số và mã luật, không ghi tên khách). Đừng bật cảnh báo thời gian thực cho luật nào cho tới khi đo xong.

### 3.7 Kết luận P0

Điền mục 5 và mục 7 của phiếu khảo sát, rồi gửi mình **bản tóm tắt đã ẩn danh** (không có tên khách, không đường dẫn): phần mềm CAD chuẩn, tính năng cần thật sự, 10 luật làm trước. Từ đó chuẩn v0 → v0.1 và quyết định có cần hướng plugin theo phần mềm cụ thể hay không.

---

## 4. Giao 3 brief cho MCA theo thứ tự M4 → J0–J2 → Y0

Quy tắc chung cho cả ba brief (mỗi brief **một** lệnh `mca ceo`):

1. Mở PowerShell ở repo MCA và **kiểm sạch**:

   ```powershell
   cd D:\Projects\multi-coding-agents
   git status
   ```

   Phải là `nothing to commit, working tree clean` và nhánh `main`. (Tệp zip trong `Claude outputs/` đã được loại trừ nên không hiện.)
2. Dán lệnh `mca ceo "…"` của brief.
3. Đợi kế hoạch. `autonomy: propose` thì duyệt:

   ```powershell
   mca inbox                          # tìm mã việc gốc
   mca approve <việc gốc>
   ```

   Muốn từ chối: `mca reject <việc gốc> "<lý do>"`. Nếu không thấy mã trong `mca inbox`, xem web MCA hoặc chạy `mca --help` để tìm lệnh liệt kê việc.
4. Khi MCA báo xong, nhận kết quả ở nhánh `mca/*`:

   ```powershell
   mca accept
   ```

5. **Chạy lệnh kiểm của brief** (bảng dưới). Chỉ coi là xong khi xanh.
6. Push `main` bằng GitHub Desktop (nút **Push origin**) — MCA không bao giờ tự push.
7. Chỉ khi brief này xong mới giao brief kế tiếp.

| Brief | Lệnh kiểm sau `mca accept` |
| --- | --- |
| 01 — M4 | `npx vitest run test/venture/collect-env.test.ts test/quality/lesson-scope.test.ts` |
| 02 — J0–J2 | `npx vitest run test/mcp/declare-rules.test.ts test/venture/init-origin.test.ts` rồi `npx vitest run test/mcp/declare.test.ts` |
| 03 — Y0 | `npx vitest run test/providers` |

### 4.1 Brief 01 — M4 (cô lập môi trường nguồn `cmd`)

Điều kiện: M0 đã trả lời (M0(e) nằm trong kế hoạch) và M1 đã làm (theo roadmap đợt 1). M4 vì vậy giao được ngay.

```powershell
mca ceo "Đọc plans/pending/briefs/01-M4-env-allow.md rồi làm đúng các bước trong đó. Làm M4 trong brief này: nguồn cmd chạy với môi trường tối thiểu cộng env_allow, mca venture check cảnh báo thiếu biến, init sinh env_allow rỗng kèm chú thích tiếng Việt, bài học có trường scope (mặc định venture:<id>), persona chỉ nạp bài học global + venture:<id>. Giữ nguyên tiêu chí và lệnh kiểm của M4 trong kế hoạch; không đọc .env hay token của repo."
```

**Sau khi `accept` xong, kiểm cad-guard không bị ảnh hưởng** (M4 là thay đổi hành vi):

```powershell
mca venture check cad-guard
```

rồi trên web **Startup → cad-guard → Thu tín hiệu**: nguồn `cadguard-stats` vẫn phải ra số 16. Script của cad-guard chỉ cần `PATH`, nên thường không cần `env_allow`; nếu ra lỗi "thiếu biến" thì thêm biến đó (ví dụ `CADGUARD_PYTHON`) vào `env_allow` của nguồn.

### 4.2 Brief 02 — Phase J, bước J0–J2 (công cụ MCP khai báo Startup)

Chỉ giao sau khi brief 01 đã `accept`, kiểm xanh và push.

```powershell
mca ceo "Đọc plans/pending/briefs/02-J0-J2-declare-tools.md rồi làm đúng các bước trong đó. Làm Phase J bước J0, J1, J2 theo plans/pending/mcp-declare.md: schema zod 4 công cụ, trường origin/provenance/from:agent tương thích ngược, checkDeclareRules (luật cmd/http_json/bí mật/kích thước), describe_declaration và get_declaration, declare_project (không gọi LLM, không ghi project.yaml, từ chối khi MCA_DEPTH>=1, hạn mức 5 phiên mở và 20 lần nộp mỗi ngày mỗi repo). Giữ nguyên tiêu chí và lệnh kiểm của từng bước."
```

Điểm cần đọc trước khi duyệt kế hoạch: mục 4.7 của `plans/pending/mcp-declare.md` — mọi nguồn `cmd` do MCP nộp phải là script **trong repo**, cấm đường dẫn tuyệt đối, `..` và ký tự ghép lệnh; MCA hiện nguyên văn + 60 dòng đầu script cho bạn duyệt. J3–J5 giao sau, khi J0–J2 đã nhận.

Sau khi xong: thử đầu-cuối bằng cad-guard (bước J6, cần bạn): nhờ Claude Code trong repo cad-guard khai báo dự án bằng công cụ mới thay cho Cách A.

### 4.3 Brief 03 — Phase Y0 (bảng nhà cung cấp, két khoá, CLI)

Chỉ giao sau khi brief 02 đã `accept`, kiểm xanh và push. Lưu ý: **không FPT.AI, không Vbee** (bạn đã loại); **không Suno** (không có API chính thức).

```powershell
mca ceo "Đọc plans/pending/briefs/03-Y0-providers-registry.md rồi làm đúng các bước trong đó. Làm Y0 trong plans/pending/provider-abilities.md: config/providers.yaml + schema zod strict (model có status/shutdown_at/replaced_by), khoá lưu qua OsSecretStore (provider:<id>:api_key) và redact() nhận dạng khoá, mca provider list|add|test|remove|usage, mca doctor cảnh báo mô hình sắp ngừng trong 60 ngày, test CI trượt khi có mô hình quá ngày ngừng; thêm ngoại lệ có phạm vi vào AGENTS.md. Không dùng FPT.AI, Vbee. Giữ tiêu chí và lệnh kiểm của Y0."
```

Y0 đụng tới két khoá: khi duyệt kế hoạch, kiểm rằng **khoá API chỉ do bạn tự nhập** qua `mca provider add` và lưu trong két hệ điều hành, không bao giờ nằm trong tệp, brief hay chat. Y1 (màn web) và Y2 (bộ chạy `api`) giao sau Y0. Y10 (năng lực qua trình duyệt) chỉ làm sau khi bạn đọc điều khoản dịch vụ của Google Flow.

---

## 5. Sau mỗi bước: lưu vào Git

Nhịp quen thuộc (chi tiết ở `docs/guides/github-tu-dau.md` mục 7): `git status` → `git add -A` → `git commit -m "mô tả ngắn"` → push bằng GitHub Desktop hoặc `git push`. Tài liệu bạn điền ở `D:\CadGuardData\private` **không** nằm trong repo nên không bị commit — đúng như mong muốn.

## 6. Còn lại chưa làm (để bạn biết)

- `bootstrap.ps1` chưa được chạy thử trên Windows của bạn (mình chỉ kiểm 31 test và quét tổng hợp ở môi trường cloud). Bước 1 chính là lần kiểm đó.
- Độ chính xác của 16 luật chưa đo trên bản vẽ thật (chờ bước 3.6).
- Danh sách lệnh `mca inbox`/`approve`/`accept` lấy từ hướng dẫn và brief; nếu phiên bản `mca` của bạn khác tên lệnh, `mca --help` là nguồn đúng.
