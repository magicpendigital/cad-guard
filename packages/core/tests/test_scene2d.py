"""Luồng 2 (3D từ bản vẽ 2D kiểu công ty): đọc hình chiếu, nhóm hạng mục, ký hiệu mặt cắt, cụm đồ, tường, đánh giá."""

from cadguard.dxf_reader import read_dxf
from cadguard.scene.feasibility import assess
from cadguard.scene.plan import components, read_walls
from cadguard.scene.views2d import (
    FURNITURE_ROLES_DEFAULT,
    frame_number,
    layer_roles,
    parse_title,
    read_drawing,
    role_from_name,
)


def _kitchen(synthetic, name="company_kitchen.dxf"):
    m = read_dxf(synthetic / "scene" / name)
    return m, read_drawing(m)


def test_role_from_name_vietnamese_conventions():
    assert role_from_name("00_Tuong") == "wall"
    assert role_from_name("00_Noithat") == "furniture"
    assert role_from_name("00_NETCAT") == "cut"
    assert role_from_name("00_Khuat") == "hidden"
    assert role_from_name("00_Dim") == "dim"
    assert role_from_name("00_Text - Ghichu") == "text"
    assert role_from_name("KYHIEU") == "symbol"
    assert role_from_name("A-Door+Window") == "door"
    assert role_from_name("ABC") is None


def test_layer_roles_override_and_type_statistics(synthetic):
    m, _ = _kitchen(synthetic)
    roles = layer_roles(m, {"SYN_Khuat": "furniture"})
    assert roles["SYN_Khuat"] == "furniture" and roles["SYN_Tuong"] == "wall"


def test_parse_title_kinds_labels_flags():
    assert parse_title("MẶT CẮT X2 TỦ BẾP") == ("section", "X2", "TỦ BẾP", [])
    assert parse_title("Mặt đứng bỏ cánh hướng A tủ bếp") == ("elevation", "A", "TỦ BẾP", ["no_doors"])
    assert parse_title("MẶT BẰNG") == ("plan", "", "", [])
    assert parse_title("GHI CHÚ") is None


def test_frame_number_groups_items():
    assert frame_number({"SO": "SYN.10. 02"}) == ("SYN.10", "02")
    assert frame_number({"SO": "d.01"}) == ("d", "01")
    assert frame_number({"SO": "NT-01"}) == ("NT", "01")
    assert frame_number({"TEN": "MẶT BẰNG TẦNG 7"}) is None


def test_views_groups_and_section_marks(synthetic):
    _, d = _kitchen(synthetic)
    kinds = sorted((v.group, v.kind, v.label) for v in d.views if v.handles)
    assert kinds == [("SYN.01", "plan", ""), ("SYN.10", "elevation", ""), ("SYN.10", "plan", ""), ("SYN.10", "section", "Y1")]
    assert set(d.groups) == {"SYN.01", "SYN.10"} and len(d.groups["SYN.10"]["sheets"]) == 2
    assert len(d.marks) == 1 and d.marks[0].label == "Y1"
    target = d.view(d.marks[0].target)
    assert target.kind == "section" and target.label == "Y1"


def test_floor_plan_walls_room_and_furniture_dimensioned(synthetic):
    _, d = _kitchen(synthetic)
    fp = next(v for v in d.views if v.group == "SYN.01" and v.kind == "plan")
    walls, rooms = read_walls(d, fp)
    assert len(rooms) == 1 and len(walls) == 4
    assert all(w.thickness == 200.0 and w.thickness_source == "geometry" for w in walls)
    r = rooms[0]
    assert (r.w.value, r.w.source, r.d.value, r.d.source) == (4000.0, "dimension", 3000.0, "dimension")
    comps = components(d, fp, FURNITURE_ROLES_DEFAULT)
    assert len(comps) == 1
    c = comps[0]
    assert (c.w.value, c.w.source, c.h.value, c.h.source) == (2400.0, "dimension", 600.0, "dimension")


def test_assess_reports_structure_only(synthetic):
    m, d = _kitchen(synthetic)
    r = assess(m, d)
    assert r["items"] == {"total": 2, "with_plan_and_elevation": 1, "with_section": 1, "plan_elevation_aligned_by_dimension": 1}
    assert r["section_marks"]["resolved"] == 1
    assert r["dimensions"]["attached_pct"] == 100.0
    assert r["elevations_with_room_height_dim"]["count"] == 1
    assert r["floor_plan"]["rooms"] == 1
    text = repr(r)
    assert "BẾP" not in text and "SYN_" not in text  # không chữ, không tên layer


# ---------------- 3D-2/3D-3: cảnh cg.scene/2 ----------------

import json as _json
import struct as _struct

from cadguard.cli import main as _main
from cadguard.scene.assemble import build_from_model, build_item_scene
from cadguard.scene.render2 import build_glb2, render_html2


def _glb_json(data: bytes) -> dict:
    assert data[:4] == b"glTF"
    n = _struct.unpack("<I", data[12:16])[0]
    return _json.loads(data[20:20 + n])


def test_item_scene_sizes_and_sources(synthetic):
    m, _ = _kitchen(synthetic)
    sc, _d = build_from_model(m, "SYN.10")
    assert [(lk.method) for lk in sc.links] == ["dimension"]
    assert sc.room.ceiling == 2700.0 and sc.room.src["ceiling"].kind == "dimension"
    base, upper = sorted(sc.modules, key=lambda x: x.z0)
    assert (base.kind, base.w, base.d, base.h, base.z0) == ("base", 2400.0, 600.0, 850.0, 0.0)
    assert {k: v.kind for k, v in base.src.items()} == {"w": "dimension", "h": "dimension", "d": "dimension", "z0": "geometry"}
    assert (upper.kind, upper.w, upper.d, upper.h, upper.z0) == ("wall", 2400.0, 350.0, 700.0, 1500.0)
    assert upper.src["d"].kind == "geometry"  # sâu tủ treo đo trên nét khuất, không có kích thước ghi
    assert len(base.fronts) == 4 and len(upper.fronts) == 4 and all(f.kind == "door" for f in base.fronts)
    assert upper.y + upper.d == base.y + base.d  # cùng sát tường sau
    assert not sc.gaps
    assert all(v.refs for x in sc.modules for k, v in x.src.items() if v.kind == "dimension")


def test_item_scene_low_worktop_fixture(synthetic):
    m, _ = _kitchen(synthetic, "company_kitchen_low.dxf")
    sc, _ = build_from_model(m, "SYN.10")
    assert min(sc.modules, key=lambda x: x.z0).h == 700.0


def test_missing_depth_is_gap_then_user_supplement(synthetic):
    m, _ = _kitchen(synthetic)
    sc, _ = build_from_model(m, "SYN.10", roles={"SYN_Khuat": "other"})  # không còn nét khuất -> không biết sâu tủ treo
    assert len(sc.modules) == 1 and len(sc.gaps) == 1
    g = sc.gaps[0]
    assert g.kind == "missing_value" and g.fields[0].key.endswith(":d")
    sc2, _ = build_from_model(m, "SYN.10", {g.fields[0].key: "320"}, roles={"SYN_Khuat": "other"})
    up = max(sc2.modules, key=lambda x: x.z0)
    assert up.d == 320.0 and up.src["d"].kind == "user" and not sc2.gaps


def test_unlinked_elevation_needs_user_link(synthetic):
    m, d = _kitchen(synthetic)
    plan = next(v for v in d.views if v.group == "SYN.10" and v.kind == "plan")
    elev = next(v for v in d.views if v.group == "SYN.10" and v.kind == "elevation")
    for h in list(plan.handles):  # bỏ kích thước ở mặt bằng: không còn căn được bằng kích thước chung
        if d.entities[h].type == "DIMENSION":
            plan.handles.remove(h)
    sc = build_item_scene(d, "SYN.10")
    assert not sc.modules and sc.gaps[0].id == f"link:{elev.id}" and sc.gaps[0].fields[0].options == [plan.id]
    sc2 = build_item_scene(d, "SYN.10", {f"link:{elev.id}": plan.id})
    assert sc2.links[0].method == "user" and len(sc2.modules) == 2


def test_preview_equals_export_same_scene_hash(synthetic, tmp_path):
    m, _ = _kitchen(synthetic)
    sc, _ = build_from_model(m, "SYN.10")
    assert sc.scene_hash and sc.scene_hash == sc.compute_hash()
    doc = _glb_json(build_glb2(sc))
    assert doc["asset"]["extras"]["scene_hash"] == sc.scene_hash
    page = render_html2(sc)
    assert sc.scene_hash in page and "kích thước" in page
    sc_again, _ = build_from_model(m, "SYN.10")
    assert sc_again.scene_hash == sc.scene_hash  # tất định


def test_cli_scene_item_and_assess(synthetic, tmp_path, capsys):
    src = synthetic / "scene" / "company_kitchen.dxf"
    out = tmp_path / "bep.glb"
    assert _main(["scene", str(src), "--item", "auto", "--out", str(out)]) == 0
    assert out.read_bytes()[:4] == b"glTF"
    capsys.readouterr()
    assert _main(["scene-assess", str(src), "--json"]) == 0
    assert _json.loads(capsys.readouterr().out)["items"]["plan_elevation_aligned_by_dimension"] == 1
    assert _main(["scene", str(src), "--item", "KHONG.CO", "--out", str(tmp_path / "x.glb")]) == 2
