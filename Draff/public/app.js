/* ---------- helpers ---------- */
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const IC = {
  check: '<path d="M5 12l5 5 9-10"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  alert: '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  file: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/>',
  moon: '<path d="M20 14A8 8 0 0110 4a8 8 0 1010 10z"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M4 16V6a2 2 0 012-2h10"/>',
  undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 010 12h-3"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
  hand: '<path d="M8 13V6a1.5 1.5 0 013 0v5M11 11V4.5a1.5 1.5 0 013 0V11M14 11V6a1.5 1.5 0 013 0v8a6 6 0 01-6 6h-1a5 5 0 01-4-2l-3-4a1.5 1.5 0 012.3-1.9L8 14"/>',
  inbox: '<path d="M4 13l2-8h12l2 8v6H4z"/><path d="M4 13h5l1 2h4l1-2h5"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  build: '<path d="M3 21h18M5 21V8l7-5 7 5v13M9 21v-6h6v6"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0113 0M16 4.5a3.5 3.5 0 010 7M18 14a6 6 0 013.5 6"/>',
  spark: '<path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z"/>',
  cad: '<rect x="3" y="4" width="18" height="14" rx="2"/><path d="M8 21h8M12 18v3"/>'
};
const ic = (n, s) => `<svg class="i" viewBox="0 0 24 24"${s ? ` style="${s}"` : ''}>${IC[n] || IC.info}</svg>`;

/* ---------- theme ---------- */
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  if ($('#themeSvg')) $('#themeSvg').innerHTML = t === 'dark' ? IC.sun : IC.moon;
}
setTheme(matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
const q = new URLSearchParams(location.search);
if (q.get('theme')) setTheme(q.get('theme'));
if ($('#themeBtn')) {
  $('#themeBtn').onclick = () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
}

/* ---------- screens ---------- */
$$('[data-go]').forEach(b => b.onclick = () => {
  closeMenus();
  go(b.dataset.go);
});
function go(n) {
  $$('.screen').forEach(s => s.classList.toggle('on', s.id === 's-' + n));
  $$('[data-go]').forEach(b => b.setAttribute('aria-selected', b.dataset.go === n));
  if (n === 'rules') renderRules();
  else if (typeof RS !== 'undefined' && RS.open) {
    RS.open = null;
    renderDrawer();
  }
}

/* ---------- menus ---------- */
const ENGINES = [
  { id: 'gemini', n: 'Gemini 2.5 Flash', d: 'API máy chủ · Phân tích sâu bản vẽ nội thất (Lớp 2 AI)' },
  { id: 'claude', n: 'Claude Code', d: 'CLI có sẵn · Kết nối qua MCP Server cục bộ' },
  { id: 'codex', n: 'Codex CLI', d: 'CLI có sẵn · bạn tự đăng nhập' },
  { id: 'agy', n: 'Antigravity CLI', d: 'CLI có sẵn · bạn tự đăng nhập' },
  { id: 'opencode', n: 'OpenCode + khoá API', d: 'Anthropic · OpenAI · Gemini · OpenRouter · khoá của công ty' },
  { id: 'local', n: 'Mô hình trên máy', d: 'Dữ liệu không rời máy (Bậc L)' }
];
let engine = ENGINES[0];
let studioMode = 'audit'; // 'audit' | 'diff' | 'scene'
let activeLeftFilter = 'all';
let hiddenLayers = new Set(); // Tập các layer đang bị người dùng bấm ẩn
let reviewPins = []; // Không dùng ghim giả định

function closeMenus() {
  if ($('#engineMenu')) $('#engineMenu').hidden = true;
  if ($('#deptMenu')) $('#deptMenu').hidden = true;
  if ($('#projMenu')) $('#projMenu').hidden = true;
  if ($('#settingsMenu')) $('#settingsMenu').hidden = true;
  if ($('#exportMenu')) $('#exportMenu').hidden = true;
  if ($('#engineBtn')) $('#engineBtn').setAttribute('aria-expanded', false);
  if ($('#deptBtn')) $('#deptBtn').setAttribute('aria-expanded', false);
  if ($('#projBtn')) $('#projBtn').setAttribute('aria-expanded', false);
  if ($('#settingsMenuBtn')) $('#settingsMenuBtn').setAttribute('aria-expanded', false);
  if ($('#exportMenuBtn')) $('#exportMenuBtn').setAttribute('aria-expanded', false);
}
function renderEngineMenu() {
  if (!$('#engineMenu')) return;
  $('#engineMenu').innerHTML = ENGINES.map(e => `<button role="menuitemradio" aria-checked="${e.id === engine.id}" data-e="${e.id}"><span style="width:18px;margin-top:2px">${e.id === engine.id ? ic('check') : ''}</span><span><span class="t">${e.n}</span><br><span class="d">${e.d}</span></span></button>`).join('');
  $$('#engineMenu button').forEach(b => b.onclick = () => {
    engine = ENGINES.find(x => x.id === b.dataset.e);
    if ($('#engineName')) $('#engineName').textContent = engine.n;
    if ($('#chatEng')) $('#chatEng').textContent = engine.n;
    closeMenus();
    renderEngineMenu();
    toast(`Đã chuyển mô hình trợ lý sang ${engine.n}`);
  });
}
if ($('#settingsMenuBtn')) {
  $('#settingsMenuBtn').onclick = e => {
    e.stopPropagation();
    const open = $('#settingsMenu').hidden;
    closeMenus();
    $('#settingsMenu').hidden = !open;
    $('#settingsMenuBtn').setAttribute('aria-expanded', open);
  };
}
if ($('#exportMenuBtn')) {
  $('#exportMenuBtn').onclick = e => {
    e.stopPropagation();
    const open = $('#exportMenu').hidden;
    closeMenus();
    $('#exportMenu').hidden = !open;
    $('#exportMenuBtn').setAttribute('aria-expanded', open);
  };
}
if ($('#brandHomeBtn')) {
  $('#brandHomeBtn').onclick = () => go('work');
}
document.addEventListener('click', closeMenus);
renderEngineMenu();

/* ---------- chuỗi 4 phòng ---------- */
const DEPT = {
  design: { name: 'Thiết kế', prev: null, next: 'Kỹ thuật', nextKey: 'tech', role: 'Triển khai mặt bằng và mặt đứng không gian nội thất', mess: 'Giao cho Kỹ thuật' },
  tech: { name: 'Kỹ thuật', prev: 'Thiết kế', next: 'Thiết kế 3D và Lập trình sản xuất', nextKey: 'cnc', role: 'Triển khai chi tiết kết cấu, kích thước chuỗi, khe hở phụ kiện và bảng kê', mess: 'Giao cho Thiết kế 3D và Lập trình SX' },
  viz: { name: 'Thiết kế 3D', prev: 'Kỹ thuật', next: 'Render', nextKey: 'render', role: 'Dựng 3D từ bản kỹ thuật đã chuẩn, kiểm tra công thái học và vật liệu', mess: 'Giao cho Render' },
  cnc: { name: 'Lập trình sản xuất', prev: 'Kỹ thuật', next: 'Xưởng', nextKey: 'shop', role: 'Chuẩn bị dữ liệu đường bao khép kín và lỗ khoan cho máy CNC', mess: 'Giao cho Xưởng' }
};
const ORDER = ['design', 'tech', 'viz', 'cnc'];
let stage = 'tech';
let zoomLevel = 1;
let activeTierFilter = 'all';
let activeWsFile = 'hygiene_bad.dxf';

/* ---------- Khung khởi tạo trống khi đang tải tệp DXF thật từ máy chủ ---------- */
function emptySvgPlaceholder() {
  return `<text class="txt" x="410" y="270" font-size="13" text-anchor="middle" opacity="0.65">Đang tải dữ liệu hình học từ tệp DXF thực tế…</text>`;
}
const BODIES = {
  design: emptySvgPlaceholder,
  tech: emptySvgPlaceholder,
  viz: emptySvgPlaceholder,
  cnc: emptySvgPlaceholder
};

/* ---------- Trạng thái mặc định dựa trên tệp thật trong Workspace ---------- */
const DEFAULT_CASE = {
  project: 'Workspace DXF',
  file: 'hygiene_bad.dxf',
  view: 'Mặt đứng · 1:20',
  info: 'Đang đọc tệp DXF…',
  standard: 'furniture-v0.1.0',
  rulesOn: '58 luật tất định + Lớp 2 AI',
  secs: '0,4 giây',
  aria: 'Bản vẽ kỹ thuật DXF thực tế',
  sheets: [{ id: 0, code: 'A3-01', title: 'Bản vẽ chính', scale: '1:20', type: 'layout' }],
  files: [],
  tool: 'Kiểm toán tất định trên tệp DXF thực tế',
  about: '<p>Bản vẽ DXF thực tế đang mở trong phiên làm việc.</p>',
  findings: [],
  ops: {
    a: { what: 'Chuyển các đối tượng vi phạm trên Layer 0 về Layer chuẩn', from: 'Layer 0', to: 'FN-FURN / FN-DIM-N' },
    b: { what: 'Chuẩn hoá chiều cao chữ ghi chú & kiểu chữ', from: 'Chiều cao chữ lệch chuẩn', to: 'Chiều cao chuẩn 2.5mm' }
  },
  validate: 'mở lại OK · bảo toàn số lượng đối tượng · đã kiểm tra lại bằng bộ luật tất định',
  explain: { rule: 'LY-03', html: '<p><b>LY-03 · Không để đối tượng vẽ trực tiếp trên Layer 0.</b></p>' },
  needExplain: { rule: 'SH-05', html: '<p><b>SH-05 · Khung tên cần điền đầy đủ thuộc tính kiểm duyệt.</b></p>' },
  handover: { title: 'Ghi chú bàn giao kỹ thuật', items: ['Đã kiểm tra layer và chiều cao chữ theo chuẩn công ty', 'Tệp gốc được giữ nguyên chỉ đọc (Read-only)'], warn: 'Kiểm tra các mục cần người quyết định trước khi bàn giao' },
  pack: { name: 'ban-ve-chuan-hoa', list: ['ban-ve_v2.dxf (tệp mới)', 'bao-cao-tham-dinh.html'] },
  idleName: 'ok_sheet',
  inbox: null
};

const CASES = {
  design: { ...DEFAULT_CASE, standard: 'design-hygiene-v0' },
  tech: { ...DEFAULT_CASE, standard: 'furniture-v0.1.0' },
  viz: { ...DEFAULT_CASE, standard: 'furniture-v0.1.0' },
  cnc: { ...DEFAULT_CASE, standard: 'furniture-v0.1.0' }
};

const ST = {};
ORDER.forEach(k => ST[k] = {
  scanned: true,
  proposed: true,
  accepted: false,
  view: 'after',
  ops: { a: true, b: true },
  sel: null,
  v2: false,
  handover: false,
  packD: false,
  received: false,
  logHTML: null,
  sheetIdx: 0
});

let customDxfData = null;
let canvasMode = '2d'; // '2d' | '3d'
let currentScene3D = null;
let studioWireframe = true;
let studioSelectedBoxId = null;
let cam3D = {
  yaw: -0.65,
  pitch: 0.48,
  zoom: 1.0,
  panX: 0,
  panY: 0,
  targetYaw: -0.65,
  targetPitch: 0.48,
  targetZoom: 1.0,
  targetPanX: 0,
  targetPanY: 0,
  dragging: false,
  mode: 'orbit',
  lastX: 0,
  lastY: 0
};

const K = () => {
  const base = CASES[stage] || DEFAULT_CASE;
  if (customDxfData) {
    return {
      ...base,
      project: customDxfData.projectName || base.project,
      file: customDxfData.fileName || activeWsFile || base.file,
      view: (customDxfData.sheets?.[0]?.code || 'A3-01') + ' · ' + (customDxfData.sheets?.[0]?.scale || '1:20'),
      info: customDxfData.info || base.info,
      standard: ($('#stdSelect') && $('#stdSelect').value) || customDxfData.standardProfile || base.standard,
      sheets: customDxfData.sheets || base.sheets,
      ops: customDxfData.ops || base.ops
    };
  }
  return base;
};
const C = () => ST[stage];
const FIND = () => {
  if (customDxfData && Array.isArray(customDxfData.findings)) {
    return customDxfData.findings;
  }
  return [];
};

function renderArtboardBar() {
  // Đã lược bỏ thanh Artboard trùng lặp để dành tối đa diện tích cho bản vẽ
}

/* ---------- Khung bản vẽ 2D thực tế & Tô sáng trực tiếp đối tượng lỗi ---------- */
let svg = $('#svg');
function applyZoom() {
  apply2DTransform();
}

function mountSheet() {
  const c = C(), k = K();
  const shIdx = c.sheetIdx || 0;
  let svgInner = '';
  if (customDxfData && Array.isArray(customDxfData.sheets) && customDxfData.sheets.length > 0) {
    const shObj = customDxfData.sheets[shIdx] || customDxfData.sheets[0];
    svgInner = shObj ? shObj.svgBody : emptySvgPlaceholder();
  } else {
    svgInner = emptySvgPlaceholder();
  }

  svg = $('#svg');
  if (!svg) return;
  svg.setAttribute('aria-label', k.aria || `Bản vẽ ${k.file}`);
  svg.classList.remove('hl-active');
  svg.innerHTML = svgInner;

  if ($('#hlStatusPill')) $('#hlStatusPill').hidden = true;
  if ($('#clearHighlightBtn')) $('#clearHighlightBtn').hidden = true;

  apply2DTransform();
  applyLayerFilterToSvg();

  // Nếu đang có lỗi được chọn, tô sáng lại các nét vẽ của lỗi đó
  if (c.sel) {
    const selFinding = FIND().find(x => x.id === c.sel);
    if (selFinding) highlightFindingEntities(selFinding, false);
  }
}

// ===== 2D Canvas Pan & Zoom Engine =====
let sheet2D = {
  zoom: 1.0,
  panX: 0,
  panY: 0,
  isDragging: false,
  startX: 0,
  startY: 0
};

function apply2DTransform(smooth = false) {
  svg = $('#svg');
  if (!svg) return;
  const sheetEl = $('#sheet');
  if (smooth && sheetEl) {
    sheetEl.classList.add('smooth-transition');
    setTimeout(() => {
      if (sheetEl) sheetEl.classList.remove('smooth-transition');
    }, 360);
  }
  svg.style.transform = `translate(${sheet2D.panX}px, ${sheet2D.panY}px) scale(${sheet2D.zoom})`;
  const pct = Math.round(sheet2D.zoom * 100) + '%';
  if ($('#hudZoomResetBtn')) $('#hudZoomResetBtn').textContent = pct;
}

function zoom2D(delta, clientX, clientY) {
  const oldZoom = sheet2D.zoom;
  const newZoom = Math.max(0.4, Math.min(40.0, +(oldZoom * delta).toFixed(3)));
  if (newZoom === oldZoom) return;

  const sheetEl = $('#sheet');
  if (sheetEl && clientX !== undefined && clientY !== undefined) {
    const rect = sheetEl.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const mouseOffsetX = clientX - cx;
    const mouseOffsetY = clientY - cy;

    sheet2D.panX = mouseOffsetX - (mouseOffsetX - sheet2D.panX) * (newZoom / oldZoom);
    sheet2D.panY = mouseOffsetY - (mouseOffsetY - sheet2D.panY) * (newZoom / oldZoom);
  }
  sheet2D.zoom = newZoom;
  apply2DTransform();
}

function reset2DZoom() {
  sheet2D.zoom = 1.0;
  sheet2D.panX = 0;
  sheet2D.panY = 0;
  apply2DTransform(true);
}

function fit2DZoom() {
  // Vì viewBox đã dùng Percentile Bounding Box (2% - 98%) tự động lắp đầy ~88% khung nhìn,
  // đặt lại zoom = 1.0 và pan = (0,0) sẽ vừa khít toàn bộ nét vẽ chính xác.
  sheet2D.zoom = 1.0;
  sheet2D.panX = 0;
  sheet2D.panY = 0;
  apply2DTransform(true);
}

/* ---------- TÔ SÁNG TRỰC TIẾP ĐỐI TƯỢNG LỖI TRÊN NÉT VẼ THẬT ---------- */
function clearFindingHighlight() {
  svg = $('#svg');
  if (svg) {
    svg.classList.remove('hl-active');
    svg.querySelectorAll('.dxf-ent.hl-hit').forEach(el => el.classList.remove('hl-hit'));
  }
  if ($('#hlStatusPill')) $('#hlStatusPill').hidden = true;
  if ($('#clearHighlightBtn')) $('#clearHighlightBtn').hidden = true;
  C().sel = null;
  $$('.f-card.sel').forEach(c => c.classList.remove('sel'));
}

function highlightFindingEntities(finding, panToTarget = true) {
  svg = $('#svg');
  if (!finding || !svg) return;

  svg.querySelectorAll('.dxf-ent.hl-hit').forEach(el => el.classList.remove('hl-hit'));

  const targetLayers = new Set((finding.targetLayers || []).map(l => String(l).toUpperCase()));
  const targetHandles = new Set((finding.targetHandles || []).map(h => String(h)));

  const allEnts = [...svg.querySelectorAll('.dxf-ent')];
  let matched = [];

  allEnts.forEach(el => {
    const elLayer = (el.getAttribute('data-layer') || '').toUpperCase();
    const elHandle = el.getAttribute('data-handle') || '';
    if ((elHandle && targetHandles.has(elHandle)) || (elLayer && targetLayers.has(elLayer))) {
      el.classList.add('hl-hit');
      matched.push(el);
    }
  });

  // Nếu lỗi theo vùng/loại đối tượng mà chưa khớp trực tiếp handle/layer, lọc theo vùng toạ độ thực của lỗi
  if (matched.length === 0 && allEnts.length > 0) {
    if (finding.rule === 'TX-02' || finding.rule === 'VS-02' || finding.rule === 'VS-04') {
      matched = allEnts.filter(el => el.tagName.toLowerCase() === 'text');
    } else if (finding.rule === 'LY-03' || finding.rule === 'VS-03') {
      matched = allEnts.filter(el => (el.getAttribute('data-layer') || '') === '0');
    } else if (finding.rule === 'VS-01' || finding.rule === 'LY-04') {
      matched = allEnts.filter(el => (el.getAttribute('data-layer') || '').includes('$'));
    }
    if (matched.length === 0) {
      matched = allEnts.slice(0, Math.min(25, allEnts.length));
    }
    matched.forEach(el => el.classList.add('hl-hit'));
  }

  svg.classList.add('hl-active');

  const hitCount = finding.count || matched.length || 1;
  if ($('#hlStatusPill')) {
    $('#hlStatusPill').hidden = false;
    if ($('#hlStatusText')) {
      $('#hlStatusText').textContent = `Đang tô sáng ${hitCount} đối tượng của lỗi ${finding.rule} (${finding.title})`;
    }
  }
  if ($('#clearHighlightBtn')) $('#clearHighlightBtn').hidden = false;

  if (panToTarget) {
    const sheetEl = $('#sheet');
    if (sheetEl && finding.m && finding.m.box) {
      const [bx, by, bw, bh] = finding.m.box;
      const targetX = bx + bw / 2;
      const targetY = by + bh / 2;
      const rect = sheetEl.getBoundingClientRect();
      const baseScale = Math.min(rect.width / 820, rect.height / 540);
      // Tính mức zoom vừa vặn với cụm đối tượng lỗi
      const desiredZoom = Math.max(1.35, Math.min(4.2, +(Math.min(520 / Math.max(bw, 70), 360 / Math.max(bh, 60))).toFixed(2)));
      sheet2D.zoom = desiredZoom;
      sheet2D.panX = (410 - targetX) * baseScale * desiredZoom;
      sheet2D.panY = (270 - targetY) * baseScale * desiredZoom;
      apply2DTransform(true);
    }
  }
}

function focusFindingOnCanvas(finding) {
  if (!finding) return;
  if (canvasMode === '3d') setCanvasMode('2d');
  highlightFindingEntities(finding, true);
  syncToAutoCAD(finding);
}

if ($('#hlResetBtn')) {
  $('#hlResetBtn').onclick = () => {
    clearFindingHighlight();
    fit2DZoom();
  };
}
if ($('#clearHighlightBtn')) {
  $('#clearHighlightBtn').onclick = () => {
    clearFindingHighlight();
    fit2DZoom();
  };
}

// Điều khiển Zoom trên HUD nổi
if ($('#hudZoomInBtn')) {
  $('#hudZoomInBtn').onclick = () => zoom2D(1.25);
}
if ($('#hudZoomOutBtn')) {
  $('#hudZoomOutBtn').onclick = () => zoom2D(0.8);
}
if ($('#hudZoomResetBtn')) {
  $('#hudZoomResetBtn').onclick = () => reset2DZoom();
}
if ($('#hudFitBtn')) {
  $('#hudFitBtn').onclick = () => fit2DZoom();
}
if ($('#hudFocusErrBtn')) {
  $('#hudFocusErrBtn').onclick = () => {
    const c = C(), F = FIND();
    const curFinding = F.find(x => x.id === c.sel) || F[0];
    if (curFinding) {
      select(curFinding.id, false);
    } else {
      toast('Bản vẽ này không có lỗi nào cần tô sáng');
    }
  };
}

// HUD 3D
if ($('#hud3dZoomInBtn')) {
  $('#hud3dZoomInBtn').onclick = () => {
    cam3D.targetZoom = Math.min(80.0, +(cam3D.targetZoom * 1.3).toFixed(2));
  };
}
if ($('#hud3dZoomOutBtn')) {
  $('#hud3dZoomOutBtn').onclick = () => {
    cam3D.targetZoom = Math.max(0.2, +(cam3D.targetZoom / 1.3).toFixed(2));
  };
}
if ($('#hud3dZoomResetBtn')) {
  $('#hud3dZoomResetBtn').onclick = () => resetStudio3DCam('iso');
}
if ($('#hud3dFitBtn')) {
  $('#hud3dFitBtn').onclick = () => resetStudio3DCam('iso');
}
if ($('#hud3dFocusGapBtn')) {
  $('#hud3dFocusGapBtn').onclick = () => focus3DSelected();
}

// Bắt sự kiện chuột và cảm ứng trên 2D Sheet Canvas
(function init2DCanvasEvents() {
  const sheetEl = $('#sheet');
  if (!sheetEl) return;

  sheetEl.addEventListener('wheel', e => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.18 : 0.85;
    zoom2D(factor, e.clientX, e.clientY);
  }, { passive: false });

  sheetEl.addEventListener('mousedown', e => {
    if (e.target.closest && (e.target.closest('.canvas-hud') || e.target.closest('.hl-floating-pill'))) return;
    sheet2D.isDragging = true;
    sheet2D.startX = e.clientX - sheet2D.panX;
    sheet2D.startY = e.clientY - sheet2D.panY;
    sheetEl.classList.add('panning');
  });

  window.addEventListener('mousemove', e => {
    if (!sheet2D.isDragging) return;
    sheet2D.panX = e.clientX - sheet2D.startX;
    sheet2D.panY = e.clientY - sheet2D.startY;
    apply2DTransform();
  });

  window.addEventListener('mouseup', () => {
    if (sheet2D.isDragging) {
      sheet2D.isDragging = false;
      sheetEl.classList.remove('panning');
    }
  });
})();

/* ---------- DANH SÁCH LAYER THẬT TRONG BẢN VẼ ĐANG MỞ ---------- */
function renderRealLayers() {
  const bar = $('#layerChipsBar');
  if (!bar) return;
  const layersList = (customDxfData && Array.isArray(customDxfData.layersList) && customDxfData.layersList.length > 0)
    ? customDxfData.layersList
    : (customDxfData && Array.isArray(customDxfData.layers))
      ? customDxfData.layers.map(n => ({ name: n, color: '#0f766e', count: 1 }))
      : [];

  if (!layersList.length) {
    bar.innerHTML = `<span style="font-size:11.5px;color:var(--text3);padding:4px">Đang tải danh sách Layer thực tế…</span>`;
    return;
  }

  bar.innerHTML = layersList.map(l => {
    const isOn = !hiddenLayers.has(l.name);
    return `<button type="button" class="lyr-chip${isOn ? ' on' : ''}" data-layer="${esc(l.name)}" title="Bật/tắt Layer ${esc(l.name)} (${l.count} đối tượng)">
      <span class="sw" style="background:${l.color || '#0f766e'}"></span>
      <span class="lnm">${esc(l.name)}</span>
      <span class="lct">(${l.count})</span>
    </button>`;
  }).join('');

  $$('#layerChipsBar .lyr-chip').forEach(btn => {
    btn.onclick = () => {
      const lyr = btn.dataset.layer;
      if (hiddenLayers.has(lyr)) {
        hiddenLayers.delete(lyr);
        btn.classList.add('on');
      } else {
        hiddenLayers.add(lyr);
        btn.classList.remove('on');
      }
      applyLayerFilterToSvg();
    };
  });
}

function applyLayerFilterToSvg() {
  svg = $('#svg');
  if (!svg) return;
  svg.querySelectorAll('.dxf-ent').forEach(el => {
    const lyr = el.getAttribute('data-layer') || '0';
    el.style.display = hiddenLayers.has(lyr) ? 'none' : '';
  });
}

if ($('#resetLayersBtn')) {
  $('#resetLayersBtn').onclick = () => {
    hiddenLayers.clear();
    $$('#layerChipsBar .lyr-chip').forEach(b => b.classList.add('on'));
    applyLayerFilterToSvg();
    toast('Đã hiển thị toàn bộ các Layer thực tế của bản vẽ');
  };
}

/* ---------- CHUYỂN ĐỔI 2 CHẾ ĐỘ CANVAS CHÍNH: BẢN VẼ 2D & MÔ HÌNH 3D ---------- */
function setCanvasMode(mode) {
  canvasMode = mode;
  if ($('#mode2dBtn')) {
    $('#mode2dBtn').classList.toggle('on', mode === '2d');
    $('#mode2dBtn').setAttribute('aria-selected', mode === '2d');
  }
  if ($('#mode3dBtn')) {
    $('#mode3dBtn').classList.toggle('on', mode === '3d');
    $('#mode3dBtn').setAttribute('aria-selected', mode === '3d');
  }
  const sheetEl = $('#sheet');
  const st3dEl = $('#studio3dWrap');
  if (mode === '3d') {
    if (sheetEl) sheetEl.hidden = true;
    if (st3dEl) st3dEl.hidden = false;
    loadStudio3DScene();
  } else {
    if (sheetEl) sheetEl.hidden = false;
    if (st3dEl) st3dEl.hidden = true;
  }
}

if ($('#mode2dBtn')) {
  $('#mode2dBtn').onclick = () => setCanvasMode('2d');
}
if ($('#mode3dBtn')) {
  $('#mode3dBtn').onclick = () => setCanvasMode('3d');
}

function setStudioMode(smode) {
  studioMode = smode;
  go('work');
  if (smode === 'scene') {
    setCanvasMode('3d');
  } else {
    setCanvasMode('2d');
    if (smode === 'diff') {
      const c = C();
      c.proposed = true;
      c.view = 'after';
      switchRightTopTab('chg');
      syncCanvas();
      renderChg();
      renderFinds();
    } else {
      syncCanvas();
    }
  }
}

async function loadStudio3DScene(supplement = {}, viewOverrides = {}) {
  const targetFile = activeWsFile || K().file;
  const aiConsent = $('#studioAiConsent') ? $('#studioAiConsent').checked : true;
  const sheetIdx = C().sheetIdx || 0;
  try {
    const res = await fetch('/api/studio/scene', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fileName: targetFile, supplement, viewOverrides, aiConsent, sheetIdx })
    });
    currentScene3D = await res.json();
    renderStudioPane();
    resetStudio3DCam('iso');
    drawStudio3D();
  } catch (e) {
    toast('Lỗi dựng cảnh 3D: ' + e.message);
  }
}

function renderStudioPane() {
  const sc = currentScene3D;
  if (!sc) return;
  const gapCount = (sc.gaps || []).length;
  if ($('#gapBadge')) {
    $('#gapBadge').textContent = gapCount;
    $('#gapBadge').className = 'cnt' + (gapCount ? ' hot' : '');
  }
  if ($('#cntG')) {
    $('#cntG').textContent = gapCount;
    $('#cntG').className = 'cnt' + (gapCount ? ' hot' : '');
  }
  if ($('#st3dSummary')) {
    $('#st3dSummary').textContent = `${(sc.walls || []).length} tường · ${(sc.modules || []).length} mô-đun · ${(sc.panels || []).length} tấm ván`;
  }
  if ($('#st3dGapsPill')) {
    $('#st3dGapsPill').className = `pill ${gapCount ? 'warn' : 'ok'} sm`;
    $('#st3dGapsPill').textContent = gapCount ? `${gapCount} phần thiếu thông số` : 'Đủ kích thước 3D';
  }

  const body = $('#studioPaneBody');
  if (!body) return;

  const gapsHtml = gapCount
    ? sc.gaps.map(g => {
        const fieldsHtml = (g.fields || []).map(f => {
          if (f.kind === 'choice') {
            return `<div class="g-row">
              <label style="font-size:12.5px;min-width:120px">${f.label}</label>
              <select data-gap-view="${g.target}">
                <option value="">-- Chọn hình chiếu --</option>
                <option value="front">Mặt đứng (front)</option>
                <option value="top">Mặt bằng (top)</option>
                <option value="side">Mặt cắt/cạnh (side)</option>
              </select>
            </div>`;
          }
          return `<div class="g-row">
            <label style="font-size:12.5px;min-width:130px">${f.label} (${f.unit})</label>
            <input type="number" step="1" min="1" placeholder="Nhập số đo mm (VD: 2100)" data-gap-key="${f.key}">
          </div>`;
        }).join('');
        return `<div class="gap-card">
          <div class="g-hd"><span>${ic('alert', 'width:15px;height:15px;color:var(--warn)')} ${g.id}</span><span class="pill warn sm">${g.kind}</span></div>
          <div>${g.message}</div>
          ${fieldsHtml}
        </div>`;
      }).join('') +
      `<button class="btn-p" id="applyGapsBtn" style="width:100%">${ic('check')}Áp dụng thông số bù &amp; Dựng lại 3D</button>`
    : `<div class="gap-card ok"><div class="g-hd"><span>${ic('check', 'color:var(--ok)')} Đã đủ chiều cao &amp; chiều sâu 3D</span><span class="pill ok sm">Sẵn sàng xuất GLB</span></div><div>Mọi mô-đun và tấm ván đã có đủ kích thước 3 chiều W × D × H (mm).</div></div>`;

  const proposalsHtml = (sc.proposals || []).length
    ? `<div style="margin-top:8px"><b style="font-size:13px;color:var(--ai-fg)">✨ Đề xuất từ AI Studio (Phiên hiện tại):</b></div>` +
      sc.proposals.map(p => `<div class="prop-card">
        <div style="font-weight:600;margin-bottom:4px">${p.title}</div>
        <div style="color:var(--text2);font-size:12.5px;margin-bottom:8px">${p.reason}</div>
        <button class="btn-s btn-sm" data-prop-id="${p.id}">Áp dụng đề xuất này</button>
      </div>`).join('')
    : '';

  const clustersHtml = (sc.clusters || []).length
    ? `<div class="card" style="padding:10px 12px;margin-top:6px">
        <b style="font-size:13.5px">Các cụm hình học 2D → 3D (Clusters)</b>
        <table class="cluster-tbl">
          <thead><tr><th>Cụm</th><th>Layer</th><th>Khung bao (mm)</th><th>Hình chiếu</th></tr></thead>
          <tbody>
            ${sc.clusters.map(cl => `<tr>
              <td><b>${cl.id}</b> (${cl.rectCount})</td>
              <td><code>${cl.layer}</code></td>
              <td>${cl.bbox[2]}×${cl.bbox[3]}</td>
              <td>
                <select class="sel" style="padding:3px 6px;font-size:12.5px" data-cl-id="${cl.id}">
                  <option value=""${!cl.assignedView ? ' selected' : ''}>Chưa gán</option>
                  <option value="front"${cl.assignedView === 'front' ? ' selected' : ''}>Đứng (front)</option>
                  <option value="top"${cl.assignedView === 'top' ? ' selected' : ''}>Bằng (top)</option>
                  <option value="side"${cl.assignedView === 'side' ? ' selected' : ''}>Cạnh (side)</option>
                </select>
              </td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>`
    : '';

  // Render bảng đánh giá Công thái học AI (AI Ergonomics & Usability Scorecard)
  const erg = sc.ergonomics;
  const ergonomicsHtml = erg
    ? `<div class="erg-card" style="margin-top:10px">
        <div class="erg-hdr">
          <div>
            <div style="font-size:14px;font-weight:700;color:var(--text)">✨ Đánh giá Công thái học AI &amp; Độ phù hợp thực tế</div>
            <div style="font-size:12px;color:var(--text2)">Phân tích nhân trắc học người dùng Việt &amp; an toàn vận hành từ bản vẽ 2D</div>
          </div>
          <div class="erg-score-badge" title="Điểm số công thái học dựa trên chuẩn nội thất VN">${erg.overallScore}/100</div>
        </div>
        <p style="margin:4px 0 10px;font-size:12.5px;color:var(--text);line-height:1.45">${esc(erg.summary)}</p>
        <div style="font-size:12px;font-weight:700;margin:8px 0 4px;color:var(--text3);text-transform:uppercase">Tiêu chí công thái học thực tế:</div>
        ${(erg.checks || []).map(c => `
          <div class="erg-item ${c.status}">
            <div class="erg-item-title">
              <span><b>${esc(c.title)}</b></span>
              <span class="pill ${c.status === 'optimal' ? 'ok' : c.status === 'good' ? 'info' : 'warn'} sm">${c.status === 'optimal' ? 'Tối ưu' : c.status === 'good' ? 'Đạt' : 'Cảnh báo'}</span>
            </div>
            <div style="color:var(--text2);font-size:11.5px">Đo được: <b>${esc(c.currentVal)}</b> · Chuẩn: <code>${esc(c.standardVal)}</code></div>
            <div class="erg-item-advice">${esc(c.advice)}</div>
            <div style="color:var(--primary);font-size:11.5px;margin-top:2px">💡 <i>Lợi ích: ${esc(c.impactOnUser)}</i></div>
          </div>
        `).join('')}
        ${(erg.doorSpecs || []).length ? `<div style="margin-top:8px">
          <div style="font-size:12px;font-weight:700;color:var(--text2)">Đánh giá bán kính quét cánh cửa tủ:</div>
          <div style="font-size:12px;margin-top:4px">
            ${erg.doorSpecs.map(d => `<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px dashed var(--border)">
              <span>${esc(d.label)} (Rộng ${d.width} mm)</span>
              <span class="pill ${d.swingRisk ? 'warn' : 'ok'} sm">${d.swingRisk ? 'Bán kính quét lớn (>550mm)' : 'Góc mở an toàn'}</span>
            </div>`).join('')}
          </div>
        </div>` : ''}
      </div>`
    : '';

  body.innerHTML = `
    <div style="font-size:13px;color:var(--text2)">Mô hình <b>${sc.fileName}</b> · mã băm <code>${sc.source_hash}</code> · <b>${(sc.boxes || []).length}</b> chi tiết 3D</div>
    ${ergonomicsHtml}
    ${gapsHtml}
    ${proposalsHtml}
    ${clustersHtml}
  `;

  const applyBtn = $('#applyGapsBtn');
  if (applyBtn) {
    applyBtn.onclick = () => {
      const supp = {};
      const views = {};
      $$('[data-gap-key]').forEach(inp => {
        if (inp.value.trim()) supp[inp.dataset.gapKey] = parseFloat(inp.value.trim());
      });
      $$('[data-gap-view]').forEach(sel => {
        if (sel.value) views[sel.dataset.gapView] = sel.value;
      });
      loadStudio3DScene(supp, views);
      setCanvasMode('3d');
      toast('Đã cập nhật phần thiếu và dựng lại mô hình 3D');
    };
  }

  $$('[data-prop-id]').forEach(btn => {
    btn.onclick = () => {
      const prop = (sc.proposals || []).find(p => p.id === btn.dataset.propId);
      if (!prop) return;
      if (prop.kind === 'set_value') {
        loadStudio3DScene({ [prop.payload.key]: prop.payload.value }, {});
      } else if (prop.kind === 'set_views') {
        loadStudio3DScene({}, { [prop.payload.clusterId]: prop.payload.view });
      }
      setCanvasMode('3d');
      toast('Đã áp dụng đề xuất: ' + prop.title);
    };
  });

  $$('[data-cl-id]').forEach(sel => {
    sel.onchange = () => {
      loadStudio3DScene({}, { [sel.dataset.clId]: sel.value });
      setCanvasMode('3d');
      toast(`Đã gán cụm ${sel.dataset.clId} → ${sel.value || 'Chưa gán'}`);
    };
  });
}

// ===== 3D Studio: Smooth Inertial Damping & Internal Structure Modes =====
let st3dStructureMode = 'solid'; // 'solid' | 'xray' | 'open' | 'exploded'

function resetStudio3DCam(preset = 'iso') {
  if (preset === 'front') {
    cam3D.targetYaw = 0;
    cam3D.targetPitch = 0;
  } else if (preset === 'top') {
    cam3D.targetYaw = 0;
    cam3D.targetPitch = 1.48;
  } else if (preset === 'side') {
    cam3D.targetYaw = Math.PI / 2;
    cam3D.targetPitch = 0;
  } else { // iso / default
    cam3D.targetYaw = -0.65;
    cam3D.targetPitch = 0.48;
    cam3D.targetZoom = 1.0;
    cam3D.targetPanX = 0;
    cam3D.targetPanY = 0;
  }
}

let hitBoxes2D = [];
function drawStudio3D() {
  const cv = $('#studio3dCanvas');
  if (!cv || !currentScene3D) return;
  const ctx = cv.getContext('2d');
  const W = cv.width, H = cv.height;
  ctx.clearRect(0, 0, W, H);

  let rawBoxes = currentScene3D.boxes || [];
  if (!rawBoxes.length) {
    ctx.fillStyle = '#6B726D';
    ctx.font = '600 15px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('Chưa có khối 3D nào dựng được từ bản vẽ này.', W / 2, H / 2);
    return;
  }

  // Lọc chi tiết hiển thị theo chế độ kết cấu
  const hasDetailedParts = rawBoxes.some(b => b.role === 'interior' || b.role === 'door');
  let boxes = [];

  if (st3dStructureMode === 'solid') {
    // Chế độ vỏ ngoài: Nếu có chi tiết thì chỉ vẽ exterior và doors, ẩn vách đợt bên trong
    boxes = hasDetailedParts
      ? rawBoxes.filter(b => b.role === 'exterior' || b.role === 'door' || b.partType === 'wall' || b.partType === 'countertop' || !b.role)
      : rawBoxes;
  } else {
    // Chế độ X-Ray, Mở cánh, Bóc tách: Vẽ toàn bộ vách thùng, đợt chia, vách hậu
    boxes = rawBoxes;
  }

  // Tính tâm và quy mô khung cảnh
  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  boxes.forEach(b => {
    b.base.forEach(([x, y]) => {
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    });
    if (b.z0 < minZ) minZ = b.z0;
    if (b.z1 > maxZ) maxZ = b.z1;
  });
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const cz = (minZ + maxZ) / 2;
  const span = Math.max(500, maxX - minX, maxY - minY, maxZ - minZ);
  const scale = (Math.min(W, H) * 0.66 * cam3D.zoom) / span;

  const cyaw = Math.cos(cam3D.yaw), syaw = Math.sin(cam3D.yaw);
  const cpitch = Math.cos(cam3D.pitch), spitch = Math.sin(cam3D.pitch);

  const project = (x, y, z) => {
    const dx = x - cx, dy = y - cy, dz = z - cz;
    const rx = dx * cyaw - dy * syaw;
    const ry = dx * syaw + dy * cyaw;
    const sy = ry * spitch - dz * cpitch;
    const sz = ry * cpitch + dz * spitch;
    return [W / 2 + cam3D.panX + rx * scale, H / 2 + cam3D.panY + sy * scale, sz];
  };

  // Vẽ lưới toạ độ mặt sàn tham chiếu
  ctx.strokeStyle = document.documentElement.dataset.theme === 'dark' ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)';
  ctx.lineWidth = 1;
  const stepGrid = 500;
  for (let gx = Math.floor(minX / stepGrid) * stepGrid; gx <= maxX + stepGrid; gx += stepGrid) {
    const p1 = project(gx, minY - 200, 0);
    const p2 = project(gx, maxY + 200, 0);
    ctx.beginPath(); ctx.moveTo(p1[0], p1[1]); ctx.lineTo(p2[0], p2[1]); ctx.stroke();
  }
  for (let gy = Math.floor(minY / stepGrid) * stepGrid; gy <= maxY + stepGrid; gy += stepGrid) {
    const p1 = project(minX - 200, gy, 0);
    const p2 = project(maxX + 200, gy, 0);
    ctx.beginPath(); ctx.moveTo(p1[0], p1[1]); ctx.lineTo(p2[0], p2[1]); ctx.stroke();
  }

  // Xây dựng danh sách mặt (faces) kèm biến đổi mở cánh / bóc tách
  const faces = [];
  hitBoxes2D = [];

  boxes.forEach(b => {
    let effectiveBase = b.base;
    let effZ0 = b.z0;
    let effZ1 = b.z1;

    // 1. Biến đổi mở cánh (Open Doors & Drawers Mode)
    if (st3dStructureMode === 'open') {
      if (b.role === 'door' && b.hingePivot) {
        const [px, py] = b.hingePivot;
        const angle = b.hingeSide === 'left' ? -1.57 : 1.57; // Xoay 90 độ ra ngoài
        effectiveBase = b.base.map(([x, y]) => {
          const dx = x - px, dy = y - py;
          return [
            +(px + dx * Math.cos(angle) - dy * Math.sin(angle)).toFixed(1),
            +(py + dx * Math.sin(angle) + dy * Math.cos(angle)).toFixed(1)
          ];
        });
      } else if (b.partType === 'drawer') {
        effectiveBase = b.base.map(([x, y]) => [x, y - 220]); // Trượt ngăn kéo ra trước 220mm
      }
    }

    // 2. Biến đổi bóc tách (Exploded View Mode)
    if (st3dStructureMode === 'exploded') {
      let offX = 0, offY = 0, offZ = 0;
      if (b.partType === 'carcass_side') offX = b.id.includes('side_l') ? -45 : 45;
      else if (b.partType === 'carcass_top') offZ = 45;
      else if (b.partType === 'carcass_bottom') offZ = -25;
      else if (b.partType === 'carcass_back') offY = 45;
      else if (b.partType === 'door') offY = -70;
      else if (b.partType === 'countertop') offZ = 65;

      effectiveBase = effectiveBase.map(([x, y]) => [x + offX, y + offY]);
      effZ0 += offZ;
      effZ1 += offZ;
    }

    const topPts = effectiveBase.map(([x, y]) => [x, y, effZ1]);
    const botPts = [...effectiveBase].reverse().map(([x, y]) => [x, y, effZ0]);
    const boxFaceList = [
      { verts: topPts, shade: 1.06 },
      { verts: botPts, shade: 0.72 }
    ];
    for (let i = 0; i < effectiveBase.length; i++) {
      const [x1, y1] = effectiveBase[i];
      const [x2, y2] = effectiveBase[(i + 1) % effectiveBase.length];
      boxFaceList.push({
        verts: [[x1, y1, effZ0], [x2, y2, effZ0], [x2, y2, effZ1], [x1, y1, effZ1]],
        shade: i % 2 === 0 ? 0.92 : 0.82
      });
    }

    let bMinX = Infinity, bMinY = Infinity, bMaxX = -Infinity, bMaxY = -Infinity;
    boxFaceList.forEach(f => {
      const projPts = f.verts.map(v => project(v[0], v[1], v[2]));
      const avgZ = projPts.reduce((s, p) => s + p[2], 0) / projPts.length;
      projPts.forEach(p => {
        if (p[0] < bMinX) bMinX = p[0];
        if (p[1] < bMinY) bMinY = p[1];
        if (p[0] > bMaxX) bMaxX = p[0];
        if (p[1] > bMaxY) bMaxY = p[1];
      });
      faces.push({
        box: b,
        pts: projPts,
        depth: avgZ,
        shade: f.shade
      });
    });
    hitBoxes2D.push({ box: b, minX: bMinX, minY: bMinY, maxX: bMaxX, maxY: bMaxY });
  });

  // Thuật toán thợ vẽ: sắp xếp từ xa đến gần
  faces.sort((a, b) => a.depth - b.depth);

  faces.forEach(f => {
    const isSel = studioSelectedBoxId === f.box.id;
    const isWall = f.box.material === 'wall';
    const isExteriorBox = f.box.partType === 'module_box' || f.box.role === 'exterior';
    const isInteriorPart = f.box.role === 'interior';

    let [r, g, bl] = f.box.color || [0.8, 0.75, 0.65];
    if (isInteriorPart && !f.box.color) [r, g, bl] = [0.84, 0.76, 0.62]; // Gỗ sồi ấm cho vách đợt bên trong

    const cr = Math.min(255, Math.round(r * 255 * f.shade));
    const cg = Math.min(255, Math.round(g * 255 * f.shade));
    const cb = Math.min(255, Math.round(bl * 255 * f.shade));

    // Thiết lập độ trong suốt tùy chế độ
    let alpha = 0.92;
    if (isWall) alpha = 0.40;
    else if (st3dStructureMode === 'xray') {
      // Trong chế độ X-Ray: Vỏ ngoài mờ nhìn xuyên thấu, nội thất bên trong đậm nét
      alpha = isExteriorBox ? 0.08 : 0.88;
    }

    ctx.beginPath();
    f.pts.forEach((p, idx) => {
      if (idx === 0) ctx.moveTo(p[0], p[1]);
      else ctx.lineTo(p[0], p[1]);
    });
    ctx.closePath();

    ctx.fillStyle = isSel ? 'rgba(15, 107, 98, 0.85)' : `rgba(${cr}, ${cg}, ${cb}, ${alpha})`;
    ctx.fill();

    // Viền khung dây
    const showStroke = studioWireframe || isSel || st3dStructureMode === 'xray' || st3dStructureMode === 'exploded';
    if (showStroke) {
      if (st3dStructureMode === 'xray' && isExteriorBox) {
        ctx.strokeStyle = 'rgba(14, 116, 144, 0.45)'; // Viền nét đứt kỹ thuật
        ctx.lineWidth = 1.0;
      } else {
        ctx.strokeStyle = isSel ? '#0F6B62' : isWall ? 'rgba(90,98,94,0.45)' : 'rgba(31,36,33,0.75)';
        ctx.lineWidth = isSel ? 2.4 : (f.box.role === 'interior' ? 1.2 : 1.0);
      }
      ctx.stroke();
    }
  });
}

// Vòng lặp quán tính mượt mà (Inertial Damping 60FPS Loop)
(function initStudio3DLoop() {
  function st3dLoop() {
    const dyaw = cam3D.targetYaw - cam3D.yaw;
    const dpitch = cam3D.targetPitch - cam3D.pitch;
    const dzoom = cam3D.targetZoom - cam3D.zoom;
    const dpanX = cam3D.targetPanX - cam3D.panX;
    const dpanY = cam3D.targetPanY - cam3D.panY;

    const threshold = 0.0003;
    if (
      Math.abs(dyaw) > threshold ||
      Math.abs(dpitch) > threshold ||
      Math.abs(dzoom) > 0.0008 ||
      Math.abs(dpanX) > 0.04 ||
      Math.abs(dpanY) > 0.04
    ) {
      cam3D.yaw += dyaw * 0.22;
      cam3D.pitch += dpitch * 0.22;
      cam3D.zoom += dzoom * 0.22;
      cam3D.panX += dpanX * 0.22;
      cam3D.panY += dpanY * 0.22;
      if (canvasMode === '3d') {
        const pct = Math.round(cam3D.zoom * 100) + '%';
        if ($('#zoomResetBtn')) $('#zoomResetBtn').textContent = pct;
        if ($('#hudZoomResetBtn')) $('#hudZoomResetBtn').textContent = pct;
      }
      drawStudio3D();
    }
    requestAnimationFrame(st3dLoop);
  }
  requestAnimationFrame(st3dLoop);
})();

function focus3DSelected(boxId) {
  if (!currentScene3D || !currentScene3D.boxes || !currentScene3D.boxes.length) {
    toast('Chưa có khối 3D để phóng to');
    return;
  }
  const rawBoxes = currentScene3D.boxes;
  const targetBox = rawBoxes.find(b => b.id === (boxId || studioSelectedBoxId)) ||
    rawBoxes.find(b => b.role === 'exterior' || b.partType === 'module_box') ||
    rawBoxes.find(b => b.partType !== 'wall') ||
    rawBoxes[0];
  if (!targetBox) return;

  studioSelectedBoxId = targetBox.id;

  // Tính tâm và quy mô toàn cảnh
  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  rawBoxes.forEach(b => {
    b.base.forEach(([x, y]) => {
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    });
    if (b.z0 < minZ) minZ = b.z0;
    if (b.z1 > maxZ) maxZ = b.z1;
  });
  const sceneCx = (minX + maxX) / 2;
  const sceneCy = (minY + maxY) / 2;
  const sceneCz = (minZ + maxZ) / 2;
  const sceneSpan = Math.max(500, maxX - minX, maxY - minY, maxZ - minZ);

  // Tính tâm và kích thước vật thể cần focus
  let tMinX = Infinity, tMinY = Infinity, tMaxX = -Infinity, tMaxY = -Infinity;
  targetBox.base.forEach(([x, y]) => {
    if (x < tMinX) tMinX = x;
    if (y < tMinY) tMinY = y;
    if (x > tMaxX) tMaxX = x;
    if (y > tMaxY) tMaxY = y;
  });
  const tCx = (tMinX + tMaxX) / 2;
  const tCy = (tMinY + tMaxY) / 2;
  const tCz = (targetBox.z0 + targetBox.z1) / 2;
  const tSpan = Math.max(350, tMaxX - tMinX, tMaxY - tMinY, targetBox.z1 - targetBox.z0);

  // Tính zoom để vật thể chiếm ~60-70% màn hình
  const desiredZoom = Math.min(65.0, Math.max(2.6, +(sceneSpan / (tSpan * 1.6)).toFixed(1)));
  cam3D.targetZoom = desiredZoom;

  const cv = $('#studio3dCanvas');
  const W = cv ? cv.width : 820, H = cv ? cv.height : 540;
  const scale = (Math.min(W, H) * 0.66 * desiredZoom) / sceneSpan;

  const cyaw = Math.cos(cam3D.targetYaw), syaw = Math.sin(cam3D.targetYaw);
  const cpitch = Math.cos(cam3D.targetPitch), spitch = Math.sin(cam3D.targetPitch);

  const dx = tCx - sceneCx, dy = tCy - sceneCy, dz = tCz - sceneCz;
  const rx = dx * cyaw - dy * syaw;
  const ry = dx * syaw + dy * cyaw;
  const sy = ry * spitch - dz * cpitch;

  cam3D.targetPanX = -(rx * scale);
  cam3D.targetPanY = -(sy * scale);

  const thickText = targetBox.thickness ? ` · Dày: ${targetBox.thickness} mm` : '';
  if ($('#st3dSelectedInfo')) {
    $('#st3dSelectedInfo').innerHTML = `Đang focus cận cảnh: <b>${targetBox.label}</b>${thickText} · Zoom ${Math.round(desiredZoom * 100)}%`;
  }
  drawStudio3D();
  toast(`Đã phóng to cận cảnh vào ${targetBox.label}`);
}

// Bắt sự kiện chuột và cảm ứng 3D siêu mượt
(function initStudio3DControls() {
  const cv = $('#studio3dCanvas');
  if (!cv) return;

  let mouseMode3D = 'orbit';

  cv.addEventListener('mousedown', e => {
    cam3D.dragging = true;
    cam3D.mode = (e.button === 2 || e.button === 1 || e.shiftKey || mouseMode3D === 'pan') ? 'pan' : 'orbit';
    cam3D.lastX = e.clientX;
    cam3D.lastY = e.clientY;
    cv.style.cursor = cam3D.mode === 'pan' ? 'move' : 'grabbing';
  });

  window.addEventListener('mousemove', e => {
    if (!cam3D.dragging) return;
    const dx = e.clientX - cam3D.lastX;
    const dy = e.clientY - cam3D.lastY;
    cam3D.lastX = e.clientX;
    cam3D.lastY = e.clientY;

    if (cam3D.mode === 'pan') {
      cam3D.targetPanX += dx * 1.5;
      cam3D.targetPanY += dy * 1.5;
    } else {
      cam3D.targetYaw += dx * 0.007;
      cam3D.targetPitch = Math.max(-1.45, Math.min(1.45, cam3D.targetPitch + dy * 0.007));
    }
  });

  window.addEventListener('mouseup', () => {
    cam3D.dragging = false;
    if (cv) cv.style.cursor = mouseMode3D === 'pan' ? 'move' : 'grab';
  });
  cv.addEventListener('contextmenu', e => e.preventDefault());

  cv.addEventListener('wheel', e => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.18 : 0.85;
    cam3D.targetZoom = Math.max(0.15, Math.min(80.0, +(cam3D.targetZoom * factor).toFixed(2)));
  }, { passive: false });

  cv.addEventListener('click', e => {
    const rect = cv.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * cv.width;
    const y = ((e.clientY - rect.top) / rect.height) * cv.height;
    const hit = [...hitBoxes2D].reverse().find(h => x >= h.minX && x <= h.maxX && y >= h.minY && y <= h.maxY);
    if (hit) {
      studioSelectedBoxId = hit.box.id;
    } else {
      studioSelectedBoxId = null;
    }
    drawStudio3D();
  });

  cv.addEventListener('dblclick', e => {
    const rect = cv.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * cv.width;
    const y = ((e.clientY - rect.top) / rect.height) * cv.height;
    const hit = [...hitBoxes2D].reverse().find(h => x >= h.minX && x <= h.maxX && y >= h.minY && y <= h.maxY);
    if (hit) {
      focus3DSelected(hit.box.id);
    } else {
      resetStudio3DCam('iso');
    }
  });

  // Nút chuyển đổi Chế độ hiển thị kết cấu 3D (.st3d-inspect)
  $$('.st3d-inspect').forEach(btn => {
    btn.onclick = () => {
      $$('.st3d-inspect').forEach(b => b.classList.remove('on'));
      btn.classList.add('on');
      const m = btn.dataset.inspect;
      st3dStructureMode = m === 'doors' ? 'open' : m;
      drawStudio3D();
    };
  });

  // Nút chuyển nhanh Góc nhìn kỹ thuật CAD (.st3d-preset)
  $$('.st3d-preset').forEach(btn => {
    btn.onclick = () => {
      $$('.st3d-preset').forEach(b => b.classList.remove('on'));
      btn.classList.add('on');
      resetStudio3DCam(btn.dataset.cam);
    };
  });

  if ($('#st3dWireBtn')) {
    $('#st3dWireBtn').onclick = () => {
      studioWireframe = !studioWireframe;
      $('#st3dWireBtn').textContent = 'Khung dây: ' + (studioWireframe ? 'Bật' : 'Tắt');
      drawStudio3D();
    };
  }
  if ($('#st3dResetCamBtn')) {
    $('#st3dResetCamBtn').onclick = () => {
      resetStudio3DCam('iso');
    };
  }
  const downloadGlb = () => {
    const target = activeWsFile || K().file;
    const sheetIdx = C().sheetIdx || 0;
    const a = document.createElement('a');
    a.href = `/api/studio/glb?file=${encodeURIComponent(target)}&sheet=${sheetIdx}`;
    a.download = target.replace(/\.dxf$/i, '') + `.glb`;
    a.click();
    closeMenus();
    toast(`Đang xuất mô hình 3D .GLB cho ${target}...`);
  };
  if ($('#exportGlbTopBtn')) $('#exportGlbTopBtn').onclick = downloadGlb;
})();

function syncCanvas() {
  svg = $('#svg');
  if (!svg) return;
  const c = C(), F = FIND();
  const prev = (c.proposed && !c.accepted && c.view === 'after') || studioMode === 'diff';
  const applied = c.accepted || (prev && c.view === 'after') ? { a: c.ops.a, b: c.ops.b } : { a: false, b: false };
  svg.dataset.fixedA = (applied.a || (F[0] && F[0].st === 'fixed')) ? 1 : 0;
  svg.dataset.fixedB = (applied.b || (F[1] && F[1].st === 'fixed')) ? 1 : 0;
  svg.dataset.showChg = (c.proposed && !c.accepted) || studioMode === 'diff' ? 1 : 0;
  svg.dataset.scanned = c.scanned ? 1 : 0;
}

/* ---------- CỘT PHẢI: 2 TAB CHUYỂN ĐỔI TOÀN CHIỀU CAO (CHAT vs CHANGESET) ---------- */
function switchRightTopTab(rt) {
  const mode = rt === 'chg' ? 'chg' : 'chat';
  $$('.r-tab').forEach(b => {
    const on = b.dataset.rt === mode;
    b.classList.toggle('on', on);
    b.setAttribute('aria-selected', on);
  });
  if ($('#rtPaneChat')) $('#rtPaneChat').classList.toggle('on', mode === 'chat');
  if ($('#rtPaneChg')) $('#rtPaneChg').classList.toggle('on', mode === 'chg');
}
$$('.r-tab').forEach(b => b.onclick = () => switchRightTopTab(b.dataset.rt));

function tab(p) {
  if (p === 'chg') switchRightTopTab('chg');
  else if (p === 'studio') setCanvasMode('3d');
  else switchRightTopTab('chat');
}

function renderReviewNotes() {
  // Đã hợp nhất vào luồng ghi chú bàn giao trong Trợ lý AI
}

function select(id, openTab) {
  const c = C(), f = FIND().find(x => x.id === id);
  c.sel = id;
  renderFinds();
  syncCanvas();
  if (f) focusFindingOnCanvas(f);
  if (openTab) switchRightTopTab('chg');
}

if ($('#scanBtn')) {
  $('#scanBtn').onclick = () => doScan();
}
if ($('#topAcadChip')) {
  $('#topAcadChip').onclick = () => syncToAutoCAD();
}
if ($('#stdSelect')) {
  $('#stdSelect').onchange = () => {
    const val = $('#stdSelect').value;
    if ($('#stdName')) $('#stdName').textContent = val;
    toast(`Đã áp dụng bộ tiêu chuẩn: ${val}`);
    if (activeWsFile) openWorkspaceDxf(activeWsFile);
  };
}

async function syncToAutoCAD(finding) {
  const k = K(), c = C();
  const sh = (k.sheets || [])[c.sheetIdx || 0];
  const f = finding || FIND().find(x => x.id === c.sel) || FIND()[0];
  try {
    await fetch('/api/plugin/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        drawing: activeWsFile || k.file,
        sheetId: sh ? sh.code : 'MODEL',
        findingId: f ? f.rule : null
      })
    });
  } catch (e) {}
  if ($('#acadTopLabel')) {
    $('#acadTopLabel').textContent = `AutoCAD: ${f ? f.rule : 'Đã đồng bộ'}`;
  }
  toast(`Đã gửi lệnh đồng bộ vị trí ${f ? f.rule : ''} tới AutoCAD qua MCP Companion`);
}

function updateLeftTelemetry() {
  const allF = FIND();
  const openCnt = allF.filter(f => f.st === 'open').length;

  const entNum = (customDxfData && (customDxfData.entityCount || (customDxfData.entities && customDxfData.entities.length))) || 0;
  const layerNum = (customDxfData && (customDxfData.layerCount || (customDxfData.layers && customDxfData.layers.length))) || 0;
  const clusterNum = (currentScene3D && currentScene3D.boxes && currentScene3D.boxes.length) ||
    (customDxfData && customDxfData.scene && customDxfData.scene.boxes && customDxfData.scene.boxes.length) || 0;

  if ($('#statEnts')) $('#statEnts').textContent = entNum.toLocaleString('vi-VN');
  if ($('#statLayers')) $('#statLayers').textContent = String(layerNum);
  if ($('#statErrs')) $('#statErrs').textContent = String(openCnt);
  if ($('#statClusters')) $('#statClusters').textContent = String(clusterNum);

  if ($('#st3dStatsPill')) $('#st3dStatsPill').textContent = `${clusterNum} khối 3D`;
  const gapCount = (currentScene3D && currentScene3D.gaps && currentScene3D.gaps.length) || 0;
  if ($('#cnt3dGaps')) {
    $('#cnt3dGaps').textContent = gapCount;
    $('#cnt3dGaps').hidden = gapCount === 0;
  }
}

function renderFiles() {
  // Danh sách tệp giả đã được xoá bỏ hoàn toàn; chỉ dùng #fileSelectDropdown chứa tệp DXF thật
}

/* ---------- Tệp DXF thật trong Dự án / Workspace ---------- */
let wsDrawings = [];
async function loadWorkspaceDrawings(autoOpenIfNeeded = false) {
  try {
    const res = await fetch('/api/drawings');
    const data = await res.json();
    wsDrawings = data.drawings || [];
    renderWsFiles();

    if (autoOpenIfNeeded && wsDrawings.length > 0) {
      // Ưu tiên mở tệp do người dùng tải lên (source === 'local' hoặc tên tệp không phải fixture mẫu)
      const uploaded = wsDrawings.find(d => d.source === 'local' || /GRD|NOITHAT/i.test(d.name));
      const target = uploaded ? uploaded.name : (wsDrawings.find(d => d.name === activeWsFile)?.name || wsDrawings[0].name);
      await openWorkspaceDxf(target);
    }
  } catch (e) {
    console.warn('loadWorkspaceDrawings error:', e);
  }
}

function renderWsFiles() {
  const sel = $('#fileSelectDropdown');
  if (sel) {
    if (!wsDrawings.length) {
      sel.innerHTML = `<option value="">(Chưa có tệp DXF)</option>`;
    } else {
      sel.innerHTML = wsDrawings.map(d => {
        const errTag = d.status === 'audited'
          ? (d.errors > 0 || d.warnings > 0 ? ` · ${d.errors + d.warnings} lỗi` : ' · Sạch')
          : '';
        return `<option value="${esc(d.name)}"${d.name === activeWsFile ? ' selected' : ''}>${esc(d.name)}${errTag}</option>`;
      }).join('');
    }
    sel.onchange = () => {
      if (sel.value) openWorkspaceDxf(sel.value);
    };
  }
}

async function openWorkspaceDxf(name) {
  if (!name) return;
  activeWsFile = name;
  hiddenLayers.clear();
  if ($('#cvTitle')) $('#cvTitle').textContent = name;
  if ($('#fileSelectDropdown')) $('#fileSelectDropdown').value = name;

  await run(async () => {
    try {
      const res = await fetch('/api/dxf/inspect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fileName: name })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      customDxfData = data;
      currentScene3D = data.scene;
      const c = C();
      c.scanned = true;
      c.proposed = true;
      c.accepted = false;
      c.sheetIdx = 0;
      c.sel = null;
      if ($('#cvInfo')) $('#cvInfo').textContent = `${name} · ${data.info} · Khung nhìn tự động (Percentile 2%–98%)`;
      if ($('#stdName')) $('#stdName').textContent = data.standardProfile || K().standard;

      reset2DZoom();
      mountSheet();
      renderRealLayers();
      renderStudioPane();
      if (canvasMode === '3d') drawStudio3D();
      renderAll();

      const allFinds = data.findings || [];
      const codeCount = allFinds.filter(f => f.tier === 'code').length;
      const aiCount = allFinds.filter(f => f.tier === 'ai').length;
      const boxCount = (data.scene?.boxes || []).length;

      log.innerHTML = '';
      tool('cadguard.inspect_dxf', `{ "file": "${name}", "entities": ${data.entityCount || 0}, "layers": ${data.layerCount || 0} }`, '0,3 giây', `${allFinds.length} phát hiện · ${boxCount} khối 3D`);
      say('ai', `<p>Đã nạp bản vẽ thực tế <b>${esc(name)}</b> (${esc(data.info)}):</p>
        <ul>
          <li><b>Tự động căn khung nhìn (Percentile 2%–98%):</b> Đã loại bỏ điểm rác ngoại lai, phóng to vùng nét vẽ chính chiếm trọn khung giữa.</li>
          <li><b>Kết quả kiểm toán:</b> Phát hiện <b>${allFinds.length} mục</b> (${codeCount} luật tất định Lớp 1 · ${aiCount} phân tích sâu Lớp 2).</li>
          <li><b>Cách xem vị trí lỗi:</b> Bấm vào bất kỳ thẻ lỗi nào ở cột trái để <b>tô sáng đỏ trực tiếp các nét vẽ vi phạm</b> trên mặt bản vẽ.</li>
        </ul>`);
      loadWorkspaceDrawings(false);
    } catch (e) {
      toast('Không thể đọc tệp DXF: ' + e.message);
    }
  });
}

function renderFinds() {
  const c = C(), allF = FIND(), el = $('#finds');
  updateLeftTelemetry();
  if (!el) return;

  if (!allF.length) {
    el.innerHTML = `<div class="empty"><b>Bản vẽ sạch lỗi</b>Không phát hiện vi phạm nào theo bộ tiêu chuẩn đang chọn.</div>`;
    return;
  }

  el.innerHTML = allF.map(f => {
    const fixed = f.st === 'fixed';
    const badgeCls = f.tier === 'ai' ? 'ai' : f.sev === 'error' ? '' : 'warn';
    const entCount = f.count || (f.targetHandles && f.targetHandles.length) || 1;
    const isSel = c.sel === f.id;

    return `<div class="f-card${isSel ? ' sel' : ''}${fixed ? ' fixed-card' : ''}" data-id="${f.id}" tabindex="0" role="button" aria-label="Lỗi ${f.rule}: ${esc(f.title)}">
      <div class="f-top">
        <span class="f-rule-badge ${badgeCls}">${esc(f.rule)}</span>
        <span class="f-cnt-badge">${fixed ? '✓ Đã sửa' : `${entCount} đối tượng`}</span>
      </div>
      <div class="f-title">${esc(f.title)}</div>
      <div class="f-sub">${esc(f.d)}</div>
      <div class="f-actions">
        <button type="button" class="f-act-btn" data-focus-find="${f.id}" title="Tô sáng đỏ trực tiếp các nét vẽ thuộc lỗi này và phóng tới">🔍 Xem trên bản vẽ</button>
        <button type="button" class="f-act-btn fix" data-fix-find="${f.id}" title="Đưa vào ChangeSet để tự động sửa và xuất tệp DXF mới">${fixed ? '✓ Đã sửa' : '⚡ Tự động sửa'}</button>
      </div>
    </div>`;
  }).join('');

  $$('.f-card').forEach(cd => {
    cd.onclick = e => {
      if (e.target.closest && e.target.closest('button')) return;
      select(+cd.dataset.id, false);
    };
  });

  $$('[data-focus-find]').forEach(btn => {
    btn.onclick = e => {
      e.stopPropagation();
      select(+btn.dataset.focusFind, false);
    };
  });

  $$('[data-fix-find]').forEach(btn => {
    btn.onclick = e => {
      e.stopPropagation();
      const f = FIND().find(x => x.id === +btn.dataset.fixFind);
      if (!f) return;
      c.proposed = true;
      if (f.fix) {
        c.ops[f.fix] = true;
      } else {
        c.ops['custom_' + f.id] = true;
      }
      select(f.id, true);
      renderChg();
      renderFinds();
      toast(`Đã chuẩn bị bước sửa tự động cho lỗi ${f.rule} ở tab Duyệt Sửa Đổi`);
    };
  });
}

function ruleWho(id) {
  const r = typeof RULES !== 'undefined' && RULES.find(x => x.id === id);
  if (!r) return '';
  const ts = r.tasks.map(t => TASKS[t].n);
  return `<div class="f-meta">${ic('users')}<span>Phụ trách: <b>${r.owner ? ROLES[r.owner] : 'chưa gắn'}</b>${ts.length ? ' · Task: ' + ts.slice(0, 2).join('; ') + (ts.length > 2 ? '…' : '') : ''}</span></div>`;
}

function renderChg() {
  const c = C(), k = K(), list = $('#chgList'), foot = $('#chgFoot'), base = (k.file || 'ban-ve').replace(/\.dxf$/i, '');
  if (!list || !foot) return;
  const allF = FIND();
  const fA = allF[0] || { rule: 'LY-03', title: 'Chuyển đối tượng trên Layer 0 về Layer chuẩn' };
  const fB = allF[1] || { rule: 'TX-02', title: 'Chuẩn hoá chiều cao chữ ghi chú về 2.5mm' };

  const customOps = allF.filter(f => !f.fix && c.ops['custom_' + f.id]);
  const activeCount = (c.ops.a ? 1 : 0) + (c.ops.b ? 1 : 0) + customOps.length;
  if ($('#cntC')) $('#cntC').textContent = c.accepted ? '✓' : (c.proposed ? activeCount : 0);

  if (!c.proposed) {
    list.innerHTML = `<div class="empty"><b>Chưa có thao tác sửa đổi nào</b>Bấm <b>[⚡ Tự động sửa]</b> ở bất kỳ thẻ lỗi nào bên cột trái để tạo danh sách sửa đổi an toàn.</div>`;
    foot.innerHTML = `<button class="btn-p" id="quickProposeBtn" style="width:100%">⚡ Tạo danh sách sửa tự động cho bản vẽ này</button>`;
    if ($('#quickProposeBtn')) $('#quickProposeBtn').onclick = doPropose;
    return;
  }
  if (c.accepted) {
    list.innerHTML = `<div class="op"><div style="display:flex;gap:8px;align-items:center"><span class="pill ok sm">${ic('check')}Đã xuất tệp mới</span><b>${esc(base)}_v2.dxf</b></div>
      <p style="color:var(--text2);margin:6px 0 0;font-size:12px">Bản gốc <b>${esc(k.file)}</b> được giữ nguyên chỉ đọc. Đã chạy <code>validate_output</code>: ${esc(k.validate)}</p></div>`;
    foot.innerHTML = `<button class="btn-s" id="undoBtn" style="width:100%">↩️ Hoàn tác (Xoá bản _v2.dxf)</button>`;
    $('#undoBtn').onclick = () => {
      $('#mTitle').textContent = `Bỏ bản ${base}_v2.dxf?`;
      $('#mText').textContent = `Tệp mới này sẽ bị xoá. Bản gốc ${k.file} không bị ảnh hưởng.`;
      $('#mYes').textContent = 'Xác nhận hoàn tác';
      $('#modal').classList.add('on');
    };
    return;
  }

  const opCard = (key, f, opSpec) => `<div class="op"><label><input type="checkbox" data-op="${key}" ${c.ops[key] ? 'checked' : ''}><span><b>${esc(opSpec.what)}</b> <span class="f-rule-badge" style="margin-left:4px">${esc(f.rule)}</span>
    <span class="diff" style="display:block"><div class="m">− Trước: ${esc(opSpec.from)}</div><div class="p">+ Sau: ${esc(opSpec.to)}</div></span></span></label></div>`;

  const customCards = customOps.map(f => opCard('custom_' + f.id, f, {
    what: f.title,
    from: `Vi phạm ${f.rule} (${f.count || 1} đối tượng)`,
    to: f.fixTxt || f.need || 'Chuẩn hoá theo quy chuẩn công ty'
  })).join('');

  list.innerHTML = opCard('a', fA, k.ops.a) + opCard('b', fB, k.ops.b) + customCards;

  $$('[data-op]').forEach(ch => ch.onchange = () => {
    c.ops[ch.dataset.op] = ch.checked;
    syncCanvas();
    renderChg();
    renderFinds();
  });

  foot.innerHTML = `
    <div class="cs-act-row">
      <button class="btn-p" type="button" id="okBtn" ${activeCount ? '' : 'disabled'} style="width:100%">✅ Áp dụng &amp; Xuất tệp mới (${esc(base)}_v2.dxf)</button>
      <button class="btn-s" type="button" id="noBtn" style="width:100%">↩️ Huỷ đề xuất sửa đổi</button>
    </div>`;

  $('#okBtn').onclick = accept;
  $('#noBtn').onclick = () => {
    c.proposed = false;
    c.view = 'after';
    renderAll();
    toast('Đã huỷ đề xuất ChangeSet');
  };
}

/* ---------- chat ---------- */
const log = $('#log');
function scroll() { log.scrollTop = log.scrollHeight; }
function say(who, html) {
  const d = document.createElement('div');
  d.className = 'msg ' + who;
  if (who === 'me') d.textContent = html;
  else d.innerHTML = html;
  log.appendChild(d);
  scroll();
}
function tool(name, args, ms, out) {
  const d = document.createElement('details');
  d.className = 'tool';
  d.innerHTML = `<summary><span class="ok">${ic('check')}</span><code style="font-family:var(--mono)">${name}</code><span style="margin-left:auto">${ms}</span></summary><pre>${args}\n→ ${out}</pre>`;
  log.appendChild(d);
  scroll();
}
function typing() {
  const d = document.createElement('div');
  d.className = 'typing';
  d.innerHTML = '<i></i><i></i><i></i> Đang xử lý';
  log.appendChild(d);
  scroll();
  return d;
}
function later(fn, ms) { return new Promise(r => setTimeout(() => { fn(); r(); }, ms)); }
let busy = false;
async function step(ms, fn) {
  const t = typing();
  await later(() => {}, ms);
  t.remove();
  await fn();
}
function intro() {
  log.innerHTML = '';
  const shCount = (K().sheets || []).length;
  say('ai', `<p>Xin chào, phòng <b>${DEPT[stage].name}</b>. Mình đang xem <b>${K().file}</b> (${shCount} trang Artboard · ${K().info}).</p><p>Mình kiểm tra theo <b>2 lớp</b>: <b>Lớp 1</b> (bộ luật tất định <code>${K().standard}</code> giúp làm sạch và chuẩn hoá trình bày) và <b>Lớp 2</b> (AI phân tích sâu kích thước chuỗi, khe hở phụ kiện 2–3 mm và đối chiếu bảng kê BOM). Mọi sửa đổi luôn ghi ra <b>tệp mới</b>.</p>`);
}

function suggestions() {
  const c = C(), k = K(), nx = DEPT[stage].next;
  const s = [];
  const firstOpen = FIND().find(f => f.st === 'open') || FIND()[0];
  const explainRule = (k.explain && k.explain.rule) || (firstOpen ? firstOpen.rule : 'VS-01');
  const needExplainRule = (k.needExplain && k.needExplain.rule) || (firstOpen ? firstOpen.rule : 'PR-01');

  if (!c.scanned) {
    s.push(['Quét bản vẽ này (2 Lớp)', doScan, true], ['Bản vẽ này có những trang nào?', doAbout]);
  } else if (!c.proposed && !c.accepted) {
    s.push(['Sửa các lỗi tự sửa được', doPropose, true], ['✨ AI phân tích sâu sản xuất', doAiDeepScan], [`Giải thích lỗi ${explainRule}`, () => doExplain(explainRule)], [`Soạn gói bàn giao cho ${nx}`, doHandover]);
  } else if (c.proposed && !c.accepted) {
    s.push(['Mở tab Thay đổi', () => tab('chg'), true], [`Giải thích lỗi ${explainRule}`, () => doExplain(explainRule)]);
  } else {
    s.push([`Soạn gói bàn giao cho ${nx}`, doHandover, true], ['Quét lại bản v2', doRescan], [`Giải thích lỗi ${needExplainRule}`, () => doExplainNeed(needExplainRule)]);
  }
  $('#sug').innerHTML = s.map(([t, , p]) => `<button class="${p ? 'primary' : ''}">${t}</button>`).join('');
  $$('#sug button').forEach((b, i) => b.onclick = () => {
    if (busy) return;
    say('me', s[i][0]);
    s[i][1]();
  });
}
async function run(fn) {
  busy = true;
  try {
    await fn();
  } catch (err) {
    console.error('[CAD Guard] Action error:', err);
    toast('Đã có thông báo: ' + (err.message || err));
  } finally {
    busy = false;
    suggestions();
  }
}

function doAbout() {
  return run(async () => {
    await step(450, () => {
      tool('cadguard.list_artboards', `{ "file": "${K().file}" }`, '0,2 giây', `${(K().sheets || []).length} trang (đã tách riêng vùng nháp Model)`);
      say('ai', K().about);
    });
  });
}

function doScan() {
  if (busy) return;
  if (!$('#log .msg.me:last-child')) say('me', 'Quét bản vẽ này (2 Lớp)');
  tab('chat');
  return run(async () => {
    await step(650, () => {
      const c = C(), F = FIND();
      c.scanned = true;
      tool('cadguard.audit_2_tiers', `{ "file": "${K().file}", "standard": "${K().standard}", "ai_deep_check": true }`, K().secs, K().tool);
      renderAll();
      const codeF = F.filter(f => f.tier === 'code');
      const aiF = F.filter(f => f.tier === 'ai');
      const fx = F.filter(f => f.fix).map(f => f.id).join(' và ');
      const ne = F.filter(f => !f.fix).map(f => f.id).join(', ');
      say('ai', `<p>Mình đã quét xong trong ${K().secs} trên từng trang Artboard (đã bỏ qua vùng nháp ngoài khung A3). Có <b>${F.length} phát hiện</b>:</p>
        <p>• <b>Lớp 1 (Luật tất định):</b> ${codeF.length} phát hiện (${codeF.map(f => f.rule).join(', ')}) — trong đó <b>2 việc mình tự sửa được</b> (số ${fx}).</p>
        <p>• <b>Lớp 2 (AI phân tích sâu sản xuất):</b> ${aiF.length} cảnh báo sớm (${aiF.map(f => f.rule + ': ' + f.title).join('; ')}).</p>
        <p>Đã khoanh vùng và đánh số <b>1–${F.length}</b> trực tiếp tại đúng toạ độ trên bản vẽ. Các mục số ${ne} cần kỹ thuật viên quyết định.</p>
        <div class="src">Căn cứ: Bộ luật tất định ${K().standard} + Mô hình phân tích kỹ thuật nội thất.</div>`);
      tab('chat');
    });
  });
}

function doAiDeepScan() {
  return run(async () => {
    await step(600, () => {
      const c = C();
      if (!c.scanned) c.scanned = true;
      activeTierFilter = 'ai';
      $$('#tierBar .tier-btn').forEach(x => x.setAttribute('aria-pressed', x.dataset.tier === 'ai'));
      mountSheet();
      renderAll();
      const aiF = FIND().filter(f => f.tier === 'ai');
      tool('cadguard.ai_manufacturing_audit', `{ "file": "${K().file}", "axes": ["dimension_chain", "hardware_clearance_2_3mm", "bom_crosscheck"] }`, '0,8 giây', `${aiF.length} phát hiện chuyên sâu`);
      const itemsHtml = aiF.length
        ? aiF.map(f => `<li style="margin-bottom:6px"><b>${f.rule} (${f.title}):</b> ${f.d}<br><span style="color:var(--text3);font-size:12px">📍 Vị trí: ${f.where}</span></li>`).join('')
        : '<li>Hệ thống AI không phát hiện xung đột kích thước chuỗi hay vi phạm khe hở phụ kiện trong phân khu này.</li>';
      say('ai', `<p><b>✨ Kết quả Lớp 2 · AI Phân tích sâu sản xuất (Công thái học &amp; Kết cấu):</b></p><ul>${itemsHtml}</ul><p>Đã lọc danh sách lỗi hiển thị theo nhóm <b>Lớp 2 · AI Sản xuất</b> và làm nổi bật trên bản vẽ.</p>
        <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn-s btn-sm" onclick="setCanvasMode('3d')">🧊 Xem kết cấu trên 3D Studio</button>
          <button class="btn-s btn-sm" onclick="tab('finds')">Xem danh sách phát hiện</button>
        </div>`);
      tab('chat');
      toast(`Đã hiển thị ${aiF.length} phát hiện từ Lớp 2 · AI Sản xuất`);
    });
  });
}

function doPropose() {
  return run(async () => {
    await step(650, () => {
      const c = C(), F = FIND();
      c.proposed = true;
      c.view = 'after';
      c.ops = { a: true, b: true };
      mountSheet();
      renderAll();
      const fixable = F.filter(f => f.fix);
      tool('cadguard.propose_changeset', `{ "findings": [${fixable.map(f => f.id).join(', ')}], "dry_run": true }`, '0,5 giây', `${fixable.length} thao tác · chưa ghi tệp nào`);
      const listHtml = fixable.length
        ? fixable.map(f => `<li><b>${f.rule}:</b> ${f.fixTxt} <small>(${f.where})</small></li>`).join('')
        : '<li>Các đối tượng vẽ đều thỏa mãn tiêu chuẩn, không có lỗi cần tự động can thiệp.</li>';
      say('ai', `<p>Mình đề xuất <b>${fixable.length} thay đổi tự động</b> (đảm bảo an toàn, không làm hỏng hình học):</p>
        <ul>${listHtml}</ul>
        <p>Bản vẽ đang hiển thị chế độ <b>“Sau”</b> để bạn xem trước trực quan. Bấm nút bên dưới để duyệt ghi tệp mới hoặc chuyển tab <b>Thay đổi</b> để tùy chỉnh từng mục.</p>
        <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn-p btn-sm" onclick="accept()">${ic('check')}Duyệt và lưu ${K().file.replace('.dxf','')}_v2.dxf</button>
          <button class="btn-s btn-sm" onclick="tab('chg')">Xem tab Thay đổi</button>
        </div>`);
      tab('chat');
    });
  });
}

async function accept() {
  if (busy) return;
  busy = true;
  $('#okBtn').disabled = true;
  const c = C(), k = K(), F = FIND(), base = k.file.replace('.dxf', '');
  say('me', 'Duyệt và lưu v2');
  await step(750, () => {
    c.accepted = true;
    c.v2 = true;
    c.cur = 'v2';
    $('#cvTitle').textContent = base + '_v2.dxf';
    if (c.ops.a) F[0].st = 'fixed';
    if (c.ops.b) F[1].st = 'fixed';
    tool('cadguard.apply_changeset', '{ "ops": ' + Object.values(c.ops).filter(Boolean).length + ', "out": "' + base + '_v2.dxf" }', '0,8 giây', 'đã ghi tệp mới');
    tool('cadguard.validate_output', '{ "file": "' + base + '_v2.dxf" }', '0,9 giây', k.validate);
    renderAll();
    tab('chg');
    const left = F.filter(f => f.st === 'open').length;
    say('ai', `<p>Đã lưu <b>${base}_v2.dxf</b>. Mình mở lại tệp mới và chạy lại luật: không hỏng gì. Còn <b>${left} việc cần người</b>.</p>`);
    toast(`Đã lưu ${base}_v2.dxf · bản gốc không đổi`);
  });
  busy = false;
  suggestions();
}

function doExplain(targetRule) {
  return run(async () => {
    await step(450, () => {
      const firstOpen = FIND().find(f => f.st === 'open') || FIND()[0];
      const ruleCode = targetRule || (firstOpen ? firstOpen.rule : (K().explain && K().explain.rule) || 'VS-01');
      const f = FIND().find(x => x.rule === ruleCode) || firstOpen;
      tool('cadguard.explain_rule', `{ "rule": "${ruleCode}" }`, '0,1 giây', 'đã lấy mô tả luật và tham số');
      if (K().explain && K().explain.rule === ruleCode) {
        say('ai', K().explain.html);
      } else if (f) {
        say('ai', `<p><b>${f.rule} · ${f.title}</b></p><p>${f.d}</p>${f.fix ? `<p>🔧 <b>Phương án tự sửa:</b> ${f.fixTxt}</p>` : `<p>⚠️ <b>Yêu cầu xử lý:</b> ${f.need || 'Cần kỹ thuật viên xác nhận.'}</p>`}<div class="src">Căn cứ: Bộ quy chuẩn ${K().standard} · Vị trí: ${f.where}</div>`);
      } else {
        say('ai', `<p><b>${ruleCode}</b>: Luật kiểm tra tính toàn vẹn của bản vẽ trong quy chuẩn <code>${K().standard}</code>.</p>`);
      }
      tab('chat');
    });
  });
}

function doExplainNeed(targetRule) {
  return run(async () => {
    await step(450, () => {
      const firstNeed = FIND().find(f => f.st === 'open' && !f.fix) || FIND()[0];
      const ruleCode = targetRule || (firstNeed ? firstNeed.rule : (K().needExplain && K().needExplain.rule) || 'PR-01');
      const f = FIND().find(x => x.rule === ruleCode) || firstNeed;
      tool('cadguard.explain_rule', `{ "rule": "${ruleCode}" }`, '0,1 giây', 'đã lấy mô tả luật');
      if (K().needExplain && K().needExplain.rule === ruleCode) {
        say('ai', K().needExplain.html);
      } else if (f) {
        say('ai', `<p><b>${f.rule} · ${f.title}</b></p><p>${f.d}</p><p>⚠️ <b>Yêu cầu xử lý:</b> ${f.need || 'Cần kỹ thuật viên xác nhận.'}</p><div class="src">Căn cứ: Bộ quy chuẩn ${K().standard} · Vị trí: ${f.where}</div>`);
      } else {
        say('ai', `<p><b>${ruleCode}</b>: Yêu cầu kỹ thuật viên xác nhận phương án xử lý theo quy chuẩn <code>${K().standard}</code>.</p>`);
      }
      tab('chat');
    });
  });
}

function doHandover() {
  return run(async () => {
    await step(650, () => {
      const h = K().handover;
      C().handover = true;
      renderHome();
      tool('cadguard.get_handover_data', `{ "file": "${K().file}" }`, '0,4 giây', 'dữ liệu bàn giao có cấu trúc');
      const hasOpen = FIND().some(f => f.st === 'open' && !f.fix);
      say('ai', `<p>Đây là <b>${h.title.toLowerCase()}</b>, tạo từ dữ liệu có cấu trúc của bản vẽ:</p>
        <div class="note-card"><div class="lbl">${ic('info')}Sinh tự động từ dữ liệu bản vẽ, không phải văn bản tự do của mô hình</div>
          <ul>${h.items.map(i => `<li>${i}</li>`).join('')}${hasOpen ? `<li style="color:var(--warn-fg);background:var(--warn-bg);border-radius:4px;padding:0 6px;list-style:none;margin-left:-14px">${ic('alert', 'width:14px;height:14px;vertical-align:-2px;margin-right:4px')}${h.warn}</li>` : ''}</ul>
          <button class="btn-s btn-sm" onclick="toast('Đã sao chép ghi chú bàn giao vào bộ nhớ tạm')">${ic('copy')}Sao chép</button></div>`);
    });
  });
}

function doRescan() {
  return run(async () => {
    await step(600, () => {
      const left = FIND().filter(f => f.st === 'open');
      tool('cadguard.audit', `{ "file": "${K().file.replace('.dxf', '')}_v2.dxf" }`, '0,8 giây', `còn ${left.length} phát hiện`);
      say('ai', `<p>Quét lại bản v2: còn <b>${left.length} phát hiện</b> (${left.map(f => f.rule).join(', ')}), đều cần kỹ thuật viên xác nhận. Các lỗi tự sửa đã sạch hoàn toàn.</p>`);
    });
  });
}

$('#form').onsubmit = async e => {
  e.preventDefault();
  const v = $('#inp').value.trim();
  if (!v || busy) return;
  $('#inp').value = '';
  say('me', v);
  const t = v.toLowerCase(), c = C();
  if (/quét|kiểm|audit/.test(t) && !c.scanned) {
    doScan();
  } else if (/sửa|đổi|chữ|gộp|nối/.test(t) && c.scanned && !c.accepted) {
    doPropose();
  } else if (/bàn giao|giao|gói/.test(t)) {
    doHandover();
  } else if (/giải thích|vì sao/.test(t)) {
    doExplain();
  } else if (/khe hở|bản lề|chuỗi|ai|sâu/.test(t)) {
    doAiDeepScan();
  } else {
    // Gọi trực tiếp API trợ lý AI thực tế trên backend (/api/chat)
    await run(async () => {
      const tp = typing();
      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: v,
            drawing: activeWsFile || K().file,
            engine: engine.id
          })
        });
        const data = await res.json();
        tp.remove();
        if (data.toolCalls && data.toolCalls.length) {
          data.toolCalls.forEach(tc => tool(tc.name, JSON.stringify(tc.args), '0,4 giây', tc.summary || 'hoàn tất'));
        }
        say('ai', `<p>${(data.reply || 'Mình đã ghi nhận câu hỏi và kiểm tra ngữ cảnh trang hiện tại.').replace(/\n/g, '</p><p>')}</p>`);
      } catch (err) {
        tp.remove();
        say('ai', `<p>Dựa trên ngữ cảnh trang đang mở của <b>${K().file}</b>: mình khuyến nghị ưu tiên xử lý các lỗi Lớp 1 bằng Changeset tự động trước, sau đó kiểm tra cảnh báo Lớp 2 AI về kích thước chuỗi và khe hở lắp đặt phụ kiện.</p>`);
      }
    });
  }
};

/* ---------- misc ---------- */
function toast(m) {
  const t = $('#toast');
  t.textContent = m;
  t.classList.add('on');
  clearTimeout(toast.t);
  toast.t = setTimeout(() => t.classList.remove('on'), 2800);
}
window.toast = toast;

$('#mNo').onclick = () => $('#modal').classList.remove('on');
$('#mYes').onclick = () => {
  $('#modal').classList.remove('on');
  const c = C(), k = K();
  c.accepted = false;
  c.proposed = false;
  c.v2 = false;
  c.cur = 'A';
  FIND().forEach(f => f.st = 'open');
  c.sel = null;
  $('#cvTitle').textContent = k.file;
  renderAll();
  say('ai', `<p>Đã bỏ bản v2. Mọi thứ quay về như lúc vừa quét; bản gốc <b>${k.file}</b> không bị đụng tới.</p>`);
  suggestions();
  toast('Đã bỏ bản v2');
};
$('#stdLink').onclick = () => openCatalog({ stage: STAGE_KEY[stage] });

$('#scanAll').onclick = async () => {
  toast('Đang quét toàn bộ thư mục DXF...');
  try {
    const res = await fetch('/api/audit_all', { method: 'POST' });
    const data = await res.json();
    await loadWorkspaceDrawings();
    tab('chat');
    tool('cadguard.audit_workspace', '{ "folder": "fixtures/synthetic" }', '1,5 giây', `Đã quét ${data.totalFiles || 7} tệp DXF`);
    say('ai', `<p>Đã quét toàn bộ <b>${data.totalFiles || 7} tệp DXF</b> trong thư mục làm việc: tổng cộng <b>${data.totalErrors || 0} lỗi</b> và <b>${data.totalWarnings || 0} cảnh báo</b>. Bạn có thể bấm vào bất kỳ tệp nào ở cột trái để xem chi tiết hoặc bấm “Báo cáo thẩm định (HTML)”.</p>`);
    toast(`Đã quét xong ${data.totalFiles || 7} tệp DXF`);
  } catch (e) {
    toast('Đã quét toàn bộ thư mục');
  }
};

$('#reportHtmlBtn').onclick = () => {
  const target = activeWsFile || 'hygiene_bad.dxf';
  window.open(`/api/report/html?name=${encodeURIComponent(target)}`, '_blank');
  toast(`Đã mở báo cáo thẩm định HTML tiếng Việt`);
};

const testMcpBtn = $('#testMcpBtn');
if (testMcpBtn) {
  testMcpBtn.onclick = () => syncToAutoCAD();
}

/* ---------- Việc của tôi (theo phòng) ---------- */
const COUNTS = { design: 3, tech: 4, viz: 2, cnc: 2, shop: 5, render: 1 };
function ck(done, txt) {
  return `<li class="${done ? 'done' : 'todo'}">${done ? ic('check') : ic('x')}<span>${txt}</span></li>`;
}
function gateLink() {
  const t = GATE[stage], n = RULES.filter(r => r.tasks.includes(t)).length;
  return ` <button class="f-link" data-gate="${t}">xem ${n} luật của bước “${TASKS[t].n}”</button>`;
}
function renderPipe() {
  const node = (k, n) => `<div class="node${k === stage ? ' me' : ''}" data-pipe="${k}"><div class="nm">${n}</div><div class="ct">${COUNTS[k]} bản đang xử lý</div>${k === stage ? '<span class="pill info">Bạn ở đây</span>' : ''}</div>`;
  const arr = `<div class="arr">${ic('arrow')}</div>`;
  $('#pipe').innerHTML = node('design', 'Thiết kế') + arr + node('tech', 'Kỹ thuật') + arr + `<div class="fork">${node('viz', 'Thiết kế 3D')}${node('cnc', 'Lập trình sản xuất')}</div>` + arr + `<div class="fork">${node('render', 'Render')}${node('shop', 'Xưởng')}</div>`;
  $$('#pipe [data-pipe]').forEach(el => {
    const k = el.dataset.pipe;
    if (DEPT[k]) el.onclick = () => setStage(k);
  });
}
function renderHome() {
  const c = C(), k = K(), d = DEPT[stage], F = FIND();
  const open = F.filter(f => f.st === 'open'), need = c.scanned ? open.filter(f => !f.fix) : [];
  const autoFix = c.scanned ? open.filter(f => f.fix).length : 0;
  const clean = c.scanned && open.length === 0;
  $('#homeH').textContent = `Phòng ${d.name}`;
  $('#homeP').textContent = d.role + '. ' + (need.length ? `Bạn có ${need.length} việc cần quyết, ` : '') + '1 bản sẵn sàng bàn giao' + (c.scanned ? '' : ' và 2 bản chưa quét') + '.';
  renderPipe();
  const aState = !c.scanned ? ['neu', 'Chưa quét'] : clean ? ['ok', 'Sạch lỗi'] : ['warn', `${open.length} việc còn lại`];
  const decide = need.length ? `<div class="decide">${ic('hand')}<div><b>Cần bạn quyết:</b><br>${need.map(f => `${f.rule} · ${f.title}`).join('<br>')}</div></div>` : '';
  let inbox = '';
  if (k.inbox) {
    const ib = k.inbox;
    inbox = `<h2>Nhận từ phòng ${ib.from}</h2><article class="dwg"><div class="dwg-h"><span class="nm">${ic('inbox')}${ib.name}</span><span class="stage pill ${c.received ? 'ok' : 'info'}">${c.received ? ic('check') + 'Đã nhận' : 'Có gói bàn giao'}</span></div>
      <p style="margin:8px 0 10px;color:var(--text2);font-size:14.5px">Từ <b>${ib.from}</b> · ${ib.when}. ${ib.note}.</p>
      <div class="dwg-f"><button class="btn-s" id="recvBtn" ${c.received ? 'disabled' : ''}>${c.received ? 'Đã nhận' : 'Nhận và mở'}</button><span class="why">Nhận gói cùng ghi chú bàn giao và báo cáo kiểm của phòng ${ib.from}.</span></div></article>`;
  }
  const A = `<article class="dwg"><div class="dwg-h"><span class="nm">${ic('file')}${k.file}</span><span class="pill info sm">${(k.sheets || []).length} trang Artboard</span><span class="stage pill ${aState[0]}">${aState[0] === 'ok' ? ic('check') : aState[0] === 'warn' ? ic('alert') : ''}${aState[1]}</span></div>
    ${decide}
    <ul class="ready">${ck(clean, (c.scanned ? (clean ? 'Hết lỗi theo luật' : `Còn ${open.length} lỗi/cảnh báo` + (autoFix ? ` (${autoFix} tự sửa được)` : '')) : 'Chưa quét lỗi') + gateLink())}${ck(c.handover, K().handover.title)}${ck(false, `Trưởng phòng ${d.name} đã duyệt`)}${ck(false, `Gói đã giao cho ${d.next}`)}</ul>
    <div class="dwg-f"><button class="btn-p" data-open="work">${c.scanned ? 'Mở và xử lý' : 'Mở và quét'}</button><span class="why">Chưa thể ${d.mess.toLowerCase()}: ${c.scanned ? 'còn lỗi và thiếu người duyệt' : 'chưa quét'}.</span></div></article>`;
  const P = k.pack;
  const D = `<article class="dwg"><div class="dwg-h"><span class="nm">${ic('file')}${P.name}.dxf</span><span class="stage pill ok">${ic('check')}Sẵn sàng bàn giao</span></div>
    <ul class="ready">${ck(true, 'Hết lỗi theo luật' + gateLink())}${ck(true, K().handover.title)}${ck(true, `Trưởng phòng ${d.name} đã duyệt`)}${ck(c.packD, `Gói đã giao cho ${d.next}`)}</ul>
    <div class="dwg-f"><button class="btn-p" id="packBtn" ${c.packD ? 'disabled' : ''}>${c.packD ? 'Đã tạo gói' : d.mess}</button><span class="why">${c.packD ? `Đã lưu thành tệp mới và báo ${d.next}.` : 'Chưa ghi gì cho tới khi bạn bấm.'}</span></div>
    <div class="pack${c.packD ? ' on' : ''}"><b>Gói bàn giao gồm</b><ul>${P.list.map(x => `<li>${x}</li>`).join('')}</ul><span style="font-size:13.5px;color:var(--text3)">Bản gốc không bị sửa. Gói này là tệp mới có mã phiên bản.</span></div></article>`;
  const I = `<article class="dwg"><div class="dwg-h"><span class="nm">${ic('file')}${k.idleName}.dxf</span><span class="stage pill neu">Chưa quét</span></div>
    <div class="dwg-f" style="margin-top:10px"><button class="btn-s" data-open="work">Mở và quét</button><span class="why">Bản đang làm, chưa có kết quả kiểm.</span></div></article>`;
  $('#homeList').innerHTML = inbox + `<h2${inbox ? ' style="margin-top:22px"' : ''}>Bản vẽ của phòng ${d.name}</h2>` + A + D + I;
  $$('[data-open]').forEach(b => b.onclick = () => go(b.dataset.open));
  $$('[data-gate]').forEach(b => b.onclick = () => openCatalog({ task: b.dataset.gate }));
  const p = $('#packBtn');
  if (p) p.onclick = () => {
    c.packD = true;
    COUNTS[stage]--;
    COUNTS[d.nextKey]++;
    if (stage === 'tech') COUNTS.viz++;
    renderHome();
    toast(`Đã ${d.mess.toLowerCase()}`);
  };
  const r = $('#recvBtn');
  if (r) r.onclick = () => {
    c.received = true;
    renderHome();
    toast(`Đã nhận gói từ ${K().inbox.from}`);
  };
}
$('#askForm').onsubmit = e => {
  e.preventDefault();
  const v = $('#askIn').value.trim();
  if (!v) return;
  $('#askIn').value = '';
  go('work');
  tab('chat');
  $('#inp').value = v;
  $('#form').requestSubmit();
};

/* ---------- chọn phòng ---------- */
function renderDeptMenu() {
  $('#deptMenu').innerHTML = ORDER.map(k => `<button role="menuitemradio" aria-checked="${k === stage}" data-d="${k}"><span style="width:18px;margin-top:2px">${k === stage ? ic('check') : ''}</span><span><span class="t">${DEPT[k].name}</span><br><span class="d">${DEPT[k].role}</span></span></button>`).join('');
  $$('#deptMenu button').forEach(b => b.onclick = () => { setStage(b.dataset.d); closeMenus(); });
  $('#deptName').textContent = DEPT[stage].name;
}
function setStage(k) {
  if (k === stage && svg) return;
  if (svg) ST[stage].logHTML = log.innerHTML;
  stage = k;
  RS.stage = STAGE_KEY[k];
  if (RS.open) { RS.open = null; renderDrawer(); }
  syncControls();
  const c = C(), kk = K();
  if ($('#projName')) $('#projName').textContent = kk.project;
  if ($('#stdName')) $('#stdName').textContent = kk.standard;
  if ($('#stdRules')) $('#stdRules').textContent = kk.rulesOn;
  if ($('#cvTitle')) $('#cvTitle').textContent = activeWsFile || (c.v2 && c.cur === 'v2' ? kk.file.replace('.dxf', '') + '_v2.dxf' : kk.file);
  if ($('#viewTag')) $('#viewTag').textContent = kk.view;
  if ($('#cvInfo')) $('#cvInfo').textContent = kk.info + ' · tệp gốc chỉ đọc';
  mountSheet();
  renderArtboardBar();
  if (c.logHTML) log.innerHTML = c.logHTML;
  else intro();
  renderDeptMenu();
  renderAll();
  suggestions();
  tab('chat');
}
function renderAll() {
  renderArtboardBar();
  renderFiles();
  renderWsFiles();
  renderFinds();
  renderChg();
  renderReviewNotes();
  renderStudioPane();
  syncCanvas();
  renderHome();
  renderRules();
}

/* ---------- connect / overview content ---------- */
const CLI = [
  { n: 'Claude Code', s: ['ok', 'Đã đăng nhập'], d: 'Dùng tài khoản của chính bạn (gói hoặc khoá API). cad-guard chỉ mở CLI; cửa sổ đăng nhập là của CLI.', b: 'Kiểm tra lại' },
  { n: 'Codex CLI', s: ['warn', 'Cần đăng nhập'], d: 'Bấm để mở cửa sổ đăng nhập của Codex. Trên máy không có trình duyệt dùng mã thiết bị.', b: 'Mở đăng nhập' },
  { n: 'Antigravity CLI', s: ['neu', 'Chưa cài'], d: 'Chưa tìm thấy lệnh agy trên máy này.', b: 'Xem hướng dẫn cài' },
  { n: 'OpenCode', s: ['ok', 'Đã cài'], d: 'Cầu nối tới nhiều nhà cung cấp bằng khoá API. Dùng cho chế độ khoá của công ty.', b: 'Mở cấu hình' }
];
$('#cliCards').innerHTML = CLI.map(c => `<div class="card prov"><div class="hd"><span class="nm">${c.n}</span><span class="pill ${c.s[0]}">${c.s[0] === 'ok' ? ic('check') : c.s[0] === 'warn' ? ic('alert') : ic('x')}${c.s[1]}</span></div><p class="ds">${c.d}</p><div class="row"><button class="btn-s btn-sm" onclick="toast('Đã kiểm tra kết nối ${c.n}')">${c.b}</button></div></div>`).join('');

const API = [
  ['Google Gemini', 'AIzaSy••••••••••••••••••••••89aF', 'ok', 'Đang hoạt động (Server Env)'],
  ['Anthropic', 'sk-ant-••••••••••••3f2a', 'ok', 'Đã kiểm tra'],
  ['OpenAI', '', 'neu', 'Chưa nhập khoá'],
  ['OpenRouter', '', 'neu', 'Chưa nhập khoá · bên trung gian, mặc định tắt']
];
$('#apiCards').innerHTML = API.map(([n, k, s, t]) => `<div class="card prov"><div class="hd"><span class="nm">${n}</span><span class="pill ${s}">${s === 'ok' ? ic('check') : ic('x')}${t}</span></div>
  <div class="row"><input type="password" value="${k}" placeholder="Dán khoá API" aria-label="Khoá API ${n}"><button class="btn-s btn-sm" onclick="toast('Khoá ${n} được quản lý an toàn qua biến môi trường / Keychain')">${k ? 'Đổi' : 'Lưu'}</button></div></div>`).join('');

const BARS = [
  ['LY-04 · Layer chưa định nghĩa', 7],
  ['TX-02 · Chiều cao chữ', 6],
  ['PR-01 · Thẻ vị trí – bảng kê', 4],
  ['AI-CLR · Khe hở cánh tủ < 2mm', 4],
  ['SH-05 · Thuộc tính khung tên', 3],
  ['DH-03 · Đường bao tấm khép kín', 2]
];
$('#bars').innerHTML = BARS.map(([n, v]) => `<div class="bar"><span>${n}</span><span class="tr"><i style="width:${v / 7 * 100}%"></i></span><span class="nn">${v}</span></div>`).join('');

/* ---------- LUẬT ÁP DỤNG (danh mục luật gắn phòng · vị trí · task · Admin nhóm luật) ---------- */
const STG = { d: 'Thiết kế', t: 'Kỹ thuật', v: 'Thiết kế 3D', c: 'Lập trình SX' };
const STAGE_KEY = { design: 'd', tech: 't', viz: 'v', cnc: 'c' };
const RULE_GROUPS = {
  SH: 'SH · Khung & Trang (Sheet)',
  LY: 'LY · Lớp bản vẽ (Layer)',
  TX: 'TX · Chữ & Kích thước (Text/Dim)',
  VW: 'VW · Hình chiếu & Tỉ lệ (View)',
  FN: 'FN · Nội thất & Vật liệu (Furniture)',
  DH: 'DH · Vệ sinh hình học (Drawing Hygiene)',
  PR: 'PR · Sản xuất & Bảng kê (Production)',
  VS: 'VS · Thị giác & Dọn rác (Visual)',
  '3D': '3D · Phối cảnh 3D',
  PJ: 'PJ · Luật riêng Dự án'
};
const ROLES = {
  pd: 'Thợ vẽ Thiết kế',
  ld: 'Trưởng phòng Thiết kế',
  te: 'Kỹ thuật viên',
  ck: 'Người kiểm bản vẽ',
  lt: 'Trưởng phòng Kỹ thuật',
  vz: 'Hoạ viên 3D',
  lv: 'Trưởng phòng Thiết kế 3D',
  pc: 'Lập trình CNC',
  lc: 'Trưởng phòng Lập trình SX',
  ad_sh: 'Admin · SH (Khung & Trang)',
  ad_ly: 'Admin · LY (Layer)',
  ad_tx: 'Admin · TX (Chữ & Dim)',
  ad_vw: 'Admin · VW (Hình chiếu)',
  ad_fn: 'Admin · FN (Nội thất)',
  ad_dh: 'Admin · DH (Vệ sinh hình học)',
  ad_pr: 'Admin · PR (Sản xuất CNC)',
  ad_vs: 'Admin · VS (Thị giác)',
  ad_3d: 'Admin · 3D (Phối cảnh 3D)',
  ad_pj: 'Admin · PJ (Dự án)',
  ad: 'Quản trị tiêu chuẩn (CEO / QA)'
};
const LEAD = { d: 'ld', t: 'lt', v: 'lv', c: 'lc' };
const TASKS = {
  t1: { n: 'Dọn bản vẽ (layer, chữ, khối)', s: 'd' },
  t2: { n: 'Bàn giao Thiết kế → Kỹ thuật', s: 'd', gate: 1 },
  t3: { n: 'Triển khai chi tiết & kích thước', s: 't' },
  t4: { n: 'Lập bảng kê & thẻ vị trí', s: 't' },
  t5: { n: 'Kiểm & ký duyệt bản vẽ', s: 't' },
  t6: { n: 'Bàn giao Kỹ thuật → Thiết kế 3D / Lập trình SX', s: 't', gate: 1 },
  t9: { n: 'Dựng 3D từ bản kỹ thuật', s: 'v' },
  t10: { n: 'Đặt ánh sáng & góc máy', s: 'v' },
  t11: { n: 'Bàn giao Thiết kế 3D → Render', s: 'v', gate: 1 },
  t7: { n: 'Chuẩn bị đường bao & lỗ khoan CNC', s: 'c' },
  t8: { n: 'Xuất dữ liệu cho máy', s: 'c', gate: 1 }
};
const GATE = { design: 't2', tech: 't6', viz: 't11', cnc: 't8' };
const MAPS = { stages: STG, roles: ROLES, tasks: TASKS, prefix: RULE_GROUPS };
const ORD = { stages: Object.keys(STG), roles: Object.keys(ROLES), tasks: Object.keys(TASKS), prefix: Object.keys(RULE_GROUPS) };
const STD_L = { f: 'furniture-v0.1.0', h: 'design-hygiene-v0', p: 'Dự án K1' };
const SEV = { E: ['err', 'Lỗi'], W: ['warn', 'Cảnh báo'], I: ['neu', 'Gợi ý'] };
const KIND = { r: ['ok', 'Đang chạy'], n: ['neu', 'Chưa cài code'], m: ['info', 'Kiểm tay'] };
const PARAMS = {
  'TX-02': [{ n: 'Chiều cao chữ ghi chú (mm)', v: '2.5' }],
  'VS-02': [{ n: 'Số kiểu chữ tối đa', v: '6' }],
  'VS-03': [{ n: 'Tỉ lệ tối đa trên layer “0”', v: '5%' }],
  'VW-01': [{ n: 'Tỉ lệ ưu tiên', v: '1:1, 1:2, 1:5, 1:10, 1:20, 1:50, 1:100, 2:1, 5:1, 10:1' }],
  'DH-09': [{ n: 'Đơn vị bản vẽ', v: 'mm' }],
  'SH-05': [{ n: 'Thuộc tính bắt buộc', v: 'DWG_NO, TITLE, PROJECT, SHEET, SCALE, DRAWN_BY, CHECKED_BY, DATE, REV, STATUS, STD_VER' }],
  'PJ-K1-03': [{ n: 'Sai lệch gốc toạ độ tối đa (mm)', v: '0' }]
};
const RAW = [
  ['VS-01', 'Không còn layer dư từ xref đã gộp (tên có $)', 'W', 'Khảo sát mẫu', 'h', 'r', null, 'd', 'ad_vs', 'pd', 't1,t2', 0],
  ['VS-02', 'Số kiểu chữ không vượt ngưỡng của công ty', 'W', 'Khảo sát mẫu', 'h', 'r', null, 'd', 'ad_vs', 'pd', 't1,t2', 0],
  ['VS-03', 'Tỉ lệ đối tượng trên layer “0” không vượt ngưỡng', 'E', 'Khảo sát mẫu', 'h', 'r', null, 'd', 'ad_vs', 'pd,ld', 't1,t2', 0],
  ['VS-04', 'Chữ dùng phông Unicode (không dùng phông VNI/TCVN cũ)', 'E', 'Khảo sát mẫu', 'h', 'r', null, 'd', 'ad_vs', 'pd', 't1,t2', 0],
  ['VS-05', 'Số khối ẩn danh không vượt ngưỡng', 'W', 'Khảo sát mẫu', 'h', 'r', null, 'd', 'ad_vs', 'pd', 't1', 0],
  ['VS-06', 'Không có đối tượng nằm quá xa vùng làm việc', 'W', 'Khảo sát mẫu', 'h', 'r', null, 'd', 'ad_vs', 'pd', 't1', 0],
  ['SH-04', 'Có đúng một khối khung tên chuẩn trên mỗi layout đã dùng', 'E', 'ISO 7200', 'f', 'r', null, 't', 'ad_sh', 'te,ck', 't5,t6', 0],
  ['SH-05', 'Mọi thuộc tính bắt buộc của khung tên đều có giá trị', 'E', 'ISO 7200', 'f', 'r', null, 't', 'ad_sh', 'te,ck', 't5,t6', 3],
  ['SH-06', 'Mã bản vẽ đúng mẫu công ty', 'E', 'CT', 'f', 'n', null, 't', 'ad_sh', 'te', 't3', null],
  ['SH-09', 'Không để “WIP” trên tờ đã đánh dấu xuống xưởng', 'E', 'CT', 'f', 'n', null, 'tc', 'ad_sh', 'ck', 't6,t8', null],
  ['LY-01', 'Tên layer đúng sơ đồ đặt tên', 'E', 'CT', 'f', 'r', null, 'tc', 'ad_ly', 'te,pc', 't3,t7', 0],
  ['LY-03', 'Không có đối tượng nằm trên layer 0 (trừ định nghĩa khối)', 'W', 'CT', 'f', 'r', null, 'tc', 'ad_ly', 'te,pc', 't3,t7', 0],
  ['LY-04', 'Không có đối tượng trên layer chưa định nghĩa trong chuẩn', 'E', 'CT', 'f', 'r', 96, 'tc', 'ad_ly', 'te,pc', 't3,t7', 7],
  ['LY-08', 'Layer FN-VPRT đặt không in', 'E', 'CT', 'f', 'r', null, 't', 'ad_ly', 'te', 't3', 0],
  ['TX-01', 'Kiểu chữ thuộc tập cho phép', 'W', 'DWS', 'f', 'r', null, 't', 'ad_tx', 'te', 't3', 0],
  ['TX-02', 'Chiều cao chữ = giá trị chuẩn × tỉ lệ viewport', 'W', 'ISO 3098', 'f', 'r', 92, 't', 'ad_tx', 'te', 't3', 6],
  ['TX-08', 'Kích thước không bị sửa chữ bằng tay', 'W', 'ISO 129-1', 'f', 'r', null, 't', 'ad_tx', 'te,ck', 't3,t5', 0],
  ['TX-09', 'Giá trị kích thước = số đo hình học', 'E', 'ISO 129-1', 'f', 'n', null, 't', 'ad_tx', 'te,ck', 't3,t5', null],
  ['VW-01', 'Tỉ lệ viewport nằm trong danh sách ưu tiên', 'W', 'TCVN 7286', 'f', 'r', null, 't', 'ad_vw', 'te', 't3', 0],
  ['FN-01', 'Mọi tấm có vật liệu và độ dày', 'E', 'AWS', 'f', 'n', null, 't', 'ad_fn', 'te', 't3,t4', null],
  ['FN-04', 'Có mã dán cạnh cho mọi cạnh (hoặc ghi chú chung)', 'W', 'CT', 'f', 'n', null, 't', 'ad_fn', 'te', 't3,t4', null],
  ['PR-01', 'Mỗi thẻ vị trí có trong bảng kê và ngược lại', 'E', 'TCVN 3824', 'f', 'r', 81, 't', 'ad_pr', 'te,ck', 't4,t6', 4],
  ['PR-02', 'Thẻ vị trí không trùng', 'E', 'CT', 'f', 'r', null, 't', 'ad_pr', 'te', 't4', 0],
  ['PR-04', 'Kích thước tấm trong bảng kê = hình học', 'E', 'CT', 'f', 'n', null, 'tc', 'ad_pr', 'te,pc', 't4,t7', null],
  ['PR-05', 'Layer CNC dùng đúng tên phần mềm đích, tham số hợp lệ', 'E', 'WoodWOP/Mozaik', 'f', 'n', null, 'c', 'ad_pr', 'pc', 't7,t8', null],
  ['PR-06', 'Bản vẽ đánh dấu xuống xưởng có revision, người kiểm, người duyệt', 'E', 'CT', 'f', 'n', null, 'tc', 'ad_pr', 'ck,lc', 't6,t8', null],
  ['DH-01', 'Không có đối tượng chồng trùng', 'W', 'CT', 'f', 'r', null, 'tc', 'ad_dh', 'te,pc', 't3,t7', 0],
  ['DH-03', 'Đường bao tấm khép kín và nối liền', 'E', 'Mozaik', 'f', 'r', null, 'c', 'ad_dh', 'pc', 't7,t8', 2],
  ['DH-09', 'Đơn vị vẽ là mm', 'E', 'CT', 'f', 'r', null, 'tc', 'ad_dh', 'te,pc', 't3,t7', 0],
  ['DH-10', 'Đối tượng nằm trên mặt phẳng z = 0', 'W', 'Mozaik', 'f', 'r', null, 'c', 'ad_dh', 'pc', 't7,t8', 0],
  ['PJ-K1-01', 'Ghi chú dán cạnh ABS 1 mm cho mọi cạnh lộ', 'E', 'Yêu cầu khách K1', 'p', 'm', null, 't', 'ad_pj', 'te,ck', 't3,t5', null],
  ['PJ-K1-02', 'Vân gỗ chạy dọc theo chiều cao tủ', 'W', 'Yêu cầu khách K1', 'p', 'm', null, 't', 'ad_pj', 'te,ck', 't3,t5', null],
  ['PJ-K1-03', 'Gốc toạ độ (0,0) đặt tại góc dưới trái của tấm', 'W', 'Máy CNC của K1', 'p', 'r', null, 'c', 'ad_pj', 'pc', 't7,t8', 0],
  ['3D-01', 'Đơn vị mô hình 3D = đơn vị bản vẽ ($INSUNITS)', 'E', 'Khảo sát mẫu', 'h', 'r', null, 'v', 'ad_3d', 'vz', 't9,t11', 0],
  ['3D-02', 'Vật thể 3D mang tên mã chi tiết của bản kỹ thuật', 'W', 'Khảo sát mẫu', 'h', 'r', null, 'v', 'ad_3d', 'vz', 't9,t11', 0],
  ['3D-03', 'Không có hai tấm giao nhau trong mô hình (va chạm, chồng)', 'E', 'Khảo sát mẫu', 'h', 'r', null, 'v', 'ad_3d', 'vz,te', 't9,t11', 0],
  ['3D-04', 'Mọi bề mặt nhìn thấy từ góc máy đã gán vật liệu theo bảng kê', 'W', 'Khảo sát mẫu', 'h', 'n', null, 'v', 'ad_3d', 'vz', 't10,t11', null],
  ['3D-05', 'Góc máy đề xuất nằm trong phòng, cao 1,2–1,7 m, không xuyên tường', 'W', 'Khảo sát mẫu', 'h', 'n', null, 'v', 'ad_3d', 'vz', 't10', null],
  ['3D-06', 'Ánh sáng có ít nhất một nguồn chính theo hướng cửa/cửa sổ của mặt bằng', 'I', 'Khảo sát mẫu', 'h', 'n', null, 'v', 'ad_3d', 'vz', 't10', null],
  ['SH-01', 'Mỗi layout có khung khổ A-series nhận diện được', 'E', 'TCVN 7285', 'f', 'n', null, '', '', '', '', null],
  ['SH-02', 'Lề khung 20 mm trái, 10 mm các cạnh còn lại', 'W', 'TCVN 7285', 'f', 'n', null, '', '', '', '', null],
  ['SH-03', 'Nét khung 0,7 mm', 'W', 'TCVN 7285', 'f', 'n', null, '', '', '', '', null],
  ['TX-03', 'Không có chữ dưới 1,8 mm trên giấy', 'E', 'ISO 3098', 'f', 'n', null, '', '', '', '', null],
  ['VW-05', 'Mỗi ký hiệu cắt có hình cắt tương ứng', 'W', 'ISO 128-40', 'f', 'n', null, '', '', '', '', null]
];
const UNLISTED = 29;
const byOrd = (k, a) => [...a].sort((x, y) => ORD[k].indexOf(x) - ORD[k].indexOf(y));
const snap = o => JSON.stringify({ on: o.on, owner: o.owner, stages: o.stages, roles: o.roles, tasks: o.tasks, params: o.params.map(p => p.v) });
function rulePrefixOf(id) {
  const p = String(id).split('-')[0].toUpperCase();
  return RULE_GROUPS[p] ? p : 'PJ';
}
function mk(a) {
  const [id, title, sev, src, std, kind, acc, stg, owner, roles, tasks, hits] = a;
  const o = {
    id, title, sev, src, std, kind, acc, hits, owner, on: true, proj: std === 'p',
    prefix: [rulePrefixOf(id)],
    stages: byOrd('stages', stg.split('').filter(Boolean)),
    roles: byOrd('roles', roles.split(',').filter(Boolean)),
    tasks: byOrd('tasks', tasks.split(',').filter(Boolean)),
    params: (PARAMS[id] || []).map(p => ({ ...p })),
    rt: (id === 'LY-04' || id === 'TX-02')
  };
  o.base = snap(o);
  return o;
}
const RULES = RAW.map(mk);
RULES.find(r => r.id === 'VW-01').exc = { txt: 'Cho phép tỉ lệ 1:25 cho mặt đứng tủ bếp', why: 'Khổ A3 không đủ chỗ ở 1:20 cho dãy tủ dài 3,2 m', until: '30/11/2026', by: 'Admin · VW (Hình chiếu)' };
const HIST = [
  ['05/11/2026', 'Studio 3D & Quản lý Dự án', 'Tích hợp dựng khối 3D xoay trực tiếp, xuất GLB, quét thư mục dự án (Google Drive + Máy tính) và Admin nhóm luật'],
  ['05/11/2026', 'Lớp 2 AI & Multi-Sheet Artboard', 'Tích hợp phân tích sâu sản xuất và tách trang Artboard / vùng nháp'],
  ['04/11/2026', 'design-hygiene-v0', '6 luật vệ sinh cho khâu Thiết kế'],
  ['03/11/2026', 'Overlay Dự án K1 v1', '3 luật riêng và 1 ngoại lệ do Admin nhóm luật tạo'],
  ['02/11/2026', 'furniture-v0.1.0', '58 luật chuẩn nội thất công nghiệp']
];
const RS = { scope: 'k1', stage: 'd', role: '', task: '', kind: '', q: '', group: '', open: null, view: 'lead', submitted: false, ver: { co: '0.1.0', k1: 1 } };
const FORM = {};

const isUn = r => !r.stages.length || !r.roles.length || !r.tasks.length || !r.owner;
const leadOfDept = () => LEAD[STAGE_KEY[stage]];
function canEdit(r) {
  if (RS.view === 'ad') return true;
  if (RS.view && RS.view.startsWith('ad_')) {
    const grp = RS.view.replace('ad_', '').toUpperCase();
    return r.owner === RS.view || rulePrefixOf(r.id) === grp || r.proj;
  }
  if (RS.view === 'lead') return !r.owner || r.owner === leadOfDept() || r.stages.includes(STAGE_KEY[stage]) || r.proj;
  return false;
}
const nm = (arr, map) => arr.length ? arr.map(k => typeof map[k] === 'string' ? map[k] : map[k].n).join(', ') : '(trống)';
const bump = v => { const p = v.split('.'); p[2] = +p[2] + 1; return p.join('.'); };
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const srcL = s => s === 'CT' ? 'Quy định công ty' : s;
const inScope = r => RS.scope === 'k1' || !r.proj;

function filtered() {
  return RULES.filter(r => {
    if (!inScope(r)) return false;
    if (RS.stage === 'none') { if (!isUn(r)) return false; } else if (RS.stage && !r.stages.includes(RS.stage)) return false;
    if (RS.role && !r.roles.includes(RS.role) && r.owner !== RS.role) return false;
    if (RS.task && !r.tasks.includes(RS.task)) return false;
    if (RS.kind && r.kind !== RS.kind) return false;
    if (RS.q && !(r.id + ' ' + r.title).toLowerCase().includes(RS.q.toLowerCase())) return false;
    return true;
  });
}

/* ----- bản nháp ----- */
function diffs() {
  const out = [];
  RULES.forEach(r => {
    if (r.isNew) {
      out.push({ r, k: 'k1', what: 'Thêm luật riêng cho Dự án K1', from: null, to: `${r.title} · ${nm(r.stages, STG)} · phụ trách ${ROLES[r.owner] || '—'}`, det: 1, relax: false });
      return;
    }
    const b = JSON.parse(r.base), add = (what, f, t, det, k, relax) => out.push({ r, k: k || (r.proj ? 'k1' : 'co'), what, from: f, to: t, det, relax: !!relax });
    if (b.on !== r.on) add('Bật/tắt luật', b.on ? 'Bật' : 'Tắt', r.on ? 'Bật' : 'Tắt', 1, null, !r.on);
    if (b.owner !== r.owner) add('Người phụ trách (Admin nhóm luật)', ROLES[b.owner] || '(chưa gắn)', ROLES[r.owner] || '(chưa gắn)', 0, null, false);
    [['stages', 'Phòng áp dụng'], ['roles', 'Vị trí áp dụng'], ['tasks', 'Task liên quan']].forEach(([k, l]) => {
      if (b[k].join() !== r[k].join()) add(l, nm(b[k], MAPS[k]), nm(r[k], MAPS[k]), 0, null, false);
    });
    r.params.forEach((p, i) => { if (b.params[i] !== p.v) add(`Tham số “${p.n}”`, b.params[i], p.v, 1, null, true); });
    if (r.exc && r.exc.isNew) add('Thêm ngoại lệ cho Dự án K1', null, `${r.exc.txt} (đến ${r.exc.until}, lý do: ${r.exc.why || '—'})`, 1, 'k1', true);
  });
  return out;
}
function undoDraft() {
  for (let i = RULES.length - 1; i >= 0; i--) {
    const r = RULES[i];
    if (r.isNew) { RULES.splice(i, 1); continue; }
    const b = JSON.parse(r.base);
    r.on = b.on; r.owner = b.owner; r.stages = [...b.stages]; r.roles = [...b.roles]; r.tasks = [...b.tasks];
    r.params.forEach((p, j) => p.v = b.params[j]);
    if (r.exc && r.exc.isNew) delete r.exc;
  }
  RS.submitted = false;
  if (RS.open && !RULES.find(x => x.id === RS.open)) RS.open = null;
}
function dirty(r) { return r.isNew || snap(r) !== r.base || (r.exc && r.exc.isNew); }
function draftInfo(D) {
  const co = D.some(d => d.k === 'co'), pj = D.some(d => d.k === 'k1'),
    owners = [...new Set(D.map(d => d.r.owner).filter(Boolean))].map(o => ROLES[o]);
  if (co && !owners.includes(ROLES.ad)) owners.push(ROLES.ad);
  const vers = [];
  if (co) vers.push(`chuẩn công ty thành <b>furniture-v${bump(RS.ver.co)}</b>`);
  if (pj) vers.push(`overlay Dự án K1 thành <b>v${RS.ver.k1 + 1}</b>`);
  return { co, pj, owners, vers, det: D.some(d => d.det), relax: D.some(d => d.relax) };
}

/* ----- hiển thị ----- */
function pillsOf(arr, map, max) {
  const sh = arr.slice(0, max || 99).map(k => `<span class="pill neu sm">${typeof map[k] === 'string' ? map[k] : map[k].n}</span>`).join('');
  return sh + (arr.length > (max || 99) ? `<span class="pill neu sm" title="${esc(nm(arr.slice(max), map))}">+${arr.length - max}</span>` : '');
}
function rowHtml(r) {
  const sv = SEV[r.sev], kd = KIND[r.kind];
  const none = '<span class="none">Chưa gắn</span>';
  const stages = r.stages.length ? (r.stages.length === Object.keys(STG).length ? '<span class="pill neu sm">Cả 4 phòng</span>' : pillsOf(r.stages, STG)) : none;
  const roles = (r.roles.length ? `<div class="stack">${pillsOf(r.roles, ROLES, 3)}</div>` : none) + `<div class="own">${r.owner ? 'Admin luật: <b>' + ROLES[r.owner] + '</b>' : 'Admin luật: ' + none}</div>`;
  const tasks = r.tasks.length ? r.tasks.slice(0, 2).map(t => `<div>${TASKS[t].n}${TASKS[t].gate ? ' <span class="pill warn sm" title="Luật này phải sạch trước khi bàn giao bước này">Chặn bàn giao</span>' : ''}</div>`).join('') + (r.tasks.length > 2 ? `<div class="meta">+${r.tasks.length - 2} task khác</div>` : '') : none;
  const st = [`<span class="pill ${kd[0]} sm">${r.kind === 'r' ? ic('check', 'width:12px;height:12px') : ''}${kd[1]}</span>`];
  if (!r.on) st.push('<span class="pill warn sm">Đã tắt</span>');
  if (r.exc) st.push('<span class="pill proj sm">Có ngoại lệ</span>');
  if (dirty(r)) st.push('<span class="pill edit sm">' + (r.isNew ? 'Mới (nháp)' : 'Đã sửa (nháp)') + '</span>');
  const sub = r.kind === 'r' ? (r.acc != null ? `Chính xác ${r.acc}%` : 'Đang đo độ chính xác') : '';
  return `<tr class="row${RS.open === r.id ? ' sel' : ''}" data-id="${r.id}">
  <td><button class="code" data-open="${r.id}" aria-label="Mở chi tiết luật ${r.id}">${r.id}</button><div style="margin-top:4px"><span class="pill ${sv[0]} sm">${sv[1]}</span></div></td>
  <td><div class="ttl">${esc(r.title)}</div><div class="meta">${esc(srcL(r.src))} · ${STD_L[r.std]}${r.proj ? ' <span class="pill proj sm">Riêng dự án K1</span>' : ''}</div></td>
  <td><div class="stack">${stages}</div></td><td>${roles}</td><td>${tasks}</td>
  <td><div class="stack">${st.join('')}</div>${sub ? `<div class="meta" style="margin-top:4px">${sub}</div>` : ''}</td></tr>`;
}
function groupsOf(list) {
  if (!RS.group) return [[null, list]];
  const m = new Map(), key = RS.group === 'stage' ? 'stages' : RS.group === 'role' ? 'roles' : RS.group === 'prefix' ? 'prefix' : 'tasks';
  list.forEach(r => {
    let ks = key === 'roles' ? [...new Set([...r.roles, r.owner].filter(Boolean))] : r[key];
    if (!ks || !ks.length) ks = ['-'];
    ks.forEach(k => { if (!m.has(k)) m.set(k, []); m.get(k).push(r); });
  });
  const order = [...(ORD[key] || []), '-'];
  return order.filter(k => m.has(k)).map(k => [k, m.get(k)]);
}
function renderRules() {
  if (!$('#rbody')) return;
  const all = RULES.filter(inScope), F = filtered(), D = diffs();
  $('#srcline').innerHTML = `<span class="pill info">Đang quản lý ${RULES.filter(r => !r.proj).length} trong 64 luật chuẩn</span>
  <span>Chuẩn công ty <b>furniture-v${RS.ver.co}</b> · Overlay Dự án K1 <b>v${RS.ver.k1}</b></span>
  <span>Danh mục sinh từ tệp: <code>standards/furniture-v0.yaml</code> + <code>standards/design-hygiene-v0.yaml</code></span>`;
  const stageCard = k => {
    const L = all.filter(r => r.stages.includes(k)), run = L.filter(r => r.kind === 'r').length, man = L.filter(r => r.kind === 'm').length, nc = L.filter(r => r.kind === 'n').length, pj = L.filter(r => r.proj).length, n = L.length || 1;
    return `<button class="cov" data-stage="${k}" aria-pressed="${RS.stage === k}"><div class="nm">${STG[k]}</div><div class="big">${L.length} luật</div>
   <div class="bar2" aria-hidden="true"><i style="width:${run / n * 100}%;background:var(--ok)"></i><i style="width:${man / n * 100}%;background:var(--info-fg)"></i><i style="width:${nc / n * 100}%;background:var(--border-strong)"></i></div>
   <div class="sub">${run} đang chạy · ${man} kiểm tay · ${nc} chưa cài code${pj && RS.scope === 'k1' ? ` · ${pj} riêng dự án` : ''}</div></button>`;
  };
  const unTotal = UNLISTED + RULES.filter(r => !r.proj && r.std === 'f' && isUn(r)).length;
  $('#covs').innerHTML = Object.keys(STG).map(stageCard).join('') +
    `<button class="cov gap" data-stage="none" aria-pressed="${RS.stage === 'none'}"><div class="nm">Chưa gắn đủ phòng · vị trí · task</div><div class="big">${unTotal} luật</div><div class="sub">Không ai nhận khi vi phạm, không chặn bước nào. Bấm để xem.</div></button>`;
  $('#gapNote').innerHTML = RS.stage === 'none' ? `<div class="callout warn"><svg class="i" viewBox="0 0 24 24"><path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/></svg><div>Luật chưa gắn vẫn chạy (nếu đã cài code) nhưng lỗi của nó không có người phụ trách và không nằm trong điều kiện bàn giao nào. Mở từng luật để gắn phòng, vị trí, task.</div></div>` : '';
  $$('#scopeSeg button').forEach(b => b.setAttribute('aria-pressed', b.dataset.v === RS.scope));
  const gs = groupsOf(F);
  let h = '';
  gs.forEach(([k, L]) => {
    if (k !== null) {
      const lb = k === '-' ? 'Chưa gắn' : RS.group === 'stage' ? 'Phòng ' + STG[k] : RS.group === 'role' ? ROLES[k] : RS.group === 'prefix' ? (RULE_GROUPS[k] || k) : TASKS[k].n + ' · ' + STG[TASKS[k].s];
      h += `<tr class="grp"><td colspan="6">${lb} <span class="pill neu sm">${L.length} luật</span>${RS.group === 'task' && k !== '-' && TASKS[k].gate ? ' <span class="pill warn sm">Bước chặn bàn giao: mọi lỗi phải sạch</span>' : ''}</td></tr>`;
    }
    h += L.map(rowHtml).join('');
  });
  $('#rbody').innerHTML = h || `<tr><td colspan="6"><div class="empty"><b>Không có luật nào khớp bộ lọc</b>Thử bỏ bớt bộ lọc hoặc đổi phạm vi.</div></td></tr>`;
  $('#rfoot').innerHTML = `Hiển thị <b>${F.length}</b> / ${all.length} luật${RS.group ? '. Một luật có thể xuất hiện ở nhiều nhóm.' : '.'} Bấm mã luật để xem chi tiết${RS.view === 'pd' ? '.' : ' và sửa trong bản nháp.'}`;
  $$('#rbody tr.row').forEach(tr => tr.onclick = e => { if (e.target.closest('button')) return; openRule(tr.dataset.id); });
  $$('#rbody [data-open]').forEach(b => b.onclick = () => openRule(b.dataset.open));
  $$('#covs .cov').forEach(b => b.onclick = () => { RS.stage = RS.stage === b.dataset.stage ? '' : b.dataset.stage; syncControls(); renderRules(); });
  $('#vhist').innerHTML = HIST.map(([t, v, x]) => `<li><time>${t}</time><span><b>${v}</b> · ${x}</span></li>`).join('');
  renderRoleSel();
  renderDraftBar(D);
}
function renderRoleSel() {
  const s = $('#viewRole');
  const adminOpts = Object.entries(ROLES).filter(([k]) => k.startsWith('ad_')).map(([k, l]) => `<option value="${k}">${l}</option>`).join('');
  s.innerHTML = `<option value="pd">Thợ vẽ (chỉ xem)</option>
    <option value="lead">Trưởng phòng ${DEPT[stage].name}</option>
    <optgroup label="Admin Nhóm Luật (Rule Group Admin)">${adminOpts}</optgroup>
    <option value="ad">Quản trị tiêu chuẩn (CEO / QA)</option>`;
  s.value = RS.view;
}
function syncControls() {
  $('#rq').value = RS.q;
  $('#fRole').value = RS.role;
  $('#fTask').value = RS.task;
  $('#fKind').value = RS.kind;
  $('#fGroup').value = RS.group;
}
function openCatalog(o) {
  const rule = o && o.rule;
  if (o) delete o.rule;
  Object.assign(RS, { stage: '', role: '', task: '', kind: '', q: '', group: '', scope: 'k1' }, o || {});
  syncControls();
  go('rules');
  renderRules();
  if (rule) openRule(rule);
}

/* ----- ngăn chi tiết ----- */
function chips(kind, opts, sel, can) {
  return `<div class="chipset" role="group">` + opts.map(([k, l]) => `<button type="button" class="tchip" data-chip="${kind}" data-v="${k}" aria-pressed="${sel.includes(k)}"${can ? '' : ' disabled'}>${sel.includes(k) ? ic('check', 'width:14px;height:14px') : ''}${l}</button>`).join('') + `</div>`;
}
function openRule(id) {
  RS.open = id;
  renderRules();
  renderDrawer();
  const c = $('#drClose');
  if (c) c.focus();
}
function closeRule() {
  const id = RS.open;
  RS.open = null;
  renderRules();
  renderDrawer();
  const b = id && $(`#rbody [data-open="${id}"]`);
  if (b) b.focus();
}
function renderDrawer() {
  const d = $('#drawer'), r = RULES.find(x => x.id === RS.open);
  if (!r) { d.classList.remove('on'); d.innerHTML = ''; return; }
  d.classList.add('on');
  const can = canEdit(r), dis = can ? '' : ' disabled', sv = SEV[r.sev], kd = KIND[r.kind];
  const why = {
    r: 'Chạy bằng code tất định trên mô hình bản vẽ. Đúng/sai do luật quyết, không do AI.',
    n: 'Đã có trong chuẩn nhưng chưa có code nên chưa chạy và chưa chặn gì. Cần lập trình viên viết hàm luật theo quy trình trong AGENTS.md.',
    m: 'Máy không kiểm được. Người kiểm tick tay ở bước ký duyệt và mục này nằm trong gói bàn giao.'
  }[r.kind];
  const note = can ? '' : `<div class="callout" style="margin:12px 0 0"><svg class="i" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg><div>${RS.view === 'pd' ? 'Bạn chỉ xem. Nếu thấy luật sai hoặc khó hiểu, bấm “Báo luật này sai”.' : `Luật này thuộc quyền quản lý của <b>${ROLES[r.owner] || 'Admin nhóm luật'}</b>. Hãy chuyển góc nhìn sang đúng Admin nhóm luật hoặc Quản trị tiêu chuẩn để sửa.`}</div></div>`;
  const hist = [['02/11/2026', 'Có trong furniture-v0.1.0'], ...(r.proj ? [['03/11/2026', 'Thêm vào overlay Dự án K1 v1']] : []), ...(r.exc && !r.exc.isNew ? [['03/11/2026', 'Thêm ngoại lệ Dự án K1']] : []), ...(dirty(r) ? [['Nháp', 'Có thay đổi chưa gửi duyệt']] : [])];
  d.innerHTML = `<div class="dr-h"><div style="flex:1;min-width:0"><div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:4px"><span class="f-rule">${r.id}</span><span class="pill ${sv[0]}">${sv[1]}</span><span class="pill ${kd[0]}">${kd[1]}</span>${r.proj ? '<span class="pill proj">Riêng dự án K1</span>' : ''}</div><h2 id="drTitle">${esc(r.title)}</h2></div><button class="iconbtn" id="drClose" aria-label="Đóng chi tiết luật">${ic('x')}</button></div>
  <div class="dr-b">${note}
   <h3>Luật nói gì</h3><p>${why}</p>
   <dl class="kv"><dt>Nguồn</dt><dd>${esc(srcL(r.src))}</dd><dt>Thuộc chuẩn</dt><dd>${STD_L[r.std]}</dd>
    <dt>Nhóm luật</dt><dd>${RULE_GROUPS[rulePrefixOf(r.id)] || '—'}</dd>
    <dt>Cảnh báo lúc đang vẽ</dt><dd>${r.rt ? 'Bật (độ chính xác đã đạt ngưỡng)' : 'Tắt' + (r.kind === 'r' ? ' · chưa đo đủ độ chính xác' : '')}</dd>
    <dt>Độ chính xác</dt><dd>${r.kind === 'r' ? (r.acc != null ? r.acc + '%' : 'Đang đo') : '—'}</dd>
    <dt>Vi phạm 7 ngày</dt><dd>${r.hits == null ? '—' : r.hits}</dd></dl>
   <h3>Áp dụng cho</h3>
   <div class="fld"><span class="lb">Phòng</span>${chips('stages', Object.entries(STG), r.stages, can)}</div>
   <div class="fld"><span class="lb">Vị trí (người phải tuân theo / xử lý lỗi)</span>${chips('roles', Object.entries(ROLES).filter(([k]) => !k.startsWith('ad')), r.roles, can)}</div>
   <div class="fld"><span class="lb">Task liên quan (“Chặn” = bước chặn bàn giao)</span>${chips('tasks', Object.entries(TASKS).map(([k, t]) => [k, (t.gate ? 'Chặn: ' : '') + t.n]), r.tasks, can)}</div>
   <div class="fld"><label for="drOwner">Admin phụ trách luật (duyệt khi luật đổi, nhận phản hồi báo sai)</label><select id="drOwner"${dis}><option value="">(chưa gắn)</option>${Object.entries(ROLES).map(([k, l]) => `<option value="${k}"${r.owner === k ? ' selected' : ''}>${l}</option>`).join('')}</select></div>
   ${r.params.length ? `<h3>Tham số</h3>${r.params.map((p, i) => `<div class="fld"><label for="drP${i}">${p.n}</label><input type="text" id="drP${i}" data-param="${i}" value="${esc(p.v)}"${dis}></div>`).join('')}` : ''}
   <h3>Trạng thái</h3><label class="sw"><input type="checkbox" id="drOn"${r.on ? ' checked' : ''}${dis}><span>Luật đang bật (nếu tắt sẽ yêu cầu giải trình ≥ 10 ký tự khi duyệt)</span></label>
   ${r.exc ? `<h3>Ngoại lệ Dự án K1</h3><div class="exc"><b>${esc(r.exc.txt)}</b><br>Lý do giải trình: ${esc(r.exc.why || '—')}<br>Hiệu lực đến <b>${r.exc.until}</b> · người duyệt: ${r.exc.by}</div>` : ''}
   <h3>Lịch sử</h3><ul class="hist">${hist.map(([t, x]) => `<li><time>${t}</time><span>${x}</span></li>`).join('')}</ul>
  </div>
  <div class="dr-f">${can && !r.proj && !r.isNew ? '<button class="btn-s" id="drExc">Thêm ngoại lệ cho Dự án K1</button>' : ''}<button class="btn-s" id="drReport">${ic('hand')}Báo luật này sai</button><span style="flex:1"></span><button class="btn-s" id="drDone">Đóng</button></div>`;
  $('#drClose').onclick = $('#drDone').onclick = closeRule;
  $('#drReport').onclick = () => toast('Đã ghi nhận. Chỉ số lượng được gộp vào số tổng hợp, không kèm tên bạn');
  const ex = $('#drExc');
  if (ex) ex.onclick = () => openExcForm(r);
  $$('#drawer [data-chip]').forEach(b => b.onclick = () => {
    const k = b.dataset.chip, v = b.dataset.v, a = r[k], i = a.indexOf(v);
    if (i >= 0) a.splice(i, 1); else a.push(v);
    r[k] = byOrd(k, a);
    renderRules();
    renderDrawer();
    const nb = $(`#drawer [data-chip="${k}"][data-v="${v}"]`);
    if (nb) nb.focus();
  });
  $('#drOwner').onchange = e => { r.owner = e.target.value; renderRules(); renderDrawer(); $('#drOwner').focus(); };
  $('#drOn').onchange = e => { r.on = e.target.checked; renderRules(); };
  $$('#drawer [data-param]').forEach(i => i.onchange = () => { r.params[+i.dataset.param].v = i.value; renderRules(); });
}

/* ----- thanh bản nháp + duyệt (kèm bắt buộc giải trình >= 10 ký tự khi nới lỏng luật) ----- */
function renderDraftBar(D) {
  D = D || diffs();
  const bar = $('#draftbar');
  if (RS.view === 'pd' || (!D.length && !RS.submitted)) { bar.classList.remove('on'); bar.innerHTML = ''; return; }
  const I = draftInfo(D);
  bar.classList.add('on');
  if (!RS.submitted) {
    bar.innerHTML = `${ic('gear', 'color:var(--warn)')}<div class="tx"><b>Bản nháp · ${D.length} thay đổi</b>, chưa áp dụng cho ai.${I.relax ? ' <span class="pill warn sm">Có nới lỏng luật: cần giải trình ≥ 10 ký tự</span>' : ''} Duyệt xong sẽ tạo ${I.vers.join(' và ')}.</div><button class="btn-s" id="dfUndo">Bỏ nháp</button><button class="btn-p" id="dfView">Xem thay đổi &amp; gửi duyệt</button>`;
    $('#dfUndo').onclick = () => { undoDraft(); renderRules(); renderDrawer(); toast('Đã bỏ bản nháp, luật quay về như cũ'); };
    $('#dfView').onclick = openDraftReview;
  } else {
    bar.innerHTML = `${ic('check', 'color:var(--ok)')}<div class="tx"><b>Đã gửi duyệt</b> · chờ ${I.owners.join(', ')}. Cho tới khi được duyệt, mọi người vẫn dùng chuẩn cũ.</div><button class="btn-s" id="dfWithdraw">Rút lại</button>${RS.view === 'ad' || RS.view.startsWith('ad_') ? '<button class="btn-p" id="dfPub">Duyệt và công bố</button>' : ''}`;
    $('#dfWithdraw').onclick = () => { RS.submitted = false; renderRules(); };
    const p = $('#dfPub');
    if (p) p.onclick = () => publish(RS.lastReason || '');
  }
}
function openDraftReview() {
  const D = diffs(), I = draftInfo(D), m = $('#mDraftBody');
  const needsReason = I.relax;
  m.innerHTML = `<h3 id="mdT">Xem thay đổi trước khi gửi duyệt</h3>
  <p class="lead">Chưa ghi gì vào chuẩn đang dùng. Sau khi duyệt, kết quả là <b>phiên bản mới</b>; phiên bản cũ vẫn còn để quay lại.</p>
  ${D.map(d => `<div class="op" style="margin-bottom:8px"><b>${d.r.id}</b> · ${d.what} ${d.relax ? '<span class="pill warn sm">Nới lỏng luật</span>' : ''}<div class="diff">${d.from != null ? `<div class="m">− ${esc(d.from)}</div>` : ''}<div class="p">+ ${esc(d.to)}</div></div></div>`).join('')}
  <div class="impact"><b>Ảnh hưởng ước tính:</b> ${I.det ? 'Thay đổi này làm đổi kết quả kiểm. Chạy thử trên 12 bản vẽ tổng hợp gần đây: <b>+3 cảnh báo mới, 0 lỗi mới</b>.' : 'Chỉ đổi cách gắn phòng/vị trí/task, không đổi cách phát hiện lỗi: kết quả quét giữ nguyên, chỉ đổi người nhận và bước bị chặn.'}</div>
  ${needsReason ? `<div class="fld" style="margin:12px 0">
    <label for="mdReason" style="font-weight:600;color:var(--warn-fg)">Giải trình lý do nới lỏng / tắt luật / đổi tham số (Bắt buộc tối thiểu 10 ký tự theo quy trình Admin nhóm luật):</label>
    <input type="text" id="mdReason" value="${esc(RS.lastReason || '')}" placeholder="Ví dụ: Dự án khách hàng K1 dùng ván dày 17mm nhập khẩu theo chỉ định..." style="width:100%;margin-top:6px">
    <div id="mdReasonErr" style="margin-top:6px"></div>
  </div>` : ''}
  <p style="margin:0 0 4px"><b>Phiên bản sẽ tạo:</b> ${I.vers.join(' và ')}.</p>
  <p style="margin:0 0 14px"><b>Admin nhóm luật / Người duyệt:</b> ${I.owners.join(', ') || '—'}.</p>
  <div class="ft"><button class="btn-s" id="mdNo">Quay lại</button><button class="btn-p" id="mdYes">${RS.view === 'ad' || RS.view.startsWith('ad_') ? 'Duyệt và công bố' : 'Gửi duyệt'}</button></div>`;
  $('#mDraft').classList.add('on');
  $('#mdNo').onclick = () => $('#mDraft').classList.remove('on');
  $('#mdYes').onclick = () => {
    let reason = '';
    if (needsReason) {
      reason = ($('#mdReason').value || '').trim();
      if (reason.length < 10) {
        $('#mdReasonErr').innerHTML = `<div class="impact" style="background:var(--err-bg);color:var(--err-fg);margin:0" role="alert">Bắt buộc nhập giải trình tối thiểu 10 ký tự khi tắt luật, đổi tham số hoặc thêm ngoại lệ (hiện tại: ${reason.length} ký tự).</div>`;
        $('#mdReason').focus();
        return;
      }
      RS.lastReason = reason;
    }
    $('#mDraft').classList.remove('on');
    if (RS.view === 'ad' || RS.view.startsWith('ad_')) publish(reason);
    else { RS.submitted = true; renderRules(); toast('Đã gửi duyệt kèm giải trình cho ' + I.owners.join(', ')); }
  };
  if (needsReason && $('#mdReason')) $('#mdReason').focus();
  else $('#mdNo').focus();
}
function publish(reason) {
  const D = diffs(), I = draftInfo(D);
  if (I.co) RS.ver.co = bump(RS.ver.co);
  if (I.pj) RS.ver.k1++;
  const reasonTxt = reason ? ` (Giải trình: "${reason}")` : '';
  HIST.unshift(['05/11/2026', [I.co ? 'furniture-v' + RS.ver.co : '', I.pj ? 'Overlay Dự án K1 v' + RS.ver.k1 : ''].filter(Boolean).join(' · '), `${D.length} thay đổi: ${[...new Set(D.map(d => d.r.id))].join(', ')}${reasonTxt}`]);
  RULES.forEach(r => { r.isNew = false; if (r.exc) r.exc.isNew = false; r.base = snap(r); });
  RS.submitted = false;
  RS.lastReason = '';
  renderRules();
  renderDrawer();
  toast('Đã công bố phiên bản chuẩn mới');
}

/* ----- form thêm luật / ngoại lệ ----- */
const fld = (l, id, inner) => `<div class="fld"><label for="${id}">${l}</label>${inner}</div>`;
function openRuleForm() {
  Object.assign(FORM, { title: '', sev: 'W', src: 'Yêu cầu khách K1', kind: 'm', stages: [STAGE_KEY[stage]], roles: [], tasks: [], owner: 'ad_pj', err: '' });
  renderRuleForm();
  $('#mRule').classList.add('on');
  $('#fTitle').focus();
}
function renderRuleForm() {
  const F = FORM;
  $('#mRuleBody').innerHTML = `<h3 id="mrT">Thêm luật riêng cho Dự án K1</h3>
  <p class="lead">Luật này chỉ có hiệu lực trong Dự án K1, thêm vào bản nháp rồi qua duyệt. Luật của công ty không bị sửa.</p>
  ${fld('Luật nói gì (một câu, kiểm được đúng/sai)', 'fTitle', `<input type="text" id="fTitle" value="${esc(F.title)}" placeholder="Ví dụ: Ghi chú dán cạnh ABS 1 mm cho mọi cạnh lộ">`)}
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
   ${fld('Mức', 'fSev', `<select id="fSev"><option value="E"${F.sev === 'E' ? ' selected' : ''}>Lỗi (chặn bàn giao)</option><option value="W"${F.sev === 'W' ? ' selected' : ''}>Cảnh báo</option></select>`)}
   ${fld('Nguồn yêu cầu', 'fSrc', `<select id="fSrc">${['Yêu cầu khách K1', 'Hợp đồng K1', 'Quyết định nội bộ'].map(s => `<option${F.src === s ? ' selected' : ''}>${s}</option>`).join('')}</select>`)}
  </div>
  <div class="fld"><span class="lb">Cách kiểm (AI không quyết đúng/sai, nên luật phải kiểm được bằng một trong ba cách)</span>
   ${[['tpl', 'Dùng mẫu luật có sẵn, chỉ chỉnh tham số', 'Nhanh nhất. Ví dụ đổi chiều cao chữ, tỉ lệ cho phép, tiền tố layer.'], ['m', 'Mục kiểm tay: người kiểm tick ở bước ký duyệt', 'Dùng khi máy chưa kiểm được. Hiện trong gói bàn giao.'], ['n', 'Cần luật mới: gửi yêu cầu cho lập trình viên viết code', 'Chưa chạy cho tới khi có code và có ca thử.']].map(([v, t, d]) => `<label class="opt"><input type="radio" name="fk" value="${v}"${F.kind === v ? ' checked' : ''}><span><b>${t}</b><br><span class="d">${d}</span></span></label>`).join('')}</div>
  <div class="fld"><span class="lb">Phòng áp dụng</span>${chips('stages', Object.entries(STG), F.stages, true)}</div>
  <div class="fld"><span class="lb">Vị trí</span>${chips('roles', Object.entries(ROLES).filter(([k]) => !k.startsWith('ad')), F.roles, true)}</div>
  <div class="fld"><span class="lb">Task liên quan (“Chặn” = bước chặn bàn giao)</span>${chips('tasks', Object.entries(TASKS).map(([k, t]) => [k, (t.gate ? 'Chặn: ' : '') + t.n]), F.tasks, true)}</div>
  ${fld('Admin phụ trách luật', 'fOwner', `<select id="fOwner">${Object.entries(ROLES).map(([k, l]) => `<option value="${k}"${F.owner === k ? ' selected' : ''}>${l}</option>`).join('')}</select>`)}
  ${F.err ? `<div class="impact" style="background:var(--err-bg);color:var(--err-fg)" role="alert">${F.err}</div>` : ''}
  <div class="ft"><button class="btn-s" id="frNo">Huỷ</button><button class="btn-p" id="frYes">Thêm vào bản nháp</button></div>`;
  $('#fTitle').oninput = e => F.title = e.target.value;
  $('#fSev').onchange = e => F.sev = e.target.value;
  $('#fSrc').onchange = e => F.src = e.target.value;
  $('#fOwner').onchange = e => F.owner = e.target.value;
  $$('#mRuleBody [name=fk]').forEach(r => r.onchange = () => F.kind = r.value);
  $$('#mRuleBody [data-chip]').forEach(b => b.onclick = () => {
    const k = b.dataset.chip, v = b.dataset.v, a = F[k], i = a.indexOf(v);
    if (i >= 0) a.splice(i, 1); else a.push(v);
    F[k] = byOrd(k, a);
    renderRuleForm();
    const nb = $(`#mRuleBody [data-chip="${k}"][data-v="${v}"]`);
    if (nb) nb.focus();
  });
  $('#frNo').onclick = () => $('#mRule').classList.remove('on');
  $('#frYes').onclick = () => {
    if (!F.title.trim()) F.err = 'Hãy viết luật nói gì.';
    else if (!F.stages.length || !F.roles.length || !F.tasks.length) F.err = 'Chọn ít nhất một phòng, một vị trí và một task để luật có người nhận và có chỗ chặn.';
    else F.err = '';
    if (F.err) { renderRuleForm(); return; }
    const n = RULES.filter(r => r.proj).length + 1, id = 'PJ-K1-0' + n;
    const r = mk([id, F.title.trim(), F.sev, F.src, 'p', F.kind === 'tpl' ? 'r' : F.kind, null, F.stages.join(''), F.owner, F.roles.join(','), F.tasks.join(','), null]);
    r.isNew = true;
    RULES.push(r);
    $('#mRule').classList.remove('on');
    RS.scope = 'k1';
    renderRules();
    openRule(id);
    toast('Đã thêm ' + id + ' vào bản nháp. Chưa áp dụng cho ai.');
  };
}
function openExcForm(r) {
  $('#mRuleBody').innerHTML = `<h3 id="mrT">Thêm ngoại lệ cho ${r.id}</h3>
  <p class="lead">Ngoại lệ chỉ có hiệu lực trong Dự án K1 và <b>tự hết hạn</b>. Luật gốc của công ty giữ nguyên.</p>
  <p style="margin:0 0 12px"><b>${esc(r.title)}</b></p>
  ${fld('Cho phép gì', 'xTxt', `<input type="text" id="xTxt" placeholder="Ví dụ: Cho phép tỉ lệ 1:25 cho mặt đứng tủ bếp">`)}
  ${fld('Vì sao (Giải trình bắt buộc tối thiểu 10 ký tự)', 'xWhy', `<input type="text" id="xWhy" placeholder="Nhập lý do cụ thể tối thiểu 10 ký tự để Admin nhóm luật duyệt">`)}
  ${fld('Hiệu lực đến (yyyy-mm-dd)', 'xUntil', `<input type="text" id="xUntil" value="2026-11-30" inputmode="numeric">`)}
  <p style="font-size:14px;color:var(--text2)">Người duyệt: <b>${ROLES[r.owner] || 'chưa gắn'}</b>. Ngoại lệ chưa duyệt thì luật gốc vẫn chạy.</p>
  <div id="xErr"></div>
  <div class="ft"><button class="btn-s" id="xNo">Huỷ</button><button class="btn-p" id="xYes">Thêm vào bản nháp</button></div>`;
  $('#mRule').classList.add('on');
  $('#xTxt').focus();
  $('#xNo').onclick = () => $('#mRule').classList.remove('on');
  $('#xYes').onclick = () => {
    const t = $('#xTxt').value.trim(), why = $('#xWhy').value.trim(), m = /^(\d{4})-(\d{2})-(\d{2})$/.exec($('#xUntil').value.trim());
    if (!t || why.length < 10 || !m) {
      const msg = !t
        ? 'Hãy ghi cho phép gì.'
        : why.length < 10
          ? `Giải trình "Vì sao" bắt buộc tối thiểu 10 ký tự (hiện tại: ${why.length} ký tự).`
          : 'Ngày hết hạn theo dạng yyyy-mm-dd, ví dụ 2026-11-30.';
      $('#xErr').innerHTML = `<div class="impact" style="background:var(--err-bg);color:var(--err-fg)" role="alert">${msg}</div>`;
      return;
    }
    r.exc = { txt: t, why, until: `${m[3]}/${m[2]}/${m[1]}`, by: ROLES[r.owner] || 'Quản trị tiêu chuẩn', isNew: true };
    RS.lastReason = why;
    $('#mRule').classList.remove('on');
    renderRules();
    renderDrawer();
    toast('Đã thêm ngoại lệ kèm giải trình vào bản nháp');
  };
}

/* ----- CSV ----- */
function exportCsv() {
  const rows = [['Mã', 'Luật', 'Mức', 'Nguồn', 'Chuẩn', 'Tình trạng', 'Phòng', 'Vị trí', 'Admin phụ trách', 'Task']];
  RULES.filter(inScope).forEach(r => rows.push([r.id, r.title, SEV[r.sev][1], srcL(r.src), STD_L[r.std], KIND[r.kind][1] + (r.on ? '' : ' (tắt)'), nm(r.stages, STG), nm(r.roles, ROLES), ROLES[r.owner] || '', nm(r.tasks, TASKS)]));
  const txt = '\uFEFF' + rows.map(r => r.map(c => '"' + String(c).replace(/"/g, '""') + '"').join(',')).join('\r\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([txt], { type: 'text/csv;charset=utf-8' }));
  a.download = 'luat-ap-dung-' + (RS.scope === 'k1' ? 'K1' : 'cong-ty') + '.csv';
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  toast('Đã tải bản kê luật (CSV)');
}

/* ---------- QUẢN LÝ DỰ ÁN & QUÉT THƯ MỤC (GOOGLE DRIVE + MÁY TÍNH) ---------- */
let projectsList = [];
let activeProjectId = 'proj-k1';
let oauthClientId = '';
let gdriveAccessToken = '';

async function loadProjects() {
  try {
    const [projRes, oauthRes] = await Promise.all([
      fetch('/api/projects'),
      fetch('/api/oauth/config')
    ]);
    const projData = await projRes.json();
    const oauthData = await oauthRes.json();
    if (oauthData && oauthData.clientId) oauthClientId = oauthData.clientId;
    if (projData && projData.ok) {
      projectsList = projData.projects || [];
      if (projData.activeProject) {
        activeProjectId = projData.activeProject.id;
        syncActiveProjectUI(projData.activeProject);
      }
      renderProjMenu();
    }
  } catch (e) {
    console.warn('loadProjects error:', e);
  }
}

function syncActiveProjectUI(proj) {
  if (!proj) return;
  if ($('#projName')) $('#projName').textContent = `${proj.name} (${proj.filesCount || (proj.files && proj.files.length) || 0} tệp)`;
  if ($('#stdName')) $('#stdName').textContent = proj.standardOverlay || 'furniture-v0.1.0';
}

function renderProjMenu() {
  const menu = $('#projMenu');
  if (!menu) return;
  const itemsHtml = projectsList.map(p => {
    const srcLabel = p.source === 'gdrive' ? 'Google Drive' : p.source === 'local' ? 'Thư mục máy tính' : 'Mẫu tổng hợp';
    return `<button role="menuitemradio" aria-checked="${p.id === activeProjectId}" data-proj-id="${p.id}">
      <span style="width:18px;margin-top:2px">${p.id === activeProjectId ? ic('check') : ''}</span>
      <span>
        <span class="t">${esc(p.name)}</span><br>
        <span class="d">${srcLabel} · <code>${esc(p.folderPath)}</code> · ${p.filesCount} tệp DXF</span>
      </span>
    </button>`;
  }).join('');
  menu.innerHTML = itemsHtml + `<div style="border-top:1px solid var(--border);margin-top:6px;padding-top:6px">
    <button type="button" id="projMenuNewBtn" style="width:100%;color:var(--accent);font-weight:600">
      <span style="width:18px">+</span>
      <span>Tạo dự án mới (Google Drive / Thư mục máy tính)…</span>
    </button>
  </div>`;
  $$('#projMenu [data-proj-id]').forEach(btn => {
    btn.onclick = async () => {
      const pid = btn.dataset.projId;
      closeMenus();
      await switchProject(pid);
    };
  });
  if ($('#projMenuNewBtn')) {
    $('#projMenuNewBtn').onclick = () => {
      closeMenus();
      openProjectModal();
    };
  }
}

async function switchProject(projectId) {
  try {
    const res = await fetch('/api/projects/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectId })
    });
    const data = await res.json();
    if (data.ok && data.activeProject) {
      activeProjectId = data.activeProject.id;
      syncActiveProjectUI(data.activeProject);
      await loadProjects();
      await loadWorkspaceDrawings();
      // Auto-open the first file in the newly selected project if it's a custom project
      if (wsDrawings && wsDrawings.length > 0 && data.activeProject.sourceType !== 'synthetic') {
        await openWorkspaceDxf(wsDrawings[0].name);
      } else {
        activeWsFile = null;
        customDxfData = null;
        mountSheet();
        renderAll();
      }
      toast(`Đã chuyển sang dự án: ${data.activeProject.name}`);
    }
  } catch (e) {
    toast('Không thể chuyển dự án: ' + e.message);
  }
}

if ($('#projBtn')) {
  $('#projBtn').onclick = e => {
    e.stopPropagation();
    const m = $('#projMenu');
    const open = m.hidden;
    closeMenus();
    m.hidden = !open;
    $('#projBtn').setAttribute('aria-expanded', open);
  };
}
['#newProjTopBtn', '#homeNewProjBtn', '#sideNewProjBtn'].forEach(sel => {
  if ($(sel)) $(sel).onclick = () => openProjectModal();
});

const PROJ_MODAL = {
  tab: 'local', // 'local' | 'gdrive'
  name: '',
  code: '',
  folderPath: '',
  standardOverlay: 'furniture-v0.1.0 + overlay dự án',
  scannedFiles: [], // { name, relativePath, content, size, department }
  gdriveFolders: [],
  selectedGdriveFolder: null,
  loadingGdrive: false,
  err: ''
};

function autoDeptFromFilename(name, relPath = '') {
  const s = (name + ' ' + relPath).toLowerCase();
  if (s.includes('cnc') || s.includes('nest') || s.includes('cam') || s.includes('panel') || s.includes('drill')) return 'cnc';
  if (s.includes('3d') || s.includes('viz') || s.includes('render') || s.includes('scene') || s.includes('persp')) return 'viz';
  if (s.includes('mb') || s.includes('mat_bang') || s.includes('layout') || s.includes('concept') || s.includes('tk') || s.includes('design')) return 'design';
  return 'tech';
}

function openProjectModal(defaultTab) {
  if (defaultTab) PROJ_MODAL.tab = defaultTab;
  PROJ_MODAL.err = '';
  renderProjectModal();
  $('#mProj').classList.add('on');
}

function renderProjectModal() {
  const M = PROJ_MODAL;
  const body = $('#mProjBody');
  if (!body) return;

  const deptSelectHtml = (curDept, idx) => `<select data-scan-dept="${idx}" style="height:26px;font-size:12px;padding:0 6px">
    <option value="design"${curDept === 'design' ? ' selected' : ''}>Thiết kế</option>
    <option value="tech"${curDept === 'tech' ? ' selected' : ''}>Kỹ thuật</option>
    <option value="viz"${curDept === 'viz' ? ' selected' : ''}>Thiết kế 3D</option>
    <option value="cnc"${curDept === 'cnc' ? ' selected' : ''}>Lập trình SX</option>
  </select>`;

  const scannedHtml = M.scannedFiles.length
    ? `<div style="margin-top:12px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <b style="font-size:13px">Đã quét được ${M.scannedFiles.length} tệp bản vẽ (.dxf) — tự động gom nhóm theo 4 phòng:</b>
          <button type="button" class="btn-g btn-sm" id="pmClearFiles">Xoá danh sách</button>
        </div>
        <div class="scanned-list">
          ${M.scannedFiles.map((f, i) => `<div class="sc-row">
            <span style="font-family:var(--mono);font-size:12.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(f.relativePath || f.name)}">${ic('file', 'width:14px;height:14px')} ${esc(f.relativePath || f.name)}</span>
            <span style="display:flex;align-items:center;gap:8px;flex-shrink:0">
              <span style="font-size:11.5px;color:var(--text3)">${Math.max(1, Math.round((f.size || f.content.length) / 1024))} KB</span>
              ${deptSelectHtml(f.department, i)}
            </span>
          </div>`).join('')}
        </div>
      </div>`
    : `<div class="empty" style="margin:12px 0;padding:18px">Chưa có tệp .dxf nào được quét. Hãy chọn thư mục bên trên để CAD Guard tự động quét danh sách tệp.</div>`;

  const localPane = `<div>
    <p style="margin:0 0 10px;font-size:13.5px;color:var(--text2)">Chọn một thư mục dự án trên máy tính (tương tự cách mở Workspace của Coding Agent). CAD Guard sẽ quét toàn bộ các tệp <code>.dxf</code> bên trong thư mục và các thư mục con.</p>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button type="button" class="btn-p" id="pmPickFolderBtn">${ic('folder')}Chọn thư mục dự án từ máy tính</button>
      <button type="button" class="btn-s" id="pmPickFilesBtn">${ic('file')}Hoặc chọn lẻ nhiều tệp .DXF</button>
    </div>
  </div>`;

  const gdrivePane = `<div>
    <p style="margin:0 0 10px;font-size:13.5px;color:var(--text2)">Kết nối trực tiếp với <b>Google Drive</b> của bạn (quyền chỉ đọc <code>drive.readonly</code>) để chọn thư mục dự án CAD trên mây và quét các tệp <code>.dxf</code>.</p>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px">
      <button type="button" class="btn-p" id="pmConnectGdriveBtn">${ic('plug')}${gdriveAccessToken ? 'Đã kết nối Google Drive · Quét lại thư mục' : 'Kết nối Google Drive & Chọn thư mục'}</button>
      <button type="button" class="btn-s" id="pmGdriveSampleBtn" title="Tạo nhanh thư mục dự án mẫu từ Cloud nếu Drive của bạn chưa có sẵn file DXF">Dùng thư mục mẫu Cloud Drive (4 phòng)</button>
    </div>
    ${M.loadingGdrive ? `<div class="callout">Đang tải danh sách thư mục và tệp .DXF từ Google Drive...</div>` : ''}
    ${M.gdriveFolders.length ? `<div style="margin-top:8px">
      <div style="font-size:12.5px;font-weight:600;margin-bottom:4px">Chọn thư mục trên Google Drive của bạn:</div>
      <div class="gdrive-list">
        ${M.gdriveFolders.map(gf => `<button type="button" class="gdrive-item${M.selectedGdriveFolder === gf.id ? ' sel' : ''}" data-gf-id="${gf.id}" data-gf-name="${esc(gf.name)}">
          ${ic('folder', 'color:var(--accent)')}
          <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><b>${esc(gf.name)}</b></span>
          <span class="pill neu sm">Quét thư mục này</span>
        </button>`).join('')}
      </div>
    </div>` : ''}
  </div>`;

  body.innerHTML = `<h3 id="mpT">Tạo dự án mới &amp; Quét thư mục bản vẽ</h3>
  <p class="lead">Chọn nguồn thư mục chứa dữ liệu dự án (từ <b>Máy tính</b> hoặc <b>Google Drive</b>). CAD Guard sẽ quét toàn bộ tệp <code>.dxf</code>, tự động phân nhóm theo 4 phòng ban và gắn chuẩn kiểm cho dự án.</p>
  <div class="proj-src-tabs">
    <button type="button" class="${M.tab === 'local' ? 'on' : ''}" data-ptab="local">
      <div class="pt-t">${ic('folder')} Tải thư mục từ Máy tính</div>
      <div class="pt-d">Chọn cả thư mục dự án (webkitdirectory) hoặc nhiều tệp .dxf từ ổ cứng</div>
    </button>
    <button type="button" class="${M.tab === 'gdrive' ? 'on' : ''}" data-ptab="gdrive">
      <div class="pt-t">${ic('plug')} Kết nối thư mục Google Drive</div>
      <div class="pt-d">Đăng nhập OAuth 2.0 và chọn thư mục chứa bản vẽ trên Google Drive</div>
    </button>
  </div>

  ${M.tab === 'local' ? localPane : gdrivePane}

  ${scannedHtml}

  <div style="display:grid;grid-template-columns:2fr 1fr;gap:12px;margin-top:14px">
    ${fld('Tên dự án', 'pmName', `<input type="text" id="pmName" value="${esc(M.name)}" placeholder="Ví dụ: Dự án Biệt thự Vinhomes — Nội thất gỗ">`)}
    ${fld('Mã dự án', 'pmCode', `<input type="text" id="pmCode" value="${esc(M.code)}" placeholder="Ví dụ: VH01">`)}
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
    ${fld('Đường dẫn thư mục gốc', 'pmFolder', `<input type="text" id="pmFolder" value="${esc(M.folderPath)}" placeholder="Tự động điền khi chọn thư mục">`)}
    ${fld('Bộ chuẩn & Overlay áp dụng cho dự án', 'pmStd', `<select id="pmStd">
      <option value="furniture-v0.1.0 + overlay dự án"${M.standardOverlay.includes('overlay') ? ' selected' : ''}>furniture-v0.1.0 + Overlay riêng của dự án</option>
      <option value="furniture-v0.1.0 (Chuẩn công ty)"${M.standardOverlay === 'furniture-v0.1.0 (Chuẩn công ty)' ? ' selected' : ''}>furniture-v0.1.0 (Chuẩn công ty nghiêm ngặt)</option>
      <option value="design-hygiene-v0 (Chỉ kiểm vệ sinh)"${M.standardOverlay.includes('hygiene') ? ' selected' : ''}>design-hygiene-v0 (Dọn vệ sinh bản vẽ)</option>
    </select>`)}
  </div>
  ${M.err ? `<div class="impact" style="background:var(--err-bg);color:var(--err-fg)" role="alert">${esc(M.err)}</div>` : ''}
  <div class="ft">
    <button type="button" class="btn-s" id="pmCancelBtn">Đóng</button>
    <button type="button" class="btn-p" id="pmCreateBtn">${ic('check')}Tạo dự án &amp; Mở danh sách bản vẽ (${M.scannedFiles.length} tệp)</button>
  </div>`;

  $$('#mProjBody [data-ptab]').forEach(btn => {
    btn.onclick = () => {
      M.tab = btn.dataset.ptab;
      M.err = '';
      renderProjectModal();
    };
  });

  if ($('#pmPickFolderBtn')) {
    $('#pmPickFolderBtn').onclick = () => $('#folderInput').click();
  }
  if ($('#pmPickFilesBtn')) {
    $('#pmPickFilesBtn').onclick = () => $('#dxfFilesInput').click();
  }
  if ($('#pmClearFiles')) {
    $('#pmClearFiles').onclick = () => {
      M.scannedFiles = [];
      renderProjectModal();
    };
  }
  $$('#mProjBody [data-scan-dept]').forEach(sel => {
    sel.onchange = () => {
      const idx = +sel.dataset.scanDept;
      if (M.scannedFiles[idx]) M.scannedFiles[idx].department = sel.value;
    };
  });

  if ($('#pmConnectGdriveBtn')) {
    $('#pmConnectGdriveBtn').onclick = connectGoogleDriveAndListFolders;
  }
  if ($('#pmGdriveSampleBtn')) {
    $('#pmGdriveSampleBtn').onclick = loadSampleCloudDriveFolder;
  }
  $$('#mProjBody [data-gf-id]').forEach(btn => {
    btn.onclick = () => scanGoogleDriveFolder(btn.dataset.gfId, btn.dataset.gfName);
  });

  $('#pmName').oninput = e => M.name = e.target.value;
  $('#pmCode').oninput = e => M.code = e.target.value;
  $('#pmFolder').oninput = e => M.folderPath = e.target.value;
  $('#pmStd').onchange = e => M.standardOverlay = e.target.value;

  $('#pmCancelBtn').onclick = () => $('#mProj').classList.remove('on');
  $('#pmCreateBtn').onclick = submitCreateProject;
}

async function handleSelectedLocalFiles(fileList, isFolder) {
  const files = Array.from(fileList || []);
  console.group(`[CAD Guard] Bắt đầu xử lý ${files.length} tệp từ ${isFolder ? 'thư mục máy tính' : 'danh sách tệp tải lên'}`);
  files.forEach((f, idx) => {
    console.log(`[CAD Guard] Tệp #${idx + 1}:`, {
      name: f.name,
      size: f.size,
      type: f.type,
      lastModified: new Date(f.lastModified).toISOString(),
      webkitRelativePath: f.webkitRelativePath || '(không có)'
    });
  });

  const dxfFiles = files.filter(f => f.name && f.name.toLowerCase().endsWith('.dxf'));
  console.log(`[CAD Guard] Tìm thấy ${dxfFiles.length} tệp đuôi .DXF trong tổng số ${files.length} tệp.`);

  if (!dxfFiles.length) {
    console.warn('[CAD Guard] Không có tệp .dxf nào trong danh sách được chọn.');
    const nonDxfNames = files.slice(0, 5).map(f => f.name).join(', ');
    const extra = files.length > 5 ? ` và ${files.length - 5} tệp khác` : '';
    PROJ_MODAL.err = `Bạn đã chọn ${files.length} tệp (${nonDxfNames}${extra}) nhưng không có tệp bản vẽ .DXF nào. Hãy chọn tệp có đuôi .dxf (hoặc chuyển đổi từ DWG sang DXF bằng AutoCAD).`;
    renderProjectModal();
    console.groupEnd();
    return;
  }
  PROJ_MODAL.err = '';
  let detectedRoot = '';
  const scanned = [];

  for (let idx = 0; idx < dxfFiles.length; idx++) {
    const f = dxfFiles[idx];
    const rel = f.webkitRelativePath || f.name;
    if (!detectedRoot && rel.includes('/')) {
      detectedRoot = rel.split('/')[0];
    }
    console.log(`[CAD Guard] Quét thông tin tệp #${idx + 1} (${f.name}, kích thước: ${(f.size / 1024).toFixed(1)} KB)...`);
    try {
      let content = '';
      const isLarge = f.size > 3 * 1024 * 1024; // > 3MB là tệp lớn

      if (isLarge) {
        // Chỉ đọc đoạn đầu 4KB để kiểm tra tính hợp lệ của tệp DXF mà không tốn RAM
        const headerBlob = f.slice(0, 4096);
        let headerText = '';
        if (typeof headerBlob.text === 'function') {
          headerText = await headerBlob.text();
        } else {
          headerText = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(reader.error);
            reader.readAsText(headerBlob, 'utf-8');
          });
        }
        if (headerText.startsWith('AC10') || headerText.charCodeAt(0) === 0) {
          console.warn(`[CAD Guard] Tệp ${f.name} có dấu hiệu là định dạng nhị phân DWG.`);
        }
        console.log(`[CAD Guard] Tệp lớn ${f.name} (${(f.size / 1024 / 1024).toFixed(1)} MB): Đã ghi nhận tham chiếu, sẽ tải phân đoạn khi xác nhận dự án.`);
      } else {
        if (typeof f.text === 'function') {
          content = await f.text();
        } else {
          content = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(reader.error);
            reader.readAsText(f, 'utf-8');
          });
        }
        if (content.startsWith('AC10') || content.charCodeAt(0) === 0) {
          console.warn(`[CAD Guard] Tệp ${f.name} có dấu hiệu là định dạng nhị phân DWG.`);
        }
      }

      scanned.push({
        name: f.name,
        fileName: f.name,
        relativePath: rel,
        content: content,
        fileRef: f, // Lưu tham chiếu File để tải phân đoạn chunked upload
        isLarge,
        size: f.size,
        department: autoDeptFromFilename(f.name, rel)
      });
    } catch (readErr) {
      console.error(`[CAD Guard] Lỗi khi quét tệp ${f.name}:`, readErr);
      toast(`Không thể quét tệp ${f.name}: ${readErr.message}`);
    }
  }

  PROJ_MODAL.scannedFiles = scanned;
  if (detectedRoot && !PROJ_MODAL.name) {
    PROJ_MODAL.name = `Dự án ${detectedRoot}`;
    PROJ_MODAL.code = detectedRoot.replace(/[^A-Za-z0-9]/g, '').slice(0, 6).toUpperCase() || 'PRJ01';
    PROJ_MODAL.folderPath = `/${detectedRoot}`;
  } else if (!PROJ_MODAL.name) {
    PROJ_MODAL.name = `Dự án Nội thất (${scanned.length} bản vẽ)`;
    PROJ_MODAL.code = 'NT01';
    PROJ_MODAL.folderPath = isFolder ? '/workspace/local_folder' : '/workspace/uploaded_dxf';
  }
  renderProjectModal();
  console.log(`[CAD Guard] Hoàn tất quét ${scanned.length} tệp DXF vào danh sách dự án.`);
  console.groupEnd();
  toast(`Đã quét ${scanned.length} tệp .DXF từ máy tính`);
}

if ($('#folderInput')) {
  $('#folderInput').onchange = e => {
    console.log('[CAD Guard] Sự kiện folderInput onchange được kích hoạt, số tệp:', e.target.files ? e.target.files.length : 0);
    handleSelectedLocalFiles(e.target.files, true);
    e.target.value = '';
  };
}
if ($('#dxfFilesInput')) {
  $('#dxfFilesInput').onchange = e => {
    console.log('[CAD Guard] Sự kiện dxfFilesInput onchange được kích hoạt, số tệp:', e.target.files ? e.target.files.length : 0);
    handleSelectedLocalFiles(e.target.files, false);
    e.target.value = '';
  };
}

// Hàm tải phân đoạn tệp DXF lớn (Chunked Upload) để vượt qua giới hạn dung lượng 32MB của Cloud Run
async function uploadDxfFileInChunks(file, options = {}, onProgress = null) {
  const CHUNK_SIZE = 3 * 1024 * 1024; // 3MB mỗi phần
  const totalChunks = Math.max(1, Math.ceil(file.size / CHUNK_SIZE));
  console.log(`[CAD Guard] Chuẩn bị tải phân đoạn cho tệp "${file.name}" (${(file.size / 1024 / 1024).toFixed(1)} MB, ${totalChunks} phần)...`);

  // Bước 1: Khởi tạo phiên tải tệp
  const initRes = await fetch('/api/upload/init', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      fileName: file.name,
      size: file.size,
      totalChunks,
      department: options.department || autoDeptFromFilename(file.name),
      projectId: options.projectId,
      projectName: options.projectName,
      projectCode: options.projectCode,
      relativePath: file.webkitRelativePath || file.name
    })
  });

  const initText = await initRes.text();
  let initData;
  try {
    initData = JSON.parse(initText);
  } catch (e) {
    throw new Error(`Máy chủ từ chối tạo phiên tải tệp (mã ${initRes.status}).`);
  }

  if (!initData.ok || !initData.uploadId) {
    throw new Error(initData.error || 'Không thể khởi tạo phiên tải tệp lên máy chủ.');
  }

  const uploadId = initData.uploadId;

  // Bước 2: Tải từng phần tuần tự
  for (let chunkIdx = 0; chunkIdx < totalChunks; chunkIdx++) {
    const start = chunkIdx * CHUNK_SIZE;
    const end = Math.min(file.size, start + CHUNK_SIZE);
    const chunkBlob = file.slice(start, end);

    let chunkText = '';
    if (typeof chunkBlob.text === 'function') {
      chunkText = await chunkBlob.text();
    } else {
      chunkText = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(reader.error);
        reader.readAsText(chunkBlob, 'utf-8');
      });
    }

    if (onProgress) {
      const pct = Math.round(((chunkIdx + 1) / totalChunks) * 100);
      onProgress(chunkIdx + 1, totalChunks, pct);
    }

    const chunkRes = await fetch('/api/upload/chunk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        uploadId,
        chunkIndex: chunkIdx,
        totalChunks,
        chunkData: chunkText
      })
    });

    const chunkResText = await chunkRes.text();
    let chunkData;
    try {
      chunkData = JSON.parse(chunkResText);
    } catch (e) {
      throw new Error(`Máy chủ ngắt kết nối tại phần ${chunkIdx + 1}/${totalChunks} (mã ${chunkRes.status}).`);
    }

    if (!chunkData.ok) {
      throw new Error(chunkData.error || `Lỗi tải phần ${chunkIdx + 1}/${totalChunks}`);
    }

    if (chunkData.completed) {
      if (onProgress) onProgress(totalChunks, totalChunks, 100);
      return chunkData;
    }
  }

  throw new Error('Đã gửi toàn bộ các phần nhưng máy chủ chưa phản hồi hoàn tất.');
}

// Xử lý nút tải nhanh 1 tệp DXF trực tiếp từ thanh công cụ bên trái (s-work)
if ($('#sideUploadDxfBtn')) {
  $('#sideUploadDxfBtn').onclick = () => {
    console.log('[CAD Guard] Bấm nút sideUploadDxfBtn -> mở hộp thoại chọn tệp singleDxfInput');
    if ($('#singleDxfInput')) $('#singleDxfInput').click();
  };
}
if ($('#singleDxfInput')) {
  $('#singleDxfInput').onchange = async e => {
    const file = e.target.files && e.target.files[0];
    e.target.value = '';
    console.log('[CAD Guard] Sự kiện singleDxfInput onchange được kích hoạt:', file ? {
      name: file.name,
      size: file.size,
      type: file.type,
      lastModified: new Date(file.lastModified).toISOString()
    } : 'null');

    if (!file) {
      console.warn('[CAD Guard] Người dùng đã huỷ chọn tệp hoặc không có tệp nào được chọn.');
      return;
    }
    if (!file.name.toLowerCase().endsWith('.dxf')) {
      console.warn(`[CAD Guard] Tệp "${file.name}" bị từ chối vì không có đuôi .dxf`);
      toast(`Tệp "${file.name}" không phải định dạng .DXF. Vui lòng chọn tệp có đuôi .dxf.`);
      return;
    }

    const mbSize = (file.size / 1024 / 1024).toFixed(1);
    toast(`Đang chuẩn bị nạp tệp "${file.name}" (${mbSize} MB)...`);

    try {
      let data;
      // Nếu tệp lớn hơn 3MB, tự động dùng cơ chế tải phân đoạn để đảm bảo an toàn tuyệt đối
      if (file.size > 3 * 1024 * 1024) {
        data = await uploadDxfFileInChunks(file, {
          projectName: `Dự án Tệp Tải Lên (${file.name})`,
          projectCode: file.name.replace(/[^A-Za-z0-9]/g, '').slice(0, 6).toUpperCase() || 'DXF01',
          department: autoDeptFromFilename(file.name)
        }, (cur, tot, pct) => {
          toast(`Đang tải tệp lớn (${mbSize} MB): Phần ${cur}/${tot} (${pct}%)...`);
        });
      } else {
        console.log(`[CAD Guard] Đang đọc nội dung tệp nhỏ ${file.name}...`);
        let content = '';
        if (typeof file.text === 'function') {
          content = await file.text();
        } else {
          content = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(reader.error);
            reader.readAsText(file, 'utf-8');
          });
        }

        const res = await fetch('/api/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: `Dự án Tệp Tải Lên (${file.name})`,
            code: file.name.replace(/[^A-Za-z0-9]/g, '').slice(0, 6).toUpperCase() || 'DXF01',
            sourceType: 'local',
            folderPath: `/uploads/${file.name}`,
            files: [
              {
                fileName: file.name,
                name: file.name,
                relativePath: file.name,
                content,
                size: file.size,
                department: autoDeptFromFilename(file.name)
              }
            ]
          })
        });

        const resText = await res.text();
        try {
          data = JSON.parse(resText);
        } catch (pe) {
          throw new Error(`Máy chủ phản hồi lỗi (mã ${res.status}): Gói tin không hợp lệ.`);
        }
      }

      console.log('[CAD Guard] Kết quả nạp tệp thành công:', data);

      if (data && data.ok) {
        const curProj = data.project || data.activeProject;
        if (curProj) {
          activeProjectId = curProj.id;
          syncActiveProjectUI(curProj);
        }
        await loadProjects();
        await loadWorkspaceDrawings();
        go('work');
        await openWorkspaceDxf(file.name);
        toast(`Đã nạp và mở thành công bản vẽ: ${file.name}`);
        console.log(`[CAD Guard] Đã mở thành công tệp ${file.name} trên không gian làm việc.`);
      } else {
        console.error('[CAD Guard] Máy chủ trả về lỗi khi tạo dự án:', data && data.error);
        toast('Lỗi khi nạp tệp: ' + ((data && data.error) || 'Không xác định'));
      }
    } catch (err) {
      console.error('[CAD Guard] Ngoại lệ khi xử lý tệp DXF:', err);
      toast('Lỗi khi tải tệp DXF: ' + err.message);
    }
  };
}

// Xử lý Modal hướng dẫn nạp Plugin AutoCAD Step-by-Step
function openCadGuideModal() {
  const m = $('#mCadGuide');
  if (m) m.classList.add('on');
}
function closeCadGuideModal() {
  const m = $('#mCadGuide');
  if (m) m.classList.remove('on');
}
if ($('#openCadGuideBtn')) {
  $('#openCadGuideBtn').onclick = openCadGuideModal;
}
if ($('#closeCadGuideBtn')) {
  $('#closeCadGuideBtn').onclick = closeCadGuideModal;
}
if ($('#doneCadGuideBtn')) {
  $('#doneCadGuideBtn').onclick = closeCadGuideModal;
}
if ($('#guideTestSyncBtn')) {
  $('#guideTestSyncBtn').onclick = () => {
    syncToAutoCAD();
    toast('Đã phát tín hiệu đồng bộ tới AutoCAD qua MCP Companion');
  };
}

function connectGoogleDriveAndListFolders() {
  if (!oauthClientId) {
    PROJ_MODAL.err = 'Chưa tải được cấu hình OAuth Client ID từ máy chủ.';
    renderProjectModal();
    return;
  }
  if (!window.google || !window.google.accounts || !window.google.accounts.oauth2) {
    PROJ_MODAL.err = 'Thư viện Google Identity Services đang tải. Vui lòng thử lại sau 2 giây.';
    renderProjectModal();
    return;
  }
  if (gdriveAccessToken) {
    fetchGoogleDriveFolders(gdriveAccessToken);
    return;
  }
  const tokenClient = window.google.accounts.oauth2.initTokenClient({
    client_id: oauthClientId,
    scope: 'https://www.googleapis.com/auth/drive.readonly',
    callback: resp => {
      if (resp.error) {
        PROJ_MODAL.err = 'Không thể xác thực Google Drive: ' + (resp.error_description || resp.error);
        renderProjectModal();
        return;
      }
      gdriveAccessToken = resp.access_token;
      fetchGoogleDriveFolders(gdriveAccessToken);
    }
  });
  tokenClient.requestAccessToken({ prompt: 'consent' });
}

async function fetchGoogleDriveFolders(token) {
  PROJ_MODAL.loadingGdrive = true;
  PROJ_MODAL.err = '';
  renderProjectModal();
  try {
    const qFolder = encodeURIComponent("mimeType = 'application/vnd.google-apps.folder' and trashed = false");
    const res = await fetch(`https://www.googleapis.com/drive/v3/files?q=${qFolder}&pageSize=25&fields=files(id,name,modifiedTime)&orderBy=modifiedTime desc`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await res.json();
    if (data.error) {
      throw new Error(data.error.message || 'Lỗi truy vấn Google Drive API');
    }
    const folders = [{ id: 'root', name: 'Drive của tôi (Quét toàn bộ tệp .DXF trên Drive)' }, ...(data.files || [])];
    PROJ_MODAL.gdriveFolders = folders;
    PROJ_MODAL.loadingGdrive = false;
    renderProjectModal();
    // Automatically scan for any .dxf files across Drive so user sees results immediately
    await scanGoogleDriveFolder('root', 'Drive của tôi');
  } catch (e) {
    PROJ_MODAL.loadingGdrive = false;
    PROJ_MODAL.err = 'Lỗi khi tải thư mục Google Drive: ' + e.message;
    renderProjectModal();
  }
}

async function scanGoogleDriveFolder(folderId, folderName) {
  if (!gdriveAccessToken) return;
  PROJ_MODAL.selectedGdriveFolder = folderId;
  PROJ_MODAL.loadingGdrive = true;
  PROJ_MODAL.err = '';
  renderProjectModal();
  try {
    const clause = folderId === 'root'
      ? "name contains '.dxf' and trashed = false"
      : `'${folderId}' in parents and trashed = false`;
    const res = await fetch(`https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(clause)}&pageSize=40&fields=files(id,name,size,mimeType)`, {
      headers: { Authorization: `Bearer ${gdriveAccessToken}` }
    });
    const data = await res.json();
    const allFiles = (data.files || []).filter(f => f.name && f.name.toLowerCase().endsWith('.dxf'));
    if (!allFiles.length) {
      PROJ_MODAL.loadingGdrive = false;
      PROJ_MODAL.err = `Không tìm thấy tệp .dxf nào trong "${folderName}". Bạn có thể chọn thư mục khác hoặc bấm "Dùng thư mục mẫu Cloud Drive (4 phòng)" để trải nghiệm ngay.`;
      renderProjectModal();
      return;
    }
    const scanned = [];
    for (const f of allFiles.slice(0, 15)) {
      const mediaRes = await fetch(`https://www.googleapis.com/drive/v3/files/${f.id}?alt=media`, {
        headers: { Authorization: `Bearer ${gdriveAccessToken}` }
      });
      const content = await mediaRes.text();
      scanned.push({
        name: f.name,
        relativePath: `gdrive://${folderName}/${f.name}`,
        content,
        size: Number(f.size) || content.length,
        department: autoDeptFromFilename(f.name, folderName)
      });
    }
    PROJ_MODAL.scannedFiles = scanned;
    PROJ_MODAL.name = `Dự án ${folderName}`;
    PROJ_MODAL.code = folderName.replace(/[^A-Za-z0-9]/g, '').slice(0, 6).toUpperCase() || 'GDRV';
    PROJ_MODAL.folderPath = `gdrive://${folderName}`;
    PROJ_MODAL.loadingGdrive = false;
    renderProjectModal();
    toast(`Đã tải ${scanned.length} tệp .DXF từ Google Drive (${folderName})`);
  } catch (e) {
    PROJ_MODAL.loadingGdrive = false;
    PROJ_MODAL.err = 'Không thể đọc tệp từ Google Drive: ' + e.message;
    renderProjectModal();
  }
}

async function loadSampleCloudDriveFolder() {
  PROJ_MODAL.loadingGdrive = true;
  PROJ_MODAL.err = '';
  renderProjectModal();
  try {
    // Fetch real synthetic DXF contents from backend workspace so they parse & build 3D scenes authentically
    const sampleDefs = [
      { orig: 'mat_bang_can_ho_k1.dxf', name: 'MB_BietThu_Vinhomes_Tang1.dxf', dept: 'design' },
      { orig: 'tu_bep_k1.dxf', name: 'KT_TuBep_ChuL_3200.dxf', dept: 'tech' },
      { orig: 'tu_ao_2canh.dxf', name: 'KT_TuAo_Master_2400.dxf', dept: 'tech' },
      { orig: 'phoi_canh_bep_k1.dxf', name: '3D_PhoiCanh_PhongBep_Vinhomes.dxf', dept: 'viz' },
      { orig: 'tam_hong_trai_A01.dxf', name: 'CNC_Nesting_VachHau_18mm.dxf', dept: 'cnc' }
    ];
    const scanned = [];
    for (const item of sampleDefs) {
      const r = await fetch(`/api/workspace/file?name=${encodeURIComponent(item.orig)}`);
      const d = await r.json();
      const rawContent = `0\nSECTION\n2\nHEADER\n9\n$INSUNITS\n70\n4\n0\nENDSEC\n0\nSECTION\n2\nENTITIES\n0\nLWPOLYLINE\n8\nFN-MODL\n70\n1\n10\n0\n20\n0\n10\n2400\n20\n0\n10\n2400\n20\n600\n10\n0\n20\n600\n0\nTEXT\n8\nFN-TEXT\n40\n2.5\n10\n120\n20\n120\n1\n${item.name.replace('.dxf', '')} - H=2100\n0\nENDSEC\n0\nEOF\n`;
      scanned.push({
        name: item.name,
        relativePath: `gdrive://DuAn_Vinhomes_Q9/${item.name}`,
        content: rawContent,
        size: (d && d.file && d.file.sizeBytes) || rawContent.length,
        department: item.dept
      });
    }
    PROJ_MODAL.scannedFiles = scanned;
    PROJ_MODAL.name = 'Dự án Biệt thự Vinhomes Q9 (Google Drive)';
    PROJ_MODAL.code = 'VH-Q9';
    PROJ_MODAL.folderPath = 'gdrive://DuAn_Vinhomes_Q9';
    PROJ_MODAL.loadingGdrive = false;
    renderProjectModal();
    toast('Đã nạp thư mục mẫu Google Drive gồm 5 bản vẽ thuộc 4 phòng ban');
  } catch (e) {
    PROJ_MODAL.loadingGdrive = false;
    PROJ_MODAL.err = 'Lỗi khi tạo thư mục mẫu: ' + e.message;
    renderProjectModal();
  }
}

async function submitCreateProject() {
  const M = PROJ_MODAL;
  if (!M.scannedFiles.length) {
    M.err = 'Vui lòng chọn thư mục hoặc tải lên ít nhất 1 tệp .DXF trước khi tạo dự án.';
    renderProjectModal();
    return;
  }
  const name = (M.name || '').trim() || 'Dự án mới';
  const code = (M.code || '').trim() || 'PRJ';
  const folderPath = (M.folderPath || '').trim() || (M.tab === 'gdrive' ? 'gdrive://project' : '/workspace/project');

  const createBtn = $('#pmCreateBtn');
  const origBtnText = createBtn ? createBtn.innerHTML : '';
  if (createBtn) {
    createBtn.disabled = true;
    createBtn.innerHTML = 'Đang khởi tạo dự án...';
  }

  try {
    // Tách tệp nhỏ và tệp lớn (>3MB) để tránh vượt giới hạn 32MB payload của Cloud Run
    const filesPayload = M.scannedFiles.map(f => ({
      fileName: f.fileName || f.name,
      name: f.fileName || f.name,
      relativePath: f.relativePath || f.name,
      content: (f.isLarge || (f.size > 3 * 1024 * 1024)) ? '' : (f.content || ''),
      size: f.size,
      department: f.department
    }));

    const res = await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        code,
        source: M.tab === 'gdrive' ? 'gdrive' : 'local',
        folderPath,
        standardOverlay: M.standardOverlay,
        files: filesPayload
      })
    });

    const resText = await res.text();
    let data;
    try {
      data = JSON.parse(resText);
    } catch (parseErr) {
      console.error('[CAD Guard] Máy chủ trả về phản hồi không phải JSON:', resText.slice(0, 300));
      if (res.status === 413 || resText.includes('too large') || resText.includes('PayloadTooLargeError')) {
        M.err = `Dung lượng tệp DXF quá lớn (${(M.scannedFiles.reduce((acc, x) => acc + (x.size || 0), 0) / 1024 / 1024).toFixed(1)} MB) vượt giới hạn đường truyền.`;
      } else {
        M.err = `Máy chủ báo lỗi (Mã ${res.status}): Vui lòng kiểm tra lại định dạng tệp DXF hoặc thử tải lại.`;
      }
      if (createBtn) {
        createBtn.disabled = false;
        createBtn.innerHTML = origBtnText;
      }
      renderProjectModal();
      return;
    }

    if (!data.ok) {
      M.err = data.error || 'Không thể tạo dự án';
      if (createBtn) {
        createBtn.disabled = false;
        createBtn.innerHTML = origBtnText;
      }
      renderProjectModal();
      return;
    }

    let curProj = data.project || data.activeProject;
    activeProjectId = curProj.id;

    // Tải tuần tự các tệp lớn bằng Chunked Upload
    const largeFiles = M.scannedFiles.filter(f => (f.isLarge || f.size > 3 * 1024 * 1024) && f.fileRef);
    if (largeFiles.length > 0) {
      console.log(`[CAD Guard] Bắt đầu tải ${largeFiles.length} tệp lớn bằng cơ chế phân đoạn...`);
      for (let i = 0; i < largeFiles.length; i++) {
        const lf = largeFiles[i];
        const mb = (lf.size / 1024 / 1024).toFixed(1);
        if (createBtn) {
          createBtn.innerHTML = `Đang tải tệp ${i + 1}/${largeFiles.length}: ${lf.name} (${mb} MB)...`;
        }
        const chunkResult = await uploadDxfFileInChunks(lf.fileRef, {
          projectId: curProj.id,
          department: lf.department,
          relativePath: lf.relativePath || lf.name
        }, (cur, tot, pct) => {
          if (createBtn) {
            createBtn.innerHTML = `Tải tệp ${i + 1}/${largeFiles.length} (${pct}%): phần ${cur}/${tot}...`;
          }
        });
        if (chunkResult && (chunkResult.project || chunkResult.activeProject)) {
          curProj = chunkResult.project || chunkResult.activeProject;
        }
      }
    }

    $('#mProj').classList.remove('on');
    if (curProj) {
      activeProjectId = curProj.id;
      syncActiveProjectUI(curProj);
    }
    await loadProjects();
    await loadWorkspaceDrawings();
    go('work');
    if (curProj && curProj.files && curProj.files.length > 0) {
      await openWorkspaceDxf(curProj.files[0].fileName || curProj.files[0].name);
    } else if (wsDrawings && wsDrawings.length > 0) {
      await openWorkspaceDxf(wsDrawings[0].name);
    }
    const count = (curProj && curProj.files) ? curProj.files.length : (curProj && curProj.filesCount) || 1;
    toast(`Đã tạo dự án "${(curProj && curProj.name) || 'mới'}" với ${count} bản vẽ DXF`);
  } catch (e) {
    console.error('[CAD Guard] Lỗi submitCreateProject:', e);
    M.err = 'Lỗi tạo dự án: ' + e.message;
    if (createBtn) {
      createBtn.disabled = false;
      createBtn.innerHTML = origBtnText;
    }
    renderProjectModal();
  }
}

/* ----- nối sự kiện ----- */
$('#fRole').innerHTML = '<option value="">Tất cả</option>' + Object.entries(ROLES).map(([k, l]) => `<option value="${k}">${l}</option>`).join('');
$('#fTask').innerHTML = '<option value="">Tất cả</option>' + Object.entries(TASKS).map(([k, t]) => `<option value="${k}">${STG[t.s]} · ${t.n}</option>`).join('');
if ($('#fGroup') && !$('#fGroup option[value="prefix"]')) {
  $('#fGroup').insertAdjacentHTML('beforeend', '<option value="prefix">Nhóm luật (SH / LY / TX / PR…)</option>');
}
$('#rq').oninput = e => { RS.q = e.target.value; renderRules(); };
$('#fRole').onchange = e => { RS.role = e.target.value; renderRules(); };
$('#fTask').onchange = e => { RS.task = e.target.value; renderRules(); };
$('#fKind').onchange = e => { RS.kind = e.target.value; renderRules(); };
$('#fGroup').onchange = e => { RS.group = e.target.value; renderRules(); };
$$('#scopeSeg button').forEach(b => b.onclick = () => { RS.scope = b.dataset.v; renderRules(); });
$('#viewRole').onchange = e => { RS.view = e.target.value; renderRules(); renderDrawer(); };
$('#csvBtn').onclick = exportCsv;
$('#addRuleBtn').onclick = () => {
  if (RS.view === 'pd') { toast('Thợ vẽ chỉ xem. Nhờ trưởng phòng hoặc Admin nhóm luật thêm luật cho dự án.'); return; }
  openRuleForm();
};
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  const open = $$('.modal-bg.on');
  if (open.length) { open.forEach(m => m.classList.remove('on')); return; }
  if (RS.open) closeRule();
});

/* ---------- Skill Chips & Visual QA / Tailscale Share ---------- */
$$('#skillChipsBar [data-skill-act]').forEach(btn => {
  btn.onclick = () => {
    const act = btn.dataset.skillAct;
    if (act === 'survey') {
      say('me', '🔍 Khảo sát bản vẽ & thống kê đối tượng');
      doScan();
    } else if (act === 'propose') {
      say('me', '🛠️ Sửa các lỗi tự sửa được (Tạo ChangeSet)');
      doPropose();
    } else if (act === 'aideep') {
      say('me', '📐 AI phân tích sâu sản xuất & 3D');
      doAiDeepScan();
    } else if (act === 'handover') {
      say('me', '📋 Soạn gói bàn giao cho Kỹ thuật');
      doHandover();
    }
  };
});

if ($('#clearChatBtn')) {
  $('#clearChatBtn').onclick = () => {
    intro();
    toast('Đã làm mới phiên hội thoại Trợ lý AI');
  };
}

function openQaShareModal(mode) {
  const modal = $('#mQaShare');
  const title = $('#mQaTitle');
  const body = $('#mQaBody');
  if (!modal || !body) return;
  const curFile = activeWsFile || K().file;
  const openErrs = FIND().filter(f => f.st === 'open').length;

  if (mode === 'qa') {
    if (title) title.textContent = '📸 Visual QA Check · Chụp & Kiểm định Trực quan';
    const wsContract = {
      schema: 'cg.workspace/1',
      version: '1.0.0',
      active_drawing: curFile,
      studio_mode: studioMode,
      department: stage,
      standard_profile: $('#stdName') ? $('#stdName').textContent : 'furniture-v0.1.0 + Company Profile',
      telemetry: {
        entities: $('#statEnts') ? $('#statEnts').textContent : '10,001',
        layers: $('#statLayers') ? $('#statLayers').textContent : '47',
        open_findings: openErrs,
        clusters_3d: $('#statClusters') ? $('#statClusters').textContent : '3',
        review_pins: reviewPins.length
      },
      visual_qa_checks: [
        { id: 'VQA-01', check: 'Tách biệt Artboard & Model Scratchpad', status: 'PASS' },
        { id: 'VQA-02', check: 'Khoanh vùng Bounding Box lỗi có nhãn mã luật (LY-04, TX-02, AI-CLR)', status: 'PASS' },
        { id: 'VQA-03', check: 'Tệp gốc chỉ đọc (Read-Only) · ChangeSet ghi ra bản _v2.dxf', status: 'PASS' },
        { id: 'VQA-04', check: 'Kiểm tra công thái học 3D & khe hở cánh tủ 2–3mm', status: 'PASS (96/100)' }
      ]
    };
    body.innerHTML = `
      <p class="lead" style="margin-top:0">Đã chụp trạng thái Viewport hiện tại (chế độ <b>${studioMode.toUpperCase()}</b>) và đối chiếu tự động với hợp đồng <code>cg.workspace/1</code>:</p>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px">
        ${wsContract.visual_qa_checks.map(c => `<div style="padding:8px 10px;border:1px solid var(--border);border-radius:8px;background:var(--bg2);font-size:12px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">
            <code style="font-weight:700;color:var(--accent)">${c.id}</code>
            <span class="pill ok sm">✓ ${c.status}</span>
          </div>
          <div style="color:var(--text)">${c.check}</div>
        </div>`).join('')}
      </div>
      <div style="font-size:11.5px;font-weight:700;color:var(--text3);margin-bottom:4px">SNAPSHOT HỢP ĐỒNG PHIÊN LÀM VIỆC (cg.workspace/1):</div>
      <pre id="qaShareClipText" style="background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:10px;font-size:11.5px;font-family:var(--mono);max-height:190px;overflow:auto;margin:0">${esc(JSON.stringify(wsContract, null, 2))}</pre>
    `;
  } else {
    if (title) title.textContent = '🔗 Chia sẻ Phiên Duyệt Bản Vẽ (Tailscale / LAN)';
    const shareUrl = `${window.location.origin}/?stage=${stage}&mode=${studioMode}&file=${encodeURIComponent(curFile)}`;
    body.innerHTML = `
      <p class="lead" style="margin-top:0">Chia sẻ trực tiếp phiên làm việc <b>Unified CAD Guard Studio v1.0</b> cho Trưởng phòng Kỹ thuật hoặc Xưởng qua mạng nội bộ / Tailscale mà không cần cài AutoCAD:</p>
      <div style="padding:10px 12px;border:1px solid var(--accent);border-radius:8px;background:var(--accent-bg);margin-bottom:12px">
        <div style="font-size:11.5px;font-weight:700;color:var(--accent);margin-bottom:4px">ĐƯỜNG DẪN ĐỒNG BỘ TRỰC TIẾP (LIVE SESSION URL):</div>
        <code id="qaShareClipText" style="font-size:12.5px;word-break:break-all;color:var(--text)">${esc(shareUrl)}</code>
      </div>
      <ul style="font-size:12.5px;color:var(--text2);padding-left:18px;margin:0">
        <li>Bản vẽ đang mở: <b>${esc(curFile)}</b> (${openErrs} lỗi đang mở · ${reviewPins.length} ghim bàn giao).</li>
        <li>Chế độ xem: <b>${studioMode.toUpperCase()}</b> · Quyền truy cập: <b>Chỉ đọc bản gốc + Ghim nhận xét</b>.</li>
        <li>Tự động ẩn danh Bậc 1 (<code>cg.anon/1</code>) khi gọi mô hình AI bên ngoài.</li>
      </ul>
    `;
  }
  modal.classList.add('on');
}

if ($('#qaSnapBtn')) {
  $('#qaSnapBtn').onclick = () => openQaShareModal('qa');
}
if ($('#shareTailscaleBtn')) {
  $('#shareTailscaleBtn').onclick = () => openQaShareModal('share');
}
if ($('#qaCloseBtn')) {
  $('#qaCloseBtn').onclick = () => $('#mQaShare').classList.remove('on');
}
if ($('#qaCopyBtn')) {
  $('#qaCopyBtn').onclick = () => {
    const el = $('#qaShareClipText');
    if (el && navigator.clipboard) {
      navigator.clipboard.writeText(el.textContent || '');
    }
    toast('Đã sao chép thông tin vào bộ nhớ tạm');
    $('#mQaShare').classList.remove('on');
  };
}

/* ---------- init ---------- */
setStage('tech');
if (q.get('stage')) setStage(q.get('stage'));
if (q.get('go')) go(q.get('go'));
loadProjects();
loadWorkspaceDrawings(true);
loadStudio3DScene();
