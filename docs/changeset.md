# Changeset: sửa bản vẽ an toàn (A2)

Trạng thái: bản đầu (04/11/2026). Mã nguồn: `packages/core/cadguard/changeset/` (`ops.py`, `engine.py`, `diff.py`, `validate.py`, `apply.py`). Test: `tests/test_changeset.py`, `tests/test_diff.py`, `tests/test_mcp_server.py`.

## 1. Quy trình

Theo `AGENTS.md`: không sửa bản vẽ nếu thiếu **xem trước + xác nhận + hoàn tác**; chỉnh sửa luôn ghi ra **tệp mới**.

```text
Đề xuất (trợ lý qua MCP, hoặc người qua CLI)      → changeset JSON + xem trước   (không ghi DXF)
Người xem trước, xác nhận: cadguard apply <mã>    → <tên>.cg-<mã ngắn>.dxf      (tệp gốc giữ nguyên)
Tự động kiểm tệp ra (validate_output)              → không đạt thì không tạo tệp
Hoàn tác: cadguard undo <mã>                       → xoá đúng tệp mới đó
```

| Bước | Lệnh / công cụ | Ghi gì |
| --- | --- | --- |
| Đề xuất | `cadguard propose <tệp> --ops <ops.json>`; MCP `propose_changeset` (khi bật `--allow-propose`) | `<thư mục làm việc>/.cadguard/changesets/<mã>.json` |
| Áp dụng | `cadguard apply <mã \| đường dẫn changeset> [--yes]` | tệp mới cạnh tệp gốc (hoặc `--out-dir`), nhật ký `<mã>.apply.json` |
| Kiểm lại | `cadguard validate <gốc> <tệp ra> --changeset <mã>` | không ghi |
| So sánh | `cadguard diff a b`; MCP `diff` | không ghi |
| Hoàn tác | `cadguard undo <mã> [--yes]` | xoá tệp ra, đánh dấu `undone_at` trong nhật ký |

`apply` không có `--yes` thì in xem trước và hỏi; gõ `co` (hoặc `có`, `c`, `y`, `yes`) để đồng ý. Không chạy tương tác (ống dẫn, tác vụ nền, thiết bị NUL của Windows) mà không có `--yes` thì **từ chối**.

## 2. Định dạng `cg.changeset/1`

```json
{
  "schema": "cg.changeset/1",
  "id": "cs-2182a1853817",
  "source": {"path": "hygiene_bad.dxf", "sha256": "<64 ký tự hex>"},
  "standard": "design-hygiene-v0",
  "standard_version": "0.1.0",
  "profile": null,
  "protection": {"layers": ["KHUNG-TEN"], "patterns": ["^KHUNG-"]},
  "ops": [
    {"op": "set_bylayer", "filter": {"layers": ["SYN-TUONG"]}, "color": true, "lineweight": true}
  ],
  "created_by": "agent",
  "created_at": "2026-11-04T08:00:00+00:00",
  "preview": {"...": "kết quả chạy khô, xem mục 4"}
}
```

- `source.path` là đường dẫn **tương đối** trong thư mục làm việc; không có đường dẫn tuyệt đối. `sha256` là mã băm SHA-256 đầy đủ của tệp gốc lúc đề xuất.
- `standard`, `standard_version`, `profile`: chuẩn và hồ sơ công ty dùng để dự báo luật. Áp dụng với hồ sơ khác (hoặc thiếu hồ sơ) thì bị từ chối.
- `protection`: layer bảo vệ (tên chính xác, không phân biệt hoa/thường) và mẫu regex lấy từ hồ sơ công ty (`layer_patterns.protected`). Ghi vào changeset để lúc áp dụng dùng đúng bộ đó.
- `created_by`: `agent` (qua MCP) hoặc `user` (qua CLI).
- Changeset lưu trên đĩa dùng **tên thật** (nằm ở máy khách). Tên ẩn danh do trợ lý gửi được giải mã trước khi lưu.
- Mã changeset `cs-` + 12 ký tự hex; mã ngắn (8 ký tự) nằm trong tên tệp ra.

Nhật ký áp dụng `cg.changeset-apply/1` (`<mã>.apply.json`): mã changeset, thời điểm, `source` (đường dẫn tương đối + mã băm vào), `output` (đường dẫn tương đối + mã băm ra), báo cáo từng thao tác, kết quả kiểm, `undone_at`.

## 3. Từ vựng thao tác (cố định)

Chọn **A** trong `plans/cad-guard-agent.md` mục 3.2: chỉ các thao tác dưới đây, không có kịch bản ezdxf tự do. **Không có thao tác xoá đối tượng hình học.**

| Thao tác | Tham số | Luật sửa được | Thuộc tính đối tượng được đổi |
| --- | --- | --- | --- |
| `rename_layer` | `from`, `to` (chưa tồn tại) | VS-01 | `layer` |
| `merge_layers` | `sources[]`, `target` (đã có) | VS-01 | `layer`; xoá định nghĩa layer nguồn |
| `move_to_layer` | `filter`, `target` (đã có) | VS-03 | `layer` |
| `set_bylayer` | `filter`, `color` (true), `lineweight` (true) | VS-04 | `color`, `true_color`, `color_name`, `lineweight` |
| `replace_text_style` | `filter`, `from[]` (tuỳ chọn), `to` (kiểu đã có) | VS-07, VS-02 (cùng `purge_unused`) | `style` (TEXT, MTEXT) |
| `replace_dim_style` | `filter`, `from[]`, `to` (kiểu đã có), `rerender` (true) | VS-02 (cùng `purge_unused`) | `dimstyle`, `geometry`, `text_midpoint` |
| `purge_unused` | `kinds[]` (`layers`, `text_styles`, `dim_styles`, `blocks`; mặc định cả bốn), `names[]` (tuỳ chọn) | VS-01, VS-02 | không đổi đối tượng; chỉ xoá **định nghĩa** không được tham chiếu |
| `set_text_height` | `filter`, `from_height` (tuỳ chọn), `to` | (chưa có luật chiều cao chữ được cài) | `height` (TEXT), `char_height` (MTEXT) |
| `clear_dim_text_override` | `filter`, `rerender` (true) | VS-06 | `text` (về `<>`), `geometry`, `text_midpoint` |

Bộ lọc `filter` (mọi khoá tuỳ chọn; AND giữa khoá, OR trong danh sách; tên không phân biệt hoa/thường):

- `layers`, `exclude_layers`: tên layer;
- `types`: loại DXF (`LINE`, `TEXT`…); thao tác chữ chỉ nhận `TEXT`/`MTEXT`, thao tác kích thước chỉ nhận `DIMENSION`;
- `spaces`: `Model` hoặc tên layout.

Bộ lọc chỉ chọn đối tượng **trực tiếp** trong không gian mô hình và giấy (không vào nội dung định nghĩa khối, không chọn VIEWPORT). Thứ tự thao tác là thứ tự trong danh sách; tối đa 50 thao tác mỗi changeset.

`purge_unused` coi một định nghĩa là "đang dùng" nếu **bất kỳ** đối tượng, định nghĩa khác, XDATA hay biến tiêu đề nào nhắc tới tên hoặc handle của nó (bảo thủ: thà giữ thừa còn hơn xoá nhầm). Không bao giờ xoá: layer `0`, `Defpoints`, layer bảo vệ, layer/khối phụ thuộc xref, kiểu `Standard`, kiểu hình (shape), khối ẩn danh (`*…`), khối layout. Xoá khối có thể giải phóng layer/kiểu chữ, nên `purge_unused` lặp tới khi ổn định.

Ví dụ tệp `ops.json` dọn `hygiene_bad.dxf`:

```json
{"ops": [
  {"op": "merge_layers", "sources": ["SYNX1|SYN-TUONG", "SYNX2$0$SYN-CUA"], "target": "SYN-TUONG"},
  {"op": "move_to_layer", "filter": {"layers": ["0"], "spaces": ["Model"]}, "target": "SYN-NOI-THAT"},
  {"op": "set_bylayer", "filter": {"layers": ["SYN-TUONG"]}},
  {"op": "replace_text_style", "from": ["SYN-VN-SHX"], "to": "SYN-CHU"},
  {"op": "clear_dim_text_override"},
  {"op": "purge_unused"}
 ],
 "protected_layers": ["KHUNG-TEN"]}
```

Xem trước của ví dụ này trên `hygiene_bad.dxf` (số liệu thật từ test): 9 đối tượng đổi (layer ×3, màu ×4, độ dày nét ×4, kiểu chữ ×1, chữ kích thước ×1), 0 thêm, 0 xoá; xoá định nghĩa: 2 layer, 25 kiểu chữ, 10 kiểu kích thước; luật hết VS-01, VS-02, VS-03, VS-04, VS-06, VS-07; còn VS-05 (11 IMAGE: muốn bớt phải xoá đối tượng, việc này người dùng tự làm trong CAD); `rules_regressed` = 0.

Thông báo lỗi schema bằng tiếng Việt, ví dụ: `Thao tác sai: thao tác [0].op: 'delete_entities' không có trong từ vựng thao tác (có: rename_layer, …).`

## 4. Xem trước (chạy khô) và `validate_output`

`propose` đọc tệp gốc hai lần vào bộ nhớ, áp thao tác lên một bản, rồi so hai bản bằng chính bộ kiểm của `validate_output`. Xem trước gồm: số đối tượng bị ảnh hưởng theo từng thao tác (và số bị bỏ qua vì layer bảo vệ), diff dạng số liệu, định nghĩa thêm/xoá, số phát hiện theo luật trước/sau, luật hết/giảm/xuất hiện mới, kết quả từng mục kiểm, tóm tắt tiếng Việt.

`validate_output(gốc, tệp ra, changeset)` mở lại hai tệp và kiểm:

| Mục | Đạt khi |
| --- | --- |
| `source_hash` | tệp gốc còn đúng mã băm trong changeset |
| `entity_count` | không đối tượng nào thêm hoặc mất (trừ nội dung khối bị purge); số theo loại trong không gian mô hình/giấy bằng nhau |
| `allowed_attrs` | mọi thuộc tính bị đổi nằm trong tập thuộc tính của các thao tác (bảng mục 3); đổi dữ liệu không tên (đỉnh, XDATA) là KHÔNG đạt |
| `protected_layers` | không đối tượng nào đang ở (hoặc bị chuyển vào) layer bảo vệ bị đổi; định nghĩa layer bảo vệ không đổi |
| `definitions` | định nghĩa chỉ thêm/xoá theo thao tác (đổi tên, gộp, purge), không định nghĩa nào bị sửa |
| `rules` | chạy lại luật của chuẩn (+ hồ sơ): `rules_regressed` = số luật xuất hiện mới hoặc tăng số phát hiện = 0 |

`apply` luôn ghi ra tệp tạm, chạy `validate_output`, và chỉ tạo tệp mới khi **đạt**. Một changeset mà xem trước báo `rules_regressed` > 0 thì `apply` từ chối.

## 5. An toàn

- **Không ghi đè**: tệp ra tạo bằng chế độ độc quyền (đã có tên đó thì từ chối, không ghi đè). Mỗi changeset chỉ áp một lần.
- **Tệp gốc không bao giờ bị ghi**: kiểm mã băm trước và sau khi áp; test kiểm mã băm gốc trước/sau.
- **Nguồn đổi sau khi đề xuất** (mã băm khác) → từ chối áp; phải đề xuất lại trên tệp hiện tại.
- **Layer bảo vệ** (tham số changeset `protected_layers`/`--protect` + hồ sơ công ty `layer_patterns.protected`): thao tác nêu tên layer bảo vệ (bộ lọc `layers`, nguồn, đích, `purge_unused.names`) bị từ chối; bộ lọc rộng quét trúng đối tượng trên layer bảo vệ thì bỏ qua đối tượng đó và báo số `skipped_protected`.
- **Không có công cụ xoá đối tượng hình học** (plans/cad-guard-agent.md mục 5.2).
- **Không có `apply_changeset` qua MCP.** Lý do: (1) trợ lý chỉ giải thích/đề xuất, không ra quyết định sửa bản vẽ sản xuất (`AGENTS.md`); (2) "xác nhận" phải là hành động của người, không phải một tham số trợ lý tự điền; (3) CLI trợ lý có thể tự chạy nhiều vòng, nên công cụ ghi qua MCP biến xác nhận thành hình thức. Áp dụng chỉ qua `cadguard apply` (hoặc ứng dụng V2 sau này) do người chạy.
- MCP mặc định vẫn **chỉ đọc** (6 công cụ, thêm `diff`). `propose_changeset` chỉ có khi máy chủ chạy với `--allow-propose`; nó chỉ ghi changeset JSON vào `.cadguard/changesets/` của thư mục làm việc, không ghi DXF.
- **Ẩn danh Bậc 1**: đầu ra MCP dùng mã phiên (`L_…` layer, `S_…` kiểu chữ, `D_…` kiểu kích thước, `B_…` khối, `Y_…` layout, `F_…` tệp); chữ trong bản vẽ bị che trong `diff`. Trợ lý gửi thao tác bằng mã phiên; máy chủ giải mã về tên thật trước khi lưu. Mã sai hoặc của phiên khác → lỗi "không khớp tên nào". Tên mới (ví dụ `rename_layer.to`) là tên thường.
- Changeset, nhật ký, thông báo lỗi không chứa đường dẫn tuyệt đối.

## 6. Giới hạn đã biết

- Đọc/ghi bằng ezdxf (nạp trọn tệp); chưa dùng bộ đọc theo dòng cho tệp rất lớn.
- `rerender` vẽ lại khối hình kích thước bằng bộ vẽ của ezdxf; hình kích thước có thể hơi khác cách AutoCAD vẽ (vị trí chữ). Đặt `rerender: false` để giữ khối cũ (khi đó phần mềm CAD hiển thị số cũ tới khi kích thước được cập nhật).
- Đổi kiểu chữ của chữ trong DIMENSION (ghi đè `dimtxsty`) và của ATTRIB/ATTDEF chưa hỗ trợ; thao tác chữ chỉ chạm TEXT/MTEXT trực tiếp trong không gian mô hình/giấy.
- `rename_layer` dùng `Layer.rename` của ezdxf: tham chiếu layer trong dữ liệu của bên thứ ba (XDATA, XRECORD lạ) có thể còn tên cũ.
- Định dạng MTEXT nội tuyến (`\H`, `\f`) không bị đổi bởi `set_text_height`/`replace_text_style`.
- Chưa có thao tác cho VS-05 (WIPEOUT/IMAGE/OLE): bớt chúng là xoá đối tượng, ngoài từ vựng.
