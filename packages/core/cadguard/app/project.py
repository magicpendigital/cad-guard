"""Chọn dự án (thư mục chứa DXF) như coding agent: hộp thoại hệ điều hành, đường dẫn nhập tay, dự án gần đây.

- Hộp thoại dùng `tkinter.filedialog` chạy trong **tiến trình con** (`python -I -c …`) để không chặn luồng máy chủ;
  máy không có tkinter thì giao diện dùng ô nhập đường dẫn.
- API không bao giờ liệt kê thư mục ngoài dự án: chỉ hộp thoại của hệ điều hành mới duyệt cây thư mục.
- Chỉ nhận thư mục tồn tại; gốc ổ đĩa, thư mục người dùng (hoặc thư mục cha của nó) cần người dùng xác nhận.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

MAX_PATH_CHARS = 1024
DIALOG_TIMEOUT_S = 900

_FOLDER_SCRIPT = r"""
import json, sys
try:
    import tkinter
    from tkinter import filedialog
except Exception:
    print(json.dumps({"unavailable": True})); sys.exit(0)
root = tkinter.Tk(); root.withdraw()
try:
    root.attributes("-topmost", True)
except Exception:
    pass
kind = sys.argv[1]
if kind == "folder":
    p = filedialog.askdirectory(title="Chọn thư mục dự án (chứa bản vẽ DXF)", mustexist=True)
else:
    p = filedialog.askopenfilename(title="Chọn tệp hồ sơ công ty (.yaml)",
                                   filetypes=[("Hồ sơ công ty", "*.yaml *.yml"), ("Mọi tệp", "*.*")])
root.destroy()
print(json.dumps({"path": p or None}, ensure_ascii=True))
"""


class DialogBusy(RuntimeError):
    pass


def dialog_available() -> bool:
    return importlib.util.find_spec("tkinter") is not None


_dialog_lock = threading.Lock()


def run_dialog(kind: str) -> dict:
    """Mở hộp thoại hệ điều hành trong tiến trình con. Trả {"path": str|None} hoặc {"unavailable": True}."""
    if kind not in ("folder", "profile"):
        raise ValueError(kind)
    if not _dialog_lock.acquire(blocking=False):
        raise DialogBusy("Hộp thoại chọn thư mục đang mở; hãy chọn hoặc đóng hộp thoại đó trước.")
    try:
        try:
            out = subprocess.run([sys.executable, "-I", "-c", _FOLDER_SCRIPT, kind], capture_output=True,
                                 timeout=DIALOG_TIMEOUT_S, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired):
            return {"unavailable": True}
        try:
            data = json.loads((out.stdout or b"").decode("utf-8", "replace").strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {"unavailable": True}
        if not isinstance(data, dict):
            return {"unavailable": True}
        if data.get("unavailable"):
            return {"unavailable": True}
        p = data.get("path")
        return {"path": p if isinstance(p, str) and p else None}
    finally:
        _dialog_lock.release()


def check_project_dir(raw: object) -> tuple[Path, str | None]:
    """(thư mục đã resolve, cảnh báo cần xác nhận hoặc None). Lỗi -> ValueError tiếng Việt (không lặp lại đường dẫn)."""
    if not isinstance(raw, str) or not raw.strip() or len(raw) > MAX_PATH_CHARS or "\0" in raw:
        raise ValueError("Đường dẫn thư mục không hợp lệ.")
    p = Path(raw.strip().strip('"')).expanduser()
    if not p.is_absolute():
        raise ValueError("Hãy nhập đường dẫn đầy đủ (tuyệt đối), ví dụ D:\\Du-an\\Tu-bep.")
    try:
        p = p.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ValueError("Thư mục không tồn tại.") from None
    if not p.is_dir():
        raise ValueError("Đường dẫn này không phải thư mục.")
    return p, broad_dir_warning(p)


def broad_dir_warning(p: Path) -> str | None:
    if p.parent == p:
        return ("Đây là gốc ổ đĩa. cad-guard sẽ quét cả ổ để tìm DXF (có trần số tệp) và ghi thư mục .cadguard ở gốc ổ. "
                "Nên chọn đúng thư mục dự án.")
    try:
        home = Path.home().resolve()
    except (OSError, RuntimeError):
        home = None
    if home is not None and (p == home or home.is_relative_to(p)):
        return ("Đây là thư mục người dùng (hoặc thư mục chứa nó). cad-guard sẽ quét rất nhiều thư mục và ghi thư mục "
                ".cadguard ở đây. Nên chọn đúng thư mục dự án.")
    return None


def check_profile_file(raw: object) -> Path:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > MAX_PATH_CHARS or "\0" in raw:
        raise ValueError("Đường dẫn tệp hồ sơ không hợp lệ.")
    p = Path(raw.strip().strip('"')).expanduser()
    if not p.is_absolute():
        raise ValueError("Hãy chọn tệp hồ sơ bằng hộp thoại hoặc nhập đường dẫn đầy đủ.")
    try:
        p = p.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ValueError("Không thấy tệp hồ sơ.") from None
    if not p.is_file() or p.suffix.lower() not in (".yaml", ".yml"):
        raise ValueError("Hồ sơ công ty phải là tệp .yaml.")
    if p.stat().st_size > 1_000_000:
        raise ValueError("Tệp hồ sơ quá lớn.")
    return p


DialogRunner = Callable[[str], dict]

__all__ = ["DialogBusy", "DialogRunner", "broad_dir_warning", "check_profile_file", "check_project_dir",
           "dialog_available", "run_dialog"]
