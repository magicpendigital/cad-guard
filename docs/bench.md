# So sánh mô hình bằng bộ chấm (bước A1)

Bộ chấm `scripts/bench.py` (12 tác vụ trên DXF **tổng hợp**, xem `bench/README.md`) chấm câu trả lời bằng kiểm tra tất định. Bước A1 cắm **trợ lý thật** vào bộ chấm qua engine của `cadguard.assistant` (`docs/assistant.md`) để có bảng **đúng – chi phí – thời gian** theo mô hình.

## Chạy

```text
python scripts/bench.py                                         # tham chiếu, không gọi mô hình, phải 12/12
python scripts/bench.py --engine claude-cli --threshold 0 --out kq-claude-cli.json
python scripts/bench.py --engine anthropic --model claude-sonnet-5-5 --threshold 0 --out kq-sonnet.json
python scripts/bench.py --engine anthropic --model claude-haiku-5-5 --threshold 0 --out kq-haiku.json
python scripts/bench.py --engine openai --model <mô hình> --threshold 0
python scripts/bench.py --engine ollama --model <mô hình cục bộ> --threshold 0
python scripts/bench.py --engine codex-cli --experimental --threshold 0
python scripts/bench.py --engine agy-cli --account business --threshold 0
python scripts/bench.py --engine claude-cli --task B01-dem-loi-e-furniture      # thử một tác vụ trước
```

- `--engine` thay cho `--answerer bench.engine_answerer:answer`; cấu hình truyền qua biến `CADGUARD_BENCH_ENGINE`, `CADGUARD_BENCH_MODEL`, `CADGUARD_BENCH_ACCOUNT`, `CADGUARD_BENCH_EXPERIMENTAL`, `CADGUARD_BENCH_TIMEOUT` (giây/tác vụ, `--task-timeout`).
- Engine C cần khoá (`cadguard keys set anthropic` hoặc biến `ANTHROPIC_API_KEY`). Engine B cần CLI đã cài và **đã tự đăng nhập**.
- `--threshold 0` để luôn thoát mã 0 khi chỉ muốn số liệu.
- **Gọi mô hình thật, tốn token.** Chạy một tác vụ trước để ước lượng.

## Mỗi tác vụ làm gì

1. Tạo thư mục làm việc tạm chỉ chứa DXF tổng hợp của tác vụ (+ `ho-so.yaml` nếu có).
2. Nối engine với công cụ cad-guard đúng cờ `moi_truong`: ẩn danh (mặc định bật), `stream_threshold_mb`, `max_entity_records`, `--profile`. Tác vụ có hồ sơ (B06) có thêm bộ công cụ **không** hồ sơ (`cad-guard-goc` / `audit_khong_ho_so`) để trả lời "trước/sau".
3. Gửi `cau_hoi` (+ `tham_so`) và yêu cầu in **một khối ```json** theo `tra_loi` (trường → kiểu). Đáp án (`kiem_tra`) không bao giờ gửi đi.
4. Trích JSON (khối ```json cuối, nếu không có thì đối tượng `{…}` khớp nhiều trường nhất), chấm tất định.
5. `_chi_phi` = tổng token, USD (ước tính; 0 nếu không rõ giá), giây.

## Đọc kết quả

Bảng in: tác vụ, ĐÚNG/SAI, thời gian, token, USD, lý do trượt. `--out <tệp>` ghi JSON tổng hợp:

```json
{"answerer": "bench.engine_answerer:answer", "engine": "anthropic", "model": "claude-sonnet-5-5",
 "score_pct": 91.7, "threshold_pct": 0, "totals": {"tasks": 12, "ok": 11, "seconds": 210.4, "tokens": 412000, "usd": 0.91},
 "results": [{"id": "B01-dem-loi-e-furniture", "ok": true, "seconds": 14.2, "tokens": 30111, "usd": 0.07, "reasons": []}],
 "date": "2026-11-04"}
```

(Số trong ví dụ là minh hoạ, chưa đo.) Tệp không có đường dẫn, không tên tệp khách; lý do trượt có thể chứa giá trị mô hình trả (trên DXF tổng hợp).

So sánh mô hình: chạy cùng lệnh cho từng engine/mô hình, gom các tệp `--out` vào một bảng: tỉ lệ đúng, USD/tác vụ, giây/tác vụ. Chọn mô hình mặc định = rẻ nhất trong nhóm đạt ngưỡng (đề xuất ≥ 11/12, B09 ẩn danh bắt buộc đúng). Chi phí của `claude-cli` là `total_cost_usd` ước tính phía máy khách; với gói thuê bao không phải tiền bị trừ. `codex-cli`, `agy-cli` không báo USD (cột = 0), chỉ token.

## Lưu ý

- Ẩn danh mặc định bật; B09 kiểm câu trả lời không lộ tên thật.
- Kết quả thay đổi theo phiên bản CLI và mô hình: ghi phiên bản (`cadguard engines`) cạnh mỗi tệp kết quả.
- Không chạy bench trên bản vẽ thật.
