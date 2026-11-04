# Hiệu năng đọc DXF rất lớn (L2, bộ đọc theo dòng)

Ngày đo: 04/11/2026. **Chỉ dùng DXF tổng hợp** do `fixtures.make_large` sinh vào thư mục tạm (layer/khối `SYN-*`, chữ tiếng Việt tổng hợp); không dùng bản vẽ thật, không commit tệp lớn.

## Máy đo

| | |
| --- | --- |
| CPU | Intel Core i3-1115G4 @ 3,00 GHz (laptop, 2 nhân / 4 luồng) |
| RAM | 7,8 GB (lúc đo chỉ còn khoảng 0,2 GB trống vì các ứng dụng khác) |
| Hệ điều hành | Windows 11 Home |
| Phần mềm | Python 3.13.17, ezdxf 1.4.5, pydantic 2.14.2 (venv dùng chung của `scripts/test.py`) |

## Tệp thử

`fixtures.make_large(path, target_mb=100)`: DXF R2018 (UTF-8), 104.893.645 byte (100,0 MiB).

- Không gian mô hình: 146.051 đối tượng (INSERT có/không thuộc tính, LINE, LWPOLYLINE, TEXT tiếng Việt, DIMENSION; khoảng 3% kích thước ghi đè chữ, 1% LINE có Z khác 0).
- Trong định nghĩa khối: 443.193 đối tượng trong 40 khối `SYN-BLK-*` lồng nhau (khoảng 70% dung lượng tệp, giống đặc điểm "phần lớn nội dung nằm trong khối" ở `docs/real-sample-profile.md`).
- Sinh tệp mất 8 giây.

## Kết quả (đo thật)

Đo trong tiến trình con riêng: thời gian bằng `time.perf_counter`, RAM đỉnh là working set đỉnh của tiến trình (Windows `GetProcessMemoryInfo`, gọi qua `ctypes`), gồm khoảng 15 MB nền của Python.

| Phép đo | Tệp | Thời gian | RAM đỉnh |
| --- | --- | --- | --- |
| `read_dxf_stream`, lần 1 (đĩa nguội) | 100 MiB | 23,8 s | 255 MB |
| `read_dxf_stream`, test slow | 100 MiB | 12,2 s | 258 MB |
| `read_dxf_stream`, lần 3 | 100 MiB | 13,4 s | 253 MB |
| `read_dxf_stream`, lần 4 (bản cuối) | 100 MiB | 14,5 s | 271 MB |
| `read_dxf_stream`, test slow (bản cuối) | 100 MiB | 11,4 s | 265 MB |
| `cadguard audit --reader auto` (đọc + 15 luật chạy + in kết quả) | 100 MiB | 16,3 s | không đo |
| `read_dxf_stream` | 30 MiB | 7,6 s | 118 MB |
| `read_dxf` (ezdxf) | 30 MiB | 42,4 s | 396 MB |
| `read_dxf_stream` | 10 MiB | 3,8 s | 74 MB |
| `read_dxf` (ezdxf) | 10 MiB | 12,6 s | 137 MB |

Ngưỡng của test slow: < 1 GB RAM đỉnh và < 120 giây cho 100 MB: **đạt** (khoảng 26% ngưỡng RAM, khoảng 10–20% ngưỡng thời gian).

Không đo ezdxf ở 100 MiB vì máy còn rất ít RAM trống. **Ước tính (chưa đo)** theo tỉ lệ ở 10–30 MiB: khoảng 140 giây và trên 1 GB RAM.

## Nhận xét

- Trên tệp tổng hợp, đọc theo dòng nhanh hơn ezdxf khoảng 3–5 lần và dùng ít bộ nhớ hơn khoảng 2–3 lần; khoảng cách tăng theo cỡ tệp.
- Bộ nhớ chủ yếu là danh sách `entities` (khoảng 1,2 KB mỗi bản ghi). Đối tượng trong khối chỉ được đếm, không giữ bản ghi. Trần mặc định `max_entity_records = 300 000` (khoảng 350 MB); quá trần thì `stats.entity_records_truncated = True` và `audit` in lưu ý.
- Máy chủ MCP (`python -m cadguard mcp`) chọn bộ đọc cùng quy tắc với `audit --reader auto` (hàm chung `cadguard/reader_select.py`): `--stream-threshold-mb` (mặc định 50; 0 = luôn theo dòng, âm = luôn ezdxf) và `--max-entity-records`. Khi bị cắt ở trần, kết quả `audit`, `get_model_summary`, `query_model` có `records_capped: true`.
- Dữ liệu tổng hợp đơn giản hơn bản thật (không có HATCH lớn, khối động, OLE/IMAGE nhúng), nên số trên bản thật có thể khác. Chưa chạy trên bản thật (agent không được đọc dữ liệu khách). Người có quyền có thể chạy cục bộ `cadguard audit <thư mục> --reader stream` trên M1–M5 rồi ghi thêm số tổng hợp vào đây.

## Chạy lại

```
python scripts/test.py -m slow tests/test_dxf_stream.py -s
```

Test slow không chạy trong `python scripts/test.py` thường (đánh dấu `@pytest.mark.slow`, bỏ chọn bằng `-m "not slow"` trong cấu hình pytest; được báo là "deselected", không tính là bỏ qua).
