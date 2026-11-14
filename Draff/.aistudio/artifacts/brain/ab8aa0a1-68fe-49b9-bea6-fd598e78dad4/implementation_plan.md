# Kế hoạch phát triển CAD Guard — Hợp nhất Bản Local (`/plans`) & Quản lý Dự án Đa nguồn (Google Drive + Thư mục Máy tính)

## 1. Bối cảnh & Kiến trúc tổng thể

Qua rà soát toàn bộ tài liệu quy hoạch trong `/plans` (`cad-guard.md`, `cad-guard-direction.md`, `cad-guard-agent.md`, `cad-guard-3d.md`), `.gitignore` và mã nguồn Python cục bộ (`packages/core/cadguard/`), nguyên nhân bản chạy trên Cloud khác biệt với bản local gồm:

1. **Thiết lập `.gitignore` chặn dữ liệu bản vẽ**: Các tệp `*.dwg`, `*.dxf` (trừ thư mục tổng hợp khi chạy lệnh sinh mẫu), `Data sample/` và `telemetry.db` đều bị loại khỏi kho lưu trữ Git nhằm bảo mật NDA.
2. **Hai nhánh giao diện local chưa được hợp nhất vào Portal**:
   - `cadguard app`: Máy quét thư mục workspace thực tế (`Workspace.list_dxf`) và kiểm định luật trực tiếp trên tệp `.dxf`.
   - `cadguard studio` & `cadguard scene`: Bộ dựng khối 3D tất định (`cg.scene/1`) từ các hình chiếu 2D (`FN-VIEW-FRONT`, `FN-VIEW-TOP`, `FN-VIEW-SIDE`), khung xoay 3D trực quan, phân tích cụm hình học (`C1…`), biểu mẫu điền phần thiếu chiều cao/chiều sâu (`gaps[]`), đề xuất gán nhãn hình chiếu (`set_views`, `set_value`, `set_attrib`, `change_layer`) và xuất tệp `.glb`.
3. **Cập nhật quản trị chuẩn trong `plans/cad-guard-agent.md` (mục 9b)**:
   - Quyền duyệt luật được phân theo **Admin nhóm luật** (`Admin · SH`, `Admin · LY`, `Admin · TX`, `Admin · VW`, `Admin · FN`, `Admin · DH`, `Admin · PR`, `Admin · VS`, `Admin · 3D`, `Admin · PJ`).
   - Mọi thao tác nới chuẩn (tắt luật, đổi tham số hoặc thêm ngoại lệ dự án) bắt buộc phải có **Giải trình tối thiểu 10 ký tự** trước khi tạo yêu cầu duyệt.

### Sơ đồ kiến trúc hợp nhất

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                   NGUỒN DỮ LIỆU DỰ ÁN (PROJECT WORKSPACE SOURCES)                 │
├───────────────────────────┬───────────────────────────┬───────────────────────────┤
│  Google Drive OAuth 2.0   │   Thư mục Máy tính Local  │   Kho Mẫu Tổng hợp Sẵn    │
│  (Chọn thư mục trên mây,  │   (webkitdirectory /      │   (Synthetic Fixtures     │
│   quét & tải tệp .dxf)    │    kéo-thả nhiều .dxf)    │    chuẩn 4 phòng ban)     │
└─────────────┬─────────────┴─────────────┬─────────────┴─────────────┬─────────────┘
              └───────────────────────────┼───────────────────────────┘
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│              BỘ QUẢN LÝ DỰ ÁN & PHÂN LOẠI TỰ ĐỘNG (PROJECT MANAGER)               │
│  • Tự động gom nhóm tệp .dxf vào 4 phòng: Thiết kế | Kỹ thuật | 3D | CNC          │
│  • Gán chuẩn áp dụng riêng cho dự án (standards/projects/<mã-dự-án>.yaml)         │
└─────────────────────────────────────────┬─────────────────────────────────────────┘
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                 LÕI PHÂN TÍCH DXF & DỰNG KHỐI 3D (DXF & 3D ENGINE)                │
├─────────────────────────────────────────┬─────────────────────────────────────────┤
│  Bộ đọc DXF & Tách Artboard (2D Vector) │  Bộ dựng cảnh 3D Tất định (cg.scene/1)  │
│  • Đọc HEADER, LAYER, BLOCKS, ENTITIES  │  • Khớp hình chiếu Đứng / Bằng / Cạnh   │
│  • Tách trang theo Layout & Khung A3    │  • Gom cụm hình học (C1, C2…)           │
│  • Kiểm 66 luật tất định + AI Gemini    │  • Phát hiện phần thiếu chiều cao (gaps)│
└────────────────────┬────────────────────┴────────────────────┬────────────────────┘
                     ▼                                         ▼
┌─────────────────────────────────────────┐ ┌───────────────────────────────────────┐
│   KHUNG VẼ 2D SVG & KIỂM ĐỊNH ĐA TRANG  │ │  KHUNG STUDIO 3D XOAY KHỐI & XUẤT GLB │
│  • Vẽ vector thực tế từ tệp DXF tải lên │ │  • Xoay/thu phóng 3D trực tiếp        │
│  • Khoanh vùng đỏ vị trí vi phạm        │ │  • Điền bù chiều cao/sâu & tải .glb   │
└─────────────────────────────────────────┘ └───────────────────────────────────────┘
```

---

## 2. Thiết kế chi tiết các hạng mục triển khai

### 2.1. Tạo Dự án & Quét Thư mục Bản vẽ (Google Drive + Thư mục Máy tính)
- **Trình chọn & khởi tạo Dự án (Project Switcher & Modal tạo dự án)**:
  - Trên thanh công cụ trên cùng và đầu danh sách tệp cột trái, bổ sung bộ chuyển đổi dự án đang mở cùng nút **`+ Tạo / Mở dự án`**.
  - Cho phép đặt tên dự án, mã dự án (`project_id`), và chọn **Hồ sơ chuẩn áp dụng** (Chuẩn gốc `furniture-v0` hoặc cấu hình ngoại lệ riêng `standards/projects/<mã>.yaml`).
- **Hai nguồn nạp thư mục dự án giống Coding Agent**:
  1. **Kết nối Google Drive (Client-side OAuth 2.0 với quyền `drive.readonly`)**:
     - Xác thực qua Google Identity Services popup theo chuẩn iframe của AI Studio.
     - Duyệt danh sách thư mục trên Google Drive của người dùng; khi chọn một thư mục dự án, hệ thống tự động quét toàn bộ các tệp `.dxf` bên trong, hiển thị dung lượng và cho phép nạp trực tiếp nội dung tệp vào dự án.
  2. **Chọn thư mục từ máy tính (`webkitdirectory`) hoặc kéo-thả tệp `.dxf`**:
     - Cho phép chọn cả thư mục dự án trên máy tính; trình duyệt tự động lọc các tệp có đuôi `.dxf` (bỏ qua các tệp rác/ẩn), giữ nguyên đường dẫn tương đối (`webkitRelativePath`) để nhận diện cấu trúc thư mục con.
- **Tự động gom nhóm theo 4 phòng ban**:
  - Dựa vào đường dẫn thư mục con, tên tệp và cấu trúc lớp (layer) bên trong tệp DXF, hệ thống tự động phân loại tệp vào 4 nhóm: **`Thiết kế`**, **`Kỹ thuật`**, **`Thiết kế 3D`**, và **`Lập trình sản xuất`** (người dùng có thể đổi nhóm nếu muốn).
  - Bấm vào bất kỳ tệp nào trong danh sách sẽ lập tức nạp bản vẽ đó vào vùng làm việc chính.

### 2.2. Bộ đọc DXF Thực tế & Hiển thị Vector Đa trang (Real DXF Parser & Renderer)
- **Giải mã cấu trúc DXF thực tế**:
  - Xây dựng bộ phân tích DXF hoàn chỉnh đọc trực tiếp nội dung văn bản của tệp `.dxf` người dùng tải lên hoặc lấy từ Google Drive:
    - `HEADER`: Đơn vị bản vẽ (`$INSUNITS`), kiểu kích thước (`$DIMSTYLE`), phạm vi toạ độ (`$EXTMIN`, `$EXTMAX`).
    - `TABLES`: Danh sách `LAYER` (tên lớp, mã màu ACI, kiểu đường nét) và `STYLE` chữ.
    - `BLOCKS` & `ENTITIES`: Đọc toạ độ và thuộc tính thực tế của `LINE`, `LWPOLYLINE`, `CIRCLE`, `ARC`, `TEXT`, `MTEXT`, `DIMENSION`, và `INSERT` (khối khung tên `A3_TITLEBLOCK`, phụ kiện, hình chiếu).
- **Tách trang (Artboard) tự động & Kiểm định 66 luật**:
  - Tự động tách các trang theo tab `Layout` và tự động nhận diện các cụm khung tên `A3` xếp dàn hàng ngang/dọc trong không gian `Model`.
  - Dựng hình học vector SVG sắc nét theo đúng toạ độ thực của bản vẽ, khoanh vùng toạ độ lỗi và chạy kiểm định cả 2 tầng: **Tầng 1 (Luật tất định)** + **Tầng 2 (AI phân tích sâu kết cấu & sản xuất)**.

### 2.3. Hợp nhất Studio 3D (`cg.scene/1`), Bù chiều cao thiếu & Xuất tệp `.glb`
- **Chuyển đổi 2D Vector ↔ Studio 3D ngay trên khung bản vẽ**:
  - Trên thanh công cụ của vùng bản vẽ chính, bổ sung nút chuyển chế độ **`2D Bản vẽ` / `3D Studio (cg.scene/1)`** cùng nút **`Xuất .GLB`**.
- **Dựng khối 3D tất định & Phân tích cụm hình học (`C1, C2…`)**:
  - Tự động ghép các hình chiếu 2D (`FN-VIEW-FRONT`, `FN-VIEW-TOP`, `FN-VIEW-SIDE`) hoặc các cụm hình học (`clusters`) từ tệp DXF để dựng thành các khối hộp 3D (`parts`: hồi trái/phải, đáy, nóc, hậu, đợt, cánh, ngăn kéo).
  - Hỗ trợ xoay khối 3D bằng chuột trái, dịch chuyển bằng chuột phải, thu phóng bằng con lăn, bật/tắt khung dây cạnh và chọn từng chi tiết trên mô hình 3D để xem kích thước `Rộng × Sâu × Cao (mm)`.
- **Biểu mẫu điền phần thiếu chiều cao/chiều sâu (`gaps[]`) & Đề xuất từ AI Studio**:
  - Khi bản vẽ 2D chỉ có mặt bằng hoặc mặt đứng khiến chi tiết thiếu chiều thứ 3 (`missing_depth` / `missing_height`), bảng điều khiển Studio 3D hiển thị danh sách **Phần thiếu cần bổ sung (`gaps`)** và **Cụm hình học chưa gán hình chiếu (`C1…`)**.
  - Người dùng có thể nhập trực tiếp chiều sâu/chiều cao còn thiếu (ví dụ `600 mm`), gán vai trò hình chiếu (`front` / `top` / `side`), hoặc bật công tắc **Đồng ý gửi nội dung phiên cho AI** để nhận đề xuất gán nhãn tự động, cập nhật tức thì khối 3D và tải xuống tệp nhị phân chuẩn **`.glb`** (Binary glTF 2.0).

### 2.4. Quy trình Admin Nhóm luật & Giải trình Tối thiểu 10 ký tự (`plans/cad-guard-agent.md` 9b)
- **Phân quyền theo Admin Nhóm luật (`Rule Group Admin`)**:
  - Trong màn hình **Tập luật & Quản trị chuẩn**, bổ sung bộ chọn vai trò người duyệt theo đúng 10 tiền tố nhóm luật: `Admin · SH` (Khung & Trang), `Admin · LY` (Lớp), `Admin · TX` (Chữ & Dim), `Admin · VW` (Hình chiếu), `Admin · FN` (Nội thất & Vật liệu), `Admin · DH` (Vệ sinh bản vẽ), `Admin · PR` (Sản xuất CNC), `Admin · VS` (Thị giác), `Admin · 3D` (Phối cảnh 3D), `Admin · PJ` (Hồ sơ Dự án).
- **Ràng buộc giải trình ≥ 10 ký tự khi nới chuẩn**:
  - Khi bất kỳ người dùng nào tắt một luật, nới lỏng ngưỡng tham số, hoặc thêm ngoại lệ cho dự án (`standards/projects/<mã>.yaml`), hệ thống kiểm tra độ dài ô **Giải trình lý do** phải đạt **tối thiểu 10 ký tự** mới cho phép gửi đề xuất hoặc phê duyệt, lưu vết đầy đủ vào nhật ký kiểm toán.

---

## 3. Tiêu chí nghiệm thu & Kiểm thử
1. **Quản lý dự án**: Tạo được dự án mới từ cả **Google Drive** (chọn thư mục, quét `.dxf`) và **Thư mục máy tính** (chọn thư mục hoặc tệp `.dxf`), tự động phân nhóm vào 4 phòng ban và gán chuẩn dự án.
2. **Đọc & Vẽ DXF thực tế**: Tải tệp `.dxf` bất kỳ lên sẽ hiển thị đúng hình học vector 2D trên khung vẽ, tách đúng các trang Artboard và chạy kiểm định 66 luật + AI phân tích sâu.
3. **Studio 3D & Xuất GLB**: Chuyển sang chế độ `3D Studio` xoay được mô hình 3D bằng chuột, điền bù được kích thước chiều cao/chiều sâu còn thiếu (`gaps[]`), gán được cụm hình chiếu (`C1…`) và tải xuống được tệp `.glb` hợp lệ.
4. **Quản trị nhóm luật**: Kiểm tra chặn thao tác nới luật nếu giải trình dưới 10 ký tự và định tuyến đúng tới `Admin · <nhóm luật>` tương ứng.
