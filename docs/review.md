# Hồ sơ duyệt, ghi chú và Tailscale

Ngày 05/11/2026. Chạy theo tệp DXF; phát hiện lỗi bằng bộ luật tất định. Các ví dụ chỉ dùng dữ liệu tổng hợp.

## Bắt đầu tại máy thiết kế

1. Chạy `python -m cadguard app --workspace <thư-mục-dự-án>`. Trong màn Bản vẽ chọn **Hồ sơ duyệt**.
2. Mở **Công bố và cấp quyền**. Thêm email ĐĂNG NHẬP Tailscale với vai trò Khách, Thiết kế hoặc Kỹ thuật. Quản trị chỉ thực hiện trong app cục bộ có mã phiên.
3. Đặt tên bộ, chọn tệp/layout, chọn khách có trách nhiệm chốt, xác nhận đã đối chiếu trong CAD rồi công bố. Chọn một phiên bản trước nếu đây là lần sửa tiếp theo. Mỗi khách được chỉ định đều phải xác nhận.
4. Công bố tạo snapshot bất biến và SHA-256 đầy đủ dưới `.cadguard/reviews/` của dự án. Bản gốc giữ nguyên. Không dùng repo phát triển để chứa bản vẽ thật.

Khách chỉ thấy hồ sơ được chỉ định, bản xem trước và ghi chú “Trao đổi với khách”. Không có API mở thư mục, cấu hình AI, xem ghi chú nội bộ hay tải DXF nguồn. Thiết kế và kỹ thuật có quyền theo dự án. Cổng rà soát được ghim vào một thư mục khi khởi động, không thay đổi theo dự án đang mở trong ứng dụng cục bộ.

## Ghi chú và Agent

- Chọn Ghim điểm/Khoanh vùng và thao tác trên bản vẽ, hoặc ghi chú chung. Neo lưu bằng tọa độ bản vẽ, layout và mã băm phiên bản, không theo pixel màn hình. Người dùng bàn phím có nút Ghim tại tâm khung nhìn.
- Chọn phạm vi Nội bộ/Với khách; phạm vi không thay đổi sau khi gửi. Muốn đưa đề xuất nội bộ cho khách: xem lại rồi tự viết ghi chú/phản hồi chia sẻ mới.
- Có trả lời, phân công, đánh dấu đã xử lý và mở lại. Bình luận mới hoặc trả lời đưa ghi chú về Mở và làm mất hiệu lực trạng thái đã chốt. Lịch sử xác nhận cũ vẫn được giữ.
- Mọi cập nhật cần row version và request id. Nếu hai người cùng gửi, người gửi sau nhận thông báo tải lại; không ghi đè nội dung trước. Khi tải lại, nội dung đang nhập được giữ. Trang báo có cập nhật từ người khác mỗi 5 giây, không tự thay màn hình khi đang nhập.
- Trao đổi với Agent tạo phiên Studio riêng theo người và hồ sơ. Mở “Dữ liệu sẽ gửi” để xem chính xác bản tóm tắt và ghi chú. Phải đồng ý theo phiên trước khi gửi; thu hồi chặn lần gửi tiếp theo. Phiên hết hạn sau 30 phút hoặc phải mở mới khi hồ sơ/ghi chú đổi.
- Luồng này gửi JSON tóm tắt và ghi chú được hiển thị, không gửi ảnh/DXF. Không tự đưa phản hồi AI cho khách hoặc áp dụng chỉnh sửa. Luồng changeset hiện có tiếp tục yêu cầu xem trước, xác nhận, tệp mới và hoàn tác. Các công cụ MCP/ask/app Bậc 1 không nhận thêm trường nội dung.

## Hai bước chốt

Khách chốt đúng phiên bản sau khi hết ghi chú chia sẻ đang mở. Thiết kế/kỹ thuật không ký thay khách trong app. Kỹ thuật quét đủ hai chuẩn `furniture-v0` và `design-hygiene-v0` trên chính snapshot, xử lý hết ghi chú, hết lỗi E và ghi quyết định cho từng cảnh báo W rồi duyệt bàn giao. Chuẩn và hồ sơ công ty được đóng băng cùng bộ hồ sơ; đổi chuẩn cần công bố bộ mới.

Chỉ kỹ thuật/quản trị cục bộ được tải gói sản xuất khi đủ điều kiện. ZIP chứa manifest, DXF theo chỉ số tệp, báo cáo HTML/JSON, ghi chú và lịch sử duyệt. Manifest ghi tên bản vẽ tương ứng. Trước khi xem/duyệt/xuất, kiểm hash các snapshot; tệp bị sửa tay bị từ chối. Phiên bản mới không kế thừa chữ ký hoặc tự dời ghim của bản cũ.

Duyệt bộ hồ sơ là quy trình vận hành; không phải chữ ký số pháp lý. Nút bàn giao phòng ban cũ chỉ là dấu lịch sử cục bộ, không phải quyền xuất bộ sản xuất.

## Tailscale nội bộ trên Windows

Cài Tailscale chính thức từ [trang tải Windows](https://tailscale.com/download/windows), tự xử lý hộp thoại cấp quyền Windows và đăng nhập tài khoản công ty. Điện thoại cài Tailscale và kết nối. Khách ngoài mạng công ty cần chấp nhận chia sẻ máy theo [hướng dẫn Tailscale](https://tailscale.com/docs/features/sharing); quản trị tài khoản thực hiện lời mời và giới hạn chính sách truy cập HTTPS cho người được phép.

Tại gốc repo:

```powershell
python scripts/share.py start --workspace <thư-mục-dự-án>
python scripts/share.py status --workspace <thư-mục-dự-án>
python scripts/share.py stop --workspace <thư-mục-dự-án>
# Chỉ sau khi tự kiểm điện thoại qua mạng di động:
python scripts/share.py verify --workspace <thư-mục-dự-án> --confirm-mobile
```

Script chọn HTTPS 443, dùng 8443 nếu 443 đang phục vụ ứng dụng khác. Không ghi đè proxy khác, không bật Funnel, không chia sẻ cả thư mục, không tự gửi lời mời. Backend chạy ẩn trên `127.0.0.1:8781`. PID được đối chiếu thời điểm khởi tạo trước khi dừng, tránh giết tiến trình bị tái sử dụng PID. Script không tự mở bản vẽ.

Có thể chạy trực tiếp để thấy thông báo:

```powershell
python -m cadguard review --workspace <thư-mục-dự-án> --public-origin https://<máy>.<tailnet>.ts.net
```

Cấu hình [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve) trỏ tới `http://127.0.0.1:8781`. Giữ backend trên localhost: header `Tailscale-User-Login` chỉ tin khi qua proxy cục bộ. Dịch vụ/chương trình khác trên cùng máy thuộc ranh giới tin cậy của máy chủ; không coi header này là bằng chứng danh tính nếu backend bị mở ra LAN. Thiết bị gắn tag không có danh tính người dùng sẽ bị từ chối.

Sau khi cổng chạy, dùng Sao chép link hoặc Mã QR trong hồ sơ. Link không chứa mã quản trị. Kiểm bằng điện thoại **tắt Wi-Fi, bật dữ liệu di động và Tailscale**, thử người có/không có quyền, thu hồi quyền, và khởi động lại máy chủ trước khi đưa vào vận hành. Trạng thái script ghi thời điểm xác nhận thủ công bằng lệnh verify. Mỗi lần khởi động cổng mới cần xác nhận lại; khi proxy đổi hoặc backend dừng, trạng thái đã kiểm không còn hiệu lực.

Cần chạy lại script sau khi khởi động Windows để mở backend; Serve chạy nền có thể giữ cấu hình nhưng không thay thế tiến trình ứng dụng. Máy ngủ/tắt thì khách không truy cập được. Khi thu hồi chia sẻ, dừng proxy bằng script và thu hồi thành viên trong app; dữ liệu đã được người có quyền xem/tải trước đó không thu hồi được.

## Giới hạn preview

Bộ vẽ ezdxf >=1.4.5, Pillow thật, SVG lọc danh sách trắng hai phía. Chọn Model hoặc layout giấy. Phông thay thế và một số đối tượng đặc biệt có thể khác CAD; phải đối chiếu trong CAD trước khi công bố. Renderer dùng tiến trình con, tối đa 60 giây toàn bộ công việc, một tiến trình render tại một thời điểm. DXF trên 20 MiB hoặc SVG trên 10 MiB chuyển sang hình đơn giản hóa trong app; không được công bố hồ sơ chốt bằng hình này.

Cache trong `.cadguard/cache/` có nội dung bản vẽ, chỉ nằm tại dự án. Khóa cache gồm hash DXF, layout, phiên bản renderer và metadata phông. SQLite và snapshot cộng tác là dữ liệu vận hành riêng, không đẩy vào telemetry. Thư mục `.cadguard` không được liệt kê như nguồn DXF thông thường.
