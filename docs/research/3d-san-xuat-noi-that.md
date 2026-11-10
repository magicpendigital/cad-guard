# Nghiên cứu: 3D "có giá trị sản xuất" cho nội thất tấm (từ bản vẽ 2D)

Ngày: 11/11/2026. Phạm vi: nghiên cứu web, không sửa mã. Ký hiệu độ tin cậy:
**[X]** đã thấy trong nguồn chính hãng/nhà sản xuất; **[D]** nguồn phụ (diễn đàn, blog, review) — chỉ là thực hành phổ biến;
**[?]** chưa xác minh được / nguồn mâu thuẫn; **[KT]** kiến thức nghề chung, không tìm được nguồn trong phiên này.

---

## 1. Phần mềm CAD/CAM sản xuất nội thất cung cấp gì

Điểm chung của mọi công cụ sản xuất: **mô hình là tập TẤM (part) có độ dày, vật liệu, kiểu liên kết và gia công**, không phải khối hộp. Từ mô hình đó sinh ra cùng lúc: danh sách cắt, dán cạnh, khoan, bản vẽ lắp, dữ liệu CNC. 3D là "hệ quả" của dữ liệu tấm, không phải mục đích.

| Công cụ | Điểm đáng học | Nguồn |
|---|---|---|
| **Cabinet Vision** (Hexagon) | Liên kết mô hình → sản xuất tự cập nhật cut list và hình học CNC; báo cáo cut list, assembly sheet, shop drawing, báo giá; "Assembly Wizard / Assign Banding" gán dán cạnh theo chi tiết; xuất CNC/nesting. [D] (chủ yếu review + tin ngành) | https://cabinetvision.com · https://www.furnitureproduction.net/node/1908 · https://softwarereview.com/s/cabinet-vision |
| **Microvellum** | "Associative hardware": phụ kiện chạm vào tấm thì tự sinh gia công (khoan, phay, rãnh, hốc) trên tấm đó; gia công suy ra từ logic sản phẩm; xuất DXF từng chi tiết có kích thước + vị trí khoan; lệnh exploded view. [X] (tài liệu cộng đồng của hãng) | https://community.microvellum.com/portal/en/kb/articles/associative-hardware-tutorial · https://intercom.help/microvellum-knowledge-base/en/articles/13907884-product-detailing-tools |
| **TopSolid'Wood** | Mọi hình chiếu từ một mô hình: chi tiết, mặt cắt, hình chiếu ngắt, **exploded**, tự cập nhật; mô hình 3D thật của phụ kiện Blum/Hettich đi kèm để định vị gia công. [D] (tài liệu marketing/handbook) | https://www.slideshare.net/PaulLenihan/topsolid-ijsbrochure0714-46899033 · https://www.p-s-s.de/files/2018/TopSolid_intern/Handbuecher/XX/02_TopSolid´Wood - Handbuch V6.18.pdf |
| **imos iX / HOMAG iX** | 3D tham số + tự do, chọn và định vị phụ kiện "thông minh", quy hoạch phòng; iX CAM sinh chương trình CNC kể cả khoan từ thiết kế 3D, tính chiều thớ gỗ, thời gian gia công; danh sách sản xuất xuất thẳng từ CAD. [X] | https://www.homag.com/en/product-detail/software/order-creation/homag-ix · https://www.homag.com/fileadmin/software/brochures/iX-3D-CAD-CAM-en.pdf · https://www.imos3d.com/en/products/manufacturing-assembly/cnc-programming-ix-cam |
| **Polyboard / OptiCut** | Liên kết khai báo ở mục "Links": chồng (overlap), **rãnh (groove)**, rebate, mitre, mộng, halving; "double back" (tấm hậu thứ hai ở độ sâu bất kỳ); tham số: đổi kích thước tổng thì mọi tấm, cut list, bản vẽ, file CNC cập nhật; bản Pro PP có post-processor CNC; OptiCut tối ưu sơ đồ cắt. [X] (trang hãng) | https://wooddesigner.org/help-centre/polyboard-basic-design/ · https://wooddesigner.org/help-centre/polyboard-additional-design-features/ · https://wooddesigner.org/polyboard-software-tools/ |
| **Mozaik** (Cyncly) | Shop drawing, 3D, assembly sheet, cut list tuỳ biến cột, nhãn chi tiết/tủ; bản CNC: nesting true-shape, G-code, khoan phụ kiện tự động, liên kết CNC; tham số "blind dado setback" cho rãnh hậu. [X] | https://www.mozaiksoftware.com/products/mozaik-manufacturing · https://www.mozaiksoftware.com/products/additional-features-mozaik-manufacturing · https://mozaik.support.cyncly.com/hc/en-us/articles/45956599342993 |
| **2020 Design / Design Flex** | Mạnh về **trình bày bán hàng**: render tự động ánh sáng (EZ Render, Cycles), in mặt bằng + mặt đứng, catalogue nhà cung cấp tủ. Không xác nhận được tính năng kiểm va chạm cánh. [D] | https://www.capterra.com/p/218525/2020-Design-Live/ · https://cyncly.com/fr/products/design-live |
| **SketchUp + ABF** (rất phổ biến ở VN) | Plugin miễn phí cho nội thất ván công nghiệp + CNC: đánh dấu bản lề, đánh dấu giao cắt, xuất DXF để nesting; gia công nhận theo **tên layer** (vd. khoan mặt `ABF-Z<sâu>-D<đường kính>`), dán nhãn chi tiết; Blum có cầu nối **BXF2ABF** nhập tủ + phụ kiện. [D]/[X cho BXF2ABF] | https://forums.sketchup.com/t/abf-furniture-cnc/127578 · https://woodsoft.gitbook.io/woodsoft-optimizers/woodsoft-optimizer-en/plugin-woodsoft-nesting/usage-guide · https://www.blum.com/ua/uk/services/industrial-production/cad-cam-interface/software-partners/bxf2abf/ |
| **SketchUp + OpenCutList** | Cut list, sơ đồ cắt (thớ theo chiều dài), nhãn có QR, CSV/PDF, báo giá; dán cạnh khai báo bằng vật liệu riêng, **không vẽ dán cạnh trên sơ đồ cắt**; nesting theo đợt phát triển. [D] | https://forums.sketchup.com/t/opencutlist-a-crowdfunded-extension-8-0-campaign/301089 · https://forums.sketchup.com/t/edge-banding/346397/5 · https://opencollective.com/lairdubois-opencutlist-sketchup-extension |
| **Blum DYNAPLAN → Cabinet Configurator** | Chọn phụ kiện, **kiểm va chạm tích hợp**, xuất dữ liệu CAD/CAM, cut list, vị trí khoan chính xác; định dạng **BXF** chứa cả phụ kiện lẫn thông tin sản xuất tấm (kích thước cắt, vị trí khoan). Bản mới lúc ra mắt chưa hỗ trợ một số ca (Servo-Drive, bản lề góc, tủ góc) [?]. | https://www.blum.com/gb/en/services/planning-construction-product-selection/dynaplan/ · https://blum.com/nz/en/services/planning-construction-product-selection/cabinet-configurator · https://www.hpponline.co.uk/newsdetail/33127/introducing-the-blum-cabinet-configurator |

**Hệ 32 mm (System 32)** [D]: lỗ hàng (line boring) cách nhau 32 mm; hàng trước cách mép trước 37 mm (với cánh trùm; cánh lọt cộng thêm độ dày cánh); hàng sau thường cũng 37 mm từ mép sau nên khoảng giữa hai hàng không nhất thiết là bội 32. Đây là quy ước, không phải chuẩn chính thức (Blum "Process 32" vs "True32" khác nhau). Nguồn: https://en.wikipedia.org/wiki/System_32_(furniture) · https://davelers.com/32mm/Basics/168.html · https://www.woodweb.com/knowledge_base/Drawer_runner_holes_in_32mm_system.html

**Rãnh hậu** [D]: không có một con số chuẩn; thực hành gặp: rãnh cách mép sau ~10–25 mm, hoặc hậu bắt vít phẳng; các phần mềm đều để thành tham số (Mozaik "blind dado setback"). Cặp số "hậu 3 mm HDF, rãnh lùi 8 mm" **không tìm được nguồn** [?] → phải lấy từ hồ sơ công ty. Nguồn: https://woodweb.com/knowledge_base/Recessed_or_flush_cabinet_backs.html · https://mozaik.support.cyncly.com/hc/en-us/articles/45956599342993

---

## 2. Luật kỹ thuật bản lề, cánh, ray

### 2.1 Bản lề chén (cup hinge)
- Chén 35 mm, khoan sâu ~13 mm (Blum 110°) [X]; Hettich ~12,8 mm; một số bản lề Salice 11 mm [D]. Nguồn: https://www.onepointesolutions.com/wp-content/uploads/2021/03/110°-FULL-OVERLAY-SELF-CLOSING-BLUM-HINGES-w-BLUMOTION.pdf · https://www.specifiedby.com/hettich/perfect-silent-system/hettich_Perfect-Silent-System_Brochures_Sensys-2015-HUK-14987-EN.pdf
- Khoảng cách mép chén – mép cánh (boring distance, "C"): Blum 125° là 3–6 mm, Blum 170° là 3–8 mm [D trích tài liệu Blum]. Nguồn: https://woodweb.com/knowledge_base/Blum_hinge_drilling_locations.html
- **Kiểu trùm** quyết định công thức: Hettich ghi trùm toàn phần D = C + B − A, trùm nửa D = C + B − A với đế khác, cánh lọt D = C + B + F (A = độ trùm, B = đế, F = khe). Giá trị đế khác theo hãng/mã → **phải tra bảng của đúng mã bản lề** [D]. Nguồn: https://web2.hettich.com/hbh/addon/en/p_KSP_A_en_34.pdf · https://www.hardwaresource.com/resources/selecting-european-hinges
- **Số bản lề** (Blum, CLIP top BLUMOTION) [X]: 2 bản lề tối ưu cho cánh 4–6 kg, 3 bản lề cho 6–12 kg (tính cả tay nắm); áp cho cánh rộng tới 600 mm; cánh tới 650 mm thêm 1 bản lề; cánh cao hẹp nên dùng 3 dù chỉ 6 kg; bản lề càng xa nhau càng chắc. Bảng chi tiết theo **chiều cao × khối lượng** nằm trong catalogue Blum (không trích được số trong phiên này) [?]. Nguồn: https://ea.blum.com/en/number-of-hinges/ · https://publications.blum.com/2024/catalogue/id/123/
  - Hệ quả cho cad-guard: khối lượng cánh suy được tất định = rộng × cao × dày × khối lượng riêng vật liệu (MDF/MFC ~ 650–750 kg/m³ [KT, cần xác nhận theo nhà cung cấp]).
- **Khe cánh** [D]: phổ biến 3 mm giữa hai cánh tủ không khung, có xưởng dùng 2 mm với bản lề Blum trùm toàn phần; "reveal" (mép lộ ở cạnh ngoài) khác "door gap" (giữa hai cánh); hãng bản lề có bảng reveal tối thiểu theo độ dày cánh và khoảng khoan. Nguồn: https://framelesskitchencabinet.com/?p=2055 · https://woodweb.com/knowledge_base/Space_Between_Cabinet_Doors.html · https://sites.google.com/a/cabinetsensesoftware.com/cabinetsense-wiki/attribute/reveals
- **Va chạm khi mở** [KT + X một phần]: cánh trùm mở sát tường/tủ đứng cạnh sẽ đụng (độ nhô của cánh khi mở 90–110°), đặc biệt khi có ngăn kéo/rổ kéo bên trong cần mở >90°; cách xử lý thông thường là thanh bù (filler) hoặc bản lề góc mở lớn. Blum Cabinet Configurator có "integrated collision check" [X] nhưng không công bố thuật toán. Số đo độ nhô cụ thể phải lấy từ bản vẽ kỹ thuật bản lề [?].

### 2.2 Ray ngăn kéo
- Blum TANDEM: chiều dài danh nghĩa (NL) 250–600 mm (full extension), 270–650 mm (single) tuỳ khu vực; biến thể 19 mm tới 750 mm [X]. Nguồn: https://www.blum.com/gb/en/products/runnersystems/tandem/programme/ (trang khu vực) · https://www.blum.com/ca/en/products/runnersystems/movento/programme/
- MOVENTO (tờ lắp đặt): khe đáy 16 mm, khe trên tối thiểu 7 mm, lùi 3 mm; **rộng trong ngăn kéo = rộng lọt lòng − 42 mm** [D trích tài liệu Blum]. Nguồn: https://static.richelieu.com/documents/docsGr/121/081/5/1210815/1684752.pdf
- TANDEMBOX: đáy ngăn kéo rộng = rộng lọt lòng − 75 mm; dài đáy = NL − 24 mm; hậu ngăn kéo = rộng lọt lòng − 87 mm; rộng lọt lòng tối thiểu 125 mm [D trích Blum]. **Sâu lọt lòng tối thiểu = NL + 3 mm** (catalogue antaro mới) — một catalogue 2009 ghi khác [?]. Nguồn: https://woodworkinstitute.com/wp-content/uploads/2024/07/Blum-Tandembox-Brochure.pdf · https://publications.blum.com/2024/catalogue/en/298/
- Luật tất định suy ra: chọn NL lớn nhất ≤ (sâu lọt lòng − dung sai hãng); nếu NL < ~70% sâu → cảnh báo phí không gian [KT].

---

## 3. Kích thước chuẩn và công thái học

**Lưu ý chung:** không tìm thấy TCVN quy định kích thước tủ bếp/tủ áo/bàn làm việc. TCVN 5373:2020 "Đồ gỗ nội thất" là yêu cầu kỹ thuật/an toàn/đóng gói (không xác nhận có bảng kích thước — văn bản trả phí) [?]; TCVN 7490:2005 chỉ cho bàn ghế học sinh. Nguồn: https://thuvienphapluat.vn/TCVN/Cong-nghiep/TCVN-5373-2020-Do-go-noi-that-918923.aspx · https://thuvienphapluat.vn/TCVN/Linh-vuc-khac/TCVN-7490-2005-Ecgonomi-kich-thuoc-co-ban-theo-chi-so-nhan-trac-hoc-907930.aspx
→ Khuyến nghị: số dưới đây đưa vào **hồ sơ công ty** (company profile) làm mặc định có thể sửa, gắn nhãn nguồn, không coi là "chuẩn quốc gia".

| Hạng mục | Giá trị thường gặp | Độ tin cậy / nguồn |
|---|---|---|
| Cao mặt bếp (VN) | 800–850 mm từ sàn (có nguồn ghi 860–1000) | [D] https://fptshop.com.vn/tin-tuc/dien-may/kich-thuoc-tu-bep-tieu-chuan-180954 · https://meta.vn/hotro/kich-thuoc-tu-bep-tieu-chuan-21437 |
| Khoảng mặt bếp → đáy tủ trên (VN) | phổ biến 600–650 mm, min 500, max 700; vùng hút mùi 600–800 | [D] cùng nguồn trên |
| Tương tự theo NKBA (Mỹ) | 15–18 in (~380–460 mm) tối thiểu | [D] (không đọc được PDF gốc) https://kb.nkba.org/uploads/2022/05/Kitchen-Planning-Guidelines.pdf · https://www.thewcsupply.com/pages/kitchen-design-guidelines-standard-clearances |
| Sâu tủ dưới / tủ trên (VN) | 560–600 / 300–350 mm; cao tủ trên 450–750 | [D] fptshop, meta.vn |
| Lối đi bếp | NKBA: lối đi ≥ 36 in (914 mm); lối làm việc ≥ 42 in (1 người), ≥ 48 in (nhiều người) | [D] (NKBA qua nguồn phụ) https://www.jlconline.com/how-to/interiors/the-31-rules-of-kitchen-design_o/ |
| Vùng với tay thoải mái | ~600–1400/1500 mm cho đồ dùng hằng ngày; dùng hằng tuần tới ~1850–2100 | [D], không xác minh được số Neufert gốc [?] https://www.bora.com/en-int/guide/designing-planning-accessible-kitchens · https://www.studiomatrx.org/guides/kitchen-storage-planning-guide |
| Thanh treo tủ áo | treo ngắn ~900–1050 mm khoảng thông thuỷ; treo dài ~1500–1700 (đến 1880); treo đôi: thanh trên ~1900–2000 khi tổng cao ≥ 2100 | [D], nguồn lệch nhau https://www.houzz.com.au/magazine/how-to-plan-your-new-wardrobe-like-a-pro-stsetivw-vs~44357655 · https://archipro.co.nz/assets/MemberUploads/Boston-Reach-in-Design-Guide.pdf |
| Sâu tủ áo treo | thông thuỷ ~600 mm để móc áo không chạm cánh | [D] https://www.studiomatrx.org/guides/why-wardrobes-become-inefficient |
| Khe trên thanh treo | kệ cách thanh ≥ ~50 mm (2 in) | [D] https://organizedliving.com/docs/default-source/design-guide-documents/closetcreationguide_storage-101.pdf |
| Bàn làm việc cố định | 29–30 in (~740–760 mm) là mặc định thị trường, BIFMA G1 cho **dải** chứ không ép 29 in | [D] https://www.officefurniture2go.com/guides/pdfs/OF2go_Straight_Desks_Top10_QA.pdf · https://eurekaergonomic.com/blogs/eureka-ergonomic-blog/bifma-g1-compliance-guide-public-offices |
| Chiều cao ngăn kéo tối đa | **không tìm được nguồn** [?]; thực tế giới hạn bởi chiều cao hộp ngăn kéo của hệ ray (vd. TANDEMBOX có vài cấp cao cố định) | |

---

## 4. Người dùng thật cần hình chiếu/đầu ra 3D nào, và dữ liệu tối thiểu

Hai nhóm nhu cầu khác hẳn nhau:

**A. Trình bày (designer → khách)**: phối cảnh có vật liệu/màu (mã MFC/laminate), ánh sáng, đặt trong phòng; mở cánh/ngăn kéo để khách hiểu công năng; mặt đứng có màu. Công cụ như 2020/Design Flex cạnh tranh ở chất lượng render + catalogue [D]. Dữ liệu tối thiểu: kích thước module, **vật liệu/màu từng mặt** (thường ghi chú bằng chữ/mã trên bản vẽ VN), vị trí cánh/ngăn kéo/tay nắm, chiều mở cánh. Với cad-guard: render "đẹp" là việc khó, ít tất định và dễ bị so với SketchUp/3ds Max — **không nên là trọng tâm v1**.

**B. Sản xuất (kỹ thuật/xưởng)**: mô hình tấm có độ dày, exploded/X-ray để kiểm liên kết, mặt cắt, cut list + dán cạnh, khoan, nhãn chi tiết, bản vẽ lắp — đây là phần mọi phần mềm sản xuất ở mục 1 cùng có [X/D]. Dữ liệu tối thiểu:

| Đầu ra | Dữ liệu bắt buộc | Lấy từ 2D thế nào |
|---|---|---|
| Mô hình tấm (carcass) | kích thước ngoài, độ dày ván (17/18), kiểu liên kết hông–nóc–đáy (hông trùm hay nóc trùm), kiểu hậu (rãnh/bắt vít, độ lùi, độ dày) | Bao ngoài từ mặt đứng+mặt bằng; nét đôi cách 17–18 mm trên mặt cắt/mặt bằng → độ dày; **liên kết + hậu nên lấy từ hồ sơ công ty** (mặc định xưởng), ghi đè nếu mặt cắt cho thấy khác |
| Đợt/kệ | cao độ từng đợt, cố định hay di động | Đường ngang trong mặt đứng/mặt cắt; phân biệt cố định/di động thường chỉ qua ghi chú → mặc định "di động" có cờ |
| Cánh | trùm toàn/nửa/lọt, khe, chiều mở (trái/phải/lật) | Ký hiệu chữ V/tam giác mở cánh trên mặt đứng (quy ước bản vẽ) → chiều bản lề; trùm/lọt: so mép cánh với mép hông trên mặt bằng; khe: mặc định công ty |
| Ngăn kéo | cao mặt, hệ ray, NL | Ô chữ nhật xếp chồng trên mặt đứng (có/không ký hiệu); NL suy từ sâu lọt lòng |
| Cut list + dán cạnh | danh sách tấm, vật liệu, cạnh nào dán (lộ ra ngoài) | Tất định từ mô hình tấm: cạnh nhìn thấy = dán; cạnh vào rãnh/áp tường = không dán (luật công ty) |
| Khoan | hệ bản lề, hệ ray, chốt kệ, liên kết (cam/minifix, chốt gỗ) | Hoàn toàn suy từ luật (System 32, bảng hãng) khi đã có cánh/ngăn kéo/đợt |
| Exploded / X-ray / mặt cắt | mô hình tấm | Hiển thị; không cần thêm dữ liệu |
| Mở cánh / kiểm va chạm | chiều mở, kiểu bản lề, vị trí tường/tủ lân cận | Mặt bằng có tường; độ nhô cánh theo bảng bản lề |

---

## 5. Đề xuất ưu tiên: 10 tính năng cho v1 "3D có ích cho sản xuất"

Nguyên tắc: (1) **mô hình tấm trước, render sau**; (2) mọi suy luận không chắc phải có cờ "giả định" hiển thị, sửa được, lưu vào changeset/supplement (khớp `cg.scene/1` + `--supplement`); (3) mặc định lấy từ **hồ sơ công ty** (ván 18, hậu rãnh/bắt vít, khe 2–3 mm, hãng bản lề) — đây là chỗ thay thế "chuẩn quốc gia" không tồn tại.

| # | Tính năng | Giá trị cho ai | Dữ liệu cần | Mức tất định | Rủi ro |
|---|---|---|---|---|---|
| 1 | **Mô hình tấm thay khối hộp**: hông/nóc/đáy/hậu/đợt/vách là tấm riêng có độ dày, theo "kiểu kết cấu" của công ty (hông trùm nóc/đáy, hậu rãnh hoặc bắt vít, lùi hậu X mm) | Kỹ thuật, xưởng, designer (thấy đúng độ dày) | Bao module + độ dày ván + hồ sơ kết cấu | Cao (sau khi có hồ sơ) | Thấp; sai kiểu kết cấu nếu hồ sơ sai → hiển thị rõ "kết cấu: mặc định công ty" |
| 2 | **Cut list + dán cạnh theo cạnh** (CSV/Excel; tên chi tiết, D×R×dày, vật liệu, số lượng, 4 cạnh dán/không, thớ) | Xưởng cắt/dán cạnh, dự toán | Từ #1 + luật "cạnh lộ thì dán" | Cao | Trung bình: xưởng VN đã có quy trình riêng (ABF/OpenCutList/Excel) → định dạng cột phải khớp mẫu của khách |
| 3 | **Đối chiếu 2D ↔ 3D** (kích thước tổng, tổng chiều cao đợt/ô = khoang, cánh phủ đủ khoang, khe đều) — xuất ra phát hiện như luật hiện có | Kỹ thuật kiểm bản vẽ (đúng sứ mệnh cad-guard) | Mặt đứng + mặt bằng + mặt cắt cùng module | Cao | Thấp; ghép nhiều hình chiếu của cùng module là khó nhất (đã có `--with`) |
| 4 | **Cánh có kiểu trùm, khe, chiều mở + hoạt cảnh mở cánh/kéo ngăn** | Designer, khách, kỹ thuật | Ký hiệu mở cánh trên mặt đứng; khe/trùm mặc định công ty | Trung bình–cao (ký hiệu V khá chuẩn) | Ký hiệu vẽ không thống nhất giữa thợ vẽ → cần luật nhận dạng + học layer |
| 5 | **Exploded view, X-ray (cánh/hậu trong suốt), mặt cắt tuỳ chọn** | Xưởng lắp, kỹ thuật, đào tạo thợ | Chỉ cần #1 | Cao | Thấp (thuần hiển thị) |
| 6 | **Bản lề tự động**: số lượng theo chiều cao/khối lượng (Blum 4–6 kg→2, 6–12 kg→3, cánh >600 mm thêm), vị trí (cách mép ~ quy ước công ty), chén 35, khoảng C 3–6 | Xưởng khoan, mua hàng (BOM phụ kiện) | Kích thước cánh + vật liệu (khối lượng riêng) + hãng bản lề | Cao khi đã chọn hãng | Bảng hãng thay đổi theo mã → để thành bảng tham số có phiên bản, ghi nguồn |
| 7 | **Kiểm va chạm & khoảng thông thuỷ**: cánh mở đụng tường/tủ cạnh/tay nắm, ngăn kéo kéo ra đụng cánh, lối đi < ngưỡng (NKBA 914/1067 mm), tủ trên quá thấp so mặt bếp | Designer, kỹ thuật | Mặt bằng có tường + chiều mở + độ nhô bản lề | Trung bình (độ nhô bản lề chỉ gần đúng) | Báo nhầm nếu thiếu tường trong bản vẽ → Skip thay vì báo |
| 8 | **Ngăn kéo theo hệ ray**: chọn NL ≤ sâu lọt lòng − dung sai; kích thước đáy/hậu/thành theo công thức hãng (vd. TANDEMBOX −75/−87; MOVENTO −42) | Xưởng, mua hàng | Sâu/rộng lọt lòng + hệ ray công ty | Cao | Công thức khác nhau giữa hãng/hàng nội địa (ray bi giá rẻ phổ biến ở VN) → bảng tham số theo hệ ray |
| 9 | **BOM phụ kiện + khoan cơ bản** (lỗ chén, lỗ đế bản lề, hàng chốt kệ System 32 cách mép 37, lỗ ray, cam/minifix) xuất DXF từng tấm theo quy ước layer kiểu ABF | Xưởng CNC | Từ #1, #6, #8 + quy ước layer khách | Cao về hình học | **Rủi ro cao về trách nhiệm**: lỗ sai = hỏng ván → chỉ bật sau khi đối chiếu với xưởng; v1 nên dừng ở "bản vẽ tham khảo", không phải file chạy máy |
| 10 | **Ghi chú công thái học có nguồn** (cao mặt bếp, khoảng tủ trên, vùng với tay, thanh treo, sâu tủ áo) như cảnh báo mềm, ngưỡng sửa được | Designer | Cao độ từ mặt đứng | Cao | Không có TCVN → dễ tranh cãi; luôn gắn "mặc định công ty / nguồn tham khảo", mức `info` |

**Không đề xuất cho v1**: render ảnh thực (vật liệu PBR, ánh sáng) — giá trị bán hàng có, nhưng ít tất định, nhiều đối thủ mạnh; G-code/nesting trực tiếp — để cho phần mềm CAM/ABF của khách, cad-guard chỉ cần xuất cut list/DXF chi tiết đúng chuẩn đầu vào của họ (BXF của Blum là định dạng trao đổi đáng cân nhắc sau v1 [?: chưa kiểm tra đặc tả công khai]).

**Thứ tự gợi ý**: #1 → #2 → #5 → #3 → #4 → #6 → #8 → #7 → #10 → #9. Ba mục đầu đã đủ để xưởng thấy 3D "không chỉ là hộp": tấm thật + danh sách cắt + exploded.

---

## Câu hỏi mở cần hỏi khách (để thay [?] bằng số thật)
1. Kiểu kết cấu chuẩn của xưởng: hông trùm hay nóc trùm; hậu rãnh (độ lùi, độ dày, độ sâu rãnh) hay bắt vít; chân tủ/len chân.
2. Hãng/mã bản lề và ray đang dùng (Blum, Hettich, Häfele, hàng nội địa) và khe cánh chuẩn.
3. Định dạng cut list/nhãn xưởng đang nhận (mẫu Excel, ABF, OpenCutList, phần mềm máy cắt/CNC).
4. Quy ước ký hiệu mở cánh, ngăn kéo, đợt di động trên bản vẽ của công ty.
5. Khối lượng riêng ván theo nhà cung cấp (MFC/MDF/plywood) để tính số bản lề.
