# cad-guard — Đánh giá hướng mở rộng: ảnh/phác thảo → bản vẽ → kiểm → 3D/render → lập trình sản xuất

Trạng thái: **ĐÁNH GIÁ, chờ CEO đọc** (05/11/2026). Bổ sung cho `plans/cad-guard.md`, `plans/cad-guard-direction.md` (hướng theo tệp, DXF chung, đã duyệt) và `plans/cad-guard-agent.md` (đề xuất agent). Chưa viết code, chưa thay đổi lộ trình đã duyệt.
Cách đọc nguồn: mục 7 tách rõ nguồn **đã kiểm** (trang chính thức, bài nghiên cứu) và nguồn **thứ cấp** (blog, tin tuyển dụng, bài PR của hãng). Các số liệu thị trường của công ty nghiên cứu thị trường chỉ để tham khảo thứ tự độ lớn.

## 1. Ý tưởng được đánh giá (diễn đạt lại thành 5 khối)

```text
[A] Ảnh chụp / phác thảo tay ──► dựng lại bản vẽ kỹ thuật
                                      │
[B] Bản vẽ kỹ thuật (DXF) ──► phân tích · làm sạch · soát lỗi · đạt chuẩn   ← đang làm (P0–P2)
                                      │
            ┌─────────────────────────┼──────────────────────────┐
[C] Dựng 3D từ bản vẽ         [D] Agent chọn ánh sáng,     [E] Bóc tách kỹ thuật · thông số ·
    đã đạt chuẩn                   góc máy, chuẩn bị render     dữ liệu theo quy chuẩn ──► nhà máy
```

Kết luận ngắn, xếp theo giá trị và độ chắc chắn:

| Khối | Khả thi kỹ thuật | Giá trị cho khách | Khuyến nghị |
| --- | --- | --- | --- |
| **B** Kiểm/làm sạch | Cao, tất định, đang làm | Cao nhưng **chỉ khi gắn với khâu sau**: bản vẽ sạch tự nó chưa ai trả tiền; bản vẽ sạch *để xuống máy không sai* thì có | Giữ làm nền, đổi trọng tâm luật sang "đủ dữ liệu để bóc tách" |
| **E** Bóc tách → dữ liệu sản xuất | Cao cho phần **tất định** (bảng chi tiết, bảng cắt, DXF theo tấm, nhãn); **không** để LLM sinh G-code | **Cao nhất** (giảm sai hỏng vật tư, rút thời gian lập trình, phục vụ cả báo giá) | Làm thành mục tiêu chính của sản phẩm; LLM chỉ hỏi/điền thông tin thiếu |
| **C** Dựng 3D | Cao **nếu** dựng từ *mô hình chi tiết* (khối E) chứ không từ hình học 2D thô; dựng từ 2D bất kỳ còn ở mức nghiên cứu | Vừa (tiết kiệm công dựng lại cho diễn hoạ; kiểm va chạm/khớp) | Làm sau E, là *sản phẩm phụ* của cùng một mô hình |
| **D** Agent ánh sáng/góc render | Vừa (kịch bản Blender headless + mẫu cài sẵn) | Thấp–vừa; hãng render (D5, Enscape, Coohom…) đang tự thêm AI | Tuỳ chọn, không đầu tư riêng; làm khi có thời gian hoặc theo yêu cầu khách |
| **A** Ảnh/phác thảo → bản vẽ | **Thấp–vừa.** Sản phẩm thương mại mới ở mức "bản nháp cần người kiểm"; không có số đo độ chính xác độc lập | Vừa cho tư vấn thiết kế (từ ý tưởng khách ra bản nháp nhanh); thấp cho nhà máy | Không làm theo kiểu "vẽ lại từ nét"; chỉ làm theo kiểu **trích tham số → sinh bản vẽ từ mẫu tham số**, có người xác nhận; đặt sau cùng |

**Nhận định tổng:** ý tưởng đúng ở chỗ nhìn cả chuỗi ba phòng (đã được dữ liệu thật xác nhận ở `docs/real-sample-profile.md` mục 4.1), nhưng **thứ tự giá trị ngược với thứ tự kể trong ý tưởng**. Thứ nối được cả ba phòng không phải "ảnh → bản vẽ" mà là một **mô hình sản phẩm có cấu trúc** (danh sách tấm/chi tiết với kích thước, vật liệu, cạnh dán, lỗ khoan, phụ kiện) được rút ra và kiểm từ bản vẽ kỹ thuật. Có mô hình đó thì 3D (C), dữ liệu máy (E) và báo giá đều là *xuất ra*; không có nó thì mỗi khối phải tự "hiểu" bản vẽ một lần nữa và sai lệch nhau.

## 2. Quy trình thiết kế → sản xuất trong nhà máy nội thất gỗ công nghiệp (research)

Mô tả dưới đây ghép từ tài liệu phần mềm (HOMAG woodWOP, Polyboard/OptiCut, Cabinet Vision), bài viết ngành và một tin tuyển dụng ở Hoài Đức (Hà Nội) mô tả đúng vị trí "lập trình sản xuất". Đây là quy trình phổ biến cho **đồ gỗ tấm (ván MDF/MFC/plywood)**; đồ gỗ tự nhiên, ghế, sofa có quy trình khác và không bàn ở đây.

```text
1 Thiết kế        Phương án, mặt bằng, phối cảnh; chốt với khách            → bản 2D/3D, bảng vật liệu sơ bộ
2 Kỹ thuật        Bản vẽ triển khai (shop drawing): mặt đứng/mặt cắt từng   → DWG/DXF có kích thước, vật liệu, phụ kiện
                  khối tủ, chi tiết liên kết, ghi chú
3 Bóc tách        Từ bản triển khai ra BẢNG CHI TIẾT: mỗi tấm = dài×rộng×dày, → bảng Excel/ERP; là đầu vào cho báo giá,
                  vật liệu, chiều vân, cạnh dán 4 phía, lỗ khoan/phay,          mua hàng và lập trình
                  mã chi tiết; bảng phụ kiện (bản lề, ray, minifix, chốt gỗ)
4 Lập trình SX    Chọn công nghệ (cưa panel saw hay nesting), xếp tấm         → chương trình máy: .mpr (HOMAG woodWOP),
                  (nesting/cut optimisation), chương trình khoan/phay,            bSolid/Biesse, hoặc DXF theo quy ước layer
                  nhãn mã vạch cho từng tấm                                       + G-code cho máy nesting phổ thông
5 Gia công        Cắt → dán cạnh → khoan (hệ 32 mm) → phay → kiểm             → tấm có nhãn
6 Lắp ráp, đóng gói, vận chuyển, lắp đặt tại công trình
```

Điều quan trọng cho cad-guard:

1. **Khâu 3 (bóc tách) là chỗ dữ liệu đổi bản chất**: từ *hình vẽ* sang *bảng có cấu trúc*. Phần mềm chuyên ngành (Cabinet Vision, imos, Mozaik, Polyboard, SWOOD) né khâu này bằng cách **mô hình tham số là nguồn sự thật**: thiết kế tủ bằng tham số, rồi bản vẽ 2D, bảng cắt, nesting, chương trình máy đều sinh tự động. Với công ty vẫn vẽ 2D trong AutoCAD (đúng bối cảnh của khách hàng hiện tại), khâu 3 là **thủ công, lặp lại, sai nhiều**: tin tuyển dụng ở Hoài Đức mô tả công việc gồm "đọc hiểu bản vẽ, bóc tách và phản biện phương án, triển khai trên Cabinet Vision và xuất file cắt CNC".
2. **Định dạng xuống máy không phải một**: HOMAG nhận `.mpr` (woodWOP) và DXF; nhiều hãng khác nhận DXF với quy ước layer riêng (layer = loại gia công, độ sâu); nesting tạo G-code theo hậu xử lý từng máy. Một bài giới thiệu triển lãm cho thấy phần mềm trung gian thường hỗ trợ cùng lúc woodWOP, NC-Hops, bSolid, TpaCAD, Maestro, Xilog và DXF. Nghĩa là **DXF theo quy ước + bảng chi tiết** là mẫu số chung thực tế, đúng với hướng "DXF làm định dạng chung" đã duyệt.
3. **Lỗi đắt nằm ở ranh giới 2→3→4**: kích thước trên hình khác số đo thật (đã thấy 0,5–5,9% kích thước bị ghi đè tay trong 5 mẫu thật), thiếu cạnh dán, sai chiều vân, thiếu lỗ khoan, hai chi tiết trùng mã, đơn vị/gốc toạ độ sai khi xuống máy. Đây là loại lỗi **kiểm được bằng code** khi đã có mô hình chi tiết.
4. **Nesting và tối ưu cắt đã có công cụ sẵn** (OptiCut, CutList Optimizer, HOMAG intelliDivide, F4Nest…). cad-guard không nên tự làm thuật toán nesting; chỉ cần xuất đúng đầu vào cho chúng.

Những điều **chưa biết về khách hàng cụ thể** (phải hỏi ở P0): máy CNC hãng nào, phần mềm CAM/nesting nào, ai bóc tách và bằng gì (Excel? Cabinet Vision?), định dạng họ đang giao cho máy, chi phí một lần cắt sai.

## 3. Đánh giá khả thi từng khối

### 3.1 [A] Ảnh chụp / phác thảo tay → bản vẽ kỹ thuật

Hiện trạng công nghệ (xem mục 7):

- **Vector hoá ảnh quét** (Scan2CAD và các dịch vụ tương tự): ra nét DXF nhưng *không hiểu* tỉ lệ, kiểu nét, không OCR chữ thành chữ; dịch vụ thương mại vẫn cần người sửa lại; con số "85% chính xác ở lượt đầu" là của bên bán dịch vụ, chưa kiểm.
- **AI bản vẽ → CAD tham số** (Backflip AI, add-in Fusion; nghiên cứu Drawing2CAD, CAD2Program, VNPT 2D→3D): tập trung vào **chi tiết cơ khí** (phay 3 trục, tiện); đầu ra là *bản nháp một phương án*, không có số đo độ chính xác độc lập; VNPT tự báo 90–95% với "chuẩn bản vẽ được hỗ trợ".
- **Phác thảo tay nội thất**: ứng dụng tiêu dùng (SketchDXF…) tự khuyến cáo "luôn kiểm mọi kích thước trước khi sản xuất".

Hệ quả: dựng lại bản vẽ kỹ thuật **từ nét vẽ** của ảnh/phác thảo để đưa thẳng vào kiểm và sản xuất là **chưa khả thi ở mức tin cậy sản xuất**, và vi phạm nguyên tắc "phát hiện lỗi bằng code tất định" vì toàn bộ hình học đầu vào sẽ là phỏng đoán của mô hình.

Cách làm khả thi hơn, phù hợp kiến trúc hiện có:

1. **Ảnh/phác thảo → tham số, không → hình học.** Mô hình thị giác-ngôn ngữ đọc ảnh và trả về *cấu trúc*: "tủ bếp dưới 3 khoang, rộng 2400, cao 820, sâu 600, 1 ngăn kéo, cánh MDF phủ melamine", kèm độ tin cậy từng trường và danh sách trường còn thiếu.
2. **Sinh bản vẽ từ mẫu tham số** (thư viện khối tủ/kệ/bàn dưới dạng ezdxf, đúng chuẩn công ty): hình học sinh ra là tất định, đã đúng chuẩn layer/chữ/kích thước, nên khối B kiểm được như bình thường.
3. **Người xác nhận bảng tham số trước khi sinh**, và bản sinh ra luôn mang nhãn "bản nháp từ ảnh" cho tới khi kỹ thuật duyệt.

Giá trị thật của A theo cách này: **tư vấn thiết kế và bán hàng** (từ ảnh tham khảo/phác thảo của khách ra bản nháp + báo giá sơ bộ trong vài phút). Với nhà máy, đầu vào gần như luôn là DWG từ phòng thiết kế, nên A ít giá trị. Đề xuất: **đặt A sau cùng**, chỉ khởi động khi (i) thư viện mẫu tham số đã tồn tại do khối E cần, và (ii) có khách tư vấn thiết kế yêu cầu.

### 3.2 [B] Phân tích, làm sạch, soát lỗi

Đang làm, đã có bằng chứng ban đầu. Điều cần đổi theo mục 1: ngoài luật "trình bày" (layer, chữ, kích thước), cần nhóm luật **"đủ dữ liệu để bóc tách"**: mỗi khối tủ có đủ mặt đứng/mặt cắt, mỗi tấm có kích thước đọc được bằng máy, vật liệu ghi theo danh mục, cạnh dán có ký hiệu, bảng phụ kiện khớp hình. Đây là cầu nối sang E và là thứ khiến B có giá trị tiền bạc. Các việc đã nêu ở `docs/real-sample-profile.md` mục 6 (đọc theo dòng, duyệt khối, chuẩn cấu hình theo công ty, học quy ước, phông tiếng Việt) vẫn đi trước.

### 3.3 [C] Dựng 3D từ bản vẽ đạt chuẩn

Hai con đường, khác hẳn nhau về độ khó:

| Đường | Đầu vào | Độ khó | Độ tin cậy |
| --- | --- | --- | --- |
| C1. Dựng từ **mô hình chi tiết** (khối E): mỗi tấm là một hộp dài×rộng×dày đặt theo vị trí lắp; phụ kiện là khối thư viện | Bảng chi tiết + vị trí | Thấp–vừa (hình học hộp, xuất glTF/OBJ/STEP; có thể sinh file SketchUp qua thư viện mở hoặc OBJ) | Cao, tất định |
| C2. Dựng từ **các hình chiếu 2D bất kỳ** (mặt bằng/đứng/cắt trong DWG) | Hình học thô | Cao; là bài toán nghiên cứu (CAD2Program, Drawing2CAD) với kết quả trên chi tiết cơ khí đơn giản | Thấp, không có bảo đảm |

Khuyến nghị: **chỉ làm C1.** Với phòng diễn hoạ, giá trị là "khối hình đúng kích thước, đúng vị trí, đặt tên theo mã chi tiết" để họ gán vật liệu và render; họ không cần cad-guard render. Định dạng bàn giao nên hỏi phòng diễn hoạ (SketchUp, 3ds Max, Blender, D5, Enscape…); glTF/OBJ/FBX là mẫu số chung, còn `.skp` cần thư viện riêng (chưa kiểm giấy phép). Giá trị thêm: từ 3D kiểm được **va chạm, hở, chồng** giữa các khối, một nhóm luật mới mà 2D không làm được.

### 3.4 [D] Agent chọn ánh sáng, góc máy

Khả thi về kỹ thuật: Blender chạy không giao diện bằng Python; agent chọn trong **tập mẫu cài sẵn** (3–5 bộ ánh sáng theo loại phòng, 3–4 góc máy theo kích thước phòng) rồi render xem trước độ phân giải thấp để người chọn. Nhưng:

- Hãng render đang tự thêm AI (D5, Enscape, Coohom, 3CAD AI Render của Cyncly dùng Gemini); phòng diễn hoạ có công cụ quen tay và gu riêng; tính năng này **không phải hàng rào cạnh tranh**.
- Giá trị thấp hơn nhiều so với E và C1; mỗi giờ bỏ vào D là một giờ không bỏ vào E.

Khuyến nghị: để D ở mức "có thể làm, không đầu tư riêng"; nếu làm thì làm dưới dạng *skill* cho agent (tri thức văn bản + vài kịch bản Blender) chứ không phải mô-đun sản phẩm.

### 3.5 [E] Bóc tách, thông số, dữ liệu sản xuất

Đây là khối đáng đầu tư nhất. Tách rõ phần tất định và phần LLM:

**Tất định (code):**

1. **Mô hình chi tiết** (`cg.product/1`, mở rộng của Drawing Model): tấm, phụ kiện, cụm; mỗi tấm có kích thước, vật liệu, vân, cạnh dán 4 phía, danh sách gia công (lỗ, rãnh, phay) với toạ độ; nguồn gốc (handle đối tượng DXF) để truy ngược.
2. **Rút từ bản vẽ**: giai đoạn đầu **bán tự động**: dựa vào quy ước của công ty (khối có thuộc tính, bảng chi tiết trong bản vẽ, layer vật liệu) và người xác nhận; tự động dần theo dữ liệu. Không hứa "đọc mọi bản vẽ".
3. **Luật kiểm trên mô hình chi tiết**: kích thước hình = kích thước bảng, tổng tấm = kích thước tủ trừ khe hở chuẩn, cạnh dán hợp lệ với vật liệu, mã chi tiết duy nhất, lỗ khoan trong phạm vi tấm, chiều vân với tấm có vân.
4. **Xuất**: bảng chi tiết và bảng phụ kiện (Excel/CSV theo mẫu khách và theo mẫu các phần mềm nesting phổ biến), **DXF theo từng tấm** với quy ước layer cấu hình được (đường bao khép kín, lỗ theo đường kính/độ sâu, gốc toạ độ, đơn vị), nhãn mã vạch. `.mpr` cho woodWOP làm sau nếu khách dùng HOMAG; **không** tự sinh G-code: để phần mềm nesting/CAM của máy làm, vì hậu xử lý theo máy là trách nhiệm của hãng máy.
5. **Luật kiểm đầu ra CNC**: đường bao khép kín, không trùng/đứt, đơn vị, gốc, layer gia công hợp lệ (đã có nhóm luật tương ứng trong chuẩn v0).

**LLM/agent (chỉ hỗ trợ):** hỏi người dùng các trường thiếu ("tấm hậu dày 9 hay 18?"), giải thích cảnh báo, gợi ý quy ước cạnh dán theo thói quen công ty, soạn ghi chú bàn giao. Nghiên cứu và chính nhà cung cấp CAM (CloudNC) đều khuyên **không** để LLM sinh chương trình máy trực tiếp: kết quả chỉ hợp với chi tiết đơn giản, có lỗi do mô hình "cắt bớt" mã, và sai một lần là mất vật tư hoặc hỏng máy.

**Giá trị đo được** (chỉ tiêu nên đưa vào hợp đồng thử nghiệm): thời gian từ bản triển khai được duyệt đến bộ dữ liệu xuống máy; số lỗi phát hiện trước khi cắt; số lần cắt lại / vật tư hỏng do bản vẽ; thời gian báo giá.

## 4. Tiềm năng ứng dụng theo loại khách

| Loại khách | Đau nhất | Khối dùng | Mức sẵn sàng trả tiền (nhận định) |
| --- | --- | --- | --- |
| **Nhà máy nội thất gỗ công nghiệp** (có CNC, 3 phòng nối tiếp; đúng khách hiện tại) | Bóc tách thủ công, sai hỏng ở ranh giới kỹ thuật → lập trình, bản vẽ mỗi người một kiểu | B + E (+ C1 để kiểm khớp) | Cao: chi phí sai hỏng đo bằng tấm ván và ngày công; dễ chứng minh ROI |
| **Công ty tư vấn thiết kế / thi công nội thất** (thuê xưởng ngoài) | Bản vẽ giao xưởng thiếu thông tin, báo giá chậm, dựng 3D lại từ đầu | B + E (bảng chi tiết để báo giá và giao xưởng) + C1 + A (nháp từ ảnh khách) | Vừa: trả cho "báo giá nhanh, giao xưởng ít cãi" hơn là cho "kiểm chuẩn" |
| **Xưởng nhỏ nhận gia công** (nhận DWG/ảnh từ nhiều khách) | Mỗi khách một chuẩn, phải vẽ lại trước khi lập trình | B (học quy ước + dọn) + E | Thấp–vừa; nhạy giá; cần gói rẻ, dùng theo tệp |
| **Phòng diễn hoạ / studio render** | Dựng lại khối hình từ 2D | C1 (+ D) | Thấp; họ coi là tiện ích |
| **Phần mềm/ERP ngành gỗ trong nước** (đối tác) | Thiếu đầu vào có cấu trúc từ bản vẽ | E dưới dạng API/mô-đun | Tiềm năng kênh phân phối, chưa có dữ kiện |

Bối cảnh thị trường (nguồn báo chí và hội thảo ngành, chưa có số thống kê chính thức về số doanh nghiệp): Việt Nam đứng thứ 2 thế giới về xuất khẩu đồ gỗ nội thất; phần lớn là doanh nghiệp nhỏ và vừa, chủ yếu gia công; mức chuyển đổi số còn thấp. Phần mềm chuyên ngành nước ngoài có rào cản giá và ngôn ngữ (Mozaik công bố 125 USD/tháng cho gói không CNC, Cabinet Vision báo giá theo mô-đun qua đại lý, imos không công bố), và được xây quanh **tủ tiêu chuẩn** hơn là **nội thất công trình đặt riêng** (sảnh, khu tiện ích, quầy) như 5 mẫu thật đã thấy. Khoảng trống hợp với cad-guard: **công ty vẫn vẽ 2D, làm đồ đặt riêng, cần một lớp cấu trúc hoá và kiểm giữa bản vẽ và máy mà không phải đổi sang phần mềm tham số.**

Rủi ro cạnh tranh: hãng CAD/CAM lớn (Cyncly, Hexagon, Autodesk) sẽ thêm AI chung; Coohom/3Dvinci đi từ thiết kế bán lẻ xuống sản xuất. Hàng rào của cad-guard (nhất quán với `plans/cad-guard-agent.md` mục 2.4) là **chuẩn + luật + dữ liệu lỗi thật của khách Việt Nam + nối xuống máy họ đang có**, không phải tính năng AI riêng lẻ.

## 5. Rủi ro chính của hướng mở rộng

| # | Rủi ro | Mức | Cách xử lý |
| --- | --- | --- | --- |
| 1 | **Phình phạm vi**: 5 khối = 5 sản phẩm; đội nhỏ, P0 còn "CHƯA ĐIỀN" | Cao | Cổng theo giai đoạn (mục 6); mỗi khối chỉ mở khi khối trước có số đo thật |
| 2 | **Chưa có bằng chứng nhu cầu** cho A, C, D; E mới được suy ra từ quy trình, chưa phỏng vấn phòng lập trình | Cao | Thêm vào P0: một buổi với phòng lập trình sản xuất và xưởng, thu bộ DXF/CNC họ đang giao máy |
| 3 | **Trách nhiệm khi dữ liệu sản xuất sai** (mất vật tư, hỏng dao, trễ đơn) | Cao | Mọi đầu ra sản xuất qua kiểm tất định + người duyệt; ghi nhật ký; hợp đồng thử nghiệm nói rõ trách nhiệm; không sinh G-code |
| 4 | **Độ chính xác chưa đo** (P1c) mà đã bàn 3D/sản xuất | Vừa | Không mở E rộng rãi trước khi B có số đo đúng/sai trên bản vẽ thật |
| 5 | Mô hình chi tiết phụ thuộc **quy ước từng công ty** | Vừa | Chuẩn cấu hình theo công ty + chế độ học quy ước (đã định hướng) |
| 6 | Pháp lý: DWG (giấy phép), ảnh của khách (bản quyền thiết kế, NDA), LLM đám mây với bản vẽ NDA | Vừa | Giữ nguyên quy tắc repo: DXF do khách xuất; BYOK; tuỳ chọn mô hình cục bộ |
| 7 | Phòng diễn hoạ/lập trình có công cụ riêng, **không muốn đổi** | Vừa | Chỉ giao *tệp* họ đã nhận quen (Excel, DXF, OBJ/glTF), không bắt dùng giao diện mới |

## 6. Lộ trình đề xuất (bổ sung, không thay lộ trình đã duyệt)

Các cổng (gate) nối tiếp; mỗi cổng có số đo để đi tiếp hoặc dừng.

| Cổng | Việc | Tiêu chí đi tiếp |
| --- | --- | --- |
| **G0** (= P0/P1 hiện tại) | Khảo sát đủ ba phòng, trong đó có phòng lập trình SX và xưởng; thu mẫu khâu 2 và 3; lõi đọc theo dòng, duyệt khối, chuẩn theo công ty; luật vệ sinh; đo độ chính xác (P1c) | ≥ 20 sự cố thật có chi phí; ≥ 10 luật có độ chính xác đo được; biết máy CNC, CAM và định dạng giao máy |
| **G1** | **Mô hình chi tiết** `cg.product/1` + rút bán tự động từ bản triển khai + luật kiểm khớp hình/bảng | Trên ≥ 10 bộ bản vẽ thật: bảng chi tiết sinh ra khớp bảng bóc tách tay ở ≥ 95% tấm (đo bằng người kỹ thuật) |
| **G2** | **Đầu ra sản xuất**: bảng chi tiết/phụ kiện theo mẫu khách, DXF theo tấm theo quy ước máy, nhãn; luật kiểm đầu ra CNC; thử trên máy thật với phòng lập trình | Một lô thật cắt từ dữ liệu cad-guard sau khi phòng lập trình duyệt; thời gian lập trình giảm đo được; 0 lỗi cắt do dữ liệu |
| **G3** | **3D từ mô hình chi tiết** (C1): glTF/OBJ, kiểm va chạm; bàn giao diễn hoạ | Phòng diễn hoạ dùng được tệp mà không dựng lại; luật va chạm bắt được ≥ 1 lỗi thật |
| **G4** | **Ảnh/phác thảo → tham số → bản nháp** (A) cho khách tư vấn thiết kế; D làm dưới dạng skill nếu còn thời gian | Có ≥ 1 khách tư vấn thiết kế cam kết thử; tỉ lệ bản nháp được duyệt không sửa kích thước ≥ 70% (đo) |

Ước lượng công sức (thô, theo tôi, đội 1–2 người làm toàn thời gian, chưa tính thời gian chờ khách): G1 2–3 tháng, G2 2–3 tháng, G3 1–2 tháng, G4 2–4 tháng; đều phụ thuộc vào tốc độ phòng kỹ thuật cung cấp mẫu và rà tay.

Điều cần CEO quyết sau khi đọc:

1. Đồng ý **đổi trọng tâm sản phẩm** từ "kiểm chuẩn bản vẽ" sang "cấu trúc hoá bản vẽ để xuống sản xuất" (B+E là lõi; C1 là phụ phẩm; A, D làm sau)?
2. Bổ sung P0: một buổi với **phòng lập trình sản xuất và xưởng**, lấy bộ DXF/CNC/bảng cắt họ đang giao máy (ẩn danh, ngoài repo).
3. Chấp nhận nguyên tắc **không sinh G-code**, chỉ giao dữ liệu cho phần mềm nesting/CAM của máy, và mọi đầu ra sản xuất phải qua người duyệt.

## 7. Nguồn

Đã kiểm (trang chính thức hoặc bài nghiên cứu):

- HOMAG woodWOP nhận DXF và `.mpr`: [forestsource.io/software/homag-woodwop](https://forestsource.io/software/homag-woodwop); nesting intelliDivide của HOMAG xuất chương trình woodWOP: [tapio.one](https://tapio.one/en/intellidivide-nesting), [tài liệu HOMAG](https://www.homag.com/fileadmin/software/brochures/intellidivide-nesting/onepager-intellidivide-nesting-en.pdf).
- Polyboard/OptiCut: bảng cắt, xuất `.mpr`, CSV cho phần mềm tối ưu tấm: [wooddesigner.org](https://wooddesigner.org/help-centre/homag-weeke-integration-polyboard/), [fittingsoftware](https://dcmpx.remotevs.com/au/com/fittingsoftware/www/PL/polyboard.htm).
- Phần mềm trung gian hỗ trợ cùng lúc woodWOP, NC-Hops, bSolid, TpaCAD, Maestro, Xilog, DXF: [holz-handwerk.de](https://holz-handwerk.de/en/exhibitors-products/t/tibek-cnc-technik-gmbh/smartwop).
- Mozaik giá công bố: [mozaiksoftware.com](https://www.mozaiksoftware.com/mozaik-manufacturing-subscription), [cyncly.com](https://cyncly.com/en-IN/mozaik/mozaik-products).
- CloudNC về LLM sinh G-code: [cloudnc.com](https://www.cloudnc.com/blog/can-i-use-chatgpt-for-generating-g-code) (nhà cung cấp, có lợi ích riêng).
- Nghiên cứu LLM sinh G-code chỉ trên bài toán đơn giản: [APEM 2025](https://apem-journal.org/Archives/2025/Abstract-APEM20-2_224-238.html); kiến trúc đa agent "LLM điều phối, công cụ vật lý quyết định": [arXiv 2605.04003](https://arxiv.org/pdf/2605.04003); [arXiv 2406.01893](https://arxiv.org/pdf/2406.01893).
- Bản vẽ 2D → CAD tham số: CAD2Program [arXiv 2412.11892](https://www.arxiv.org/pdf/2412.11892); Drawing2CAD [tóm tắt](https://www.emergentmind.com/topics/drawing2cad-framework); ánh xạ chú thích 2D → đặc trưng 3D [arXiv 2602.18296](https://fugumt.com/fugumt/paper_check/2602.18296v2_enmode); Backflip AI [backflip.ai](https://backflip.ai/), [blog Autodesk Fusion](https://www.autodesk.com/products/fusion-360/blog/?p=90581), [develop3d](https://develop3d.com/ai/backflip-ai-reverse-engineering/).
- Cyncly 3CAD AI Render (camera đặt tay trước khi render): [3cad.support.cyncly.com](https://3cad.support.cyncly.com/hc/en-us/articles/48554632094865).

Thứ cấp (blog, tin tuyển dụng, PR, báo chí; chưa kiểm độc lập):

- Vị trí "kỹ thuật viên Cabinet Vision" tại Hoài Đức, Hà Nội, mô tả bóc tách và xuất file CNC: [joboko.com](https://vn.joboko.com/viec-lam-ky-thuat-vien-cabinet-vision-lam-tai-nha-may-hoai-duc-xvi6595068); tin tuyển dụng quốc tế yêu cầu Cabinet Vision/imos/Mozaik: [weekday.works](https://jobs.weekday.works/we-re-hiring-cnc-designer-modular-furniture-interior-industry-at-the-design-company-wkdyvotpwv).
- Cabinet Vision tính năng và case study (của hãng): [forestsource.io](https://forestsource.io/software/cabinet-vision), [hexagon.com](https://hexagon.com/resources/resource-library/cabinet-vision-reduces-former-two-day-process-minutes), [casestudies.com](https://www.casestudies.com/company/vero-software/case-study/creative-woodwork-customer-case-study); giá Cabinet Vision theo đại lý: [myarchitectai.com](https://www.myarchitectai.com/blog/cabinet-vision-pricing).
- Vector hoá ảnh quét không hiểu tỉ lệ/kiểu nét, không OCR: [designpresentation.com](https://www.designpresentation.com/vectorizer/); dịch vụ scan-to-CAD và con số "85%": [designpresentation.com](https://www.designpresentation.com/scan-to-cad-conversion.html); SketchDXF khuyến cáo kiểm kích thước: [sketch-to-cad.onrender.com](https://sketch-to-cad.onrender.com/support); VNPT 2D→3D tự báo 90–95%: [global.vnpt.vn](https://global.vnpt.vn/vi/case-studies/ai-2d-to-3d-models).
- AI trong render (studio, PR): [ambar-estudio](https://ambar-estudio-landing.pages.dev/blog/ai-in-3d-rendering); D5 Render diễn đàn về tạo đèn từ ảnh: [forum.d5render.com](https://forum.d5render.com/t/automatic-creation-of-physical-light-from-an-inspiration-image/40635).
- Ngành gỗ Việt Nam: xuất khẩu 2025 trên 17 tỷ USD, nội thất gỗ ~61%: [tapchikinhtetaichinh.vn](https://thuehaiquan.tapchikinhtetaichinh.vn/them-nhieu-co-hoi-xuat-khau-cho-doanh-nghiep-nganh-go-103877.html), [sggp.org.vn](https://www.sggp.org.vn/nganh-go-viet-nam-phai-chuyen-tu-ban-go-sang-xuat-khau-he-sinh-thai-noi-that-va-thuong-hieu-post863635.html); chuyển đổi số còn thấp: [baodautu.vn](https://baodautu.vn/ty-le-chuyen-doi-so-trong-nganh-go-con-thap-d217185.html), [brandsvietnam.com](https://www.brandsvietnam.com/20182-go-cung-chuyen-doi-so); phần lớn là DNNVV gia công: [theleader.vn](https://theleader.vn/ba-thach-thuc-lon-voi-nganh-che-bien-go-va-noi-that-d23959.html).
- Quy mô thị trường phần mềm ngành gỗ (công ty nghiên cứu thị trường, số liệu khác nhau theo phạm vi): [credenceresearch.com](https://www.credenceresearch.com/report/woodworking-design-software-market), [datahorizzonresearch.com](https://datahorizzonresearch.com/furniture-manufacturing-software-market-38997).

## 8. Not yet specified

- Máy CNC, phần mềm CAM/nesting và định dạng giao máy của khách hiện tại (hỏi ở P0).
- Định dạng 3D phòng diễn hoạ muốn nhận; giấy phép thư viện ghi `.skp` nếu cần.
- Mẫu bảng bóc tách và quy ước cạnh dán/lỗ khoan của khách (cần bản thật, ẩn danh, ngoài repo).
- Cách tính giá và trách nhiệm pháp lý cho đầu ra sản xuất trong hợp đồng thử nghiệm.
- Thư viện mẫu tham số (tủ/kệ/bàn) cho khối A và sinh bản vẽ: phạm vi và ai cung cấp.
