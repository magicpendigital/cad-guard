"""Chú giải hạng mục (bước 2): chia khối tại vách thật, hình bỏ cánh đi kèm, bộ kiểm hình học, áp chia khi Đồng ý.
Hình tổng hợp kiểu tủ áo "2 cánh + cột ngăn kéo" vẽ liền thân (không có khe để cắt XY)."""
from __future__ import annotations

from types import SimpleNamespace

from cadguard.model import EntityRec
from cadguard.scene import annotate
from cadguard.scene.views2d import Drawing2D, View

ROLES = {"N": "furniture", "K": "hidden"}


class _B:
    def __init__(self):
        self.ents: dict[str, EntityRec] = {}

    def rect(self, x0, z0, x1, z1, layer="N"):
        h = f"{len(self.ents) + 1:X}"
        self.ents[h] = EntityRec(handle=h, type="LWPOLYLINE", layer=layer, closed=True, pts=[(x0, z0), (x1, z0), (x1, z1), (x0, z1)])
        return h

    def line(self, a, b, layer="N"):
        h = f"{len(self.ents) + 1:X}"
        self.ents[h] = EntityRec(handle=h, type="LINE", layer=layer, pts=[a, b])
        return h


def _wardrobe(dx=0.0, doors=True, shelves=False):
    """Tủ 1800×2400: phần 2 cánh 0–1182, vách đôi 1182/1200, cột 1200–1800 (ngăn kéo hoặc đợt)."""
    b = _B()
    hs = [b.rect(dx, 0, dx + 1800, 2400)]
    hs += [b.line((dx + 1182, 18), (dx + 1182, 2382)), b.line((dx + 1200, 18), (dx + 1200, 2382))]
    if doors:
        hs += [b.rect(dx + 2, 2, dx + 591, 2398), b.rect(dx + 591, 2, dx + 1180, 2398)]
        hs += [b.line((dx + 591, 2), (dx + 591, 2398))]  # đường ráp hai cánh: một nét đơn, không phải vách
    for z in (18, 400, 800):
        if shelves:
            hs += [b.rect(dx + 18, z + 400, dx + 1182, z + 418), b.rect(dx + 1200, z + 400, dx + 1782, z + 418)]
        else:
            hs += [b.rect(dx + 1202, z, dx + 1798, z + 380)]
    return b, hs


def _drawing(b, views):
    d = Drawing2D(structure=None, roles=ROLES, views=views, groups={"~T": {"name": "T", "sheets": []}}, sheet_group={},
                  marks=[], entities=b.ents)
    return d


def _scene(fronts):
    m = SimpleNamespace(id="M1", elevation="V:E", ebox=[0.0, 0.0, 1800.0, 2400.0], form="cabinet", x=0.0,
                        fronts=[SimpleNamespace(x0=a, x1=c) for a, c in fronts])
    return SimpleNamespace(item="~T", modules=[m])


def test_board_found_seam_ignored_and_split_proposed():
    b, hs = _wardrobe()
    d = _drawing(b, [View("V:E", "S", "elevation", handles=hs, box=(0, 0, 1800, 2400), group="~T")])
    assert [(round(x0), round(x1)) for x0, x1, _h in annotate.boards(d, hs, (0, 0, 1800, 2400))] == [(1182, 1200)]
    sc = _scene([(2, 591), (591, 1180), (1202, 1798)])
    props = annotate.split_proposals(d, sc)
    assert len(props) == 1 and props[0]["key"] == "split:~T" and 1182 <= float(props[0]["value"]) <= 1200
    assert annotate.check_split(d, sc, float(props[0]["value"]), props[0]["evidence"])[0]


def test_check_rejects_cut_through_door_and_no_board():
    b, hs = _wardrobe()
    d = _drawing(b, [View("V:E", "S", "elevation", handles=hs, box=(0, 0, 1800, 2400), group="~T")])
    sc = _scene([(2, 591), (591, 1180), (1202, 1798)])
    ok, why = annotate.check_split(d, sc, 300.0)
    assert not ok and "cánh" in why
    ok, why = annotate.check_split(d, _scene([]), 900.0)
    assert not ok and "vách" in why
    ok, why = annotate.check_split(d, sc, 1191.0, ["FFFF"])
    assert not ok and "nét dẫn" in why


def test_companion_no_doors_view_gives_board():
    # hình chính chỉ có cánh liền mặt (không thấy vách); hình bỏ cánh đặt cạnh (lệch 5000) thấy vách
    main = _B()
    hm = [main.rect(0, 0, 1800, 2400), main.rect(2, 2, 1180, 2398), main.rect(1202, 2, 1798, 2398)]
    comp, hc = _wardrobe(dx=5000.0, doors=False)
    main.ents.update({k + "C": EntityRec(**{**v.model_dump(), "handle": k + "C"}) for k, v in comp.ents.items()})
    hc = [h + "C" for h in hc]
    d = _drawing(main, [View("V:E", "S", "elevation", handles=hm, box=(0, 0, 1800, 2400), group="~T"),
                        View("V:F", "S", "elevation", flags=["no_doors"], handles=hc, box=(5000, 0, 6800, 2400), group="~T")])
    sc = _scene([(2, 1180), (1202, 1798)])
    comps = annotate.companions(d, sc)
    assert comps and comps[0]["view"] == "V:F"
    props = annotate.split_proposals(d, sc)
    assert props and 1182 <= float(props[0]["value"]) <= 1200 and "bỏ cánh" in props[0]["reason"]


def test_divider_with_same_shelves_is_not_split():
    b, hs = _wardrobe(doors=False, shelves=True)
    d = _drawing(b, [View("V:E", "S", "elevation", handles=hs, box=(0, 0, 1800, 2400), group="~T")])
    assert annotate.split_proposals(d, _scene([])) == []  # đợt hai bên cùng cao độ: một tủ có vách chia


def test_apply_splits_divides_block_and_fronts():
    b, hs = _wardrobe()
    d = _drawing(b, [])
    fr = [((2, 2, 591, 2398), hs[3]), ((591, 2, 1180, 2398), hs[4]), ((1202, 18, 1798, 398), hs[6])]
    out = annotate.apply_splits(d, [((0, 0, 1800, 2400), hs, fr, "cabinet", 0)], [1200.0])
    assert [(o[0][0], o[0][2], len(o[2])) for o in out] == [(0, 1200.0, 2), (1200.0, 1800, 1)]
    assert annotate.accepted({"split:~T": "1200.0;600"}, "~T") == [1200.0, 600.0]


def test_ai_agreeing_with_code_split_is_merged():
    from cadguard.app.scene_ai import _merge

    code = [{"key": "split:~T", "value": "1191.0", "origin": "code", "reason": "vách"}]
    llm = [{"key": "split:~T", "value": "1200", "origin": "llm", "reason": "tủ 2 cánh | cột ngăn kéo"},
           {"key": "label:M1", "value": "tủ áo", "origin": "llm"}]
    out = _merge(code, llm, "~T")
    assert len(out) == 2 and out[0]["origin"] == "code+llm" and "AI:" in out[0]["reason"]
