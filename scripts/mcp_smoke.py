#!/usr/bin/env python3
"""Đo máy chủ MCP của cad-guard qua stdio thật trên DXF tổng hợp (không dữ liệu khách, không gọi mô hình).

  python scripts/test.py --extras agent --run ../../scripts/mcp_smoke.py [--calls 100] [--out docs/perf/mcp-smoke.json]

In bảng tiêu chí chạy thử (PLAN.md, Đợt 3); mã thoát 1 nếu có tiêu chí không đạt. `--out` ghi số đo (chỉ số tổng hợp).
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calls", type=int, default=100)
    ap.add_argument("--out", help="ghi số đo JSON (đường dẫn tương đối với gốc repo hoặc tuyệt đối)")
    a = ap.parse_args()
    from cadguard.mcp_probe import evaluate, probe_synthetic

    m = probe_synthetic(calls=a.calls)
    rows = evaluate(m)
    for name, ok, detail in rows:
        print(f"{'[đạt]  ' if ok else '[KHÔNG]'} {name}: {detail}")
    print(f"Công cụ: {', '.join(m['tools'])}; {m['drawings']} DXF tổng hợp.")
    if a.out:
        out = Path(a.out) if Path(a.out).is_absolute() else ROOT / a.out
        out.parent.mkdir(parents=True, exist_ok=True)
        rec = {"schema": "cg.mcp-smoke/1", "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "python": platform.python_version(), "os": platform.system(), "metrics": m,
               "criteria": [{"name": n, "ok": ok, "detail": d} for n, ok, d in rows]}
        out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Đã ghi: {out}")
    return 0 if all(ok for _, ok, _ in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
