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
                                    renumber=True, frames=False)
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


# ---------- thao tác khung: replace_title_block, set_sheet_scale, fit_sheet (kế hoạch mục 4.4) ----------

NOT_FIXABLE = {"TP-07", "TP-08", "TP-09", "TP-12"}  # tràn quá vùng vẽ, ngoài tờ, chữ nhỏ: quyết định thiết kế; Unicode: thao tác riêng


def _legacy_ws(tmp_path) -> Path:
    fixtures.make_model_sheets(tmp_path / "m.dxf", legacy=(1,))  # tờ 2 dùng khung tên CŨ
    template.learn(tmp_path / "m.dxf", 1, tmp_path / ".cadguard" / "template")
    return tmp_path


def _tpl(ws):
    return template.load_template(ws / ".cadguard" / "template" / "template.yaml")


def _drawing_snapshot(path):
    """Mọi đối tượng KHÔNG phải khung tên/thuộc tính: (loại, layer, thuộc tính DXF) theo handle."""
    from cadguard.changeset.diff import snapshot
    from cadguard.changeset.engine import read_doc

    snap = snapshot(read_doc(path))["entities"]
    return {h: (s.type, s.layer, s.attrs) for h, s in snap.items()
            if s.type not in ("INSERT", "ATTRIB") or s.space.startswith("block:SYN-KY")}


def test_map_tags_learned_role_similar():
    fields = [{"tag": "DU_AN"}, {"tag": "TEN_BAN_VE"}, {"tag": "SO_BAN_VE", "role": "number", "pattern": r"^NT\-\d+$"},
              {"tag": "TI_LE", "role": "scale"}, {"tag": "NGAY"}]
    old = {"DUAN": "X", "TENBV": "Mặt bằng", "KYHIEU": "NT-02", "TL": "1/15", "NGAYVE": "1/1", "GHI_CHU": "abc"}
    m, lost = template.map_tags(old, fields)
    assert m == {"DUAN": "DU_AN", "KYHIEU": "SO_BAN_VE", "TL": "TI_LE", "TENBV": "TEN_BAN_VE", "NGAYVE": "NGAY"}
    assert lost == ["GHI_CHU"]
    m2, _ = template.map_tags(old, fields, {"GHI_CHU": "TEN_BAN_VE"})  # bảng đã học thắng
    assert m2["GHI_CHU"] == "TEN_BAN_VE" and "TENBV" not in m2


def test_frame_ops_fix_tp_keep_drawing_and_undo(tmp_path):
    from cadguard.changeset import undo
    from cadguard.changeset.diff import sha256_file

    ws = _legacy_ws(tmp_path)
    before_ids, _ = _ids(ws)
    assert "TP-01" in before_ids and "TP-05" in before_ids
    ops, notes = template.apply_ops(read_dxf(ws / "m.dxf"), _tpl(ws), renumber=True,
                                    template_dir=ws / ".cadguard" / "template")
    kinds = [o["op"] for o in ops]
    assert kinds == ["replace_title_block", "set_sheet_scale", "set_attribs"]
    rep = ops[0]["items"][0]["values"]
    assert rep["SO_BAN_VE"] == "NT-02" and rep["TI_LE"] == "1/15" and rep["TEN_BAN_VE"] == "MẶT BẰNG TRẦN"
    assert ops[1]["items"][0]["scale"] == 20.0
    assert any("lớn hơn vùng vẽ" in n for n in notes)  # tờ 2 tràn dải khung tên: chỉ báo
    w = Workspace(ws)
    sha = sha256_file(ws / "m.dxf")
    cs, pv = propose(w, "m.dxf", ops, standard="sheet-layout-v0")
    assert pv["ok"], pv["checks"]
    assert set(pv["rules"].get("tolerated", [])) <= {"TP-07"}  # lỗi có sẵn của tờ 2 hiện ra sau khi thay khung
    res = apply(w, cs.id, confirm=True)
    out = ws / res["output"]["path"]
    after_ids, _ = _ids(ws, res["output"]["path"])
    assert set(after_ids) <= NOT_FIXABLE and not set(after_ids) & set(template.FIXABLE_TP) - {"TP-07"}
    assert after_ids.count("TP-07") == 1  # chỉ tờ 2 (nội dung lớn hơn vùng vẽ)
    assert _drawing_snapshot(ws / "m.dxf") == _drawing_snapshot(out)  # 0 hình vẽ/kích thước/chú thích đổi
    undo(w, cs.id, confirm=True)
    assert not out.exists() and sha256_file(ws / "m.dxf") == sha


def test_fit_sheet_moves_only_frame(tmp_path):
    fixtures.make_model_sheets(tmp_path / "m.dxf")
    template.learn(tmp_path / "m.dxf", 1, tmp_path / ".cadguard" / "template")
    doc = ezdxf.readfile(tmp_path / "m.dxf")
    frame = next(e for e in doc.modelspace().query("INSERT") if e.dxf.name == fixtures.CO_FRAME)
    frame.translate(0, -50 * 15, 0)  # khung tờ 1 lệch xuống: chữ ghi chú tràn mép trên vùng vẽ
    doc.saveas(tmp_path / "s.dxf")
    before, _ = _ids(tmp_path, "s.dxf")
    assert before.count("TP-07") == 2
    ops, _notes = template.apply_ops(read_dxf(tmp_path / "s.dxf"), _tpl(tmp_path), fill_scale=False, fixed=False,
                                     template_dir=tmp_path / ".cadguard" / "template")
    fit = next(o for o in ops if o["op"] == "fit_sheet")
    assert [it["insert"] for it in fit["items"]] == [frame.dxf.handle]
    w = Workspace(tmp_path)
    cs, pv = propose(w, "s.dxf", [fit], standard="sheet-layout-v0")
    assert pv["ok"] and pv["diff"]["changed_by_attr"].keys() <= {"insert", "align_point"}
    res = apply(w, cs.id, confirm=True)
    after, _ = _ids(tmp_path, res["output"]["path"])
    assert after.count("TP-07") == 1
    assert _drawing_snapshot(tmp_path / "s.dxf") == _drawing_snapshot(tmp_path / res["output"]["path"])


def test_frame_scope_is_not_loosened(tmp_path):
    """fit_sheet cho khung A không cho phép đổi khung B hay đối tượng hình vẽ."""
    from cadguard.changeset.engine import Protection, read_doc, run_ops
    from cadguard.changeset.ops import parse_ops
    from cadguard.changeset.validate import evaluate

    fixtures.make_model_sheets(tmp_path / "m.dxf")
    a = read_doc(tmp_path / "m.dxf")
    b = read_doc(tmp_path / "m.dxf")
    frames = [e for e in b.modelspace().query("INSERT") if e.dxf.name == fixtures.CO_FRAME]
    ops = parse_ops([{"op": "fit_sheet", "items": [{"insert": frames[0].dxf.handle, "offset": [10, 0]}]}])
    run_ops(b, ops, Protection())
    std = rule_config.effective_standard("sheet-layout-v0", STD, workspace=tmp_path)
    assert evaluate(a, b, ops, Protection(), std)["checks"][1]["ok"]
    frames[1].translate(10, 0, 0)  # khung khác: ngoài phạm vi thao tác
    bad = evaluate(a, b, ops, Protection(), std)
    assert not bad["ok"] and not next(c for c in bad["checks"] if c["id"] == "allowed_attrs")["ok"]
    with pytest.raises(Exception, match="không phải khối chèn"):
        line = next(iter(read_doc(tmp_path / "m.dxf").modelspace().query("LINE")))
        run_ops(read_doc(tmp_path / "m.dxf"), parse_ops([{"op": "set_sheet_scale", "items": [
            {"insert": line.dxf.handle, "scale": 20}]}]), Protection())


def test_cli_template_apply_frames(tmp_path, capsys):
    ws = _legacy_ws(tmp_path)
    assert main(["template", "apply", str(ws / "m.dxf"), "--renumber", "--yes"]) == 0
    out = capsys.readouterr().out
    assert "replace_title_block" in out or "thay khung" in out.lower()
    outs = [p for p in ws.glob("m.*.dxf")]
    assert len(outs) == 1
    ids, _ = _ids(ws, outs[0].name)
    assert set(ids) <= NOT_FIXABLE


def test_tp11_rows_aligned_and_evenly_spaced(tmp_path):
    fixtures.make_model_sheets(tmp_path / "m.dxf")  # tờ kề nhau, cùng mép dưới: không có TP-11
    std = rule_config.effective_standard("sheet-layout-v0", STD, workspace=tmp_path)
    assert not [f for f in audit_model(read_dxf(tmp_path / "m.dxf"), std).findings if f.rule_id == "TP-11"]
    doc = ezdxf.readfile(tmp_path / "m.dxf")
    frames = sorted((e for e in doc.modelspace().query("INSERT") if e.dxf.name == fixtures.CO_FRAME),
                    key=lambda e: e.dxf.insert.x)
    frames[2].translate(0, 300, 0)  # tờ 3 lệch lên
    for f in frames[4:]:  # khe 500 trước tờ 5 (các khe khác 0)
        f.translate(500, 0, 0)
    doc.saveas(tmp_path / "x.dxf")
    tp11 = [f for f in audit_model(read_dxf(tmp_path / "x.dxf"), std).findings if f.rule_id == "TP-11"]
    msgs = " | ".join(f.message for f in tp11)
    assert len(tp11) == 2 and "lệch mép dưới" in msgs and "Tờ 3" in msgs and "không đều" in msgs and "Tờ 5" in msgs
    assert all(f.severity == "I" for f in tp11)
    frames[5].translate(-3000, 0, 0)  # tờ 6 chồng lên tờ 5
    doc.saveas(tmp_path / "y.dxf")
    tp11 = [f for f in audit_model(read_dxf(tmp_path / "y.dxf"), std).findings if f.rule_id == "TP-11"]
    assert any("chồng" in f.message for f in tp11)
