"""P3 + đối chiếu 2D↔3D: hồ sơ kết cấu xưởng, tấm ván, danh sách cắt, bản lề; nguồn từng khối, sửa số đo, chọn mặt đứng.
Chỉ DXF tổng hợp."""
from __future__ import annotations

import pytest

from cadguard import construction, fixtures
from cadguard.app import scene_api
from cadguard.dxf_reader import read_dxf
from cadguard.scene.assemble import build_item_scene
from cadguard.scene.panels import boxes, cutlist, cutlist_csv, hinges_for, panels_for
from cadguard.scene.views2d import read_drawing


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))
    return tmp_path


@pytest.fixture
def kitchen(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    fixtures.make_company_kitchen(root / "bep.dxf")
    return root, read_dxf(root / "bep.dxf")


def test_construction_defaults_save_validate_scope_and_reset(cfg, tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    e = construction.effective(proj)
    assert not e["confirmed"] and e["values"]["board_thickness"] == 17 and set(e["origin"].values()) == {"default"}
    with pytest.raises(ValueError, match="ngoài khoảng"):
        construction.save(proj, "machine", {"board_thickness": 500})
    with pytest.raises(ValueError, match="lựa chọn"):
        construction.save(proj, "machine", {"back_type": "keo"})
    construction.save(proj, "machine", {"board_thickness": 18, "back_type": "groove"})
    construction.save(proj, "project", {"board_thickness": 25})
    e = construction.effective(proj)
    assert e["confirmed"] and e["values"]["board_thickness"] == 25 and e["origin"]["board_thickness"] == "project"
    assert e["values"]["back_type"] == "groove" and e["origin"]["back_type"] == "machine"
    assert (proj / ".cadguard" / "construction-log.jsonl").is_file()
    e = construction.reset(proj, "project")
    assert e["values"]["board_thickness"] == 18


def test_panels_cutlist_hinges_and_view_modes(kitchen):
    _root, m = kitchen
    sc = build_item_scene(read_drawing(m), "SYN.10")
    c = construction.defaults()
    ps = panels_for(sc, c)
    parts = {p.part for p in ps}
    assert {"side_l", "side_r", "top", "bottom", "back", "door"} <= parts
    lower = min(sc.modules, key=lambda x: x.z0)
    sides = [p for p in ps if p.module == lower.id and p.part == "side_l"]
    assert sides and sides[0].dims[2] == 17 and sides[0].dims[0] == pytest.approx(lower.h)  # hông trùm: cao bằng tủ
    top = next(p for p in ps if p.module == lower.id and p.part == "top")
    assert top.x1 - top.x0 == pytest.approx(lower.w - 2 * 17)
    doors = [p for p in ps if p.part == "door"]
    assert all(hinges_for(p, c) >= 2 for p in doors)
    cl = cutlist(ps, c)
    assert cl["panels"] == len(ps) and cl["area_m2"] > 0 and cl["hinges"] >= 2 * len(doors)
    assert "Chi tiết" in cutlist_csv(cl).splitlines()[0]
    n_panel, n_xray = len(boxes(ps, "panel")), len(boxes(ps, "xray"))
    assert n_xray < n_panel  # xuyên thấu: bỏ cánh + hậu để thấy bên trong
    ex = boxes(ps, "explode")
    assert ex != boxes(ps, "panel") and len(ex) == n_panel
    c2 = {**c, "joint": "top_over", "back_type": "groove", "door_overlay": "inset"}
    ps2 = panels_for(sc, c2)
    top2 = next(p for p in ps2 if p.module == lower.id and p.part == "top")
    assert top2.x1 - top2.x0 == pytest.approx(lower.w)  # nóc trùm: rộng bằng tủ
    d2 = [p for p in ps2 if p.part == "door"]
    assert sum(p.x1 - p.x0 for p in d2) < sum(p.x1 - p.x0 for p in doors)  # cánh lọt nhỏ hơn cánh trùm


def test_cutlist_uses_confirmed_materials():
    from cadguard.scene.panels import Panel

    ps = [Panel("M1:side_l", "M1", "side_l", 0, 0, 0, 17, 560, 800, 1), Panel("M1:door1", "M1", "door", 0, -17, 0, 400, 0, 700, 4)]
    cl = cutlist(ps, construction.defaults(), [{"material": "MDF", "component": "thùng, hậu", "spec": "MDF 17MM chống ẩm"},
                                                  {"material": "Kính", "component": "cánh"}])
    mats = {r["part"]: r["material"] for r in cl["rows"]}
    assert mats == {"Hông trái": "MDF 17MM chống ẩm", "Cánh": "Kính"}


def test_scene_view_has_provenance_production_and_editable_dims(cfg, kitchen):
    root, m = kitchen
    r = scene_api.view(m, root, "SYN.10")
    pv = r["provenance"]
    assert pv["used"]["elevations"] and pv["used"]["plans"]
    mod = r["modules"][0]
    src = pv["modules"][mod["id"]]
    assert src["elevation"] in pv["views"] and src["plan"] in pv["views"] and len(src["ebox"]) == 4
    assert "Tờ" in pv["views"][src["elevation"]]["label"] or "tờ" in pv["views"][src["elevation"]]["label"]
    assert mod["w"]["kind"] in ("dimension", "geometry")
    assert r["panels"]["panel"] and r["cutlist"]["panels"] > 0 and r["construction"]["confirmed"] is False
    g = scene_api.source_geometry(m, root, "SYN.10", src["elevation"])
    assert g["items"] and len(g["box"]) == 4
    # sửa số đo: nguồn thành user, Bỏ sửa thì về số từ bản vẽ
    r2 = scene_api.set_value(m, root, "SYN.10", f"module:{mod['id']}:w", "1234")
    m2 = next(x for x in r2["modules"] if x["id"] == mod["id"])
    assert m2["w"]["value"] == 1234 and m2["w"]["kind"] == "user" and "w" in r2["provenance"]["modules"][mod["id"]]["user"]
    r3 = scene_api.set_value(m, root, "SYN.10", f"module:{mod['id']}:w", "reset")
    assert next(x for x in r3["modules"] if x["id"] == mod["id"])["w"]["value"] == mod["w"]["value"]
    with pytest.raises(scene_api.SceneApiError):
        scene_api.set_value(m, root, "SYN.10", f"module:{mod['id']}:w", "-5")
    with pytest.raises(scene_api.SceneApiError):
        scene_api.set_value(m, root, "SYN.10", f"main:SYN.10", "V:khong-co")


def test_production_gate_needs_confirmed_profile(cfg, kitchen):
    from cadguard.graph import build_graph

    _root, m = kitchen
    g0 = build_graph(m, profile={"construction": False})
    gate = next(x for x in g0["gates"] if x["id"] == "production")
    assert gate["done"] == 0 and any(t["action"] == {"id": "construction"} for t in gate["tasks"])
    g1 = build_graph(m, profile={"construction": True})
    assert next(x for x in g1["gates"] if x["id"] == "production")["done"] >= 1
