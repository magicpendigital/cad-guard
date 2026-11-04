# Tích hợp Antigravity CLI (`agy`) với cad-guard

Ngày kiểm: 04/11/2026. Bản đã cài và thử: `agy` **1.5.0** (Windows x64, `C:\Users\Admin\AppData\Local\agy\bin\agy.exe`; `agy --version` in `1.5.0`).

Quy ước ghi nguồn:

- **[tài liệu]** kèm link: trang chính thức trên antigravity.google.
- **[registry]**: tệp [registry.json của ACP Registry](https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json).
- **[đã kiểm trên máy]** kèm lệnh: chạy trên máy với 1.5.0. **Không lệnh nào gửi lời nhắc cho mô hình.** Không đọc tệp token hay xác thực.
- **[changelog nhúng]**: nhật ký thay đổi nằm sẵn trong `agy.exe`, từ 1.0.0 tới 1.4.12 (chưa có mục 1.5.0). Đây là văn bản của Google nhưng chưa đối chiếu với trang web.

Cách kiểm trên máy:

- Mọi lệnh đều chạy với thư mục người dùng tạm: `USERPROFILE` và `HOME` trỏ vào `scratchpad\cli-agy\home`. Trên Windows, `agy` theo `USERPROFILE` để tìm `~/.gemini`. Cấu hình thật của người dùng không bị đụng.
- Thư mục làm việc tạm chứa 2 DXF tổng hợp (`ok_sheet.dxf`, `bad_layers.dxf`). Máy chủ chạy bằng Python của venv thử, `PYTHONPATH` trỏ vào `<worktree>\packages\core`.
- Lệnh đã chạy:
  - `agy --version`, `agy --help`;
  - `agy mcp --help`, `agy mcp add|list|remove|enable --help`;
  - `agy acp --help`, `agy models|plugin|agents|remote-control|update --help`, `agy help install`;
  - `agy mcp add …`, `agy mcp list`;
  - `agy -p "/permissions"`, `agy -p "/config"`, `agy -p "/skills"`. Đây là các lệnh gạch chéo **do CLI tự trả lời**, không gọi mô hình (theo changelog nhúng 1.1.11 và 1.1.12);
  - `agy acp`: chỉ gửi `initialize` và `session/new`, **không** gửi `session/prompt`.

**Lưu ý khi chạy `agy` từ chương trình khác.** Kết quả **[đã kiểm trên máy]**:

- Trong sandbox của Claude Code, mọi lệnh `agy` (kể cả `--version`) treo, không in gì, kể cả khi cấp terminal giả (ConPTY).
- Ra ngoài sandbox, `--version` chạy ngay. Còn `--help`, `help mcp`, `mcp list --help`… **thỉnh thoảng treo** mà không in gì, không ghi log. Chạy lại thì xong trong vài giây.
- Đặt `AGY_CLI_DISABLE_AUTO_UPDATE=true` (tên biến có trong tệp chạy, tài liệu không nói) kèm thời hạn và chạy lại thì lấy được mọi trang help.
- `agy --help` in ra **stderr**, stdout rỗng (lần chạy tốt: stdout 0 byte, stderr 3.323 byte).
- `-p "/permissions"` và `-p "/config"` in ra **stdout** bình thường khi stdout là tệp, không phải terminal.

Vì vậy hiện tượng "`agy -p` không in gì khi stdout không phải terminal" ghi trong `plans/cad-guard-agent.md` mục 2.1 có thể là một trong hai việc: tiến trình treo lúc khởi động (nghi do bước kiểm cập nhật, **chưa chắc**), hoặc đọc nhầm stdout trong khi help nằm ở stderr. Lượt có gọi mô hình chưa được thử.

---

## 1. Cấu hình MCP

**Tệp và chỗ đặt** ([tài liệu MCP](https://antigravity.google/docs/mcp)):

| Phạm vi | Tệp | Kiểm |
| --- | --- | --- |
| Người dùng (mọi phiên) | `~/.gemini/config/mcp_config.json`. Trên Windows là `%USERPROFILE%\.gemini\config\mcp_config.json` | [tài liệu] + **[đã kiểm trên máy]**: `agy mcp add` ghi vào đúng tệp này; `agy acp` + `session/new` khởi động máy chủ ghi ở đây |
| Thư mục làm việc | `<thư mục làm việc>/.agents/mcp_config.json` | [tài liệu]. **Chưa kiểm được**: `agy mcp list` chỉ liệt kê tệp cấp người dùng (đã thử, máy chủ khai ở `.agents/mcp_config.json` không hiện ra). Có thể cần "tin cậy" thư mục trước (`trustedWorkspaces`) |
| Plugin | `<plugin>/mcp_config.json`. Tên máy chủ tự đổi thành `<plugin>_<máy chủ>` | [tài liệu], [changelog nhúng] 1.2.2 |

Đường dẫn cũ `~/.gemini/antigravity/mcp_config.json` (bản trước khi chuyển sang `config/`) không còn được đọc ([changelog nhúng] 1.0.3).

**Định dạng** ([tài liệu MCP](https://antigravity.google/docs/mcp)). Khoá gốc là `mcpServers`, mỗi khoá con là tên máy chủ.

- Máy chủ stdio: `command`, `args`, `env`, `cwd`.
- Máy chủ từ xa: `serverUrl` (nhận cả `url`), `headers`. Chỉ hỗ trợ Streamable HTTP, không hỗ trợ SSE kiểu cũ.
- Khoá điều khiển:
  - `disabled`: tạm tắt máy chủ;
  - `enabledTools`: danh sách công cụ được dùng, mọi công cụ khác bị ẩn;
  - `disabledTools`: danh sách công cụ bị ẩn;
  - `timeoutSeconds`: mặc định 300 giây để kết nối và 180 giây mỗi lần gọi; số dương thay cả hai mức; `-1` bỏ giới hạn.
- Tệp chấp nhận chú thích `//`, `/* */`, dấu phẩy thừa ([changelog nhúng] 1.1.24) và BOM UTF-8 (1.3.1).

**Lệnh quản lý** **[đã kiểm trên máy]**. Có từ 1.1.16 theo changelog nhúng; trang tài liệu MCP chỉ nói tới `/mcp` trong giao diện.

```text
agy mcp add [--env KEY=value]... [--header "K: V"]... [--type stdio|http] <tên> <lệnh hoặc URL> [args...]
agy mcp list | remove <tên> | enable <tên> | disable <tên>
```

- Cờ phải đứng **trước** `<tên>`. Đối số bắt đầu bằng `-` thì đặt sau `--`.
- Đã thử `agy mcp add --env PYTHONPATH=<…>\packages\core cad-guard <python> -m cadguard mcp --workspace <ws>`. Lệnh in `Added MCP server "cad-guard" (stdio)` và ghi `{"mcpServers":{"cad-guard":{"args":[…],"command":"…","disabled":false,"env":{"PYTHONPATH":"…"}}}}`.
- `agy mcp list` in bảng `NAME TYPE STATUS COMMAND/URL`. Lệnh **không** khởi động máy chủ.

**Máy chủ cad-guard chạy thật trong `agy`** **[đã kiểm trên máy]**:

- Với mẫu `knowledge/mcp/antigravity/mcp_config.json` (đã thay giữ chỗ, bật cả mục `--profile`), `agy mcp list` hiện đủ hai máy chủ.
- Một `session/new` qua `agy acp` làm `agy` khởi động cả hai và lưu đặc tả công cụ vào `~/.gemini/antigravity-cli/mcp/<máy chủ>/*.json`, kèm `instructions.md`.
- Máy chủ hiện trả **6** công cụ: `list_drawings`, `audit`, `explain_rule`, `get_model_summary`, `query_model` và `diff` (`diff` mới có từ commit 7a5d491). Mẫu `enabledTools` liệt kê đủ 6 công cụ chỉ đọc này (test giữ khớp với `TOOL_NAMES` của máy chủ). Khi máy chủ chạy với `--allow-propose`, phải thêm `propose_changeset` vào `enabledTools` thì trợ lý mới thấy; mặc định không bật (xem `knowledge/mcp/README.md`).

**Biến môi trường cho máy chủ.** Đặt trong khoá `env` (hoặc `agy mcp add --env`). Chỉ cần `PYTHONPATH` khi chạy cad-guard từ mã nguồn. Không đặt khoá hay token vào đây.

## 2. Giới hạn để agent chỉ dùng cad-guard

**Cơ chế có sẵn** ([tài liệu quyền](https://antigravity.google/docs/permissions), [tài liệu tham chiếu CLI](https://antigravity.google/docs/cli/reference/)):

- **Luật quyền** dạng `hành_động(đích)`, chia ba danh sách `permissions.allow`, `ask`, `deny` trong `~/.gemini/antigravity-cli/settings.json`.
  - Thứ tự ưu tiên: **Deny > Ask > Allow**.
  - Các hành động: `read_file`, `write_file`, `read_url`, `execute_url`, `command`, `mcp(máy_chủ/công_cụ)`; `*` là "tất cả".
  - Trang tham chiếu ghi: luật deny áp dụng ở mọi chế độ.
- `toolPermission`: mặc định `request-review`; các giá trị khác là `strict`, `proceed-in-sandbox`, `always-proceed` (tức `--dangerously-skip-permissions`). `agentMode`: `""`, `accept-edits`, `auto`, `plan`.
- `allowNonWorkspaceAccess` (mặc định `false`): không cho đọc/ghi ngoài thư mục làm việc.
- `enableTerminalSandbox` / cờ `--sandbox`: lệnh shell của agent chạy trong hộp cát của hệ điều hành. Trên Windows cần Windows 11 24H2 trở lên; bản cũ hơn thì tự tắt ([changelog nhúng] 1.4.1, 1.4.3).
- `enabledTools` trong `mcp_config.json`: chỉ để lộ các công cụ cad-guard đã liệt kê.
- **Không có** khoá tắt hẳn công cụ có sẵn (đọc tệp, shell, web). Trang tham chiếu xác nhận không có nút như vậy; chỉ có luật quyền.

**Cờ `--settings`** **[đã kiểm trên máy]**: `agy --help` ghi "Settings for this session only, never saved: a JSON object of settings.json keys, inline or as a file path".

- Đã thử `agy -p "/permissions" --settings knowledge/mcp/antigravity/cadguard.settings.json`. Lệnh in đủ 2 luật allow `mcp(cad-guard/*)`, `mcp(cad-guard-ho-so/*)` và 5 luật deny `read_file(*)`, `write_file(*)`, `command(*)`, `read_url(*)`, `execute_url(*)`.
- Không có `--settings` thì danh sách rỗng, và tệp settings của người dùng không bị tạo.
- `-p "/config"` xác nhận `agy` đọc được `enableTerminalSandbox true` và `allowNonWorkspaceAccess false`.
- Vậy ta áp được chính sách cho riêng phiên cad-guard mà **không sửa** cài đặt chung của người dùng.

**Mức ép buộc thật.**

- Luật quyền do chính `agy` kiểm, ngay trong tiến trình của nó. Chỉ hộp cát terminal là rào ở mức hệ điều hành.
- Mặc định `agy` tự cho đọc mọi tệp trong thư mục làm việc ([changelog nhúng] 1.1.20). Vì vậy **phải** có `deny read_file(*)`; nếu thiếu, trợ lý đọc thẳng DXF và bỏ qua lớp ẩn danh.
- Ở chế độ không giao diện (`-p`), hành động cần phê duyệt bị **từ chối mềm**: lượt chạy vẫn tiếp tục, có ghi chú ra stderr ([tài liệu headless](https://antigravity.google/docs/cli/headless/)).
- **Chưa kiểm** (cần một lượt có gọi mô hình):
  - `read_file(*)` có chặn cả công cụ liệt kê thư mục và tìm trong tệp (`list_dir`, `grep_search`) hay không;
  - công cụ tìm web và công cụ trình duyệt có nằm dưới `read_url`/`execute_url` hay không;
  - deny `read_file(*)` có làm hỏng việc nạp `AGENTS.md`/skills hay không.

  Trước khi dùng với bản vẽ thật, phải chạy bài thử của `knowledge/mcp/README.md`: yêu cầu trợ lý đọc DXF bằng công cụ của CLI, liệt kê thư mục, mở web.
- Cách mạnh hơn nhưng **chưa kiểm**: tác tử tuỳ biến `.agents/agents/cad-guard.md`, chạy bằng `--agent cad-guard`. Frontmatter của tác tử có `tools` (danh sách công cụ, mặc định rỗng) và `mcpServers` ([tài liệu subagents](https://antigravity.google/docs/subagents/)). Thêm `excludeDefaultComponents: true` thì bỏ công cụ có sẵn ([changelog nhúng] 1.2.1). Đã tạo thử tệp nhưng `agy agents` không in gì (có thể vì cần đăng nhập hoặc tin cậy thư mục), nên chưa xác nhận được.

## 3. Chạy không giao diện (cho cách B và bench)

**Cờ** (**[đã kiểm trên máy]** bằng `agy --help`; khớp [tài liệu headless](https://antigravity.google/docs/cli/headless/)):

- `-p`/`--print`/`--prompt "<yêu cầu>"`;
- `--output-format text|json|stream-json`;
- `--input-format stream-json` (nhiều lượt trong một hội thoại, cần `--output-format stream-json`);
- `--json-schema`, `--print-timeout` (mặc định `0s`, tức không giới hạn);
- `--mode`, `--model`, `--effort`, `--agent`, `--sandbox`, `--settings`, `--add-dir`;
- `--conversation`, `-c`, `--disable-slash-commands`, `--log-file`, `--dangerously-skip-permissions`.

**Đầu ra JSON** ([tài liệu headless](https://antigravity.google/docs/cli/headless/)):

- Các trường `conversation_id`, `status` (`SUCCESS`, `ERROR`, `CANCELED`, `INTERRUPTED`…), `response`, `duration_seconds`, `num_turns`, `usage`, cùng `error`/`structured_output` khi có.
- **`usage`** có `input_tokens`, `output_tokens`, `thinking_tokens`, `cache_read_tokens`, `total_tokens`. Đây là chỗ lấy số token cho bench.
- `stream-json` phát các sự kiện `init`, `step_update` (có `usage`) và `result`.

**Mã thoát.**

- Theo tài liệu: 0 là thành công; 1 là lỗi cách dùng hoặc dữ liệu vào; 2 là sự kiện điều khiển trong phiên stream.
- [changelog nhúng] thêm:
  - 3 khi lượt chạy hỏng do mô hình hoặc agent, kèm dòng `AGY_ERROR: {...}` trên stderr (1.2.10);
  - trường `finished_reason` (1.4.11), mà trang tài liệu chưa ghi.

**Đăng nhập.** Chế độ không giao diện dùng thông tin đăng nhập đã lưu. Nếu chưa đăng nhập, lệnh báo lỗi "authentication required" chứ không treo (tài liệu headless).

**Quota.** `-p "/usage"` in hạn mức (UTC khi stdout không phải terminal) ([changelog nhúng] 1.1.11, 1.2.15). Lệnh này chưa chạy.

## 4. ACP

- **ACP có sẵn trong `agy`, không qua adapter.**
  - **[đã kiểm trên máy]**: `agy acp --help` ghi "Start the Agent Client Protocol (ACP) stdio server".
  - Khi gửi `initialize`, máy chủ trả:
    - `agentInfo` = `{"name":"Antigravity ACP Server","version":"1.5.0"}`, `protocolVersion` 1;
    - khả năng `loadSession`, `sessionCapabilities` (resume, close, load, list, additionalDirectories);
    - `authMethods`: `oauth-personal`, `oauth-business`, `gemini-api-key`, `agent-platform` (tức Vertex AI qua ADC).
  - `session/new` trả mã phiên, danh sách mô hình, chế độ (`default`, `accept-edits`, `plan`) và `_meta.antigravity.tier` (tên gói của tài khoản).
- **Cờ của `agy acp`** **[đã kiểm trên máy]**:
  - `--login`: đăng nhập Google tương tác rồi thoát;
  - `--sandbox`, `--dangerously-skip-permissions`, `--add-dir`, `--agent`;
  - `--app-data-dir`, `--gemini-dir`, `--cli_dir_name`: đổi thư mục dữ liệu và cấu hình;
  - `--disable-telemetry`, `--process-per-session`, `--log-file`.
- **Cách chạy** ([tài liệu ACP](https://antigravity.google/docs/cli/acp/)): trình soạn chạy `agy acp` làm tiến trình con, nói JSON-RPC qua stdin/stdout. Ví dụ cho Zed là `"command": "agy", "args": ["acp"]`. Đăng nhập một lần bằng `agy` tương tác hoặc `agy acp --login`.
- **ACP Registry** [registry]:
  - mục `antigravity-acp`, tên "Google Antigravity", phiên bản 1.4.5;
  - **license "proprietary"**, tác giả "Google LLC";
  - chỉ phát hành dạng tệp chạy riêng (`agy_acp_server.exe` trên Windows), không có gói npm.
- **Truyền máy chủ MCP qua ACP**: đã gửi `session/new` có `mcpServers: [{name: "cad-guard-acp", command, args, env}]`. Log của `agy` ghi "Preloading 1 MCP servers of the session". Như vậy ứng dụng có thể gắn cad-guard cho riêng phiên mà không sửa `mcp_config.json` của người dùng. **Chưa xác nhận** công cụ đã được nạp (không thấy tệp đặc tả lưu lại trong 20 giây chờ).

## 5. Xác thực và điều khoản

**Cách đăng nhập** ([tài liệu cài đặt và đăng nhập](https://antigravity.google/docs/install/)):

| Cách | Ghi chú |
| --- | --- |
| Tài khoản Google cá nhân | Mở trình duyệt khi chạy `agy` |
| Doanh nghiệp | Gemini Enterprise / Google Cloud, có WIF |
| Khoá API | `GEMINI_API_KEY` **kèm** `"modelProvider": "gemini"` trong settings. Chỉ đặt biến thì không có tác dụng |
| ADC (Vertex) | `gcloud auth application-default login` + `AGY_ADC_AUTH=true` |

- Thông tin đăng nhập lưu trong kho khoá của hệ điều hành (Windows Credential Manager).
- **[đã kiểm trên máy]**: dù đổi `USERPROFILE` sang thư mục tạm, `agy acp` vẫn nạp token từ kho khoá (log `keyringAuth: loaded token`) và trả tên gói của tài khoản. Đổi thư mục cấu hình **không** tách được thông tin đăng nhập; cad-guard cũng không cần và không được chạm vào kho khoá này.

**Điều khoản**, đều **đã kiểm trên tài liệu chính thức**:

- [FAQ](https://antigravity.google/docs/faq/), câu hỏi "Why can't I use third-party software (such as Claude Code, OpenClaw, or OpenCode) with my Antigravity login?":
  - làm vậy có thể bị khoá hoặc chấm dứt tài khoản;
  - Google khuyên dùng khoá Gemini Enterprise hoặc Google AI Studio cho agent bên thứ ba.
- FAQ, câu hỏi về headless:
  - "Antigravity CLI headless mode (`agy -p`) is intended for direct scripting and CI workflows";
  - bọc `agy` trong agent hoặc **ứng dụng** bên thứ ba **không được hỗ trợ với gói cá nhân** (consumer plans).
- [Điều khoản Antigravity](https://antigravity.google/terms), mục 6: cấm dùng phần mềm, công cụ, dịch vụ bên thứ ba để truy cập dịch vụ. Vi phạm có thể bị khoá tài khoản Antigravity và/hoặc Gemini CLI.
- Điều khoản, mục 5: với tài khoản cá nhân, Google dùng "Interactions" (dữ liệu người dùng, dữ liệu sử dụng) để cải tiến sản phẩm; nhân sự có thể xem. Tắt được trong cài đặt. Tài khoản doanh nghiệp theo điều khoản của tổ chức.

**Phân loại:**

- **Đã kiểm trên tài liệu chính thức**: các cách đăng nhập; FAQ và điều khoản ở trên.
- **Đã kiểm trên máy**: bốn `authMethods` của ACP; token nằm ở kho khoá hệ điều hành.
- **Chưa chắc**:
  - Cách A (người dùng tự mở `agy`, cad-guard chỉ là máy chủ MCP) **có** được coi là "phần mềm bên thứ ba truy cập dịch vụ" không. Theo cách đọc của chúng tôi thì không: MCP là tính năng chính thức, `agy` không bị bọc. Nhưng chưa có văn bản nói thẳng.
  - Cách B với tài khoản doanh nghiệp hoặc khoá API có được phép không. FAQ chỉ nói "không hỗ trợ với gói cá nhân" và gợi ý khoá Enterprise/AI Studio.

## 6. Giấy phép

- `agy` là **phần mềm độc quyền** của Google: ACP Registry ghi `"license": "proprietary"`, tác giả "Google LLC".
- Không có repo mã nguồn công khai. Trang [điều khoản](https://antigravity.google/terms) là hợp đồng sử dụng dịch vụ, không cấp giấy phép phần mềm riêng, cũng không nói về dịch ngược.
- So sánh: tiền thân Gemini CLI theo Apache-2.0 [registry].
- Hệ quả: cad-guard **không được đóng gói hay phân phối lại** `agy`. Người dùng tự cài từ Google, cad-guard chỉ gọi tệp đã cài.

---

## Khuyến nghị cho cad-guard

**A. Người dùng tự mở `agy` trong thư mục làm việc của phiên (khuyến nghị cho `agy`).**

1. Chép `knowledge/mcp/antigravity/mcp_config.json` (đã thay `<PYTHON>`, `<THU_MUC_LAM_VIEC>`) vào `%USERPROFILE%\.gemini\config\mcp_config.json`. Hoặc dùng lệnh:

   ```text
   agy mcp add cad-guard <PYTHON> -m cadguard mcp --workspace <THU_MUC_LAM_VIEC>
   ```

   Lệnh này không ghi `enabledTools`/`timeoutSeconds`, nên chép tệp thì tốt hơn. Tệp cấp người dùng áp cho **mọi** phiên `agy`: đổi `<THU_MUC_LAM_VIEC>` mỗi phiên, hoặc tắt bằng `agy mcp disable cad-guard` khi không dùng. Tệp cấp thư mục `.agents/mcp_config.json` theo tài liệu là có, nhưng chưa kiểm.
2. Mở `agy` **trong** thư mục làm việc rỗng, kèm chính sách riêng cho phiên:

   ```text
   agy --settings <đường dẫn>\cadguard.settings.json --sandbox
   ```

   Không sửa `settings.json` chung của người dùng.
3. Người dùng tự đăng nhập. Nên dùng tài khoản công ty (Gemini Enterprise / Google Cloud) hoặc khoá API của công ty, vì tài khoản cá nhân bị dùng dữ liệu để cải tiến sản phẩm.
4. Thêm `"--profile", "<HO_SO_CONG_TY>"` thì bật mục `cad-guard-ho-so` (`"disabled": false`) và tắt mục `cad-guard`.

**B. Ứng dụng cad-guard khởi chạy `agy` bằng hạn mức tài khoản của người dùng.**

- **Không** làm với tài khoản Google cá nhân. FAQ chính thức nói bọc `agy` trong ứng dụng bên thứ ba không được hỗ trợ với gói cá nhân, và điều khoản mục 6 có thể dẫn tới khoá tài khoản của **khách**.
- Chỉ bật B khi người dùng đăng nhập bằng:
  - khoá API (`gemini-api-key`);
  - Vertex AI qua ADC (`agent-platform`);
  - tài khoản doanh nghiệp, và quản trị của tổ chức đã đồng ý bằng văn bản.
- Về kỹ thuật, ACP là đường tốt nhất:
  - chạy `agy acp --sandbox` làm tiến trình con;
  - truyền cad-guard qua `mcpServers` của `session/new` (không sửa cấu hình người dùng);
  - đọc `usage`, áp chính sách bằng tệp settings riêng.
  - `_meta.antigravity.tier` trong `session/new` giúp ứng dụng **nhận ra** tài khoản cá nhân để từ chối. Cách nhận dạng (tên gói nào là cá nhân) chưa kiểm.
- Với bench và lượt đơn: dùng `agy -p … --output-format json --settings … --print-timeout …`, luôn đặt thời hạn ở phía cad-guard (do hiện tượng treo đã gặp), đọc stdout và stderr riêng.

**C. API trực tiếp bằng khoá của khách.**

- Đây là đường sạch nhất về điều khoản: Google khuyên dùng khoá Gemini Enterprise / AI Studio cho agent bên thứ ba.
- Nếu vẫn muốn dùng vòng lặp agent của `agy`, cho `agy` chạy bằng khoá của khách: `"modelProvider": "gemini"` trong `--settings`, kèm `GEMINI_API_KEY` trong môi trường của tiến trình con.
- cad-guard không ghi khoá ra tệp. Khoá lấy từ kho khoá hệ điều hành ngay lúc chạy.

## Chưa chắc

- `<thư mục làm việc>/.agents/mcp_config.json` có được nạp không, và có cần "tin cậy" thư mục trước không. `agy mcp list` không hiện máy chủ khai ở đây.
- Luật deny `read_file(*)`, `read_url(*)`, `execute_url(*)` có chặn được **mọi** công cụ đọc, liệt kê, tìm tệp, tìm web và trình duyệt của `agy` hay không. Cần một lượt thử có gọi mô hình.
- Tác tử tuỳ biến (`--agent`, `tools: []`, `excludeDefaultComponents: true`) có thật sự bỏ hết công cụ có sẵn không.
- Máy chủ MCP truyền qua `session/new` của ACP có được nạp công cụ không. Log chỉ ghi "Preloading".
- Nguyên nhân `agy` thỉnh thoảng treo khi khởi động (nghi bước kiểm cập nhật). Và `AGY_CLI_DISABLE_AUTO_UPDATE=true` có tác dụng thật không (biến không có trong tài liệu).
- Hành vi của lượt `-p` **có gọi mô hình** khi stdout không phải terminal: chưa thử.
- `finished_reason` và mã thoát 3 chỉ thấy trong changelog nhúng, trang tài liệu headless chưa ghi.
- Cách A có bị coi là "phần mềm bên thứ ba truy cập dịch vụ" không. Cách B với tài khoản doanh nghiệp có được phép không (mục 5).
- Changelog nhúng chỉ tới 1.4.12. Thay đổi của 1.5.0 chưa đọc được (`agy changelog` chưa chạy).

## Nguồn

- Tài liệu chính thức:
  - [MCP](https://antigravity.google/docs/mcp)
  - [Quyền](https://antigravity.google/docs/permissions)
  - [Tham chiếu CLI](https://antigravity.google/docs/cli/reference/)
  - [Headless](https://antigravity.google/docs/cli/headless/)
  - [ACP](https://antigravity.google/docs/cli/acp/)
  - [Cài đặt và đăng nhập](https://antigravity.google/docs/install/)
  - [Subagents](https://antigravity.google/docs/subagents/)
  - [FAQ](https://antigravity.google/docs/faq/)
  - [Điều khoản](https://antigravity.google/terms)
- ACP Registry: [trang registry](https://agentclientprotocol.com/registry), [registry.json](https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json).
- Trên máy: `agy` 1.5.0 (các lệnh liệt kê ở đầu tệp); changelog nhúng 1.0.0–1.4.12 (trích bằng cách đọc chuỗi trong `agy.exe`).
