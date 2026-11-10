"""Dựng hình TỪNG TỜ (SVG; PNG/PDF nếu máy có matplotlib) để xem trước và so trước/sau (kế hoạch Đợt C, PRD FR-03).

- Tờ lấy từ chỉ mục `sheets.py` (layout có khung nhìn hoặc khung tên trong Model). Mỗi tờ vẽ đúng đối tượng thuộc tờ
  (cộng đối tượng không có toạ độ như HATCH), cắt theo khung tờ, nền trắng, nét đen như bản in.
- Chữ TCVN3/VNI được chuyển sang Unicode TRONG BỘ NHỚ trước khi vẽ (`unicode_convert.convert_doc`) để hình hiện đúng
  tiếng Việt; tệp bản vẽ không bị ghi.
- Ra `<thư mục>/to-NN.svg` + `index.html` (danh sách tờ, tiêu đề, khổ/tỉ lệ). Chỉ để người dùng xem trên máy.
"""
from __future__ import annotations

import html
import time
from pathlib import Path

PAPER_MM = {"A0": (1189, 841), "A1": (841, 594), "A2": (594, 420), "A3": (420, 297), "A4": (297, 210)}


def _doc_and_structure(path: Path):
    from .changeset.engine import read_doc
    from .dxf_reader import build_model
    from .sheets import build_structure

    doc = read_doc(path)
    model = build_model(doc)
    return doc, build_structure(model)


def render_sheets(path: Path, out_dir: Path, picks: list[int] | None = None, *, fmt: str = "svg",
                  decode_text: bool = True) -> dict:
    """Dựng các tờ (đánh số từ 1). Trả {"sheets": [{index, name, title, file}], "seconds": …}."""
    from ezdxf.addons.drawing import Frontend, RenderContext, layout, svg
    from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
    from ezdxf.math import BoundingBox2d

    import logging

    logging.getLogger("ezdxf").setLevel(logging.ERROR)  # cảnh báo sao chép FIELD lặp lại mỗi tờ: không có ích ở đây
    t0 = time.monotonic()
    doc, st = _doc_and_structure(Path(path))
    if decode_text:
        from .unicode_convert import convert_doc

        convert_doc(doc)  # chỉ trong bộ nhớ
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    assigned = set(st.sheet_of)
    # đối tượng chưa gán tờ (HATCH… không có toạ độ trong mô hình): khung bao tính một lần, vẽ ở tờ nào nó giao
    from ezdxf import bbox as ezbbox

    cache = ezbbox.Cache()
    loose: list[tuple[str, tuple[float, float, float, float]]] = []
    for e in doc.modelspace():
        h = e.dxf.handle
        if h in assigned:
            continue
        try:
            ext = ezbbox.extents([e], cache=cache, fast=True)
        except Exception:  # noqa: BLE001
            continue
        if ext.has_data:
            loose.append((h, (ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y)))
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.BLACK)
    rows = []
    for i, s in enumerate(st.sheets, 1):
        if picks is not None and i not in picks:
            continue
        if not s.windows:
            continue
        x0 = min(w[0] for w in s.windows)
        y0 = min(w[1] for w in s.windows)
        x1 = max(w[2] for w in s.windows)
        y1 = max(w[3] for w in s.windows)
        handles = set(s.handles) | {h for h, b in loose if b[0] <= x1 and b[2] >= x0 and b[1] <= y1 and b[3] >= y0}
        if s.kind == "layout":
            lay = doc.layouts.get(s.name)
            box = None
        else:
            lay = doc.modelspace()
            box = BoundingBox2d([(x0, y0), (x1, y1)])

        def keep(e, handles=handles) -> bool:
            return e.dxf.handle in handles

        ctx = RenderContext(doc)
        ctx.set_current_layout(lay)
        backend = svg.SVGBackend()
        Frontend(ctx, backend, config=cfg).draw_layout(lay, filter_func=keep if s.kind == "frame" else None)
        pw, ph = PAPER_MM.get(s.paper or "", (420, 297))
        if (x1 - x0) < (y1 - y0):
            pw, ph = ph, pw
        page = layout.Page(pw, ph, layout.Units.mm)
        name = f"to-{i:02d}.{fmt if fmt == 'svg' else 'svg'}"
        text = backend.get_string(page, settings=layout.Settings(fit_page=True), render_box=box)
        (out_dir / name).write_text(text, encoding="utf-8")
        row = {"index": i, "name": s.name, "title": s.title, "paper": s.paper, "scale": s.scale, "file": name}
        if fmt in ("png", "pdf"):
            row["file_" + fmt] = _raster(doc, lay, keep if s.kind == "frame" else None, box, out_dir, i, fmt, cfg)
        rows.append(row)
    _index(out_dir, Path(path).name, rows)
    return {"sheets": rows, "seconds": round(time.monotonic() - t0, 2), "count": len(st.sheets)}


def _raster(doc, lay, filt, box, out_dir: Path, i: int, fmt: str, cfg) -> str | None:
    """PNG/PDF qua matplotlib nếu có (tuỳ chọn); không có thì bỏ qua, SVG vẫn đủ để xem."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    except ImportError:
        return None
    fig = plt.figure(figsize=(16.5, 11.7))
    ax = fig.add_axes([0, 0, 1, 1])
    ctx = RenderContext(doc)
    ctx.set_current_layout(lay)
    Frontend(ctx, MatplotlibBackend(ax), config=cfg).draw_layout(lay, filter_func=filt)
    if box is not None:
        ax.set_xlim(box.extmin.x, box.extmax.x)
        ax.set_ylim(box.extmin.y, box.extmax.y)
    name = f"to-{i:02d}.{fmt}"
    fig.savefig(out_dir / name, dpi=150)
    plt.close(fig)
    return name


def _index(out_dir: Path, source: str, rows: list[dict]) -> None:
    items = []
    for r in rows:
        cap = f"{html.escape(r['name'])}" + (f": {html.escape(r['title'])}" if r.get("title") else "")
        meta = " · ".join(x for x in (r.get("paper"), f"1:{r['scale']:g}" if r.get("scale") else None) if x)
        items.append(f'<figure><a href="{r["file"]}"><img src="{r["file"]}" alt="{cap}" loading="lazy"></a>'
                     f"<figcaption>{cap}<small>{html.escape(meta)}</small></figcaption></figure>")
    page = ("<!doctype html><html lang=\"vi\"><meta charset=\"utf-8\"><title>Các tờ — "
            f"{html.escape(source)}</title><style>body{{font:14px system-ui;margin:16px;background:#f4f4f4}}"
            "main{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}"
            "figure{margin:0;background:#fff;border:1px solid #ddd;padding:8px}img{width:100%;height:auto}"
            "figcaption{margin-top:6px}small{display:block;color:#666}</style>"
            f"<h1>{html.escape(source)}: {len(rows)} tờ</h1><main>{''.join(items)}</main></html>")
    (out_dir / "index.html").write_text(page, encoding="utf-8")


__all__ = ["render_sheets"]
