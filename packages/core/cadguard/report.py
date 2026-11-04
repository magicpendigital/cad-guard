"""Báo cáo tiếng Việt: report.json (cho máy) và report.html (cho người)."""

from __future__ import annotations

import html
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .runner import AuditResult
from .standard import Standard

SEV_LABEL = {"E": "Lỗi", "W": "Cảnh báo", "I": "Thông tin"}


def build_report(standard: Standard, items: list[tuple[str, str, AuditResult]]) -> dict:
    """items: (tên tệp hiển thị, băm nội dung, kết quả)."""
    files = []
    totals = {"E": 0, "W": 0, "I": 0}
    for name, fhash, res in items:
        counts = {"E": 0, "W": 0, "I": 0}
        for f in res.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        for k, v in counts.items():
            totals[k] += v
        files.append(
            {
                "file": name,
                "file_hash": fhash,
                "rules_run": res.rules_run,
                "counts": counts,
                "findings": [asdict(f) for f in res.findings],
                "skipped": [{"rule": r, "reason": why} for r, why in res.skipped],
            }
        )
    return {
        "schema": "cg.report/1",
        "tool_version": __version__,
        "standard": {"name": standard.name, "version": standard.version,
                     **({"profile": dict(standard.profile)} if standard.profile else {})},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": files,
        "totals": totals,
    }


def write_json(report: dict, path: Path) -> None:
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


_CSS = """
:root{--bg:#fff;--fg:#1d2433;--mut:#5b6577;--line:#d9dee7;--e:#b42318;--w:#a15c07;--i:#1d5fa6;--card:#f6f8fb}
@media (prefers-color-scheme:dark){:root{--bg:#10141c;--fg:#e6e9ef;--mut:#9aa4b5;--line:#2a3140;--e:#ff8a80;--w:#ffc069;--i:#7db7ff;--card:#171c26}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,Segoe UI,Roboto,sans-serif;margin:0;padding:24px 16px}
main{max-width:980px;margin:0 auto}h1{font-size:22px}h2{font-size:17px;margin-top:28px}
table{width:100%;border-collapse:collapse;margin:8px 0}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:10px 0}
.E{color:var(--e);font-weight:600}.W{color:var(--w);font-weight:600}.I{color:var(--i);font-weight:600}.mut{color:var(--mut)}
code{font-size:13px}
"""


def render_html(report: dict) -> str:
    e = html.escape
    parts = [
        "<!doctype html><html lang='vi'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>Báo cáo kiểm tra bản vẽ</title><style>" + _CSS + "</style></head><body><main>",
        "<h1>Báo cáo kiểm tra bản vẽ</h1>",
        f"<p class='mut'>Chuẩn <b>{e(report['standard']['name'])}</b>"
        + (f" · hồ sơ công ty <b>{e(report['standard']['profile']['name'])}</b> {e(report['standard']['profile']['version'])}"
           if report["standard"].get("profile") else "")
        + f" · cad-guard {e(report['tool_version'])} · {e(report['generated_at'])}</p>",
        f"<p>Tổng: <span class='E'>{report['totals']['E']} lỗi</span> · <span class='W'>{report['totals']['W']} cảnh báo</span> · <span class='I'>{report['totals']['I']} thông tin</span></p>",
        "<p class='mut'>Công cụ chỉ gợi ý, không ký duyệt bản vẽ. Người kiểm vẫn là người quyết định.</p>",
    ]
    for f in report["files"]:
        c = f["counts"]
        parts.append(f"<h2>{e(f['file'])} <span class='mut'>({e(f['file_hash'])})</span></h2>")
        parts.append(f"<div class='card'>{f['rules_run']} luật đã chạy · {c['E']} lỗi · {c['W']} cảnh báo · {c['I']} thông tin</div>")
        if f["findings"]:
            parts.append("<table><tr><th>Mã</th><th>Mức</th><th>Nội dung</th><th>Vị trí</th></tr>")
            order = {"E": 0, "W": 1, "I": 2}
            for it in sorted(f["findings"], key=lambda x: (order.get(x["severity"], 9), x["rule_id"])):
                where = []
                if it.get("layout"):
                    where.append(f"layout {it['layout']}")
                if it.get("layer"):
                    where.append(f"layer {it['layer']}")
                if it.get("handles"):
                    where.append("handle " + ", ".join(it["handles"]))
                parts.append(
                    f"<tr><td><code>{e(it['rule_id'])}</code></td><td class='{e(it['severity'])}'>{SEV_LABEL.get(it['severity'], it['severity'])}</td>"
                    f"<td>{e(it['message'])}</td><td class='mut'>{e(' · '.join(where))}</td></tr>"
                )
            parts.append("</table>")
        else:
            parts.append("<p>Không có phát hiện nào.</p>")
        if f["skipped"]:
            parts.append("<p class='mut'>Luật bỏ qua: " + e("; ".join(f"{s['rule']} ({s['reason']})" for s in f["skipped"])) + "</p>")
    parts.append("</main></body></html>")
    return "".join(parts)


def write_html(report: dict, path: Path) -> None:
    path.write_text(render_html(report), encoding="utf-8")
