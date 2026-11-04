# Cấu hình MCP mẫu cho CLI agent

Thư mục này có mẫu cấu hình để một CLI agent có sẵn gọi máy chủ MCP **chỉ đọc** của cad-guard:

```text
<PYTHON> -m cadguard mcp --workspace <THU_MUC_LAM_VIEC>
```

| CLI | Tệp mẫu | Đặt ở đâu | Độ chắc về định dạng |
| --- | --- | --- | --- |
| Claude Code | `claude-code/.mcp.json` | gốc thư mục làm việc của phiên | Theo tài liệu Claude Code (khoá `mcpServers`); nên kiểm lại theo phiên bản đang dùng |
| Claude Code (quyền) | `claude-code/settings.json` | `.claude/settings.json` trong thư mục làm việc | Khoá `permissions.allow/deny`, `enabledMcpjsonServers`; tên công cụ MCP dạng `mcp__cad-guard__<tên>`. Nên kiểm lại |
| Codex CLI | `codex/config.toml` | gộp vào `~/.codex/config.toml` | Mục `[mcp_servers.<tên>]` với `command`, `args`. Chỗ đặt tệp cấu hình theo dự án (nếu có) **cần kiểm lại với tài liệu chính thức** |
| OpenCode | `opencode/opencode.json` | gốc thư mục làm việc | Khoá `mcp` (`type: local`, `command` là mảng) và `permission`. Tên quyền **cần kiểm lại với tài liệu chính thức** |
| Antigravity CLI (`agy`) | `antigravity/mcp_config.json` | **chưa rõ** | **Chưa chắc.** Mẫu dùng dạng `mcpServers` (`command`, `args`) mà Gemini CLI, tiền thân của Antigravity CLI, dùng trong `settings.json`. Tên tệp, chỗ đặt và khoá chặn công cụ của Antigravity CLI **cần kiểm lại với tài liệu chính thức** trước khi dùng |

Chưa mẫu nào được thử chạy thật với từng CLI. Đây là việc của bước A0/A1 trong `plans/cad-guard-agent.md`.

## Cách dùng

1. Cài cad-guard kèm SDK MCP vào một Python trên máy: `pip install cadguard[agent]` (hoặc trong repo: `pip install -e packages/core[agent]`). Kiểm: `<PYTHON> -m cadguard mcp --help`.
2. Tạo **thư mục làm việc rỗng** cho phiên (ví dụ `D:/CadGuardPhien/phien-01`). Chỉ chép vào đó các DXF cần xem trong phiên này. Không mở CLI ở thư mục chứa toàn bộ bản vẽ của công ty.
3. Chép tệp mẫu của CLI vào chỗ ghi ở bảng trên. Thay giữ chỗ:
   - `<PYTHON>`: đường dẫn đầy đủ tới `python` đã cài cad-guard (ví dụ `C:/Python313/python.exe`);
   - `<THU_MUC_LAM_VIEC>`: đường dẫn đầy đủ tới thư mục làm việc của phiên.
   - Trên Windows, trong JSON viết `/` hoặc `\\` (hai dấu gạch ngược).
4. Chép `knowledge/AGENTS.md` vào gốc thư mục làm việc (CLI đọc `AGENTS.md`; Claude Code đọc `CLAUDE.md`, có thể tạo `CLAUDE.md` chỉ chứa dòng `@AGENTS.md`). Chép `knowledge/skills/` vào chỗ CLI đọc skill (ví dụ `.claude/skills/` cho Claude Code); chỗ đọc skill của các CLI khác cần kiểm lại.
5. Mở CLI **trong thư mục làm việc đó**, tự đăng nhập bằng tài khoản hoặc khoá API của chính bạn/công ty.

Máy chủ mặc định ẩn danh Bậc 1. Chỉ thêm `--no-anonymize` vào `args` khi khách đã đồng ý bằng văn bản.

Hồ sơ công ty (tuỳ chọn): thêm `"--profile", "<HO_SO_CONG_TY>"` vào cuối `args` (đường dẫn đầy đủ tới tệp YAML `cg.company-profile/1`); không có `--standard` thì chuẩn mặc định là chuẩn ghi trong hồ sơ, và `audit`/`explain_rule` trả `profile: {name, version}` của hồ sơ đã áp. Mẫu Codex có dòng ví dụ để bỏ dấu `#`; mẫu OpenCode có mục `cad-guard-ho-so` đang tắt (`enabled: false`).

## Đăng nhập và khoá

- cad-guard **không đọc, không lưu, không chuyển** thông tin đăng nhập hay khoá của CLI. CLI tự đăng nhập theo cách của nó.
- Các tệp mẫu không chứa khoá hay token, và **không được** thêm vào. Khoá API (nếu dùng) để trong kho khoá của hệ điều hành hoặc biến môi trường do CLI quản lý, không ghi vào tệp cấu hình chép đi chép lại.

## Chặn công cụ đọc tệp và shell của CLI (mục 5.1 của kế hoạch)

CLI agent có sẵn công cụ đọc tệp, tìm tệp, chạy lệnh, mở web. Nếu để mở, trợ lý có thể đọc thẳng DXF hoặc tệp khác và **bỏ qua lớp ẩn danh** của cad-guard. Khuyến nghị:

1. Mở CLI trong **thư mục làm việc rỗng chỉ chứa tệp của phiên** (bước 2 ở trên). Đây là lớp bảo vệ dựa vào cách dùng, áp dụng được cho mọi CLI.
2. Tắt hoặc từ chối công cụ đọc/ghi tệp, shell và web của CLI, chỉ cho phép 5 công cụ của `cad-guard`:
   - Claude Code: `claude-code/settings.json` từ chối `Bash`, `Read`, `Edit`, `Write`, `Glob`, `Grep`, `WebFetch`, `WebSearch` và cho phép `mcp__cad-guard__*`.
   - OpenCode: `opencode/opencode.json` đặt `permission` của `edit`, `bash`, `webfetch` là `deny`. OpenCode có thể còn công cụ đọc/liệt kê tệp không nằm dưới các quyền này; **cần kiểm lại với tài liệu chính thức** cách tắt chúng.
   - Codex CLI: có chế độ sandbox và chính sách phê duyệt, nhưng theo hiểu biết hiện tại chế độ chỉ đọc **vẫn cho đọc tệp**. Cách tắt hẳn công cụ đọc tệp/shell **cần kiểm lại với tài liệu chính thức**; tới lúc đó dựa vào thư mục làm việc rỗng.
   - Antigravity CLI: **chưa biết** cơ chế chặn công cụ; cần kiểm lại với tài liệu chính thức.
3. `AGENTS.md` cũng dặn trợ lý chỉ dùng công cụ cad-guard, nhưng đó là **lời dặn**, không phải rào chặn. Đừng chỉ dựa vào nó.

**Mức ép buộc khác nhau theo CLI và chưa được kiểm trên từng CLI.** Trước khi dùng với bản vẽ thật của khách phải thử: yêu cầu trợ lý đọc một tệp ngoài thư mục làm việc (và một DXF trong thư mục bằng công cụ đọc tệp của CLI), xác nhận bị từ chối. Ghi kết quả thử theo từng CLI và phiên bản.
