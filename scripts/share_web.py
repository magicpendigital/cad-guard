#!/usr/bin/env python3
"""Cổng web mật khẩu: start cục bộ -> người dùng đặt mật khẩu -> publish bằng Funnel."""
import argparse
import http.client
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from share import ROOT, cli, process_stamp, proxy, ts


def health(port):
    c=http.client.HTTPConnection("127.0.0.1",port,timeout=2)
    try:
        c.request("GET","/internal/web-status")
        r=c.getresponse()
        if r.status!=200:raise ValueError("Gateway mật khẩu chưa sẵn sàng.")
        value=json.loads(r.read())
        if value.get("service")!="cadguard-password-gateway":raise ValueError("Sai dịch vụ tại cổng gateway.")
        return value
    finally:c.close()


def main():
    for stream in (sys.stdout,sys.stderr):stream.reconfigure(encoding="utf-8",errors="replace")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["start","status","publish","stop"])
    parser.add_argument("--port",type=int,default=8783)
    parser.add_argument("--setup-port",type=int,default=8784)
    parser.add_argument("--https",type=int,default=10000)
    parser.add_argument("--upstream",type=int,default=8780)
    args=parser.parse_args()
    file=ROOT/".cadguard"/"web-proxy.json"
    try:saved=json.loads(file.read_text(encoding="utf-8"))
    except (FileNotFoundError,ValueError):saved={}
    alive=bool(saved.get("pid") and process_stamp(saved["pid"])==saved.get("created"))
    config=json.loads(ts("serve","status","--json"))
    if args.action=="status":
        h=health(saved["port"]) if alive else {}
        public=bool(saved.get("origin") and config.get("AllowFunnel",{}).get(saved["origin"].split("//",1)[1]+(":443" if saved["https"]==443 else "")))
        print(json.dumps({"running":alive,"password_ready":h.get("password_ready",False),"origin":saved.get("origin"),"funnel":public,"target_matches":bool(saved.get("https") and proxy(config,saved["https"])==saved["target"])},ensure_ascii=False));return 0
    if args.action=="stop":
        if saved.get("https") and proxy(config,saved["https"])==saved["target"]:
            subprocess.run([cli(),"funnel","--https="+str(saved["https"]),"off"],check=True)
        if alive:process_stamp(saved["pid"],terminate=True,expected=saved["created"])
        print("Đã dừng cổng web mật khẩu; app gốc và cổng hồ sơ giữ nguyên.");return 0
    if args.action=="publish":
        if not alive:raise ValueError("Chạy start và tự đặt mật khẩu trước.")
        h=health(saved["port"])
        if not h.get("password_ready"):raise ValueError("Chưa đặt mật khẩu; chưa được phép mở Internet.")
        current=proxy(config,saved["https"])
        if current not in (None,saved["target"],"http://127.0.0.1:8782"):
            raise ValueError("Cổng HTTPS đang phục vụ ứng dụng khác; giữ nguyên cấu hình đó.")
        code=subprocess.run([cli(),"funnel","--bg","--https="+str(saved["https"]),saved["target"]]).returncode
        if code:return code
        config=json.loads(ts("serve","status","--json"))
        if proxy(config,saved["https"])!=saved["target"]:raise ValueError("Funnel chưa trỏ tới gateway mật khẩu.")
        print("Địa chỉ web đăng nhập bằng mật khẩu: "+saved["origin"]);return 0
    if alive:
        print("Gateway đang chạy. Thiết lập cục bộ: http://127.0.0.1:"+str(saved["setup_port"]));return 0
    state=json.loads(ts("status","--json"))
    if state.get("BackendState")!="Running":raise ValueError("Tailscale máy chủ chưa đăng nhập.")
    dns=state.get("Self",{}).get("DNSName","").rstrip(".")
    if not dns.endswith(".ts.net"):raise ValueError("Chưa có tên DNS Tailscale.")
    origin="https://"+dns+(":"+str(args.https) if args.https!=443 else "")
    exe=ROOT/"packages/core/.venv/Scripts/python.exe"
    env=dict(os.environ,PYTHONPATH=str(ROOT/"packages/core"),PYTHONUTF8="1")
    proc=subprocess.Popen([str(exe),"-m","cadguard.app.web_access","--origin",origin,"--port",str(args.port),"--setup-port",str(args.setup_port),"--upstream",str(args.upstream)],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    pid,created=None,None
    try:
        for _ in range(40):
            if proc.poll() is not None:raise ValueError("Không khởi động được gateway; kiểm tra kho khóa/cổng.")
            try:
                h=health(args.port)
                if h.get("pid")==proc.pid or h.get("parent_pid")==proc.pid:
                    pid=h["pid"];created=process_stamp(pid);break
            except (OSError,ValueError,http.client.HTTPException):pass
            time.sleep(.2)
        if pid is None:raise ValueError("Gateway chưa sẵn sàng.")
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(json.dumps({"pid":pid,"created":created,"port":args.port,"setup_port":args.setup_port,"https":args.https,"origin":origin,"target":"http://127.0.0.1:"+str(args.port)}),encoding="utf-8")
    except BaseException:
        if pid and process_stamp(pid)==created:process_stamp(pid,terminate=True,expected=created)
        if proc.poll() is None:proc.terminate()
        raise
    print("Chưa mở Internet. Người dùng tự đặt mật khẩu tại http://127.0.0.1:"+str(args.setup_port))
    return 0


if __name__=="__main__":
    try:raise SystemExit(main())
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        print(str(exc),file=sys.stderr);raise SystemExit(2)
