# AGENTS.md — Quy chế Phối hợp Multi-Coding-Agents (CAD Guard)

> **TÀI LIỆU BẮT BUỘC ĐỌC TRƯỚC KHI SỬA CODE**: Kho mã nguồn này được phát triển song song bởi nhiều Coding Agents (Claude Code, Codex, Antigravity). Để tránh xung đột kiến trúc (Architectural Drift) và giẫm chân lên nhau, mọi Agent **BẮT BUỘC** tuân thủ Ma trận Phân vùng Sở hữu và Cổng Kiểm chứng dưới đây.

---

## 1. Kiến trúc Cốt lõi & Nguồn Sự Thật Duy Nhất (Single Source of Truth)

1. **Định hướng sản phẩm**: Kiểm tra, chuẩn hóa, dựng 3D tất định và hỗ trợ bàn giao bản vẽ nội thất theo **TỆP DXF** (`cg.drawing/1`), không phụ thuộc phần mềm CAD.
2. **Nguyên tắc Vàng (Deterministic First)**:
   - **Phát hiện lỗi 100% bằng code tất định** (`packages/core/cadguard/rules/`).
   - **LLM / AI chỉ giải thích lỗi, tóm tắt, viết ghi chú bàn giao và đề xuất ChangeSet** (chạy khô, không bao giờ tự ghi đè bản vẽ gốc).
3. **Hợp đồng Dữ liệu Trung tâm**:
   - Mọi cấu trúc dữ liệu (`DrawingModel`, `EntityRec`, `LayerRec`, `WorkspaceState` / `DrawingSessionSpec`) định nghĩa tại `packages/core/cadguard/model.py` (và `contracts.py`).
   - **Quy tắc Đồng bộ Bộ đọc**: Bất kỳ trường nào thêm vào `DrawingModel` / `EntityRec` **BẮT BUỘC** phải được cài đặt đồng thời ở cả `dxf_reader.py` (ezdxf) **VÀ** `dxf_stream.py` (bộ đọc theo dòng cho tệp lớn).
4. **Một Web Server & Một Giao diện Duy nhất (Unified Studio)**:
   - Máy chủ & API Gateway duy nhất: `packages/core/cadguard/app/server.py` và `packages/core/cadguard/app/api.py`.
   - Giao diện người dùng duy nhất: `packages/core/cadguard/app/static/` (`index.html`, `app.js`, `app.css`).
   - **CẤM** tạo thêm HTTP server mới hay thư mục `static/` rời rạc ở các gói khác.
5. **Một Luồng Công cụ AI Duy nhất**:
   - Toàn bộ định nghĩa công cụ cho AI (`list_drawings`, `audit`, `explain_rule`, `get_model_summary`, `query_model`, `diff`, `propose_changeset`) đặt tại `packages/core/cadguard/agent/tools.py`.
   - `mcp_server.py`, `assistant/`, và `studio/llm.py` chỉ gọi lại hàm và schema từ `agent/tools.py`, **CẤM** viết trùng lặp logic công cụ hay danh sách trắng ẩn danh (`QUERY_FIELDS_ANON`).

---

## 2. Ma trận Phân vùng Sở hữu (Strict Ownership Matrix cho Multi-Agents)

Khi nhận nhiệm vụ, mỗi Agent chỉ sửa đổi trong phân vùng được giao và giao tiếp với phân vùng khác qua Hợp đồng Dữ liệu (`model.py`):

| Phân vùng (Zone) | Thư mục / Tệp Sở hữu | Quy định & Ràng buộc Cứng |
| --- | --- | --- |
| **Zone 1 — Lõi Mô hình & Bộ đọc DXF** | `cadguard/model.py`, `cadguard/contracts.py`, `cadguard/dxf_reader.py`, `cadguard/dxf_stream.py`, `cadguard/reader_select.py` | Giữ tương thích ngược schema `cg.drawing/1`. Sửa `dxf_reader.py` phải sửa `dxf_stream.py` tương ứng. Chạy `pytest tests/test_stream_reader.py`. |
| **Zone 2 — Bộ Luật Tất định & Chuẩn** | `cadguard/rules/*.py`, `cadguard/standard.py`, `cadguard/runner.py`, `standards/*.yaml`, `standards/*.md` | Mỗi luật dùng `@rule("<mã>")`, chỉ đọc `DrawingModel`. Thiếu dữ liệu thì `raise Skip("lý do")`. Bản `ok_sheet.dxf` luôn phải sạch lỗi. |
| **Zone 3 — Sửa An toàn & Dựng 3D** | `cadguard/changeset/*`, `cadguard/scene/*`, `cadguard/studio/{clusters,session,protocol}.py` | Không bao giờ sửa đè tệp DXF gốc; luôn xuất tệp mới kèm `validate_output`. Giữ nguyên chữ ký hàm để `test_changeset.py`, `test_scene.py`, `test_studio.py` luôn xanh. |
| **Zone 4 — Agent Tools, MCP & Assistant** | `cadguard/agent/*`, `cadguard/mcp_server.py`, `cadguard/assistant/*`, `cadguard/studio/llm.py`, `knowledge/*` | Mặc định ẩn danh Bậc 1 (`agent/anonymize.py`). Không lộ tên thật/chữ/toạ độ trừ phiên Studio đã được người dùng tích đồng ý. Không bao giờ lưu API key ra đĩa. |
| **Zone 5 — Unified Web App & UI** | `cadguard/app/server.py`, `cadguard/app/api.py`, `cadguard/app/chat.py`, `cadguard/app/static/*` | Mọi tính năng UI mới (Audit 2D, Diff, 3D Scene, Review Notes) tích hợp vào 4 chế độ của `app/static/` và `app/api.py`. |

---

## 3. Quy trình Bắt buộc khi Thêm Luật Mới (58 Luật `furniture-v0` & `design-hygiene-v0`)

1. Chọn mã luật trong `standards/furniture-v0.yaml` hoặc `standards/design-hygiene-v0.yaml`.
2. Viết hàm kiểm tra trong `packages/core/cadguard/rules/*.py` với decorator `@rule("<mã>")`. Chỉ đọc `DrawingModel`; thiếu dữ liệu thì `raise Skip("lý do")`.
3. Nếu cần thêm trường vào `DrawingModel`, cập nhật đồng thời `model.py`, `dxf_reader.py` và `dxf_stream.py`.
4. Bổ sung ca kiểm thử dương (vi phạm) vào `fixtures.py` và `EXPECTED` trong `tests/test_rules.py`; đảm bảo `ok_sheet.dxf` không báo lỗi giả.
5. Đặt `implemented: true` trong tệp `.yaml` tương ứng và chạy `pytest -q`.

---

## 4. Quy tắc Bảo mật, Mã hoá & Vệ sinh Kho Mã (Không được vi phạm)

- **Mã hoá UTF-8**: Chỉ ghi tệp bằng công cụ sửa tệp của Agent hoặc Python `Path.write_text(..., encoding="utf-8")` (không BOM). Tuyệt đối không dùng PowerShell `Set-Content` / `Out-File` / `>` gây hỏng dấu tiếng Việt (`tests/test_source_encoding.py` và `tests/test_console_encoding.py` sẽ chặn).
- **Không chứa dữ liệu thật của khách**: Tuyệt đối không đọc, không sao chép tệp `.dwg` / `.dxf` thật của khách vào repo, test hay telemetry. Chỉ dùng DXF tổng hợp sinh bởi `fixtures.py`.
- **Không lộ khoá bí mật**: Mọi khoá API đọc qua `assistant/keys.py` (biến môi trường hoặc keyring hệ điều hành).
- **Ngôn ngữ**: Giao tiếp, báo cáo, chú thích và tài liệu bằng **tiếng Việt có dấu chuẩn**; tên hàm, biến, lớp bằng **tiếng Anh**. Không tự ý chạy `git push`.

---

## 5. Cổng Kiểm chứng Bắt buộc trước khi Hoàn thành Nhiệm vụ (Verification Gates)

Trước khi kết thúc bất kỳ phiên làm việc nào, Agent **BẮT BUỘC** chạy và đảm bảo 3 lệnh sau xanh 100%:

```bash
# 1. Kiểm tra vệ sinh repo, bảo mật & chống rò rỉ dữ liệu khách
python scripts/check_repo_hygiene.py

# 2. Chạy toàn bộ bộ kiểm thử đơn vị, mã hoá UTF-8, luật, 3D, Studio và Web App
pytest -q

# 3. Chạy bộ chấm 12 tác vụ chuẩn (CAD-Bench)
python scripts/bench.py
```
