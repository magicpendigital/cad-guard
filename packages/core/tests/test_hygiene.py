"""Chuẩn design-hygiene-v0 (VS-*) và hồ sơ công ty. Chỉ dùng DXF tổng hợp và mô hình dựng tay."""

from collections import Counter
from pathlib import Path

import pytest
import yaml

from cadguard import fixtures
from cadguard.cli import main
from cadguard.dxf_reader import read_dxf
from cadguard.dxf_stream import read_dxf_stream
from cadguard.model import DrawingModel, EntityRec, LayerRec, ModelStats, SpaceStats, StyleRec
from cadguard.rules import REGISTRY, Ctx, Skip
from cadguard.runner import audit_model
from cadguard.standard import ProfileError, apply_profile, load_profile, load_standard

REPO = Path(__file__).resolve().parents[3]
STANDARDS = REPO / "standards"
VS_IDS = {f"VS-0{i}" for i in range(1, 8)}

# Tập VS-* mỗi fixture gây ra với ngưỡng mặc định (không hơn, không kém).
EXPECTED = {
    "hygiene_ok.dxf": set(),
    "hygiene_bad.dxf": VS_IDS,
    "ok_sheet.dxf": {"VS-02"},  # ezdxf setup=True thêm 28 kiểu chữ, 12 kiểu kích thước
    "model_features.dxf": {"VS-01", "VS-02", "VS-04", "VS-06"},
    "bad_layers.dxf": {"VS-02", "VS-03"},
    "bad_titleblock.dxf": {"VS-02", "VS-04"},
    "bad_geometry.dxf": {"VS-02", "VS-04"},
    "bad_parts.dxf": {"VS-02", "VS-04", "VS-06"},
}


def _ids(model, std) -> set[str]:
    return {f.rule_id for f in audit_model(model, std).findings}


def _profile(tmp_path: Path, **fields) -> Path:
    data = {"schema": "cg.company-profile/1", "name": "cong-ty-thu", "version": "0.0.1", "standard": "design-hygiene-v0"}
    data.update(fields)
    p = tmp_path / "ho-so.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return p


def _with(tmp_path: Path, **fields):
    return load_standard("design-hygiene-v0", STANDARDS, profile=_profile(tmp_path, **fields))


# ---- fixture: ca dương / ca âm

def test_expected_covers_all_fixtures():
    assert set(EXPECTED) == set(fixtures.ALL)


@pytest.mark.parametrize("name,expected", EXPECTED.items())
def test_fixture_triggers_exact_vs_rules(synthetic, hygiene, name, expected):
    assert _ids(read_dxf(synthetic / name), hygiene) == expected


def test_clean_fixture_runs_every_rule(synthetic, hygiene):
    res = audit_model(read_dxf(synthetic / "hygiene_ok.dxf"), hygiene)
    assert res.findings == [] and res.skipped == [] and res.rules_run == len(VS_IDS)


def test_every_vs_rule_has_positive_case(hygiene):
    implemented = {r.id for r in hygiene.rules if r.implemented}
    assert implemented == VS_IDS == set().union(*EXPECTED.values())
    assert implemented <= set(REGISTRY)


@pytest.mark.parametrize("name", sorted(fixtures.ALL))
def test_stream_and_ezdxf_give_same_vs_findings(synthetic, hygiene, name):
    def key(model):
        res = audit_model(model, hygiene)
        return Counter((f.rule_id, f.message, f.count, f.layer, f.layout, tuple(f.handles)) for f in res.findings), sorted(res.skipped)

    assert key(read_dxf(synthetic / name)) == key(read_dxf_stream(synthetic / name))


def test_vietnamese_text_counted_per_style_both_readers(synthetic):
    for reader in (read_dxf, read_dxf_stream):
        bad = reader(synthetic / "hygiene_bad.dxf").stats.text_non_ascii_by_style
        assert bad == {"SYN-CHU": 3, "SYN-VN-SHX": 1}  # gồm chữ trong định nghĩa khối SYN-GHE và MTEXT


# ---- từng luật trên mô hình dựng tay (ca dương + ca âm)

def _stats(**msp) -> ModelStats:
    return ModelStats(source="ezdxf", modelspace=SpaceStats(**msp), paperspace=SpaceStats(), blocks=SpaceStats())


def _run(rule_id: str, model: DrawingModel, std, **globals_):
    spec = std.rule(rule_id)
    return REGISTRY[rule_id](model, Ctx(globals={**std.globals, **globals_}, params=dict(spec.params)))


def test_vs01_xref_layers(hygiene):
    clean = DrawingModel(layers=[LayerRec(name="0"), LayerRec(name="SYN-TUONG")])
    dirty = DrawingModel(layers=[LayerRec(name="X|A", xref_dependent=True, xref_name="X")])
    assert _run("VS-01", clean, hygiene) == []
    assert [f.count for f in _run("VS-01", dirty, hygiene)] == [1]
    assert _run("VS-01", dirty, hygiene, allowed_layer_patterns=["^X\\|"]) == []


def test_vs02_style_counts(hygiene):
    few = DrawingModel(styles=[StyleRec(name=f"S{i}") for i in range(15)], dim_styles=[f"D{i}" for i in range(10)])
    many = DrawingModel(styles=[StyleRec(name=f"S{i}") for i in range(16)], dim_styles=[f"D{i}" for i in range(11)])
    assert _run("VS-02", few, hygiene) == []
    assert [f.count for f in _run("VS-02", many, hygiene)] == [16, 11]


def test_vs03_layer0_ratio(hygiene):
    ok = DrawingModel(stats=_stats(entities=100, by_layer={"0": 5, "A": 95}))
    bad = DrawingModel(stats=_stats(entities=100, by_layer={"0": 6, "A": 94}))
    tiny = DrawingModel(stats=_stats(entities=3, by_layer={"0": 3}))
    assert _run("VS-03", ok, hygiene) == []
    assert [f.count for f in _run("VS-03", bad, hygiene)] == [6]
    with pytest.raises(Skip):
        _run("VS-03", tiny, hygiene)
    with pytest.raises(Skip):
        _run("VS-03", DrawingModel(), hygiene)  # không có stats


def _ents(n: int, overrides: int, layer: str = "A") -> list[EntityRec]:
    return [EntityRec(handle=f"H{i}", type="LINE", layer=layer, color=1 if i < overrides else None) for i in range(n)]


def test_vs04_overrides(hygiene):
    assert _run("VS-04", DrawingModel(entities=_ents(20, 2)), hygiene) == []  # 10% = ngưỡng
    found = _run("VS-04", DrawingModel(entities=_ents(20, 3)), hygiene)
    assert [(f.count, "màu" in f.message) for f in found] == [(3, True)]
    lw = [EntityRec(handle=f"L{i}", type="LINE", layer="A", lineweight=50 if i == 0 else -1) for i in range(10)]
    assert [f.count for f in _run("VS-04", DrawingModel(entities=lw), hygiene)] == [1]
    exempt = DrawingModel(entities=_ents(20, 20, layer="TRINH-BAY-1") + _ents(20, 0))
    assert _run("VS-04", exempt, hygiene, exempt_layer_patterns=["^TRINH-BAY-"]) == []


def test_vs05_wipeout_image_ole(hygiene):
    ok = DrawingModel(stats=_stats(wipeout=100, image=10, ole=0))
    bad = DrawingModel(stats=_stats(wipeout=101, image=10, ole=1))
    assert _run("VS-05", ok, hygiene) == []
    assert sorted(f.count for f in _run("VS-05", bad, hygiene)) == [1, 101]


def test_vs06_dim_text_override_counts_blocks(hygiene):
    ok = DrawingModel(stats=_stats(dim_total=5))
    stats = _stats(dim_total=5)
    stats.blocks.dim_text_override = 2
    assert _run("VS-06", ok, hygiene) == []
    assert [f.count for f in _run("VS-06", DrawingModel(stats=stats), hygiene)] == [2]


def _font_model(font: str, n: int = 4, style: str = "S") -> DrawingModel:
    st = _stats()
    st.text_non_ascii_by_style = {style: n}
    return DrawingModel(styles=[StyleRec(name="S", font=font)], stats=st)


@pytest.mark.parametrize("font,fires", [
    ("arial.ttf", False),
    ("times.ttf", False),
    ("syn_vn.shx", True),
    ("txt", True),  # tên phông không đuôi trong bảng STYLE là SHX
    (".VnTime.ttf", True),  # phông TCVN3 cũ
    ("VNI-Times.ttf", True),
    ("", False),  # không biết phông: không phán
])
def test_vs07_font_kinds(hygiene, font, fires):
    assert bool(_run("VS-07", _font_model(font), hygiene)) is fires


def test_vs07_whitelist_and_unknown_style(hygiene):
    spec = hygiene.rule("VS-07")
    ctx = Ctx(globals={}, params={**spec.params, "unicode_shx_fonts": ["syn_vn"]})
    assert REGISTRY["VS-07"](_font_model("syn_vn.shx"), ctx) == []
    assert _run("VS-07", _font_model("syn_vn.shx", style="KHONG-CO"), hygiene) == []
    assert _run("VS-07", _font_model("syn_vn.shx", n=0), hygiene) == []


@pytest.mark.parametrize("rule_id", sorted(VS_IDS))
def test_vs_rules_on_empty_model_skip_or_pass(rule_id, hygiene):
    try:
        assert _run(rule_id, DrawingModel(), hygiene) == []
    except Skip:
        pass
    with pytest.raises(Skip):  # thiếu tham số: không đoán ngưỡng
        REGISTRY[rule_id](DrawingModel(stats=_stats(entities=50)), Ctx(globals={}))


# ---- hồ sơ công ty

def test_profile_thresholds_change_results(synthetic, tmp_path):
    bad = read_dxf(synthetic / "hygiene_bad.dxf")
    loose = _with(tmp_path, overrides={"VS-02": {"max_text_styles": 40, "max_dim_styles": 20},
                                       "VS-05": {"max_images": 20},
                                       "VS-03": {"max_layer0_ratio": 0.5}})
    assert _ids(bad, loose) == VS_IDS - {"VS-02", "VS-05", "VS-03"}
    ok = read_dxf(synthetic / "hygiene_ok.dxf")
    strict = _with(tmp_path, overrides={"VS-07": {"legacy_font_patterns": ["^arial"]}, "VS-02": {"max_text_styles": 1}})
    assert _ids(ok, strict) == {"VS-07", "VS-02"}


def test_profile_layer_patterns_and_disabled(synthetic, tmp_path):
    bad = read_dxf(synthetic / "hygiene_bad.dxf")
    std = _with(tmp_path, layer_patterns={"allowed": ["^SYNX\\d"], "exempt": ["^SYN-TUONG$"]}, disabled=["VS-06"])
    assert _ids(bad, std) == VS_IDS - {"VS-01", "VS-04", "VS-06"}
    assert std.profile == {"name": "cong-ty-thu", "version": "0.0.1"}


def test_profile_does_not_touch_base_standard(hygiene, tmp_path):
    before = hygiene.model_dump()
    prof = load_profile(_profile(tmp_path, overrides={"VS-01": {"max_xref_layers": 9}}))
    out = apply_profile(hygiene, prof)
    assert out.rule("VS-01").params["max_xref_layers"] == 9
    assert hygiene.model_dump() == before


def test_example_profile_is_valid(hygiene):
    std = load_standard("design-hygiene-v0", STANDARDS, profile=STANDARDS / "company-profile.example.yaml")
    assert std.rule("VS-02").params["max_text_styles"] == 20
    assert std.rule("VS-04").params["max_color_override_ratio"] == 0.2
    assert std.globals["exempt_layer_patterns"] == ["^TRINH-BAY-"]


BAD_PROFILES = [
    ({"overrides": {"VS-99": {"max_texts": 1}}}, "không có luật 'VS-99'"),
    ({"overrides": {"VS-02": {"max_fonts": 3}}}, "không có tham số 'max_fonts'"),
    ({"overrides": {"VS-02": {"max_text_styles": "nhieu"}}}, "phải là số nguyên"),
    ({"overrides": {"VS-02": {"max_text_styles": 2.5}}}, "phải là số nguyên"),
    ({"overrides": {"VS-03": {"max_layer0_ratio": 1.5}}}, "tỉ lệ"),
    ({"overrides": {"VS-01": {"max_xref_layers": -1}}}, "không được âm"),
    ({"overrides": {"VS-07": {"legacy_font_patterns": ["(vn"]}}}, "biểu thức chính quy"),
    ({"overrides": {"VS-01": {}}}, "không rỗng"),
    ({"layer_patterns": {"allowed": "^X"}}, "sai kiểu"),
    ({"layer_patterns": {"exempt": ["[abc"]}}, "biểu thức chính quy"),
    ({"disabled": ["VS-42"]}, "không có luật 'VS-42'"),
    ({"thresholds": {}}, "trường lạ 'thresholds'"),
    ({"standard": "furniture-v9"}, "không dùng được với chuẩn"),
    ({"standard_version": "9.9.9"}, "phiên bản 9.9.9"),
    ({"schema": "cg.khac/1"}, "schema phải là"),
]


@pytest.mark.parametrize("fields,needle", BAD_PROFILES)
def test_bad_profile_raises_vietnamese_error(tmp_path, fields, needle):
    with pytest.raises(ProfileError) as exc:
        _with(tmp_path, **fields)
    assert needle in str(exc.value)


def test_profile_missing_required_field(tmp_path):
    p = tmp_path / "thieu.yaml"
    p.write_text("schema: cg.company-profile/1\nname: x\nstandard: design-hygiene-v0\n", encoding="utf-8")
    with pytest.raises(ProfileError, match="thiếu trường bắt buộc 'version'"):
        load_profile(p)


def test_profile_not_yaml_or_missing(tmp_path):
    p = tmp_path / "hong.yaml"
    p.write_text("a: [1, 2\n", encoding="utf-8")
    with pytest.raises(ProfileError, match="không phải YAML hợp lệ"):
        load_profile(p)
    with pytest.raises(ProfileError, match="Không thấy tệp hồ sơ"):
        load_profile(tmp_path / "khong-co.yaml")


# ---- dòng lệnh

def test_cli_bad_profile_exits_2_in_vietnamese(synthetic, tmp_path, capsys):
    p = _profile(tmp_path, overrides={"VS-02": {"max_text_styles": "nhieu"}})
    code = main(["audit", str(synthetic / "hygiene_ok.dxf"), "--standards-dir", str(STANDARDS), "--profile", str(p)])
    err = capsys.readouterr().err
    assert code == 2 and "phải là số nguyên" in err and "Traceback" not in err
    p2 = _profile(tmp_path, overrides={"VS-99": {"x": 1}})
    assert main(["audit", str(synthetic / "hygiene_ok.dxf"), "--standards-dir", str(STANDARDS), "--profile", str(p2)]) == 2
    assert "không có luật 'VS-99'" in capsys.readouterr().err


def test_cli_audit_with_profile_and_standard(synthetic, tmp_path, capsys):
    import json

    ok = str(synthetic / "hygiene_ok.dxf")
    bad = str(synthetic / "hygiene_bad.dxf")
    sd = ["--standards-dir", str(STANDARDS)]
    assert main(["audit", ok, "--standard", "design-hygiene-v0", *sd]) == 0
    assert main(["audit", bad, "--standard", "design-hygiene-v0", *sd]) == 1  # VS-06 mức E
    capsys.readouterr()
    # Không truyền --standard: dùng chuẩn ghi trong hồ sơ.
    p = _profile(tmp_path, disabled=["VS-06"])
    assert main(["audit", bad, "--json", "--profile", str(p), *sd]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["standard"] == {"name": "design-hygiene-v0", "version": "0.1.0",
                               "profile": {"name": "cong-ty-thu", "version": "0.0.1"}}
    assert {f["rule_id"] for f in rep["files"][0]["findings"]} == VS_IDS - {"VS-06"}
    # Hồ sơ của chuẩn khác với --standard: lỗi rõ, mã 2.
    assert main(["audit", bad, "--standard", "furniture-v0", "--profile", str(p), *sd]) == 2
    assert "không dùng được với chuẩn 'furniture-v0'" in capsys.readouterr().err


def test_cli_rules_lists_hygiene(capsys):
    assert main(["rules", "--standard", "design-hygiene-v0", "--standards-dir", str(STANDARDS)]) == 0
    out = capsys.readouterr().out
    for rid in sorted(VS_IDS):
        assert f"[x] {rid}" in out
    assert "7/7 luật đã cài (chuẩn design-hygiene-v0 0.1.0)" in out
