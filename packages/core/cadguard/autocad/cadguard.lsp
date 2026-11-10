;;; cadguard.lsp — cầu nối mỏng AutoCAD <-> cad-guard theo TỆP (hướng C, P1b "adapter xuất DXF + thư mục theo dõi").
;;;
;;; Không sửa bản vẽ, không lưu đè DWG, không gọi mạng, không dùng ActiveX (vla-/vlax-) để chạy được cả AutoCAD LT 2024+.
;;; Lệnh:
;;;   CGTHUMUC  chọn thư mục làm việc của cad-guard (nơi `cadguard watch` / `cadguard mcp --workspace` đang trỏ tới)
;;;   CGXUAT    xuất bản vẽ đang mở ra <thư mục>\<tên bản vẽ>.dxf bằng DXFOUT (bản sao; DWG đang mở giữ nguyên)
;;;   CGTOI     nhập một hoặc nhiều handle (cách nhau dấu phẩy/khoảng trắng) mà cad-guard hoặc trợ lý AI báo -> phóng tới và chọn
;;;   CGDEN     tới đối tượng/layer mà người dùng vừa bấm "Tới trong AutoCAD" trên giao diện cad-guard (đọc .cadguard\goto.txt)
;;;   CGBAOCAO  mở báo cáo HTML do `cadguard watch` ghi cho bản vẽ đang mở
;;;   CGHELP    danh sách lệnh cad-guard và hướng dẫn chi tiết từng lệnh (gõ tên lệnh để xem)
;;; Nạp: APPLOAD -> chọn tệp này (hoặc thêm vào Startup Suite). Thư mục chứa tệp nên nằm trong Trusted Locations.
;;; Tệp lưu UTF-8; AutoCAD 2021+ (LISPSYS = 1, mặc định) đọc đúng tiếng Việt.
;;; Cần kiểm trên máy thử (docs/autocad.md mục 4): handle giữ nguyên qua DXFOUT; DXFOUT không đổi tên bản vẽ đang mở.

(setq cg:*env* "CadGuardFolder")

(defun cg:folder ( / f)
  (setq f (getenv cg:*env*))
  (if (and f (/= f "") (vl-file-directory-p f)) f nil)
)

(defun cg:base ( / n)
  (setq n (getvar "DWGNAME"))
  (vl-filename-base n)
)

;; Đường dẫn Windows chuẩn (dấu \): explorer.exe không mở được đường dẫn lẫn / và \ (gõ D:/... ở CGTHUMUC) mà mở Documents.
(defun cg:winpath (p)
  (vl-string-translate "/" "\\" p)
)

(defun cg:join (dir name / last)
  (setq dir (cg:winpath dir) last (substr dir (strlen dir)))
  (cg:winpath (if (= last "\\") (strcat dir name) (strcat dir "\\" name)))
)

(defun c:CGTHUMUC ( / cur f)
  (setq cur (cg:folder))
  (princ (strcat "\n[cad-guard] Thư mục làm việc hiện tại: " (if cur cur "(chưa đặt)")))
  (setq f (getstring T "\n[cad-guard] Nhập đường dẫn thư mục làm việc (Enter để giữ nguyên): "))
  (cond
    ((= f "") (princ "\n[cad-guard] Giữ nguyên."))
    ((vl-file-directory-p f)
     (setq f (cg:winpath f))
     (setenv cg:*env* f)
     (princ (strcat "\n[cad-guard] Đã đặt thư mục làm việc: " f)))
    (T (princ "\n[cad-guard] Thư mục không tồn tại. Tạo thư mục trước rồi chạy lại CGTHUMUC.")))
  (princ)
)

(defun c:CGXUAT ( / dir out fd ce ok)
  (cond
    ((= (getvar "DWGTITLED") 0)
     (princ "\n[cad-guard] Bản vẽ chưa có tên. Hãy lưu bản vẽ (SAVE) trước rồi chạy CGXUAT."))
    ((null (setq dir (cg:folder)))
     (princ "\n[cad-guard] Chưa đặt thư mục làm việc. Chạy CGTHUMUC trước."))
    ;; Bản đang mở là chính tệp DXF trong thư mục làm việc: xuất sẽ xoá rồi ghi đè tệp gốc. Không làm.
    ((= (strcase (setq out (cg:join dir (strcat (cg:base) ".dxf"))))
        (strcase (cg:winpath (strcat (getvar "DWGPREFIX") (getvar "DWGNAME")))))
     (princ (strcat "\n[cad-guard] Bản vẽ đang mở chính là tệp DXF trong thư mục làm việc: CGXUAT không ghi đè tệp này."
                    "\n[cad-guard] `cadguard watch` đã tự kiểm tệp; sau khi sửa và lưu (SAVE), báo cáo tự cập nhật.")))
    (T
     (if (findfile out) (vl-file-delete out))
     (setq fd (getvar "FILEDIA") ce (getvar "CMDECHO"))
     (setvar "FILEDIA" 0)
     (setvar "CMDECHO" 0)
     (command "_.DXFOUT" out "16")
     (setvar "FILEDIA" fd)
     (setvar "CMDECHO" ce)
     (setq ok (findfile out))
     (if ok
       (princ (strcat "\n[cad-guard] Đã xuất DXF: " out
                      "\n[cad-guard] Bản vẽ đang mở KHÔNG bị đổi. `cadguard watch` sẽ tự kiểm; xem kết quả bằng CGBAOCAO."))
       (princ "\n[cad-guard] Không thấy tệp DXF sau khi xuất. Kiểm quyền ghi thư mục hoặc chạy DXFOUT bằng tay."))))
  (princ)
)

(defun cg:split (s / out cur ch i)
  (setq out '() cur "" i 1)
  (while (<= i (strlen s))
    (setq ch (substr s i 1))
    (if (member ch '(" " "," ";" "\t"))
      (progn (if (/= cur "") (setq out (cons cur out))) (setq cur ""))
      (setq cur (strcat cur ch)))
    (setq i (1+ i)))
  (if (/= cur "") (setq out (cons cur out)))
  (reverse out)
)

;; Thêm các handle vào bộ chọn ss; trả danh sách handle không có trong bản vẽ.
(defun cg:addhandles (hs ss / e missing)
  (setq missing '())
  (foreach h hs
    (setq e (handent h))
    (if (and e (entget e))
      (ssadd e ss)
      (setq missing (cons h missing))))
  (reverse missing)
)

;; Thoát ký tự đại diện của ssget/wcmatch (# @ . * ? ~ [ ] - , `) để lọc đúng tên layer.
(defun cg:wcesc (s / out i ch)
  (setq out "" i 1)
  (while (<= i (strlen s))
    (setq ch (substr s i 1))
    (setq out (strcat out (if (vl-string-search ch "#@.*?~[]-,`") "`" "") ch))
    (setq i (1+ i)))
  out
)

;; Thêm mọi đối tượng trên layer (trong không gian/tờ đang xem) vào ss; trả T nếu có.
(defun cg:addlayer (name ss / sel i)
  (if (setq sel (ssget "_X" (list (cons 8 (cg:wcesc name)) (cons 410 (getvar "CTAB")))))
    (progn
      (setq i 0)
      (while (< i (sslength sel)) (ssadd (ssname sel i) ss) (setq i (1+ i)))
      T))
)

;; Phóng tới và chọn ss; in những gì không tìm thấy.
(defun cg:show (ss missing)
  (if (> (sslength ss) 0)
    (progn
      (command "_.ZOOM" "_Object" ss "")
      (sssetfirst nil ss)
      (princ (strcat "\n[cad-guard] Đã phóng tới và chọn " (itoa (sslength ss)) " đối tượng. Nhấn Esc để bỏ chọn.")))
    (princ "\n[cad-guard] Không tìm thấy đối tượng nào."))
  (if missing
    (princ (strcat "\n[cad-guard] Không có trong bản vẽ/tờ đang mở (bản vẽ đã đổi sau khi kiểm, đối tượng nằm trong khối, "
                   "hoặc ở tờ khác): "
                   (apply 'strcat (mapcar '(lambda (x) (strcat x " ")) missing)))))
  (princ)
)

(defun c:CGTOI ( / txt ss)
  (setq txt (getstring T "\n[cad-guard] Nhập handle (vd. 2A3F hoặc 2A3F,2A40): "))
  (setq ss (ssadd))
  (cg:show ss (cg:addhandles (cg:split (strcase txt)) ss))
)

;; Đọc tệp yêu cầu do giao diện cad-guard ghi (dòng "F <bản vẽ>", "H <handle>", "L <layer>") rồi phóng tới.
;; Giao diện (M3) gọi thẳng hàm này qua COM; người dùng gõ CGDEN khi không có COM (M2, AutoCAD LT).
(defun cg:den (path / fd line want hs ls ss missing)
  (cond
    ((not (findfile path))
     (princ "\n[cad-guard] Chưa có yêu cầu. Bấm \"Tới trong AutoCAD\" trên giao diện cad-guard trước."))
    (T
     (setq fd (open path "r" "utf8") hs '() ls '())
     (while (setq line (read-line fd))
       (if (> (strlen line) 2)
         (cond
           ((= (substr line 1 2) "F ") (setq want (substr line 3)))
           ((= (substr line 1 2) "H ") (setq hs (cons (strcase (substr line 3)) hs)))
           ((= (substr line 1 2) "L ") (setq ls (cons (substr line 3) ls))))))
     (close fd)
     (if (and want (/= (strcase want) (strcase (cg:base))))
       (princ (strcat "\n[cad-guard] Yêu cầu dành cho bản vẽ \"" want "\", không phải bản đang mở."
                      " Chuyển sang tab bản vẽ đó rồi chạy lại CGDEN."))
       (progn
         (setq ss (ssadd) missing (cg:addhandles (reverse hs) ss))
         (foreach l (reverse ls)
           (if (not (cg:addlayer l ss)) (setq missing (append missing (list (strcat "layer:" l))))))
         (cg:show ss missing)))))
  (princ)
)

(defun c:CGDEN ( / dir)
  (if (null (setq dir (cg:folder)))
    (princ "\n[cad-guard] Chưa đặt thư mục làm việc. Chạy CGTHUMUC trước.")
    (cg:den (cg:join dir ".cadguard\\goto.txt")))
  (princ)
)

(defun c:CGBAOCAO ( / dir html)
  (if (null (setq dir (cg:folder)))
    (princ "\n[cad-guard] Chưa đặt thư mục làm việc. Chạy CGTHUMUC trước.")
    (progn
      (setq html (cg:join dir (strcat ".cadguard\\reports\\" (cg:base) ".html")))
      (if (findfile html)
        (startapp "explorer.exe" (strcat "\"" html "\""))
        (princ "\n[cad-guard] Chưa có báo cáo. Chạy CGXUAT và kiểm `cadguard watch` đang chạy."))))
  (princ)
)

;; ---------- Đợt F: chạy cad-guard trên bản vẽ đang mở rồi áp vào chính bản đó (xem trước + xác nhận + undo) ----------
;; Tệp chạy cadguard-run.cmd do `cadguard autocad --copy-to <thư mục>` ghi cạnh tệp này.
(defun cg:runner ( / r)
  (setq r (getenv "CadGuardRunner"))
  (if (or (null r) (not (findfile r))) (setq r (findfile "cadguard-run.cmd")))
  (if (null r)
    (progn
      (setq r (getfiled "Chọn cadguard-run.cmd (do `cadguard autocad --copy-to` tạo)" "" "cmd" 0))
      (if r (setenv "CadGuardRunner" r))))
  r
)

(defun cg:run (action extra / r dir)
  (cond
    ((= (getvar "DWGTITLED") 0)
     (princ "
[cad-guard] Bản vẽ chưa có tên. Hãy lưu bản vẽ (SAVE) trước."))
    ((/= (getvar "DBMOD") 0)
     (princ "
[cad-guard] Bản vẽ có thay đổi chưa lưu. Hãy SAVE trước (cad-guard sao lưu bản đã lưu trước khi sửa)."))
    ((null (setq dir (cg:folder)))
     (princ "
[cad-guard] Chưa đặt thư mục làm việc. Chạy CGTHUMUC trước."))
    ((null (setq r (cg:runner)))
     (princ "
[cad-guard] Chưa có cadguard-run.cmd: chạy `cadguard autocad --copy-to <thư mục>`."))
    (T
     (c:CGXUAT)
     (startapp "cmd.exe" (strcat "/c \"\"" r "\" autocad-run " action " --workspace \"" dir "\" --drawing \""
                                 (cg:base) "\" --pause" extra "\""))
     (princ "
[cad-guard] Đã mở cửa sổ cad-guard: xem trước rồi xác nhận ở đó. Sau khi áp: gõ U để hoàn tác, SAVE khi ưng.")))
  (princ)
)

(defun c:CGUNICODE () (cg:run "unicode" ""))
(defun c:CGDICH ( / l)
  (initget "en zh")
  (setq l (getkword "
[cad-guard] Dịch sang [en = Tiếng Anh / zh = Tiếng Trung] <en>: "))
  (cg:run "translate" (strcat " --to " (if l l "en")))
)
(defun c:CGTRINHBAY () (cg:run "template" ""))
(defun c:CGKIEM () (cg:run "check" ""))

;; ---------- CGHELP: tra cứu lệnh ----------
;; Mỗi mục: (tên  mô-tả-ngắn  (dòng hướng dẫn chi tiết ...)). Giữ khớp docs/autocad.md.
(setq cg:*help*
  (list
    (list "CGTHUMUC" "Chọn thư mục làm việc của cad-guard"
      (list "Dùng khi: lần đầu, hoặc khi đổi sang thư mục dự án khác."
            "Cách dùng: gõ CGTHUMUC, dán đường dẫn thư mục (vd. D:\\CadGuardPhien\\phien-01), Enter."
            "Thư mục này phải TRÙNG thư mục `cadguard watch` / `cadguard app --workspace` đang mở."
            "Enter không nhập gì: giữ thư mục cũ. Thiết lập được nhớ cho lần mở AutoCAD sau."))
    (list "CGXUAT" "Xuất bản vẽ đang mở ra DXF vào thư mục làm việc"
      (list "Dùng khi: muốn cad-guard kiểm bản vẽ đang vẽ."
            "Cách dùng: lưu bản vẽ (Ctrl+S) rồi gõ CGXUAT. Tệp <tên bản vẽ>.dxf được ghi vào thư mục làm việc."
            "DWG đang mở giữ nguyên, không đổi tên. `cadguard watch` tự kiểm tệp DXF mới trong vài giây."
            "Từ chối nếu bản đang mở chính là tệp DXF trong thư mục làm việc (tránh ghi đè tệp gốc)."))
    (list "CGBAOCAO" "Mở báo cáo lỗi HTML của bản vẽ đang mở"
      (list "Dùng khi: đã CGXUAT và `cadguard watch` đang chạy."
            "Cách dùng: gõ CGBAOCAO; báo cáo mở trong trình duyệt."
            "Lỗi theo đối tượng có mã handle ở cột Vị trí: dùng CGTOI để tới."
            "Lỗi theo layer/kiểu chữ (vd. LY-01) không có handle: dùng nút 'Tới trong AutoCAD' trên cadguard app."))
    (list "CGTOI" "Tới và chọn đối tượng theo handle"
      (list "Cách dùng: gõ CGTOI, dán một hoặc nhiều handle (cách nhau dấu phẩy hoặc khoảng trắng), Enter."
            "AutoCAD phóng tới và chọn các đối tượng; handle không có trong bản vẽ được liệt kê."
            "Xem xong nhấn Esc để bỏ chọn. ĐỪNG nhấn Delete khi đang chọn."))
    (list "CGDEN" "Tới đối tượng vừa bấm 'Tới trong AutoCAD' trên giao diện"
      (list "Thường không cần gõ: bấm nút trên cadguard app thì AutoCAD tự nhảy tới (M3)."
            "Gõ CGDEN khi AutoCAD không tự nhảy (đang bận lệnh khác, hoặc app chạy với --no-autocad-com)."
            "Cần CGTHUMUC trỏ đúng thư mục app đang mở. Lỗi theo layer: chọn mọi đối tượng của layer trong tờ đang xem."))
    (list "CGKIEM" "Kiểm bản vẽ đang mở (vệ sinh + trình bày theo template)"
      (list "Cách dùng: SAVE rồi gõ CGKIEM; cửa sổ cad-guard hiện kết quả. Không sửa bản vẽ."))
    (list "CGUNICODE" "Chuyển chữ TCVN3/VNI sang Unicode (phông Be Vietnam Pro) ngay trong bản vẽ đang mở"
      (list "Cách dùng: SAVE rồi gõ CGUNICODE; xem trước trong cửa sổ cad-guard, gõ c để áp."
            "Áp trong một nhóm undo (gõ U để trả lại), có bản sao lưu DWG trong .cadguard/backup. Cần cài phông Be Vietnam Pro."))
    (list "CGDICH" "Dịch chữ bản vẽ đang mở sang Tiếng Anh hoặc Tiếng Trung"
      (list "Cách dùng: SAVE, gõ CGDICH, chọn en hoặc zh; ngôn ngữ nguồn tự nhận theo nội dung."
            "Số, đơn vị, mã vật liệu giữ nguyên; xem trước rồi xác nhận; gõ U để trả lại."))
    (list "CGTRINHBAY" "Điền khung tên theo template công ty (thông tin cố định, tỉ lệ theo hệ số khung)"
      (list "Cần template (cadguard template learn hoặc nút 'Học template từ tờ này' trên app)."
            "Chỉ đổi giá trị thuộc tính khung tên; không đụng hình vẽ, kích thước, chú thích."))
    (list "CGHELP" "Danh sách lệnh và hướng dẫn"
      (list "Gõ CGHELP, rồi gõ tên lệnh (vd. CGTOI) để xem chi tiết; Enter trống để thoát."
            "Nhấn F2 để mở cửa sổ chữ nếu dòng lệnh quá ngắn."))
    (list "CGBANG" "Mở bảng cad-guard cạnh màn hình (cần plugin CadGuard.Acad.dll)"
      (list "Có khi đã nạp plugin .NET (NETLOAD CadGuard.Acad.dll, xem docs/autocad.md mục 7)."
            "Bảng hiện danh sách lỗi, trò chuyện với trợ lý và hướng dẫn; cần `cadguard app` đang chạy."))
    (list "CGGHIM" "Hiện/ẩn ghim số lỗi tạm thời trên bản vẽ (cần plugin CadGuard.Acad.dll)"
      (list "Ghim chỉ vẽ trên màn hình, KHÔNG lưu vào DWG; số luôn cùng cỡ khi phóng."
            "Lấy lỗi từ báo cáo `cadguard watch` của bản vẽ đang mở. Gõ lại CGGHIM để ẩn."))
  )
)

(defun cg:helpline (it)
  (princ (strcat "\n  " (car it) (substr "            " 1 (max 1 (- 10 (strlen (car it))))) (cadr it)))
)

(defun c:CGHELP ( / name it)
  (princ "\n[cad-guard] Các lệnh:")
  (foreach it cg:*help* (cg:helpline it))
  (princ "\n  Quy trình thường dùng: CGTHUMUC (một lần) -> CGXUAT -> CGBAOCAO hoặc cadguard app -> CGTOI/CGDEN.")
  (while (/= "" (setq name (strcase (getstring "\n[cad-guard] Gõ tên lệnh để xem chi tiết (Enter để thoát): "))))
    (if (setq it (assoc name cg:*help*))
      (progn
        (princ (strcat "\n" (car it) " — " (cadr it)))
        (foreach ln (caddr it) (princ (strcat "\n  - " ln))))
      (princ (strcat "\n[cad-guard] Không có lệnh \"" name "\". Gõ một trong: CGTHUMUC CGXUAT CGBAOCAO CGTOI CGDEN CGKIEM CGUNICODE CGDICH CGTRINHBAY CGHELP CGBANG CGGHIM."))))
  (princ)
)

(princ "\n[cad-guard] Đã nạp: CGTHUMUC, CGXUAT, CGTOI, CGDEN, CGBAOCAO, CGKIEM, CGUNICODE, CGDICH, CGTRINHBAY, CGHELP. Gõ CGHELP để xem hướng dẫn.")
(princ)
