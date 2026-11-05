#!/usr/bin/env python3
"""Chia sẻ đúng phiên app đang chạy cho tài khoản chủ Tailscale; không lưu token app."""
import argparse
import http.client
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from share import ROOT, process_stamp, proxy, ts


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["start", "status", "stop"])
    p.add_argument("--upstream", type=int, default=8780)
    p.add_argument("--port", type=int, default=8782)
    p.add_argument("--https", type=int, default=10000)
    args = p.parse_args()
    state_path = ROOT / ".cadguard" / "owner-proxy.json"
    try:
        saved = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        saved = {}
    target = f"http://127.0.0.1:{args.port}"
    config = json.loads(ts("serve", "status", "--json"))
    alive = bool(saved.get("pid") and process_stamp(saved["pid"]) == saved.get("created"))
    if args.action == "status":
        matches = bool(saved.get("https") and proxy(config,saved["https"]) == saved.get("target"))
        print(json.dumps({"running":alive,"serve_matches":matches,"origin":saved.get("origin")},ensure_ascii=False))
        return 0
    if args.action == "stop":
        if alive:
            process_stamp(saved["pid"],terminate=True,expected=saved["created"])
            if proxy(config,saved["https"]) == saved["target"]:
                ts("serve","--https="+str(saved["https"]),"off")
        print("Đã dừng cổng app riêng; ứng dụng gốc và cổng khách giữ nguyên.")
        return 0
    if alive:
        if proxy(config,saved["https"]) != saved["target"]:
            raise ValueError("Proxy Serve đã đổi; dùng stop rồi start để cấu hình lại.")
        print("Cổng app riêng đang chạy: "+saved["origin"])
        return 0
    if str(args.https) in config.get("TCP",{}) and proxy(config,args.https) != target:
        raise ValueError("Cổng HTTPS đã dùng cho ứng dụng khác; chọn --https khác.")
    state = json.loads(ts("status","--json"))
    if state.get("BackendState") != "Running":
        raise ValueError("Tailscale chưa đăng nhập.")
    user = state.get("User",{}).get(str(state["Self"]["UserID"]),{})
    login = user.get("LoginName")
    dns = state["Self"].get("DNSName","").rstrip(".")
    if not login or not dns.endswith(".ts.net"):
        raise ValueError("Không xác định được tài khoản chủ Tailscale.")
    origin = "https://"+dns+((":"+str(args.https)) if args.https != 443 else "")
    conn = http.client.HTTPConnection("127.0.0.1",args.upstream,timeout=5)
    try:
        conn.request("HEAD","/")
        if conn.getresponse().status != 200:
            raise ValueError("Ứng dụng gốc chưa sẵn sàng.")
    finally:
        conn.close()
    exe = ROOT / "packages/core/.venv/Scripts/python.exe"
    env = dict(os.environ,PYTHONPATH=str(ROOT/"packages/core"),PYTHONUTF8="1")
    proc = subprocess.Popen([str(exe),"-m","cadguard.app.remote","--origin",origin,"--login",login,
                             "--upstream",str(args.upstream),"--port",str(args.port)],cwd=ROOT,env=env,
                            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    pid, created = None, None
    try:
        for _ in range(40):
            if proc.poll() is not None:
                raise ValueError("Không chạy được gateway localhost; kiểm tra cổng đang bận.")
            health_conn = http.client.HTTPConnection("127.0.0.1",args.port,timeout=.3)
            try:
                health_conn.request("GET","/internal/owner-status")
                response = health_conn.getresponse(); health = json.loads(response.read())
                if response.status == 200 and health.get("service") == "cadguard-owner-gateway" and (health.get("pid") == proc.pid or health.get("parent_pid") == proc.pid) and health.get("upstream") == args.upstream and health.get("origin") == origin:
                    pid=health["pid"];created=process_stamp(pid)
                    break
            except (OSError,ValueError,http.client.HTTPException):
                pass
            finally:
                health_conn.close()
            time.sleep(.2)
        if pid is None:
            raise ValueError("Gateway chưa sẵn sàng.")
        ts("serve","--bg","--https="+str(args.https),target)
        state_path.parent.mkdir(parents=True,exist_ok=True)
        state_path.write_text(json.dumps({"pid":pid,"created":created,"https":args.https,"target":target,"origin":origin}),encoding="utf-8")
    except BaseException:
        if pid and process_stamp(pid)==created:
            process_stamp(pid,terminate=True,expected=created)
        if proc.poll() is None:
            proc.terminate()
        raise
    print("Cổng đầy đủ dành cho chủ: "+origin)
    print("Mở bằng mã ?t= của app gốc; script không đọc hay lưu mã đó.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print(str(exc),file=sys.stderr)
        raise SystemExit(2)
