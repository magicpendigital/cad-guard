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
