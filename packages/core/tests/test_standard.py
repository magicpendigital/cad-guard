import hashlib
import subprocess
from collections import Counter
from pathlib import Path

import pytest

from cadguard.rules import REGISTRY
from cadguard.standard import load_standard

REPO = Path(__file__).resolve().parents[3]
STANDARDS = ["furniture-v0", "design-hygiene-v0", "sheet-layout-v0"]
# sha256 của standards/furniture-v0.yaml trên `main` (xuống dòng chuẩn hoá về LF). Chuẩn đã công bố không sửa đè.
FURNITURE_V0_SHA256 = "19cc6ea101bc34a162507139f3ffe2e45a406fa08a9485437c43c61acca257d0"


def _lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def test_catalog_is_complete_and_unique(standard):
    ids = [r.id for r in standard.rules]
    assert len(ids) == len(set(ids)) == 58
    groups = Counter(i.split("-")[0] for i in ids)
    assert groups == {"SH": 10, "LY": 9, "TX": 10, "VW": 6, "FN": 7, "DH": 10, "PR": 6}


def test_implemented_flag_matches_registry(standard):
    flagged = {r.id for r in standard.rules if r.implemented}
    assert flagged <= set(REGISTRY), "mỗi luật `implemented: true` của furniture-v0 phải có hàm luật"
    assert flagged == {i for i in REGISTRY if not i.startswith(("VS-", "TP-"))}, "hàm luật ngoài VS-*/TP-* phải thuộc furniture-v0"


def test_registry_matches_all_standards():
    """Mọi luật `implemented: true` của mọi chuẩn có hàm đăng ký, và mọi hàm đăng ký thuộc đúng một chuẩn."""
    flagged: list[str] = []
    for name in STANDARDS:
        flagged += [r.id for r in load_standard(name, REPO / "standards").rules if r.implemented]
    assert len(flagged) == len(set(flagged)), "một mã luật không được đánh dấu cài ở hai chuẩn"
    assert set(flagged) == set(REGISTRY)


@pytest.mark.parametrize("name", STANDARDS)
def test_realtime_never_on_for_unmeasured_rules(name):
    std = load_standard(name, REPO / "standards")
    assert not any(r.realtime_ok for r in std.rules), "chưa đo độ chính xác (P1c) thì không bật thời gian thực"


@pytest.mark.parametrize("name", STANDARDS)
def test_rule_ids_unique(name):
    ids = [r.id for r in load_standard(name, REPO / "standards").rules]
    assert len(ids) == len(set(ids))


def test_hygiene_catalog(hygiene):
    implemented = [r for r in hygiene.rules if r.implemented]
    assert len(implemented) >= 6
    for r in hygiene.rules:
        assert r.id.startswith("VS-") and r.kind == "deterministic"
        assert r.severity in {"E", "W", "I"} and r.false_positive_risk in {"low", "medium", "high"}
        assert r.source and r.reads and r.params, f"{r.id}: thiếu nguồn, trường đọc hoặc tham số"
    assert set(hygiene.globals) == {"allowed_layer_patterns", "exempt_layer_patterns"}


def test_furniture_v0_unchanged():
    data = _lf((REPO / "standards" / "furniture-v0.yaml").read_bytes())
    assert hashlib.sha256(data).hexdigest() == FURNITURE_V0_SHA256, "không sửa đè furniture-v0; tạo phiên bản chuẩn mới"
    try:  # đối chiếu thêm với nhánh main nếu có git và nhánh main (không cần mạng)
        main = subprocess.run(["git", "show", "main:standards/furniture-v0.yaml"], cwd=REPO, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return
    if main.returncode == 0:
        assert _lf(main.stdout) == data
