"""L3 — mô hình tủ chuẩn `cg.cabinet/1` (`scene/cabinet.py`): cây khoang, chuyển hai chiều với `Scene2`, tấm ván đọc từ
mô hình. Chỉ DXF tổng hợp."""
from __future__ import annotations

import pytest

from cadguard import drafting, synth
from cadguard.construction import effective
from cadguard.dxf_reader import read_dxf
from cadguard.scene.assemble import build_item_scene
from cadguard.scene.cabinet import Cabinet, from_scene, summary, to_scene
from cadguard.scene.panels import cutlist, panels_for


@pytest.fixture(autouse=True)
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))


def _scene(tmp_path):
    spec = next(s for seed in range(1, 40) for s in synth.design_specs(9, seed=seed)
                if s["kind"] == "wardrobe" and any(m.get("use") == "hang" and m.get("inner_drawers") for m in s["modules"]))
    p = tmp_path / "x.dxf"
    synth.draw(spec, ["chuan", "noithat"], p)
    d = drafting.read(read_dxf(p), tmp_path)
    return build_item_scene(d, spec["id"], {}), spec


def test_roundtrip_lossless(tmp_path):
    sc, _spec = _scene(tmp_path)
    cab = from_scene(sc)
    assert isinstance(cab, Cabinet) and cab.model_dump(by_alias=True)["schema"] == "cg.cabinet/1"
    assert to_scene(cab).model_dump(by_alias=True) == sc.model_dump(by_alias=True)


def test_compartment_tree_of_hanging_unit(tmp_path):
    sc, spec = _scene(tmp_path)
    cab = from_scene(sc)
    hang_w = next(m["w"] for m in spec["modules"] if m.get("use") == "hang" and m.get("inner_drawers"))
    u = next(u for u in cab.units if abs(u.w - hang_w) < 1 and any(q["kind"] == "rod" for q in u.inner))
    root = u.root
    assert root.split == "h" and len(root.boards) == 2  # nóc hộc + đợt trên
    bottom, middle, _top = root.children
    assert bottom.split == "v" and [q["kind"] for q in bottom.boards] == ["partition"]
    assert [c.contents[0]["kind"] for c in bottom.children] == ["drawer", "drawer"]
    assert [q["kind"] for q in middle.contents] == ["rod"]
    assert len(u.compartments()) == 4
    tree = summary(cab)
    assert any(t["unit"] == u.id and t["compartments"] == 4 for t in tree)


def test_fronts_attach_to_covered_compartment(tmp_path):
    sc, _spec = _scene(tmp_path)
    for u in from_scene(sc).units:
        for n in u.root.walk():
            for f in n.fronts:  # cánh gắn ở khoang che ≥ 85 % mặt cánh
                area = (f["x1"] - f["x0"]) * (f["z1"] - f["z0"])
                ov = max(0, min(f["x1"], n.x1) - max(f["x0"], n.x0)) * max(0, min(f["z1"], n.z1) - max(f["z0"], n.z0))
                assert n is u.root or ov >= 0.85 * area


def test_panels_same_from_scene_or_cabinet(tmp_path):
    sc, _spec = _scene(tmp_path)
    c = effective(None)["values"]
    a, b = panels_for(sc, c), panels_for(from_scene(sc), c)
    assert [(p.id, p.part, p.x0, p.z0, p.x1, p.z1) for p in a] == [(p.id, p.part, p.x0, p.z0, p.x1, p.z1) for p in b]
    assert cutlist(a, c) == cutlist(b, c)
