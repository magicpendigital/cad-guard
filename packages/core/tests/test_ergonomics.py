"""3D-4: công thái học đo trên cảnh cg.scene/2, harness nhận xét AI, công cụ trợ lý get_scene/measure/list_ergonomic_checks."""

import json

import pytest

from cadguard.agent.anonymize import Anonymizer
from cadguard.agent.tools import ToolContext
from cadguard.agent.workspace import Workspace
from cadguard.agent import registry
from cadguard.dxf_reader import read_dxf
from cadguard.ergonomics import check, load_ergonomics, measures, validate_review
from cadguard.scene.assemble import build_from_model
from cadguard.standard import find_standards_dir, load_standard


def _scene(synthetic, name="company_kitchen.dxf"):
    sc, _ = build_from_model(read_dxf(synthetic / "scene" / name), "SYN.10")
    return sc


def _with_ranges(**ranges):
    """Chuẩn THỬ (không phải ergonomics-v0): điền khoảng để kiểm logic đạt/không đạt. Số ở đây không phải khuyến nghị."""
    std = load_ergonomics()
    for r in std.rules:
        if r.id in ranges:
            r.params = {**r.params, "range": list(ranges[r.id])}
    return std


def test_standard_is_draft_with_sources_and_no_unsourced_ranges():
    std = load_standard("ergonomics-v0", find_standards_dir())
    assert std.version.endswith("draft") and all(r.id.startswith("ER-") for r in std.rules)
    for r in std.rules:
        assert r.source and "status" in r.params and "candidate_sources" in r.params
        assert r.params["range"] is None  # chưa duyệt: không điền khoảng từ trí nhớ
        assert not r.implemented and not r.realtime_ok  # không phải luật 2D


def test_measures_have_evidence_and_sources(synthetic):
    ms = {m.criterion: m for m in measures(_scene(synthetic))}
    assert ms["ER-01"].value == 850.0 and ms["ER-02"].value == 650.0 and ms["ER-03"].value == 600.0
    assert ms["ER-04"].value == 350.0 and ms["ER-05"].value == 2200.0
    assert ms["ER-01"].refs and "dimension" in ms["ER-01"].sources


@pytest.mark.parametrize("name,top,status", [("company_kitchen.dxf", 850.0, "đạt"), ("company_kitchen_low.dxf", 700.0, "không đạt")])
def test_worktop_height_answer_key(synthetic, name, top, status):
    sc = _scene(synthetic, name)
    r = check(sc, _with_ranges(**{"ER-01": (800, 950)}))
    er1 = next(x for x in r["results"] if x["id"] == "ER-01")
    assert er1["status"] == status
    assert next(m for m in r["measures"] if m["criterion"] == "ER-01")["value"] == top
    pending = check(sc)  # chuẩn thật: chưa có khoảng -> chỉ đo, không kết luận
    assert next(x for x in pending["results"] if x["id"] == "ER-01")["status"] == "chờ duyệt"


def test_door_swing_hits_opposite_wall(synthetic):
    ok = check(_scene(synthetic))
    assert next(x for x in ok["results"] if x["id"] == "ER-06")["status"] == "đạt"
    bad = check(_scene(synthetic, "company_kitchen_aisle.dxf"))
    er6 = next(x for x in bad["results"] if x["id"] == "ER-06")
    assert er6["status"] == "không đạt" and len(er6["failed"]) == 4
    m = next(x for x in bad["measures"] if x["id"] == er6["failed"][0])
    assert m["value"] == 146.0  # cánh 596 quét vào lối đi 450
    assert next(x for x in bad["measures"] if x["criterion"] == "ER-07")["value"] == 450.0


def test_review_harness_drops_items_without_evidence_or_wrong_numbers(synthetic):
    r = check(_scene(synthetic, "company_kitchen_aisle.dxf"))
    m1 = next(m for m in r["measures"] if m["criterion"] == "ER-01")
    m6 = next(m for m in r["measures"] if m["criterion"] == "ER-06")
    review = {"items": [
        {"criterion": "ER-06", "measure_ids": [m6["id"]], "refs": m6["refs"], "finding": "Cánh va tường đối diện 146 mm.",
         "impact": "Không mở hết cánh.", "suggestion": "Đổi sang cánh lùa hoặc nới lối đi.", "severity": "warn", "confidence": "high"},
        {"criterion": "ER-01", "measure_ids": [m1["id"]], "finding": "Mặt bàn cao 820 mm (mô phỏng).", "impact": "",
         "suggestion": "", "severity": "info", "confidence": "low"},  # số bịa
        {"criterion": "ER-02", "measure_ids": [], "finding": "Khoảng hở tủ trên 630 mm.", "severity": "info", "confidence": "low"},
        {"criterion": "ER-01", "measure_ids": [m1["id"]], "finding": "Cao 850 mm, không đạt chuẩn.", "severity": "warn",
         "confidence": "low"},  # kết luận khi chưa duyệt khoảng
        {"criterion": "ER-03", "measure_ids": [m6["id"]], "finding": "x", "severity": "info", "confidence": "low"},
    ], "questions": ["Người dùng chính cao bao nhiêu?"], "summary": "Điểm 96/100."}
    out = validate_review(json.dumps(review, ensure_ascii=False), r)
    assert [i["criterion"] for i in out["items"]] == ["ER-06"] and out["items"][0]["label"] == "AI nhận xét"
    assert len(out["rejected"]) == 4 and out["summary"] == "" and out["questions"]
    reasons = " ".join(x["reason"] for x in out["rejected"])
    assert "không khớp" in reasons and "số đo có thật" in reasons and "chưa có khoảng" in reasons


def _ctx(synthetic, anonymize: bool):
    return ToolContext(workspace=Workspace(synthetic), anonymizer=Anonymizer(enabled=anonymize))


def test_scene_tools_via_registry_anonymized_has_no_coordinates(synthetic):
    ctx = _ctx(synthetic, True)
    o = registry.options_for(ctx)
    r = registry.call(ctx, "get_scene", {"file": "scene/company_kitchen.dxf"}, o)
    data = json.loads(r.text())
    assert data["modules"] and all("x" not in m and "y" not in m for m in data["modules"])
    assert all("start" not in w for w in data["walls"]) and data["item"] != "SYN.10"
    assert "SYN.10" not in r.text() and "SYN_" not in r.text()
    item = data["item"]
    r2 = json.loads(registry.call(ctx, "measure", {"file": "scene/company_kitchen.dxf", "a": "M1", "b": "M2", "item": item}, o).text())
    assert r2["gap_z"] == 650.0 and r2["overlap"] is False
    r3 = json.loads(registry.call(ctx, "list_ergonomic_checks", {"file": "scene/company_kitchen.dxf", "item": item}, o).text())
    assert r3["schema"] == "cg.ergonomics/1" and r3["results"]


def test_scene_tools_internal_mode_includes_positions(synthetic):
    ctx = _ctx(synthetic, False)
    data = json.loads(registry.call(ctx, "get_scene", {"file": "scene/company_kitchen.dxf", "item": "SYN.10"},
                                    registry.options_for(ctx)).text())
    assert data["item"] == "SYN.10" and "x" in data["modules"][0]
