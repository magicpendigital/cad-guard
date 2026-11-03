# cad-guard

Trợ lý kiểm tra và chuẩn hoá bản vẽ nội thất cho doanh nghiệp sản xuất nội thất (tủ bếp, tủ áo, văn phòng).

- **Hướng:** làm theo tệp, lấy DXF làm định dạng chung, không phụ thuộc phần mềm CAD nào (CEO duyệt 03/11/2026). Plugin AutoCAD là phương án dự phòng.
- **Nguyên tắc:** phát hiện lỗi bằng code tất định, chạy cục bộ, không cần LLM. LLM (về sau) chỉ giải thích và đề xuất.
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
| Giấy phép các thành phần | `docs/licenses.md` |
| Quy tắc cho agent làm việc trong repo | `AGENTS.md` |

## Cấu trúc

```text
packages/core/       lõi Python (cadguard/, tests/, pyproject.toml)
standards/           furniture-v0.yaml + furniture-v0.md
fixtures/synthetic/  DXF tổng hợp (sinh bằng `python -m cadguard fixtures`)
docs/                khảo sát P0, thu mẫu, giấy phép, đo độ chính xác, hướng dẫn
plans/               kế hoạch dự án
scripts/             bootstrap.ps1, metrics.mjs (số tổng hợp cho MCA)
```
