"""Hằng số và kiểm tham số dùng chung cho bộ đọc DXF — module NHẸ (không import ezdxf), để máy chủ MCP và CLI
khởi động nhanh; `dxf_stream`/`reader_select` dẫn lại các tên này nên mã cũ không đổi."""
from __future__ import annotations

import math

DEFAULT_MAX_ENTITY_RECORDS = 300_000  # ~1,2 KB/bản ghi -> khoảng 350 MB ở trần
DEFAULT_STREAM_THRESHOLD_MB = 50.0


def check_threshold(threshold_mb: float | None) -> None:
    """Ném ValueError (tiếng Việt) nếu ngưỡng là NaN hoặc vô cực; None và số hữu hạn đều hợp lệ."""
    if threshold_mb is None:
        return
    if isinstance(threshold_mb, bool) or not isinstance(threshold_mb, (int, float)):
        raise ValueError("Ngưỡng đọc theo dòng (MB) phải là một số.")
    if not math.isfinite(threshold_mb):
        raise ValueError(
            f"Ngưỡng đọc theo dòng (MB) phải là số hữu hạn, không nhận NaN hay vô cực (đang là {threshold_mb}). "
            "Dùng 0 để luôn đọc theo dòng, số âm để luôn dùng ezdxf."
        )
