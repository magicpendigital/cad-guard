"""Dòng lệnh: cadguard audit | stats | rules | profile | fixtures | mcp | propose | apply | undo | diff | validate.

Mã thoát của `audit`: 0 = không có lỗi mức E; 1 = có lỗi mức E; 2 = không đọc được đầu vào/chuẩn.
`propose`/`validate`: 0 = đạt, 1 = kiểm không đạt, 2 = lỗi/từ chối. `apply`/`undo`: 0 = xong, 2 = từ chối/lỗi.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import json
import sys
from pathlib import Path

from . import __version__, fixtures, report, telemetry
from .rules import REGISTRY
from .runner import audit_model
from .standard import ProfileError, find_standards_dir, load_profile, load_standard
from .stats import compute_stats

DEFAULT_STANDARD = "furniture-v0"


def _utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass


def _collect(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            out += sorted(x for x in pp.rglob("*") if x.suffix.lower() == ".dxf")
        elif pp.is_file():
            out.append(pp)
        else:
            raise FileNotFoundError(f"Không thấy {p}")
    return out


def _read_model(f: Path, reader: str, threshold_mb: float):
    """Chọn đường đọc: ezdxf (nạp trọn) hoặc theo dòng; `auto` = theo dòng khi tệp >= ngưỡng MB."""
    from .dxf_stream import DXFStreamError
    from .reader_select import choose_reader, read_with

    choice = choose_reader(f, reader, threshold_mb)
    if choice.reason == "binary":
        print(f"{f.name}: DXF nhị phân, bộ đọc theo dòng không hỗ trợ; dùng ezdxf.", file=sys.stderr)
    elif choice.reason == "large":
        print(f"{f.name}: tệp lớn ({choice.size_mb:.0f} MB ≥ {threshold_mb:g} MB), dùng bộ đọc theo dòng.", file=sys.stderr)
    try:
        return read_with(f, choice.reader)
    except DXFStreamError as exc:
        raise ValueError(str(exc)) from None


def cmd_audit(args: argparse.Namespace) -> int:
    from .reader_select import check_threshold

    try:
        check_threshold(args.stream_threshold_mb)
    except ValueError as exc:
        print(f"--stream-threshold-mb: {exc}", file=sys.stderr)
        return 2
    profile =load_profile(args.profile) if args.profile else None
    name = args.standard or (profile.standard if profile else DEFAULT_STANDARD)
    std = load_standard(name, Path(args.standards_dir) if args.standards_dir else None, profile=profile)
    files = _collect(args.paths)
    if not files:
        print("Không có tệp .dxf nào để quét.", file=sys.stderr)
        return 2
    items = []
    for f in files:
        try:
            model = _read_model(f, args.reader, args.stream_threshold_mb)
        except Exception as exc:  # noqa: BLE001
            print(f"Không đọc được {f.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        if model.stats is not None and model.stats.entity_records_truncated:
            print(f"Lưu ý {f.name}: danh sách đối tượng đã bị cắt ở trần bộ nhớ; thống kê vẫn đủ nhưng "
                  "luật đọc từng đối tượng có thể bỏ sót.", file=sys.stderr)
        res = audit_model(model, std)
        telemetry.record_audit(model.file_hash)
        items.append((f.name, model.file_hash, res))
    if not items:
        return 2
    rep = report.build_report(std, items)
    if args.out:
        out = Path(args.out)
        if out.suffix.lower() == ".html":
            report.write_html(rep, out)
        else:
            report.write_json(rep, out)
        print(f"Đã ghi báo cáo: {out}")
    elif args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        for f in rep["files"]:
            c = f["counts"]
            print(f"{f['file']}: {c['E']} lỗi, {c['W']} cảnh báo, {c['I']} thông tin ({f['rules_run']} luật chạy)")
            for it in f["findings"]:
                print(f"  [{it['severity']}] {it['rule_id']}: {it['message']}")
    return 1 if rep["totals"]["E"] else 0


def cmd_stats(args: argparse.Namespace) -> int:
    std = load_standard(args.standard or DEFAULT_STANDARD, Path(args.standards_dir) if args.standards_dir else None)
    stats = compute_stats(std)
    print(json.dumps(stats) if args.json else "\n".join(f"{k}: {v}" for k, v in stats.items()))
    return 0


def cmd_rules(args: argparse.Namespace) -> int:
    std = load_standard(args.standard or DEFAULT_STANDARD, Path(args.standards_dir) if args.standards_dir else None)
    for r in std.rules:
        mark = "x" if (r.implemented and r.id in REGISTRY) else " "
        print(f"[{mark}] {r.id}  {r.severity}  {r.title}")
    done = sum(1 for r in std.rules if r.implemented and r.id in REGISTRY)
    print(f"\n{done}/{len(std.rules)} luật đã cài (chuẩn {std.name} {std.version})")
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    """Hồ sơ số liệu cho bản vẽ thật: chỉ số tổng hợp, khoá là mã băm, không tên tệp/layer/nội dung."""
    from .profile import profile_dxf, profile_dxf_stream

    out: dict[str, dict] = {}
    for f in _collect(args.paths):
        try:
            prof = profile_dxf_stream(f) if args.stream else profile_dxf(f)
        except Exception as exc:  # noqa: BLE001
            print(f"Không lập được hồ sơ một tệp: {type(exc).__name__}", file=sys.stderr)
            continue
        key = prof.get("file_hash") or hashlib.sha256(Path(f).name.encode()).hexdigest()[:12]
        out["d_" + key] = prof
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"Đã ghi hồ sơ {len(out)} tệp: {args.out}")
    else:
        print(text)
    return 0 if out else 2


def cmd_fixtures(args: argparse.Namespace) -> int:
    paths = fixtures.make_all(Path(args.out_dir))
    for p in paths:
        print(p)
    return 0


# ---------- công cụ ghi an toàn: propose / apply / undo / diff / validate ----------

YES_WORDS = {"c", "co", "có", "y", "yes"}


def _print_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _load_profile_arg(args):
    return load_profile(args.profile) if getattr(args, "profile", None) else None


def _std_dir(args):
    return Path(args.standards_dir) if getattr(args, "standards_dir", None) else None


def _print_preview(pv: dict) -> None:
    prof = pv.get("profile")
    print(f"Changeset {pv['changeset_id']} cho '{pv['source']['path']}' (chuẩn {pv['standard']} {pv['standard_version']}"
          + (f"; hồ sơ {prof['name']} {prof['version']}" if prof else "; ngưỡng mặc định") + ")")
    prot = pv.get("protection") or {}
    if prot.get("layers") or prot.get("patterns"):
        print(f"Layer bảo vệ: {', '.join(prot.get('layers', [])) or '—'}; mẫu: {', '.join(prot.get('patterns', [])) or '—'}")
    print("Thao tác:")
    for r in pv["ops"]:
        extra = f", bỏ qua {r['skipped_protected']} trên layer bảo vệ" if r.get("skipped_protected") else ""
        print(f"  {r['index']}. {r['op']}: {r['affected']} mục bị ảnh hưởng{extra}")
    print("Khác biệt: " + pv["diff_summary_vi"])
    rules = pv["rules"]
    print(f"Luật trước: {rules['before'] or '{}'}")
    print(f"Luật sau:   {rules['after'] or '{}'}")
    for c in pv["checks"]:
        print(f"  [{'x' if c['ok'] else ' '}] {c['id']}: {c['message']}")
    print(pv["summary_vi"])


def _changeset_workspace(args):
    from .agent.workspace import Workspace
    from .changeset import workspace_of

    if getattr(args, "workspace", None):
        return Workspace(Path(args.workspace))
    if Path(args.changeset).suffix.lower() == ".json":
        return workspace_of(args.changeset)
    return Workspace(Path.cwd())


def _interactive() -> bool:
    """stdin là bàn phím thật. Trên Windows, thiết bị NUL cũng báo isatty() = True nên phải hỏi thêm GetConsoleMode."""
    try:
        if sys.stdin is None or not sys.stdin.isatty():
            return False
        if os.name == "nt":
            import ctypes
            import msvcrt

            mode = ctypes.c_uint32()
            handle = msvcrt.get_osfhandle(sys.stdin.fileno())
            return bool(ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)))
        return True
    except Exception:  # noqa: BLE001 - không chắc thì coi như không tương tác (từ chối)
        return False


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().casefold() in YES_WORDS
    except EOFError:
        return False


def _changeset_errors():
    from .agent.workspace import PathDenied
    from .changeset import ChangesetError, OpError

    return (ChangesetError, OpError, PathDenied)


def cmd_propose(args: argparse.Namespace) -> int:
    from .agent.workspace import Workspace
    from .changeset import propose

    try:
        raw = json.loads(Path(args.ops).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"Không đọc được tệp thao tác JSON '{Path(args.ops).name}' ({type(exc).__name__}).", file=sys.stderr)
        return 2
    protected = list(args.protect or [])
    if isinstance(raw, dict) and isinstance(raw.get("protected_layers"), list):
        protected += [str(x) for x in raw["protected_layers"]]
    try:
        profile = _load_profile_arg(args)
        src = Path(args.file).resolve()
        ws = Workspace(Path(args.workspace) if args.workspace else src.parent)
        if not src.is_relative_to(ws.root):
            print("Tệp bản vẽ phải nằm trong thư mục làm việc (--workspace).", file=sys.stderr)
            return 2
        standard = args.standard or (profile.standard if profile else "design-hygiene-v0")
        cs, pv = propose(ws, src.relative_to(ws.root).as_posix(), raw, standard=standard, standards_dir=_std_dir(args),
                         profile=profile, protected_layers=protected, created_by="user")
    except _changeset_errors() as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        _print_json(pv)
    else:
        _print_preview(pv)
        print(f"\nĐã lưu changeset: {Path('.cadguard') / 'changesets' / (cs.id + '.json')} (trong thư mục làm việc). "
              f"Chưa ghi bản vẽ nào. Áp dụng: cadguard apply {cs.id} --workspace <thư mục làm việc>")
    return 0 if pv["ok"] else 1


def cmd_apply(args: argparse.Namespace) -> int:
    from .changeset import apply
    from .changeset.apply import load_for_apply

    try:
        profile = _load_profile_arg(args)
        ws = _changeset_workspace(args)
        cs, _ops, _std, _prot, _src = load_for_apply(ws, args.changeset, profile, _std_dir(args))
        if not args.yes:
            if cs.preview:
                _print_preview(cs.preview)
            if not _interactive():
                print("Từ chối: không có --yes và không chạy tương tác (không hỏi xác nhận được).", file=sys.stderr)
                return 2
            if not _confirm(f"Áp dụng changeset {cs.id} ra TỆP MỚI (tệp gốc giữ nguyên)? Gõ 'co' để đồng ý: "):
                print("Đã huỷ, không ghi gì.", file=sys.stderr)
                return 2
        res = apply(ws, args.changeset, confirm=True, out_dir=args.out_dir, profile=profile, standards_dir=_std_dir(args))
    except _changeset_errors() as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        _print_json(res)
    else:
        print(f"Đã ghi tệp mới: {res['output']['path']} (sha256 {res['output']['sha256'][:16]}…); tệp gốc không đổi.")
        print(res["validation"]["summary_vi"])
        print(f"Nhật ký: {res['log']}. Hoàn tác: cadguard undo {res['changeset_id']} (xoá tệp mới).")
    return 0


def cmd_undo(args: argparse.Namespace) -> int:
    from .changeset import undo

    try:
        ws = _changeset_workspace(args)
        if not args.yes:
            if not _interactive():
                print("Từ chối: không có --yes và không chạy tương tác.", file=sys.stderr)
                return 2
            if not _confirm(f"Xoá tệp mới do changeset {args.changeset} tạo ra? Gõ 'co' để đồng ý: "):
                print("Đã huỷ.", file=sys.stderr)
                return 2
        res = undo(ws, args.changeset, confirm=True)
    except _changeset_errors() as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Đã hoàn tác {res['changeset_id']}: xoá {res['removed']}.")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    from .changeset import diff_files

    for p in (args.a, args.b):
        if not Path(p).is_file():
            print(f"Không thấy tệp '{Path(p).name}'.", file=sys.stderr)
            return 2
    try:
        d = diff_files(args.a, args.b, args.max_items)
    except Exception as exc:  # noqa: BLE001
        print(f"Không so được hai tệp ({type(exc).__name__}).", file=sys.stderr)
        return 2
    if args.json:
        _print_json(d)
        return 0
    print(f"{d['a']['name']} → {d['b']['name']}: {d['summary_vi']}")
    for key, label in (("added", "+"), ("removed", "-")):
        for e in d["entities"][key]:
            print(f"  {label} {e['handle']} {e['type']} layer '{e['layer']}' ({e['space']})")
    for e in d["entities"]["changed"]:
        attrs = ", ".join(f"{k}: {v[0]!r} → {v[1]!r}" for k, v in e["attrs"].items())
        print(f"  ~ {e['handle']} {e['type']} ({e['space']}): {attrs}")
    if d["truncated"]:
        print(f"(danh sách bị cắt ở {d['max_items']} mục mỗi loại; số tổng ở trên là đủ)")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from .changeset import validate_output
    from .changeset.apply import load_changeset, load_std, resolve_changeset_path
    from .changeset.engine import Protection
    from .changeset.ops import parse_ops

    try:
        profile = _load_profile_arg(args)
        args.workspace = getattr(args, "workspace", None)
        ws = _changeset_workspace(args)
        cs = load_changeset(resolve_changeset_path(ws, args.changeset))
        std = load_std(cs.standard, _std_dir(args), profile)
        res = validate_output(args.original, args.output, parse_ops(cs.ops), Protection(**cs.protection.model_dump()), std,
                              cs.source.sha256)
    except _changeset_errors() as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Không đọc được tệp ({type(exc).__name__}).", file=sys.stderr)
        return 2
    if args.json:
        _print_json(res)
    else:
        for c in res["checks"]:
            print(f"  [{'x' if c['ok'] else ' '}] {c['id']}: {c['message']}")
        print(res["summary_vi"])
    return 0 if res["ok"] else 1


def cmd_mcp(args: argparse.Namespace) -> int:
    from .mcp_server import run_from_args  # SDK `mcp` chỉ được import bên trong, khi chạy lệnh này

    return run_from_args(args)


def main(argv: list[str] | None = None) -> int:
    _utf8()
    p = argparse.ArgumentParser(prog="cadguard", description="cad-guard: kiểm tra bản vẽ theo luật tất định")
    p.add_argument("--version", action="version", version=f"cadguard {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--standard", default=None, help=f"tên chuẩn trong standards/ (mặc định {DEFAULT_STANDARD})")
        sp.add_argument("--standards-dir", default=None)

    a = sub.add_parser("audit", help="quét tệp/thư mục DXF")
    a.add_argument("paths", nargs="+")
    a.add_argument("--out", help="ghi báo cáo: .html hoặc .json")
    a.add_argument("--json", action="store_true", help="in báo cáo JSON ra stdout")
    a.add_argument("--reader", choices=["ezdxf", "stream", "auto"], default="auto",
                   help="bộ đọc DXF: ezdxf (nạp trọn), stream (theo dòng, ít bộ nhớ), auto (stream khi tệp lớn; mặc định)")
    a.add_argument("--stream-threshold-mb", type=float, default=50.0,
                   help="ngưỡng MB để auto chuyển sang đọc theo dòng (mặc định 50)")
    a.add_argument("--profile", default=None,
                   help="hồ sơ công ty (YAML cg.company-profile/1) ghi đè ngưỡng/mẫu layer; không có --standard thì dùng chuẩn ghi trong hồ sơ")
    common(a)
    a.set_defaults(fn=cmd_audit)

    s = sub.add_parser("stats", help="số tổng hợp cho MCA")
    s.add_argument("--json", action="store_true")
    common(s)
    s.set_defaults(fn=cmd_stats)

    r = sub.add_parser("rules", help="liệt kê luật và tình trạng cài đặt")
    common(r)
    r.set_defaults(fn=cmd_rules)

    pr = sub.add_parser("profile", help="hồ sơ số liệu của DXF (chỉ số tổng hợp, ẩn danh)")
    pr.add_argument("paths", nargs="+")
    pr.add_argument("--out", help="ghi JSON ra tệp")
    pr.add_argument("--stream", action="store_true", help="đọc theo dòng cho tệp rất lớn (ít bộ nhớ)")
    pr.set_defaults(fn=cmd_profile)

    f = sub.add_parser("fixtures", help="sinh lại DXF tổng hợp")
    f.add_argument("out_dir", nargs="?", default="fixtures/synthetic")
    f.set_defaults(fn=cmd_fixtures)

    from .changeset.ops import OP_HELP

    ops_help = "Thao tác (từ vựng cố định): " + "; ".join(f"{k}: {v}" for k, v in OP_HELP.items())
    pp = sub.add_parser("propose", help="đề xuất changeset (chạy khô, xem trước; không ghi bản vẽ)", description=ops_help)
    pp.add_argument("file", help="tệp DXF gốc")
    pp.add_argument("--ops", required=True, help="tệp JSON: mảng thao tác, hoặc {\"ops\": [...], \"protected_layers\": [...]}")
    pp.add_argument("--protect", action="append", metavar="LAYER", help="layer bảo vệ (lặp lại được)")
    pp.add_argument("--workspace", help="thư mục làm việc (mặc định: thư mục chứa tệp)")
    pp.add_argument("--profile", help="hồ sơ công ty (ngưỡng luật + layer_patterns.protected)")
    pp.add_argument("--json", action="store_true", help="in xem trước dạng JSON")
    common(pp)
    pp.set_defaults(fn=cmd_propose)

    ap = sub.add_parser("apply", help="áp changeset ra TỆP MỚI (cần xác nhận; tệp gốc không đổi)")
    ap.add_argument("changeset", help="mã changeset (cs-…) hoặc đường dẫn .cadguard/changesets/<mã>.json")
    ap.add_argument("--yes", action="store_true", help="đã xem trước và đồng ý (bắt buộc khi không chạy tương tác)")
    ap.add_argument("--workspace", help="thư mục làm việc (mặc định: suy từ đường dẫn changeset, hoặc thư mục hiện tại)")
    ap.add_argument("--out-dir", help="thư mục đầu ra tương đối trong thư mục làm việc (mặc định: cạnh tệp gốc)")
    ap.add_argument("--profile", help="hồ sơ công ty (phải trùng hồ sơ lúc đề xuất)")
    ap.add_argument("--json", action="store_true")
    common(ap)
    ap.set_defaults(fn=cmd_apply)

    up = sub.add_parser("undo", help="hoàn tác changeset đã áp: xoá tệp mới (mã băm phải khớp nhật ký)")
    up.add_argument("changeset")
    up.add_argument("--yes", action="store_true")
    up.add_argument("--workspace")
    up.set_defaults(fn=cmd_undo)

    dp = sub.add_parser("diff", help="so hai DXF theo handle: đối tượng thêm/xoá/đổi, định nghĩa thêm/xoá")
    dp.add_argument("a")
    dp.add_argument("b")
    dp.add_argument("--max-items", type=int, default=200, help="số mục tối đa mỗi danh sách (mặc định 200)")
    dp.add_argument("--json", action="store_true")
    dp.set_defaults(fn=cmd_diff)

    vp = sub.add_parser("validate", help="kiểm tệp ra so với tệp gốc theo changeset (validate_output)")
    vp.add_argument("original")
    vp.add_argument("output")
    vp.add_argument("--changeset", required=True, help="mã changeset hoặc đường dẫn tệp JSON")
    vp.add_argument("--workspace")
    vp.add_argument("--profile")
    vp.add_argument("--json", action="store_true")
    common(vp)
    vp.set_defaults(fn=cmd_validate)

    from .mcp_server import add_arguments as mcp_arguments

    m = sub.add_parser(
        "mcp",
        add_help=False,
        help="máy chủ MCP stdio chỉ đọc cho trợ lý AI (cần extras [agent])",
        description="Máy chủ MCP stdio, mặc định CHỈ ĐỌC: 6 công cụ list_drawings, audit, explain_rule, get_model_summary, "
        "query_model, diff; --allow-propose thêm propose_changeset (chỉ ghi changeset JSON). Không có công cụ áp dụng. "
        "stdout chỉ dành cho JSON-RPC; thông báo ra stderr. Cần SDK: pip install cadguard[agent].",
    )
    mcp_arguments(m)
    m.set_defaults(fn=cmd_mcp)

    args = p.parse_args(argv)
    try:
        return int(args.fn(args))
    except (FileNotFoundError, ProfileError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
