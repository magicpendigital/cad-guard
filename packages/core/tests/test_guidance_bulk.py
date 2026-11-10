"""Thông báo lỗi có hướng dẫn khắc phục + Sửa hàng loạt (bắt buộc sao lưu). Chỉ DXF tổng hợp."""
from __future__ import annotations

import re
from pathlib import Path

from cadguard.app import start_in_thread
from cadguard.app.guidance import ACTION_IDS, all_hints, hint_for
from cadguard.app.server import STATIC_DIR
from cadguard.changeset.diff import sha256_file

from test_app import Client, make_app, ws  # noqa: F401 - fixture dùng chung


def _served(root: Path):
    app = make_app(root, anonymize=False)
    srv, _t = start_in_thread(app)
    return app, srv, Client(app)


def test_every_hint_action_exists_in_ui():
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    block = js[js.index("const NOTICE_ACTIONS"):js.index("function notice(")]
    ui = set(re.findall(r"^\s{4}(\w+): \{run:", block, re.M))
    assert ui == ACTION_IDS
    for h in all_hints():
        assert h["title"] and h["steps"], h
        assert {a["id"] for a in h["actions"]} <= ACTION_IDS


def test_known_errors_get_specific_guidance():
    assert "tự kiểm" in hint_for("Kiểm tệp ra KHÔNG ĐẠT, không tạo tệp mới: abc")["title"]
    assert hint_for("Tệp gốc đã thay đổi sau khi đề xuất (mã băm không khớp)")["actions"][0]["id"] == "repropose"
    assert hint_for("Quá 3000 chuỗi chữ; hãy dịch theo tờ (--sheets).")["actions"][0]["id"] == "sheets"
    assert hint_for("điều gì đó lạ")["title"] == "Chưa thực hiện được"
    assert "bên trong" in hint_for("x", 500)["title"]


def test_api_errors_carry_hint(ws):  # noqa: F811
    app, srv, c = _served(ws)
    try:
        status, _h, body = c.post("/api/changeset/apply", {"changeset_id": "cs-000000000000", "confirm": True})
        assert status >= 400 and body["error"] and body["hint"]["title"] and body["hint"]["steps"]
    finally:
        srv.shutdown()
        srv.server_close()


def test_bulk_fix_plans_dry_run_then_requires_backup(ws):  # noqa: F811
    app, srv, c = _served(ws)
    src = ws / "hygiene_bad.dxf"
    sha = sha256_file(src)
    try:
        status, _h, p = c.post("/api/fix/bulk/plan", {"file": "hygiene_bad.dxf", "dept": "ky-thuat"})
        assert status == 200, p
        assert p["picked"] and p["preview"]["ok"]
        ops = [o["op"]["op"] for o in p["picked"]]
        assert ops[-1] == "purge_unused" or "purge_unused" not in ops  # dọn định nghĩa luôn ở cuối
        assert not list(ws.glob("hygiene_bad.cg-*.dxf"))  # chạy khô: chưa ghi gì
        cid = p["preview"]["changeset_id"]

        status, _h, body = c.post("/api/fix/bulk/apply", {"changeset_id": cid, "confirm": True, "backup": False})
        assert status == 409 and "sao lưu" in body["error"]
        assert not (ws / ".cadguard" / "backups").exists()

        status, _h, r = c.post("/api/fix/bulk/apply", {"changeset_id": cid, "confirm": True, "backup": True})
        assert status == 200, r
        bk = ws / r["backup"]["path"]
        assert bk.is_file() and sha256_file(bk) == sha == r["backup"]["sha256"]
        assert sha256_file(src) == sha  # gốc không đổi
        assert (ws / r["output"]["path"]).is_file() and r["validation"]["ok"]
    finally:
        srv.shutdown()
        srv.server_close()


def test_bulk_fix_renames_xref_residue_layer_when_no_base():
    from cadguard.app.bulkfix import _auto_target

    o = {"rule_id": "VS-01", "op": {"op": "merge_layers", "sources": ["X1$0$A-FUR"], "target": ""}, "choices": {"target": []},
         "checked": False, "title": "", "description": ""}
    r = _auto_target(o, {"0"})
    assert r["op"] == {"op": "rename_layer", "from": "X1$0$A-FUR", "to": "A-FUR"} and r["checked"]
    assert _auto_target(o, {"a-fur"}) is o  # đã có layer gốc: để người chọn gộp
    m = _auto_target(o, {"a-fur"}, {"a-fur"})  # vừa đổi tên ra A-FUR trong cùng lần sửa: gộp vào đó
    assert m["op"] == {"op": "merge_layers", "sources": ["X1$0$A-FUR"], "target": "A-FUR"}
    n = {**o, "op": {**o["op"], "sources": ["XR A3$0$KT$0$Khung"]}}
    assert _auto_target(n, set())["op"]["to"] == "Khung"  # xref lồng: lấy tên cuối
