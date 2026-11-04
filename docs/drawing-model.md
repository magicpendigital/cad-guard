# Giao diện Drawing Model mở rộng

Schema vẫn là `cg.drawing/1`. Các trường mới có mặc định để đọc JSON cũ. Tên khối được so sánh không phân biệt hoa thường khi tính độ sâu. Luật nên đọc `model.stats`/`model.blocks`/`model.styles` để chạy được với cả hai đường đọc; `entities` có thể bị cắt trần ở đường stream (`stats.entity_records_truncated`). Khi `stats` là `None`, dữ liệu thống kê không có sẵn, không được coi là số 0.

| Trường | Kiểu; mặc định | Ý nghĩa |
| --- | --- | --- |
| `layers[].xref_dependent` | bool; false | Cờ 70 bit 16 hoặc tên có `|` hay `$0$`. |
| `layers[].xref_name` | string/null; null | Phần trước dấu phân cách đầu tiên; null nếu không có dấu. |
| `entities[].color` | int/null; null | Mã 62; 256 là ByLayer, 0 là ByBlock. |
| `entities[].lineweight` | int/null; null | Mã 370; -1/-2/-3 lần lượt là ByLayer/ByBlock/Default. |
| `entities[].true_color` | int/null; null | Mã 420. |
| `styles` | list; [] | Kiểu chữ, không gồm STYLE có cờ 70 bit 1. |
| `styles[].name` | string; bắt buộc | Tên kiểu. |
| `styles[].font`, `bigfont` | string; "" | Tên phông chính và phông lớn. |
| `styles[].font_kind` | enum; `none` | Đuôi phông chính không phân biệt hoa thường: shx, ttf (ttf/ttc/otf), other, none nếu rỗng. Không xác nhận mã hóa Unicode. |
| `dim_styles` | list[string]; [] | Tên các kiểu kích thước trong bảng DIMSTYLE. |
| `blocks` | list; [] | Một bản ghi mỗi định nghĩa khối, kể cả khối layout. |
| `blocks[].name` | string; bắt buộc | Tên định nghĩa. |
| `blocks[].kind` | enum; bắt buộc | `named`, `anon_U`, `anon_D`, `anon_X`, `anon_A`, `anon_other`; phân loại theo tiền tố tên. |
| `blocks[].is_xref`, `is_layout` | bool; false | Cờ khối xref bit 4; tên `*Model_Space` hoặc bắt đầu bằng `*Paper_Space` là layout, không phân biệt hoa thường. |
| `blocks[].entity_count` | int; 0 | Số đối tượng trực tiếp trong định nghĩa, không bung INSERT. Khối layout để 0. |
| `blocks[].types`, `layers`, `child_blocks` | map[string,int]; {} | Số trực tiếp theo loại, layer, và tên khối được INSERT; khối layout để rỗng. |
| `blocks[].depth` | int; 0 | Số cạnh tối đa tới khối lá; bỏ cạnh tới khối đã có trên đường đi, bỏ tham chiếu không tồn tại. Khối layout bằng 0. |
| `stats` | ModelStats/null; null | Thống kê đầy đủ, null nếu nguồn cũ không cung cấp. |
| `stats.source` | `ezdxf`/`stream`; bắt buộc | Đường đọc. |
| `stats.modelspace`, `paperspace`, `blocks` | SpaceStats; bắt buộc | Đối tượng trực tiếp trong model, mọi layout giấy, hoặc mọi định nghĩa khối ngoài layout. |
| `stats.blocks_named`, `blocks_anonymous`, `blocks_xref` | int; 0 | Số định nghĩa theo loại; xref có thể đồng thời là named. Không tính layout. |
| `stats.max_block_depth` | int; 0 | Độ sâu lớn nhất trong các khối ngoài layout. |
| `stats.layers_xref_dependent`, `shape_styles` | int; 0 | Số layer phụ thuộc xref và STYLE có cờ hình bit 1. |
| `stats.entity_records_truncated` | bool; false | Danh sách entities bị cắt trần; thống kê vẫn tính toàn bộ. |
| `stats.text_non_ascii_by_style` | map[string,int]; {} | Số TEXT/MTEXT có ký tự ngoài ASCII (hoặc mã `\U+`/`\M+`), theo tên kiểu chữ ghi trên đối tượng (thiếu = `Standard`); tính cả model, layout giấy và định nghĩa khối. MTEXT xét mã 1 và 3. Không tính ATTRIB/ATTDEF. Dùng cho VS-07. |

Trong mỗi `SpaceStats`:

| Trường | Kiểu; mặc định | Định nghĩa đếm |
| --- | --- | --- |
| `entities` | int; 0 | Tổng đối tượng trực tiếp, không tính ATTRIB, VERTEX, SEQEND; tính VIEWPORT giấy. |
| `by_type`, `by_layer` | map[string,int]; {} | Phân bố theo loại DXF và layer, cùng tập với entities; layer thiếu mặc định `0`. |
| `color_override` | int; 0 | Có mã 62 khác 256, kể cả 0. |
| `lineweight_override` | int; 0 | Có mã 370 ngoài {-1,-2,-3}. |
| `true_color` | int; 0 | Có mã 420, kể cả giá trị 0. |
| `dim_total`, `dim_text_override` | int; 0 | Số DIMENSION; số DIMENSION có mã 1 khác rỗng và `<>`. |
| `wipeout`, `image`, `ole`, `proxy` | int; 0 | Lần lượt WIPEOUT, IMAGE, tổng OLE2FRAME + OLEFRAME, và ACAD_PROXY_ENTITY. |

Khối chỉ đếm mỗi định nghĩa một lần, không nhân theo số INSERT. `entities` giữ ngữ nghĩa cũ: chỉ model/layout giấy và không chứa VIEWPORT; `block_layers` giữ ngữ nghĩa cũ, chỉ layer trong khối tên thường.

## Dành cho Luồng 3

Đã cài thành chuẩn `design-hygiene-v0` (VS-01…VS-07, xem `standards/design-hygiene-v0.md`); bảng dưới là thiết kế ban đầu, cách tính thật xem tệp chuẩn.

| Luật vệ sinh dự kiến | Trường cần dùng |
| --- | --- |
| Layer dư xref | `layers[].xref_dependent`, `xref_name`, đối chiếu `stats.*.by_layer` và `blocks[].layers`. |
| Số kiểu chữ/kích thước | Độ dài `styles`, `dim_styles`; `stats.shape_styles` riêng. |
| Tỉ lệ trên layer 0 | `stats.modelspace.by_layer.get("0", 0) / stats.modelspace.entities`; xử lý mẫu số 0. |
| Ghi đè màu/nét | `stats.modelspace`, `paperspace`, `blocks`: `color_override`, `lineweight_override`, `true_color`. |
| WIPEOUT/IMAGE/OLE | Các bộ đếm cùng tên trong từng `SpaceStats`. |
| Chữ ghi đè kích thước | `dim_text_override` và `dim_total` trong từng `SpaceStats`. |
| Phông không Unicode | `styles[].font`, `bigfont`, `font_kind`; cần danh sách phông hoặc quy tắc mã hóa đã xác minh, đuôi tệp không đủ kết luận. |
