# Giấy phép các thành phần

Cập nhật khi thêm phụ thuộc. Nguyên tắc: không đưa vào sản phẩm thành phần có giấy phép copyleft hoặc phi thương mại mà chưa có ý kiến pháp lý.

## Đang dùng

| Thành phần | Dùng để | Giấy phép | Ghi chú |
| --- | --- | --- | --- |
| ezdxf | Đọc/ghi DXF | MIT | Lõi chỉ xử lý DXF. DWG chỉ qua add-on `odafc` (không dùng) |
| Pillow 13.0.0 (yêu cầu >=10.4) | Phụ thuộc renderer ezdxf, xử lý QR | MIT-CMU | Kiểm metadata cài ngày 05/11/2026: License-Expression MIT-CMU; không cài toàn bộ extras draw của ezdxf |
| qrcode 8.2 (yêu cầu >=8) | QR link nội bộ, dựng cục bộ | BSD | Kiểm metadata cài ngày 05/11/2026: License BSD |
| pydantic | Mô hình dữ liệu | MIT | |
| PyYAML | Nạp chuẩn | MIT | |
| pytest (dev) | Test | MIT | |
| keyring 25.7.0 (extras tuỳ chọn `[keyring]`) | Kho khoá hệ điều hành cho `cadguard keys` (import lười, không bắt buộc) | MIT | Đã kiểm 04/11/2026 trong `keyring-25.7.0.dist-info` (`License-Expression: MIT`, `licenses/LICENSE`). Bắc cầu trên Windows: jaraco.classes 3.4.0 (MIT, classifier), jaraco.context 6.1.2, jaraco.functools 4.6.0, more-itertools 11.2.1 (MIT), pywin32-ctypes 0.2.3 (BSD-3-Clause, chỉ Windows). Trên Linux/macOS còn kéo SecretStorage/jeepney… — **chưa kiểm** |
| mcp 1.30.0 (extras `[agent]`) | SDK MCP chính thức cho Python, chạy `python -m cadguard mcp` | MIT | Đã kiểm 04/11/2026 trong `mcp-1.30.0.dist-info` (METADATA `License: MIT`, `licenses/LICENSE` "Copyright (c) 2024 Anthropic, PBC"). Ràng buộc `mcp>=1.10,<2` |

(Giấy phép trên ghi theo hiểu biết hiện tại; kiểm lại tệp LICENSE của từng gói đã cài trước khi phát hành.)

### Phụ thuộc bắc cầu của extras `[agent]`

Kiểm 04/11/2026 bằng `importlib.metadata` trên venv đã cài `python scripts/test.py --extras agent` (Python 3.13, Windows): đọc `License-Expression`/`License`/classifier và tệp trong `*.dist-info/licenses/`.

| Gói (phiên bản) | Giấy phép | Ghi chú |
| --- | --- | --- |
| anyio 4.16.0, httpx-sse 0.4.3, jsonschema 4.26.0, jsonschema-specifications 2025.9.1, referencing 0.37.0, rpds-py 2026.9.1, attrs 26.1.0, pydantic-settings 2.16.2, typing-inspection 0.4.4, PyJWT 2.15.1, h11 0.16.0 | MIT | |
| cffi 2.1.1 | MIT-0 | qua `pyjwt[crypto]` → cryptography |
| httpx 0.28.1, httpcore 1.0.9, idna 3.20, starlette 1.10.0, sse-starlette 3.6.0, uvicorn 0.54.0, python-dotenv 1.2.4, click 8.5.0, pycparser 3.12 | BSD-3-Clause | colorama 0.4.6: BSD (Windows) |
| python-multipart 0.0.33 | Apache-2.0 | |
| cryptography 50.0.2 | Apache-2.0 OR BSD-3-Clause | |
| typing_extensions 4.16.0 | PSF-2.0 | đã có sẵn qua pydantic; giấy phép dễ dãi |
| **pywin32 312** | **PSF** | chỉ trên Windows (`mcp` khai báo `sys_platform == 'win32'`); dễ dãi nhưng ngoài danh sách MIT/BSD/Apache |
| **certifi 2026.10.23** | **MPL-2.0** | qua httpx; copyleft yếu theo từng tệp (dùng nguyên bản, không sửa thì chỉ cần giữ thông báo). Máy chủ stdio không dùng HTTP nhưng gói vẫn được cài. **Cần ý kiến pháp lý trước khi phân phối bản đóng gói có extras `[agent]`** |

### SDK `anthropic` (nhánh studio) — đã kiểm, KHÔNG dùng

Nhánh dựng 3D/studio ban đầu khai báo extras `llm = ["anthropic>=0.40"]`. Khi tích hợp (05/11/2026), `cadguard studio` chuyển sang gọi Messages API bằng thư viện chuẩn qua `assistant/api_engines.post_json` (cùng đường với `cadguard ask`/`app`) và đọc khoá bằng `assistant/keys.py`, nên **bỏ extras `llm`; cad-guard không phụ thuộc SDK `anthropic`**. Giấy phép vẫn được kiểm để lưu hồ sơ nếu sau này dùng lại.

Kiểm 05/11/2026 bằng `importlib.metadata` trên venv `CADGUARD_VENV` (Python 3.13, Windows) sau `pip install "anthropic>=0.40"` (bản cài được: 2.5.0), rồi gỡ:

| Gói (phiên bản) | Giấy phép | Ghi chú |
| --- | --- | --- |
| anthropic 2.5.0 | Apache-2.0 | `licenses/LICENSE` (Apache-2.0) và `licenses/LICENSE-MIT` |
| httpx2 2.16.0, httpcore2 2.16.0, idna 3.20 | BSD-3-Clause | bản 2.x của SDK dùng `httpx2`, không kéo `httpx`/`certifi` |
| truststore 0.10.5, jiter 0.18.0, anyio 4.16.0, h11 0.16.0, docstring_parser 0.18.0, pydantic 2.14.2 (+ pydantic_core, annotated-types, typing-inspection) | MIT | truststore dùng kho chứng chỉ của hệ điều hành |
| sniffio 1.3.1 | MIT OR Apache-2.0 | |
| opentelemetry-api 1.45.2 | Apache-2.0 | |
| typing_extensions 4.16.0 | PSF-2.0 | đã có sẵn qua pydantic |

Kết luận: toàn bộ MIT/BSD/Apache (+ PSF dễ dãi), không có copyleft; không có certifi. Bản `anthropic` cũ hơn (0.x) dùng `httpx` nên kéo certifi (MPL-2.0, xem mục "Cần quyết"): nếu dùng lại SDK thì ghim `anthropic>=2` và kiểm lại.

## Đã xem xét và KHÔNG dùng

| Thành phần | Lý do |
| --- | --- |
| ODA File Converter | Chỉ miễn phí cho mục đích **phi thương mại** nếu không là thành viên ODA; không được phân phối lại (kiểm ngày 02/11/2026 trên trang FAQ của ODA) |
| LibreDWG | GPLv3+ (ràng buộc cách phân phối sản phẩm); đọc DWG r1.2–r2018 nhưng ghi mặc định chỉ r2000 trở xuống; DXF nó sinh ra có tệp AutoCAD nhập lỗi (theo sổ tay GNU) |
| Fork LibreCAD/QCAD/FreeCAD | Ngoài hướng đã chọn (xem `plans/cad-guard-direction.md`); giấy phép copyleft chưa kiểm |
| SDK `anthropic` (extras `llm` cũ của studio) | Không cần: studio gọi API bằng thư viện chuẩn như trợ lý; giấy phép đã kiểm ở mục trên (Apache-2.0, bắc cầu MIT/BSD/Apache) |
| Autodesk APS Model Derivative | Gửi bản vẽ lên đám mây + tính phí theo token; trái nguyên tắc xử lý cục bộ |

## Cần quyết

- **certifi (MPL-2.0)**, kéo theo bắc cầu: SDK `mcp` → httpx → certifi. Chỉ ảnh hưởng khi **phân phối** bản đóng gói có extras `[agent]`; lõi `cadguard` (không extras) không chứa certifi, và máy chủ MCP stdio không gọi HTTP. Phương án (chưa chọn, chưa đổi phụ thuộc):
  1. Xin ý kiến pháp lý: MPL-2.0 là copyleft yếu theo từng tệp; dùng nguyên bản không sửa thường chỉ cần kèm giấy phép và chỉ nơi lấy mã nguồn của certifi.
  2. Nếu khả thi: dùng kho chứng chỉ của hệ điều hành qua `truststore` (MIT) thay cho bó chứng chỉ của certifi; phải kiểm xem httpx/`mcp` có còn bắt buộc cài certifi không (nếu vẫn bắt buộc thì phương án này không bỏ được certifi khỏi gói phân phối).

## Chưa quyết (quyết ở đầu P1b)

- Thư viện dựng hình DXF cho trình xem/rà soát (web hoặc máy tính): chọn và ghi giấy phép ở đây.
