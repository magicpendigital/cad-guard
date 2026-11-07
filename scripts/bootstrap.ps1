# scripts/bootstrap.ps1 — cài lõi cad-guard, chạy test và quét thử DXF tổng hợp (Windows PowerShell).
# Chạy từ thư mục gốc repo:  powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
# Tệp này lưu UTF-8 có BOM để Windows PowerShell 5.1 hiển thị đúng tiếng Việt. Giữ nguyên khi sửa.
#
# Python hợp lệ: 3.10 đến 3.14 (khuyên dùng 3.13). Bản 3.15 trở lên chưa phát hành chính thức:
# nhiều thư viện (ví dụ PyYAML) chưa có sẵn gói cài, pip phải tự biên dịch và đòi Visual C++ Build Tools.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent $PSScriptRoot
$core = Join-Path $root 'packages\core'
Set-Location $core

$minVer = [version]'3.10'
$maxVer = [version]'3.14'

# Trả về phiên bản Python (kiểu [version]) của một lệnh, hoặc $null nếu chạy không được.
function Get-PyVersion([string]$exe, [string[]]$pyArgs) {
  $ErrorActionPreference = 'Continue'   # trong hàm này, lỗi của lệnh ngoài không làm dừng script
  try {
    $out = & $exe @pyArgs -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
    return [version]($out | Select-Object -First 1).ToString().Trim()
  } catch { return $null }
}

function Test-InRange($v) { return ($null -ne $v) -and ($v -ge $minVer) -and ($v -le $maxVer) }

# --- 1. Chọn Python ---
$pyExe = $null; $pyArgs = @(); $pyVer = $null
$candidates = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
  # Chỉ thử các bản Python đã cài (tránh để py hỏi/cài tự động một bản chưa có).
  $ErrorActionPreference = 'Continue'
  $installed = (& py --list 2>$null | Out-String)
  $ErrorActionPreference = 'Stop'
  foreach ($minor in '3.13', '3.12', '3.11', '3.14', '3.10') {
    if ($installed -match ('(?<![\d.])' + [regex]::Escape($minor) + '(?!\d)')) { $candidates += ,@('py', "-$minor") }
  }
}
if (Get-Command python -ErrorAction SilentlyContinue) { $candidates += ,@('python') }

foreach ($c in $candidates) {
  $exe = $c[0]
  $a = @(); if ($c.Count -gt 1) { $a = $c[1..($c.Count - 1)] }
  $v = Get-PyVersion $exe $a
  if (Test-InRange $v) { $pyExe = $exe; $pyArgs = $a; $pyVer = $v; break }
}

if (-not $pyExe) {
  Write-Host 'Không tìm thấy Python 3.10–3.14 trên máy.' -ForegroundColor Yellow
  Write-Host 'Cài Python 3.13 (bản ổn định) rồi chạy lại. Một trong hai cách:' -ForegroundColor Yellow
  Write-Host '  winget install Python.Python.3.13' -ForegroundColor Yellow
  Write-Host '  hoặc tải ở python.org/downloads, tick "Add python.exe to PATH" khi cài.' -ForegroundColor Yellow
  Write-Host 'Đóng PowerShell, mở lại, rồi chạy lại script này.' -ForegroundColor Yellow
  exit 1
}
Write-Host ("Dùng Python {0} ({1} {2})" -f $pyVer, $pyExe, ($pyArgs -join ' ')) -ForegroundColor Cyan

# --- 2. Môi trường .venv: nếu đã có nhưng dựng từ Python ngoài dải hợp lệ thì đổi tên (không xoá) ---
$venvPy = Join-Path $core '.venv\Scripts\python.exe'
if (Test-Path $venvPy) {
  $vv = Get-PyVersion $venvPy @()
  if (-not (Test-InRange $vv)) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $old = ".venv-cu-$stamp"
    Rename-Item (Join-Path $core '.venv') $old
    Write-Host "Môi trường .venv cũ dựng từ Python không phù hợp ($vv). Đã đổi tên thành $old (có thể xoá tay)." -ForegroundColor Yellow
  }
}
if (-not (Test-Path (Join-Path $core '.venv'))) {
  & $pyExe @pyArgs -m venv .venv
  if ($LASTEXITCODE -ne 0) { Write-Host 'Không tạo được môi trường .venv.' -ForegroundColor Red; exit 1 }
}
$py = $venvPy

# --- 3. Cài lõi + thư viện ---
& $py -m pip install --upgrade pip | Out-Null
# [agent] = SDK MCP cho `cadguard mcp` (trợ lý AI); [keyring] = kho khoá hệ điều hành cho khoá API.
& $py -m pip install -e ".[dev,agent,keyring]"
if ($LASTEXITCODE -ne 0) {
  Write-Host 'Cài thư viện thất bại; xem lỗi ở trên. Dừng trước khi chạy test.' -ForegroundColor Red
  Write-Host 'Nếu thấy "Microsoft Visual C++ 14.0 or greater is required": bạn đang dùng Python quá mới. Cài Python 3.13 rồi chạy lại.' -ForegroundColor Yellow
  Write-Host 'Nếu thấy "CERTIFICATE_VERIFY_FAILED" hoặc "Could not fetch URL": mạng đang chặn tải thư viện; thử mạng khác.' -ForegroundColor Yellow
  exit 1
}

# --- 4. Test ---
& $py -m pytest -q
if ($LASTEXITCODE -ne 0) { Write-Host 'Test không qua; xem lỗi ở trên.' -ForegroundColor Red; exit 1 }

# --- 5. Quét thử DXF tổng hợp (mã thoát 1 là bình thường: bản vẽ "xấu" cố ý có lỗi mức E) ---
& $py -m cadguard audit (Join-Path $root 'fixtures\synthetic') --out (Join-Path $root 'report.html')
Write-Host ''
Write-Host 'Xong. Mở file report.html ở thư mục gốc repo để xem báo cáo mẫu.' -ForegroundColor Green
& $py -m cadguard stats --json
