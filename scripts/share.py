#!/usr/bin/env python3
"""Quản lý cổng Tailscale riêng; không mở hay công bố bản vẽ, không ghi khóa/token.

python scripts/share.py start --workspace <project>
python scripts/share.py status --workspace <project>
python scripts/share.py stop --workspace <project>
"""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import http.client
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cli():
    exe = shutil.which("tailscale")
    if not exe:
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Tailscale" / "tailscale.exe"
        if candidate.is_file():
            exe = str(candidate)
    if not exe:
        raise ValueError("Chưa có Tailscale. Cài từ https://tailscale.com/download/windows rồi đăng nhập.")
    return exe


def ts(*args):
    p = subprocess.run([cli(), *args], capture_output=True, text=True, encoding="utf-8", timeout=40,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if p.returncode:
        raise ValueError("Tailscale chưa sẵn sàng; đăng nhập và kiểm tra lệnh tailscale status tại máy chủ.")
    return p.stdout


def process_stamp(pid, terminate=False, expected=None):
    """Chỉ dừng đúng tiến trình đã khởi chạy, kiểm thời điểm tạo để tránh PID tái sử dụng."""
    if os.name != "nt":
        raise ValueError("Script chạy nền này dành cho Windows; hệ khác chạy cadguard review trực tiếp.")
    from ctypes import wintypes
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.restype = wintypes.HANDLE
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    api.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    handle = api.OpenProcess(0x1000 | (1 if terminate else 0), False, pid)
    if not handle:
        return None
    try:
        created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not api.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
            return None
        stamp = (created.dwHighDateTime << 32) | created.dwLowDateTime
        if terminate:
            if expected != stamp:
                raise ValueError("PID đã được dùng lại: không dừng tiến trình này.")
            if not api.TerminateProcess(handle, 0):
                raise ValueError("Không dừng được tiến trình cổng rà soát.")
        return stamp
    finally:
        api.CloseHandle(handle)


def proxy(config, port):
    web = config.get("Web", {})
    for host, info in web.items():
        if host.rsplit(":",1)[-1] == str(port):
            handler = info.get("Handlers", {}).get("/", {})
            return handler.get("Proxy")
    return None


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "status", "stop", "verify"])
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--confirm-mobile", action="store_true", help="đã tự kiểm qua điện thoại dùng mạng di động và Tailscale")
    args = parser.parse_args()
    workspace = args.workspace.resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError("Cần thư mục dự án.")
    state_path = workspace / ".cadguard" / "reviews" / "server.json"
    try:
        saved = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        saved = {}
    if args.action == "verify":
        if not args.confirm_mobile:
            raise ValueError("Chỉ xác nhận sau khi người dùng đã kiểm trên điện thoại: thêm --confirm-mobile.")
        config = json.loads(ts("serve", "status", "--json"))
        if not saved.get("pid") or process_stamp(saved["pid"]) != saved.get("created") or proxy(config,saved.get("https")) != "http://127.0.0.1:8781":
            raise ValueError("Cổng không còn chạy đúng cấu hình; cần kiểm tra lại.")
        saved["verified_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        state_path.write_text(json.dumps(saved),encoding="utf-8")
        print("Đã ghi nhận người dùng xác nhận truy cập được trên điện thoại.")
        return 0
    if args.action == "status":
        live = bool(saved.get("pid") and process_stamp(saved["pid"]) == saved.get("created"))
        status = json.loads(ts("status", "--json"))
        config = json.loads(ts("serve", "status", "--json"))
        matches = bool(saved.get("https") and proxy(config,saved["https"]) == "http://127.0.0.1:8781")
        print(json.dumps({"server_running": live, "tailscale": status.get("BackendState"), "origin": saved.get("origin"),
                          "serve_proxy_matches": matches, "second_device_verified": bool(saved.get("verified_at")) and live and matches,
                          "verified_at": saved.get("verified_at")}, ensure_ascii=False))
        return 0
    if args.action == "stop":
        managed = bool(saved.get("pid") and process_stamp(saved["pid"]) == saved.get("created"))
        if managed:
            process_stamp(saved["pid"], terminate=True, expected=saved["created"])
        config = json.loads(ts("serve", "status", "--json"))
        if managed and saved.get("https") and proxy(config,saved["https"]) == "http://127.0.0.1:8781":
            ts("serve", "--https="+str(saved["https"]), "off")
        print("Đã dừng cổng do script này quản lý; dữ liệu hồ sơ giữ nguyên.")
        return 0
    if saved.get("pid") and process_stamp(saved["pid"]) == saved.get("created"):
        config = json.loads(ts("serve", "status", "--json"))
        if proxy(config,saved["https"]) != "http://127.0.0.1:8781":
            raise ValueError("Backend đang chạy nhưng Serve đã đổi. Dùng stop rồi start để chọn cổng còn trống.")
        print("Cổng đang chạy: " + saved["origin"])
        return 0
    status = json.loads(ts("status", "--json"))
    if status.get("BackendState") != "Running":
        raise ValueError("Tailscale chưa đăng nhập. Mở Tailscale và đăng nhập tài khoản công ty rồi chạy lại.")
    dns = status.get("Self", {}).get("DNSName", "").rstrip(".")
    if not dns.endswith(".ts.net"):
        raise ValueError("Chưa có tên DNS Tailscale; kiểm tra cấu hình DNS/HTTPS trong tài khoản.")
    config = json.loads(ts("serve", "status", "--json"))
    https = None
    for candidate in (443,8443):
        taken = str(candidate) in config.get("TCP", {})
        if not taken or proxy(config,candidate) == "http://127.0.0.1:8781":
            https=candidate
            break
    if https is None:
        raise ValueError("443 và 8443 đang phục vụ ứng dụng khác; giữ nguyên cấu hình đó.")
    origin = "https://" + dns + ("" if https==443 else ":8443")
    venv = ROOT / "packages/core/.venv/Scripts/python.exe"
    if not venv.exists():
        raise ValueError("Chưa có venv dự án; chạy bootstrap trước.")
    env = dict(os.environ, PYTHONPATH=str(ROOT / "packages/core"), PYTHONUTF8="1")
    proc = subprocess.Popen([str(venv), "-m", "cadguard", "review", "--workspace", str(workspace), "--public-origin", origin],
                            cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    server_pid = None
    server_created = None
    try:
        import time
        for _ in range(30):
            if proc.poll() is not None:
                raise ValueError("Không chạy được cổng 8781; kiểm tra cổng đang bận hoặc chạy cadguard review trực tiếp.")
            conn = http.client.HTTPConnection("127.0.0.1",8781,timeout=.2)
            try:
                conn.request("GET","/internal/status")
                response=conn.getresponse()
                health=json.loads(response.read())
                if response.status==200 and health.get("service")=="cadguard-review" and (health.get("pid")==proc.pid or health.get("parent_pid")==proc.pid) and health.get("workspace_hash")==hashlib.sha256(str(workspace).encode()).hexdigest():
                    server_pid=health["pid"]
                    server_created=process_stamp(server_pid)
                    break
            except (OSError,ValueError,http.client.HTTPException):
                pass
            finally:
                conn.close()
            time.sleep(.2)
        else:
            raise ValueError("Cổng rà soát chưa sẵn sàng.")
        ts("serve", "--bg", "--https="+str(https), "http://127.0.0.1:8781")
        state_path.parent.mkdir(parents=True,exist_ok=True)
        state_path.write_text(json.dumps({"pid":server_pid,"created":server_created,"origin":origin,"https":https}),encoding="utf-8")
    except BaseException:
        if server_pid and process_stamp(server_pid)==server_created:
            process_stamp(server_pid,terminate=True,expected=server_created)
        if proc.poll() is None:
            proc.terminate()
        raise
    print("Cổng nội bộ đã cấu hình: " + origin)
    print("Cấp quyền thành viên trong Hồ sơ duyệt, kiểm tra bằng điện thoại bật Tailscale qua mạng di động trước khi gửi khách.")
    print("Chưa xác minh thiết bị thứ hai. Máy chủ cần đang hoạt động; script không công bố bản vẽ hay gửi lời mời.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(str(exc),file=sys.stderr)
        raise SystemExit(2)
