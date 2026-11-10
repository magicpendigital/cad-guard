"""Bộ thực thi trong AutoCAD (autocad/executor.py) với COM giả: cùng changeset, kiểm chưa đổi, sao lưu, một nhóm undo."""
from pathlib import Path

import ezdxf
import pytest

from cadguard import fixtures
from cadguard.agent.workspace import Workspace
from cadguard.autocad.bridge import BridgeError
from cadguard.autocad.executor import apply_in_autocad, plan
from cadguard.changeset import propose


class Obj:
    def __init__(self, e):
        t = e.dxftype()
        self.TextString = e.text if t == "MTEXT" else (e.context.mtext.default_content if t == "MULTILEADER" else e.dxf.get("text", ""))
        self.StyleName = e.dxf.get("style", "") if e.dxf.is_supported("style") else ""
        self.TextOverride = e.dxf.get("text", "") if t == "DIMENSION" else ""


class Style:
    def __init__(self):
        self.fontFile, self.font = "", None

    def SetFont(self, family, bold, italic, charset, pitch):
        self.font = family


class Styles:
    def __init__(self):
        self.items = {}

    def Item(self, name):
        return self.items.setdefault(name, Style())

    def Add(self, name):
        return self.items.setdefault(name, Style())


class Doc:
    def __init__(self, dxf: Path, dwg: Path, dbmod=0):
        self.Name, self.FullName = dwg.name, str(dwg)
        src = ezdxf.readfile(dxf)
        self.objs = {h: Obj(e) for h, e in src.entitydb.items() if e.dxftype() in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF", "MULTILEADER", "DIMENSION")}
        self.vars = {"DBMOD": dbmod, "CMDACTIVE": 0}
        self.TextStyles = Styles()
        self.undo = []

    def GetVariable(self, n):
        return self.vars[n]

    def HandleToObject(self, h):
        return self.objs[h]

    def StartUndoMark(self):
        self.undo.append("start")

    def EndUndoMark(self):
        self.undo.append("end")

    def Regen(self, x):
        pass


class Acad:
    def __init__(self, doc):
        self.Documents = [doc]


@pytest.fixture()
def env(tmp_path):
    fixtures.make_model_sheets(tmp_path / "m.dxf")
    dwg = tmp_path / "m.dwg"
    dwg.write_bytes(b"DWG gia")
    ws = Workspace(tmp_path)
    cs, pv = propose(ws, "m.dxf", [{"op": "convert_unicode"}])
    assert pv["ok"]
    return tmp_path, ws, cs.id, dwg


def test_plan_and_apply_with_undo_and_backup(env):
    root, ws, cid, dwg = env
    p = plan(ws, cid)
    assert len(p["entities"]) == 6 and {s["name"] for s in p["styles"]} == {"VN-ARIAL"}
    doc = Doc(root / "m.dxf", dwg)
    rep = apply_in_autocad(ws, cid, "m", confirm=True, connect=lambda: Acad(doc))
    assert rep["entities"] == 6 and doc.undo == ["start", "end"]
    assert {o.TextString for o in doc.objs.values() if "tủ bếp" in o.TextString} == {"tủ bếp trên"}
    assert doc.TextStyles.items["VN-ARIAL"].font == "Be Vietnam Pro"
    assert (root / ".cadguard" / "backup" / rep["backup"]).read_bytes() == b"DWG gia"
    assert (root / ".cadguard" / "changesets" / f"{cid}.autocad.json").is_file()


def test_refuses_unsaved_or_changed_drawing(env):
    root, ws, cid, dwg = env
    with pytest.raises(BridgeError, match="chưa lưu"):
        apply_in_autocad(ws, cid, "m", confirm=True, connect=lambda: Acad(Doc(root / "m.dxf", dwg, dbmod=1)))
    doc = Doc(root / "m.dxf", dwg)
    first = next(o for o in doc.objs.values() if o.TextString == "tñ bÕp trªn")
    first.TextString = "người dùng đã sửa"
    with pytest.raises(BridgeError, match="khác lúc xem trước"):
        apply_in_autocad(ws, cid, "m", confirm=True, connect=lambda: Acad(doc))
    assert doc.undo == [] and not (root / ".cadguard" / "backup").exists()  # không đổi gì, không sao lưu
    with pytest.raises(BridgeError, match="xác nhận"):
        apply_in_autocad(ws, cid, "m", confirm=False, connect=lambda: Acad(doc))


def test_refuses_non_text_ops(env):
    root, ws, _cid, dwg = env
    cs, _pv = propose(ws, "m.dxf", [{"op": "set_bylayer", "filter": {}}])
    with pytest.raises(BridgeError, match="đường tệp"):
        plan(ws, cs.id)
