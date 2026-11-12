"""P7 — chỉ số "đúng không cần sửa" dựng 3D theo tuần / kiểu vẽ trên màn Tổng quan. Chỉ DXF tổng hợp."""
from __future__ import annotations

import json
from datetime import timedelta

import pytest

from cadguard import drafting, fixtures
from cadguard.app import history


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))
    root = tmp_path / "ws"
    root.mkdir()
    fixtures.make_company_kitchen(root / "bep.dxf")
    return root


def _ev(t, **kw):
    return {"event": "scene", "ts": t.isoformat(), "_t": t, **kw}


def test_weekly_latest_per_item_and_styles():
    now = history._now()
    w0 = history.week_start(now)
    last = w0 - timedelta(days=3)  # tuần trước
    ev = [
        _ev(last, file="f1", item="a", style="s1", edits=2, kinds={"dim": 2}, unsure=1),
        _ev(last + timedelta(hours=1), file="f1", item="b", style="s1", edits=0, unsure=0),
        _ev(w0 + timedelta(hours=1), file="f1", item="a", style="s1", edits=0, unsure=0),  # tuần này: a xác nhận lại, không sửa
        _ev(w0 + timedelta(hours=2), file="f2", item="c", style="-", edits=1, kinds={"split": 1}, unsure=2),
        _ev(w0 + timedelta(hours=3), file="f2", item="c", style="-", edits=1, kinds={"split": 1}, unsure=2),  # trùng: lấy mới nhất
        {"event": "bench", "ts": now.isoformat(), "_t": now, "answers": 3, "items": 3, "exact": 2, "score_pct": 80},
    ]
    q = history.scene_quality(ev, {"s1": "Công ty A"}.get)
    assert q["has_data"] and [w["items"] for w in q["weeks"]] == [2, 2]  # tuần trống trước đó bị bỏ
    prev, cur = q["weeks"]
    assert prev["ok"] == 1 and prev["pct"] == 50 and cur["ok"] == 1 and cur["pct"] == 50
    assert cur["bench"] == {"answers": 3, "items": 3, "exact": 2, "score_pct": 80} and prev["bench"] is None
    st = {s["style"]: s for s in q["styles"]}
    assert st["s1"]["name"] == "Công ty A" and st["s1"]["items"] == 2 and st["s1"]["pct"] == 100  # a mới nhất không sửa
    assert st["-"]["name"] is None and st["-"]["pct"] == 0
    assert q["kinds"] == {"split": 1} and q["total"]["items"] == 3
    assert history.scene_quality([], lambda s: None)["has_data"] is False


def test_drafting_name_and_known_names(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))
    assert drafting.effective(tmp_path)["name"] == ""
    drafting.save(tmp_path, "machine", {"name": "  Công ty   A "})
    p = drafting.save(tmp_path, "project", {"name": "Xưởng B"})
    assert p["name"] == "Xưởng B" and p["origin"]["name"] == "project"
    drafting.save(tmp_path, "project", {"name": ""})  # bỏ tên dự án -> về tên cả máy
    assert drafting.effective(tmp_path)["name"] == "Công ty A"
    assert set(drafting.known_names(tmp_path)) >= {"Công ty A", "Xưởng B"}
    with pytest.raises(ValueError):
        drafting.save(tmp_path, "project", {"name": "x" * 61})


def test_edit_counts_by_kind(ws):
    from cadguard.app import scene_api
    from cadguard.dxf_reader import read_dxf

    m = read_dxf(ws / "bep.dxf")
    v = scene_api.view(m, ws, "SYN.10")
    assert v["edits"] == {"total": 0, "kinds": {}}
    mid = v["modules"][0]["id"]
    v = scene_api.set_value(m, ws, "SYN.10", f"module:{mid}:d", 500)
    assert v["edits"] == {"total": 1, "kinds": {"dim": 1}}
    info = scene_api.confirm_info(m, ws, "SYN.10")
    assert info["edits"] == 1 and info["modules"] == 2 and info["ms"] >= 0 and 0 <= info["dim_pct"] <= 100
    v = scene_api.set_value(m, ws, "SYN.10", f"module:{mid}:d", "reset")
    assert v["edits"]["total"] == 0


def test_app_confirm_answer_bench_and_overview(ws):
    from cadguard.app import AppConfig, CadGuardApp, api

    app = CadGuardApp(AppConfig(workspace=ws), cli_detect=lambda n: {"installed": None})
    d = app.d()
    assert api.scene3d(d, "bep.dxf", "SYN.10")["confirmed"] is None
    r = api.scene_action(d, "bep.dxf", "confirm", {"item": "SYN.10"})
    assert r["edits"] == 0 and r["confirmed"]["edits"] == 0
    assert api.scene3d(d, "bep.dxf", "SYN.10")["confirmed"]["edits"] == 0
    drafting.save(ws, "project", {"name": "Công ty mô phỏng"})
    api.scene_action(d, "bep.dxf", "answer", {"item": "SYN.10"})  # đáp án = một lần xác nhận
    api.bench3d(d)
    ev = d.history.read()
    sc = [e for e in ev if e["event"] == "scene"]
    assert len(sc) == 2 and sc[-1]["answer"] is True and sc[0]["style"] == "-" and sc[-1]["style"] != "-"
    raw = (ws / ".cadguard" / "history.jsonl").read_text(encoding="utf-8")
    assert "SYN.10" not in raw and "bep" not in raw and json.dumps("Công ty mô phỏng")[1:-1] not in raw  # lịch sử ghi ASCII
    b = [e for e in ev if e["event"] == "bench"][-1]
    assert b["items"] == 1 and b["exact"] == 1 and b["score_pct"] == 100
    q = app.overview()["scene"]
    assert q["total"] == {**q["total"], "items": 1, "ok": 1, "pct": 100}
    assert q["styles"][0]["name"] == "Công ty mô phỏng" and q["weeks"][-1]["bench"]["exact"] == 1
