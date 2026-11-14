#!/usr/bin/env python3
"""Chạy test/lệnh của cad-guard bằng một venv DÙNG CHUNG, không cần .venv trong từng worktree.

Dùng cho agent (MCA) và CI: chỉ cần Python 3.10–3.14 có sẵn (chỉ dùng thư viện chuẩn ở đây).

  python scripts/test.py                    # pytest -q toàn bộ packages/core
  python scripts/test.py tests/test_x.py -k abc
  python scripts/test.py --extras agent     # cài thêm extras [agent] (SDK MCP) rồi chạy pytest
  python scripts/test.py --run -m cadguard rules      # chạy `python -m cadguard rules` trong venv

Mã nguồn lấy từ worktree chứa script này (PYTHONPATH=packages/core), không phải bản đã cài.
venv ở %LOCALAPPDATA%\\cad-guard\\venv (Windows) hoặc ~/.cache/cad-guard/venv; đổi bằng CADGUARD_VENV.
Không ghi khoá/token; chỉ cài từ PyPI các phụ thuộc khai báo trong packages/core/pyproject.toml.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "packages" / "core"

# Dấu hiệu pip hỏng vì ứng dụng đóng gói MSIX (vd. ứng dụng Claude) chuyển hướng %LOCALAPPDATA%.
MSIX_MARKERS = ("escapes package",)


def _utf8_console() -> None:
    """In tiếng Việt đúng trên console Windows/ống dẫn: ép UTF-8, ký tự không mã hoá được thì thay thế."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 — luồng không hỗ trợ reconfigure: giữ nguyên
            pass


def _say(msg: str) -> None:
    print(f"[cad-guard] {msg}", file=sys.stderr, flush=True)


def venv_dir() -> Path:
    if os.environ.get("CADGUARD_VENV"):
        return Path(os.environ["CADGUARD_VENV"])
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "cad-guard" / "venv"
    return Path.home() / ".cache" / "cad-guard" / "venv"


def venv_python(v: Path) -> Path:
    return v / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def requirements(extras: list[str]) -> list[str]:
    text = (CORE / "pyproject.toml").read_text(encoding="utf-8")
    try:
        import tomllib

        proj = tomllib.loads(text)["project"]
        reqs = list(proj.get("dependencies", []))
        opt = proj.get("optional-dependencies", {})
        for name in ["dev", *extras]:
            reqs += opt.get(name, [])
        return reqs
    except ImportError:  # Python 3.10: đọc thô các mảng chuỗi
        reqs = []
        for block in re.findall(r"(?:dependencies|dev|%s)\s*=\s*\[(.*?)\]" % "|".join(["agent", *extras]), text, flags=re.S):
            reqs += re.findall(r'"([^"]+)"', block)
        return reqs


def pip_failure_hint(output: str, venv: Path) -> str | None:
    """Gợi ý tiếng Việt khi lỗi pip giống lỗi chuyển hướng thư mục của ứng dụng MSIX; None nếu không nhận ra."""
    if not any(m in output for m in MSIX_MARKERS):
        return None
    return (
        "Gợi ý: lỗi \"Resource name escapes package\" thường do ứng dụng đóng gói MSIX (vd. ứng dụng Claude) "
        f"chuyển hướng %LOCALAPPDATA%, nên venv dùng chung ở {venv} bị hỏng khi cài.\n"
        "Đặt CADGUARD_VENV sang một thư mục khác ngoài %LOCALAPPDATA% rồi chạy lại, ví dụ:\n"
        "  PowerShell: $env:CADGUARD_VENV = \"$env:USERPROFILE\\cad-guard-venv\"\n"
        "  cmd:        set CADGUARD_VENV=%USERPROFILE%\\cad-guard-venv\n"
        "(Có thể xoá thư mục venv cũ bị hỏng sau khi đã chạy được bằng thư mục mới.)"
    )


def _run_reporting(cmd: list[str], venv: Path, what: str) -> None:
    """Chạy lệnh cài đặt; lỗi thì in đầu ra, thêm gợi ý (nếu có) và thoát với mã của lệnh."""
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    if proc.stdout:
        sys.stderr.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        _say(f"{what} thất bại (mã {proc.returncode}).")
        hint = pip_failure_hint(proc.stdout + proc.stderr, venv)
        if hint:
            _say(hint)
        raise SystemExit(proc.returncode or 1)


def ensure_venv(extras: list[str]) -> Path:
    v = venv_dir()
    py = venv_python(v)
    if not py.exists():
        _say(f"tạo venv dùng chung: {v}")
        _run_reporting([sys.executable, "-m", "venv", str(v)], v, "tạo venv")
    stamp = v / f".deps-{'-'.join(sorted(extras)) or 'base'}"
    want = "\n".join(sorted(requirements(extras)))
    if not stamp.exists() or stamp.read_text(encoding="utf-8") != want:
        _say("cài phụ thuộc...")
        _run_reporting(
            [str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check", *sorted(requirements(extras))], v, "cài phụ thuộc"
        )
        stamp.write_text(want, encoding="utf-8")
    return py


def main(argv: list[str]) -> int:
    _utf8_console()
    extras: list[str] = []
    run_mode = False
    args: list[str] = []
    it = iter(argv)
    for a in it:
        if a == "--extras":
            extras += next(it, "").split(",")
        elif a == "--run":
            run_mode = True
        else:
            args.append(a)
    py = ensure_venv([e for e in extras if e])
    env = dict(os.environ, PYTHONPATH=str(CORE) + os.pathsep + os.environ.get("PYTHONPATH", ""), PYTHONUTF8="1")
    cmd = [str(py), *args] if run_mode else [str(py), "-m", "pytest", *args]
    return subprocess.run(cmd, cwd=CORE, env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
