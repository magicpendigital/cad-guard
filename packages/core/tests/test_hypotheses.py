"""L4 (P4) — sinh cách hiểu + chọn theo điểm (`scene/hypotheses.py`), thẻ "máy phân vân" (`/api/scene/decide`).
Chỉ DXF tổng hợp (`synth`)."""
from __future__ import annotations

import pytest

from cadguard import drafting, synth
from cadguard.dxf_reader import read_dxf
from cadguard.scene import hypotheses as hyp
from cadguard.scene.assemble import Module2, Scene2, Src, build_item_scene, build_once
from cadguard.scene.consistency import check
from cadguard.scene.views2d import Drawing2D


@pytest.fixture(autouse=True)
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))


def _spec():
    return next(s for seed in range(1, 40) for s in synth.design_specs(9, seed=seed)
                if s["kind"] == "wardrobe" and any(m.get("use") == "hang" and m.get("inner_drawers") for m in s["modules"]))


def _drawing(tmp_path, styles=("trungtieude", "noithat")):
    spec = _spec()
    p = tmp_path / "x.dxf"
    ans = synth.draw(spec, ["chuan", *styles], p)
    return drafting.read(read_dxf(p), tmp_path), spec, ans, p


def _reverse_elevations(monkeypatch):
    """Đảo thứ tự mặt đứng: cách dựng một lần lấy nhầm hình bỏ cánh làm hình chính (như ca TESt 2)."""
    orig = Drawing2D.views_of

    def rev(self, group, kind=None):
        vs = orig(self, group, kind)
        return list(reversed(vs)) if kind == "elevation" else vs

    monkeypatch.setattr(Drawing2D, "views_of", rev)


def _fronts_ok(sc, ans):
    return [len(m.fronts) for m in sorted(sc.modules, key=lambda m: m.x)] == [a["fronts"] for a in ans["modules"]]


def test_wrong_view_order_is_fixed_by_scoring_not_by_rule(tmp_path, monkeypatch):
    d, spec, ans, _p = _drawing(tmp_path)
    _reverse_elevations(monkeypatch)
    once = build_once(d, spec["id"])
    assert not _fronts_ok(once, ans)  # một cách hiểu, không quy tắc riêng: sai
    sc = build_item_scene(d, spec["id"], {})
    assert _fronts_ok(sc, ans)
    role = next(r for r in sc._choice["decisions"] if r["id"] == "role")
    assert role["status"] == "auto" and role["gap"] >= hyp.MARGIN
    assert any(n.startswith("Máy chọn cách hiểu") for n in sc.notes)
    assert sc._choice["builds"] <= hyp.MAX_BUILDS
    assert build_item_scene(d, spec["id"], {}).scene_hash == sc.scene_hash  # tất định


def test_right_order_keeps_scene_and_no_card(tmp_path):
    d, spec, _ans, _p = _drawing(tmp_path)
    sc = build_item_scene(d, spec["id"], {})
    assert sc.model_dump(exclude={"notes", "scene_hash"}) == build_once(d, spec["id"]).model_dump(exclude={"notes", "scene_hash"})
    assert hyp.cards(sc) == []


def test_user_choice_pins_decision(tmp_path, monkeypatch):
    d, spec, ans, _p = _drawing(tmp_path)
    _reverse_elevations(monkeypatch)
    g = spec["id"]
    sc = build_item_scene(d, g, {f"decided:{g}": "role"})  # người dùng đã giữ cách hiểu ban đầu
    assert not _fronts_ok(sc, ans) and not any(r["id"] == "role" for r in ((sc._choice or {}).get("decisions") or []))


def test_single_elevation_has_no_role_decision(tmp_path):
    d, spec, _ans, _p = _drawing(tmp_path, ())
    sc = build_item_scene(d, spec["id"], {})
    assert not any(r["id"] == "role" for r in ((sc._choice or {}).get("decisions") or []))


def test_tall_inner_drawer_is_conflict():
    m = Module2(id="M1", kind="tall", form="cabinet", x=0, y=0, z0=0, w=1200, d=600, h=2400, elevation="E", interior="I",
                src={k: Src(kind="dimension") for k in ("w", "d", "h", "z0")},
                inner=[{"kind": "drawer", "x0": 18, "x1": 600, "z0": 100, "z1": 2000, "refs": ["d"]}])
    assert any(x["code"] == "K07" for x in check(Scene2(item="X", modules=[m]))["issues"])


def test_decide_api_pins_and_resets(tmp_path, monkeypatch):
    from cadguard.app import scene_api

    d, spec, ans, p = _drawing(tmp_path)
    _reverse_elevations(monkeypatch)
    model = read_dxf(p)
    v = scene_api.view(model, tmp_path, spec["id"])
    card = next(c for c in v["decisions"] if c["id"] == "role")
    assert card["status"] == "auto" and all("keys" not in o for o in card["options"])
    kept = scene_api.decide(model, tmp_path, spec["id"], "role", 0)  # giữ cách hiểu ban đầu (sai) theo ý người dùng
    assert not any(c["id"] == "role" for c in kept["decisions"])
    assert scene_api.read_supplement(tmp_path, model.file_hash)[f"decided:{spec['id']}"] == "role"
    back = scene_api.decide(model, tmp_path, spec["id"], "role", -1)  # để máy tự chọn lại
    assert any(c["id"] == "role" for c in back["decisions"])
    best = next(o["index"] for o in card["options"] if o["chosen"])
    picked = scene_api.decide(model, tmp_path, spec["id"], "role", best)
    vals = scene_api.read_supplement(tmp_path, model.file_hash)
    assert vals[f"main:{spec['id']}"] and vals[f"interior:{spec['id']}"]
    assert picked["counts"]["fronts"] == sum(a["fronts"] for a in ans["modules"])
    with pytest.raises(scene_api.SceneApiError):
        scene_api.decide(model, tmp_path, spec["id"], "role", 99)
