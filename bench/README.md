# Bộ chấm (bench) cad-guard

Bộ chấm đo xem một "người trả lời" (trợ lý AI qua CLI agent, hay một mô hình) trả lời câu hỏi về bản vẽ **đúng hay sai**, bằng kiểm tra **tất định**. Mọi tác vụ chạy trên DXF **tổng hợp** do `cadguard.fixtures` sinh. Không dùng bản vẽ thật. Xem `plans/cad-guard-agent.md` mục 6.2.

## Chạy

```text
python scripts/bench.py                       # người trả lời tham chiếu, phải đạt 100%
python scripts/bench.py --task B08-ghi-chu-ban-giao
python scripts/bench.py --json                # kết quả dạng JSON
python scripts/bench.py --answerer goi.mo_dun:ham --threshold 80
```

- Không có `ezdxf` trong Python đang chạy thì script tự chạy lại trong venv dùng chung của `scripts/test.py` (đổi bằng `CADGUARD_VENV`).
- In bảng: tác vụ, ĐÚNG/SAI, thời gian, token, chi phí USD, dòng tổng và tỉ lệ đúng. Tác vụ sai có dòng lý do bên dưới.
- Mã thoát: 0 khi tỉ lệ đúng ≥ ngưỡng (`--threshold`, mặc định 100), 1 khi thấp hơn, 2 khi tác vụ sai schema hoặc thiếu phụ thuộc.
- Chế độ mặc định **không gọi LLM, không gọi mạng**.

## Cấu trúc

```text
bench/
  tasks/<id>.yaml        một tác vụ mỗi tệp
  ho-so/                 hồ sơ công ty dùng cho tác vụ (dữ liệu minh hoạ)
  reference.py           người trả lời tham chiếu (gọi thẳng cadguard.agent.tools)
scripts/bench.py         trình chạy + bộ chấm
```

## Định dạng tác vụ

| Khoá | Bắt buộc | Nội dung |
| --- | --- | --- |
| `id` | có | Trùng tên tệp (`<id>.yaml`) |
| `mo_ta` | có | Mô tả tiếng Việt |
| `dang` | có | Dạng tác vụ; người trả lời tham chiếu chọn cách trả lời theo khoá này |
| `fixture` | có | Tên DXF trong `cadguard.fixtures.ALL` (một tên hoặc danh sách) |
| `cau_hoi` | có | Câu hỏi đưa cho trợ lý, nói rõ các trường JSON cần trả |
| `tra_loi` | có | Schema câu trả lời: trường → kiểu (`so_nguyen`, `chuoi`, `dung_sai`, `danh_sach`, `doi_tuong`) |
| `kiem_tra` | có | Danh sách kiểm tra tất định (bảng dưới) |
| `moi_truong` | không | Cờ máy chủ: `an_danh` (mặc định đúng), `stream_threshold_mb`, `max_entity_records`, `ho_so` (đường dẫn hồ sơ trong repo) |
| `tham_so` | không | Tham số của câu hỏi (chuẩn, phòng, cảnh báo đã chấp nhận…) |

Kiểm tra (`kiem_tra[].loai`):

| Loại | Khoá | Đạt khi |
| --- | --- | --- |
| `bang` | `truong`, `gia_tri` | Trường bằng đúng giá trị, đúng kiểu (đúng/sai không lẫn với số) |
| `tap` | `truong`, `gia_tri` | Trường là danh sách, so như tập hợp |
| `co_truong` | `truong` (danh sách) | Mọi trường có mặt và khác `null` |
| `khong_chua` | `chuoi` (danh sách) | JSON câu trả lời không chứa chuỗi nào (dùng để bắt lộ tên thật khi ẩn danh) |

`truong` nhận đường dẫn có dấu chấm (`a.b`). Trường dùng trong kiểm tra phải khai trong `tra_loi`.

## Danh sách tác vụ

| Id | Fixture | Kiểm gì |
| --- | --- | --- |
| B01-dem-loi-e-furniture | `bad_layers.dxf` | Đếm lỗi E theo `furniture-v0` và tập mã luật E |
| B02-vs-hygiene-bad | `hygiene_bad.dxf` | Tập VS-* đúng bằng VS-01…VS-07, số luật đã chạy |
| B03-layer-du-xref | `hygiene_bad.dxf` | Số layer dư từ xref (VS-01) |
| B04-kich-thuoc-ghi-de | `hygiene_bad.dxf` | Tổng số kích thước và số bị ghi đè chữ (qua `query_model`) |
| B05-hygiene-ok-sach | `hygiene_ok.dxf` | Xác nhận sạch theo `design-hygiene-v0` |
| B06-ho-so-cong-ty | `hygiene_bad.dxf` + hồ sơ | Hồ sơ công ty làm mất VS-02, VS-05; `profile.name` đúng hồ sơ đã áp |
| B07-records-capped | `hygiene_bad.dxf` (trần 5 bản ghi) | Báo `records_capped` và cảnh báo người dùng |
| B08-ghi-chu-ban-giao | `hygiene_bad.dxf` | Ghi chú bàn giao Thiết kế → Kỹ thuật đủ trường bắt buộc |
| B09-an-danh-khong-lo-ten | `hygiene_bad.dxf` (ẩn danh) | Trả lời đúng mà không lộ tên layer/tệp thật |
| B10-luat-bo-qua | `ok_sheet.dxf` | Nêu luật bị bỏ qua (VS-03, VS-04) và lý do |
| B11-giai-thich-vs06 | `hygiene_bad.dxf` (không cần đọc) | Giải thích VS-06 bằng `explain_rule` |
| B12-tom-tat-mo-hinh | `hygiene_bad.dxf` | Số liệu tóm tắt mô hình |

Đáp án là số cố định, khớp các fixture tổng hợp hiện tại (`tests/test_hygiene.py`, `tests/test_rules.py` cũng dựa vào chúng). Đổi fixture hay luật thì chạy lại bộ chấm và sửa đáp án trong cùng commit.

## Người trả lời

Giao diện: một hàm Python `ham(task: dict, workspace: Path) -> dict`.

- `task`: bản công khai của tác vụ, **không có** `kiem_tra`.
- `workspace`: thư mục làm việc tạm, rỗng, chỉ chứa DXF tổng hợp của tác vụ (và `ho-so.yaml` nếu có). Người trả lời qua CLI agent sẽ khởi `python -m cadguard mcp --workspace <workspace>` với các cờ trong `moi_truong`, đưa `cau_hoi` cho trợ lý và đọc JSON trả về.
- Kết quả: dict theo `tra_loi`. Kèm `_chi_phi = {"tokens": ..., "usd": ...}` để điền cột chi phí; khoá này không bị chấm.
- Ném ngoại lệ = tác vụ trượt, các tác vụ khác vẫn chạy.

### Người trả lời tham chiếu (`bench/reference.py`)

Gọi thẳng 5 hàm công cụ trong `cadguard.agent.tools` (đúng những gì máy chủ MCP đưa cho trợ lý), tất định, chi phí 0. Phải đạt 100%; nếu không thì đáp án, tác vụ hoặc hành vi công cụ đã lệch.

Hồ sơ công ty (B06): `moi_truong.ho_so` tương ứng cờ `python -m cadguard mcp --profile ho-so.yaml`. Tham chiếu dựng `ToolContext(profile=...)` và gọi `audit` như mọi tác vụ khác; `audit` tự áp hồ sơ khi chuẩn trùng chuẩn của hồ sơ và trả `profile: {name, version}` (null nếu không áp). Kết quả "trước" lấy từ cùng công cụ với `profile=None`, tức một máy chủ không có `--profile`. Người trả lời qua CLI thật cần hai máy chủ cho B06: một có `--profile`, một không.

## Chưa làm

- Người trả lời chạy qua CLI agent thật (Claude Code, Codex CLI, OpenCode, Antigravity CLI) và đọc số token/chi phí của từng CLI.
- Tác vụ có sửa bản vẽ (chờ công cụ ghi: changeset, `validate_output`).
- Tác vụ trên bản vẽ khâu Kỹ thuật/Lập trình sản xuất chi tiết hơn (chờ mẫu và luật).
