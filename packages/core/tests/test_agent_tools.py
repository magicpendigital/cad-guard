import json
import math
from pathlib import Path
import ezdxf
import pytest
from cadguard import fixtures
from cadguard.agent.workspace import Workspace, PathDenied
from cadguard.agent.anonymize import Anonymizer
from cadguard.agent.tools import MAX_QUERY_RECORDS, ToolContext, ToolError, list_drawings, audit, explain_rule, get_model_summary, load_model, query_model


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


@pytest.mark.parametrize("threshold", [None, 0])
def test_privacy(ctx, tmp_path, threshold):
    ctx.stream_threshold_mb = threshold
    doc = ezdxf.new()
    doc.layers.new("PRIVATE_LAYER")
    doc.styles.new("PRIVATE_STYLE")
    block = doc.blocks.new("PRIVATE_BLOCK")
    block.add_attdef("TAG", (0, 0))
    insert = doc.modelspace().add_blockref("PRIVATE_BLOCK", (0, 0), dxfattribs={"layer": "PRIVATE_LAYER"})
    insert.add_attrib("TAG", "PRIVATE_VALUE", (0, 0))
    doc.modelspace().add_text("text", dxfattribs={"style": "PRIVATE_STYLE", "layer": "PRIVATE_LAYER"})
    doc.saveas(ctx.workspace.root / "private_file.dxf")
    expected = "stream" if threshold == 0 else "ezdxf"
    assert load_model(ctx.workspace.root / "private_file.dxf", threshold).stats.source == expected
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


# ---- chọn bộ đọc theo kích thước tệp (L1b)


def _ctx_with(root, threshold, max_records=None):
    extra = {} if max_records is None else {"max_entity_records": max_records}
    return ToolContext(Workspace(root), Anonymizer(True, "salt"), Path(__file__).resolve().parents[3] / "standards", stream_threshold_mb=threshold, **extra)


def _all_tool_outputs(ctx, name):
    pages, cursor = [], None
    while True:
        page = query_model(ctx, name, {}, MAX_QUERY_RECORDS, cursor)
        pages.append(page)
        cursor = page["next_cursor"]
        if cursor is None:
            break
    return {
        "list_drawings": list_drawings(ctx),
        "audit": audit(ctx, name),
        "explain_rule": explain_rule(ctx, "LY-01"),
        "get_model_summary": get_model_summary(ctx, name),
        "query_model": pages,
    }


def _same(a, b, path=""):
    """So khớp đệ quy; số thực so theo dung sai tương đối nhỏ (length/area tính toán có thể lệch chữ số cuối)."""
    if isinstance(a, dict) and isinstance(b, dict):
        assert set(a) == set(b), path
        for k in a:
            _same(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list) and isinstance(b, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            _same(x, y, f"{path}[{i}]")
    elif isinstance(a, float) and isinstance(b, float):
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12), (path, a, b)
    else:
        assert a == b, (path, a, b)


@pytest.mark.parametrize("name", sorted(fixtures.ALL))
def test_stream_tools_match_ezdxf(ctx, name):
    root = ctx.workspace.root
    path = root / name
    assert load_model(path, 0).stats.source == "stream"
    assert load_model(path, -1).stats.source == load_model(path, None).stats.source == "ezdxf"
    ezdxf_out = _all_tool_outputs(_ctx_with(root, -1), name)
    assert _all_tool_outputs(_ctx_with(root, None), name) == ezdxf_out
    stream_out = _all_tool_outputs(_ctx_with(root, 0), name)
    _same(stream_out, ezdxf_out)
    assert ezdxf_out["audit"]["records_capped"] is False
    assert ezdxf_out["get_model_summary"]["records_capped"] is False
    assert all(page["records_capped"] is False for page in ezdxf_out["query_model"])


def test_threshold_picks_reader_by_size(ctx):
    path = ctx.workspace.root / "ok_sheet.dxf"
    size_mb = path.stat().st_size / (1024 * 1024)
    assert load_model(path, size_mb * 2).stats.source == "ezdxf"  # dưới ngưỡng
    assert load_model(path, size_mb / 2).stats.source == "stream"  # trên ngưỡng
    assert ToolContext(ctx.workspace).stream_threshold_mb == 50.0  # mặc định như CLI


def test_cache_key_includes_reader_and_cap(ctx):
    path = ctx.workspace.root / "bad_layers.dxf"
    a, b = load_model(path, None), load_model(path, 0)
    assert a is load_model(path, -5) and b is load_model(path, 0)
    assert a.stats.source == "ezdxf" and b.stats.source == "stream"
    capped = load_model(path, 0, max_entity_records=1)
    assert capped is not b and len(capped.entities) == 1 and capped.stats.entity_records_truncated
    assert not load_model(path, 0).stats.entity_records_truncated
    assert load_model(path, None, max_entity_records=1) is a  # ezdxf không bị trần, dùng chung mục


def test_records_capped_flag(ctx):
    capped = _ctx_with(ctx.workspace.root, 0, max_records=2)
    a = audit(capped, "bad_layers.dxf")
    s = get_model_summary(capped, "bad_layers.dxf")
    q = query_model(capped, "bad_layers.dxf", {})
    assert a["records_capped"] is s["records_capped"] is q["records_capped"] is True
    assert q["total_matched"] == 2 and sum(s["entities_by_type"].values()) == 2
    full = _ctx_with(ctx.workspace.root, 0)
    assert query_model(full, "bad_layers.dxf", {})["records_capped"] is False
    encoded = json.dumps([a, s, q])
    assert "bad_layers" not in encoded
