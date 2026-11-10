"""`cadguard open`: một cú bấm (lối tắt màn hình) hoặc một lệnh AutoCAD (CADGUARD) là vào thẳng ứng dụng.

- Ứng dụng đang chạy thì dùng lại (đọc `<thư mục cấu hình>/app-instance.json`: địa chỉ, mã phiên, pid); chưa chạy thì
  khởi động ngầm (`pythonw -m cadguard app --no-browser`) và chờ nó sẵn sàng.
- Có `--workspace` thì chuyển ứng dụng sang thư mục dự án đó; có `--drawing` thì mở và quét bản vẽ trùng tên.
- Mở trình duyệt mặc định. Tệp phiên chỉ nằm trong thư mục cấu hình của người dùng, ứng dụng chỉ nghe 127.0.0.1.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

INSTANCE = "app-instance.json"


def instance_path() -> Path:
    from .settings import config_dir

    return config_dir() / INSTANCE


def write_instance(url: str, token: str, port: int) -> None:
    p = instance_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"url": url, "token": token, "port": port, "pid": os.getpid()}), encoding="utf-8")


def clear_instance() -> None:
    try:
        data = json.loads(instance_path().read_text(encoding="utf-8"))
        if data.get("pid") == os.getpid():
            instance_path().unlink()
    except (OSError, ValueError):
        pass


def _call(inst: dict, path: str, body: dict | None = None, timeout: float = 3.0) -> dict:
    from .server import TOKEN_HEADER

    url = f"http://127.0.0.1:{int(inst['port'])}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET",
                                 headers={TOKEN_HEADER: inst["token"], "Content-Type": "application/json",
                                          "Origin": f"http://127.0.0.1:{int(inst['port'])}",
                                          "Host": f"127.0.0.1:{int(inst['port'])}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - chỉ 127.0.0.1
        return json.loads(r.read().decode("utf-8"))


def running() -> dict | None:
    try:
        inst = json.loads(instance_path().read_text(encoding="utf-8"))
        _call(inst, "/api/session")
        return inst
    except Exception:  # noqa: BLE001 - không có, đã tắt, hay hỏng: coi như chưa chạy
        return None


def _spawn(workspace: Path | None) -> None:
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    cmd = [str(pyw if pyw.is_file() else exe), "-m", "cadguard", "app", "--no-browser"]
    if workspace is not None:
        cmd += ["--workspace", str(workspace)]
    flags = 0
    if os.name == "nt":
        flags = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW
    env = dict(os.environ)
    pkg = str(Path(__file__).resolve().parents[2])
    env["PYTHONPATH"] = pkg + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("PYTHONUTF8", "1")
    subprocess.Popen(cmd, creationflags=flags, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, close_fds=True)


def open_app(workspace: Path | None = None, drawing: str | None = None, *, browser=None, wait_s: float = 30.0) -> str:
    """Bảo đảm ứng dụng chạy, chuyển dự án, trả địa chỉ đã mở trong trình duyệt."""
    inst = running()
    started = False
    if inst is None:
        _spawn(workspace)
        started = True
        t0 = time.monotonic()
        while time.monotonic() - t0 < wait_s:
            time.sleep(0.4)
            inst = running()
            if inst is not None:
                break
        if inst is None:
            raise RuntimeError("CAD Guard không khởi động được (quá thời gian chờ).")
    if workspace is not None and not started:
        try:
            _call(inst, "/api/project/open", {"path": str(Path(workspace).resolve()), "confirm": True}, timeout=30)
        except Exception:  # noqa: BLE001 - vẫn mở giao diện; người dùng chọn dự án trên màn hình
            pass
    q = {"t": inst["token"]}
    if drawing:
        q.update({"dwg": drawing, "open": "1"})
    url = f"http://127.0.0.1:{int(inst['port'])}/?" + urllib.parse.urlencode(q)
    if browser is None:
        import webbrowser

        webbrowser.open(url)
    else:
        browser(url)
    return url


__all__ = ["clear_instance", "open_app", "running", "write_instance"]
