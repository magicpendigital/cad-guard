"""Chuẩn hoá trước khi dựng 3D + dòng phiên bản. Chỉ DXF tổng hợp.

- Khung tên không có số bản vẽ: nhóm hạng mục theo tên đồ trong tiêu đề hình.
- Số thiếu: code đọc mặt cắt, AI đề xuất phải dẫn đúng kích thước/chữ trên bản vẽ (harness), người dùng xác nhận.
- Dòng phiên bản: bản gốc → tệp mới của từng lệnh; bản đang dùng, hoàn tác/làm lại không xoá tệp.
"""
from __future__ import annotations

import json

import ezdxf
import pytest

from cadguard import fixtures
from cadguard.dxf_reader import read_dxf
from cadguard.scene.assemble import build_item_scene
from cadguard.scene.proposals import code_suggestions, validate
from cadguard.scene.views2d import read_drawing


def _no_numbers(path):
    doc = ezdxf.readfile(path)
    for ins in doc.modelspace().query("INSERT"):
        for a in list(ins.attribs):
            if a.dxf.tag == "SO_BAN_VE":
                a.dxf.text = ""
    doc.saveas(path)


def test_groups_by_title_when_frame_has_no_number(tmp_path):
    p = tmp_path / "k.dxf"
    fixtures.make_company_kitchen(p)
    _no_numbers(p)
    d = read_drawing(read_dxf(p))
    g = next(k for k in d.groups if k.startswith("~") and "TỦ BẾP SYN" in k)
    assert d.groups[g]["by_title"] and d.views_of(g, "plan") and d.views_of(g, "elevation")
    sc = build_item_scene(d, g)
    assert len(sc.modules) == 2  # dựng được như khi có số bản vẽ


@pytest.fixture
def kitchen_no_hidden(tmp_path):
    p = tmp_path / "k.dxf"
    fixtures.make_company_kitchen(p)
    m = read_dxf(p)
    from cadguard.scene.views2d import read_drawing as rd

    # không còn nét khuất ở mặt bằng, mặt cắt không còn nét thân tủ (chỉ kích thước) -> code không tự đọc được sâu tủ treo
    d = rd(m, roles={"SYN_Khuat": "other", "SYN_Netcat": "other"})
    return m, d, build_item_scene(d, "SYN.10")


def test_code_reads_depth_from_section(kitchen_no_hidden):
    _m, d, sc = kitchen_no_hidden
    gap = next(g for g in sc.gaps if g.id.startswith("module:"))
    sug = code_suggestions(d, "SYN.10", sc)
    assert sug and sug[0]["key"] == gap.fields[0].key and sug[0]["evidence"]
    ok, bad = validate(sug, d, "SYN.10", sc)
    assert ok and not bad and ok[0]["origin"] == "code"


def test_ai_numbers_need_matching_evidence(kitchen_no_hidden):
    _m, d, sc = kitchen_no_hidden
    key = next(g for g in sc.gaps if g.id.startswith("module:")).fields[0].key
    sec = d.views_of("SYN.10", "section")[0]
    dim = next(h for h in sec.handles if d.entities[h].type == "DIMENSION" and abs((d.entities[h].dim_value or 0) - 600) < 1)
    raw = [{"key": key, "value": "600", "evidence": [dim], "reason": "mặt cắt Y1"},
           {"key": key, "value": "350", "evidence": [dim], "reason": "đoán"},  # số không khớp bằng chứng
           {"key": key, "value": "350", "reason": "đoán"},  # không bằng chứng
           {"key": "module:M9:w", "value": "100", "evidence": [dim]}]  # không phải ô phần thiếu
    ok, bad = validate(raw, d, "SYN.10", sc)
    assert [p["value"] for p in ok] == ["600"] and len(bad) == 3
    assert {b["rejected"] for b in bad} >= {"thiếu bằng chứng (handle kích thước/chữ trên bản vẽ)"}


def test_scene_ai_job_with_fake_llm(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))
    from cadguard.app import AppConfig, CadGuardApp, scene_ai

    root = tmp_path / "ws"
    root.mkdir()
    fixtures.make_company_kitchen(root / "bep.dxf")
    app = CadGuardApp(AppConfig(workspace=root), cli_detect=lambda n: {"installed": None})

    class Fake:
        def complete(self, system, messages):
            ctx = json.loads(messages[0]["content"])
            assert "evidence" in ctx and "Số PHẢI đọc" in system
            return json.dumps({"proposals": [{"key": "label:M1", "value": "tủ bếp dưới", "reason": "ở sàn"}]})

    job = scene_ai.start(app.d(), "bep.dxf", "SYN.10", True, Fake())
    for _ in range(100):
        if job["state"] != "running":
            break
        import time

        time.sleep(0.05)
        job = scene_ai.status(job["id"])
    assert job["state"] == "done" and job["accepted"] >= 1


def _apply_log(root, cid, src, dst, at, ops=("convert_unicode",)):
    d = root / ".cadguard" / "changesets"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{cid}.apply.json").write_text(json.dumps({"schema": "cg.changeset-apply/1", "changeset_id": cid, "applied_at": at,
                                                     "source": {"path": src, "sha256": "x"}, "output": {"path": dst, "sha256": "y"},
                                                     "ops": [{"op": o} for o in ops]}), encoding="utf-8")
    (root / dst).write_text("0\nEOF\n", encoding="utf-8")


def test_version_family_current_undo_redo(tmp_path):
    from cadguard.app import versions

    (tmp_path / "a.dxf").write_text("0\nEOF\n", encoding="utf-8")
    _apply_log(tmp_path, "cs-1", "a.dxf", "a.cg-1.dxf", "2026-11-11T01:00:00")
    _apply_log(tmp_path, "cs-2", "a.cg-1.dxf", "a.cg-1.zhlayer.dxf", "2026-11-11T02:00:00", ("add_texts",))
    i = versions.info(tmp_path, "a.dxf")
    assert i["state"] == "old" and i["current"] == "a.cg-1.zhlayer.dxf" and [v["path"] for v in i["versions"]][0] == "a.dxf"
    assert versions.overview(tmp_path)["a.cg-1.zhlayer.dxf"]["state"] == "current"
    u = versions.undo(tmp_path, "a.cg-1.zhlayer.dxf")
    assert u["current"] == "a.cg-1.dxf" and u["redo"] == ["a.cg-1.zhlayer.dxf"]
    assert (tmp_path / "a.cg-1.zhlayer.dxf").is_file()  # hoàn tác không xoá tệp
    r = versions.redo(tmp_path, "a.dxf")
    assert r["current"] == "a.cg-1.zhlayer.dxf"
    s = versions.set_current(tmp_path, "a.dxf", "a.dxf")
    assert s["current"] == "a.dxf" and s["state"] == "current"
    with pytest.raises(ValueError):
        versions.undo(tmp_path, "a.dxf")
    with pytest.raises(ValueError):
        versions.set_current(tmp_path, "a.dxf", "khac.dxf")
    assert versions.info(tmp_path, "b.dxf")["state"] == "single"
