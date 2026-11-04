# Cấu hình MCP mẫu cho CLI agent

Thư mục này có mẫu cấu hình để một CLI agent có sẵn gọi máy chủ MCP **chỉ đọc** của cad-guard:

```text
<PYTHON> -m cadguard mcp --workspace <THU_MUC_LAM_VIEC>
```

| CLI | Tệp mẫu | Đặt ở đâu | Độ chắc về định dạng |
| --- | --- | --- | --- |
| Claude Code | `claude-code/.mcp.json` | gốc thư mục làm việc của phiên | **Đã kiểm** với Claude Code 2.1.318 (`claude mcp list` báo `✔ Connected` sau khi tin cậy thư mục). Hai máy chủ: `cad-guard` và `cad-guard-ho-so` (có `--profile`) |
| Claude Code (quyền) | `claude-code/.claude/settings.json` | `.claude/settings.json` trong thư mục làm việc (giữ nguyên đường dẫn) | **Đã kiểm** tên công cụ bằng `claude doctor`, allowlist máy chủ bằng `claude mcp list`. Chưa kiểm trong phiên có gọi mô hình. Chi tiết: `docs/integrations/claude-code.md` |
| Codex CLI (khuyến nghị) | `codex/cadguard.config.toml` | `$CODEX_HOME/cadguard.config.toml` (mặc định `~/.codex/`), mở bằng `codex -p cadguard -C <THU_MUC_LAM_VIEC>` | **Đã kiểm với codex-cli 0.165.0** (04/11/2026): hồ sơ cấu hình gồm máy chủ MCP + tắt shell/xem ảnh/web + read-only. Chi tiết và nguồn: `docs/integrations/codex.md` |
| Codex CLI (chỉ MCP) | `codex/config.toml` | gộp vào `~/.codex/config.toml`, hoặc `<THU_MUC_LAM_VIEC>/.codex/config.toml` (chỉ nạp khi thư mục được Codex đánh dấu `trusted`) | Đã kiểm: `[mcp_servers.cad-guard]` với `command`, `args`, `cwd`, `startup_timeout_sec`, `required`, `enabled_tools`. Không có khoá chặn công cụ |
| OpenCode | `opencode/opencode.json` | gốc thư mục làm việc (`opencode.json` của dự án) | **Đã thử với OpenCode 1.19.4**: `opencode mcp list` báo `cad-guard connected` (cả bản có `--profile`); quyền `"*": "deny"` + `cad-guard_*` đã kiểm bằng `opencode debug agent`. Chưa thử phiên có mô hình. Chi tiết: `docs/integrations/opencode.md` |
| Antigravity CLI (`agy`) | `antigravity/mcp_config.json` | `%USERPROFILE%\.gemini\config\mcp_config.json` (cấp người dùng, áp cho mọi phiên `agy`). Tài liệu còn nêu `<THU_MUC_LAM_VIEC>/.agents/mcp_config.json`, nhưng chưa kiểm | **Đã kiểm với `agy` 1.5.0** (04/11/2026, thư mục người dùng tạm): `agy mcp list` đọc đúng mẫu (cả mục `cad-guard-ho-so` có `--profile`); `agy acp` + `session/new` khởi động máy chủ và nạp công cụ. Khoá `mcpServers` (`command`, `args`, `env`, `disabled`, `enabledTools`, `timeoutSeconds`). Chưa thử phiên có mô hình. Chi tiết: `docs/integrations/antigravity.md` |
| Antigravity CLI (quyền) | `antigravity/cadguard.settings.json` | để đâu cũng được, mở bằng `agy --settings <tệp> --sandbox` (chỉ áp cho phiên, không ghi vào `settings.json` của người dùng) | **Đã kiểm** bằng `agy -p "/permissions" --settings …` và `-p "/config"` (CLI tự trả lời, không gọi mô hình): `agy` nạp đủ luật. Chưa kiểm luật có chặn hết công cụ trong phiên có mô hình |

Mẫu OpenCode đã được thử kết nối MCP và kiểm quyền với OpenCode 1.19.4 (chưa thử phiên có mô hình). Mẫu Claude Code đã được thử kết nối MCP với Claude Code 2.1.318 (chưa thử phiên có mô hình), xem mục "Claude Code". Mẫu Codex đã được thử với codex-cli 0.165.0 (chưa thử phiên có mô hình): Codex nạp đúng mẫu, khởi động máy chủ cad-guard và gọi được `list_drawings`/`audit`/`explain_rule` có áp `--profile`, xem `docs/integrations/codex.md`. Các mẫu khác chưa được thử chạy thật với từng CLI. Đây là việc của bước A0/A1 trong `plans/cad-guard-agent.md`.

## Cách dùng

1. Cài cad-guard kèm SDK MCP vào một Python trên máy: `pip install cadguard[agent]` (hoặc trong repo: `pip install -e packages/core[agent]`). Kiểm: `<PYTHON> -m cadguard mcp --help`.
2. Tạo **thư mục làm việc rỗng** cho phiên (ví dụ `D:/CadGuardPhien/phien-01`). Chỉ chép vào đó các DXF cần xem trong phiên này. Không mở CLI ở thư mục chứa toàn bộ bản vẽ của công ty.
3. Chép tệp mẫu của CLI vào chỗ ghi ở bảng trên. Thay giữ chỗ:
   - `<PYTHON>`: đường dẫn đầy đủ tới `python` đã cài cad-guard (ví dụ `C:/Python313/python.exe`);
   - `<THU_MUC_LAM_VIEC>`: đường dẫn đầy đủ tới thư mục làm việc của phiên.
   - Trên Windows, trong JSON viết `/` hoặc `\\` (hai dấu gạch ngược).
4. Chép `knowledge/AGENTS.md` vào gốc thư mục làm việc. Claude Code từ v2.1.277 đọc thẳng `AGENTS.md` khi không có `CLAUDE.md`; cách chắc nhất vẫn là tạo thêm `CLAUDE.md` chỉ chứa dòng `@AGENTS.md`. Chép `knowledge/skills/` vào chỗ CLI đọc skill (ví dụ `.claude/skills/` cho Claude Code); chỗ đọc skill của các CLI khác cần kiểm lại.
5. Mở CLI **trong thư mục làm việc đó**, tự đăng nhập bằng tài khoản hoặc khoá API của chính bạn/công ty.

Máy chủ mặc định ẩn danh Bậc 1. Chỉ thêm `--no-anonymize` vào `args` khi khách đã đồng ý bằng văn bản.

Hồ sơ công ty (tuỳ chọn): thêm `"--profile", "<HO_SO_CONG_TY>"` vào cuối `args` (đường dẫn đầy đủ tới tệp YAML `cg.company-profile/1`); không có `--standard` thì chuẩn mặc định là chuẩn ghi trong hồ sơ, và `audit`/`explain_rule` trả `profile: {name, version}` của hồ sơ đã áp. Hai mẫu Codex có dòng ví dụ để bỏ dấu `#` (đừng nhầm `--profile` của cad-guard với `-p/--profile` của Codex: cái sau chọn tệp `$CODEX_HOME/<tên>.config.toml`); mẫu OpenCode có mục `cad-guard-ho-so` đang tắt (`enabled: false`): thay `<HO_SO_CONG_TY>`, đặt `enabled: true` và đặt `cad-guard` thành `enabled: false` (chỉ bật một trong hai để trợ lý không thấy hai bộ công cụ trùng nhau).

## Đăng nhập và khoá

- cad-guard **không đọc, không lưu, không chuyển** thông tin đăng nhập hay khoá của CLI. CLI tự đăng nhập theo cách của nó.
- Các tệp mẫu không chứa khoá hay token, và **không được** thêm vào. Khoá API (nếu dùng) để trong kho khoá của hệ điều hành hoặc biến môi trường do CLI quản lý, không ghi vào tệp cấu hình chép đi chép lại.

## Chặn công cụ đọc tệp và shell của CLI (mục 5.1 của kế hoạch)

CLI agent có sẵn công cụ đọc tệp, tìm tệp, chạy lệnh, mở web. Nếu để mở, trợ lý có thể đọc thẳng DXF hoặc tệp khác và **bỏ qua lớp ẩn danh** của cad-guard. Khuyến nghị:

1. Mở CLI trong **thư mục làm việc rỗng chỉ chứa tệp của phiên** (bước 2 ở trên). Đây là lớp bảo vệ dựa vào cách dùng, áp dụng được cho mọi CLI.
2. Tắt hoặc từ chối công cụ đọc/ghi tệp, shell và web của CLI, chỉ cho phép 6 công cụ chỉ đọc của `cad-guard` (`list_drawings`, `audit`, `explain_rule`, `get_model_summary`, `query_model`, `diff`):
   - Claude Code: `claude-code/.claude/settings.json` từ chối 19 công cụ dựng sẵn (shell gồm cả `PowerShell` và `Monitor`, đọc/ghi/tìm tệp, web, subagent, công cụ đẩy nội dung ra ngoài), chỉ cho phép `mcp__cad-guard__*`, `mcp__cad-guard-ho-so__*` và `Skill`, chạy ở chế độ `dontAsk`, chặn máy chủ MCP khác bằng `allowedMcpServers`. Xem mục "Claude Code".
   - OpenCode: `opencode/opencode.json` đặt `permission` `"*": "deny"` (chặn mọi công cụ tích hợp: `read`, `glob`, `grep`, `edit`/`write`/`apply_patch`, `bash`, `webfetch`, `websearch`, `task`, `todowrite`, `question`, `external_directory`…), rồi cho phép `cad-guard_*`, `cad-guard-ho-so_*` và 4 skill cad-guard theo tên (`permission.skill`). Agent `cad-guard` là mặc định (`default_agent`). Đã kiểm trên OpenCode 1.19.4 bằng `opencode debug agent <tên>`: với `cad-guard`, `build`, `plan`, `explore`, `general` chỉ còn công cụ `skill`; gọi `read` bị từ chối; skill ngoài danh sách bị từ chối. Chép `knowledge/skills/*` vào `.opencode/skills/` của thư mục làm việc. Khi khởi chạy, nên đặt `OPENCODE_DISABLE_CLAUDE_CODE=1` và `OPENCODE_DISABLE_EXTERNAL_SKILLS=1` để OpenCode không nạp `~/.claude/CLAUDE.md` và skill cá nhân. Cài cad-guard bằng `pip` thì không cần `environment`; chạy từ mã nguồn thì thêm `"environment": {"PYTHONPATH": "<repo>/packages/core"}` vào mục MCP. **Chưa xác nhận** tên công cụ MCP trong phiên có mô hình (dự kiến `cad-guard_<tên>`). Nếu tên khác, `"*": "deny"` sẽ chặn cả công cụ cad-guard, tức hỏng theo hướng an toàn.
   - Codex CLI: dùng `codex/cadguard.config.toml` với `codex -p cadguard`. Đã kiểm trên 0.165.0 bằng `codex debug prompt-input` (liệt kê công cụ mô hình thấy, không gọi mô hình): `features.shell_tool = false` bỏ hẳn công cụ chạy lệnh (Codex không có công cụ đọc tệp riêng, đọc tệp vốn đi qua shell), `features.view_image = false` bỏ công cụ xem ảnh, `web_search = "disabled"` bỏ tìm web. Còn công cụ ghi `apply_patch` (không tắt được), bị `sandbox_mode = "read-only"` + `approval_policy = "never"` chặn. `enabled_tools` giới hạn đúng 6 công cụ chỉ đọc của cad-guard (cơ chế lọc đã kiểm). Chặn đọc `**/*.dxf` bằng hồ sơ quyền của Codex trên Windows cần cài sandbox "elevated" bằng quyền admin, chưa kiểm hết. Với Codex, `AGENTS.md` ở gốc và skill ở `<THU_MUC_LAM_VIEC>/.agents/skills/<tên>/SKILL.md` được nạp cả khi thư mục không phải repo git. Đặt `startup_timeout_sec = 60` vì mặc định 10 giây không đủ cho Python khởi động lạnh trên Windows.
   - Antigravity CLI (`agy` 1.5.0): không có khoá tắt hẳn công cụ có sẵn, chỉ có luật quyền `action(target)` (thứ tự Deny > Ask > Allow). `antigravity/cadguard.settings.json` từ chối `read_file(*)`, `write_file(*)`, `command(*)`, `read_url(*)`, `execute_url(*)`, chỉ cho phép `mcp(cad-guard/*)` và `mcp(cad-guard-ho-so/*)`, đặt `allowNonWorkspaceAccess: false` và bật hộp cát terminal (cần Windows 11 24H2 trở lên). **Phải** có deny `read_file(*)`, vì mặc định `agy` tự cho đọc mọi tệp trong thư mục làm việc. `enabledTools` trong `mcp_config.json` chỉ để lộ 6 công cụ chỉ đọc. Đã kiểm `agy` nạp các luật. **Chưa kiểm** trong phiên có mô hình xem luật có chặn cả công cụ liệt kê/tìm tệp, tìm web, trình duyệt hay không.
     - Hồ sơ công ty: đặt `"disabled": false` cho `cad-guard-ho-so` và `"disabled": true` cho `cad-guard`.
     - Không dùng `agy` bằng tài khoản Google cá nhân khi ứng dụng cad-guard khởi chạy `agy` (cách B). FAQ chính thức nói cách đó không được hỗ trợ với gói cá nhân. Xem `docs/integrations/antigravity.md` mục 5.
3. Claude Code (`mcp__cad-guard__*`) và OpenCode (`cad-guard_*`) cho phép theo ký tự đại diện, nên tự bao mọi công cụ máy chủ đưa ra; Codex (`enabled_tools`) và Antigravity (`enabledTools`) liệt kê tên, công cụ mới phải thêm tay. Danh sách trong hai mẫu này được test giữ khớp với `TOOL_NAMES` của `cadguard/mcp_server.py`.
4. `AGENTS.md` cũng dặn trợ lý chỉ dùng công cụ cad-guard, nhưng đó là **lời dặn**, không phải rào chặn. Đừng chỉ dựa vào nó.

**Mức ép buộc khác nhau theo CLI và chưa được kiểm trên từng CLI.** Trước khi dùng với bản vẽ thật của khách phải thử: yêu cầu trợ lý đọc một tệp ngoài thư mục làm việc (và một DXF trong thư mục bằng công cụ đọc tệp của CLI), xác nhận bị từ chối. Ghi kết quả thử theo từng CLI và phiên bản.

## Bật đề xuất sửa (`--allow-propose`, mặc định TẮT)

Mặc định máy chủ chỉ có 6 công cụ chỉ đọc. Thêm cờ `--allow-propose` vào `args` thì có thêm `propose_changeset`: trợ lý chạy khô thao tác sửa trên bản sao trong bộ nhớ và ghi changeset JSON vào `<THU_MUC_LAM_VIEC>/.cadguard/changesets/`. Công cụ này **không** ghi DXF. Áp dụng changeset chỉ do người làm bằng `cadguard apply` (xem trước, xác nhận, ghi ra tệp mới); không có công cụ áp dụng qua MCP.

Các mẫu trong thư mục này **không** bật cờ. Chỉ bật khi công ty đã chấp nhận cho trợ lý ghi changeset vào thư mục làm việc. Khi bật, phải làm cả hai việc:

1. Thêm `"--allow-propose"` vào cuối `args` của máy chủ dùng trong phiên (`cad-guard` hoặc `cad-guard-ho-so`).
2. Cho phép `propose_changeset` trong CLI:
   - Codex: thêm `"propose_changeset"` vào `enabled_tools` (cả `cadguard.config.toml` và `config.toml` nếu dùng). Không thêm thì Codex lọc mất công cụ.
   - Antigravity: thêm `"propose_changeset"` vào `enabledTools` trong `mcp_config.json`; `mcp(cad-guard/*)` trong `cadguard.settings.json` đã bao công cụ này.
   - Claude Code (`mcp__cad-guard__*`) và OpenCode (`cad-guard_*`): ký tự đại diện đã bao, không cần sửa. Muốn bật cờ mà vẫn chặn công cụ này thì thêm `mcp__cad-guard__propose_changeset` vào `deny` (Claude Code) hoặc `"cad-guard_propose_changeset": "deny"` ngay sau dòng `cad-guard_*` trong `permission`, cả cấp gốc lẫn agent `cad-guard` (OpenCode). Hai cách chặn này chưa thử chạy thật.

Tắt lại: bỏ `--allow-propose` khỏi `args` (bỏ thêm tên trong danh sách cho gọn).

## Claude Code (đã kiểm với 2.1.318)

Chi tiết, nguồn và khuyến nghị cho ba cách dùng (gói làm việc / hạn mức tài khoản / khoá API): `docs/integrations/claude-code.md`.

1. Chép **cả hai** tệp, giữ đường dẫn: `claude-code/.mcp.json` → `<THU_MUC_LAM_VIEC>/.mcp.json`, `claude-code/.claude/settings.json` → `<THU_MUC_LAM_VIEC>/.claude/settings.json`. Thay `<PYTHON>`, `<THU_MUC_LAM_VIEC>` và, nếu dùng hồ sơ, `<HO_SO_CONG_TY>`.
2. Hồ sơ công ty: mặc định bật `cad-guard`, tắt `cad-guard-ho-so`. Muốn dùng hồ sơ thì đổi chỗ hai tên giữa `enabledMcpjsonServers` và `disabledMcpjsonServers` trong `.claude/settings.json`.
3. Cách khác, không chép `.mcp.json`: chạy trong thư mục làm việc (tên máy chủ phải đứng ngay sau `add`, trước `-e`):
   `claude mcp add cad-guard -s project -- "<PYTHON>" -m cadguard mcp --workspace "<THU_MUC_LAM_VIEC>"` (thêm `--profile "<HO_SO_CONG_TY>"` ở cuối nếu cần).
4. Mở `claude` trong thư mục làm việc và **chấp nhận hộp thoại tin cậy thư mục**. Chưa tin cậy thì máy chủ ở trạng thái `Pending approval` và các quy tắc allow của dự án bị bỏ qua, nên công cụ cad-guard bị từ chối.
5. Kiểm: `claude mcp list` phải báo `cad-guard: … ✔ Connected` và không còn máy chủ nào khác. Máy chậm thì đặt `MCP_TIMEOUT=60000` (ms) trước khi chạy `claude`.
6. Trước khi dùng với bản vẽ thật: trong phiên, yêu cầu trợ lý đọc một DXF bằng công cụ tệp, đọc một tệp ngoài thư mục và chạy một lệnh shell. Cả ba phải bị từ chối. Ghi kết quả kèm phiên bản Claude Code.

Giới hạn cần biết: đây là chặn của chương trình theo cấu hình dự án. Người dùng sửa được cấu hình đó, và mod người dùng tự cài có thể vượt deny khi máy không có managed settings. Trên Windows không có sandbox hệ điều hành cho Claude Code. Muốn chặn cứng thì IT công ty đưa cùng nội dung vào managed settings.
