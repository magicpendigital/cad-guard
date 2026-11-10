"""Sinh DXF tổng hợp (ezdxf) để test. KHÔNG dùng và KHÔNG chứa bản vẽ thật của khách.

Mỗi tệp "xấu" cố ý vi phạm một nhóm luật; `ok_sheet.dxf` không được vi phạm luật nào đã cài.
"""

from __future__ import annotations

from pathlib import Path

import ezdxf
import ezdxf.render.mleader
from ezdxf.math import Vec2

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


# ---- Bộ "kiểu công ty" cho dựng 3D từ bản vẽ 2D (Luồng 2). TỔNG HỢP, mô phỏng CẤU TRÚC cách vẽ đã đo trên tệp phiên
# thử (không chép nội dung): nhiều tờ A3 trong Model, khối khung tên có số bản vẽ "<hạng mục>. <tờ>", mỗi tờ nhiều
# hình chiếu có tiêu đề chữ lớn, tường/đồ/nét cắt/nét khuất/kích thước trên layer riêng, ký hiệu mặt cắt có nhãn.
KT_LAYERS = ["SYN_Tuong", "SYN_Noithat", "SYN_Netcat", "SYN_Khuat", "SYN_Dim", "SYN_Text", "SYN_Kyhieu"]


def _kt_dim(msp, p1, p2, base, angle=0):
    msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dxfattribs={"layer": "SYN_Dim"}).render()


def _kt_title(msp, text, at, k):
    msp.add_text(text, height=2.5 * k, dxfattribs={"layer": "SYN_Text", "style": "STD", "insert": at})


def make_company_kitchen(path: Path, lower_h: float = 850.0, upper_z0: float = 1500.0, aisle: float | None = None,
                         room_h: float = 2700.0) -> None:
    """Ba tờ: (1) SYN.01. 01 mặt bằng bố trí 1:50: phòng 4000×3000 tường đôi dày 200, dải tủ bếp 2400×600 sát tường
    trên; (2) SYN.10. 01 tủ bếp 1:20: mặt đứng (tủ dưới 2400×`lower_h`, tủ trên 2400×700 từ cao `upper_z0`, mỗi tủ 4
    cánh 600; tường, sàn, trần cao `room_h`) và mặt bằng (tủ dưới nét liền sâu 600, tủ trên nét khuất sâu 350); ký hiệu
    mặt cắt y1; (3) SYN.10. 02 mặt cắt Y1. `aisle`: thêm tường đối diện cách mặt tủ `aisle` mm (thử vùng quét cánh)."""
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    for name in KT_LAYERS:
        doc.layers.add(name)
    doc.layers.get("SYN_Khuat").dxf.linetype = "DASHED"
    _company_frame(doc)
    mark = doc.blocks.new("SYN_DAUCAT")
    mark.add_circle((0, 0), 150, dxfattribs={"layer": "SYN_Kyhieu"})
    mark.add_line((0, -150), (0, -600), dxfattribs={"layer": "SYN_Kyhieu"})
    mark.add_attdef("NHAN", (-60, -40), dxfattribs={"height": 80, "layer": "SYN_Kyhieu"})
    msp = doc.modelspace()

    def frame(x, k, number, name):
        ref = msp.add_blockref(CO_FRAME, (x, 0), dxfattribs={"layer": "SYN-KHUNG", "xscale": k, "yscale": k})
        ref.add_auto_attribs({"DU_AN": "CĂN HỘ SYN", "TEN_BAN_VE": name, "SO_BAN_VE": number, "TI_LE": f"1/{k}",
                              "NGAY": "10/11/2026"})

    # Tờ 1: mặt bằng bố trí 1:50
    frame(0, 50, "SYN.01. 01", "MẶT BẰNG BỐ TRÍ")
    msp.add_lwpolyline([(2800, 2800), (7200, 2800), (7200, 6200), (2800, 6200)], close=True, dxfattribs={"layer": "SYN_Tuong"})
    msp.add_lwpolyline([(3000, 3000), (7000, 3000), (7000, 6000), (3000, 6000)], close=True, dxfattribs={"layer": "SYN_Tuong"})
    _rect(msp, 3600, 5400, 6000, 6000, "SYN_Noithat")
    _rect(msp, 3600, 5650, 6000, 6000, "SYN_Khuat")
    msp.add_text("P. BẾP", height=150, dxfattribs={"layer": "SYN_Text", "style": "STD", "insert": (4600, 4300)})
    _kt_dim(msp, (3000, 3000), (7000, 3000), (5000, 2400))
    _kt_dim(msp, (3000, 3000), (3000, 6000), (2400, 4500), angle=90)
    _kt_dim(msp, (3600, 5400), (6000, 5400), (4800, 5000))
    _kt_dim(msp, (6000, 5400), (6000, 6000), (6400, 5700), angle=90)
    _kt_title(msp, "MẶT BẰNG BỐ TRÍ", (3800, 1700), 50)

    # Tờ 2: tủ bếp 1:20 (mặt đứng ở trên, mặt bằng ở dưới, cùng gốc X)
    x0, k = 21000.0, 20
    frame(x0, k, "SYN.10. 01", "CHI TIẾT TỦ BẾP SYN")
    ex, fz = x0 + 1000, 2000.0  # gốc X (mép trong tường trái), cao độ sàn trên giấy
    for a, b in (((ex, fz), (ex + 4000, fz)), ((ex, fz + room_h), (ex + 4000, fz + room_h)),
                 ((ex, fz), (ex, fz + room_h)), ((ex + 4000, fz), (ex + 4000, fz + room_h))):
        msp.add_line(a, b, dxfattribs={"layer": "SYN_Tuong"})
    for z0, z1 in ((0.0, lower_h), (upper_z0, upper_z0 + 700)):
        _rect(msp, ex + 600, fz + z0, ex + 3000, fz + z1, "SYN_Noithat")
        for i in range(4):
            _rect(msp, ex + 600 + 600 * i + 2, fz + z0 + (100 if z0 == 0 else 2), ex + 600 + 600 * (i + 1) - 2, fz + z1 - 2, "SYN_Noithat")
    _kt_dim(msp, (ex + 600, fz + upper_z0 + 700), (ex + 3000, fz + upper_z0 + 700), (ex + 1800, fz + room_h + 200))
    _kt_dim(msp, (ex, fz + room_h), (ex + 4000, fz + room_h), (ex + 2000, fz + room_h + 400))
    _kt_dim(msp, (ex, fz), (ex, fz + room_h), (ex - 400, fz + 1000), angle=90)
    _kt_dim(msp, (ex + 600, fz), (ex + 600, fz + lower_h), (ex - 200, fz + 400), angle=90)
    _kt_dim(msp, (ex + 600, fz + upper_z0), (ex + 600, fz + upper_z0 + 700), (ex - 200, fz + upper_z0 + 300), angle=90)
    ref = msp.add_blockref("SYN_DAUCAT", (ex + 1500, fz + 400), dxfattribs={"layer": "SYN_Kyhieu", "xscale": 0.5, "yscale": 0.5})
    ref.add_auto_attribs({"NHAN": "y1"})
    _kt_title(msp, "MẶT ĐỨNG TỦ BẾP SYN", (ex + 1000, 1650), k)
    py = 600.0  # mặt bằng: mép trước tủ ở y = py, tường sau ở y = py + 600
    msp.add_line((ex, py + 600), (ex + 4000, py + 600), dxfattribs={"layer": "SYN_Tuong"})
    msp.add_line((ex, py - (aisle or 200)), (ex, py + 600), dxfattribs={"layer": "SYN_Tuong"})
    if aisle is not None:
        msp.add_line((ex, py - aisle), (ex + 4000, py - aisle), dxfattribs={"layer": "SYN_Tuong"})
    _rect(msp, ex + 600, py, ex + 3000, py + 600, "SYN_Noithat")
    _rect(msp, ex + 600, py + 250, ex + 3000, py + 600, "SYN_Khuat")
    _kt_dim(msp, (ex + 600, py), (ex + 3000, py), (ex + 1800, py - 150))
    _kt_dim(msp, (ex + 3000, py), (ex + 3000, py + 600), (ex + 3300, py + 300), angle=90)
    _kt_title(msp, "MẶT BẰNG TỦ BẾP SYN", (ex + 1000, 250), k)

    # Tờ 3: mặt cắt Y1 (ngang = chiều sâu từ tường sau, dọc = cao)
    x0 = 21000.0 + 420 * k
    frame(x0, k, "SYN.10. 02", "CHI TIẾT TỦ BẾP SYN")
    sx, sz = x0 + 1500, 1000.0
    msp.add_line((sx, sz), (sx, sz + room_h), dxfattribs={"layer": "SYN_Tuong"})
    msp.add_line((sx, sz), (sx + 1500, sz), dxfattribs={"layer": "SYN_Tuong"})
    _rect(msp, sx, sz, sx + 600, sz + lower_h, "SYN_Netcat")
    _rect(msp, sx, sz + upper_z0, sx + 350, sz + upper_z0 + 700, "SYN_Netcat")
    _kt_dim(msp, (sx, sz + lower_h), (sx + 600, sz + lower_h), (sx + 300, sz + lower_h + 150))
    _kt_dim(msp, (sx + 600, sz), (sx + 600, sz + lower_h), (sx + 800, sz + 400), angle=90)
    _kt_title(msp, "MẶT CẮT Y1 TỦ BẾP SYN", (sx, 600), k)
    _finish(doc, path)


def make_company_kitchen_low(path: Path) -> None:
    make_company_kitchen(path, lower_h=700.0)


def make_company_kitchen_aisle(path: Path) -> None:
    make_company_kitchen(path, aisle=450.0)


SCENE_FIXTURES = {
    "company_kitchen.dxf": make_company_kitchen,
    "company_kitchen_low.dxf": make_company_kitchen_low,
    "company_kitchen_aisle.dxf": make_company_kitchen_aisle,
    "cabinet_views_ok.dxf": make_cabinet_views,
    "cabinet_nolayers.dxf": make_cabinet_nolayers,
    "cabinet_views_front_only.dxf": make_cabinet_front_only,
    "cabinet_views_conflict.dxf": make_cabinet_conflict,
    "room_ok.dxf": make_room_ok,
    "room_missing_height.dxf": make_room_missing_height,
}


# ---- Bộ xem trước (preview): mặt bằng sảnh TỔNG HỢP để test và QC bằng mắt bộ vẽ xem trước của `cadguard app`.
# Không nằm trong ALL (không đổi kết quả luật của bộ chính); sinh vào thư mục con preview/.

PV_LAYERS = {  # tên: màu ACI (7 = đen/trắng theo nền)
    "SYN-TUONG": 7, "SYN-COT": 8, "SYN-CUA": 3, "SYN-NOI-THAT": 4, "SYN-HATCH": 9, "SYN-KICH-THUOC": 1,
    "SYN-CHU": 2, "SYN-KHUNG-TEN": 7, "SYN-TRUC": 5,
}


def _pv_blocks(doc) -> None:
    """Khối đồ nội thất có hình bên trong: bàn họp, ghế, sofa, tủ, cây cảnh (đơn vị mm, gốc ở tâm/góc)."""
    ban = doc.blocks.new("SYN-BAN-HOP")  # bàn 2400x1200 bo góc + mặt kính + chân
    ban.add_lwpolyline([(-1200, -600), (1200, -600), (1200, 600), (-1200, 600)], close=True)
    ban.add_lwpolyline([(-1100, -500), (1100, -500), (1100, 500), (-1100, 500)], close=True)
    for x in (-1000, 1000):
        for y in (-400, 400):
            ban.add_circle((x, y), 40)
    ban.add_line((-1100, 0), (1100, 0))
    ghe = doc.blocks.new("SYN-GHE")  # ghế 500x500, lưng là cung
    ghe.add_lwpolyline([(-250, -250), (250, -250), (250, 200), (-250, 200)], close=True)
    ghe.add_arc((0, 150), 260, 20, 160)
    ghe.add_line((-200, -200), (200, -200))
    sofa = doc.blocks.new("SYN-SOFA")  # sofa 2000x900: lưng, tay, 3 đệm
    sofa.add_lwpolyline([(0, 0), (2000, 0), (2000, 900), (0, 900)], close=True)
    sofa.add_lwpolyline([(0, 700), (2000, 700)])
    sofa.add_lwpolyline([(200, 0), (200, 700)])
    sofa.add_lwpolyline([(1800, 0), (1800, 700)])
    for i in range(3):
        x0 = 200 + i * 533.3
        sofa.add_lwpolyline([(x0 + 20, 40), (x0 + 513, 40), (x0 + 513, 660), (x0 + 20, 660)], close=True)
    tu = doc.blocks.new("SYN-TU")  # tủ 1200x600: 2 cánh + đường chéo mở cánh + hatch chéo
    tu.add_lwpolyline([(0, 0), (1200, 0), (1200, 600), (0, 600)], close=True)
    tu.add_line((600, 0), (600, 600))
    tu.add_line((0, 0), (600, 600), dxfattribs={"linetype": "DASHED"})
    tu.add_line((1200, 0), (600, 600), dxfattribs={"linetype": "DASHED"})
    h = tu.add_hatch(color=9)
    h.set_pattern_fill("ANSI31", scale=20)
    h.paths.add_polyline_path([(20, 20), (580, 20), (580, 120), (20, 120)], is_closed=True)
    cay = doc.blocks.new("SYN-CAY")  # chậu cây: tròn + lá elip xoay + spline
    cay.add_circle((0, 0), 300)
    for a in range(0, 360, 60):
        cay.add_ellipse((0, 0), major_axis=(260, 0), ratio=0.3, start_param=0, end_param=6.283185).rotate_z(a * 0.0174533)
    cay.add_spline([(-200, -50), (-80, 120), (60, -100), (200, 60)])
    # khung tên: khung + bảng kẻ ô + thuộc tính (chữ nhỏ dày đặc như bản vẽ thật)
    kt = doc.blocks.new("SYN-KHUNG-TEN")
    kt.add_lwpolyline([(0, 0), (6000, 0), (6000, 3000), (0, 3000)], close=True)
    for i in range(1, 12):
        kt.add_line((0, i * 250), (6000, i * 250))
    kt.add_line((2000, 0), (2000, 3000))
    kt.add_line((4200, 0), (4200, 3000))
    for i, tag in enumerate(("SO_BV", "TEN_BV", "DU_AN", "TY_LE", "NGUOI_VE", "NGAY")):
        kt.add_attdef(tag, (2100, 2780 - i * 250), dxfattribs={"height": 120, "style": "SYN-ST"})


def make_preview_lobby(path: Path) -> None:
    """Mặt bằng sảnh TỔNG HỢP (mm), tái hiện các thứ bộ xem trước cũ vẽ sai: khung tên chữ dày đặc, MTEXT nhiều dòng,
    hàng trăm INSERT khối đồ nội thất (xoay/co giãn), kích thước, hatch, ARC, ELLIPSE, SPLINE, POLYLINE cũ, chữ xoay.
    Toạ độ đặt sẵn: LINE `SYN-MOC` từ (1000, 1000) tới (3000, 1000) để test định vị phát hiện.
    """
    doc = ezdxf.new("R2010", setup=True)  # AC1024 như bản vẽ thật hay gặp
    doc.header["$INSUNITS"] = 4
    for name, color in PV_LAYERS.items():
        doc.layers.add(name, color=color)
    doc.styles.add("SYN-ST", font="arial.ttf")
    _pv_blocks(doc)
    msp = doc.modelspace()
    W, H = 30000.0, 18000.0
    # tường: hai đường bao (LWPOLYLINE) + một đoạn POLYLINE kiểu cũ
    msp.add_lwpolyline([(0, 0), (W, 0), (W, H), (0, H)], close=True, dxfattribs={"layer": "SYN-TUONG"})
    msp.add_lwpolyline([(200, 200), (W - 200, 200), (W - 200, H - 200), (200, H - 200)], close=True,
                       dxfattribs={"layer": "SYN-TUONG"})
    msp.add_polyline2d([(12000, 200), (12000, 6000), (14000, 6000), (14000, 200)], dxfattribs={"layer": "SYN-TUONG"})
    msp.add_line((1000, 1000), (3000, 1000), dxfattribs={"layer": "SYN-TRUC"})  # mốc định vị (handle trả về dưới)
    # cột: hatch đặc
    for cx in range(3000, int(W), 6000):
        for cy in (3000, 9000, 15000):
            pts = [(cx - 300, cy - 300), (cx + 300, cy - 300), (cx + 300, cy + 300), (cx - 300, cy + 300)]
            msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "SYN-COT"})
            hc = msp.add_hatch(color=8, dxfattribs={"layer": "SYN-HATCH"})
            hc.paths.add_polyline_path(pts, is_closed=True)
    # sàn khu chờ: hatch mẫu
    hs = msp.add_hatch(dxfattribs={"layer": "SYN-HATCH"})
    hs.set_pattern_fill("ANSI37", scale=200)
    hs.paths.add_polyline_path([(16000, 10000), (26000, 10000), (26000, 16000), (16000, 16000)], is_closed=True)
    # cửa: cung mở cánh + lá cửa
    for i, x in enumerate((5000, 9000, 20000, 24000)):
        msp.add_line((x, 200), (x, 1100), dxfattribs={"layer": "SYN-CUA"})
        msp.add_arc((x, 200), 900, 0 if i % 2 else 90, 90 if i % 2 else 180, dxfattribs={"layer": "SYN-CUA"})
    # đồ nội thất: bàn họp + ghế quanh bàn (xoay), sofa, tủ (co giãn), cây
    n = 0
    for bx in (4000, 9000):
        for by in (5000, 12000):
            msp.add_blockref("SYN-BAN-HOP", (bx, by), dxfattribs={"layer": "SYN-NOI-THAT"})
            for k in range(-2, 3):
                msp.add_blockref("SYN-GHE", (bx + k * 450, by - 900), dxfattribs={"layer": "SYN-NOI-THAT"})
                msp.add_blockref("SYN-GHE", (bx + k * 450, by + 900), dxfattribs={"layer": "SYN-NOI-THAT", "rotation": 180})
                n += 2
            msp.add_blockref("SYN-GHE", (bx - 1600, by), dxfattribs={"layer": "SYN-NOI-THAT", "rotation": 270})
            msp.add_blockref("SYN-GHE", (bx + 1600, by), dxfattribs={"layer": "SYN-NOI-THAT", "rotation": 90})
            n += 3
    for i in range(6):
        msp.add_blockref("SYN-SOFA", (16500 + (i % 3) * 3000, 10500 + (i // 3) * 3000),
                         dxfattribs={"layer": "SYN-NOI-THAT", "rotation": (i * 30) % 90})
    for i in range(8):
        msp.add_blockref("SYN-TU", (16000 + i * 1300, 16900), dxfattribs={"layer": "SYN-NOI-THAT",
                                                                         "xscale": 1.0 + (i % 3) * 0.1, "yscale": 0.8})
    for i in range(30):
        msp.add_blockref("SYN-CAY", (1500 + (i % 10) * 2700, 7500 + (i // 10) * 300 + (i % 2) * 150),
                         dxfattribs={"layer": "SYN-NOI-THAT", "xscale": 0.6 + (i % 4) * 0.15, "yscale": 0.6 + (i % 4) * 0.15})
    # kích thước
    dims = [((0, -1200), (0, 0), (W, 0)), ((0, -600), (0, 0), (6000, 0)), ((6000, -600), (6000, 0), (12000, 0))]
    for base, p1, p2 in dims:
        msp.add_linear_dim(base=base, p1=p1, p2=p2, dxfattribs={"layer": "SYN-KICH-THUOC"}).render()
    msp.add_linear_dim(base=(-1200, 0), p1=(0, 0), p2=(0, H), angle=90, dxfattribs={"layer": "SYN-KICH-THUOC"}).render()
    msp.add_aligned_dim(p1=(16000, 10000), p2=(26000, 16000), distance=500,
                        dxfattribs={"layer": "SYN-KICH-THUOC"}).render()
    # chữ: nhãn phòng nhiều cỡ, chữ xoay, MTEXT ghi chú nhiều dòng
    labels = [("SẢNH CHỜ SYN", (17000, 9200), 450, 0), ("PHÒNG HỌP 1 SYN", (2500, 3000), 300, 0),
              ("PHÒNG HỌP 2 SYN", (7500, 3000), 300, 0), ("HÀNH LANG SYN", (13000, 8000), 250, 90),
              ("LỐI THOÁT HIỂM SYN", (27000, 4000), 200, 45), ("kho SYN", (12500, 3000), 150, 0)]
    for text, at, height, rot in labels:
        msp.add_text(text, height=height, rotation=rot, dxfattribs={"layer": "SYN-CHU", "style": "SYN-ST"}).set_placement(at)
    note = ("GHI CHÚ SYN:\\P1. Kích thước tính bằng mm, đo tại công trình trước khi sản xuất.\\P"
            "2. Gỗ công nghiệp MDF chống ẩm, phủ melamine vân sồi SYN.\\P"
            "3. Dán cạnh nhựa PVC 1 ly các cạnh lộ.\\P4. Phụ kiện bản lề giảm chấn, ray bi 3 tầng.\\P"
            "5. Mọi sai khác báo lại phòng kỹ thuật SYN.")
    msp.add_mtext(note, dxfattribs={"layer": "SYN-CHU", "char_height": 180, "width": 5200, "style": "SYN-ST"}
                  ).set_location((W + 600, H - 400))
    # khung tên ngoài khung bản vẽ (phải dưới) + bảng ghi chú chữ nhỏ dày đặc
    kt = msp.add_blockref("SYN-KHUNG-TEN", (W + 600, 0), dxfattribs={"layer": "SYN-KHUNG-TEN"})
    kt.add_auto_attribs({"SO_BV": "SYN-MB-01", "TEN_BV": "MẶT BẰNG SẢNH TỔNG HỢP", "DU_AN": "DỰ ÁN MẪU SYN",
                         "TY_LE": "1:100", "NGUOI_VE": "A", "NGAY": "2026-11-05"})
    for i in range(1, 12):
        y = 3000 + 3000 - i * 250
        msp.add_text(f"{i:02d}", height=100, dxfattribs={"layer": "SYN-KHUNG-TEN", "style": "SYN-ST"}
                     ).set_placement((W + 700, y - 180))
        msp.add_text(f"Vật liệu hoàn thiện hạng mục số {i} SYN", height=100,
                     dxfattribs={"layer": "SYN-KHUNG-TEN", "style": "SYN-ST"}).set_placement((W + 1300, y - 180))
    msp.add_lwpolyline([(W + 600, 3000), (W + 6600, 3000), (W + 6600, 6000), (W + 600, 6000)], close=True,
                       dxfattribs={"layer": "SYN-KHUNG-TEN"})
    for i in range(1, 12):
        msp.add_line((W + 600, 3000 + i * 250), (W + 6600, 3000 + i * 250), dxfattribs={"layer": "SYN-KHUNG-TEN"})
    doc.saveas(path)


PREVIEW_FIXTURES = {
    "preview_lobby.dxf": make_preview_lobby,
}


# ---- Bộ tờ (sheets.py): khung tên trong không gian mô hình như nhiều công ty VN vẽ, chữ TCVN3, rác, một layout.
SHEET_W, SHEET_H = 420 * 20, 297 * 20  # khổ A3 tỉ lệ 1:20


def _sheet_content(msp, x0: float, y0: float, n: int = 15) -> None:
    for i in range(n):
        msp.add_line((x0 + 600 + i * 300, y0 + 1500), (x0 + 600 + i * 300, y0 + 4500), dxfattribs={"layer": "SYN-NOI-THAT"})
    msp.add_circle((x0 + 4000, y0 + 3000), 400, dxfattribs={"layer": "SYN-NOI-THAT"})


def make_sheet_set(path: Path) -> None:
    """Ba tờ A3 1:20 trong Model (hai khối khung tên KHUNG_A3, một khung vẽ bằng polyline), một layout có khung nhìn,
    chữ tiêu đề mã TCVN3 (theo phông .VnTime và theo đoán), một đối tượng ngoài tờ, một đối tượng lạc rất xa, một
    layer rỗng, một khối không dùng."""
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    for name in HYG_LAYERS + ["SYN-KHUNG", "RAC-RONG"]:
        doc.layers.add(name)
    doc.styles.add("STD", font="arial.ttf")
    doc.styles.add("VN3", font=".VnTime")
    frame = doc.blocks.new("KHUNG_A3")
    frame.add_lwpolyline([(0, 0), (420, 0), (420, 297), (0, 297)], close=True, dxfattribs={"layer": "SYN-KHUNG"})
    frame.add_lwpolyline([(20, 10), (410, 10), (410, 287), (20, 287)], close=True, dxfattribs={"layer": "SYN-KHUNG"})
    frame.add_attdef("TENBANVE", (300, 20), dxfattribs={"height": 4, "layer": "SYN-KHUNG", "style": "STD"})
    unused = doc.blocks.new("KHOI_THUA")
    unused.add_circle((0, 0), 50, dxfattribs={"layer": "SYN-NOI-THAT"})
    msp = doc.modelspace()
    row1 = 10000
    # tờ 1: khối khung tên, tiêu đề từ thuộc tính; nhãn tỉ lệ
    ref = msp.add_blockref("KHUNG_A3", (0, row1), dxfattribs={"layer": "SYN-KHUNG", "xscale": 20, "yscale": 20})
    ref.add_auto_attribs({"TENBANVE": "MAT BANG BO TRI"})
    _sheet_content(msp, 0, row1)
    msp.add_text("1/20", height=150, dxfattribs={"layer": "SYN-CHU", "style": "STD", "insert": (6000, row1 + 400)})
    # tờ 2: khối khung tên không ghi thuộc tính; tiêu đề là TEXT mã TCVN3 (phông .VnTime) ở dải khung tên
    msp.add_blockref("KHUNG_A3", (10000, row1), dxfattribs={"layer": "SYN-KHUNG", "xscale": 20, "yscale": 20})
    _sheet_content(msp, 10000, row1)
    msp.add_text("mÆt ®øng tñ bÕp", height=250,
                 dxfattribs={"layer": "SYN-CHU", "style": "VN3", "insert": (10000 + 5500, row1 + 600)})
    # tờ 3: khung vẽ bằng polyline (không khối), tiêu đề TCVN3 nhưng kiểu chữ Arial (phải đoán)
    msp.add_lwpolyline([(0, 0), (SHEET_W, 0), (SHEET_W, SHEET_H), (0, SHEET_H)], close=True, dxfattribs={"layer": "SYN-KHUNG"})
    _sheet_content(msp, 0, 0)
    msp.add_text("chi tiÕt tñ ¸o", height=250, dxfattribs={"layer": "SYN-CHU", "style": "STD", "insert": (5500, 600)})
    # kích thước ghi đè chữ trong tờ 3 (VS-06/TX-08, bậc Chặn mặc định): tờ 3 không chốt được
    msp.add_linear_dim(base=(1000, 5200), p1=(1000, 4600), p2=(2000, 4600), text="1200",
                       dxfattribs={"layer": "SYN-KICH-THUOC"}).render()
    # ngoài tờ: nằm giữa hai hàng tờ; lạc xa: rất xa vùng vẽ
    msp.add_line((3000, 8000), (5000, 8000), dxfattribs={"layer": "SYN-NOI-THAT"})
    msp.add_circle((5_000_000, 5_000_000), 10, dxfattribs={"layer": "SYN-NOI-THAT"})
    # chi tiết in qua layout (khung nhìn nhìn vùng x = 30000)
    for i in range(6):
        msp.add_line((28500 + i * 400, 2000), (28500 + i * 400, 4000), dxfattribs={"layer": "SYN-NOI-THAT"})
    lo = doc.layouts.new("IN-CHI-TIET")
    lo.page_setup(size=(420, 297), margins=(10, 10, 10, 20), units="mm")
    lo.add_viewport(center=(210, 148), size=(380, 250), view_center_point=(29500, 3000), view_height=3000)
    _finish(doc, path)


# ---- Bộ nhiều tờ trong Model theo kiểu công ty nội thất (mô phỏng CẤU TRÚC tệp phiên thử, không phải bản vẽ thật):
# một khối khung tên A3 của công ty có thuộc tính, chèn nhiều lần, tỉ lệ khác nhau, khung kề nhau, có tờ trống.
CO_FRAME = "SYN-KHUNG-CTY"
CO_TAGS = ["DU_AN", "TEN_BAN_VE", "SO_BAN_VE", "TI_LE", "NGAY"]
CO_BAND_X = 370.0  # dải khung tên dọc bên phải: x 370..410 (đơn vị khối, 1:1 = mm)


def _company_frame(doc) -> None:
    for name in ("SYN-KHUNG", "SYN-LOGO"):
        if not doc.layers.has_entry(name):
            doc.layers.add(name)
    if not doc.styles.has_entry("STD"):
        doc.styles.add("STD", font="arial.ttf")
    b = doc.blocks.new(CO_FRAME)
    b.add_lwpolyline([(0, 0), (420, 0), (420, 297), (0, 297)], close=True, dxfattribs={"layer": "SYN-KHUNG"})
    b.add_lwpolyline([(20, 10), (410, 10), (410, 287), (20, 287)], close=True, dxfattribs={"layer": "SYN-KHUNG"})
    b.add_line((CO_BAND_X, 10), (CO_BAND_X, 287), dxfattribs={"layer": "SYN-KHUNG"})
    # logo: hình vẽ (polyline + hatch) ở đầu dải khung tên
    b.add_lwpolyline([(375, 262), (405, 262), (405, 282), (375, 282)], close=True, dxfattribs={"layer": "SYN-LOGO"})
    h = b.add_hatch(color=1, dxfattribs={"layer": "SYN-LOGO"})
    h.paths.add_polyline_path([(380, 266), (400, 266), (390, 278)], is_closed=True)
    b.add_text("CÔNG TY NỘI THẤT SYN", height=2.5, dxfattribs={"layer": "SYN-KHUNG", "style": "STD", "insert": (372, 255)})
    labels = ["DỰ ÁN", "TÊN BẢN VẼ", "SỐ BẢN VẼ", "TỈ LỆ", "NGÀY"]
    for i, (tag, lab) in enumerate(zip(CO_TAGS, labels)):
        y = 200 - i * 40
        b.add_text(lab, height=2.0, dxfattribs={"layer": "SYN-KHUNG", "style": "STD", "insert": (372, y + 12)})
        b.add_line((CO_BAND_X, y), (410, y), dxfattribs={"layer": "SYN-KHUNG"})
        b.add_attdef(tag, (372, y + 4), dxfattribs={"height": 3.0, "layer": "SYN-KHUNG", "style": "STD"})


# (hệ số, giá trị thuộc tính, có nội dung, cỡ chữ ghi chú khi in (mm))
CO_SHEETS = [
    (15, {"DU_AN": "CĂN HỘ SYN", "TEN_BAN_VE": "MẶT BẰNG BỐ TRÍ", "SO_BAN_VE": "NT-01", "TI_LE": "1/15", "NGAY": "10/11/2026"}, True, 2.5),
    (15, {"DU_AN": "CĂN HỘ SYN", "TEN_BAN_VE": "MẶT BẰNG TRẦN", "SO_BAN_VE": "NT-02", "TI_LE": "1/15", "NGAY": "10/11/2026"}, True, 2.5),
    (20, {"DU_AN": "CĂN HỘ SYN", "TEN_BAN_VE": "MẶT ĐỨNG TỦ BẾP", "SO_BAN_VE": "NT-03", "TI_LE": "1/25", "NGAY": "10/11/2026"}, True, 2.5),
    (19.77, {"DU_AN": "CĂN HỘ SYN", "TEN_BAN_VE": "CHI TIẾT TỦ ÁO", "SO_BAN_VE": "NT-04", "TI_LE": "1/20", "NGAY": "10/11/2026"}, True, 2.5),
    (10, {"DU_AN": "CĂN HỘ SYN", "TEN_BAN_VE": "CHI TIẾT NẸP", "SO_BAN_VE": "", "TI_LE": "1/10", "NGAY": "10/11/2026"}, True, 0.6),
    (15, {"DU_AN": "CĂN HỘ SYN", "TEN_BAN_VE": "TỜ DỰ PHÒNG", "SO_BAN_VE": "NT-02", "TI_LE": "1/15", "NGAY": "10/11/2026"}, False, 2.5),
]
# chữ ghi chú TCVN3 (phông .VnArial) và Unicode: dùng cho chuyển mã và dịch
CO_NOTES_TCVN3 = ["tñ bÕp trªn", "c¸nh tñ MDF chèng Èm 18mm", "nÑp chØ nh«m"]
CO_NOTES_UNICODE = ["Tủ áo cánh mở", "Kính cường lực 8mm", "Sơn PU màu trắng"]


LEGACY_FRAME = "SYN-KHUNG-CU"
LEGACY_TAGS = {"DU_AN": "DUAN", "TEN_BAN_VE": "TENBV", "SO_BAN_VE": "KYHIEU", "TI_LE": "TL", "NGAY": "NGAYVE"}


def _legacy_frame(doc) -> None:
    """Khung tên CŨ của công ty (cùng khổ A3, khác khối, khác tên thẻ, dải khung tên hẹp hơn): ca thay khung."""
    b = doc.blocks.new(LEGACY_FRAME)
    b.add_lwpolyline([(0, 0), (420, 0), (420, 297), (0, 297)], close=True, dxfattribs={"layer": "SYN-KHUNG"})
    b.add_lwpolyline([(20, 10), (410, 10), (410, 287), (20, 287)], close=True, dxfattribs={"layer": "SYN-KHUNG"})
    b.add_line((380, 10), (380, 287), dxfattribs={"layer": "SYN-KHUNG"})
    for i, tag in enumerate(LEGACY_TAGS.values()):
        y = 200 - i * 40
        b.add_attdef(tag, (382, y + 4), dxfattribs={"height": 2.5, "layer": "SYN-KHUNG", "style": "STD"})


def make_model_sheets(path: Path, sheets: list | None = None, legacy: tuple[int, ...] = ()) -> None:
    """Sáu tờ A3 trong Model (khối khung tên công ty có thuộc tính), khung kề nhau, tỉ lệ 15/15/20/19,77/10/15; tờ 6
    trống. Cố ý: tỉ lệ ghi trong khung khác hệ số (tờ 3), hệ số lạ 19,77 (tờ 4), thiếu số bản vẽ và chữ in quá nhỏ
    (tờ 5), số bản vẽ trùng (tờ 6 = tờ 2), một đối tượng tràn khung (tờ 2), một khối nằm ngoài mọi tờ. Chữ ghi chú có
    TCVN3 (phông .VnArial) và Unicode, một kích thước ghi đè chữ. `legacy`: chỉ số (từ 0) các tờ dùng khung tên CŨ
    `LEGACY_FRAME` (ca thay khung tên)."""
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    for name in HYG_LAYERS:
        doc.layers.add(name)
    doc.styles.add("VN-ARIAL", font=".VnArial")
    _company_frame(doc)
    if legacy:
        _legacy_frame(doc)
    marker = doc.blocks.new("SYN-KY-HIEU")
    marker.add_circle((0, 0), 50, dxfattribs={"layer": "SYN-NOI-THAT"})
    msp = doc.modelspace()
    x = 0.0
    for i, (k, values, content, note_mm) in enumerate(sheets or CO_SHEETS):
        if i in legacy:  # khung cũ: cùng giá trị, tên thẻ cũ
            ref = msp.add_blockref(LEGACY_FRAME, (x, 0), dxfattribs={"layer": "SYN-KHUNG", "xscale": k, "yscale": k})
            ref.add_auto_attribs({LEGACY_TAGS[t]: v for t, v in values.items()})
        else:
            ref = msp.add_blockref(CO_FRAME, (x, 0), dxfattribs={"layer": "SYN-KHUNG", "xscale": k, "yscale": k})
            ref.add_auto_attribs(values)
        if content:
            for j in range(8):
                msp.add_line((x + 40 * k + j * 25 * k, 60 * k), (x + 40 * k + j * 25 * k, 220 * k), dxfattribs={"layer": "SYN-NOI-THAT"})
            msp.add_circle((x + 200 * k, 150 * k), 30 * k, dxfattribs={"layer": "SYN-NOI-THAT"})
            msp.add_text(CO_NOTES_TCVN3[i % 3], height=note_mm * k,
                         dxfattribs={"layer": "SYN-CHU", "style": "VN-ARIAL", "insert": (x + 40 * k, 240 * k)})
            msp.add_mtext(CO_NOTES_UNICODE[i % 3], dxfattribs={"layer": "SYN-CHU", "style": "STD", "char_height": 2.5 * k,
                                                                 "insert": (x + 40 * k, 40 * k)})
            msp.add_linear_dim(base=(x + 60 * k, 50 * k), p1=(x + 60 * k, 45 * k), p2=(x + 160 * k, 45 * k),
                               dxfattribs={"layer": "SYN-KICH-THUOC"}).render()
        if i == 0:  # chú thích có đường dẫn (MULTILEADER), chữ TCVN3 theo kiểu chữ .VnArial
            ml = msp.add_multileader_mtext("Standard")
            ml.set_content("®Ìn h¾t trÇn", char_height=2.5 * k, style="VN-ARIAL")
            ml.add_leader_line(ezdxf.render.mleader.ConnectionSide.left, [Vec2(x + 120 * k, 200 * k)])
            ml.build(insert=Vec2(x + 150 * k, 210 * k))
        if i == 1:  # tràn khung: đường kéo ra ngoài mép phải vùng vẽ, đè dải khung tên
            msp.add_line((x + 300 * k, 120 * k), (x + 400 * k, 120 * k), dxfattribs={"layer": "SYN-NOI-THAT"})
        x += 420 * k  # kề nhau, không khe hở
    msp.add_blockref("SYN-KY-HIEU", (x + 5000, -8000), dxfattribs={"layer": "SYN-NOI-THAT"})  # ngoài mọi tờ
    _finish(doc, path)


SHEET_FIXTURES = {
    "sheet_set.dxf": make_sheet_set,
    "model_sheets.dxf": make_model_sheets,
}


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
    scene_dir = out_dir / "scene"
    scene_dir.mkdir(exist_ok=True)
    for name, fn in SCENE_FIXTURES.items():
        p = scene_dir / name
        fn(p)
        paths.append(p)
    preview_dir = out_dir / "preview"
    preview_dir.mkdir(exist_ok=True)
    for name, fn in PREVIEW_FIXTURES.items():
        p = preview_dir / name
        fn(p)
        paths.append(p)
    sheet_dir = out_dir / "sheets"
    sheet_dir.mkdir(exist_ok=True)
    for name, fn in SHEET_FIXTURES.items():
        p = sheet_dir / name
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
