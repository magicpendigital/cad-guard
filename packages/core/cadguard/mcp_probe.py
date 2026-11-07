"""Đo máy chủ MCP của cad-guard qua stdio THẬT (client của SDK `mcp`), như một máy khách (Claude Desktop/Code…) thấy.

Dùng cho `cadguard doctor --mcp` và `scripts/mcp_smoke.py`. Chỉ chạy trên thư mục DXF được truyền vào (thường là DXF
tổng hợp do `fixtures.py` sinh). Không gọi mô hình, không mạng.

Tiêu chí chạy thử (PLAN.md, Đợt 3): khởi động tới `list_tools` ≤ 5 s; `audit` lần sau ≤ 1 s; mỗi kết quả ước lượng
< 10.000 token (ngưỡng cảnh báo của Claude Code); chuỗi gọi liên tiếp không lỗi giao thức.
"""
from __future__ import annotations

import asyncio
import math
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

LIMITS = {"startup_s": 5.0, "audit_warm_s": 1.0, "est_tokens": 10_000, "errors": 0}
CHARS_PER_TOKEN = 3  # ước lượng thận trọng cho JSON có tiếng Việt (ít ký tự/token hơn tiếng Anh)


def _env() -> dict:
    core = Path(__file__).resolve().parents[1]
    paths = [str(core)] + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else [])
    return {"PYTHONPATH": os.pathsep.join(paths), "PYTHONUTF8": "1"}


async def _probe(workspace: Path, python: str, calls: int, errlog) -> dict:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=python, args=["-m", "cadguard", "mcp", "--workspace", str(workspace)],
                                   env=_env(), cwd=str(workspace))
    m: dict = {"calls": 0, "errors": 0, "max_result_chars": 0}
    t0 = time.perf_counter()

    def size(res) -> int:
        n = sum(len(getattr(c, "text", "") or "") for c in res.content)
        m["max_result_chars"] = max(m["max_result_chars"], n)
        return n

    async with stdio_client(params, errlog=errlog) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            m["initialize_s"] = time.perf_counter() - t0
            tools = (await s.list_tools()).tools
            m["startup_s"] = time.perf_counter() - t0
            m["tools"] = [t.name for t in tools]

            listing = await s.call_tool("list_drawings", {})
            size(listing)
            import json

            ids = [d["id"] for d in json.loads(listing.content[0].text)["drawings"]] if not listing.isError else []
            m["drawings"] = len(ids)
            cold, warm = [], []
            for fid in ids:
                for bucket in (cold, warm):
                    t = time.perf_counter()
                    r = await s.call_tool("audit", {"file": fid})
                    bucket.append(time.perf_counter() - t)
                    size(r)
                    m["errors"] += int(r.isError)
                r = await s.call_tool("get_model_summary", {"file": fid})
                size(r)
                m["errors"] += int(r.isError)
            m["audit_cold_s"] = max(cold, default=0.0)
            m["audit_warm_s"] = max(warm, default=0.0)

            lat = []
            plan = [("explain_rule", {"rule_id": "LY-01"})]
            plan += [("audit", {"file": f}) for f in ids] + [("query_model", {"file": f, "limit": 50}) for f in ids]
            for i in range(calls):
                name, args = plan[i % len(plan)]
                t = time.perf_counter()
                try:
                    r = await s.call_tool(name, args)
                    m["errors"] += int(r.isError)
                    size(r)
                except Exception:  # noqa: BLE001 — lỗi giao thức được đếm, không làm dừng phép đo
                    m["errors"] += 1
                lat.append(time.perf_counter() - t)
                m["calls"] += 1
            if lat:
                lat.sort()
                m["call_p50_s"] = statistics.median(lat)
                m["call_p95_s"] = lat[min(len(lat) - 1, math.ceil(0.95 * len(lat)) - 1)]
    m["est_tokens"] = math.ceil(m["max_result_chars"] / CHARS_PER_TOKEN)
    return m


def probe(workspace: Path, *, python: str | None = None, calls: int = 100, timeout: float = 300.0) -> dict:
    """Chạy máy chủ MCP thật trên `workspace` và trả số đo (giây, ký tự, số lỗi)."""
    with tempfile.TemporaryFile("w+", encoding="utf-8") as errlog:
        try:
            return asyncio.run(asyncio.wait_for(_probe(Path(workspace), python or sys.executable, calls, errlog), timeout))
        except Exception as exc:  # noqa: BLE001
            errlog.seek(0)
            tail = errlog.read()[-800:]
            raise RuntimeError(f"Không chạy được máy chủ MCP ({type(exc).__name__}). stderr máy chủ:\n{tail}") from None


def probe_synthetic(calls: int = 100) -> dict:
    """Đo trên thư mục tạm chứa DXF tổng hợp (không chạm dữ liệu thật)."""
    from . import fixtures

    with tempfile.TemporaryDirectory(prefix="cadguard-probe-") as d:
        fixtures.make_all(Path(d))
        return probe(Path(d), calls=calls)


def evaluate(m: dict) -> list[tuple[str, bool, str]]:
    """[(tên tiêu chí, đạt?, mô tả)] theo `LIMITS`."""
    return [
        ("Khởi động tới list_tools", m["startup_s"] <= LIMITS["startup_s"], f"{m['startup_s']:.2f} s (≤ {LIMITS['startup_s']:g} s)"),
        ("audit lần sau (nóng)", m["audit_warm_s"] <= LIMITS["audit_warm_s"],
         f"{m['audit_warm_s']:.2f} s lớn nhất (≤ {LIMITS['audit_warm_s']:g} s); lần đầu {m['audit_cold_s']:.2f} s"),
        ("Kích thước kết quả", m["est_tokens"] < LIMITS["est_tokens"],
         f"~{m['est_tokens']} token ước lượng ({m['max_result_chars']} ký tự lớn nhất; < {LIMITS['est_tokens']})"),
        ("Gọi liên tiếp", m["errors"] == 0 and m["calls"] > 0,
         f"{m['calls']} lượt, {m['errors']} lỗi; p50 {m.get('call_p50_s', 0):.3f} s, p95 {m.get('call_p95_s', 0):.3f} s"),
    ]


__all__ = ["LIMITS", "evaluate", "probe", "probe_synthetic"]
