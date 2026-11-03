from collections import Counter

from cadguard.rules import REGISTRY


def test_catalog_is_complete_and_unique(standard):
    ids = [r.id for r in standard.rules]
    assert len(ids) == len(set(ids)) == 58
    groups = Counter(i.split("-")[0] for i in ids)
    assert groups == {"SH": 10, "LY": 9, "TX": 10, "VW": 6, "FN": 7, "DH": 10, "PR": 6}


def test_implemented_flag_matches_registry(standard):
    flagged = {r.id for r in standard.rules if r.implemented}
    assert flagged == set(REGISTRY), "mỗi luật `implemented: true` phải có hàm luật và ngược lại"


def test_realtime_never_on_for_unmeasured_rules(standard):
    assert not any(r.realtime_ok for r in standard.rules), "chưa đo độ chính xác (P1c) thì không bật thời gian thực"
