"""Build plugin AutoCAD `CadGuard.Acad.dll` (packages/acad-plugin) và ghi `cadguard-acad.json` cạnh DLL.

    python scripts/build_acad_plugin.py [--acad-dir "<thư mục cài AutoCAD>"] [--out <thư mục>] [--python <python.exe>]

- Tự tìm thư mục AutoCAD qua registry (HKLM\\SOFTWARE\\Autodesk\\AutoCAD\\…\\AcadLocation), bản mới nhất.
- Cần .NET SDK (dotnet) cùng đời với AutoCAD: AutoCAD 2027 dùng .NET 10.
- `cadguard-acad.json` chỉ chứa đường dẫn Python và PYTHONPATH để plugin chạy `python -m cadguard app`; KHÔNG có mã
  phiên hay khoá nào (mã phiên plugin đọc từ đầu ra tiến trình, không ghi ra tệp).
Nạp vào AutoCAD: NETLOAD -> chọn <out>\\CadGuard.Acad.dll (thư mục nên nằm trong Trusted Locations). Xem docs/autocad.md mục 7.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROJ = REPO / "packages" / "acad-plugin" / "CadGuard.Acad.csproj"
CORE = REPO / "packages" / "core"


def find_acad() -> Path | None:
    if sys.platform != "win32":
        return None
    import winreg

    found: list[tuple[str, Path]] = []

    def walk(key, path: str, depth: int) -> None:
        try:
            loc, _ = winreg.QueryValueEx(key, "AcadLocation")
            p = Path(loc)
            if (p / "acmgd.dll").is_file():
                found.append((path, p))
        except OSError:
            pass
        if depth >= 3:
            return
        i = 0
        while True:
            try:
                name = winreg.EnumKey(key, i)
            except OSError:
                break
            i += 1
            try:
                with winreg.OpenKey(key, name) as sub:
                    walk(sub, path + "\\" + name, depth + 1)
            except OSError:
                continue

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Autodesk\AutoCAD") as root:
            walk(root, "", 0)
    except OSError:
        return None
    return sorted(found)[-1][1] if found else None


def default_python() -> str:
    venv = CORE / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    return str(venv if venv.is_file() else Path(sys.executable))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--acad-dir", default=None)
    ap.add_argument("--out", default=str(REPO / "packages" / "acad-plugin" / "bin" / "plugin"))
    ap.add_argument("--python", default=None, help="python.exe chạy cad-guard (mặc định: packages/core/.venv nếu có)")
    a = ap.parse_args(argv)
    dotnet = shutil.which("dotnet")
    if not dotnet:
        print("Không thấy dotnet. Cài .NET SDK 10 (AutoCAD 2027) rồi chạy lại.", file=sys.stderr)
        return 2
    acad = Path(a.acad_dir) if a.acad_dir else find_acad()
    if acad is None or not (acad / "acmgd.dll").is_file():
        print("Không tìm thấy thư mục AutoCAD (acmgd.dll). Truyền --acad-dir.", file=sys.stderr)
        return 2
    out = Path(a.out)
    cmd = [dotnet, "build", str(PROJ), "-c", "Release", "-o", str(out), f"-p:AcadDir={acad}", "-nologo", "-v", "q"]
    print("Build:", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        return r.returncode
    cfg = {"python": a.python or default_python(), "pythonpath": str(CORE)}
    (out / "cadguard-acad.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Xong: {out / 'CadGuard.Acad.dll'}")
    print("Trong AutoCAD: NETLOAD -> chọn tệp trên; rồi CGBANG (bảng cad-guard), CGGHIM (ghim lỗi).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
