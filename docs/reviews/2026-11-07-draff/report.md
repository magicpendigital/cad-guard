# Đánh giá bản clone Draff và khả năng ứng dụng vào CAD Guard

Ngày đánh giá: 07/11/2026. Phạm vi: source đang có tại `D:/Projects/cad-guard/Draff`, đối chiếu checkout CAD Guard hiện tại và HEAD `7a66d8e11fee3ecaace60f6879a6f51b7d2c1506`.

**Kết luận: có giá trị để tiếp nhận chọn lọc về quy trình làm việc và giao diện; chưa đủ điều kiện hợp nhất nguyên bản hoặc dùng bản Node/TypeScript để xử lý hồ sơ sản xuất.** Phần đáng tiếp nhận nhất là ghi chú duyệt/bàn giao cục bộ, giao diện nối kiểm lỗi–sửa–3D–review và hợp đồng trạng thái phiên. Những phần này vẫn cần sửa lỗi và bổ sung kiểm thử trước khi đưa vào CAD Guard.

Đây là báo cáo trước triển khai. Chỉ tạo tài liệu, log và chương trình kiểm chứng của đợt review; không sửa source sản phẩm, chuẩn hay cấu hình vận hành; không cài thêm dependency, không gọi LLM/Google Drive/AutoCAD, không push. Chỉ dùng DXF tổng hợp. Không sử dụng tuyên bố “hoàn thành” trong tài liệu clone làm bằng chứng nghiệm thu.

## 1. Cơ sở và cách đối chiếu

Đã đọc kế hoạch gốc, hướng theo tệp, chuẩn 58 luật, phiếu khảo sát khách, cùng kế hoạch Agent và 3D. Thứ tự ưu tiên dùng trong đánh giá:

- Hướng DXF theo tệp đã duyệt; lõi kiểm luật tất định và chạy cục bộ.
- Chuỗi Thiết kế → Kỹ thuật → Lập trình sản xuất → Xưởng. Diễn họa là nhánh bổ sung, không tự thay chuỗi sản xuất chính.
- LLM giải thích/đề xuất; trợ lý mặc định ẩn danh Bậc 1. Chế độ Studio gửi nội dung cần đồng ý theo phiên.
- Sửa bản vẽ có xem trước, xác nhận, tệp mới, kiểm chứng và hoàn tác.
- P0/P1c và thử với người dùng thật vẫn cần bằng chứng; kiểm thử tổng hợp không thay thế các bước này.

Checkout gốc có sẵn 11 tệp tracked đang sửa và các tệp preview/UI chưa tracked. Đã giữ nguyên. So sánh gồm cả working tree lẫn HEAD để tránh coi công việc đang làm của CAD Guard là thiếu sót của bản gốc.

Loại trừ cache và `.aistudio`, bản clone có **165 tệp cùng đường dẫn và 32 tệp riêng**. Trong 165 tệp chung: **148 chỉ khác LF/CRLF**, một tệp bootstrap khác thêm BOM, và **16 tệp có khác biệt nội dung**. Vì vậy, raw diff 165 tệp không phản ánh quy mô thay đổi thực. Danh sách và SHA-256 nằm trong [source-comparison.json](D:/Projects/cad-guard/docs/reviews/2026-11-07-draff/source-comparison.json).

So với HEAD, Python thay đổi thực chất ở sáu tệp: `model.py`, `agent/tools.py`, `assistant/toolspec.py`, `studio/llm.py`, `app/api.py`, `app/server.py`; thêm `contracts.py`. Các bộ đọc DXF, luật, chuẩn, Changeset engine, lõi Scene và CLI về cơ bản giữ nguyên sau chuẩn hoá xuống dòng. Không thấy bộ luật sản xuất mới được cài trong lõi Python. Các test Python có trong clone giữ nguyên nội dung so với HEAD; các API mới không có test chuyên biệt tương ứng.

## 2. Hai hướng triển khai đang cùng tồn tại trong clone

| Thành phần | CAD Guard hiện tại | Phần mới trong clone | Đánh giá |
|---|---|---|---|
| Lõi dữ liệu/luật | Python, `cg.drawing/1`, ezdxf + streaming reader, chuẩn YAML | Giữ lõi Python; thêm bộ đọc và phép kiểm khác bằng TypeScript | Giữ Python làm nguồn kết quả duy nhất; hai bộ luật vận hành riêng sẽ lệch nhau |
| Web | App Python local; có Studio riêng; preview ezdxf đang được cải tiến trong working tree | App Python thêm bốn chế độ; thêm Express server và `public/` độc lập | Chưa thực sự “một server, một UI” như `PLAN.md` tuyên bố |
| Kiểm bản vẽ | Chạy `audit_model` trên DrawingModel | Python tái dùng đúng lõi; Node trộn phép kiểm hình học với kết quả viết sẵn theo tên fixture | Không dùng kết quả Node để nghiệm thu hoặc báo sạch |
| Sửa | Động cơ thật, hash nguồn/đầu ra, kiểm đầu ra | Python giữ động cơ; Node có Changeset mô phỏng | Loại đường sửa Node khỏi phương án tích hợp |
| 3D | Lõi Scene tất định, thiếu thì báo gap | Python đưa Scene vào App; TS thêm xem cấu kiện, vật liệu, mở cánh, gợi ý ergonomics | Tiếp nhận tương tác UI; tránh đưa cấu kiện suy ra thành dữ liệu sản xuất |
| Dự án | Workspace cục bộ được chặn đường dẫn | ProjectManager nhiều dự án, nhập thư mục/Drive, upload chia mảnh | Ý tưởng có ích, phần vận hành còn thiếu lưu bền và định danh tệp |
| Trợ lý | Nhiều engine, ToolContext ẩn danh, kho khoá hệ điều hành | Python dồn ToolBox/specs; Node dùng Gemini hoặc trả lời mẫu | Tiếp nhận thiết kế dùng chung có kiểm soát; không thay assistant hiện tại bằng Node |
| Bàn giao | Có công cụ/tham chiếu ghi chú | Python có review notes lưu cục bộ, tổng hợp biên bản | Phù hợp kế hoạch, cần sửa điều kiện cổng bàn giao |

## 3. Những điểm chặn tiếp nhận nguyên trạng

Mức **Chặn**: phải giải quyết trước khi sử dụng phần liên quan với hồ sơ sản xuất. Mức **Cao**: có thể thử cô lập nhưng chưa đưa vào vận hành thường ngày.

| Mức | Phát hiện và bằng chứng | Hệ quả / cách xử lý trước tích hợp |
|---|---|---|
| **Chặn** | [Node Changeset](D:/Projects/cad-guard/Draff/src/changeset.ts:279) không áp phép sửa lên bản vẽ: ghi chuỗi DXF giả 32 byte; hash sinh từ tên/thời gian; kiểm chứng luôn `ok: true`. Probe chấp nhận cả thao tác không hỗ trợ khi tệp nguồn không tồn tại. | Có thể báo đã bảo toàn hình học dù đầu ra không chứa hình học. Chỉ dùng `cadguard.changeset` thật; không port đoạn này. `undo` của Node cũng chưa có bảo vệ hash/biên workspace như yêu cầu sản phẩm. |
| **Chặn** | [DrawingsManager](D:/Projects/cad-guard/Draff/src/drawings.ts:118) tạo phát hiện theo basename; tệp có mẫu tên `.cg-…dxf` được coi sạch. [Audit API](D:/Projects/cad-guard/Draff/server.ts:351) lấy counts/groups từ nguồn này rồi thay `findings` bằng kết quả ProjectManager; report và AI vẫn dùng nguồn khác. | Cùng tệp có thể ra số lỗi khác nhau giữa màn hình, JSON, report, chat. Mọi consumer phải nhận cùng một AuditResult từ Python. |
| **Chặn** | [Parser TS](D:/Projects/cad-guard/Draff/src/dxfParser.ts:123) mặc định mm, không xác thực DXF hoàn chỉnh. Probe với `THIS IS NOT A DXF` vẫn trả một sheet và 0 phát hiện. Phép kiểm Z và đơn vị dùng `else if`: khi có Z sai thì không báo sai đơn vị. Không sử dụng ngưỡng/hồ sơ YAML cho các phép kiểm này. | Thiếu hoặc hỏng dữ liệu bị hiểu thành sạch. Dùng hai reader hiện có; báo không đọc được/không đủ dữ liệu, không suy ra đã đạt. |
| **Chặn** | [Node server](D:/Projects/cad-guard/Draff/server.ts:16) nghe `0.0.0.0:3000`; các API thao tác không có token phiên/Host/Origin guard như Python. Upload giữ chunks trong RAM, thiếu trần tổng phiên/tổng byte và kiểm chỉ số chunk; parse chạy đồng bộ. | Trái mô hình local được bảo vệ; có nguy cơ truy cập từ mạng và treo tiến trình khi nhiều tệp lớn. Không chạy cạnh hệ thống hiện tại để thử trên dữ liệu thật. |
| **Chặn** | [Bàn giao Python](D:/Projects/cad-guard/Draff/packages/core/cadguard/app/api.py:765) chỉ dùng `E == 0` để đặt `ready`; chưa xét ghi chú review mức E, luật lỗi/bỏ qua hoặc dữ liệu bị cắt. Probe cho thấy có ghi chú E chưa xử lý nhưng vẫn `ready: true`. | Chỉ nên hiển thị “kết quả bộ luật đã chạy”. Muốn là cổng bàn giao cần quy định luật bắt buộc, dữ liệu đầy đủ, reviewer, ngoại lệ được duyệt và dấu vết xác nhận. |
| **Chặn** | [GLB API Python](D:/Projects/cad-guard/Draff/packages/core/cadguard/app/api.py:645) dựng lại cảnh không nhận supplement/views. UI gọi export chỉ với tên tệp. Probe: preview sau bổ sung có 3 module, snapshot còn 1; GLB khác GLB từ cảnh đã bổ sung. | Tệp xuất không thể đại diện đúng cảnh người dùng vừa duyệt. Export/snapshot phải nhận cùng trạng thái cảnh và hash của nguồn. |
| **Cao** | [contracts.py](D:/Projects/cad-guard/Draff/packages/core/cadguard/contracts.py:7) import `DrawingModel`, còn [model.py](D:/Projects/cad-guard/Draff/packages/core/cadguard/model.py:145) import ngược contracts. `import cadguard.contracts` trong tiến trình mới lỗi; import model trước thì qua. | Bỏ vòng import/re-export, giữ phụ thuộc một chiều. Cần test import trực tiếp, packaging và schema, không chỉ đường khởi động sẵn có. |
| **Cao** | [openFile](D:/Projects/cad-guard/Draff/packages/core/cadguard/app/static/app.js:303) chưa reset supplement/views theo tệp; [review store](D:/Projects/cad-guard/Draff/packages/core/cadguard/app/api.py:677) read–modify–write JSON không khoá, không ghi nguyên tử, không hash revision; parse lỗi trả danh sách rỗng. | Bổ sung của bản A có thể sang bản B khi trùng handle; nhiều request ghi chú có thể mất cập nhật; ghi chú cũ không biết bản vẽ đã đổi. Lưu theo file hash/revision, xử lý đồng thời và lỗi kho dữ liệu rõ ràng. |
| **Cao** | [Nút hỏi trợ lý](D:/Projects/cad-guard/Draff/packages/core/cadguard/app/static/app.js:1370) đưa `S.file` thật vào câu hỏi. Luồng chat truyền user messages nguyên văn. Node cũng gửi tên tệp/câu hỏi thẳng tới Gemini khi có khoá, dù `/api/session` ghi ẩn danh. | Lớp ẩn danh của tool không che được dữ liệu được UI tự chèn vào prompt. Dùng ID phiên; tách ngữ cảnh local và ngữ cảnh LLM; đồng ý riêng khi gửi nội dung Studio. Chưa thực hiện cuộc gọi mạng để kiểm chứng rò rỉ ngoài máy. |
| **Cao** | [ProjectManager](D:/Projects/cad-guard/Draff/src/projectManager.ts:41) lưu bằng Map trong RAM; khóa tệp bằng basename dù nhận relativePath. `getFileInspection` tạo bản tổng hợp nếu không tìm thấy tệp. Overlay chỉ là metadata/đường dẫn hiển thị. | Restart mất dự án; hai thư mục có tệp trùng tên đè entry; thiếu tệp bị che bằng mẫu. Cần lưu bền, ID đầy đủ, báo lỗi thiếu tệp và thực thi overlay thực sự. |
| **Cao** | [scene3d.ts](D:/Projects/cad-guard/Draff/src/scene3d.ts:443) tự dựng vách 18 mm, hậu/đợt/cánh từ khối bao; ergonomics có ngưỡng hard-code, nhãn “chuẩn VN”. `aiAudit.ts` tổng hợp nhận định viết sẵn từ `sheets.ts`, có nhánh không có insight được gắn `pass`. | Dễ coi cấu tạo minh hoạ hoặc thiếu dữ liệu là kết luận kỹ thuật. Nếu giữ phải ghi rõ nguồn: bản vẽ/người nhập/quy ước/minh hoạ. Luật mới cần nguồn, phiên bản chuẩn, fixture và đánh giá sai dương. |

Các giới hạn khác: `/api/mcp/sse` được quảng cáo trong [mcpCompanion](D:/Projects/cad-guard/Draff/src/mcpCompanion.ts:19) nhưng không có route phục vụ giao thức đó; “sync” chỉ cập nhật biến trạng thái. Có source C#/LISP nhưng không có project build/DLL/test tương thích các bản AutoCAD. Tuyên bố kết nối/sửa trực tiếp chưa được chứng minh. Tính năng phê duyệt luật, dashboard, bàn giao ở `public/app.js` có nhiều nhánh đổi trạng thái phía trình duyệt; hàm `accept()` thông báo đã lưu sau timer, không gọi API ghi DXF. Đây là prototype, không phải bằng chứng hoàn tất nghiệp vụ.

## 4. Những tính năng nên ứng dụng

Ưu tiên dưới đây là thứ tự tiếp nhận, không phải tình trạng đã được duyệt triển khai.

| Ưu tiên | Tính năng và giá trị | Phù hợp kế hoạch | Cách áp dụng để giảm ảnh hưởng hệ thống | Sẵn sàng hiện tại |
|---|---|---|---|---|
| **1** | **Ghi chú duyệt, đóng/mở lại, gắn rule/handle và biên bản bàn giao**: giảm thất lạc yêu cầu giữa các phòng | Bàn giao sản xuất và chuỗi ba phòng trong kế hoạch Agent | Tiếp nhận API Python và ý tưởng UI; lưu cục bộ riêng, theo revision; bổ sung khoá/atomic write, guard đường dẫn, migration và quy tắc ghi chú chặn | Chạy được API; phải sửa cổng ready và kho lưu |
| **2** | **Một luồng bốn chế độ kiểm–sửa–3D–review**: giữ tệp/ngữ cảnh khi chuyển việc, giảm chuyển ứng dụng | Tầng kiểm luật, Changeset A2 và 3D A/A2 | Gắn từng panel vào App hiện tại bằng cờ tính năng; tái dùng API/lõi thật, không thay nguyên bộ static hoặc dừng Studio cũ ngay | Có code Python/UI thực; chưa QA trình duyệt |
| **3** | **Click lỗi để focus, lọc layer, chọn cụm hình chiếu**: kỹ thuật viên tìm lỗi nhanh hơn | Trình xem/rà soát theo tệp | Dùng cách tương tác từ clone nhưng giữ renderer ezdxf hiện tại. Preview clone chỉ hiện một phần loại entity, cắt đỉnh và biểu diễn ARC thành CIRCLE, không phù hợp để thay renderer | Tiếp nhận hành vi UI; không tiếp nhận parser/renderer đơn giản |
| **4** | **Panel 3D + phần thiếu + gán front/top/side + xuất GLB** | Hướng 3D tất định đã có | Dùng `scene/` và `studio/clusters.py` hiện tại; lưu supplement/views theo hash tệp; dùng cùng scene cho preview/export/snapshot; giữ xung đột là chưa giải quyết | API dựng cảnh chạy; export chưa nhất quán |
| **5** | **Hợp đồng WorkspaceState có phiên bản**: nối audit, sửa, review, scene và hỗ trợ debug | Kiến trúc hợp đồng giữa các tầng | Tách DTO giao diện khỏi DrawingModel, phụ thuộc một chiều; có revision/hash, trạng thái skipped/truncated, validation chặt. JSON trạng thái phải ghi đúng “snapshot dữ liệu”, không gọi là đã QA hình ảnh | Ý tưởng tốt; import vòng và dữ liệu phiên chưa đầy đủ |
| **6** | **Một nơi định nghĩa schema/dispatch tool**: giảm lệch giữa API engine, MCP và Studio | Mô hình trợ lý A0/A2, ẩn danh Bậc 1 | Refactor riêng, giữ chữ ký/giới hạn/đa bộ lọc hiện có và kiểm đồng nhất tool list. Clone mới chuyển ToolBox/specs; MCP vẫn giữ khai báo riêng, Studio chỉ import tên chưa thực sự dùng chung | Có thể tái dùng một phần; chưa đạt “một nguồn duy nhất” |
| **7** | **Nút tác vụ mẫu, hỏi giải thích theo mã luật, báo trạng thái thao tác thật** | Bốn gói knowledge và thử người dùng A3 | Thêm vào UI hiện tại, dùng ID đã ẩn danh, lấy kết quả/cost/engine availability từ thực thi thật; không gán trạng thái hoàn tất bằng timer | Ít phụ thuộc, phù hợp thử sớm sau sửa prompt |
| **8** | **Danh mục dự án và phân loại bản vẽ theo phòng** | Hỗ trợ P0 và chuỗi bàn giao | Làm local trước, dùng workspace registry/relative path+hash và người dùng xác nhận phân loại; chưa bật đồng bộ Drive hoặc tự đổi chuẩn theo tên phòng | Mẫu nghiệp vụ có giá trị; backend Map cần thiết kế lại |
| **9** | **Upload có tiến độ/chia mảnh, tương tác 3D như đo/ẩn lớp/mặt cắt** | Tiện ích phụ cho tệp lớn/3D | Chỉ ưu tiên khi P0/A3 xác nhận nhu cầu. Cần giới hạn tài nguyên, parser ngoài luồng UI, kiểm toàn vẹn chunk; phép đo chỉ dựa hình học đã xác minh | Chưa có benchmark tải, không dùng làm đường đọc lớn thay streaming reader |

Theme, bố cục và mẫu review có thể tham khảo độc lập với backend. Tuy nhiên chưa có bằng chứng khả dụng, tiếp cận bàn phím hay hiệu năng giao diện trên thiết bị thật, nên không kết luận UI mới tốt hơn chỉ từ source.

## 5. Những phần nên hoãn hoặc loại khỏi lần tiếp nhận

- **Loại khỏi phương án tích hợp:** Changeset Node giả, audit/report theo tên tệp, fallback sinh bản vẽ tổng hợp khi thiếu dữ liệu, kết quả `pass` không có bằng chứng và trạng thái hoàn thành giả.
- **Hoãn:** AutoCAD palette/plugin/MCP companion. Chỉ xem lại nếu đường DXF theo tệp được đo là không đáp ứng; chưa có lý do đảo hướng CEO đã duyệt.
- **Hoãn:** Google Drive/OAuth/cloud upload. Đây là thay đổi ranh giới dữ liệu và vận hành; cần nhu cầu thật, quyền truy cập, lưu trữ, thu hồi quyền và đồng ý dữ liệu. `drive.readonly` trong source không tự chứng minh quy trình dữ liệu đã an toàn.
- **Hoãn:** ergonomics, đếm phụ kiện, khe hở, tự sinh cấu kiện tủ và “AI kiểm sâu” làm cơ sở quyết định sản xuất. Chỉ đưa thành gợi ý minh hoạ hoặc luật mới có nguồn/phiên bản và kiểm chứng đúng quy trình.
- **Không lấy nguyên:** `Draff/AGENTS.md` hoặc `PLAN.md` làm chính sách mới. Chúng có hướng thiết kế hữu ích nhưng còn tuyên bố đã hợp nhất và hoàn thành vượt quá bằng chứng source.

## 6. Kiểm chứng đã thực hiện và giới hạn

| Kiểm tra | CAD Guard hiện tại | Clone | Diễn giải |
|---|---|---|---|
| Pytest mặc định, venv chung có sẵn | Exit 0; 562 passed, 15 skipped | Exit 0; 549 passed, 16 skipped | Đếm ký hiệu kết quả từ output vì cấu hình `-qq` không in summary. Không bật slow; một số test tuỳ chọn bị skip. Không so số test để suy ra chất lượng: working tree gốc có test preview/UI bổ sung |
| CAD-Bench mặc định | 12/12 | 12/12 | `bench.reference:answer`, không gọi LLM; không kiểm đường Node hoặc tính năng UI mới |
| Hygiene hiện có | Exit 0 | Exit 0 nhưng phạm vi trống | `git -C Draff ls-files` có 0 tệp: clone không có index Git riêng trong snapshot này. Không dùng kết quả hygiene clone để chứng nhận sạch |
| JS syntax `node --check` | Không chạy lại vì không sửa source | Cả hai `public/app.js` và Python static JS qua | Chỉ cú pháp, không xác nhận render/DOM hay quy trình người dùng |
| Node build `npm run build` | Không áp dụng | Không chạy được: thiếu `tsc`/dependency | Không cài npm, không có lockfile trong snapshot. Chưa chứng minh cài đặt, build, khởi động hoặc độ ổn định server |
| Probe Python bổ sung | Không áp dụng | Import vòng được tái hiện; preview/state hoạt động; bàn giao và scene export có lỗi như mục 3 | Dùng DXF tổng hợp; không đổi source clone |
| Probe Node tách module | Không áp dụng | DXF sai vẫn 0 phát hiện; bỏ qua sai đơn vị khi có Z sai; Changeset giả vẫn báo đạt | Dùng Node strip TypeScript trong bộ nhớ, bỏ import chỉ dùng cho type để tải module. Đây là kiểm hành vi module, không thay thế production build |

Lần chạy đầu gặp lỗi quyền thư mục tạm của sandbox ở cả hai bản. Đã chạy lại cùng test/bench với quyền thực thi phù hợp, thư mục tạm nằm trong repo; kết quả chính thức là các lượt `*-verified.txt`. Không coi lỗi môi trường ban đầu là lỗi của clone.

Bằng chứng: [pytest hiện tại](D:/Projects/cad-guard/docs/reviews/2026-11-07-draff/current-pytest-verified.txt), [pytest clone](D:/Projects/cad-guard/docs/reviews/2026-11-07-draff/clone-pytest-verified.txt), [bench clone](D:/Projects/cad-guard/docs/reviews/2026-11-07-draff/clone-bench-verified.txt), [probe import/API](D:/Projects/cad-guard/docs/reviews/2026-11-07-draff/python-probes.json), [probe bàn giao/GLB](D:/Projects/cad-guard/docs/reviews/2026-11-07-draff/python-behavior.txt), [probe Node](D:/Projects/cad-guard/docs/reviews/2026-11-07-draff/node-probes.txt), [build Node](D:/Projects/cad-guard/docs/reviews/2026-11-07-draff/npm-build.txt).

Chưa thực hiện: QA hình ảnh/trình duyệt, AutoCAD, Drive/OAuth, LLM thật, kiểm tải/tệp 100 MB+, đóng gói/upgrade, lỗi mất điện/đồng thời, phép đo độ chính xác trên hồ sơ khách. Chưa xác minh quyền tái sử dụng code/tài sản hình ảnh mới hoặc license bắc cầu npm; tài liệu giấy phép clone chưa bao quát các thành phần Node/C#/assets mới. Vì vậy **chưa có tính năng mới nào đủ bằng chứng để cam kết vận hành ổn định nguyên trạng hoặc không ảnh hưởng hệ thống**.

## 7. Phương án tiếp nhận để trình duyệt

**Đợt A — Giao diện hỗ trợ và review cục bộ.** Giữ lõi, reader, luật, renderer ezdxf và luồng sửa hiện tại. Đưa vào từng panel/nút tác vụ và ghi chú review bằng cờ tính năng mặc định tắt; sửa lưu ghi chú và ẩn danh; biên bản chỉ mô tả kết quả kiểm đã biết, không tự ký duyệt. Tiêu chí: bật/tắt không đổi audit, không đổi DXF, không lộ dữ liệu khi hỏi trợ lý; ghi chú tồn tại sau restart, không mất khi hai request ghi đồng thời.

**Đợt B — Phiên 3D nhất quán và hợp đồng giao diện.** Bỏ import vòng; cùng một state có file hash/revision cho preview, supplement, views, snapshot, GLB. Tách state theo tệp; không trộn bản A/B khi đổi nhanh. Tiêu chí: GLB xuất đúng cảnh đã duyệt, thiếu dữ liệu vẫn hiện gap, thay nguồn làm vô hiệu bổ sung cũ, bộ test Scene/Studio và App cũ không hồi quy.

**Đợt C — Hợp nhất công cụ và danh mục dự án.** Làm refactor nhỏ riêng cho tool schema/dispatch và local project registry; chỉ xem Drive/plugin sau P0/A3. Tiêu chí: cùng tool list/quyền/ẩn danh trên các engine; MCP không có apply; cùng DXF+chuẩn+hồ sơ cho cùng kết quả trên CLI/App/assistant/report; không đổi telemetry chỉ số tổng hợp.

Mỗi đợt cần bản diff cụ thể, kiểm thử cho lỗi mới nêu trong báo cáo, smoke test trình duyệt và khả năng tắt/hoàn nguyên riêng; không thay cả ứng dụng bằng clone. Bảo toàn các sửa đổi chưa commit trước khi bắt đầu, không ghi đè standards hay tự đổi ngưỡng. Chỉ quyết định phạm vi sau khi người dùng xem báo cáo này. **Chưa thực hiện đợt A/B/C.**
