"""Đọc/ghi DWG bằng `accoreconsole.exe` của AutoCAD bản đầy đủ đã cài trên máy (không thư viện DWG bên thứ ba).

- `find_accoreconsole()`: biến môi trường `CADGUARD_ACCORECONSOLE`, rồi sổ đăng ký Windows
  (`HKLM\\SOFTWARE\\Autodesk\\AutoCAD\\R*\\*\\AcadLocation`), bản mới nhất trước.
- `dwg_to_dxf(src)`: mở DWG trong lõi AutoCAD không giao diện, `SAVEAS DXF 2018` ra tệp đệm
  `<thư mục của tệp>/.cadguard/cache/dwg-<băm>.dxf` (theo băm nội dung: chạy lại không chuyển lại). Tệp gốc chỉ đọc.
- `dxf_to_dwg(src, dst)`: ghi DWG 2018 từ một DXF (dùng sau khi áp changeset nếu người dùng cần DWG).
Lệnh gửi cho AutoCAD bằng LISP `(command ...)` trong tệp .scr tạm, không có câu hỏi tương tác nên không treo.
AutoCAD LT không có `accoreconsole`: khi đó dùng `CGXUAT` trong AutoCAD (docs/autocad.md).
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

TIMEOUT_S = 300.0
CACHE_DIR = Path(".cadguard") / "cache"


class DwgError(RuntimeError):
    """Không chuyển được DWG (tiếng Việt)."""


def _registry_locations() -> list[Path]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []
    out: list[tuple[str, Path]] = []
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Autodesk\AutoCAD")
    except OSError:
        return []
    with root:
        i = 0
        while True:
            try:
                rel = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            try:
                rk = winreg.OpenKey(root, rel)
            except OSError:
                continue
            with rk:
                j = 0
                while True:
                    try:
                        prod = winreg.EnumKey(rk, j)
                    except OSError:
                        break
                    j += 1
                    try:
                        with winreg.OpenKey(rk, prod) as pk:
                            loc, _t = winreg.QueryValueEx(pk, "AcadLocation")
                    except OSError:
                        continue
                    if loc:
                        out.append((rel, Path(loc)))
    out.sort(key=lambda t: t[0], reverse=True)
    return [p for _r, p in out]


def find_accoreconsole() -> Path | None:
    env = os.environ.get("CADGUARD_ACCORECONSOLE")
    if env:
        p = Path(env)
        return p if p.is_file() else None
    for loc in _registry_locations():
        exe = loc / "accoreconsole.exe"
        if exe.is_file():
            return exe
    which = shutil.which("accoreconsole")
    return Path(which) if which else None


def _lisp_str(p: Path) -> str:
    s = str(p).replace("\\", "/")
    if '"' in s:
        raise DwgError("Đường dẫn có dấu nháy kép: không chuyển được.")
    return f'"{s}"'


def run_script(src: Path, script: str, timeout: float = TIMEOUT_S, exe: Path | None = None) -> str:
    """Chạy `accoreconsole /i <src> /s <script>`; trả nhật ký (đã bỏ ký tự NUL)."""
    exe = exe or find_accoreconsole()
    if exe is None:
        raise DwgError("Không thấy accoreconsole.exe (cần AutoCAD bản đầy đủ). Đặt CADGUARD_ACCORECONSOLE hoặc "
                       "xuất DXF bằng CGXUAT trong AutoCAD.")
    with tempfile.TemporaryDirectory(prefix="cadguard-acc-") as tmp:
        scr = Path(tmp) / "cg.scr"
        scr.write_text(script, encoding="utf-8")
        try:
            proc = subprocess.run([str(exe), "/i", str(src), "/s", str(scr), "/l", "en-US"], cwd=tmp,
                                  capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise DwgError(f"AutoCAD không xong trong {timeout:.0f} giây.") from None
        except OSError as exc:
            raise DwgError(f"Không chạy được accoreconsole ({type(exc).__name__}).") from None
    raw = proc.stdout or b""
    for enc in ("utf-16-le", "utf-8"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("latin-1")
    return text.replace("\x00", "")


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dwg_to_dxf(src: Path, out: Path | None = None, *, timeout: float = TIMEOUT_S, exe: Path | None = None) -> Path:
    src = Path(src).resolve()
    if src.suffix.lower() != ".dwg" or not src.is_file():
        raise DwgError("Cần một tệp .dwg có thật.")
    if out is None:
        out = src.parent / CACHE_DIR / f"dwg-{_sha(src)[:16]}.dxf"
        if out.is_file() and out.stat().st_size > 0:
            return out
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = out.with_name(out.stem + ".part.dxf")
    if tmp_out.exists():
        tmp_out.unlink()
    script = ('(setvar "FILEDIA" 0)\r\n'
              f'(command "_.SAVEAS" "DXF" "_V" "2018" "16" {_lisp_str(tmp_out)})\r\n')
    log = run_script(src, script, timeout, exe)
    if not tmp_out.is_file() or tmp_out.stat().st_size == 0:
        tail = " ".join(re.findall(r"error[^\r\n]*", log, re.I)[-2:])
        raise DwgError("AutoCAD không ghi được DXF" + (f" ({tail})" if tail else "") + ".")
    os.replace(tmp_out, out)
    return out


def dxf_to_dwg(src: Path, dst: Path, *, timeout: float = TIMEOUT_S, exe: Path | None = None) -> Path:
    src, dst = Path(src).resolve(), Path(dst).resolve()
    if dst.exists():
        raise DwgError(f"Tệp '{dst.name}' đã có: không ghi đè.")
    script = ('(setvar "FILEDIA" 0)\r\n'
              f'(command "_.SAVEAS" "2018" {_lisp_str(dst)})\r\n')
    run_script(src, script, timeout, exe)
    if not dst.is_file():
        raise DwgError("AutoCAD không ghi được DWG.")
    return dst


def ensure_dxf(path: Path) -> Path:
    """DXF giữ nguyên; DWG chuyển qua accoreconsole (có đệm)."""
    p = Path(path)
    return dwg_to_dxf(p) if p.suffix.lower() == ".dwg" else p


__all__ = ["DwgError", "dwg_to_dxf", "dxf_to_dwg", "ensure_dxf", "find_accoreconsole", "run_script"]
