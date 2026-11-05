# AGENTS.md — cad-guard

Mục tiêu: kiểm tra và chuẩn hoá bản vẽ nội thất cho doanh nghiệp sản xuất nội thất. **Hướng đã chọn (CEO duyệt 03/11/2026): làm theo TỆP, lấy DXF làm định dạng chung, không phụ thuộc phần mềm CAD nào.** Plugin AutoCAD chỉ là phương án dự phòng nếu hướng theo tệp không giải quyết được bài toán.

Đọc trước khi sửa: `plans/cad-guard.md` (kế hoạch), `plans/cad-guard-direction.md` (hướng đi + P0), `standards/furniture-v0.md` (chuẩn + 58 luật), `docs/discovery.md` (khảo sát khách).

## Lệnh

Windows (PowerShell):

- Cài và thử một lượt: `scripts\bootstrap.ps1`
- Cài tay: `cd packages\core; python -m venv .venv; .venv\Scripts\pip install -e .[dev]`
- Test: `cd packages\core; .venv\Scripts\pytest -q`; agent/CI dùng venv chung: `python scripts/test.py [--extras agent]`. Kiểm thêm: `python scripts/bench.py` (12 tác vụ), `python scripts/check_repo_hygiene.py`
- Quét thử: `.venv\Scripts\python -m cadguard audit ..\..\fixtures\synthetic --out report.html`
- Liệt kê luật và tình trạng: `python -m cadguard rules`
- Số tổng hợp cho MCA: `python -m cadguard stats --json`
- Sinh lại DXF tổng hợp: `python -m cadguard fixtures fixtures/synthetic`
- Sửa an toàn (xem trước → xác nhận → tệp mới → hoàn tác): `propose`, `apply`, `undo`, `diff`, `validate` (`docs/changeset.md`)
- Trợ lý AI ẩn danh Bậc 1: máy chủ MCP chỉ đọc `python -m cadguard mcp --workspace <thư mục>` (extras `[agent]`); hỏi một lần `cadguard ask`, trò chuyện `cadguard chat`, `cadguard engines`, khoá API `cadguard keys set|status|delete <nhà cung cấp>` (`docs/assistant.md`)
- Giao diện cục bộ kiểm luật + trợ lý: `python -m cadguard app --workspace <thư mục>` (`docs/app.md`)
- Dựng 3D tất định: `python -m cadguard scene <dxf> --out cảnh.glb|.html|.json [--form form.html] [--supplement x.cgsup.json] [--with khac.dxf]`
- Studio (web cục bộ, LLM xem nội dung bản vẽ sau khi đồng ý từng phiên, dựng 3D, bổ sung phần thiếu): `python -m cadguard studio [--backend auto|api|cli|none]` (`plans/cad-guard-3d.md` mục 3c)

macOS/Linux: thay `.venv\Scripts\` bằng `.venv/bin/`.

## Cấu trúc

- `packages/core/cadguard/`: `model.py` (Drawing Model `cg.drawing/1`, `docs/drawing-model.md`), `dxf_reader.py` (DXF → mô hình qua ezdxf), `dxf_stream.py` (bộ đọc theo dòng cho tệp rất lớn, phải khớp `dxf_reader` trên mọi fixture: trường mới thêm vào mô hình phải cài ở **cả hai** bộ đọc), `rules/` (mỗi luật một hàm `@rule("<mã>")`), `standard.py` (nạp `standards/*.yaml`, hồ sơ công ty), `runner.py`, `report.py` (JSON + HTML tiếng Việt), `changeset/` (đề xuất/áp dụng/hoàn tác), `agent/` (công cụ trợ lý + ẩn danh), `mcp_server.py`, `assistant/` (engine CLI/API, khoá), `app/` (giao diện cục bộ), `scene/` (dựng 3D), `studio/` (web cục bộ + LLM), `telemetry.py`, `stats.py`, `fixtures.py`, `cli.py`.
- `standards/furniture-v0.yaml`, `design-hygiene-v0.yaml`: luật + tham số có phiên bản; `*.md`: nội dung chuẩn; `company-profile.example.yaml`: mẫu hồ sơ công ty.
- `fixtures/synthetic/`: DXF **tổng hợp** do `fixtures.py` sinh (bộ chính `ALL`; bộ dựng 3D `SCENE_FIXTURES` trong `scene/`). Không phải bản vẽ khách.
- `scripts/metrics.mjs`: đưa số tổng hợp cho MCA (nguồn `cmd` của điều lệ).

## Thêm một luật (quy trình bắt buộc)

1. Chọn mã trong `standards/furniture-v0.yaml` (đã có đủ 58 mã). Ưu tiên luật `deterministic` + `false_positive_risk: low`.
2. Viết hàm trong `cadguard/rules/*.py` với `@rule("<mã>")`. Luật chỉ đọc `DrawingModel`; thiếu dữ liệu thì `raise Skip("lý do")`, không ném lỗi khác.
3. Thiếu trường trong mô hình thì thêm vào `model.py` + `dxf_reader.py` (giữ tương thích ngược), đừng đọc ezdxf trong luật.
4. Thêm ca dương (vi phạm) vào một fixture "xấu" hoặc tạo fixture mới trong `fixtures.py`, cập nhật `EXPECTED` trong `tests/test_rules.py`; bản `ok_sheet.dxf` vẫn phải sạch.
5. Đặt `implemented: true` trong `standards/furniture-v0.yaml`. `tests/test_standard.py` kiểm khớp với sổ đăng ký.
6. `pytest -q` xanh, rồi mới báo `rules_implemented` mới cho MCA.

## Quy tắc không được vi phạm

- Chỉ ghi tệp bằng công cụ sửa tệp của agent hoặc Python `Path.write_text(..., encoding="utf-8")`; không dùng PowerShell `Set-Content`, `Out-File` hay `>` để ghi mã nguồn hoặc tài liệu. `tests/test_source_encoding.py` sẽ chặn chữ hỏng mã hoá.
- Phát hiện lỗi bằng code tất định. LLM chỉ giải thích/đề xuất, không ra quyết định đúng sai.
- Test chỉ dùng DXF tổng hợp tạo bằng ezdxf. **Không đọc, không sao chép bản vẽ thật của khách vào repo, vào prompt hay vào worktree của agent phát triển.** Ngoại lệ có điều kiện (quyết định 05/11/2026): sản phẩm Studio, chạy trên máy người dùng, được gửi nội dung bản vẽ của phiên đang mở cho LLM sau khi người dùng đồng ý trong phiên đó; vẫn không đưa bản vẽ thật vào repo/test/telemetry. Bản vẽ thật để ở thư mục ngoài repo (xem `docs/samples-intake.md`).
- Mọi luật có id ổn định, nguồn, mức độ; sửa luật hoặc ngưỡng = tạo phiên bản chuẩn mới (`furniture-v0.1`…), không sửa đè.
- Không bật `realtime_ok` cho luật chưa đo độ chính xác (P1c).
- Không sửa bản vẽ nếu thiếu bước xem trước + xác nhận + hoàn tác; chỉnh sửa luôn ghi ra tệp **mới**.
- Telemetry và số xuất ra ngoài chỉ là số tổng hợp, không tên tệp/khách/thợ vẽ, không đường dẫn (dùng mã băm).
- Trợ lý (MCP, `ask`, `app`) mặc định ẩn danh Bậc 1: kết quả công cụ không có tên thật, chữ, giá trị thuộc tính hay toạ độ (`agent/tools.py` dùng danh sách trắng trường). Trường mới chứa nội dung bản vẽ không được tự lọt ra; có test chặn.
- Không ghi khoá API/token ra tệp; mọi khoá đọc qua `assistant/keys.py` (biến môi trường hoặc kho khoá hệ điều hành). Không dùng thư viện đọc DWG có giấy phép copyleft hoặc phi thương mại (xem `docs/licenses.md`).
- Không `git push`. Thông báo cho người dùng bằng tiếng Việt; tên hàm/biến bằng tiếng Anh.
