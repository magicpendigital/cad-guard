"""Chế độ dữ liệu cho trợ lý: "nội bộ" (mặc định, quyết định 10/11/2026) hoặc "ẩn danh Bậc 1" (công tắc theo dự án).

CAD Guard là công cụ nội bộ công ty, chạy cục bộ: mặc định trợ lý thấy nội dung thật (tên layer, khối, chữ). Dự án có
NDA bật ẩn danh trong `<dự án>/.cadguard/project.yaml` (`anonymize: true`) hoặc bằng cờ `--anonymize`; khi đó mọi kết
quả công cụ trợ lý đi qua danh sách trắng như trước (`agent/tools.py`) và chức năng dịch bị khoá cho dự án đó.
Thứ tự ưu tiên: cờ dòng lệnh (`--anonymize` / `--no-anonymize`) > tệp dự án > mặc định (không ẩn danh).
"""
from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_FILE = Path(".cadguard") / "project.yaml"
DEFAULT_ANONYMIZE = False


def _read(ws: Path) -> dict:
    try:
        data = yaml.safe_load((Path(ws) / PROJECT_FILE).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def project_anonymize(ws: Path | None) -> bool | None:
    """Giá trị ghi trong tệp dự án; None nếu chưa đặt."""
    if ws is None:
        return None
    v = _read(ws).get("anonymize")
    return v if isinstance(v, bool) else None


def set_project_anonymize(ws: Path, value: bool) -> None:
    data = _read(ws)
    data["anonymize"] = bool(value)
    path = Path(ws) / PROJECT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=True), encoding="utf-8")


def effective(ws: Path | None, flag: bool | None = None) -> bool:
    """Ẩn danh hay không: `flag` (cờ dòng lệnh, None = không đặt) > tệp dự án > mặc định."""
    if flag is not None:
        return bool(flag)
    v = project_anonymize(ws)
    return DEFAULT_ANONYMIZE if v is None else v


def label(anonymize: bool) -> str:
    return "Ẩn danh Bậc 1 (dự án NDA)" if anonymize else "Nội bộ: trợ lý thấy nội dung bản vẽ"


__all__ = ["DEFAULT_ANONYMIZE", "effective", "label", "project_anonymize", "set_project_anonymize"]
