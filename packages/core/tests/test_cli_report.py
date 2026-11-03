import json

from cadguard import telemetry
from cadguard.cli import main


def test_audit_report_files(synthetic, tmp_path, standard):
    from cadguard import report
    from cadguard.dxf_reader import read_dxf
    from cadguard.runner import audit_model

    items = []
    for p in sorted(synthetic.glob("*.dxf")):
        m = read_dxf(p)
        items.append((p.name, m.file_hash, audit_model(m, standard)))
    rep = report.build_report(standard, items)
    assert rep["schema"] == "cg.report/1" and rep["totals"]["E"] > 0
    page = report.render_html(rep)
    assert "<html lang='vi'>" in page and "LY-04" in page and "Cảnh báo" in page
    report.write_json(rep, tmp_path / "r.json")
    assert json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))["standard"]["name"] == "furniture-v0"


def test_cli_exit_codes_and_telemetry(synthetic, capsys):
    from pathlib import Path

    repo = Path(__file__).resolve().parents[3] / "standards"
    assert main(["audit", str(synthetic / "ok_sheet.dxf"), "--standards-dir", str(repo)]) == 0
    assert main(["audit", str(synthetic / "bad_layers.dxf"), "--standards-dir", str(repo)]) == 1
    assert main(["audit", str(synthetic / "missing.dxf"), "--standards-dir", str(repo)]) == 2
    assert telemetry.drawings_audited(7) == 2  # chỉ đếm bản vẽ khác nhau (băm)
    log = (telemetry.home() / "telemetry.jsonl").read_text(encoding="utf-8")
    assert "ok_sheet" not in log and "bad_layers" not in log, "telemetry không được chứa tên tệp"


def test_stats_json_is_flat_numbers(capsys):
    from pathlib import Path

    repo = Path(__file__).resolve().parents[3] / "standards"
    assert main(["stats", "--json", "--standards-dir", str(repo)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["rules_implemented"] == 16 and set(data) == {"rules_implemented", "drawings_audited_7d"}
    assert all(isinstance(v, (int, float)) for v in data.values())
