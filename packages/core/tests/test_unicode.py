"""Chuyển chữ TCVN3/VNI sang Unicode (unicode_convert.py + thao tác changeset convert_unicode)."""
import unicodedata
from pathlib import Path

import ezdxf
import pytest

from cadguard import fixtures
from cadguard.agent.workspace import Workspace
from cadguard.changeset import apply, propose
from cadguard.textcodec import _TCVN3, _VNI_BREVE, _VNI_CIRC, _VNI_SINGLE, _VNI_TONE
from cadguard.unicode_convert import convert_mtext, decode_with

BASES = "aăâeêioôơuưy"
TONES = ["", "̀", "́", "̃", "̉", "̣"]
LOWER = sorted({unicodedata.normalize("NFC", b + t) for b in BASES for t in TONES} - set(BASES) | set("ăâêôơưđ"))
ALL = LOWER + [c.upper() for c in LOWER]


def _enc_tcvn3(s: str) -> str:
    inv = {v: chr(k) for k, v in _TCVN3.items() if v.islower() or v in "ĂÂÊÔƠƯĐ"}
    return "".join(inv.get(c, c) for c in s)


def _enc_vni(ch: str) -> str:
    inv_single = {v: k for k, v in _VNI_SINGLE.items() if v in "ơưđƠƯĐ"}
    d = unicodedata.normalize("NFD", ch)
    base, marks = d[0], d[1:]
    tone = next((m for m in marks if m in TONES[1:]), "")
    up = base.isupper()
    if "̂" in marks:  # mũ
        return base + next(k for k, v in _VNI_CIRC.items() if v == tone and k.isupper() == up)
    if "̆" in marks:  # trăng
        return base + next(k for k, v in _VNI_BREVE.items() if v == tone and k.isupper() == up)
    if "̛" in marks:  # móc: ơ ư
        b = inv_single[unicodedata.normalize("NFC", base + "̛")]
        return b + (next(k for k, v in _VNI_TONE.items() if v == tone and k.isupper() == up) if tone else "")
    if base in "iI":
        if not tone:
            return base
        return next(k for k, v in _VNI_SINGLE.items() if unicodedata.normalize("NFD", v)[1:] == tone and k.isupper() == up)
    return base + next(k for k, v in _VNI_TONE.items() if v == tone and k.isupper() == up)


def test_table_covers_134_letters_roundtrip():
    assert len(ALL) == 134
    for c in LOWER:
        assert decode_with(_enc_tcvn3(c), "tcvn3") == c, c
        assert decode_with(_enc_tcvn3(c), "tcvn3-upper") == c.upper(), c  # phông chữ hoa .VnXxxH
    for c in ALL:
        if c in "đĐ":
            enc = {"đ": "ñ", "Đ": "Ñ"}[c]
        else:
            enc = _enc_vni(c)
        assert decode_with(enc, "vni") == c, (c, enc)


def test_mtext_inline_fonts_and_codes_untouched():
    raw = r"{\f.VnTime|b0|i0|c0|p18;mÆt b»ng}\P\H2.5x;{\fArial|b0;Tủ bếp}"
    new, changed = convert_mtext(raw, None, False, "Be Vietnam Pro")
    assert changed
    assert new == r"{\fBe Vietnam Pro|b0|i0|c0|p18;mặt bằng}\P\H2.5x;{\fArial|b0;Tủ bếp}"
    assert convert_mtext(new, None, False, "Be Vietnam Pro") == (new, False)


@pytest.fixture()
def ws(tmp_path) -> Path:
    fixtures.make_model_sheets(tmp_path / "m.dxf")
    return tmp_path


def test_convert_whole_drawing_idempotent(ws):
    w = Workspace(ws)
    cs, pv = propose(w, "m.dxf", [{"op": "convert_unicode"}])
    assert pv["ok"] and pv["ops"][0]["affected"] == 6 and "VS-07" in pv["rules"]["resolved"]
    res = apply(w, cs.id, confirm=True)
    doc = ezdxf.readfile(ws / res["output"]["path"])
    texts = [e.dxf.text for e in doc.modelspace().query("TEXT")]
    assert texts[:3] == ["tủ bếp trên", "cánh tủ MDF chống ẩm 18mm", "nẹp chỉ nhôm"]
    st = doc.styles.get("VN-ARIAL")
    assert st.dxf.font == "BeVietnamPro-Regular.ttf" and st.get_extended_font_data()[0] == "Be Vietnam Pro"
    assert [e.text for e in doc.modelspace().query("MTEXT")][:1] == ["Tủ áo cánh mở"]  # Unicode sẵn: giữ nguyên
    _cs2, pv2 = propose(w, res["output"]["path"], [{"op": "convert_unicode"}])
    assert pv2["ops"][0]["affected"] == 0  # chạy lần hai không đổi thêm


def test_convert_selected_handles_uses_new_style(ws):
    doc = ezdxf.readfile(ws / "m.dxf")
    first = doc.modelspace().query("TEXT")[0]
    w = Workspace(ws)
    cs, pv = propose(w, "m.dxf", [{"op": "convert_unicode", "handles": [first.dxf.handle]}])
    assert pv["ok"] and pv["ops"][0]["affected"] == 1
    out = ezdxf.readfile(ws / apply(w, cs.id, confirm=True)["output"]["path"])
    e = out.entitydb.get(first.dxf.handle)
    assert e.dxf.text == "tủ bếp trên" and e.dxf.style == "VN-ARIAL-UNICODE"
    assert out.styles.get("VN-ARIAL").dxf.font == ".VnArial"  # chữ chưa chuyển vẫn đọc đúng với kiểu cũ


def test_uncertain_left_alone(tmp_path):
    doc = ezdxf.new("R2018")
    doc.styles.add("A", font="arial.ttf")
    msp = doc.modelspace()
    msp.add_text("Tủ bếp", dxfattribs={"style": "A"})  # Unicode thật: bản vẽ không bị nhận là TCVN3
    t = msp.add_text("mÆt b»ng", dxfattribs={"style": "A"})
    doc.saveas(tmp_path / "u.dxf")
    _cs, pv = propose(Workspace(tmp_path), "u.dxf", [{"op": "convert_unicode"}])
    d = pv["ops"][0]
    assert d["affected"] == 0 and d["details"]["uncertain_handles"] == [t.dxf.handle]


def test_style_family_read_by_both_readers(tmp_path):
    from cadguard.dxf_reader import read_dxf
    from cadguard.dxf_stream import read_dxf_stream
    from cadguard.textcodec import style_encodings

    doc = ezdxf.new("R2018")
    st = doc.styles.add("AVANH", font="")
    st.set_extended_font_data(family=".VnAvantH")
    doc.saveas(tmp_path / "f.dxf")
    for reader in (read_dxf, read_dxf_stream):
        m = reader(tmp_path / "f.dxf")
        assert next(s for s in m.styles if s.name == "AVANH").family == ".VnAvantH"
        assert style_encodings(m)["avanh"] == "tcvn3-upper"


def test_multileader_converted(ws):
    w = Workspace(ws)
    cs, pv = propose(w, "m.dxf", [{"op": "convert_unicode"}])
    assert pv["ops"][0]["details"]["by_type"].get("MULTILEADER") == 1
    doc = ezdxf.readfile(ws / apply(w, cs.id, confirm=True)["output"]["path"])
    ml = doc.modelspace().query("MULTILEADER")[0]
    assert "đèn hắt trần" in ml.context.mtext.default_content
