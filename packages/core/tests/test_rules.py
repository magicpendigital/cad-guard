import pytest

from cadguard.dxf_reader import read_dxf
from cadguard.model import DrawingModel, EntityRec
from cadguard.rules import REGISTRY, Ctx, Skip
from cadguard.runner import audit_model

# Mỗi tệp xấu phải gây ĐÚNG tập mã luật này (không hơn, không kém).
EXPECTED = {
    "ok_sheet.dxf": set(),
    "bad_layers.dxf": {"LY-01", "LY-03", "LY-04", "LY-08", "LY-09"},
    "bad_titleblock.dxf": {"SH-04", "SH-05"},
    "bad_geometry.dxf": {"DH-01", "DH-02", "DH-09", "DH-10"},
    "bad_parts.dxf": {"PR-02", "TX-01", "TX-08", "VW-01"},
}


@pytest.mark.parametrize("name,expected", EXPECTED.items())
def test_fixture_triggers_exact_rules(synthetic, standard, name, expected):
    res = audit_model(read_dxf(synthetic / name), standard)
    assert {f.rule_id for f in res.findings} == expected


def test_every_implemented_rule_has_positive_and_negative_case(synthetic, standard):
    positive = set().union(*EXPECTED.values()) | {"DH-07"}  # DH-07 kiểm bằng mô hình ở dưới
    assert positive == set(REGISTRY), "luật nào chưa có ca dương trong EXPECTED thì phải bổ sung"
    ok = {f.rule_id for f in audit_model(read_dxf(synthetic / "ok_sheet.dxf"), standard).findings}
    assert ok == set()  # ca âm: bản vẽ sạch không vi phạm luật nào


def test_dh07_proxy_objects(standard):
    m = DrawingModel(entities=[EntityRec(handle="A1", type="ACAD_PROXY_ENTITY", layer="FN-PART-OUTL", is_proxy=True)])
    assert [f.rule_id for f in audit_model(m, standard).findings if f.rule_id == "DH-07"] == ["DH-07"]


@pytest.mark.parametrize("rule_id", sorted(REGISTRY))
def test_rule_never_raises_on_empty_model(rule_id, standard):
    try:
        REGISTRY[rule_id](DrawingModel(), Ctx(globals=standard.globals))
    except Exception as exc:  # noqa: BLE001
        assert exc.__class__.__name__ == "Skip", f"{rule_id} ném {exc!r}"


def test_empty_default_layout_is_not_a_sheet(standard):
    from cadguard.model import LayoutRec

    m = DrawingModel(layouts=[LayoutRec(name="Layout1")])
    assert [f for f in audit_model(m, standard).findings if f.rule_id == "SH-04"] == []


def test_broken_rule_is_reported_not_fatal(standard, monkeypatch):
    def boom(model, ctx):
        raise RuntimeError("x")

    monkeypatch.setitem(REGISTRY, "DH-09", boom)
    res = audit_model(DrawingModel(), standard)
    assert any(r == "DH-09" and "lỗi nội bộ" in why for r, why in res.skipped)
    assert "DH-09" in res.internal_errors


def test_skipped_rule_is_not_an_internal_error(standard, monkeypatch):
    def skip(model, ctx):
        raise Skip("thiếu dữ liệu")

    monkeypatch.setitem(REGISTRY, "DH-09", skip)
    res = audit_model(DrawingModel(), standard)
    assert ("DH-09", "thiếu dữ liệu") in res.skipped
    assert "DH-09" not in res.internal_errors
