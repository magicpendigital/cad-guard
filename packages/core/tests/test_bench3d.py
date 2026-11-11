"""Bộ đáp án đo độ chính xác dựng 3D (bước 3) + chiều sâu ghi trên mặt bằng. Chỉ DXF tổng hợp."""
from __future__ import annotations

import json

import pytest

from cadguard import bench3d, fixtures
from cadguard.dxf_reader import read_dxf


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))
    root = tmp_path / "ws"
    root.mkdir()
    fixtures.make_company_kitchen(root / "bep.dxf")
    return root


def test_score_matches_and_tolerance():
    ans = [{"x": 0, "w": 1200, "d": 600, "h": 2400, "z0": 0, "form": "cabinet", "fronts": 2},
           {"x": 1200, "w": 600, "d": 600, "h": 2400, "z0": 0, "form": "cabinet", "fronts": 3}]
    same = bench3d.score([dict(a) for a in ans], ans)
    assert same["score"] == 1.0 and same["count_ok"] and same["dims_pct"]["d"] == 100
    merged = bench3d.score([{"x": 0, "w": 1800, "d": 560, "h": 2400, "z0": 0, "form": "cabinet", "fronts": 5}], ans)
    assert merged["score"] == 0.0 and not merged["count_ok"] and merged["dims_pct"]["h"] == 50
    close = bench3d.score([{**ans[0], "w": 1201.5}, {**ans[1], "d": 590}], ans)
    assert close["correct"] == 1 and close["dims_pct"]["w"] == 100 and close["dims_pct"]["d"] == 50


def test_save_answer_and_run_pipelines(ws):
    from cadguard.app import scene_api

    m = read_dxf(ws / "bep.dxf")
    r = scene_api.save_answer(m, ws, "SYN.10", "kỹ thuật đã kiểm", "bep.dxf")
    assert r["saved"] and r["modules"] == 2
    data = json.loads(bench3d.answer_path(ws, m.file_hash, "SYN.10").read_text(encoding="utf-8"))
    assert data["schema"] == bench3d.SCHEMA and data["created_by"] == "user"
    out = bench3d.run(ws, lambda ans: bench3d.find_model(ws, ans, read_dxf))
    assert out["answers"] == 1 and out["summary"]["code"]["score_pct"] == 100
    assert set(out["summary"]) == {"code", "code+suggest"}
    # đáp án khác bản dựng (vd. người kỹ thuật ghi sâu tủ treo 320): điểm giảm, chỉ rõ số sâu sai
    data["modules"][1]["d"] = 320.0
    bench3d.answer_path(ws, m.file_hash, "SYN.10").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = bench3d.run(ws, lambda ans: bench3d.find_model(ws, ans, read_dxf))
    assert out["summary"]["code"]["score_pct"] == 50 and out["summary"]["code"]["dims_pct"]["d"] == 50


def test_app_bench_and_missing_drawing(ws):
    from cadguard.app import AppConfig, CadGuardApp, api

    app = CadGuardApp(AppConfig(workspace=ws), cli_detect=lambda n: {"installed": None})
    api.scene_action(app.d(), "bep.dxf", "answer", {"item": "SYN.10"})
    r = api.bench3d(app.d())
    assert r["answers"] == 1 and r["summary"]["code"]["items"] == 1
    (ws / "bep.dxf").unlink()
    r = api.bench3d(app.d())
    assert "skipped" in r["rows"][0]


def test_depth_from_plan_dimension_when_outline_does_not_match(tmp_path):
    """Mặt bằng không vẽ đường bao khớp khối nhưng có ghi kích thước sâu: lấy số ghi (nguồn kích thước)."""
    import ezdxf

    from cadguard.scene.assemble import build_item_scene
    from cadguard.scene.views2d import read_drawing

    p = tmp_path / "k.dxf"
    fixtures.make_company_kitchen(p)
    doc = ezdxf.readfile(p)
    for e in doc.modelspace().query("LWPOLYLINE"):
        pts = [tuple(x[:2]) for x in e.get_points()]
        if e.dxf.layer == "SYN_Noithat" and len(pts) == 4 and min(y for _x, y in pts) == 600.0:  # đường bao tủ dưới trên mặt bằng
            doc.modelspace().delete_entity(e)
    doc.saveas(p)
    sc = build_item_scene(read_drawing(read_dxf(p)), "SYN.10")
    lower = min(sc.modules, key=lambda x: x.z0)
    assert lower.d == 600.0 and lower.src["d"].kind == "dimension" and lower.src["d"].refs
