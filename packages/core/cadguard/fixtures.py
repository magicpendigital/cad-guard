"""Sinh DXF tổng hợp (ezdxf) để test. KHÔNG dùng và KHÔNG chứa bản vẽ thật của khách.

Mỗi tệp "xấu" cố ý vi phạm một nhóm luật; `ok_sheet.dxf` không được vi phạm luật nào đã cài.
"""

from __future__ import annotations

from pathlib import Path

import ezdxf

GOOD_LAYERS = [
    "FN-PART-OUTL",
    "FN-PART-HIDD",
    "FN-ANNO-DIMS",
    "FN-ANNO-TEXT",
    "FN-SHT-FRAM",
    "FN-SHT-TTLB",
    "FN-VPRT",
]
TITLE_ATTRIBS = ["DWG_NO", "TITLE", "PROJECT", "SHEET", "SCALE", "DRAWN_BY", "CHECKED_BY", "DATE", "REV", "STATUS", "STD_VER"]
TITLE_VALUES = {
    "DWG_NO": "TEST-0001",
    "TITLE": "Tu bep mau",
    "PROJECT": "Du an mau",
    "SHEET": "1/1",
    "SCALE": "1:20",
    "DRAWN_BY": "A",
    "CHECKED_BY": "B",
    "DATE": "2026-11-03",
    "REV": "A",
    "STATUS": "WIP",
    "STD_VER": "furniture-v0",
}


def _base(units: int = 4):
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = units
    for name in GOOD_LAYERS:
        la = doc.layers.add(name)
        la.dxf.plot = 0 if name == "FN-VPRT" else 1
    doc.styles.add("STD", font="arial.ttf")
    doc.styles.add("TITLE", font="arial.ttf")
    tb = doc.blocks.new("FN_TTLB")
    for i, tag in enumerate(TITLE_ATTRIBS):
        tb.add_attdef(tag, (0, i * 4), dxfattribs={"height": 2.5, "layer": "FN-SHT-TTLB", "style": "STD"})
    tb.add_line((0, 0), (170, 0), dxfattribs={"layer": "FN-SHT-TTLB"})
    return doc


def _finish(doc, path: Path) -> None:
    names = doc.layouts.names()
    if "Layout1" in names and len(names) > 2:  # Model + Layout1 + các layout ta tạo
        doc.layouts.delete("Layout1")  # chỉ giữ layout của bản vẽ tổng hợp
    doc.saveas(path)


def _layout(doc, name="A3", scale_den=20, title_blocks: int = 1, values: dict | None = None):
    lo = doc.layouts.new(name)
    lo.page_setup(size=(420, 297), margins=(10, 10, 10, 20), units="mm")
    lo.add_viewport(center=(210, 148), size=(380, 250), view_center_point=(0, 0), view_height=250 * scale_den)
    lo.add_lwpolyline([(20, 10), (410, 10), (410, 287), (20, 287)], close=True, dxfattribs={"layer": "FN-SHT-FRAM", "lineweight": 70})
    for i in range(title_blocks):
        ref = lo.add_blockref("FN_TTLB", (230 - i * 5, 12), dxfattribs={"layer": "FN-SHT-TTLB"})
        ref.add_auto_attribs(values if values is not None else TITLE_VALUES)
    return lo


def _good_geometry(doc):
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (600, 0), (600, 720), (0, 720)], close=True, dxfattribs={"layer": "FN-PART-OUTL"})
    msp.add_line((0, 0), (600, 720), dxfattribs={"layer": "FN-PART-HIDD"})
    msp.add_lwpolyline([(-50, -50), (650, -50), (650, 770), (-50, 770)], close=True, dxfattribs={"layer": "FN-VPRT"})
    msp.add_text("Tu bep", dxfattribs={"layer": "FN-ANNO-TEXT", "style": "STD", "height": 50, "insert": (0, -100)})
    msp.add_linear_dim(base=(0, -200), p1=(0, 0), p2=(600, 0), dxfattribs={"layer": "FN-ANNO-DIMS"}).render()
    return msp


def make_ok_sheet(path: Path) -> None:
    doc = _base()
    _good_geometry(doc)
    _layout(doc)
    _finish(doc, path)


def make_bad_layers(path: Path) -> None:
    doc = _base()
    msp = _good_geometry(doc)
    doc.layers.add("Wall")  # LY-01 (tên sai) và LY-09 (rỗng)
    msp.add_line((0, 0), (10, 10), dxfattribs={"layer": "0"})  # LY-03
    msp.add_line((0, 5), (10, 15), dxfattribs={"layer": "LAYER_CHUA_KHAI_BAO"})  # LY-04
    doc.layers.get("FN-VPRT").dxf.plot = 1  # LY-08
    _layout(doc)
    _finish(doc, path)


def make_bad_titleblock(path: Path) -> None:
    doc = _base()
    _good_geometry(doc)
    _layout(doc, "A3", title_blocks=2)  # SH-04: hai khung tên
    partial = dict(TITLE_VALUES)
    partial["CHECKED_BY"] = ""
    partial["REV"] = ""
    _layout(doc, "A3-b", values=partial)  # SH-05: thiếu giá trị
    _finish(doc, path)


def make_bad_geometry(path: Path) -> None:
    doc = _base(units=0)  # DH-09: không đơn vị
    msp = _good_geometry(doc)
    msp.add_line((0, 0), (600, 0), dxfattribs={"layer": "FN-PART-OUTL"})  # DH-01
    msp.add_line((0, 0), (600, 0), dxfattribs={"layer": "FN-PART-OUTL"})
    msp.add_line((5, 5), (5, 5), dxfattribs={"layer": "FN-PART-OUTL"})  # DH-02
    msp.add_line((0, 0, 30), (10, 10, 30), dxfattribs={"layer": "FN-PART-OUTL"})  # DH-10
    _layout(doc)
    _finish(doc, path)


def make_bad_parts(path: Path) -> None:
    doc = _base()
    msp = _good_geometry(doc)
    pb = doc.blocks.new("FN_PART_TAG")
    pb.add_attdef("PART_ID", (0, 0), dxfattribs={"height": 2.5, "layer": "FN-PART-OUTL"})
    for _ in range(2):  # PR-02: trùng mã
        msp.add_blockref("FN_PART_TAG", (100, 100), dxfattribs={"layer": "FN-PART-OUTL"}).add_auto_attribs({"PART_ID": "P-001"})
    doc.styles.add("Arial", font="arial.ttf")
    msp.add_text("Sai kieu chu", dxfattribs={"layer": "FN-ANNO-TEXT", "style": "Arial", "height": 50, "insert": (0, -300)})  # TX-01
    dim = msp.add_linear_dim(base=(0, -400), p1=(0, 0), p2=(600, 0), text="999", dxfattribs={"layer": "FN-ANNO-DIMS"})  # TX-08
    dim.render()
    _layout(doc, "A3", scale_den=25)  # VW-01: 1:25
    _finish(doc, path)


def _room_doc():
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    doc.layers.add("FN-ROOM-WALL")
    mod = doc.blocks.new("FN_MOD_BASE")
    for tag in ("W", "D", "H", "MAT", "KIND"):
        mod.add_attdef(tag, (0, 0), dxfattribs={"height": 20})
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (4000, 0), (4000, 3000), (0, 3000)], close=True, dxfattribs={"layer": "FN-ROOM-WALL"})
    return doc, msp


def _cab(msp, at, rot, attribs):
    ref = msp.add_blockref("FN_MOD_BASE", at, dxfattribs={"rotation": rot})
    ref.add_auto_attribs(attribs)


def make_room_ok(path: Path) -> None:
    doc, msp = _room_doc()
    _cab(msp, (60, 60), 0, {"W": "1800", "D": "600", "H": "2200", "MAT": "MFC-OAK", "KIND": "wardrobe"})
    _cab(msp, (3940, 60), 90, {"W": "900", "D": "560", "H": "850", "MAT": "MFC-WHITE", "KIND": "base"})
    _cab(msp, (2000, 2940), 180, {"W": "1200", "D": "350", "H": "720", "MAT": "MFC-WHITE", "KIND": "wall"})
    doc.saveas(path)


def make_room_missing_height(path: Path) -> None:
    doc, msp = _room_doc()
    _cab(msp, (60, 60), 0, {"W": "1800", "D": "600", "H": "2200", "MAT": "MFC-OAK"})
    _cab(msp, (2000, 60), 0, {"W": "900", "D": "560", "MAT": "MFC-OAK"})  # thiếu H
    _cab(msp, (3000, 60), 0, {"W": "abc", "D": "560", "H": "850"})  # W sai
    doc.saveas(path)


def _rect(msp, x0, y0, x1, y1, layer):
    msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs={"layer": layer})


def make_cabinet_views(path: Path, with_side: bool = True, with_top: bool = True, top_w: float = 800.0, layers: bool = True) -> None:
    """Tủ 800x2000x500: 5 tấm ván (hông trái/phải, nóc, đáy, đợt giữa lùi 20mm). Ba hình chiếu đặt rời nhau."""
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    for lay in ("FN-VIEW-FRONT", "FN-VIEW-TOP", "FN-VIEW-SIDE"):
        doc.layers.add(lay)
    msp = doc.modelspace()
    F = "FN-VIEW-FRONT" if layers else "0"
    _rect(msp, 0, 0, 18, 2000, F)  # hông trái
    _rect(msp, 782, 0, 800, 2000, F)  # hông phải
    _rect(msp, 18, 1982, 782, 2000, F)  # nóc
    _rect(msp, 18, 0, 782, 18, F)  # đáy
    _rect(msp, 18, 1000, 782, 1018, F)  # đợt giữa
    if with_top:  # đặt phía trên mặt đứng
        T = "FN-VIEW-TOP" if layers else "0"
        oy = 3000
        _rect(msp, 0, oy, 18, oy + 500, T)
        _rect(msp, top_w - 18, oy, top_w, oy + 500, T)
        _rect(msp, 18, oy, top_w - 18, oy + 500, T)
    if with_side:  # đặt bên phải mặt đứng; ngang = chiều sâu từ mặt trước
        S = "FN-VIEW-SIDE" if layers else "0"
        ox = 1500
        _rect(msp, ox, 0, ox + 500, 2000, S)  # hông
        _rect(msp, ox, 1982, ox + 500, 2000, S)  # nóc
        _rect(msp, ox, 0, ox + 500, 18, S)  # đáy
        _rect(msp, ox + 20, 1000, ox + 480, 1018, S)  # đợt giữa lùi 20mm
    doc.saveas(path)


def make_cabinet_nolayers(path: Path) -> None:
    """Cùng bản vẽ nhưng mọi nét ở layer 0: code theo quy ước layer không nhận ra hình chiếu; LLM + cụm hình học thì có."""
    make_cabinet_views(path, layers=False)
    import ezdxf as _e

    doc = _e.readfile(path)
    msp = doc.modelspace()
    msp.add_text("MAT DUNG", dxfattribs={"layer": "0", "height": 40, "insert": (0, -150)})
    msp.add_text("MAT BEN", dxfattribs={"layer": "0", "height": 40, "insert": (1500, -150)})
    msp.add_text("MAT BANG", dxfattribs={"layer": "0", "height": 40, "insert": (0, 2900)})
    doc.saveas(path)


def make_cabinet_front_only(path: Path) -> None:
    make_cabinet_views(path, with_side=False, with_top=False)


def make_cabinet_conflict(path: Path) -> None:
    make_cabinet_views(path, top_w=810.0)


SCENE_FIXTURES = {
    "cabinet_views_ok.dxf": make_cabinet_views,
    "cabinet_nolayers.dxf": make_cabinet_nolayers,
    "cabinet_views_front_only.dxf": make_cabinet_front_only,
    "cabinet_views_conflict.dxf": make_cabinet_conflict,
    "room_ok.dxf": make_room_ok,
    "room_missing_height.dxf": make_room_missing_height,
}


ALL = {
    "ok_sheet.dxf": make_ok_sheet,
    "bad_layers.dxf": make_bad_layers,
    "bad_titleblock.dxf": make_bad_titleblock,
    "bad_geometry.dxf": make_bad_geometry,
    "bad_parts.dxf": make_bad_parts,
}


def make_all(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, fn in ALL.items():
        p = out_dir / name
        fn(p)
        paths.append(p)
    scene_dir = out_dir / "scene"
    scene_dir.mkdir(exist_ok=True)
    for name, fn in SCENE_FIXTURES.items():
        p = scene_dir / name
        fn(p)
        paths.append(p)
    return paths
