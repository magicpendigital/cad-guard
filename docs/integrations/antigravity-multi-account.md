# Nhiều tài khoản Antigravity CLI (`agy`): các công cụ khác làm thế nào, cad-guard nên làm gì

Ngày nghiên cứu: 05/11/2026. Chỉ đọc web, README và tài liệu. **Không** cài, chạy hay đăng nhập công cụ đa tài khoản nào; không chạy `agy`; không đọc tệp xác thực hay kho khoá.

Đọc kèm: `antigravity.md` (mục 5: xác thực và điều khoản), `claude-code.md` (mục 5), `codex.md` (mục 5), `../assistant.md`.

Quy ước nguồn:

- **[chính thức]**: trang của Google, Anthropic hoặc OpenAI, có link.
- **[thứ cấp]**: báo chí, blog, README của bên thứ ba. Có thể thiên vị, nhất là blog của hãng bán công cụ.
- **[diễn đàn]**: bài người dùng tự viết. Chỉ là giai thoại.
- **[chưa kiểm]**: chưa đối chiếu được với nguồn gốc.

Tên repo dưới đây ghi để **tham chiếu**, không phải khuyến nghị dùng. Cố ý không để link tải.

## 0. Kết luận ngắn

1. "Nhiều tài khoản Antigravity" trong các ứng dụng bên ngoài thường là một trong ba cách:
   - **ghi đè mục token duy nhất** của `agy` trong kho khoá hệ điều hành (đổi qua lại);
   - **proxy OAuth** gộp nhiều tài khoản Google thành một API, rồi xoay vòng khi hết hạn mức;
   - **khoá Gemini API** riêng cho từng tiến trình.
2. Theo văn bản chính thức của Google:
   - Hai cách đầu **không hợp lệ** khi đi qua ứng dụng khác, hoặc khi tự động hoá.
   - FAQ Antigravity nói thẳng: bọc `agy` trong ứng dụng bên thứ ba **và tự động xoay vòng tài khoản** "is not supported under consumer plans".
   - Điều khoản mục 6 cấm phần mềm bên thứ ba truy cập dịch vụ. Hệ quả có thể là khoá tài khoản. Đợt khoá hàng loạt tháng 2/2026 có thật.
3. Cách hợp lệ là **tách thông tin xác thực theo người dùng hoặc theo dự án**, không gộp để lấy thêm hạn mức:
   - mỗi nhân viên **một tài khoản doanh nghiệp** (Gemini Enterprise), tự đăng nhập trên máy mình;
   - hoặc **khoá Gemini API / ADC theo dự án Google Cloud** của công ty, gắn với phòng hay dự án.
4. `agy` **không có** cách chính thức để giữ hai lần đăng nhập Google song song. Tức là không có biến kiểu `CLAUDE_CONFIG_DIR`. Yêu cầu này đang mở: issue #155 và #381 trên `google-antigravity/antigravity-cli`. Muốn "nhiều tài khoản" chạy song song với `agy` thì chỉ có khoá API, hoặc ADC theo tiến trình (chưa kiểm).
5. Đề xuất cho cad-guard: thêm khái niệm **"kết nối AI"**, khai báo được nhiều kết nối, chọn theo dự án hoặc phòng. cad-guard **không** chạm token của CLI, **không** xoay vòng khi hết hạn mức, **không** đọc kho khoá của `agy`. Chi tiết ở mục 6.

## 1. Các công cụ tìm được

Số sao và giấy phép lấy bằng `gh repo view` / `gh api repos/<repo>/license` ngày 05/11/2026. Cách làm lấy từ README **[thứ cấp]**; chưa đọc mã nguồn.

| Công cụ (repo) | Sao · giấy phép | Cách làm | Rủi ro điều khoản |
| --- | --- | --- | --- |
| `lbjlaq/Antigravity-Manager` (Tauri) | ~32.800 · không rõ (NOASSERTION) | Thêm tài khoản bằng OAuth. Có bộ lệnh "rotation" đổi token `agy` trong Keychain. Proxy cục bộ "silent rotation" khi gặp 429/401 | **Cao.** Xoay vòng tự động + proxy |
| `router-for-me/CLIProxyAPI` | ~57.600 · MIT | Bọc đăng nhập Antigravity, Codex, Claude Code… thành API tương thích OpenAI/Gemini/Claude cho công cụ khác dùng. README quảng cáo proxy dân cư "for multi-account operations" | **Rất cao.** Đúng hành vi FAQ Google nêu tên |
| `NoeFabris/opencode-antigravity-auth` | ~11.000 · MIT | Plugin cho OpenCode xác thực bằng OAuth Antigravity. Lưu token trong `~/.config/opencode/antigravity-accounts.json`. Có danh sách tài khoản và "rotation" | **Rất cao.** OpenCode được FAQ nêu tên là phần mềm bên thứ ba bị cấm |
| `badrisnarayanan/antigravity-claude-proxy` | ~4.000 · MIT | Proxy đưa mô hình của Antigravity sang Claude Code/OpenClaw bằng token OAuth của nhiều tài khoản | **Rất cao.** README tự cảnh báo Google "has been issuing ToS violation bans on accounts connected to this proxy" |
| `kaitranntt/ccs` | ~2.900 · MIT | Đổi tài khoản Claude, gọi Gemini/Antigravity qua CLIProxyAPI. Tài liệu ghi "auto-rotation on rate limits" | **Cao** (qua CLIProxyAPI) |
| `Draculabo/AntigravityManager` (Electron) | ~2.500 · không rõ | Đổi tài khoản cho IDE, App và `agy`. Có "local API gateway" cho Claude Code/Codex/OpenCode. Token OAuth lưu **dạng chữ thường trong SQLite**. Nhà tài trợ là dịch vụ proxy dân cư | **Cao.** README tự cảnh báo: "Reverse-proxy use can violate provider terms and lead to account restrictions or suspension" |
| `anglee0323/agy-switch` | ~150 · không rõ | Ứng dụng desktop + CLI quản lý tài khoản, hạn mức, mức dùng. Thêm tài khoản bằng Google, bằng refresh token, hoặc nhập cục bộ. README không nói rõ cơ chế; có lẽ ghi đè kho khoá **[chưa kiểm]** | Trung bình–cao. Không có proxy (theo README); có chuyển refresh token |
| `tuxevil/tuxevil-rotator` (trước là `pi-antigravity-rotator`) | ~80 · MIT | Proxy OpenAI-compatible xoay vòng nhiều tài khoản Antigravity (và nhà cung cấp khác), đọc hạn mức định kỳ | **Rất cao.** README: "Multi-account rotation and proxying can increase account risk"; khuyên "do not use your primary account" |
| `ChillingWombat/AntigravitySwissKnife` | ~19 · MIT | Đổi token OAuth trong kho khoá hệ điều hành, đồng bộ IDE/CLI/VS Code. Có "standby quota rotation" và "hardware fingerprint virtualization" | Cao. README **tự nhận** tuân thủ điều khoản, nhưng có xoay vòng theo hạn mức, trái câu FAQ ở mục 2.1 |
| `hrmasss/antigravity-swap` (`aswap`, PyPI) | 3 · MIT | Lưu bản sao token của từng tài khoản. Tự đổi khi dùng quá ngưỡng (mặc định 90%). Định kỳ đặt token của tài khoản không dùng vào kho khoá vài giây để làm mới. Trên Linux chạy song song bằng thư mục `agy` riêng; trên Windows thì một tài khoản cho cả máy | Cao. Tự động xoay vòng để né hạn mức |
| AgentsRoom (ứng dụng thương mại) | — | Mỗi agent Antigravity = **một khoá Gemini API**. **Không** ghi đè kho khoá. Với Claude Code/Codex dùng `CLAUDE_CONFIG_DIR` / `CODEX_HOME`, và tự chuyển tài khoản khi hết hạn mức | Thấp với khoá API. Việc tự chuyển tài khoản thuê bao khi hết hạn mức (Claude/Codex) thì đáng ngờ, xem mục 5 |

Nguồn kỹ thuật chung **[thứ cấp]**: [AgentsRoom, "Antigravity CLI Keeps One Google Login Per Machine"](https://agentsroom.dev/blog/multiple-accounts-antigravity-cli). Đây là blog của hãng bán công cụ, nhưng khớp với tài liệu chính thức và hai issue GitHub ở dưới. Nội dung chính:

- token của `agy` nằm ở **một** mục kho khoá: service `gemini`, account `antigravity`; Windows ghi là `gemini:antigravity`;
- công cụ "switcher" chỉ ghi đè mục đó, nên đổi cho **cả máy**;
- chỉ khoá API mới chạy song song được.

## 2. Các kỹ thuật và mức hợp lệ

### 2.1 Văn bản chính thức của Google

- [FAQ Antigravity](https://antigravity.google/docs/faq/) **[chính thức]**:
  - Câu "Can I use Antigravity CLI headless mode in third-party coding agents or automate account switching?":
    - `agy -p` "is intended for direct scripting and CI workflows";
    - bọc `agy` trong agent hay ứng dụng bên thứ ba, **hoặc tự động xoay vòng tài khoản**, "is not supported under consumer plans".
  - Câu "Why can't I use third-party software…":
    - "Using third-party software, tools, or services to access Antigravity is a violation of our Terms of Service";
    - có thể dẫn tới "suspension or termination of your account";
    - Google khuyên dùng khoá Gemini Enterprise hoặc Google AI Studio.
  - Tài khoản doanh nghiệp: quản trị "must assign you a Gemini Enterprise license or the required IAM role". Tức là giấy phép gán **theo từng người**.
  - FAQ **không** nói gì về chuyện một người có nhiều tài khoản.
- [Điều khoản Antigravity](https://antigravity.google/terms) mục 6 **[chính thức]**:
  - cấm dùng phần mềm bên thứ ba để truy cập dịch vụ (ví dụ "using OpenClaw with Antigravity OAuth");
  - vi phạm có thể bị khoá tài khoản Antigravity và/hoặc Gemini CLI.
  - Phần mở đầu: truy cập qua Gemini Enterprise, Workspace hoặc khoá API thì theo điều khoản mà quản trị đã ký.
  - Điều khoản **không** có câu riêng về nhiều tài khoản hay né hạn mức.
- [Gemini CLI – Terms and privacy](https://geminicli.com/docs/resources/tos-privacy) **[chính thức]**:
  - cũng cấm dùng phần mềm bên thứ ba truy cập dịch vụ phía sau Gemini CLI (ví dụ OpenClaw với Gemini CLI OAuth);
  - khoá Gemini API thì theo Gemini API Terms; khoá Vertex thì theo Google Cloud Service Terms.
- [Google APIs Terms](https://developers.google.com/terms) mục 2(d) **[chính thức]**:
  - "You agree to, and will not attempt to circumvent, such limitations";
  - muốn vượt giới hạn phải xin Google đồng ý.
  - Mục 2(c): không che giấu danh tính của mình hay của API Client.
  - Áp cho đường khoá API. Tạo thêm khoá hay dự án **để né** giới hạn có thể bị coi là lách 2(d). Đây là cách đọc của chúng tôi; văn bản không nêu ví dụ "nhiều dự án".
- [Gemini API Additional Terms](https://aistudio.google.com/docs/terms) **[chính thức]**:
  - dịch vụ **không trả phí**: Google dùng nội dung gửi lên để cải tiến; "Do not submit sensitive, confidential, or personal information to the Unpaid Services";
  - dịch vụ **trả phí** (dự án Cloud có thanh toán): Google không dùng lời nhắc để cải tiến.
  - Hệ quả cho cad-guard: kết nối khoá API phải là **dự án có thanh toán**.

### 2.2 Đánh giá từng kỹ thuật

| Kỹ thuật | Ai dùng | Kỹ thuật có tách được không | Hợp lệ? |
| --- | --- | --- | --- |
| **K1. Đổi `HOME`/`USERPROFILE`/thư mục cấu hình** | `aswap` (Linux), nhiều script | Với `agy` trên Windows/macOS thì **không**: token vẫn ở kho khoá chung. `antigravity.md` mục 5 đã kiểm trên máy: đổi `USERPROFILE`, `agy acp` vẫn nạp token từ kho khoá | Bản thân việc đổi thư mục không vi phạm, nhưng vô dụng. **Với Claude Code thì đây là cách chính thức** (mục 4) |
| **K2. Ghi đè mục token trong kho khoá** (lưu bản sao token từng tài khoản rồi đặt lại) | `aswap`, `agy-switch`, Antigravity-Manager, SwissKnife | Được, nhưng đổi cho **cả máy**; không chạy song song được | Một người tự đổi tay giữa các tài khoản **của chính mình**: văn bản không cấm, cũng không hỗ trợ. Cách chính thức là `/logout` rồi đăng nhập lại. Khi **tự động hoá** (đổi theo ngưỡng hạn mức) thì đúng là "automate account switching", thứ FAQ nói không hỗ trợ với gói cá nhân. Ứng dụng khác đọc/ghi token của `agy` thì rất dễ bị coi là "third-party software… to access". **cad-guard: không làm** |
| **K3. Proxy OAuth trung gian** (gộp token nhiều tài khoản thành một API cho công cụ khác) | CLIProxyAPI, antigravity-claude-proxy, opencode-antigravity-auth, tuxevil-rotator, ccs, gateway của các Manager | Được về kỹ thuật | **Không hợp lệ.** Đúng ví dụ Google nêu trong điều khoản mục 6 và FAQ. Đây là nguồn chính của các vụ khoá tài khoản (mục 3). **Gộp tài khoản (account pooling)** |
| **K4. Xoay vòng khi hết hạn mức** (tự hoặc theo ngưỡng) | `aswap auto`, Antigravity-Manager, rotator, SwissKnife | — | **Không hợp lệ với gói cá nhân** (FAQ nói thẳng). Với khoá API: tạo thêm khoá hay dự án để lách giới hạn có thể vi phạm Google APIs Terms 2(d). **Né hạn mức** |
| **K5. Thông tin xác thực theo tiến trình, không phải thuê bao**: `GEMINI_API_KEY` + `"modelProvider": "gemini"`; ADC (`AGY_ADC_AUTH=true` + `gcloud auth application-default login --project …`) | AgentsRoom; tài liệu chính thức | Có, chạy song song được: khoá đọc từ môi trường của từng tiến trình. ADC theo tiến trình **chưa kiểm** | **Hợp lệ**, và là đường Google khuyên ([cài đặt & xác thực](https://antigravity.google/docs/install): khoá API "suits headless and CI runs"; ADC cho "headless enterprise environments and automated terminal workflows"). Phải là khoá của tổ chức khách, dự án có thanh toán, mỗi khoá/dự án gắn với một mục đích thật (phòng, dự án), **không** để cộng dồn hạn mức |
| **K6. Mỗi người một tài khoản doanh nghiệp** tự đăng nhập trên máy mình | Cách chuẩn của Gemini Enterprise | Một máy, một người, một tài khoản | **Hợp lệ về tài khoản.** Việc cad-guard **khởi chạy** `agy -p` với tài khoản doanh nghiệp thì vẫn **chưa có văn bản** cho phép hay cấm rõ (FAQ chỉ nói "not supported under consumer plans"). Câu hỏi mở này đã ghi ở `antigravity.md` mục 5 |

Ghi chú về `--settings`. AgentsRoom nói "key mode" là cài đặt toàn máy. cad-guard thì truyền `modelProvider` qua `--settings <tệp tạm>` cho từng phiên (`cli_engines.py`), nên có lẽ chỉ áp cho tiến trình đó. **Chưa kiểm có token.**

## 3. Ghi nhận khoá tài khoản công khai

- **Tháng 2/2026 — đợt khoá hàng loạt** **[thứ cấp]**:
  - Google chặn Antigravity với tài khoản dùng kèm agent bên ngoài, chủ yếu OpenClaw qua OAuth Antigravity;
  - bị khoá cả người dùng miễn phí lẫn thuê bao trả phí;
  - lý do Google nêu: tải nặng, liên tục, "not a normal or intended use";
  - nguồn: [Techzine 24/02/2026](https://www.techzine.eu/news/privacy-compliance/139032/google-intervenes-in-heavy-use-of-antigravity-and-gemini), [The Register 23/02/2026](https://www.theregister.com/2026/02/23/google_antigravity_compute_burden/).
- **27/02/2026** **[thứ cấp, chưa kiểm bài gốc trên X]**:
  - tài khoản Google Antigravity được cho là tuyên bố mở lại cho những người bị chặn vì công cụ bên thứ ba;
  - luật cấm vẫn giữ.
- **12/03/2026** **[diễn đàn]**: bài ["Update on Antigravity ToS ban"](https://discuss.ai.google.dev/t/update-on-antigravity-tos-ban/131424) trên diễn đàn Google AI. Bài **không** ghi rõ người đăng là nhân viên Google, nhưng viết như thông báo chính thức. Nội dung:
  - dùng công cụ bên thứ ba với đăng nhập Antigravity "remains against our terms";
  - có biểu mẫu để gỡ khoá;
  - **tái phạm thì khoá vĩnh viễn**.
- **Nhiều bài kháng nghị** trên `discuss.ai.google.dev` **[diễn đàn]**:
  - lỗi 403 "This service has been disabled in this account for violation of Terms of Service";
  - có bài nói bị khoá **cả tài khoản Google**, không chỉ Antigravity;
  - một thông báo được trích có câu về tài khoản "used with multiple other accounts" **[chưa kiểm]**.
  - Không có văn bản chính thức nào nói **chỉ** có nhiều tài khoản là bị khoá.
- **README của chính công cụ** **[thứ cấp]**: antigravity-claude-proxy, tuxevil-rotator và AntigravityManager đều tự cảnh báo có thể bị khoá hoặc "shadow-ban". Hai công cụ đầu khuyên đừng dùng tài khoản chính.
- **Gói gia đình** **[thứ cấp, AgentsRoom, dựa trên đo đạc của người dùng]**: hai suất Google AI Pro trong cùng nhóm gia đình dùng chung một hạn mức. Chưa kiểm.

Kết luận: rủi ro khoá tài khoản là **có thật và đã xảy ra hàng loạt**. Nhóm bị khoá chủ yếu dùng **K3 (proxy) và K4 (xoay vòng)**. Nếu cad-guard dùng các cách này, người bị khoá là **khách hàng** của ta.

## 4. Đối chiếu Anthropic (Claude Code) và OpenAI (Codex)

| | Anthropic | OpenAI |
| --- | --- | --- |
| Nhiều tài khoản của **một người** trên một máy | **Có cách chính thức.** [Authentication › Log in with multiple accounts](https://code.claude.com/docs/en/authentication): mỗi tài khoản một `CLAUDE_CONFIG_DIR`, chạy song song được. Ví dụ trong tài liệu là `alias claude-work='CLAUDE_CONFIG_DIR=~/.claude-work claude'` **[chính thức]** | `CODEX_HOME` quyết định nơi lưu `auth.json` ([Auth](https://learn.chatgpt.com/docs/auth), xem `codex.md`) **[chính thức]**. Không thấy trang nào hướng dẫn riêng "nhiều tài khoản" |
| Chia sẻ tài khoản | [Consumer Terms](https://www.anthropic.com/legal/consumer-terms) mục 2: không được chia sẻ thông tin đăng nhập, khoá API hay "make your Account available to anyone else" **[chính thức]** | Terms of Use: "You may not share your account credentials or make your account available to anyone else" **[chính thức; trang chặn tải trực tiếp, đọc qua chỉ mục tìm kiếm]**. Services Agreement (doanh nghiệp/API): không dùng chung đăng nhập giữa nhiều người **[như trên]** |
| Né hạn mức | Consumer Terms mục 3 cấm "bypassing any of our systems or protective measures". Truy cập tự động chỉ được qua khoá API hoặc khi được cho phép rõ **[chính thức]**. Không có câu riêng về xoay vòng tài khoản | Terms of Use cấm "circumvent any rate limits or restrictions" **[chính thức, qua chỉ mục]**. Xoay vòng nhiều tài khoản để né giới hạn rơi thẳng vào câu này |
| Ứng dụng bên thứ ba dùng thuê bao | Xem `claude-code.md` mục 5.2. Người dùng tự đăng nhập binary nguyên bản; không cung cấp đăng nhập claude.ai trong sản phẩm qua Agent SDK nếu chưa được duyệt | Xem `codex.md` mục 5. Đường chính thức là chương trình "Sign in with ChatGPT" đã đăng ký; trường hợp (B) chưa có văn bản |

Tóm lại:

- Cả ba hãng đều cấm **chia sẻ tài khoản** và **lách giới hạn**.
- Anthropic (và ở mức thấp hơn là OpenAI) có cơ chế chính thức để **một người** tách nhiều tài khoản của mình theo thư mục cấu hình. Google thì **chưa có** cho `agy` (issue #155, #381 đang mở).
- Việc tự chuyển sang tài khoản thuê bao khác khi hết hạn mức (như AgentsRoom làm với Claude/Codex) là vùng xám, nghiêng về "bypassing protective measures" / "circumvent rate limits". **cad-guard không làm.**

## 5. Thế nào là "nhiều tài khoản" hợp lệ cho khách của cad-guard

Khách là công ty sản xuất nội thất, nhiều nhân viên ở 3–4 phòng (`packages/core/cadguard/app/departments.json`: Thiết kế, Kỹ thuật, Lập trình sản xuất…). Các mẫu hợp lệ:

1. **Mỗi nhân viên, một tài khoản doanh nghiệp, trên máy của mình.**
   - Quản trị Google Workspace/Cloud của khách gán giấy phép Gemini Enterprise theo người.
   - Nhân viên tự mở `agy` và chọn "Business account".
   - cad-guard chỉ **kiểm** đã đăng nhập chưa và loại tài khoản (`_meta.antigravity.tier`). Không bao giờ đăng nhập hộ.
   - Đây là "nhiều tài khoản" theo nghĩa **nhiều người**, không phải một máy nhiều tài khoản.
2. **Khoá API hoặc ADC theo dự án Google Cloud của công ty**, gắn theo phòng hoặc dự án:
   - Ví dụ dự án GCP `noithat-thietke` cho phòng Thiết kế, `noithat-kythuat` cho phòng Kỹ thuật.
   - Lý do tách là **phân bổ chi phí và quyền**, không phải cộng dồn hạn mức.
   - Khoá do IT của khách tạo trong dự án có thanh toán. Lưu trong kho khoá hệ điều hành dưới tên của **cad-guard** (không phải của `agy`).
   - cad-guard đưa khoá vào môi trường của tiến trình con lúc chạy.
3. **Nhiều kết nối khác nhà cung cấp** (Gemini, Anthropic API, OpenAI API, Ollama cục bộ):
   - người dùng chọn tay theo dự án;
   - đổi nhà cung cấp do người dùng quyết thì không phải né hạn mức.

**Không hợp lệ hoặc không làm:**

- một tài khoản doanh nghiệp dùng chung cho nhiều nhân viên (chia sẻ tài khoản);
- tài khoản Google cá nhân;
- xoay vòng tài khoản hay khoá khi gặp 429 / hết hạn mức;
- proxy gộp token;
- đọc, sao chép hay chuyển token giữa máy;
- ghi đè kho khoá của `agy`;
- tạo thêm dự án hay khoá chỉ để có thêm hạn mức.

## 6. Thiết kế đề xuất: "kết nối AI"

Tên khái niệm là **"kết nối AI"** (`ai_connection`), không gọi là "hồ sơ". Lý do: "hồ sơ" (`--profile`, `profile.py`) đã dùng cho hồ sơ chuẩn bản vẽ.

### 6.1 Mô hình dữ liệu

Tệp `cg.ai-connections/1`. Đề xuất chỗ lưu:

- danh sách kết nối: thư mục cấu hình người dùng, ví dụ `%APPDATA%\cad-guard\ai-connections.json`;
- dự án gắn kết nối nào: lưu trong thư mục dự án (`.cadguard/ai.json`, chỉ chứa `connection_id`).

Tệp **không bao giờ** chứa khoá hay token.

```json
{
  "schema": "cg.ai-connections/1",
  "default": "kt-gemini-key",
  "connections": [
    {
      "id": "kt-gemini-key",
      "name": "Kỹ thuật – Gemini (khoá dự án GCP)",
      "engine": "agy-cli",
      "account_type": "api-key",
      "credential": {"source": "os_keyring", "ref": "conn:kt-gemini-key"},
      "model": null,
      "departments": ["ky-thuat"],
      "note": "Dự án GCP có thanh toán của phòng Kỹ thuật"
    },
    {
      "id": "tk-agy-business",
      "name": "Thiết kế – tài khoản doanh nghiệp của tôi",
      "engine": "agy-cli",
      "account_type": "business",
      "credential": {"source": "cli_login"},
      "departments": ["thiet-ke"]
    },
    {
      "id": "adc-sx",
      "name": "Lập trình SX – ADC",
      "engine": "agy-cli",
      "account_type": "adc",
      "credential": {"source": "adc", "quota_project": "noithat-sx", "location": "global"},
      "departments": ["lap-trinh-san-xuat"]
    },
    {
      "id": "anthropic-cty",
      "name": "Anthropic API của công ty",
      "engine": "anthropic",
      "account_type": "api-key",
      "credential": {"source": "os_keyring", "ref": "conn:anthropic-cty"},
      "model": "claude-sonnet-5-5"
    }
  ]
}
```

Các trường:

- `engine`: tên engine đã có trong `cadguard/assistant` (`agy-cli`, `claude-cli`, `codex-cli`, `anthropic`, `openai`, `gemini`, `openrouter`, `ollama`).
- `account_type`:
  - với `agy-cli`: `business` | `api-key` | `adc` (`personal` luôn bị từ chối, như `AGY_ACCOUNTS` hiện nay);
  - với `claude-cli` / `codex-cli`: `subscription` | `api-key`;
  - với engine C: `api-key` | `local`.
- `credential.source`:
  - `cli_login`: CLI tự đăng nhập. cad-guard không chạm gì, chỉ kiểm bằng mã thoát hoặc `agy acp` `initialize` + `session/new` (không gửi lời nhắc).
  - `os_keyring`: khoá của **khách**, lưu trong kho khoá hệ điều hành, service `cad-guard`, username `conn:<id>`. Đây là mở rộng `keys.py` hiện có (hiện chỉ một khoá cho mỗi nhà cung cấp).
  - `env`: tên biến môi trường. Lưu tên biến, không lưu giá trị.
  - `adc`: `agy` chạy với `AGY_ADC_AUTH=true` (kèm `GOOGLE_CLOUD_QUOTA_PROJECT`, `GOOGLE_CLOUD_LOCATION`). Thông tin ADC do `gcloud` quản lý, cad-guard không đọc.
  - `none`: Ollama cục bộ.
- `departments` / gắn dự án: cad-guard chọn kết nối theo thứ tự sau:
  1. người dùng chọn trong phiên;
  2. kết nối gắn với thư mục dự án;
  3. kết nối mặc định của phòng;
  4. `default`.

  Không có bước tự chuyển sang kết nối khác.

Tuỳ chọn (chờ CEO duyệt, mục 7): `config_dir` cho `claude-cli` (`CLAUDE_CONFIG_DIR`) và `codex-cli` (`CODEX_HOME`):

- Đây là cách **chính thức** để một người giữ tài khoản công ty tách khỏi tài khoản riêng.
- Người dùng tự đăng nhập trong terminal, ví dụ đặt `CLAUDE_CONFIG_DIR=…` rồi chạy `claude auth login`.
- cad-guard chỉ đặt biến thư mục cho tiến trình con, không đọc tệp trong đó.
- `agy` không có trường tương ứng.

### 6.2 Tác động lên mã hiện có

- `cli_engines.child_env` hiện "không thêm, không bớt biến xác thực" (đã chốt cho `claude-cli` vì trang pháp lý Anthropic). Kết nối `agy-cli` loại `api-key`/`adc` **cần thêm** `GEMINI_API_KEY` (lấy từ kho khoá lúc chạy) hoặc `AGY_ADC_AUTH`/`GOOGLE_CLOUD_*` vào môi trường tiến trình con.
  - Việc này **đổi nguyên tắc**, nên cần CEO/QC duyệt.
  - Đề xuất giới hạn: chỉ **thêm**, chỉ cho kết nối khách tự khai báo, chỉ cho `agy-cli`/engine C. `claude-cli` vẫn giữ nguyên môi trường.
- `AgyCliEngine(account=…)` nhận thêm `connection`. `check_allowed` giữ nguyên: chặn tài khoản cá nhân, thêm `adc`.
- `keys.py`: thêm `get_key(provider, ref=None)` để mỗi kết nối có khoá riêng, tương thích ngược với khoá theo nhà cung cấp.
- `app/chat.py engines()`: thêm danh sách kết nối và trạng thái từng kết nối.

### 6.3 Giao diện (ứng dụng `cadguard app`)

Trang **Cài đặt › Kết nối AI**:

- **Bảng kết nối**: tên, engine, loại tài khoản, nguồn xác thực (chữ, ví dụ "kho khoá hệ điều hành", "CLI tự đăng nhập"), phòng/dự án gắn, trạng thái, nhãn "mặc định".
- **Thêm/Sửa**: biểu mẫu chọn engine → loại tài khoản (chỉ hiện các loại hợp lệ; `agy-cli` không có "cá nhân") → nguồn xác thực → mô hình → phòng.
  - **Không có ô nhập khoá trên trình duyệt** (giữ nguyên tắc hiện tại "khoá không bao giờ đi qua trình duyệt").
  - Giao diện hiện lệnh để chạy trong terminal, ví dụ `cadguard keys set --connection kt-gemini-key`. Nếu CEO muốn nhập khoá trên giao diện thì xem mục 7.
- **Xoá**: xoá kết nối và **hỏi** có xoá khoá tương ứng của cad-guard trong kho khoá không. Không bao giờ đụng mục của `agy`/`claude`/`codex`.
- **Kiểm tra**: nút "Kiểm" chạy kiểm tra không tốn hạn mức:
  - CLI: `--version`, trạng thái đăng nhập bằng mã thoát;
  - `agy`: `acp` `initialize` + `session/new` để đọc tier, **từ chối nếu là tài khoản cá nhân**;
  - khoá: chỉ có/không, không in giá trị.
- **Chọn mặc định theo dự án/phòng**: trong màn hình dự án có ô "Kết nối AI" (mặc định kế thừa từ phòng).
- **Khi hết hạn mức (429)**: hiện thông báo tiếng Việt kèm thời điểm thử lại nếu nhà cung cấp trả về. **Không** có nút "chuyển sang tài khoản khác cùng nhà cung cấp". Người dùng có thể tự chọn kết nối khác nhà cung cấp. cad-guard ghi sự kiện ẩn danh (chỉ mã băm kết nối, không tên) để quản trị thấy nhu cầu nâng gói.

### 6.4 Những gì cad-guard KHÔNG làm

- Không đọc, ghi, sao chép, làm mới hay chuyển token của `agy`, `claude`, `codex` (kho khoá `gemini:antigravity`, `.credentials.json`, `auth.json`).
- Không ghi đè kho khoá của CLI để "đổi tài khoản". Không đặt `HOME`/`USERPROFILE` giả để lách.
- Không xoay vòng tài khoản hay khoá khi gặp 429 hoặc gần hết hạn mức. Không chọn kết nối theo "hạn mức còn nhiều nhất".
- Không chạy proxy hay gateway gộp token. Không đưa token thuê bao sang công cụ khác.
- Không hỗ trợ tài khoản Google cá nhân cho `agy-cli`.
- Không đăng nhập hộ người dùng. Không chuyển thông tin xác thực giữa máy.
- Không ghi khoá ra tệp. Không đưa khoá qua trình duyệt, log, telemetry, báo cáo.
- Không khuyến khích tạo thêm dự án hay khoá để có thêm hạn mức. Tài liệu hướng dẫn khách **nâng gói / xin tăng quota** theo đường chính thức.

## 7. Điểm cần CEO quyết

1. **Duyệt mô hình "kết nối AI"** (mục 6). Phạm vi "nhiều tài khoản" chỉ là: nhiều người, mỗi người tài khoản doanh nghiệp riêng; và/hoặc khoá/ADC theo dự án GCP của phòng. Không xoay vòng.
2. **Đổi nguyên tắc "không thêm biến xác thực"** cho `agy-cli` (thêm `GEMINI_API_KEY` từ kho khoá, hoặc `AGY_ADC_AUTH`) và cho engine C. `claude-cli` giữ nguyên.
3. **Khoá đặt theo phòng hay theo dự án**, và ai giữ khoá (IT của khách hay từng nhân viên). Chỉ chấp nhận dự án **có thanh toán**? Đề xuất: có, vì gói không trả phí cấm gửi thông tin mật.
4. **Nhập khoá trên giao diện hay chỉ qua terminal.** Đề xuất: chỉ terminal (giữ nguyên tắc hiện tại).
5. **Hết hạn mức thì làm gì.** Đề xuất: chỉ báo, người dùng tự chọn kết nối **khác nhà cung cấp**; không tự chuyển cùng nhà cung cấp.
6. **Có hỗ trợ `CLAUDE_CONFIG_DIR` / `CODEX_HOME` theo kết nối không** (cách chính thức để một người tách tài khoản công ty với tài khoản riêng).
7. **Có hỏi Google bằng văn bản không** (qua kênh Gemini Enterprise): `cad-guard` khởi chạy `agy -p` với tài khoản Business có được phép không. FAQ chỉ nói "not supported under consumer plans". Đến khi có trả lời, `agy-cli` + `business` vẫn để nhãn "chưa rõ điều khoản".
8. **Có theo dõi issue #155/#381** của `google-antigravity/antigravity-cli` không. Nếu Google thêm bộ chọn hồ sơ chính thức thì có thể hỗ trợ nhiều tài khoản doanh nghiệp trên một máy mà không chạm kho khoá.

## 8. Còn chưa chắc

- `--settings` có thật sự cô lập `modelProvider` theo tiến trình không (AgentsRoom nói "key mode" toàn máy). Cần thử có khoá.
- ADC theo tiến trình cho `agy` (ví dụ `GOOGLE_APPLICATION_CREDENTIALS` hoặc `CLOUDSDK_CONFIG` riêng): tài liệu không nhắc.
- Tên tier nào là "cá nhân" trong `_meta.antigravity.tier` (đã ghi ở `antigravity.md`).
- Bài X ngày 27/02/2026 và vai trò của người đăng bài diễn đàn 12/03/2026: chưa đối chiếu với nguồn gốc.
- Văn bản Terms of Use của OpenAI: đọc qua chỉ mục tìm kiếm vì trang chặn tải trực tiếp.

## Nguồn

Chính thức:

- [Antigravity FAQ](https://antigravity.google/docs/faq/)
- [Antigravity Terms](https://antigravity.google/terms)
- [Antigravity – cài đặt & xác thực CLI](https://antigravity.google/docs/install)
- [Gemini CLI Terms & privacy](https://geminicli.com/docs/resources/tos-privacy)
- [Google APIs Terms](https://developers.google.com/terms)
- [Gemini API Additional Terms](https://aistudio.google.com/docs/terms)
- [Claude Code Authentication](https://code.claude.com/docs/en/authentication)
- [Anthropic Consumer Terms](https://www.anthropic.com/legal/consumer-terms)
- [OpenAI Terms of Use](https://openai.com/policies/row-terms-of-use/)
- [OpenAI Services Agreement](https://openai.com/policies/services-agreement/)

GitHub issues (repo chính thức của Google, chỉ có issue):

- `google-antigravity/antigravity-cli` #155 "Add equivalent to GEMINI_CLI_HOME env variable" (mở từ 24/05/2026)
- `google-antigravity/antigravity-cli` #381 "supported auth profile selection for wrappers and headless workflows" (mở từ 13/06/2026)

Thứ cấp và diễn đàn:

- [AgentsRoom blog](https://agentsroom.dev/blog/multiple-accounts-antigravity-cli)
- [Techzine](https://www.techzine.eu/news/privacy-compliance/139032/google-intervenes-in-heavy-use-of-antigravity-and-gemini)
- [The Register](https://www.theregister.com/2026/02/23/google_antigravity_compute_burden/)
- [Diễn đàn Google AI – Update on Antigravity ToS ban](https://discuss.ai.google.dev/t/update-on-antigravity-tos-ban/131424)
- README các repo ở mục 1
