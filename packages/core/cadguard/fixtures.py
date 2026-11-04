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


def make_model_features(path: Path) -> None:
    """Synthetic drawing with model-space and block features."""
    doc = _base()
    msp = _good_geometry(doc)
    doc.layers.add("XR1|WALL")
    doc.layers.add("XR2$0$DOOR")
    doc.styles.add("LEGACY_SHX", font="simplex.shx")
    doc.styles.add("LEGACY_BIG", font="romans.shx")
    a = doc.blocks.new("FEATURE_A")
    b = doc.blocks.new("FEATURE_B")
    c = doc.blocks.new("FEATURE_C")
    a.add_blockref("FEATURE_B", (0, 0), dxfattribs={"layer": "XR1|WALL"})
    b.add_blockref("FEATURE_C", (0, 0), dxfattribs={"layer": "XR2$0$DOOR"})
    c.add_line((0, 0), (10, 10), dxfattribs={"layer": "XR1|WALL"})
    doc.blocks.new_anonymous_block("U").add_line((0, 0), (1, 1), dxfattribs={"layer": "XR2$0$DOOR"})
    msp.add_blockref("FEATURE_A", (0, 0), dxfattribs={"layer": "FN-PART-OUTL"})
    msp.add_line((20, 20), (30, 30), dxfattribs={"layer": "FN-PART-OUTL", "color": 1, "lineweight": 50})
    wipeout = msp.add_wipeout([(0, 0), (5, 0), (5, 5), (0, 5)])
    wipeout.dxf.layer = "FN-PART-OUTL"
    image_def = doc.add_image_def(filename="synthetic.png", size_in_pixel=(10, 10))
    msp.add_image(image_def, insert=(40, 40), size_in_units=(10, 10), dxfattribs={"layer": "FN-PART-OUTL"})
    msp.add_linear_dim(base=(0, -400), p1=(0, 0), p2=(600, 0), text="999", dxfattribs={"layer": "FN-ANNO-DIMS"}).render()
    _layout(doc)
    _finish(doc, path)


ALL = {
    "ok_sheet.dxf": make_ok_sheet,
    "model_features.dxf": make_model_features,
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
    return paths
