"""Tách khối trên mặt đứng (cắt XY) + mặt trước từ ký hiệu mở. Hình tổng hợp theo kiểu vẽ kệ TV phòng khách:
hai tủ cao chung nóc, tủ ngăn kéo thấp vẽ bằng LINE + nét khuất chéo, tấm ốp có khung TV ở giữa, kệ mở có vách chia."""
from __future__ import annotations

from cadguard.model import EntityRec
from cadguard.scene import segment as seg

ROLES = {"N": "furniture", "K": "hidden"}


class _D:
    def __init__(self):
        self.entities: dict[str, EntityRec] = {}
        self.roles = ROLES

    def rect(self, x0, z0, x1, z1, layer="N"):
        h = f"{len(self.entities) + 1:X}"
        self.entities[h] = EntityRec(handle=h, type="LWPOLYLINE", layer=layer, closed=True,
                                     pts=[(x0, z0), (x1, z0), (x1, z1), (x0, z1)])
        return h

    def line(self, a, b, layer="N"):
        h = f"{len(self.entities) + 1:X}"
        self.entities[h] = EntityRec(handle=h, type="LINE", layer=layer, pts=[a, b])
        return h


def _tv_unit() -> _D:
    d = _D()
    # hai tủ cao 0–1110 và 1110–1890, chung nóc 2850–2890
    d.rect(0, 0, 30, 2850), d.rect(1080, 0, 1110, 2850), d.rect(1860, 0, 1890, 2850), d.rect(0, 2850, 1890, 2890)
    d.rect(30, 2050, 555, 2850), d.rect(555, 2050, 1080, 2850)  # hai cánh trên tủ trái
    d.line((30, 2050), (555, 2450), "K"), d.line((555, 2050), (1080, 2450), "K")
    d.rect(1110, 50, 1860, 402), d.rect(1110, 402, 1860, 420), d.rect(1110, 420, 1860, 2850)  # ngăn kéo + cánh cao
    d.line((1110, 50), (1860, 402), "K")
    # tủ ngăn kéo thấp 1890–4330: vẽ bằng LINE, mỗi ô một nét khuất chéo
    for y in (0, 50, 402):
        d.line((1890, y), (4300, y))
    d.rect(4300, 0, 4330, 402), d.rect(1890, 402, 4330, 420)
    for x in (1890, 2500, 3110, 3700):
        d.line((x, 0), (x, 402))
    for a, b in ((1890, 2500), (2500, 3110), (3110, 3700), (3700, 4300)):
        d.line((a, 50), (b, 402), "K")
    # tấm ốp TV 1890–3600 × 670–2300 có khung TV lơ lửng giữa
    d.rect(1890, 670, 3600, 2300), d.rect(2200, 900, 3300, 1800)
    # kệ mở 3600–4900, vách chia 4250–4275, đợt cùng cao độ hai bên
    d.rect(3600, 670, 4900, 695), d.rect(3600, 2275, 4900, 2300), d.rect(3600, 695, 3625, 2275), d.rect(4875, 695, 4900, 2275)
    d.rect(4250, 695, 4275, 2275)
    for z in (1071, 1472, 1874):
        d.rect(3625, z, 4250, z + 25), d.rect(4275, z, 4875, z + 25)
    return d


def _blocks(d):
    items = seg.items_in(d, list(d.entities), frozenset({"furniture", "hidden"}))
    out = []
    for leaf in seg.split_blocks(items):
        body = [it for it in leaf if it[2] == "furniture"]
        box = seg.box_of(body)
        fr = seg.fronts(d, body, [it for it in leaf if it[2] == "hidden"], box)
        out.append((tuple(round(v) for v in box), len(fr), seg.form_of(d, body, box, fr)))
    return sorted(out)


def test_tv_unit_split_into_real_modules():
    got = _blocks(_tv_unit())
    assert got == [
        ((0, 0, 1110, 2890), 2, "cabinet"),  # tủ trái: hai cánh trên; nóc chung kéo khung tới 2890
        ((1110, 0, 1890, 2890), 2, "cabinet"),  # tủ giữa: ngăn kéo + cánh cao
        ((1890, 0, 4330, 420), 4, "cabinet"),  # ngăn kéo vẽ bằng LINE vẫn nhận ra nhờ ký hiệu chéo
        ((1890, 670, 3600, 2300), 0, "panel"),  # khung TV giữa tấm ốp không phải cánh
        ((3600, 670, 4900, 2300), 0, "open"),  # đợt hai bên vách cùng cao độ: một kệ có vách chia
    ]


def test_door_seam_is_not_a_module_boundary():
    d = _D()
    for i in range(4):  # bốn cánh sát nhau, không có hông giữa
        d.rect(i * 450, 0, (i + 1) * 450, 700)
    got = _blocks(d)
    assert len(got) == 1 and got[0][0] == (0, 0, 1800, 700)


def test_items_ignore_text_and_dims():
    d = _tv_unit()
    d.entities["T1"] = EntityRec(handle="T1", type="TEXT", layer="N", pos=(10, 10), text="tủ rượu")
    assert all(h != "T1" for _b, h, _r in seg.items_in(d, list(d.entities), frozenset({"furniture"})))


def test_x_mark_is_open_niche_not_drawer():
    d = _D()
    d.rect(0, 0, 1200, 30), d.rect(0, 400, 1200, 430), d.rect(0, 30, 25, 400), d.rect(1175, 30, 1200, 400), d.rect(590, 30, 610, 400)
    d.line((25, 30), (590, 400), "K")  # ngăn kéo: một đường chéo
    d.line((610, 30), (1175, 400), "K"), d.line((610, 400), (1175, 30), "K")  # khoang hở: dấu X
    for y in (30, 400):
        d.line((25, y), (1175, y))
    for x in (25, 590, 610, 1175):
        d.line((x, 30), (x, 400))
    got = _blocks(d)
    assert len(got) == 1 and got[0][1] == 1  # chỉ một ngăn kéo
