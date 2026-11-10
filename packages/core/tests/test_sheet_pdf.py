"""In PDF hàng loạt theo tờ (sheet_pdf.py): kế hoạch tờ, tên tệp theo số bản vẽ, tệp lệnh -PLOT, chạy (giả/thật)."""
import os
import re
from pathlib import Path

import pytest

from cadguard import fixtures, sheet_pdf, template
from cadguard.cli import main
from cadguard.dxf_reader import read_dxf


@pytest.fixture()
def ws(tmp_path) -> Path:
    fixtures.make_model_sheets(tmp_path / "m.dxf")
    template.learn(tmp_path / "m.dxf", 1, tmp_path / ".cadguard" / "template")
    return tmp_path


def _tpl(ws):
    return template.load_template(ws / ".cadguard" / "template" / "template.yaml")


def test_plan_names_by_drawing_number(ws):
    items, notes = sheet_pdf.plan(read_dxf(ws / "m.dxf"), _tpl(ws))
    assert [it["file"] for it in items] == ["NT-01.pdf", "NT-02.pdf", "NT-03.pdf", "NT-04.pdf", "To-05.pdf",
                                            "NT-02-to06.pdf"]
    assert all(it["paper"] == "A3" and it["landscape"] for it in items)
    assert any("thiếu số bản vẽ" in n for n in notes) and any("trùng" in n for n in notes)
    no_tpl, _ = sheet_pdf.plan(read_dxf(ws / "m.dxf"), None, picks=[2, 3])
    assert [it["file"] for it in no_tpl] == ["To-02.pdf", "To-03.pdf"]
    assert sheet_pdf.safe_name(' A/B:C*? ') == "A-B-C"


def test_script_one_plot_per_sheet(ws):
    items, _ = sheet_pdf.plan(read_dxf(ws / "m.dxf"), _tpl(ws))
    scr = sheet_pdf.script(items, Path("C:/out"))
    plots = re.findall(r'\(command "_\.-PLOT".*\)', scr)
    assert len(plots) == 6 and '"ISO full bleed A3 (420.00 x 297.00 MM)"' in plots[0]
    assert '"C:/out/NT-01.pdf"' in plots[0] and '"_W" \'(0.0 0.0) \'(6300.0 4455.0) "_F"' in plots[0]


def test_plot_sheets_with_fake_autocad(ws, monkeypatch):
    seen = {}

    def fake_run(src, script, timeout, exe=None):
        seen["n"] = script.count("-PLOT")
        for f in re.findall(r'"([^"]+\.pdf)"', script)[:-1]:  # tờ cuối "không in được"
            Path(f).write_bytes(b"%PDF-1.7")
        return ""

    monkeypatch.setattr("cadguard.dwg.run_script", fake_run)
    res = sheet_pdf.plot_sheets(ws / "m.dxf", ws / "pdf", tpl=_tpl(ws))
    assert seen["n"] == 6 and res["count"] == 6 and len(res["printed"]) == 5
    assert [m["file"] for m in res["missing"]] == ["NT-02-to06.pdf"]
    with pytest.raises(sheet_pdf.PdfError, match="không ghi đè"):
        sheet_pdf.plot_sheets(ws / "m.dxf", ws / "pdf", tpl=_tpl(ws))


@pytest.mark.skipif(not os.environ.get("CADGUARD_TEST_AUTOCAD"), reason="đặt CADGUARD_TEST_AUTOCAD=1 để chạy với AutoCAD thật")
def test_cli_pdf_real_autocad(ws, capsys):
    assert main(["sheets", str(ws / "m.dxf"), "--pdf", str(ws / "pdf")]) == 0
    files = sorted(p.name for p in (ws / "pdf").glob("*.pdf"))
    assert len(files) == 6 and "NT-01.pdf" in files
    assert b"/MediaBox [0 0 1191 842]" in (ws / "pdf" / "NT-01.pdf").read_bytes()
