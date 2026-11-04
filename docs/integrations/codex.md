# Tích hợp OpenAI Codex CLI với cad-guard

Ngày kiểm: 04/11/2026. Bản đã cài trên máy kiểm: `codex-cli 0.165.0` (Windows 11, cài qua npm; `codex doctor` báo đã có 0.166.0).
Quy ước: **[máy]** = đã kiểm trên máy bằng lệnh ghi kèm; **[tài liệu]** = theo link nguồn, chưa thử; **[chưa chắc]** = nguồn thiếu hoặc mâu thuẫn.

Mọi phép thử trên máy dùng `CODEX_HOME` trỏ vào thư mục tạm (không đụng `~/.codex` của người dùng), thư mục làm việc chứa 3 bản sao DXF **tổng hợp** (`ok_sheet`, `bad_layers`, `hygiene_bad`), **không gọi mô hình, không đăng nhập**. Không đọc `auth.json`.

Ba cách dùng nhắc tới bên dưới: **(A)** người dùng mở Codex trong "gói làm việc" và gọi cad-guard qua MCP; **(B)** ứng dụng cad-guard khởi chạy Codex nguyên bản làm tiến trình con, người dùng tự đăng nhập bằng tài khoản của họ; **(C)** gọi API trực tiếp bằng khoá của khách.

## 1. Cấu hình MCP

**Khoá của `[mcp_servers.<tên>]` (máy chủ stdio)** [tài liệu: [MCP](https://learn.chatgpt.com/docs/extend/mcp), [Config reference](https://learn.chatgpt.com/docs/config-file/config-reference)]:

| Khoá | Ý nghĩa | Mặc định |
| --- | --- | --- |
| `command` (bắt buộc), `args`, `cwd` | lệnh khởi động, tham số, thư mục chạy | — |
| `env` (bảng), `env_vars` (danh sách tên biến chuyển tiếp) | biến môi trường | — |
| `startup_timeout_sec` (bí danh `startup_timeout_ms`) | thời gian chờ khởi động | **10 s** |
| `tool_timeout_sec` | thời gian chờ mỗi lần gọi công cụ | 60 s |
| `enabled` | `false` = tắt mà không xoá | bật |
| `required` | `true` = không lên thì phiên khởi động lỗi; `codex exec` thoát lỗi thay vì chạy tiếp ([non-interactive](https://learn.chatgpt.com/docs/non-interactive-mode.md)) | — |
| `enabled_tools` / `disabled_tools` | danh sách cho phép / chặn (chặn áp sau cho phép) | — |
| `default_tools_approval_mode`, `tools.<tên>.approval_mode` | `auto`, `prompt`, `writes`, `approve` | — |
| `startup_readiness` | `connection` hoặc `catalog` | `connection` |

Đã kiểm [máy]:

- Mẫu `knowledge/mcp/codex/config.toml` và `cadguard.config.toml` sau khi điền đường dẫn thật (python của venv, `PYTHONPATH` = `packages/core`, workspace tạm, `--profile standards/company-profile.example.yaml`) được Codex đọc đúng: `codex mcp list`, `codex mcp list --json`, `codex mcp get cad-guard`, `codex -p cadguard mcp get cad-guard` hiện đủ `command`, `args` (có `--profile`), `cwd`, `env` (giá trị bị che `*****`), `enabled_tools`, `startup_timeout_sec = 60`, `tool_timeout_sec = 120`.
- **Kết nối thật mà không gọi mô hình**: chạy `codex app-server` (stdio JSON-RPC), gửi `initialize` → `mcpServerStatus/list` → `thread/start` (`sandbox: read-only`, `approvalPolicy: never`, `ephemeral: true`) → `mcpServer/tool/call`. Kết quả: máy chủ `cad-guard` (MCP SDK 1.30.0) trả đủ 5 công cụ; `list_drawings` trả 3 tệp với mã băm `F_…` (không tên tệp); `audit` trả `standard: design-hygiene-v0`, `profile: {name: cong-ty-mau, version: 0.1.0}`, `counts: {E: 0, W: 2, I: 0}`; `explain_rule VS-01` trả tham số đã gộp hồ sơ công ty. Không cần đăng nhập cho bước này. (`codex doctor` chỉ đếm số máy chủ MCP, không khởi động chúng.)
- **`enabled_tools` / `disabled_tools` lọc thật**: `-c 'mcp_servers.cad-guard.enabled_tools=["list_drawings","audit"]'` → chỉ còn 2 công cụ; `disabled_tools=["query_model"]` → còn 4.
- **Thời gian khởi động**: lần đầu `startup_timeout_sec = 20` bị lỗi `timed out handshaking with MCP server after 19.99s`; đo riêng `import cadguard.mcp_server` khởi động lạnh mất ~13 s. Mặc định 10 s của Codex **không đủ** trên Windows → mẫu đặt 60 s.
- `codex --strict-config` **không** dùng được với `codex mcp` (`Error: --strict-config is not supported for codex mcp`).

**Nơi đặt cấu hình** [tài liệu: Config reference]:

- Người dùng: `~/.codex/config.toml` (tức `$CODEX_HOME/config.toml`; `CODEX_HOME` mặc định `~/.codex` theo [trang xác thực](https://learn.chatgpt.com/docs/auth)).
- Dự án: `<thư mục>/.codex/config.toml`, **chỉ nạp khi thư mục được tin cậy** (`[projects.'<đường dẫn>'] trust_level = "trusted"` trong cấu hình người dùng). [máy] Thư mục không có git, chưa tin cậy → mục MCP của dự án bị bỏ qua; thêm `trust_level = "trusted"` vào cấu hình người dùng → được nạp (có git hay không đều được). Thử đặt tin cậy bằng `-c "projects.'<đường dẫn>'.trust_level=..."` thì **không** có tác dụng.
- Hồ sơ cấu hình (bản 0.165): `-p/--profile <tên>` chồng tệp `$CODEX_HOME/<tên>.config.toml` lên cấu hình người dùng ([máy]: `codex --help`; tài liệu cũng ghi "Profile files live at `$CODEX_HOME/profile-name.config.toml`"). [máy] Hồ sơ chứa được `[mcp_servers]`, `[features]`, `sandbox_mode`…; không có `-p` thì các khoá đó không áp.
- Ghi đè từng lần chạy: `-c khoa.con=gia_tri` (TOML) trên mọi lệnh con; [máy] `codex mcp list -c 'mcp_servers.tam.command="python"'` thêm được máy chủ tạm không cần tệp.
- `codex exec --ignore-user-config`: không nạp `$CODEX_HOME/config.toml`, xác thực vẫn dùng `CODEX_HOME` [máy: `codex exec --help`].
- Thêm bằng lệnh: `codex mcp add <tên> --env K=V -- <lệnh...>` [máy: `codex mcp add --help`]. Lệnh này ghi vào cấu hình người dùng; không đặt được `cwd`, `enabled_tools`, timeout → cad-guard nên dùng tệp mẫu.

**`AGENTS.md` và skill** [máy, bằng `codex debug prompt-input` – lệnh dựng lời nhắc mà mô hình sẽ thấy, không gọi mô hình]: trong thư mục làm việc không có git, Codex vẫn nạp `AGENTS.md` ở gốc và skill ở `.agents/skills/<tên>/SKILL.md`. Vậy với Codex, chép `knowledge/skills/*` vào `<THU_MUC_LAM_VIEC>/.agents/skills/`.

## 2. Giới hạn để trợ lý chỉ dùng cad-guard

Phép thử chính [máy]: `codex debug prompt-input x` liệt kê công cụ mô hình thấy (bản 0.165 bọc công cụ trong `exec` kiểu "code mode", danh sách công cụ con nằm trong mô tả của `exec`).

| Cấu hình | Công cụ con còn lại |
| --- | --- |
| mặc định | `exec_command`, `write_stdin` (shell), `apply_patch` (ghi tệp), `view_image`, `list_mcp_resources`, `list_mcp_resource_templates`, `read_mcp_resource`, `clock__curr_time` |
| `--disable shell_tool` (= `features.shell_tool=false`) | mất `exec_command`, `write_stdin` |
| thêm `--disable view_image` | mất `view_image` |
| `-c include_apply_patch_tool=false` | **không** tác dụng, `apply_patch` vẫn còn |
| `--disable multi_agent` | công cụ `collaboration.spawn_agent`… vẫn còn |
| `-p cadguard` với mẫu `cadguard.config.toml` | `apply_patch`, `clock__curr_time`, 3 công cụ tài nguyên MCP |

Công cụ MCP `cad-guard` không hiện trong `prompt-input` (lệnh này có vẻ không khởi động máy chủ MCP hoặc công cụ MCP được nạp hoãn) — [chưa chắc] cách mô hình thấy chúng; phép thử A1 với mô hình thật sẽ xác nhận.

Đánh giá mức ép buộc:

- **Shell: tắt hẳn được** bằng `features.shell_tool = false` (đã kiểm). Không có shell thì trợ lý không còn cách đọc tệp tuỳ ý (Codex không có công cụ "read file" riêng; đọc tệp vốn đi qua shell). Đây là rào thật, mạnh hơn lời dặn trong `AGENTS.md`.
- **Web**: `web_search = "disabled"` bỏ công cụ tìm web [tài liệu: Config reference]; mặc định là `"cached"`, và thành `"live"` khi chạy full-access.
- **Ghi tệp**: `apply_patch` không tắt được bằng khoá đã biết; `sandbox_mode = "read-only"` + `approval_policy = "never"` làm việc ghi bị từ chối, không hỏi [tài liệu: [Approvals & security](https://learn.chatgpt.com/docs/agent-approvals-security)]. cad-guard không cần ghi.
- **Sandbox**: `read-only`, `workspace-write`, `danger-full-access`; `approval_policy`: `on-request`, `never`, hoặc bảng `granular`; `untrusted` đã bỏ [tài liệu]. `codex exec` mặc định read-only, không hỏi phê duyệt; `--full-auto` không còn [tài liệu: non-interactive].
- **Chặn đọc theo mẫu tệp (permission profiles)**: `[permissions.<tên>.filesystem.":workspace_roots"] "**/*.dxf" = "deny"` và `default_permissions = "<tên>"` [tài liệu: [Permissions](https://learn.chatgpt.com/docs/permissions)]. Chỉ áp cho lệnh chạy trong sandbox, **không** áp cho máy chủ MCP (đúng ý: cad-guard vẫn đọc được). [máy] Trên Windows, `codex sandbox -P cadguard` báo `Restricted read-only access requires the elevated Windows sandbox backend`, rồi `elevated Windows sandbox requires effective ':root' read access`; khi thêm `":root" = "read"` thì cần chạy trình cài đặt sandbox với quyền quản trị (UAC) – phép thử dừng ở đây (`ShellExecuteExW … 1223`, hộp UAC bị huỷ). Vậy chặn đọc DXF bằng hồ sơ quyền trên Windows **cần cài sandbox "elevated" một lần bằng quyền admin**, chưa kiểm hết. Khi đã tắt shell thì lớp này chỉ là dự phòng.
- **Thư mục làm việc rỗng** vẫn là lớp bảo vệ nền: Codex lấy thư mục chạy (`-C`) làm gốc làm việc.

Kết luận: với Codex, "chỉ dùng cad-guard" đạt **gần như cứng** bằng hồ sơ `cadguard.config.toml` (tắt shell + view_image + web, read-only, never). Còn mở: `apply_patch` (bị sandbox chặn), subagent (`collaboration.*`) [chưa chắc chúng có kế thừa cấu hình không – theo lẽ thường là có, chưa kiểm], công cụ tài nguyên MCP (chỉ đọc tài nguyên do máy chủ MCP cung cấp; cad-guard không công bố tài nguyên).

## 3. Chạy không giao diện cho (B) và bench

**`codex exec`** [máy: `codex exec --help`; tài liệu: [non-interactive](https://learn.chatgpt.com/docs/non-interactive-mode.md)]:

- `--json`: stdout thành JSONL sự kiện: `thread.started`, `turn.started`, `turn.completed`, `turn.failed`, `item.*`, `error`.
- **Đếm token**: `turn.completed` có `usage` gồm `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens` (ví dụ trong tài liệu) → bench đọc trực tiếp.
- `-o/--output-last-message <tệp>`, `--output-schema <tệp JSON Schema>` (câu trả lời cuối theo lược đồ).
- `--skip-git-repo-check` (bắt buộc vì thư mục làm việc không phải repo git), `--ephemeral` (không lưu tệp phiên ra đĩa — nên bật để không giữ kết quả công cụ trên máy), `--ignore-user-config`, `--ignore-rules`, `-C/--cd`, `-m/--model`, `-s/--sandbox`, `-p/--profile`, `-c`, `--enable/--disable`, `codex exec resume <id>|--last`.
- Lệnh mẫu cho (B)/bench:
  `codex exec -p cadguard -C <THU_MUC_LAM_VIEC> --skip-git-repo-check --ephemeral --json -o <tệp>.txt "<yêu cầu>"`

**`codex app-server`** [máy: `codex app-server --help` ghi `[experimental]`; tài liệu: [App server](https://learn.chatgpt.com/docs/app-server)]:

- Giao thức: JSON-RPC 2.0 (tài liệu: bỏ trường `jsonrpc`; [máy] gửi kèm trường này vẫn chạy) qua stdio JSONL (mặc định), WebSocket (`--listen ws://…`, tài liệu ghi "experimental and unsupported"), unix socket. `codex app-server generate-json-schema --out <dir>` / `generate-ts` sinh lược đồ đúng phiên bản đang cài [máy: sinh được 39 tệp, ~130 phương thức].
- Có: phê duyệt từ phía client (`item/commandExecution/requestApproval`, `item/fileChange/requestApproval`, `item/permissions/requestApproval`, `mcpServer/elicitation/request`), `thread/tokenUsage/updated`, `account/rateLimits/read` (phần trăm hạn mức đã dùng), `account/login/start` (`apiKey`, `chatgpt`, `chatgptDeviceCode`, `chatgptAuthTokens` thử nghiệm), `mcpServerStatus/list`, `mcpServer/tool/call`, `thread/start` nhận `sandbox`, `approvalPolicy`, `config`, `developerInstructions`, `ephemeral`.
- Tài liệu định vị app-server cho "tích hợp sâu trong sản phẩm" (VS Code extension dùng nó); tự động hoá/CI thì khuyên dùng SDK; tích hợp doanh nghiệp nên liên hệ OpenAI để vào danh sách client đã biết. Một số phương thức phải bật `experimentalApi`.
- Độ ổn định: lệnh vẫn gắn nhãn `[experimental]`; giao thức đổi theo phiên bản → cad-guard phải **ghim phiên bản Codex** và sinh lại lược đồ khi nâng.

**SDK chính thức** [tài liệu: [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk.md)]:

- TypeScript `@openai/codex-sdk` (Node 18+, phía server). [máy, đọc mã `sdk/typescript/src/exec.ts` trên GitHub] SDK sinh tiến trình `codex exec --experimental-json`. npm: bản 0.166.0, giấy phép Apache-2.0.
- Python `openai-codex` (Python 3.10+), "controls the local Codex app-server over JSON-RPC", kèm gói nhị phân CLI ghim phiên bản (`openai-codex-cli-bin`), cho chọn `codex_bin`. PyPI có tới 0.163.0; `pyproject.toml` ghi Apache-2.0 [máy: `pip index versions`, GitHub API]. Tài liệu ghi bản Python là "stable".
- `codex mcp-server` (Codex làm máy chủ MCP) **đã bị gỡ** theo trang SDK.

## 4. ACP

- Codex **không có ACP gốc**; dùng adapter. Trang [ACP agents](https://agentclientprotocol.com/overview/agents) ghi Codex CLI "via ACP's adapter" trỏ tới [agentclientprotocol/codex-acp](https://github.com/agentclientprotocol/codex-acp) [tài liệu].
- Adapter [máy: GitHub API, 04/11/2026]: repo thuộc tổ chức `agentclientprotocol`, chưa lưu trữ (archive), cập nhật 03/11/2026, bản mới nhất v2.5.0 (29/10/2026). Gói npm `@agentclientprotocol/codex-acp`, `package.json` ghi `"license": "Apache-2.0"` và phụ thuộc `@openai/codex ^0.166.0` (GitHub hiện `NOASSERTION` cho tệp LICENSE — nên đọc tệp LICENSE trước khi nhúng). Còn một repo cũ `zed-industries/codex-acp` (cập nhật lần cuối 22/07/2026, bản v0.16.0) — đừng nhầm với bản đang được trang ACP trỏ tới.
- Cách chạy: adapter **khởi động Codex App Server** rồi dịch ACP sang thao tác Codex; `CODEX_PATH` chọn nhị phân Codex khác; xác thực: đăng nhập ChatGPT, hoặc `CODEX_API_KEY`/`OPENAI_API_KEY` [tài liệu: README adapter].
- Hệ quả: đi ACP thì vẫn là app-server ở dưới, thêm một lớp do bên thứ ba duy trì. Nếu cad-guard chỉ hỗ trợ Codex, nói thẳng app-server ít lớp hơn; nếu V2 là ACP client chung cho nhiều CLI thì dùng adapter này.

## 5. Xác thực và điều khoản

Đã kiểm [tài liệu: [Authentication](https://learn.chatgpt.com/docs/auth)]:

- Hai cách: **Sign in with ChatGPT** (dùng hạn mức gói, theo quyền/RBAC/lưu trữ của workspace ChatGPT) và **khoá API** (tính tiền theo API, theo cài đặt dữ liệu của tổ chức API).
- `codex login --device-auth` cho máy không trình duyệt: **beta**, phải bật trong cài đặt bảo mật ChatGPT/quyền workspace.
- Lưu thông tin: `cli_auth_credentials_store` = `file` (`$CODEX_HOME/auth.json`), `keyring`, `auto`, `ephemeral` (chỉ trong bộ nhớ tiến trình). Tài liệu dặn coi `auth.json` "like a password".
- `CODEX_ACCESS_TOKEN`: token truy cập do admin ChatGPT Enterprise cho phép tạo, cho quy trình cục bộ "trusted, non-interactive"; nạp bằng `printenv CODEX_ACCESS_TOKEN | codex login --with-access-token` [máy: `codex login --help` có `--with-access-token`, `--with-api-key`, `--device-auth`, `status`].
- `CODEX_API_KEY`: trang non-interactive dặn đặt biến này "only for the Codex invocation that needs it" cho `codex exec`; trang auth không nhắc. Một bản dịch nói nó dùng được cả cho SDK TypeScript — [chưa chắc] phạm vi.
- `forced_login_method = "chatgpt" | "api"` và `forced_chatgpt_workspace_id` ép cách đăng nhập; sai thì Codex đăng xuất và thoát. Hữu ích cho công ty muốn chỉ dùng workspace của mình.
- [máy] `codex doctor` trong `CODEX_HOME` tạm báo `no Codex credentials were found` → cách ly `CODEX_HOME` thì Codex **không** thấy đăng nhập của người dùng; muốn dùng hạn mức của người dùng thì phải để `CODEX_HOME` mặc định (hoặc để người dùng tự `codex login` trong `CODEX_HOME` riêng của cad-guard).

Văn bản về **ứng dụng bên thứ ba dùng gói ChatGPT của người dùng** [tài liệu]:

- OpenAI có chương trình **Sign in with ChatGPT** cho nhà phát triển ([quickstart](https://developers.openai.com/siwc/quickstart)): đăng nhập + (tuỳ chọn) dùng hạn mức gói cho yêu cầu AI. "currently available to selected commercial partners through a limited trial"; dùng hạn mức gói "available to all open-source partners and selected private clients"; người dùng đủ điều kiện là Plus và Pro (trang trợ giúp nói Go, Plus, Pro — mâu thuẫn).
- Trang [ChatGPT plan usage](https://developers.openai.com/siwc/token-sharing-open-source) giới hạn tài liệu cho ứng dụng **mã nguồn mở và chạy cục bộ**; ứng dụng **trả phí hoặc chạy từ xa** phải điền mẫu đăng ký quan tâm. Có hướng dẫn riêng [Codex app-server với hạn mức gói](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server): ứng dụng tự lấy token OAuth (có `client_id` đã đăng ký), đặt `ACCESS_TOKEN` cho tiến trình app-server, cấu hình provider `openai_chatgpt_plan`; `clientInfo.name` phải khớp tên agent đã đăng ký. Tức là đường **chính thức** cho "ứng dụng dùng hạn mức gói của người dùng" là ứng dụng **giữ token** qua chương trình đã đăng ký — ngược với nguyên tắc "cad-guard không chạm token".
- **Không tìm thấy** văn bản nào nói về trường hợp của (B): ứng dụng bên thứ ba khởi chạy Codex CLI **nguyên bản**, người dùng tự `codex login` bằng ChatGPT, ứng dụng không đụng token. Không có câu cho phép, cũng không có câu cấm. Trang auth chỉ dặn không phơi Codex ra "untrusted or public environments", và nói khoá API hợp cho "programmatic Codex CLI workflows, such as CI/CD jobs".

## 6. Giấy phép

- `openai/codex`: **Apache-2.0** [máy: `gh api repos/openai/codex` → `license.spdx_id = Apache-2.0`]. SDK TS/Python cùng Apache-2.0 (mục 3). Adapter ACP: `package.json` ghi Apache-2.0 (mục 4).
- Apache-2.0 hợp với quy tắc `docs/licenses.md` (không copyleft). Giấy phép phần mềm khác điều khoản dịch vụ: dùng mã CLI thì tự do, còn dùng **tài khoản ChatGPT** qua CLI vẫn theo điều khoản của OpenAI (mục 5).

## Khuyến nghị cho cad-guard

**(A) Gói làm việc + CLI của người dùng — làm ngay, rủi ro thấp.**

- Dùng hồ sơ `knowledge/mcp/codex/cadguard.config.toml` (chép vào `$CODEX_HOME/cadguard.config.toml`), mở `codex -p cadguard -C <THU_MUC_LAM_VIEC>`. Không gộp các khoá chặn vào `~/.codex/config.toml` vì sẽ làm hỏng mọi phiên Codex khác của người dùng.
- Chép `knowledge/AGENTS.md` vào gốc thư mục làm việc và `knowledge/skills/*` vào `<THU_MUC_LAM_VIEC>/.agents/skills/`.
- Giữ `startup_timeout_sec = 60`, `required = true`, `enabled_tools` đủ 5 công cụ.
- Trước khi dùng với bản vẽ thật: chạy phép thử A1 có mô hình (yêu cầu trợ lý đọc một DXF/tệp ngoài thư mục; xác nhận không có công cụ làm được).

**(B) Ứng dụng cad-guard khởi chạy Codex — được về kỹ thuật, chưa rõ về điều khoản.**

- Kỹ thuật: dùng `codex exec --json` cho tác vụ một lần và bench (ổn định nhất, có `usage`); dùng `codex app-server` khi cần hội thoại nhiều lượt, phê duyệt và đọc hạn mức (`account/rateLimits/read`) — ghim phiên bản Codex, sinh lược đồ bằng `generate-json-schema`, chặn công cụ bằng `-c features.shell_tool=false -c features.view_image=false -c web_search="disabled"` và `thread/start {sandbox: "read-only", approvalPolicy: "never", ephemeral: true}`. ACP qua `codex-acp` chỉ khi V2 cần client chung cho nhiều CLI.
- Truyền cấu hình bằng `-c` hoặc `-p cadguard`, **không** sửa `~/.codex/config.toml` của người dùng; **không** đặt `CODEX_HOME` riêng nếu muốn dùng đăng nhập sẵn có của người dùng (đăng nhập nằm trong `CODEX_HOME`). Không bao giờ đọc/chép `auth.json`.
- Điều khoản: không có văn bản cho phép trường hợp này; đường chính thức OpenAI mô tả cho ứng dụng thương mại là chương trình Sign in with ChatGPT (đăng ký, ứng dụng giữ token). Vì vậy: (1) để tuỳ chọn "dùng đăng nhập Codex của bạn" ở trạng thái **thử nghiệm, có thể tắt**; (2) gửi câu hỏi bằng văn bản cho OpenAI và/hoặc điền mẫu quan tâm của Sign in with ChatGPT; (3) khách doanh nghiệp ưu tiên khoá API của tổ chức hoặc `CODEX_ACCESS_TOKEN` do admin của họ cấp.

**(C) API trực tiếp bằng khoá của khách — đường mặc định cho thương mại.**

- Không cần Codex: gọi Responses API bằng khoá của khách (lưu trong kho khoá hệ điều hành). Nếu muốn giữ vòng lặp agent của Codex mà vẫn BYOK: chạy `codex exec` với `CODEX_API_KEY` đặt riêng cho tiến trình con (không ghi ra tệp), hoặc `cli_auth_credentials_store = "ephemeral"` để khoá không nằm trên đĩa.

## Chưa chắc

1. Mô hình có thấy và gọi được 5 công cụ cad-guard trong phiên thật không, và MCP tool có bị đòi phê duyệt khi `approval_policy = "never"` không (chưa chạy mô hình; `prompt-input` không hiện công cụ MCP).
2. Subagent (`collaboration.spawn_agent`) có kế thừa `shell_tool = false` và sandbox không.
3. `apply_patch` có thật sự bị từ chối hoàn toàn ở read-only + never trên Windows không (theo tài liệu là có; chưa thử vì cần mô hình).
4. Hồ sơ quyền chặn đọc `**/*.dxf` trên Windows: cần sandbox "elevated" (cài bằng quyền admin), chưa chạy hết.
5. Hồ sơ `-p` kiểu mới (`<tên>.config.toml`) với bảng `[profiles.<tên>]` kiểu cũ trong `config.toml` — bản 0.165 chỉ mô tả kiểu mới; chưa thử kiểu cũ.
6. Phạm vi `CODEX_API_KEY` (chỉ `exec` hay cả SDK) — hai bản tài liệu nói khác nhau.
7. Điều khoản cho (B): chưa có văn bản; cần hỏi OpenAI. Điều kiện gói (Plus/Pro hay Go/Plus/Pro) cho Sign in with ChatGPT mâu thuẫn giữa trang nhà phát triển và trang trợ giúp.
8. Mức ổn định giao thức app-server giữa các bản (nhãn `[experimental]`; Python SDK dựa trên nó lại ghi "stable").
