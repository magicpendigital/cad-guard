"""Template trình bày cg.template/1 (học từ tờ mẫu), gói luật sheet-layout-v0 (TP-*), áp dụng khung tên."""
from pathlib import Path

import ezdxf
import pytest

from cadguard import fixtures, rule_config, template
from cadguard.agent.workspace import Workspace
from cadguard.changeset import apply, propose
from cadguard.cli import main
from cadguard.dxf_reader import read_dxf
from cadguard.dxf_stream import read_dxf_stream
from cadguard.runner import audit_model
from conftest import REPO

STD = REPO / "standards"


@pytest.fixture()
def ws(tmp_path) -> Path:
    fixtures.make_model_sheets(tmp_path / "m.dxf")
    logo = tmp_path / "logo-src.png"
    from PIL import Image

    Image.new("RGB", (8, 4), (200, 30, 30)).save(logo)
    template.learn(tmp_path / "m.dxf", 1, tmp_path / ".cadguard" / "template", logo=logo, company="SYN")
    return tmp_path


def _ids(ws, name="m.dxf", reader=read_dxf):
    std = rule_config.effective_standard("sheet-layout-v0", STD, workspace=ws)
    res = audit_model(reader(ws / name), std)
    return sorted(f.rule_id for f in res.findings), res


def test_learn_fields_band_scales_logo(ws):
    tpl = template.load_template(ws / ".cadguard" / "template" / "template.yaml")
    fr = tpl["frame"]
    assert fr["block"] == fixtures.CO_FRAME and fr["paper"] == "A3"
    assert fr["band"][0] == fixtures.CO_BAND_X and fr["drawing_area"] == [20.0, 10.0, fixtures.CO_BAND_X, 287.0]
    roles = {f["tag"]: f.get("role") for f in tpl["fields"]}
    assert roles["SO_BAN_VE"] == "number" and roles["TI_LE"] == "scale"
    assert {f["tag"]: f["kind"] for f in tpl["fields"]}["DU_AN"] == "fixed"
    assert tpl["rules"]["allowed_scales"] == [10.0, 15.0, 20.0]
    assert tpl["logo"]["file"] == "logo.png" and (ws / ".cadguard" / "template" / "logo.png").is_file()
    tb = ezdxf.readfile(ws / ".cadguard" / "template" / "titleblock.dxf")
    assert fixtures.CO_FRAME in tb.blocks


@pytest.mark.parametrize("reader", [read_dxf, read_dxf_stream])
def test_tp_rules_find_designed_violations(ws, reader):
    ids, res = _ids(ws, reader=reader)
    assert ids == ["TP-04", "TP-05", "TP-06", "TP-06", "TP-07", "TP-08", "TP-09", "TP-10", "TP-10", "TP-12"]
    msgs = " | ".join(f.message for f in res.findings)
    assert "Tờ 5: khung tên thiếu SO_BAN_VE" in msgs and "hệ số khung 19.77" in msgs and "'NT-02' trùng" in msgs


def test_no_template_skips(tmp_path):
    fixtures.make_model_sheets(tmp_path / "m.dxf")
    std = rule_config.effective_standard("sheet-layout-v0", STD, workspace=tmp_path)
    res = audit_model(read_dxf(tmp_path / "m.dxf"), std)
    assert {f.rule_id for f in res.findings} <= {"TP-08", "TP-12"}
    assert any(r == "TP-01" for r, _why in res.skipped)


def test_apply_fills_titleblock_without_touching_drawing(ws):
    ops, notes = template.apply_ops(read_dxf(ws / "m.dxf"),
                                    template.load_template(ws / ".cadguard" / "template" / "template.yaml"),
                                    renumber=True)
    assert any("19.77" in n for n in notes)
    w = Workspace(ws)
    cs, pv = propose(w, "m.dxf", ops, standard="sheet-layout-v0")
    assert pv["ok"] and set(pv["rules"]["resolved"]) == {"TP-04", "TP-10"}
    assert pv["diff"]["changed_by_attr"] == {"text": pv["diff"]["changed"]}  # chỉ đổi chữ thuộc tính
    res = apply(w, cs.id, confirm=True)
    ids, _ = _ids(ws, res["output"]["path"])
    assert "TP-04" not in ids and "TP-10" not in ids and ids.count("TP-06") == 1


def test_cli_template_learn_check(tmp_path, capsys):
    fixtures.make_model_sheets(tmp_path / "m.dxf")
    assert main(["template", "check", str(tmp_path / "m.dxf")]) == 2  # chưa có template
    assert main(["template", "learn", str(tmp_path / "m.dxf"), "--sheet", "1"]) == 0
    assert main(["template", "check", str(tmp_path / "m.dxf")]) == 1  # có lỗi mức E (TP-04, TP-06)
    out = capsys.readouterr().out
    assert "Đã học template" in out and "TP-06" in out


def test_value_helpers():
    assert template.value_pattern("FUR.64. 02") == r"^FUR\.\d+\.\s*\d+$"
    assert template.number_format("NT-01") == {"prefix": "NT-", "width": 2, "suffix": ""}
    assert template.format_number({"prefix": "NT-", "width": 2, "suffix": ""}, 7) == "NT-07"
    assert template.scale_format("TL 1:20") == "TL 1:{n}"
