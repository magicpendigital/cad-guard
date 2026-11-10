"""Trình xem 3D một tệp HTML, không phụ thuộc thư viện ngoài, không cần GPU (canvas 2D, xoay bằng chuột).

Dữ liệu nhúng chỉ là hình khối và nhãn vật liệu: không tên tệp, không đường dẫn.
"""

from __future__ import annotations

import json

from .build import Scene
from .geometry import boxes
from .gltf import color_for


VIEWER_JS = """function makeViewer(cv){
const cx=cv.getContext('2d');let BOXES=[],yaw=0.8,pitch=0.6,zoom=1;
function fit(){cv.width=cv.clientWidth*devicePixelRatio;cv.height=cv.clientHeight*devicePixelRatio;draw()}
function bounds(){let a=[1e18,1e18,1e18],b=[-1e18,-1e18,-1e18];for(const o of BOXES)for(const p of o.b){for(const z of[o.z0,o.z1]){const v=[p[0],p[1],z];for(let i=0;i<3;i++){a[i]=Math.min(a[i],v[i]);b[i]=Math.max(b[i],v[i])}}}return[a,b]}
function draw(){cx.clearRect(0,0,cv.width,cv.height);if(!BOXES.length)return;const[a,b]=bounds(),c=[(a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2],
r=Math.max(b[0]-a[0],b[1]-a[1],b[2]-a[2])||1,k=Math.min(cv.width,cv.height)/(r*1.6)*zoom,cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);
function pr(p){const x=p[0]-c[0],y=p[1]-c[1],z=p[2]-c[2],x1=x*cy-y*sy,y1=x*sy+y*cy;return[cv.width/2+x1*k,cv.height/2-(z*cp+y1*sp)*k,y1*cp-z*sp]}
const faces=[];for(const o of BOXES){const n=o.b.length,top=o.b.map(p=>[p[0],p[1],o.z1]),bot=o.b.map(p=>[p[0],p[1],o.z0]);
faces.push({v:top,n:[0,0,1],c:o.c,k:o.k});for(let i=0;i<n;i++){const p=o.b[i],q=o.b[(i+1)%n],e=[q[0]-p[0],q[1]-p[1]],l=Math.hypot(e[0],e[1])||1;
faces.push({v:[[p[0],p[1],o.z0],[q[0],q[1],o.z0],[q[0],q[1],o.z1],[p[0],p[1],o.z1]],n:[e[1]/l,-e[0]/l,0],c:o.c,k:o.k})}}
const cells=[];for(const f of faces){const[v0,v1,v2,v3]=f.v,lu=Math.hypot(v1[0]-v0[0],v1[1]-v0[1],v1[2]-v0[2]),lw=Math.hypot(v3[0]-v0[0],v3[1]-v0[1],v3[2]-v0[2]),nu=Math.max(1,Math.ceil(lu/300)),nw=Math.max(1,Math.ceil(lw/300));
const L=(a,b,t)=>[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t],P=(u,w)=>L(L(v0,v1,u),L(v3,v2,u),w);
for(let i=0;i<nu;i++)for(let j=0;j<nw;j++)cells.push({v:[P(i/nu,j/nw),P((i+1)/nu,j/nw),P((i+1)/nu,(j+1)/nw),P(i/nu,(j+1)/nw)],n:f.n,c:f.c,k:f.k})}
faces.length=0;cells.forEach(x=>faces.push(x));
for(const f of faces){f.p=f.v.map(pr);f.d=f.p.reduce((s,p)=>s+p[2],0)/f.p.length;const nx=f.n[0]*cy-f.n[1]*sy,ny=f.n[0]*sy+f.n[1]*cy,nz=f.n[2];f.vis=(ny*cp-nz*sp)<=0.0001;f.l=0.45+0.55*Math.max(0,(nx*-0.4+(nz*cp-ny*sp)*0.8+0.3))}
faces.filter(f=>f.vis).sort((x,y)=>y.d-x.d).forEach(f=>{cx.beginPath();f.p.forEach((p,i)=>i ? cx.lineTo(p[0],p[1]):cx.moveTo(p[0],p[1]));cx.closePath();
cx.globalAlpha=((f.k==='wall'&&f.n[2]===0)||f.k==='ceiling')?0.22:1;cx.fillStyle='rgb('+f.c.map(v=>Math.round(v*255*Math.min(1,f.l))).join(',')+')';cx.fill();cx.strokeStyle=cx.fillStyle;cx.lineWidth=0.7;cx.stroke()});cx.globalAlpha=1}
let drag=null;cv.onmousedown=e=>drag=[e.clientX,e.clientY];addEventListener('mouseup',()=>drag=null);
addEventListener('mousemove',e=>{if(!drag)return;yaw+=(e.clientX-drag[0])*0.01;pitch=Math.max(0.05,Math.min(1.5,pitch+(e.clientY-drag[1])*0.01));drag=[e.clientX,e.clientY];draw()});
cv.onwheel=e=>{e.preventDefault();zoom*=e.deltaY<0?1.1:0.9;draw()};addEventListener('resize',fit);return{set(b){BOXES=b;fit()},fit};
}
"""

_TEMPLATE = """<!doctype html>
<html lang='vi'><head><meta charset='utf-8'><title>cad-guard 3D</title>
<style>body{margin:0;font:14px system-ui,sans-serif;background:#f4f4f2}#c{display:block;width:100vw;height:calc(100vh - 56px)}
#bar{height:56px;padding:6px 12px;box-sizing:border-box}small{color:#666}</style></head><body>
<div id='bar'><b>Cảnh 3D (cg.scene/1)</b> — kéo chuột để xoay, cuộn để phóng to. <small>Ảnh minh hoạ từ bản vẽ, không dùng để đo.</small><br>
<small>__SUMMARY__</small></div><canvas id='c'></canvas>
<script>
__VIEWER_JS__
const V=makeViewer(document.getElementById('c'));V.set(__DATA__);
</script></body></html>
"""


def render_html(scene: Scene) -> str:
    data = [{"b": [list(p) for p in b.base], "z0": b.z0, "z1": b.z1, "c": list(color_for(b.material)), "k": b.kind} for b in boxes(scene)]
    summary = f"{len(scene.walls)} đoạn tường, {len(scene.modules)} mô-đun, {len(scene.panels)} tấm, {len(scene.gaps)} phần thiếu, {len(scene.skipped)} bỏ qua."
    if scene.notes:
        summary += " " + " ".join(scene.notes)
    return _TEMPLATE.replace("__VIEWER_JS__", VIEWER_JS).replace("__DATA__", json.dumps(data, separators=(",", ":"))).replace("__SUMMARY__", summary)
