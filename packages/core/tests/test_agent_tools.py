import json
from pathlib import Path
import ezdxf
import pytest
from cadguard import fixtures
from cadguard.agent.workspace import Workspace, PathDenied
from cadguard.agent.anonymize import Anonymizer
from cadguard.agent.tools import ToolContext, ToolError, list_drawings, audit, explain_rule, get_model_summary, query_model


@pytest.fixture
def ctx(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    fixtures.make_all(root)
    return ToolContext(Workspace(root), Anonymizer(True, "salt"), Path(__file__).resolve().parents[3] / "standards")


def test_list(ctx):
    assert list_drawings(ctx)["total"] == len(fixtures.ALL)


def test_audit(ctx):
    result = audit(ctx, "bad_layers.dxf")
    assert result["rules_run"] and result["findings"]
    assert sum(result["counts"].values()) == len(result["findings"])


def test_audit_hides_internal_exception(ctx, monkeypatch):
    from cadguard.rules import REGISTRY

    def boom(model, rule_ctx):
        raise RuntimeError(r"C:\secret\khach_A.dxf")

    monkeypatch.setitem(REGISTRY, "DH-09", boom)
    result = audit(ctx, "ok_sheet.dxf")
    assert next(item for item in result["skipped"] if item["rule_id"] == "DH-09")["reason"] == "Lỗi nội bộ của luật."
    encoded = json.dumps(result, ensure_ascii=False)
    assert "secret" not in encoded and "khach_A" not in encoded


def test_explain(ctx):
    result = explain_rule(ctx, "LY-01")
    assert result["id"] == "LY-01" and result["description_md"]


def test_summary(ctx):
    for entry in list_drawings(ctx)["drawings"]:
        result = get_model_summary(ctx, entry["id"])
        assert result["layer_count"] > 0
        assert len(json.dumps(result).encode()) <= 16384


def test_query(ctx):
    result = query_model(ctx, "bad_layers.dxf", {})
    assert result["total_matched"] == len(result["items"])
    assert all("attribs" not in x and "dim_text" not in x for x in result["items"])


def test_pagination(ctx):
    doc = ezdxf.new()
    for i in range(750): doc.modelspace().add_line((i, 0), (i, 1))
    doc.saveas(ctx.workspace.root / "many.dxf")
    cursor, handles = None, []
    while True:
        result = query_model(ctx, "many.dxf", {"type": "LINE"}, 10000, cursor)
        assert len(result["items"]) <= 500 and len(json.dumps(result).encode()) <= 65536
        handles.extend(x["handle"] for x in result["items"])
        cursor = result["next_cursor"]
        if cursor is None: break
    assert len(handles) == result["total_matched"] == len(set(handles)) == 750


def test_privacy(ctx, tmp_path):
    doc = ezdxf.new()
    doc.layers.new("PRIVATE_LAYER")
    doc.styles.new("PRIVATE_STYLE")
    block = doc.blocks.new("PRIVATE_BLOCK")
    block.add_attdef("TAG", (0, 0))
    insert = doc.modelspace().add_blockref("PRIVATE_BLOCK", (0, 0), dxfattribs={"layer": "PRIVATE_LAYER"})
    insert.add_attrib("TAG", "PRIVATE_VALUE", (0, 0))
    doc.modelspace().add_text("text", dxfattribs={"style": "PRIVATE_STYLE", "layer": "PRIVATE_LAYER"})
    doc.saveas(ctx.workspace.root / "private_file.dxf")
    output = [list_drawings(ctx), audit(ctx, "private_file.dxf"), explain_rule(ctx, "LY-01"), get_model_summary(ctx, "private_file.dxf"), query_model(ctx, "private_file.dxf", {})]
    encoded = json.dumps(output)
    for secret in ("PRIVATE_LAYER", "PRIVATE_STYLE", "PRIVATE_BLOCK", "PRIVATE_VALUE", "private_file.dxf", str(tmp_path)):
        assert secret not in encoded
    ctx.anonymizer.enabled = False
    assert "PRIVATE_LAYER" in json.dumps(query_model(ctx, "private_file.dxf", {}))


@pytest.mark.parametrize("path", [r"..\x.dxf", "../x.dxf", "/etc/passwd", r"C:\Windows\win.ini", r"C:x.dxf", r"\\host\share\a.dxf", "a\x00.dxf", "notes.txt"])
def test_denied(ctx, path):
    with pytest.raises(PathDenied): ctx.workspace.resolve(path)
    with pytest.raises(ToolError): query_model(ctx, path, {})


def test_symlink(ctx, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    ezdxf.new().saveas(outside / "outside.dxf")
    try:
        (ctx.workspace.root / "link").symlink_to(outside, target_is_directory=True)
        (ctx.workspace.root / "link.dxf").symlink_to(outside / "outside.dxf")
    except OSError:
        pytest.skip("Không tạo được liên kết")
    with pytest.raises(PathDenied): ctx.workspace.resolve("link/outside.dxf")
    with pytest.raises(PathDenied): ctx.workspace.resolve("link.dxf")
    assert list_drawings(ctx)["total"] == len(fixtures.ALL)


def test_resolved_path_outside_workspace_denied(ctx, tmp_path, monkeypatch):
    original_resolve = Path.resolve
    candidate = ctx.workspace.root / "escape" / "outside.dxf"
    outside = tmp_path / "outside.dxf"

    def fake_resolve(path, *args, **kwargs):
        if path == candidate:
            return outside
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fake_resolve)
    with pytest.raises(PathDenied):
        ctx.workspace.resolve("escape/outside.dxf")


def test_invalid_standard(ctx):
    with pytest.raises(ToolError): explain_rule(ctx, "LY-01", "../../etc/x")


def test_cursor_and_bbox(ctx):
    with pytest.raises(ToolError, match="vùng chưa hỗ trợ"): query_model(ctx, "bad_layers.dxf", {"bbox": [0, 0, 1, 1]})
    first = query_model(ctx, "bad_layers.dxf", {}, 1)
    with pytest.raises(ToolError): query_model(ctx, "bad_layers.dxf", {"type": "LINE"}, cursor=first["next_cursor"])
