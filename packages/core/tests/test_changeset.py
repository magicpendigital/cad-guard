"""Test công cụ ghi an toàn (A2): changeset, apply, validate_output, undo, CLI. Chỉ dùng DXF tổng hợp (fixtures.py)."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import ezdxf
import pytest

import cadguard
from cadguard import fixtures
from cadguard.agent.anonymize import Anonymizer
from cadguard.agent.tools import ToolContext, ToolError, audit, propose_changeset, query_model
from cadguard.agent.workspace import Workspace
from cadguard.changeset import ChangesetError, OpError, apply, parse_ops, propose, undo, validate_output
from cadguard.changeset.diff import sha256_file
from cadguard.changeset.engine import Protection, iter_layout_entities, read_doc
from cadguard.dxf_reader import read_dxf
from cadguard.runner import audit_model
from cadguard.standard import load_profile

REPO = Path(__file__).resolve().parents[3]
STDS = REPO / "standards"
CORE = Path(cadguard.__file__).resolve().parents[1]
BAD = "hygiene_bad.dxf"


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    fixtures.make_hygiene_bad(root / BAD)
    fixtures.make_hygiene_ok(root / "hygiene_ok.dxf")
    return Workspace(root)


def _rules(path, hygiene) -> set[str]:
    return {f.rule_id for f in audit_model(read_dxf(path), hygiene).findings}


def _layout_counts(path) -> dict:
    doc = read_doc(path)
    out = {}
    for _space, e in iter_layout_entities(doc):
        out[e.dxftype()] = out.get(e.dxftype(), 0) + 1
    return out


# Mỗi thao tác: (danh sách thao tác, luật VS phải hết sau khi áp)
CASES = {
    "merge_layers": ([{"op": "merge_layers", "sources": ["SYNX1|SYN-TUONG", "SYNX2$0$SYN-CUA"], "target": "SYN-TUONG"}], {"VS-01"}),
    "rename_layer": ([{"op": "rename_layer", "from": "SYNX1|SYN-TUONG", "to": "SYN-TUONG-CU"},
                      {"op": "rename_layer", "from": "SYNX2$0$SYN-CUA", "to": "SYN-CUA"}], {"VS-01"}),
    "move_to_layer": ([{"op": "move_to_layer", "filter": {"layers": ["0"], "spaces": ["Model"]}, "target": "SYN-NOI-THAT"}], {"VS-03"}),
    "set_bylayer": ([{"op": "set_bylayer", "filter": {"layers": ["SYN-TUONG"]}}], {"VS-04"}),
    "replace_text_style": ([{"op": "replace_text_style", "from": ["SYN-VN-SHX"], "to": "SYN-CHU"}], {"VS-07"}),
    "purge_unused": ([{"op": "purge_unused", "kinds": ["text_styles", "dim_styles"]}], {"VS-02"}),
    "replace_dim_style": ([{"op": "replace_dim_style", "to": "EZDXF"},
                           {"op": "purge_unused", "kinds": ["dim_styles", "text_styles"]}], {"VS-02"}),
    "clear_dim_text_override": ([{"op": "clear_dim_text_override", "filter": {"types": ["DIMENSION"]}}], {"VS-06"}),
    "set_text_height": ([{"op": "set_text_height", "filter": {"layers": ["SYN-CHU"]}, "from_height": 100, "to": 250}], set()),
}


@pytest.mark.parametrize("name", list(CASES))
def test_each_op_fixes_rule_and_validates(ws, hygiene, name):
    ops, fixed = CASES[name]
    src = ws.root / BAD
    sha_before = sha256_file(src)
    before = _rules(src, hygiene)
    assert fixed <= before

    cs, pv = propose(ws, BAD, ops, standard="design-hygiene-v0", standards_dir=STDS)
    assert pv["ok"] and pv["rules_regressed"] == 0
    assert fixed <= set(pv["rules"]["resolved"])
    assert all(r["affected"] > 0 or r.get("details") for r in pv["ops"])  # gộp/đổi tên layer rỗng: chỉ đổi định nghĩa
    assert not list(ws.root.glob("*.cg-*.dxf"))  # chạy khô: không ghi DXF
    assert (ws.root / ".cadguard" / "changesets" / f"{cs.id}.json").is_file()

    res = apply(ws, cs.id, confirm=True, standards_dir=STDS)
    out = ws.root / res["output"]["path"]
    assert out.name == f"hygiene_bad.cg-{cs.id[3:11]}.dxf" and out.parent == src.parent
    assert sha256_file(src) == sha_before  # gốc không đổi
    assert res["source"]["sha256"] == sha_before and res["output"]["sha256"] == sha256_file(out)

    val = validate_output(src, out, parse_ops(cs.ops), Protection(), hygiene, cs.source.sha256)
    assert val["ok"], val["checks"]
    assert val["rules_regressed"] == 0
    after = _rules(out, hygiene)
    assert not (fixed & after)
    assert after <= before
    assert _layout_counts(out) == _layout_counts(src)


def test_set_text_height_values_and_dim_attrs(ws, hygiene):
    cs, _ = propose(ws, BAD, CASES["set_text_height"][0] + CASES["clear_dim_text_override"][0], standards_dir=STDS)
    out = ws.root / apply(ws, cs.id, confirm=True, standards_dir=STDS)["output"]["path"]
    doc = read_doc(out)
    msp = doc.modelspace()
    assert sorted(t.dxf.height for t in msp.query("TEXT")) == [250.0, 250.0]
    assert [m.dxf.char_height for m in msp.query("MTEXT")] == [250.0]
    assert all(d.dxf.get("text", "") in ("", "<>") for d in msp.query("DIMENSION"))
    assert all(d.dxf.geometry in doc.blocks for d in msp.query("DIMENSION"))  # khối hình được vẽ lại, còn tồn tại
    # chữ trong định nghĩa khối không bị chạm
    assert [t.dxf.height for t in doc.blocks.get("SYN-GHE").query("TEXT")] == [50.0]


def test_full_cleanup_preview_numbers(ws, hygiene):
    ops = [o for key in ("merge_layers", "move_to_layer", "set_bylayer", "replace_text_style", "clear_dim_text_override")
           for o in CASES[key][0]] + [{"op": "purge_unused"}]
    cs, pv = propose(ws, BAD, ops, standards_dir=STDS)
    assert pv["ok"] and pv["rules"]["before"]["VS-05"] == 11
    assert set(pv["rules"]["resolved"]) == {"VS-01", "VS-02", "VS-03", "VS-04", "VS-06", "VS-07"}
    assert pv["rules"]["after"] == {"VS-05": 11}  # không có thao tác xoá đối tượng: IMAGE vẫn còn
    assert pv["diff"]["added"] == 0 and pv["diff"]["removed"] == 0 and pv["diff"]["changed"] == 9
    stored = json.loads((ws.root / ".cadguard" / "changesets" / f"{cs.id}.json").read_text(encoding="utf-8"))
    assert stored["schema"] == "cg.changeset/1" and stored["id"] == cs.id and stored["created_by"] == "user"
    assert stored["source"] == {"path": BAD, "sha256": sha256_file(ws.root / BAD)}
    assert stored["standard"] == "design-hygiene-v0" and stored["standard_version"] and stored["created_at"]
    text = json.dumps(stored, ensure_ascii=False)
    assert str(ws.root) not in text and str(ws.root).replace("\\", "/") not in text and json.dumps(str(ws.root))[1:-1] not in text


def test_purge_never_removes_geometry(ws, hygiene):
    doc = ezdxf.readfile(ws.root / BAD)
    unused = doc.blocks.new("SYN-KHOI-THUA")
    unused.add_line((0, 0), (1, 1), dxfattribs={"layer": "SYN-TUONG"})
    doc.layers.add("SYN-RONG")
    doc.saveas(ws.root / "purge.dxf")
    before = _layout_counts(ws.root / "purge.dxf")
    cs, pv = propose(ws, "purge.dxf", [{"op": "purge_unused"}], standards_dir=STDS)
    removed = pv["ops"][0]["details"]["removed"]
    assert "SYN-KHOI-THUA" in removed["blocks"] and "SYN-RONG" in removed["layers"]
    assert "SYN-GHE" not in removed["blocks"]  # khối đang dùng: giữ
    for keep in ("0", "SYN-TUONG", "SYN-NOI-THAT", "SYN-CHU", "SYN-KICH-THUOC"):
        assert keep not in removed["layers"]
    assert "SYN-VN-SHX" not in removed["text_styles"] and "Standard" not in removed["text_styles"]
    out = ws.root / apply(ws, cs.id, confirm=True, standards_dir=STDS)["output"]["path"]
    assert _layout_counts(out) == before
    out_doc = read_doc(out)
    assert "SYN-GHE" in out_doc.blocks and "SYN-KHOI-THUA" not in out_doc.blocks
    assert len(out_doc.blocks.get("SYN-GHE")) == len(read_doc(ws.root / "purge.dxf").blocks.get("SYN-GHE"))


def test_apply_requires_confirm_and_never_overwrites(ws):
    cs, _ = propose(ws, BAD, CASES["set_bylayer"][0], standards_dir=STDS)
    with pytest.raises(ChangesetError, match="xác nhận"):
        apply(ws, cs.id, confirm=False, standards_dir=STDS)
    res = apply(ws, cs.id, confirm=True, standards_dir=STDS)
    out = ws.root / res["output"]["path"]
    sha_out = sha256_file(out)
    with pytest.raises(ChangesetError, match="không ghi đè"):
        apply(ws, cs.id, confirm=True, standards_dir=STDS)
    assert sha256_file(out) == sha_out

    cs2, _ = propose(ws, BAD, CASES["set_bylayer"][0], standards_dir=STDS)
    squatter = ws.root / f"hygiene_bad.cg-{cs2.id[3:11]}.dxf"
    squatter.write_bytes(b"tep cua nguoi dung")
    with pytest.raises(ChangesetError, match="không ghi đè"):
        apply(ws, cs2.id, confirm=True, standards_dir=STDS)
    assert squatter.read_bytes() == b"tep cua nguoi dung"


def test_source_changed_after_propose_is_refused(ws):
    cs, _ = propose(ws, BAD, CASES["set_bylayer"][0], standards_dir=STDS)
    doc = ezdxf.readfile(ws.root / BAD)
    doc.modelspace().add_line((0, 0), (5, 5))
    doc.saveas(ws.root / BAD)
    with pytest.raises(ChangesetError, match="đã thay đổi"):
        apply(ws, cs.id, confirm=True, standards_dir=STDS)
    assert not list(ws.root.glob("*.cg-*.dxf"))


def test_protected_layers_refused_or_skipped(ws, tmp_path):
    with pytest.raises(OpError, match="bảo vệ"):
        propose(ws, BAD, [{"op": "move_to_layer", "filter": {"layers": ["0"]}, "target": "SYN-TUONG"}],
                standards_dir=STDS, protected_layers=["SYN-TUONG"])
    with pytest.raises(OpError, match="bảo vệ"):
        propose(ws, BAD, CASES["set_bylayer"][0], standards_dir=STDS, protected_layers=["syn-tuong"])
    with pytest.raises(OpError, match="bảo vệ"):
        propose(ws, BAD, [{"op": "rename_layer", "from": "SYN-TUONG", "to": "X"}], standards_dir=STDS, protected_layers=["SYN-TUONG"])
    with pytest.raises(OpError, match="bảo vệ"):
        propose(ws, BAD, [{"op": "purge_unused", "names": ["SYN-TUONG"]}], standards_dir=STDS, protected_layers=["SYN-TUONG"])
    # bộ lọc rộng: đối tượng trên layer bảo vệ bị bỏ qua, không đổi
    cs, pv = propose(ws, BAD, [{"op": "set_bylayer"}], standards_dir=STDS, protected_layers=["SYN-TUONG"])
    assert pv["ops"][0]["skipped_protected"] == 10 and pv["ops"][0]["affected"] == 0
    assert pv["rules"]["after"]["VS-04"] == pv["rules"]["before"]["VS-04"]
    # mẫu từ hồ sơ công ty (layer_patterns.protected)
    prof = tmp_path / "hs.yaml"
    prof.write_text("schema: cg.company-profile/1\nname: hs-thu\nversion: 0.1.0\nstandard: design-hygiene-v0\n"
                    "layer_patterns:\n  protected: ['^SYN-TUO']\n", encoding="utf-8")
    profile = load_profile(prof)
    cs, pv = propose(ws, BAD, [{"op": "set_bylayer"}], standards_dir=STDS, profile=profile)
    assert pv["protection"]["patterns"] == ["^SYN-TUO"] and pv["ops"][0]["skipped_protected"] == 10
    assert pv["profile"] == {"name": "hs-thu", "version": "0.1.0"}
    with pytest.raises(ChangesetError, match="hồ sơ"):
        apply(ws, cs.id, confirm=True, standards_dir=STDS)  # thiếu hồ sơ lúc áp
    apply(ws, cs.id, confirm=True, standards_dir=STDS, profile=profile)


def test_bad_profile_protected_pattern(tmp_path):
    from cadguard.standard import ProfileError

    prof = tmp_path / "hs.yaml"
    prof.write_text("schema: cg.company-profile/1\nname: x\nversion: 0.1.0\nstandard: design-hygiene-v0\n"
                    "layer_patterns:\n  protected: ['([']\n", encoding="utf-8")
    with pytest.raises(ProfileError, match="protected"):
        load_profile(prof)


def _tampered(ws, cs, mutate) -> Path:
    """Tệp ra 'giả' dựng từ bản áp đúng rồi sửa thêm, để thử validate_output."""
    out = ws.root / apply(ws, cs.id, confirm=True, standards_dir=STDS)["output"]["path"]
    doc = ezdxf.readfile(out)
    mutate(doc)
    bad = ws.root / "tampered.dxf"
    doc.saveas(bad)
    return bad


def test_validate_detects_protected_change(ws, hygiene):
    cs, _ = propose(ws, BAD, CASES["set_bylayer"][0], standards_dir=STDS, protected_layers=["SYN-CHU"])

    def mutate(doc):
        for t in doc.modelspace().query("TEXT"):
            t.dxf.color = 3

    bad = _tampered(ws, cs, mutate)
    val = validate_output(ws.root / BAD, bad, parse_ops(cs.ops), Protection(layers=["SYN-CHU"]), hygiene, cs.source.sha256)
    checks = {c["id"]: c for c in val["checks"]}
    assert not val["ok"] and not checks["protected_layers"]["ok"] and "bảo vệ" in checks["protected_layers"]["message"]


def test_validate_detects_geometry_and_disallowed_attrs(ws, hygiene):
    cs, _ = propose(ws, BAD, CASES["set_bylayer"][0], standards_dir=STDS)

    def mutate(doc):
        msp = doc.modelspace()
        msp.query("LINE")[0].dxf.end = (1, 2, 0)
        msp.delete_entity(msp.query("CIRCLE")[0])

    bad = _tampered(ws, cs, mutate)
    val = validate_output(ws.root / BAD, bad, parse_ops(cs.ops), Protection(), hygiene, cs.source.sha256)
    checks = {c["id"]: c for c in val["checks"]}
    assert not checks["entity_count"]["ok"] and "1 xoá" in checks["entity_count"]["message"]
    assert not checks["allowed_attrs"]["ok"] and "end" in checks["allowed_attrs"]["message"]
    assert checks["source_hash"]["ok"]


def test_regression_predicted_and_apply_refused(ws):
    ops = [{"op": "move_to_layer", "filter": {"layers": ["SYN-TUONG"]}, "target": "0"}]  # làm VS-03 tăng
    cs, pv = propose(ws, BAD, ops, standards_dir=STDS)
    assert not pv["ok"] and pv["rules_regressed"] == 1 and pv["rules"]["regressed"] == ["VS-03"]
    with pytest.raises(ChangesetError, match="KHÔNG ĐẠT"):
        apply(ws, cs.id, confirm=True, standards_dir=STDS)
    assert not list(ws.root.glob("*.cg-*.dxf")) and not list(ws.root.glob(".*.part"))


@pytest.mark.parametrize("ops, needle", [
    ([], "không rỗng"),
    ([{"op": "delete_entities", "filter": {}}], "không có trong từ vựng"),
    ([{"filter": {}}], "thiếu trường 'op'"),
    ([{"op": "rename_layer", "from": "A"}], "thiếu trường bắt buộc"),
    ([{"op": "set_bylayer", "mau": 1}], "trường lạ"),
    ([{"op": "set_text_height", "to": -1}], "ngoài khoảng"),
    ([{"op": "purge_unused", "kinds": ["entities"]}], "không thuộc danh sách"),
    ([{"op": "move_to_layer", "filter": {"layers": "0"}, "target": "X"}], "sai kiểu"),
    ({"khong": "phai danh sach"}, "mảng JSON"),
])
def test_schema_errors_in_vietnamese(ops, needle):
    with pytest.raises(OpError) as exc:
        parse_ops(ops)
    assert needle in str(exc.value)


@pytest.mark.parametrize("ops, needle", [
    ([{"op": "move_to_layer", "target": "KHONG-CO"}], "không có layer 'KHONG-CO'"),
    ([{"op": "rename_layer", "from": "SYN-TUONG", "to": "SYN-CHU"}], "dùng merge_layers"),
    ([{"op": "rename_layer", "from": "0", "to": "X"}], "layer hệ thống"),
    ([{"op": "replace_text_style", "to": "KHONG-CO"}], "chỉ đổi sang kiểu đã có"),
    ([{"op": "replace_text_style", "filter": {"types": ["LINE"]}, "to": "SYN-CHU"}], "không áp dụng được"),
])
def test_reference_errors(ws, ops, needle):
    with pytest.raises(OpError, match=re.escape(needle)):
        propose(ws, BAD, ops, standards_dir=STDS)
    assert not (ws.root / ".cadguard" / "changesets").exists() or not list((ws.root / ".cadguard" / "changesets").iterdir())


def test_undo_removes_only_output(ws):
    src = ws.root / BAD
    sha = sha256_file(src)
    cs, _ = propose(ws, BAD, CASES["set_bylayer"][0], standards_dir=STDS)
    with pytest.raises(ChangesetError, match="chưa được áp dụng"):
        undo(ws, cs.id, confirm=True)
    out = ws.root / apply(ws, cs.id, confirm=True, standards_dir=STDS)["output"]["path"]
    res = undo(ws, cs.id, confirm=True)
    assert not out.exists() and src.exists() and sha256_file(src) == sha and res["removed"] == out.name
    log = json.loads((ws.root / ".cadguard" / "changesets" / f"{cs.id}.apply.json").read_text(encoding="utf-8"))
    assert log["undone_at"] and log["source"]["sha256"] == sha
    with pytest.raises(ChangesetError, match="đã được hoàn tác"):
        undo(ws, cs.id, confirm=True)

    cs2, _ = propose(ws, BAD, CASES["set_bylayer"][0], standards_dir=STDS)
    out2 = ws.root / apply(ws, cs2.id, confirm=True, standards_dir=STDS)["output"]["path"]
    out2.write_bytes(out2.read_bytes() + b"\n")  # người dùng đã sửa tệp ra
    with pytest.raises(ChangesetError, match="đã bị sửa"):
        undo(ws, cs2.id, confirm=True)
    assert out2.exists()


def test_changeset_ref_must_stay_in_store(ws, tmp_path):
    with pytest.raises(ChangesetError):
        apply(ws, "../../x.json", confirm=True)
    outside = tmp_path / "cs-000000000000.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ChangesetError):
        apply(ws, str(outside), confirm=True)


# ---------- công cụ cho trợ lý (ẩn danh, không cần SDK MCP) ----------


@pytest.fixture
def ctx(ws):
    return ToolContext(ws, Anonymizer(True, "salt"), STDS)


def test_tool_propose_decodes_tokens_and_anonymizes(ctx, ws):
    anon = ctx.anonymizer
    vs07 = next(f for f in audit(ctx, BAD, "design-hygiene-v0")["findings"] if f["rule_id"] == "VS-07")
    bad_style = re.search(r"S_[0-9a-f]{10}", vs07["message"]).group()
    texts = query_model(ctx, BAD, {"type": "TEXT"})["items"]
    good_style = next(t["text_style"] for t in texts if t["text_style"] != bad_style)
    layer_tok = texts[0]["layer"]
    assert bad_style == anon.token("style", "SYN-VN-SHX") and layer_tok == anon.token("layer", "SYN-CHU")

    res = propose_changeset(ctx, BAD, [{"op": "replace_text_style", "filter": {"layers": [layer_tok]}, "from": [bad_style], "to": good_style},
                                       {"op": "purge_unused", "kinds": ["text_styles"]}], "design-hygiene-v0", [anon.token("layer", "SYN-TUONG")])
    assert res["ok"] and "VS-07" in res["rules"]["resolved"] and res["rules_regressed"] == 0
    assert res["ops"][0]["from"] == [bad_style]  # trả lại đúng mã trợ lý đã gửi
    assert res["protection"]["layers"] == [anon.token("layer", "SYN-TUONG")]
    assert anon.token("style", "SYN-VN-SHX") in res["ops_report"][1]["details"]["removed"]["text_styles"]
    text = json.dumps(res, ensure_ascii=False)
    for secret in ("SYN-VN-SHX", "SYN-CHU", "SYN-TUONG", "OpenSans", "hygiene_bad", str(ws.root)):
        assert secret not in text, secret
    assert "cadguard apply" in res["apply"]

    stored = json.loads((ws.root / ".cadguard" / "changesets" / f"{res['changeset_id']}.json").read_text(encoding="utf-8"))
    assert stored["created_by"] == "agent"
    assert stored["ops"][0] == {"op": "replace_text_style", "filter": {"layers": ["SYN-CHU"]}, "from": ["SYN-VN-SHX"],
                                "to": "SYN-CHU", } and stored["protection"]["layers"] == ["SYN-TUONG"]
    assert stored["source"]["path"] == BAD
    # người dùng áp dụng changeset do trợ lý đề xuất
    out = ws.root / apply(ws, res["changeset_id"], confirm=True, standards_dir=STDS)["output"]["path"]
    assert out.is_file()


def test_tool_propose_errors_are_safe(ctx):
    with pytest.raises(ToolError, match="không khớp tên nào"):
        propose_changeset(ctx, BAD, [{"op": "move_to_layer", "target": "L_0123456789"}])
    with pytest.raises(ToolError, match="không có trong từ vựng"):
        propose_changeset(ctx, BAD, [{"op": "xoa_het"}])
    tok = ctx.anonymizer.token("layer", "SYN-TUONG")
    to_tok = ctx.anonymizer.token("layer", "SYN-CHU")
    with pytest.raises(ToolError) as exc:
        propose_changeset(ctx, BAD, [{"op": "rename_layer", "from": tok, "to": to_tok}])
    msg = str(exc.value)
    assert "merge_layers" in msg and to_tok in msg  # lỗi tham chiếu nêu lại bằng mã, không lộ tên thật
    assert "SYN-TUONG" not in msg and "SYN-CHU" not in msg


def test_anonymizer_decoder():
    anon = Anonymizer(True, "s")
    dec = anon.decoder([("layer", "A"), ("style", "B"), ("dimstyle", "C")])
    assert dec("layer", anon.token("layer", "A")) == "A"
    assert dec("any", anon.token("dimstyle", "C")) == "C"
    assert dec("layer", "TEN-MOI") == "TEN-MOI" and dec("layer", "0") == "0"
    with pytest.raises(ValueError):
        dec("style", anon.token("layer", "A"))  # sai loại
    plain = Anonymizer(False).decoder([("layer", "A")])
    assert plain("layer", "L_0123456789") == "L_0123456789"


# ---------- CLI ----------


def _cli(args, cwd, stdin=subprocess.DEVNULL):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "CADGUARD_STANDARDS")}
    env.update({"PYTHONPATH": str(CORE), "PYTHONUTF8": "1", "CADGUARD_STANDARDS": str(STDS)})
    return subprocess.run([sys.executable, "-m", "cadguard", *args], cwd=cwd, env=env, capture_output=True,
                          timeout=120, stdin=stdin)


def test_cli_propose_apply_diff_validate(ws, tmp_path):
    ops_file = tmp_path / "ops.json"
    ops_file.write_text(json.dumps({"ops": CASES["set_bylayer"][0] + CASES["clear_dim_text_override"][0]}), encoding="utf-8")
    p = _cli(["propose", str(ws.root / BAD), "--ops", str(ops_file), "--json"], tmp_path)
    assert p.returncode == 0, p.stderr.decode("utf-8", "replace")
    pv = json.loads(p.stdout.decode("utf-8"))
    cid = pv["changeset_id"]
    assert set(pv["rules"]["resolved"]) == {"VS-04", "VS-06"}

    # không TTY, không --yes -> từ chối, không ghi
    a = _cli(["apply", cid, "--workspace", str(ws.root)], tmp_path)
    assert a.returncode == 2 and "Từ chối" in a.stderr.decode("utf-8") and not list(ws.root.glob("*.cg-*.dxf"))
    assert "Changeset" in a.stdout.decode("utf-8")  # vẫn in xem trước

    cs_path = ws.root / ".cadguard" / "changesets" / f"{cid}.json"
    a = _cli(["apply", str(cs_path), "--yes"], tmp_path)
    assert a.returncode == 0, a.stderr.decode("utf-8", "replace")
    out = ws.root / f"hygiene_bad.cg-{cid[3:11]}.dxf"
    assert out.is_file() and "Đã ghi tệp mới" in a.stdout.decode("utf-8")

    d = _cli(["diff", str(ws.root / BAD), str(out), "--json"], tmp_path)
    assert d.returncode == 0
    dj = json.loads(d.stdout.decode("utf-8"))
    assert dj["summary"]["changed"] == 5 and dj["summary"]["added"] == dj["summary"]["removed"] == 0

    v = _cli(["validate", str(ws.root / BAD), str(out), "--changeset", str(cs_path)], tmp_path)
    assert v.returncode == 0, v.stdout.decode("utf-8", "replace") + v.stderr.decode("utf-8", "replace")
    assert "ĐẠT" in v.stdout.decode("utf-8")

    u = _cli(["undo", cid, "--workspace", str(ws.root)], tmp_path)
    assert u.returncode == 2 and out.exists()
    u = _cli(["undo", cid, "--workspace", str(ws.root), "--yes"], tmp_path)
    assert u.returncode == 0 and not out.exists()


def test_cli_propose_bad_ops_vietnamese(ws, tmp_path):
    ops_file = tmp_path / "ops.json"
    ops_file.write_text(json.dumps([{"op": "xoa_doi_tuong"}]), encoding="utf-8")
    p = _cli(["propose", str(ws.root / BAD), "--ops", str(ops_file)], tmp_path)
    assert p.returncode == 2 and "không có trong từ vựng" in p.stderr.decode("utf-8")


def test_apply_tolerates_explicit_defaults_written_by_autocad(tmp_path):
    """AutoCAD ghi tường minh giá trị mặc định (vd. độ rộng nét 43 = 0.0); ezdxf bỏ khi lưu. Không được coi là
    'thuộc tính bị đổi ngoài phạm vi' (lỗi gặp ở bản vẽ thật 10/11: const_width ×6056)."""
    root = tmp_path / "ws"
    root.mkdir()
    doc = ezdxf.new("R2018")
    doc.layers.add("CU")
    msp = doc.modelspace()
    for i in range(3):
        msp.add_lwpolyline([(0, i), (100, i), (100, i + 50)], dxfattribs={"layer": "CU"})
    raw = root / "raw.dxf"
    doc.saveas(raw)
    lines = raw.read_text(encoding="utf-8").splitlines()
    out_lines, i, injected = [], 0, 0
    while i < len(lines):
        out_lines.append(lines[i])
        if lines[i].strip() == "90" and i > 0 and any(x.strip() == "LWPOLYLINE" for x in lines[max(0, i - 30):i]):
            out_lines.append(lines[i + 1])
            out_lines += [" 43", "0.0"]
            injected += 1
            i += 2
            continue
        i += 1
    assert injected == 3
    (root / "autocad.dxf").write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    assert read_doc(root / "autocad.dxf").modelspace().query("LWPOLYLINE")[0].dxf.hasattr("const_width")
    ws = Workspace(root)
    cs, pv = propose(ws, "autocad.dxf", [{"op": "rename_layer", "from": "CU", "to": "MOI"}], standard="design-hygiene-v0",
                     standards_dir=STDS)
    assert pv["ok"]
    res = apply(ws, cs.id, confirm=True, standards_dir=STDS)
    assert res["validation"]["ok"], res["validation"]["checks"]
