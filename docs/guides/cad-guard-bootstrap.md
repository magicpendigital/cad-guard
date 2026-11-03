# Hướng dẫn: tạo dự án cad-guard, đăng ký vào MCA và nối `report_signal`

> **Ghi chú khi dùng bản này trong repo:** mục 2 (Tạo repo) đã được gói khung làm sẵn: thư mục, `AGENTS.md`, `.gitignore`, `scripts/metrics.mjs`, lõi `packages/core` đã có. Bạn chỉ cần commit đầu tiên và push lên GitHub (làm từng bước theo `docs/guides/github-tu-dau.md`), rồi sang mục 3 (đăng ký vào MCA). `scripts/metrics.mjs` trong repo là bản đã nối `stats` thật (dùng `.venv` của lõi nếu có), thay cho bản mẫu ở mục 6b. Đường dẫn `guides/…` và `plans/…` trong văn bản là đường dẫn trong Project trên claude.ai; trong repo chúng nằm ở `docs/guides/` và `plans/`.


Cập nhật: 02/11/2026. Dành cho CEO (không cần rành kỹ thuật) và người kỹ thuật đi cùng. Mọi lệnh kiểm tra theo code MCA ở `main` `f53ab78` và hướng dẫn `docs/huong-dan/10`, `13`.
Đọc trước: `plans/cad-guard.md` (kế hoạch), `plans/cad-guard-standard-v0.md` (chuẩn + luật).

## Tóm tắt luồng

```text
1. Máy sẵn sàng      mca chạy, org có phòng dev (+ quality), Python, git
2. Tạo repo          D:\Projects\cad-guard, commit đầu tiên sạch, repo riêng tư trên GitHub
3. Đăng ký MCA       mca venture init …  → trả lời câu hỏi → mca venture apply
4. Bật daemon        mca daemon  → thu tín hiệu mỗi ngày, họp theo nhịp
5. Nối tín hiệu      (a) agent báo report_signal  (b) script mca đọc số tổng hợp  (c) thả file ghi chú/cảnh báo
6. Giao việc đầu     mca ceo "…"  hoặc  submit_goal từ Claude Code
7. Hằng tuần         đọc biên bản họp, duyệt kế hoạch, điều chỉnh chuẩn theo số liệu
```

## 1. Chuẩn bị máy

Máy phát triển (Windows, nơi chạy mca và daemon):

- `mca --version` chạy được; `mca doctor` không báo thiếu thứ bắt buộc.
- `mca org check` không có lỗi. Phòng **dev** có trưởng phòng và nhân viên (có sẵn trong sơ đồ mẫu).
- Python 3.12 (`python --version`), git, Node (đã có vì chạy mca). Chỉ khi làm plugin AutoCAD mới cần .NET SDK và Visual Studio; chưa cần ở P1a.
- Máy có AutoCAD (đầy đủ) để thử plugin ở P1b. Không bắt buộc cho P1a.

Phòng ban dùng cho cuộc họp vận hành phải **đang bật và có trưởng phòng**, nếu không `mca venture check` báo lỗi. Sơ đồ mẫu để phòng `quality` ở `enabled: false`. Bật nó bằng màn **Nhân viên** trên web, hoặc `mca org build --dept quality "bật phòng chất lượng"`, rồi `mca org check`. Phòng `research` mới có trong kế hoạch (roadmap mục 4); chưa có thì bỏ qua, dùng `dev` + `quality`.

## 2. Tạo repo cad-guard

PowerShell:

```powershell
mkdir D:\Projects\cad-guard
cd D:\Projects\cad-guard
git init -b main
mkdir packages\core, standards, fixtures\synthetic, docs, scripts
```

Khung thư mục đề xuất:

```text
cad-guard/
  AGENTS.md  CLAUDE.md  README.md  .gitignore
  packages/core/            lõi Python (cadguard/, tests/, pyproject.toml)
  packages/autocad-plugin/  plugin C# (tạo ở P1b)
  standards/                furniture-v0.yaml  furniture-v0.md  (chuẩn trình bày có phiên bản)
  fixtures/synthetic/       DXF tổng hợp/ẩn danh dùng cho test (KHÔNG bản vẽ khách thật)
  docs/                     discovery.md  licenses.md  accuracy-p1.md
  scripts/metrics.mjs       đưa số tổng hợp cho MCA (mục 6)
  .mca/signals/             thư mục thả file cho MCA (mca tự tạo khi đăng ký)
```

`.gitignore` tối thiểu (bản vẽ khách và bí mật không bao giờ vào repo):

```text
*.dwg
*.dxf
!fixtures/synthetic/*.dxf
.venv/
__pycache__/
*.bak
telemetry.db
.env
```

`AGENTS.md` (agent Claude/Codex/… đọc đầu tiên). Các quy tắc cứng tối thiểu:

```markdown
# AGENTS.md — cad-guard
Mục tiêu: kiểm tra và chuẩn hoá bản vẽ nội thất (AutoCAD). Đọc plans/cad-guard.md và standards/furniture-v0.md trước khi sửa.

## Lệnh
- Cài: `cd packages/core && python -m venv .venv && .venv\Scripts\pip install -e .[dev]`
- Test: `cd packages/core && .venv\Scripts\pytest -q`
- Audit thử: `python -m cadguard audit fixtures/synthetic --standard furniture-v0`

## Quy tắc không được vi phạm
- Phát hiện lỗi bằng code tất định. LLM chỉ giải thích/đề xuất, không ra quyết định đúng sai.
- Test chỉ dùng DXF tổng hợp tạo bằng ezdxf. Không đọc, không sao chép bản vẽ thật của khách vào repo hay vào prompt.
- Mọi luật có id ổn định, nguồn, mức độ; sửa luật = tạo phiên bản chuẩn mới, không sửa đè.
- Không sửa bản vẽ nếu thiếu bước xem trước + xác nhận + hoàn tác.
- Không ghi khoá API/token ra file. Số liệu xuất ra ngoài chỉ là số tổng hợp.
- Không `git push`. Thông báo cho người dùng bằng tiếng Việt; tên hàm/biến bằng tiếng Anh.
```

Commit đầu tiên (mca ghi code theo nhánh `mca/*` từ commit hiện tại nên repo phải **commit sạch**):

```powershell
git add -A
git commit -m "chore: khung dự án cad-guard"
```

Tạo repo **riêng tư** trên GitHub và đẩy lên là việc của bạn (agent của mca không bao giờ `git push`): `git remote add origin <url>` rồi `git push -u origin main`.

## 3. Đăng ký vào MCA

Có hai cách dùng được ngay; cách thứ ba (tool MCP `declare_project`) là kế hoạch Phase J (`plans/mcp-declare.md`).

### Cách A — Qua trò chuyện (khuyên dùng)

```powershell
mca venture init D:\Projects\cad-guard "cad-guard: trợ lý kiểm tra và chuẩn hoá bản vẽ AutoCAD cho doanh nghiệp sản xuất nội thất (tủ bếp, tủ áo, văn phòng). Khách hàng: phòng kỹ thuật và thiết kế sản xuất của nhà máy nội thất. Giai đoạn: building, đang khảo sát và làm lõi kiểm tra tất định. Đo tiến độ bằng số luật đã làm xong có test; khi thử với khách thì đo bằng số lỗi được xác nhận đúng mỗi tuần, tỉ lệ cảnh báo sai, tỉ lệ thợ vẽ chấp nhận gợi ý. Phòng tham gia: dev và quality. Số liệu lấy từ lệnh python -m cadguard stats --json và thư mục .mca/signals. Ngân sách khoảng 2 triệu token mỗi tuần. Lúc đầu muốn tự chủ ở mức propose (kế hoạch họp chờ tôi duyệt)."
```

Trợ lý đọc README/cấu trúc repo, hỏi tối đa 5 câu một lượt. Trả lời bằng:

```powershell
mca venture reply <mã phiên> "<trả lời>"
mca venture draft <mã phiên>          # xem bản nháp hồ sơ dự án
mca venture apply <mã phiên>          # khi hài lòng
```

`apply` ghi hồ sơ dự án vào `~/.mca/projects/cad-guard/project.yaml`, đăng ký dự án, tạo thư mục `.mca/signals/` và script mẫu `scripts/metrics.mjs` nếu chưa có (mở ra và thay số giả bằng bản ở mục 6). Cũng làm được trên web: **Startup → Thêm dự án**.

### Cách B — Viết điều lệ tay

Tạo file `D:\Projects\cad-guard\.mca\charter.yaml` (file này không bị commit vì mca đưa `.mca/` vào danh sách loại trừ của git), nội dung đề xuất:

```yaml
version: 1
id: cad-guard
name: cad-guard
mission: Kiểm tra và chuẩn hoá bản vẽ AutoCAD của nhà máy nội thất để lỗi bị bắt sớm, trước khi xuống xưởng.
customer: Phòng kỹ thuật và thiết kế sản xuất của doanh nghiệp sản xuất nội thất (tủ bếp, tủ áo, văn phòng).
stage: building

# Giai đoạn làm lõi: đo bằng số luật đã làm xong có test. Sang giai đoạn thử với khách (sau P1c),
# CEO đổi north_star sang confirmed_defects_7d và đặt lại target/by.
north_star: { metric: rules_implemented, target: 30, by: 2027-01-31 }

metrics:
  - { id: rules_implemented, label: Số luật đã làm xong có test, unit: count, direction: up }
  - { id: confirmed_defects_7d, label: Lỗi bản vẽ được xác nhận đúng (7 ngày), unit: count, direction: up }
  - { id: rule_precision_pct, label: Độ chính xác cảnh báo, unit: pct, direction: up }
  - { id: false_positive_pct, label: Tỉ lệ cảnh báo sai, unit: pct, direction: down }
  - { id: suggestion_accept_pct, label: Tỉ lệ thợ vẽ chấp nhận gợi ý, unit: pct, direction: up }
  - { id: rework_incidents_7d, label: Lần làm lại ở xưởng do bản vẽ (7 ngày), unit: count, direction: down }
  - { id: active_drafters_7d, label: Thợ vẽ dùng trong 7 ngày, unit: count, direction: up }
  - { id: drawings_audited_7d, label: Bản vẽ đã quét (7 ngày), unit: count, direction: up }

sources:
  # In JSON { "<metric>": <số> } ra stdout; xem scripts/metrics.mjs ở mục 6
  - { id: cadguard-stats, type: cmd, run: node scripts/metrics.mjs }
  # Thả vào đây *.json / *.csv (metric,value,observed_at) hoặc *.md (ghi chú; bắt đầu bằng "Alert:" để báo động)
  - { id: field-notes, type: file, path: .mca/signals }

departments: [dev, quality]

cadence: { review: weekly, day: mon, at: "09:00" }

triggers:
  - { metric: false_positive_pct, change_pct: 30, within: 7d }
  - { kind: alert }

budget: { tokens_per_week: 2000000, max_items_per_review: 4 }

# Hai tuần đầu để propose: kế hoạch họp chờ bạn duyệt (mca approve). Quen rồi mới đổi sang execute.
autonomy: propose

guardrails_md: |
  - Không đưa bản vẽ thật của khách (.dwg/.dxf) vào repo, vào brief của agent hay vào prompt.
  - Không sửa luật của chuẩn trình bày mà không tạo phiên bản chuẩn mới kèm lý do và số liệu.
  - Không bật cảnh báo thời gian thực cho luật chưa đo độ chính xác.
  - Không gửi dữ liệu theo từng thợ vẽ lên quản lý; chỉ số tổng hợp.
```

Rồi:

```powershell
mca venture check --repo D:\Projects\cad-guard     # kiểm điều lệ
mca venture add --repo D:\Projects\cad-guard       # đăng ký
mca venture migrate cad-guard                      # chuyển hồ sơ ra ~/.mca/projects/cad-guard/project.yaml
```

Lỗi hay gặp ở `check`: phòng ghi trong `departments` chưa bật hoặc chưa có trưởng phòng (bật ở mục 1); metric ở `north_star`/`triggers` không có trong `metrics`; `autonomy: execute` với hơn hai phòng sẽ có cảnh báo.

## 4. Bật vòng vận hành

```powershell
mca venture check cad-guard         # không còn lỗi
mca daemon                          # hoặc: mca daemon install (chạy nền)
mca venture review cad-guard        # họp ngay lần đầu, không chờ thứ Hai
mca venture status cad-guard        # chỉ số vs mục tiêu, token tuần, lần họp kế
```

Trên web: **Startup → cad-guard** (chỉ số 30 ngày, biên bản họp, giả thuyết, nút **Họp ngay**, **Thu tín hiệu**, **Thêm ghi chú / số**). Mỗi dự án chỉ có **một máy chạy daemon** (chủ của dự án); máy khác chỉ xem.

## 5. Cho agent trong repo gọi MCA

Agent (Claude Code, Codex) làm việc trong `D:\Projects\cad-guard` cần MCP của mca (xem `docs/huong-dan/10`):

```powershell
claude mcp add --scope user mca -- mca mcp         # Windows nếu /mcp báo lỗi: claude mcp add --scope user mca -- cmd /c mca mcp
codex mcp add mca -- mca mcp
```

Hoặc cài plugin `mca-tools` (có sẵn các skill hướng dẫn agent).
Gọi từ **app Claude desktop / Cowork** thì mca chạy ở thư mục hệ thống: bắt buộc nói rõ repo (`repo = D:\Projects\cad-guard`) hoặc agent truyền tham số `repo`. Không truyền, mca từ chối kèm danh sách dự án đã đăng ký.

## 6. Nối `report_signal` — ba đường, dùng đúng việc

| Đường | Ai gửi | Dùng cho | Cách |
| --- | --- | --- | --- |
| **(a) `report_signal` (MCP)** | Agent đang làm trong repo | Sự kiện/số đo trong lúc **phát triển**: phát hành bản, số luật xong, cảnh báo build | Agent gọi công cụ |
| **(b) Nguồn `cmd`** | Daemon tự chạy mỗi ngày | Số **tổng hợp** của chính sản phẩm (telemetry cục bộ) | `scripts/metrics.mjs` in JSON |
| **(c) Thả file** | Người/phần mềm tại khách | Số xuất từ máy khách, ghi chú của xưởng, cảnh báo | Thả `*.json|*.csv|*.md` vào `.mca/signals/` |

Phần mềm cad-guard chạy ở máy khách **không gọi MCP**: nó không phải agent và không nên mang quyền gọi mca. Nó chỉ xuất số tổng hợp ra file hoặc qua lệnh `stats`; MCA đọc.

### 6a. `report_signal` từ agent

Công cụ nhận: `kind` (`metric|event|alert|note`), `metric` + `value` (cho `metric`), `text` (cho `event/alert/note`), `unit` (tuỳ chọn), `repo` (bắt buộc khi gọi từ app desktop/Cowork).

Ví dụ nhờ agent (trong Claude Code ở repo cad-guard):

> Báo mca: đã làm xong 12 luật có test (metric rules_implemented = 12).
> Báo mca sự kiện: phát hành bản 0.1.0 của lõi kiểm tra.
> Báo mca cảnh báo: bộ test luật TX-09 trượt trên DXF mẫu mới, cần xem.

Agent gọi tương ứng:

```json
{ "kind": "metric", "metric": "rules_implemented", "value": 12 }
{ "kind": "event",  "text": "Phát hành lõi 0.1.0: audit chạy được trên DXF tổng hợp" }
{ "kind": "alert",  "text": "Test luật TX-09 trượt trên fixtures/synthetic/dim_bad.dxf" }
```

Quy tắc của mca (theo code):

- Repo phải thuộc dự án đã đăng ký; không thì từ chối và nói cách đăng ký.
- `metric` phải nằm trong điều lệ; sai tên thì mca liệt kê tên đúng.
- Tối đa **20 tín hiệu mỗi ngày cho mỗi app gọi** (mỗi dự án); cùng chỉ số trong cùng một phút, hoặc cùng nội dung trong cùng ngày, chỉ ghi một lần.
- Nguồn ghi là `mcp:<tên app>` (ví dụ `mcp:claude-code`).
- **`alert` không tự mở họp**: chỉ khi điều lệ có `triggers: [{ kind: alert }]` (đã có ở mẫu trên), và mỗi trigger tối đa một họp / 24 giờ.
- Agent do mca khởi chạy ở độ sâu ≥ 2 không ghi được tín hiệu (chống vòng lặp).

### 6b. Script số tổng hợp: `scripts/metrics.mjs`

Daemon chạy `node scripts/metrics.mjs` trong repo mỗi ngày (giới hạn 2 phút, chạy bằng shell, kế thừa môi trường của daemon — **không để token trong script**). Mẫu:

```js
// scripts/metrics.mjs — in { "<metric>": <số> } cho MCA. Chỉ số tổng hợp, không có tên khách hay đường dẫn.
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const core = path.join(root, 'packages', 'core');
const python = process.env.CADGUARD_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');

try {
  const out = execFileSync(python, ['-m', 'cadguard', 'stats', '--json'], { cwd: core, encoding: 'utf8', timeout: 60_000 });
  const stats = JSON.parse(out); // ví dụ: { rules_implemented: 12, drawings_audited_7d: 0, ... }
  process.stdout.write(JSON.stringify(stats));
} catch (err) {
  // Chưa có lõi hoặc chưa cài: báo 0 thay vì làm hỏng lần thu (nguồn lỗi 3 ngày liên tiếp mới thành cảnh báo).
  process.stdout.write(JSON.stringify({ rules_implemented: 0 }));
}
```

Hợp đồng đầu ra của `python -m cadguard stats --json` (viết ở P1a): một object phẳng `{ "<metric id>": <số> }`. Metric lạ (không có trong điều lệ) bị bỏ qua và được báo trong kết quả thu. Quy ước tính:

| Chỉ số | Tính thế nào | Nguồn dữ liệu |
| --- | --- | --- |
| `rules_implemented` | số luật trong `standards/*.yaml` có `implemented: true` và test xanh | repo |
| `drawings_audited_7d` | số lần `audit` chạy trên bản vẽ khác nhau (băm) trong 7 ngày | telemetry cục bộ |
| `confirmed_defects_7d` | số phát hiện có `state ∈ {accepted, fixed}` trong 7 ngày | telemetry |
| `false_positive_pct` | `false_positive / (accepted + fixed + false_positive) × 100` (đã phân loại) | telemetry |
| `rule_precision_pct` | `100 − false_positive_pct` | telemetry |
| `suggestion_accept_pct` | gợi ý được chấp nhận / tổng gợi ý hiển thị × 100 | telemetry |
| `rework_incidents_7d` | số lần xưởng báo làm lại do bản vẽ (nhập tay hoặc file) | file thả vào |
| `active_drafters_7d` | số thợ vẽ (mã băm) có ≥ 1 lần dùng | telemetry |

Lưu ý: trên **máy phát triển**, telemetry chỉ là số thử nghiệm; số thật của khách đến qua đường (c).

### 6c. Thả file (số từ máy khách, ghi chú xưởng, cảnh báo)

Daemon đọc thư mục `.mca/signals/` mỗi ngày rồi đổi tên file đã đọc thành `*.done`.

- **Số xuất từ máy khách** (tuần một lần, tên tuỳ ý, ví dụ `stats-2026-11-09.json`):

  ```json
  [
    { "metric": "confirmed_defects_7d", "value": 18, "observed_at": "2026-11-09" },
    { "metric": "false_positive_pct",   "value": 9.5, "observed_at": "2026-11-09" },
    { "metric": "active_drafters_7d",   "value": 4,   "observed_at": "2026-11-09" }
  ]
  ```

  hoặc CSV có dòng tiêu đề: `metric,value,observed_at`. Dạng object phẳng `{ "metric": số }` cũng được (lấy thời điểm lúc thu làm ngày quan sát).
- **Ghi chú của xưởng/lắp đặt**: file `.md`, ví dụ `loi-xuong-2026-11-09.md` với nội dung "Tủ bếp lô K12 lệch khoảng cách chén bản lề 3 mm so với bản vẽ — mã bản vẽ hash a1b2…". Bắt đầu bằng `Alert:` nếu cần họp gấp.
- **Số làm lại**: `rework_incidents_7d` do xưởng báo, nhập bằng file hoặc lệnh tay.

Ghi tay nhanh:

```powershell
mca signal add cad-guard --metric rework_incidents_7d --value 2
mca signal add cad-guard "Xưởng báo thiếu mã dán cạnh ở 3 bản vẽ lô K12"
mca signal add cad-guard "Phần mềm CNC từ chối DXF: tên layer sai" --alert
mca signals cad-guard --since 7d
```

**Quyền riêng tư**: chỉ chuyển số tổng hợp và ghi chú đã ẩn danh. Không gửi tên bản vẽ, tên khách hay đường dẫn. Nếu cần liên kết một lỗi với bản vẽ cụ thể, dùng mã băm.

## 7. Kiểm chứng đã nối đúng

| Bước | Lệnh / thao tác | Kết quả mong đợi |
| --- | --- | --- |
| 1 | `mca venture check cad-guard` | Không có lỗi (có thể có cảnh báo) |
| 2 | `mca signal add cad-guard --metric rules_implemented --value 1` rồi `mca signals cad-guard --since 1d` | Hiện dòng `rules_implemented 1 count · manual` |
| 3 | Trong Claude Code ở repo: "Báo mca: rules_implemented = 2" | Trả lời `inserted: true`, nguồn `mcp:claude-code` |
| 4 | Thả `.mca/signals/test.json` = `[{"metric":"drawings_audited_7d","value":3}]`, rồi web **Startup → Thu tín hiệu** | Có tín hiệu; file đổi thành `test.json.done` |
| 5 | Sửa `metrics.mjs` in `{"rules_implemented":5}`, bấm **Thu tín hiệu** | `mca signals` có dòng nguồn `cadguard-stats` |
| 6 | `mca venture review cad-guard` | Có biên bản trong `~/.mca/ventures/cad-guard/reviews/`; kế hoạch chờ duyệt vì `autonomy: propose` |

Thông báo lỗi thường gặp:

| Thông báo | Nguyên nhân | Cách xử |
| --- | --- | --- |
| "Repo … chưa phải dự án (venture) đã đăng ký" | Chưa `apply`/`add`, hoặc gọi từ thư mục khác repo | Đăng ký (mục 3); app desktop thì truyền `repo` |
| "Metric … không có trong điều lệ" | Tên chỉ số sai | Dùng đúng id trong `metrics`; hoặc thêm vào điều lệ |
| "tối đa 20 mỗi ngày" | Quá hạn mức báo | Gộp lại, ghi tiếp ngày mai |
| "Chỉ số đã ghi trong phút này" | Báo lặp cùng chỉ số trong một phút | Bình thường, không lỗi |
| Không họp khi có alert | Điều lệ thiếu `triggers: [{ kind: alert }]` | Thêm trigger |
| Nguồn `cmd` báo lỗi nhiều ngày | `python` không có trong PATH của daemon | Đặt `CADGUARD_PYTHON`, hoặc sửa script |

## 8. Việc đầu tiên giao cho MCA

Giao qua `mca ceo "<mục tiêu>"` hoặc từ Claude Code bằng `submit_goal`. Mẫu mục tiêu (mỗi cái có tiêu chí đo được, nhớ chạy sau khi repo đã commit sạch):

| # | Mục tiêu | Tiêu chí | Lệnh kiểm |
| --- | --- | --- | --- |
| 1 | Dựng khung `packages/core` (pyproject, `cadguard` CLI rỗng, `stats --json` trả `{ "rules_implemented": 0 }`) | CLI chạy được; có test | `cd packages/core && pytest -q` |
| 2 | Định nghĩa schema Drawing Model `cg.drawing/1` (pydantic) + bộ sinh DXF tổng hợp bằng ezdxf | Sinh 5 DXF mẫu đúng/sai; đọc lại thành Drawing Model | `pytest -q` |
| 3 | Cài 10 luật tất định đầu (SH-04, SH-05, LY-01, LY-03, LY-04, LY-08, DH-01, DH-02, DH-09, PR-02) kèm test đúng/sai | Mỗi luật có ≥ 2 test; luật không ném lỗi khi thiếu dữ liệu | `pytest -q` |
| 4 | Báo cáo `report.json` + `report.html` tiếng Việt từ kết quả luật | HTML mở được, hiện mã luật, mức, vị trí | `python -m cadguard audit fixtures/synthetic --out report.html` |
| 5 | `scripts/metrics.mjs` nối `stats` thật | Thu tín hiệu ngày chạy xanh | Thu tín hiệu ngay trên web |

Trong lúc agent làm: **không** đưa bản vẽ thật vào repo hay brief. P0 (khảo sát tại khách) làm song song bởi bạn.

## 9. Nhịp vận hành hằng tuần

1. Sáng thứ Hai (09:00 giờ máy) daemon họp. Đọc biên bản ở web **Startup → cad-guard** hoặc `mca inbox`.
2. `autonomy: propose`: duyệt kế hoạch bằng `mca approve <việc gốc>` hoặc từ chối `mca reject <việc gốc> "<lý do>"`. Sau 2–3 cuộc họp ổn, đổi `autonomy` sang `execute` (sửa hồ sơ dự án).
3. Đọc ba con số: `false_positive_pct`, `confirmed_defects_7d`, `rework_incidents_7d`. Luật nào báo sai nhiều: đề xuất hạ mức hoặc tắt trong phiên bản chuẩn mới.
4. Khi qua P1c (đã đo độ chính xác), đổi `north_star` sang `confirmed_defects_7d` và đặt `target`/`by` theo thực tế.
5. Cần dừng: `mca venture pause cad-guard --days 7`.

## 10. Lưu ý và giới hạn hiện tại của MCA

- Nguồn `cmd` hiện **kế thừa toàn bộ môi trường của daemon** (kết quả M0(e)); việc cô lập bằng `env_allow` (M4 của Phase M) chưa làm. Vì vậy không đặt token vào script, và đừng đăng ký dự án có script không tin cậy.
- Điều lệ nằm ở `~/.mca/projects/cad-guard/project.yaml` (đồng bộ giữa máy bằng `mca sync`); thư mục `.mca/signals` vẫn ở trong repo trên máy chạy daemon.
- Bài học (playbook) hiện còn toàn cục; ghi đè theo dự án nằm ở Phase H, chưa làm. Trong lúc chờ, đặt quy tắc riêng của cad-guard vào `guardrails_md` và `AGENTS.md`.
- Việc nhờ qua MCP từ repo này được gắn dự án và tính vào ngân sách `tokens_per_week` của cad-guard; vượt ngân sách không chặn việc nhờ qua MCP nhưng chặn việc nền và họp.
- Một dự án chỉ có một máy chạy daemon.
