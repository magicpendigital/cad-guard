# Tích hợp OpenCode với cad-guard

Ngày kiểm: 04/11/2026. Bản đã cài và thử: `opencode` **1.19.4** (gói npm `opencode-ai`, Windows x64).

Quy ước ghi nguồn:

- **[tài liệu]** kèm link: đọc trên opencode.ai/docs hoặc repo chính thức.
- **[đã kiểm trên máy]** kèm lệnh: chạy trên máy với 1.19.4. Không lệnh nào gọi mô hình; không đọc `auth.json`.
- **[mã nguồn dev]**: đọc mã ở nhánh `dev` của repo chính thức. Nhánh này có thể đã khác bản 1.19.4.

Repo chính thức hiện nay là [github.com/anomalyco/opencode](https://github.com/anomalyco/opencode). `sst/opencode` chuyển hướng về đúng repo này. **[đã kiểm trên máy]** bằng `gh api repos/sst/opencode`: kết quả trả `full_name = anomalyco/opencode`, giấy phép MIT, không lưu trữ (archived = false), nhánh mặc định `dev`.

Các lệnh không gọi mô hình đã chạy: `opencode --help`, `opencode run|mcp|acp|serve|auth|agent|debug|models|stats --help`, `opencode mcp list`, `opencode debug agent <tên>`, `opencode debug agent <tên> --tool …`, `opencode debug skill`, `opencode debug paths`. Ngoài ra đã thử `opencode serve` (gọi `GET /doc`, `GET /mcp`, `GET /experimental/tool…`) và `opencode acp` (chỉ gửi `initialize` và `session/new`, không gửi `session/prompt`).

---

## 1. Cấu hình MCP

**Tệp và thứ tự ưu tiên.** Các tệp cấu hình được **gộp** với nhau, không thay thế nhau. Tệp sau chỉ thắng tệp trước ở khoá trùng. Thứ tự từ thấp lên cao ([tài liệu config](https://opencode.ai/docs/config/)):

1. Cấu hình từ xa (`.well-known/opencode`).
2. Cấu hình toàn cục `~/.config/opencode/opencode.json`. Trên Windows là `C:\Users\<user>\.config\opencode` (**[đã kiểm trên máy]** bằng `opencode debug paths`).
3. Tệp do biến `OPENCODE_CONFIG` trỏ tới.
4. `opencode.json` của dự án, tức thư mục đang mở.
5. Thư mục `.opencode/` (agents, commands, plugins, skills).
6. Cấu hình viết thẳng trong biến `OPENCODE_CONFIG_CONTENT` (JSON).
7. Cấu hình quản lý (managed) và MDM trên macOS. Người dùng không ghi đè được tầng này.

`OPENCODE_CONFIG_DIR` được nạp sau cấu hình toàn cục và sau `.opencode`, nên ghi đè được hai tầng đó. Trong tệp cấu hình viết được `{env:TEN_BIEN}` (biến chưa đặt thì thành chuỗi rỗng) và `{file:đường_dẫn}`. Danh sách biến môi trường nằm ở [tài liệu CLI](https://opencode.ai/docs/cli/).

**Máy chủ MCP cục bộ** đặt ở `mcp.<tên>` ([tài liệu MCP](https://opencode.ai/docs/mcp-servers/)):

| Khoá | Bắt buộc | Ý nghĩa |
| --- | --- | --- |
| `type` | có | `"local"` |
| `command` | có | **Mảng** gồm lệnh và tham số |
| `environment` | không | Biến môi trường cho tiến trình máy chủ |
| `cwd` | không | Thư mục chạy máy chủ |
| `enabled` | không | Bật hoặc tắt khi khởi động |
| `timeout` | không | Thời gian chờ (ms) cho mọi yêu cầu, kể cả gọi công cụ. Mặc định 30000 khi kết nối và lấy danh sách công cụ |

Công cụ MCP mang tiền tố tên máy chủ, ví dụ `my-mcp_search` ([tài liệu MCP](https://opencode.ai/docs/mcp-servers/)). Với cad-guard, tên dự kiến là `cad-guard_list_drawings`, `cad-guard_audit`… Trên máy **chưa xác nhận** được tên thật, vì `opencode debug agent --tool` và `GET /experimental/tool` chỉ liệt kê công cụ tích hợp, không liệt kê công cụ MCP.

**[đã kiểm trên máy]**: dựng thư mục tạm `…/scratchpad/cli-opencode/ws/` gồm 3 DXF tổng hợp, `AGENTS.md`, `.opencode/skills/` và `opencode.json` sinh từ mẫu `knowledge/mcp/opencode/opencode.json` (đã điền `<PYTHON>` = python của venv-agent, `<THU_MUC_LAM_VIEC>` = thư mục đó, `--profile` = bản sao `standards/company-profile.example.yaml`, thêm `environment.PYTHONPATH` = `packages/core`). Chạy `opencode mcp list` cho kết quả `✓ cad-guard connected` và `✓ cad-guard-ho-so connected`. `GET /mcp` của `opencode serve` cũng trả `{"cad-guard":{"status":"connected"},…}`. Các khoá `default_agent`, `share`, `autoupdate`, `permission."*"` và `permission.skill` dạng đối tượng đều được nhận, không báo lỗi lược đồ.

## 2. Giới hạn để agent chỉ dùng cad-guard

**Theo tài liệu** ([permissions](https://opencode.ai/docs/permissions/), [tools](https://opencode.ai/docs/tools/), [agents](https://opencode.ai/docs/agents/)):

- Mỗi quyền nhận một trong ba giá trị `allow`, `ask`, `deny`. Có thể dùng mẫu `*` và `?`. **Luật khớp sau cùng thắng**, nên đặt `"*"` trước, luật cụ thể sau.
- Các khoá quyền: `read`, `edit` (gồm `edit`, `write`, `apply_patch`), `glob`, `grep`, `bash`, `task`, `todowrite`, `skill`, `lsp`, `question`, `webfetch`, `websearch`, `external_directory`, `doom_loop`. Bản 1.19.4 **không có** công cụ `list`: danh sách công cụ **[đã kiểm trên máy]** chỉ gồm `invalid, question, bash, read, glob, grep, edit, write, task, webfetch, todowrite, websearch, skill, apply_patch`.
- Mặc định gần như mọi quyền là `allow`. Riêng `doom_loop` và `external_directory` là `ask`, còn `read` với tệp `*.env` là `ask`.
- Khoá `tools` (bật/tắt từng công cụ) **đã lỗi thời**. Nên dùng `permission`. Mẫu tên công cụ MCP cũng dùng được trong `permission`, ví dụ `"mymcp_*": "deny"` ([agents](https://opencode.ai/docs/agents/)).
- Quyền của agent được gộp với quyền toàn cục, luật của agent được ưu tiên.

**Cấu hình đã chọn** (xem `knowledge/mcp/opencode/opencode.json`):

```json
"permission": {
  "*": "deny",
  "cad-guard_*": "allow",
  "cad-guard-ho-so_*": "allow",
  "skill": { "*": "deny", "khao-sat-ban-ve": "allow", "kiem-va-giai-thich-loi": "allow", "don-ban-ve": "allow", "ghi-chu-ban-giao": "allow" }
}
```

Mẫu thêm agent `cad-guard` (`mode: primary`, cùng bộ quyền) và đặt `"default_agent": "cad-guard"`.

**Mức ép buộc, [đã kiểm trên máy]:**

| Thử | Kết quả |
| --- | --- |
| `opencode debug agent cad-guard` | Bảng `tools` cuối cùng: mọi công cụ tích hợp là `false`, chỉ `skill` là `true`. Theo nghĩa của lệnh debug, công cụ `false` bị bỏ khỏi danh sách công cụ gửi cho mô hình |
| `opencode debug agent build`, `plan`, `explore`, `general` | Cũng chỉ còn `skill`. Quyền `"*": "deny"` toàn cục đè cả agent tích hợp, nên người dùng có chuyển sang `build` cũng không có lại `read` hay `bash` |
| Đối chứng: thư mục chỉ có `mcp`, không có `permission` | `build` có đủ `read, bash, edit, write, glob, grep, webfetch, websearch, task…` = `true` |
| `opencode debug agent build --tool read --params {"filePath":"AGENTS.md"}` | `Tool read is disabled for agent build` |
| `--tool skill` với skill `customize-opencode` (tích hợp sẵn, không được phép) | Bị từ chối lúc gọi: "The user has specified a rule which prevents you from using this specific tool call" |
| `--tool skill` với skill `khao-sat-ban-ve` | Nạp được (`Loaded skill: khao-sat-ban-ve`) |
| `opencode acp`, gửi `session/new` | Chế độ hiện tại là `cad-guard`; các chế độ có sẵn: `cad-guard`, `build`, `plan` |

**Giới hạn của mức ép buộc:**

- Chưa thử bằng một phiên có mô hình thật. Vì vậy chưa xác nhận được công cụ MCP mang đúng tên `cad-guard_<tên>` và được phép. Nếu tên khác thì luật `"*": "deny"` sẽ **chặn luôn công cụ cad-guard**, tức hỏng theo hướng an toàn: agent không dùng được gì chứ không mở thêm quyền.
- Cấu hình dự án có thứ tự ưu tiên **cao hơn** cấu hình toàn cục của người dùng. Nhưng `OPENCODE_CONFIG_CONTENT`, cấu hình quản lý và `.opencode/` có thứ tự cao hơn nữa, nên người dùng vẫn tự mở lại được quyền. Đây là rào chống trợ lý đọc nhầm, **không** phải rào chống chính người dùng.
- Cờ `--auto` chỉ tự duyệt những quyền **không** bị `deny` rõ ràng (**[đã kiểm trên máy]** qua `opencode run --help`), nên không phá được `"*": "deny"`.
- OpenCode tự nạp skill và lời dặn từ `~/.claude/` (skill của người dùng hiện ra trong `opencode debug skill`). Skill bị chặn bằng `permission.skill`, nhưng `~/.claude/CLAUDE.md` vẫn có thể vào prompt. Khi cad-guard tự khởi chạy OpenCode, nên đặt `OPENCODE_DISABLE_CLAUDE_CODE=1` và `OPENCODE_DISABLE_EXTERNAL_SKILLS=1` ([tài liệu CLI](https://opencode.ai/docs/cli/)). Đã kiểm: với biến thứ hai, `debug skill` chỉ còn 4 skill cad-guard và `customize-opencode`.
- Lịch sử phiên, gồm cả kết quả công cụ đã ẩn danh, được lưu trên máy ở `~/.local/share/opencode`. Có thể đổi chỗ lưu bằng `OPENCODE_DB`.

## 3. Chạy không giao diện: `run`, `serve`, SDK

- `opencode run [message..]` có `--format default|json` (`json` trả "raw JSON events"), `-m/--model provider/model`, `--agent`, `--dir`, `--attach <url>` để gắn vào một `serve` đang chạy, `--variant` (mức suy luận) và `--auto` (**[đã kiểm trên máy]** qua `opencode run --help`). Tài liệu không liệt kê các loại sự kiện JSON, cũng không ghi mã thoát ([CLI](https://opencode.ai/docs/cli/)).
- Mức dùng và chi phí: trong OpenAPI của `serve` (**[đã kiểm trên máy]**, `GET /doc`), `AssistantMessage` có trường `cost` (số) và `tokens {total, input, output, reasoning, cache{read, write}}`. `opencode stats` cũng thống kê token và chi phí theo ngày, mô hình, dự án. Với bench, có hai đường: đọc sự kiện của `run --format json`, hoặc chạy `serve` rồi đọc tin nhắn. Hình dạng sự kiện JSON **chưa kiểm**.
- `opencode serve` mặc định lắng nghe ở `127.0.0.1:4096` ([server](https://opencode.ai/docs/server/)). Nếu không chọn cổng, CLI mặc định `--port 0`, tức chọn ngẫu nhiên. Đặt `OPENCODE_SERVER_PASSWORD` để bật basic auth. OpenAPI có ở `/doc` (bản 1.19.4 có 162 đường dẫn, **[đã kiểm trên máy]**). Các điểm chính: `POST /session`, `POST /session/:id/message`, `POST /session/:id/prompt_async`, `GET /event` (SSE), `POST /session/:id/permissions/:permissionID`, `PUT /auth/:id`.
- SDK `@opencode-ai/sdk` ([SDK](https://opencode.ai/docs/sdk/)): `createOpencode()` dựng cả máy chủ lẫn client và nhận `config` viết thẳng. `createOpencodeClient({ baseUrl })` nối vào máy chủ có sẵn. `client.event.subscribe()` để nhận sự kiện.

## 4. ACP: `opencode acp`

- Trình soạn hoặc ứng dụng chạy `opencode acp` làm tiến trình con và nói chuyện bằng JSON-RPC qua stdio. Theo tài liệu, mọi thứ hoạt động như trong terminal: công cụ tích hợp, MCP trong cấu hình OpenCode, `AGENTS.md`, agent và quyền. Chưa hỗ trợ một số lệnh gạch chéo như `/undo`, `/redo` ([ACP](https://opencode.ai/docs/acp/)).
- **[đã kiểm trên máy]** (gửi `initialize` rồi `session/new`, không gửi prompt): bản 1.19.4 trả `protocolVersion 1`. `agentCapabilities` gồm `loadSession`, `mcpCapabilities {http, sse}`, `promptCapabilities {image, embeddedContext}`, `sessionCapabilities {close, fork, list, resume}`. `authMethods` chỉ có `opencode-login` ("Run `opencode auth login` in the terminal"): ACP **không** có bước nhập khoá. `session/new` trả `configOptions` gồm `model` (82 lựa chọn trên máy này) và `mode` (= agent).
- **Chọn mô hình và agent**: client đổi qua config option `model`, `effort` (khi mô hình có biến thể) và `mode` ([mã nguồn dev `packages/cli/src/acp/config-option.ts`](https://github.com/anomalyco/opencode/tree/dev/packages/cli/src/acp)). Mặc định lấy theo `model` và `default_agent` trong cấu hình.
- **Cấp quyền**: quyền đặt là `ask` sẽ thành `session/request_permission` gửi cho client, với ba lựa chọn `allow_once`, `allow_always`, `reject_once` ([mã nguồn dev `permission.ts`](https://github.com/anomalyco/opencode/tree/dev/packages/cli/src/acp)). Quyền `deny` bị chặn ngay trong OpenCode, không hỏi client.
- **MCP do client truyền vào**: theo `mcpCapabilities`, OpenCode nhận máy chủ HTTP/SSE trong `session/new`. Stdio là mức cơ bản của ACP. Chưa thử OpenCode có chạy máy chủ stdio do client truyền hay không.
- Mức ổn định: mã ACP ở nhánh `dev` đã dời sang `packages/cli/src/acp/` (khoảng 20 tệp, viết bằng Effect). Thư mục này thay đổi nhiều, nên phải **ghim phiên bản**.

## 5. Nhà cung cấp và xác thực

- OpenCode dùng AI SDK và Models.dev, hỗ trợ "75+" nhà cung cấp, gồm cả mô hình cục bộ: Ollama `http://localhost:11434/v1`, LM Studio, llama.cpp qua `@ai-sdk/openai-compatible` ([providers](https://opencode.ai/docs/providers/)). Danh sách gồm Anthropic, OpenAI, Google, OpenRouter, Bedrock, Vertex, Azure, GitHub Copilot, DeepSeek, Groq…
- **Biến môi trường khoá API**: Models.dev khai báo biến cho từng nhà cung cấp. **[đã kiểm]** bằng `https://models.dev/api.json`: `anthropic` → `ANTHROPIC_API_KEY`; `openai` → `OPENAI_API_KEY`; `google` → `GOOGLE_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, `GEMINI_API_KEY`; `openrouter` → `OPENROUTER_API_KEY`. Tài liệu config ghi rằng `disabled_providers` chặn nhà cung cấp "kể cả khi đã đặt biến môi trường", tức biến môi trường tự bật nhà cung cấp. Cũng có thể viết `options.apiKey: "{env:TEN_BIEN}"`.
- **Nơi lưu khoá**: khoá thêm bằng `/connect` hoặc `opencode auth login` được ghi vào `~/.local/share/opencode/auth.json` ([providers](https://opencode.ai/docs/providers/)). `PUT /auth/:id` của `serve` nhận `{type:"api", key}` (**[đã kiểm trên máy]** qua OpenAPI). Rất có thể đường này cũng ghi vào `auth.json`, **chưa kiểm**. Vì vậy cad-guard **không dùng** `auth login` hay `PUT /auth`. Cách làm: đọc khoá từ kho khoá hệ điều hành, đặt vào biến môi trường **của riêng tiến trình con** `opencode acp`, kèm `enabled_providers: ["<nhà cung cấp>"]` để không vô tình dùng khoá khác có sẵn trong môi trường.
- **Đăng nhập thuê bao**:
  - Claude Pro/Max, **đã kiểm** trên trang providers: OpenCode ghi rằng Anthropic cấm rõ việc này, và từ bản 1.3.0 OpenCode không còn đi kèm plugin đăng nhập Pro/Max. Trang pháp lý Claude Code (đã dẫn trong `plans/cad-guard-agent.md` mục 2.2) cũng cấm định tuyến qua gói thuê bao cho bên thứ ba. → **Không** dùng Claude Pro/Max qua OpenCode.
  - ChatGPT Plus/Pro, **đã kiểm** trên trang providers: `/connect` có lựa chọn "ChatGPT Plus/Pro", mở trình duyệt để xác thực, trang không kèm cảnh báo gì. **Chưa chắc**: OpenAI chưa có văn bản cho phép ứng dụng bên thứ ba dùng đăng nhập ChatGPT (xem mục 2.2 của kế hoạch).
  - GitHub Copilot có trong danh sách nhà cung cấp; điều khoản **chưa kiểm**.

## 6. Giấy phép

- **MIT**, "Copyright (c) 2025 opencode". **[đã kiểm trên máy]**: tệp `LICENSE` trong gói npm đã cài (`…\npm\node_modules\opencode-ai\LICENSE`), `package.json` có `"license": "MIT"`, và GitHub API của `anomalyco/opencode` trả `license = MIT`.
- Hệ quả với cad-guard:
  - Được khởi chạy OpenCode làm tiến trình con, kể cả trong sản phẩm thương mại. Không có điều khoản copyleft nên không ảnh hưởng mã cad-guard.
  - Nếu **đóng gói kèm** tệp chạy, phải giữ thông báo bản quyền và nội dung giấy phép MIT (ví dụ trong `THIRD_PARTY_NOTICES`).
  - Tệp `opencode.exe` khoảng **212 MB** là bản biên dịch gộp, kèm nhiều thư viện bên thứ ba. Giấy phép của các thư viện bên trong **chưa kiểm**; gói nền tảng `opencode-windows-x64` không ghi trường `license`. Trước khi đóng gói kèm phải lập danh sách giấy phép từ mã nguồn, theo `docs/licenses.md`.
  - Phương án nhẹ hơn: không đóng gói, để người dùng tự cài `opencode-ai` từ npm và cad-guard chỉ ghim phiên bản tối thiểu.
- Tên "OpenCode" là tên của dự án khác. Không dùng nó làm tên sản phẩm cad-guard; chỉ ghi "chạy bằng OpenCode".

---

## Khuyến nghị cho cad-guard

**(A) Từ CLI agent người dùng đang dùng (gói làm việc + MCP).** Dùng mẫu `knowledge/mcp/opencode/opencode.json` đặt ở gốc thư mục làm việc của phiên, chép kèm `AGENTS.md` và `skills/` vào `.opencode/skills/`. Rào thật là `permission` `"*": "deny"` cộng với cho phép riêng `cad-guard_*`; đã kiểm là rào này chặn công cụ tích hợp của mọi agent. Trước khi dùng với bản vẽ thật, làm một phiên thử có mô hình để xác nhận tên công cụ MCP và việc từ chối `read`.

**(B) Trong ứng dụng cad-guard qua hạn mức tài khoản.** OpenCode **không phải** đường đúng cho Claude: Anthropic cấm dùng Pro/Max qua OpenCode, nên muốn dùng hạn mức Claude thì cad-guard chạy chính Claude Code. Với ChatGPT, nên chạy Codex CLI nguyên bản. OpenCode cộng đăng nhập ChatGPT chỉ là tuỳ chọn người dùng tự chịu, mặc định tắt, cho tới khi OpenAI trả lời bằng văn bản. Nếu dùng OpenCode trong (B) thì người dùng tự chạy `opencode auth login` trong terminal của họ; cad-guard không đọc `auth.json`.

**(C) API trực tiếp bằng khoá của khách (BYOK).** Có hai cách:

| | OpenCode qua `opencode acp` | cad-guard tự gọi API |
| --- | --- | --- |
| Lớp nhà cung cấp | Có sẵn hơn 75 nhà cung cấp, kể cả cục bộ | Phải tự viết. Phần lớn nhà cung cấp đi được qua lối tương thích OpenAI (OpenRouter, Ollama, LM Studio, DeepSeek…), Anthropic viết riêng |
| Vòng lặp agent, phiên, nén ngữ cảnh, hỏi quyền | Có sẵn | Tự viết. Với 6 công cụ chỉ đọc, vòng lặp nhỏ |
| Bảo đảm "chỉ cad-guard" | Bằng cấu hình (đã kiểm ở mức cấu hình), có thể bị cấu hình tầng cao hơn ghi đè | Tuyệt đối: không tồn tại công cụ nào khác |
| Đường đi dữ liệu | Thêm một tiến trình tự lưu lịch sử phiên, tự lấy danh mục mô hình từ models.dev, tự kiểm cập nhật (tắt được bằng biến môi trường) | Chỉ cad-guard ↔ nhà cung cấp |
| Mã client | Dùng chung client ACP của V2 (đằng nào cũng phải viết cho Claude/Codex) | Thêm một đường riêng trong ứng dụng |
| Rủi ro duy trì | ACP của OpenCode thay đổi nhanh, phải ghim phiên bản; tệp chạy 212 MB | Theo kịp thay đổi API nhà cung cấp |

**Đề xuất:**

- **V2 dùng OpenCode qua ACP cho BYOK**, vì client ACP đằng nào cũng phải viết. Cấu hình cứng khi chạy:
  - đặt cấu hình bằng `OPENCODE_CONFIG_CONTENT` (giống mẫu, thêm `enabled_providers`), vì tầng này ưu tiên cao hơn tệp của dự án;
  - đặt khoá bằng biến môi trường của tiến trình con, đọc từ kho khoá hệ điều hành;
  - đặt các biến `OPENCODE_DISABLE_CLAUDE_CODE=1`, `OPENCODE_DISABLE_EXTERNAL_SKILLS=1`, `OPENCODE_DISABLE_AUTOUPDATE=1`, `OPENCODE_DISABLE_MODELS_FETCH=1` (cần kèm `OPENCODE_MODELS_PATH` ghim danh mục mô hình), `OPENCODE_DB` trỏ vào thư mục phiên;
  - ghim phiên bản OpenCode.
- **Giữ phương án dự phòng "cad-guard tự gọi API"** cho hai trường hợp: khách đòi bảo đảm tuyệt đối "không có công cụ nào khác" (bậc NDA), hoặc ACP của OpenCode đổi làm vỡ tích hợp. Với 6 công cụ chỉ đọc, phương án này nhỏ: một lớp Anthropic, một lớp tương thích OpenAI, vòng lặp gọi công cụ.
- Không nên tự viết lại toàn bộ harness (V3), đúng như kế hoạch đã nêu.
- Bench có thể dùng `opencode run --format json --agent cad-guard -m <provider/model>` để chạy nhiều mô hình bằng một lệnh.

## Chưa chắc

- Tên thật của công cụ MCP trong phiên có mô hình (dự kiến `cad-guard_<tên>`) và việc `permission` `cad-guard_*` khớp với tên đó. Chưa chạy phiên có mô hình.
- Mô hình có thật sự không nhìn thấy công cụ bị `deny` không. Lệnh `debug agent` cho thấy `tools: false`, nhưng chưa xem request gửi đi.
- Hình dạng sự kiện của `opencode run --format json` và mã thoát.
- OpenCode có nhận máy chủ MCP **stdio** do client ACP truyền trong `session/new` không.
- `PUT /auth/:id` có ghi xuống `auth.json` không.
- Điều khoản của OpenAI về đăng nhập ChatGPT trong OpenCode; điều khoản GitHub Copilot.
- Giấy phép các thư viện được gộp trong `opencode.exe`.
- OpenCode có gửi dữ liệu nào khác ra ngoài ngoài nhà cung cấp mô hình, models.dev và kiểm cập nhật không (chia sẻ phiên đã tắt bằng `share: "disabled"`). Chưa đo lưu lượng mạng.
- Mã ACP ở nhánh `dev` có thể khác bản 1.19.4.

## Nguồn

- Tài liệu: [config](https://opencode.ai/docs/config/), [mcp-servers](https://opencode.ai/docs/mcp-servers/), [permissions](https://opencode.ai/docs/permissions/), [tools](https://opencode.ai/docs/tools/), [agents](https://opencode.ai/docs/agents/), [providers](https://opencode.ai/docs/providers/), [acp](https://opencode.ai/docs/acp/), [server](https://opencode.ai/docs/server/), [sdk](https://opencode.ai/docs/sdk/), [cli](https://opencode.ai/docs/cli/).
- Repo: [anomalyco/opencode](https://github.com/anomalyco/opencode) (nhánh `dev`, `packages/cli/src/acp/`).
- Danh mục mô hình và biến môi trường: [models.dev/api.json](https://models.dev/api.json).
- Trên máy: gói `opencode-ai` 1.19.4 (`LICENSE`, `package.json`); thư mục thử `C:\Users\Admin\AppData\Local\Temp\claude\f0564dbf59e0ad85\dbb54a00-046a-4bf3-8b7f-6a92e828e571\scratchpad\cli-opencode\`.
