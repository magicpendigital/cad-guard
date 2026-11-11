# AGENTS.md — cad-guard

Mục tiêu: kiểm tra và chuẩn hoá bản vẽ nội thất cho doanh nghiệp sản xuất nội thất. **Hướng đã chọn (CEO duyệt 03/11/2026): làm theo TỆP, lấy DXF làm định dạng chung, không phụ thuộc phần mềm CAD nào.** Plugin AutoCAD chỉ là phương án dự phòng nếu hướng theo tệp không giải quyết được bài toán.

Đọc trước khi sửa: `PLAN.md` (kim chỉ nam: trạng thái và lộ trình hiện tại), `plans/cad-guard.md` (kế hoạch gốc), `plans/cad-guard-direction.md` (hướng đi + P0), `standards/furniture-v0.md` (chuẩn + 58 luật), `docs/discovery.md` (khảo sát khách).

## Lệnh

Windows (PowerShell):

- Cài và thử một lượt: `scripts\bootstrap.ps1`
- Cài tay: `cd packages\core; python -m venv .venv; .venv\Scripts\pip install -e .[dev,agent,keyring]`; kiểm môi trường: `python -m cadguard doctor`
- Test: `cd packages\core; .venv\Scripts\pytest -q`; agent/CI dùng venv chung: `python scripts/test.py [--extras agent]`. Kiểm thêm: `python scripts/bench.py` (12 tác vụ), `python scripts/check_repo_hygiene.py`
- Quét thử: `.venv\Scripts\python -m cadguard audit ..\..\fixtures\synthetic --out report.html`
- Liệt kê luật và tình trạng: `python -m cadguard rules`
- Số tổng hợp cho MCA: `python -m cadguard stats --json`
- Sinh lại DXF tổng hợp: `python -m cadguard fixtures fixtures/synthetic`
- Sửa an toàn (xem trước → xác nhận → tệp mới → hoàn tác): `propose`, `apply`, `undo`, `diff`, `validate` (`docs/changeset.md`)
- Trợ lý AI ẩn danh Bậc 1: máy chủ MCP chỉ đọc `python -m cadguard mcp --workspace <thư mục>` (extras `[agent]`); hỏi một lần `cadguard ask`, trò chuyện `cadguard chat`, `cadguard engines`, khoá API `cadguard keys set|status|delete <nhà cung cấp>` (`docs/assistant.md`)
- Chạy thử với AutoCAD theo tệp (M1+M2, `docs/autocad.md`): `cadguard watch <thư mục>` (tự kiểm DXF mới), `cadguard autocad --copy-to <thư mục>` (`cadguard.lsp`: CGXUAT/CGTOI/CGDEN/CGBAOCAO/CGHELP; nút "Tới trong AutoCAD" của `app` + M3 điều hướng qua COM, `autocad/bridge.py`); plugin .NET (hướng D) `python scripts/build_acad_plugin.py` → `packages/acad-plugin/` (CGBANG bảng neo, CGGHIM ghim tạm thời); lệnh mới thêm vào `cg:*help*` của `cadguard.lsp` (test kiểm), `cadguard mcp-config claude-desktop|claude-code|codex --workspace <thư mục>`, `cadguard doctor [--mcp]`, đo MCP: `python scripts/test.py --extras agent --run ../../scripts/mcp_smoke.py`
- Giao diện cục bộ kiểm luật + trợ lý: `python -m cadguard app --workspace <thư mục>` (`docs/app.md`)
- Chỉ mục tờ (trang in) + ứng viên rác: `python -m cadguard sheets <dxf> [--json]` (`sheets.py`, `textcodec.py` giải mã TCVN3/VNI; bậc chốt tờ `gate.py`, trạng thái `sheet_state.py`)
- Dựng 3D tất định: `python -m cadguard scene <dxf> --out cảnh.glb|.html|.json [--form form.html] [--supplement x.cgsup.json] [--with khac.dxf]`
- Hồ sơ trình bày (cách công ty/người vẽ trình bày): `cadguard/drafting.py` (`cg.drafting-profile/1`; vai trò layer, thẻ số bản vẽ, nghĩa ghi chú; đề xuất code + AI qua `drafting.check`), app `app/drafting_api.py` (`/api/drafting[/save|/propose]`); mọi chỗ đọc bản vẽ cho 3D/bản đồ dùng `drafting.read`
- Chú giải hạng mục (chia khối tại vách thật, hình bỏ cánh đi kèm): `scene/annotate.py` (`split_proposals`, bộ kiểm `check_split`, áp `apply_splits`; khoá `split:<hạng mục>`), đề xuất tự hiện ở màn 3D, AI chọn trong ứng viên qua `/api/scene/ai`
- Dòng phiên bản + chuẩn hoá trước 3D (`docs/research/luong-phien-ban-va-chuan-hoa.md`): `app/versions.py` (bản đang dùng, hoàn tác/làm lại không xoá tệp, `/api/versions[/set|undo|redo]`, `.cadguard/versions.json`), `app/scene_ai.py` (`/api/scene/ai`: code đọc mặt cắt + AI đề xuất số thiếu, mỗi số phải dẫn kích thước/chữ có đúng số đó, người dùng xác nhận); trình xem 3D WebGL `makeViewerGL` trong `app.js`
- Dựng 3D cả tầng (`docs/research/phoi-canh-ca-khong-gian.md`): `cadguard space <dxf> [--out x.glb|x.json]` (`scene/space.py`, `cg.space/1`: tường mặt bằng tổng, đặt hạng mục theo ký hiệu số, đồ rời, cửa); tách khối mặt đứng `scene/segment.py` (cắt XY)
- Dựng 3D từ bản vẽ 2D kiểu công ty (Luồng 2, `docs/3d-feasibility.md`): `cadguard scene <dxf> --item <mã hạng mục|auto> --out x.glb|.html|.json` (`cg.scene/2`, `scene/views2d.py`, `scene/assemble.py`), đo khả năng `cadguard scene-assess <dxf> [--json]`; công thái học `cadguard/ergonomics.py` + `standards/ergonomics-v0.yaml` (khoảng chờ duyệt, không điền số không nguồn)
- Tờ, Unicode, template, dịch, thực thi trong AutoCAD (Đợt A–F, `docs/sheets-presentation.md`): `cadguard sheets <dxf> [--render <thư mục>]`, `cadguard unicode <dxf|dwg> [--sheets] [--yes] [--dwg]`, `cadguard template learn|check|apply <dxf>`, `cadguard translate <dxf> --to en|zh`, `cadguard rule-set <mã> --disable|--severity|--param`, `cadguard learn-layers <dxf>`, `cadguard autocad-run unicode|translate|template|check` (gọi từ CGUNICODE/CGDICH/CGTRINHBAY/CGKIEM)
- Đồ thị tri thức bản vẽ + cổng sẵn sàng (P1, `plans/cad-guard-kg-3d-production.md`): `python -m cadguard graph <dxf> [--json] [--out tệp.json]` (`graph.py`, `cg.drawing-graph/1`; app: nút Bản đồ, `/api/graph`, lưu `.cadguard/graph/`). Sửa hàng loạt bắt buộc sao lưu: `app/bulkfix.py` (`/api/fix/bulk/plan|apply|folder`); hướng dẫn lỗi: `app/guidance.py` (mã hành động phải khớp `NOTICE_ACTIONS` trong `app.js`, test kiểm); P2 đề xuất bổ sung đồ thị: `graph_ai.py` (`cg.graph-proposals/1`: 4 agent views/links/materials/review, gợi ý code + AI, harness `check`, chỉ ghi khi người dùng Đồng ý: ghép hình → `.cadguard/scene/`, còn lại → `.cadguard/graph/<băm>.overrides.json`), app `app/graph_api.py` (`/api/graph/suggest|proposals|decide`), công cụ trợ lý `get_drawing_graph` (lọc ẩn danh, test kiểm); AI dùng `studio/llm.all_backends` (một AI lỗi thì sang AI khác; Codex CLI chỉ khi người dùng đã bật thử nghiệm)
- P3 + đối chiếu 2D↔3D: hồ sơ kết cấu xưởng `construction.py` (`cg.construction/1`, mặc định có nguồn, lưu máy/dự án; app `/api/construction`, màn Kết cấu xưởng), tấm ván + danh sách cắt + bản lề `scene/panels.py` (`/api/scene/cutlist`), nguồn từng khối + hình 2D gốc `app/scene_api.py` (`provenance`, `/api/scene/source`), sửa số đo khối `module:<id>:w|d|h|z0`, chọn mặt đứng dựng `main:<hạng mục>` (giá trị `reset` để bỏ); thanh công cụ theo phòng (`syncToolbar` trong `app.js`); AI theo trợ lý người dùng chọn (`studio/llm.all_backends(prefer=…)`)
- Studio (web cục bộ, LLM xem nội dung bản vẽ sau khi đồng ý từng phiên, dựng 3D, bổ sung phần thiếu): `python -m cadguard studio [--backend auto|api|cli|none]` (`plans/cad-guard-3d.md` mục 3c)

macOS/Linux: thay `.venv\Scripts\` bằng `.venv/bin/`.

## Cấu trúc

- `packages/core/cadguard/`: `contracts.py` (hợp đồng `cg.audit/1` dùng chung cho CLI/App/trợ lý; dẫn lại `cg.drawing/1`, `cg.changeset/1`, `cg.scene/1`), `agent/registry.py` (sổ khai báo công cụ DUY NHẤT cho MCP và engine API), `limits.py`, `watch.py`, `autocad/cadguard.lsp`, `model.py` (Drawing Model `cg.drawing/1`, `docs/drawing-model.md`), `dxf_reader.py` (DXF → mô hình qua ezdxf), `dxf_stream.py` (bộ đọc theo dòng cho tệp rất lớn, phải khớp `dxf_reader` trên mọi fixture: trường mới thêm vào mô hình phải cài ở **cả hai** bộ đọc), `rules/` (mỗi luật một hàm `@rule("<mã>")`), `standard.py` (nạp `standards/*.yaml`, hồ sơ công ty), `runner.py`, `report.py` (JSON + HTML tiếng Việt), `changeset/` (đề xuất/áp dụng/hoàn tác), `agent/` (công cụ trợ lý + ẩn danh), `mcp_server.py`, `assistant/` (engine CLI/API, khoá), `app/` (giao diện cục bộ), `scene/` (dựng 3D), `studio/` (web cục bộ + LLM), `telemetry.py`, `stats.py`, `fixtures.py`, `cli.py`; Đợt A–F: `rule_config.py` (cài đặt luật), `privacy.py` (chế độ dữ liệu), `sheets.py` (chỉ mục tờ), `textcodec.py` + `unicode_convert.py`, `sheet_render.py`, `dwg.py` (accoreconsole), `template.py` + `rules/presentation.py` (gói `sheet-layout-v0`), `translate.py`, `autocad/executor.py` (áp changeset qua COM).
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
- **Định hướng 10/11/2026: công cụ nội bộ công ty, chạy cục bộ** (`plans/cad-guard-sheets-presentation.md` mục 5, `PLAN.md` mục 1). Các rào dưới đây đã được viết lại theo quyết định đó.
- Phát hiện lỗi bằng code tất định. LLM được đọc nội dung, nhận xét, đề xuất sửa, dịch; đúng/sai của luật vẫn do code tính, nhận xét của LLM hiển thị riêng.
- Test chỉ dùng DXF tổng hợp tạo bằng ezdxf; **không commit bản vẽ thật vào git**, không đưa vào test/telemetry. Agent phát triển được đọc bản vẽ thật ở thư mục ngoài repo (vd. phiên chạy thử) để chẩn đoán và đo, chỉ ghi lại con số cấu trúc vào tài liệu. Bản vẽ thật để ở thư mục ngoài repo (xem `docs/samples-intake.md`).
- Mọi luật có id ổn định, nguồn, mức độ. Tệp chuẩn trong `standards/` là mặc định có phiên bản; người dùng sửa bật/tắt, mức độ, ngưỡng trên giao diện (không tài khoản), lưu ở cài đặt dự án/máy (`rule_config.py`, `cg.rule-settings/1`) kèm nhật ký, không sửa tệp chuẩn. Đổi mặc định của chuẩn vẫn = tạo phiên bản chuẩn mới.
- Người dùng được tự bật `realtime_ok`; luật chưa đo độ chính xác hiện nhãn "chưa đo".
- Không sửa bản vẽ nếu thiếu bước xem trước + xác nhận + hoàn tác; chỉnh sửa luôn ghi ra tệp **mới**.
- Telemetry và số xuất ra ngoài chỉ là số tổng hợp, không tên tệp/khách/thợ vẽ, không đường dẫn (dùng mã băm).
- Trợ lý (MCP, `ask`, `app`) mặc định chế độ **nội bộ** (thấy nội dung thật). Ẩn danh Bậc 1 là công tắc theo dự án (`privacy.py`, `.cadguard/project.yaml`, cờ `--anonymize`) cho hồ sơ NDA: khi bật, kết quả công cụ không có tên thật, chữ, giá trị thuộc tính hay toạ độ (`agent/tools.py` dùng danh sách trắng trường); trường mới chứa nội dung bản vẽ không được tự lọt ra ở chế độ này, có test chặn. Thêm/sửa công cụ trợ lý chỉ ở `agent/registry.py` (MCP và engine API sinh từ đó; test kiểm trùng khớp); số lỗi hiển thị ở mọi nơi lấy từ `contracts.audit_report`, không tự đếm lại.
- Không ghi khoá API/token ra tệp; mọi khoá đọc qua `assistant/keys.py` (biến môi trường hoặc kho khoá hệ điều hành). Đọc/ghi DWG ưu tiên `accoreconsole` của AutoCAD đã cài (`dwg.py`); thư viện DWG copyleft/phi thương mại chỉ được gọi như chương trình ngoài khi dùng nội bộ, phải gỡ nếu phát hành ra ngoài (xem `docs/licenses.md`).
- Không `git push`. Thông báo cho người dùng bằng tiếng Việt; tên hàm/biến bằng tiếng Anh.
