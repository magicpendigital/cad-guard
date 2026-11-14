import json
import struct

from cadguard.cli import main
from cadguard.dxf_reader import read_dxf
from cadguard.scene import boxes, build_scene, render_html
from cadguard.scene.gltf import build_glb


def test_room_ok_builds_exact_dimensions(synthetic):
    sc = build_scene(read_dxf(synthetic / "scene" / "room_ok.dxf"))
    assert len(sc.walls) == 4 and len(sc.modules) == 3 and not sc.skipped
    wardrobe = next(m for m in sc.modules if m.kind == "wardrobe")
    assert (wardrobe.w, wardrobe.d, wardrobe.h) == (1800.0, 600.0, 2200.0)
    bx = {b.name: b for b in boxes(sc)}
    b = next(b for b in boxes(sc) if b.kind == "module" and b.z1 == 2200.0)
    xs = [p[0] for p in b.base]
    ys = [p[1] for p in b.base]
    assert round(max(xs) - min(xs), 3) == 1800.0 and round(max(ys) - min(ys), 3) == 600.0
    assert "floor" in bx


def test_rotation_swaps_footprint(synthetic):
    sc = build_scene(read_dxf(synthetic / "scene" / "room_ok.dxf"))
    base = next(b for b in boxes(sc) if b.kind == "module" and b.z1 == 850.0)  # xoay 90 độ
    xs = [p[0] for p in base.base]
    ys = [p[1] for p in base.base]
    assert round(max(xs) - min(xs), 3) == 560.0 and round(max(ys) - min(ys), 3) == 900.0


def test_missing_height_becomes_gap_not_guess(synthetic):
    sc = build_scene(read_dxf(synthetic / "scene" / "room_missing_height.dxf"))
    assert len(sc.modules) == 1 and not sc.skipped
    assert len(sc.gaps) == 2 and all(g.kind == "missing_value" and g.fields for g in sc.gaps)
    keys = {f.key.rsplit(":", 1)[1] for g in sc.gaps for f in g.fields}
    assert keys == {"h", "w"}


def test_supplement_fills_gaps_and_marks_user(synthetic):
    model = read_dxf(synthetic / "scene" / "room_missing_height.dxf")
    sc0 = build_scene(model)
    supp = {f.key: "850" if f.key.endswith(":h") else "900" for g in sc0.gaps for f in g.fields}
    sc = build_scene(model, supp)
    assert not sc.gaps and len(sc.modules) == 3
    assert sum(m.source == "user" for m in sc.modules) == 2


def test_supplement_wrong_hash_or_schema_ignored(synthetic):
    from cadguard.scene import load_supplement

    vals, note = load_supplement({"schema": "cg.supplement/1", "source_hash": "x", "values": {"a": 1}}, "y")
    assert vals == {} and note
    vals, note = load_supplement({"schema": "other"}, "y")
    assert vals == {} and note


def _panels(sc):
    return {p.id: p for p in sc.panels}


def test_views_ok_reconstructs_exact_panels(synthetic):
    sc = build_scene(read_dxf(synthetic / "scene" / "cabinet_views_ok.dxf"))
    assert not sc.gaps and len(sc.panels) == 5
    dims = sorted((round(p.x1 - p.x0, 1), round(p.y1 - p.y0, 1), round(p.z1 - p.z0, 1), round(p.y0, 1)) for p in sc.panels)
    assert (18.0, 500.0, 2000.0, 0.0) in dims  # hông
    assert (764.0, 460.0, 18.0, 20.0) in dims  # đợt giữa lùi 20 mm, sâu 460
    assert (764.0, 500.0, 18.0, 0.0) in dims  # nóc/đáy
    xs = [p.x1 for p in sc.panels]
    assert max(xs) == 800.0


def test_views_front_only_gaps_then_supplement(synthetic):
    model = read_dxf(synthetic / "scene" / "cabinet_views_front_only.dxf")
    sc = build_scene(model)
    assert not sc.panels and len(sc.gaps) == 5 and all(g.kind == "missing_value" for g in sc.gaps)
    supp = {g.fields[0].key: "500" for g in sc.gaps}
    sc2 = build_scene(model, supp)
    assert not sc2.gaps and len(sc2.panels) == 5 and all(p.source == "user" and p.y1 == 500.0 for p in sc2.panels)


def test_views_conflict_reported_not_fixable_by_input(synthetic):
    sc = build_scene(read_dxf(synthetic / "scene" / "cabinet_views_conflict.dxf"))
    conflicts = [g for g in sc.gaps if g.kind == "conflict"]
    assert len(conflicts) == 1 and conflicts[0].id == "conflict:width" and not conflicts[0].fields


def test_views_missing_front_view_gap(synthetic, tmp_path):
    import ezdxf

    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    doc.layers.add("FN-VIEW-SIDE")
    doc.modelspace().add_lwpolyline([(0, 0), (500, 0), (500, 2000), (0, 2000)], close=True, dxfattribs={"layer": "FN-VIEW-SIDE"})
    p = tmp_path / "s.dxf"
    doc.saveas(p)
    sc = build_scene(read_dxf(p))
    assert [g.kind for g in sc.gaps] == ["missing_view"] and not sc.panels


def test_ambiguous_depth_gives_choice(synthetic, tmp_path):
    import ezdxf

    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    for lay in ("FN-VIEW-FRONT", "FN-VIEW-SIDE"):
        doc.layers.add(lay)
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (800, 0), (800, 18), (0, 18)], close=True, dxfattribs={"layer": "FN-VIEW-FRONT"})
    for a, b in ((1500, 1900), (1500, 2000)):  # hai khoảng sâu cùng khoảng cao
        m.add_lwpolyline([(a, 0), (b, 0), (b, 18), (a, 18)], close=True, dxfattribs={"layer": "FN-VIEW-SIDE"})
    p = tmp_path / "a.dxf"
    doc.saveas(p)
    sc = build_scene(read_dxf(p))
    assert len(sc.gaps) == 1 and sc.gaps[0].kind == "ambiguous" and sc.gaps[0].fields[0].kind == "choice"
    key = sc.gaps[0].fields[0].key
    sc2 = build_scene(read_dxf(p), {key: sc.gaps[0].fields[0].options[0]})
    assert not sc2.gaps and len(sc2.panels) == 1


def test_form_has_inputs_no_paths(synthetic):
    from cadguard.scene import render_form

    sc = build_scene(read_dxf(synthetic / "scene" / "room_missing_height.dxf"))
    page = render_form(sc)
    assert page.count("data-key=") == 2 and "cg.supplement/1" in page and str(synthetic) not in page


def test_cli_gaps_form_supplement_round_trip(synthetic, tmp_path, capsys):
    import json

    src = synthetic / "scene" / "cabinet_views_front_only.dxf"
    out, form = tmp_path / "c.glb", tmp_path / "f.html"
    assert main(["scene", str(src), "--out", str(out), "--form", str(form)]) == 3
    assert form.exists() and "data-key=" in form.read_text(encoding="utf-8")
    h = read_dxf(src).file_hash
    gaps = build_scene(read_dxf(src)).gaps
    sup = tmp_path / "s.cgsup.json"
    sup.write_text(json.dumps({"schema": "cg.supplement/1", "source_hash": h, "values": {g.fields[0].key: "500" for g in gaps}}), encoding="utf-8")
    assert main(["scene", str(src), "--out", str(out), "--supplement", str(sup)]) == 0


def test_cli_with_extra_dxf_supplies_missing_views(synthetic, tmp_path):
    import ezdxf

    doc = ezdxf.readfile(synthetic / "scene" / "cabinet_views_ok.dxf")
    msp = doc.modelspace()
    for e in list(msp.query("LWPOLYLINE[layer=='FN-VIEW-FRONT']")):
        msp.delete_entity(e)
    extra = tmp_path / "views2.dxf"
    doc.saveas(extra)
    out = tmp_path / "w.json"
    code = main(["scene", str(synthetic / "scene" / "cabinet_views_front_only.dxf"), "--with", str(extra), "--out", str(out)])
    assert code == 0
    import json

    d = json.loads(out.read_text(encoding="utf-8"))
    assert len(d["panels"]) == 5 and not d["gaps"]
