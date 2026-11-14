"""Bộ chuyển đổi (adapter) công cụ trợ lý cho các engine API trực tiếp và CLI.

Toàn bộ định nghĩa công cụ (`TOOL_SPECS`, `PROPOSE_SPEC`, `BASELINE_SPEC`), hộp công cụ (`ToolBox`)
và hàm điều phối (`dispatch_tool`) được lấy trực tiếp từ nguồn sự thật duy nhất `cadguard.agent.tools`.
"""
from __future__ import annotations

from ..agent import tools
from ..agent.tools import (
    BASELINE_SPEC,
    BASELINE_TOOL,
    PROPOSE_SPEC,
    TOOL_SPECS,
    ToolBox,
    ToolContext,
    dispatch_tool,
)

__all__ = [
    "BASELINE_SPEC",
    "BASELINE_TOOL",
    "PROPOSE_SPEC",
    "TOOL_SPECS",
    "ToolBox",
    "ToolContext",
    "dispatch_tool",
    "tools",
]
