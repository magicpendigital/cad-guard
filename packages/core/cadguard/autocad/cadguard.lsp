;;; cadguard.lsp — cầu nối mỏng AutoCAD <-> cad-guard theo TỆP (hướng C, P1b "adapter xuất DXF + thư mục theo dõi").
;;;
;;; Không sửa bản vẽ, không lưu đè DWG, không gọi mạng, không dùng ActiveX (vla-/vlax-) để chạy được cả AutoCAD LT 2024+.
;;; Lệnh:
;;;   CGTHUMUC  chọn thư mục làm việc của cad-guard (nơi `cadguard watch` / `cadguard mcp --workspace` đang trỏ tới)
;;;   CGXUAT    xuất bản vẽ đang mở ra <thư mục>\<tên bản vẽ>.dxf bằng DXFOUT (bản sao; DWG đang mở giữ nguyên)
;;;   CGTOI     nhập một hoặc nhiều handle (cách nhau dấu phẩy/khoảng trắng) mà cad-guard hoặc trợ lý AI báo -> phóng tới và chọn
;;;   CGBAOCAO  mở báo cáo HTML do `cadguard watch` ghi cho bản vẽ đang mở
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

(defun cg:join (dir name / last)
  (setq last (substr dir (strlen dir)))
  (if (or (= last "\\") (= last "/")) (strcat dir name) (strcat dir "\\" name))
)

(defun c:CGTHUMUC ( / cur f)
  (setq cur (cg:folder))
  (princ (strcat "\n[cad-guard] Thư mục làm việc hiện tại: " (if cur cur "(chưa đặt)")))
  (setq f (getstring T "\n[cad-guard] Nhập đường dẫn thư mục làm việc (Enter để giữ nguyên): "))
  (cond
    ((= f "") (princ "\n[cad-guard] Giữ nguyên."))
    ((vl-file-directory-p f)
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
    (T
     (setq out (cg:join dir (strcat (cg:base) ".dxf")))
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

(defun c:CGTOI ( / txt hs ss e missing)
  (setq txt (getstring T "\n[cad-guard] Nhập handle (vd. 2A3F hoặc 2A3F,2A40): "))
  (setq hs (cg:split (strcase txt)) ss (ssadd) missing '())
  (foreach h hs
    (setq e (handent h))
    (if (and e (entget e))
      (ssadd e ss)
      (setq missing (cons h missing))))
  (if (> (sslength ss) 0)
    (progn
      (command "_.ZOOM" "_Object" ss "")
      (sssetfirst nil ss)
      (princ (strcat "\n[cad-guard] Đã phóng tới và chọn " (itoa (sslength ss)) " đối tượng.")))
    (princ "\n[cad-guard] Không tìm thấy đối tượng nào."))
  (if missing
    (princ (strcat "\n[cad-guard] Không có trong bản vẽ đang mở (bản vẽ đã đổi sau khi xuất, hoặc đối tượng nằm trong khối): "
                   (apply 'strcat (mapcar '(lambda (x) (strcat x " ")) (reverse missing))))))
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

(princ "\n[cad-guard] Đã nạp: CGTHUMUC, CGXUAT, CGTOI, CGBAOCAO.")
(princ)
