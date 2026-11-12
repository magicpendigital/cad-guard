"""Bộ chạy luồng xử lý theo hạng mục: các bước, leo thang AI chỉ khi code chưa giải xong, lưu/dùng lại kết quả. Chỉ DXF
tổng hợp."""
from __future__ import annotations

import json

import pytest

from cadguard import fixtures, pipeline
from cadguard.dxf_reader import read_dxf


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))
    root = tmp_path / "ws"
    root.mkdir()
    fixtures.make_company_kitchen(root / "bep.dxf")
    return root, read_dxf(root / "bep.dxf")


def test_run_item_steps_and_cache(ws):
    root, m = ws
    r = pipeline.run_item(m, root, "SYN.10")
    ids = [s["id"] for s in r["steps"]]
    assert ids == [s for s, _l, _k in pipeline.STEPS] and not r["cached"]
    st = {s["id"]: s for s in r["steps"]}
    assert st["build"]["out"]["modules"] == 2 and st["ai"]["status"] == "skipped"
    assert st["structure"]["out"]["auto"] == 2  # vách ngăn giữa hai cặp cánh, tủ trên và tủ dưới
    again = pipeline.run_item(m, root, "SYN.10")
    assert again["cached"] and again["key"] == r["key"]
    assert len(pipeline.history(root, m.file_hash, "SYN.10")) == 1
    pipeline.run_item(m, root, "SYN.10", force=True)
    assert len(pipeline.history(root, m.file_hash, "SYN.10")) == 2


def test_ai_only_when_code_left_work(ws, tmp_path):
    root, _m = ws
    calls = []

    class Fake:
        def complete(self, system, messages):
            calls.append(1)
            return json.dumps({"proposals": []})

    # bếp đủ số: AI không được gọi
    r = pipeline.run_item(_m, root, "SYN.10", backend=Fake())
    assert next(s for s in r["steps"] if s["id"] == "ai")["status"] == "skipped" and not calls
    # tủ treo thiếu chiều sâu (bỏ nét khuất): AI được gọi, kết quả qua bộ kiểm
    p = tmp_path / "k2" / "bep.dxf"
    p.parent.mkdir()
    fixtures.make_company_kitchen(p)
    from cadguard import drafting

    drafting.save(p.parent, "project", {"layer_roles": {"SYN_Khuat": "other", "SYN_Netcat": "other"}})
    r2 = pipeline.run_item(read_dxf(p), p.parent, "SYN.10", backend=Fake())
    ai = next(s for s in r2["steps"] if s["id"] == "ai")
    assert calls and ai["status"] in ("ok", "needs_review") and r2["state"] == "needs_review"


def test_app_pipeline_job(ws):
    import time

    from cadguard.app import AppConfig, CadGuardApp, pipeline_api

    root, _m = ws
    app = CadGuardApp(AppConfig(workspace=root), cli_detect=lambda n: {"installed": None})
    job = pipeline_api.start(app.d(), "bep.dxf", False, False, None)
    for _ in range(200):
        job = pipeline_api.status(job["id"])
        if job["state"] != "running":
            break
        time.sleep(0.05)
    assert job["state"] == "done" and job["result"]["items"] == 1 and job["result"]["rows"][0]["name"]
    h = pipeline_api.item_history(app.d(), "bep.dxf", "SYN.10")
    assert h["runs"]
