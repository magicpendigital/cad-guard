# Trợ lý AI trong cad-guard

Ngày viết: 04/11/2026. Mã: `packages/core/cadguard/assistant/`. Nguồn điều khoản: `docs/integrations/claude-code.md`, `codex.md`, `antigravity.md`, `opencode.md`.

Trợ lý chỉ **giải thích và đề xuất**. Đúng/sai do luật tất định của cad-guard quyết. Trợ lý không bao giờ áp dụng sửa đổi: nếu bật `--allow-propose`, nó chỉ ghi changeset JSON; người dùng tự chạy `cadguard apply`.

## 1. Ba cách dùng

| Cách | Ai chạy vòng lặp agent | Đăng nhập/khoá | Lệnh |
| --- | --- | --- | --- |
| **A.** Gói làm việc | CLI của người dùng (Claude Code, Codex, OpenCode, agy) tự mở trong thư mục phiên | Người dùng tự đăng nhập CLI | Xem `knowledge/mcp/README.md` |
| **B.** Hạn mức tài khoản qua CLI | cad-guard khởi chạy CLI **nguyên bản** đã cài trên máy, làm tiến trình con | Người dùng **tự** đăng nhập CLI trước; cad-guard không chạm token | `cadguard ask … --engine claude-cli` |
| **C.** API trực tiếp | cad-guard tự gọi API (vòng gọi công cụ tối thiểu, chỉ công cụ cad-guard) | Khoá API **của khách** (biến môi trường hoặc kho khoá hệ điều hành) | `cadguard ask … --engine anthropic` |

Lệnh:

```text
cadguard engines                         # liệt kê engine: đã cài/đăng nhập/có khoá chưa, điều khoản (không in khoá)
cadguard ask "Bản vẽ có lỗi E nào?" --engine claude-cli --workspace D:/Phien/01 [--standard design-hygiene-v0]
         [--profile ho-so.yaml] [--model …] [--allow-propose] [--experimental] [--account business|api-key] [--json]
cadguard chat --engine anthropic --workspace D:/Phien/01      # nhiều lượt; /chi-phi, /thoat
cadguard keys set|delete|status anthropic|openai|openrouter|gemini
```

`ask` in câu trả lời ra stdout, bảng token/chi phí ra stderr; `--json` in câu trả lời, usage, lỗi và mọi sự kiện. Mã thoát: 0 có câu trả lời, 1 lỗi không có câu trả lời, 2 cấu hình sai.

## 2. Bảng engine × điều khoản

| Engine | Cách | Chạy thế nào | Chặn công cụ | Điều khoản (tóm tắt) | Trạng thái |
| --- | --- | --- | --- | --- | --- |
| `claude-cli` | B | `claude -p --input-format stream-json --output-format stream-json --verbose`, lời nhắc qua stdin; `--mcp-config <tạm> --strict-mcp-config`; `--append-system-prompt` = `knowledge/AGENTS.md`; **không** `--bare` | `--tools Skill`, `--allowedTools mcp__cad-guard__*`, `--disallowedTools` 19 công cụ (Bash, PowerShell, Read, Write, Web…), `--permission-mode dontAsk`, `--permission-prompts none`, `--settings <tạm>` (deny, chặn ngoài thư mục, tắt auto memory); kiểm `system/init` có `cad-guard: connected` | **Được phép rõ nhất**: binary không sửa, mỗi người tự đăng nhập bằng gói/khoá của chính họ, tự chịu cước. Không dùng tên "Claude Code" trong tên sản phẩm. `total_cost_usd` là ước tính, với gói thuê bao không phải tiền bị trừ | Test bằng CLI giả; **chưa** chạy với mô hình |
| `codex-cli` | B | `codex exec --json --skip-git-repo-check --ephemeral --ignore-user-config -C <tạm> -s read-only`, cấu hình qua `-c` (không đặt `CODEX_HOME` riêng, để dùng đăng nhập của người dùng); `AGENTS.md` ghi vào thư mục tạm | `approval_policy="never"`, `features.shell_tool=false`, `features.view_image=false`, `web_search="disabled"`, MCP `required=true`, `startup_timeout_sec=60` | **Chưa rõ**: không có văn bản cho/cấm ứng dụng bên thứ ba khởi chạy Codex bằng đăng nhập ChatGPT. Vì vậy **thử nghiệm**, chỉ chạy với `--experimental` | Test bằng CLI giả; chưa chạy với mô hình |
| `agy-cli` | B | `agy -p "<AGENTS.md + câu hỏi>" --output-format stream-json --settings <tạm> --sandbox --print-timeout`; MCP ở `<tạm>/.agents/mcp_config.json`; `AGY_CLI_DISABLE_AUTO_UPDATE=true`; thời hạn phía cad-guard (agy có lúc treo) | Luật quyền deny `read_file(*)`, `write_file(*)`, `command(*)`, `read_url(*)`, `execute_url(*)`; allow `mcp(cad-guard/*)` | **Cấm với tài khoản Google cá nhân** (FAQ Antigravity). Chỉ chạy khi khai `--account business` (quản trị tổ chức đã đồng ý) hoặc `--account api-key`; nếu sự kiện `init` lộ tier cá nhân thì dừng | Test bằng CLI giả; chưa chạy với mô hình; nạp MCP từ `.agents/mcp_config.json` chưa kiểm |
| `anthropic` | C | `POST /v1/messages` (`x-api-key`, `anthropic-version: 2026-10-21`), mô hình mặc định `claude-sonnet-5-5` (đổi bằng `--model` hoặc `CADGUARD_ANTHROPIC_MODEL`) | Chỉ có công cụ cad-guard do cad-guard định nghĩa; gọi thẳng `cadguard.agent.tools` | Khoá của khách, tính cước cho khách (Commercial Terms) | Test bằng máy chủ HTTP giả |
| `openai` | C | Chat Completions có `tools`; cần `--model` hoặc `CADGUARD_OPENAI_MODEL` | như trên | Khoá API của tổ chức khách | Test bằng máy chủ giả |
| `gemini` | C | Endpoint tương thích OpenAI của Google AI | như trên | Google khuyên khoá Gemini Enterprise/AI Studio cho agent bên thứ ba | Test chung lớp OpenAI; endpoint thật chưa thử |
| `openrouter` | C | `openrouter.ai/api/v1`, đọc `usage.cost` | như trên | **Bên trung gian thứ ba**: thêm một chặng chuyển dữ liệu. **Mặc định tắt**; bật bằng `--allow-openrouter` khi khách đồng ý | Test bằng máy chủ giả |
| `ollama` | C | `localhost:11434/v1`, không khoá | như trên | Dữ liệu không rời máy | Test bằng máy chủ giả; chất lượng chưa đo |

Không dùng ACP cho Claude (adapter chạy trên Agent SDK; đăng nhập thuê bao qua đó chưa rõ, xem `claude-code.md` mục 4).

## 3. Dữ liệu đi đâu

- **Bậc 1 mặc định**: mô hình chỉ thấy kết quả công cụ đã ẩn danh (mã phiên `F_…`, `L_…`, `B_…`, `S_…`, `Y_…` thay tên tệp/layer/khối/kiểu chữ/layout). Không gửi DXF thô, không gửi đường dẫn tuyệt đối.
- Engine B: thư mục làm việc của CLI là thư mục **tạm** chỉ chứa tệp cấu hình sinh ra (`mcp.json`, `settings.json`, `AGENTS.md`…), xoá sau mỗi lượt. Máy chủ MCP `python -m cadguard mcp --workspace <thư mục phiên>` (bằng `sys.executable` và `PYTHONPATH` của cad-guard) là đường duy nhất tới bản vẽ. Dữ liệu đi tới nhà cung cấp của CLI theo điều khoản tài khoản người dùng.
- Engine C: yêu cầu đi thẳng tới nhà cung cấp đã chọn (trừ `ollama`: ở lại máy). OpenRouter thêm một bên trung gian, nên tắt mặc định.
- Lịch sử hội thoại do cad-guard giữ trong bộ nhớ của lệnh `chat`; không ghi ra đĩa. Engine B gộp lịch sử thành một lời nhắc cho mỗi lượt (mỗi lượt một tiến trình mới, `--no-session-persistence`/`--ephemeral`).
- Telemetry và báo cáo không chứa nội dung hội thoại.

## 4. Khoá lưu ở đâu

- Engine C đọc khoá theo thứ tự: biến môi trường (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`) rồi **kho khoá hệ điều hành** (Windows Credential Manager, macOS Keychain, Secret Service) qua gói `keyring` nếu đã cài.
- `cadguard keys set <nhà cung cấp>` nhập ẩn (`getpass`) và chỉ ghi vào kho khoá hệ điều hành. **Không bao giờ ghi tệp.** Không có gói `keyring` thì báo cách cài hoặc dùng biến môi trường.
- `keyring` là extras **tuỳ chọn** `[keyring]` (`pip install cadguard[keyring]`), MIT, đã kiểm giấy phép (xem `docs/licenses.md`). Không cài thì dùng biến môi trường.
- Khoá không xuất hiện trong log, lỗi, `--json`, telemetry, báo cáo bench; lỗi HTTP được che chuỗi giống khoá.
- Engine B: cad-guard **không** đọc, sao chép hay chuyển token (`.credentials.json`, `auth.json`, kho khoá của agy) và **không thêm, không bớt** biến xác thực nào của CLI. Tiến trình CLI nhận nguyên `os.environ` của người dùng, cộng vài biến kỹ thuật (`MCP_TIMEOUT=60000` cho Claude Code, `AGY_CLI_DISABLE_AUTO_UPDATE=true` cho agy). Lý do: trang pháp lý của Anthropic cấm sản phẩm "gỡ, tắt hay hạn chế phương thức xác thực" của Claude Code, và `CLAUDE_CODE_OAUTH_TOKEN` là một cách đăng nhập thuê bao hợp lệ.
- Khi môi trường có biến khoá API của nhà cung cấp tương ứng (`ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` cho `claude-cli`, `CODEX_API_KEY`/`OPENAI_API_KEY` cho `codex-cli`, `GEMINI_API_KEY` cho `agy-cli`), cad-guard **cảnh báo** bằng tiếng Việt trong `cadguard engines` và trước khi chạy `ask`/`chat`/bench: CLI sẽ dùng khoá đó (tính cước theo khoá) thay cho hạn mức gói; muốn dùng hạn mức gói thì người dùng tự bỏ biến trong phiên terminal. Không in giá trị. `agy-cli --account api-key` đặt `modelProvider: gemini` trong tệp quyền tạm để agy dùng `GEMINI_API_KEY` sẵn có.
- Máy chủ MCP của cad-guard (tiến trình con của CLI) không cần khoá: chạy qua `python -m cadguard.assistant.mcp_launch` (= `cadguard mcp` sau khi gỡ mọi biến xác thực khỏi môi trường của chính máy chủ); tệp cấu hình MCP tạm chỉ truyền `PYTHONPATH`, `PYTHONUTF8`.
- Chưa đăng nhập: cad-guard hiện hướng dẫn (`claude auth login`, `codex login`, mở `agy`) thay vì tự làm. `cadguard engines` kiểm đăng nhập chỉ bằng **mã thoát** của `claude auth status`/`codex login status` (không in, không lưu nội dung).

## 5. Giới hạn

| Giới hạn | Mặc định | Đổi |
| --- | --- | --- |
| Thời hạn mỗi lượt (engine B) | 600 giây; quá hạn thì giết cả cây tiến trình | `--timeout` |
| Huỷ | `CancelToken`; Ctrl+C trong `ask`/`chat` | — |
| Số vòng gọi công cụ (engine C) | 12 | `--max-tool-rounds` |
| Trần token mỗi phiên (engine C) | 300.000 | tham số `max_session_tokens` |
| Trần chi phí ước tính mỗi phiên (engine C) | 2 USD (chỉ khi biết giá) | `--max-cost-usd` |
| Thời hạn mạng (engine C) | 120 giây | `--timeout` |
| Trần token đầu ra mỗi yêu cầu (engine C) | 16.000 | tham số `max_output_tokens` |

Giá dùng để ước tính (USD / triệu token, bảng Anthropic 10/2026): `claude-sonnet-5-5` 2 / 10 (đọc cache 0,20), `claude-opus-5-5` 4 / 20, `claude-haiku-5-5` 0,10 / 0,50. Mô hình khác: chi phí "không rõ" trừ khi nhà cung cấp trả về (OpenRouter `usage.cost`, Claude Code `total_cost_usd`).

## 6. Giao diện cho nhà phát triển

```python
from cadguard.assistant import create_engine
eng = create_engine("anthropic", model="claude-sonnet-5-5")
for ev in eng.run([{"role": "user", "content": "Có lỗi E nào?"}], workspace="D:/Phien/01",
                  standard="design-hygiene-v0", profile=None, allow_propose=False):
    print(ev.type, ev.data)   # text | tool_call | tool_result | usage | error | done (luôn có done ở cuối)
```

Tham số thêm: `compare_without_profile` (thêm bộ công cụ không áp hồ sơ: máy chủ `cad-guard-goc` hoặc công cụ `audit_khong_ho_so`), `server_options` (`anonymize`, `stream_threshold_mb`, `max_entity_records`, như cờ của `cadguard mcp`), `cancel`.

## 7. Chưa chắc / cần thử có token

1. `claude-cli`: `--tools Skill` có làm công cụ MCP bị hoãn nạp (cần `ToolSearch`) không; deny + `dontAsk` có chặn thật `Read`/`PowerShell` trong phiên thật (bài thử bắt buộc của `claude-code.md` mục 8.A). Thông điệp "chưa đăng nhập" thật của `claude -p` chưa thấy; nhận diện theo mẫu chữ.
2. `codex-cli`: công cụ MCP có bị đòi phê duyệt khi `approval_policy="never"` không; tên trường JSONL `mcp_tool_call` (`tool`, `arguments`, `result`, `error`) theo tài liệu, chưa thấy đầu ra thật. Trên Windows, Codex cài qua npm là `codex.cmd`: đối số `-c` có dấu `"` đi qua `cmd.exe` — đã tránh ký tự `& | < >` nhưng chưa thử thật.
3. `agy-cli`: dạng sự kiện `stream-json` (`init`, `step_update`, `result`) chỉ biết tên, chưa biết trường; nhận diện tier cá nhân là phỏng đoán (`oauth-personal`, `personal`, `free`…). Nạp MCP từ `.agents/mcp_config.json` của thư mục tạm chưa kiểm (có thể cần tin cậy thư mục).
4. Engine C với Gemini: endpoint tương thích OpenAI có nhận `anyOf`/`additionalProperties` trong lược đồ công cụ không.
5. Đã chốt (QC 04/11/2026): cad-guard không thêm/bớt biến xác thực của CLI, chỉ cảnh báo (`claude-code.md` mục 9.6). Còn mở: `--bare` chỉ dùng khi chính người dùng chọn khoá API; engine `claude-cli` hiện không dùng `--bare`.
