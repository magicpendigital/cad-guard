# Thu và xử lý bản vẽ mẫu của khách

Nguyên tắc: **bản vẽ thật không bao giờ vào repo, vào brief của agent hay vào prompt.** Chúng là tài sản của khách và có thể có thông tin bảo mật.

## 1. Chỗ để

- Tạo thư mục **ngoài repo**, ví dụ `D:\CadGuardData\` với `samples\raw\` (nguyên bản), `samples\anon\` (đã ẩn danh), `reports\`.
- Không đặt trong `D:\Projects\cad-guard\`. Nếu lỡ đặt, `.gitignore` chặn `*.dwg`/`*.dxf` (trừ `fixtures/synthetic/`) nhưng đừng dựa vào đó.
- Không để thư mục này trong vùng đồng bộ đám mây công khai. Sao lưu theo quy định của công ty.

## 2. Thu thập

1. Xin bản đại diện (30–50), gồm cả bản tốt và bản từng gây lỗi. Ghi mã khách (K1, K2…) và phần mềm/bản đã tạo ra mỗi tệp vào bảng `samples\index.csv` (ngoài repo): `mã, phần mềm, bản, có DXF gốc?, ghi chú`.
2. Nếu phần mềm gốc xuất được DXF, xin **cả hai** (DWG và DXF) để so sánh đường chuyển đổi.
3. Chỉ nhận bản đã được người có thẩm quyền đồng ý (xem phiếu `docs/discovery.md` mục 4).

## 3. Ẩn danh (làm trước khi cho bất kỳ công cụ nào đọc)

Xoá hoặc thay: tên khách, địa chỉ, số điện thoại, tên dự án thật, tên người vẽ/kiểm/duyệt trong khung tên và thuộc tính, logo, ghi chú có tên riêng, đường dẫn xref tuyệt đối, tên tệp gốc (đổi thành `K1-001.dxf`). Giữ nguyên cấu trúc layer, kiểu chữ, kích thước, khối, layout, để luật còn ý nghĩa.

## 4. Chạy rà soát cục bộ

```powershell
cd D:\Projects\cad-guard\packages\core
.venv\Scripts\python -m cadguard audit D:\CadGuardData\samples\anon --out D:\CadGuardData\reports\p0.html
```

Báo cáo và telemetry chỉ lưu mã băm nội dung; tên tệp có trong báo cáo cục bộ nên **không** đưa báo cáo vào repo.

## 5. Điều không làm

- Không sao chép bản vẽ thật vào `fixtures/`. Muốn có ca test mới, dựng DXF tổng hợp bằng `cadguard/fixtures.py` mô phỏng lỗi đã gặp.
- Không gửi bản vẽ thật (hay ảnh chụp) cho agent/LLM. Khi cần LLM giải thích, chỉ gửi trích đoạn Drawing Model đã ẩn danh và chỉ khi khách đã đồng ý.
