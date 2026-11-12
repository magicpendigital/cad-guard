"""P6 — thông số đọc nét là dữ liệu của hồ sơ trình bày (`scene/params.py`, `drafting.params`); đề xuất hồ sơ (code/AI)
được L4 chấm bằng cách dựng lại (`drafting.impact`). Kiểu vẽ mới "kieumoi" đọc đúng CHỈ bằng hồ sơ. DXF tổng hợp."""
from __future__ import annotations

import json

import pytest

from cadguard import bench3d, drafting, synth
from cadguard.dxf_reader import read_dxf
from cadguard.scene import params
from cadguard.scene.assemble import build_item_scene


@pytest.fixture(autouse=True)
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))


def test_params_default_scope_and_bounds():
    assert params.P("stack_gap") == 62.0
    with params.scope({"stack_gap": 90, "glass_max": 999, "nope": 1}):  # ngoài khoảng / không có: bỏ qua
        assert params.P("stack_gap") == 90.0 and params.P("glass_max") == 14.0
        with params.scope({"glass_max": 20}):
            assert params.P("glass_max") == 20.0 and params.P("stack_gap") == 90.0
    assert params.P("stack_gap") == 62.0


def test_profile_params_save_validate_reset(tmp_path):
    prof = drafting.save(tmp_path, "project", {"params": {"glass_max": "20"}})
    assert prof["params"] == {"glass_max": 20.0} and prof["origin"]["param:glass_max"] == "project"
    with pytest.raises(ValueError):
        drafting.save(tmp_path, "project", {"params": {"glass_max": 500}})
    with pytest.raises(ValueError):
        drafting.save(tmp_path, "project", {"params": {"khong_co": 1}})
    assert drafting.save(tmp_path, "project", {"params": {"glass_max": "reset"}})["params"] == {}


def _kieumoi(tmp_path):
    spec = next(s for s in synth.design_specs(9, seed=2) if s["kind"] == "wardrobe")
    p = tmp_path / "km.dxf"
    ans = synth.draw(spec, ["chuan", "kieumoi"], p)
    return spec, ans, read_dxf(p)


def _score(model, root, spec, ans):
    sc = build_item_scene(drafting.read(model, root), spec["id"], {})
    return bench3d.score(bench3d.snapshot(sc), ans["modules"])


def test_new_drafting_style_needs_only_a_profile(tmp_path):
    spec, ans, model = _kieumoi(tmp_path)
    assert _score(model, tmp_path, spec, ans)["score"] == 0.0  # hồ sơ mặc định: đọc sai
    drafting.save(tmp_path, "project", synth.PROFILE_KIEUMOI)  # chỉ dữ liệu, không sửa code
    r = _score(model, tmp_path, spec, ans)
    assert r["score"] == 1.0 and r["inner_answers"] and r["inner_ok"] == r["inner_answers"]


def test_code_proposal_is_scored_by_l4(tmp_path):
    _spec, _ans, model = _kieumoi(tmp_path)
    prof = drafting.effective(tmp_path)
    r = drafting.propose(drafting.read(model, tmp_path), prof, None, model=model, project_root=tmp_path)
    it = next(x for x in r["items"] if x["kind"] == "layer_role" and x["target"] == "KT-DOGO")
    assert it["value"] == "furniture" and it["impact"]["delta"] > 0 and it["impact"]["changed"] >= 1


def test_ai_param_and_keyword_proposals_go_through_harness_and_l4(tmp_path):
    spec, ans, model = _kieumoi(tmp_path)
    drafting.save(tmp_path, "project", {"layer_roles": {"KT-DOGO": "furniture"}})
    d = drafting.read(model, tmp_path)
    note = next(h for h, t, _g in drafting._texts(d) if "MICA" in t)

    class Fake:
        def complete(self, system, messages):
            assert "glass_max" in system and json.loads(messages[0]["content"])["params"]
            return json.dumps({"proposals": [
                {"kind": "keyword", "target": "MICA", "value": "glass", "evidence": [note]},
                {"kind": "param", "target": "glass_max", "value": 20, "evidence": [note]},
                {"kind": "param", "target": "glass_max", "value": 500, "evidence": [note]},  # ngoài khoảng
                {"kind": "param", "target": "stack_gap", "value": 80, "evidence": []}]})  # không bằng chứng

    r = drafting.propose(d, drafting.effective(tmp_path), Fake(), model=model, project_root=tmp_path)
    kinds = {(x["kind"], x["target"]) for x in r["items"]}
    assert kinds == {("keyword", "MICA"), ("param", "glass_max")} and len(r["rejected"]) == 2
    assert all(x["impact"] is not None for x in r["items"])
    for x in r["items"]:  # người dùng Đồng ý cả hai
        drafting.save(tmp_path, "project", drafting.patch_for(x))
    res = _score(model, tmp_path, spec, ans)
    assert res["score"] == 1.0 and res["inner_ok"] == res["inner_answers"]
