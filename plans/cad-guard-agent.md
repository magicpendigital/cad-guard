# cad-guard thành "Coding Agent cho nội thất" — research, phân tích, đánh giá

Trạng thái: **ĐỀ XUẤT, chờ CEO duyệt** (04/11/2026). Bổ sung cho `plans/cad-guard.md` (Tầng 2, Tầng 3) và `plans/cad-guard-direction.md` (hướng theo tệp, DXF chung). Chưa viết code.
Cách đọc nguồn: mục 2 tách rõ **đã kiểm trên tài liệu chính thức** và **chỉ thấy ở nguồn thứ cấp (blog/diễn đàn), chưa kiểm**. Nhiều thứ trong mảng này đổi theo tháng; trước khi cam kết với khách phải kiểm lại.

## 1. Kết luận ngắn

**Hướng đúng, đáng làm, nhưng nên đổi cách làm so với trực giác ban đầu.** Ba khuyến nghị cốt lõi:

1. **Không tự viết "agent harness" (vòng lặp agent, công cụ file/shell, quản lý ngữ cảnh, giao diện terminal).** Phần đó đã có sẵn ở Claude Code, Codex CLI, OpenCode, Antigravity CLI… và đang đổi nhanh. Thứ chỉ ta có là **bộ công cụ + tri thức + kiểm chứng tất định cho bản vẽ nội thất**. Làm ba thứ đó trước, vỏ (shell) làm sau và mỏng.
2. **Dùng ACP (Agent Client Protocol) làm cổng nối tới các CLI agent, và MCP làm cổng đưa công cụ cad-guard cho agent.** Một lần làm client ACP là nối được hơn 40 agent (mục 2.1). Chế độ "API trực tiếp" (OpenRouter, Anthropic, OpenAI, Gemini…) giao cho một engine có sẵn (đề xuất OpenCode qua `opencode acp`), không tự viết lớp nhà cung cấp.
3. **Đừng lấy "đăng nhập bằng gói thuê bao của người dùng" làm trụ của sản phẩm.** Anthropic đã cấm bên thứ ba cấp đăng nhập claude.ai hoặc định tuyến yêu cầu qua gói Pro/Max (mục 2.2). Đường an toàn và đã được cho phép là: **chạy nguyên bản CLI chưa sửa trên máy người dùng, người dùng tự đăng nhập**, hoặc dùng khoá API của chính khách. Hai đường còn lại (OpenAI, Google) chưa thấy văn bản cho phép rõ ràng.

Điều làm bài toán này khác "Coding Agent cho phần mềm" và khiến nó **khả thi hơn nhiều**: bản vẽ DXF là văn bản có cấu trúc, mà ta đã có sẵn thứ giống "trình biên dịch + bộ test" của code — **bộ luật tất định** (16/58 luật đã cài). Nghĩa là agent có thể được **chấm đúng/sai bằng máy**, không cần người đọc từng kết quả. Đó là lợi thế lớn nhất và là hàng rào cạnh tranh.

Điều cần cảnh giác nhất: **chưa có bằng chứng nhu cầu**. `docs/discovery.md` vẫn "CHƯA ĐIỀN"; "thợ vẽ muốn chat để ra lệnh" là giả thuyết, chưa phải dữ kiện. Và có một xung đột trực tiếp với quy tắc dữ liệu của repo (mục 5.1).

## 2. Research

### 2.1 Cổng nối tới CLI agent: ACP đã là chuẩn thực tế

- ACP do Zed khởi xướng: JSON-RPC 2.0 qua stdin/stdout, client (trình soạn/ứng dụng) chạy agent như tiến trình con. Danh sách agent công bố ở [agentclientprotocol.com](https://agentclientprotocol.com/overview/agents) (**đã kiểm**) gồm: Claude Agent (qua adapter SDK của Zed), Codex CLI (qua adapter), Gemini CLI, OpenCode, Cursor, GitHub Copilot, Goose, Cline, OpenHands, Junie, Kimi CLI, Qwen Code, Mistral Vibe, Factory Droid, Kiro CLI… (hơn 40 mục).
- OpenCode: `opencode acp` chạy qua stdio JSON-RPC, giữ nguyên công cụ, MCP, `AGENTS.md`, quyền; một số lệnh như `/undo`, `/redo` chưa hỗ trợ trong ACP ([opencode.ai/docs/acp](https://opencode.ai/docs/acp/), **đã kiểm**). `opencode serve` cho máy chủ HTTP có OpenAPI + SDK `@opencode-ai/sdk` (nguồn thứ cấp, chưa kiểm trên trang chính thức).
- Codex CLI: có `codex exec --json` (một lần) và `codex app-server` (JSON-RPC giàu tính năng, có phê duyệt từ phía máy chủ); các SDK cộng đồng ghi là còn **thử nghiệm, API chưa ổn định** (thứ cấp).
- Claude Code: có chế độ không giao diện (`-p`, `--output-format json`) và Agent SDK (Python/TypeScript) với công cụ, hooks, subagent, MCP, quyền, phiên ([tài liệu Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview), **đã kiểm**).
- Antigravity CLI (`agy`): ra mắt 19/05/2026, kế nhiệm Gemini CLI (bản cũ ngừng phục vụ 18/06/2026); viết bằng Go, hỗ trợ MCP, skills, hooks, subagent (thứ cấp). Có adapter ACP chính thức trong ACP Registry theo diễn đàn Google (thứ cấp). Cờ chạy không giao diện và cách xác thực **các nguồn mâu thuẫn nhau** (một bên nói OAuth là chính, một bên nói đặt `GEMINI_API_KEY`); ví dụ `agy -p` không in gì khi stdout không phải terminal thật. **Phải tự thử trên máy.**
- Điểm chung quan trọng: cả bốn đều đọc được `AGENTS.md`/skills và gọi được công cụ qua MCP. Vì vậy **tri thức nội thất viết một lần dưới dạng markdown + công cụ MCP dùng chung được cho mọi CLI** — đây là chỗ đáng đầu tư nhất.

### 2.2 Đăng nhập và điều khoản (rủi ro pháp lý số 1)

| Nhà cung cấp | Điều đã kiểm | Điều chưa rõ |
| --- | --- | --- |
| **Anthropic** | [Trang pháp lý Claude Code](https://code.claude.com/docs/en/legal-and-compliance) (**đã kiểm**): OAuth chỉ dành cho người mua gói thuê bao dùng Claude Code và ứng dụng gốc của Anthropic. Nhà phát triển sản phẩm (kể cả dùng Agent SDK) phải dùng khoá API; **không được cấp đăng nhập claude.ai hay định tuyến qua thông tin gói Free/Pro/Max/Ultra thay cho người dùng, không được thu thập/lưu/làm trung gian thông tin đăng nhập**. Cho phép: chạy Claude Code **không sửa đổi** trong sản phẩm/sandbox của mình, **mỗi người dùng tự xác thực bằng khoá API, gói thuê bao hoặc nhà cung cấp 3P của chính họ**; công ty không được trả tiền/bán lại/làm trung gian cho người dùng. Không được dùng tên/logo "Claude Code" trong tên sản phẩm. | Nguồn thứ cấp nói từ 04/04/2026 gói thuê bao không còn bao phủ "harness bên thứ ba" (phải bật dùng thêm). Chưa kiểm trên tài liệu Anthropic. Adapter ACP của Zed cho Claude chạy trên Agent SDK — theo câu "trừ khi đã được duyệt trước" ở trang SDK thì **chưa rõ nó rơi vào phía nào**. |
| **OpenAI** | Trang xác thực Codex ([learn.chatgpt.com/docs/auth](https://learn.chatgpt.com/docs/auth), **đã kiểm**): hỗ trợ "Sign in with ChatGPT" và khoá API; đăng nhập không màn hình bằng `codex login --device-auth` (beta); thông tin lưu ở `~/.codex/auth.json` hoặc kho khoá hệ điều hành; có `CODEX_ACCESS_TOKEN` cho tự động hoá doanh nghiệp (admin cấp). | Trang **không nói gì** về việc ứng dụng bên thứ ba dùng đăng nhập ChatGPT. Plugin cộng đồng cho OpenCode dùng được và tự ghi "chỉ dùng cá nhân". Không có văn bản cho phép. |
| **Google** | Chỉ nguồn thứ cấp/diễn đàn. | Có chủ đề diễn đàn hỏi đúng câu này (gọi `agy` từ trợ lý cục bộ trên tài khoản cá nhân) và trả lời cộng đồng dẫn một điều khoản cấm công cụ bên thứ ba — chưa phải kết luận chính thức. |

Hệ quả thiết kế (không phụ thuộc vào việc điều khoản sau này nới hay siết):

- cad-guard **không bao giờ chạm vào token/OAuth của người dùng**. Chỉ khởi chạy CLI nguyên bản, để CLI tự đăng nhập; không đọc, không sao chép, không chuyển `auth.json`/keyring.
- Mỗi nhân viên dùng thông tin đăng nhập của **chính họ hoặc của công ty** (khoá API doanh nghiệp, Bedrock/Vertex, gói Team/Enterprise). Công ty (hoặc ta) không mua một gói rồi chia cho cả phòng.
- Đường mặc định của sản phẩm = **khoá API của khách (BYOK)**; đăng nhập thuê bao là "tiện ích tuỳ chọn, theo từng nhà cung cấp, có thể bị tắt". Ghi vào hợp đồng.
- **Việc cần người:** gửi câu hỏi bằng văn bản cho Anthropic (sales), OpenAI, Google: "ứng dụng X chạy nguyên bản CLI của quý vị làm tiến trình con qua ACP trên máy khách hàng, người dùng tự đăng nhập — có được phép không?". Thường mất vài tuần; bắt đầu sớm.

### 2.3 Cổng LLM trực tiếp (API)

- **OpenRouter**: dịch vụ đám mây, một tài khoản gọi hơn 400 mô hình; không tự host được (thứ cấp). **Vercel AI Gateway**: chỉ chạy trong Vercel. **LiteLLM**: tự host, chuyển đổi đa nhà cung cấp; một bảng so sánh ghi giấy phép "BSL 1.1" trong khi trang khác gọi là mã nguồn mở — **phải đọc giấy phép gốc** trước khi nhúng (theo quy tắc `docs/licenses.md`).
- Đánh giá: với dữ liệu bản vẽ có thể bị NDA, một bên trung gian thứ ba (OpenRouter) thêm một chặng chuyển dữ liệu; nên để **tuỳ chọn, mặc định tắt**, ưu tiên gọi thẳng nhà cung cấp hoặc cổng tự host. Nếu dùng OpenCode làm engine thì lớp nhà cung cấp đã có sẵn, ta không cần chọn cổng riêng (OpenCode hỗ trợ nhiều nhà cung cấp theo hiểu biết của tôi; **trang ACP tôi đọc không liệt kê, chưa kiểm**).
- Mô hình cục bộ (Ollama/vLLM qua OpenCode) là đường duy nhất thật sự "không rời máy" — đáng có dưới dạng chế độ thử nghiệm để nói chuyện NDA với khách, dù chất lượng tiếng Việt và gọi công cụ sẽ kém hơn mô hình lớn (chưa đo).

### 2.4 Bối cảnh sản phẩm quanh bản vẽ và nội thất

- **Chat trong CAD đã có** nhưng là trợ giúp lệnh/tài liệu: Autodesk Assistant và Markup Assist trong AutoCAD, BricsCAD Assist/AI Assist (nguồn thứ cấp, chưa kiểm trên trang hãng). Không thấy công cụ nào kiểm bản vẽ theo **chuẩn riêng của một xưởng nội thất**.
- **MCP cho CAD đã có, còn non**: nhiều máy chủ MCP cộng đồng cho AutoCAD (COM, cần AutoCAD đang chạy trên Windows; một số hỗ trợ tạo DXF không cần giao diện), MCP cho FreeCAD trong nghiên cứu TOOLCAD (arXiv 2604.07960). Phần lớn tập trung **vẽ mới từ văn bản**, không phải kiểm/chuẩn hoá bản vẽ có sẵn. Chưa thấy ai làm tốt, ổn định, có kiểm chứng.
- **Phần mềm đồ gỗ chuyên dụng** (Cabinet Vision của Hexagon, v.v.): AI chủ yếu ở diễn hoạ/thiết kế; bảng cắt đến từ **luật trong engine**, không từ AI; AI bắt đầu xuất hiện ở nesting/CNC (một "PN Assistant" sửa chi tiết bằng tiếng Anh thường — vendor, thứ cấp). Polyboard/imos/Microvellum: kết quả tìm không cho thông tin → chưa biết.
- Đánh giá của tôi: **ô trống có thật** (agent hiểu chuẩn nội thất + tệp trung gian + nối sản xuất), nhưng hãng CAD sẽ tự thêm chat chung; hàng rào của ta không phải "có chat" mà là **chuẩn + luật + dữ liệu lỗi thật của khách + nối xuống xưởng**.

## 3. Phân tích: ánh xạ "Coding Agent" → "Drawing Agent"

| Phần mềm | Bản vẽ nội thất | Ghi chú |
| --- | --- | --- |
| Mã nguồn | DXF (+ Drawing Model JSON) | DXF là văn bản nhưng rất dài; agent không nên đọc thô mà **truy vấn mô hình** |
| Trình biên dịch/linter/test | `cadguard audit` (bộ luật tất định) | Đây là "vòng phản hồi" để agent tự sửa → chạy lại → xanh. Có thể làm tự động nhiều vòng |
| `git diff` | So sánh DXF (đối tượng thêm/xoá/đổi, theo handle) + ảnh trước/sau | **Phải xây**; không có sẵn, và là thứ quyết định độ tin cậy |
| commit/branch/revert | Luôn ghi **tệp mới** có phiên bản; gốc không bao giờ bị ghi đè | Đã là quy tắc của repo |
| Code review | Xem trước + người duyệt trước khi bản mới thành "bản chính" | |
| Agent chạy lệnh shell | **Không có** shell; chỉ có các công cụ cad-guard | An toàn là vì ta *không đưa* công cụ chung chung |
| Tìm trong repo | Tìm trong thư mục dự án theo mã băm/tên bản vẽ; tra chuẩn | |
| Skills/`AGENTS.md` | Gói tri thức: chuẩn `furniture-v0`, quy ước dán cạnh, layer CNC, từ vựng ngành bằng tiếng Việt | Dùng chung mọi CLI |
| SWE-bench | **Bộ chấm nội bộ** (mục 6.2) | Chấm tất định nên so được mô hình/nhà cung cấp bằng số |

### 3.1 Bề mặt công cụ cho agent (MCP server `cadguard mcp`)

Công cụ **chỉ đọc** (phát hành trước): `list_drawings`, `audit` (trả `Finding[]`), `explain_rule(rule_id)`, `query_model` (layer, khối, kích thước, bộ phận, theo bộ lọc), `get_entity(handle)`, `render_preview(bbox|layout)` → SVG/PNG, `compare(a, b)`.
Công cụ **ghi** (sau, chỉ ghi ra tệp mới): `propose_changeset` (chạy khô, ra bản xem trước), `apply_changeset` (cần xác nhận, ghi tệp mới), `validate_output` (mở lại, đếm đối tượng, kiểm layer bảo vệ, chạy lại luật).
Về sau: `extract_parts`/`bom`, `cutlist`, `export_cnc_layers`.

### 3.2 Hai cách agent "ra lệnh sửa" — chọn có điều kiện

- **A. Từ vựng thao tác cố định** (đổi layer, đổi kiểu chữ…, như `plans/cad-guard.md` mục 4 Tầng 2): an toàn, kiểm duyệt dễ, nhưng giới hạn; lệnh như "đổi hết chữ 3.5 sang 2.5 trừ khung tên" cần nhiều toán tử.
- **B. Agent viết kịch bản ezdxf (code-as-action)** chạy trong sandbox trên **bản sao**, rồi hệ thống tự chuyển kết quả thành bản diff để duyệt: rất mạnh cho phần đuôi dài ("coding agent" đúng nghĩa), nhưng bề mặt rủi ro lớn hơn.
- **Đề xuất:** làm A trước cho ~8 loại sửa phổ biến (khớp P2). Mở B sau, **chỉ khi** có sandbox (tiến trình riêng, không mạng, không ghi ngoài thư mục làm việc), `validate_output` bắt buộc và quy tắc "không có xác nhận thì không sinh tệp chính". Quyết định cần CEO/đội: có chấp nhận B không.

## 4. Kiến trúc đề xuất

```text
Người dùng (chat / lệnh / duyệt xem trước)
   │
[Vỏ cad-guard]  giai đoạn 1: không có vỏ riêng, chỉ "gói làm việc" mở bằng CLI sẵn có
                 giai đoạn 2: ứng dụng ACP client + trình xem DXF + hộp duyệt thay đổi
   │  ACP (JSON-RPC/stdio)                      ┌─ Claude Code (người dùng tự đăng nhập / API key)
   ├────────────────────────────────────────────┼─ Codex CLI · Antigravity CLI (người dùng tự đăng nhập)
   │                                            └─ OpenCode  ← chế độ BYOK: OpenRouter / Anthropic / OpenAI / Gemini / cục bộ
   │  MCP (stdio)
[cadguard mcp]  ← công cụ mục 3.1, KHÔNG có shell/đọc file tuỳ ý
   │
[Lõi Python hiện có]  Drawing Model · bộ luật · báo cáo · (mới) diff, changeset, sandbox ezdxf
   │
DXF (tệp gốc không ghi; chỉ ghi tệp mới)  ← adapter theo từng phần mềm CAD (hướng đã duyệt)
```

Nguyên tắc:

- **Công cụ là hợp đồng, nhà cung cấp là phần thay được.** Cùng một `cadguard mcp` chạy dưới mọi agent; đổi mô hình không phải viết lại.
- **Tri thức nằm trong repo dưới dạng văn bản** (`knowledge/` gồm `AGENTS.md` cho khách, skills theo khâu: kiểm bản vẽ, chuẩn hoá, ghi chú bàn giao, bóc tách). Có phiên bản gắn với `furniture-v0.x`.
- **Quy tắc đã có vẫn là luật cứng**: phát hiện lỗi bằng code; LLM giải thích/đề xuất/điều phối; sửa chỉ ra tệp mới có xem trước và hoàn tác; số liệu ra ngoài là tổng hợp.

### 4.1 Ba lựa chọn về "vỏ", đánh giá

| Lựa chọn | Nội dung | Công sức | Ưu | Nhược |
| --- | --- | --- | --- | --- |
| **V1. Chỉ gói làm việc + MCP** | Thư mục mẫu (`AGENTS.md`, cấu hình MCP, skills, hook an toàn) mà người dùng mở bằng CLI họ có | Nhỏ (tuần) | Rẻ, kiểm giả thuyết nhu cầu ngay; nhận mọi nâng cấp của CLI | Người kỹ thuật phải quen terminal/CLI; chưa có trình xem bản vẽ |
| **V2. Ứng dụng ACP client + trình xem** | Cửa sổ chat + xem DXF + duyệt thay đổi; chạy bất kỳ agent ACP | Vừa–lớn (tháng) | Trải nghiệm hợp nghiệp vụ; chọn mô hình ở một chỗ; **kiểm soát quyền file từ phía client** | Phải duy trì client; adapter mỗi agent mỗi khác |
| **V3. Tự viết harness riêng (gọi API)** | Vòng lặp agent riêng | Lớn, liên tục | Toàn quyền | Giành lại điều mà CLI/OpenCode đã làm; **không nên** |

→ **V1 ngay, V2 khi V1 chứng minh nhu cầu, bỏ V3.** Chế độ BYOK đạt được bằng cách cho V2 nói chuyện với `opencode acp` (cần kiểm giấy phép OpenCode và mức ổn định ACP trước khi cam kết; tôi chưa kiểm giấy phép).

## 5. Rủi ro và cách xử lý

### 5.1 Xung đột với quy tắc dữ liệu của repo (nghiêm trọng)

`AGENTS.md` cấm đưa bản vẽ thật vào prompt/repo/worktree của agent. Một sản phẩm agent trên máy khách thì **chính là** đưa nội dung bản vẽ cho LLM. Hai mức cần tách:

- *Agent phát triển* (Claude/Codex làm việc trong repo này): giữ nguyên quy tắc, chỉ DXF tổng hợp.
- *Agent sản phẩm* (chạy ở khách): phải có **chế độ dữ liệu theo bậc**, quyết bằng văn bản đồng ý ở P0 (mục 4 của `docs/discovery.md` đã có ô này):
  - Bậc 0: không LLM — các luật tất định (đã có).
  - Bậc 1: LLM chỉ thấy **kết quả công cụ đã ẩn danh** (mã băm thay tên, bỏ chữ trong khung tên, số liệu thay hình); đây là mặc định.
  - Bậc 2: gửi ảnh/đoạn thô khi khách đồng ý rõ.
  - Bậc L: mô hình cục bộ cho khách không chấp nhận gửi đi.
- **Điểm nguy hiểm thực tế:** CLI agent có sẵn công cụ đọc file/chạy lệnh của riêng nó. Nếu mở nó ngay trong thư mục bản vẽ thật, nó đọc được mọi thứ, bỏ qua lớp ẩn danh của ta. Cần: tắt/chặn công cụ file và shell của CLI (qua cấu hình quyền), cho agent chạy trong **thư mục làm việc rỗng** chỉ chứa tệp của phiên, và chỉ cho đi qua `cadguard mcp`. Mức ép buộc khác nhau theo CLI → **phải kiểm từng CLI** và có test (agent cố đọc tệp ngoài thư mục thì bị từ chối).
- Khoá API: chỉ lưu trong kho khoá hệ điều hành, không ghi ra tệp (đúng quy tắc repo); không đưa vào log/telemetry.

### 5.2 Các rủi ro khác

| Rủi ro | Mức | Giảm thiểu |
| --- | --- | --- |
| Điều khoản đăng nhập thay đổi/siết thêm | Cao | Mục 2.2: BYOK mặc định; không chạm token; hỏi bằng văn bản; thiết kế để bỏ đăng nhập thuê bao mà không mất tính năng |
| Agent sửa sai làm hỏng bản vẽ sản xuất | Cao | Chỉ ghi tệp mới; `validate_output` bắt buộc; xem trước + người duyệt; layer bảo vệ; không có công cụ xoá |
| Mô hình đọc sai kích thước từ ảnh | Cao | Kích thước lấy từ mô hình dữ liệu qua công cụ, không từ ảnh; ảnh chỉ để người xem |
| Chất lượng tiếng Việt/thuật ngữ nội thất | Trung bình | Skills có từ điển ngành; đưa tiếng Việt vào bộ chấm (6.2) |
| Chi phí token (bản vẽ lớn) | Trung bình | Công cụ trả tóm tắt + phân trang; trần theo phiên/ngày; hiển thị chi phí |
| CLI đổi giao diện không báo trước (đặc biệt cờ không giao diện) | Trung bình | Chỉ nối qua ACP/MCP (giao thức) thay vì phân tích đầu ra terminal; test hợp đồng cho từng agent |
| Cạnh tranh: hãng CAD thêm chat | Trung bình | Hàng rào là chuẩn + luật + dữ liệu lỗi + nối xưởng, không phải chat |
| Mở rộng phạm vi ("tư vấn, sản xuất, thi công, lắp đặt") quá sớm | Cao | Mục 7: mỗi khâu là một gói riêng, chỉ mở khi P0 xác nhận nỗi đau |
| Thợ vẽ thấy bị giám sát | Trung bình | Nhật ký phiên nằm cục bộ; báo cáo tổng hợp (đã có trong kế hoạch) |

## 6. Đo lường: biến tính tất định thành lợi thế

### 6.1 Chỉ số sản phẩm (nối với `stats`/MCA)

`tasks_completed_pct` (tác vụ agent hoàn thành mà `validate_output` xanh), `changes_accepted_pct`, `findings_resolved_per_session`, `rules_regressed` (đáng ra phải bằng 0), `cost_per_session`, `time_saved` do người dùng tự báo. Vẫn chỉ số tổng hợp, không tên tệp/khách/thợ vẽ.

### 6.2 Bộ chấm nội bộ ("CAD-bench" của cad-guard)

Tập tác vụ trên DXF tổng hợp, mỗi tác vụ có kiểm tra tự động: "sửa mọi lỗi LY-xx trong `bad_layers.dxf` mà không làm hỏng luật khác", "đổi chữ 3.5→2.5 trừ khung tên", "tạo ghi chú bàn giao đúng", "trả lời đúng câu hỏi về bản vẽ (đếm tấm, tìm layer sai)". Chạy cùng tác vụ qua Claude/Codex/Gemini/mô hình cục bộ → bảng **chính xác – chi phí – thời gian**. Việc này (a) chọn mô hình mặc định bằng số, (b) bắt hồi quy khi CLI/mô hình đổi, (c) làm bằng chứng bán hàng. Rẻ vì tái dùng `fixtures.py` và `tests/`.

## 7. Phạm vi "toàn chuỗi" nội thất — các gói theo khâu

Mỗi khâu = một gói (công cụ + tri thức + bộ chấm), mở theo thứ tự nỗi đau thật, không hứa trước:

| Gói | Nội dung | Điều kiện mở |
| --- | --- | --- |
| G1 Kiểm & chuẩn hoá bản vẽ | Đã có lõi (16/58 luật), thêm hội thoại, diff, changeset | Làm ngay |
| G2 Bóc tách & bảng kê | Trích bộ phận, BOM, bảng cắt từ bản vẽ; so khớp hình ↔ bảng | Sau G1 + P0 cho thấy lỗi bảng kê đắt |
| G3 Thiết kế sản xuất | Layer/đơn vị cho CNC, kiểm khả thi gia công, nesting (tận dụng thư viện mở nếu giấy phép cho phép) | Biết phần mềm CNC đích (câu hỏi P0) |
| G4 Thi công & lắp đặt | Danh mục kiểm lắp đặt, khối lượng, đối chiếu bản vẽ hoàn công | Có dữ liệu sự cố hiện trường |
| G5 Tư vấn thiết kế/báo giá | Trợ lý tư vấn, tóm tắt yêu cầu khách, ước tính | Cần số liệu giá của công ty; khác hẳn bài toán bản vẽ, **chưa nghiên cứu** |

G4–G5 hiện chỉ là ý tưởng; tôi chưa có dữ liệu ngành hay khảo sát nào về chúng.

## 8. Lộ trình đề xuất (song song với P0–P2 hiện có)

| Bước | Nội dung | Cổng đi tiếp |
| --- | --- | --- |
| A0 (1–2 tuần) | `cadguard mcp` chỉ đọc (audit, query_model, explain_rule) + gói làm việc V1 + `AGENTS.md`/skills tiếng Việt; thử với 2–3 CLI trên **DXF tổng hợp** | Agent trả lời đúng ≥ ngưỡng trên bộ chấm; test chặn đọc tệp ngoài thư mục qua cả 3 CLI |
| A1 | Bộ chấm 6.2 + so sánh mô hình; kiểm tra 5.1 hoàn chỉnh; hỏi điều khoản (2.2) | Có bảng số; có phản hồi pháp lý hoặc quyết định chỉ BYOK |
| A2 (cùng P2) | Công cụ ghi: changeset, diff, `validate_output`, ảnh xem trước; lệnh tự nhiên → changeset | Không lần nào hỏng bản vẽ; người duyệt chấp nhận ≥ ngưỡng |
| A3 | Thử V1 với 2–3 người kỹ thuật thật (Wizard of Oz nếu cần) — **đo nhu cầu chat thật** | Họ dùng lại tuần sau mà không bị nhắc |
| A4 | V2: ACP client + trình xem; BYOK qua OpenCode; chế độ dữ liệu theo bậc | A3 đạt; giấy phép OpenCode/ACP đã kiểm |
| A5 | Mở B (kịch bản ezdxf trong sandbox) và G2 | Theo dữ liệu A2–A4 |

A0–A1 không cần bản vẽ khách và không phụ thuộc P0, nên có thể bắt đầu ngay mà không vi phạm quy tắc dữ liệu.

## 9. Quyết định cần CEO

| # | Câu hỏi | Đề xuất |
| --- | --- | --- |
| 1 | Chấp nhận định hướng "bộ công cụ + tri thức + kiểm chứng" thay vì tự viết harness | Có |
| 2 | Cổng nối: ACP cho CLI agent, MCP cho công cụ; BYOK qua OpenCode | Có, nhưng cổng A1/A4 kiểm giấy phép trước |
| 3 | Đăng nhập thuê bao chỉ là tiện ích tuỳ chọn; mặc định là khoá API của khách | Có; đồng thời cho phép tôi soạn thư hỏi 3 nhà cung cấp |
| 4 | Dữ liệu theo bậc 0/1/2/L; bậc 1 mặc định | Có; ghi vào văn bản đồng ý P0 |
| 5 | Cho phép agent viết kịch bản (B) sau A2, trong sandbox | Hoãn đến A5, quyết sau khi có số liệu |
| 6 | Ngân sách thử: chi phí token cho bộ chấm A1 (khoảng nhỏ, do đội đặt trần) | Cần CEO đặt trần |

## 9a. Quyết định đã chốt và điều chỉnh

| Ngày | Nội dung | Hệ quả |
| --- | --- | --- |
| 04/11/2026 | CEO xác nhận bối cảnh: **công ty sản xuất có ba phòng nối tiếp: Thiết kế, Kỹ thuật, Lập trình sản xuất** (rồi xưởng). Năm bản vẽ thật đã có thuộc khâu thiết kế/kỹ thuật (triển khai). Dữ liệu mẫu đã chuyển ra ngoài repo | Bắt đầu từ **vệ sinh và nhất quán bản vẽ** (đo được trên mẫu thật), bộ đọc bản vẽ lớn, hỏi đáp/khảo sát, chuẩn cấu hình theo công ty. `furniture-v0` giữ nguyên cho khâu cuối. Cần mẫu khâu kỹ thuật chi tiết và lập trình sản xuất để chọn luật hai khâu này (xem `docs/real-sample-profile.md` mục 4.1). Chuẩn mới cho khâu đầu: `design-hygiene-v0` |
| 04/11/2026 (đính chính) | Một bản ghi trước đó ghi "người dùng đích là đơn vị thiết kế" là **hiểu sai** bối cảnh; thay bằng dòng trên | Giao MCA lần 2 (w-4c26ae) viết theo hiểu biết cũ; phần nền (hợp nhất nhánh, bộ đọc lớn, MCP, hygiene) không đổi, phần `knowledge/` và lời văn "đơn vị thiết kế" cần chỉnh khi nghiệm thu |

Giao diện mẫu (`design/ui-mockup.html`) đã cập nhật theo chuỗi ba phòng (chọn phòng ở góc trên; mỗi phòng có bản vẽ, lỗi và gói bàn giao riêng; mã luật VS-/CN- là minh hoạ). Dữ liệu trong mẫu hoàn toàn minh hoạ, chưa qua người dùng thật.

## 10. Chưa xác định / chưa kiểm

- Điều khoản chính thức của OpenAI và Google về việc bên thứ ba dùng đăng nhập thuê bao; việc áp dụng của Anthropic cho adapter ACP chạy trên Agent SDK.
- Cờ chạy không giao diện và cách đăng nhập của `agy` (nguồn mâu thuẫn); tính ổn định của `codex app-server`.
- Giấy phép OpenCode, LiteLLM, các adapter ACP; ghi vào `docs/licenses.md` trước khi dùng.
- Danh sách nhà cung cấp OpenCode hỗ trợ và chất lượng chế độ BYOK qua ACP.
- Chất lượng gọi công cụ và tiếng Việt của mô hình cục bộ.
- Thị trường: phần mềm nội thất cụ thể đang dùng tại Việt Nam (Polyboard/imos/Microvellum… không có kết quả); tính năng AI hiện tại của AutoCAD/BricsCAD/ZWCAD chỉ từ nguồn thứ cấp.
- Nhu cầu thật của người dùng với giao diện chat (A3).
- Khâu thi công, lắp đặt, tư vấn: chưa có dữ liệu.

## 11. Nguồn đã dùng

- Anthropic, [Legal and compliance (Claude Code)](https://code.claude.com/docs/en/legal-and-compliance); [Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview).
- OpenAI, [Codex authentication](https://learn.chatgpt.com/docs/auth).
- [Agent Client Protocol — danh sách agent](https://agentclientprotocol.com/overview/agents); [OpenCode ACP](https://opencode.ai/docs/acp/).
- Thứ cấp (chưa kiểm trên trang chính thức): [Gigazine về việc Anthropic cấm xác thực thuê bao bên thứ ba](https://gigazine.net/gsc_news/en/20260220-anthropic-third-party-block); [Antigravity CLI](https://agentpedia.codes/blog/antigravity-cli-deep-dive); [diễn đàn Google về `agy` bên thứ ba](https://discuss.ai.google.dev/t/is-invoking-the-official-agy-cli-from-a-local-ai-coding-assistant-allowed-on-an-individual-google-ai-account/185992); [OpenCode server](https://opencode.ai/docs/de/server); [Codex SDK/app-server (cộng đồng)](https://codex.danielvaughan.com/2026/03/31/codex-cli-python-sdk-app-server-rpc/); [TOOLCAD](https://arxiv.org/pdf/2604.07960); [AutoCAD MCP cộng đồng](https://github.com/vigneshpbmenon/autocad-mcp-server); [so sánh cổng LLM](https://pinggy.io/blog/best_ai_llm_routers_openrouter_alternatives/); [Bricsys AI](https://bricsys.com/cad-software/cad-ai-software); [phần mềm tủ bếp 2026](https://www.myarchitectai.com/blog/cabinet-design-software).
