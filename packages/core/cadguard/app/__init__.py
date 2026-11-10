"""Ứng dụng web cục bộ `cadguard app`: giao diện dùng trực tiếp cad-guard trong trình duyệt (chỉ 127.0.0.1).

Chỉ dùng thư viện chuẩn (`http.server`, `json`); giao diện là HTML/CSS/JS thuần trong `static/`, chạy offline.
Xem docs/app.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .api import ApiError, AppConfig
from .server import CadGuardApp, create_server, start_in_thread, url_of


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--workspace", default=None, metavar="THƯ_MỤC",
                   help="mở thẳng dự án này (thư mục chứa DXF). Không có: mở màn chọn dự án (dự án gần đây, Mở thư mục…)")
    p.add_argument("--profile", default=None, metavar="TỆP", help="hồ sơ công ty (YAML cg.company-profile/1)")
    p.add_argument("--port", type=int, default=0, help="cổng (mặc định 0 = ngẫu nhiên); chỉ nghe 127.0.0.1")
    p.add_argument("--no-browser", action="store_true", help="không tự mở trình duyệt; chỉ in địa chỉ")
    p.add_argument("--anonymize", action="store_true", default=None,
                   help="ép BẬT ẩn danh Bậc 1 cho trợ lý (dự án NDA). Mặc định theo công tắc của dự án; chưa đặt = nội bộ")
    p.add_argument("--no-anonymize", action="store_true", help="ép chế độ nội bộ (trợ lý thấy nội dung thật)")
    p.add_argument("--experimental", action="store_true", help="bật engine thử nghiệm (codex-cli)")
    p.add_argument("--allow-openrouter", action="store_true", help="bật OpenRouter (bên trung gian thứ ba, mặc định tắt)")
    p.add_argument("--account", choices=["business", "api-key"], default=None,
                   help="agy-cli: loại tài khoản (tài khoản Google cá nhân bị từ chối)")
    p.add_argument("--no-detect", action="store_true", help="không chạy CLI (claude/codex/agy) để kiểm đã cài/đăng nhập")
    p.add_argument("--no-autocad-com", action="store_true",
                   help="nút 'Tới trong AutoCAD' chỉ ghi yêu cầu (người dùng gõ CGDEN), không điều khiển AutoCAD qua COM")
    p.add_argument("--standards-dir", default=None, help=argparse.SUPPRESS)


def run_from_args(args: argparse.Namespace) -> int:
    ws = Path(args.workspace) if args.workspace else None
    if ws is not None and not ws.is_dir():
        print("Thư mục làm việc không tồn tại hoặc không phải thư mục.", file=sys.stderr)
        return 2
    if not (0 <= args.port <= 65535):
        print("Cổng phải trong khoảng 0–65535.", file=sys.stderr)
        return 2
    cfg = AppConfig(workspace=ws, profile_path=Path(args.profile).resolve() if args.profile else None,
                    anonymize=True if args.anonymize else (False if args.no_anonymize else None),
                    experimental=args.experimental,
                    allow_openrouter=args.allow_openrouter, account=args.account,
                    autocad_com=not args.no_autocad_com,
                    standards_dir=Path(args.standards_dir) if args.standards_dir else None)
    try:
        kwargs = {"cli_detect": lambda name: {"installed": None}} if args.no_detect else {}
        app = CadGuardApp(cfg, **kwargs)
        srv = create_server(app, args.port)
    except ApiError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError:
        print(f"Không mở được cổng {args.port} trên 127.0.0.1 (đang bận?). Thử --port 0.", file=sys.stderr)
        return 2
    url = url_of(app)
    from .launcher import clear_instance, write_instance

    try:
        write_instance(url, app.token, app.port)  # để lối tắt / lệnh CADGUARD dùng lại phiên đang chạy
    except OSError:
        pass
    print("cad-guard app đang chạy (chỉ máy này, 127.0.0.1). Mở địa chỉ sau trong trình duyệt:")
    print(f"  {url}")
    print("Mã phiên trong địa chỉ là mật khẩu của phiên này: đừng gửi cho người khác. Nhấn Ctrl+C để dừng.")
    sys.stdout.flush()
    if not args.no_browser:
        import webbrowser

        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001 — không mở được trình duyệt: người dùng tự mở
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng cad-guard app.")
    finally:
        srv.server_close()
        clear_instance()
    return 0


__all__ = ["AppConfig", "CadGuardApp", "add_arguments", "create_server", "run_from_args", "start_in_thread", "url_of"]
