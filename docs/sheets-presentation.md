# Tờ, Unicode, template trình bày, dịch, thực thi trong AutoCAD (Đợt A–F, 10/11/2026)

Triển khai theo `plans/cad-guard-sheets-presentation.md` và câu trả lời mục 10 của chủ dự án (`PLAN.md` mục 1).
Mọi chỉnh sửa vẫn đi đường changeset: xem trước → xác nhận → tệp MỚI (hoặc một nhóm undo trong AutoCAD) → hoàn tác.

## A. Dùng nội bộ: sửa luật không tài khoản, chế độ dữ liệu

| Việc | Lệnh / nơi bấm |
| --- | --- |
| Bật/tắt luật, đổi mức độ E/W/I, sửa ngưỡng | App: màn **Luật áp dụng** → bấm luật → mục *Sửa luật* (dự án này / mọi dự án trên máy); thẻ lỗi có nút **Tắt luật**, **Sửa ngưỡng**. CLI: `cadguard rule-set LY-01 --disable`, `--severity I`, `--param max_text_styles=20`, `--reset`, `--scope machine` |
| Nhật ký thay đổi luật | `<dự án>/.cadguard/rules-log.jsonl` (máy: thư mục cấu hình cad-guard) |
| Học quy ước layer của công ty (giảm nhiễu LY-01) | App: nút **Học quy ước layer** trên thẻ LY-01. CLI: `cadguard learn-layers <bản vẽ>` |
| Chế độ dữ liệu cho trợ lý | Mặc định **nội bộ** (trợ lý thấy nội dung thật). Dự án NDA: App → Kết nối AI → *Ẩn danh Bậc 1*, hoặc `.cadguard/project.yaml: anonymize: true`, hoặc cờ `--anonymize`. Khi ẩn danh, chức năng dịch bị khoá |

App, CLI (`cadguard audit`) và MCP đọc cùng cài đặt (`rule_config.effective_standard`), nên cùng một bản vẽ ra cùng số.

## B. Chỉ mục tờ

`cadguard sheets <bản vẽ>` liệt kê tờ (layout có khung nhìn, hoặc khung tên trong Model), tiêu đề, khổ/tỉ lệ, **hệ số
khung thật** (vd. 19,773), độ tin cậy. Bộ khung tên có thuộc tính chèn nhiều lần được nhận cả tờ còn trống.
Tệp phiên thử: **40 tờ** (25 tờ 1:15, 10 tờ 1:20, 1 tờ 1:10, 4 tờ 1:66,87), khớp số người dùng đếm.

## C. Unicode, hình từng tờ, DWG

- `cadguard unicode <bản vẽ> [--sheets 1,3-5] [--yes] [--dwg]`: chuyển TCVN3/VNI sang Unicode, kiểu chữ phông cũ trỏ
  sang **Be Vietnam Pro** (cần cài phông trên máy để AutoCAD hiển thị). Nhận bảng mã theo phông của kiểu chữ (kể cả tên
  họ phông trong XDATA), mã `\f` nội tuyến của MTEXT, rồi mới đoán theo ký tự khi cả bản vẽ là TCVN3. Chuỗi không chắc
  giữ nguyên, có danh sách handle. Chạy lần hai không đổi thêm. App: gợi ý *Chuyển chữ TCVN3/VNI sang Unicode* ở tab
  Thay đổi (mặc định không chọn). Tệp phiên thử: 675 chuỗi (TEXT, MTEXT, thuộc tính, MULTILEADER), 0 không chắc.
- `cadguard sheets <bản vẽ> --render <thư mục> [--pick 1,3]`: SVG từng tờ + `index.html`, chữ mã cũ hiện đúng (giải mã
  trong bộ nhớ). 40 tờ thật: ~15 giây. `--format png|pdf` cần matplotlib (tuỳ chọn).
- DWG: `audit`, `sheets`, `unicode`, `translate`, `template` nhận thẳng `.dwg` khi máy có AutoCAD bản đầy đủ
  (`accoreconsole`, tự tìm qua sổ đăng ký; đặt `CADGUARD_ACCORECONSOLE` nếu cần). `--dwg` ghi thêm bản DWG của tệp mới.

## D. Template trình bày (`cg.template/1`) và gói luật `sheet-layout-v0`

- Học từ một tờ mẫu: `cadguard template learn <bản vẽ> --sheet N --logo <logo.png> --name "…" --company "…"`, hoặc nút
  **Học template từ tờ này** trên thanh Tờ của app. Lưu ở `<dự án>/.cadguard/template/` (`template.yaml`,
  `titleblock.dxf`, logo).
- Kiểm: `cadguard template check <bản vẽ>` hoặc phòng **Trình bày hồ sơ** trong app. Luật TP-01…TP-10, TP-12
  (TP-11 chưa cài): đúng khung, chữ ký khối, trường cố định, trường bắt buộc/mẫu, tỉ lệ cho phép, tỉ lệ ghi khớp hệ số,
  tràn vùng vẽ/đè dải khung tên, đối tượng ngoài tờ, cỡ chữ in tối thiểu, số bản vẽ trùng/sai thứ tự, chữ chưa Unicode.
- Áp dụng: `cadguard template apply <bản vẽ> [--renumber] [--yes]` hoặc gợi ý *Điền khung tên theo template* /
  *Đánh số bản vẽ lại* ở tab Thay đổi. Chỉ đổi giá trị thuộc tính khung tên; hệ số khung lạ, khung khác template được
  báo "không tự làm" (cần chỉnh trong CAD).
- Template Grande A3 đã học từ tờ 2 của tệp phiên thử (kèm logo PNG) tại `D:\CadGuardPhien\phien-01\.cadguard\template`.

## E. Dịch sang Tiếng Anh / Tiếng Trung

`cadguard translate <bản vẽ> --to en|zh [--sheets …] [--engine auto|anthropic|claude-cli|none] [--yes]`

- Ngôn ngữ nguồn tự nhận theo nội dung (Việt / Trung / Anh). Số, đơn vị, mã vật liệu, mã định dạng MTEXT được giữ
  bằng ký hiệu ⟦n⟧ và kiểm lại sau khi dịch; thiếu ký hiệu thì bản dịch bị loại.
- Bảng thuật ngữ có sẵn (nội thất) + `<dự án>/.cadguard/glossary.yaml` (`terms: [{vi, en, zh}]`), bộ nhớ dịch
  `.cadguard/translation-memory.json`. LLM chỉ đề xuất; code kiểm thuật ngữ, chữ có thể tràn khung.
- Tiếng Trung: chữ đã dịch dùng kiểu chữ `CG-ZH` (Microsoft YaHei).
- Duyệt bằng Excel: `--export-review duyet.csv`, sửa cột `target`, chạy lại với `--from-review duyet.csv`.
- Ra tệp mới `<tên>.en.dxf` / `<tên>.zh.dxf`. App: nút **Dịch** trên thanh Tờ. Trợ lý (MCP/App, cờ `--allow-propose`):
  công cụ `propose_translation` hai bước (trợ lý là người dịch, code kiểm).

## F. Thực thi trong AutoCAD (bản đầy đủ)

- Cài: `cadguard autocad --copy-to <thư mục tin cậy>` (chép `cadguard.lsp` + ghi `cadguard-run.cmd`), APPLOAD.
- Lệnh: **CGKIEM** (kiểm), **CGUNICODE**, **CGDICH** (en/zh), **CGTRINHBAY** (điền khung tên theo template).
  Mỗi lệnh: SAVE → CGXUAT tự chạy → cửa sổ cad-guard hiện xem trước → gõ `c` để áp vào bản vẽ đang mở.
- Bộ thực thi (`autocad/executor.py`): cùng changeset với đường tệp; chỉ nhận thao tác về chữ (`convert_unicode`,
  `set_texts`, `set_attribs`); bản vẽ phải đã lưu; sao lưu DWG vào `.cadguard/backup/`; chỉ áp khi chữ hiện tại của
  mọi đối tượng khớp lúc xem trước; một nhóm undo (gõ U để trả lại); không tự lưu. Không chạy LISP do trợ lý viết.

## Chưa làm / giới hạn

- Thao tác `replace_title_block`, `set_sheet_scale`, `fit_sheet` (đổi khung/hệ số/vị trí khung) và chế độ dịch `layer`
  (giữ chữ gốc, thêm chữ dịch trên layer riêng) chưa làm: cần thêm đối tượng/di chuyển hình, đi ngoài bước kiểm hiện có.
- In PDF hàng loạt theo tờ qua AutoCAD, gộp Studio vào App, TP-11 chưa làm.
- Bộ thực thi AutoCAD mới thử với COM giả trong test; cần kiểm tay trên AutoCAD 2027 (danh sách ở `docs/autocad.md`).
- Phông Be Vietnam Pro chưa cài trên máy thử: AutoCAD sẽ thay phông cho tới khi cài (Google Fonts, giấy phép OFL).
