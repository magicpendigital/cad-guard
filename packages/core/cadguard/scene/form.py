"""Form HTML tĩnh (không máy chủ) để người dùng điền phần còn thiếu và tải về `.cgsup.json`.

Chỉ chứa mã khối/tấm, nhãn và mã băm bản vẽ: không tên tệp, không đường dẫn.
"""

from __future__ import annotations

import html
import json

from .build import SUPPLEMENT_SCHEMA, Scene

_PAGE = """<!doctype html>
<html lang='vi'><head><meta charset='utf-8'><title>cad-guard — bổ sung dữ liệu</title>
<style>body{font:14px system-ui,sans-serif;max-width:760px;margin:24px auto;padding:0 12px}
fieldset{margin:12px 0;border:1px solid #ccc;border-radius:6px}legend{font-weight:600}
label{display:block;margin:6px 0}input,select{margin-left:8px;padding:3px}
.c{background:#fff4f0;border-left:4px solid #d64;padding:8px;margin:12px 0}button{padding:6px 14px}</style></head><body>
<h2>Bổ sung dữ liệu còn thiếu</h2>
<p>Điền các ô bên dưới rồi bấm <b>Tải tệp bổ sung</b>. Chạy lại: <code>cadguard scene &lt;bản vẽ&gt; --supplement &lt;tệp vừa tải&gt; --out ...</code>.
Giá trị nhập tay sẽ được đánh dấu "do người nhập" trong cảnh 3D. Bản vẽ gốc không bị sửa.</p>
<form id='f'>__BODY__</form>
<button onclick='save()'>Tải tệp bổ sung</button>
<script>
const META=__META__;
function save(){const v={};document.querySelectorAll('#f [data-key]').forEach(e=>{if(e.value!=='')v[e.dataset.key]=e.value});
const b=new Blob([JSON.stringify({schema:META.schema,source_hash:META.hash,origin:'user',values:v},null,2)],{type:'application/json'});
const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='bo-sung.cgsup.json';a.click()}
</script></body></html>
"""


def render_form(scene: Scene) -> str:
    parts: list[str] = []
    for g in scene.gaps:
        msg = html.escape(g.message)
        if not g.fields:
            parts.append(f"<div class='c'><b>Cần sửa/bổ sung bản vẽ:</b> {msg}</div>")
            continue
        rows = []
        for f in g.fields:
            key = html.escape(f.key, quote=True)
            label = html.escape(f.label)
            if f.kind == "choice":
                opts = "<option value=''>— chọn —</option>" + "".join(f"<option>{html.escape(o)}</option>" for o in f.options)
                rows.append(f"<label>{label}<select data-key='{key}'>{opts}</select></label>")
            else:
                rows.append(f"<label>{label} ({html.escape(f.unit)})<input type='number' step='any' min='0' data-key='{key}'></label>")
        parts.append(f"<fieldset><legend>{html.escape(g.id)}</legend><p>{msg}</p>{''.join(rows)}</fieldset>")
    if not parts:
        parts.append("<p>Không có phần nào còn thiếu.</p>")
    meta = json.dumps({"schema": SUPPLEMENT_SCHEMA, "hash": scene.source_hash})
    return _PAGE.replace("__BODY__", "".join(parts)).replace("__META__", meta)
