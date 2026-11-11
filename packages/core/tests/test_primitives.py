"""L1 — nguyên tố hình học (`scene/primitives.py`): tấm (chồng nét), khung, ký hiệu, ghi chú; chỉ DXF tổng hợp."""
from __future__ import annotations

import pytest

from cadguard import drafting, synth
from cadguard.dxf_reader import read_dxf
from cadguard.scene import interior, primitives as prim


@pytest.fixture(autouse=True)
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))


def _drawing(tmp_path, styles):
    spec = next(s for seed in range(1, 40) for s in synth.design_specs(9, seed=seed)
                if s["kind"] == "wardrobe" and any(m.get("use") == "hang" and m.get("inner_drawers") for m in s["modules"]))
    p = tmp_path / "x.dxf"
    synth.draw(spec, ["chuan"] + styles, p)
    return drafting.read(read_dxf(p), tmp_path), spec


def test_extract_interior_view(tmp_path):
    d, spec = _drawing(tmp_path, ["noithat", "khuat_chuthich"])
    elev = [v for v in d.views_of(spec["id"], "elevation") if v.box]
    inner = next(v for v in elev if "no_doors" in v.flags)
    doors = next(v for v in elev if v is not inner)
    pi, pd = prim.extract(d, inner), prim.extract(d, doors)
    ci, cd = pi.count(), pd.count()
    assert ci["boards_h"] >= 2 and ci["boards_v"] >= 1  # đợt hai nét, vách giữa hộc
    assert cd.get("symbol_opening", 0) > 0 and ci.get("symbol_opening", 0) == 0
    assert cd.get("symbol_curve", 0) == 1 and cd.get("symbol_callout", 0) == 1
    assert any("drawer" in n.meanings for n in pi.notes)
    assert all(b.refs for b in pi.boards) and pi.to_dict()["view"] == inner.id


def test_board_stack_conf_and_aliases():
    segs = [(0, 600, 825, "a"), (0, 600, 850, "b"), (0, 600, 1200, "s")]
    lv = prim.board_stacks(segs, 0, 600, 0, 2400)
    assert [(b["z0"], b["conf"]) for b in lv] == [(825, 1.0), (1200, 0.7)]
    assert interior.levels is prim.board_stacks  # tên cũ vẫn dùng được


def test_meanings_lists_all():
    kws = drafting.effective(None)["keywords"]
    d = type("D", (), {"keywords": kws})()
    ms = prim.meanings(d, "GHI CHÚ KHẤU 2 CẠNH BÊN TỦ MINIBAR CHO THOÁT HƠI TỦ LẠNH")
    assert "curve" in ms and "appliance" in ms and prim.meaning(d, "TỦ LẠNH MINI") == "appliance"
