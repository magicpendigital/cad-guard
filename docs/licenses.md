# Giấy phép các thành phần

Cập nhật khi thêm phụ thuộc. Nguyên tắc: không đưa vào sản phẩm thành phần có giấy phép copyleft hoặc phi thương mại mà chưa có ý kiến pháp lý.

## Đang dùng

| Thành phần | Dùng để | Giấy phép | Ghi chú |
| --- | --- | --- | --- |
| ezdxf | Đọc/ghi DXF | MIT | Lõi chỉ xử lý DXF. DWG chỉ qua add-on `odafc` (không dùng) |
| pydantic | Mô hình dữ liệu | MIT | |
| PyYAML | Nạp chuẩn | MIT | |
| pytest (dev) | Test | MIT | |

(Giấy phép trên ghi theo hiểu biết hiện tại; kiểm lại tệp LICENSE của từng gói đã cài trước khi phát hành.)

## Đã xem xét và KHÔNG dùng

| Thành phần | Lý do |
| --- | --- |
| ODA File Converter | Chỉ miễn phí cho mục đích **phi thương mại** nếu không là thành viên ODA; không được phân phối lại (kiểm ngày 02/11/2026 trên trang FAQ của ODA) |
| LibreDWG | GPLv3+ (ràng buộc cách phân phối sản phẩm); đọc DWG r1.2–r2018 nhưng ghi mặc định chỉ r2000 trở xuống; DXF nó sinh ra có tệp AutoCAD nhập lỗi (theo sổ tay GNU) |
| Fork LibreCAD/QCAD/FreeCAD | Ngoài hướng đã chọn (xem `plans/cad-guard-direction.md`); giấy phép copyleft chưa kiểm |
| Autodesk APS Model Derivative | Gửi bản vẽ lên đám mây + tính phí theo token; trái nguyên tắc xử lý cục bộ |

## Chưa quyết (quyết ở đầu P1b)

- Thư viện dựng hình DXF cho trình xem/rà soát (web hoặc máy tính): chọn và ghi giấy phép ở đây.
