"""Lệnh người dùng: `cadguard ask | chat | engines | keys`."""
from __future__ import annotations

import argparse
import getpass
import json
import sys

from . import API_ENGINES, CLI_ENGINES, ENGINE_NAMES, CancelToken, EngineError, create_engine, engine_infos
from .events import Usage


def _engine_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--engine", required=True, choices=ENGINE_NAMES, help="engine trợ lý (xem `cadguard engines`)")
    p.add_argument("--workspace", required=True, metavar="THƯ_MỤC", help="thư mục làm việc chứa DXF của phiên")
    p.add_argument("--standard", default=None, help="chuẩn (vd. design-hygiene-v0, furniture-v0)")
    p.add_argument("--profile", default=None, metavar="TỆP", help="hồ sơ công ty (như `cadguard mcp --profile`)")
    p.add_argument("--model", default=None, help="mô hình (mặc định theo cấu hình của engine)")
    p.add_argument("--allow-propose", action="store_true", help="cho trợ lý ĐỀ XUẤT changeset (không bao giờ áp dụng)")
    p.add_argument("--experimental", action="store_true", help="bật engine thử nghiệm (codex-cli)")
    p.add_argument("--account", choices=["business", "api-key"], default=None,
                   help="agy-cli: loại tài khoản (BẮT BUỘC; tài khoản Google cá nhân bị từ chối)")
    p.add_argument("--allow-openrouter", action="store_true", help="bật OpenRouter (bên trung gian thứ ba, mặc định tắt)")
    p.add_argument("--timeout", type=float, default=None, help="thời hạn mỗi lượt, giây")
    p.add_argument("--max-cost-usd", type=float, default=None, help="engine API: trần chi phí ước tính mỗi phiên (USD)")
    p.add_argument("--max-tool-rounds", type=int, default=None, help="engine API: số vòng gọi công cụ tối đa")


def _make(args) -> object:
    api = {}
    if args.engine in API_ENGINES:
        if args.max_cost_usd is not None:
            api["max_cost_usd"] = args.max_cost_usd
        if args.max_tool_rounds is not None:
            api["max_tool_rounds"] = args.max_tool_rounds
    return create_engine(args.engine, model=args.model, experimental=args.experimental, account=args.account,
                         timeout=args.timeout, allow_openrouter=args.allow_openrouter, **api)


def usage_table(u: Usage) -> str:
    cost = "không rõ" if u.cost_usd is None else f"{u.cost_usd:.4f}" + (" (ước tính)" if u.cost_estimated else "")
    rows = [("Token vào", str(u.input_tokens)), ("Token ra", str(u.output_tokens)),
            ("Token đọc cache", str(u.cache_read_tokens)), ("Token ghi cache", str(u.cache_write_tokens)),
            ("Tổng token", str(u.total_tokens)), ("Chi phí USD", cost)]
    w = max(len(a) for a, _ in rows)
    return "\n".join(f"{a.ljust(w)} : {b}" for a, b in rows)


def _turn(engine, messages, args, cancel, *, stream: bool) -> tuple[str, Usage, list[str], list[dict]]:
    total, answer, errors, events = Usage(cost_usd=None), "", [], []
    for e in engine.run(messages, workspace=args.workspace, standard=args.standard, profile=args.profile,
                        allow_propose=args.allow_propose, cancel=cancel):
        events.append(e.to_dict())
        if e.type == "usage":
            total.add(e.data["usage"])
        elif e.type == "error":
            errors.append(e.data["message"])
            if stream:
                print(f"[lỗi] {e.data['message']}", file=sys.stderr)
        elif e.type == "tool_call" and stream:
            print(f"  → công cụ {e.data.get('name')}", file=sys.stderr)
        elif e.type == "done":
            answer = e.data.get("text", "")
    return answer, total, errors, events


def cmd_ask(args) -> int:
    try:
        engine = _make(args)
    except EngineError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    cancel = CancelToken()
    try:
        answer, total, errors, events = _turn(engine, [{"role": "user", "content": args.question}], args, cancel,
                                              stream=not args.json)
    except KeyboardInterrupt:
        cancel.cancel()
        print("Đã huỷ.", file=sys.stderr)
        return 130
    if args.json:
        print(json.dumps({"engine": args.engine, "answer": answer, "usage": total.to_dict(), "errors": errors,
                          "events": events}, ensure_ascii=False, indent=2))
    else:
        if answer:
            print(answer)
        print("\n" + usage_table(total), file=sys.stderr)
    return 1 if errors and not answer else 0


def cmd_chat(args) -> int:
    try:
        engine = _make(args)
    except EngineError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    history: list[dict] = []
    session = Usage(cost_usd=None)
    print(f"Trò chuyện với trợ lý cad-guard ({args.engine}). Gõ /chi-phi để xem chi phí, /thoat để thoát.")
    while True:
        try:
            line = input("Bạn> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("/thoat", "/thoát", "/quit", "/exit"):
            break
        if line in ("/chi-phi", "/chi-phí"):
            print(usage_table(session))
            continue
        history.append({"role": "user", "content": line})
        cancel = CancelToken()
        try:
            answer, total, errors, _ = _turn(engine, history, args, cancel, stream=True)
        except KeyboardInterrupt:
            cancel.cancel()
            history.pop()
            print("Đã huỷ lượt này.", file=sys.stderr)
            continue
        session.add(total)
        if answer:
            print(f"Trợ lý> {answer}")
            history.append({"role": "assistant", "content": answer})
        else:
            history.pop()  # lượt hỏng: không giữ câu hỏi treo trong lịch sử
    print(usage_table(session))
    return 0


def cmd_engines(args) -> int:
    from .api_engines import PROVIDERS, provider_model
    from .keys import key_status

    rows = []
    for info in engine_infos():
        row = {"engine": info.name, "che_do": "B (CLI, tài khoản của bạn)" if info.mode == "cli" else "C (API, khoá của bạn)",
               "ten": info.title, "dieu_khoan": info.terms, "thu_nghiem": info.experimental, "mac_dinh_tat": info.default_off}
        if info.mode == "cli":
            if args.no_detect:
                row["trang_thai"] = "chưa kiểm (--no-detect)"
            else:
                d = create_engine(info.name).detect()
                if not d["installed"]:
                    row["trang_thai"] = "chưa cài"
                else:
                    login = {True: "đã đăng nhập", False: "CHƯA đăng nhập", None: "không rõ đăng nhập"}[d["logged_in"]]
                    row["trang_thai"] = f"đã cài ({d['version'] or '?'}), {login}"
        else:
            p = PROVIDERS[info.name]
            if p.key_env is None:
                row["trang_thai"] = "không cần khoá (cục bộ)"
            else:
                st = key_status(info.name)
                src = "biến môi trường" if st["env"] else ("kho khoá hệ điều hành" if st["keyring"] else None)
                row["trang_thai"] = f"có khoá ({src})" if src else "chưa có khoá"
            row["mo_hinh"] = provider_model(p, None) or "(chưa đặt; dùng --model)"
        rows.append(row)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    for r in rows:
        flags = (" [THỬ NGHIỆM]" if r["thu_nghiem"] else "") + (" [MẶC ĐỊNH TẮT]" if r["mac_dinh_tat"] else "")
        print(f"{r['engine']}{flags} — {r['ten']}")
        print(f"  chế độ: {r['che_do']}; trạng thái: {r['trang_thai']}" + (f"; mô hình: {r['mo_hinh']}" if "mo_hinh" in r else ""))
        print(f"  điều khoản: {r['dieu_khoan']}")
    print("\nCLI chỉ dùng bản bạn đã cài và tự đăng nhập; cad-guard không đọc, không lưu token. Khoá API chỉ đọc từ biến "
          "môi trường hoặc kho khoá hệ điều hành (`cadguard keys`).")
    return 0


def cmd_keys(args) -> int:
    from .keys import KeyStoreError, delete_key, key_status, set_key

    try:
        if args.action == "set":
            value = getpass.getpass(f"Dán khoá API cho {args.provider} (không hiện trên màn hình): ")
            set_key(args.provider, value)
            print(f"Đã lưu khoá {args.provider} vào kho khoá hệ điều hành.")
        elif args.action == "delete":
            print(f"Đã xoá khoá {args.provider}." if delete_key(args.provider) else f"Không có khoá {args.provider} để xoá.")
        else:
            st = key_status(args.provider)
            kr = {True: "có", False: "không", None: "không dùng được (thiếu gói keyring)"}[st["keyring"]]
            print(f"{args.provider}: biến {st['env_var']}: {'có' if st['env'] else 'không'}; kho khoá hệ điều hành: {kr}.")
    except KeyStoreError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


def add_parsers(sub) -> None:
    a = sub.add_parser("ask", help="hỏi trợ lý AI một lượt về bản vẽ trong thư mục làm việc")
    a.add_argument("question", help="câu hỏi")
    _engine_args(a)
    a.add_argument("--json", action="store_true", help="in JSON (câu trả lời, usage, sự kiện)")
    a.set_defaults(fn=cmd_ask)

    c = sub.add_parser("chat", help="trò chuyện nhiều lượt với trợ lý AI (/thoat, /chi-phi)")
    _engine_args(c)
    c.set_defaults(fn=cmd_chat)

    e = sub.add_parser("engines", help="liệt kê engine trợ lý AI: đã cài/đăng nhập/có khoá chưa, điều khoản")
    e.add_argument("--json", action="store_true")
    e.add_argument("--no-detect", action="store_true", help="không chạy CLI để kiểm phiên bản/đăng nhập")
    e.set_defaults(fn=cmd_engines)

    k = sub.add_parser("keys", help="khoá API trong kho khoá hệ điều hành (không bao giờ ghi tệp)")
    k.add_argument("action", choices=["set", "delete", "status"])
    k.add_argument("provider", choices=["anthropic", "openai", "openrouter", "gemini"])
    k.set_defaults(fn=cmd_keys)


__all__ = ["add_parsers", "cmd_ask", "cmd_chat", "cmd_engines", "cmd_keys", "usage_table", "CLI_ENGINES"]
