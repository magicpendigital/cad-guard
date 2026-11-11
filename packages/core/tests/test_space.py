"""Dựng cả tầng cg.space/1 (5 bậc): tường, đặt hạng mục theo ký hiệu số, đồ rời, cửa, GLB. Chỉ DXF tổng hợp."""
from __future__ import annotations

import json
import struct

import pytest

from cadguard import fixtures
from cadguard.app import scene_api
from cadguard.dxf_reader import read_dxf
from cadguard.scene.gltf import _triangulate
from cadguard.scene.space import SCHEMA, build_space, register, render_space_glb, space_boxes
from cadguard.scene.views2d import read_drawing


@pytest.fixture
def floor(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))
    root = tmp_path / "ws"
    root.mkdir()
    fixtures.make_company_floor(root / "tang.dxf")
    return root, read_dxf(root / "tang.dxf")


def test_space_walls_items_loose_doors(floor):
    _root, m = floor
    sp = build_space(m, read_drawing(m))
    assert sp["schema"] == SCHEMA and sp["plan"]["title"].startswith("MẶT BẰNG BỐ TRÍ")
    assert sp["ceiling"] == {"value": 2700.0, "src": "dimension", "n": 1}  # cao trần từ kích thước sàn–trần của mặt đứng
    assert len(sp["walls"]) == 1 and len(sp["walls"][0]["base"]) == 10  # vành tường (hai đường bao lồng nhau) nối khe
    it = sp["items"][0]
    assert it["item"] == "SYN.10" and it["placed"] and it["rot"] == 0 and it["score"] >= 0.9
    lower = min(it["modules"], key=lambda x: x["z0"])
    xs = sorted({p[0] for p in lower["base"]})
    assert xs == [800.0, 3200.0]  # tủ dài 2400 đặt đúng vị trí trên mặt bằng tổng (gốc = góc hình)
    assert sp["loose"] and sp["loose"][0]["z1"] == 800.0 and sp["loose"][0]["src"] == "default"  # sofa: cao mặc định
    assert sp["doors"] and sp["doors"][0]["z1"] == 2200.0 and sp["door_h"]["src"] == "default"
    assert not sp["tasks"]
    kinds = {b["k"] for b in space_boxes(sp)}
    assert {"floor", "wall", "module", "loose", "door", "lintel"} <= kinds
    json.dumps(sp, ensure_ascii=False)


def test_legend_column_is_not_a_tag(tmp_path):
    def extra(doc, msp):
        fixtures._floor_extra(doc, msp)
        for i, t in enumerate(("10", "01", "10")):  # bảng chú thích: số xếp thẳng cột
            msp.add_text(t, height=150, dxfattribs={"layer": "SYN_Text", "insert": (8000, 4000 - 300 * i)})

    fixtures.make_company_kitchen(tmp_path / "f.dxf", extra=extra)
    m = read_dxf(tmp_path / "f.dxf")
    sp = build_space(m, read_drawing(m))
    assert [x["tag"] for x in sp["items"]] == [(1900.0, 2200.0)]


def test_register_finds_rotation_and_shift():
    from cadguard.scene.space import _grid, _samples

    seg = [((0, 0), (2400, 0)), ((2400, 0), (2400, 600)), ((2400, 600), (0, 600)), ((0, 600), (0, 0)), ((0, 300), (900, 300))]
    rot = lambda p: (-p[1] + 5000, p[0] + 1000)  # noqa: E731  # xoay 90° rồi dời
    dst_seg = [(rot(a), rot(b)) for a, b in seg]
    src_pts = sorted({p for s in seg for p in s})
    dst_pts = sorted({p for s in dst_seg for p in s})
    cov, k, t = register(src_pts, _samples(seg), dst_pts, _grid(_samples(dst_seg, 20.0)))
    assert k == 1 and t == (5000.0, 1000.0) and cov > 0.95


def test_glb_triangulates_concave_walls(floor):
    _root, m = floor
    sp = build_space(m, read_drawing(m))
    data = render_space_glb(sp)
    assert data[:4] == b"glTF"
    jlen = struct.unpack("<I", data[12:16])[0]
    doc = json.loads(data[20:20 + jlen])
    assert doc["asset"]["extras"]["schema"] == SCHEMA
    lshape = [(0, 0, 0), (2, 0, 0), (2, 1, 0), (1, 1, 0), (1, 2, 0), (0, 2, 0)]
    tri = _triangulate(lshape, (0, 0, 1))
    assert len(tri) == 12 and sorted(set(tri)) == list(range(6))  # 6 đỉnh lõm -> 4 tam giác


def test_space_api_rotation_override_and_scoped_supplement(floor):
    root, m = floor
    r = scene_api.space_view(m, root)
    assert r["boxes"] and r["items"][0]["sheet_names"]
    r2 = scene_api.space_set(m, root, "place:SYN.10", "90")
    assert r2["items"][0]["method"] in ("user", "user_tag") and r2["items"][0]["rot"] == 90
    r3 = scene_api.space_set(m, root, "place:SYN.10", "reset")
    assert r3["items"][0]["method"] == "match"
    r4 = scene_api.space_set(m, root, "space:door_h", "2400")
    assert r4["door_h"] == {"value": 2400.0, "src": "user"}
    with pytest.raises(scene_api.SceneApiError):
        scene_api.space_set(m, root, "place:SYN.10", "45")
    with pytest.raises(scene_api.SceneApiError):
        scene_api.space_set(m, root, "module:M1:w", "100")
    # số khối người dùng sửa lưu kèm mã hạng mục: M1 của hạng mục khác không bị ảnh hưởng
    v = scene_api.view(m, root, "SYN.10")
    mid = v["modules"][0]["id"]
    scene_api.set_value(m, root, "SYN.10", f"module:{mid}:w", "1234")
    raw = scene_api.read_supplement(root, m.file_hash)
    assert raw.get(f"SYN.10|module:{mid}:w") == "1234" and f"module:{mid}:w" not in raw
    assert scene_api.item_supp(raw, "SYN.99").get(f"module:{mid}:w") is None


def test_cli_space_writes_glb(floor, tmp_path, capsys):
    from cadguard.cli import main

    root, _m = floor
    out = tmp_path / "tang.glb"
    assert main(["space", str(root / "tang.dxf"), "--out", str(out)]) == 0
    assert out.read_bytes()[:4] == b"glTF" and "1/1 hạng mục đã đặt" in capsys.readouterr().out
