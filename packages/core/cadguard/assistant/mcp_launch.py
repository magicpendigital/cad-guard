"""Khởi chạy máy chủ MCP của cad-guard cho engine CLI: gỡ biến xác thực khỏi môi trường CỦA CHÍNH máy chủ rồi chạy
`cadguard mcp <cờ…>`.

Máy chủ cad-guard không cần khoá hay token nào. CLI (Claude Code, Codex, agy) truyền cho máy chủ MCP môi trường của
nó cộng mục `env` trong tệp cấu hình, nên chỉ bỏ khỏi `env` là không đủ; gỡ ngay trong tiến trình thì chắc chắn.
Môi trường của chính CLI không bị đổi (cad-guard không thêm/bớt biến xác thực của CLI).

Chạy: `python -m cadguard.assistant.mcp_launch --workspace <thư mục> [cờ khác của `cadguard mcp`]`.
"""
from __future__ import annotations

import os
import sys

from .base import AUTH_ENV_VARS


def main(argv: list[str] | None = None) -> int:
    for var in AUTH_ENV_VARS:
        os.environ.pop(var, None)
    from ..cli import main as cli_main

    return cli_main(["mcp", *(sys.argv[1:] if argv is None else argv)])


if __name__ == "__main__":
    raise SystemExit(main())
