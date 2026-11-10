"""Cài đặt một lần cho người dùng không cần biết lệnh: phông Be Vietnam Pro, gắn CAD Guard vào AutoCAD, lối tắt.

Mỗi bước có `status` (đã xong chưa) và `install` / `uninstall`; màn **Cài đặt** của app và lệnh `cadguard setup` gọi
cùng các hàm này. Chỉ đụng thư mục của NGƯỜI DÙNG hiện tại (không cần quyền quản trị):

- phông: chép TTF vào `%LOCALAPPDATA%\\Microsoft\\Windows\\Fonts` và đăng ký trong `HKCU\\...\\Fonts`
  (nguồn: thư mục người dùng chỉ ra, hoặc tải từ kho Google Fonts chính thức trên GitHub; giấy phép SIL OFL 1.1);
- AutoCAD: chép `cadguard.lsp` + `cadguard-run.cmd` vào `%LOCALAPPDATA%\\cad-guard\\autocad`, thêm MỘT khối có đánh
  dấu vào `acaddoc.lsp` trong thư mục Support của người dùng (AutoCAD tự nạp mỗi khi mở bản vẽ; gỡ = xoá khối đó).
  Không sửa cài đặt bảo mật của AutoCAD: lần đầu AutoCAD có thể hỏi "Load / Always load", bấm Always load;
- lối tắt "CAD Guard" trên màn hình mở ứng dụng.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

FONT_FAMILY = "Be Vietnam Pro"
FONT_FILES = ["BeVietnamPro-Regular.ttf", "BeVietnamPro-Bold.ttf", "BeVietnamPro-Italic.ttf",
              "BeVietnamPro-BoldItalic.ttf", "BeVietnamPro-Medium.ttf", "BeVietnamPro-SemiBold.ttf"]
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/bevietnampro/{name}"
MARK_BEGIN = ";; >>> cad-guard (tự thêm bởi Cài đặt CAD Guard; gỡ trong app hoặc `cadguard setup --remove autocad`)"
MARK_END = ";; <<< cad-guard"


class SetupError(RuntimeError):
    """Bước cài đặt không làm được (tiếng Việt)."""


def _local() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")


# ---------- phông ----------

def user_font_dir() -> Path:
    return _local() / "Microsoft" / "Windows" / "Fonts"


def _system_font_dir() -> Path:
    return Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"


def font_status() -> dict:
    found = [f for f in FONT_FILES if (user_font_dir() / f).is_file() or (_system_font_dir() / f).is_file()]
    return {"id": "font", "title": f"Phông {FONT_FAMILY}", "done": "BeVietnamPro-Regular.ttf" in found,
            "detail": f"Đã có {len(found)}/{len(FONT_FILES)} kiểu chữ." if found else "Chưa cài.",
            "why": "Phông Unicode của công ty: chữ tiếng Việt sau khi chuyển mã hiện đúng trong AutoCAD và ảnh tờ."}


def _register_font(path: Path) -> None:
    if os.name != "nt":
        return
    import ctypes
    import winreg

    style = path.stem.split("-", 1)[1] if "-" in path.stem else "Regular"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows NT\CurrentVersion\Fonts") as k:
        winreg.SetValueEx(k, f"{FONT_FAMILY} {style} (TrueType)", 0, winreg.REG_SZ, str(path))
    try:
        ctypes.windll.gdi32.AddFontResourceW(str(path))
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001D, 0, 0, 0x0002, 1000, None)  # WM_FONTCHANGE
    except Exception:  # noqa: BLE001
        pass


def install_font(source: Path | None = None, *, fetch=None) -> dict:
    """Cài phông cho người dùng hiện tại. `source`: thư mục có sẵn các tệp TTF; không có thì tải từ Google Fonts."""
    dst_dir = user_font_dir()
    dst_dir.mkdir(parents=True, exist_ok=True)
    fetch = fetch or _download
    done = []
    for name in FONT_FILES:
        dst = dst_dir / name
        if not dst.is_file():
            if source is not None:
                src = Path(source) / name
                if not src.is_file():
                    continue
                data = src.read_bytes()
            else:
                data = fetch(FONT_URL.format(name=name))
            if data[:4] not in (b"\x00\x01\x00\x00", b"true", b"OTTO"):
                raise SetupError(f"Tệp phông {name} tải về không hợp lệ.")
            dst.write_bytes(data)
        _register_font(dst)
        done.append(name)
    if "BeVietnamPro-Regular.ttf" not in done:
        raise SetupError("Không cài được BeVietnamPro-Regular.ttf.")
    return {**font_status(), "installed": done}


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "cad-guard-setup"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 - địa chỉ cố định của kho Google Fonts
            return r.read()
    except OSError as exc:
        raise SetupError(f"Không tải được phông ({type(exc).__name__}). Kiểm tra mạng, hoặc chỉ thư mục có sẵn tệp TTF.") from None


def uninstall_font() -> dict:
    if os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows NT\CurrentVersion\Fonts", 0,
                                winreg.KEY_ALL_ACCESS) as k:
                for name in FONT_FILES:
                    style = Path(name).stem.split("-", 1)[1]
                    try:
                        winreg.DeleteValue(k, f"{FONT_FAMILY} {style} (TrueType)")
                    except OSError:
                        pass
        except OSError:
            pass
    for name in FONT_FILES:
        try:
            (user_font_dir() / name).unlink()
        except OSError:
            pass
    return font_status()


# ---------- AutoCAD ----------

def autocad_profiles() -> list[dict]:
    """Bản AutoCAD đã cài cho người dùng: {"name", "support"} (thư mục Support của người dùng)."""
    out = []
    if os.name != "nt":
        return out
    import winreg

    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Autodesk\AutoCAD")
    except OSError:
        return out
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
                            roam, _t = winreg.QueryValueEx(pk, "RoamableRootFolder")
                    except OSError:
                        continue
                    sup = Path(roam) / "Support"
                    if sup.is_dir():
                        out.append({"name": Path(roam).parent.parent.name or rel, "release": rel, "support": sup})
    return out


def addon_dir() -> Path:
    return _local() / "cad-guard" / "autocad"


def _block(lsp: Path) -> str:
    p = str(lsp).replace("\\", "/")
    home = str(lsp.parent).replace("\\", "/") + "/"
    return f'{MARK_BEGIN}\n(setq cg:*home* "{home}")\n(if (findfile "{p}") (load "{p}"))\n{MARK_END}\n'


def _strip_block(text: str) -> str:
    if MARK_BEGIN not in text:
        return text
    a = text.index(MARK_BEGIN)
    b = text.find(MARK_END, a)
    b = len(text) if b < 0 else b + len(MARK_END)
    rest = text[:a] + text[b:]
    return rest.replace("\n\n\n", "\n\n").lstrip("\n") if rest.strip() else ""


def autocad_status() -> dict:
    profs = autocad_profiles()
    linked = [p for p in profs if MARK_BEGIN in _read(p["support"] / "acaddoc.lsp")]
    files_ok = (addon_dir() / "cadguard.lsp").is_file() and (addon_dir() / "cadguard-run.cmd").is_file()
    if not profs:
        detail = "Không thấy AutoCAD bản đầy đủ cho người dùng này."
    elif linked and files_ok:
        detail = "Đã gắn vào " + ", ".join(p["name"] for p in linked) + ". Trong AutoCAD gõ CADGUARD."
    else:
        detail = "Tìm thấy " + ", ".join(p["name"] for p in profs) + "; chưa gắn."
    return {"id": "autocad", "title": "Gắn CAD Guard vào AutoCAD", "done": bool(linked) and files_ok,
            "available": bool(profs), "detail": detail,
            "why": "AutoCAD tự nạp CAD Guard; chỉ cần gõ một lệnh CADGUARD trên bản vẽ đang mở."}


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def runner_lines() -> list[str]:
    pkg = Path(__file__).resolve().parents[1]
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    return ["@echo off", "chcp 65001 >nul", f'set "PYTHONPATH={pkg};%PYTHONPATH%"', "set PYTHONUTF8=1",
            f'if /I "%1"=="open" (start "" "{pyw if pyw.is_file() else exe}" -m cadguard %* & exit /b)',
            f'"{exe}" -m cadguard %*']


def write_runner(dst_dir: Path) -> Path:
    crlf = chr(13) + chr(10)
    runner = Path(dst_dir) / "cadguard-run.cmd"
    runner.write_bytes((crlf.join(runner_lines()) + crlf).encode("utf-8"))
    return runner


def install_autocad() -> dict:
    profs = autocad_profiles()
    if not profs:
        raise SetupError("Không thấy AutoCAD bản đầy đủ cho người dùng này (AutoCAD LT không chạy được LISP ngoài).")
    d = addon_dir()
    d.mkdir(parents=True, exist_ok=True)
    lsp = d / "cadguard.lsp"
    shutil.copyfile(Path(__file__).with_name("autocad") / "cadguard.lsp", lsp)
    write_runner(d)
    for p in profs:
        f = p["support"] / "acaddoc.lsp"
        old = _strip_block(_read(f))
        f.write_text((old.rstrip("\n") + "\n\n" if old.strip() else "") + _block(lsp), encoding="utf-8")
    return autocad_status()


def uninstall_autocad() -> dict:
    for p in autocad_profiles():
        f = p["support"] / "acaddoc.lsp"
        txt = _read(f)
        if MARK_BEGIN in txt:
            rest = _strip_block(txt)
            if rest.strip():
                f.write_text(rest, encoding="utf-8")
            else:
                f.unlink()
    return autocad_status()


# ---------- lối tắt ----------

def desktop() -> Path:
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
                v, _t = winreg.QueryValueEx(k, "Desktop")
                return Path(os.path.expandvars(v))
        except OSError:
            pass
    return Path.home() / "Desktop"


SHORTCUT = "CAD Guard.lnk"


def shortcut_status() -> dict:
    ok = (desktop() / SHORTCUT).is_file()
    return {"id": "shortcut", "title": "Lối tắt CAD Guard trên màn hình", "done": ok,
            "detail": "Đã có trên màn hình." if ok else "Chưa có.",
            "why": "Bấm đúp để mở CAD Guard, không cần gõ lệnh."}


def install_shortcut() -> dict:
    if os.name != "nt":
        raise SetupError("Lối tắt chỉ tạo trên Windows.")
    d = addon_dir()
    d.mkdir(parents=True, exist_ok=True)
    runner = write_runner(d)
    lnk = desktop() / SHORTCUT
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:CG_LNK);"
          "$s.TargetPath=$env:CG_TARGET;$s.Arguments='open';$s.WindowStyle=7;"
          "$s.Description='CAD Guard - kiểm và chuẩn hoá bản vẽ';$s.Save()")
    env = dict(os.environ, CG_LNK=str(lnk), CG_TARGET=str(runner))
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], env=env, capture_output=True,
                       timeout=60)
    if r.returncode != 0 or not lnk.is_file():
        raise SetupError("Không tạo được lối tắt trên màn hình.")
    return shortcut_status()


def uninstall_shortcut() -> dict:
    try:
        (desktop() / SHORTCUT).unlink()
    except OSError:
        pass
    return shortcut_status()


# ---------- tổng ----------

STEPS = {"font": (font_status, install_font, uninstall_font),
         "autocad": (autocad_status, install_autocad, uninstall_autocad),
         "shortcut": (shortcut_status, install_shortcut, uninstall_shortcut)}


def status() -> list[dict]:
    return [fn() for fn, _i, _u in STEPS.values()]


def run(step: str, remove: bool = False) -> dict:
    if step not in STEPS:
        raise SetupError("Không có bước cài đặt này.")
    _s, inst, uninst = STEPS[step]
    return uninst() if remove else inst()


__all__ = ["FONT_FILES", "SetupError", "run", "status"]
