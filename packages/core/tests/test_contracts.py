"""Hợp đồng `cg.audit/1` (`cadguard.contracts`): cùng một bản vẽ cho cùng kết quả ở CLI/báo cáo, App và trợ lý;
import một chiều (không vòng). Chỉ dùng DXF tổng hợp."""
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

import cadguard
from cadguard import contracts, fixtures, report
from cadguard.agent.anonymize import Anonymizer
from cadguard.agent.tools import ToolContext, audit as tool_audit, load_model
from cadguard.agent.workspace import Workspace
from cadguard.app.api import AppConfig, AppData, audit_file
from cadguard.runner import audit_model
from cadguard.standard import load_standard

CORE = Path(cadguard.__file__).resolve().parents[1]
STDS = CORE.parents[1] / "standards"
STANDARDS = ("furniture-v0", "design-hygiene-v0")


@pytest.fixture(scope="module")
def ws(tmp_path_factory):
    d = tmp_path_factory.mktemp("contracts")
    fixtures.make_all(d)
    return d


def _per_rule(findings) -> Counter:
    return Counter((f["rule_id"], f["severity"]) for f in findings)


@pytest.mark.parametrize("standard", STANDARDS)
def test_same_drawing_same_result_everywhere(ws, standard):
    std = load_standard(standard, STDS)
    app = AppData(AppConfig(workspace=ws, standards_dir=STDS))
    ctx = ToolContext(Workspace(ws), Anonymizer(enabled=True), STDS, max_findings=10_000)
    for path in sorted(ws.glob("*.dxf")):
        model = load_model(path)
        rep = contracts.audit_report(model, std).dump()
        assert rep["schema"] == "cg.audit/1"
        expect = (rep["counts"], rep["rules_run"], _per_rule(rep["findings"]))

        cli = report.build_report(std, [(path.name, model.file_hash, audit_model(model, std))])["files"][0]
        assert (cli["counts"], cli["rules_run"], _per_rule(cli["findings"])) == expect, path.name

        ui = audit_file(app, path.name, standard)
        ui_findings = [{"rule_id": g["rule_id"], "severity": g["severity"]} for grp in ui["groups"] for g in grp["rules"]
                       for _ in g["items"]]
        assert (ui["counts"], ui["rules_run"], _per_rule(ui_findings)) == expect, path.name
        assert ui["fixable_rules"] == rep["fixable_rules"] and ui["records_capped"] == rep["records_capped"]

        ai = tool_audit(ctx, path.name, standard)
        assert (ai["counts"], ai["rules_run"], _per_rule(ai["findings"])) == expect, path.name
        assert ai["fixable_rules"] == rep["fixable_rules"] and not ai["truncated"]
        assert all("bbox" not in f for f in ai["findings"])  # toạ độ không ra khỏi Bậc 1
        assert [s["rule_id"] for s in ai["skipped"]] == [s["rule_id"] for s in rep["skipped"]]


def test_fix_ops_and_bbox_are_optional_never_invented(ws):
    std = load_standard("design-hygiene-v0", STDS)
    rep = contracts.audit_report(load_model(ws / "hygiene_bad.dxf"), std)
    assert rep.findings
    for f in rep.findings:
        assert f.fix_ops == contracts.FIXABLE_RULES.get(f.rule_id, [])
        if f.bbox is not None:
            assert f.handles and f.bbox[0] <= f.bbox[2] and f.bbox[1] <= f.bbox[3]
        if not f.handles:
            assert f.bbox is None
    assert set(rep.fixable_rules) <= set(contracts.FIXABLE_RULES)


def test_json_schema_and_round_trip(ws):
    schemas = contracts.json_schemas()
    assert {"cg.audit/1", "cg.drawing/1"} <= set(schemas)
    std = load_standard("furniture-v0", STDS)
    rep = contracts.audit_report(load_model(ws / "bad_layers.dxf"), std)
    again = contracts.AuditReport.model_validate(json.loads(json.dumps(rep.dump())))
    assert again == rep


@pytest.mark.parametrize("module", ["cadguard.contracts", "cadguard.model", "cadguard.runner", "cadguard.report",
                                   "cadguard.agent.tools", "cadguard.agent.registry", "cadguard.app.api",
                                   "cadguard.mcp_server", "cadguard.assistant.toolspec"])
def test_each_module_imports_alone(module):
    """Import đầu tiên trong tiến trình mới phải chạy được (bắt vòng import kiểu contracts <-> model)."""
    env = dict(os.environ, PYTHONPATH=str(CORE), PYTHONUTF8="1")
    out = subprocess.run([sys.executable, "-c", f"import {module}"], env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]


def test_contracts_import_is_light_and_reexports_lazily():
    code = ("import sys, cadguard.contracts as c; light = 'ezdxf' not in sys.modules; "
            "ok = c.DrawingModel.__name__ == 'DrawingModel' and c.Scene.__name__ == 'Scene'; print(light, ok)")
    env = dict(os.environ, PYTHONPATH=str(CORE), PYTHONUTF8="1")
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.split() == ["True", "True"]
