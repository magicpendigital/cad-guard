"""Xuất cảnh `cg.scene/2`: GLB (glTF 2.0) và trang HTML xem 3D (không thư viện ngoài). Cả hai mang cùng `scene_hash`
nên "xem trước = xuất": trang xem trong App và tệp GLB tải về dựng từ cùng một cảnh.

Dữ liệu nhúng: hình khối, mã khối/handle, số đo và nguồn số đo. Không tên tệp, không đường dẫn.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from .assemble import Scene2
from .geometry import boxes2
from .gltf import color_for, glb_from_boxes
from .viewer import VIEWER_JS

SRC_LABEL = {"dimension": "kích thước", "geometry": "đo trên hình", "user": "người nhập", "default": "mặc định"}


def build_glb2(sc: Scene2) -> bytes:
    return glb_from_boxes(boxes2(sc), "cadguard cg.scene/2", {"scene_hash": sc.scene_hash, "schema": "cg.scene/2", "unit": "mm"})


def write_glb2(sc: Scene2, path: str | Path) -> Path:
    p = Path(path)
    p.write_bytes(build_glb2(sc))
    return p


def _fmt(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def sources_table(sc: Scene2) -> str:
    rows = []
    for m in sc.modules:
        cells = []
        for k, label in (("w", "rộng"), ("d", "sâu"), ("h", "cao"), ("z0", "chân")):
            v = getattr(m, k)
            s = m.src.get(k)
            cells.append(f"<td>{_fmt(v)} <small>{html.escape(SRC_LABEL.get(s.kind, s.kind) if s else '?')}</small></td>")
        rows.append(f"<tr><td>{html.escape(m.id)}</td><td>{html.escape(m.kind)}</td>{''.join(cells)}"
                    f"<td>{len(m.fronts)}</td><td>{m.shelves}</td></tr>")
    c = sc.room.src.get("ceiling")
    ceil = f"{_fmt(sc.room.ceiling)} ({SRC_LABEL.get(c.kind, c.kind)})" if sc.room.ceiling and c else "chưa có"
    return ("<table><tr><th>Khối</th><th>Loại</th><th>Rộng</th><th>Sâu</th><th>Cao</th><th>Cao độ chân</th><th>Cánh/ngăn kéo</th>"
            f"<th>Đợt</th></tr>{''.join(rows)}</table><p>Cao sàn–trần: {html.escape(ceil)}. Phần thiếu: {len(sc.gaps)}.</p>")


_PAGE = """<!doctype html>
<html lang='vi'><head><meta charset='utf-8'><title>cad-guard 3D</title>
<style>body{margin:0;font:14px system-ui,sans-serif;background:#f4f4f2;color:#222}#c{display:block;width:100%;height:62vh;background:#fbfbfa}
#bar,#info{padding:8px 12px}small{color:#666}table{border-collapse:collapse;margin:6px 0}td,th{border:1px solid #ccc;padding:3px 6px;text-align:left}
.gap{background:#fff4f0;border-left:4px solid #d64;padding:4px 8px;margin:4px 0}</style></head><body>
<div id='bar'><b>Cảnh 3D (cg.scene/2)</b> · mã cảnh <code id='h'>__HASH__</code> — kéo chuột để xoay, cuộn để phóng to.
<label><input type='checkbox' id='ceil'> hiện trần</label> <small>Hình minh hoạ dựng từ bản vẽ; số đo và nguồn ở bảng dưới.</small></div>
<canvas id='c'></canvas><div id='info'>__TABLE__ __GAPS__ __NOTES__</div>
<script>
__VIEWER_JS__
const ALL=__DATA__;const V=makeViewer(document.getElementById('c'));
function show(){const c=document.getElementById('ceil').checked;V.set(ALL.filter(b=>c||b.k!=='ceiling'))}
document.getElementById('ceil').onchange=show;show();
</script></body></html>
"""


def render_html2(sc: Scene2) -> str:
    data = [{"b": [list(p) for p in b.base], "z0": b.z0, "z1": b.z1, "c": list(color_for(b.material)), "k": b.kind, "n": b.name}
            for b in boxes2(sc)]
    gaps = "".join(f"<div class='gap'>{html.escape(g.message)}</div>" for g in sc.gaps)
    notes = "".join(f"<p><small>{html.escape(n)}</small></p>" for n in sc.notes)
    return (_PAGE.replace("__VIEWER_JS__", VIEWER_JS).replace("__DATA__", json.dumps(data, separators=(",", ":")))
            .replace("__HASH__", html.escape(sc.scene_hash)).replace("__TABLE__", sources_table(sc))
            .replace("__GAPS__", gaps).replace("__NOTES__", notes))


__all__ = ["build_glb2", "render_html2", "sources_table", "write_glb2"]
