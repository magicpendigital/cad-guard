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
- `cadguard sheets <bản vẽ> --pdf <thư mục> [--pick 1,3-5] [--ctb monochrome.ctb]`: **in PDF từng tờ qua AutoCAD**
  (`accoreconsole`, một lần mở bản vẽ, mỗi tờ một lệnh `-PLOT` cửa sổ đúng khung, khổ ISO full bleed theo khổ khung,
  vừa khổ, căn giữa). Tên tệp theo số bản vẽ của template (`NT-01.pdf`); không có template hoặc thiếu số: `To-05.pdf`;
  trùng số: thêm `-to06`. Khung hệ số lạ (1:66,87) nhận khổ theo kích thước ÷ hệ số. Không ghi đè PDF có sẵn; tờ dạng
  layout chưa hỗ trợ. Tệp phiên thử (bản sao, AutoCAD 2027): **40/40 tờ** trong 16,8 giây (27 giây cả đọc chỉ mục),
  tên theo số bản vẽ, khổ A3 420 × 297 mm. Test với AutoCAD thật: `CADGUARD_TEST_AUTOCAD=1`.
- DWG: `audit`, `sheets`, `unicode`, `translate`, `template` nhận thẳng `.dwg` khi máy có AutoCAD bản đầy đủ
  (`accoreconsole`, tự tìm qua sổ đăng ký; đặt `CADGUARD_ACCORECONSOLE` nếu cần). `--dwg` ghi thêm bản DWG của tệp mới.

## D. Template trình bày (`cg.template/1`) và gói luật `sheet-layout-v0`

- Học từ một tờ mẫu: `cadguard template learn <bản vẽ> --sheet N --logo <logo.png> --name "…" --company "…"`, hoặc nút
  **Học template từ tờ này** trên thanh Tờ của app. Lưu ở `<dự án>/.cadguard/template/` (`template.yaml`,
  `titleblock.dxf`, logo).
- Kiểm: `cadguard template check <bản vẽ>` hoặc phòng **Trình bày hồ sơ** trong app. Luật TP-01…TP-12: đúng khung, chữ ký khối, trường cố định, trường bắt buộc/mẫu, tỉ lệ cho phép, tỉ lệ ghi khớp hệ số,
  tràn vùng vẽ/đè dải khung tên, đối tượng ngoài tờ, cỡ chữ in tối thiểu, số bản vẽ trùng/sai thứ tự, hàng tờ thẳng mép
  dưới/khoảng cách đều/không chồng (TP-11, mức thông tin, không cần template; tham số `align_tol`, `gap_tol`), chữ chưa
  Unicode. Tệp phiên thử: TP-11 ra 1 phát hiện (một hàng 31 tờ, một khe khác).
- Áp dụng: `cadguard template apply <bản vẽ> [--renumber] [--attribs-only] [--yes]` hoặc các gợi ý TP ở tab Thay đổi.
  Chỉ đổi khung tên, thuộc tính và hệ số/vị trí khung; không đụng hình vẽ, kích thước, chú thích. Thao tác theo thứ tự:
  1. `replace_title_block` (TP-01): khung cũ cùng khổ được thay bằng khối template tại cùng góc dưới trái, giữ hệ số.
     Giá trị thẻ cũ chuyển sang thẻ mới theo: bảng đã học `title_block_maps: {KHỐI_CŨ: {THẺ_CŨ: THẺ_MỚI}}` trong
     `template.yaml` (sửa tay khi đoán sai), trùng tên, vai trò (giá trị dạng 1/NN → trường tỉ lệ; khớp mẫu số bản vẽ →
     trường số), tên gần giống. Ánh xạ được in trong ghi chú; thẻ cũ không có chỗ được báo. Khối chưa có trong bản vẽ
     được chép từ `titleblock.dxf` của template (kiểm mã băm lúc áp dụng).
  2. `set_sheet_scale` (TP-05, TP-06): hệ số lạ (vd. 19,77) về tỉ lệ cho phép gần nhất, giữ tâm vùng vẽ, thuộc tính
     phóng theo; **chỉ khi** nội dung vẫn nằm trong vùng vẽ và khung mới không trùm đối tượng của tờ khác.
  3. `fit_sheet` (TP-07): nội dung tràn nhưng vừa vùng vẽ thì dời khung (không dời nội dung) cho nội dung vào giữa;
     nội dung lớn hơn vùng vẽ hoặc đè dải khung tên chỉ được báo.
  4. `set_attribs` (TP-03, TP-04, TP-06, TP-10): trường cố định, tỉ lệ theo hệ số (mới), đánh số tờ (`--renumber`).
- Bước kiểm (`validate.py`, `FrameScope`) chỉ cho phép: đổi `name`/`insert`/hệ số đúng INSERT khung được nêu, đổi vị
  trí/cỡ ATTRIB của khung đó, xoá ATTRIB cũ và thêm ATTRIB mới của khung được thay, thêm khối khung tên template cùng
  layer/kiểu chữ chính khối đó dùng. Sau khi thay khung, lỗi có sẵn của tờ (vd. nội dung tràn) mới được luật TP kiểm:
  báo là "chấp nhận tăng theo thao tác", không chặn.
- Nghiệm thu trên fixture `make_model_sheets(legacy=(1,))`: sau áp dụng không còn TP-01/03/04/05/06/10; chỉ còn TP-07
  (tờ 2: nội dung 360 mm > vùng vẽ 350 mm, chỉ báo), TP-08, TP-09, TP-12 (thao tác Unicode riêng); mọi đối tượng hình
  vẽ/kích thước/chú thích giữ nguyên thuộc tính; hoàn tác xoá tệp mới, tệp gốc giữ nguyên mã băm.
- Trong AutoCAD (CGTRINHBAY) chỉ áp phần thuộc tính; thay khung/hệ số/dời khung đi đường tệp.
- Xem trước trên bản sao tệp phiên thử (chưa áp dụng): 50 đối tượng đổi (chỉ khung tên và thuộc tính), kiểm ĐẠT;
  TP-06 11 → 4, TP-07 33 → 16, TP-05 5 → 4; TP-11 1 → 7 (dời khung cho nội dung vào vùng vẽ làm hàng tờ lệch, mức thông
  tin, được báo là tác dụng phụ). 4 tờ 1:66,87 không đưa về tỉ lệ chuẩn được (nội dung sẽ tràn), 4 tờ nội dung lớn hơn
  vùng vẽ: chỉ báo.
- Template Grande A3 đã học từ tờ 2 của tệp phiên thử (kèm logo PNG) tại `D:\CadGuardPhien\phien-01\.cadguard\template`.

## E. Dịch sang Tiếng Anh / Tiếng Trung

`cadguard translate <bản vẽ> --to en|zh [--sheets …] [--mode copy|layer] [--engine auto|anthropic|claude-cli|none] [--yes]`

- Hai chế độ: `copy` (mặc định) thay chữ tại chỗ, ra `<tên>.en.dxf`; `layer` (song ngữ) **giữ nguyên chữ gốc** (kể cả
  mã TCVN3), thao tác `add_texts` thêm chữ dịch (TEXT/MTEXT) trên layer `CG-DICH-EN`/`CG-DICH-ZH`, đặt ngay dưới chữ
  gốc (1,4 lần chiều cao chữ, theo hướng xoay), kiểu chữ Unicode riêng `CG-DICH` (Be Vietnam Pro) hoặc `CG-ZH`; ra
  `<tên>.enlayer.dxf`. Tắt layer `CG-DICH-…` là về bản gốc. Thuộc tính khung tên thành TEXT tại cùng vị trí; chữ ghi
  đè kích thước không thêm được (báo số lượng). Bước kiểm chỉ cho phép thêm TEXT/MTEXT trên đúng layer đó, không quá
  số mục, mọi đối tượng có sẵn không đổi. App: chọn *Song ngữ (layer)* cạnh nút Dịch.

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

- Gộp Studio vào App chưa làm.
- Bộ thực thi AutoCAD mới thử với COM giả trong test; cần kiểm tay trên AutoCAD 2027 (danh sách ở `docs/autocad.md`).
- Phông Be Vietnam Pro chưa cài trên máy thử: AutoCAD sẽ thay phông cho tới khi cài (Google Fonts, giấy phép OFL).
