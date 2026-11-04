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


HYG_LAYERS = ["SYN-TUONG", "SYN-NOI-THAT", "SYN-CHU", "SYN-KICH-THUOC"]


def _hygiene_base():
    """Bản vẽ khâu thiết kế tổng hợp, KHÔNG dùng setup=True (để số kiểu chữ/kích thước nhỏ)."""
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    for name in HYG_LAYERS:
        doc.layers.add(name)
    doc.styles.add("SYN-CHU", font="arial.ttf")
    blk = doc.blocks.new("SYN-GHE")  # nội dung khối trên layer 0: đúng thông lệ, VS-03 không tính
    blk.add_lwpolyline([(0, 0), (450, 0), (450, 450), (0, 450)], close=True, dxfattribs={"layer": "0"})
    blk.add_text("Ghế đơn", dxfattribs={"layer": "0", "style": "SYN-CHU", "height": 50})
    msp = doc.modelspace()
    for i in range(6):
        msp.add_line((0, i * 1000), (6000, i * 1000), dxfattribs={"layer": "SYN-TUONG"})
    for i in range(3):
        msp.add_blockref("SYN-GHE", (i * 600, 200), dxfattribs={"layer": "SYN-NOI-THAT"})
    msp.add_text("Tủ bếp trên", dxfattribs={"layer": "SYN-CHU", "style": "SYN-CHU", "height": 100, "insert": (0, -300)})
    msp.add_mtext("Ghi chú: dán cạnh nhựa 1 ly", dxfattribs={"layer": "SYN-CHU", "style": "SYN-CHU", "char_height": 100,
                                                             "insert": (0, -600)})
    msp.add_linear_dim(base=(0, -900), p1=(0, 0), p2=(6000, 0), dimstyle="Standard",
                       dxfattribs={"layer": "SYN-KICH-THUOC"}).render()
    return doc, msp


def make_hygiene_ok(path: Path) -> None:
    """Sạch với design-hygiene-v0: không VS-* nào."""
    doc, _msp = _hygiene_base()
    doc.saveas(path)


def make_hygiene_bad(path: Path) -> None:
    """Gây đúng VS-01..VS-07 của design-hygiene-v0 (ngưỡng mặc định)."""
    doc, msp = _hygiene_base()
    ezdxf_setup = ezdxf.new("R2018", setup=True)  # VS-02: chép hàng loạt kiểu chữ/kích thước của bộ cài đặt ezdxf
    for st in ezdxf_setup.styles:
        if st.dxf.name not in doc.styles:
            doc.styles.add(st.dxf.name, font=st.dxf.font)
    for ds in ezdxf_setup.dimstyles:
        if ds.dxf.name not in doc.dimstyles:
            doc.dimstyles.new(ds.dxf.name)
    doc.layers.add("SYNX1|SYN-TUONG")  # VS-01: layer dư của xref
    doc.layers.add("SYNX2$0$SYN-CUA")
    for i in range(3):  # VS-03: 3/… đối tượng trực tiếp trên layer 0
        msp.add_circle((i * 100, 5000), 40, dxfattribs={"layer": "0"})
    for i in range(4):  # VS-04: ghi đè màu và độ dày nét
        msp.add_line((0, 7000 + i * 50), (900, 7000 + i * 50), dxfattribs={"layer": "SYN-TUONG", "color": 1, "lineweight": 50})
    image_def = doc.add_image_def(filename="syn_anh.png", size_in_pixel=(10, 10))
    for i in range(11):  # VS-05: 11 IMAGE > 10
        msp.add_image(image_def, insert=(i * 20, 8000), size_in_units=(10, 10), dxfattribs={"layer": "SYN-NOI-THAT"})
    msp.add_linear_dim(base=(0, -1200), p1=(0, 0), p2=(6000, 0), text="5999", dimstyle="Standard",
                       dxfattribs={"layer": "SYN-KICH-THUOC"}).render()  # VS-06
    doc.styles.add("SYN-VN-SHX", font="syn_vn.shx")  # VS-07: chữ có dấu dùng phông SHX
    msp.add_text("Cửa trượt kính", dxfattribs={"layer": "SYN-CHU", "style": "SYN-VN-SHX", "height": 100, "insert": (0, -1500)})
    doc.saveas(path)


ALL = {
    "ok_sheet.dxf": make_ok_sheet,
    "model_features.dxf": make_model_features,
    "bad_layers.dxf": make_bad_layers,
    "bad_titleblock.dxf": make_bad_titleblock,
    "bad_geometry.dxf": make_bad_geometry,
    "bad_parts.dxf": make_bad_parts,
    "hygiene_ok.dxf": make_hygiene_ok,
    "hygiene_bad.dxf": make_hygiene_bad,
}


def make_all(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, fn in ALL.items():
        p = out_dir / name
        fn(p)
        paths.append(p)
    return paths


# ---- Tệp rất lớn (đo hiệu năng bộ đọc theo dòng). Không nằm trong ALL; không commit tệp sinh ra.

SYN_TEXTS = [
    "Tủ bếp trên SYN",
    "Kệ tivi gỗ sồi SYN",
    "Cửa trượt kính cường lực SYN",
    "Bàn làm việc chữ L SYN",
    "Ghi chú: dán cạnh nhựa 1 ly SYN",
    "Vách thạch cao khung xương SYN",
    "Đèn hắt trần thạch cao SYN",
    "Tủ quần áo cánh mở SYN",
]
SYN_BLOCKS = 40


def _fmt(x: float) -> str:
    return f"{x:.4f}"


class _LargeWriter:
    """Ghi thẳng văn bản DXF cho đối tượng tổng hợp (nhanh hơn dựng hàng trăm nghìn đối tượng ezdxf)."""

    def __init__(self, rng) -> None:
        self.rng = rng
        self.handle = 0x10000000
        self.counts = {"blocks": 0, "model": 0}

    def _h(self) -> str:
        self.handle += 1
        return f"{self.handle:X}"

    def _common(self, kind: str, owner: str, layer: str, extra: str = "") -> list[str]:
        return ["  0", kind, "  5", self._h(), "330", owner, "100", "AcDbEntity", "  8", layer] + ([extra] if extra else [])

    def line(self, owner: str, layer: str, z: float = 0.0) -> list[str]:
        r = self.rng
        x, y = r.uniform(-5000, 5000), r.uniform(-5000, 5000)
        out = self._common("LINE", owner, layer)
        if r.random() < 0.05:
            out += [" 62", str(r.randint(1, 7))]
        out += ["100", "AcDbLine", " 10", _fmt(x), " 20", _fmt(y), " 30", _fmt(z),
                " 11", _fmt(x + r.uniform(1, 900)), " 21", _fmt(y + r.uniform(-400, 400)), " 31", _fmt(z)]
        return out

    def arc(self, owner: str, layer: str) -> list[str]:
        r = self.rng
        return self._common("ARC", owner, layer) + [
            "100", "AcDbCircle", " 10", _fmt(r.uniform(-5000, 5000)), " 20", _fmt(r.uniform(-5000, 5000)), " 30", "0.0",
            " 40", _fmt(r.uniform(5, 300)), "100", "AcDbArc", " 50", _fmt(r.uniform(0, 180)), " 51", _fmt(r.uniform(180, 360))]

    def text(self, owner: str, layer: str, style: str) -> list[str]:
        r = self.rng
        return self._common("TEXT", owner, layer) + [
            "100", "AcDbText", " 10", _fmt(r.uniform(-5000, 5000)), " 20", _fmt(r.uniform(-5000, 5000)), " 30", "0.0",
            " 40", _fmt(r.choice([2.5, 3.5, 50, 100, 250])), "  1", f"{r.choice(SYN_TEXTS)} {r.randint(1, 99999)}",
            "  7", style, "100", "AcDbText"]

    def lwpolyline(self, owner: str, layer: str) -> list[str]:
        r = self.rng
        x, y, w, h = r.uniform(-5000, 5000), r.uniform(-5000, 5000), r.uniform(10, 2400), r.uniform(10, 900)
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        out = self._common("LWPOLYLINE", owner, layer) + ["100", "AcDbPolyline", " 90", "4", " 70", "1", " 43", "0.0"]
        for px, py in pts:
            out += [" 10", _fmt(px), " 20", _fmt(py)]
        return out

    def insert(self, owner: str, layer: str, block: str, attribs: dict[str, str] | None = None) -> list[str]:
        r = self.rng
        ins = self._h()
        out = ["  0", "INSERT", "  5", ins, "330", owner, "100", "AcDbEntity", "  8", layer, "100", "AcDbBlockReference"]
        if attribs:
            out += [" 66", "1"]
        x, y = r.uniform(-5000, 5000), r.uniform(-5000, 5000)
        out += ["  2", block, " 10", _fmt(x), " 20", _fmt(y), " 30", "0.0"]
        for tag, value in (attribs or {}).items():
            out += ["  0", "ATTRIB", "  5", self._h(), "330", ins, "100", "AcDbEntity", "  8", layer,
                    "100", "AcDbText", " 10", _fmt(x), " 20", _fmt(y), " 30", "0.0", " 40", "2.5", "  1", value,
                    "100", "AcDbAttribute", "280", "0", "  2", tag, " 70", "0"]
        if attribs:
            out += ["  0", "SEQEND", "  5", self._h(), "330", ins, "100", "AcDbEntity", "  8", layer]
        return out

    def dimension(self, owner: str, layer: str, geometry_block: str) -> list[str]:
        r = self.rng
        x, y, d = r.uniform(-5000, 5000), r.uniform(-5000, 5000), r.uniform(100, 2400)
        text = f"{round(d)}" if r.random() < 0.03 else ""  # vài kích thước bị ghi đè chữ
        return self._common("DIMENSION", owner, layer) + [
            "100", "AcDbDimension", "280", "0", "  2", geometry_block, " 10", _fmt(x + d), " 20", _fmt(y - 200), " 30", "0.0",
            " 11", _fmt(x + d / 2), " 21", _fmt(y - 200), " 31", "0.0", " 70", "32", "  1", text, "  3", "Standard",
            "100", "AcDbAlignedDimension", " 13", _fmt(x), " 23", _fmt(y), " 33", "0.0",
            " 14", _fmt(x + d), " 24", _fmt(y), " 34", "0.0", "100", "AcDbRotatedDimension", " 50", "0.0"]

    def block_content(self, owner: str, layers: list[str], style: str) -> list[str]:
        r = self.rng
        k = r.random()
        layer = r.choice(layers)
        self.counts["blocks"] += 1
        if k < 0.55:
            return self.line(owner, layer)
        if k < 0.70:
            return self.arc(owner, layer)
        if k < 0.85:
            return self.lwpolyline(owner, layer)
        return self.text(owner, layer, style)

    def model_content(self, owner: str, layers: list[str], style: str, dim_block: str) -> list[str]:
        r = self.rng
        k = r.random()
        layer = r.choice(layers)
        self.counts["model"] += 1
        if k < 0.30:
            return self.insert(owner, layer, f"SYN-BLK-{r.randrange(SYN_BLOCKS):03d}")
        if k < 0.38:
            return self.insert(owner, layer, "SYN-TAG", {"SYN_MA": f"SYN-{r.randint(1, 9999):04d}", "SYN_GHI_CHU": r.choice(SYN_TEXTS)})
        if k < 0.58:
            return self.line(owner, layer, z=5.0 if r.random() < 0.01 else 0.0)
        if k < 0.70:
            return self.lwpolyline(owner, layer)
        if k < 0.88:
            return self.text(owner, layer, style)
        return self.dimension(owner, layer, dim_block)


def _large_skeleton():
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    layers = [f"SYN-L{i:02d}" for i in range(40)] + ["SYN-XR|L01", "SYN-XR$0$L02"]
    for name in layers:
        doc.layers.add(name)
    doc.styles.add("SYN-ST-TTF", font="arial.ttf")
    doc.styles.add("SYN-ST-SHX", font="syn_vn.shx")
    tag = doc.blocks.new("SYN-TAG")
    tag.add_attdef("SYN_MA", (0, 0), dxfattribs={"height": 2.5, "layer": "SYN-L00"})
    tag.add_attdef("SYN_GHI_CHU", (0, -4), dxfattribs={"height": 2.5, "layer": "SYN-L00"})
    for i in range(SYN_BLOCKS):
        blk = doc.blocks.new(f"SYN-BLK-{i:03d}")
        blk.add_line((0, 0), (100, 0), dxfattribs={"layer": layers[i % 40]})
        if i:
            blk.add_blockref(f"SYN-BLK-{i - 1:03d}", (10, 10), dxfattribs={"layer": layers[i % 40]})  # khối lồng
    msp = doc.modelspace()
    dim = msp.add_linear_dim(base=(0, -200), p1=(0, 0), p2=(600, 0), dxfattribs={"layer": "SYN-L01"})
    dim.render()
    lo = doc.layouts.new("SYN-A3")
    lo.page_setup(size=(420, 297), margins=(10, 10, 10, 20), units="mm")
    lo.add_viewport(center=(210, 148), size=(380, 250), view_center_point=(0, 0), view_height=250 * 20)
    return doc, layers, dim.dimension.dxf.geometry


def make_large(path: Path, target_mb: float = 100.0, seed: int = 0) -> dict:
    """Sinh DXF R2018 TỔNG HỢP cỡ >= `target_mb` MiB: layer/khối `SYN-*`, nhiều INSERT, chữ tiếng Việt tổng hợp,
    kích thước. Khoảng 70% dung lượng nằm trong định nghĩa khối (giống đặc điểm ở docs/real-sample-profile.md).

    Khung tệp do ezdxf dựng; đối tượng hàng loạt được ghi thẳng dạng văn bản. Trả về số đếm đã sinh.
    Chỉ ghi vào thư mục tạm (tmp_path), không commit.
    """
    import random

    path = Path(path)
    target = int(target_mb * 1024 * 1024)
    doc, layers, dim_block = _large_skeleton()
    owners = {b.name: b.block_record_handle for b in doc.blocks if b.name.startswith("SYN-BLK-")}
    msp_owner = doc.modelspace().block_record_handle
    skel = path.with_name(path.stem + ".skel.tmp")
    doc.saveas(skel)
    w = _LargeWriter(random.Random(seed))
    per_block = int(target * 0.70 / len(owners))
    written = 0

    def emit(out, lines: list[str]) -> int:
        chunk = "\n".join(lines) + "\n"
        out.write(chunk)
        return len(chunk.encode("utf-8"))

    try:
        with open(skel, encoding="utf-8") as src, open(path, "w", encoding="utf-8", newline="\n") as out:
            section = block = expect = None
            while True:
                code = src.readline()
                if not code:
                    break
                value = src.readline()
                c, v = code.strip(), value.rstrip("\n")
                if c == "0":
                    if v == "ENDBLK" and block in owners:  # nội dung khối: chèn trước ENDBLK
                        budget = 0
                        while budget < per_block:
                            n = emit(out, [x for _ in range(50) for x in w.block_content(owners[block], layers, "SYN-ST-TTF")])
                            budget += n
                            written += n
                    elif v == "ENDSEC" and section == "ENTITIES":  # không gian mô hình: chèn tới đủ cỡ
                        while written < target:
                            written += emit(out, [x for _ in range(50) for x in w.model_content(msp_owner, layers, "SYN-ST-SHX", dim_block)])
                    if v == "SECTION":
                        expect = "section"
                    elif v == "ENDSEC":
                        section = None
                    elif v == "BLOCK":
                        block, expect = None, "block"
                    elif v == "ENDBLK":
                        block = None
                elif c == "2" and expect == "section":
                    section, expect = v, None
                elif c == "2" and expect == "block":
                    block, expect = v, None
                written += emit(out, [code.rstrip("\n"), v])
    finally:
        skel.unlink(missing_ok=True)
    return {"bytes": path.stat().st_size, "block_entities": w.counts["blocks"], "model_entities": w.counts["model"]}
