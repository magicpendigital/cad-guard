"""L4 (P3) — bộ chấm nhất quán chế độ chỉ báo (`scene/consistency.py`): ca đúng không báo nhầm, ca sai báo đúng mã,
không đổi cảnh. Chỉ dữ liệu tổng hợp."""
from __future__ import annotations

import copy

import pytest

from cadguard import drafting, synth
from cadguard.dxf_reader import read_dxf
from cadguard.scene.assemble import Front, Module2, Scene2, Src, build_item_scene
from cadguard.scene.consistency import check


@pytest.fixture(autouse=True)
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))


def _wardrobe_scene(tmp_path, styles=("noithat",)):
    spec = next(s for seed in range(1, 40) for s in synth.design_specs(9, seed=seed)
                if s["kind"] == "wardrobe" and any(m.get("use") == "hang" and m.get("inner_drawers") for m in s["modules"]))
    p = tmp_path / "x.dxf"
    synth.draw(spec, ["chuan", *styles], p)
    return build_item_scene(drafting.read(read_dxf(p), tmp_path), spec["id"], {})


def _unit(**kw) -> Module2:
    m = Module2(id="M1", kind="tall", form="cabinet", x=0, y=0, z0=0, w=1200, d=600, h=2400, elevation="E", interior="I",
                src={k: Src(kind="dimension") for k in ("w", "d", "h", "z0")})
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def _codes(m: Module2) -> set[str]:
    return {x["code"] for x in check(Scene2(item="X", modules=[m]))["issues"] if x["level"] != "info"}


def test_good_drawing_has_no_conflict_and_is_not_mutated(tmp_path):
    sc = _wardrobe_scene(tmp_path, ("noithat", "trungtieude", "khuat_chuthich"))
    before = copy.deepcopy(sc.model_dump(by_alias=True))
    r = check(sc)
    assert r["counts"]["conflict"] == 0 and r["counts"]["warn"] == 0 and r["score"] == 1.0
    assert any(x["code"] == "I02" for x in r["issues"])
    assert sc.model_dump(by_alias=True) == before


def test_front_conflicts():
    f1 = Front(id="M1.F1", kind="door", x0=18, x1=600, z0=50, z1=2350, refs=["a"])
    f2 = Front(id="M1.F2", kind="door", x0=500, x1=1182, z0=50, z1=2350, refs=["b"])  # chồng 100 mm lên F1
    f3 = Front(id="M1.F3", kind="door", x0=1100, x1=1400, z0=50, z1=900, refs=["c"])  # lòi ra ngoài khối
    assert {"K01", "K02"} <= _codes(_unit(fronts=[f1, f2, f3]))


def test_inner_conflicts():
    shelf = {"kind": "shelf", "x0": 18, "x1": 1182, "z0": 1200, "z1": 1218, "refs": ["s"]}
    part = {"kind": "partition", "x0": 591, "x1": 609, "z0": 100, "z1": 2300, "refs": ["p"]}  # vách xuyên qua tấm
    app = {"kind": "appliance", "x0": 50, "x1": 550, "z0": 1000, "z1": 1500, "refs": ["t"]}  # tấm xuyên ô thiết bị
    out = {"kind": "drawer", "x0": 1100, "x1": 1500, "z0": 50, "z1": 300, "refs": ["d"]}  # ngoài khối
    rod = {"kind": "rod", "x0": 18, "x1": 1182, "z0": 1600, "z1": 1630, "refs": ["r"]}  # cách tấm 1218 chỉ ~400
    assert {"K03", "K04", "K05", "K06"} <= _codes(_unit(inner=[shelf, part, app, out, rod]))


def test_door_seam_without_board_behind():
    low = Front(id="M1.F1", kind="door", x0=18, x1=600, z0=50, z1=1500, refs=["a"])
    high = Front(id="M1.F2", kind="door", x0=18, x1=600, z0=1504, z1=2350, refs=["b"])
    shelf = {"kind": "shelf", "x0": 18, "x1": 1182, "z0": 800, "z1": 818, "refs": ["s"]}
    assert "H01" in _codes(_unit(fronts=[low, high], inner=[shelf]))
    fixed = {"kind": "shelf", "x0": 18, "x1": 1182, "z0": 1495, "z1": 1513, "refs": ["s2"]}
    assert "H01" not in _codes(_unit(fronts=[low, high], inner=[shelf, fixed]))


def test_default_depth_is_flagged():
    m = _unit()
    m.src["d"] = Src(kind="default")
    assert "H02" in _codes(m)


def test_api_returns_consistency(tmp_path):
    from cadguard.app import scene_api

    spec = next(s for s in synth.design_specs(3, seed=2) if s["kind"] == "wardrobe")
    p = tmp_path / "x.dxf"
    synth.draw(spec, ["chuan", "noithat"], p)
    v = scene_api.view(read_dxf(p), tmp_path, spec["id"])
    assert "score" in v["consistency"] and v["cabinet"]
