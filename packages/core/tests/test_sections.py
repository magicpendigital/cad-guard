"""P5 — đối chiếu nhiều hình (`scene/sections.py`): chiều sâu + cao độ tấm từ mặt cắt, mép ngăn kéo không phải tấm,
cột ngăn kéo hẹp, mâu thuẫn H03–H05. Chỉ DXF tổng hợp (`synth`)."""
from __future__ import annotations

import pytest

from cadguard import bench3d, drafting, synth
from cadguard.dxf_reader import read_dxf
from cadguard.scene.assemble import Front, Module2, Scene2, Src, build_item_scene
from cadguard.scene.consistency import check


@pytest.fixture(autouse=True)
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))


def _spec(kind):
    return next(s for s in synth.design_specs(9, seed=2) if s["kind"] == kind)


def _build(tmp_path, spec, styles):
    p = tmp_path / f"{spec['id']}.dxf"
    ans = synth.draw(spec, ["chuan", *styles], p)
    sc = build_item_scene(drafting.read(read_dxf(p), tmp_path), spec["id"], {})
    return sc, ans


@pytest.mark.parametrize("kind", ["wardrobe", "kitchen", "tv"])
def test_depth_only_in_section_is_read(tmp_path, kind):
    sc, ans = _build(tmp_path, _spec(kind), ["sauomatcat"])
    r = bench3d.score(bench3d.snapshot(sc), ans["modules"])
    assert r["dims_pct"]["d"] == 100 and r["score"] == 1.0
    floor = [m for m in sc.modules if m.z0 == 0 and m.form != "panel"]
    assert all(m.src["d"].kind in ("dimension", "geometry") for m in floor)
    assert any(g["via"] == "mark" and g["depth_src"] == "dimension" for m in floor for g in m.sections)
    assert not {g.id for g in sc.gaps} & {f"module:{m.id}" for m in floor}  # không còn ô "nhập chiều sâu"
    assert any("mặt cắt" in n for n in sc.notes)


def test_levels_from_section_when_no_interior_view(tmp_path):
    sc, ans = _build(tmp_path, _spec("wardrobe"), ["sauomatcat"])
    r = bench3d.score(bench3d.snapshot(sc), ans["modules"])
    assert r["inner_answers"] >= 1 and r["inner_ok"] == r["inner_answers"]
    assert any(q.get("from") == "section" for m in sc.modules for q in m.inner)


def test_section_with_interior_view_keeps_interior(tmp_path):
    sc, ans = _build(tmp_path, _spec("wardrobe"), ["sauomatcat", "noithat"])
    r = bench3d.score(bench3d.snapshot(sc), ans["modules"])
    assert r["score"] == 1.0 and r["inner_ok"] == r["inner_answers"]
    assert not any(q.get("from") == "section" for m in sc.modules for q in m.inner)


def test_drawer_seams_are_not_shelves_and_narrow_drawers(tmp_path):
    sc, ans = _build(tmp_path, _spec("wardrobe"), [])
    col = [m for m in sc.modules if sum(f.kind == "drawer" for f in m.fronts) >= 3]
    assert col, "cột ngăn kéo hẹp phải được nhận là ngăn kéo"
    for m in col:  # mép ngăn kéo xếp chồng (hình có cánh) không thành tấm ngang
        drawer_top = max(f.z1 for f in m.fronts if f.kind == "drawer")
        assert not any(q["kind"] == "shelf" and q["z1"] < drawer_top - 10 for q in m.inner)


def _unit(**kw) -> Module2:
    m = Module2(id="M1", kind="tall", form="cabinet", x=0, y=0, z0=0, w=1200, d=600, h=2400, elevation="E", interior="I",
                src={k: Src(kind="dimension") for k in ("w", "d", "h", "z0")})
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def _codes(m):
    return {x["code"] for x in check(Scene2(item="X", modules=[m]))["issues"]}


def test_section_conflicts():
    sec = {"view": "S", "label": "1-1", "via": "mark", "x": 300.0, "depth": 450.0, "depth_src": "dimension", "refs": ["d"],
           "levels": [{"z0": 1500.0, "z1": 1518.0, "refs": ["l"]}]}
    shelf = {"kind": "shelf", "x0": 18, "x1": 1182, "z0": 800, "z1": 818, "refs": ["s"]}
    assert {"H03", "H04"} <= _codes(_unit(sections=[sec], inner=[shelf]))
    ok = {**sec, "depth": 600.0, "levels": [{"z0": 805.0, "z1": 823.0, "refs": []}]}
    assert not {"H03", "H04"} & _codes(_unit(sections=[ok], inner=[shelf]))
    door = Front(id="M1.F1", kind="door", x0=18, x1=1182, z0=50, z1=2350, refs=["f"])
    part = {"kind": "partition", "x0": 591, "x1": 609, "z0": 100, "z1": 2300, "refs": ["p"]}
    assert "H05" in _codes(_unit(fronts=[door], inner=[part]))
