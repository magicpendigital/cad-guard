"""Dòng lệnh: cadguard audit | stats | rules | fixtures.

Mã thoát của `audit`: 0 = không có lỗi mức E; 1 = có lỗi mức E; 2 = không đọc được đầu vào/chuẩn.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from . import __version__, fixtures, report, telemetry
from .dxf_reader import read_dxf
from .rules import REGISTRY
from .runner import audit_model
from .standard import find_standards_dir, load_standard
from .stats import compute_stats


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


def cmd_audit(args: argparse.Namespace) -> int:
    std = load_standard(args.standard, Path(args.standards_dir) if args.standards_dir else None)
    files = _collect(args.paths)
    if not files:
        print("Không có tệp .dxf nào để quét.", file=sys.stderr)
        return 2
    items = []
    for f in files:
        try:
            model = read_dxf(f)
        except Exception as exc:  # noqa: BLE001
            print(f"Không đọc được {f.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
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
    std = load_standard(args.standard, Path(args.standards_dir) if args.standards_dir else None)
    stats = compute_stats(std)
    print(json.dumps(stats) if args.json else "\n".join(f"{k}: {v}" for k, v in stats.items()))
    return 0


def cmd_rules(args: argparse.Namespace) -> int:
    std = load_standard(args.standard, Path(args.standards_dir) if args.standards_dir else None)
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


def main(argv: list[str] | None = None) -> int:
    _utf8()
    p = argparse.ArgumentParser(prog="cadguard", description="cad-guard: kiểm tra bản vẽ theo luật tất định")
    p.add_argument("--version", action="version", version=f"cadguard {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--standard", default="furniture-v0")
        sp.add_argument("--standards-dir", default=None)

    a = sub.add_parser("audit", help="quét tệp/thư mục DXF")
    a.add_argument("paths", nargs="+")
    a.add_argument("--out", help="ghi báo cáo: .html hoặc .json")
    a.add_argument("--json", action="store_true", help="in báo cáo JSON ra stdout")
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

    args = p.parse_args(argv)
    try:
        return int(args.fn(args))
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
