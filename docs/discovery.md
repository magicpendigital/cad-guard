# Khảo sát tại khách (P0) — phiếu điền

Trạng thái: **CHƯA ĐIỀN**. Người điền: CEO cùng trưởng phòng kỹ thuật. Mục đích: biết phần mềm nào đang dùng, lỗi nào đắt nhất, mẫu bản vẽ nào đại diện. Không có tên khách thật trong repo: dùng mã (K1, K2…).
Kế hoạch tham chiếu: `plans/cad-guard-direction.md` mục 5.

## 1. Kiểm kê phần mềm (1 buổi với phòng kỹ thuật)

| Bộ phận | Vị trí | Phần mềm đang dùng | Bản/năm | Phần mềm sẽ chuyển sang | Hạn chuyển | Định dạng đầu ra | Người nhận tiếp theo |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Kỹ thuật |  |  |  |  |  |  |  |
| Thiết kế sản xuất |  |  |  |  |  |  |  |
| Diễn họa |  |  |  |  |  |  |  |
| Xưởng / CNC |  |  |  |  |  |  |  |
| Mua hàng |  |  |  |  |  |  |  |

Câu hỏi bổ sung:

1. Phần mềm nào sẽ thay AutoCAD, khi nào, do ai quyết? Có thể thống nhất **một** phần mềm CAD chuẩn cho phòng kỹ thuật không?
2. Phần mềm CAD hiện tại có lệnh/tập lệnh LISP không? Có ai biết viết hoặc đã có tập lệnh dùng chung không?
3. Có phần mềm chuyên cho đồ gỗ không (ghi đúng tên theo lời họ)? Nó xuất ra định dạng gì?
4. Máy CNC/xưởng nhận định dạng gì (DXF, bảng cắt, tệp riêng của máy)? Yêu cầu tên layer, đơn vị, gốc toạ độ?
5. Ai đang kiểm bản vẽ hiện nay, kiểm bằng cách nào, mất bao lâu mỗi bản?
6. Bản vẽ lưu ở đâu (thư mục mạng, ổ cá nhân, hệ thống quản lý)? Quy tắc đặt tên tệp/mã bản vẽ?
7. Có chuẩn/mẫu nào đang dùng ngầm (file mẫu .dwt, khung tên, danh sách layer) chưa ghi ra giấy không? Xin bản.

## 2. Mẫu bản vẽ (xem `docs/samples-intake.md`)

- [ ] 30–50 bản đại diện: tủ bếp, tủ áo, văn phòng, chi tiết; đủ cả bản tốt và bản từng gây lỗi.
- [ ] Mỗi bản kèm: phần mềm và bản tạo ra, DXF xuất từ chính phần mềm gốc nếu họ có.
- [ ] Đã ẩn danh theo hướng dẫn; để ở thư mục **ngoài repo**.

Số lượng thu được: ___ DWG, ___ DXF. Phần mềm gốc: ___.

## 3. Sự cố thật (≥ 20)

| # | Lỗi gì | Ở khâu nào | Phát hiện ở đâu/khi nào | Tốn bao nhiêu (giờ/tiền/vật tư) | Ai sửa |
| --- | --- | --- | --- | --- | --- |
| 1 |  |  |  |  |  |

Xếp hạng 10 lỗi đắt nhất (tần suất × chi phí): ghi ở đây sau khi điền bảng. Đây quyết định luật nào làm trước.

## 4. Đồng ý về dữ liệu

- [ ] Xử lý cục bộ trên máy của công ty (mặc định).
- [ ] Cho phép gửi **trích đoạn đã ẩn danh** lên LLM để giải thích lỗi: có / không.
- [ ] Cho phép lưu fixture ẩn danh trong repo để test: có / không.
- Người có thẩm quyền đồng ý: ______ Ngày: ______ (giữ văn bản ngoài repo.)

## 5. Quyết định cho chuẩn v0 (mục 6 của `standards/furniture-v0.md`)

Ghi quyết định hoặc "chưa quyết, dùng mặc định v0":

1. Chiếu góc thứ nhất hay thứ ba; khổ giấy thực sự in:
2. Danh sách layer cuối cùng, nét lấy từ layer hay CTB/STB:
3. Cặp độ dày nét; font hỗ trợ tiếng Việt:
4. Dung sai chung cho gỗ:
5. Mã dán cạnh, ký hiệu vân, quy ước đặt tên tấm:
6. Cách đánh mã bản vẽ và phiên bản; bản xuống xưởng có cần người kiểm ký không:
7. Phần mềm đích của xưởng và tên layer DXF cho CNC:
8. Danh mục phụ kiện và khe hở chuẩn:

## 6. Ghi chú AutoCAD dùng thử

- Ngày bắt đầu dùng thử: ______ ; hết hạn: ______ (thường có hạn, kiểm điều khoản).
- Đã đọc điều khoản dùng thử về dữ liệu của khách: có / không.
- Việc làm trong thời gian dùng thử: mở thử toàn bộ DWG mẫu; xuất DXF đối chiếu; ghi bản nào lỗi/thiếu font.
- Kết quả (bản mở lỗi, font thiếu, khác biệt DWG → DXF):

## 7. Kết luận P0 (điền sau cùng)

- Phần mềm CAD chuẩn (nếu có):
- Tính năng cần thật sự (đơn giản, cơ bản):
- 10 luật làm trước:
- Có cần chuyển sang hướng plugin theo phần mềm cụ thể không, và cho phần mềm nào:
