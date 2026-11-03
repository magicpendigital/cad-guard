# GitHub từ đầu — hướng dẫn từng bước cho người mới (Windows)

Dành cho bạn nếu mới làm quen với GitHub. Làm theo thứ tự, không bỏ bước. Chỗ nào có khung lệnh, bạn gõ (hoặc dán) đúng nguyên văn vào cửa sổ **PowerShell** rồi nhấn Enter.

> Cách mở PowerShell: nhấn phím Windows, gõ `PowerShell`, nhấn Enter. Để chuyển tới thư mục dự án: `cd D:\Projects\cad-guard`.

## 0. Năm từ cần biết

| Từ | Hiểu đơn giản |
| --- | --- |
| **Repository (repo)** | Thư mục dự án có theo dõi lịch sử. Máy bạn có một bản; GitHub giữ một bản trên mạng. |
| **Commit** | Một "điểm lưu" kèm lời ghi chú: chụp lại toàn bộ các tệp tại thời điểm đó. Làm trên máy bạn, chưa lên mạng. |
| **Branch (nhánh)** | Một dòng lịch sử riêng. Nhánh chính tên `main`. MCA làm việc trên nhánh `mca/...` rồi bạn mới ghép vào `main`. |
| **Remote / origin** | Địa chỉ bản trên GitHub. Tên mặc định là `origin`. |
| **Push** | Gửi các commit từ máy bạn lên GitHub. **Chỉ lúc này người khác (và GitHub) mới thấy.** |

Hình dung: commit là chụp ảnh tủ đồ; push là gửi ảnh lên kho lưu trữ. Chụp bao nhiêu lần cũng không ảnh hưởng ai cho tới khi gửi.

## 1. Kiểm tra máy đã có Git

```powershell
git --version
```

- Thấy `git version 2.x.x`: được, sang bước 2.
- Báo "không nhận ra": tải Git cho Windows ở `git-scm.com`, cài và **giữ nguyên các tuỳ chọn mặc định** (bản cài đã gồm Git Credential Manager, công cụ nhớ đăng nhập GitHub giúp bạn khỏi nhập mật khẩu mỗi lần). Đóng PowerShell, mở lại, gõ lại lệnh trên.

## 2. Khai báo tên và email (làm một lần cho cả máy)

```powershell
git config --global user.name "Magicpen"
git config --global user.email "magicpendigital@gmail.com"
git config --global --list
```

Dòng cuối in ra để bạn kiểm. Tên và email này sẽ gắn vào mỗi commit. Repo của chúng ta là **riêng tư**, nên email hiện ra chỉ người được mời mới thấy.

## 3. Tạo repo trống trên GitHub (làm trong trình duyệt)

1. Vào `github.com`, đăng nhập tài khoản của bạn (`magicpendigital`). Khuyên bật xác thực hai bước ở Settings → Password and authentication.
2. Bấm dấu **+** góc trên bên phải → **New repository**.
3. **Repository name:** `cad-guard`.
4. **Visibility:** chọn **Private** (riêng tư). Dự án này có thể liên quan dữ liệu khách; không để Public.
5. **Quan trọng:** **không** tick "Add a README", "Add .gitignore" hay "Choose a license". Repo phải **trống** vì thư mục trên máy bạn đã có sẵn các tệp đó. Tick nhầm sẽ gây lỗi lúc push (xem mục 9).
6. Bấm **Create repository**. Trang kế tiếp hiện địa chỉ dạng `https://github.com/magicpendigital/cad-guard.git`.

## 4. Nối thư mục trên máy với repo trên GitHub

```powershell
cd D:\Projects\cad-guard
git remote add origin https://github.com/magicpendigital/cad-guard.git
git remote -v
```

Lệnh cuối phải hiện hai dòng `origin ... (fetch)` và `origin ... (push)`.

## 5. Commit lần đầu

Trước tiên xem có gì sắp được lưu:

```powershell
git status
```

Các tệp màu đỏ là "chưa được theo dõi". Đây là lúc **kiểm tra an toàn**: danh sách không được có tệp `.dwg`, `.dxf` thật của khách, `.env`, hay tệp chứa khoá/mật khẩu. (Repo đã có `.gitignore` chặn sẵn các loại này, trừ 5 tệp `.dxf` tổng hợp trong `fixtures\synthetic\` là hợp lệ.)

```powershell
git add -A
git status
```

Lúc này tệp chuyển màu xanh, tức đã "xếp vào hàng chờ commit". Nếu thấy tệp lạ, **dừng lại** (xem mục 8), đừng commit.

```powershell
git commit -m "chore: khung dự án cad-guard"
git log --oneline
```

`git log --oneline` phải hiện một dòng commit. Đến đây mọi thứ vẫn chỉ nằm trên máy bạn.

## 6. Push lần đầu

```powershell
git push -u origin main
```

- Lần đầu, cửa sổ đăng nhập GitHub sẽ bật lên (hoặc trình duyệt mở ra): chọn **Sign in with your browser**, đăng nhập, bấm **Authorize**. Quay lại PowerShell.
- Thành công khi thấy dòng gần giống `branch 'main' set up to track 'origin/main'`.
- Tải lại trang repo trên GitHub (phím F5): bạn thấy các thư mục `packages`, `standards`, `docs`… là xong.

`-u` chỉ cần ở lần đầu; từ lần sau chỉ cần `git push`.

## 7. Nhịp làm việc hằng ngày

```powershell
cd D:\Projects\cad-guard
git status                         # xem đã đổi gì
git add -A                         # xếp mọi thay đổi vào hàng chờ
git commit -m "mô tả ngắn việc đã làm"
git push                           # gửi lên GitHub
```

- Muốn lấy bản mới từ GitHub (ví dụ làm ở máy khác): `git pull`.
- Ghi chú commit viết ngắn, nói **làm gì**: `"thêm luật TX-02"`, `"sửa tên layer trong chuẩn"`.
- Commit thường xuyên (mỗi xong một việc nhỏ). Commit nhỏ dễ hoàn tác.

### Khi MCA làm việc trong repo

MCA ghi code trên nhánh `mca/...`, **không** đụng `main`. Khi bạn đồng ý kết quả: `mca accept` ghép nhánh vào `main` trên máy bạn. Sau đó **bạn tự** push `main`:

```powershell
git status          # phải sạch, và đang ở nhánh main
git push
```

Agent của MCA không bao giờ tự push; việc đẩy lên GitHub luôn do bạn chủ động.

## 8. Điều không bao giờ commit

- Bản vẽ thật của khách (`.dwg`, `.dxf`), ảnh chụp bản vẽ.
- Tệp `.env`, khoá API, mật khẩu, mã token.
- Báo cáo sinh ra từ bản vẽ thật (`report.html`, `report.json`).

Nếu `git status` hiện tệp như vậy ở danh sách chờ commit:

1. **Chưa commit:** gỡ khỏi hàng chờ bằng `git restore --staged <tên tệp>`, rồi di chuyển tệp ra ngoài thư mục dự án.
2. **Đã commit nhưng chưa push:** dừng, **không push**. Gõ `git reset --soft HEAD~1` (huỷ commit vừa rồi nhưng giữ nguyên tệp), gỡ tệp ra như trên, commit lại.
3. **Đã push:** coi như dữ liệu/khoá đã lộ. Không tự xoá lịch sử. Đổi ngay khoá liên quan (nếu là khoá), giữ repo ở chế độ Private và hỏi lại người hỗ trợ trước khi làm gì tiếp.

## 9. Lỗi thường gặp

| Thông báo | Nghĩa là | Cách xử |
| --- | --- | --- |
| `fatal: not a git repository` | Đang đứng sai thư mục | `cd D:\Projects\cad-guard` rồi gõ lại |
| `Author identity unknown` | Chưa làm bước 2 | Làm bước 2 rồi commit lại |
| `remote origin already exists` | Đã nối rồi | `git remote -v` để xem; nếu địa chỉ sai: `git remote set-url origin <địa chỉ đúng>` |
| `Repository not found` | Gõ sai tên repo, repo chưa tạo, hoặc đăng nhập nhầm tài khoản GitHub | Kiểm tên ở `git remote -v` so với trang GitHub; đăng nhập đúng tài khoản |
| `Authentication failed` hoặc `Permission denied` | Đăng nhập hết hạn hoặc sai tài khoản | Gõ lại `git push`, đăng nhập lại khi cửa sổ hiện ra |
| `rejected ... fetch first` hoặc `non-fast-forward` | Trên GitHub đã có commit mà máy bạn chưa có (thường do lúc tạo repo đã tick README) | **Dừng.** Đừng dùng `--force`. Hỏi người hỗ trợ; hoặc tạo lại repo trống |
| `detected dubious ownership` | Git nghi ngờ quyền sở hữu thư mục | `git config --global --add safe.directory D:/Projects/cad-guard` |
| Cảnh báo `LF will be replaced by CRLF` | Khác kiểu xuống dòng giữa Windows và Linux | Bình thường, bỏ qua |
| `Unable to create '.git/index.lock': File exists` | Có tiến trình git khác đang chạy hoặc bị treo | Đóng các cửa sổ git/VS Code khác; nếu vẫn lỗi, hỏi người hỗ trợ trước khi xoá tệp |

**Không bao giờ dùng** `git push --force` hoặc `git reset --hard` khi chưa hiểu rõ: hai lệnh này có thể xoá công việc không lấy lại được.

## 10. Hoàn tác an toàn

| Muốn | Lệnh | Lưu ý |
| --- | --- | --- |
| Xem lịch sử | `git log --oneline` | Nhấn `q` để thoát |
| Xem đã đổi gì | `git diff` | Nhấn `q` để thoát |
| Bỏ thay đổi **chưa commit** của một tệp | `git restore <tên tệp>` | **Mất thay đổi đó**, không lấy lại được |
| Huỷ commit vừa làm (chưa push), giữ tệp | `git reset --soft HEAD~1` | An toàn |
| Đảo ngược một commit **đã push** | `git revert <mã commit>` | Tạo commit mới đảo ngược, không xoá lịch sử |

## 11. Danh sách kiểm trước mỗi lần push

- [ ] `git status` không có tệp bản vẽ thật, `.env`, khoá, báo cáo.
- [ ] Đang ở nhánh `main` (`git branch --show-current`).
- [ ] Repo trên GitHub là **Private**.
- [ ] Lời ghi chú commit nói rõ làm gì.

## 12. Muốn học thêm

- Tài liệu chính thức: `docs.github.com` (mục "Get started" và "Git basics").
- Khi bí, copy nguyên thông báo lỗi và hỏi trợ lý kèm lệnh vừa gõ; đừng thử các lệnh có `--force`.
