# scripts/bootstrap.ps1 — cài lõi cad-guard, chạy test và quét thử DXF tổng hợp (Windows PowerShell).
# Chạy từ thư mục gốc repo:  powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root 'packages\core')

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host 'Chưa có Python. Cài Python 3.10 trở lên (python.org), tick "Add python.exe to PATH", rồi chạy lại.' -ForegroundColor Yellow
  exit 1
}
python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if ($LASTEXITCODE -ne 0) { Write-Host 'Cần Python 3.10 trở lên.' -ForegroundColor Yellow; exit 1 }

if (-not (Test-Path .venv)) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip | Out-Null
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { Write-Host 'Test không qua; xem lỗi ở trên.' -ForegroundColor Red; exit 1 }

& .\.venv\Scripts\python.exe -m cadguard audit (Join-Path $root 'fixtures\synthetic') --out (Join-Path $root 'report.html')
Write-Host ''
Write-Host "Xong. Mở file report.html ở thư mục gốc repo để xem báo cáo mẫu." -ForegroundColor Green
& .\.venv\Scripts\python.exe -m cadguard stats --json
