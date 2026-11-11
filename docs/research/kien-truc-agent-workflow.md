# Kiến trúc trợ lý AI: nhiều agent/sub-agent theo luồng xử lý (11/11/2026)

Câu hỏi: có nên chia trợ lý AI của CAD Guard thành nhiều agent / sub-agent phối hợp theo một luồng xử lý (ý tưởng như
ComfyUI, n8n: các "nút" nối nhau, mỗi nút làm một việc) để giải bài toán bản vẽ phức tạp không?

## 1. Trả lời ngắn

**Có, nhưng theo nghĩa "luồng các bước nhỏ, mỗi bước có đầu vào/đầu ra rõ, bước code trước, bước AI chỉ xử lý phần code
chưa giải được", không phải "nhiều AI nói chuyện tự do với nhau".** Người dùng không phải tự nối nút như ComfyUI; CAD
Guard dựng sẵn luồng, người dùng thấy tiến trình từng bước và duyệt ở những bước cần người.

## 2. Vì sao chia nhỏ tốt hơn một AI đọc cả bản vẽ

- Bản vẽ thật lớn: phiên 01 có 40 tờ, khoảng 15.000 đối tượng. Một lần gọi AI không chứa hết; nếu tóm tắt thì mất chi
  tiết (chính chỗ chứa số chiều sâu, chiều cao).
- Việc nhỏ, ngữ cảnh hẹp → AI chính xác hơn: "đọc chiều sâu của khối M2 từ mặt bằng và mặt cắt này" tốt hơn nhiều so với
  "dựng 3D cả hạng mục".
- Mỗi bước kiểm được riêng (bộ kiểm hình học, bằng chứng handle), đo được riêng (bộ đáp án bước 3), lưu kết quả theo nội
  dung (không chạy lại khi bản vẽ không đổi), chạy song song nhiều hạng mục.
- Khi sai, biết sai ở bước nào (phân vùng hình sai? ghép mặt đứng sai? đọc số sai?) thay vì "AI dựng sai".

## 3. Luồng đề xuất (mỗi ô là một "nút")

```
Đọc tệp ─► Hồ sơ trình bày ─► Phân vùng tờ/hình ─► (mỗi hạng mục, song song)
                                                   ├─ Ghép hình (mặt đứng ↔ mặt bằng ↔ mặt cắt ↔ hình bỏ cánh)
                                                   ├─ Chia khối (vách, tấm bù)
                                                   ├─ Đọc số: rộng · sâu · cao · cao độ · trần   ◄─ sub-agent riêng
                                                   ├─ Mặt trước: cánh · ngăn kéo · khoang hở
                                                   └─ Vật liệu
                                                 ─► Bộ kiểm hình học ─► Người duyệt ─► Dựng 3D / tấm / danh sách cắt
```

Mỗi nút: **code chạy trước** (tất định, rẻ, lặp lại được). Chỉ phần code chưa giải được mới **leo thang** sang
sub-agent AI với đúng phần dữ liệu cần (các hình của hạng mục đó, ảnh cắt vùng đó nếu cần, danh sách kích thước/ghi chú có
handle). Kết quả AI luôn qua bộ kiểm và hiện là "đề xuất" chờ người duyệt — giống cách đã làm cho hồ sơ trình bày, chia
khối, số thiếu.

Sub-agent theo loại câu hỏi (mỗi cái prompt ngắn, ví dụ mẫu riêng, đầu ra JSON có bằng chứng): phân vùng hình; ghép hình;
chia khối; đọc chiều sâu; đọc chiều cao/cao độ; mặt trước; vật liệu; soát nhất quán (so các số giữa các hình, chỉ ra mâu
thuẫn). Điều phối (orchestrator) là code, không phải AI: thứ tự, song song, gộp, xử lý mâu thuẫn (hai nguồn khác số →
hỏi người hoặc gọi sub-agent soát).

Hiển thị cho người dùng giống "lịch sử chạy" của n8n: mỗi hạng mục một dòng các bước, bước nào xong/đang chạy/cần duyệt,
bấm vào thấy đầu vào–đầu ra và bằng chứng. Không cần trình soạn nút kéo thả ở giai đoạn này.

## 4. Đã có gì, còn thiếu gì

Đã có (từng nút rời): hồ sơ trình bày (code + AI), phân vùng hình theo tiêu đề + tách cụm bản vẽ, ghép mặt đứng–mặt bằng
theo kích thước chung, chia khối XY + vách thật + hình bỏ cánh, mặt trước theo ký hiệu, số thiếu (code đọc mặt cắt + AI có
bằng chứng), 4 agent bổ sung bản đồ (loại hình, ghép hình, vật liệu, soát), bộ kiểm, màn duyệt, bộ đáp án đo.

Còn thiếu: bộ chạy luồng chung (nút có kiểu đầu vào/ra, lưu kết quả theo băm nội dung, chạy song song, ghi lịch sử chạy
`.cadguard/runs/`), sub-agent đọc số tách riêng theo từng loại số, sub-agent nhìn **ảnh vùng** (cắt ảnh hình chiếu) khi
cách trình bày quá lạ, màn "lịch sử chạy".

## 5. Ví dụ: chiều sâu, chiều cao có trên bản vẽ nhưng CAD Guard không nhận

Đo trên `test 2.dxf` và `TEST.dxf` (phiên Demo, ngoài repo): chiều sâu 600 **có ghi** bằng kích thước đứng trên mặt bằng
tủ áo; code chỉ lấy sâu từ đường bao thân tủ trên mặt bằng, đường bao không khớp khối nên bỏ qua kích thước có sẵn. Đây là
lỗ hổng của nút "Đọc số" (code), không cần AI: đã sửa — không khớp đường bao thì dùng kích thước sâu ghi trên mặt bằng nằm
ngang qua khối (nguồn "Ghi", dẫn handle). Tủ treo không dùng cách này (mặt bằng thể hiện tủ dưới). Kết quả: tủ áo sâu 600
lấy từ bản vẽ ở cả hai tệp; bộ 40 tờ không đổi.

Bài học cho kiến trúc: mỗi lần người dùng phải nhập một số mà bản vẽ có ghi, đó là một ca cho bộ đáp án; chạy bộ đáp án
sẽ chỉ ra nút nào bỏ sót, rồi sửa code nút đó trước, chỉ dùng AI cho phần code không thể làm tất định.

## 6. Thứ tự làm

1. Bộ đáp án (bước 3, đã có công cụ): người kỹ thuật lưu đáp án 15–20 hạng mục của 3–4 kiểu vẽ.
2. Bộ chạy luồng + lịch sử chạy; chuyển các nút sẵn có vào luồng; đo bằng bộ đáp án sau mỗi thay đổi.
3. Sub-agent đọc số theo loại (sâu, cao, cao độ, trần) có leo thang từ code, và sub-agent nhìn ảnh vùng.
4. Màn "lịch sử chạy" cho người dùng.
