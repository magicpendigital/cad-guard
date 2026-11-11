"""P2: đề xuất bổ sung đồ thị bản vẽ (code + AI) qua harness, người dùng xác nhận. Chỉ DXF tổng hợp."""
from __future__ import annotations

import json

import ezdxf
import pytest

from cadguard import fixtures, graph_ai
from cadguard.agent import registry
from cadguard.agent.anonymize import Anonymizer
from cadguard.agent.tools import ToolContext
from cadguard.agent.workspace import Workspace
from cadguard.app import scene_api
from cadguard.dxf_reader import read_dxf
from cadguard.graph import build_graph
from cadguard.scene.views2d import read_drawing

NOTE = "THÙNG, CÁNH, HẬU TỦ MDF 17MM CHỐNG ẨM"


@pytest.fixture
def kitchen(tmp_path):
    """Bếp tổng hợp + ghi chú vật liệu trên tờ SYN.10 + mặt bằng bỏ kích thước (mặt đứng không tự ghép được)."""
    src = tmp_path / "src.dxf"
    fixtures.make_company_kitchen(src)
    doc = ezdxf.readfile(src)
    msp = doc.modelspace()
    d = read_drawing(read_dxf(src))
    elev = next(v for v in d.views if v.group == "SYN.10" and v.kind == "elevation")
    plan = next(v for v in d.views if v.group == "SYN.10" and v.kind == "plan")
    title = next(e for e in msp.query("TEXT MTEXT") if "MẶT ĐỨNG" in (e.dxf.get("text", "") or getattr(e, "text", "")))
    x, y = elev.box[0], elev.box[1] - 300
    msp.add_text(NOTE, dxfattribs={"layer": title.dxf.layer, "style": title.dxf.get("style", "Standard"),
                                   "height": 50, "insert": (x, y)})
    for h in plan.handles:
        ent = doc.entitydb.get(h)
        if ent is not None and ent.dxftype() == "DIMENSION":
            msp.delete_entity(ent)
    root = tmp_path / "ws"
    root.mkdir()
    doc.saveas(root / "bep.dxf")
    return root, read_dxf(root / "bep.dxf")


def test_code_proposals_link_by_width_and_material_by_note(kitchen):
    root, m = kitchen
    d = read_drawing(m)
    props = graph_ai.code_proposals(d, {})
    kinds = {p["kind"] for p in props}
    assert {"link_views", "item_material"} <= kinds
    mat = next(p for p in props if p["kind"] == "item_material" and p["target"] == "SYN.10")
    assert mat["value"]["material"] == "MDF" and "thùng" in mat["value"]["component"] and "cánh" in mat["value"]["component"]
    st = graph_ai.run(d, {}, root, m.file_hash)
    assert st["items"] and not st["rejected"] and all(p["status"] == "proposed" for p in st["items"])


def test_decide_link_feeds_3d_and_material_feeds_graph(kitchen):
    root, m = kitchen
    st = graph_ai.run(read_drawing(m), {}, root, m.file_hash)
    before = build_graph(m)
    assert next(r for r in before["items"] if r["id"] == "SYN.10")["modules"] == 0
    link = next(p for p in st["items"] if p["kind"] == "link_views")
    mat = next(p for p in st["items"] if p["kind"] == "item_material" and p["target"] == "SYN.10")
    graph_ai.decide(m, root, link["id"], True)
    graph_ai.decide(m, root, mat["id"], True)
    supp = scene_api.read_supplement(root, m.file_hash)
    assert supp == {f"link:{link['target']}": link["value"]["plan"]}  # ghép hình ghi vào phần bổ sung 3D
    g = build_graph(m, supplement=supp, overrides=graph_ai.load_overrides(root, m.file_hash))
    assert next(r for r in g["items"] if r["id"] == "SYN.10")["modules"] == 2
    made = [e for e in g["edges"] if e["type"] == "made_of"]
    assert made and made[0]["source"] == "user" and made[0]["status"] == "confirmed" and "thùng" in made[0]["attrs"]["component"]
    st2 = graph_ai.load_proposals(root, m.file_hash)
    assert {p["id"]: p["status"] for p in st2["items"]}[link["id"]] == "confirmed"
    # chạy lại không làm mất quyết định
    st3 = graph_ai.run(read_drawing(m), supp, root, m.file_hash)
    assert all(p["status"] != "proposed" or p["id"] not in (link["id"], mat["id"]) for p in st3["items"])


def test_dismiss_writes_nothing(kitchen):
    root, m = kitchen
    st = graph_ai.run(read_drawing(m), {}, root, m.file_hash)
    p = st["items"][0]
    graph_ai.decide(m, root, p["id"], False)
    assert scene_api.read_supplement(root, m.file_hash) == {}
    ov = graph_ai.load_overrides(root, m.file_hash)
    assert not ov["view_kind"] and not ov["materials"] and not ov["issues"]


def test_harness_rejects_ungrounded_proposals(kitchen):
    _root, m = kitchen
    d = read_drawing(m)
    plan01 = next(v for v in d.views if v.group == "SYN.01" and v.kind == "plan")
    elev = next(v for v in d.views if v.group == "SYN.10" and v.kind == "elevation")
    typed = d.views[0]
    note_h = next(h for h, e in d.entities.items() if e.text and "MDF" in e.text)
    cases = [
        ({"kind": "view_kind", "target": typed.id, "value": {"kind": "plan"}, "evidence": []}, "đã có loại"),
        ({"kind": "link_views", "target": elev.id, "value": {"plan": plan01.id}, "evidence": []}, "khác hạng mục"),
        ({"kind": "item_material", "target": "SYN.10", "value": {"material": "Kính"}, "evidence": [note_h]}, "không nhắc"),
        ({"kind": "item_material", "target": "SYN.10", "value": {"material": "MDF"}, "evidence": ["FFFFFF"]}, "không có trong"),
        ({"kind": "item_material", "target": "SYN.10", "value": {"material": "MDF"}, "evidence": []}, "dẫn chứng"),
        ({"kind": "issue", "target": "KHONG-CO", "value": {"message": "x"}, "evidence": []}, "có thật"),
        ({"kind": "delete_layer", "target": "SYN.10", "value": {}, "evidence": []}, "không hợp lệ"),
    ]
    for p, why in cases:
        ok, reason, _q = graph_ai.check(p, d)
        assert not ok and why in reason, (p, reason)
    ok, _r, q = graph_ai.check({"kind": "item_material", "target": "SYN.10", "value": {"material": "MDF", "component": "thùng"},
                                "evidence": [note_h], "reason": "ghi chú", "confidence": 2}, d)
    assert ok and q["confidence"] == 1.0 and q["status"] == "proposed"


class ScriptedLLM:
    """AI giả: trả lời theo việc (đọc từ system prompt); một việc ném lỗi để thử cách ly lỗi."""

    name = "fake"

    def __init__(self, d, note_h):
        self.d, self.note_h, self.calls = d, note_h, []

    def complete(self, system, messages):
        ctx = json.loads(messages[0]["content"])
        self.calls.append(system[:40])
        if "ghép" in system or "candidates" in system:
            e = ctx["elevations"][0]
            return json.dumps({"proposals": [
                {"kind": "link_views", "target": e["elevation"], "value": {"plan": e["candidates"][0]["plan"]},
                 "evidence": [], "reason": "cùng tủ bếp", "confidence": 0.9}]})
        if "vật liệu" in system:
            return "```json\n" + json.dumps({"proposals": [
                {"kind": "item_material", "target": "SYN.10", "value": {"material": "MDF chống ẩm", "component": "thùng"},
                 "evidence": [self.note_h], "reason": "ghi chú vật liệu", "confidence": 0.8},
                {"kind": "item_material", "target": "SYN.10", "value": {"material": "Đá granite"}, "evidence": ["ABCDEF"],
                 "reason": "bịa", "confidence": 0.9}]}) + "\n```"
        if "soát" in system:
            raise RuntimeError("hết lượt")
        return '{"proposals": []}'


def test_llm_agents_go_through_harness_and_errors_are_isolated(kitchen):
    root, m = kitchen
    d = read_drawing(m)
    note_h = next(h for h, e in d.entities.items() if e.text and "MDF" in e.text)
    be = ScriptedLLM(d, note_h)
    st = graph_ai.run(d, {}, root, m.file_hash, backend=be)
    srcs = {p["id"]: p["sources"] for p in st["items"]}
    assert any("llm" in s and "code" in s for s in srcs.values())  # cùng đề xuất từ code và AI: gộp nguồn
    merged = [p for p in st["items"] if p["kind"] == "item_material" and p["value"].get("spec") == "MDF chống ẩm"]
    assert merged and merged[0]["sources"] == ["code", "llm"] and merged[0]["value"]["material"] == "MDF"  # gộp, giữ thông số AI
    assert len(st["rejected"]) == 1 and "không có trong" in st["rejected"][0]["why"]  # handle bịa bị loại
    review = next(r for r in st["runs"] if r["agent"] == "review")
    assert review["ok"] is False and "hết lượt" in review["error"]
    assert next(r for r in st["runs"] if r["agent"] == "materials")["ok"] is True


def test_app_suggest_proposals_decide_and_anonymized_ai_is_blocked(kitchen):
    from cadguard.app import AppConfig, CadGuardApp
    from cadguard.app import graph_api

    root, m = kitchen

    class Boom:
        name = "boom"

        def complete(self, system, messages):
            raise AssertionError("ẩn danh: không được gọi AI")

    app = CadGuardApp(AppConfig(workspace=root, anonymize=True), cli_detect=lambda n: {"installed": None},
                      translate_backend=Boom())
    job = graph_api.start(app.d(), "bep.dxf", True, app.translate_backend)
    assert job["state"] == "done" and job["ai"] is False and "ẩn danh" in job["note"]
    r = graph_api.proposals(app.d(), "bep.dxf")
    assert r["counts"]["proposed"] >= 2 and all(p["target_label"] for p in r["items"])
    link = next(p for p in r["items"] if p["kind"] == "link_views")
    assert "Mặt bằng" in link["value_label"]
    graph_api.decide(app.d(), "bep.dxf", link["id"], True)
    assert graph_api.proposals(app.d(), "bep.dxf")["counts"]["confirmed"] == 1
    from cadguard.app import api

    g = api.drawing_graph(app.d(), "bep.dxf")
    assert next(x for x in g["items"] if x["id"] == "SYN.10")["modules"] == 2


def test_get_drawing_graph_tool_anonymized_has_no_names(kitchen):
    root, _m = kitchen
    for anon in (True, False):
        ctx = ToolContext(workspace=Workspace(root), anonymizer=Anonymizer(enabled=anon))
        r = registry.call(ctx, "get_drawing_graph", {"file": "bep.dxf"}, registry.options_for(ctx))
        txt = r.text()
        data = json.loads(txt)
        assert data["schema"] == "cg.drawing-graph/1" and data["stats"]["sheets"] >= 2
        if anon:
            assert "SYN.10" not in txt and "TỦ BẾP" not in txt and "MDF" not in txt and "materials" not in data
        else:
            assert "SYN.10" in txt and any(x["name"] == "MDF" for x in data["materials"])



def test_claude_cli_answer_kept_when_only_post_answer_hook_fails(monkeypatch):
    """Máy có hook SessionEnd lỗi: CLI trả mã 1 dù đã trả lời xong. Dùng câu trả lời; lỗi thật vẫn báo lỗi."""
    import subprocess
    import types

    from cadguard.studio import llm

    monkeypatch.setattr(llm.shutil, "which", lambda name: "claude")
    be = llm.ClaudeCliBackend()
    out = {"stdout": json.dumps({"is_error": False, "result": '{"proposals": []}'}), "stderr": "SessionEnd hook failed", "rc": 1}
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: types.SimpleNamespace(returncode=out["rc"], stdout=out["stdout"],
                                                                                   stderr=out["stderr"]))
    assert be.complete("s", [{"role": "user", "content": "x"}]) == '{"proposals": []}'
    out.update(stdout=json.dumps({"is_error": True, "result": "Hết hạn mức"}), stderr="")
    with pytest.raises(llm.LlmError, match="Hết hạn mức"):
        be.complete("s", [{"role": "user", "content": "x"}])


def test_fallback_backend_moves_to_next_ai_and_remembers():
    from cadguard.studio.llm import FallbackBackend, LlmError

    class Broke:
        name = "a"

        def complete(self, s, m):
            raise LlmError("Credit balance is too low")

    class Ok:
        name = "b"
        n = 0

        def complete(self, s, m):
            Ok.n += 1
            return "{}"

    fb = FallbackBackend([Broke(), Ok()])
    assert fb.complete("s", []) == "{}" and fb.backends[0].name == "b" and "Credit" in fb.errors[0]
    assert fb.complete("s", []) == "{}" and len(fb.errors) == 1  # lần sau đi thẳng tới AI dùng được
    with pytest.raises(LlmError):
        FallbackBackend([Broke()]).complete("s", [])


def test_conflicting_proposals_are_flagged_and_accepting_one_dismisses_other(kitchen):
    root, m = kitchen
    d = read_drawing(m)
    elev = next(v for v in d.views if v.group == "SYN.10" and v.kind == "elevation")
    plan = next(v for v in d.views if v.group == "SYN.10" and v.kind == "plan")
    sec = next(v for v in d.views if v.kind == "section")

    class TwoLinks:
        name = "fake"

        def complete(self, system, messages):
            if "candidates" in system or "ghép" in system:
                return json.dumps({"proposals": [
                    {"kind": "link_views", "target": elev.id, "value": {"plan": plan.id}, "evidence": [elev.id], "reason": "a"},
                    {"kind": "link_views", "target": elev.id, "value": {"plan": sec.id}, "evidence": [], "reason": "b"}]})
            return '{"proposals": []}'

    st = graph_ai.run(d, {}, root, m.file_hash, backend=TwoLinks(), agents=("links",))
    links = [p for p in st["items"] if p["kind"] == "link_views"]
    assert len(links) == 1 and "llm" in links[0]["sources"]  # mã hình làm bằng chứng được nhận; mặt cắt bị harness loại
    assert any("mặt bằng" in r["why"] for r in st["rejected"])
    st["items"].append({**links[0], "id": "p-000000000000", "value": {"plan": "khac"}, "sources": ["llm"]})
    graph_ai._flag_conflicts({x["id"]: x for x in st["items"]})
    assert all(any("Mâu thuẫn" in f for f in x["flags"]) for x in st["items"] if x["kind"] == "link_views")


def test_material_clauses_pair_components_and_keep_diacritics():
    from cadguard.graph_ai import _clauses

    assert _clauses("THÙNG, CÁNH, HẬU TỦ MDF 17MM CHỐNG ẨM") == [("MDF", ["thùng", "cánh", "hậu"])]
    assert _clauses("TỦ CAO CÁNH KÍNH KHUNG NHÔM, MÀU CHỈ ĐỊNH") == [("Kính", ["cánh"]), ("Nhôm", ["khung"])]
    assert _clauses("TỦ BẾP TRÊN KHUNG NHÔM, CÁNH KÍNH, TAY NẮM") == [("Nhôm", ["khung"]), ("Kính", ["cánh"])]
    assert _clauses("GƯƠNG NHẬT 5MM CÓ MÀI CẠNH") == [("Gương", [])]  # CẠNH (mép) không phải CÁNH (cửa)
