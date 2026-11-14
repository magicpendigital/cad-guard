"""Test `diff` theo handle trên cặp DXF dựng tay bằng ezdxf (tổng hợp)."""

import json

import ezdxf
import pytest

from cadguard.agent.anonymize import Anonymizer
from cadguard.agent.tools import ToolContext, diff as tool_diff
from cadguard.agent.workspace import Workspace
from cadguard.changeset.diff import diff_files


@pytest.fixture
def pair(tmp_path):
    doc = ezdxf.new("R2018")
    for name in ("SYN-A", "SYN-B"):
        doc.layers.add(name)
    doc.styles.add("SYN-STYLE-THUA", font="arial.ttf")
    blk = doc.blocks.new("SYN-KHOI")
    blk.add_line((0, 0), (1, 0), dxfattribs={"layer": "0"})
    msp = doc.modelspace()
    line = msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "SYN-A"})
    circle = msp.add_circle((5, 5), 2, dxfattribs={"layer": "SYN-A"})
    text = msp.add_text("Bí mật khách", dxfattribs={"layer": "SYN-B", "height": 2.5})
    poly = msp.add_lwpolyline([(0, 0), (1, 0), (1, 1)], dxfattribs={"layer": "SYN-B"})
    a = tmp_path / "a.dxf"
    doc.saveas(a)
    handles = {"line": line.dxf.handle, "circle": circle.dxf.handle, "text": text.dxf.handle, "poly": poly.dxf.handle}

    doc = ezdxf.readfile(a)
    msp = doc.modelspace()
    ents = {e.dxf.handle: e for e in msp}
    ents[handles["line"]].dxf.color = 1
    ents[handles["line"]].dxf.layer = "SYN-B"
    msp.delete_entity(ents[handles["circle"]])
    ents[handles["text"]].dxf.text = "Chữ đã đổi"
    ents[handles["poly"]].set_points([(0, 0), (2, 0), (2, 2)])
    new = msp.add_line((0, 0), (0, 10), dxfattribs={"layer": "SYN-A"})
    doc.layers.add("SYN-MOI")
    doc.styles.remove("SYN-STYLE-THUA")
    b = tmp_path / "b.dxf"
    doc.saveas(b)
    handles["new"] = new.dxf.handle
    return a, b, handles


def test_diff_detects_added_removed_changed(pair):
    a, b, h = pair
    d = diff_files(a, b)
    s = d["summary"]
    assert (s["added"], s["removed"], s["changed"]) == (1, 1, 3)
    assert [e["handle"] for e in d["entities"]["added"]] == [h["new"]]
    assert [e["handle"] for e in d["entities"]["removed"]] == [h["circle"]]
    changed = {e["handle"]: e for e in d["entities"]["changed"]}
    assert set(changed[h["line"]]["attrs"]) == {"color", "layer"}
    assert changed[h["line"]]["attrs"]["layer"] == ["SYN-A", "SYN-B"]
    assert set(changed[h["text"]]["attrs"]) == {"text"}
    assert set(changed[h["poly"]]["attrs"]) == {"data"}  # đỉnh đa tuyến không phải thuộc tính có tên
    assert d["definitions"]["layers"]["added"] == ["SYN-MOI"]
    assert d["definitions"]["text_styles"]["removed"] == ["SYN-STYLE-THUA"]
    assert d["definitions"]["blocks"] == {"added": [], "removed": [], "changed": []}
    assert s["changed_by_attr"] == {"color": 1, "data": 1, "layer": 1, "text": 1}
    assert "1 thêm" in d["summary_vi"] and "1 xoá" in d["summary_vi"]
    assert d["a"]["name"] == "a.dxf" and len(d["a"]["sha256"]) == 64
    assert str(a.parent) not in json.dumps(d, ensure_ascii=False)


def test_identical_files_have_empty_diff(pair):
    a, _, _ = pair
    d = diff_files(a, a)
    assert d["summary"]["added"] == d["summary"]["removed"] == d["summary"]["changed"] == 0
    assert all(not v for kind in d["definitions"].values() for v in kind.values())


def test_diff_caps_items(tmp_path):
    doc = ezdxf.new()
    doc.saveas(tmp_path / "a.dxf")
    for i in range(30):
        doc.modelspace().add_line((i, 0), (i, 1))
    doc.saveas(tmp_path / "b.dxf")
    d = diff_files(tmp_path / "a.dxf", tmp_path / "b.dxf", max_items=10)
    assert d["truncated"] and len(d["entities"]["added"]) == 10 and d["summary"]["added"] == 30


def test_tool_diff_anonymized(pair):
    a, b, h = pair
    ctx = ToolContext(Workspace(a.parent), Anonymizer(True, "salt"))
    out = tool_diff(ctx, "a.dxf", "b.dxf")
    text = json.dumps(out, ensure_ascii=False)
    for secret in ("SYN-A", "SYN-B", "SYN-MOI", "SYN-STYLE-THUA", "Bí mật", "Chữ đã đổi", "a.dxf"):
        assert secret not in text, secret
    changed = {e["handle"]: e for e in out["entities"]["changed"]}
    anon = ctx.anonymizer
    assert changed[h["line"]]["attrs"]["layer"] == [anon.token("layer", "SYN-A"), anon.token("layer", "SYN-B")]
    assert changed[h["line"]]["attrs"]["color"][1] == 1
    assert out["definitions"]["layers"]["added"] == [anon.token("layer", "SYN-MOI")]
    assert out["summary"]["added"] == 1 and out["a"]["id"].startswith("F_")
