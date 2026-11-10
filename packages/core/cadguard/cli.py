"""Dòng lệnh: cadguard audit | stats | rules | profile | fixtures | mcp | propose | apply | undo | diff | validate
| ask | chat | engines | keys | app | scene | studio | review | watch | doctor | mcp-config | autocad.

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

from . import __version__, report, telemetry
from .rules import REGISTRY
from .runner import audit_model
from .standard import ProfileError, find_standards_dir, load_profile, load_standard
from .stats import compute_stats

DEFAULT_STANDARD = "furniture-v0"


def _utf8() -> None:
    """In tiếng Việt không sập trên console Windows (cp1252…): ép UTF-8, ký tự không mã hoá được thì thay thế."""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
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
    """Chọn đường đọc: ezdxf (nạp trọn) hoặc theo dòng; `auto` = theo dòng khi tệp >= ngưỡng MB. DWG: chuyển qua
    accoreconsole của AutoCAD đã cài (dwg.py)."""
    if f.suffix.lower() == ".dwg":
        from .dwg import dwg_to_dxf

        f = dwg_to_dxf(f)
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
    from .rule_config import effective_standard, find_workspace

    files = _collect(args.paths)
    ws = find_workspace(Path(args.paths[0])) if args.paths else None
    std = effective_standard(name, Path(args.standards_dir) if args.standards_dir else None, profile=profile,
                             workspace=ws)
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


def _parse_value(raw: str):
    import json

    try:
        return json.loads(raw)
    except ValueError:
        return raw


def cmd_rule_set(args: argparse.Namespace) -> int:
    """Sửa một luật không cần tài khoản: bật/tắt, mức độ, tham số (phạm vi dự án hoặc máy)."""
    from .rule_config import RuleSettingsError, reset_rule, update_rule

    std_dir = Path(args.standards_dir) if args.standards_dir else None
    ws = Path(args.workspace)
    try:
        if args.reset:
            res = reset_rule(args.standard or DEFAULT_STANDARD, args.rule, scope=args.scope, workspace=ws,
                             standards_dir=std_dir)
        else:
            changes: dict = {}
            if args.enable or args.disable:
                changes["enabled"] = bool(args.enable)
            if args.severity:
                changes["severity"] = args.severity
            params = {}
            for kv in args.param or []:
                if "=" not in kv:
                    print(f"--param cần dạng tên=giá_trị (gặp '{kv}').", file=sys.stderr)
                    return 2
                k, v = kv.split("=", 1)
                params[k.strip()] = _parse_value(v)
            if params:
                changes["params"] = params
            res = update_rule(args.standard or DEFAULT_STANDARD, args.rule, changes, scope=args.scope, workspace=ws,
                              standards_dir=std_dir)
    except RuleSettingsError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Đã lưu {args.rule} ({'dự án' if args.scope == 'project' else 'máy'}): {res['rule'] or 'mặc định'}")
    return 0


def cmd_learn_layers(args: argparse.Namespace) -> int:
    """Học quy ước tên layer có sẵn của công ty từ một bản vẽ; LY-01 coi các layer đó là đúng quy ước."""
    from .reader_select import choose_reader, read_with
    from .rule_config import RuleSettingsError, learn_layers

    path = Path(args.path)
    model = read_with(path, choose_reader(path).reader)
    ws = Path(args.workspace) if args.workspace else path.resolve().parent
    try:
        res = learn_layers(args.standard or DEFAULT_STANDARD, [la.name for la in model.layers], scope=args.scope,
                           workspace=ws, standards_dir=Path(args.standards_dir) if args.standards_dir else None)
    except RuleSettingsError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Đã học {len(res['patterns'])} mẫu layer ({res['total']} mẫu trong cài đặt). Quét lại để thấy LY-01 mới.")
    return 0


def parse_sheet_list(spec: str | None, count: int) -> list[int] | None:
    """'1,3-5' -> [1, 3, 4, 5] (đánh số từ 1 như tên 'Tờ n'). None/'' -> None (mọi tờ)."""
    if not spec:
        return None
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        a, _, b = part.partition("-")
        lo, hi = int(a), int(b or a)
        if lo < 1 or hi > count or lo > hi:
            raise ValueError(f"Tờ '{part}' ngoài khoảng 1–{count}.")
        out.extend(range(lo, hi + 1))
    return sorted(set(out))


def sheet_handles(model, picks: list[int] | None) -> set[str] | None:
    """Handle của các tờ chọn (gồm khung tên và mọi đối tượng thuộc tờ)."""
    if picks is None:
        return None
    from .sheets import build_structure

    st = build_structure(model)
    out: set[str] = set()
    for i in picks:
        out.update(st.sheets[i - 1].handles)
    return out


def run_edit(path: Path, ops_data, *, yes: bool, standard: str = "design-hygiene-v0", dwg: bool = False,
             label: str = "") -> int:
    """Đề xuất changeset trên tệp (thư mục chứa tệp là thư mục làm việc), in xem trước; `yes` thì áp ra tệp MỚI."""
    from .agent.workspace import Workspace
    from .changeset import ChangesetError, OpError, apply, propose

    ws = Workspace(path.resolve().parent)
    try:
        cs, pv = propose(ws, path.name, ops_data, standard=standard, created_by="user")
    except (OpError, ChangesetError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    _print_preview(pv)
    if not pv["ok"]:
        print("Kiểm KHÔNG ĐẠT: không áp dụng.", file=sys.stderr)
        return 1
    if not yes:
        if not (_interactive() and _confirm(f"Áp dụng {label or 'thay đổi'} ra tệp MỚI? [c/k] ")):
            print(f"Chưa áp dụng. Áp dụng sau: cadguard apply {cs.id} --workspace \"{ws.root}\" --yes")
            return 0
    try:
        res = apply(ws, cs.id, confirm=True)
    except ChangesetError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    out = ws.root / res["output"]["path"]
    print(f"Đã ghi tệp mới: {out.name} (hoàn tác: cadguard undo {cs.id} --workspace \"{ws.root}\" --yes)")
    if dwg:
        from .dwg import DwgError, dxf_to_dwg

        try:
            print(f"Đã ghi DWG: {dxf_to_dwg(out, out.with_suffix('.dwg')).name}")
        except DwgError as exc:
            print(f"Không ghi được DWG: {exc}", file=sys.stderr)
    return 0


def cmd_unicode(args: argparse.Namespace) -> int:
    """Chuyển chữ TCVN3/VNI sang Unicode (phông Be Vietnam Pro), ra tệp MỚI; chỉ chạy khi người dùng gọi."""
    from .dwg import DwgError, ensure_dxf
    from .reader_select import read_with

    try:
        path = ensure_dxf(Path(args.path))
    except DwgError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    op: dict = {"op": "convert_unicode", "font": args.font_file, "family": args.font}
    if args.sheets:
        from .sheets import build_structure

        model = read_with(path, "ezdxf")
        try:
            picks = parse_sheet_list(args.sheets, len(build_structure(model).sheets))
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        op["handles"] = sorted(sheet_handles(model, picks) or [])
        if not op["handles"]:
            print("Các tờ đã chọn không có đối tượng.", file=sys.stderr)
            return 2
    return run_edit(path, [op], yes=args.yes, dwg=args.dwg, label="chuyển Unicode")


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
    from . import fixtures  # nạp lười: kéo ezdxf

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


def cmd_app(args: argparse.Namespace) -> int:
    from .app import run_from_args

    return run_from_args(args)


def cmd_mcp(args: argparse.Namespace) -> int:
    from .mcp_server import run_from_args  # SDK `mcp` chỉ được import bên trong, khi chạy lệnh này

    return run_from_args(args)


def cmd_watch(args: argparse.Namespace) -> int:
    from . import watch
    from .reader_select import check_threshold

    try:
        check_threshold(args.stream_threshold_mb)
    except ValueError as exc:
        print(f"--stream-threshold-mb: {exc}", file=sys.stderr)
        return 2
    profile = load_profile(args.profile) if args.profile else None
    name = args.standard or (profile.standard if profile else DEFAULT_STANDARD)
    from .rule_config import effective_standard

    std = effective_standard(name, Path(args.standards_dir) if args.standards_dir else None, profile=profile,
                             workspace=Path(args.folder))
    return watch.run(Path(args.folder), std, interval=args.interval, once=args.once, reader=args.reader,
                     threshold_mb=args.stream_threshold_mb)


def cmd_doctor(args: argparse.Namespace) -> int:
    from .doctor import run_doctor

    return run_doctor(probe_mcp=args.mcp, as_json=args.json)


def cmd_mcp_config(args: argparse.Namespace) -> int:
    from .mcp_config import render

    try:
        text, note = render(args.client, Path(args.workspace), profile=Path(args.profile) if args.profile else None,
                            allow_propose=args.allow_propose, allow_autocad=args.allow_autocad)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(text)
    print(note, file=sys.stderr)
    return 0


def cmd_sheets(args: argparse.Namespace) -> int:
    """Chỉ mục tờ (trang in) của một bản vẽ: tờ, tiêu đề, khổ/tỉ lệ, số đối tượng, ứng viên rác. Không sửa bản vẽ."""
    import json

    from .reader_select import choose_reader, read_with
    from .sheets import build_structure

    from .dwg import ensure_dxf

    path = ensure_dxf(Path(args.path))
    if getattr(args, "render", None):
        from .sheet_render import render_sheets

        model = read_with(path, "ezdxf")
        try:
            picks = parse_sheet_list(args.pick, len(build_structure(model).sheets))
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        res = render_sheets(path, Path(args.render), picks, fmt=args.format)
        print(f"Đã dựng {len(res['sheets'])}/{res['count']} tờ trong {res['seconds']} giây: "
              f"{Path(args.render) / 'index.html'}")
        return 0
    model = read_with(path, choose_reader(path).reader)
    d = build_structure(model).to_dict(include_map=args.map)
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return 0
    if not d["sheets"]:
        print("Không nhận ra tờ nào (không có layout có khung nhìn, không có khung tên/khung tờ khổ ISO trong Model).")
    for s in d["sheets"]:
        extra = ", ".join(x for x in (s["paper"], f"1:{s['scale']:g}" if s["scale"] else None,
                                      "layout" if s["kind"] == "layout" else "khung trong Model") if x)
        title = f": {s['title']}" + (" (giải mã TCVN3/VNI)" if s["title_source"] == "text-decoded" else "") if s["title"] else ""
        print(f"{s['name']}{title}  [{extra}]  {s['entity_count']} đối tượng")
    j = d["junk"]
    print(f"Ứng viên rác (chỉ gợi ý, không tự xoá): {j['outside']['count']} đối tượng ngoài tờ, "
          f"{j['stray']['count']} đối tượng lạc xa, {len(j['empty_layers'])} layer rỗng, {len(j['unused_blocks'])} khối không dùng.")
    if d["no_position"]:
        print(f"{d['no_position']} đối tượng không có toạ độ trong mô hình (HATCH…): không gán được vào tờ.")
    return 0


def cmd_autocad(args: argparse.Namespace) -> int:
    import shutil

    src = Path(__file__).with_name("autocad") / "cadguard.lsp"
    if args.copy_to:
        dest_dir = Path(args.copy_to)
        if not dest_dir.is_dir():
            print("Thư mục đích không tồn tại.", file=sys.stderr)
            return 2
        dest = dest_dir / src.name
        shutil.copyfile(src, dest)
        src = dest
        print(f"Đã chép: {dest}")
    print(f"Tệp AutoLISP: {src}")
    print("Trong AutoCAD: APPLOAD -> chọn tệp trên (nên đặt thư mục chứa tệp vào Trusted Locations), rồi:\n"
          "  CGTHUMUC  đặt thư mục làm việc (trùng thư mục của `cadguard watch` / `cadguard mcp --workspace`)\n"
          "  CGXUAT    xuất bản vẽ đang mở ra DXF (bản sao, DWG giữ nguyên)\n"
          "  CGTOI     nhập handle do cad-guard/trợ lý báo để phóng tới đối tượng\n"
          "  CGDEN     tới đối tượng vừa bấm 'Tới trong AutoCAD' trên giao diện `cadguard app`\n"
          "  CGBAOCAO  mở báo cáo HTML của bản vẽ đang mở\n"
          "  CGHELP    danh sách lệnh và hướng dẫn chi tiết từng lệnh\n"
          "Plugin .NET (bảng CGBANG, ghim lỗi CGGHIM; AutoCAD bản đầy đủ): python scripts/build_acad_plugin.py rồi NETLOAD.\n"
          "Hướng dẫn và danh sách kiểm tay: docs/autocad.md")
    return 0


def cmd_scene(args: argparse.Namespace) -> int:
    import json

    from .dxf_reader import read_dxf
    from .scene import build_scene, load_supplement, render_form, render_html, write_glb

    model = read_dxf(args.path)
    for extra in args.with_ or []:  # bổ sung hình chiếu còn thiếu từ DXF khác; mã tay cầm thêm tiền tố để khỏi trùng
        for e in read_dxf(extra).entities:
            e.handle = f"x{len(model.entities)}-{e.handle}"
            model.entities.append(e)
    supp: dict = {}
    notes: list[str] = []
    if args.supplement:
        supp, note = load_supplement(json.loads(Path(args.supplement).read_text(encoding="utf-8")), model.file_hash)
        if note:
            notes.append(note)
    sc = build_scene(model, supp)
    sc.notes.extend(notes)
    out = Path(args.out)
    if out.suffix.lower() == ".html":
        out.write_text(render_html(sc), encoding="utf-8")
    elif out.suffix.lower() == ".json":
        out.write_text(sc.model_dump_json(by_alias=True, indent=2), encoding="utf-8")
    else:
        write_glb(sc, out)
    if args.form and sc.gaps:
        Path(args.form).write_text(render_form(sc), encoding="utf-8")
    print(f"{len(sc.walls)} đoạn tường, {len(sc.modules)} mô-đun, {len(sc.panels)} tấm, {len(sc.gaps)} phần thiếu, {len(sc.skipped)} bỏ qua -> {out}")
    for note in sc.notes:
        print(note, file=sys.stderr)
    for g in sc.gaps:
        print(f"thiếu [{g.kind}] {g.message}", file=sys.stderr)
    for sk in sc.skipped:
        print(f"bỏ qua {sk.handle}: {sk.reason}", file=sys.stderr)
    if sc.gaps and args.form:
        print(f"Form bổ sung: {args.form}", file=sys.stderr)
    if sc.gaps:
        return 3  # đã ghi phần dựng được; còn phần thiếu cần bổ sung
    return 0 if (sc.walls or sc.modules or sc.panels) else 2


def cmd_studio(args: argparse.Namespace) -> int:
    from .studio.llm import AnthropicBackend, ClaudeCliBackend, LlmError, auto_backend
    from .studio.server import serve

    backend = None
    try:
        if args.backend == "auto":
            backend = auto_backend()
        elif args.backend == "api":
            backend = AnthropicBackend()
        elif args.backend == "cli":
            backend = ClaudeCliBackend()
    except LlmError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    serve(args.port, backend, open_browser=args.open)
    return 0


def _main_mcp(argv: list[str]) -> int:
    """Đường nhanh cho `cadguard mcp`: không dựng parser của mọi lệnh khác (chúng kéo ezdxf, ứng dụng, Studio), để máy
    chủ trả `initialize` sớm và không chạm trần thời gian khởi động của máy khách MCP."""
    from .mcp_server import add_arguments, run_from_args

    p = argparse.ArgumentParser(prog="cadguard mcp", add_help=False,
                                description="Máy chủ MCP stdio của cad-guard, mặc định CHỈ ĐỌC. Cần SDK: pip install cadguard[agent].")
    add_arguments(p)
    return run_from_args(p.parse_args(argv))


def main(argv: list[str] | None = None) -> int:
    _utf8()
    args_in = sys.argv[1:] if argv is None else list(argv)
    if args_in[:1] == ["mcp"]:
        return _main_mcp(args_in[1:])
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

    rs = sub.add_parser("rule-set", help="sửa một luật không cần tài khoản: --enable/--disable, --severity, --param")
    rs.add_argument("rule", help="mã luật, vd. LY-01")
    rs.add_argument("--standard", default=None)
    rs.add_argument("--standards-dir", default=None)
    rs.add_argument("--workspace", default=".", help="thư mục dự án (mặc định thư mục hiện tại)")
    rs.add_argument("--scope", choices=["project", "machine"], default="project",
                    help="project = dự án này; machine = mọi dự án trên máy")
    g = rs.add_mutually_exclusive_group()
    g.add_argument("--enable", action="store_true")
    g.add_argument("--disable", action="store_true")
    rs.add_argument("--severity", choices=["E", "W", "I"])
    rs.add_argument("--param", action="append", metavar="TÊN=GIÁ_TRỊ", help="giá trị JSON hoặc chuỗi; lặp được")
    rs.add_argument("--reset", action="store_true", help="về mặc định (xoá mọi cài đặt của luật trong phạm vi)")
    rs.set_defaults(fn=cmd_rule_set)

    un = sub.add_parser("unicode", help="chuyển chữ TCVN3/VNI sang Unicode (phông Be Vietnam Pro), ra tệp mới")
    un.add_argument("path", help="tệp .dxf (hoặc .dwg khi máy có AutoCAD bản đầy đủ)")
    un.add_argument("--sheets", default=None, help="chỉ các tờ này, vd. 1,3-5 (mặc định cả bản vẽ)")
    un.add_argument("--font", default="Be Vietnam Pro", help="tên họ phông Unicode (mặc định Be Vietnam Pro)")
    un.add_argument("--font-file", default="BeVietnamPro-Regular.ttf", help="tệp phông TTF ghi vào kiểu chữ")
    un.add_argument("--yes", action="store_true", help="áp dụng ngay sau khi xem trước đạt (không hỏi)")
    un.add_argument("--dwg", action="store_true", help="ghi thêm bản DWG của tệp mới (cần accoreconsole)")
    un.set_defaults(fn=cmd_unicode)

    ll = sub.add_parser("learn-layers", help="học quy ước tên layer của công ty từ một bản vẽ (giảm nhiễu LY-01)")
    ll.add_argument("path")
    ll.add_argument("--standard", default=None)
    ll.add_argument("--standards-dir", default=None)
    ll.add_argument("--workspace", default=None, help="thư mục dự án (mặc định thư mục chứa bản vẽ)")
    ll.add_argument("--scope", choices=["project", "machine"], default="project")
    ll.set_defaults(fn=cmd_learn_layers)

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

    from .assistant.commands import add_parsers as assistant_parsers  # ask, chat, engines, keys (trợ lý AI)

    assistant_parsers(sub)

    from .app import add_arguments as app_arguments

    ua = sub.add_parser("app", help="mở giao diện cục bộ trong trình duyệt (chỉ 127.0.0.1, có mã phiên)",
                        description="Ứng dụng web cục bộ: danh sách bản vẽ, kết quả kiểm, đề xuất sửa (xem trước, áp dụng "
                        "ra tệp mới khi bạn xác nhận, hoàn tác), luật áp dụng, trò chuyện với trợ lý AI. Xem docs/app.md.")
    app_arguments(ua)
    ua.set_defaults(fn=cmd_app)
    sc = sub.add_parser("scene", help="dựng 3D tất định từ DXF (.glb, .html hoặc .json)")
    sc.add_argument("path")
    sc.add_argument("--out", required=True, help="tệp đầu ra: .glb, .html hoặc .json")
    sc.add_argument("--form", help="nếu còn phần thiếu: ghi form HTML để nhập bổ sung")
    sc.add_argument("--supplement", help="tệp .cgsup.json (tải từ form) chứa giá trị bổ sung")
    sc.add_argument("--with", dest="with_", action="append", help="DXF bổ sung hình chiếu còn thiếu (có thể lặp)")
    sc.set_defaults(fn=cmd_scene)

    st = sub.add_parser("studio", help="ứng dụng web cục bộ: trao đổi với LLM, xem 3D, bổ sung dữ liệu thiếu")
    st.add_argument("--port", type=int, default=8770)
    st.add_argument("--backend", choices=["auto", "api", "cli", "none"], default="auto", help="api = khoá Anthropic của bạn (biến ANTHROPIC_API_KEY hoặc `cadguard keys set anthropic`); "
                    "cli = lệnh claude nguyên bản; none = không LLM")
    st.add_argument("--open", action="store_true", help="mở trình duyệt")
    st.set_defaults(fn=cmd_studio)

    from .review.server import run as run_review
    from .review.store import ReviewError
    rv = sub.add_parser("review", help="cổng duyệt hồ sơ riêng qua Tailscale Serve")
    rv.add_argument("--workspace", required=True)
    rv.add_argument("--port", type=int, default=8781)
    rv.add_argument("--public-origin", help="HTTPS .ts.net của Tailscale Serve")
    rv.add_argument("--profile", help="hồ sơ công ty YAML")
    rv.set_defaults(fn=run_review)

    w = sub.add_parser("watch", help="theo dõi thư mục: tự kiểm DXF mới/vừa đổi (vd. từ lệnh CGXUAT trong AutoCAD)",
                       description="Theo dõi thư mục; mỗi DXF mới hoặc vừa đổi được kiểm và ghi báo cáo vào "
                       "<thư mục>/.cadguard/reports/<tên>.html|.json. Chỉ đọc DXF, không ghi bản vẽ.")
    w.add_argument("folder", help="thư mục theo dõi (nên trùng --workspace của `cadguard mcp`)")
    w.add_argument("--interval", type=float, default=2.0, help="giây giữa hai lần quét (mặc định 2)")
    w.add_argument("--once", action="store_true", help="kiểm mọi DXF hiện có một lần rồi thoát")
    w.add_argument("--profile", default=None, help="hồ sơ công ty (YAML cg.company-profile/1)")
    w.add_argument("--reader", choices=["ezdxf", "stream", "auto"], default="auto")
    w.add_argument("--stream-threshold-mb", type=float, default=50.0)
    common(w)
    w.set_defaults(fn=cmd_watch)

    dr = sub.add_parser("doctor", help="kiểm môi trường: Python, thư viện, SDK MCP, kho khoá, tệp AutoLISP, tốc độ MCP")
    dr.add_argument("--mcp", action="store_true", help="chạy thử máy chủ MCP thật qua stdio trên DXF tổng hợp và đo thời gian")
    dr.add_argument("--json", action="store_true")
    dr.set_defaults(fn=cmd_doctor)

    mc = sub.add_parser("mcp-config", help="in cấu hình MCP cho máy khách (claude-desktop, claude-code, codex); không ghi tệp")
    mc.add_argument("client", choices=["claude-desktop", "claude-code", "codex"])
    mc.add_argument("--workspace", required=True, help="thư mục làm việc (DXF của phiên)")
    mc.add_argument("--profile", default=None, help="hồ sơ công ty (YAML)")
    mc.add_argument("--allow-propose", action="store_true", help="bật công cụ propose_changeset (mặc định TẮT)")
    mc.add_argument("--allow-autocad", action="store_true",
                    help="bật công cụ show_in_autocad: trợ lý đưa AutoCAD tới đối tượng lỗi (mặc định TẮT)")
    mc.set_defaults(fn=cmd_mcp_config)

    sh = sub.add_parser("sheets", help="chỉ mục tờ (trang in): tờ, tiêu đề, khổ/tỉ lệ, ứng viên rác (không sửa bản vẽ)")
    sh.add_argument("path", help="tệp DXF")
    sh.add_argument("--json", action="store_true", help="in JSON cg.structure/1")
    sh.add_argument("--map", action="store_true", help="kèm bảng handle -> tờ trong JSON")
    sh.add_argument("--render", default=None, metavar="THƯ_MỤC",
                    help="dựng hình từng tờ (SVG + index.html; chữ mã cũ hiện đúng) vào thư mục này")
    sh.add_argument("--pick", default=None, help="chỉ dựng các tờ này, vd. 1,3-5")
    sh.add_argument("--format", choices=["svg", "png", "pdf"], default="svg", help="png/pdf cần matplotlib")
    sh.set_defaults(fn=cmd_sheets)

    ac = sub.add_parser("autocad", help="đường dẫn và cách nạp cadguard.lsp (CGXUAT, CGTOI, CGDEN, CGBAOCAO, CGHELP) cho AutoCAD")
    ac.add_argument("--copy-to", metavar="THƯ_MỤC", help="chép cadguard.lsp vào thư mục này")
    ac.set_defaults(fn=cmd_autocad)

    args = p.parse_args(argv)
    try:
        return int(args.fn(args))
    except (FileNotFoundError, ProfileError, ReviewError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
