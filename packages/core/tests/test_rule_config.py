"""Cài đặt luật không tài khoản (`rule_config`): App, CLI và MCP cùng đọc một nguồn nên ra cùng số."""
import json
import shutil

import pytest

from cadguard import rule_config
from cadguard.agent import tools
from cadguard.agent.workspace import Workspace
from cadguard.cli import main
from conftest import REPO

STD = REPO / "standards"


@pytest.fixture()
def ws(synthetic, tmp_path):
    d = tmp_path / "duan"
    d.mkdir()
    shutil.copy(synthetic / "hygiene_bad.dxf", d / "bad.dxf")
    return d


def test_update_and_reset_project(ws):
    rule_config.update_rule("design-hygiene-v0", "VS-06", {"enabled": False}, workspace=ws, standards_dir=STD)
    std = rule_config.effective_standard("design-hygiene-v0", STD, workspace=ws)
    assert std.rule("VS-06").enabled is False and std.profile == {"rule_settings": "project"}
    base = rule_config.effective_standard("design-hygiene-v0", STD, workspace=None)
    assert base.rule("VS-06").enabled is True  # tệp chuẩn gốc không đổi
    rule_config.reset_rule("design-hygiene-v0", "VS-06", workspace=ws, standards_dir=STD)
    assert rule_config.effective_standard("design-hygiene-v0", STD, workspace=ws).rule("VS-06").enabled is True
    log = rule_config.read_log("project", ws)
    assert [e["new"] for e in log] == [{"enabled": False}, {}]


def test_params_and_severity_checked(ws):
    std = rule_config.effective_standard("design-hygiene-v0", STD)
    rid, pname, value = next((r.id, k, v) for r in std.rules if r.implemented for k, v in r.params.items()
                             if isinstance(v, (int, float)) and not isinstance(v, bool))
    rule_config.update_rule("design-hygiene-v0", rid, {"params": {pname: value + 3}, "severity": "I"}, workspace=ws,
                            standards_dir=STD)
    eff = rule_config.effective_standard("design-hygiene-v0", STD, workspace=ws).rule(rid)
    assert eff.params[pname] == value + 3 and eff.severity == "I"
    with pytest.raises(rule_config.RuleSettingsError):
        rule_config.update_rule("design-hygiene-v0", rid, {"params": {pname: "abc"}}, workspace=ws, standards_dir=STD)
    with pytest.raises(rule_config.RuleSettingsError):
        rule_config.update_rule("design-hygiene-v0", rid, {"params": {"khong_co": 1}}, workspace=ws, standards_dir=STD)
    with pytest.raises(rule_config.RuleSettingsError):
        rule_config.update_rule("design-hygiene-v0", "KHONG-CO", {"enabled": False}, workspace=ws, standards_dir=STD)


def test_machine_scope_then_project_overrides(ws):
    rule_config.update_rule("design-hygiene-v0", "VS-06", {"enabled": False}, scope="machine", standards_dir=STD)
    assert rule_config.effective_standard("design-hygiene-v0", STD, workspace=None).rule("VS-06").enabled is False
    rule_config.update_rule("design-hygiene-v0", "VS-06", {"enabled": True}, workspace=ws, standards_dir=STD)
    assert rule_config.effective_standard("design-hygiene-v0", STD, workspace=ws).rule("VS-06").enabled is True


def test_cli_and_mcp_same_numbers(ws, capsys):
    rule_config.update_rule("design-hygiene-v0", "VS-06", {"enabled": False}, workspace=ws, standards_dir=STD)
    assert main(["audit", str(ws / "bad.dxf"), "--standard", "design-hygiene-v0", "--json",
                 "--standards-dir", str(STD)]) == 0
    rep = json.loads(capsys.readouterr().out)
    cli_ids = {f["rule_id"] for f in rep["files"][0]["findings"]}
    assert "VS-06" not in cli_ids
    ctx = tools.ToolContext(Workspace(ws), standards_dir=STD)
    res = tools.audit(ctx, "bad.dxf", "design-hygiene-v0")
    mcp_ids = {f["rule_id"] for f in res["findings"]}
    assert mcp_ids == cli_ids
