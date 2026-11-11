---
name: ket-cau-tu
description: Kiến thức kết cấu thùng tủ nội thất (hồi, nóc, đáy, hậu, vách ngăn, đợt, cánh, ngăn kéo, thanh giằng) để đọc, kiểm và giải thích cấu tạo một hạng mục từ bản vẽ 2D và cảnh 3D của CAD Guard. Dùng khi người dùng hỏi "tủ này lắp được không", "thiếu vách ngăn không", "cánh này có xệ không", "đợt có võng không", hoặc khi giải thích phần "Kiểm kết cấu" ở màn 3D.
---

# Kết cấu thùng tủ (frameless / hệ 32 mm)

Trợ lý chỉ **giải thích và đề xuất**. Số đo lấy từ bản vẽ qua công cụ (`get_scene`, `get_drawing_graph`, `query_model`,
`measure`); không tự bịa số. Kết luận "lắp được / không" là nhận xét kỹ thuật kèm lý do, hiển thị riêng với kết quả luật.
Thông số xưởng (độ dày ván, kiểu hậu, kiểu liên kết, nhịp đợt, cánh tối đa, thanh giằng) lấy từ **Kết cấu xưởng** của
CAD Guard; chưa xác nhận thì nói rõ đang dùng số mặc định.

## Cấu tạo một thùng tủ

| Bộ phận | Vai trò | Lưu ý kiểm |
| --- | --- | --- |
| Hồi (hông) trái/phải | Chịu lực đứng, bắt bản lề và ray ngăn kéo | Hông trùm nóc/đáy hay nóc/đáy trùm hông quyết định kích thước cắt |
| Nóc | Giằng đỉnh thùng | Tủ bếp dưới đỡ mặt đá thường thay bằng **2 thanh giằng** trước/sau (~80–100 mm) |
| Đáy | Đỡ đồ, giằng chân | Tủ dưới thường có chân/len chân phía dưới |
| Hậu | Giữ vuông thùng, chống xô lệch | Bắt vít sau thùng hoặc lọt rãnh; tủ không hậu dễ lệch |
| Vách ngăn | Chia khoang, **bắt bản lề/ray**, đỡ đợt dài | Bắt buộc ở các chỗ dưới đây |
| Đợt | Kệ trong khoang | Nhịp dài thì võng |
| Cánh / mặt ngăn kéo | Mặt trước | Trùm toàn / trùm nửa / lọt lòng |

## Khi nào BẮT BUỘC có vách ngăn

1. **Bản lề:** đế bản lề bật phải bắt vào một tấm đứng (hồi hoặc vách). Hai cánh cạnh nhau mà cả hai bắt bản lề vào đường
   ráp chung (bản lề quay lưng nhau) → sau đường ráp phải có vách. Cặp hai cánh mở từ giữa (bản lề ở hai hồi) thì không cần.
   Ví dụ: tủ 2400 có 4 cánh 600 = hai cặp cánh → cần vách ở giữa (1200); thiếu vách thì cánh thứ 2 và 3 không có chỗ bắt bản lề.
2. **Ray ngăn kéo:** ray bắt vào hai tấm đứng → cột ngăn kéo hẹp hơn thùng phải có vách hai bên; ngăn kéo cạnh cánh cũng cần vách
   giữa.
3. **Nhịp đợt:** đợt ván 17–18 mm không nên vượt khoảng 600–700 mm (tuỳ tải, vật liệu); khoang dài hơn cần vách, hoặc đợt dày
   hơn / nẹp đỡ / bắt vít vào hậu.

## Cánh

- Cánh bản lề rộng tối đa ~600 mm và nên **cao hơn rộng** (Blum). Rộng hơn → chia 2 cánh, hoặc thêm bản lề và kiểm tải.
  Cánh thấp và rộng (tủ trên dạng lật) → cánh lật/tay nâng.
- Số bản lề theo chiều cao và khối lượng cánh (bảng của hãng bản lề; CAD Guard tính theo Kết cấu xưởng).

## Quy trình khi được hỏi về kết cấu một hạng mục

1. `get_scene` cho hạng mục: lấy khối (rộng, sâu, cao, cao độ), mặt trước (cánh/ngăn kéo, vị trí), số đợt.
2. Xác định bên bản lề từng cánh (cặp mở giữa hay quay lưng) → liệt kê đường ráp cần vách. Đối chiếu bản vẽ: có vách thật ở
   đó không (`get_drawing_graph`, `query_model` theo vùng; vách = hai nét song song cách 8–60 mm cao gần suốt thùng).
3. Kiểm nhịp đợt từng khoang, cánh rộng/thấp, cột ngăn kéo.
4. Trả lời theo dạng: **chỗ nào – vì sao – sửa thế nào (trong CAD Guard / trong AutoCAD)**. CAD Guard đã tự thêm vách nào
   (nhãn "Tự thêm theo kết cấu") thì nói rõ đó là bổ sung của phần mềm, bản vẽ gốc chưa có.

## Nguồn

- Blum, CLIP top BLUMOTION – số bản lề (cánh tới 600 mm; cánh cao hơn rộng): https://ea.blum.com/en/number-of-hinges/
- Hệ 32 mm / tủ không khung (bản lề, ray, chốt đợt định vị trên tấm đứng): https://en.wikipedia.org/wiki/Frameless_construction
- Nhịp đợt và độ võng: https://woodweb.com/knowledge_base/Frameless_Shelf_Spans.html , https://woodbin.com/calcs/sagulator/
- Số của từng xưởng (nhịp đợt, thanh giằng, kiểu hậu) phải do xưởng xác nhận trong Kết cấu xưởng.
