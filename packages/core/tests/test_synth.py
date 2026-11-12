"""Bộ dữ liệu mô phỏng: agent thiết kế (code + AI có kiểm luật), bộ vẽ nhiều kiểu trình bày, đáp án, chấm bench3d."""
from __future__ import annotations

import json

import pytest

from cadguard import bench3d, synth
from cadguard.dxf_reader import read_dxf


@pytest.fixture(autouse=True)
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))


def test_specs_follow_rules_and_are_reproducible():
    a, b = synth.design_specs(9, seed=3), synth.design_specs(9, seed=3)
    assert a == b and {s["kind"] for s in a} == {"wardrobe", "kitchen", "tv"}
    assert all(not synth.validate_spec(s) for s in a)
    bad = {"modules": [{"w": 1000, "d": 600, "h": 2400, "z0": 0, "form": "cabinet",
                        "fronts": [{"kind": "door", "x0": 0, "x1": 1000, "z0": 0, "z1": 2400}]}]}
    assert any("cánh rộng" in e for e in synth.validate_spec(bad))


def test_each_style_draws_and_scores(tmp_path):
    spec = synth.design_specs(1, seed=2)[0]
    for key in synth.STYLES:
        keys = ["chuan"] if key == "chuan" else ["chuan", key]
        out = tmp_path / key
        out.mkdir()
        ans = synth.draw(spec, keys, out / "x.dxf")
        assert ans["modules"] and read_dxf(out / "x.dxf").file_hash


def test_generate_and_bench_full_score_with_suggestions(tmp_path):
    out = tmp_path / "mp"
    r = synth.generate(out, n=6, seed=11)
    assert len(r["items"]) == 6 and len(list((out / ".cadguard" / "answers").glob("*.json"))) == 6
    res = bench3d.run(out, lambda ans: bench3d.find_model(out, ans, read_dxf))
    assert res["answers"] == 6 and res["summary"]["code+suggest"]["score_pct"] == 100
    a = json.loads(next((out / ".cadguard" / "answers").glob("*.json")).read_text(encoding="utf-8"))
    assert a["created_by"] == "synth" and a["styles"][0] == "chuan"


def test_depth_only_in_section_is_read_by_code(tmp_path):
    spec = next(s for s in synth.design_specs(3, seed=5) if s["kind"] == "tv")
    out = tmp_path / "s"
    out.mkdir()
    ans = synth.draw(spec, ["chuan", "sauomatcat"], out / "tv.dxf")
    m = read_dxf(out / "tv.dxf")
    p = bench3d.answer_path(out, m.file_hash, spec["id"])
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"schema": bench3d.SCHEMA, "source_hash": m.file_hash, "file": "tv.dxf", "item": spec["id"],
                             "modules": ans["modules"]}, ensure_ascii=False), encoding="utf-8")
    res = bench3d.run(out, lambda a: bench3d.find_model(out, a, read_dxf))
    # P5: mặt cắt có ký hiệu trên mặt đứng -> code tự đọc sâu, không cần bước gợi ý
    assert res["summary"]["code"]["dims_pct"]["d"] == 100 and res["summary"]["code+suggest"]["score_pct"] == 100


def test_ai_designer_specs_are_validated():
    class Fake:
        def complete(self, system, messages):
            assert "kỹ sư thiết kế" in system
            return json.dumps({"specs": [
                {"name": "TỦ GIÀY", "kind": "wardrobe", "room_h": 2700, "modules": [
                    {"w": 800, "d": 350, "h": 1000, "z0": 0, "form": "cabinet", "shelves": 3,
                     "fronts": [{"kind": "door", "x0": 0, "x1": 400, "z0": 0, "z1": 1000}, {"kind": "door", "x0": 400, "x1": 800, "z0": 0, "z1": 1000}]}]},
                {"name": "SAI", "kind": "wardrobe", "modules": [{"w": 900, "d": 600, "h": 2400, "z0": 0, "form": "cabinet",
                                                                 "fronts": [{"kind": "door", "x0": 0, "x1": 900, "z0": 0, "z1": 2400}]}]}]})

    ok, bad = synth.design_specs_ai(Fake(), ["tủ giày 2 cánh"])
    assert [s["name"] for s in ok] == ["TỦ GIÀY"] and bad[0]["errors"]


def test_cli_synth(tmp_path, capsys):
    from cadguard.cli import main

    assert main(["synth", "--out", str(tmp_path / "c"), "--n", "3", "--seed", "4"]) == 0
    assert "Đã sinh 3 hạng mục" in capsys.readouterr().out
