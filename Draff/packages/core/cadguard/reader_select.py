"""Chọn bộ đọc DXF (ezdxf nạp trọn hay theo dòng) theo kích thước tệp; dùng chung cho CLI `audit` và công cụ MCP.

Quy ước ngưỡng `threshold_mb` ở chế độ `auto`:
- `None` hoặc số âm: luôn ezdxf;
- `0`: luôn theo dòng (trừ DXF nhị phân);
- số dương: theo dòng khi tệp >= ngưỡng (MiB).
DXF nhị phân luôn quay về ezdxf ở chế độ `auto`, vì bộ đọc theo dòng chỉ hỗ trợ DXF ASCII.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Literal, NamedTuple

from .dxf_reader import read_dxf
from .dxf_stream import DEFAULT_MAX_ENTITY_RECORDS, is_binary_dxf, read_dxf_stream
from .model import DrawingModel

DEFAULT_STREAM_THRESHOLD_MB = 50.0

ReaderName = Literal["ezdxf", "stream"]


class ReaderChoice(NamedTuple):
    reader: ReaderName
    # forced: chọn tay; disabled: ngưỡng None/âm; small: dưới ngưỡng; binary: DXF nhị phân; large: >= ngưỡng
    reason: Literal["forced", "disabled", "small", "binary", "large"]
    size_mb: float


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


def choose_reader(path: str | Path, reader: str = "auto", threshold_mb: float | None = DEFAULT_STREAM_THRESHOLD_MB) -> ReaderChoice:
    """Quyết định bộ đọc cho một tệp, không đọc nội dung (trừ vài byte đầu để nhận DXF nhị phân).

    Ngưỡng NaN/vô cực bị từ chối bằng ValueError (xem `check_threshold`).
    """
    check_threshold(threshold_mb)
    p = Path(path)
    size_mb = p.stat().st_size / (1024 * 1024)
    if reader in ("ezdxf", "stream"):
        return ReaderChoice(reader, "forced", size_mb)
    if reader != "auto":
        raise ValueError(f"Bộ đọc không hợp lệ: {reader}")
    if threshold_mb is None or threshold_mb < 0:
        return ReaderChoice("ezdxf", "disabled", size_mb)
    if size_mb < threshold_mb:
        return ReaderChoice("ezdxf", "small", size_mb)
    if is_binary_dxf(p):
        return ReaderChoice("ezdxf", "binary", size_mb)
    return ReaderChoice("stream", "large", size_mb)


def read_with(path: str | Path, reader: ReaderName, max_entity_records: int = DEFAULT_MAX_ENTITY_RECORDS) -> DrawingModel:
    """Đọc bằng bộ đọc đã chọn. Đường stream có thể ném `DXFStreamError` (tiếng Việt)."""
    if reader == "stream":
        return read_dxf_stream(path, max_entity_records=max_entity_records)
    return read_dxf(path)


__all__ = ["DEFAULT_STREAM_THRESHOLD_MB", "ReaderChoice", "check_threshold", "choose_reader", "read_with"]
