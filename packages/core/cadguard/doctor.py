"""`cadguard doctor`: kiểm môi trường chạy thử (Python, thư viện, chuẩn, SDK MCP, kho khoá, tệp AutoLISP, tốc độ MCP).

Không đọc khoá hay token (chỉ hỏi kho khoá có cài không), không gọi mạng, không đọc bản vẽ thật. `--mcp` chạy máy chủ MCP
thật trên DXF tổng hợp trong thư mục tạm.
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _version(mod: str) -> str | None:
    try:
        m = importlib.import_module(mod)
    except Exception:  # noqa: BLE001
        return None
    try:
        from importlib.metadata import version

        dist = {"yaml": "PyYAML", "PIL": "Pillow"}.get(mod, mod)
        return version(dist)
    except Exception:  # noqa: BLE001
        return getattr(m, "__version__", "có")


def _import_seconds(module: str) -> float | None:
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(Path(__file__).resolve().parents[1]),
                                                        os.environ.get("PYTHONPATH", "")]), PYTHONUTF8="1")
    t = time.perf_counter()
    r = subprocess.run([sys.executable, "-c", f"import {module}"], env=env, capture_output=True, timeout=120)
    return time.perf_counter() - t if r.returncode == 0 else None


def checks(probe_mcp: bool = False) -> list[dict]:
    """[{name, ok, required, detail}]"""
    out: list[dict] = []

    def add(name: str, ok: bool, detail: str, required: bool = True) -> None:
        out.append({"name": name, "ok": bool(ok), "required": required, "detail": detail})

    v = sys.version_info
    add("Python 3.10–3.14", (3, 10) <= v[:2] <= (3, 14), f"{v.major}.{v.minor}.{v.micro} ({sys.executable})")
    for mod, label in (("ezdxf", "ezdxf"), ("pydantic", "pydantic"), ("yaml", "PyYAML"), ("PIL", "Pillow"), ("qrcode", "qrcode")):
        ver = _version(mod)
        add(f"Thư viện {label}", ver is not None, ver or "thiếu: pip install -e packages/core")
    try:
        from .rules import REGISTRY
        from .standard import find_standards_dir, load_standard

        sd = find_standards_dir(Path(__file__).resolve())
        std = load_standard("furniture-v0", sd)
        n = sum(1 for r in std.rules if r.implemented and r.id in REGISTRY)
        add("Chuẩn furniture-v0", True, f"{n}/{len(std.rules)} luật đã cài ({sd})")
    except Exception as exc:  # noqa: BLE001
        add("Chuẩn furniture-v0", False, f"không nạp được: {type(exc).__name__}")
    mcp_ver = _version("mcp")
    add("SDK MCP (extras [agent])", mcp_ver is not None,
        mcp_ver or "thiếu: pip install cadguard[agent] (trong repo: python scripts/test.py --extras agent)")
    kr = _version("keyring")
    add("Kho khoá hệ điều hành (keyring)", kr is not None, kr or "tuỳ chọn: pip install cadguard[keyring]", required=False)
    lsp = Path(__file__).with_name("autocad") / "cadguard.lsp"
    add("Tệp AutoLISP cadguard.lsp", lsp.is_file(), str(lsp))
    secs = _import_seconds("cadguard.mcp_server")
    add("Nạp máy chủ MCP", secs is not None and secs < 5, f"{secs:.2f} s (tiến trình mới)" if secs is not None else "lỗi import")
    if probe_mcp:
        if mcp_ver is None:
            add("Chạy thử MCP qua stdio", False, "bỏ qua: chưa có SDK MCP")
        else:
            from .mcp_probe import evaluate, probe_synthetic

            try:
                m = probe_synthetic(calls=40)
                for name, ok, detail in evaluate(m):
                    add(f"MCP: {name}", ok, detail)
            except RuntimeError as exc:
                add("Chạy thử MCP qua stdio", False, str(exc))
    return out


def run_doctor(probe_mcp: bool = False, as_json: bool = False) -> int:
    res = checks(probe_mcp)
    if as_json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        for c in res:
            mark = "[đạt] " if c["ok"] else ("[THIẾU]" if c["required"] else "[nên có]")
            print(f"{mark} {c['name']}: {c['detail']}")
        bad = [c for c in res if c["required"] and not c["ok"]]
        print("Môi trường sẵn sàng." if not bad else f"Còn {len(bad)} mục bắt buộc chưa đạt.")
    return 0 if all(c["ok"] for c in res if c["required"]) else 1


__all__ = ["checks", "run_doctor"]
