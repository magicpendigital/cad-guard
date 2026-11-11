"""Kết cấu thùng tủ: vách ngăn bắt buộc (bản lề, ray ngăn kéo, nhịp đợt), thanh giằng tủ dưới, kiểm cánh. Chỉ dữ liệu
tổng hợp."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from cadguard import construction, fixtures
from cadguard.dxf_reader import read_dxf
from cadguard.scene.assemble import build_item_scene
from cadguard.scene.panels import hinge_sides, panels_for
from cadguard.scene.structure import check, plan_module
from cadguard.scene.views2d import read_drawing

C = construction.defaults()


def _m(w, fronts, shelves=0, kind="base", h=850.0):
    fr = [SimpleNamespace(id=f"M1.F{i}", kind=k, x0=a, x1=b, z0=z0, z1=z1) for i, (k, a, b, z0, z1) in enumerate(fronts, 1)]
    return SimpleNamespace(id="M1", kind=kind, form="cabinet", x=0.0, y=0.0, z0=0.0, w=w, d=560.0, h=h, fronts=fr, shelves=shelves)


def test_four_doors_need_middle_partition():
    m = _m(2400, [("door", 600 * i, 600 * (i + 1), 100, 850) for i in range(4)])
    hs = hinge_sides(m.fronts, 0, 2400)
    parts = plan_module(m, hs, C)
    assert [round(p["x"]) for p in parts] == [1200] and parts[0]["code"] == "hinge"


def test_pair_of_doors_needs_no_partition_and_drawer_column_does():
    m = _m(1200, [("door", 0, 600, 0, 850), ("door", 600, 1200, 0, 850)])
    assert plan_module(m, hinge_sides(m.fronts, 0, 1200), C) == []
    m2 = _m(1200, [("door", 0, 600, 0, 850)] + [("drawer", 600, 1200, z, z + 280) for z in (0, 285, 570)])
    xs = [round(p["x"]) for p in plan_module(m2, hinge_sides(m2.fronts, 0, 1200), C)]
    assert xs == [600]


def test_shelf_span_adds_partition_and_can_be_turned_off():
    m = _m(1600, [("door", 0, 800, 0, 2000), ("door", 800, 1600, 0, 2000)], shelves=4, h=2000)
    parts = plan_module(m, hinge_sides(m.fronts, 0, 1600), C)
    assert [p["code"] for p in parts] == ["span"] and round(parts[0]["x"]) == 800
    assert plan_module(m, hinge_sides(m.fronts, 0, 1600), {**C, "partition_auto": "off"}) == []
    # mỗi khoang 800 vẫn > nhịp 700 nhưng không còn đường ráp cánh: cảnh báo, không đặt vách sau cánh
    codes = [x["code"] for x in check(SimpleNamespace(modules=[m]), C, lambda mm: hinge_sides(mm.fronts, mm.x, mm.x + mm.w))]
    assert codes.count("S05") == 1 and codes.count("S06") == 2


def test_check_wide_and_low_doors():
    m = _m(1400, [("door", 0, 700, 0, 500), ("door", 700, 1400, 0, 500)], kind="wall", h=500)
    sc = SimpleNamespace(modules=[m])
    codes = [x["code"] for x in check(sc, C, lambda mm: hinge_sides(mm.fronts, mm.x, mm.x + mm.w))]
    assert codes.count("S01") == 2  # rộng > 600 (Blum)


@pytest.fixture
def kitchen(tmp_path):
    p = tmp_path / "k.dxf"
    fixtures.make_company_kitchen(p)
    return build_item_scene(read_drawing(read_dxf(p)), "SYN.10")


def test_kitchen_panels_have_partitions_rails_and_cutlist(kitchen):
    from cadguard.scene.panels import cutlist

    ps = panels_for(kitchen, C)
    lower = min(kitchen.modules, key=lambda x: x.z0)
    upper = max(kitchen.modules, key=lambda x: x.z0)
    assert [p.part for p in ps if p.module == lower.id].count("rail") == 2 and not any(p.part == "top" and p.module == lower.id for p in ps)
    assert any(p.part == "top" for p in ps if p.module == upper.id)  # tủ treo vẫn có nóc liền
    for mod in (lower, upper):
        part = [p for p in ps if p.module == mod.id and p.part == "partition"]
        assert len(part) == 1 and abs((part[0].x0 + part[0].x1) / 2 - (mod.x + 1200)) < 1 and part[0].meta["auto"]
    rows = {r["part"] for r in cutlist(ps, C)["rows"]}
    assert {"Vách ngăn", "Thanh giằng"} <= rows


def test_scene_view_reports_structure(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))
    from cadguard.app import scene_api

    root = tmp_path / "ws"
    root.mkdir()
    fixtures.make_company_kitchen(root / "bep.dxf")
    r = scene_api.view(read_dxf(root / "bep.dxf"), root, "SYN.10")
    assert [x["code"] for x in r["structure"]].count("S03") == 2
