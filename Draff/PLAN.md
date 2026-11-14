# PLAN.md — Kiến trúc Tổng thể & Lộ trình Hợp nhất Dự án CAD Guard (`magicpendigital/cad-guard`)

> **Bản kế hoạch nguồn sự thật duy nhất (Single Master Plan)** — hợp nhất từ `plans/cad-guard.md`, `plans/cad-guard-direction.md`, `plans/cad-guard-agent.md`, và `plans/cad-guard-3d.md` sau giai đoạn **Phase 0: Consolidation & Contract-First**.

---

## 1. Mục tiêu Sản phẩm & Định hướng Cốt lõi (Đã duyệt bởi CEO)

- **Bài toán**: Doanh nghiệp sản xuất nội thất (Thiết kế → Kỹ thuật → Lập trình sản xuất → Xưởng) gặp lỗi bản vẽ lọt xuống xưởng hoặc công trình gây chi phí sửa sai lớn (sai layer CNC, thiếu ghi chú dán cạnh, lệch chữ kích thước, thừa đối tượng rác từ xref).
- **Hướng đi đã chốt (Hướng C — Làm theo tệp, DXF làm định dạng chung)**:
  - Không phụ thuộc vào một phần mềm CAD cố định (AutoCAD, ZWCAD, BricsCAD, GstarCAD đều xuất được DXF).
  - **100% phát hiện lỗi bằng code tất định (Deterministic Rules)** chạy cục bộ. Mô hình ngôn ngữ lớn (LLM) chỉ giải thích lỗi bằng tiếng Việt, tổng hợp báo cáo, soạn ghi chú bàn giao và đề xuất thao tác sửa (`ChangeSet`) trong từ vựng cố định.
  - **An toàn tuyệt đối cho tài sản sản xuất**: Tệp bản vẽ gốc chỉ đọc. Mọi chỉnh sửa luôn đi qua quy trình *Đề xuất → Xem trước (Dry-run) → Người dùng xác nhận → Ghi ra tệp mới (`.cg-xxxx.dxf`) → Kiểm chứng đầu ra (`validate_output`) → Hoàn tác 1 bước*.

---

## 2. Kiến trúc Hợp nhất (Unified Architecture — Phase 0)

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ Tầng 3: Quản trị & Đo lường MCA                                            │
│   cadguard stats --json · scripts/metrics.mjs · scripts/bench.py (12 task) │
├────────────────────────────────────────────────────────────────────────────┤
│ Tầng 2: Unified CAD Guard Studio (1 Máy chủ & 1 Giao diện Duy nhất)        │
│   Backend: packages/core/cadguard/app/{server.py, api.py, chat.py}         │
│   Frontend: packages/core/cadguard/app/static/{index.html, app.js, app.css}│
│   4 Chế độ tích hợp:                                                       │
│     [1. Kiểm lỗi 2D (Audit)]         [2. So sánh Sửa đổi (Diff/ChangeSet)] │
│     [3. Không gian 3D (Scene/Gaps)]  [4. Duyệt & Bàn giao (Review Notes)]  │
├────────────────────────────────────────────────────────────────────────────┤
│ Tầng 1: Trợ lý AI Đa Động Cơ & Cổng MCP (Single Source of Truth)           │
│   Nguồn công cụ duy nhất: packages/core/cadguard/agent/tools.py (ToolBox)  │
│   Giao thức: cadguard mcp (stdio) · CLI Engines · Direct API Engines       │
│   Bảo mật: Ẩn danh Bậc 1 mặc định (F_xxxx, L_xxxx, che chữ & toạ độ)       │
├────────────────────────────────────────────────────────────────────────────┤
│ Tầng 0: Lõi Tất định & Hợp đồng Dữ liệu Trung tâm (Central Contracts)      │
│   model.py & contracts.py: DrawingModel (cg.drawing/1) + WorkspaceState    │
│   dxf_reader.py (ezdxf) + dxf_stream.py (bộ đọc theo dòng cho tệp lớn)     │
│   rules/ (luật tất định) · changeset/ · scene/ (3D glTF/GLB) · studio/     │
└────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Hợp đồng Dữ liệu Trung tâm (`packages/core/cadguard/contracts.py` & `model.py`)
Mọi tầng trong hệ thống giao tiếp qua các lược đồ Pydantic có phiên bản:
1. **`DrawingModel` (`cg.drawing/1`)**: Lớp hình học & thuộc tính trích xuất đồng nhất từ cả `dxf_reader.py` và `dxf_stream.py`.
2. **`AuditReportSpec` (`cg.audit/1`)**: Kết quả chạy bộ luật tất định (`findings[]`, `counts`, `fixable_rules`).
3. **`ChangesetSpec` (`cg.changeset/1`)**: Đề xuất sửa đổi chạy khô (`ops[]`, `preview`, `applied`, `validation`).
4. **`Scene` (`cg.scene/1`)**: Mô hình không gian 3D tất định (`walls[]`, `modules[]`, `panels[]`, `gaps[]`, `skipped[]`).
5. **`ReviewNoteSpec` & `WorkspaceState` (`cg.workspace/1`)**: Hợp đồng phiên làm việc hợp nhất nối kết 4 chế độ trên giao diện Studio.

### 2.2 Chuẩn hoá Luồng Công cụ AI (`packages/core/cadguard/agent/tools.py`)
- Toàn bộ định nghĩa công cụ (`TOOL_SPECS`, `PROPOSE_SPEC`, `BASELINE_SPEC`), hộp công cụ (`ToolBox`) và bộ điều phối (`dispatch_tool`) đặt tại `cadguard/agent/tools.py`.
- `cadguard/mcp_server.py`, `cadguard/assistant/toolspec.py`, `cadguard/assistant/api_engines.py`, và `cadguard/studio/llm.py` đều tái sử dụng nguồn sự thật này, đảm bảo luật ẩn danh Bậc 1 (`QUERY_FIELDS_ANON`) không bao giờ bị rò rỉ khi thêm trường mới vào `EntityRec`.

---

## 3. Lộ trình Triển khai & Tình trạng Các Giai đoạn

| Giai đoạn | Hạng mục Trọng tâm | Trạng thái | Tiêu chí Nghiệm thu (Verification Gate) |
| --- | --- | --- | --- |
| **Phase 0** | Hợp nhất 3 Ốc đảo Server/UI, Chuẩn hoá `WorkspaceState` & `agent/tools.py` | **Hoàn thành** | `pytest -q` xanh 100%, `check_repo_hygiene.py` xanh |
| **P0** | Khảo sát tại khách, thu thập mẫu thực tế ngoài repo (`docs/samples-intake.md`) | Đang thực hiện | Hồ sơ mẫu thực tế (`docs/real-sample-profile.md`) |
| **P1a/L1b** | Lõi `DrawingModel`, bộ đọc lớn `dxf_stream`, chuẩn `design-hygiene-v0` & `furniture-v0` | **Hoàn thành** | Khớp 100% giữa `dxf_reader` và `dxf_stream` trên mọi fixture |
| **A0/A2** | Máy chủ `cadguard mcp`, `ChangeSet` xem trước/áp dụng/hoàn tác, 4 gói `knowledge/skills/` | **Hoàn thành** | `scripts/bench.py` đạt 12/12 tác vụ trên DXF tổng hợp |
| **3D Tầng A/A2** | Dựng cảnh 3D tất định (`cg.scene/1`), nhận diện cụm hình chiếu (`clusters`), xuất `.glb` | **Hoàn thành** | `tests/test_scene.py` và `tests/test_studio.py` xanh |
| **P1c/P2** | Đo độ chính xác thực tế cùng kỹ sư rà soát, mở rộng các luật `furniture-v0` còn lại | Tiếp theo | Độ chính xác cảnh báo ≥ 85–90%, `rules_regressed == 0` |
| **P3** | Cảnh báo tức thời khi lưu tệp (Watch folder / Adapter mỏng theo phần mềm CAD chốt) | Giai đoạn sau | Chỉ bật cho luật có `realtime_ok: true` sau P1c |

---

## 4. Quy tắc Bất biến (Always / Never)

- **LUÔN LUÔN**:
  - Ghi tệp bằng UTF-8 chuẩn; giữ `dxf_reader.py` và `dxf_stream.py` đồng bộ tuyệt đối khi mở rộng `DrawingModel`.
  - Mọi luật kiểm tra phải tất định (`@rule("<mã>")`), chỉ đọc `DrawingModel`, thiếu dữ liệu thì `raise Skip("lý do")`.
  - Mọi chỉnh sửa bản vẽ phải tạo tệp mới, có bước xem trước và hoàn tác.
- **KHÔNG BAO GIỜ**:
  - Đưa bản vẽ thật của khách (`.dwg`, `.dxf`) vào kho mã nguồn, test hoặc telemetry.
  - Lưu khoá API/token ra đĩa (chỉ đọc qua `assistant/keys.py` từ biến môi trường hoặc kho khoá hệ điều hành).
  - Dùng tài nguyên mạng ngoài (CDN), `innerHTML`, `eval(`, hoặc `style=` nội tuyến trong `packages/core/cadguard/app/static/`.
