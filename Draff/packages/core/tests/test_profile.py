"""Hồ sơ số liệu: chỉ số tổng hợp, không rò tên; đường đọc theo dòng khớp đường ezdxf ở các số chính."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadguard.profile import profile_dxf, profile_dxf_stream

FIX = Path(__file__).resolve().parents[3] / "fixtures" / "synthetic"
FILES = sorted(FIX.glob("*.dxf"))


@pytest.mark.parametrize("f", FILES, ids=lambda p: p.name)
def test_stream_matches_full_on_core_counts(f: Path) -> None:
    a, b = profile_dxf(f), profile_dxf_stream(f)
    assert a["layers"]["total"] == b["layers"]["total"]
    assert a["layers"]["by_naming"] == b["layers"]["by_naming"]
    assert a["dim_styles"] == b["dim_styles"]
    assert a["blocks"] == b["blocks"]
    assert a["text"]["total"] == b["text"]["total"]
    assert a["dimensions"]["total"] == b["dimensions"]["total"]


@pytest.mark.parametrize("f", FILES, ids=lambda p: p.name)
def test_profile_has_no_names_or_paths(f: Path) -> None:
    """Hồ sơ không chứa tên layer/khối/tệp hay đường dẫn: chuỗi duy nhất cho phép là khoá cố định, tên phông và nhãn nhóm."""
    text = json.dumps(profile_dxf(f), ensure_ascii=False) + json.dumps(profile_dxf_stream(f), ensure_ascii=False)
    for secret in (f.name, str(f.parent), "FN-WALL", "FN_TTLB", "DWG_NO"):
        assert secret not in text
