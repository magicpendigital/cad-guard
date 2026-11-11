"""Hồ sơ trình bày cg.drafting-profile/1: lưu/nạp, đề xuất code + AI qua harness, áp vào bộ đọc và bộ dựng 3D.
Chỉ DXF tổng hợp."""
from __future__ import annotations

import json

import ezdxf
import pytest

from cadguard import drafting, fixtures
from cadguard.dxf_reader import read_dxf
from cadguard.scene.assemble import build_item_scene


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))
    return tmp_path


def _kitchen_on_thay(path, filler=False):
    """Bếp tổng hợp nhưng thân tủ vẽ trên layer "THAY" (kiểu của một người vẽ khác); tuỳ chọn thêm tấm fix có ghi chú."""
    fixtures.make_company_kitchen(path)
    doc = ezdxf.readfile(path)
    doc.layers.add("THAY")
    for e in doc.modelspace():
        if e.dxf.layer == "SYN_Noithat":
            e.dxf.layer = "THAY"
    if filler:
        ex, fz = 22000.0, 2000.0  # gốc mặt đứng của bếp tổng hợp
        msp = doc.modelspace()
        msp.add_lwpolyline([(ex + 3100, fz), (ex + 3400, fz), (ex + 3400, fz + 850), (ex + 3100, fz + 850)], close=True,
                           dxfattribs={"layer": "THAY"})
        msp.add_text("TẤM FIX ĐO THỰC TẾ", height=40, dxfattribs={"layer": "SYN_Text", "insert": (ex + 3120, fz + 400)})
    doc.saveas(path)


def test_profile_defaults_save_remove_reset(cfg):
    proj = cfg / "p"
    proj.mkdir()
    e = drafting.effective(proj)
    assert not e["confirmed"] and any(k["text"] == "TẤM FIX" and k["origin"] == "default" for k in e["keywords"])
    with pytest.raises(ValueError):
        drafting.save(proj, "project", {"layer_roles": {"THAY": "bàn ghế"}})
    e = drafting.save(proj, "machine", {"layer_roles": {"THAY": "furniture"}, "keywords": [{"text": "tấm che", "meaning": "filler"}]})
    assert e["layer_roles"] == {"THAY": "furniture"} and e["origin"]["layer:THAY"] == "machine"
    assert any(k["text"] == "TẤM CHE" and k["origin"] == "machine" for k in e["keywords"])
    e = drafting.save(proj, "project", {"removed_keywords": ["ĐÈN"]})
    assert not any(k["text"] == "ĐÈN" for k in e["keywords"]) and (proj / ".cadguard" / "drafting-log.jsonl").is_file()
    e = drafting.save(proj, "machine", {"layer_roles": {"THAY": "reset"}})
    assert e["layer_roles"] == {}
    assert drafting.reset(proj, "project")["keywords"] and drafting.meaning_of("tấm fix đo kéo", e["keywords"]) == "filler"


def test_code_proposes_layer_role_then_build_matches(cfg, tmp_path):
    p = tmp_path / "k.dxf"
    _kitchen_on_thay(p)
    m = read_dxf(p)
    prof = drafting.effective(tmp_path)
    r = drafting.propose(drafting.read(m, tmp_path), prof)
    it = next(x for x in r["items"] if x["kind"] == "layer_role")
    assert it["target"] == "THAY" and it["value"] == "furniture" and it["origin"] == "code" and it["evidence"]
    drafting.save(tmp_path, "project", drafting.patch_for(it))
    d = drafting.read(m, tmp_path)
    assert d.roles["THAY"] == "furniture"
    sc = build_item_scene(d, "SYN.10")
    assert len(sc.modules) == 2 and not drafting.propose(d, drafting.effective(tmp_path))["items"]  # đã đúng: hết đề xuất


def test_filler_note_becomes_thin_panel(cfg, tmp_path):
    p = tmp_path / "k.dxf"
    _kitchen_on_thay(p, filler=True)
    m = read_dxf(p)
    drafting.save(tmp_path, "project", {"layer_roles": {"THAY": "furniture"}})
    sc = build_item_scene(drafting.read(m, tmp_path), "SYN.10")
    fill = [x for x in sc.modules if x.form == "filler"]
    assert len(fill) == 1 and round(fill[0].w) == 300 and any("tấm bù" in n for n in sc.notes)
    from cadguard.scene.panels import panels_for

    ps = [x for x in panels_for(sc, __import__("cadguard.construction", fromlist=["defaults"]).defaults()) if x.module == fill[0].id]
    assert [x.part for x in ps] == ["filler"]


def test_ai_proposals_need_real_evidence(cfg, tmp_path):
    p = tmp_path / "k.dxf"
    _kitchen_on_thay(p, filler=True)
    m = read_dxf(p)
    d = drafting.read(m, tmp_path)
    thay = next(h for h, e in d.entities.items() if e.layer == "THAY")
    note = next(h for h, e in d.entities.items() if e.type == "TEXT" and "FIX" in (e.text or ""))

    class Fake:
        def complete(self, system, messages):
            ctx = json.loads(messages[0]["content"])
            assert ctx["layers"] and "known_keywords" in ctx
            return json.dumps({"proposals": [
                {"kind": "layer_role", "target": "THAY", "value": "furniture", "evidence": [thay], "reason": "thân tủ"},
                {"kind": "layer_role", "target": "KHONG_CO", "value": "furniture", "evidence": [thay]},
                {"kind": "keyword", "target": "ĐO THỰC TẾ", "value": "filler", "evidence": [note], "reason": "ghi chú"},
                {"kind": "keyword", "target": "TỦ RƯỢU", "value": "appliance", "evidence": [note]},
                {"kind": "layer_role", "target": "THAY", "value": "furniture", "evidence": [note]}]})

    r = drafting.propose(d, drafting.effective(tmp_path), Fake())
    got = {(x["kind"], x["target"]) for x in r["items"]}
    assert ("layer_role", "THAY") in got and ("keyword", "ĐO THỰC TẾ") in got
    assert {x["why"] for x in r["rejected"]} >= {"layer không có trong bản vẽ", "chữ này không có trong ghi chú được dẫn"}


def test_app_drafting_api(cfg, tmp_path):
    from cadguard.app import AppConfig, CadGuardApp, drafting_api

    root = tmp_path / "ws"
    root.mkdir()
    _kitchen_on_thay(root / "bep.dxf")
    app = CadGuardApp(AppConfig(workspace=root), cli_detect=lambda n: {"installed": None})
    v = drafting_api.view(app.d(), "bep.dxf")
    assert any(x["layer"] == "THAY" for x in v["layers"]) and "filler" in v["meanings"]
    job = drafting_api.start(app.d(), "bep.dxf", False, None)
    assert job["state"] == "done" and job["items"]
    v2 = drafting_api.save(app.d(), {"scope": "project", "patch": drafting.patch_for(job["items"][0]), "file": "bep.dxf"})
    assert v2["confirmed"] and next(x for x in v2["layers"] if x["layer"] == "THAY")["origin"] == "project"
