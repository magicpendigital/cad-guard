"""Chỉ mục tờ (`sheets.py`), giải mã chữ TCVN3/VNI (`textcodec.py`), bậc chốt tờ (`gate.py`) và API chốt tờ của app."""
from __future__ import annotations

from pathlib import Path

import ezdxf
import pytest

from cadguard import fixtures, gate
from cadguard.app.api import (ApiError, AppConfig, AppData, ack_finding, audit_file, lock_sheet, sheets_info,
                              unlock_sheet)
from cadguard.app.geometry import drawing_geometry
from cadguard.dxf_reader import read_dxf
from cadguard.dxf_stream import read_dxf_stream
from cadguard.sheets import build_structure, paper_match
from cadguard.standard import ProfileError, load_standard
from cadguard.textcodec import decode, drawing_looks_tcvn3, font_encoding

REPO = Path(__file__).resolve().parents[3]
STDS = REPO / "standards"


@pytest.fixture(autouse=True)
def _private_config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))


@pytest.fixture(scope="module")
def sheet_dxf(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("sheets") / "sheet_set.dxf"
    fixtures.make_sheet_set(p)
    return p


# ---------- giải mã chữ ----------

def test_decode_tcvn3_vni_and_font_detection():
    assert decode("mÆt b»ng", "tcvn3") == ("mặt bằng", "font")
    assert decode("néi thÊt tÇng 7", None, guess=True) == ("nội thất tầng 7", "guess")
    assert decode("cöa t4-5-6", None, guess=True)[1] is None  # 1 ký tự đặc trưng: không đoán từng chữ
    assert decode("cöa t4-5-6", None, guess="drawing") == ("cửa t4-5-6", "guess")  # cả bản vẽ đã nhận là TCVN3
    assert decode("noäi thaát taàng 7, cöûa, ñöôøng, tuû aùo", "vni")[0] == "nội thất tầng 7, cửa, đường, tủ áo"
    assert decode("Phòng ngủ", None, guess=True) == ("Phòng ngủ", None)  # Unicode thật: giữ nguyên
    assert decode("Möbel 1200", None, guess=True) == ("Möbel 1200", None)
    assert [font_encoding(f) for f in (".VnTime", "VNTIMEH.TTF", "VNI-Times", "arial.ttf", "romans.shx")] == [
        "tcvn3", "tcvn3-upper", "vni", None, None]
    assert drawing_looks_tcvn3(["néi thÊt", "mÆt b»ng", "tñ bÕp"])
    assert not drawing_looks_tcvn3(["néi thÊt", "mÆt b»ng", "tñ bÕp", "Phòng ngủ"])


# ---------- chỉ mục tờ ----------

def test_paper_match():
    assert paper_match(8400, 5940) == ("A3", 20.0, True)
    assert paper_match(5940, 8400)[:2] == ("A3", 20.0)  # khổ đứng
    assert paper_match(1000, 1000) == (None, None, False)


@pytest.mark.parametrize("reader", [read_dxf, read_dxf_stream])
def test_structure_detects_sheets_titles_and_junk(sheet_dxf, reader):
    st = build_structure(reader(sheet_dxf))
    d = st.to_dict()
    sheets = d["sheets"]
    assert [s["name"] for s in sheets] == ["Tờ 1", "Tờ 2", "Tờ 3", "IN-CHI-TIET"]
    t1, t2, t3, lo = sheets
    assert (t1["title"], t1["title_source"], t1["paper"], t1["scale"], t1["scale_label"]) == (
        "MAT BANG BO TRI", "attrib", "A3", 20.0, "1/20")
    assert (t2["title"], t2["title_source"]) == ("mặt đứng tủ bếp", "text-decoded")  # theo phông .VnTime
    assert (t3["title"], t3["title_source"]) == ("chi tiết tủ áo", "text-decoded")  # đoán TCVN3
    assert t3["kind"] == "frame" and t3["frame_handle"] and t3["window"] == [0.0, 0.0, 8400.0, 5940.0]
    assert lo["kind"] == "layout" and lo["entity_count"] == 6 and lo["scale"] == 12.0
    assert all(s["entity_count"] >= 16 for s in (t1, t2, t3))
    junk = d["junk"]
    assert junk["outside"]["count"] == 1 and junk["stray"]["count"] == 1
    assert "RAC-RONG" in junk["empty_layers"] and junk["unused_blocks"] == ["KHOI_THUA"]
    assert d["text_encoding"]["styles"] == {"vn3": "tcvn3"}
    # đối tượng gán đúng tờ: kích thước ghi đè nằm trong tờ 3
    dim = next(e for e in reader(sheet_dxf).entities if e.type == "DIMENSION")
    assert st.sheet_of[dim.handle] == t3["id"]


def test_structure_same_for_both_readers(sheet_dxf):
    a = build_structure(read_dxf(sheet_dxf)).to_dict(include_map=True)
    b = build_structure(read_dxf_stream(sheet_dxf)).to_dict(include_map=True)
    assert a == b


def test_drawing_without_frames_has_no_sheets(tmp_path):
    p = tmp_path / "x.dxf"
    fixtures.ALL["hygiene_bad.dxf"](p)
    d = build_structure(read_dxf(p)).to_dict()
    assert all(s["kind"] == "layout" for s in d["sheets"])
    assert d["junk"]["outside"]["count"] == 0 or d["sheets"]


def test_simplified_geometry_has_model_transform(sheet_dxf):
    g = drawing_geometry(read_dxf(sheet_dxf))
    sx, sy, tx, ty = g["transform"]
    assert sx > 0 and sy < 0
    # điểm (0, 0) của tờ 3 nằm trong khung nhìn
    x, y = sx * 0 + tx, sy * 0 + ty
    assert 0 <= x <= g["viewbox"][2] and 0 <= y <= g["viewbox"][3]


# ---------- bậc chốt tờ ----------

def test_default_tiers_and_profile_gate(tmp_path):
    std = load_standard("design-hygiene-v0", STDS)
    assert gate.tier_of(std, "VS-06", "E") == "block"
    assert gate.tier_of(std, "VS-01", "W") == "warn"
    assert gate.tier_of(std, "VS-02", "W") == "hint"
    prof = tmp_path / "p.yaml"
    prof.write_text("schema: cg.company-profile/1\nname: t\nversion: 0.1.0\nstandard: design-hygiene-v0\n"
                    "gate:\n  block: [VS-01]\n  hint: [VS-06]\n  require_ack: false\n", encoding="utf-8")
    std2 = load_standard("design-hygiene-v0", STDS, profile=prof)
    assert gate.tier_of(std2, "VS-01", "W") == "block" and gate.tier_of(std2, "VS-06", "E") == "hint"
    assert std2.gate_require_ack is False
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema: cg.company-profile/1\nname: t\nversion: 0.1.0\nstandard: design-hygiene-v0\n"
                   "gate:\n  block: [XX-99]\n", encoding="utf-8")
    with pytest.raises(ProfileError, match="XX-99"):
        load_standard("design-hygiene-v0", STDS, profile=bad)
    both = tmp_path / "both.yaml"
    both.write_text("schema: cg.company-profile/1\nname: t\nversion: 0.1.0\nstandard: design-hygiene-v0\n"
                    "gate:\n  block: [VS-01]\n  warn: [VS-01]\n", encoding="utf-8")
    with pytest.raises(ProfileError, match="VS-01"):
        load_standard("design-hygiene-v0", STDS, profile=both)


# ---------- API app: tờ, xác nhận, chốt ----------

@pytest.fixture()
def app(tmp_path, sheet_dxf):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "s.dxf").write_bytes(sheet_dxf.read_bytes())
    return AppData(AppConfig(workspace=ws, standards_dir=STDS))


def test_audit_items_carry_sheet_and_tier(app):
    r = audit_file(app, "s.dxf", "design-hygiene-v0")
    rules = {g["rule_id"]: g for grp in r["groups"] for g in grp["rules"]}
    vs06 = rules["VS-06"]
    assert vs06["tier"] == "block" and vs06["tier_label"] == "Chặn"
    info = sheets_info(app, "s.dxf")
    t3 = next(s for s in info["sheets"] if s["name"] == "Tờ 3")
    assert all(it["sheets"] == [t3["id"]] for it in vs06["items"])
    assert r["gate"]["block"] >= 1 and r["gate"]["can_lock"] is False
    furn = audit_file(app, "s.dxf", "furniture-v0")
    sh04 = next(g for grp in furn["groups"] for g in grp["rules"] if g["rule_id"] == "SH-04")
    lo = next(it for it in sh04["items"] if it["layout"] == "IN-CHI-TIET")
    assert lo["sheets"] == ["L:IN-CHI-TIET"]  # lỗi của layout thuộc tờ layout đó, không lan sang tờ khác


def test_lock_flow_blocks_acks_and_goes_stale(app):
    info = sheets_info(app, "s.dxf")
    ids = {s["name"]: s["id"] for s in info["sheets"]}
    std = ["design-hygiene-v0"]
    with pytest.raises(ApiError, match="Chặn"):
        lock_sheet(app, "s.dxf", ids["Tờ 3"], std, confirm=True)
    with pytest.raises(ApiError, match="xác nhận"):
        lock_sheet(app, "s.dxf", ids["Tờ 1"], std)
    # tờ 1: cảnh báo chưa xác nhận thì chưa chốt được; xác nhận từng luật rồi chốt
    r = audit_file(app, "s.dxf", "design-hygiene-v0")
    warns = {g["rule_id"] for grp in r["groups"] for g in grp["rules"] if g["tier"] == "warn"
             and any(not it["sheets"] or ids["Tờ 1"] in it["sheets"] for it in g["items"])}
    if warns:
        with pytest.raises(ApiError, match="cảnh báo chưa xác nhận"):
            lock_sheet(app, "s.dxf", ids["Tờ 1"], std, confirm=True)
        with pytest.raises(ApiError, match="lý do"):
            ack_finding(app, "s.dxf", "design-hygiene-v0", sorted(warns)[0], ids["Tờ 1"], "skip", "")
        for rule in warns:
            ack_finding(app, "s.dxf", "design-hygiene-v0", rule, ids["Tờ 1"], "skip", "quy ước riêng của khách")
    with pytest.raises(ApiError, match="Chặn"):
        ack_finding(app, "s.dxf", "design-hygiene-v0", "VS-06", ids["Tờ 3"], "seen")
    out = lock_sheet(app, "s.dxf", ids["Tờ 1"], std, confirm=True)
    assert out["status"] == "locked"
    info = sheets_info(app, "s.dxf")
    assert info["locked"] == 1
    # trạng thái lưu cục bộ, không có tên tệp/tên người
    state_files = list((app.ws.root / ".cadguard" / "sheets").glob("*.json"))
    assert len(state_files) == 1 and "s.dxf" not in state_files[0].read_text(encoding="utf-8")
    # nội dung tờ 1 đổi -> tờ tự mở lại
    doc = ezdxf.readfile(app.ws.root / "s.dxf")
    doc.modelspace().add_line((100, 10100), (200, 10200), dxfattribs={"layer": "SYN-NOI-THAT"})
    doc.saveas(app.ws.root / "s.dxf")
    t1 = next(s for s in sheets_info(app, "s.dxf")["sheets"] if s["id"] == ids["Tờ 1"])
    assert t1["status"] == "open" and t1["stale"] is True
    assert unlock_sheet(app, "s.dxf", ids["Tờ 1"])["status"] == "open"


# ---------- bộ nhiều tờ trong Model kiểu công ty (Đợt B) ----------

@pytest.fixture(scope="module")
def model_sheets(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("msheets") / "model_sheets.dxf"
    fixtures.make_model_sheets(p)
    return p


@pytest.mark.parametrize("reader", [read_dxf, read_dxf_stream])
def test_model_sheets_counts_blank_and_factor(model_sheets, reader):
    st = build_structure(reader(model_sheets))
    frames = [s for s in st.sheets if s.kind == "frame"]
    assert len(frames) == len(fixtures.CO_SHEETS)  # khung kề nhau, khác tỉ lệ, kể cả tờ trống
    assert [s.factor for s in frames] == [k for k, *_ in fixtures.CO_SHEETS]
    assert [s.scale for s in frames] == [15, 15, 20, 20, 10, 15]  # 19,77 -> tỉ lệ chuẩn gần nhất 1:20
    assert all(s.block == fixtures.CO_FRAME and s.confidence >= 0.9 for s in frames)
    blank = frames[-1]
    assert blank.handles == [blank.frame_handle]  # tờ trống vẫn là tờ, khung thuộc chính nó
    assert len(st.outside) == 1  # khối ngoài mọi tờ
    assert [s.title for s in frames][:2] == ["MẶT BẰNG BỐ TRÍ", "MẶT BẰNG TRẦN"]


def test_learn_layers_silences_ly01(model_sheets, tmp_path):
    from cadguard import rule_config
    from cadguard.runner import audit_model

    m = read_dxf(model_sheets)
    before = [f for f in audit_model(m, rule_config.effective_standard("furniture-v0", STDS, workspace=tmp_path)).findings
              if f.rule_id == "LY-01"]
    assert before
    rule_config.learn_layers("furniture-v0", [la.name for la in m.layers], workspace=tmp_path, standards_dir=STDS)
    after = [f for f in audit_model(m, rule_config.effective_standard("furniture-v0", STDS, workspace=tmp_path)).findings
             if f.rule_id == "LY-01"]
    assert after == []
    assert rule_config.learn_layer_patterns(["A-1", "A-2", "A-3", "B", "0", "x|y"]) == [r"^A[-_. ]", "^B$"]


def test_render_sheets_svg(model_sheets, tmp_path):
    from cadguard.cli import main

    out = tmp_path / "to"
    assert main(["sheets", str(model_sheets), "--render", str(out), "--pick", "1,6"]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["index.html", "to-01.svg", "to-06.svg"]
    svg = (out / "to-01.svg").read_text(encoding="utf-8")
    assert svg.startswith("<?xml") and "<path" in svg
    assert main(["sheets", str(model_sheets), "--render", str(out), "--pick", "9"]) == 2
