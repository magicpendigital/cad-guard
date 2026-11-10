"""Dịch bản vẽ (translate.py): nhận ngôn ngữ nguồn, bảo vệ số/mã, bảng thuật ngữ, LLM giả, changeset, CSV duyệt."""
import json
import re
from pathlib import Path

import ezdxf
import pytest

from cadguard import fixtures, privacy, translate
from cadguard.agent.workspace import Workspace
from cadguard.changeset import apply, propose
from cadguard.cli import main


class FakeLlm:
    """Giả LLM: 'dịch' bằng cách thêm tiền tố, giữ nguyên ký hiệu giữ chỗ; có thể cố ý làm mất một ký hiệu."""
    name = "fake"

    def __init__(self, lang="en", drop: str | None = None):
        self.lang, self.drop, self.calls = lang, drop, 0

    def complete(self, system, messages):
        self.calls += 1
        data = json.loads(messages[0]["content"])
        out = []
        for it in data["items"]:
            text = ("EN " if self.lang == "en" else "中文 ") + it["text"]
            if self.drop and self.drop in it["text"]:
                text = re.sub(r"⟦\d+⟧", "", text)
            out.append({"id": it["id"], "text": text})
        return json.dumps({"items": out}, ensure_ascii=False)


@pytest.fixture()
def ws(tmp_path) -> Path:
    fixtures.make_model_sheets(tmp_path / "m.dxf")
    return tmp_path


def test_detect_language():
    assert translate.detect_language("Tủ áo cánh mở") == "vi"
    assert translate.detect_language("橱柜 800mm") == "zh"
    assert translate.detect_language("Kitchen cabinet door") == "en"
    assert translate.detect_language("NT-01 1200") is None
    d = translate.detect_drawing_language(["Tủ bếp", "Kính cường lực 8mm", "TV 86QNED80"])
    assert d["language"] == "vi" and d["counts"]["vi"] == 2


def test_protect_numbers_units_codes_and_mtext_codes():
    masked, kept = translate.protect(r"{\fArial|b0;cánh tủ MDF chống ẩm 18mm}\Pđệm 1800*2000mm NT-01", True)
    assert "MDF" in kept and "18mm" in kept and "1800*2000mm" in kept and "NT-01" in kept and r"\P" in kept
    assert "cánh tủ" in masked and "MDF" not in masked
    assert translate.restore(masked, kept) == r"{\fArial|b0;cánh tủ MDF chống ẩm 18mm}\Pđệm 1800*2000mm NT-01"
    assert translate.placeholders_ok("a ⟦0⟧ ⟦1⟧", "b ⟦1⟧ ⟦0⟧") and not translate.placeholders_ok("⟦0⟧", "x")


def test_translate_en_changeset_and_output_name(ws):
    llm = FakeLlm("en")
    res = translate.build(ws / "m.dxf", "en", workspace=ws, backend=llm)
    rep = res["report"]
    assert rep["source_language"]["language"] == "vi" and rep["untranslated"] == 0 and llm.calls == 1
    assert [o["op"] for o in res["ops"]] == ["convert_unicode", "set_texts"]
    w = Workspace(ws)
    cs, pv = propose(w, "m.dxf", res["ops"], output_tag="en")
    assert pv["ok"], [c for c in pv["checks"] if not c["ok"]]
    out = apply(w, cs.id, confirm=True)
    assert out["output"]["path"] == "m.en.dxf"
    doc = ezdxf.readfile(ws / "m.en.dxf")
    texts = [e.dxf.text for e in doc.modelspace().query("TEXT")]
    assert "EN cánh tủ MDF chống ẩm 18mm" in texts  # số/đơn vị/mã giữ nguyên
    attr = [a.dxf.text for i in doc.modelspace().query("INSERT") for a in i.attribs if a.dxf.tag == "SO_BAN_VE"]
    assert "NT-01" in attr  # mã số bản vẽ không có chữ để dịch: giữ nguyên
    assert (ws / ".cadguard" / "translation-memory.json").is_file()
    # lần sau dùng bộ nhớ dịch, không gọi LLM
    llm2 = FakeLlm("en")
    rep2 = translate.build(ws / "m.dxf", "en", workspace=ws, backend=llm2)["report"]
    assert llm2.calls == 0 and rep2["by_source"].get("tm")


def test_glossary_exact_and_mismatch(ws):
    (ws / ".cadguard").mkdir()
    (ws / ".cadguard" / "glossary.yaml").write_text(
        "terms:\n  - {vi: 'Tủ áo cánh mở', en: 'Hinged wardrobe', zh: '平开衣柜'}\n", encoding="utf-8")
    rep = translate.build(ws / "m.dxf", "en", workspace=ws, backend=FakeLlm("en"))["report"]
    rows = {r["source"]: r for r in rep["rows"]}
    assert any(r["from"] == "glossary" for r in rep["rows"]) or rows["Tủ áo cánh mở"]["target"]
    # thuật ngữ 'tủ bếp' có trong bảng nhưng LLM giả không dùng 'kitchen cabinet': bị báo
    assert any("lệch thuật ngữ" in "; ".join(x["issues"]) for x in rep["issues"])


def test_lost_placeholder_is_rejected(ws):
    rep = translate.build(ws / "m.dxf", "en", workspace=ws, backend=FakeLlm("en", drop="chống ẩm"))["report"]
    assert rep["untranslated"] >= 1
    assert any("mất/đổi số" in "; ".join(x["issues"]) for x in rep["issues"])


def test_zh_uses_cjk_style(ws):
    res = translate.build(ws / "m.dxf", "zh", workspace=ws, backend=FakeLlm("zh"))
    op = res["ops"][-1]
    assert op["style"] == "CG-ZH" and op["style_font"] == "msyh.ttc"
    w = Workspace(ws)
    cs, pv = propose(w, "m.dxf", res["ops"], output_tag="zh")
    assert pv["ok"]
    doc = ezdxf.readfile(ws / apply(w, cs.id, confirm=True)["output"]["path"])
    t = next(e for e in doc.modelspace().query("TEXT") if e.dxf.text.startswith("中文"))
    assert t.dxf.style == "CG-ZH" and doc.styles.get("CG-ZH").dxf.font == "msyh.ttc"


def test_locked_when_anonymized(ws):
    privacy.set_project_anonymize(ws, True)
    with pytest.raises(translate.TranslateError, match="ẩn danh"):
        translate.build(ws / "m.dxf", "en", workspace=ws, backend=FakeLlm())


def test_cli_review_csv_roundtrip(ws, capsys):
    csv_path = ws / "duyet.csv"
    assert main(["translate", str(ws / "m.dxf"), "--to", "en", "--engine", "none", "--export-review", str(csv_path)]) == 0
    text = csv_path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    assert lines[0] == "handle,type,source,target,from" and len(lines) > 5
    import csv

    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
    first = next(r for r in rows if r["source"] == "Kính cường lực 8mm")
    first["target"] = "Tempered glass 8mm"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    assert main(["translate", str(ws / "m.dxf"), "--to", "en", "--engine", "none", "--from-review", str(csv_path),
                 "--yes"]) == 0
    doc = ezdxf.readfile(ws / "m.en.dxf")
    assert any(e.text == "Tempered glass 8mm" for e in doc.modelspace().query("MTEXT"))


def test_app_translate_endpoint(ws, monkeypatch, tmp_path):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))
    from cadguard.app import AppConfig, CadGuardApp
    from cadguard.app import api as app_api

    app = CadGuardApp(AppConfig(workspace=ws), cli_detect=lambda name: {"installed": None}, translate_backend=FakeLlm("en"))
    r = app_api.translate_drawing(app.d(), "m.dxf", "en", None, app.translate_backend)
    assert r["report"]["source_language"]["language"] == "vi" and r["preview"]["ok"]
    with pytest.raises(app_api.ApiError):
        app_api.translate_drawing(app.d(), "m.dxf", "fr", None, app.translate_backend)


def test_assistant_tool_two_steps(ws):
    from cadguard.agent import tools
    from cadguard.agent.anonymize import Anonymizer

    ctx = tools.ToolContext(Workspace(ws), Anonymizer(enabled=False))
    s1 = tools.propose_translation(ctx, "m.dxf", "en")
    assert s1["step"] == 1 and s1["source_language"]["language"] == "vi" and s1["to_translate"] > 0
    tr = [{"source": x["source"], "text": "EN " + x["source"]} for x in s1["items"]]
    s2 = tools.propose_translation(ctx, "m.dxf", "en", tr)
    assert s2["step"] == 2 and s2["ok"] and s2["report"]["untranslated"] == 0
    anon = tools.ToolContext(Workspace(ws), Anonymizer(enabled=True))
    with pytest.raises(tools.ToolError, match="ẩn danh"):
        tools.propose_translation(anon, "m.dxf", "en")
