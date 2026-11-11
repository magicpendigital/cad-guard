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
    c = {**construction.defaults(), "base_top": "full"}  # thanh giằng tủ dưới kiểm riêng ở test_structure.py
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
    assert src["handles"] and pv["views"][src["elevation"]]["handles"]  # "Tới trong AutoCAD" cho khối và cho hình
    assert mod["type_vi"] in ("Tủ dưới", "Tủ treo", "Tủ cao", "Kệ mở", "Tấm ốp", "Kệ mở treo", "Tấm ốp treo")
    it = next(x for x in r["items"] if x["id"] == "SYN.10")
    assert it["sheet_names"]  # danh sách hạng mục ghi tờ
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


def test_fronts_hinge_side_pivot_and_drawer_slide():
    """Đóng/mở cánh trên màn 3D: bên bản lề, trục xoay, ngăn kéo trượt; tay nắm đi theo cánh."""
    from cadguard.scene.assemble import Front, Module2
    from cadguard.scene.panels import hinge_sides

    pair = [Front(id="A", kind="door", x0=0, x1=450, z0=0, z1=2000), Front(id="B", kind="door", x0=450, x1=900, z0=0, z1=2000)]
    assert hinge_sides(pair, 0, 900) == {"A": "l", "B": "r"}  # cặp hai cánh mở đối xứng
    assert hinge_sides([Front(id="R", kind="door", x0=500, x1=900, z0=0, z1=700)], 0, 900) == {"R": "r"}  # nửa phải
    assert hinge_sides([Front(id="W", kind="door", x0=0, x1=900, z0=0, z1=700)], 0, 900) == {"W": "l"}
    # tủ áo: 2 cánh trên, 2 cánh dưới (hai hàng), cột ngăn kéo không có bản lề
    rows = pair + [Front(id="C", kind="door", x0=0, x1=450, z0=2000, z1=2400), Front(id="D", kind="door", x0=450, x1=900, z0=2000, z1=2400),
                   Front(id="K", kind="drawer", x0=900, x1=1400, z0=0, z1=300)]
    assert hinge_sides(rows, 0, 1400) == {"A": "l", "B": "r", "C": "l", "D": "r"}
    m = Module2(id="M1", kind="tall", x=0, y=0, z0=0, w=1400, d=600, h=2400, fronts=rows)

    class Sc:
        modules = [m]

    c = construction.defaults()
    ps = panels_for(Sc, c)
    bx = boxes(ps, "panel")
    doors = {b["n"]: b for b in bx if b["k"] == "panel-door"}
    assert len(doors) == 4 and all(b["m"]["open"] == "swing" and b["m"]["angle"] == 90 for b in doors.values())
    left = next(b for b in doors.values() if b["m"]["hinge"] == "l")
    xs = [q[0] for q in left["b"]]
    assert left["m"]["pivot"][0] == pytest.approx(min(xs))  # trục ở mép bản lề
    right = next(b for b in doors.values() if b["m"]["hinge"] == "r")
    assert right["m"]["pivot"][0] == pytest.approx(max(q[0] for q in right["b"]))
    # khe giữa hai cánh cùng hàng = door_gap
    ab = sorted((b for b in doors.values() if b["z1"] < 2100), key=lambda b: b["b"][0][0])
    assert ab[1]["b"][0][0] - ab[0]["b"][1][0] == pytest.approx(float(c["door_gap"]))
    drw = next(b for b in bx if b["k"] == "panel-drawer")
    assert drw["m"] == {"open": "slide", "slide": pytest.approx(0.6 * 600)}
    handles = [b for b in bx if b["k"] == "panel-handle"]
    assert len(handles) == 5 and all(any(h["n"].startswith(d + ".") and h["m"] == doors[d]["m"] for d in doors) or h["m"]["open"] == "slide"
                                     for h in handles)
    assert any(b["k"] == "panel-tray" for b in bx)  # lòng ngăn kéo thấy khi trượt ra
    # tách lớp: trục dời theo cánh; xuyên thấu: bỏ cánh lẫn tay nắm
    ex = {b["n"]: b for b in boxes(ps, "explode")}
    for n, b in doors.items():
        dy = ex[n]["b"][0][1] - b["b"][0][1]
        assert ex[n]["m"]["pivot"][1] == pytest.approx(b["m"]["pivot"][1] + dy)
    assert not [b for b in boxes(ps, "xray") if "m" in b]
    # danh sách cắt không tính tay nắm/lòng ngăn kéo
    assert cutlist(ps, c)["panels"] == len(ps)


def test_block_view_fronts_have_gap_and_motion(cfg, kitchen):
    root, m = kitchen
    r = scene_api.view(m, root, "SYN.10")
    fr = [b for b in r["boxes"] if b["k"] == "front"]
    assert fr and all(b["m"]["open"] in ("swing", "slide") for b in fr)
    gap = float(construction.defaults()["door_gap"])
    row = sorted((b for b in fr if b["z0"] < 1000), key=lambda b: b["b"][0][0])
    assert row[1]["b"][0][0] - row[0]["b"][1][0] >= gap - 1e-6  # khe giữa hai cánh (cộng khe đã vẽ trên mặt đứng)
    assert [b["m"]["hinge"] for b in row][:2] == ["l", "r"]
    assert sum(1 for b in r["boxes"] if b["k"] == "front-handle") == len(fr)
    assert all("m" in b for b in r["panels"]["panel"] if b["k"] in ("panel-door", "panel-drawer", "panel-handle"))
