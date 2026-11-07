"""Công cụ cad-guard cho engine API: lớp chuyển tiếp mỏng tới sổ khai báo `cadguard.agent.registry`.

Danh sách công cụ, mô tả, schema, kiểm tham số và xử lý lỗi lấy từ registry — CÙNG nguồn với máy chủ MCP
(`cadguard mcp`), nên hai đường không thể lệch nhau. Ẩn danh Bậc 1 mặc định, chỉ đọc; `propose_changeset` chỉ khi
`allow_propose`; KHÔNG BAO GIỜ có công cụ áp dụng (apply). Lỗi trả về là câu tiếng Việt chung.
"""
from __future__ import annotations

from pathlib import Path

from ..agent import registry, tools
from ..agent.anonymize import Anonymizer
from ..agent.workspace import PathDenied, Workspace
from ..dxf_stream import DEFAULT_MAX_ENTITY_RECORDS
from ..reader_select import DEFAULT_STREAM_THRESHOLD_MB
from ..standard import ProfileError, find_standards_dir, load_profile
from .base import EngineError

DEFAULT_STANDARD = registry.DEFAULT_STANDARD
PATH_DENIED_MSG = registry.PATH_DENIED_MSG
GENERIC_ERROR_MSG = registry.GENERIC_ERROR_MSG
BASELINE_TOOL = registry.BASELINE_TOOL


class ToolBox:
    """Bộ công cụ của một phiên engine API: giữ `ToolContext` (ẩn danh ổn định suốt phiên)."""

    def __init__(self, workspace: Path, *, standard: str | None = None, profile: Path | None = None,
                 allow_propose: bool = False, compare_without_profile: bool = False, anonymize: bool = True,
                 stream_threshold_mb: float | None = DEFAULT_STREAM_THRESHOLD_MB,
                 max_entity_records: int = DEFAULT_MAX_ENTITY_RECORDS):
        try:
            prof = load_profile(profile) if profile else None
        except ProfileError as exc:
            raise EngineError(f"Hồ sơ công ty không dùng được: {exc}", "profile") from None
        try:
            ws = Workspace(Path(workspace))
        except PathDenied:
            raise EngineError("Thư mục làm việc không tồn tại hoặc không phải thư mục.", "workspace") from None
        self.ctx = tools.ToolContext(ws, Anonymizer(enabled=anonymize), find_standards_dir(Path(__file__).resolve()),
                                     stream_threshold_mb=stream_threshold_mb, max_entity_records=max_entity_records,
                                     profile=prof)
        self.opts = registry.options_for(self.ctx, standard, allow_propose=allow_propose,
                                         compare_without_profile=compare_without_profile)
        self.standard = self.opts.default_standard
        self.allow_propose = self.opts.allow_propose
        self.compare = self.opts.compare_without_profile

    def specs(self) -> list[dict]:
        """[{name, description, schema, read_only}] — từ registry; không có apply."""
        return registry.specs(self.opts)

    def names(self) -> list[str]:
        return [s["name"] for s in self.specs()]

    def call(self, name: str, args) -> tuple[str, bool]:
        """Gọi công cụ; trả (nội dung JSON/chuỗi, is_error)."""
        res = registry.call(self.ctx, name, args, self.opts)
        return res.text(), not res.ok
