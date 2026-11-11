# Dựng phối cảnh 3D cả không gian: đánh giá khả năng (11/11/2026)

Câu hỏi: CAD Guard có dựng được 3D của **cả một tầng/căn** (phòng, tường, cửa, mọi hạng mục đặt đúng chỗ) để xem
phối cảnh không, hay chỉ dựng được từng hạng mục như hiện nay?

Đo trên bản sao tệp phiên 01 (40 tờ, ngoài repo). Chỉ ghi số cấu trúc.

## 1. Bản vẽ có gì để dựng cả không gian

| Thứ cần | Có trong tệp? | Ghi chú |
|---|---|---|
| Mặt bằng tổng của tầng | Có, 1 hình ở tờ 1 | khoảng 13,7 × 17,8 m, cùng đơn vị mm với hình chi tiết |
| Tường | Có nhưng vẽ bằng hatch + nét cắt | bộ đọc tường hiện tại chỉ nhận 2 đoạn: cần bộ đọc tường kiểu "hai nét song song + hatch" |
| Ranh giới phòng | Không có đường bao | có chữ tên phòng + diện tích (4 phòng) |
| Vị trí từng hạng mục trên mặt bằng tổng | **Có**: ký hiệu số hạng mục (11 số, khớp mã hạng mục) + bảng chú thích tên | đặt được hạng mục vào mặt bằng tổng bằng code, không cần đoán |
| Hướng của hạng mục (tựa vào tường nào) | Gián tiếp | suy từ tường gần ký hiệu nhất + chiều dài khối; cần người xác nhận khi không chắc |
| Cao trần | Theo từng hạng mục | vd. kệ TV ghi sàn–trần 2890 trên mặt đứng; không có mặt bằng trần tổng của tầng này (chỉ 1 hạng mục ốp trần) |
| Cửa đi/cửa sổ | Thiếu cho tầng này | 3 tờ định vị cửa là của tầng khác; 9 nét cửa trên mặt bằng tổng, không có cao cửa |
| Đồ rời, thiết bị | Có dạng khối (block) | sofa, giường, thiết bị vệ sinh, bếp…: lấy được kích thước mặt bằng; cao lấy mặc định có nhãn |
| Vật liệu | Có ghi chú vật liệu trên tờ chi tiết | đã có bước Đề xuất/Đồng ý vật liệu (P2), dùng lại được để tô màu |

Kết luận: **dựng được cả không gian ở mức "khung phòng + hạng mục đặt đúng chỗ + đồ rời dạng khối"**, đủ để xem
bố cục, lối đi, va chạm, đối chiếu thiết kế. **Chưa đủ cho ảnh phối cảnh đẹp như ảnh diễn họa** nếu chỉ dựa vào tệp
này: thiếu cửa, trần, ánh sáng, chất liệu bề mặt chi tiết. Phần đẹp nên giao cho phần mềm diễn họa (D5, Twinmotion,
Enscape, Blender) bằng tệp glTF CAD Guard xuất ra, vì nhóm diễn họa đã quen các phần mềm đó.

## 2. Cách làm đề xuất (theo bậc, mỗi bậc dùng được ngay)

1. **Khung phòng** (code): bộ đọc tường hatch/nét đôi trên mặt bằng tổng → tường 3D; cao tường lấy từ kích thước sàn–trần
   của các mặt đứng trong phòng, thiếu thì mặc định có nhãn và ô nhập. Chữ tên phòng → nhãn phòng.
2. **Đặt hạng mục** (code + người xác nhận): ký hiệu số trên mặt bằng tổng ↔ mã hạng mục; xoay theo tường gần nhất;
   căn chính xác bằng cách khớp đường bao mặt bằng chi tiết với nét đồ trên mặt bằng tổng. Hạng mục đã dựng 3D (như
   kệ TV) được đặt nguyên khối vào phòng. Chỗ không chắc → việc cần làm ở màn Bản đồ, không tự đoán.
3. **Đồ rời + thiết bị** (code): khối block → hộp theo kích thước mặt bằng, cao theo bảng mặc định (bảng công thái học đã
   có), nhãn "Mặc định".
4. **Cửa** (code + người nhập): lỗ cửa từ nét cửa trên mặt bằng; cao cửa nhập một lần cho cả dự án.
5. **Phối cảnh** (trong app): góc nhìn đi bộ theo phòng, chuyển 2D/3D, màu theo vật liệu đã Đồng ý. **Diễn họa đẹp**:
   xuất glTF cả tầng sang D5/Twinmotion/Blender.

LLM/agent giúp ở bậc 2 và 5: đọc bảng chú thích (chữ TCVN3), đề xuất hướng đặt khi code không chắc, kiểm "khối này có
khớp ảnh minh hoạ không". Số đo và vị trí vẫn do code tính, người dùng Đồng ý mới ghi (giống P2).

## 3. Rủi ro

- Mỗi công ty vẽ mặt bằng tổng khác nhau (ký hiệu số, chữ, block). Ký hiệu số hạng mục là chuẩn nội bộ của công ty
  này; nên đưa vào hồ sơ công ty để kiểm bằng luật (thiếu ký hiệu → cảnh báo).
- Hạng mục chỉ có một mặt đứng (một hướng) dựng ra đúng mặt trước, các mặt khác (hướng B, C của bếp chữ L) cần ghép
  nhiều mặt đứng: việc đang chờ ở kế hoạch 3D.
- Tầng có nhiều hạng mục lớn (bếp chữ L, quầy đảo) thì phần thiếu nhiều hơn; mỗi phần thiếu phải nói rõ ở đâu, sửa thế nào.

## 4. Ước lượng

| Bậc | Khối lượng | Kết quả thấy được |
|---|---|---|
| 1 Khung phòng | vừa | tường + sàn + nhãn phòng của tầng |
| 2 Đặt hạng mục | vừa–lớn | các hạng mục đã dựng nằm đúng phòng |
| 3 Đồ rời | nhỏ | bố cục đầy đủ để xem lối đi |
| 4 Cửa | nhỏ | lỗ cửa trên tường |
| 5 Xuất diễn họa | nhỏ | tệp glTF cả tầng mở trong phần mềm diễn họa |

## 5. Đã triển khai (11/11/2026)

`scene/space.py` (`cg.space/1`), lệnh `cadguard space <dxf> --out x.glb|x.json`, màn 3D → ô Hạng mục → "★ Cả tầng"
(`/api/space`, `/api/space/set`, `/api/space/glb`).

| Bậc | Cách làm | Đo trên phiên 01 |
|---|---|---|
| 1 Khung phòng | mặt bằng tổng = hình mặt bằng có nhiều ký hiệu số nhất; tường = đa giác kín nét cắt/tường mảnh (bề dày quy đổi ≤ 600 mm, hai đường bao lồng nhau = vành tường) + cặp nét song song hở cách 60–450 mm; cao = trung vị sàn–trần của các mặt đứng hạng mục | 44 mảng tường, 4 phòng, cao 2685 (7 mặt đứng ghi sàn–trần) |
| 2 Đặt hạng mục | ký hiệu số (bỏ cột chú thích); xoay 0/90/180/270 + dời: ứng viên từ bỏ phiếu đầu mút, chấm bằng tỷ lệ nét chi tiết nằm trên nét mặt bằng tổng (≥ 45 %), tâm hình phải gần ký hiệu; khớp yếu → việc cần làm, người chọn góc xoay | 4/10 đặt chắc (khớp 61–88 %); bếp ướt và bàn đảo 39–40 % chờ chọn góc; 4 hạng mục chưa dựng được khối |
| 3 Đồ rời | block layer nội thất ngoài hạng mục đã đặt; cao theo tên block, nhãn Mặc định | 6 |
| 4 Cửa | block layer cửa ≤ 2400 mm: cánh + lanh tô; cao cửa mặc định 2200, sửa được | 7 (1 block vách kính lớn bỏ qua, có ghi chú) |
| 5 Xuất | GLB cả tầng (mặt lõm chia tam giác cắt tai), trình xem trong app | 0,4 s dựng |

Chưa làm: khoét lỗ cửa trong tường (cửa đứng chồng lên tường nếu mặt bằng không chừa khe), cửa sổ, trần, vật liệu bề mặt
theo phòng, ghép nhiều mặt đứng của bếp chữ L. Số khối người dùng sửa giờ lưu kèm mã hạng mục (`<mã>|module:M1:w`) để
M1 của hạng mục này không đè lên M1 của hạng mục khác.
