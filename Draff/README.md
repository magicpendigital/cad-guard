# cad-guard

Trợ lý kiểm tra và chuẩn hoá bản vẽ nội thất cho doanh nghiệp sản xuất nội thất (tủ bếp, tủ áo, văn phòng).

- **Hướng:** làm theo tệp, lấy DXF làm định dạng chung, không phụ thuộc phần mềm CAD nào (CEO duyệt 03/11/2026). Plugin AutoCAD là phương án dự phòng.
- **Nguyên tắc:** phát hiện lỗi bằng code tất định, chạy cục bộ, không cần LLM. LLM chỉ giải thích và đề xuất (trợ lý ẩn danh, studio cần đồng ý từng phiên).
- **Trạng thái:** lõi v0.1.0 — 16/58 luật đã cài và có test; chưa thử với bản vẽ thật (chờ P0).

## Chạy thử (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
```

Script cài lõi vào `packages\core\.venv`, chạy test, quét các DXF tổng hợp và ghi `report.html` (mở bằng trình duyệt).

Quét bản vẽ của bạn (để bản vẽ **ngoài** repo, xem `docs/samples-intake.md`):

```powershell
cd packages\core
.venv\Scripts\python -m cadguard audit D:\CadGuardData\samples --out D:\CadGuardData\report.html
```

Lệnh khác: `python -m cadguard rules` (danh sách luật), `python -m cadguard stats --json` (số tổng hợp cho MCA).

### Giao diện cục bộ trong trình duyệt

```powershell
python -m cadguard app --workspace D:\CadGuardData\phien-01 [--profile ho-so.yaml]
```

Mở giao diện chỉ trên máy này (`127.0.0.1`, cổng ngẫu nhiên, mã phiên trong địa chỉ in ra): chọn phòng (Thiết kế / Kỹ thuật / Lập trình sản xuất), xem lỗi theo mức E/W/I, đề xuất sửa → xem trước → áp dụng ra **tệp mới** khi bạn bấm xác nhận → hoàn tác; tab Luật áp dụng (chỉ đọc); trò chuyện với trợ lý AI bằng hạn mức CLI đã đăng nhập hoặc khoá API của bạn (khoá đặt bằng `cadguard keys set …`, không nhập trong trình duyệt). Không cần phụ thuộc thêm. Chi tiết: `docs/app.md`.

### Máy chủ MCP chỉ đọc cho trợ lý AI

Cài SDK (extras `[agent]`): `pip install cadguard[agent]`, hoặc trong repo `python scripts/test.py --extras agent`. Chạy:

```powershell
python -m cadguard mcp --workspace D:\CadGuardData\phien-01
```

- Máy chủ nói MCP qua stdio (stdout chỉ có JSON-RPC, thông báo ra stderr), mặc định có 6 công cụ chỉ đọc: `list_drawings`, `audit`, `explain_rule`, `get_model_summary`, `query_model`, `diff`. `--allow-propose` thêm `propose_changeset` (chạy khô, chỉ ghi changeset JSON); **không** có công cụ áp dụng qua MCP.
- Sửa bản vẽ an toàn: `cadguard propose <tệp> --ops ops.json` → xem trước; `cadguard apply <mã>` (hỏi xác nhận) → tệp mới `<tên>.cg-<mã>.dxf`, tệp gốc giữ nguyên; `cadguard undo <mã>` hoàn tác; `cadguard diff a b`, `cadguard validate a b --changeset <mã>`. Chi tiết: `docs/changeset.md`.
- `--workspace` **bắt buộc** (không mặc định thư mục hiện tại): chỉ đọc tệp `.dxf` nằm trong thư mục này; đường dẫn `..`, tuyệt đối, UNC hay trỏ ra ngoài đều bị từ chối. Nên dùng một thư mục phiên chỉ chứa bản vẽ cần kiểm.
- Mặc định ẩn danh Bậc 1 (tên tệp/layer/khối/kiểu chữ thành mã phiên). `--no-anonymize` tắt ẩn danh, chỉ dùng khi khách đã đồng ý; `--standard` chọn chuẩn mặc định. Xem `python -m cadguard mcp --help`.
- Mẫu cấu hình cho từng CLI agent: `knowledge/`, `docs/integrations/`.
- Hỏi trợ lý từ dòng lệnh: `cadguard ask "…" --engine <engine> --workspace <thư mục>`, `cadguard chat`, `cadguard engines`; khoá API đặt bằng `cadguard keys set anthropic` (kho khoá hệ điều hành) hoặc biến môi trường. Chi tiết: `docs/assistant.md`.

### Dựng 3D và Studio

```powershell
python -m cadguard scene ban-ve.dxf --out canh.glb   # hoặc .html (xem ngay), .json; --form form.html khi còn phần thiếu
python -m cadguard studio --open                      # web cục bộ: LLM đọc bản vẽ, đề xuất, dựng 3D, bổ sung
```

- `scene` dựng tất định từ thuộc tính khối (W/D/H) hoặc ba hình chiếu (layer `FN-VIEW-FRONT/TOP/SIDE`); thiếu thì báo phần thiếu, không đoán; `--supplement`/`--with` để bổ sung.
- `studio` gửi **nội dung bản vẽ** (layer, chữ, số đo, khối, thuộc tính, toạ độ) cho LLM chỉ khi bạn tích đồng ý trong phiên; không gửi đường dẫn/tên tệp. LLM: khoá Anthropic của bạn (`cadguard keys set anthropic` hoặc `ANTHROPIC_API_KEY`) hoặc CLI `claude` đã đăng nhập. Đề xuất áp dụng ra tệp mới, hoàn tác được. Chi tiết: `plans/cad-guard-3d.md` mục 3c.

## Đọc gì

| Cần | Đọc |
| --- | --- |
| Kế hoạch và lộ trình P0–P5 | `plans/cad-guard.md`, `plans/cad-guard-direction.md` |
| Chuẩn trình bày v0 và 58 luật | `standards/furniture-v0.md`, `standards/furniture-v0.yaml` |
| Việc cần người làm trước (khảo sát, thu mẫu) | `docs/discovery.md`, `docs/samples-intake.md` |
| Đăng ký dự án vào MCA, nối `report_signal` | `docs/guides/cad-guard-bootstrap.md` |
| **Mới dùng GitHub: commit, push từng bước** | `docs/guides/github-tu-dau.md` |
| **Các bước tiếp theo: chạy bootstrap, đăng ký MCA, P0, giao brief** | `docs/guides/buoc-tiep-theo.md` |
| **Các bước tiếp theo bằng giao diện (Claude Code + mca HQ), không gõ lệnh** | `docs/guides/buoc-tiep-theo-giao-dien.md` |
| Giao diện cục bộ `cadguard app` | `docs/app.md` |
| Dựng 3D, studio, dữ liệu gửi LLM | `plans/cad-guard-3d.md` |
| Trường của Drawing Model, hai bộ đọc | `docs/drawing-model.md` |
| Trợ lý AI (CLI theo hạn mức, API bằng khoá của bạn) | `docs/assistant.md` |
| Giấy phép các thành phần | `docs/licenses.md` |
| Quy tắc cho agent làm việc trong repo | `AGENTS.md` |

## Cấu trúc

```text
packages/core/       lõi Python (cadguard/, tests/, pyproject.toml)
standards/           furniture-v0, design-hygiene-v0 (.yaml + .md), mẫu hồ sơ công ty
fixtures/synthetic/  DXF tổng hợp (sinh bằng `python -m cadguard fixtures`)
docs/                khảo sát P0, thu mẫu, giấy phép, đo độ chính xác, hướng dẫn
plans/               kế hoạch dự án
scripts/             bootstrap.ps1, metrics.mjs (số tổng hợp cho MCA)
```
