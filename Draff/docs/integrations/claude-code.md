# Tích hợp Claude Code với cad-guard

Ngày kiểm: 04/11/2026. Bản đã cài: `claude` **2.1.318** (`C:\Users\Admin\.local\bin\claude`, Windows 11). Tài liệu chính thức đọc cùng ngày.

Quy ước ghi nguồn:

- **[máy]**: đã kiểm trên máy bằng lệnh ghi kèm. Không lệnh nào gọi mô hình (không `claude -p`, không phiên tương tác).
- **[tài liệu]**: đã đọc trên trang chính thức có link. Chưa chạy thử.
- **Chưa chắc**: suy luận hoặc nguồn chưa đủ. Gom lại ở mục 9.

Các lần chạy `claude mcp …` và `claude doctor` đặt `CLAUDE_CONFIG_DIR=<scratchpad>\cli-claude\config…`, tức một thư mục cấu hình trống riêng cho bài thử. Cách này không đụng tới `~/.claude` hay thông tin đăng nhập của người dùng, và máy chủ MCP của người dùng không bị khởi động. Thư mục thử nằm ngoài repo, chứa bản sao 3 tệp `fixtures/synthetic/*.dxf` (`ok_sheet`, `bad_layers`, `hygiene_bad`).

## 1. Cấu hình MCP

### 1.1 Ba phạm vi và chỗ lưu

| Phạm vi | Lưu ở | Ai thấy | Nguồn |
| --- | --- | --- | --- |
| `local` (mặc định của `claude mcp add`) | `~/.claude.json`, dưới khoá đường dẫn dự án | Chỉ mình, chỉ dự án đó | [tài liệu MCP](https://code.claude.com/docs/en/mcp); [máy] `claude mcp add --help`: `-s, --scope <scope> … (default: "local")` |
| `project` | `.mcp.json` ở gốc thư mục dự án | Ai mở thư mục đó | như trên |
| `user` | `~/.claude.json` | Mình, mọi dự án | như trên |

Trên Windows `~` là `%USERPROFILE%` ([Settings](https://code.claude.com/docs/en/settings)).

### 1.2 `.mcp.json` cho máy chủ stdio

Dạng do chính `claude mcp add -s project` ghi ra **[máy]**:

```json
{
  "mcpServers": {
    "cad-guard": {
      "type": "stdio",
      "command": "C:/…/python.exe",
      "args": ["-m", "cadguard", "mcp", "--workspace", "C:/…/phien", "--profile", "C:/…/ho-so.yaml"],
      "env": { "PYTHONPATH": "D:/…/packages/core" }
    }
  }
}
```

- `env` là tuỳ chọn. Chỉ cần khi cadguard chạy từ mã nguồn chưa cài (như máy thử). Cài bằng `pip install cadguard[agent]` thì bỏ `env`.
- Biến môi trường trong `command`, `args`, `env`: `${VAR}` và `${VAR:-mặc_định}` ([tài liệu MCP](https://code.claude.com/docs/en/mcp)). Biến chưa đặt và không có mặc định thì giữ nguyên chữ `${VAR}` và cảnh báo.
- Đường dẫn Windows: viết `/` chạy được **[máy]**. Viết `\` thì phải gấp đôi (`\\`) vì là JSON. Gọi thẳng `python.exe` nên **không cần** `cmd /c` (lời khuyên `cmd /c` chỉ dành cho `npx`).
- Trần thời gian khởi động máy chủ: `MCP_TIMEOUT` (ms), mặc định 30 giây cho `-p` với `--mcp-config` ([CLI reference](https://code.claude.com/docs/en/cli-reference)). Đầu ra công cụ: cảnh báo khi quá 10.000 token, cắt ở 25.000 token, đổi bằng `MAX_MCP_OUTPUT_TOKENS` ([tài liệu MCP](https://code.claude.com/docs/en/mcp)).
- Đo trên máy thử: chỉ riêng `import cadguard.mcp_server` mất ~9 giây; `claude mcp get cad-guard` ~21 giây; `claude mcp list` với 2 máy chủ ~47 giây **[máy]**. Máy khách chậm hơn có thể chạm trần 30 giây, nên đặt `MCP_TIMEOUT=60000` nếu thấy "Failed to connect".

### 1.3 `claude mcp add` (cú pháp đúng)

```powershell
claude mcp add cad-guard -s project -- "C:/Python313/python.exe" -m cadguard mcp --workspace "D:/CadGuardPhien/phien-01"
# có hồ sơ công ty:
claude mcp add cad-guard -s project -- "C:/Python313/python.exe" -m cadguard mcp --workspace "D:/CadGuardPhien/phien-01" --profile "D:/CadGuard/ho-so.yaml"
# có biến môi trường: tên máy chủ phải đứng TRƯỚC -e
claude mcp add cad-guard -s project -e PYTHONPATH=D:/cad-guard/packages/core -- "C:/…/python.exe" -m cadguard mcp --workspace "D:/…"
```

- `--` tách cờ của Claude Code khỏi lệnh chạy máy chủ ([tài liệu MCP](https://code.claude.com/docs/en/mcp)). `-t/--transport` mặc định `stdio` **[máy]** `claude mcp add --help`.
- **Bẫy đã gặp [máy]:** `claude mcp add -s project -e PYTHONPATH=… cad-guard -- …` báo `Invalid environment variable format: cad-guard` vì `-e` nhận nhiều cặp và nuốt luôn tên máy chủ. Đặt tên ngay sau `add` thì chạy.
- `-s project` ghi `.mcp.json` trong thư mục hiện tại; `-s local` ghi vào `.claude.json` dưới khoá dự án **[máy]**.
- Có `claude mcp add-json <tên> '<json>'` để dán nguyên khối JSON **[máy]** `claude mcp add-json --help`.

### 1.4 Phê duyệt máy chủ trong `.mcp.json` và tin cậy thư mục

Phiên tương tác hỏi trước khi dùng máy chủ từ `.mcp.json`; đặt lại lựa chọn bằng `claude mcp reset-project-choices` ([tài liệu MCP](https://code.claude.com/docs/en/mcp)). Các khoá ([Settings reference](https://code.claude.com/docs/en/settings-reference)):

- `enableAllProjectMcpServers`: duyệt mọi máy chủ trong `.mcp.json`. Mẫu đặt `false`.
- `enabledMcpjsonServers`: duyệt theo tên.
- `disabledMcpjsonServers`: từ chối theo tên, có hiệu lực ở mọi tệp cài đặt và mọi chế độ quyền.

Kết quả kiểm **[máy]** (`claude mcp list` trong thư mục thử):

| Tình huống | Kết quả |
| --- | --- |
| Chỉ có `.mcp.json` | `⏸ Pending approval (run 'claude' to approve)` |
| `enabledMcpjsonServers` trong `.claude/settings.json` hoặc `.claude/settings.local.json`, thư mục **chưa tin cậy** | Vẫn `Pending approval` |
| `enabledMcpjsonServers` trong **cài đặt người dùng** (`<CLAUDE_CONFIG_DIR>/settings.json`) | `✔ Connected` |
| Thư mục **đã tin cậy** (`projects["<đường dẫn>"].hasTrustDialogAccepted: true` trong `.claude.json` của thư mục cấu hình thử), duyệt trong `.claude/settings.json` | `✔ Connected` |
| Như trên nhưng `--profile` trỏ tới tệp không có | `✘ Failed to connect — CONNECTION_CLOSED` (kiểm sức khoẻ là thật, máy chủ thoát mã 2 đúng như thiết kế) |

Khớp tài liệu: quy tắc `permissions.allow`, `additionalDirectories` và việc tự duyệt `.mcp.json` của chính thư mục chỉ có hiệu lực **sau khi người dùng chấp nhận hộp thoại tin cậy**; `deny`/`ask` có hiệu lực ngay ([Permissions › Project allow rules and workspace trust](https://code.claude.com/docs/en/permissions)). `claude doctor` in đúng cảnh báo `Ignoring 3 permissions.allow entries from .claude/settings.json: this workspace has not been trusted…` **[máy]**.

Hệ quả cho cách A: lần đầu mở `claude` trong thư mục làm việc, người dùng **phải chấp nhận hộp thoại tin cậy** (hộp thoại liệt kê các quy tắc allow). cad-guard **không** tự ghi `hasTrustDialogAccepted` vào `~/.claude.json` của người dùng: tệp đó do Claude Code quản lý và chứa cả thông tin tài khoản.

## 2. Giới hạn công cụ để agent chỉ dùng cad-guard

### 2.1 Cú pháp quyền ([Permissions](https://code.claude.com/docs/en/permissions))

- Dạng `Tool` hoặc `Tool(specifier)`. Thứ tự xét: **deny → ask → allow**, khớp đầu tiên thắng. allow không khoét được ngoại lệ trong deny.
- Deny **tên trần** (ví dụ `"Bash"`) **gỡ hẳn công cụ khỏi ngữ cảnh**; deny có phạm vi (`Bash(rm *)`) chỉ chặn lời gọi khớp.
- Tên công cụ phải là tên chuẩn trong [Tools reference](https://code.claude.com/docs/en/tools-reference). Tên sai sinh cảnh báo; `claude doctor` báo `Permission deny rule "Reed" matches no known tool` **[máy]**. Với 19 tên trong mẫu, `doctor` **không** cảnh báo, nên cả 19 đều là công cụ có thật ở 2.1.318 **[máy]**.
- MCP: `mcp__<máy chủ>__*` (mọi công cụ của máy chủ) hoặc `mcp__<máy chủ>__<công cụ>`. Tên máy chủ có `.` hoặc dấu cách thành `_`. Allow chỉ nhận glob sau tiền tố `mcp__<máy chủ>__`; `"mcp__*"` trong allow bị bỏ qua. `cad-guard` có `-`, dùng nguyên được.
- `Write(path)`, `NotebookEdit(path)`, `Glob(path)` **không bao giờ khớp**; quyền theo đường dẫn chỉ dùng `Read(...)`/`Edit(...)`. Tên trần như mẫu thì đúng.
- `Read` deny áp "best-effort" cho Grep, Glob, `@tệp`. `Read`/`Edit` deny áp cho `cat`, `head`… trong Bash, nhưng **không** áp cho `grep -r .` hay script Python/Node tự mở tệp.
- Subagent: `Agent(Tên)`; tên trần `Agent` gỡ cả công cụ.
- Trên Windows có Git Bash, deny `Bash` cũng tắt công cụ `PowerShell`; không có Git Bash thì PowerShell bật sẵn và **cần deny riêng** ([Tools reference › PowerShell tool](https://code.claude.com/docs/en/tools-reference)). Mẫu deny cả hai.

### 2.2 Danh sách deny trong mẫu và lý do

| Công cụ | Lý do chặn |
| --- | --- |
| `Bash`, `PowerShell`, `Monitor` | Chạy lệnh (Monitor chạy lệnh nền) |
| `Read`, `Glob`, `Grep`, `LSP` | Đọc/tìm tệp, kể cả DXF, mà bỏ qua lớp ẩn danh |
| `Edit`, `Write`, `NotebookEdit` | Ghi tệp |
| `WebFetch`, `WebSearch` | Ra mạng |
| `Agent`, `Workflow` | Sinh subagent; subagent có bộ công cụ riêng |
| `Artifact`, `SendUserFile`, `RemoteTrigger`, `CronCreate`, `EnterWorktree` | Đẩy nội dung lên claude.ai/thiết bị khác, tác vụ đám mây hoặc lịch, đổi thư mục |

Giữ lại: các công cụ không chạm tệp (`AskUserQuestion`, `ToolSearch`, nhóm Task…) và `Skill` (được allow để dùng `knowledge/skills`).

### 2.3 Các lớp chặn và mức ép buộc thực sự

| Lớp | Chặn tới đâu | Mức | Nguồn |
| --- | --- | --- | --- |
| `--tools "<danh sách>"` / `--tools ""` khi khởi chạy | Công cụ dựng sẵn không có trong danh sách **không tồn tại** trong phiên. Không ảnh hưởng công cụ MCP | Mạnh nhất cho dựng sẵn. Chỉ dùng được khi cad-guard tự khởi chạy (B, C, bench) | [CLI reference](https://code.claude.com/docs/en/cli-reference) |
| `--restricted` | Gỡ công cụ chạy lệnh/mã và WebFetch (trừ khi `--tools` nêu tên), giam công cụ tệp trong thư mục làm việc, **bỏ qua cài đặt user/project/local** (chỉ managed + `--settings`), cấm `bypassPermissions` | Mạnh; thiết kế cho harness đánh giá | [CLI reference](https://code.claude.com/docs/en/cli-reference); [máy] có trong `claude --help` |
| Deny tên trần (tệp cài đặt hoặc `--disallowedTools`) | Gỡ công cụ khỏi ngữ cảnh; Claude Code thi hành, không phụ thuộc mô hình | Mạnh, với hai ngoại lệ ở dưới | [Permissions](https://code.claude.com/docs/en/permissions) |
| `defaultMode: "dontAsk"` | Mọi lời gọi cần hỏi đều bị từ chối, trừ cái có trong allow | Mạnh; công cụ "không cần hỏi" (đọc tệp trong thư mục làm việc) vẫn chạy, nên vẫn cần deny | [Permissions › modes](https://code.claude.com/docs/en/permissions) |
| `blockReadsOutsideWorkingDirectories`, `blockWritesOutsideWorkingDirectories` | Công cụ tệp từ chối đường dẫn ngoài thư mục làm việc ở mọi chế độ. **Không** giới hạn shell, MCP, hook. Giá trị `true` thắng cả managed | Lớp phòng thủ thêm | [Permissions › Working directories](https://code.claude.com/docs/en/permissions) |
| `allowedMcpServers` trong `.claude/settings.json` | Chặn máy chủ MCP **khác** cad-guard (ví dụ máy chủ đọc tệp người dùng đã cài ở phạm vi user). Đã thấy [máy]: máy chủ phạm vi user `may-chu-khac` biến khỏi `claude mcp list` khi có allowlist, hiện lại khi bỏ allowlist; `claude mcp add` trong thư mục đó báo `not allowed by enterprise policy` | **Mềm**: allowlist hợp nhất từ mọi phạm vi, người dùng mở rộng được trong cài đặt của mình; `serverName` "không phải biện pháp an ninh". Muốn cứng: managed + `allowManagedMcpServersOnly` + `serverCommand` | [Managed MCP](https://code.claude.com/docs/en/managed-mcp) |
| `--strict-mcp-config --mcp-config <tệp>` | Chỉ nạp máy chủ từ tệp chỉ định, bỏ `.mcp.json`, user, local | Mạnh, cho B/C/bench | [CLI reference](https://code.claude.com/docs/en/cli-reference) |
| Hook `PreToolUse` | Hook thoát mã 2 chặn **trước** khi xét quy tắc, kể cả khi allow khớp; hook trả "allow" **không** vượt deny | Mạnh, nhưng cần một lệnh (Python…) chạy được trên máy | [Permissions › hooks](https://code.claude.com/docs/en/permissions) |
| Sandbox | Ép ở mức hệ điều hành cho Bash/PowerShell/Monitor | **Không có trên Windows thuần**: chỉ macOS, Linux, WSL2 | [Settings reference](https://code.claude.com/docs/en/settings-reference), [Permissions › sandboxing](https://code.claude.com/docs/en/permissions) |
| Managed settings (admin cài vào thư mục hệ thống) | Không phạm vi nào ghi đè được | Mạnh nhất trên máy khách. Cần quyền quản trị máy | [Settings](https://code.claude.com/docs/en/settings), [Managed MCP](https://code.claude.com/docs/en/managed-mcp) (`managed-mcp.json` trên Windows: `C:\Program Files\ClaudeCode\managed-mcp.json`) |
| `CLAUDE.md` / `AGENTS.md` | Chỉ là lời dặn | **Không chặn gì** | [Memory](https://code.claude.com/docs/en/memory): dùng hook nếu muốn chặn chắc |

Hai ngoại lệ của deny ([Permissions › Precedence among rules, hooks, and mods](https://code.claude.com/docs/en/permissions)):

1. **Mod** (plugin dạng mod, người dùng tự cài) xử lý `tool.check` **có thể duyệt** một lời gọi mà deny đã từ chối hoặc hook đã chặn, khi máy **không có managed settings** và phiên **không** đăng nhập Team/Enterprise. Máy khách nào cài mod lạ thì deny trong tệp dự án không còn chắc.
2. `-p` bỏ qua **im lặng** tệp cài đặt bị lỗi xác thực (`claude --help` ở mục `-p` **[máy]**). Một `.claude/settings.json` hỏng thì mất hết deny mà không báo. Với B/C/bench, phải đưa các chặn chính lên **dòng lệnh** (`--tools`, `--disallowedTools`, `--strict-mcp-config`), không chỉ dựa vào tệp.

Kết luận: trên Windows, cách A (người dùng tự mở `claude`) đạt mức "Claude Code từ chối công cụ theo cấu hình dự án". Đó là ép buộc bởi chương trình, nhưng người dùng sửa được và mod có thể vượt. Chặn cứng hơn cần managed settings do IT công ty cài, hoặc cách B/C nơi cad-guard tự đặt cờ dòng lệnh. Lớp chắc chắn trong mọi trường hợp vẫn là **thư mục làm việc chỉ chứa tệp của phiên**.

### 2.4 Tự học (auto memory)

Claude Code tự ghi ghi chú giữa các phiên. Tắt cho dự án bằng `"autoMemoryEnabled": false` ([Memory](https://code.claude.com/docs/en/memory)). Mẫu tắt để ghi chú về bản vẽ (dù đã ẩn danh) không đọng lại trên máy.

## 3. Chạy không giao diện (cách B và bench)

### 3.1 Cờ ([Headless](https://code.claude.com/docs/en/headless), [CLI reference](https://code.claude.com/docs/en/cli-reference))

| Cờ | Ý nghĩa | Có trong `claude --help` 2.1.318 **[máy]** |
| --- | --- | --- |
| `-p` | Chạy một lượt rồi thoát; bỏ hộp thoại tin cậy | có |
| `--output-format text\|json\|stream-json` | `json`: một kết quả, có `result`, `session_id`, `usage`, `total_cost_usd` và chi phí theo mô hình. `stream-json`: JSON theo dòng, dòng cuối là `result` | có |
| `--input-format stream-json` | Nhận tin nhắn người dùng theo luồng qua stdin; hợp cho hội thoại nhiều lượt trong một tiến trình | có |
| `--verbose`, `--include-partial-messages` | Cần cho `stream-json` khi muốn từng mẩu chữ | có |
| `--max-turns N` | Trần số lượt agent (chỉ `-p`) | **không** (ẩn), nhưng có trong CLI reference |
| `--max-budget-usd` | Dừng khi chi phí **ước tính** chạm trần (chỉ `-p`) | có |
| `--model` | Bí danh (`sonnet`, `opus`…) hoặc tên đầy đủ | có |
| `--append-system-prompt`, `--system-prompt` | Thêm hoặc thay lời nhắc hệ thống | có |
| `--append-system-prompt-file`, `--system-prompt-file` | Như trên, đọc từ tệp | **không** (ẩn), có trong CLI reference |
| `--permission-mode dontAsk` | Từ chối mọi thứ cần hỏi | có |
| `--permission-prompts none` | Không ai trả lời hỏi quyền: từ chối, bảo mô hình đừng thử lại, gỡ `AskUserQuestion` | có |
| `--no-session-persistence` | Không lưu phiên ra đĩa | có |
| `--bare` | Không nạp hook, skill, plugin, `CLAUDE.md`, `.mcp.json`, auto memory; **chỉ** dùng `ANTHROPIC_API_KEY` hoặc `apiKeyHelper` qua `--settings`, **không đọc OAuth/keychain** | có |
| `--json-schema` | Ép đầu ra theo JSON Schema, kết quả ở `structured_output` | có |

- Phiên `-p` hoặc SDK **không bao giờ** được coi là đã tin cậy thư mục. `permissions.allow` trong `.claude/settings.json` **không** được dùng (in cảnh báo `this workspace has not been trusted`), trong khi `.mcp.json` lại được nối **không hỏi** ([Permissions › What runs before you trust a folder](https://code.claude.com/docs/en/permissions)). B/bench phải đưa allow qua `--allowedTools` hoặc `--settings`, và dùng `--strict-mcp-config`.
- `system/init` (dòng đầu của `stream-json`) có `mcp_servers` (tên + trạng thái) và `mcp_server_errors` ([Headless](https://code.claude.com/docs/en/headless)). cad-guard nên kiểm `cad-guard` có `connected` trước khi gửi việc.
- `total_cost_usd` là **ước tính phía máy khách**, có thể khác hoá đơn ([Headless](https://code.claude.com/docs/en/headless), [cost tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking)).

### 3.2 Lệnh đề xuất (chưa chạy vì tốn token)

Cách B, hội thoại nhiều lượt, đăng nhập thuê bao của người dùng (không `--bare`):

```text
claude -p --input-format stream-json --output-format stream-json --verbose
  --mcp-config <phien>/.mcp.json --strict-mcp-config
  --tools "Skill"
  --allowedTools "mcp__cad-guard__*" "Skill"
  --disallowedTools "Bash" "PowerShell" "Monitor" "Read" "Edit" "Write" "NotebookEdit" "Glob" "Grep" "LSP" "WebFetch" "WebSearch" "Agent" "Workflow" "Artifact" "SendUserFile" "RemoteTrigger" "CronCreate" "EnterWorktree"
  --permission-mode dontAsk --permission-prompts none
  --settings <cad-guard>/claude-settings.json
  (cwd = thư mục làm việc của phiên)
```

Bench (khoá API của bên chạy bench, tái lập được):

```text
claude --bare -p "<câu hỏi>" --output-format json
  --mcp-config <phien>/.mcp.json --strict-mcp-config
  --tools "" --allowedTools "mcp__cad-guard__*" --permission-mode dontAsk
  --append-system-prompt-file knowledge/AGENTS.md
  --max-turns 20 --max-budget-usd 1 --no-session-persistence --model <mô hình>
```

Chưa chắc: `--tools ""` hoặc `--tools "Skill"` có gỡ luôn `ToolSearch` không, và khi đó công cụ MCP còn nạp được không (6 công cụ thì có lẽ không bị hoãn nạp). Phải thử một lần có token trước khi chốt.

### 3.3 Agent SDK ([tổng quan](https://code.claude.com/docs/en/agent-sdk/overview))

- Python `claude-agent-sdk` 0.2.178 (PyPI, phân loại MIT, **gói kèm CLI Claude Code**, có `cli_path` để dùng bản đã cài) ([repo](https://github.com/anthropics/claude-agent-sdk-python)). TypeScript `@anthropic-ai/claude-agent-sdk` 0.3.318, license `SEE LICENSE IN README.md` **[máy]** `npm view`, `pip index versions`.
- Giấy phép: "Use of the Claude Agent SDK is governed by Anthropic's Commercial Terms of Service…", trừ thành phần có LICENSE riêng ([tổng quan](https://code.claude.com/docs/en/agent-sdk/overview)). Nhãn MIT trên PyPI/GitHub chỉ là lớp vỏ; CLI đi kèm vẫn theo điều khoản thương mại.
- Đăng nhập thuê bao: "Unless previously approved, Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK." → **SDK chỉ dùng với khoá API/Bedrock/Vertex/Foundry**, trừ khi Anthropic duyệt bằng văn bản.
- Thương hiệu khi dùng SDK: được "Claude Agent", "{Tên} Powered by Claude"; **không** được "Claude Code", "Claude Code Agent" hay ASCII art giống Claude Code.

## 4. ACP

- Danh sách agent trên [agentclientprotocol.com](https://agentclientprotocol.com/overview/agents) ghi "Claude Agent (via Zed's SDK adapter)", link tới `zed-industries/claude-agent-acp`.
- Gói npm hiện tại: `@agentclientprotocol/claude-agent-acp` **0.100.0**, Apache-2.0, lệnh `claude-agent-acp`, repo `agentclientprotocol/claude-agent-acp`, người duy trì benbrandt, aguzubiaga, cirwin (nhóm Zed), phụ thuộc `@anthropic-ai/claude-agent-sdk` 0.3.316 và `@agentclientprotocol/sdk` 2.4.0 **[máy]** `npm view`. Hai tên cũ `@zed-industries/claude-code-acp` và `@zed-industries/claude-agent-acp` đã đánh dấu deprecated, trỏ sang tên mới **[máy]**.
- Như vậy adapter **chạy trên Agent SDK**. README: bản phát hành độc lập kèm sẵn CLI `claude`; đặt `CLAUDE_CODE_EXECUTABLE` để dùng bản đã cài ([repo](https://github.com/zed-industries/claude-agent-acp)).
- Cách chạy: client ACP khởi chạy `claude-agent-acp` làm tiến trình con (JSON-RPC qua stdio), ví dụ `npx @agentclientprotocol/claude-agent-acp` (suy từ trường `bin`; README không ghi lệnh `npx`, **chưa chạy**). Zed: cài "Claude Agent" từ ACP Registry; xác thực bằng `/login`, "API key or with Claude Code where supported"; điều khoản do người dùng và nhà cung cấp agent tự lo ([Zed external agents](https://zed.dev/docs/ai/external-agents)).
- Hệ quả: đi qua ACP là đi qua **Agent SDK**, nên rơi vào câu "không cung cấp đăng nhập claude.ai cho sản phẩm bên thứ ba… kể cả agent dựng trên Agent SDK". Với cad-guard: **ACP + khoá API: được. ACP + đăng nhập thuê bao: chưa chắc**, cần Anthropic trả lời bằng văn bản. Zed có thể đã được duyệt; ta không biết.

## 5. Xác thực và điều khoản

### 5.1 Các cách xác thực ([Authentication](https://code.claude.com/docs/en/authentication))

Thứ tự ưu tiên khi có nhiều thông tin:

1. Bedrock/Vertex/Foundry (`CLAUDE_CODE_USE_BEDROCK`/`_VERTEX`/`_FOUNDRY`)
2. `ANTHROPIC_AUTH_TOKEN`
3. `ANTHROPIC_API_KEY` (với `-p` luôn dùng nếu có)
4. `apiKeyHelper`
5. `CLAUDE_CODE_OAUTH_TOKEN` (từ `claude setup-token`)
6. Hồ sơ Anthropic/WIF
7. Đăng nhập thuê bao `/login`

Trên Windows thông tin đăng nhập nằm ở `%USERPROFILE%\.claude\.credentials.json`. Đăng nhập không cần phiên tương tác: `claude auth login` (có trong `claude auth --help` **[máy]**). `--bare` không đọc OAuth, không đọc `CLAUDE_CODE_OAUTH_TOKEN`.

### 5.2 Trang pháp lý ([Legal and compliance](https://code.claude.com/docs/en/legal-and-compliance), đọc ngày 04/11/2026)

Đã kiểm, có trong văn bản:

- Giấy phép dùng: Commercial Terms cho Team/Enterprise/API; Consumer Terms cho Free/Pro/Max/Ultra.
- "Can customers offer Claude Code in their products?": **chạy hoặc cài sẵn Claude Code trong sản phẩm** phải đồng ý Commercial Terms và hai điều kiện:
  1. **Không sửa binary**, cài và chạy như Anthropic phát hành, **không gỡ, tắt hay hạn chế phương thức xác thực có sẵn** (kể cả đăng nhập tài khoản Claude hoặc khoá API của người dùng).
  2. **Không trả tiền thay, bán lại hay làm trung gian** việc dùng Claude; **mỗi người dùng cuối tự xác thực** bằng khoá API, thông tin gói thuê bao Claude hoặc nhà cung cấp 3P **của chính họ**, và bị tính tiền trực tiếp.
- OAuth chỉ dành cho người mua gói thuê bao, cho "ordinary use of Claude Code and other native Anthropic applications". Nhà phát triển sản phẩm, kể cả dùng Agent SDK, phải dùng khoá API. **Cấm** cung cấp đăng nhập Claude.ai trong ứng dụng của mình, **cấm** định tuyến yêu cầu qua thông tin gói Free/Pro/Max/Ultra thay người dùng, **cấm** thu thập, lưu hay làm trung gian thông tin đăng nhập hoặc token phiên; đăng nhập phải đi qua luồng của Anthropic.
- Câu then chốt cho cách B: quy định trên "không ngăn người dùng cuối đăng nhập vào **binary Claude Code không sửa đổi** bằng gói thuê bao Claude của chính họ, kể cả khi một nền tảng host Claude Code như mô tả ở trên".
- Hạn mức gói Pro/Max/Ultra giả định "ordinary, individual usage".
- Tên: được nói bằng chữ thường rằng sản phẩm "chạy Claude Code"/"cài sẵn Claude Code". **Không** được dùng tên hay logo Claude Code/Anthropic trong tên sản phẩm, tính năng, công ty, logo, hoặc theo cách gợi ý Anthropic làm, bảo trợ hay hợp tác.
- Anthropic có thể thi hành không báo trước. Câu hỏi về cách xác thực → liên hệ sales.

Chưa chắc:

- Kế hoạch (`plans/cad-guard-agent.md` mục 2.2) ghi theo nguồn thứ cấp rằng từ 04/04/2026 gói thuê bao không còn bao phủ "harness bên thứ ba". Trang pháp lý hiện tại **không** nói vậy; nó cho phép rõ người dùng tự đăng nhập binary nguyên bản do nền tảng host. Coi tin thứ cấp kia là chưa xác nhận.
- Chạy cad-guard với `--bare` khi người dùng chỉ có gói thuê bao có bị coi là "hạn chế phương thức xác thực" không. Đề xuất: chỉ dùng `--bare` khi chính người dùng chọn khoá API (cách C, bench).
- "Cài sẵn" có bao gồm việc cad-guard **đóng gói kèm** binary trong bộ cài không. LICENSE "All rights reserved" → đề xuất **không** đóng gói; để người dùng cài bằng bộ cài chính thức, cad-guard chỉ tìm `claude` trên máy.

## 6. Giấy phép của Claude Code CLI

- `LICENSE.md` trong [anthropics/claude-code](https://github.com/anthropics/claude-code/blob/main/LICENSE.md) chỉ có một dòng: "© Anthropic PBC. All rights reserved. Use is subject to Anthropic's Commercial Terms of Service." Đây **không** phải giấy phép mã nguồn mở.
- Hệ quả cho cad-guard:
  1. Không nhúng, không sửa, không phân phối lại binary. Khởi chạy bản người dùng đã cài là cách duy nhất phù hợp với cả LICENSE lẫn trang pháp lý.
  2. Không phải copyleft, không lây giấy phép sang mã cad-guard, vì cad-guard không liên kết mà chỉ gọi tiến trình con. Không vướng quy tắc DWG/copyleft của `docs/licenses.md`.
  3. Công ty phát hành cad-guard cần **đồng ý Commercial Terms** nếu "chạy Claude Code trong sản phẩm" (cách B/C). Việc cần người: pháp chế đọc Commercial Terms.
  4. Adapter ACP là Apache-2.0 (dùng tự do, giữ NOTICE), nhưng kéo theo Agent SDK và CLI dưới Commercial Terms.

## 7. Mẫu `knowledge/mcp/claude-code/` (đã sửa, đã kiểm)

| Tệp mẫu | Chép tới | Nội dung |
| --- | --- | --- |
| `.mcp.json` | `<THU_MUC_LAM_VIEC>/.mcp.json` | Hai máy chủ: `cad-guard` (mặc định) và `cad-guard-ho-so` (thêm `--profile <HO_SO_CONG_TY>`), cùng `"type": "stdio"` |
| `.claude/settings.json` | `<THU_MUC_LAM_VIEC>/.claude/settings.json` | Duyệt `cad-guard`, từ chối `cad-guard-ho-so`; allowlist 2 máy chủ; allow `mcp__cad-guard__*`, `mcp__cad-guard-ho-so__*`, `Skill`; deny 19 công cụ; `dontAsk`; cấm bypass/auto; chặn đọc/ghi ngoài thư mục; tắt auto memory |

Muốn dùng hồ sơ công ty: đổi chỗ hai tên giữa `enabledMcpjsonServers` và `disabledMcpjsonServers`. Đã kiểm [máy]: sau khi đổi, `claude mcp list` chỉ còn `cad-guard-ho-so … --profile … ✔ Connected`.

Kiểm thật **[máy]**: điền mẫu bằng đường dẫn thật (Python của venv thử, `PYTHONPATH` trỏ `packages/core`, thêm `CLAUDE.md` = `@AGENTS.md`, `AGENTS.md`, `.claude/skills/`) vào `<scratchpad>\cli-claude\phien2\`:

1. Chưa tin cậy: `cad-guard … ⏸ Pending approval`; `doctor` báo 3 allow bị bỏ qua.
2. Đã tin cậy: `cad-guard … ✔ Connected`; `cad-guard-ho-so` ẩn (bị từ chối); máy chủ user `may-chu-khac` ẩn (allowlist); `doctor` không có cảnh báo về quyền.
3. Bỏ allowlist: `may-chu-khac ✔ Connected` lộ ra. Đây là bằng chứng allowlist có tác dụng.

Chưa kiểm vì cần gọi mô hình: trong phiên thật, trợ lý gọi được 6 công cụ chỉ đọc (thêm `propose_changeset` nếu máy chủ chạy với `--allow-propose`) và bị từ chối khi thử `Read`/`Bash`/`PowerShell`. Đây là bài thử bắt buộc trước khi dùng với bản vẽ khách (mục 5.1 kế hoạch).

Điều mẫu cũ sai hoặc thiếu:

- `settings.json` nằm ở gốc thư mục mẫu, dễ chép nhầm chỗ. Nay đặt sẵn đúng đường dẫn `.claude/settings.json`.
- Thiếu deny `PowerShell` (trên Windows không có Git Bash thì PowerShell bật sẵn và deny `Bash` không che), `Monitor` (chạy lệnh), `LSP`, `Agent`, `Workflow`, `Artifact`/`SendUserFile`/`RemoteTrigger` (đẩy nội dung ra ngoài máy), `CronCreate`, `EnterWorktree`.
- Ngầm cho rằng `enabledMcpjsonServers` trong tệp dự án tự duyệt máy chủ. Thực tế chỉ có hiệu lực **sau khi tin cậy thư mục**, và allow của dự án **không** dùng trong `-p`/SDK.
- Không chặn máy chủ MCP khác của người dùng (thiếu `allowedMcpServers`).
- Thiếu `Skill` trong allow, thiếu `dontAsk`, thiếu khoá cấm bypass/auto, thiếu chặn ngoài thư mục, không tắt auto memory.
- Không có lựa chọn `--profile`, thiếu `"type": "stdio"`.
- README ghi "Claude Code đọc `CLAUDE.md`". Từ v2.1.277 Claude Code đọc `AGENTS.md` trực tiếp khi không có `CLAUDE.md` ([Memory](https://code.claude.com/docs/en/memory)). `CLAUDE.md` chứa `@AGENTS.md` vẫn là cách chắc nhất.

## 8. Khuyến nghị cho cad-guard

### A. Từ CLI agent của người dùng (gói làm việc)

- Giao gói gồm `.mcp.json` + `.claude/settings.json` theo mẫu, `AGENTS.md`, `CLAUDE.md` (`@AGENTS.md`), `.claude/skills/`, và **chỉ** DXF của phiên. Người dùng tự cài Claude Code bằng bộ cài chính thức, tự `claude auth login`.
- Lần đầu: hướng dẫn **chấp nhận hộp thoại tin cậy**. Thiếu bước này thì máy chủ treo "Pending" và allow không có hiệu lực, nên công cụ cad-guard bị `dontAsk` từ chối.
- Bài thử chấp nhận cho mỗi phiên bản Claude Code: hỏi trợ lý đọc một DXF bằng công cụ tệp, đọc tệp ngoài thư mục, chạy một lệnh shell. Cả ba phải bị từ chối. Ghi lại phiên bản.
- Công ty khách có IT: đề nghị đẩy cùng nội dung deny + `allowedMcpServers` (`serverCommand`) + `allowManagedMcpServersOnly` + `disableBypassPermissionsMode` vào **managed settings** để người dùng và mod không vượt được.
- Mức ép buộc phải nói thật với khách: chương trình chặn theo cấu hình người dùng sửa được; không có sandbox hệ điều hành trên Windows.

### B. Trong ứng dụng cad-guard, AI qua hạn mức tài khoản

- Dùng **`claude -p` stream-json** (binary nguyên bản, tiến trình con, mỗi phiên một thư mục làm việc do cad-guard tạo) với cờ ở mục 3.2. Đây là đường mà trang pháp lý cho phép rõ nhất: binary không sửa, người dùng tự đăng nhập qua luồng của Anthropic, tự chịu cước.
- cad-guard **không** đọc, sao chép hay chuyển `.credentials.json`, `CLAUDE_CODE_OAUTH_TOKEN`; không gọi `setup-token` thay người dùng; không đặt `--bare` (giữ nguyên mọi phương thức xác thực). Khi chưa đăng nhập: hiển thị "chạy `claude auth login` trong terminal" thay vì tự làm.
- Mọi chặn đặt trên **dòng lệnh** (`--tools`, `--disallowedTools`, `--strict-mcp-config`, `--permission-mode dontAsk`, `--permission-prompts none`), không chỉ trong tệp. Kiểm `system/init.mcp_servers` trước lượt đầu.
- **Không** dùng ACP adapter cho đăng nhập thuê bao cho tới khi Anthropic trả lời bằng văn bản (adapter chạy trên Agent SDK). Gửi câu hỏi cho sales sớm.
- Tên sản phẩm/tính năng không chứa "Claude Code". Được ghi "chạy Claude Code do bạn tự đăng nhập".
- Hiển thị `total_cost_usd` là **ước tính**. Với gói thuê bao, đó không phải số tiền bị trừ.

### C. Trong ứng dụng cad-guard, API trực tiếp (khoá của khách)

- Hai đường hợp lệ:
  1. Vẫn chạy `claude --bare -p` với khoá của khách đưa vào **biến môi trường của riêng tiến trình con**, lấy từ kho khoá hệ điều hành, không ghi ra tệp (đúng quy tắc repo). Hoặc `apiKeyHelper` trong `--settings` gọi lệnh đọc kho khoá.
  2. Agent SDK (Python) với khoá API. Đúng như tài liệu SDK yêu cầu; theo Commercial Terms.
- Khoá phải là của khách, tính cước cho khách. cad-guard không trả thay, không bán lại.
- Bedrock/Vertex/Foundry của khách dùng được như nhau (biến `CLAUDE_CODE_USE_*`).
- Đây cũng là chế độ cho **bench**: tái lập, `--bare`, có `--max-turns`, `--max-budget-usd`, không phụ thuộc cấu hình máy người chạy.

## 9. Chưa chắc

1. `--tools ""` / `--tools "Skill"` có gỡ `ToolSearch` không, và MCP còn chạy bình thường không (mục 3.2). Cần một lần chạy có token.
2. Trong phiên thật, deny + `dontAsk` từ `.claude/settings.json` có thật sự chặn `Read`/`PowerShell` như tài liệu nói. Mới kiểm được ở mức `doctor` (tên hợp lệ) và tài liệu.
3. `defaultMode: "dontAsk"` đặt trong tệp **dự án** có được tôn trọng không. Tài liệu chỉ nói `auto` và `bypassPermissions` bị bỏ qua ở tệp dự án.
4. `allowedMcpServers` ở tệp dự án có áp **trước** khi tin cậy thư mục không (mới thấy nó áp sau khi tin cậy).
5. ACP + gói thuê bao: được hay không (mục 4). Zed có giấy phép riêng không.
6. `--bare` có bị coi là "hạn chế phương thức xác thực" trong cách B không (mục 5.2). Theo cùng lập luận, gỡ biến xác thực (`CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`…) khỏi môi trường của `claude` cũng là hạn chế phương thức xác thực. **Đã chốt cho engine `claude-cli`** (`cadguard/assistant/cli_engines.py`, 04/11/2026): không dùng `--bare`; tiến trình `claude` nhận nguyên môi trường của người dùng, cad-guard không thêm và không bớt biến xác thực; có `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` thì chỉ cảnh báo rằng Claude Code sẽ tính cước theo khoá thay cho hạn mức gói. Biến xác thực chỉ bị gỡ khỏi máy chủ MCP của cad-guard (không cần khoá).
7. Đóng gói kèm binary trong bộ cài cad-guard có tính là "preinstalling" được phép không. Hiện khuyến nghị không đóng gói.
8. Tin thứ cấp "từ 04/04/2026 thuê bao không bao phủ harness bên thứ ba": không thấy trên trang chính thức hôm nay.
9. Tên các trường trong JSON kết quả ngoài `result`, `session_id`, `usage`, `total_cost_usd`, `structured_output` (ví dụ `num_turns`, `duration_ms`, `is_error`, `modelUsage`): theo trí nhớ, chưa thấy liệt kê trên trang đã đọc.
10. Lệnh `npx @agentclientprotocol/claude-agent-acp` chưa chạy; chỉ suy từ trường `bin` của gói.
11. Thời gian khởi động máy chủ (~9–20 giây trên máy thử) có vượt `MCP_TIMEOUT` mặc định trên máy khách yếu hay không.
