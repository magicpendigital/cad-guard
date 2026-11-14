# Các bước tiếp theo bằng giao diện (không gõ lệnh PowerShell)

Cập nhật 04/11/2026. Bản này làm lại `docs/guides/buoc-tiep-theo.md` cho người thích **bấm và dán văn bản** hơn là gõ lệnh. Nội dung và thứ tự không đổi; chỉ đổi cách làm.

Bạn dùng hai giao diện:

| Giao diện | Dùng cho | Bạn làm gì |
| --- | --- | --- |
| **Claude Code (tab Code của app Claude)** | Chạy `bootstrap`, đọc và giải thích lỗi, chạy kiểm tra, `git status` | Dán câu yêu cầu tiếng Việt; Claude chạy lệnh thay bạn; bạn bấm **duyệt** từng lệnh |
| **mca HQ (`mca web`, trang web trên máy bạn)** | Đăng ký dự án, giao 3 brief, duyệt kế hoạch, nhận kết quả vào `main` | Bấm nút, điền form, dán văn bản |

Vài việc **cố ý** không làm trong khung chat Claude (có ghi lý do ở từng mục): bản vẽ thật của khách, và push lên GitHub (dùng GitHub Desktop).

> Giới hạn của bản này: tên nút và thanh bên của mca HQ mình lấy từ tài liệu `docs/huong-dan/09` và `13` của MCA, tên các điều khiển của app Claude lấy từ tài liệu Claude Code Desktop; mình chưa tận mắt thấy màn hình của bạn. Nếu nút nào tên khác, chọn nút gần nghĩa nhất và nhờ mình chỉnh lại tài liệu.

---

## 0. Mở phiên Claude Code cho dự án cad-guard (làm một lần)

1. Mở app **Claude**, bấm tab **Code** ở đầu thanh bên (nếu chỉ thấy biểu tượng, rê chuột để xem tên).
2. Ở hàng dưới ô nhập, bấm điều khiển đầu tiên (chọn môi trường) và chọn mục **trên cùng của nhóm Local**.
3. Bấm điều khiển thư mục bên cạnh, chọn **Open folder…**, chọn `D:\Projects\cad-guard`.
4. Cũng ở hàng đó, đặt chế độ quyền là **Manual**: Claude hỏi bạn trước khi sửa tệp hoặc chạy lệnh. Khi bạn quen mới nên cân nhắc chế độ khác.
5. Mở khung **Terminal** bằng `` Ctrl + ` `` (dấu huyền) nếu cần xem hoặc gõ lệnh tay; nó mở sẵn ở thư mục dự án.

Lưu ý riêng cho Windows: app Claude **không đọc hồ sơ PowerShell**; chương trình như `python`, `git`, `node`, `mca` phải nằm trong biến môi trường **PATH của Windows**. Mỗi khi cài thêm chương trình mới (ví dụ Python 3.13), **thoát hẳn app Claude rồi mở lại** để nó thấy PATH mới.

**Quy tắc an toàn dữ liệu** (đọc kỹ):

- Phiên này chỉ mở thư mục `D:\Projects\cad-guard`. **Không** dùng **+ → Add folder** để thêm `D:\CadGuardData`.
- **Không** kéo thả hoặc gõ `@` để đưa bản vẽ thật, báo cáo quét bản vẽ thật hay phiếu khảo sát đã điền vào khung chat. Nội dung trong chat đi qua mô hình AI trên đám mây.

---

## 1. Chạy bootstrap bằng Claude Code

Dán nguyên văn vào ô nhập của phiên cad-guard rồi gửi:

```text
Chạy lệnh sau trong thư mục dự án và cho tôi xem kết quả:
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
Nếu có lỗi: đừng tự sửa. Hãy giải thích nguyên nhân bằng tiếng Việt dễ hiểu, đề xuất cách khắc phục và hỏi tôi trước khi làm.
Khi chạy xong, tóm tắt cho tôi: script dùng Python bản nào, bao nhiêu test qua, dòng JSON cuối (stats) là gì, và lệnh git status có sạch không.
```

Claude hiện một thẻ **xin duyệt lệnh**; bấm duyệt. Kết quả đúng (như mục 1.3 của `buoc-tiep-theo.md`): dòng `Dùng Python 3.13...`, `31 passed`, `Xong...`, và `{"rules_implemented": 16, ...}`; `git status` sạch.

- **Chưa có Python 3.13**: dán tiếp `Kiểm tra bằng "py --list" xem máy có Python 3.13 chưa. Nếu chưa, đề xuất lệnh cài (winget install Python.Python.3.13) và chờ tôi đồng ý.` Cài đặt có thể hiện hộp xác nhận của Windows; bạn bấm Yes. Sau khi cài: **thoát hẳn app Claude, mở lại**, mở lại phiên cad-guard rồi dán lại câu yêu cầu ở đầu mục này.
- **Thẻ lệnh báo hết thời gian** (lần đầu tải thư viện có thể lâu): bảo Claude "chạy lại lệnh đó ở nền và báo khi xong", hoặc gõ lệnh trong khung **Terminal** ở mục 0.
- **Lỗi khác**: để Claude giải thích; muốn mình xem thì copy đoạn đầu và đoạn cuối của lỗi gửi mình.

---

## 2. Đăng ký cad-guard vào MCA — bằng mca HQ (trang web)

### 2.1 Mở mca HQ

Cần một lệnh duy nhất. Dán vào phiên Claude Code (mở phiên ở thư mục nào cũng được):

```text
Chạy lệnh mca web --open như một tác vụ nền (không chờ nó kết thúc) rồi cho tôi biết trình duyệt đã mở chưa.
```

Nếu Claude không giữ được tác vụ nền: mở khung **Terminal** (`` Ctrl + ` ``), gõ `mca web --open` và **để cửa sổ đó mở** (dừng bằng Ctrl+C). Trang mở ra có đường dẫn dạng `http://127.0.0.1:4317/?token=...`; chỉ truy cập được trên máy bạn.

Nhìn ô trạng thái ở thanh bên: **Trợ lý đang trực** là daemon đã chạy; **Daemon chưa chạy** thì các việc giao sẽ chờ. Cách bật daemon: xem `docs/huong-dan/05-daemon.md` của MCA (`mca daemon`, hoặc `mca daemon install` để tự chạy khi đăng nhập máy — việc đổi cấu hình máy nên do bạn tự quyết định).

### 2.2 Bật phòng Chất lượng (nếu chưa)

Vào mục **Nhân viên** trên thanh bên; bật phòng **quality** và bảo đảm phòng có trưởng phòng. (Điều lệ cad-guard dùng hai phòng dev và quality; thiếu thì bước kiểm báo lỗi.)

### 2.3 Thêm dự án

1. Thanh bên: **Startup → Thêm dự án**.
2. Chọn **Trò chuyện với trợ lý** (không cần hiểu cấu hình; trợ lý hỏi, bạn trả lời) hoặc **Tự cấu hình** (6 bước, không tốn lượt AI). Mình khuyên **Trò chuyện** cho lần đầu.
3. Bước chọn thư mục: chọn hoặc dán `D:\Projects\cad-guard`.
4. Dán đoạn mô tả dưới đây (là đoạn trong dấu nháy ở mục 2.2 của `buoc-tiep-theo.md`, dán không kèm dấu nháy):

```text
cad-guard: trợ lý kiểm tra và chuẩn hoá bản vẽ nội thất cho doanh nghiệp sản xuất nội thất (tủ bếp, tủ áo, văn phòng). Định dạng làm việc chung là DXF, không phụ thuộc phần mềm CAD. Khách hàng: phòng kỹ thuật và thiết kế sản xuất của nhà máy nội thất. Giai đoạn: building, đang khảo sát và làm lõi kiểm tra tất định. Chỉ số chính (north star): rules_implemented, mục tiêu 30 luật trước 31/01/2027. Chỉ số phụ: drawings_audited_7d, confirmed_defects_7d, false_positive_pct, rule_precision_pct, suggestion_accept_pct, rework_incidents_7d, active_drafters_7d. Dùng đúng các mã chỉ số này. Nguồn số liệu: lệnh node scripts/metrics.mjs (in JSON từ python -m cadguard stats --json) và thư mục .mca/signals cho tệp thả vào. Phòng tham gia: dev và quality. Ngân sách khoảng 2 triệu token mỗi tuần. Tự chủ mức propose (kế hoạch họp chờ tôi duyệt). Quy tắc cấm: không đưa bản vẽ thật của khách (.dwg/.dxf) vào repo, brief của agent hay prompt; không sửa luật của chuẩn mà không tạo phiên bản chuẩn mới kèm số liệu; không bật cảnh báo thời gian thực cho luật chưa đo độ chính xác; không gửi dữ liệu theo từng thợ vẽ, chỉ số tổng hợp.
```

5. Trả lời các câu trợ lý hỏi (tối đa 5 câu một lượt). Không biết thì ghi "chưa biết".
6. **Đọc bản nháp dạng thẻ trước khi lưu.** Phải đúng: mã `cad-guard`; phòng dev + quality; tự chủ **propose**; chỉ số chính `rules_implemented` mục tiêu 30, hạn 2027-01-31; hai nguồn số liệu (lệnh `node scripts/metrics.mjs` và thư mục `.mca/signals`); phần cấm có đủ 4 ý. Khung **Kiểm tra bản nháp** bên phải sẽ chỉ chỗ cần sửa.
7. Hài lòng thì bấm **Lưu và đăng ký**.

### 2.4 Kiểm hai đường tín hiệu

Trong **Startup → cad-guard** bấm **Thu tín hiệu**: nguồn `cadguard-stats` phải ra số 16 (nếu bước 1 đã chạy xong). Muốn Claude kiểm hộ, dán vào phiên cad-guard: `Chạy mca venture check cad-guard và mca signals cad-guard --since 1d, giải thích kết quả cho tôi bằng tiếng Việt.`

Khi cần họp thử: nút **Họp ngay** trong cùng trang. Vì tự chủ là **propose**, kế hoạch họp sẽ nằm ở **Chờ bạn duyệt**, chưa chạy gì cho tới khi bạn bấm.

> Khi MCA làm xong brief 02 (công cụ MCP khai báo Startup), bước đăng ký này sẽ làm được thẳng bằng một câu trong khung chat Claude Code. Hiện tại chưa có.

---

## 3. P0: khảo sát và thu bản vẽ mẫu — gần như không cần Claude

Phần này **không** làm trong chat Claude vì liên quan dữ liệu khách.

### 3.1 Dựng thư mục dữ liệu bằng File Explorer (không cần lệnh)

1. Mở File Explorer, vào ổ `D:`, tạo thư mục `CadGuardData`.
2. Trong đó tạo 4 thư mục: `samples`, `reports`, `private`; trong `samples` tạo `raw` và `anon`.
3. Chép `D:\Projects\cad-guard\docs\discovery.md` vào `D:\CadGuardData\private` và đổi tên thành `discovery-dien.md` (đây là bản điền thật; bản trong repo giữ nguyên là phiếu trắng).
4. Tạo `samples\index.csv`: mở Excel, gõ ở dòng 1 năm cột `ma`, `phan_mem`, `ban`, `co_dxf_goc`, `ghi_chu`, lưu thành CSV UTF-8 vào `D:\CadGuardData\samples\index.csv`.

Ý nghĩa từng thư mục, buổi khảo sát với trưởng phòng kỹ thuật, tin nhắn hẹn mẫu, cách thu, ẩn danh và đổi sang DXF: giống hệt mục 3.2 đến 3.5 của `buoc-tiep-theo.md`.

### 3.2 Quét thử bản đã ẩn danh

Chỉ làm khi bản vẽ đã ẩn danh, nằm trong `samples\anon`. Mở khung **Terminal** (`` Ctrl + ` ``) và tự gõ (đừng nhờ Claude chạy, để nội dung bản vẽ không đi vào cuộc trò chuyện):

```powershell
cd packages\core
.venv\Scripts\python -m cadguard audit D:\CadGuardData\samples\anon --out D:\CadGuardData\reports\p0.html
```

Mở `D:\CadGuardData\reports\p0.html` bằng trình duyệt cùng người kỹ thuật. Nếu muốn nhờ Claude giải thích: chỉ dán **mã luật và số lần** (ví dụ "LY-01: 12 lần"), không dán tên layer, nội dung chữ, tên tệp hay ảnh chụp báo cáo, và chỉ khi phiếu khảo sát mục 4 đã ghi khách cho phép.

---

## 4. Giao 3 brief cho MCA — bằng mca HQ

Quy tắc cho cả ba brief, theo thứ tự **01 (M4) → 02 (J0–J2) → 03 (Y0)**; brief sau chỉ giao khi brief trước đã nhận vào `main`, kiểm xanh và push.

### 4.1 Trước mỗi brief: kiểm repo MCA sạch

Mở **một phiên Claude Code thứ hai** ở thư mục `D:\Projects\multi-coding-agents` (thanh bên của tab Code có nút tạo phiên mới) và dán:

```text
Chạy git status và git branch --show-current. Cho tôi biết repo đã sạch (không có thay đổi chưa commit) và đang ở nhánh main chưa. Đừng sửa gì.
```

Kết quả phải là sạch + nhánh `main`. Nếu không, **dừng** và hỏi mình.

### 4.2 Giao việc trên web

Trong mca HQ: **Giao việc** (hoặc khung **Giao việc mới** ở Tổng quan):

- **Giao cho:** Trợ lý tự phân công
- **Thư mục repo:** `D:\Projects\multi-coding-agents` (web nhớ lần gõ trước; phải gõ đúng vì khác với lệnh `mca ceo` chạy tại thư mục repo)
- **Ưu tiên:** Thường
- Dán văn bản mục tiêu của brief tương ứng (bên dưới), rồi bấm **Giao việc**.

Văn bản mục tiêu cho từng brief (dán nguyên văn, không kèm dấu nháy ngoài cùng):

**Brief 01 — M4**

```text
Đọc plans/pending/briefs/01-M4-env-allow.md rồi làm đúng các bước trong đó. Làm M4 trong brief này: nguồn cmd chạy với môi trường tối thiểu cộng env_allow, mca venture check cảnh báo thiếu biến, init sinh env_allow rỗng kèm chú thích tiếng Việt, bài học có trường scope (mặc định venture:<id>), persona chỉ nạp bài học global + venture:<id>. Giữ nguyên tiêu chí và lệnh kiểm của M4 trong kế hoạch; không đọc .env hay token của repo.
```

**Brief 02 — Phase J, J0–J2** (chỉ sau khi brief 01 đã xong)

```text
Đọc plans/pending/briefs/02-J0-J2-declare-tools.md rồi làm đúng các bước trong đó. Làm Phase J bước J0, J1, J2 theo plans/pending/mcp-declare.md: schema zod 4 công cụ, trường origin/provenance/from:agent tương thích ngược, checkDeclareRules (luật cmd/http_json/bí mật/kích thước), describe_declaration và get_declaration, declare_project (không gọi LLM, không ghi project.yaml, từ chối khi MCA_DEPTH>=1, hạn mức 5 phiên mở và 20 lần nộp mỗi ngày mỗi repo). Giữ nguyên tiêu chí và lệnh kiểm của từng bước.
```

**Brief 03 — Y0** (chỉ sau khi brief 02 đã xong)

```text
Đọc plans/pending/briefs/03-Y0-providers-registry.md rồi làm đúng các bước trong đó. Làm Y0 trong plans/pending/provider-abilities.md: config/providers.yaml + schema zod strict (model có status/shutdown_at/replaced_by), khoá lưu qua OsSecretStore (provider:<id>:api_key) và redact() nhận dạng khoá, mca provider list|add|test|remove|usage, mca doctor cảnh báo mô hình sắp ngừng trong 60 ngày, test CI trượt khi có mô hình quá ngày ngừng; thêm ngoại lệ có phạm vi vào AGENTS.md. Không dùng FPT.AI, Vbee. Giữ tiêu chí và lệnh kiểm của Y0.
```

### 4.3 Duyệt kế hoạch và nhận kết quả

1. Khung **Chờ bạn duyệt** (Tổng quan) hoặc **Hộp thư**: đọc kế hoạch, bấm **Duyệt kế hoạch** nếu đồng ý (hoặc **Yêu cầu sửa** kèm góp ý).
   - Brief 02: trước khi duyệt, đọc mục 4.7 của `plans/pending/mcp-declare.md`: mọi nguồn `cmd` do MCP nộp phải là script **trong repo**, cấm đường dẫn tuyệt đối, `..` và ký tự ghép lệnh.
   - Brief 03: kiểm khoá API chỉ do **bạn tự nhập** qua `mca provider add`, lưu trong két hệ điều hành, không nằm trong tệp, brief hay chat.
2. Chờ MCA làm xong (theo dõi ở **Tiến trình** / **Bảng việc**; thông báo hiện ở góc màn hình).
3. Khung **Chờ nhận vào main**: bấm **Chạy thử (không đổi gì)** trước; thấy ổn bấm **Nhận vào main**.
4. Kiểm lệnh xanh bằng Claude Code (phiên ở repo MCA). Dán, đổi dòng lệnh theo brief:

```text
Chạy lệnh sau trong thư mục dự án và cho tôi biết đạt hay không, kèm tên test trượt nếu có. Đừng sửa mã.
npx vitest run test/venture/collect-env.test.ts test/quality/lesson-scope.test.ts
```

| Brief | Lệnh kiểm |
| --- | --- |
| 01 — M4 | `npx vitest run test/venture/collect-env.test.ts test/quality/lesson-scope.test.ts` |
| 02 — J0–J2 | `npx vitest run test/mcp/declare-rules.test.ts test/venture/init-origin.test.ts`, rồi `npx vitest run test/mcp/declare.test.ts` |
| 03 — Y0 | `npx vitest run test/providers` |

5. Sau brief 01, kiểm cad-guard không bị ảnh hưởng: vào **Startup → cad-guard → Thu tín hiệu**, nguồn `cadguard-stats` vẫn phải ra 16; hoặc nhờ Claude `mca venture check cad-guard`.
6. **Push `main` bằng GitHub Desktop** (nút **Push origin**). Mca không bao giờ tự push, và cũng không nên nhờ Claude push thay: GitHub Desktop đang giữ đăng nhập của bạn.

---

## 5. Lưu thay đổi của cad-guard vào Git

Trong GitHub Desktop (repo `cad-guard`): xem các tệp đã đổi, ghi một câu mô tả ngắn, bấm **Commit to main**, rồi **Push origin**. Chi tiết và danh sách kiểm: `docs/guides/github-tu-dau.md`. Tài liệu bạn điền ở `D:\CadGuardData\private` không nằm trong repo nên không bị commit, đúng như mong muốn.
