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

## 7. Đã làm (11/11/2026)

- **Bộ chạy luồng** `cadguard/pipeline.py` (`cg.pipeline-run/1`): mỗi hạng mục chạy các bước đọc theo hồ sơ → ghép hình →
  dựng khối → chia khối → đọc số còn thiếu → AI (chỉ khi code còn phần thiếu/đề xuất và người dùng bấm "Chạy có AI") →
  kiểm kết cấu → người duyệt. Ghi lịch sử 20 lần gần nhất ở `.cadguard/runs/<băm>/<hạng mục>.json`; khoá đầu vào (băm tệp +
  số người nhập + hồ sơ trình bày + kết cấu xưởng) không đổi thì dùng lại kết quả.
- App: nút "Luồng xử lý" ở thanh công cụ 3D: bảng hạng mục × bước (✓ xong, ✋ chờ duyệt, ⚠ cần xem, – bỏ qua, ✗ lỗi), bấm
  một dòng để mở hạng mục (`/api/pipeline/run|status|history`).
- **Kết cấu thùng tủ** `scene/structure.py` + Kết cấu xưởng (tự thêm vách ngăn, nhịp đợt tối đa, cánh rộng tối đa, nóc tủ
  dưới bằng thanh giằng): vách bắt buộc ở đường ráp mà cánh bắt bản lề vào, cạnh cột ngăn kéo, khoang có đợt quá nhịp (chỉ
  tại đường ráp cánh); kiểm cánh rộng > 600 / rộng hơn cao (Blum). Màn 3D: mục "Kiểm kết cấu"; danh sách cắt có "Vách ngăn",
  "Thanh giằng". Skill trợ lý `knowledge/skills/ket-cau-tu/SKILL.md` (kèm nguồn).

Chưa làm: sub-agent đọc số tách riêng theo từng loại số; sub-agent nhìn ảnh vùng hình chiếu; chạy song song nhiều hạng mục.

## 8. Bộ dữ liệu mô phỏng thay cho người ghi đáp án (11/11/2026)

Chưa có người kỹ thuật ghi đáp án nên dùng **agent thiết kế + bộ vẽ bằng code** (`cadguard/synth.py`, lệnh
`cadguard synth --out <thư mục> --n 36 --seed 7 [--brief "tủ áo 3 buồng có ngăn kéo"]`):

- Agent thiết kế tạo THÔNG SỐ đồ (`cg.furniture-spec/1`: tủ áo, tủ bếp hai hàng, kệ TV) theo luật kết cấu (cánh ≤ 600, cặp
  cánh, cột ngăn kéo, tấm bù); tuỳ chọn AI thiết kế theo yêu cầu bằng lời, qua `validate_spec` (sai luật thì loại).
- Bộ vẽ dựng DXF từ thông số theo 9 kiểu trình bày (nay 12, xem mục 9) (chuẩn; layer THAY; khung không số; ngăn kéo vẽ LINE; liền thân; hình bỏ
  cánh riêng; một tiêu đề chung cho hai hình; mặt bằng không đường bao; chiều sâu chỉ ở mặt cắt) và ghi đáp án đúng 100 %
  (máy vẽ ra), không phụ thuộc kết quả đọc của CAD Guard.
- Chấm: `cadguard bench3d --workspace <thư mục>`. Lần đầu bộ dữ liệu tìm ra 3 lỗi thật của CAD Guard, đã sửa: (1) cánh/ngăn
  kéo đơn phủ > 90 % mặt khối bị bỏ (nhận nhầm là tấm ốp); (2) đề xuất chia tủ treo theo hồi của tủ dưới (vách phải thuộc
  đúng khối); (3) tấm bù hẹp < 150 mm bị gộp vào tủ cạnh (giữ theo ghi chú "tấm fix" của hồ sơ trình bày).
- Kết quả 36 hạng mục (hạt giống 11): chỉ code 86 % (sai chiều sâu khi số sâu chỉ ghi ở mặt cắt), code + gợi ý tự áp 100 %.
  Bộ 40 tờ thật không đổi.

Giới hạn: dữ liệu tổng hợp đều đặn hơn bản vẽ thật; dùng để kiểm hồi quy và đo từng kiểu trình bày. Thêm kiểu mới mỗi khi
gặp một cách vẽ lạ ở bản vẽ thật; vẫn nên có vài đáp án thật để kiểm chéo.

## 9. Ca thật: hình bỏ cánh bị bỏ qua, vùng bo cong bị đọc nhầm (11/11/2026)

Người dùng thử `TESt 2 (1).dxf` (phiên Demo, ngoài repo): tủ áo 3 khối (tấm fix 830, tủ áo 1200, tủ minibar 600). Đo bằng
code, chỉ ghi số cấu trúc:

- **Tiêu đề chép trùng.** Hai mặt đứng đặt cạnh nhau đều tên "MẶT ĐỨNG BỎ CÁNH TỦ ÁO"; hình trái thật ra có cánh (ký hiệu mở
  cánh), hình phải mới bỏ cánh. CAD Guard coi cả hai là "bỏ cánh", dựng khối từ hình trái và đọc đợt cũng từ hình trái;
  hình phải (thanh treo, 2 hộc, ô tủ lạnh) chỉ dùng gợi ý chia khối. Sửa: tiêu đề trùng thì phân biệt theo diện tích ký
  hiệu mở cánh (không có ký hiệu thì theo số khung cánh/ngăn kéo); có ghi chú giải thích; người dùng chọn tay được
  ("Dùng làm hình bỏ cánh", khoá `interior:<hạng mục>`).
- **Đếm nét thành đợt.** Mỗi tấm vẽ hai nét (ván 25, đá 20, kính 10) nên tủ minibar ra "6 đợt". Sửa: tầng ngang = chồng nét
  ngang cách nhau ≤ 62 mm, dài gần bằng nhau, phải tựa hông/vách (đáy lòng ngăn kéo, đáy máy hút mùi không tính), bỏ tầng
  sát chân/nóc; loại theo ghi chú gần nhất (kính → đợt kính, đá → ván đỡ + mặt đá).
- **Ký hiệu trên layer khuất.** Hai polyline 3 điểm ở cạnh phải tủ minibar là đường khấu (hai đầu trên hai cạnh vuông góc,
  điểm giữa lồi về góc — khác ký hiệu mở cánh có hai đầu cùng cạnh); vòng tròn r ≈ 113 ở góc trên là vòng chú thích mối
  ghép. Hình chi tiết khấu cạnh bên (không tiêu đề hình, chỉ có dòng ghi chú) có cung R200. Sửa: hai loại
  này không còn vào bước tách khối/ký hiệu cánh; ghi thành `features` của khối (kèm chi tiết và bán kính), tấm hông trong
  danh sách cắt ghi "có khấu bo cong R200, xem chi tiết". 3D chỉ đánh dấu, không vẽ đúng đường cong.

Kết quả trên tệp này: tủ áo = 4 cánh, 2 tấm ngang (nóc hộc, đợt trên), 2 hộc trong + vách giữa hộc, 1 thanh treo, 1 đèn
LED; tủ minibar = 1 cánh soi, ván đỡ + mặt đá, 1 đợt kính, ô tủ lạnh (thiết bị, không sản xuất), 2 đường khấu, 1 vòng chú
thích. Vách ngăn suốt chiều cao do luật nhịp đợt tự thêm trước đây không còn khi có hình bỏ cánh (vách theo bản vẽ; kiểm
kết cấu vẫn cảnh báo đợt 1164 mm > nhịp 700).

Bộ 40 tờ thật: kích thước, số khối, số cánh không đổi; số đợt đổi ở 6 hạng mục theo hướng đúng hơn (đã soát bằng ảnh: hai
nét một tấm không còn đếm đôi, đợt từng khoang được nhận, đợt kính sau cánh kính vẽ nét khuất vẫn được tính). Bộ mô phỏng
thêm 3 kiểu (`trungtieude`, `noithat`, `khuat_chuthich`), đáp án có số nội thất; 36 hạng mục × 4 tổ hợp kiểu mới: 100 %
(lần đầu kiểu `trungtieude` tìm ra lỗi kệ TV chỉ có ngăn kéo khung kín, đã sửa bằng dấu hiệu thứ hai).

Giới hạn: khấu/bo cong chỉ là ký hiệu + ghi chú (chưa dựng hình cong); hộc trong lấy theo ô chứa chữ "HỘC"; thanh treo
nhận theo hình chữ nhật mảnh nét khuất trên khoang cao ≥ 800 hoặc có chữ "thanh treo".
