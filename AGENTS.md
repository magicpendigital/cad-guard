# AGENTS.md — cad-guard

Mục tiêu: kiểm tra và chuẩn hoá bản vẽ nội thất cho doanh nghiệp sản xuất nội thất. **Hướng đã chọn (CEO duyệt 03/11/2026): làm theo TỆP, lấy DXF làm định dạng chung, không phụ thuộc phần mềm CAD nào.** Plugin AutoCAD chỉ là phương án dự phòng nếu hướng theo tệp không giải quyết được bài toán.

Đọc trước khi sửa: `plans/cad-guard.md` (kế hoạch), `plans/cad-guard-direction.md` (hướng đi + P0), `standards/furniture-v0.md` (chuẩn + 58 luật), `docs/discovery.md` (khảo sát khách).

## Lệnh

Windows (PowerShell):

- Cài và thử một lượt: `scripts\bootstrap.ps1`
- Cài tay: `cd packages\core; python -m venv .venv; .venv\Scripts\pip install -e .[dev]`
- Test: `cd packages\core; .venv\Scripts\pytest -q`
- Quét thử: `.venv\Scripts\python -m cadguard audit ..\..\fixtures\synthetic --out report.html`
- Liệt kê luật và tình trạng: `python -m cadguard rules`
- Số tổng hợp cho MCA: `python -m cadguard stats --json`
- Sinh lại DXF tổng hợp: `python -m cadguard fixtures fixtures/synthetic`
- Dựng 3D tất định: `python -m cadguard scene <dxf> --out cảnh.glb|.html|.json [--form form.html] [--supplement x.cgsup.json] [--with khac.dxf]`
- Studio (web cục bộ + LLM): `python -m cadguard studio [--backend auto|api|cli|none]` (xem `plans/cad-guard-3d.md` mục 3c)

macOS/Linux: thay `.venv\Scripts\` bằng `.venv/bin/`.

## Cấu trúc

- `packages/core/cadguard/`: `model.py` (Drawing Model `cg.drawing/1`), `dxf_reader.py` (DXF → mô hình), `rules/` (mỗi luật một hàm `@rule("<mã>")`), `standard.py` (nạp `standards/*.yaml`), `runner.py`, `report.py` (JSON + HTML tiếng Việt), `telemetry.py`, `stats.py`, `fixtures.py`, `cli.py`.
- `standards/furniture-v0.yaml`: luật + tham số có phiên bản. `furniture-v0.md`: nội dung chuẩn.
- `fixtures/synthetic/`: DXF **tổng hợp** do `fixtures.py` sinh. Không phải bản vẽ khách.
- `scripts/metrics.mjs`: đưa số tổng hợp cho MCA (nguồn `cmd` của điều lệ).

## Thêm một luật (quy trình bắt buộc)

1. Chọn mã trong `standards/furniture-v0.yaml` (đã có đủ 58 mã). Ưu tiên luật `deterministic` + `false_positive_risk: low`.
2. Viết hàm trong `cadguard/rules/*.py` với `@rule("<mã>")`. Luật chỉ đọc `DrawingModel`; thiếu dữ liệu thì `raise Skip("lý do")`, không ném lỗi khác.
3. Thiếu trường trong mô hình thì thêm vào `model.py` + `dxf_reader.py` (giữ tương thích ngược), đừng đọc ezdxf trong luật.
4. Thêm ca dương (vi phạm) vào một fixture "xấu" hoặc tạo fixture mới trong `fixtures.py`, cập nhật `EXPECTED` trong `tests/test_rules.py`; bản `ok_sheet.dxf` vẫn phải sạch.
5. Đặt `implemented: true` trong `standards/furniture-v0.yaml`. `tests/test_standard.py` kiểm khớp với sổ đăng ký.
6. `pytest -q` xanh, rồi mới báo `rules_implemented` mới cho MCA.

## Quy tắc không được vi phạm

- Phát hiện lỗi bằng code tất định. LLM chỉ giải thích/đề xuất, không ra quyết định đúng sai.
- Test chỉ dùng DXF tổng hợp tạo bằng ezdxf. **Không đọc, không sao chép bản vẽ thật của khách vào repo, vào prompt hay vào worktree của agent phát triển.** Ngoại lệ có điều kiện (quyết định 05/11/2026): sản phẩm Studio, chạy trên máy người dùng, được gửi nội dung bản vẽ của phiên đang mở cho LLM sau khi người dùng đồng ý trong phiên đó; vẫn không đưa bản vẽ thật vào repo/test/telemetry. Bản vẽ thật để ở thư mục ngoài repo (xem `docs/samples-intake.md`).
- Mọi luật có id ổn định, nguồn, mức độ; sửa luật hoặc ngưỡng = tạo phiên bản chuẩn mới (`furniture-v0.1`…), không sửa đè.
- Không bật `realtime_ok` cho luật chưa đo độ chính xác (P1c).
- Không sửa bản vẽ nếu thiếu bước xem trước + xác nhận + hoàn tác; chỉnh sửa luôn ghi ra tệp **mới**.
- Telemetry và số xuất ra ngoài chỉ là số tổng hợp, không tên tệp/khách/thợ vẽ, không đường dẫn (dùng mã băm).
- Không ghi khoá API/token ra tệp. Không dùng thư viện đọc DWG có giấy phép copyleft hoặc phi thương mại (xem `docs/licenses.md`).
- Không `git push`. Thông báo cho người dùng bằng tiếng Việt; tên hàm/biến bằng tiếng Anh.
