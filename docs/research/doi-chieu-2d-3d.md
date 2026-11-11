# Nghiên cứu UX: đối chiếu 2D ↔ 3D, nguồn gốc kích thước, sửa và phản hồi

Ngày: 11/11/2026. Bối cảnh: công cụ cục bộ dựng tủ 3D tất định từ bản vẽ DXF (mặt bằng + mặt đứng trên ~40 tờ). Người dùng là nhà thiết kế nội thất, không biết mỗi khối 3D lấy từ tờ/hình chiếu nào, không kiểm được đúng sai, muốn sửa hoặc gửi phản hồi cho trợ lý AI.

Ký hiệu độ tin cậy: **[đã xác minh]** có tài liệu chính hãng; **[nguồn phụ]** diễn đàn/blog bên thứ ba; **[chưa xác minh]** không tìm được tài liệu, là suy luận.

## 1. Sản phẩm đã khảo sát

### Autodesk Docs / BIM 360 / APS Viewer
- **Split View** [đã xác minh]: hiện tờ 2D và mô hình 3D (hoặc hai tờ 2D) cạnh nhau; chọn một phần tử ở bên này thì bên kia tô sáng; chọn trên tờ 2D thì 3D tự zoom tới phần tử đó. Giới hạn: chỉ mô hình Revit, chỉ các view đã xuất bản. https://help.autodesk.com/cloudhelp/ENU/BIM360D-Document-Management/files/About-Viewing-2D-and-3D-Designs/GUID-64FF4FEF-B222-4383-9220-01503422E6CE.html
- Cơ chế kỹ thuật [nguồn phụ, blog Autodesk tiếng Nhật]: hình học 2D và 3D cùng mang một `dbId`, lắng nghe sự kiện chọn ở mỗi viewer rồi isolate + fit ở viewer kia. https://blog.autodesk.io/forge-viewer-forge-viewer-event-and-2d-3d/
- Ánh xạ toạ độ tờ ↔ mô hình qua viewport + ma trận 2D→3D (bài 2020, API đã đổi tên) https://aps.autodesk.com/blog/mapping-between-sheets-and-3d-views-aec-models
- Công cụ "Place me": từ tờ nhảy tới vị trí tương ứng trong 3D (Revit ≥2017) [nguồn: kết quả tìm kiếm tài liệu Autodesk, chưa đọc trang gốc].

### Revit
- **Selection Box** [đã xác minh]: chọn phần tử ở bất kỳ view nào (kể cả 2D) → mở view 3D mặc định với section box ôm vừa phần tử đã chọn. https://help.autodesk.com/cloudhelp/2022/ENU/Revit-DocumentPresent/files/GUID-0BBD875D-0E36-4FA4-A997-D6E3573CA3FF.htm
- Viewport biết tờ (`SheetId`) và view (`ViewId`); "Open Sheet" từ tên view [đã xác minh] https://help.autodesk.com/cloudhelp/2026/ENU/Revit-API-MainReference/files/html/5991dc40-234a-4835-cc06-07524d2e61a4.htm

### Archicad
- **Show Selection/Marquee in 3D** (F4) [đã xác minh]: chỉ hiện phần tử đã chọn ở 2D trong cửa sổ 3D. https://help.graphisoft.com/AC/30/INT/Topics/050_ViewsVB/050_ViewsVB-18.html
- Bài học [nguồn phụ]: lệnh này **không tự cập nhật** khi đổi lựa chọn, mỗi cửa sổ giữ tập chọn riêng; người dùng phàn nàn nhiều trên diễn đàn. → Đồng bộ chọn phải là hai chiều và tức thời. https://community.graphisoft.com/t5/Modeling/See-Selected-Element-in-a-2D-also-in-3D/m-p/319739

### Bluebeam Revu
- **Overlay Pages** [đã xác minh]: chồng hai bản vẽ, mỗi bản một màu, lớp trong suốt; phần trùng hiện màu hoà, phần lệch hiện màu riêng. **Compare Documents** khoanh mây chỗ khác. https://support.bluebeam.com/user-manual/menus/document/overlay-pages.html , https://support.bluebeam.com/articles/compare-documents-vs-overlay-pages/
- Khuyến nghị tránh cặp đỏ/xanh lá cho người mù màu, dùng xanh dương/cam hoặc xanh dương/hồng [nguồn phụ, NOVEDGE].

### Trimble Connect / Revizto
- Tekla đẩy chú thích bản vẽ lên lớp phủ trong 3D viewer; cảnh báo vị trí sai nếu chú thích lệch phiên bản mô hình [đã xác minh, tài liệu Tekla]. https://teklastructures.support.tekla.com/not-version-specific/en/ext_publish_annotations_connect
- Revizto: phủ tờ PDF lên mô hình 3D bằng cách khớp điểm tham chiếu [đã xác minh]. https://help.revizto.com/hc/en-us/articles/360001659316

### SketchUp LayOut
- Tham chiếu mô hình **lỗi thời** được tô đỏ (Windows) và có nút Update; viewport có thể bị "ghi đè" so với scene gốc, có nút Reset [đã xác minh + nguồn phụ]. https://help.sketchup.com/en/layout/managing-model-references (bản pt-br/zh-cn trong kết quả tìm), https://prod-aws-help.sketchup.com/article/3000214

### Shapr3D / SOLIDWORKS (kích thước dẫn vs bị dẫn)
- SOLIDWORKS: kích thước tham chiếu (driven) mặc định **màu xám, trong ngoặc đơn**, không sửa được, tự cập nhật; kích thước dẫn (driving) màu đen, sửa được. Người dùng khuyên giữ xám vì nếu đổi hết sang đen sẽ không phân biệt được [đã xác minh + nguồn phụ]. https://help.solidworks.com/2018/English/SolidWorks/sldworks/c_Reference_Dimensions.htm
- Shapr3D: phác thảo "fully defined / under-defined" hiển thị trạng thái ràng buộc [đã xác minh]. https://support.shapr3d.com/hc/en-us/articles/18816009328284-Sketching-in-Shapr3D

### Phần mềm tủ bếp/nội thất
- **Mozaik** [đã xác minh, một phần trên trang Google Sites cũ]: bấm trực tiếp vào số kích thước trên sơ đồ tủ để sửa; khoá/cho phép co giãn từng chiều (Width/Height/Depth OK); Part Editor cho gõ số hoặc công thức; quy tắc "cấp cao ghi đè cấp thấp", sửa ở cấp chi tiết không bị tham số chung xoá. https://sites.google.com/view/mozaikonlinehelp/help/editors/part-editor , https://mozaik.support.cyncly.com/hc/en-us/articles/44831885477905
- **Cabinet Vision** [nguồn phụ, KB tiếng Pháp]: bấm vào chi tiết để xem thuộc tính, nhập điều chỉnh +/- trên từng kích thước (lưu là điều chỉnh, không thay số gốc). https://cvfkb.screenstepslive.com/a/1446554-dimension-and-angle-part-adjustment-user-guide
- **Polyboard, imos iX** [chưa xác minh]: không tìm được tài liệu công khai mô tả cách hiển thị "kích thước này đến từ đâu". Chỉ biết Polyboard có mục Links/advanced parameters, imos có article script tính kích thước chi tiết từ tham số. https://wooddesigner.org/help-centre/polyboard-additional-design-features/ , https://dev.to/akshay_nikhare/parametric-furniture-design-with-imos-ix-22cf . Nhận xét: phần mềm tủ là **tham số → 3D**, nên "nguồn" là công thức/tham số, không phải hình chiếu 2D; mô hình gần với bài toán của ta hơn là nhóm BIM và nhóm "mặt bằng → 3D".

### Mặt bằng → 3D và nghiên cứu
- **Planner 5D** nhận diện tường/cửa từ ảnh, cho chỉnh sau khi nhận diện; trang sản phẩm có nhắc người kiểm duyệt [nguồn phụ; trang gốc nay trả 404]. Các bài tổng hợp đều mô tả quy trình "AI nhận diện → người duyệt/sửa → dựng", và khuyên đối chiếu từng phần tử với bản gốc [nguồn phụ, blog SEO].
- Nghiên cứu human-in-the-loop: người dùng xoay 3D, vẽ nét sửa trên hình chiếu 2D (silhouette), mạng dự đoán lại; lặp tới khi đạt (arXiv 2008.10719) https://arxiv.org/pdf/2008.10719 . Bài CAD 2D → mô hình tham số (arXiv 2412.11892) không có giao diện độ tin cậy https://arxiv.org/pdf/2412.11892v1
- [chưa xác minh] Không tìm thấy sản phẩm thương mại nào công bố hiển thị **độ tin cậy theo từng phần tử** khi dựng 3D từ bản vẽ CAD. Đây là khoảng trống, không phải mẫu đã được chứng minh.

### BCF (định dạng trao đổi vấn đề BIM)
- Mỗi "issue" lưu: camera, danh sách phần tử **được chọn** / hiện / ẩn theo GUID, mặt cắt, ảnh chụp, bình luận [đã xác minh]. https://github.com/BuildingSMART/BCF/blob/1d3ad49bced7f27135c5ce4ca6ac3591ad1057b8/Documentation/README.md , https://helpcenter.bimcollab.com/portal/en/kb/articles/create-the-best-viewpoints

## 2. Mẫu UX nên chép (xếp theo ưu tiên)

Công sức ước tính cho viewer web dạng canvas, giả định bộ dựng 3D đã có hoặc thêm được bản ghi nguồn cho từng khối (mã tờ, hình chiếu, handle thực thể DXF, khung bao trên tờ).

### P1. Thẻ "Nguồn" cho từng khối + nút "Xem trên tờ"
- **Là gì:** bấm một tấm/khối 3D → thẻ bên hiện: Tờ 12 "MĐ tủ bếp trên" → hình chiếu Mặt đứng A → các đường/kích thước đã dùng. Nút "Xem trên tờ" mở tờ, zoom và tô sáng đúng các thực thể đó.
- **Ai dùng:** Revit (viewport biết SheetId/ViewId, Open Sheet, Go To View), APS "Place me".
- **Vì sao tạo niềm tin:** biến 3D từ "hộp đen" thành thứ truy được tới nét vẽ người dùng đã vẽ; người thiết kế kiểm bằng chính bản vẽ của họ.
- **Công sức:** thấp nếu bộ dựng đã ghi nguồn; trung bình nếu phải thêm bản ghi nguồn vào `cg.scene`.

### P2. Nhãn nguồn kích thước: Ghi chú / Đo / Mặc định / Người sửa
- **Là gì:** mỗi kích thước của khối có huy hiệu: **Ghi** (đọc từ DIMENSION/chữ trên tờ), **Đo** (đo từ hình học), **Mặc định** (chuẩn công ty, vd. dày ván 18), **Đã sửa** (người dùng ghi đè). Kiểu chữ khác nhau như SOLIDWORKS: số suy ra màu xám trong ngoặc, số người nhập màu đậm. Khi Ghi và Đo lệch nhau → cờ cảnh báo.
- **Ai dùng:** SOLIDWORKS/Shapr3D (dẫn vs bị dẫn, fully/under-defined); Mozaik (cấp ghi đè, khoá chiều).
- **Vì sao:** người dùng biết ngay số nào là "bịa" (mặc định) cần kiểm; quy ước xám/ngoặc đã quen với người dùng CAD.
- **Công sức:** thấp (chủ yếu dữ liệu + CSS); phần phát hiện lệch Ghi/Đo là tất định.

### P3. Chia đôi màn hình 2D tờ | 3D, chọn liên kết hai chiều, tô sáng khi rê chuột
- **Là gì:** trái là tờ (render vector), phải là 3D. Rê chuột lên khối 3D → nét nguồn trên tờ sáng lên; chọn nét trên tờ → khối 3D sáng + camera bay tới. Đồng bộ tức thời và hai chiều (bài học Archicad: không tự cập nhật bị phàn nàn).
- **Ai dùng:** Autodesk Docs Split View, APS (dbId chung), Archicad F4.
- **Vì sao:** người dùng tự thấy tương ứng mà không cần đọc; đây là mẫu chuẩn của ngành BIM.
- **Công sức:** trung bình (hai canvas, ánh xạ id chung, hit-test trên tờ).

### P4. Lớp phủ "chiếu ngược" (ghost overlay) để kiểm đúng sai
- **Là gì:** chiếu khối 3D đã dựng ngược về mặt phẳng hình chiếu nguồn rồi phủ lên tờ, hai màu (bản vẽ: xanh dương, 3D chiếu ngược: cam); chỗ khớp hoà màu, chỗ lệch nổi bật và có thể khoanh mây tự động kèm số mm lệch.
- **Ai dùng:** Bluebeam Overlay Pages + Compare Documents; Revizto/Trimble phủ tờ lên mô hình.
- **Vì sao:** "kiểm bằng mắt" mà không phải tin máy; lệch được đo bằng code tất định, hợp với nguyên tắc dự án. Chọn cặp màu thân thiện người mù màu.
- **Công sức:** trung bình–cao (chiếu orthographic thì đơn giản, phần khoanh vùng lệch và căn chỉnh tờ mới tốn).

### P5. Cô lập khối/hạng mục (section box)
- **Là gì:** chọn một hạng mục hoặc nét trên tờ → 3D chỉ hiện phần đó, hộp cắt ôm vừa; các khối khác mờ (ghost) thay vì ẩn hẳn.
- **Ai dùng:** Revit Selection Box, Archicad Show Selection in 3D.
- **Vì sao:** 40 tờ, nhiều tủ: người dùng cần nhìn từng món để kiểm, tránh rối.
- **Công sức:** thấp–trung bình (clipping plane trong three.js/WebGL có sẵn).

### P6. Ghi đè có lưu vết + thứ tự ưu tiên rõ, xem trước rồi mới áp
- **Là gì:** bấm vào số kích thước trên khối để sửa (như Mozaik) hoặc nhập điều chỉnh +/- (như Cabinet Vision); lưu là "lớp bổ sung" tách khỏi bản vẽ (dự án đã có `.cgsup.json`), có thứ tự: Người sửa > Ghi > Đo > Mặc định; nút "Bỏ sửa" trả về giá trị nguồn. Dựng lại không làm mất sửa của người dùng.
- **Ai dùng:** Mozaik (click-to-edit, khoá chiều, cấp cao ghi đè cấp thấp), Cabinet Vision (part adjustment), Planner 5D (sửa sau nhận diện).
- **Vì sao:** người dùng sửa được mà không phải động vào DXF; không sợ mất công khi bản vẽ cập nhật; khớp nguyên tắc xem trước + hoàn tác.
- **Công sức:** trung bình.

### P7. Gửi phản hồi ghim vào khối, kèm "điểm nhìn" có cấu trúc (kiểu BCF)
- **Là gì:** nút "Báo sai" trên khối → ô bình luận; hệ thống tự đóng gói: mã khối, nguồn (tờ/hình chiếu/handle), camera, ảnh chụp 3D + ảnh vùng tờ, các kích thước kèm nhãn nguồn. Gửi cho trợ lý AI như ngữ cảnh có cấu trúc; AI chỉ **đề xuất** sửa (P6), người dùng Đồng ý mới áp. Danh sách phản hồi mở/đã xử lý.
- **Ai dùng:** chuẩn BCF (camera, phần tử được chọn, ảnh, bình luận), BIMcollab.
- **Vì sao:** người dùng không phải diễn đạt "cái tủ thứ hai bên trái"; AI nhận đúng chỗ, câu trả lời kiểm được.
- **Công sức:** trung bình (dữ liệu sẵn từ P1–P2; phần AI đã có hạ tầng trợ lý).

### P8. Báo "3D đã cũ" khi bản vẽ đổi
- **Là gì:** lưu mã băm DXF lúc dựng; nếu tệp đổi, khung 3D có dải đỏ "Bản vẽ đã thay đổi sau lần dựng — Dựng lại", liệt kê khối bị ảnh hưởng (nguồn của chúng thay đổi).
- **Ai dùng:** SketchUp LayOut (tham chiếu lỗi thời tô đỏ + Update), Tekla/Trimble (cảnh báo chú thích lệch phiên bản).
- **Vì sao:** tránh người dùng kiểm/duyệt trên 3D không còn khớp bản vẽ.
- **Công sức:** thấp.

### (Phụ) Mức chắc chắn theo khối
- Tô viền theo mức: khớp đủ 2 hình chiếu / chỉ 1 hình chiếu / suy đoán từ mặc định. Bản chất là tổng hợp của P2 (đếm kích thước Mặc định) nên làm sau P2. **[chưa xác minh]** không thấy sản phẩm thương mại nào công bố cách này; nghiên cứu (arXiv 2008.10719) chỉ cho thấy vòng lặp "xem 3D → sửa trên hình chiếu 2D → dựng lại". Nên dùng nhãn mô tả ("chỉ thấy ở 1 hình chiếu") thay vì phần trăm, tránh cảm giác số giả.

## 3. Thứ tự gợi ý
P1 + P2 (rẻ, nền dữ liệu cho mọi thứ) → P5 + P8 → P3 → P6 → P7 → P4.

## 4. Điểm chưa chắc
- Chi tiết Polyboard / imos / Cabinet Vision về hiển thị nguồn kích thước: không có tài liệu công khai, chưa xác minh.
- Planner 5D: trang tính năng gốc trả 404 khi kiểm; mô tả dựa vào kết quả tìm kiếm và bài đánh giá.
- APS "Place me" và tên hàm AEC: lấy từ tóm tắt tìm kiếm, API có thể đã đổi.
- Hành vi Archicad ở các phiên bản mới (Archicad 25 có "Select in 3D") đến từ diễn đàn.
