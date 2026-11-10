"""Đồ thị tri thức bản vẽ cg.drawing-graph/1 + cổng sẵn sàng (P1). Chỉ DXF tổng hợp."""
from __future__ import annotations

import json

from cadguard.dxf_reader import read_dxf
from cadguard.graph import SCHEMA, build_graph, materials_in, summary_vi
from cadguard.scene.views2d import read_drawing


def _kitchen(synthetic):
    m = read_dxf(synthetic / "scene" / "company_kitchen.dxf")
    return m, read_drawing(m)


def test_graph_nodes_edges_and_provenance(synthetic):
    m, d = _kitchen(synthetic)
    g = build_graph(m, drawing=d)
    assert g["schema"] == SCHEMA and g["source_hash"] == m.file_hash
    types = {n["type"] for n in g["nodes"]}
    assert {"sheet", "view", "item", "module"} <= types
    ids = {n["id"] for n in g["nodes"]}
    for e in g["edges"]:  # mọi cạnh trỏ tới nút có thật
        assert e["from"] in ids and e["to"] in ids, e
    for n in g["nodes"]:
        assert n["source"] == "code" and n["status"] == "measured" and 0 < n["confidence"] <= 1
    item = next(r for r in g["items"] if r["id"] == "SYN.10")
    assert item["modules"] == 2 and item["status"] == "đủ" and item["plans"] >= 1 and item["elevations"] >= 1
    assert any(e["type"] == "aligned_with" for e in g["edges"])
    json.dumps(g, ensure_ascii=False)  # lưu được


def test_gates_turn_gaps_into_tasks_with_fixes(synthetic):
    m, d = _kitchen(synthetic)
    plan = next(v for v in d.views if v.group == "SYN.10" and v.kind == "plan")
    for h in list(plan.handles):  # bỏ kích thước ở mặt bằng: mặt đứng không ghép được -> việc cần làm
        if d.entities[h].type == "DIMENSION":
            plan.handles.remove(h)
    g = build_graph(m, drawing=d)
    gate3d = next(x for x in g["gates"] if x["id"] == "3d")
    assert gate3d["status"] != "ok" and gate3d["task_count"] >= 1
    t = next(x for x in gate3d["tasks"] if x["action"] == {"id": "open3d", "item": "SYN.10"})
    assert t["title"] and t["why"] and t["fix_here"] and t["fix_cad"]
    assert "V:" not in t["where"]  # nói bằng tên hình/tờ, không bằng mã máy
    prod = next(x for x in g["gates"] if x["id"] == "production")
    assert prod["status"] == "blocked"  # chưa có hồ sơ kết cấu công ty (P3)
    assert "Dựng 3D hình khối" in summary_vi(g)


def test_supplement_closes_gap(synthetic):
    m, d = _kitchen(synthetic)
    plan = next(v for v in d.views if v.group == "SYN.10" and v.kind == "plan")
    elev = next(v for v in d.views if v.group == "SYN.10" and v.kind == "elevation")
    for h in list(plan.handles):
        if d.entities[h].type == "DIMENSION":
            plan.handles.remove(h)
    g = build_graph(m, drawing=d, supplement={f"link:{elev.id}": plan.id})
    assert next(r for r in g["items"] if r["id"] == "SYN.10")["modules"] == 2


def test_materials_in_notes():
    assert materials_in("THÙNG, CÁNH TỦ MDF 17MM CHỐNG ẨM PHỦ LAMINATE") == ["MDF", "Laminate"]
    assert materials_in("CÁNH KÍNH CƯỜNG LỰC 8MM") == ["Kính"]
    assert materials_in("MẶT ĐÁ GRANITE ĐEN") == ["Đá"]
    assert materials_in("MẶT ĐỨNG HƯỚNG A") == []


def test_cli_graph(synthetic, capsys, tmp_path):
    from cadguard.cli import main

    out = tmp_path / "g.json"
    assert main(["graph", str(synthetic / "scene" / "company_kitchen.dxf"), "--out", str(out)]) == 0
    assert "Đồ thị bản vẽ" in capsys.readouterr().out
    assert json.loads(out.read_text(encoding="utf-8"))["schema"] == SCHEMA


def test_app_graph_api_caches_by_content(synthetic, tmp_path):
    import shutil

    from cadguard.app import AppConfig, CadGuardApp

    root = tmp_path / "ws"
    root.mkdir()
    shutil.copy(synthetic / "scene" / "company_kitchen.dxf", root / "bep.dxf")
    app = CadGuardApp(AppConfig(workspace=root), cli_detect=lambda n: {"installed": None})
    from cadguard.app import api

    a = api.drawing_graph(app.d(), "bep.dxf")
    b = api.drawing_graph(app.d(), "bep.dxf")
    assert a["cached"] is False and b["cached"] is True and a["stats"] == b["stats"]
    assert list((root / ".cadguard" / "graph").glob("*.json"))
    assert api.drawing_graph(app.d(), "bep.dxf", True)["cached"] is False
