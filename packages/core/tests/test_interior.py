"""Nội thất đọc từ hình bỏ cánh, hai mặt đứng chép trùng tiêu đề, ký hiệu khấu/vòng chú thích trên layer nét khuất.
Ca thật 11/11/2026 (tủ áo + minibar) dựng lại bằng DXF tổng hợp của `synth` (kiểu trungtieude, noithat, khuat_chuthich)."""
from __future__ import annotations

import pytest

from cadguard import drafting, synth
from cadguard.dxf_reader import read_dxf
from cadguard.scene import interior as itr
from cadguard.scene.assemble import build_item_scene


@pytest.fixture(autouse=True)
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))


def _wardrobe(min_hang_drawers=True):
    for seed in range(1, 40):
        for s in synth.design_specs(9, seed=seed):
            uses = [m.get("use") for m in s["modules"]]
            hang = [m for m in s["modules"] if m.get("use") == "hang"]
            if s["kind"] == "wardrobe" and hang and "shelf" in uses and (hang[0]["inner_drawers"] or not min_hang_drawers):
                return s
    raise AssertionError("không có mẫu tủ áo phù hợp")


def _build(tmp_path, spec, styles):
    p = tmp_path / "x.dxf"
    ans = synth.draw(spec, ["chuan"] + styles, p)
    m = read_dxf(p)
    d = drafting.read(m, tmp_path)
    return build_item_scene(d, spec["id"], {}), ans, d


def test_duplicate_titles_pick_door_view_and_read_interior(tmp_path):
    spec = _wardrobe()
    sc, ans, d = _build(tmp_path, spec, ["trungtieude", "noithat"])
    assert any("hình CÓ CÁNH" in n for n in sc.notes)
    by_x = sorted(sc.modules, key=lambda m: m.x)
    want = [a for a in ans["modules"]]
    assert [len(m.fronts) for m in by_x] == [a["fronts"] for a in want]
    for m, a in zip(by_x, want):
        if "inner" in a:
            got = {k: sum(1 for q in m.inner if q["kind"] == k) for k in a["inner"]}
            assert got == a["inner"], (m.id, got, a["inner"])
            assert m.interior and m.interior != m.elevation


def test_marks_on_hidden_layer_are_not_fronts(tmp_path):
    spec = _wardrobe(min_hang_drawers=False)
    plain, ans, _d = _build(tmp_path, spec, [])
    (tmp_path / "x.dxf").unlink()
    marked, _ans, _d = _build(tmp_path, spec, ["khuat_chuthich"])
    assert [len(m.fronts) for m in marked.modules] == [len(m.fronts) for m in plain.modules]
    feats = [f for m in marked.modules for f in m.features]
    assert any(f["kind"] == "curve" and f["side"] == "r" for f in feats)
    call = next(f for f in feats if f["kind"] == "callout")
    assert "GHÉP MÒI" in call["text"] and call["meaning"] == "joint"


def test_levels_stack_double_lines_and_need_support():
    # ván 25 + đá 20 vẽ ba nét sát nhau = một tầng; đáy lòng ngăn kéo không tựa hông/vách = không phải đợt
    segs = [(0, 600, 825, "a"), (0, 600, 850, "b"), (0, 600, 870, "c"), (0, 590, 1750, "g1"), (0, 590, 1760, "g2"),
            (100, 400, 400, "t1"), (100, 400, 410, "t2")]
    vs = [(0, 2400, 0, "L"), (0, 2400, 600, "R"), (400, 520, 100, "s1"), (400, 520, 400, "s2")]
    lv = itr.levels(segs, 0, 600, 0, 2400, vs)
    assert [(L["z0"], L["z1"]) for L in lv] == [(825, 870), (1750, 1760)]


def test_curve_mark_shape():
    assert itr.is_curve_mark([(1485444, 2530537), (1485343, 2531020), (1485137, 2531097)])
    assert not itr.is_curve_mark([(1484844, 2529602), (1485426, 2529233), (1484844, 2528827)])  # ký hiệu mở cánh


def test_panels_cutlist_fixed_materials(tmp_path):
    from cadguard.construction import effective
    from cadguard.scene.panels import cutlist, panels_for

    spec = _wardrobe()
    sc, _ans, _d = _build(tmp_path, spec, ["noithat"])
    c = effective(None)["values"]
    ps = panels_for(sc, c)
    parts = {p.part for p in ps}
    assert {"rod", "drawer_in", "glass"} <= parts
    cl = cutlist(ps, c)
    mats = {r["part"]: r["material"] for r in cl["rows"]}
    assert mats["Đợt kính"] == "Kính" and mats["Thanh treo"].startswith("Phụ kiện")
    assert "Lòng hộc" not in mats  # chỉ để hình dung
    wood = sum(r["length"] * r["width"] * r["qty"] for r in cl["rows"] if r["board"]) / 1e6
    assert cl["area_m2"] == round(wood, 2)


def test_drafting_meanings_new_keywords():
    kws = drafting.effective(None)["keywords"]
    assert drafting.meaning_of("ĐÁ CĐT CẤP", kws) == "stone"
    assert drafting.meaning_of("THANH TREO INOX", kws) == "rod"
    assert drafting.meaning_of("VỊ TRÍ GHÉP MÒI 45 ĐỘ", kws) == "joint"
    d = type("D", (), {"keywords": kws})()
    assert itr.has_meaning(d, "GHI CHÚ KHẤU 2 CẠNH BÊN TỦ MINIBAR CHO THOÁT HƠI TỦ LẠNH", "curve")


def test_app_interior_key(tmp_path):
    from cadguard.app import scene_api

    spec = _wardrobe()
    p = tmp_path / "x.dxf"
    synth.draw(spec, ["chuan", "noithat"], p)
    m = read_dxf(p)
    v = scene_api.view(m, tmp_path, spec["id"])
    assert v["provenance"]["used"]["interior"] and any(x["inner_vi"] for x in v["modules"])
    # Hình khối: khối có nội thất là thùng rỗng + nội thất (mở cánh thấy bên trong), không còn khối đặc
    inner_ids = {x["id"] for x in v["modules"] if x["inner_vi"]}
    assert not any(b["k"] == "module" and b["n"] in inner_ids for b in v["boxes"])
    parts = {b["n"].split(":", 1)[1].rstrip("0123456789.v") for b in v["boxes"] if b["k"] == "module-part"}
    assert {"rod", "side_l", "shelf"} <= parts and "door" not in parts
    assert any(b["k"].startswith("front") for b in v["boxes"])
    other = v["provenance"]["used"]["interior"][0]
    r = scene_api.set_value(m, tmp_path, spec["id"], f"interior:{spec['id']}", other)
    assert r["provenance"]["interior_pick"] == other
    r = scene_api.set_value(m, tmp_path, spec["id"], f"interior:{spec['id']}", "reset")
    assert not r["provenance"]["interior_pick"]
