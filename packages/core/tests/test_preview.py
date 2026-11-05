"""Renderer chỉ dùng DXF tổng hợp; kiểm render, cache, ranh giới và timeout thật."""
import json
import time
from pathlib import Path
from xml.etree import ElementTree as ET

import ezdxf
import pytest
from cadguard.fixtures import make_preview_lobby
from cadguard.app.preview import PreviewManager, PreviewError, render_preview, isolated_render, sanitize_svg, svg_box
from cadguard.dxf_reader import read_dxf
from cadguard.runner import audit_model
from cadguard.standard import load_standard


def test_full_renderer_shapes_layout_and_same_transform(tmp_path):
    p = tmp_path / "synthetic.dxf"
    make_preview_lobby(p)
    doc = ezdxf.readfile(p)
    m = doc.modelspace()
    known_line = m.add_line((123,234),(456,567))
    e = m.add_ellipse((500, 500), major_axis=(300, 0), ratio=.5)
    m.add_spline([(0, 0), (200, 400), (500, 100)])
    block = doc.blocks.new("SYN-NEST")
    block.add_blockref("SYN-SOFA", (0, 0)) if "SYN-SOFA" in doc.blocks else block.add_line((0,0),(200,200))
    m.add_blockref("SYN-NEST", (3000, 2000), dxfattribs={"rotation": 30, "xscale": 2, "yscale": .5})
    ps = doc.layouts.get("Layout1")
    paper = ps.add_line((10, 20), (100, 50))
    doc.saveas(p)
    svg, meta = isolated_render(p.read_bytes(), 60, "Model")
    assert meta["paths"] > 0 and meta["layout"] == "Model" and "Layout1" in meta["layouts"]
    assert len(svg.encode()) < 10 * 1024 * 1024
    sx,sy,tx,ty = meta["transform"]
    xs=[123*sx+tx,456*sx+tx];ys=[234*sy+ty,567*sy+ty]
    assert meta["boxes"][known_line.dxf.handle] == [round(min(xs)),round(min(ys)),round(max(xs)),round(max(ys))]
    assert e.dxf.handle in meta["boxes"]
    assert paper.dxf.handle not in meta["boxes"]
    assert "<script" not in svg and "<text" not in svg
    _, paper_meta = render_preview(p.read_bytes(), layout_name="Layout1")
    assert paper.dxf.handle in paper_meta["boxes"] and e.dxf.handle not in paper_meta["boxes"]
    with pytest.raises(PreviewError):
        render_preview(p.read_bytes(), layout_name="missing")


def test_cache_changes_with_layout_content_and_fonts(tmp_path):
    p = tmp_path / "a.dxf"
    make_preview_lobby(p)
    doc = ezdxf.readfile(p)
    doc.layouts.get("Layout1").add_line((0,0),(100,100))
    doc.saveas(p)
    manager = PreviewManager(tmp_path)
    def ready(layout="Model"):
        for _ in range(30):
            result = manager.status(p, wait=1, layout_name=layout)
            if result["status"] != "pending":
                return result
        pytest.fail("worker not finished")
    a = ready()
    assert a["status"] == "ready"
    assert ready()["cached"] is True
    assert ready("Layout1")["layout"] == "Layout1"
    manager.font_signature = "changed"
    assert ready()["cached"] is False
    doc = ezdxf.readfile(p)
    doc.modelspace().add_circle((0,0),20)
    doc.saveas(p)
    assert ready()["sha256"] != a["sha256"]


def test_hard_timeout_and_large_file_fallback(tmp_path):
    p = tmp_path / "a.dxf"
    make_preview_lobby(p)
    start = time.monotonic()
    with pytest.raises(PreviewError, match="thời gian"):
        isolated_render(p.read_bytes(), .05, "Model")
    assert time.monotonic() - start < 5
    assert PreviewManager(tmp_path, max_mb=.001).status(p)["status"] == "fallback"


def test_svg_sanitizer_blocks_active_content():
    raw = '<svg viewBox="0 0 100 100"><script>alert(1)</script><foreignObject/><g class="dxf-g"><path d="M0 0 L1 1" onclick="alert(1)" fill="url(evil)"/><image href="evil"/></g></svg>'
    clean = sanitize_svg(raw)
    assert all(x not in clean for x in ("script", "onclick", "foreignObject", "image", "evil"))
    with pytest.raises(PreviewError):
        sanitize_svg('<!DOCTYPE svg [<!ENTITY x "x">]><svg/>')
    with pytest.raises(PreviewError):
        sanitize_svg("x" * (10 * 1024 * 1024 + 1))


def test_20000_entities_render_does_not_change_audit(tmp_path):
    p = tmp_path / "large-synthetic.dxf"
    doc = ezdxf.new()
    for i in range(20000):
        x, y = i % 200, i // 200
        doc.modelspace().add_line((x*10,y*10),(x*10+5,y*10+5))
    doc.saveas(p)
    std = load_standard("furniture-v0")
    before = audit_model(read_dxf(p), std)
    _, meta = isolated_render(p.read_bytes(), 60, "Model")
    after = audit_model(read_dxf(p), std)
    assert meta["model_entities"] == 20000
    assert before.findings == after.findings and before.skipped == after.skipped
