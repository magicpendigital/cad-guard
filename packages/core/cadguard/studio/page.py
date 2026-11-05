"""Trang web của studio, đồng bộ với bản mẫu đã duyệt `design/ui-mockup.html`.

Dùng lại bộ biến màu/chữ, thanh trên cùng, ba cột (Bản vẽ | Khung vẽ | Trợ lý), tab, pill, nút, thẻ, khối diff của bản mẫu;
chế độ sáng/tối (`data-theme`). Mọi dữ liệu từ DXF/LLM chỉ gán bằng textContent, không innerHTML (chỉ innerHTML cho biểu tượng hằng).
"""

from __future__ import annotations

from ..scene.viewer import VIEWER_JS

CSS = """
:root{
  --font:"Segoe UI",system-ui,-apple-system,"Inter",Roboto,"Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,"Cascadia Mono",Consolas,"SF Mono",monospace;--r:10px;
  --bg:#F6F5F2;--surface:#FFFFFF;--surface2:#EFEDE8;--border:#DEDAD2;--border-strong:#C9C4B9;
  --text:#1F2421;--text2:#555C57;--text3:#6B726D;
  --primary:#0F6B62;--primary-hover:#0B554E;--primary-soft:#DDF0EC;--on-primary:#FFFFFF;--primary-text:#0B4F48;
  --ok-bg:#DFF3E4;--ok-fg:#14532D;--err-bg:#FBE3E1;--err-fg:#8E1B13;--warn-bg:#FCEFCB;--warn-fg:#7A4B00;
  --neu-bg:#E9E7E2;--neu-fg:#4A504B;--info-bg:#DEEBFA;--info-fg:#1E4C84;
  --err:#C0392B;--warn:#B7791F;--ok:#2E7D4F;--cv-bg:#FFFFFF;
  --shadow:0 1px 2px rgba(20,25,22,.06),0 4px 14px rgba(20,25,22,.06);
}
html[data-theme="dark"]{
  --bg:#121513;--surface:#1A1E1C;--surface2:#232826;--border:#323935;--border-strong:#46504A;
  --text:#E9ECEA;--text2:#A8B0AA;--text3:#8E968F;
  --primary:#3FBFAE;--primary-hover:#63D0C1;--primary-soft:#173A35;--on-primary:#06201C;--primary-text:#9FE3D9;
  --ok-bg:#163A24;--ok-fg:#8EDCA6;--err-bg:#46201D;--err-fg:#FFB4AC;--warn-bg:#44330A;--warn-fg:#F3CF7A;
  --neu-bg:#2C312E;--neu-fg:#B8BFBA;--info-bg:#1C3350;--info-fg:#A9CBF4;
  --err:#F0766A;--warn:#E0B04A;--ok:#5CC98A;--cv-bg:#0F1211;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 4px 14px rgba(0,0,0,.35);
}
*{box-sizing:border-box}html,body{height:100%;margin:0}
body{font-family:var(--font);font-size:15px;line-height:1.5;color:var(--text);background:var(--bg);-webkit-font-smoothing:antialiased}
button,input,select,textarea{font:inherit;color:inherit}button{cursor:pointer}
:focus-visible{outline:2px solid var(--primary);outline-offset:2px;border-radius:6px}
.app{display:grid;grid-template-rows:56px 1fr;height:100vh;min-width:980px}
.topbar{display:flex;align-items:center;gap:14px;padding:0 16px;background:var(--surface);border-bottom:1px solid var(--border)}
.brand{display:flex;align-items:center;gap:9px;font-weight:700;font-size:16px;letter-spacing:.2px}
.brand .logo{width:28px;height:28px;border-radius:8px;background:var(--primary);color:var(--on-primary);display:grid;place-items:center}
.sample-tag{font-size:12px;font-weight:600;padding:2px 8px;border-radius:99px;background:var(--warn-bg);color:var(--warn-fg);white-space:nowrap}
.spacer{flex:1}
.chip{display:inline-flex;align-items:center;gap:7px;padding:5px 11px;border:1px solid var(--border);border-radius:99px;background:var(--surface);font-size:13.5px;color:var(--text2);white-space:nowrap}
.chip b{color:var(--text);font-weight:600}label.chip{cursor:pointer}label.chip input{accent-color:var(--primary)}
.iconbtn{width:36px;height:36px;display:grid;place-items:center;border:1px solid var(--border);background:var(--surface);border-radius:8px;color:var(--text2)}
.iconbtn:hover{background:var(--surface2);color:var(--text)}
svg.i{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex:none}
.pill{display:inline-flex;align-items:center;gap:5px;padding:2px 9px;border-radius:99px;font-size:13px;font-weight:600;line-height:1.5;white-space:nowrap}
.pill svg.i{width:14px;height:14px}.pill.ok{background:var(--ok-bg);color:var(--ok-fg)}.pill.err{background:var(--err-bg);color:var(--err-fg)}
.pill.warn{background:var(--warn-bg);color:var(--warn-fg)}.pill.neu{background:var(--neu-bg);color:var(--neu-fg)}.pill.info{background:var(--info-bg);color:var(--info-fg)}
.btn-p,.btn-s{border-radius:8px;padding:8px 14px;font-weight:600;border:1px solid transparent;display:inline-flex;gap:7px;align-items:center;justify-content:center;text-decoration:none}
.btn-p{background:var(--primary);color:var(--on-primary)}.btn-p:hover{background:var(--primary-hover)}
.btn-s{background:var(--surface);border-color:var(--border-strong);color:var(--text)}.btn-s:hover{background:var(--surface2)}
.btn-p[disabled],.btn-s[disabled]{opacity:.45;cursor:not-allowed}.btn-sm{padding:5px 10px;font-size:14px}
#s-work{display:grid;grid-template-columns:272px minmax(0,1fr) 420px;min-height:0}
.col{min-height:0;display:flex;flex-direction:column;background:var(--surface)}
.col.left{border-right:1px solid var(--border)}.col.right{border-left:1px solid var(--border)}
.col-h{padding:14px 16px 8px;font-size:12.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--text3)}
.files{padding:0 8px;overflow:auto;flex:1}
.file{display:block;width:100%;text-align:left;border:1px solid transparent;background:transparent;padding:10px;border-radius:9px;margin-bottom:2px;color:inherit}
.file[aria-current="true"]{background:var(--primary-soft);border-color:color-mix(in srgb,var(--primary) 35%,transparent)}
.file .n{display:flex;align-items:center;gap:8px;font-weight:600;word-break:break-all}.file .n svg{color:var(--text3)}
.file .m{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px;padding-left:26px}.file.child{margin-left:18px;width:calc(100% - 18px)}
.std-box{margin:8px 12px 12px;padding:12px;border:1px solid var(--border);border-radius:var(--r);background:var(--surface2);font-size:14px}
.std-box .k{color:var(--text3);font-size:12.5px}.std-box .v{font-weight:600}
.center{display:flex;flex-direction:column;min-width:0;min-height:0;background:var(--bg)}
.cv-tools{display:flex;align-items:center;gap:10px;padding:10px 14px;background:var(--surface);border-bottom:1px solid var(--border)}
.cv-wrap{flex:1;min-height:0;padding:14px;display:flex}
.sheet{flex:1;background:var(--cv-bg);border:1px solid var(--border);border-radius:var(--r);box-shadow:var(--shadow);display:flex;padding:6px;min-height:340px;position:relative}
#c{flex:1;width:100%;height:100%;display:block}
.empty3d{position:absolute;inset:0;display:grid;place-items:center;color:var(--text3);text-align:center;padding:24px}
.cv-status{display:flex;gap:16px;align-items:center;padding:8px 14px;background:var(--surface);border-top:1px solid var(--border);font-size:13.5px;color:var(--text2);flex-wrap:wrap}
.cv-status .lock{display:inline-flex;gap:6px;align-items:center;color:var(--ok-fg);background:var(--ok-bg);padding:2px 9px;border-radius:99px;font-weight:600}
.tabs{display:flex;gap:2px;padding:8px 10px 0;border-bottom:1px solid var(--border)}
.tabs button{border:0;background:transparent;padding:9px 7px;font-weight:600;font-size:14px;color:var(--text2);border-bottom:3px solid transparent;display:flex;gap:5px;align-items:center;white-space:nowrap}
.tabs button svg.i{width:15px;height:15px}
.tabs button[aria-selected="true"]{color:var(--primary-text);border-bottom-color:var(--primary)}
.tabs .cnt{font-size:12px;background:var(--neu-bg);color:var(--neu-fg);padding:0 7px;border-radius:99px;font-weight:700}
.tabs .cnt.hot{background:var(--err-bg);color:var(--err-fg)}
.pane{display:none;min-height:0;flex:1;flex-direction:column}.pane.on{display:flex}
.chat-head{display:flex;align-items:center;gap:8px;padding:10px 14px;font-size:13.5px;color:var(--text2);border-bottom:1px dashed var(--border)}
.chat-log{flex:1;overflow:auto;padding:14px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:94%;white-space:pre-wrap}
.msg.me{align-self:flex-end;background:var(--primary);color:var(--on-primary);padding:9px 13px;border-radius:14px 14px 4px 14px}
.msg.ai{align-self:flex-start;background:var(--surface2);padding:11px 14px;border-radius:14px 14px 14px 4px}
.note-card{align-self:stretch;border:1px solid var(--border-strong);border-radius:9px;background:var(--surface);padding:8px 12px;font-size:13.5px;color:var(--text2)}
.suggest{display:flex;flex-wrap:wrap;gap:7px;padding:8px 14px 0}
.suggest button{border:1px solid var(--border-strong);background:var(--surface);border-radius:99px;padding:6px 12px;font-size:14px;font-weight:500}
.suggest button:hover{background:var(--primary-soft);border-color:var(--primary);color:var(--primary-text)}
.suggest button.primary{background:var(--primary);color:var(--on-primary);border-color:var(--primary);font-weight:600}
.suggest button[disabled]{opacity:.45;cursor:not-allowed}
.composer{display:flex;gap:8px;padding:10px 14px 12px}
.composer input{flex:1;padding:10px 12px;border:1px solid var(--border-strong);border-radius:9px;background:var(--surface)}
.hint{padding:0 14px 10px;font-size:12.5px;color:var(--text3)}
.list{overflow:auto;flex:1;padding:12px 12px 16px;display:flex;flex-direction:column;gap:9px}
.empty{padding:34px 20px;text-align:center;color:var(--text2)}.empty b{display:block;color:var(--text);font-size:16px;margin-bottom:4px}
.f-card{border:1px solid var(--border);border-radius:var(--r);padding:12px;background:var(--surface);text-align:left;width:100%}
.f-top{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.f-title{font-weight:600;margin:7px 0 3px}
.f-d{color:var(--text2);font-size:14px}.f-act{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
.f-meta{margin-top:8px;font-size:13px;color:var(--text3)}
.f-card label.fld{display:flex;gap:8px;align-items:center;margin-top:8px;font-size:14px;color:var(--text2)}
.f-card input[type=number],.f-card select{flex:1;padding:6px 8px;border:1px solid var(--border-strong);border-radius:8px;background:var(--surface)}
.op{border:1px solid var(--border);border-radius:var(--r);padding:12px;background:var(--surface)}
.diff{margin-top:9px;font:13px/1.55 var(--mono);border-radius:8px;overflow:hidden;border:1px solid var(--border)}
.diff div{padding:3px 10px;word-break:break-all}.diff .p{background:var(--ok-bg);color:var(--ok-fg)}
.cs-foot{border-top:1px solid var(--border);padding:12px 14px;background:var(--surface)}
.safe{display:flex;gap:8px;font-size:13.5px;color:var(--text2);align-items:flex-start}.safe svg{color:var(--ok);margin-top:2px}
@media (max-width:1180px){#s-work{grid-template-columns:minmax(0,1fr) 400px}.col.left{display:none}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""

BODY = """
<div class="app">
<header class="topbar">
  <div class="brand"><span class="logo"><svg class="i" viewBox="0 0 24 24"><path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M9 12l2 2 4-4"/></svg></span>cad-guard</div>
  <span class="sample-tag" title="Tầng dựng 3D và trợ lý LLM đang thử nghiệm">Studio 3D · thử nghiệm</span>
  <div class="spacer"></div>
  <label class="chip" title="LLM sẽ thấy toàn bộ nội dung bản vẽ"><input type="checkbox" id="consent"> Gửi nội dung bản vẽ tới <b id="bk">LLM</b></label>
  <button class="iconbtn" id="theme" title="Đổi giao diện sáng/tối" aria-label="Đổi giao diện sáng/tối"><svg class="i" viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/></svg></button>
</header>
<main id="s-work">
  <aside class="col left" aria-label="Bản vẽ">
    <div class="col-h">Bản vẽ</div>
    <div class="files" id="files"></div>
    <div class="std-box">
      <div class="k">Quy ước dựng 3D</div><div class="v">Đề xuất, chưa vào chuẩn</div>
      <div class="k" style="margin-top:6px">Dữ liệu gửi LLM</div><div class="v" id="dataMode">Chưa đồng ý</div>
      <div class="k" style="margin-top:6px">Chỉnh sửa chờ xuất</div><div class="v" id="editCnt">0</div>
    </div>
    <div style="padding:0 12px 14px;display:flex;flex-direction:column;gap:8px">
      <input type="file" id="file" accept=".dxf" hidden>
      <button class="btn-s" id="open" style="width:100%"><svg class="i" viewBox="0 0 24 24"><path d="M4 7a2 2 0 012-2h4l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H6a2 2 0 01-2-2z"/></svg>Mở tệp DXF…</button>
    </div>
  </aside>
  <section class="center" aria-label="Cảnh 3D">
    <div class="cv-tools">
      <strong id="cvTitle">Chưa mở bản vẽ</strong>
      <span class="pill neu" id="viewTag">Cảnh 3D · minh hoạ</span>
      <div class="spacer"></div>
      <button class="btn-s btn-sm" id="undo"><svg class="i" viewBox="0 0 24 24"><path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 010 12h-3"/></svg>Hoàn tác</button>
      <a class="btn-s btn-sm" id="glb" href="#">Tải .glb</a>
      <button class="btn-p btn-sm" id="export">Xuất bản chuẩn hoá (tệp mới)</button>
    </div>
    <div class="cv-wrap"><div class="sheet"><canvas id="c"></canvas><div class="empty3d" id="empty3d"><div><b>Chưa có gì để dựng</b><br>Mở một tệp DXF, hoặc bổ sung phần còn thiếu ở tab "Thiếu".</div></div></div></div>
    <div class="cv-status">
      <span class="lock"><svg class="i" viewBox="0 0 24 24" style="width:14px;height:14px"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/></svg>Tệp gốc chỉ đọc</span>
      <span>Mọi thay đổi được ghi ra <b>tệp mới</b>, có xem trước và hoàn tác. Ảnh 3D không dùng để đo.</span>
      <span class="spacer"></span><span id="cvInfo"></span>
    </div>
  </section>
  <aside class="col right" aria-label="Trợ lý">
    <div class="tabs" role="tablist" id="tabs"></div>
    <div class="pane on" id="p-chat">
      <div class="chat-head"><svg class="i" viewBox="0 0 24 24"><rect x="4" y="7" width="16" height="12" rx="3"/><path d="M12 3v4"/></svg><span>Đang dùng <b id="chatEng">chưa có LLM</b> · thấy toàn bộ nội dung bản vẽ khi bạn đồng ý</span></div>
      <div class="chat-log" id="log" aria-live="polite"></div>
      <div class="suggest" id="sug"></div>
      <form class="composer" id="form"><input id="msg" autocomplete="off" placeholder="Hỏi hoặc trao đổi, ví dụ: tấm giữa có đủ chịu tải không?" aria-label="Nhập câu hỏi"><button class="btn-p" id="send" aria-label="Gửi"><svg class="i" viewBox="0 0 24 24"><path d="M4 12l16-8-6 16-3-7z"/></svg></button></form>
      <div class="hint">Trợ lý giải thích và đề xuất. Đề xuất được mã kiểm tra rồi chờ bạn duyệt; đúng/sai về kích thước do mã tất định quyết định.</div>
    </div>
    <div class="pane" id="p-gaps"><div class="list" id="gaps"></div><div class="cs-foot" id="gapFoot" style="display:none"></div></div>
    <div class="pane" id="p-props"><div class="list" id="props"></div></div>
    <div class="pane" id="p-obs"><div class="list" id="obs"></div></div>
  </aside>
</main>
</div>
"""

JS = """
const T=new URLSearchParams(location.search).get('t');let S=null,tab='chat',fname='bản vẽ.dxf',busy=false;
const V=makeViewer(document.getElementById('c'));
const $=id=>document.getElementById(id);
function h(tag,attrs,...kids){const e=document.createElement(tag);for(const[k,v]of Object.entries(attrs||{})){if(k==='class')e.className=v;else if(k.startsWith('on'))e[k]=v;else e.setAttribute(k,v)}
for(const c of kids)if(c!=null)e.append(c instanceof Node?c:document.createTextNode(String(c)));return e}
const ICON={file:'<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/>',warn:'<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>',chat:'<path d="M21 12a8 8 0 01-11.5 7.2L4 20l1-4.6A8 8 0 1121 12z"/>',chg:'<path d="M7 4v12a3 3 0 003 3h7M17 4v8M14 7l3-3 3 3"/>',eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'};
function ic(n){const s=document.createElementNS('http://www.w3.org/2000/svg','svg');s.setAttribute('class','i');s.setAttribute('viewBox','0 0 24 24');s.innerHTML=ICON[n]||'';return s}
async function call(path,opts){const r=await fetch(path,Object.assign({headers:{'X-CG-Token':T}},opts||{}));if(!r.ok){let m=await r.text();try{m=JSON.parse(m).error||m}catch(e){}throw new Error(m)}return r}
async function post(path,obj){if(busy)return;busy=true;render();try{const r=await call(path,{method:'POST',headers:{'X-CG-Token':T,'Content-Type':'application/json'},body:JSON.stringify(obj||{})});S=await r.json()}catch(e){alert(e.message)}busy=false;render()}
function setTab(k){tab=k;render()}
const KIND={missing_value:['Thiếu giá trị','warn'],ambiguous:['Mơ hồ','warn'],missing_view:['Thiếu hình chiếu','err'],conflict:['Mâu thuẫn','err']};
function render(){
  if(!S){return}
  const sc=S.scene,pend=S.proposals.filter(p=>p.status==='pending');
  $('bk').textContent=S.backend||'LLM (chưa có)';$('chatEng').textContent=S.backend||'chưa có LLM';$('consent').checked=S.consent;$('consent').disabled=!S.backend;
  $('dataMode').textContent=S.consent?'Toàn bộ nội dung bản vẽ':'Chưa đồng ý';$('editCnt').textContent=S.edits;
  $('undo').disabled=!S.can_undo||busy;$('cvTitle').textContent=fname;$('glb').href='/api/glb?t='+T;
  $('cvInfo').textContent=sc.panels.length+' tấm · '+sc.modules+' mô-đun · '+sc.walls+' đoạn tường · '+S.clusters.length+' cụm hình học';
  $('empty3d').style.display=sc.boxes.length?'none':'grid';V.set(sc.boxes);
  const files=$('files');files.replaceChildren(h('button',{class:'file','aria-current':'true'},h('span',{class:'n'},ic('file'),fname),h('span',{class:'m'},
    h('span',{class:'pill '+(sc.gaps.length||!sc.boxes.length?'warn':'ok')},sc.gaps.length?sc.gaps.length+' phần thiếu':!sc.boxes.length?'Chưa dựng được 3D':'Đủ dữ liệu'),h('span',{class:'pill neu'},'#'+S.hash.slice(0,6)))));
  for(const c of S.clusters)files.append(h('div',{class:'file child'},h('span',{class:'n'},c.id),h('span',{class:'m'},h('span',{class:'pill neu'},c.size[0]+'×'+c.size[1]),h('span',{class:'pill neu'},c.entities+' nét'),...c.layers.slice(0,3).map(l=>h('span',{class:'pill info'},l)))));
  const tabs=[['chat','chat','Trợ lý',0],['gaps','warn','Thiếu',sc.gaps.length],['props','chg','Thay đổi',pend.length],['obs','eye','Nhận xét',S.observations.length]];
  $('tabs').replaceChildren(...tabs.map(([k,i,t,n])=>{const b=h('button',{role:'tab','aria-selected':k===tab},ic(i),t);if(k!=='chat')b.append(h('span',{class:'cnt'+(k==='gaps'&&n?' hot':'')},n));b.onclick=()=>setTab(k);return b}));
  for(const k of['chat','gaps','props','obs'])$('p-'+k).classList.toggle('on',k===tab);
  // trợ lý
  const log=$('log');log.replaceChildren();
  if(!S.chat.length)log.append(h('div',{class:'msg ai'},'Chào bạn. Bấm "Phân tích bản vẽ" hoặc đặt câu hỏi. Tôi chỉ đề xuất; mọi đề xuất được mã kiểm tra rồi chờ bạn duyệt trước khi áp dụng.'));
  for(const m of S.chat)log.append(h('div',{class:'msg '+(m.role==='user'?'me':'ai')},m.text));
  for(const n of S.notes)log.append(h('div',{class:'note-card'},n));
  if(busy)log.append(h('div',{class:'note-card'},'Đang xử lý…'));
  log.scrollTop=log.scrollHeight;
  const ok=S.backend&&S.consent&&!busy;const sug=$('sug');sug.replaceChildren();
  for(const[t,q,pr]of[['Phân tích bản vẽ',null,true],['Tìm điểm bất hợp lý','Tìm các điểm bất hợp lý hoặc lỗ hổng kỹ thuật trong bản vẽ này.'],['Cần bổ sung gì để dựng 3D?','Để dựng 3D đầy đủ và chính xác, còn thiếu thông tin gì? Hãy hỏi tôi.']]){
    const b=h('button',{class:pr?'primary':''},t);b.disabled=!ok;b.onclick=()=>q?post('/api/chat',{message:q}):post('/api/analyze');sug.append(b)}
  $('send').disabled=!ok;
  // thiếu
  const gl=$('gaps');gl.replaceChildren();const inputs=[];
  if(!sc.gaps.length)gl.append(h('div',{class:'empty'},h('b',{},'Không có phần nào còn thiếu'),'Cảnh 3D đã dựng đủ từ dữ liệu hiện có.'));
  for(const g of sc.gaps){const k=KIND[g.kind]||[g.kind,'neu'];const c=h('div',{class:'f-card'},h('div',{class:'f-top'},h('span',{class:'pill '+k[1]},k[0]),h('span',{class:'f-meta'},g.id)),h('div',{class:'f-title'},g.message));
    if(!g.fields.length)c.append(h('div',{class:'f-d'},'Phải sửa hoặc bổ sung bản vẽ; không nhập tay được.'));
    for(const f of g.fields){let inp;if(f.kind==='choice')inp=h('select',{},h('option',{value:''},'— chọn —'),...f.options.map(o=>h('option',{},o)));else inp=h('input',{type:'number',step:'any',min:'0'});inp.dataset.key=f.key;inputs.push(inp);c.append(h('label',{class:'fld'},f.label+' ('+f.unit+')',inp))}
    gl.append(c)}
  const gf=$('gapFoot');gf.style.display=inputs.length?'block':'none';gf.replaceChildren();
  if(inputs.length){gf.append(h('div',{class:'safe'},h('span',{},'Giá trị bạn nhập được đánh dấu "do người nhập" trong cảnh 3D. Bản vẽ gốc không bị sửa.')));
    const b=h('button',{class:'btn-p',style:'width:100%;margin-top:10px'},'Lưu giá trị đã nhập');b.onclick=()=>{const v={};inputs.forEach(i=>{if(i.value!=='')v[i.dataset.key]=i.value});post('/api/values',{values:v})};gf.append(b)}
  // thay đổi (đề xuất)
  const pl=$('props');pl.replaceChildren();
  if(!S.proposals.length)pl.append(h('div',{class:'empty'},h('b',{},'Chưa có thay đổi nào'),'Khi trợ lý đề xuất, từng thay đổi hiện ở đây để bạn xem và duyệt.'));
  for(const p of S.proposals){const lines=p.kind==='set_views'?Object.entries(p.views).map(([a,b])=>'+ hình chiếu '+a+' = cụm '+b):p.kind==='set_value'?['+ '+p.key+' = '+p.value]:p.kind==='set_attrib'?['+ khối '+p.handle+': '+p.tag+' = '+p.value]:['+ '+(p.handles||[]).length+' đối tượng → layer '+p.layer];
    const st={pending:['Chờ duyệt','warn'],accepted:['Đã duyệt','ok'],rejected:['Đã bỏ','neu']}[p.status];
    const c=h('div',{class:'op'},h('div',{class:'f-top'},h('span',{class:'pill '+st[1]},st[0]),h('span',{class:'pill neu'},p.kind),h('span',{class:'pill info'},'LLM đề xuất, mã đã kiểm tham chiếu')),h('div',{class:'f-title'},p.why||'(không có lý do)'),h('div',{class:'diff'},...lines.map(l=>h('div',{class:'p'},l))));
    if(p.status==='pending'){const a=h('button',{class:'btn-p btn-sm'},'Duyệt');a.onclick=()=>post('/api/proposals/'+p.id+'/accept');const r=h('button',{class:'btn-s btn-sm'},'Bỏ');r.onclick=()=>post('/api/proposals/'+p.id+'/reject');c.append(h('div',{class:'f-act'},a,r))}
    pl.append(c)}
  // nhận xét
  const ol=$('obs');ol.replaceChildren(h('div',{class:'note-card'},'Gợi ý của LLM, chưa kiểm tất định. Hãy đối chiếu với bản vẽ trước khi tin.'));
  for(const o of S.observations)ol.append(h('div',{class:'f-card'},h('div',{class:'f-top'},h('span',{class:'pill '+({error:'err',warn:'warn'}[o.severity]||'info')},o.severity),h('span',{class:'pill neu'},'LLM · chưa kiểm')),h('div',{class:'f-title'},o.text),h('div',{class:'f-meta'},o.refs.length?'Tham chiếu: '+o.refs.join(', '):'')));
}
$('open').onclick=()=>$('file').click();
$('file').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const r=await call('/api/open',{method:'POST',body:await f.arrayBuffer()});S=await r.json();fname=f.name;tab='chat';render()}catch(x){alert(x.message)}e.target.value=''};
$('consent').onchange=e=>post('/api/consent',{value:e.target.checked});
$('undo').onclick=()=>post('/api/undo');
$('export').onclick=async()=>{if(!S)return;try{const j=await(await call('/api/export',{method:'POST'})).json();alert('Đã ghi tệp mới: '+j.path+'\\nBản gốc không bị thay đổi.')}catch(x){alert(x.message)}};
$('form').onsubmit=e=>{e.preventDefault();const t=$('msg').value.trim();if(!t||$('send').disabled)return;$('msg').value='';post('/api/chat',{message:t})};
$('theme').onclick=()=>{const d=document.documentElement;d.dataset.theme=d.dataset.theme==='dark'?'light':'dark';V.fit()};
call('/api/state').then(r=>r.json()).then(j=>{S=j;render()}).catch(()=>{render0()});
function render0(){S={hash:'',backend:null,consent:false,scene:{boxes:[],walls:0,modules:0,panels:[],gaps:[],skipped:[],notes:[]},clusters:[],proposals:[],observations:[],chat:[],notes:[],can_undo:false,edits:0};fname='Chưa mở bản vẽ';render()}
"""

PAGE = (
    "<!doctype html>\n<html lang='vi' data-theme='light'><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width, initial-scale=1'><title>cad-guard studio</title><style>"
    + CSS
    + "</style></head><body>"
    + BODY
    + "<script>\n"
    + VIEWER_JS
    + JS
    + "</script></body></html>\n"
)
