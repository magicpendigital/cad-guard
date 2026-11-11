/* cad-guard app — JS thuần, không thư viện, không tài nguyên ngoài. Bố cục, chữ và tên màn theo bản mẫu chốt
 * design/ui-mockup.html; dữ liệu lấy từ API cục bộ (không có số minh hoạ).
 * An toàn: mọi dữ liệu chèn bằng textContent/createElement (không chèn chuỗi HTML); mọi API gửi header X-CadGuard-Token;
 * không có mã/kiểu nội tuyến (CSP); khoá API chỉ gửi đi một chiều, ô nhập bị xoá ngay sau khi gửi.
 */
"use strict";
(() => {
  // ---------- biểu tượng (SVG dựng bằng DOM, nét theo bản mẫu) ----------
  const ICONS = {
    shield: [["path", "M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"], ["path", "M9 12l2 2 4-4"]],
    home: [["path", "M4 11l8-7 8 7v9H4z"], ["path", "M10 20v-6h4v6"]],
    pen: [["path", "M4 20h4L19 9l-4-4L4 16z"], ["path", "M13.5 6.5l4 4"]],
    bars: [["path", "M4 20V10M10 20V4M16 20v-7M22 20H2"]],
    list: [["path", "M9 6h11M9 12h11M9 18h11"], ["path", "M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2"]],
    plug: [["path", "M9 7V3M15 7V3M7 7h10v4a5 5 0 01-10 0zM12 16v5"]],
    lock: [["rect", {x: 5, y: 11, width: 14, height: 9, rx: 2}], ["path", "M8 11V8a4 4 0 018 0v3"]],
    building: [["path", "M3 21h18M5 21V8l7-5 7 5v13M9 21v-6h6v6"]],
    bot: [["rect", {x: 4, y: 7, width: 16, height: 12, rx: 3}], ["path", "M12 3v4M9 13h.01M15 13h.01"]],
    chev: [["path", "M6 9l6 6 6-6"]],
    chat: [["path", "M21 12a8 8 0 01-11.5 7.2L4 20l1-4.6A8 8 0 1121 12z"]],
    alert: [["path", "M12 3l10 18H2z"], ["path", "M12 10v5M12 18h.01"]],
    alertc: [["path", "M12 8v5M12 17h.01"], ["circle", {cx: 12, cy: 12, r: 9}]],
    branch: [["path", "M7 4v12a3 3 0 003 3h7M17 4v8M14 7l3-3 3 3"]],
    send: [["path", "M4 12l16-8-6 16-3-7z"]],
    stop: [["rect", {x: 6, y: 6, width: 12, height: 12, rx: 2}]],
    check: [["path", "M5 12l5 5 9-10"]],
    x: [["path", "M6 6l12 12M18 6L6 18"]],
    info: [["circle", {cx: 12, cy: 12, r: 9}], ["path", "M12 11v5M12 8h.01"]],
    file: [["path", "M7 3h7l5 5v13H7z"], ["path", "M14 3v5h5"]],
    sun: [["circle", {cx: 12, cy: 12, r: 4}], ["path", "M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"]],
    moon: [["path", "M20 14A8 8 0 0110 4a8 8 0 1010 10z"]],
    gear: [["circle", {cx: 12, cy: 12, r: 3}], ["path", "M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"]],
    copy: [["rect", {x: 8, y: 8, width: 12, height: 12, rx: 2}], ["path", "M4 16V6a2 2 0 012-2h10"]],
    undo: [["path", "M9 14L4 9l5-5"], ["path", "M4 9h10a6 6 0 010 12h-3"]],
    search: [["circle", {cx: 11, cy: 11, r: 7}], ["path", "M21 21l-4.3-4.3"]],
    hand: [["path", "M8 13V6a1.5 1.5 0 013 0v5M11 11V4.5a1.5 1.5 0 013 0V11M14 11V6a1.5 1.5 0 013 0v8a6 6 0 01-6 6h-1a5 5 0 01-4-2l-3-4a1.5 1.5 0 012.3-1.9L8 14"]],
    inbox: [["path", "M4 13l2-8h12l2 8v6H4z"], ["path", "M4 13h5l1 2h4l1-2h5"]],
    arrow: [["path", "M5 12h14M13 6l6 6-6 6"]],
    users: [["circle", {cx: 9, cy: 8, r: 3.5}], ["path", "M2.5 20a6.5 6.5 0 0113 0M16 4.5a3.5 3.5 0 010 7M18 14a6 6 0 013.5 6"]],
    folder: [["path", "M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"]],
    refresh: [["path", "M20 11a8 8 0 10-2.3 5.7M20 4v7h-7"]],
    key: [["circle", {cx: 8, cy: 15, r: 4}], ["path", "M11 12l9-9M17 6l3 3"]],
    trash: [["path", "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"]],
    cube: [["path", "M12 3l8 4.5v9L12 21l-8-4.5v-9z"], ["path", "M12 12l8-4.5M12 12v9M12 12L4 7.5"]],
  };
  const SVGNS = document.getElementById("svgns").namespaceURI;
  function icon(name, cls) {
    const svg = document.createElementNS(SVGNS, "svg");
    svg.setAttribute("class", "i" + (cls ? " " + cls : ""));
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    for (const [tag, spec] of ICONS[name] || []) {
      const node = document.createElementNS(SVGNS, tag);
      if (typeof spec === "string") node.setAttribute("d", spec);
      else for (const [k, v] of Object.entries(spec)) node.setAttribute(k, String(v));
      svg.appendChild(node);
    }
    return svg;
  }
  function svgEl(tag, attrs) {
    const n = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs || {})) if (v !== null && v !== undefined) n.setAttribute(k, String(v));
    return n;
  }

  // ---------- tạo phần tử an toàn ----------
  function el(tag, attrs, ...kids) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = String(v);
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v === true ? "" : String(v));
    }
    return append(node, kids);
  }
  function fill(node, ...kids) { node.replaceChildren(); return append(node, kids); }
  function append(node, kids) {
    for (const kid of kids.flat(Infinity)) {
      if (kid === null || kid === undefined || kid === false) continue;
      node.appendChild(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return node;
  }
  const $ = (id) => document.getElementById(id);
  const $$ = (sel, root) => [...(root || document).querySelectorAll(sel)];
  const nf = new Intl.NumberFormat("vi-VN");
  const fmt = (n) => nf.format(Number(n) || 0);
  const pill = (cls, text, ic) => el("span", {class: "pill " + cls}, ic ? icon(ic) : null, text);
  const SEV = {E: ["err", "Lỗi", "x"], W: ["warn", "Cảnh báo", "alert"], I: ["neu", "Gợi ý", "info"]};
  const b = (t) => el("b", {text: t});

  function toast(msg) {
    const t = $("toast");
    t.textContent = msg;
    t.classList.add("on");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => t.classList.remove("on"), 3600);
  }

  // ---------- THÔNG BÁO BỀN: lỗi kèm cách khắc phục, việc đang chạy lâu ----------
  // Thông báo ngắn (toast) chỉ cho tin vui; lỗi không tự tắt, có "vì sao" + "làm gì" + nút làm ngay.
  const NOTICE_ACTIONS = {
    repropose: {run: () => S.lastPropose ? S.lastPropose() : toast("Bấm lại nút đã dùng (Chuyển Unicode, Dịch…).")},
    connect: {run: () => go("connect")},
    project: {run: () => go("home")},
    ask_ai: {run: (n) => askAI(`Mình gặp lỗi trong CAD Guard: "${n.msg}". Giải thích ngắn gọn cho người làm thiết kế: lỗi này nghĩa là gì, vì sao xảy ra và cần làm gì để chạy được.`)},
    guide3d: {run: () => { if (S.showDiscussion) S.showDiscussion(); rightTab("help"); }},
    sheets: {run: () => { const b = document.querySelector(".sheetbar, #sheetBar"); if (b) b.scrollIntoView({block: "nearest"}); toast("Bấm chọn một tờ ở thanh Tờ phía trên bản vẽ."); }},
    changes: {run: () => { if (S.showDiscussion) S.showDiscussion(); rightTab("chg"); }},
    setup: {run: () => go("setup")},
  };
  function notice({kind = "err", title, msg, hint, ctx}) {
    const box = $("notices");
    const h = hint || {};
    const x = el("button", {class: "n-x", type: "button", "aria-label": "Đóng thông báo", onclick: () => n.remove()}, "×");
    const steps = (h.steps || []).length ? el("ol", {}, h.steps.map((s) => el("li", {text: s}))) : null;
    const data = {msg: msg || "", ctx};
    const acts = (h.actions || []).filter((a) => NOTICE_ACTIONS[a.id]).map((a) =>
      el("button", {class: "btn-s btn-sm", type: "button", onclick: () => { NOTICE_ACTIONS[a.id].run(data); }}, a.label));
    if (kind === "err") acts.push(el("button", {class: "btn-s btn-sm", type: "button", onclick: async () => {
      try { await navigator.clipboard.writeText(`${title || h.title || ""}\n${msg || ""}${ctx ? "\nThao tác: " + ctx : ""}`); toast("Đã sao chép nội dung lỗi."); } catch (_) { toast("Không sao chép được: hãy bôi đen và Ctrl+C."); }
    }}, "Sao chép"));
    const n = el("div", {class: "notice " + kind, role: kind === "err" ? "alert" : "status"}, x,
      el("h4", {text: title || h.title || (kind === "err" ? "Chưa thực hiện được" : "")}),
      ctx ? el("div", {class: "n-msg", text: "Thao tác: " + ctx}) : null,
      msg ? el("div", {class: "n-msg", text: msg}) : null,
      h.why ? el("div", {}, el("b", {text: "Vì sao: "}), h.why) : null,
      steps ? [el("b", {text: "Làm gì để chạy được:"}), steps] : null,
      acts.length ? el("div", {class: "n-act"}, acts) : null);
    box.prepend(n);
    while (box.children.length > 4) box.lastChild.remove();
    return n;
  }
  function fail(e, ctx) {
    const msg = (e && e.message) || String(e);
    return notice({kind: "err", msg, hint: e && e.hint, ctx});
  }
  function busy(title, msg) {
    const n = notice({kind: "busy", title, msg});
    return {done: () => n.remove()};
  }

  function when(ts) {
    if (!ts) return "";
    const d = new Date(ts);
    if (isNaN(d)) return "";
    const now = new Date();
    const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
    const diff = Math.round((day(now) - day(d)) / 86400000);
    if (diff === 0) return d.toLocaleTimeString("vi-VN", {hour: "2-digit", minute: "2-digit"});
    if (diff === 1) return "Hôm qua";
    return d.toLocaleDateString("vi-VN", {day: "2-digit", month: "2-digit"});
  }
  function greeting() {
    const h = new Date().getHours();
    return h < 11 ? "Chào buổi sáng" : h < 14 ? "Chào buổi trưa" : h < 18 ? "Chào buổi chiều" : "Chào buổi tối";
  }

  // ---------- mã phiên + gọi API ----------
  const qs = new URLSearchParams(location.search);
  let TOKEN = qs.get("t") || sessionStorage.getItem("cg-token") || "";
  // Bảng neo trong AutoCAD (plugin CadGuard.Acad, lệnh CGBANG): ?panel=1&dwg=<tên bản vẽ đang mở>
  if (qs.get("panel") === "1") sessionStorage.setItem("cg-panel", "1");
  if (qs.get("dwg")) sessionStorage.setItem("cg-dwg", qs.get("dwg").slice(0, 255));
  // Lệnh AutoCAD CADGUARD: ?open=1&dwg=<tên bản vẽ> -> mở và quét ngay bản vẽ đó (không phải chế độ bảng neo)
  const OPEN_DWG = qs.get("open") === "1";
  const PANEL = sessionStorage.getItem("cg-panel") === "1";
  if (qs.get("t")) {
    sessionStorage.setItem("cg-token", TOKEN);
    history.replaceState(null, "", "/");
  }

  async function api(path, body) {
    const init = {method: body === undefined ? "GET" : "POST", headers: {"X-CadGuard-Token": TOKEN}, cache: "no-store"};
    if (body !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }
    const r = await fetch(path, init);
    let data = null;
    try { data = await r.json(); } catch (_) { data = null; }
    if (r.status === 401) $("tokenBanner").hidden = false;
    if (!r.ok) {
      const err = new Error((data && data.error) || ("Lỗi máy chủ " + r.status));
      err.status = r.status;
      err.hint = data && data.hint;
      throw err;
    }
    return data;
  }

  // ---------- trạng thái ----------
  const S = {
    session: null, dept: null, screen: "home",
    files: [], file: null, geo: null, geoOut: null, audits: {}, findings: [], sel: null, stat: {},
    suggest: null, suggestStd: null, preview: null, applied: null, changesets: [], cmp: "after", recheck: null,
    engines: [], groups: [], engine: null, history: [], run: null, busy: false, ai: null,
    sessionUsage: {input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_write_tokens: 0, cost_usd: null},
    home: null, rules: null, ruleFilter: {dept: "", q: "", kind: "", sev: ""},
    sheets: null, sheetSel: null, showHints: false,
  };
  const hasProject = () => !!(S.session && S.session.project);
  const deptById = (id) => (S.session ? S.session.departments.find((d) => d.id === id) : null);
  const deptStd = () => (S.dept && S.dept.standards.length ? S.dept.standards : []);
  const chatStd = () => deptStd()[deptStd().length - 1] || (S.session && S.session.standards.includes("furniture-v0") ? "furniture-v0" : (S.session ? S.session.standards[0] : null));
  const nextNames = (d) => (d.next || []).map((n) => (deptById(n) || {name: n}).name);

  // ---------- giao diện chung ----------
  function initIcons(root) {
    for (const span of $$("[data-icon]", root)) {
      const svg = icon(span.getAttribute("data-icon"), span.getAttribute("class") || "");
      span.replaceWith(svg);
    }
  }

  function confirmDialog({title, body, yes, danger, no}) {
    return new Promise((resolve) => {
      const bg = $("modal");
      $("mTitle").textContent = title;
      fill($("mText"), ...body.map((p) => (p instanceof Node ? p : el("p", {text: p}))));
      const y = $("mYes"), n = $("mNo");
      y.textContent = yes || "Đồng ý";
      n.textContent = no || "Huỷ";
      y.className = danger ? "btn-d" : "btn-p";
      const prev = document.activeElement;
      bg.classList.add("on");
      n.focus();
      const done = (v) => {
        bg.classList.remove("on");
        y.removeEventListener("click", onY); n.removeEventListener("click", onN); bg.removeEventListener("keydown", onK);
        if (prev && prev.focus) prev.focus();
        resolve(v);
      };
      const onY = () => done(true);
      const onN = () => done(false);
      const onK = (e) => {
        if (e.key === "Escape") { e.preventDefault(); done(false); }
        if (e.key === "Tab") { e.preventDefault(); (document.activeElement === y ? n : y).focus(); }
      };
      y.addEventListener("click", onY); n.addEventListener("click", onN); bg.addEventListener("keydown", onK);
    });
  }

  function kv(pairs) {
    const dl = el("dl", {class: "kv"});
    for (const [k, v] of pairs) {
      if (v === null || v === undefined || v === "") continue;
      dl.append(el("dt", {text: k}), el("dd", {}, v instanceof Node ? v : String(v)));
    }
    return dl;
  }

  function emptyBox(title, ...rest) { return el("div", {class: "empty"}, el("b", {text: title}), ...rest); }

  // ---------- giao diện sáng/tối ----------
  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    fill($("themeBtn"), icon(t === "dark" ? "sun" : "moon"));
    localStorage.setItem("cg-theme", t);
    if (S.v3d) S.v3d.redraw();
  }

  // ---------- menu thả xuống ----------
  function closeMenus() {
    for (const id of ["deptMenu", "engineMenu"]) $(id).hidden = true;
    $("deptBtn").setAttribute("aria-expanded", "false");
    $("engineBtn").setAttribute("aria-expanded", "false");
  }
  function toggleMenu(btn, menu) {
    return (e) => {
      e.stopPropagation();
      const open = $(menu).hidden;
      closeMenus();
      $(menu).hidden = !open;
      $(btn).setAttribute("aria-expanded", open ? "true" : "false");
      if (open) { const first = $(menu).querySelector("button:not([disabled])"); if (first) first.focus(); }
    };
  }
  function menuItem(checked, title, desc, onclick, disabled) {
    return el("button", {type: "button", role: "menuitemradio", "aria-checked": checked ? "true" : "false", disabled: !!disabled,
      onclick: (e) => { e.stopPropagation(); closeMenus(); onclick(); }},
    el("span", {class: "ck"}, checked ? icon("check") : null),
    el("span", {}, el("span", {class: "t", text: title}), el("br"), el("span", {class: "d", text: desc})));
  }

  // ---------- điều hướng màn ----------
  const NEED_PROJECT = new Set(["home", "work", "overview", "rules"]);
  function go(name) {
    if (NEED_PROJECT.has(name) && !hasProject()) name = "project";
    S.screen = name;
    for (const s of $$(".screen")) s.classList.toggle("on", s.id === "s-" + name);
    for (const t of $$(".nav [data-go]")) {
      const on = t.dataset.go === name;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
    }
    closeDrawer();
    if (name === "home") loadHome();
    else if (name === "overview") loadOverview();
    else if (name === "rules") loadRules();
    else if (name === "connect") loadConnect();
    else if (name === "setup") loadSetup();
    else if (name === "project") loadProjects();
    else if (name === "work") renderSheet();
  }

  function renderNav() {
    for (const t of $$(".nav [data-go]")) t.disabled = NEED_PROJECT.has(t.dataset.go) && !hasProject();
  }

  // ---------- phiên ----------
  function renderSession() {
    const s = S.session;
    $("projTop").textContent = s.project ? s.project.name : "chưa mở";
    $("dataMode").textContent = s.anonymize ? "Ẩn danh (NDA)" : "Nội bộ";
    $("dataChip").classList.toggle("danger", false);
    $("dataChip").title = s.anonymize
      ? "Dự án NDA: trợ lý chỉ thấy kết quả công cụ đã ẩn danh (mã F_…, L_…). Chức năng dịch bị khoá. Đổi ở Kết nối AI."
      : "Nội bộ: trợ lý thấy nội dung thật của bản vẽ để hiểu và đề xuất. Dự án có NDA: bật ẩn danh ở Kết nối AI.";
    const ab = $("anonBanner");
    ab.hidden = true;
    const saved = localStorage.getItem("cg-dept");
    S.dept = deptById(S.dept && S.dept.id) || deptById(saved) || deptById(s.default) || s.departments[0];
    renderDeptMenu();
    renderNav();
  }

  function renderDeptMenu() {
    $("deptName").textContent = S.dept ? S.dept.name : "–";
    fill($("deptMenu"), ...S.session.departments.map((d) => menuItem(d.id === S.dept.id,
      d.name + (d.priority ? " · ưu tiên khảo sát" : ""),
      (d.role || d.description) + (d.standards.length ? ` · chuẩn: ${d.standards.join(" + ")}` : d.view === "scene" ? " · xem 3D (chỉ xem)" : ""),
      () => setDept(d.id))));
  }

  function setDept(id) {
    const d = deptById(id);
    if (!d || (S.dept && d.id === S.dept.id)) return;
    S.dept = d;
    localStorage.setItem("cg-dept", d.id);
    renderDeptMenu();
    resetDrawing(false);
    renderWorkSide();
    if (S.file) openFile(S.file, {scan: false});
    else renderSheet();
    if (S.screen === "home") loadHome();
    if (S.screen === "rules") renderRules();
    renderSuggestions();
  }

  // ---------- chọn dự án ----------
  async function loadProjects() {
    let r;
    try { r = await api("/api/projects"); } catch (e) { fail(e); return; }
    $("pickBtn").disabled = !r.dialog_available;
    $("pickNote").textContent = r.dialog_available ? "Mở hộp thoại chọn thư mục của hệ điều hành."
      : "Máy này không có hộp thoại chọn thư mục (thiếu tkinter): hãy dán đường dẫn bên dưới.";
    const box = $("recentList");
    if (!r.recent.length) {
      fill(box, el("div", {class: "card"}, emptyBox("Chưa có dự án gần đây", "Mở một thư mục chứa bản vẽ DXF để bắt đầu. Lần sau dự án sẽ hiện ở đây.")));
      return;
    }
    fill(box, ...r.recent.map((p) => {
      const cur = r.current && r.current.name === p.name && hasProject();
      return el("article", {class: "dwg recent-card"},
        el("div", {class: "dwg-h"}, el("span", {class: "nm"}, icon("folder"), p.name),
          el("span", {class: "stage"}, !p.exists ? pill("err", "Không còn thư mục này", "x") : cur ? pill("info", "Đang mở") : null)),
        el("div", {class: "path", text: p.path}),
        el("div", {class: "dwg-f"},
          el("button", {class: "btn-p", type: "button", disabled: !p.exists, onclick: () => openProject(p.path)}, "Mở"),
          el("button", {class: "btn-s", type: "button", onclick: async () => {
            try { await api("/api/project/forget", {path: p.path}); loadProjects(); } catch (e) { fail(e); }
          }}, "Bỏ khỏi danh sách"),
          el("span", {class: "why", text: p.opened_at ? "Mở lần cuối: " + new Date(p.opened_at).toLocaleString("vi-VN") : ""})));
    }));
  }

  async function pickProject() {
    const btn = $("pickBtn");
    btn.disabled = true;
    $("pickNote").textContent = "Đang mở hộp thoại chọn thư mục… (cửa sổ có thể nằm sau trình duyệt)";
    try {
      const r = await api("/api/project/pick", {});
      if (r.unavailable) { $("pickNote").textContent = "Không mở được hộp thoại trên máy này: hãy dán đường dẫn bên dưới."; return; }
      if (r.cancelled || !r.path) { $("pickNote").textContent = "Đã huỷ chọn thư mục."; return; }
      $("pickNote").textContent = "";
      await openProject(r.path);
    } catch (e) { fail(e); $("pickNote").textContent = ""; } finally { btn.disabled = false; }
  }

  async function openProject(path, confirmed) {
    let r;
    try { r = await api("/api/project/open", {path, confirm: !!confirmed}); } catch (e) { fail(e); return; }
    if (r.needs_confirm) {
      const ok = await confirmDialog({title: `Mở “${r.name}” làm dự án?`, body: [r.warning, "Vẫn mở thư mục này?"], yes: "Vẫn mở", no: "Chọn thư mục khác"});
      if (ok) await openProject(path, true);
      return;
    }
    if (r.note) toast(r.note);
    S.session = r.session;
    onProjectChanged();
    toast("Đã mở dự án " + S.session.project.name);
  }

  function onProjectChanged() {
    renderSession();
    S.files = []; S.stat = {}; S.changesets = []; S.home = null; S.rules = null;
    S.history = []; fill($("log"));
    resetDrawing(true);
    renderWorkSide();
    loadFiles();
    loadChangesets();
    go("home");
  }

  // ---------- VIỆC CỦA TÔI ----------
  async function loadHome() {
    if (!hasProject()) return;
    try { S.home = await api("/api/home?dept=" + encodeURIComponent(S.dept.id)); } catch (e) { fail(e); return; }
    for (const d of S.home.drawings) if (d.scanned) S.stat[d.path] = S.stat[d.path] || {E: d.errors, W: d.warnings, I: d.infos, from: "history"};
    renderFiles();
    renderHome();
  }

  const ck = (done, ...txt) => el("li", {class: done ? "done" : "todo"}, icon(done ? "check" : "x"), el("span", {}, ...txt));

  function renderPipe(h) {
    const node = (d) => {
      const p = h.pipe[d.id] || {in_progress: 0, ready: 0};
      return el("div", {class: "node" + (d.id === S.dept.id ? " me" : "")}, el("div", {class: "nm", text: d.name}),
        el("div", {class: "ct", text: `${p.in_progress} bản đang xử lý · ${p.ready} sẵn sàng`}),
        d.id === S.dept.id ? pill("info", "Bạn ở đây") : null);
    };
    const ext = (n, t) => el("div", {class: "node ext"}, el("div", {class: "nm", text: n}), el("div", {class: "ct", text: t}));
    const arr = () => el("div", {class: "arr"}, icon("arrow"));
    const ds = S.session.departments;
    const tk = ds.find((d) => d.id === "ky-thuat");
    const parts = [];
    if (tk && ds.length === 4) {
      parts.push(node(ds[0]), arr(), node(tk), arr(),
        el("div", {class: "fork"}, node(deptById("thiet-ke-3d")), node(deptById("lap-trinh-san-xuat"))), arr(),
        el("div", {class: "fork"}, ext("Render", "ngoài cad-guard"), ext("Xưởng", "ngoài cad-guard")));
    } else {
      ds.forEach((d, i) => { if (i) parts.push(arr()); parts.push(node(d)); });
    }
    fill($("pipe"), ...parts);
  }

  function drawingCard(d) {
    const dept = S.dept;
    const stds = deptStd();
    const nx = nextNames(dept);
    const state = !d.scanned ? ["neu", "Chưa quét", null] : d.errors ? ["err", `${d.errors} lỗi mức E còn lại`, "x"]
      : d.scanned_all ? ["ok", "Sạch lỗi E", "check"] : ["warn", "Chưa quét đủ chuẩn", "alert"];
    const ready = d.scanned_all && !d.errors;
    const topRules = Object.entries(d.rules || {}).sort((a, x) => x[1] - a[1]).slice(0, 4);
    const decide = d.errors ? el("div", {class: "decide"}, icon("hand"), el("div", {}, b("Còn lỗi mức E. Luật vi phạm nhiều nhất:"), el("br"),
      topRules.map(([r, n], i) => [i ? el("br") : null, `${r} · ${n} chỗ`]))) : null;
    const gate = el("button", {class: "f-link", type: "button", onclick: () => openCatalog({dept: dept.id})}, `xem luật của phòng ${dept.name}`);
    const items = stds.length ? [
      ck(d.scanned_all, `Đã quét theo ${stds.join(" + ")}`),
      ck(ready, d.scanned ? (d.errors ? `Còn ${d.errors} lỗi mức E, ${d.warnings || 0} cảnh báo` : `Hết lỗi mức E (${d.warnings || 0} cảnh báo)`) : "Chưa quét lỗi", " · ", gate),
      ck(!!d.handover, nx.length ? `Đã đánh dấu sẵn sàng bàn giao cho ${nx.join(" và ")}` : "Đã đánh dấu sẵn sàng xuất cho xưởng"),
    ] : [ck(false, "Phòng này chưa có chuẩn kiểm; xem 3D ở màn Bản vẽ")];
    const packBtn = stds.length ? el("button", {class: "btn-s", type: "button", disabled: !ready || !!d.handover,
      onclick: () => markHandover(d.path)}, d.handover ? "Đã đánh dấu" : (nx.length ? `Sẵn sàng giao cho ${nx.join(" và ")}` : "Sẵn sàng xuất cho xưởng")) : null;
    const why = !stds.length ? "" : d.handover ? `Đánh dấu lúc ${when(d.handover)}. cad-guard không gửi tệp đi đâu.`
      : ready ? "Chưa ghi gì cho tới khi bạn bấm." : !d.scanned ? "Chưa quét." : d.errors ? "Chưa thể bàn giao: còn lỗi mức E." : "Cần quét đủ các chuẩn của phòng.";
    return el("article", {class: "dwg"},
      el("div", {class: "dwg-h"}, el("span", {class: "nm"}, icon("file"), d.path),
        el("span", {class: "stage pill " + state[0]}, state[2] ? icon(state[2]) : null, state[1])),
      decide,
      el("ul", {class: "ready"}, items),
      el("div", {class: "dwg-f"},
        el("button", {class: "btn-p", type: "button", onclick: () => { go("work"); openFile(d.path, {scan: !d.scanned}); }}, d.scanned ? "Mở và xử lý" : "Mở và quét"),
        packBtn, el("span", {class: "why", text: why})));
  }

  async function markHandover(path) {
    try {
      const r = await api("/api/handover", {file: path, dept: S.dept.id});
      toast(r.note);
      loadHome();
    } catch (e) { fail(e); }
  }

  function renderHome() {
    const h = S.home;
    const d = S.dept;
    $("homeH").textContent = `${greeting()}, phòng ${d.name}`;
    const scanned = h.drawings.filter((x) => x.scanned);
    const need = scanned.filter((x) => x.errors).length;
    const ready = scanned.filter((x) => x.scanned_all && !x.errors && !x.handover).length;
    const unscanned = h.drawings_total - scanned.length;
    $("homeP").textContent = (d.role ? d.role + ". " : "") + (h.drawings_total
      ? [need ? `Bạn có ${need} bản còn lỗi mức E` : null, `${ready} bản sẵn sàng bàn giao`, unscanned ? `${unscanned} bản chưa quét` : null].filter(Boolean).join(", ") + "."
      : "Thư mục dự án chưa có tệp DXF.");
    renderPipe(h);
    const list = [];
    if (h.inbox.length) {
      const prev = h.inbox[0].from;
      list.push(el("h2", {text: `Nhận từ phòng ${prev}`}));
      for (const it of h.inbox) {
        list.push(el("article", {class: "dwg"},
          el("div", {class: "dwg-h"}, el("span", {class: "nm"}, icon("inbox"), it.file),
            el("span", {class: "stage pill " + (it.received ? "ok" : "info")}, it.received ? icon("check") : null, it.received ? "Đã nhận và quét" : "Có gói bàn giao")),
          el("p", {class: "lead small", text: `Từ ${it.from} · ${when(it.ts)}. Phòng ${it.from} đã đánh dấu sẵn sàng (hết lỗi mức E theo chuẩn của họ).`}),
          el("div", {class: "dwg-f"}, el("button", {class: "btn-s", type: "button", onclick: () => { go("work"); openFile(it.file, {scan: true}); }}, it.received ? "Mở" : "Nhận và mở"),
            el("span", {class: "why", text: "Mở bản vẽ và quét theo chuẩn của phòng bạn."}))));
      }
    }
    list.push(el("h2", {class: h.inbox.length ? "mt12" : "mt0", text: `Bản vẽ của phòng ${d.name}`}));
    if (!h.drawings.length) {
      list.push(el("div", {class: "card"}, emptyBox("Chưa có bản vẽ DXF trong dự án", "Chép tệp .dxf vào thư mục dự án (hoặc mở thư mục khác ở nút Dự án trên cùng), rồi quay lại đây.")));
    } else {
      list.push(...h.drawings.map(drawingCard));
      if (h.drawings_total > h.drawings.length) list.push(el("p", {class: "muted small", text: `Hiện ${h.drawings.length}/${h.drawings_total} bản (mới quét gần đây trước). Xem đủ ở màn Bản vẽ.`}));
    }
    fill($("homeList"), ...list);

    const mine = [];
    mine.push(el("div", {class: "mine"},
      el("div", {class: "lockline"}, icon("lock", "i14"), "Chỉ mình bạn thấy · lưu trên máy này"),
      el("h3", {text: "Lỗi tôi hay gặp (30 ngày)"}),
      h.frequent_rules.length ? h.frequent_rules.map((r) => el("div", {class: "row"},
        el("span", {}, el("button", {class: "f-rule link", type: "button", onclick: () => openCatalog({rule: r.rule_id})}, r.rule_id), " ", r.title),
        b(`${r.times} lần`)))
        : el("p", {class: "empty-s", text: "Chưa có dữ liệu. Mỗi lần quét, cad-guard ghi đếm theo luật vào lịch sử dự án (không tên tệp)."}),
      h.frequent_rules.length ? el("div", {class: "tip"}, el("span", {}, "Bấm mã luật để xem luật nói gì và tham số đang áp.")) : null));
    const a = h.assistant;
    mine.push(el("div", {class: "mine"}, el("h3", {text: "Đề xuất của trợ lý"}),
      el("div", {class: "row"}, el("span", {text: "Bạn đã áp dụng"}), b(`${a.agent_applied} / ${a.agent_proposed}`)),
      el("div", {class: "row"}, el("span", {text: "Thay đổi bạn tự đề xuất đã áp dụng"}), b(String(a.user_applied))),
      el("p", {class: "note", text: "Số đếm từ các changeset trong dự án này. Đúng/sai vẫn do bộ luật kiểm tất định quyết định."})));
    mine.push(el("div", {class: "mine"}, el("h3", {text: "Gần đây"}),
      h.recent.length ? el("ul", {class: "tl"}, h.recent.map((r) => el("li", {}, el("time", {text: when(r.ts)}), el("span", {}, ...recentText(r)))))
        : el("p", {class: "empty-s", text: "Chưa có hoạt động. Lịch sử quét lưu trong .cadguard/history.jsonl của dự án."})));
    fill($("homeMine"), ...mine);
  }

  function recentText(r) {
    const f = r.file ? b(r.file) : "một bản vẽ đã đổi tên/xoá";
    if (r.event === "audit") return ["Quét ", f, `: ${r.findings} phát hiện (${r.standard})`];
    if (r.event === "apply") return ["Áp dụng thay đổi trên ", f, r.output ? [" → ", b(r.output)] : ""];
    if (r.event === "undo") return ["Hoàn tác, xoá ", r.output ? b(r.output) : "tệp mới"];
    if (r.event === "handover") return ["Đánh dấu ", f, ` sẵn sàng giao cho ${(r.to || []).join(", ") || "xưởng"}`];
    return [r.event];
  }

  $("askForm") && $("askForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const v = $("askIn").value.trim();
    if (!v) return;
    $("askIn").value = "";
    go("work");
    rightTab("chat");
    $("inp").value = v;
    $("form").requestSubmit();
  });

  // ---------- TỔNG QUAN ----------
  async function loadOverview() {
    if (!hasProject()) return;
    let o;
    try { o = await api("/api/overview"); } catch (e) { fail(e); return; }
    const box = $("ovBody");
    if (!o.has_data) {
      fill(box, el("div", {class: "card"}, emptyBox("Chưa có số liệu tuần này", "Số liệu sinh từ lịch sử quét của dự án trên máy này. Quét vài bản vẽ ở màn Bản vẽ (hoặc “Quét cả thư mục”), rồi quay lại.")));
      return;
    }
    const kpi = (v, l, dlt) => el("div", {class: "card kpi"}, el("div", {class: "v", text: v}), el("div", {class: "l", text: l}), el("div", {class: "dlt", text: dlt}));
    const pct = o.changesets_proposed ? Math.round(o.changesets_applied / o.changesets_proposed * 100) + "%" : "–";
    const maxBar = Math.max(1, ...o.top_rules.map((r) => r.count));
    fill(box,
      el("div", {class: "kpis"},
        kpi(fmt(o.files_scanned), "Bản vẽ đã quét", `7 ngày gần nhất · ${fmt(o.audits)} lần quét`),
        kpi(fmt(o.open_errors), "Lỗi mức E đang mở", "theo lần quét mới nhất mỗi bản"),
        kpi(pct, "Đề xuất sửa được áp dụng", `trên ${o.changesets_proposed} đề xuất`),
        kpi(fmt(o.handovers), "Bản đánh dấu sẵn sàng bàn giao", "7 ngày gần nhất")),
      el("h2", {text: "Bàn giao giữa các phòng tuần này"}),
      el("p", {class: "lead lead-tight", text: "Lỗi bắt ở phòng trước rẻ hơn nhiều so với lỗi lọt sang phòng sau. Đây là chỗ cho thấy cad-guard có đáng không."}),
      el("div", {class: "flow"}, o.flows.map((f) => el("div", {class: "card"}, el("div", {class: "big", text: fmt(f.handed_over)}),
        el("div", {text: `${f.from} → ${f.to.join(" / ")}`}),
        el("div", {class: "kpi"}, el("div", {class: "dlt", text: `${f.blocked} bản còn lỗi mức E, chưa giao được`}))))),
      el("h2", {text: "Luật bị vi phạm nhiều nhất"}),
      el("p", {class: "lead lead-tight", text: "Danh sách này quyết định luật nào nên ưu tiên đo độ chính xác và nên đưa vào mẫu bản vẽ chuẩn."}),
      el("div", {class: "card"},
        o.top_rules.length ? el("div", {class: "bars"}, o.top_rules.map((r) => {
          const bar = el("i");
          bar.style.width = (r.count / maxBar * 100) + "%";
          return el("div", {class: "bar"}, el("span", {text: `${r.rule_id} · ${r.title}`}), el("span", {class: "tr"}, bar), el("span", {class: "nn", text: fmt(r.count)}));
        })) : el("p", {class: "muted", text: "Tuần này chưa có vi phạm nào."}),
        el("div", {class: "privacy"}, icon("lock"), "Số tổng hợp từ lịch sử trên máy này. Lịch sử chỉ chứa mã băm tệp, không tên tệp hay tên khách.")),
      el("h2", {text: "Độ tin cậy của luật"}),
      el("div", {class: "card flush"}, el("table", {},
        el("thead", {}, el("tr", {}, ["Luật", "Nội dung", "Số lần", "Độ chính xác", "Cảnh báo khi đang vẽ"].map((t) => el("th", {text: t})))),
        el("tbody", {}, o.top_rules.length ? o.top_rules.map((r) => el("tr", {},
          el("td", {class: "f-rule", text: r.rule_id}), el("td", {text: r.title}), el("td", {text: fmt(r.count)}),
          el("td", {}, pill("neu", "Chưa đo")),
          el("td", {}, r.realtime_ok ? pill("ok", "Được bật") : pill("neu", "Chưa đo đủ"))))
          : el("tr", {}, el("td", {colspan: "5", class: "muted", text: "Chưa có dữ liệu."}))))),
      el("p", {class: "muted small mt8", text: "Độ chính xác của luật chỉ có sau khi đo trên mẫu đã gắn nhãn (kế hoạch P1c); cảnh báo khi đang vẽ chỉ bật cho luật đã đo đạt ngưỡng."}));
  }

  // ---------- BẢN VẼ: cột trái ----------
  const OUT_RE = /\.cg-[0-9a-f]{8}\.dxf$/i;
  function parentOf(path) { return path.replace(OUT_RE, ".dxf"); }

  async function loadFiles() {
    if (!hasProject()) return;
    try {
      const r = await api("/api/drawings");
      S.files = r.drawings;
      S.filesTruncated = r.truncated ? r.limit : 0;
      renderFiles();
    } catch (e) { fail(e); }
  }

  function statPills(st) {
    if (!st) return [pill("neu", "Chưa quét")];
    const out = [];
    if (st.E) out.push(pill("err", `${st.E} lỗi`, "x"));
    if (st.W) out.push(pill("warn", `${st.W} cảnh báo`, "alert"));
    if (!st.E && !st.W) out.push(pill("ok", st.I ? `Sạch · ${st.I} gợi ý` : "Sạch", "check"));
    return out;
  }

  function renderFiles() {
    const box = $("files");
    $("projName").textContent = hasProject() ? "Dự án " + S.session.project.name : "Dự án";
    if (!S.files.length) {
      fill(box, emptyBox("Chưa có tệp DXF", "Thư mục dự án không có tệp .dxf nào. Chép bản vẽ vào thư mục, rồi bấm “Quét cả thư mục”."));
      return;
    }
    const src = S.files.filter((f) => !f.is_output);
    const outs = S.files.filter((f) => f.is_output);
    const btn = (f, child) => el("button", {class: "file" + (child ? " child" : ""), type: "button", role: "listitem",
      "aria-current": f.path === S.file || (S.applied && S.applied.output === f.path && S.cmp === "after") ? "true" : "false",
      onclick: () => openFile(f.path, {scan: false})},
    el("span", {class: "n"}, icon("file"), f.path),
    el("span", {class: "m"}, f.version ? (f.version.state === "current" ? pill("ok", "Đang dùng") : pill("warn", "Bản cũ"))
      : (child ? pill("info", "Bản mới") : null), statPills(S.stat[f.path]),
      el("span", {class: "muted small", text: `${fmt(Math.max(1, Math.round(f.size_bytes / 1024)))} KB`})));
    const nodes = [];
    for (const f of src) {
      nodes.push(btn(f, false));
      for (const o of outs.filter((x) => parentOf(x.path) === f.path)) nodes.push(btn(o, true));
    }
    for (const o of outs.filter((x) => !src.some((f) => f.path === parentOf(x.path)))) nodes.push(btn(o, true));
    if (S.filesTruncated) nodes.push(el("p", {class: "muted small", text: `Chỉ liệt kê ${fmt(S.filesTruncated)} tệp đầu (thư mục quá lớn). Nên mở đúng thư mục dự án.`}));
    fill(box, ...nodes);
  }

  function renderWorkSide() {
    syncToolbar();
    if (!S.session) return;
    const stds = deptStd();
    $("stdName").textContent = stds.length ? stds.join(" + ") : (S.dept && S.dept.view === "scene" ? "Chưa có (luật 3D đang phát triển)" : "Chưa gán chuẩn");
    const res = Object.values(S.audits);
    $("stdRules").textContent = res.length ? `${res.reduce((a, r) => a + r.rules_run, 0)} / ${res.reduce((a, r) => a + r.rules_total, 0)} luật` : "–";
    const p = S.session.profile;
    $("stdProfile").textContent = p ? `${p.name} ${p.version} (cho ${p.standard})` : "Mặc định của chuẩn";
    $("profileBtn").hidden = !hasProject();
    $("scanAll").disabled = !stds.length || !hasProject();
  }

  async function scanAll() {
    const btn = $("scanAll");
    const stds = deptStd();
    if (!stds.length) return;
    btn.disabled = true;
    const h = $("handoff");
    h.hidden = false;
    fill(h, "Đang quét cả thư mục theo ", b(stds.join(" + ")), "…");
    const agg = {};
    try {
      for (const std of stds) {
        const r = await api("/api/audit_all", {standard: std, dept: S.dept.id});
        for (const x of r.results) {
          if (!x.counts) continue;
          const a = agg[x.path] || (agg[x.path] = {E: 0, W: 0, I: 0});
          for (const k of ["E", "W", "I"]) a[k] += x.counts[k];
        }
      }
      for (const [p, c] of Object.entries(agg)) S.stat[p] = c;
      renderFiles();
      const total = Object.keys(agg).length;
      const ready = Object.values(agg).filter((c) => !c.E).length;
      const nx = nextNames(S.dept);
      fill(h, b(`${ready}/${total} bản không còn lỗi mức E`), el("br"),
        nx.length ? `Có thể đánh dấu sẵn sàng giao cho ${nx.join(" và ")} ở màn Việc của tôi.` : "Có thể đánh dấu sẵn sàng xuất cho xưởng ở màn Việc của tôi.");
    } catch (e) { fail(e); h.hidden = true; }
    btn.disabled = false;
  }

  // ---------- BẢN VẼ: mở một tệp ----------
  function resetDrawing(clearFile) {
    if (clearFile) S.file = null;
    S.geo = null; S.geoOut = null; S.geoPending = false; S.audits = {}; S.findings = []; S.sel = null;
    S.suggest = null; S.preview = null; S.applied = null; S.cmp = "after"; S.recheck = null;
    S.sheets = null; S.sheetSel = null; S.mapOn = false;
    if (S.v3d) { S.v3d.stop(); S.v3d = null; }
    renderSheetBar();
    $("cmp").hidden = true; $("cmpLabel").hidden = true;
    renderFinds(); renderChg();
  }

  async function openFile(path, opts) {
    const o = opts || {};
    const isOut = OUT_RE.test(path);
    resetDrawing(false);
    S.file = path;
    S.layout = "Model"; $("layoutSel").replaceChildren(el("option", {text:"Model",value:"Model"}));
    $("cvTitle").textContent = path;
    renderFiles();
    renderWorkSide();
    if (!$("log").childElementCount || o.intro !== false) introChat();
    renderSuggestions();
    checkVersion(path);
    if (S.dept.view === "scene") { load3d(path); return; }
    loadGeometry(path);
    loadSheets(path);
    if (o.scan && deptStd().length) await doScan(true);
    if (isOut) toast("Đây là tệp mới do cad-guard tạo; tệp gốc giữ nguyên.");
  }

  // Dòng phiên bản: một bản vẽ = bản gốc + các tệp mới do lệnh sửa tạo ra. Mở nhầm bản cũ thì cảnh báo ngay;
  // Hoàn tác/Làm lại đổi "bản đang dùng" (không xoá tệp nào); Lịch sử cho xem và chọn lại bản bất kỳ.
  async function checkVersion(path) {
    const bar = $("verBar");
    bar.hidden = true;
    if (S.verNote) { S.verNote.remove(); S.verNote = null; }
    let v;
    try { v = await api("/api/versions", {file: path}); } catch (e) { return; }
    if (S.file !== path || v.state === "single") return;
    const alive = v.versions.filter(x => x.exists);
    const idx = alive.findIndex(x => x.path === path) + 1;
    const cur = alive.find(x => x.path === v.current) || {};
    const act = async (url, body, msg) => {
      try {
        const r = await api(url, {file: path, ...(body || {})});
        toast(msg(r));
        await loadFiles();
        if (r.current !== S.file) openFile(r.current, {scan: false, intro: false}); else checkVersion(path);
      } catch (e) { fail(e, "Phiên bản"); }
    };
    const vbtn = (t, title, fn, dis) => el("button", {class: "btn-s btn-sm", type: "button", title, disabled: dis ? "disabled" : null, onclick: fn}, t);
    fill(bar, el("span", {class: "muted small", text: `Phiên bản ${idx}/${alive.length}${v.state === "current" ? " · đang dùng" : " · BẢN CŨ"}`}),
      vbtn("↶ Hoàn tác", "Về bản trước (tệp vẫn giữ, chỉ đổi bản đang dùng)", () => act("/api/versions/undo", null, r => `Bản đang dùng: ${r.current}`), !cur.parent),
      vbtn("↷ Làm lại", "Dùng lại bản vừa hoàn tác", () => act("/api/versions/redo", null, r => `Bản đang dùng: ${r.current}`), !(v.redo || []).length),
      vbtn("Lịch sử", "Xem các bản và chọn bản đang dùng", () => showVersions(path, v, act)));
    bar.hidden = false;
    if (v.state === "old") {
      const n = notice({kind: "warn", title: "Bạn đang mở một bản CŨ của bản vẽ này",
        msg: `Bản đang dùng là “${v.current}” (${cur.summary || "mới nhất"}${cur.at ? ", " + cur.at.slice(0, 16).replace("T", " ") : ""}). ` +
          "Các phòng sau (Thiết kế 3D, Lập trình sản xuất) nên làm trên bản đang dùng để không mất phần đã chuẩn hoá."});
      n.append(el("div", {class: "n-act"},
        el("button", {class: "btn-p btn-sm", type: "button", onclick: () => { n.remove(); openFile(v.current, {scan: false, intro: false}); }}, "Mở bản đang dùng"),
        el("button", {class: "btn-s btn-sm", type: "button", onclick: () => { n.remove(); act("/api/versions/set", {target: path}, () => "Đã chọn bản này làm bản đang dùng."); }}, "Dùng bản này")));
      S.verNote = n;
    }
  }
  function showVersions(path, v, act) {
    const rows = v.versions.slice().reverse().map(x => el("tr", {class: x.path === v.current ? "on" : ""},
      el("td", {}, b(x.path === v.current ? "● " : ""), x.path), el("td", {text: x.summary}),
      el("td", {text: x.at ? x.at.slice(0, 16).replace("T", " ") : "—"}),
      el("td", {}, !x.exists ? el("span", {class: "muted small", text: "đã xoá"}) : x.path === v.current ? el("span", {class: "muted small", text: "đang dùng"}) :
        el("button", {class: "btn-s btn-sm", type: "button", onclick: () => { d.remove(); act("/api/versions/set", {target: x.path}, () => "Đã đổi bản đang dùng."); }}, "Dùng bản này"))));
    const d = notice({kind: "info", title: "Lịch sử phiên bản",
      msg: "Bản gốc luôn giữ nguyên; mỗi lệnh sửa tạo một bản mới. Chọn bản đang dùng để các phòng sau làm trên đúng bản."});
    d.append(el("table", {class: "tbl3d"}, el("tr", {}, ["Tệp", "Thay đổi", "Lúc", ""].map(t => el("th", {text: t}))), rows));
  }

  async function loadGeometry(path) {
    renderSheet();
    const wantedLayout = S.layout || "Model";
    try {
      const g = await fetchView(path, () => S.file === path && (S.layout || "Model") === wantedLayout && !S.geo, () => {
        if (S.file === path && (S.layout || "Model") === wantedLayout && !S.geo && !S.geoPending) { S.geoPending = true; renderSheet(); }
      });
      if (S.file !== path || (S.layout || "Model") !== wantedLayout || !g) return;
      if(g.layouts) $("layoutSel").replaceChildren(...g.layouts.map(n=>el("option",{value:n,text:n,selected:n===wantedLayout})));
      S.geo = g; S.geoPending = false;
      S.view = null;
      renderSheet();
      selectPendingSheet();
    } catch (e) {
      if (S.file !== path) return;
      S.geo = {error: e.message}; S.geoPending = false;
      renderSheet();
    }
  }

  // Xem trước: hình đầy đủ do bộ vẽ ezdxf dựng ở máy chủ (SVG đã lọc, cache theo nội dung tệp); tệp quá lớn hoặc bộ vẽ
  // lỗi thì máy chủ trả "fallback" và dùng hình đơn giản hoá (/api/geometry).
  async function fetchView(path, wanted, onPending) {
    const requestedLayout = S.layout || "Model";
    let r = await api("/api/preview", {file: path, layout:requestedLayout, wait: 1.5});
    while (r.status === "pending") {
      if (!wanted()) return null;
      if (onPending) onPending();
      await new Promise((ok) => setTimeout(ok, 400));
      if (!wanted()) return null;
      r = await api("/api/preview", {file: path, layout:requestedLayout, wait: 3});
    }
    if (r.status === "ready") {
      try { return svgView(r); } catch (_) { r = {status: "fallback", reason: "Hình xem trước không đọc được."}; }
    }
    if(requestedLayout !== "Model") return {empty_reason:r.reason || "Không dựng được layout này; hãy mở trong CAD.",viewbox:[0,0,1,1],items:[]};
    const g = await api("/api/geometry", {file: path});
    g.simplified = true;
    g.fallback_reason = r.reason || "";
    return g;
  }

  // Danh sách trắng phía trình duyệt (máy chủ đã lọc; lọc lại ở đây cho chắc): chỉ g/path, thuộc tính vẽ, không URL.
  const SVG_ATTR_OK = {
    d: /^[MLQCZmlqcz0-9 .\-]*$/, class: /^(dxf-g|dxf-s|dxf-f|dxf-hs|dxf-hf)$/, stroke: /^(none|currentColor)$/,
    fill: /^(none|currentColor)$/, "stroke-opacity": /^[01](\.\d{1,3})?$/, "fill-opacity": /^[01](\.\d{1,3})?$/,
    "fill-rule": /^evenodd$/, "stroke-linecap": /^round$/, "stroke-linejoin": /^round$/,
  };
  function copySafe(src, dst, depth) {
    if (depth > 4) return;
    for (const ch of src.children) {
      const name = ch.localName;
      if (name !== "g" && name !== "path") continue;
      const n = document.createElementNS(SVGNS, name);
      for (const a of ch.attributes) {
        const re = SVG_ATTR_OK[a.name];
        if (re && re.test(a.value)) n.setAttribute(a.name, a.value);
      }
      if (name === "g") copySafe(ch, n, depth + 1);
      dst.appendChild(n);
    }
  }
  function svgView(r) {
    const doc = new DOMParser().parseFromString(r.svg, "image/svg+xml");
    const root = doc.documentElement;
    if (!root || root.localName !== "svg" || doc.getElementsByTagName("parsererror").length) throw new Error("svg");
    const node = document.createElementNS(SVGNS, "g");
    node.setAttribute("class", "dxf");
    copySafe(root, node, 0);
    return {mode: "svg", node, layout:r.layout, layouts:r.layouts, limitations:r.limitations, viewbox: r.viewbox, transform: r.transform, boxes: new Map(Object.entries(r.boxes || {})), model_entities: r.model_entities,
      insunits: r.insunits, dxf_version: r.dxf_version, paths: r.paths, render_seconds: r.render_seconds, cached: r.cached};
  }

  async function doScan(fromOpen) {
    const path = S.file;
    const stds = deptStd();
    if (!path || !stds.length) return;
    if (!fromOpen) say("me", "Quét bản vẽ này");
    rightTab("chat");
    const t0 = performance.now();
    const typing = showTyping();
    const results = {};
    try {
      for (const std of stds) results[std] = await api("/api/audit", {file: path, standard: std, dept: S.dept.id});
    } catch (e) { typing.remove(); say("err", "Không quét được: " + e.message); return; }
    typing.remove();
    if (S.file !== path) return;
    S.audits = results;
    buildFindings();
    const sec = ((performance.now() - t0) / 1000).toLocaleString("vi-VN", {maximumFractionDigits: 1});
    const all = Object.values(results);
    const c = {E: 0, W: 0, I: 0};
    for (const r of all) for (const k of ["E", "W", "I"]) c[k] += r.counts[k];
    S.stat[path] = c;
    for (const r of all) toolCard("cadguard.audit", `{ "file": "${path}", "standard": "${r.standard} ${r.version}" }`, sec + " giây",
      `${r.rules_run} luật chạy · ${r.counts.E + r.counts.W + r.counts.I} phát hiện · ${r.skipped.length} luật bỏ qua (thiếu dữ liệu)`);
    const fixable = S.findings.filter((f) => f.fixable).length;
    const located = S.findings.filter((f) => f.box).length;
    const total = S.findings.length;
    sayRich([
      el("p", {}, `Quét xong trong ${sec} giây. Có `, b(`${total} nhóm phát hiện`), `: ${c.E} lỗi, ${c.W} cảnh báo, ${c.I} gợi ý.`,
        located ? ` Đã đánh dấu ${located} vị trí trên bản vẽ.` : ""),
      total ? el("p", {}, fixable ? ["Trong đó ", b(`${fixable} nhóm sửa tự động được`), " bằng thao tác an toàn (xem tab Thay đổi)."]
        : "Không nhóm nào sửa tự động được; cần sửa trong phần mềm CAD.", total - fixable ? ` ${total - fixable} nhóm cần người sửa.` : "") : null,
      el("div", {class: "src", text: `Căn cứ: bộ luật ${all.map((r) => r.standard + " " + r.version).join(", ")}. Việc đúng/sai do luật quyết, không phải do mô hình.`}),
    ]);
    renderFiles(); renderWorkSide(); renderFinds(); renderSheet(); renderChg(); renderSuggestions(); renderSheetBar();
    if (total) rightTab("finds");
  }

  function buildFindings() {
    const out = [];
    const order = ["E", "W", "I"];
    for (const sev of order) {
      for (const [std, r] of Object.entries(S.audits)) {
        const g = r.groups.find((x) => x.severity === sev);
        if (!g) continue;
        for (const rule of g.rules) {
          const handles = [...new Set(rule.items.flatMap((it) => it.handles || []))];
          out.push({no: out.length + 1, std, rule_id: rule.rule_id, severity: sev, title: rule.title, count: rule.count,
            items: rule.items, handles, fixable: r.fixable_rules.includes(rule.rule_id), box: null, st: "open",
            tier: rule.tier || (sev === "I" ? "hint" : "warn"), tier_label: rule.tier_label || ""});
        }
      }
    }
    S.findings = out;
    locateFindings();
  }

  // ---------- canvas 2D ----------
  function geoIndex() {
    const g = S.cmp === "after" && S.geoOut ? S.geoOut : S.geo;
    if (g && g.boxes) return g.boxes;
    if (!g || !g.items) return null;
    if (g._idx) return g._idx;
    const idx = new Map();
    for (const [h, k, d] of g.items) {
      let xs, ys;
      if (k === "L" || k === "P" || k === "Q") { xs = d.filter((_, i) => i % 2 === 0); ys = d.filter((_, i) => i % 2 === 1); }
      else if (k === "C" || k === "A") { xs = [d[0] - d[2], d[0] + d[2]]; ys = [d[1] - d[2], d[1] + d[2]]; }
      else if (k === "T") { const s = d[3] || g.text_size || 10; xs = [d[0], d[0] + s * Math.min(30, String(d[2]).length) * 0.6]; ys = [d[1] - s, d[1]]; }
      else { const s = (g.text_size || 10) * 0.5; xs = [d[0] - s, d[0] + s]; ys = [d[1] - s, d[1] + s]; }
      idx.set(h, [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]);
    }
    g._idx = idx;
    return idx;
  }

  function locateFindings() {
    const idx = geoIndex();
    for (const f of S.findings) {
      f.box = null;
      if (!idx) continue;
      let bb = null; f.positions = [];
      for (const h of f.handles) {
        const x = idx.get(h);
        if (!x) continue;
        f.positions.push(x.slice());
        bb = bb ? [Math.min(bb[0], x[0]), Math.min(bb[1], x[1]), Math.max(bb[2], x[2]), Math.max(bb[3], x[3])] : x.slice();
      }
      f.position = Math.min(f.position || 0, Math.max(0,f.positions.length-1));
      f.box = f.positions[f.position] || bb;
    }
  }

  function viewOf(g) {
    if (!S.view) S.view = tightView(g);
    return S.view;
  }

  // Khung nhìn gọn: bỏ đối tượng lạc xa vùng vẽ chính (phân vị 1–99 % tâm khung bao theo handle) để bản vẽ lấp khung.
  // Hình đơn giản hoá đã cắt phân vị ở máy chủ (geometry.py); ở đây áp cho hình dựng đầy đủ (g.boxes).
  function tightView(g) {
    const full = g.viewbox.slice();
    if (g._tight) return g._tight.slice();
    const boxes = !g.boxes ? [] : g.boxes instanceof Map ? [...g.boxes.values()] : Object.values(g.boxes);
    if (g.mode !== "svg" || boxes.length < 40) { g._tight = full; return full.slice(); }
    const xs = boxes.map((b) => (b[0] + b[2]) / 2).sort((a, b) => a - b);
    const ys = boxes.map((b) => (b[1] + b[3]) / 2).sort((a, b) => a - b);
    const q = (arr, p) => arr[Math.min(arr.length - 1, Math.max(0, Math.round(p * (arr.length - 1))))];
    let x0 = q(xs, 0.01), x1 = q(xs, 0.99), y0 = q(ys, 0.01), y1 = q(ys, 0.99);
    // mở rộng theo khung bao thật của các đối tượng nằm trong vùng lõi để không cắt mép hình
    for (const b of boxes) {
      const cx = (b[0] + b[2]) / 2, cy = (b[1] + b[3]) / 2;
      if (cx < x0 || cx > x1 || cy < y0 || cy > y1) continue;
      x0 = Math.min(x0, b[0]); y0 = Math.min(y0, b[1]); x1 = Math.max(x1, b[2]); y1 = Math.max(y1, b[3]);
    }
    let w = Math.max(x1 - x0, 1), h = Math.max(y1 - y0, 1);
    if (w * h > full[2] * full[3] * 0.8) { g._tight = full; return full.slice(); }  // không có đối tượng lạc đáng kể
    const pad = 0.04 * Math.max(w, h);
    x0 -= pad; y0 -= pad; w += 2 * pad; h += 2 * pad;
    const r = full[3] / full[2];  // giữ tỉ lệ khung gốc để phóng/kéo nhất quán
    if (h / w > r) { const nw = h / r; x0 -= (nw - w) / 2; w = nw; } else { const nh = w * r; y0 -= (nh - h) / 2; h = nh; }
    g._tight = [x0, y0, w, h];
    g.stray = boxes.length - boxes.filter((b) => { const cx = (b[0] + b[2]) / 2, cy = (b[1] + b[3]) / 2; return cx >= x0 && cx <= x0 + w && cy >= y0 && cy <= y0 + h; }).length;
    return g._tight.slice();
  }

  function renderSheet() {
    const sheet = $("sheet");
    if (S.mapOn) return;  // đang xem Bản đồ bản vẽ: không vẽ đè
    if (S.dept && S.dept.view === "scene") return;
    const g = S.cmp === "after" && S.geoOut ? S.geoOut : S.geo;
    $("viewTag").hidden = true;
    if (!hasProject()) { fill(sheet, emptyBox("Chưa mở dự án", "Chọn thư mục dự án ở nút Dự án trên cùng.")); return; }
    if (!S.file) { fill(sheet, emptyBox("Chưa mở bản vẽ", "Chọn một bản vẽ ở cột trái để xem trước và quét.")); $("cvInfo").textContent = ""; return; }
    if (!g) {
      fill(sheet, S.geoPending && !(S.cmp === "after" && S.applied)
        ? emptyBox("Đang dựng hình…", "Bộ vẽ đang dựng bản vẽ đầy đủ (khối, chữ, kích thước, hatch). Tệp lớn có thể mất vài chục giây; lần mở sau dùng lại hình đã lưu.")
        : emptyBox("Đang đọc bản vẽ…", "Tệp lớn có thể mất vài giây."));
      return;
    }
    if (g.error) { fill(sheet, emptyBox("Không đọc được hình bản vẽ", g.error)); return; }
    const units = {4: "mm", 5: "cm", 6: "m", 1: "inch", 0: "không đơn vị"}[g.insunits];
    $("viewTag").textContent = (g.simplified ? "Hình đơn giản hoá" : "Không gian mô hình") + (units ? " · " + units : "");
    $("viewTag").hidden = false;
    const a = Object.values(S.audits)[0];
    const ver = (a && a.dxf_version) || g.dxf_version;
    $("cvInfo").textContent = `${fmt(g.model_entities)} đối tượng` + (ver ? ` · DXF ${ver}` : "") + (g.simplified ? ` · vẽ ${fmt(g.drawn)}` : "") + (units ? ` · ${units}` : "");
    if (g.empty_reason) { fill(sheet, emptyBox("Không có hình để xem trước", g.empty_reason, el("br"), "Kết quả quét vẫn đầy đủ ở tab Lỗi.")); return; }
    const vb = viewOf(g);
    const svg = svgEl("svg", {viewBox: vb.join(" "), role: "img", "aria-label": "Xem trước bản vẽ " + (S.cmp === "after" && S.geoOut ? S.applied.output : S.file),
      "data-scanned": Object.keys(S.audits).length ? "1" : "0", "data-mode": g.mode === "svg" ? "full" : "simple",
      class: g.mode === "svg" ? "dxf-view" : "simple-view", preserveAspectRatio: "xMidYMid meet"});
    if (g.mode === "svg") svg.appendChild(g.node);
    else svg.appendChild(simpleDrawing(g));
    locateFindings();
    const note = [];
    if (g.limitations) note.push(g.limitations);
    if (g.simplified) note.push("Hình đơn giản hoá" + (/lớn hơn/.test(g.fallback_reason || "") ? " (tệp lớn)" : "") + ": không vẽ nội dung khối, kích thước, hatch." + (g.fallback_reason ? " " + g.fallback_reason : ""));
    if (g.truncated) note.push(`Chỉ vẽ ${fmt(g.drawn)} đối tượng đầu.`);
    if (g.records_capped) note.push("Tệp rất lớn: danh sách đối tượng đã bị cắt ở trần bộ nhớ.");
    const unlocated = S.findings.filter((f) => !f.box).length;
    if (Object.keys(S.audits).length && unlocated) note.push(`${unlocated} nhóm phát hiện không có vị trí trên hình (bảng layer, kiểu chữ, khung tên…).`);
    if (g.stray) note.push(`Khung nhìn bỏ qua ${fmt(g.stray)} đối tượng nằm xa vùng vẽ chính (thu nhỏ để xem).`);
    fill(sheet, svg, note.length ? el("div", {class: "sheet-note", text: note.join(" ")}) : null);
    attachPanZoom(svg, g);
    applyLod(svg, g);
    drawMarks(svg);
  }

  // Hình đơn giản hoá: chữ xếp theo nhóm cỡ để ẩn/hiện theo mức phóng (level-of-detail); INSERT là chấm nhỏ.
  function simpleDrawing(g) {
    const draw = svgEl("g", {});
    const ts = g.text_size || 10;
    const texts = new Map();
    const ins = svgEl("g", {class: "lod-ins"});
    for (const [, k, d] of g.items) {
      let n;
      if (k === "L") n = svgEl("line", {class: "ln thin", x1: d[0], y1: d[1], x2: d[2], y2: d[3]});
      else if (k === "P" || k === "Q") n = svgEl(k === "Q" ? "polygon" : "polyline", {class: "ln thin", points: d.join(" ")});
      else if (k === "C") n = svgEl("circle", {class: "ln thin", cx: d[0], cy: d[1], r: d[2]});
      else if (k === "A") n = svgEl("path", {class: "ln thin", d: arcPath(d)});
      else if (k === "T") {
        const hgt = d[3] > 0 ? d[3] : ts;
        const b = Math.round(Math.log2(hgt) * 2);
        if (!texts.has(b)) texts.set(b, svgEl("g", {class: "lod-txt", "data-h": String(2 ** (b / 2))}));
        n = svgEl("text", {class: "cv-txt", x: d[0], y: d[1], "font-size": hgt});
        if (d[4]) n.setAttribute("transform", `rotate(${-d[4]} ${d[0]} ${d[1]})`);
        n.textContent = String(d[2]);
        texts.get(b).appendChild(n);
        continue;
      } else {
        n = svgEl("path", {class: "cv-ins", d: `M${d[0]} ${d[1]}h0`});
        const t = svgEl("title"); t.textContent = "Khối " + d[2]; n.appendChild(t);
        ins.appendChild(n);
        continue;
      }
      draw.appendChild(n);
    }
    draw.appendChild(ins);
    for (const grp of texts.values()) draw.appendChild(grp);
    return draw;
  }

  function arcPath(d) {
    const [cx, cy, r, a0, a1] = d;
    let sweep = ((a1 - a0) % 360 + 360) % 360;
    if (sweep === 0) sweep = 360;
    if (sweep >= 359.99) return `M${cx + r} ${cy}a${r} ${r} 0 1 0 ${-2 * r} 0a${r} ${r} 0 1 0 ${2 * r} 0`;
    const p = (ang) => [cx + r * Math.cos(ang * Math.PI / 180), cy - r * Math.sin(ang * Math.PI / 180)];
    const [x0, y0] = p(a0), [x1, y1] = p(a0 + sweep);
    return `M${x0} ${y0}A${r} ${r} 0 ${sweep > 180 ? 1 : 0} 0 ${x1} ${y1}`;
  }

  // Hình đơn giản hoá: ẩn chữ quá nhỏ trên màn (dưới ~5 px); ẩn chấm INSERT khi nhìn toàn cảnh mà có quá nhiều.
  function applyLod(svg, g) {
    if (g.mode === "svg") return;
    const r = svg.getBoundingClientRect();
    if (!r.width || !S.view) return;
    const px = Math.min(r.width / S.view[2], (r.height || r.width) / S.view[3]);
    for (const grp of svg.querySelectorAll(".lod-txt")) grp.style.display = Number(grp.dataset.h) * px >= 5 ? "" : "none";
    const ins = svg.querySelector(".lod-ins");
    if (ins) ins.style.display = ins.childElementCount > 300 && S.view[2] > g.viewbox[2] * 0.5 ? "none" : "";
  }

  // Ghim phát hiện: vòng khoanh nằm trong toạ độ bản vẽ (phóng theo hình), còn số + đường dẫn tính theo ĐIỂM ẢNH màn
  // hình và vẽ lại mỗi lần phóng/kéo (số luôn cùng cỡ). Ghim gần nhau trên màn hình gộp thành bong bóng "n lỗi"; bấm để
  // phóng tới. Số đặt ở vị trí trống quanh vòng (thử 8 hướng) để không đè lên nhau.
  const MK = {r: 11, gap: 16, merge: 30, minRing: 14};
  function unitsPerPx(svg) {
    const r = svg.getBoundingClientRect(), v = S.view;
    if (!r.width || !r.height || !v) return 0;
    return Math.max(v[2] / r.width, v[3] / r.height);
  }

  function drawMarks(svg) {
    const old = svg.querySelector("g.marks");
    if (old) old.remove();
    const k = unitsPerPx(svg);
    if (!k) return;
    const layer = svgEl("g", {class: "marks"});
    const sevCls = (f) => f.st === "fixed" ? "fixed" : "sev-" + (f.severity === "E" ? "error" : "warn");
    drawSheetFrames(layer, k);
    const placed = S.findings.filter((f) => f.box && visibleFinding(f)).map((f) => {
      const [x0, y0, x1, y1] = f.box, pad = 6 * k, min = MK.minRing * k;
      let x = x0 - pad, y = y0 - pad, w = x1 - x0 + 2 * pad, h = y1 - y0 + 2 * pad;
      if (w < min) { x -= (min - w) / 2; w = min; }
      if (h < min) { y -= (min - h) / 2; h = min; }
      return {f, ring: [x, y, w, h], ax: x + w, ay: y};
    });
    // 1) vòng khoanh (dưới cùng)
    for (const p of placed) {
      const [x, y, w, h] = p.ring;
      const ring = svgEl("g", {class: "mk mk-ring " + sevCls(p.f) + (S.sel === p.f.no ? " sel" : ""), "data-f": p.f.no});
      ring.appendChild(svgEl("circle", {class: "pulse", cx: x + w / 2, cy: y + h / 2, r: 14 * k}));
      ring.appendChild(svgEl("rect", {class: "ring", x, y, width: w, height: h, rx: Math.min(6 * k, w / 2, h / 2)}));
      layer.appendChild(ring);
    }
    // 2) gộp nhóm theo khoảng cách trên màn hình (ghim đang chọn luôn tách riêng)
    const groups = [];
    for (const p of placed.sort((a, b) => a.f.no - b.f.no)) {
      const near = S.sel === p.f.no ? null
        : groups.find((g) => !g.sel && Math.hypot(g.ax - p.ax, g.ay - p.ay) < MK.merge * k);
      if (near) { near.items.push(p); continue; }
      groups.push({ax: p.ax, ay: p.ay, items: [p], sel: S.sel === p.f.no});
    }
    // 3) đặt nhãn: thử 8 hướng, 2 vòng khoảng cách; chọn chỗ không đè nhãn đã đặt
    const dirs = [[1, -1], [-1, -1], [1, 1], [-1, 1], [1.4, 0], [-1.4, 0], [0, -1.4], [0, 1.4]];
    const labels = [];
    for (const g of groups) {
      const big = g.items.length > 1;
      const rr = (big ? MK.r + 3 : MK.r) * k;
      let best = null;
      for (const dist of [MK.gap, MK.gap * 2.2]) {
        for (const [dx, dy] of dirs) {
          const lx = g.ax + dx * dist * k, ly = g.ay + dy * dist * k;
          if (labels.every((o) => Math.hypot(o.x - lx, o.y - ly) > o.r + rr + 2 * k)) { best = [lx, ly]; break; }
        }
        if (best) break;
      }
      if (!best) best = [g.ax + MK.gap * k, g.ay - MK.gap * k];
      labels.push({x: best[0], y: best[1], r: rr});
      layer.appendChild(big ? clusterLabel(g, best, rr, k) : findingLabel(g.items[0], best, rr, k, sevCls(g.items[0].f)));
    }
    svg.appendChild(layer);
  }

  function findingLabel(p, [lx, ly], rr, k, cls) {
    const f = p.f;
    const g = svgEl("g", {class: "mk mk-lbl " + cls + (S.sel === f.no ? " sel" : ""), "data-f": f.no, tabindex: "0", role: "button",
      "aria-label": `${SEV[f.severity][1]} ${f.no}: ${f.title}`});
    g.appendChild(svgEl("line", {class: "lead", x1: p.ax, y1: p.ay, x2: lx, y2: ly}));
    g.appendChild(svgEl("circle", {class: "dot", cx: lx, cy: ly, r: rr}));
    const t = svgEl("text", {class: "num", x: lx, y: ly + 4.5 * k});
    t.style.fontSize = (String(f.no).length > 2 ? 10 : 12.5) * k + "px";
    t.textContent = String(f.no);
    g.appendChild(t);
    const pick = () => selectFinding(f.no, true);
    g.addEventListener("click", pick);
    g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
    return g;
  }

  function clusterLabel(grp, [lx, ly], rr, k) {
    const nos = grp.items.map((p) => p.f.no);
    const worst = grp.items.some((p) => p.f.st !== "fixed" && p.f.severity === "E") ? "sev-error"
      : grp.items.some((p) => p.f.st !== "fixed") ? "sev-warn" : "fixed";
    const g = svgEl("g", {class: "mk mk-cl " + worst, tabindex: "0", role: "button",
      "aria-label": `Nhóm ${nos.length} phát hiện: ${nos.join(", ")}. Bấm để phóng tới.`});
    const tip = svgEl("title"); tip.textContent = `Phát hiện ${nos.join(", ")} — bấm để phóng tới`; g.appendChild(tip);
    g.appendChild(svgEl("line", {class: "lead", x1: grp.ax, y1: grp.ay, x2: lx, y2: ly}));
    g.appendChild(svgEl("circle", {class: "halo", cx: lx, cy: ly, r: rr + 3 * k}));
    g.appendChild(svgEl("circle", {class: "dot", cx: lx, cy: ly, r: rr}));
    const t = svgEl("text", {class: "num", x: lx, y: ly + 4.5 * k});
    t.style.fontSize = 12 * k + "px";
    t.textContent = "×" + nos.length;
    g.appendChild(t);
    const zoomIn = () => {
      let bb = null;
      for (const p of grp.items) { const b = p.f.box; bb = bb ? [Math.min(bb[0], b[0]), Math.min(bb[1], b[1]), Math.max(bb[2], b[2]), Math.max(bb[3], b[3])] : b.slice(); }
      focusCluster(bb, grp.items.length);
    };
    g.addEventListener("click", zoomIn);
    g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); zoomIn(); } });
    return g;
  }

  // Phóng tới nhóm ghim: khung đủ rộng để các ghim tách nhau (mỗi ghim cách nhau > MK.merge px).
  function focusCluster(bb, n) {
    const svg = $("sheet").querySelector("svg");
    if (!svg || !S.view) return;
    const g0 = S.cmp === "after" && S.geoOut ? S.geoOut : S.geo;
    const w0 = Math.max(bb[2] - bb[0], bb[3] - bb[1], 0);
    const minW = g0 ? g0.viewbox[2] / (g0.mode === "svg" ? 5000 : 400) : 0;
    if (S.view[2] * 0.6 < minW) {  // đã phóng hết mức mà ghim vẫn trùng chỗ: chọn ghim đầu, danh sách bên phải có đủ
      const first = S.findings.find((f) => f.box && f.box[0] >= bb[0] && f.box[2] <= bb[2] && f.box[1] >= bb[1] && f.box[3] <= bb[3]);
      if (first) selectFinding(first.no, true);
      return;
    }
    const w = Math.max(minW, Math.min(S.view[2] * 0.6, Math.max(w0 * 2.5, S.view[2] * 0.25))), h = w * S.view[3] / S.view[2];
    const cx = (bb[0] + bb[2]) / 2, cy = (bb[1] + bb[3]) / 2;
    S.view = [cx - w / 2, cy - h / 2, w, h];
    svg.setAttribute("viewBox", S.view.join(" "));
    const g = S.cmp === "after" && S.geoOut ? S.geoOut : S.geo;
    if (g) applyLod(svg, g);
    drawMarks(svg);
  }

  function attachPanZoom(svg, g) {
    const setVB = () => { svg.setAttribute("viewBox", S.view.join(" ")); applyLod(svg, g); drawMarks(svg); };
    const toUser = (cx, cy) => {
      const r = svg.getBoundingClientRect();
      const v = S.view;
      const sc = Math.max(v[2] / r.width, v[3] / r.height);
      const ox = (r.width * sc - v[2]) / 2, oy = (r.height * sc - v[3]) / 2;
      return [v[0] - ox + (cx - r.left) * sc, v[1] - oy + (cy - r.top) * sc, sc];
    };
    svg.addEventListener("wheel", (e) => {
      e.preventDefault();
      const [ux, uy] = toUser(e.clientX, e.clientY);
      zoomAt(e.deltaY < 0 ? 0.8 : 1.25, ux, uy, g);
      setVB();
    }, {passive: false});
    let drag = null; const pointers = new Map(); let pinch = null;
    svg.addEventListener("pointerdown", (e) => {
      if (e.target.closest && e.target.closest(".mk, .sh-frame")) return;
      pointers.set(e.pointerId,[e.clientX,e.clientY]);
      if(pointers.size===2){const pts=[...pointers.values()]; pinch=Math.hypot(pts[0][0]-pts[1][0],pts[0][1]-pts[1][1]);drag=null;}
      else drag = {x: e.clientX, y: e.clientY, v: S.view.slice()};
      svg.setPointerCapture(e.pointerId);
      svg.classList.add("drag");
    });
    svg.addEventListener("pointermove", (e) => {
      if(pointers.has(e.pointerId))pointers.set(e.pointerId,[e.clientX,e.clientY]);
      if(pointers.size===2){const pts=[...pointers.values()];const d=Math.hypot(pts[0][0]-pts[1][0],pts[0][1]-pts[1][1]);const [ux,uy]=toUser((pts[0][0]+pts[1][0])/2,(pts[0][1]+pts[1][1])/2);if(pinch&&d>0)zoomAt(pinch/d,ux,uy,g);pinch=d;setVB();return;}
      if (!drag) return;
      const [, , sc] = toUser(e.clientX, e.clientY);
      S.view = [drag.v[0] - (e.clientX - drag.x) * sc, drag.v[1] - (e.clientY - drag.y) * sc, drag.v[2], drag.v[3]];
      setVB();
    });
    const end = (e) => { pointers.delete(e.pointerId);pinch=null;drag = null; svg.classList.remove("drag"); };
    svg.addEventListener("pointerup", end);
    svg.addEventListener("pointercancel", end);
  }

  function zoomAt(f, ux, uy, g) {
    const v = S.view;
    const full = g.viewbox;
    const w = Math.min(full[2] * 4, Math.max(full[2] / (g.mode === "svg" ? 5000 : 400), v[2] * f));
    const h = w * v[3] / v[2];
    const cx = ux === undefined ? v[0] + v[2] / 2 : ux, cy = uy === undefined ? v[1] + v[3] / 2 : uy;
    const rx = (cx - v[0]) / v[2], ry = (cy - v[1]) / v[3];
    S.view = [cx - rx * w, cy - ry * h, w, h];
  }

  function zoomButton(f) {
    const g = S.cmp === "after" && S.geoOut ? S.geoOut : S.geo;
    if (!g || !g.viewbox || g.empty_reason || g.error || !S.view) return;
    if (f === 0) S.view = tightView(g); else zoomAt(f, undefined, undefined, g);
    const svg = $("sheet").querySelector("svg");
    if (svg) { svg.setAttribute("viewBox", S.view.join(" ")); applyLod(svg, g); drawMarks(svg); }
  }

  function focusBox(bb) {
    const g = S.cmp === "after" && S.geoOut ? S.geoOut : S.geo;
    if (!g || !bb) return;
    const full = tightView(g);
    // đủ rộng để thấy ngữ cảnh, nhưng không thu nhỏ quá khung nhìn gọn (lỗi rất rộng: vừa khít lỗi)
    const bw = Math.max(bb[2] - bb[0], (bb[3] - bb[1]) * full[2] / full[3]);
    const w = Math.max(full[2] * 0.3, Math.min(bw * 3, Math.max(full[2], bw * 1.15))), h = w * full[3] / full[2];
    const cx = (bb[0] + bb[2]) / 2, cy = (bb[1] + bb[3]) / 2;
    S.view = [cx - w / 2, cy - h / 2, w, h];
  }

  function selectFinding(no, openTab) {
    S.sel = no;
    const f = S.findings.find((x) => x.no === no);
    if (f && f.box) focusBox(f.box);
    renderSheet();
    renderFinds();
    if (openTab) rightTab("finds");
    const card = $("finds").querySelector(`[data-no="${no}"]`);
    if (card) card.scrollIntoView({block: "nearest"});
  }

  // ---------- 3D (phòng Thiết kế 3D, chỉ xem) ----------
  async function load3d(path, item) {
    const sheet = $("sheet");
    S.mapOn = false;
    $("viewTag").textContent = "3D · chỉ xem";
    $("viewTag").hidden = false;
    fill(sheet, emptyBox("Đang dựng 3D…", "Dựng tất định từ bản vẽ (hộp đúng kích thước), không dùng AI."));
    let r;
    try { r = await api("/api/scene", item ? {file: path, item} : {file: path}); } catch (e) { fill(sheet, emptyBox("Không dựng được 3D", e.message)); return; }
    if (S.file !== path) return;
    if (r.schema === "cg.scene/2") { render3d2(path, r); return; }
    const c = r.counts;
    $("cvInfo").textContent = `${c.walls} đoạn tường · ${c.modules} mô-đun · ${c.panels} tấm · ${c.gaps} phần thiếu`;
    if (!r.boxes.length) {
      $("t3Item").replaceChildren();
      fill(sheet, emptyBox("Bản vẽ này chưa dựng được 3D", "CAD Guard không tìm thấy hạng mục nào có cả mặt bằng và mặt đứng: khung tên không ghi số bản vẽ, và tiêu đề hình không theo mẫu “MẶT ĐỨNG …” / “MẶT BẰNG …” cùng tên đồ. Sửa tiêu đề hình trong AutoCAD, hoặc mở Bản đồ để AI đề xuất loại hình. ",
        r.gaps.length ? el("br") : null, r.gaps.slice(0, 3).join(" · ")));
      return;
    }
    const cv = el("canvas", {"aria-label": "Mô hình 3D dựng từ bản vẽ, kéo chuột để xoay, cuộn để phóng to", role: "img"});
    fill(sheet, cv, el("div", {class: "sheet-note", text: "Kéo để xoay, cuộn để phóng to. Ảnh minh hoạ từ bản vẽ, không dùng để đo." + (r.truncated ? " Đã cắt bớt hộp." : "")}));
    S.v3d = makeViewer(cv);
    S.v3d.set(r.boxes);
    S.findings = [];
    renderFinds();
  }

  // cg.space/1: cả tầng = tường từ mặt bằng tổng + hạng mục đặt theo ký hiệu số + đồ rời + cửa. Mọi số có nguồn;
  // hạng mục chưa chắc vị trí thành việc cần làm (chọn góc xoay), không tự đoán.
  async function loadSpace(path) {
    const sheet = $("sheet");
    fill(sheet, emptyBox("Đang dựng cả tầng…", "Đọc tường ở mặt bằng tổng, đặt từng hạng mục theo ký hiệu số, không dùng AI."));
    try { renderSpace(path, await api("/api/space", {file: path})); } catch (e) { fill(sheet, emptyBox("Không dựng được cả tầng", e.message)); }
  }
  function renderSpace(path, r) {
    if (S.file !== path) return;
    S.r3d = null;
    $("t3Item").value = "__space__";
    const c = r.counts || {walls: 0, rooms: 0, items: 0, placed: 0, loose: 0, doors: 0, tasks: r.tasks.length};
    $("cvInfo").textContent = `Cả tầng · ${c.walls} mảng tường · ${c.placed}/${c.items} hạng mục đã đặt · ${c.loose} đồ rời · ${c.doors} cửa · ${c.tasks} việc cần làm`;
    const save = async (key, value) => {
      try { renderSpace(path, await api("/api/space/set", {file: path, key, value})); } catch (e) { fail(e, "Lưu cả tầng"); }
    };
    const numEdit = (label, obj, key) => {
      const inp = el("input", {type: "number", min: "1500", max: "6000", step: "10", value: obj ? String(Math.round(obj.value)) : "", "aria-label": label});
      return el("span", {class: "sp-edit"}, b(label + ": "), inp, " mm ", badge(obj ? obj.src : "missing"), " ",
        el("button", {class: "btn-s btn-sm", type: "button", onclick: () => save(key, inp.value)}, "Lưu"),
        obj && obj.src === "user" ? el("button", {class: "link sm", type: "button", onclick: () => save(key, "reset")}, "Bỏ sửa") : null);
    };
    const srcBar = el("div", {class: "v3d-src"},
      el("div", {}, b("Đang xem: "), "Cả tầng", r.plan && r.plan.label ? [" · dựng từ ", r.plan.label] : null),
      r.rooms.length ? el("div", {}, b("Phòng: "), r.rooms.map(x => `${x.name || "?"} (${x.area_m2} m²)`).join(" · ")) : null,
      el("div", {}, numEdit("Cao sàn – trần", r.ceiling, "space:ceiling"), "  ", numEdit("Cao cửa", r.door_h, "space:door_h")),
      el("div", {class: "f-d", text: "Tường lấy từ đa giác nét cắt của mặt bằng tổng; hạng mục đặt bằng cách khớp nét mặt bằng chi tiết với mặt bằng tổng quanh ký hiệu số; đồ rời và cửa là hộp theo khung block, cao mặc định. Ảnh để xem bố cục, không dùng để đo."}));
    const cv = el("canvas", {"aria-label": "Mô hình 3D cả tầng, kéo để xoay, cuộn để phóng to", role: "img"});
    const stage = el("div", {class: "v3d-stage"});
    stage.append(el("div", {}, cv, el("span", {class: "cap", text: "3D cả tầng · kéo trái: xoay · kéo phải: dời · cuộn: phóng"}), stageTools(stage)));
    const METHOD = {match: "Khớp nét", user: "Bạn chọn góc + khớp nét", user_tag: "Bạn chọn góc, đặt theo ký hiệu"};
    const head = el("tr", {}, ["Hạng mục", "Tờ", "Đặt", "Góc xoay", "Độ khớp", ""].map(t => el("th", {text: t})));
    const rows = r.items.map(it => {
      const rot = el("select", {"aria-label": `Góc xoay ${it.name}`}, ["", "0", "90", "180", "270"].map(v => el("option", {value: v, text: v ? v + "°" : "tự động"})));
      rot.value = it.method && it.method.startsWith("user") ? String(it.rot) : "";
      return el("tr", {}, el("td", {}, b(it.name || it.item)), el("td", {text: it.sheet_names || ""}),
        el("td", {text: it.placed ? (METHOD[it.method] || it.method) : "Chưa đặt"}),
        el("td", {}, rot, " ", el("button", {class: "btn-s btn-sm", type: "button", onclick: () => save(`place:${it.item}`, rot.value || "reset")}, "Lưu")),
        el("td", {text: it.score != null ? Math.round(it.score * 100) + "%" : "—"}),
        el("td", {}, el("button", {class: "link sm", type: "button", onclick: () => load3d(path, it.item)}, "Xem hạng mục")));
    });
    const tasks = r.tasks.map(t => el("div", {class: "gap3d"}, el("div", {class: "g-title", text: t.title}),
      t.why ? el("div", {class: "g-why", text: "Vì sao: " + t.why}) : null,
      t.fix_here ? el("div", {class: "g-fix", text: "Sửa nhanh tại đây: " + t.fix_here}) : null,
      t.fix_cad ? el("div", {class: "g-fix", text: "Sửa gốc trong AutoCAD: " + t.fix_cad}) : null));
    const dl = el("button", {type: "button", class: "btn-s btn-sm", text: "Tải GLB cả tầng", title: "Mở bằng D5, Twinmotion, Blender… để diễn họa", onclick: async () => {
      try {
        const g = await api("/api/space/glb", {file: path});
        const bin = Uint8Array.from(atob(g.b64), ch => ch.charCodeAt(0));
        el("a", {href: URL.createObjectURL(new Blob([bin], {type: "model/gltf-binary"})), download: g.name}).click();
      } catch (e) { fail(e, "Tải GLB cả tầng"); }
    }});
    const bottom = el("div", {class: "v3d-bottom"}, el("div", {class: "bar-act"}, dl, el("small", {text: ` mã cảnh ${r.space_hash || ""}`})),
      el("table", {class: "tbl3d"}, head, rows),
      tasks.length ? el("div", {class: "sub-h", text: "Việc cần làm để dựng đủ cả tầng"}) : null, tasks,
      (r.notes || []).map(n => el("small", {text: n})));
    fill($("sheet"), el("div", {class: "v3d"}, srcBar, stage, bottom));
    if (S.v3d) { S.v3d.stop(); S.v3d = null; }
    S.v3d = makeViewer(cv);
    S.v3d.set(r.boxes);
  }
  // Khung xem: kéo mép dưới để đổi chiều cao (nhớ theo máy), góc nhìn nhanh, toàn màn hình.
  function stageTools(stage, fronts) {
    let h = null;
    try { h = localStorage.getItem("cg.stageH"); } catch (e) { h = null; }
    if (h && +h >= 260) stage.style.setProperty("--stage-h", h + "px");
    new ResizeObserver(() => {
      if (document.fullscreenElement === stage || !stage.isConnected) return;
      try { localStorage.setItem("cg.stageH", String(Math.round(stage.getBoundingClientRect().height))); } catch (e) { /* bỏ qua */ }
    }).observe(stage);
    const v = (y, p) => () => { if (S.v3d && S.v3d.view) S.v3d.view(y, p); };
    const btn = (t, title, fn) => el("button", {class: "btn-s btn-sm", type: "button", title, onclick: (e) => { e.stopPropagation(); fn(); }}, t);
    return el("div", {class: "v3d-tools"},
      btn("Trước", "Nhìn thẳng mặt trước (như mặt đứng)", v(0, 0)),
      btn("Trên", "Nhìn từ trên xuống (như mặt bằng)", v(0, 1.5)),
      btn("3/4", "Góc nhìn phối cảnh", v(0.8, 0.6)),
      btn("⛶", "Toàn màn hình (Esc để thoát)", () => {
        if (document.fullscreenElement) document.exitFullscreen();
        else if (stage.requestFullscreen) stage.requestFullscreen().catch(() => {});
      }),
      fronts ? openTools() : null);
  }
  // Đóng/mở cánh: cánh xoay quanh bản lề, ngăn kéo trượt ra (server gửi `m` cho từng hộp). Nhớ độ mở khi dựng lại.
  function openTools() {
    const cur = () => (S.open3d || 0);
    const label = () => (cur() > 0.5 ? "Đóng cánh" : "Mở cánh");
    const rng = el("input", {type: "range", min: "0", max: "100", step: "1", value: String(Math.round(cur() * 100)),
      "aria-label": "Độ mở cánh và ngăn kéo (%)", title: "Kéo để mở cánh/ngăn kéo từng phần"});
    const tb = el("button", {class: "btn-s btn-sm", type: "button", title: "Mở/đóng tất cả cánh và ngăn kéo để thấy từng cánh và bên trong"}, label());
    const sync = () => { tb.textContent = label(); tb.setAttribute("aria-pressed", cur() > 0.5 ? "true" : "false"); rng.value = String(Math.round(cur() * 100)); };
    const onStep = (t) => { S.open3d = t; sync(); };
    tb.addEventListener("click", (e) => {
      e.stopPropagation();
      if (S.v3d && S.v3d.open) S.v3d.open(cur() > 0.5 ? 0 : 1, true, onStep);
    });
    rng.addEventListener("input", (e) => {
      e.stopPropagation();
      if (S.v3d && S.v3d.open) S.v3d.open(+rng.value / 100, false, onStep);
    });
    for (const ev of ["pointerdown", "pointermove"]) rng.addEventListener(ev, (e) => e.stopPropagation());
    sync();
    return [tb, rng];
  }
  // Toạ độ XY của một đỉnh khi mặt trước mở t (0..1): xoay quanh trục bản lề đứng, hoặc trượt ra phía trước (Y giảm).
  function moveXY(m, t, x, y) {
    if (!m || !t) return [x, y];
    if (m.open === "slide") return [x, y - t * (m.slide || 0)];
    const a = (m.hinge === "r" ? 1 : -1) * t * (m.angle || 90) * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
    const dx = x - m.pivot[0], dy = y - m.pivot[1];
    return [m.pivot[0] + dx * c - dy * s, m.pivot[1] + dx * s + dy * c];
  }
  async function showBench() {
    const bz = busy("Đang chấm điểm dựng 3D…", "Dựng lại từng hạng mục có đáp án theo từng cách đọc.");
    let r;
    try { r = await api("/api/bench3d", {}); } catch (e) { bz.done(); fail(e, "Chấm điểm 3D"); return; }
    bz.done();
    const PL = {code: "Chỉ code", "code+suggest": "Code + gợi ý tự áp", "code+ai": "Code + AI"};
    const n = notice({kind: "info", title: `Chấm điểm dựng 3D · ${r.answers} hạng mục có đáp án`,
      msg: r.answers ? "Điểm = số khối đúng hoàn toàn (4 số đo lệch ≤ 2 mm, đúng dạng, đúng số cánh) / số khối." :
        "Chưa có đáp án. Ở màn 3D, khi một hạng mục đã đúng hết, bấm “Lưu làm đáp án”."});
    if (r.answers) {
      n.append(el("table", {class: "tbl3d"}, el("tr", {}, ["Cách đọc", "Điểm", "Đúng số khối", "Rộng", "Sâu", "Cao", "Cao độ"].map(t => el("th", {text: t}))),
        Object.entries(r.summary).map(([k, s]) => el("tr", {}, el("td", {text: PL[k] || k}), el("td", {}, b(s.score_pct + "%")), el("td", {text: s.count_ok_pct + "%"}),
          ["w", "d", "h", "z0"].map(x => el("td", {text: s.dims_pct[x] + "%"}))))));
      n.append(el("table", {class: "tbl3d"}, el("tr", {}, ["Hạng mục", ...Object.keys(r.summary).map(k => PL[k] || k)].map(t => el("th", {text: t}))),
        r.rows.map(row => el("tr", {}, el("td", {text: row.item_name || row.item}),
          row.skipped ? el("td", {text: row.skipped}) : Object.keys(r.summary).map(k => el("td", {text: row.scores[k] ? `${row.scores[k].correct}/${row.scores[k].modules_answer}` : "—"}))))));
    }
  }
  function badge(kind) {
    return el("span", {class: "src-b src-" + (kind || "missing"), title: SRC_TIP[kind] || "", text: SRC_BADGE[kind] || kind});
  }

  // cg.scene/2: một hạng mục dựng từ mặt bằng + mặt đứng. Đối chiếu 2D ↔ 3D: dựng từ hình nào/tờ nào, mỗi số đo
  // lấy từ đâu (Ghi = kích thước trên bản vẽ, Đo = đo trên nét, Đã sửa = người dùng), xem song song hình 2D gốc,
  // bấm khối để tô sáng cả hai bên, sửa số đo (lưu vết, Bỏ sửa), hỏi trợ lý về một khối.
  const SRC_BADGE = {dimension: "Ghi", geometry: "Đo", user: "Đã sửa", default: "Mặc định", missing: "Thiếu"};
  const SRC_TIP = {dimension: "Lấy từ kích thước ghi trên bản vẽ", geometry: "Đo trên nét vẽ (không có kích thước ghi)",
    user: "Bạn đã sửa số này", default: "Giá trị mặc định", missing: "Chưa có"};
  function syncToolbar() {
    const scene = !!(S.dept && S.dept.view === "scene");
    for (const id of ["toolUnicode", "toolLang", "toolMode", "toolTranslate", "toolTemplate", "toolBulk", "toolReview", "layoutLbl"]) {
      const x = $(id); if (x) x.hidden = scene;
    }
    $("tools3d").hidden = !scene;
  }
  function seg(id, v) { for (const x of $$(`#${id} button`)) x.setAttribute("aria-pressed", x.dataset.v === v ? "true" : "false"); }
  async function draw2d(host, path, r, viewId) {
    const pv = r.provenance;
    fill(host, el("span", {class: "cap", text: "Đang tải hình 2D…"}));
    let g;
    try { g = await api("/api/scene/source", {file: path, item: r.item, view: viewId}); } catch (e) { fill(host, el("span", {class: "cap", text: e.message})); return; }
    const [x0, y0, x1, y1] = g.box, pad = 0.06 * Math.max(x1 - x0, y1 - y0);
    const svg = svgEl("svg", {viewBox: `${x0 - pad} ${-(y1 + pad)} ${x1 - x0 + 2 * pad} ${y1 - y0 + 2 * pad}`, role: "img", "aria-label": g.label});
    const root = svgEl("g", {transform: "scale(1,-1)"});
    const sw = 0.0015 * Math.max(x1 - x0, y1 - y0);
    const hl = new Set();
    const sel = S.sel3d && pv.modules[S.sel3d];
    if (sel) for (const k of Object.keys(sel.refs)) for (const h of sel.refs[k]) hl.add(h);
    for (const [h, k, d] of g.items) {
      const cls = hl.has(h) ? "ln hl" : "ln";
      if (k === "L") root.append(svgEl("line", {x1: d[0], y1: d[1], x2: d[2], y2: d[3], class: cls, "stroke-width": sw}));
      else if (k === "P" || k === "Q") { const pts = []; for (let i = 0; i < d.length; i += 2) pts.push(d[i] + "," + d[i + 1]); root.append(svgEl(k === "Q" ? "polygon" : "polyline", {points: pts.join(" "), class: cls, "stroke-width": sw})); }
      else if (k === "C") root.append(svgEl("circle", {cx: d[0], cy: d[1], r: d[2], class: cls, "stroke-width": sw}));
      else if (k === "A") {
        const a0 = d[3] * Math.PI / 180, a1 = d[4] * Math.PI / 180, sx = d[0] + d[2] * Math.cos(a0), sy = d[1] + d[2] * Math.sin(a0), ex = d[0] + d[2] * Math.cos(a1), ey = d[1] + d[2] * Math.sin(a1);
        const large = ((d[4] - d[3] + 360) % 360) > 180 ? 1 : 0;
        root.append(svgEl("path", {d: `M${sx} ${sy} A${d[2]} ${d[2]} 0 ${large} 1 ${ex} ${ey}`, class: cls, "stroke-width": sw}));
      } else if (k === "D" || k === "T") {
        const size = k === "D" ? 0.018 * Math.max(x1 - x0, y1 - y0) : Math.max(d[3] || 0, 0.012 * Math.max(x1 - x0, y1 - y0));
        const txt = svgEl("text", {x: d[0], y: -d[1], transform: "scale(1,-1)", "font-size": size, class: hl.has(h) ? "tx hl" : (k === "D" ? "dim" : "tx"),
          "text-anchor": k === "D" ? "middle" : "start"});
        txt.textContent = k === "D" ? String(Math.round(d[2])) : d[2];
        root.append(txt);
      }
    }
    // khung các khối dựng được trên hình này: bấm để chọn (tô sáng bên 3D và hàng trong bảng)
    const isPlan = pv.views[viewId] && pv.views[viewId].kind === "plan";
    const pbox = isPlan ? pv.views[viewId].box : null;
    for (const m of r.modules) {
      const src = pv.modules[m.id];
      if (!src) continue;
      let rect = null;
      if (!isPlan && src.elevation === viewId && src.ebox.length === 4) rect = src.ebox;
      if (isPlan && src.plan === viewId && pbox) rect = [pbox[0] + m.x, pbox[1] + m.y, pbox[0] + m.x + m.w.value, pbox[1] + m.y + m.d.value];
      if (!rect) continue;
      const rc = svgEl("rect", {x: rect[0], y: rect[1], width: rect[2] - rect[0], height: rect[3] - rect[1], class: "mod" + (S.sel3d === m.id ? " on" : ""), "stroke-width": sw * 2});
      rc.addEventListener("click", () => select3d(m.id));
      const tl = svgEl("title", {}); tl.textContent = `${m.id} — bấm để chọn`; rc.append(tl);
      root.append(rc);
    }
    // đường chia khối: đã Đồng ý (liền, xanh) và đang đề xuất (đứt, cam) — chỉ trên mặt đứng chính
    if (!isPlan) {
      const onMain = r.modules.some(m => (pv.modules[m.id] || {}).elevation === viewId);
      const line = (x, cls, tip) => {
        const ln = svgEl("line", {x1: x, y1: y0, x2: x, y2: y1, class: cls, "stroke-width": sw * 3});
        const t = svgEl("title", {}); t.textContent = tip; ln.append(t); root.append(ln);
      };
      if (onMain) {
        for (const x of r.splits || []) line(x, "cut-ok", "Đã chia khối tại vách này");
        for (const p of r.proposals) if (p.key === `split:${r.item}`) line(+p.value, "cut-prop", "Đề xuất chia khối: " + (p.reason || ""));
      }
    }
    svg.append(root);
    fill(host, svg, el("span", {class: "cap", text: g.label + (g.truncated ? " (đã cắt bớt)" : "")}));
  }
  function select3d(id) {
    S.sel3d = S.sel3d === id ? null : id;
    if (S.r3d) render3d2(S.file, S.r3d, true);
  }
  function render3d2(path, r, keepView) {
    S.r3d = r;
    const sheet = $("sheet");
    const pv = r.provenance || {views: {}, modules: {}, elevations: [], used: {elevations: [], plans: []}, sheets: []};
    const fmt = v => (Math.round(v * 10) / 10).toString();
    $("cvInfo").textContent = `Hạng mục ${pv.item_name || r.item} · ${r.counts.modules} khối · ${r.counts.fronts} cánh/ngăn kéo · ${r.counts.gaps} phần thiếu · mã cảnh ${r.scene_hash}`;
    // thanh công cụ: chọn hạng mục
    const isel = $("t3Item");
    isel.replaceChildren(el("option", {value: "__space__", text: "★ Cả tầng (mặt bằng tổng + các hạng mục)"}), ...r.items.map(it => el("option", {value: it.id,
      text: `${it.name || it.id}${it.sheet_names ? " · " + it.sheet_names : ""}${it.plans && it.elevations ? "" : " (chưa dựng được)"}`})));
    isel.title = "Hạng mục (tên lấy từ khung tên) và các tờ chứa hạng mục đó";
    isel.value = r.item;
    if (!isel.dataset.bound) { isel.dataset.bound = "1"; isel.addEventListener("change", () => { S.sel3d = null; isel.value === "__space__" ? loadSpace(S.file) : load3d(S.file, isel.value); }); }
    const mode = S.mode3d || "3d";
    seg("t3Mode", mode);
    seg("t3Body", S.body3d || "block");
    const save = async (key, value) => {
      try { render3d2(path, await api("/api/scene/set", {file: path, item: r.item, key, value}), true); } catch (e) { fail(e, "Lưu số liệu 3D"); }
    };
    // nguồn: dựng từ hình nào, tờ nào; mặt đứng nào chưa dùng
    const vlabel = (id) => (pv.views[id] ? pv.views[id].label : id);
    const elevChips = pv.elevations.map(e => el("span", {class: "chip" + (e.used ? " used" : " off"), title: e.used ? "Đang dùng để dựng khối" : (e.linked ? "Đã ghép với mặt bằng, chưa dùng để dựng" : "Chưa ghép với mặt bằng (xem Phần thiếu)")},
      (e.used ? "✓ " : "") + e.label,
      !e.used && e.linked ? [" ", el("button", {class: "link sm", type: "button", onclick: () => save(`main:${r.item}`, e.id)}, "Dựng từ hình này")] : null));
    const srcBar = el("div", {class: "v3d-src"},
      el("div", {}, b("Đang xem: "), pv.item_name || r.item, ` · ${pv.sheets.length} tờ của hạng mục`),
      el("div", {}, b("Dựng từ: "), pv.used.elevations.map(vlabel).join("; ") || "—", " + ", pv.used.plans.map(vlabel).join("; ") || "—",
        ...[...pv.used.elevations, ...pv.used.plans].filter(id => pv.views[id] && (pv.views[id].handles || []).length).map(id =>
          [" ", el("button", {class: "link sm", type: "button", title: "Mở AutoCAD và phóng tới " + vlabel(id),
            onclick: () => showInAutocad({handles: pv.views[id].handles, items: []})}, (pv.views[id].kind === "plan" ? "Mặt bằng" : "Mặt đứng") + " trong AutoCAD")])),
      pv.elevations.length > 1 || pv.main_pick ? el("div", {}, b("Các mặt đứng của hạng mục: "), elevChips,
        pv.main_pick ? el("button", {class: "link sm", type: "button", onclick: () => save(`main:${r.item}`, "reset")}, "Về mặc định") : null) : null,
      el("div", {class: "f-d", text: "Bấm một hàng trong bảng hoặc một khung khối trên hình 2D để tô sáng cả hai bên. Bấm vào số đo để sửa nếu dựng sai; nhãn cho biết số lấy từ đâu."}));
    // sân khấu: 3D | song song | 2D
    const stage = el("div", {class: "v3d-stage"});
    const host3 = el("div", {});
    const host2 = el("div", {});
    const cv = el("canvas", {"aria-label": "Mô hình 3D dựng từ bản vẽ, kéo chuột để xoay, cuộn để phóng to", role: "img"});
    host3.append(cv, el("span", {class: "cap", text: "3D · kéo trái: xoay · kéo phải: dời · cuộn: phóng"}), stageTools(stage, r.counts.fronts > 0));
    if (mode !== "2d") stage.append(host3);
    if (mode !== "3d") stage.append(host2);
    const viewSel = el("select", {"aria-label": "Hình 2D để đối chiếu"},
      [...pv.used.elevations, ...pv.used.plans].map(v => el("option", {value: v, text: vlabel(v)})));
    if (S.view2d && [...pv.used.elevations, ...pv.used.plans].includes(S.view2d)) viewSel.value = S.view2d;
    viewSel.addEventListener("change", () => { S.view2d = viewSel.value; draw2d(host2, path, r, viewSel.value); });
    // bảng khối: số đo + nhãn nguồn, bấm để sửa
    const head = el("tr", {}, ["Khối", "Loại", "Rộng", "Sâu", "Cao", "Cao độ chân", "Cánh/ngăn kéo", "Đợt", ""].map(t => el("th", {text: t})));
    const rows = r.modules.map(m => {
      const src = pv.modules[m.id] || {user: []};
      const cell = (k) => {
        const td = el("td", {class: "ed", title: SRC_TIP[m[k].kind] + " · bấm để sửa"}, fmt(m[k].value), el("span", {class: "src-b src-" + m[k].kind, text: SRC_BADGE[m[k].kind] || m[k].kind}));
        td.addEventListener("click", (ev) => {
          ev.stopPropagation();
          const inp = el("input", {type: "number", min: "0", step: "1", value: fmt(m[k].value), "aria-label": `${m.id} ${k}`});
          fill(td, inp, el("button", {class: "btn-s btn-sm", type: "button", onclick: (e2) => { e2.stopPropagation(); save(`module:${m.id}:${k}`, inp.value); }}, "Lưu"),
            (src.user || []).includes(k) ? el("button", {class: "link sm", type: "button", onclick: (e2) => { e2.stopPropagation(); save(`module:${m.id}:${k}`, "reset"); }}, "Bỏ sửa") : null);
          inp.focus();
        });
        return td;
      };
      const tr = el("tr", {class: S.sel3d === m.id ? "on" : ""}, el("td", {}, b(m.id)), el("td", {text: m.label || m.type_vi || m.kind}),
        cell("w"), cell("d"), cell("h"), cell("z0"), el("td", {text: String(m.fronts)}), el("td", {text: String(m.shelves)}),
        el("td", {}, el("button", {class: "link sm", type: "button", title: "Nhờ trợ lý AI kiểm khối này và đề xuất sửa (bạn vẫn là người lưu)",
          onclick: (ev) => { ev.stopPropagation(); askAI(feedbackPrompt(r, m, pv)); }}, "Hỏi trợ lý"),
          (pv.modules[m.id] || {}).handles && pv.modules[m.id].handles.length ? el("button", {class: "link sm", type: "button",
            title: "Mở AutoCAD và chọn các nét của khối này trên mặt đứng để chỉnh thiết kế",
            onclick: (ev) => { ev.stopPropagation(); showInAutocad({handles: pv.modules[m.id].handles, items: []}); }}, "Tới trong AutoCAD") : null));
      tr.addEventListener("click", () => select3d(m.id));
      return tr;
    });
    const gaps = r.gaps.map(g => el("div", {class: "gap3d"}, g.explain ? [
        el("div", {class: "g-title", text: `${g.explain.title} · ${g.explain.where}`}),
        el("div", {class: "g-why", text: "Vì sao: " + g.explain.why}),
        g.fields.length ? el("div", {class: "g-fix", text: "Sửa nhanh tại đây: " + g.explain.fix_here}) : null,
        el("div", {class: "g-fix", text: "Sửa gốc trong AutoCAD: " + g.explain.fix_cad})]
      : el("div", {text: g.message}), g.fields.map(f => {
      const inp = f.kind === "choice" ? el("select", {}, el("option", {value: "", text: "— chọn —"}), f.options.map(o => el("option", {value: o, text: (f.labels && f.labels[o]) || o})))
                                      : el("input", {type: "number", min: "0", step: "any", "aria-label": f.label});
      return el("label", {}, `${f.label}${f.kind === "choice" ? "" : " (mm)"} `, inp,
        el("button", {type: "button", class: "btn", text: "Lưu", onclick: () => inp.value && save(f.key, inp.value)}));
    })));
    const keyVi = (k) => {
      const m = /^module:([^:]+):(w|d|h|z0)$/.exec(k);
      if (m) return `${{w: "Rộng", d: "Chiều sâu", h: "Cao", z0: "Cao độ chân"}[m[2]]} khối ${m[1]}`;
      if (k === "room:ceiling") return "Cao sàn – trần";
      if (k.startsWith("link:")) return "Ghép mặt đứng với mặt bằng";
      if (k.startsWith("label:")) return `Nhãn khối ${k.slice(6)}`;
      if (k.startsWith("split:")) return "Chia khối tại vách";
      return k;
    };
    const props = r.proposals.map(p => el("div", {class: "gap3d prop3d"},
      el("span", {class: "src-b " + (p.origin === "code" ? "src-geometry" : "src-user"),
        text: {code: "Code đọc", llm: "AI đọc", "code+llm": "Code + AI đồng ý"}[p.origin] || "AI đọc"}), " ",
      b(keyVi(p.key)), p.key.startsWith("split:") ? "" : ` = ${p.value}${/^module:|^room:/.test(p.key) ? " mm" : ""}`,
      p.reason ? el("div", {class: "g-why", text: p.reason}) : null,
      p.evidence && p.evidence.length ? el("small", {text: `Bằng chứng trên bản vẽ: ${p.evidence.length} kích thước/chữ (đã kiểm có đúng số này)`}) : null, " ",
      el("button", {type: "button", class: "btn", text: "Xác nhận", onclick: () => save(p.key, p.value)})));
    const warnMods = r.modules.filter(m => ["w", "d", "h", "z0"].some(k => m[k].kind === "default" || m[k].kind === "missing"));
    const splitBar = (r.splits || []).length ? el("div", {class: "f-d"}, `Đã chia khối tại ${r.splits.length} vách bạn Đồng ý. `,
      el("button", {class: "link sm", type: "button", onclick: () => save(`split:${r.item}`, "reset")}, "Bỏ chia khối")) : null;
    const banner = (r.gaps.length || r.proposals.length) ? el("div", {class: "warn3d", role: "alert"},
      el("div", {class: "w-head"}, b(`⚠ ${r.gaps.length} chỗ CAD Guard chưa đọc được từ bản vẽ`),
        warnMods.length ? ` · ${warnMods.length} khối đang dùng số tạm (tô màu cam trên 3D)` : "",
        el("div", {class: "f-d", text: "3D sai ở đây là do bản vẽ thiếu số hoặc trình bày khác mẫu CAD Guard đọc được. Nhập số đúng, hoặc nhờ code/AI đọc lại bản vẽ (mặt cắt, ghi chú) rồi xác nhận."})),
      el("div", {class: "w-act"},
        el("button", {class: "btn-s btn-sm", type: "button", title: "Tìm chiều sâu ở kích thước ngang của các mặt cắt cùng hạng mục", onclick: () => runSceneAI(path, r.item, false)}, "Gợi ý bằng code"),
        el("button", {class: "btn-p btn-sm", type: "button", title: "AI đọc tiêu đề, kích thước, ghi chú của hạng mục; mỗi số phải dẫn đúng kích thước/chữ trên bản vẽ", onclick: () => runSceneAI(path, r.item, true)}, "Nhờ AI đọc bản vẽ"),
        el("button", {class: "btn-s btn-sm", type: "button", title: "Khai một lần cách công ty/người vẽ trình bày (layer thân tủ, ghi chú…) để mọi bản vẽ kiểu này đọc đúng", onclick: () => openDrafting()}, "Hồ sơ trình bày")),
      props.length ? [el("div", {class: "sub-h", text: "Đề xuất chờ bạn xác nhận"}), props] : null,
      gaps.length ? el("details", {class: "w-gaps", open: gaps.length <= 3}, el("summary", {text: `Từng chỗ thiếu, vì sao và ô nhập (${gaps.length})`}), gaps) : null) : null;
    const room = r.room.ceiling ? `Cao sàn–trần ${fmt(r.room.ceiling)} · ${r.room.src}` : "Chưa có cao sàn–trần";
    const ceil = el("input", {type: "checkbox", "aria-label": "Hiện trần"});
    const dl = el("button", {type: "button", class: "btn-s btn-sm", text: "Tải GLB", onclick: async () => {
      try {
        const g = await api("/api/scene/glb", {file: path, item: r.item});
        const bin = Uint8Array.from(atob(g.b64), c => c.charCodeAt(0));
        el("a", {href: URL.createObjectURL(new Blob([bin], {type: "model/gltf-binary"})), download: g.name}).click();
      } catch (e) { fail(e, "Tải GLB"); }
    }});
    const ansBtn = el("button", {type: "button", class: "btn-s btn-sm", text: "Lưu làm đáp án",
      title: "Người kỹ thuật: khi mọi khối và số đo đã đúng như bản vẽ, lưu làm đáp án để đo độ chính xác của CAD Guard", onclick: async () => {
        const ok = await confirmDialog({title: "Lưu làm đáp án", body: ["Chỉ lưu khi bạn đã kiểm MỌI khối và số đo (rộng, sâu, cao, cao độ chân, số cánh) đúng như bản vẽ.",
          "Đáp án dùng để chấm điểm các cách đọc của CAD Guard (chỉ code, code + gợi ý, code + AI). Lưu trong dự án, không gửi đi đâu."], yes: "Lưu đáp án", no: "Huỷ"});
        if (!ok) return;
        try { const a = await api("/api/scene/answer", {file: path, item: r.item}); toast(`Đã lưu đáp án ${a.modules} khối.`); } catch (e) { fail(e, "Lưu đáp án"); }
      }});
    const benchBtn = el("button", {type: "button", class: "btn-s btn-sm", text: "Chấm điểm 3D",
      title: "Chấm các cách đọc của CAD Guard trên mọi đáp án đã lưu trong dự án", onclick: () => showBench()});
    const bottom = el("div", {class: "v3d-bottom"},
      r.readiness ? el("div", {class: "ready3d"}, b(`Sẵn sàng: ${r.readiness.level}`),
        ` · ${r.readiness.modules} khối, ${r.readiness.complete} đủ 4 số đo · ${r.readiness.from_dimension_pct}% số đo lấy từ kích thước ghi trên bản vẽ, ${r.readiness.from_user_pct}% bạn đã sửa · ${r.readiness.gaps} phần thiếu`) : null,
      el("div", {class: "bar-act"}, mode !== "3d" ? [el("span", {text: "Hình 2D: "}), viewSel] : null, el("label", {}, ceil, " hiện trần"), dl, ansBtn, benchBtn, el("small", {text: ` mã cảnh ${r.scene_hash}`})),
      el("table", {class: "tbl3d"}, head, rows), el("div", {text: room}), cutlistBox(r),
      r.notes.map(n => el("small", {text: n})));
    S.warn3d = new Set(warnMods.map(m => m.id));
    fill(sheet, el("div", {class: "v3d"}, srcBar, splitBar, banner, stage, bottom));
    if (S.v3d) { S.v3d.stop(); S.v3d = null; }
    if (mode !== "2d") {
      S.v3d = makeViewer(cv);
      const show = () => S.v3d.set(boxesFor(r).filter(bx => ceil.checked || bx.k !== "ceiling"));
      ceil.addEventListener("change", show);
      show();
    }
    if (mode !== "3d") draw2d(host2, path, r, viewSel.value || pv.used.elevations[0]);
    S.findings = [];
    renderFinds();
  }
  function setBody3d(v) {
    S.body3d = v;
    seg("t3Body", v);
    if (S.r3d && !S.mapOn) render3d2(S.file, S.r3d, true);
  }
  async function openConstruction() {
    let c;
    try { c = await api("/api/construction"); } catch (e) { fail(e, "Mở hồ sơ kết cấu xưởng"); return; }
    const d = $("drawer");
    const inputs = {};
    const origin = {default: "mặc định", machine: "cả máy", project: "dự án này"};
    const rows = c.fields.map((f) => {
      const id = "cons-" + f.key;
      let inp;
      if (f.type === "choice") inp = el("select", {id}, Object.entries(f.options).map(([v, t]) => el("option", {value: v, text: t})));
      else inp = el("input", {id, type: f.type === "number" ? "number" : "text", step: "any", min: f.min, max: f.max});
      inp.value = c.values[f.key];
      inputs[f.key] = inp;
      return el("div", {class: "task"},
        el("label", {for: id}, b(f.label), f.unit ? ` (${f.unit})` : "", " ", el("span", {class: "src-b " + (c.origin[f.key] === "default" ? "src-default" : "src-user"), text: origin[c.origin[f.key]]})),
        el("div", {}, inp),
        f.help ? el("div", {class: "f-d", text: f.help}) : null,
        f.source ? el("div", {class: "f-d", text: "Nguồn số mặc định: " + f.source}) : null);
    });
    const scope = el("select", {"aria-label": "Lưu cho"}, el("option", {value: "machine", text: "Cả máy (mọi dự án)"}), el("option", {value: "project", text: "Riêng dự án này"}));
    const save = async (reset) => {
      const values = {};
      for (const [k, x] of Object.entries(inputs)) values[k] = x.value;
      try { await api("/api/construction", reset ? {scope: scope.value, reset: true} : {scope: scope.value, values}); }
      catch (e) { fail(e, "Lưu hồ sơ kết cấu"); return; }
      toast(reset ? "Đã bỏ hồ sơ đã lưu ở phạm vi này." : "Đã lưu hồ sơ kết cấu xưởng. Tấm ván và danh sách cắt dựng lại theo số mới.");
      closeDrawer();
      if (S.file && S.dept && S.dept.view === "scene") load3d(S.file, S.r3d ? S.r3d.item : undefined);
      else if (S.mapOn) loadMap(false);
    };
    const close = el("button", {class: "iconbtn", type: "button", "aria-label": "Đóng", onclick: closeDrawer}, icon("x"));
    fill(d,
      el("div", {class: "dr-h"}, el("div", {class: "grow1"}, el("h2", {id: "drTitle", text: "Kết cấu xưởng"}),
        el("div", {class: "f-d", text: c.confirmed ? "Đã có hồ sơ lưu. Sửa để khớp thực tế xưởng." : "Đang dùng SỐ MẶC ĐỊNH thường gặp. Hãy để người làm kỹ thuật/xưởng kiểm và lưu."})), close),
      el("div", {class: "dr-b"},
        el("p", {class: "f-d", text: "Không có chuẩn quốc gia về kết cấu tủ: mỗi xưởng tự khai. Các số này dùng để dựng tấm ván, danh sách cắt, dán cạnh, số bản lề (mô hình tham khảo, không phải dữ liệu chạy máy). Bản vẽ không bị sửa."}),
        rows),
      el("div", {class: "dr-f"}, el("label", {}, "Lưu cho ", scope), el("span", {class: "spacer"}),
        el("button", {class: "btn-s", type: "button", onclick: () => save(true)}, "Về mặc định"),
        el("button", {class: "btn-p", type: "button", onclick: () => save(false)}, "Lưu")));
    d.classList.add("on");
    close.focus();
  }
  // Hồ sơ trình bày: cách công ty/người vẽ trình bày (vai trò layer, nghĩa ghi chú). Code/AI đề xuất có bằng chứng,
  // người dùng Đồng ý từng mục; lưu cả máy hoặc riêng dự án; code đọc mọi bản vẽ theo hồ sơ này.
  async function openDrafting(found) {
    let c;
    try { c = await api("/api/drafting", {file: S.file}); } catch (e) { fail(e, "Mở hồ sơ trình bày"); return; }
    const d = $("drawer");
    const ORIG = {default: "mặc định", machine: "cả máy", project: "dự án này", code: "code đoán"};
    const scope = el("select", {"aria-label": "Lưu cho"}, el("option", {value: "machine", text: "Cả máy (mọi dự án)"}), el("option", {value: "project", text: "Riêng dự án này"}));
    const reload = () => {
      if (S.file && S.dept && S.dept.view === "scene") load3d(S.file, S.r3d ? S.r3d.item : undefined);
      else if (S.mapOn) loadMap(false);
    };
    const savePatch = async (patch, msg, keep) => {
      try { await api("/api/drafting/save", {scope: scope.value, patch, file: S.file}); } catch (e) { fail(e, "Lưu hồ sơ trình bày"); return; }
      toast(msg || "Đã lưu hồ sơ trình bày. 3D và bản đồ đọc lại theo hồ sơ mới.");
      reload();
      openDrafting(keep);
    };
    const roleSel = (cur) => el("select", {"aria-label": "Vai trò layer"}, Object.entries(c.roles).map(([k, v]) => el("option", {value: k, text: v, selected: k === cur})));
    const layerRows = c.layers.map((x) => {
      const sel = roleSel(x.role);
      return el("tr", {}, el("td", {text: x.layer}), el("td", {text: String(x.lines)}), el("td", {}, sel),
        el("td", {}, el("span", {class: "src-b " + (x.origin === "code" ? "src-geometry" : "src-user"), text: ORIG[x.origin] || x.origin})),
        el("td", {}, el("button", {class: "btn-s btn-sm", type: "button", onclick: () => savePatch({layer_roles: {[x.layer]: sel.value}})}, "Lưu"),
          x.origin !== "code" ? el("button", {class: "link sm", type: "button", onclick: () => savePatch({layer_roles: {[x.layer]: "reset"}})}, "Bỏ") : null));
    });
    const kwRows = c.keywords.map((k) => el("tr", {}, el("td", {text: k.text}), el("td", {text: c.meanings[k.meaning] || k.meaning}),
      el("td", {}, el("span", {class: "src-b " + (k.origin === "default" ? "src-default" : "src-user"), text: ORIG[k.origin] || k.origin})),
      el("td", {}, el("button", {class: "link sm", type: "button", onclick: () => savePatch({removed_keywords: [k.text]}, "Đã bỏ từ khoá.")}, "Bỏ"))));
    const kwText = el("input", {type: "text", maxlength: "60", placeholder: "vd. TẤM FIX", "aria-label": "Chữ ghi chú"});
    const kwMean = el("select", {"aria-label": "Nghĩa"}, Object.entries(c.meanings).map(([k, v]) => el("option", {value: k, text: v})));
    const props = el("div", {class: "props"});
    const showProps = (items, rejected) => {
      fill(props, items.length ? items.map((p) => el("div", {class: "gap3d prop3d"},
        el("span", {class: "src-b " + (p.origin === "code" ? "src-geometry" : "src-user"), text: p.origin === "code" ? "Code" : "AI"}), " ",
        p.kind === "layer_role" ? [b(`Layer “${p.target}”`), ` là ${c.roles[p.value] || p.value}`] : [b(`“${p.target}”`), ` nghĩa là ${c.meanings[p.value] || p.value}`],
        el("div", {class: "g-why", text: p.reason}),
        el("button", {class: "btn-p btn-sm", type: "button", onclick: () => savePatch(p.kind === "layer_role" ? {layer_roles: {[p.target]: p.value}} : {keywords: [{text: p.target, meaning: p.value}]},
          "Đã đồng ý và lưu vào hồ sơ.", {items: items.filter((x) => x !== p), rejected})}, "Đồng ý"),
        " ", el("button", {class: "link sm", type: "button", onclick: () => showProps(items.filter((x) => x !== p), rejected)}, "Bỏ qua")))
        : el("div", {class: "f-d", text: "Không có đề xuất mới: hồ sơ hiện tại đã đọc được bản vẽ này."}),
        rejected && rejected.length ? el("small", {class: "muted", text: `${rejected.length} đề xuất bị loại vì không có bằng chứng trong bản vẽ.`}) : null);
    };
    const propose = async (ai) => {
      if (!S.file) { toast("Mở một bản vẽ trước để đề xuất."); return; }
      const bz = busy(ai ? "AI đang xem cách trình bày bản vẽ…" : "Đang tìm bằng code…", ai ? "Mỗi đề xuất phải dẫn đúng layer/ghi chú có trong bản vẽ." : "");
      let job;
      try { job = await api("/api/drafting/propose", {file: S.file, ai, engine: S.engine ? S.engine.name : null}); } catch (e) { bz.done(); fail(e, "Đề xuất hồ sơ trình bày"); return; }
      if (job.note) toast(job.note);
      while (job.state === "running") {
        await new Promise((res) => setTimeout(res, 2000));
        try { job = await api("/api/drafting/propose/status", {job: job.id}); } catch (e) { bz.done(); fail(e, "Đề xuất hồ sơ trình bày"); return; }
      }
      bz.done();
      if (job.state === "error") { fail(new Error(job.error || "Lỗi khi đề xuất."), "Đề xuất hồ sơ trình bày"); return; }
      showProps(job.items, job.rejected);
    };
    if (found) showProps(found.items, found.rejected);
    const close = el("button", {class: "iconbtn", type: "button", "aria-label": "Đóng", onclick: closeDrawer}, icon("x"));
    fill(d,
      el("div", {class: "dr-h"}, el("div", {class: "grow1"}, el("h2", {id: "drTitle", text: "Hồ sơ trình bày"}),
        el("div", {class: "f-d", text: c.confirmed ? "Đã có hồ sơ lưu cho công ty/dự án này." : "Chưa lưu hồ sơ: đang đọc theo cách đoán mặc định."})), close),
      el("div", {class: "dr-b"},
        el("p", {class: "f-d", text: "Mỗi người kỹ thuật trình bày một kiểu. Khai một lần ở đây (hoặc để code/AI đề xuất rồi Đồng ý), CAD Guard sẽ đọc mọi bản vẽ kiểu này đúng cách. Bản vẽ không bị sửa."}),
        el("div", {class: "w-act"},
          el("button", {class: "btn-s btn-sm", type: "button", onclick: () => propose(false)}, "Đề xuất bằng code"),
          el("button", {class: "btn-p btn-sm", type: "button", onclick: () => propose(true)}, "Nhờ AI xem bản vẽ")),
        props,
        el("h3", {text: "Layer trong các hình hạng mục"}),
        c.layers.length ? el("table", {class: "tbl3d"}, el("tr", {}, ["Layer", "Số nét", "Là", "Nguồn", ""].map((t) => el("th", {text: t}))), layerRows)
          : el("div", {class: "f-d", text: "Mở một bản vẽ có hạng mục để xem layer."}),
        el("h3", {text: "Ghi chú và nghĩa"}),
        el("table", {class: "tbl3d"}, el("tr", {}, ["Chữ trên bản vẽ", "Nghĩa", "Nguồn", ""].map((t) => el("th", {text: t}))), kwRows),
        el("div", {class: "w-act"}, kwText, kwMean,
          el("button", {class: "btn-s btn-sm", type: "button", onclick: () => kwText.value.trim() && savePatch({keywords: [{text: kwText.value, meaning: kwMean.value}]})}, "Thêm"))),
      el("div", {class: "dr-f"}, el("label", {}, "Lưu cho ", scope), el("span", {class: "spacer"}),
        el("button", {class: "btn-s", type: "button", onclick: async () => {
          try { await api("/api/drafting/save", {scope: scope.value, reset: true}); toast("Đã bỏ hồ sơ đã lưu ở phạm vi này."); reload(); openDrafting(); } catch (e) { fail(e, "Hồ sơ trình bày"); }
        }}, "Về mặc định")));
    d.classList.add("on");
    close.focus();
  }
  function cutlistBox(r) {
    const cl = r.cutlist;
    if (!cl || !cl.rows.length) return null;
    const head = el("tr", {}, ["Chi tiết", "Dài", "Rộng", "Dày", "SL", "Vật liệu", "Cạnh dán", "Khối"].map((t) => el("th", {text: t})));
    const rows = cl.rows.map((x) => el("tr", {}, el("td", {text: x.part}), el("td", {text: String(x.length)}), el("td", {text: String(x.width)}),
      el("td", {text: String(x.thickness)}), el("td", {text: String(x.qty)}), el("td", {text: x.material}), el("td", {text: String(x.edges)}), el("td", {text: x.modules.join(" ")})));
    const dl = el("button", {class: "btn-s btn-sm", type: "button", onclick: async () => {
      try {
        const f = await api("/api/scene/cutlist", {file: S.file, item: r.item});
        el("a", {href: URL.createObjectURL(new Blob([f.csv], {type: "text/csv;charset=utf-8"})), download: f.name}).click();
      } catch (e) { fail(e, "Tải danh sách cắt"); }
    }}, "Tải CSV (Excel)");
    return el("details", {open: S.body3d && S.body3d !== "block"},
      el("summary", {}, b(`Danh sách cắt (tham khảo): ${cl.panels} tấm · ${cl.area_m2} m² ván · ${cl.edge_band_m} m dán cạnh · ${cl.hinges} bản lề`)),
      el("div", {class: "f-d"}, `Theo hồ sơ kết cấu: ${r.construction.summary}${r.construction.confirmed ? "" : " (SỐ MẶC ĐỊNH, chưa xác nhận)"}. `,
        el("button", {class: "link sm", type: "button", onclick: openConstruction}, "Sửa kết cấu xưởng"), " · ", dl,
        " · Vật liệu lấy từ vật liệu theo bộ phận bạn đã Đồng ý ở Bản đồ; chưa có thì ghi “Chưa gán”."),
      el("table", {class: "tbl3d"}, head, rows));
  }
  function boxesFor(r) {
    const hl = S.sel3d;
    const src = (S.body3d && S.body3d !== "block" && r.panels) ? r.panels[S.body3d] || r.boxes : r.boxes;
    const own = (n, id) => n && (n === id || n.startsWith(id + ".") || n.startsWith(id + ":"));
    const warn = S.warn3d || new Set();
    return src.map(bx => {
      if (hl && own(bx.n, hl)) return {...bx, c: [0.15, 0.39, 0.92]};
      for (const id of warn) if (own(bx.n, id)) return {...bx, c: [0.96, 0.58, 0.2]};  // khối dùng số tạm
      return bx;
    });
  }
  function feedbackPrompt(r, m, pv) {
    const src = pv.modules[m.id] || {};
    const vals = ["w", "d", "h", "z0"].map(k => `${{w: "rộng", d: "sâu", h: "cao", z0: "cao độ chân"}[k]} ${Math.round(m[k].value)} mm (${SRC_TIP[m[k].kind]})`).join("; ");
    return `Kiểm giúp khối ${m.id} (${m.label || m.type_vi || m.kind}) của hạng mục “${pv.item_name || r.item}” trong bản vẽ ${S.file}. ` +
      `CAD Guard dựng nó từ ${(pv.views[src.elevation] || {}).label || "?"} và ${(pv.views[src.plan] || {}).label || "?"}. Số đo hiện tại: ${vals}. ` +
      `Dùng công cụ get_scene/get_drawing_graph/query_model để đối chiếu với kích thước ghi trên bản vẽ. Nếu thấy sai, chỉ ra số đúng và lấy từ kích thước/hình nào; ` +
      `tôi sẽ tự sửa trong bảng 3D. Ghi rõ đâu là nhận xét của AI.`;
  }

  // Trình xem 3D canvas 2D (chuyển từ scene/viewer.py, gắn sự kiện bằng addEventListener).
  // Trình xem 3D WebGL: bộ đệm độ sâu nên mặt sát nhau (cánh trước thùng, đợt sau cánh) không chồng sai khi xoay.
  // Không có WebGL thì dùng bản canvas 2D (sắp mặt theo độ sâu). Kéo trái: xoay; kéo phải hoặc Shift+kéo: dời; cuộn: phóng.
  function makeViewer(cv) {
    const gl = cv.getContext("webgl", {antialias: true}) || null;
    return gl ? makeViewerGL(cv, gl) : makeViewer2d(cv);
  }
  function earcut2(pts) {  // cắt tai đa giác (lồi/lõm) -> chỉ số tam giác
    const n = pts.length;
    if (n < 3) return [];
    if (n === 4) return [0, 1, 2, 0, 2, 3];
    let area = 0;
    for (let i = 0; i < n; i++) { const a = pts[i], b = pts[(i + 1) % n]; area += a[0] * b[1] - b[0] * a[1]; }
    const sg = area > 0 ? 1 : -1, cr = (a, b, c) => ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) * sg;
    const idx = [...Array(n).keys()], out = [];
    let guard = 0;
    while (idx.length > 3 && guard++ < 4 * n * n) {
      let cut = false;
      for (let k = 0; k < idx.length; k++) {
        const i0 = idx[(k + idx.length - 1) % idx.length], i1 = idx[k], i2 = idx[(k + 1) % idx.length];
        const a = pts[i0], b = pts[i1], c = pts[i2];
        if (cr(a, b, c) <= 1e-9) continue;
        if (idx.some(j => j !== i0 && j !== i1 && j !== i2 && cr(a, b, pts[j]) > 1e-9 && cr(b, c, pts[j]) > 1e-9 && cr(c, a, pts[j]) > 1e-9)) continue;
        out.push(i0, i1, i2); idx.splice(k, 1); cut = true; break;
      }
      if (!cut) break;
    }
    for (let k = 1; k + 1 < idx.length; k++) out.push(idx[0], idx[k], idx[k + 1]);
    return out;
  }
  function makeViewerGL(cv, gl) {
    const VS = "attribute vec3 p;attribute vec4 c;uniform vec3 ctr;uniform vec4 rot;uniform vec3 sc;uniform vec2 pan;varying vec4 vc;" +
      "void main(){vec3 q=p-ctr;float x1=q.x*rot.x-q.y*rot.y;float y1=q.x*rot.y+q.y*rot.x;" +
      "gl_Position=vec4(x1*sc.x+pan.x,(q.z*rot.z+y1*rot.w)*sc.y+pan.y,(y1*rot.z-q.z*rot.w)*sc.z,1.0);vc=c;}";
    const FS = "precision mediump float;varying vec4 vc;void main(){gl_FragColor=vc;}";
    const sh = (t, src) => { const o = gl.createShader(t); gl.shaderSource(o, src); gl.compileShader(o); return o; };
    const prog = gl.createProgram();
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return makeViewer2d(cv);
    gl.useProgram(prog);
    const U = n => gl.getUniformLocation(prog, n), aP = gl.getAttribLocation(prog, "p"), aC = gl.getAttribLocation(prog, "c");
    const bufP = gl.createBuffer(), bufC = gl.createBuffer(), bufE = gl.createBuffer();
    const ext = gl.getExtension("OES_element_index_uint");
    let BOXES = [], yaw = 0.8, pitch = 0.6, zoom = 1, pan = [0, 0], drag = null, alive = true, nOpaque = 0, nAll = 0, nLines = 0, ctr = [0, 0, 0], rad = 1;
    let P0 = null, Pcur = null, MOV = [], openT = S.open3d || 0, anim = 0;
    const light = (n, c, a) => {
      const l = 0.5 + 0.5 * Math.max(0, n[0] * -0.35 + n[1] * -0.45 + n[2] * 0.82);
      return [c[0] * l, c[1] * l, c[2] * l, a];
    };
    function build() {
      const P = [], C = [], Eo = [], Et = [], El = [];
      MOV = [];
      const a = [1e18, 1e18, 1e18], bb = [-1e18, -1e18, -1e18];
      for (const o of BOXES) for (const p of o.b) for (const z of [o.z0, o.z1]) { const v = [p[0], p[1], z]; for (let i = 0; i < 3; i++) { a[i] = Math.min(a[i], v[i]); bb[i] = Math.max(bb[i], v[i]); } }
      ctr = [(a[0] + bb[0]) / 2, (a[1] + bb[1]) / 2, (a[2] + bb[2]) / 2];
      rad = Math.max(bb[0] - a[0], bb[1] - a[1], bb[2] - a[2]) || 1;
      const face = (verts, n, col, tris, E) => {
        const s0 = P.length / 3, cc = light(n, col, col[3]);
        for (const v of verts) { P.push(v[0], v[1], v[2]); C.push(cc[0], cc[1], cc[2], cc[3]); }
        for (const t of tris) E.push(s0 + t);
      };
      for (const o of BOXES) {
        const v0 = P.length / 3;
        const n = o.b.length, alpha = (o.k === "wall" || o.k === "ceiling") ? 0.35 : 1;
        const col = [o.c[0], o.c[1], o.c[2], alpha], E = alpha < 1 ? Et : Eo;
        const tri = earcut2(o.b);
        face(o.b.map(p => [p[0], p[1], o.z1]), [0, 0, 1], col, tri, E);
        face(o.b.map(p => [p[0], p[1], o.z0]), [0, 0, -1], col, tri.slice().reverse(), E);
        let ar = 0;
        for (let i = 0; i < n; i++) { const p = o.b[i], q = o.b[(i + 1) % n]; ar += p[0] * q[1] - q[0] * p[1]; }
        const sg = ar >= 0 ? 1 : -1;
        for (let i = 0; i < n; i++) {
          const p = o.b[i], q = o.b[(i + 1) % n], e = [q[0] - p[0], q[1] - p[1]], l = Math.hypot(e[0], e[1]) || 1;
          face([[p[0], p[1], o.z0], [q[0], q[1], o.z0], [q[0], q[1], o.z1], [p[0], p[1], o.z1]], [sg * e[1] / l, -sg * e[0] / l, 0], col, [0, 1, 2, 0, 2, 3], E);
        }
        // viền tối (đường ráp) cho đồ nội thất: thấy rõ từng cánh, khe giữa hai cánh, mép tấm
        if (alpha === 1 && o.k !== "floor") {
          const s0 = P.length / 3, dk = [o.c[0] * 0.3, o.c[1] * 0.3, o.c[2] * 0.3, 1];
          for (const z of [o.z0, o.z1]) for (const p of o.b) { P.push(p[0], p[1], z); C.push(dk[0], dk[1], dk[2], dk[3]); }
          for (let i = 0; i < n; i++) { const j = (i + 1) % n; El.push(s0 + i, s0 + j, s0 + n + i, s0 + n + j, s0 + i, s0 + n + i); }
        }
        if (o.m) MOV.push([v0, P.length / 3, o.m]);
      }
      nOpaque = Eo.length; nAll = Eo.length + Et.length; nLines = El.length;
      P0 = new Float32Array(P); Pcur = new Float32Array(P);
      gl.bindBuffer(gl.ARRAY_BUFFER, bufP); gl.bufferData(gl.ARRAY_BUFFER, Pcur, gl.DYNAMIC_DRAW);
      gl.bindBuffer(gl.ARRAY_BUFFER, bufC); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(C), gl.STATIC_DRAW);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, bufE);
      const all = Eo.concat(Et, El);
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, ext ? new Uint32Array(all) : new Uint16Array(all), gl.STATIC_DRAW);
    }
    const itype = ext ? gl.UNSIGNED_INT : gl.UNSIGNED_SHORT, isize = ext ? 4 : 2;
    function pose() {  // đặt cánh/ngăn kéo theo độ mở hiện tại (chỉ sửa đỉnh của hộp có `m`)
      if (!MOV.length || !Pcur) return;
      for (const [a, z, m] of MOV) for (let i = a; i < z; i++) {
        const q = moveXY(m, openT, P0[3 * i], P0[3 * i + 1]);
        Pcur[3 * i] = q[0]; Pcur[3 * i + 1] = q[1];
      }
      gl.bindBuffer(gl.ARRAY_BUFFER, bufP); gl.bufferSubData(gl.ARRAY_BUFFER, 0, Pcur);
    }
    function open(target, animate, onStep) {
      target = Math.max(0, Math.min(1, +target || 0));
      if (anim) { cancelAnimationFrame(anim); anim = 0; }
      if (!animate) { openT = target; pose(); draw(); if (onStep) onStep(openT); return; }
      const from = openT, t0 = performance.now(), dur = 600;
      const step = (now) => {
        if (!alive) return;
        const u = Math.min(1, (now - t0) / dur), e = u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;
        openT = from + (target - from) * e; pose(); draw();
        if (onStep) onStep(openT);
        anim = u < 1 ? requestAnimationFrame(step) : 0;
      };
      anim = requestAnimationFrame(step);
    }
    function fit() {
      const w = Math.max(1, Math.round(cv.clientWidth * devicePixelRatio)), h = Math.max(1, Math.round(cv.clientHeight * devicePixelRatio));
      if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
      draw();
    }
    function draw() {
      if (!alive) return;
      gl.viewport(0, 0, cv.width, cv.height);
      gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      if (!nAll) return;
      const k = Math.min(cv.width, cv.height) / (rad * 1.6) * zoom;
      gl.uniform3f(U("ctr"), ctr[0], ctr[1], ctr[2]);
      gl.uniform4f(U("rot"), Math.cos(yaw), Math.sin(yaw), Math.cos(pitch), Math.sin(pitch));
      gl.uniform3f(U("sc"), 2 * k / cv.width, 2 * k / cv.height, 1 / rad);
      gl.uniform2f(U("pan"), pan[0], pan[1]);
      gl.bindBuffer(gl.ARRAY_BUFFER, bufP); gl.enableVertexAttribArray(aP); gl.vertexAttribPointer(aP, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, bufC); gl.enableVertexAttribArray(aC); gl.vertexAttribPointer(aC, 4, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, bufE);
      gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL);
      gl.disable(gl.BLEND); gl.depthMask(true);
      gl.enable(gl.POLYGON_OFFSET_FILL); gl.polygonOffset(1, 1);  // mặt lùi nhẹ để viền không bị chìm
      gl.drawElements(gl.TRIANGLES, nOpaque, itype, 0);
      gl.disable(gl.POLYGON_OFFSET_FILL);
      if (nLines) gl.drawElements(gl.LINES, nLines, itype, nAll * isize);
      if (nAll > nOpaque) {  // tường/trần trong suốt vẽ sau, không ghi độ sâu
        gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(false);
        gl.drawElements(gl.TRIANGLES, nAll - nOpaque, itype, nOpaque * isize);
        gl.depthMask(true);
      }
    }
    cv.addEventListener("contextmenu", e => e.preventDefault());
    cv.addEventListener("pointerdown", e => { drag = [e.clientX, e.clientY, e.button === 2 || e.shiftKey]; cv.setPointerCapture(e.pointerId); });
    cv.addEventListener("pointermove", e => {
      if (!drag) return;
      const dx = e.clientX - drag[0], dy = e.clientY - drag[1];
      if (drag[2]) { pan[0] += 2 * dx / cv.clientWidth; pan[1] -= 2 * dy / cv.clientHeight; }
      else { yaw += dx * 0.01; pitch = Math.max(-0.2, Math.min(1.5, pitch + dy * 0.01)); }
      drag = [e.clientX, e.clientY, drag[2]]; draw();
    });
    cv.addEventListener("pointerup", () => { drag = null; });
    cv.addEventListener("wheel", e => { e.preventDefault(); zoom *= e.deltaY < 0 ? 1.1 : 0.9; draw(); }, {passive: false});
    const ro = new ResizeObserver(fit); ro.observe(cv);
    return {set(bx) { BOXES = bx; build(); pose(); fit(); }, redraw: draw, gl: true, open,
      zoom(f) { if (f === 0) { zoom = 1; pan = [0, 0]; } else zoom *= f; draw(); },
      view(y, p) { yaw = y; pitch = p; draw(); },
      stop() { alive = false; if (anim) cancelAnimationFrame(anim); ro.disconnect(); }};
  }
  function makeViewer2d(cv) {
    const cx = cv.getContext("2d");
    let BOXES = [], yaw = 0.8, pitch = 0.6, zoom = 1, drag = null, alive = true, openT = S.open3d || 0, anim = 0;
    function fit() { cv.width = Math.max(1, cv.clientWidth * devicePixelRatio); cv.height = Math.max(1, cv.clientHeight * devicePixelRatio); draw(); }
    function bounds() {
      const a = [1e18, 1e18, 1e18], bb = [-1e18, -1e18, -1e18];
      for (const o of BOXES) for (const p of o.b) for (const z of [o.z0, o.z1]) { const v = [p[0], p[1], z]; for (let i = 0; i < 3; i++) { a[i] = Math.min(a[i], v[i]); bb[i] = Math.max(bb[i], v[i]); } }
      return [a, bb];
    }
    function draw() {
      if (!alive) return;
      cx.clearRect(0, 0, cv.width, cv.height);
      if (!BOXES.length) return;
      const [a, bb] = bounds(), c = [(a[0] + bb[0]) / 2, (a[1] + bb[1]) / 2, (a[2] + bb[2]) / 2];
      const r = Math.max(bb[0] - a[0], bb[1] - a[1], bb[2] - a[2]) || 1, k = Math.min(cv.width, cv.height) / (r * 1.6) * zoom;
      const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
      const pr = (p) => { const x = p[0] - c[0], y = p[1] - c[1], z = p[2] - c[2], x1 = x * cy - y * sy, y1 = x * sy + y * cy; return [cv.width / 2 + x1 * k, cv.height / 2 - (z * cp + y1 * sp) * k, y1 * cp - z * sp]; };
      const faces = [];
      for (const o of BOXES) {
        const ob = o.m ? o.b.map(p => moveXY(o.m, openT, p[0], p[1])) : o.b;
        const n = ob.length, top = ob.map((p) => [p[0], p[1], o.z1]);
        faces.push({v: top, n: [0, 0, 1], c: o.c, k: o.k});
        for (let i = 0; i < n; i++) {
          const p = ob[i], q = ob[(i + 1) % n], e = [q[0] - p[0], q[1] - p[1]], l = Math.hypot(e[0], e[1]) || 1;
          faces.push({v: [[p[0], p[1], o.z0], [q[0], q[1], o.z0], [q[0], q[1], o.z1], [p[0], p[1], o.z1]], n: [e[1] / l, -e[0] / l, 0], c: o.c, k: o.k});
        }
      }
      for (const f of faces) {
        f.p = f.v.map(pr);
        f.d = f.p.reduce((s, p) => s + p[2], 0) / f.p.length;
        const nx = f.n[0] * cy - f.n[1] * sy, ny = f.n[0] * sy + f.n[1] * cy, nz = f.n[2];
        f.vis = (ny * cp - nz * sp) <= 0.0001;
        f.l = 0.45 + 0.55 * Math.max(0, (nx * -0.4 + (nz * cp - ny * sp) * 0.8 + 0.3));
      }
      faces.filter((f) => f.vis).sort((x, y) => y.d - x.d).forEach((f) => {
        cx.beginPath();
        f.p.forEach((p, i) => (i ? cx.lineTo(p[0], p[1]) : cx.moveTo(p[0], p[1])));
        cx.closePath();
        cx.globalAlpha = ((f.k === "wall" && f.n[2] === 0) || f.k === "ceiling") ? 0.22 : 1;
        cx.fillStyle = "rgb(" + f.c.map((v) => Math.round(v * 255 * Math.min(1, f.l))).join(",") + ")";
        cx.fill();
        cx.strokeStyle = f.k === "wall" || f.k === "ceiling" ? cx.fillStyle : "rgba(40,36,30,0.85)"; cx.lineWidth = 0.9; cx.stroke();
      });
      cx.globalAlpha = 1;
    }
    const down = (e) => { drag = [e.clientX, e.clientY]; cv.setPointerCapture(e.pointerId); };
    const move = (e) => { if (!drag) return; yaw += (e.clientX - drag[0]) * 0.01; pitch = Math.max(0.05, Math.min(1.5, pitch + (e.clientY - drag[1]) * 0.01)); drag = [e.clientX, e.clientY]; draw(); };
    const up = () => { drag = null; };
    cv.addEventListener("pointerdown", down);
    cv.addEventListener("pointermove", move);
    cv.addEventListener("pointerup", up);
    cv.addEventListener("wheel", (e) => { e.preventDefault(); zoom *= e.deltaY < 0 ? 1.1 : 0.9; draw(); }, {passive: false});
    window.addEventListener("resize", fit);
    function open(target, animate, onStep) {
      target = Math.max(0, Math.min(1, +target || 0));
      if (anim) { cancelAnimationFrame(anim); anim = 0; }
      if (!animate) { openT = target; draw(); if (onStep) onStep(openT); return; }
      const from = openT, t0 = performance.now();
      const step = (now) => {
        if (!alive) return;
        const u = Math.min(1, (now - t0) / 600);
        openT = from + (target - from) * (u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2); draw();
        if (onStep) onStep(openT);
        anim = u < 1 ? requestAnimationFrame(step) : 0;
      };
      anim = requestAnimationFrame(step);
    }
    return {set(bx) { BOXES = bx; fit(); }, redraw: draw, open, zoom(f) { zoom = f === 0 ? 1 : zoom * f; draw(); },
      stop() { alive = false; if (anim) cancelAnimationFrame(anim); window.removeEventListener("resize", fit); }};
  }

  // ---------- tab phải ----------
  function rightTab(p) {
    for (const t of $$("#rightTabs [role=tab]")) {
      const on = t.dataset.p === p;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
    }
    for (const x of ["chat", "finds", "chg", "help"]) $("p-" + x).classList.toggle("on", x === p);
    if (p === "chg") { loadChangesets(); if (S.file && !S.suggest && !S.preview && !S.applied && S.findings.some((f) => f.fixable)) loadSuggest(); }
  }

  // ---------- tab Lỗi ----------
  function renderFinds() {
    const box = $("finds");
    const cnt = $("cntF");
    if (S.dept && S.dept.view === "scene") {
      cnt.textContent = "–"; cnt.className = "cnt";
      fill(box, emptyBox("Luật kiểm 3D đang phát triển", "Phòng Thiết kế 3D hiện chỉ xem mô hình dựng từ bản vẽ. Kiểm đơn vị, tên vật thể, va chạm và vật liệu sẽ có ở bản sau."));
      return;
    }
    if (!S.file) { cnt.textContent = "–"; cnt.className = "cnt"; fill(box, emptyBox("Chưa mở bản vẽ", "Chọn một bản vẽ ở cột trái.")); return; }
    if (!Object.keys(S.audits).length) {
      cnt.textContent = "–"; cnt.className = "cnt";
      fill(box, emptyBox("Chưa quét bản vẽ này", `Quét theo ${deptStd().join(" + ") || "chuẩn của phòng"}.`, el("br"), el("br"),
        el("button", {class: "btn-p", type: "button", disabled: !deptStd().length, onclick: () => doScan(false)}, icon("search"), "Quét bản vẽ này")));
      return;
    }
    const shown = S.findings.filter(visibleFinding);
    const open = shown.filter((f) => f.st === "open");
    cnt.textContent = String(open.length);
    cnt.className = "cnt" + (open.some((f) => f.tier === "block") ? " hot" : "");
    const out = [];
    const head = sheetPanel();
    if (head) out.push(head);
    if (!S.findings.length) out.push(emptyBox("Không có phát hiện nào", `Bản vẽ đạt các luật đang chạy của ${deptStd().join(" + ")}.`));
    else if (!shown.length) out.push(emptyBox("Tờ này không có phát hiện", S.showHints ? "" : "Gợi ý đang ẩn."));
    for (const f of shown) {
      const fixed = f.st === "fixed";
      const sevPill = fixed ? pill("ok", "Đã sửa", "check") : pill(SEV[f.severity][0], SEV[f.severity][1], SEV[f.severity][2]);
      const inSheet = S.sheetSel ? itemsInSheet(f, S.sheetSel) : f.items;
      const first = inSheet[0] || f.items[0] || {};
      const where = [first.layer ? "layer " + first.layer : null, first.layout && first.layout !== "Model" ? "tờ " + first.layout : null].filter(Boolean).join(" · ");
      out.push(el("div", {class: "f-card" + (S.sel === f.no ? " sel" : ""), "data-no": f.no, tabindex: "0", role: "button",
        "aria-label": `${SEV[f.severity][1]} ${f.no}: ${f.title}`,
        onclick: () => selectFinding(f.no, false),
        onkeydown: (e) => { if ((e.key === "Enter" || e.key === " ") && e.target === e.currentTarget) { e.preventDefault(); selectFinding(f.no, false); } }},
      el("div", {class: "f-top"}, el("span", {class: "f-no", text: String(f.no)}), sevPill,
        el("button", {class: "f-rule link", type: "button", title: "Xem luật này", onclick: (e) => { e.stopPropagation(); showExplain(f.rule_id, f.std); }}, f.rule_id),
        tierPill(f), f.count > 1 ? pill("neu sm", S.sheetSel && !findingWide(f) ? `${fmt(countItems(inSheet))} chỗ trong tờ` : `${fmt(f.count)} chỗ`) : null,
        S.sheets && S.sheets.sheets.length && findingWide(f) ? pill("neu sm", "cả bản vẽ") : null,
        el("span", {class: "std"}, pill("neu sm", f.std)),
        el("button", {class: "link sm", type: "button", title: "Nhờ trợ lý AI giải thích tầm quan trọng, hậu quả và cách sửa của lỗi này trên bản vẽ đang mở",
          onclick: (e) => { e.stopPropagation(); askAI(explainPrompt(f.rule_id, f.title, f.std, (f.items || []).slice(0, 3).map((it) => it.message).join("; "))); }}, "Giải thích sâu (AI)"),
        el("button", {class: "link sm", type: "button", title: "Tắt luật này cho dự án (quét lại để thấy kết quả)", onclick: (e) => { e.stopPropagation(); disableRule(f.rule_id, f.std); }}, "Tắt luật"),
        f.rule_id === "LY-01" && S.file ? el("button", {class: "link sm", type: "button", title: "Coi các layer có sẵn của bản vẽ này là quy ước của công ty (LY-01)",
          onclick: async (e) => { e.stopPropagation(); try { const r = await api("/api/rules/learn_layers", {file: S.file, standard: f.std}); S.rules = null; toast(`Đã học ${r.patterns.length} mẫu layer. Quét lại để thấy kết quả.`); } catch (err) { fail(err); } }}, "Học quy ước layer") : null,
        el("button", {class: "link sm", type: "button", title: "Sửa ngưỡng, mức độ của luật", onclick: async (e) => { e.stopPropagation(); await loadRulesQuiet(); showExplain(f.rule_id, f.std); }}, "Sửa ngưỡng")),
      el("div", {class: "f-title", text: f.title}),
      el("div", {class: "f-d"}, el("ul", {}, inSheet.slice(0, 3).map((it) => el("li", {text: it.message}))),
        inSheet.length > 3 ? el("span", {class: "muted", text: `+${inSheet.length - 3} mục khác`}) : null),
      fixed ? null : ackRow(f),
      fixed ? el("div", {class: "f-meta"}, icon("check"), "Không còn trong tệp mới " + (S.applied ? S.applied.output : ""))
        : f.fixable ? el("div", {class: "f-meta"}, icon("gear"), "Có thể tự sửa bằng thao tác an toàn: xem tab Thay đổi")
          : el("div", {class: "f-meta"}, icon("hand"), "Cần người sửa trong phần mềm CAD. Trợ lý không tự sửa."),
      el("div", {class: "f-meta"}, icon("search"), f.box ? `Vị trí: đánh dấu số ${f.no} trên bản vẽ` + (where ? " · " + where : "")
        : (where ? where + " · " : "") + "không có vị trí trên hình mô hình"),
      acadTarget(f) ? el("div", {class: "f-acad"},
        el("button", {class: "btn-s btn-sm", type: "button", title: "Phóng tới và chọn đối tượng trong AutoCAD (bản vẽ phải đang mở)",
          onclick: (e) => { e.stopPropagation(); showInAutocad(f); }}, icon("arrow"), "Tới trong AutoCAD"),
        el("span", {class: "muted", text: f.handles.length ? `${fmt(f.handles.length)} đối tượng` : `mọi đối tượng trên ${fmt(acadTarget(f).layers.length)} layer`})) : null));
    }
    for (const f of S.findings) if (f.positions && f.positions.length > 1) {
      const card=out.find(n=>n.dataset && n.dataset.no===String(f.no));
      if(card)card.appendChild(el("div",{class:"position-nav"},
        el("button",{type:"button",class:"btn-s",text:"Trước",onclick:(e)=>{e.stopPropagation();f.position=(f.position+f.positions.length-1)%f.positions.length;selectFinding(f.no,false);}}),
        el("span",{text:`Vị trí ${f.position+1}/${f.positions.length}`}),
        el("button",{type:"button",class:"btn-s",text:"Tiếp",onclick:(e)=>{e.stopPropagation();f.position=(f.position+1)%f.positions.length;selectFinding(f.no,false);}})));
    }
    const hints = S.findings.filter((f) => f.tier === "hint" && (!S.sheetSel || itemsInSheet(f, S.sheetSel).length));
    if (hints.length) out.push(el("div", {class: "hint-toggle"},
      el("button", {class: "btn-s btn-sm", type: "button", "aria-pressed": S.showHints ? "true" : "false",
        onclick: () => { S.showHints = !S.showHints; renderFinds(); redrawMarks(); }},
        S.showHints ? `Ẩn ${hints.length} gợi ý` : `Hiện ${hints.length} gợi ý`),
      el("span", {class: "muted", text: " Gợi ý không ảnh hưởng chốt tờ."})));
    const sk = Object.values(S.audits).flatMap((r) => r.skipped.map((s) => ({...s, std: r.standard})));
    if (sk.length) out.push(el("details", {class: "skipped"}, el("summary", {text: `${sk.length} luật bỏ qua (thiếu dữ liệu trong bản vẽ)`}),
      el("ul", {}, sk.map((s) => el("li", {}, b(s.rule_id + ": "), s.reason)))));
    fill(box, ...out);
  }

  // ---------- tờ (trang in): chọn tờ, lọc phát hiện, bậc Chặn/Cảnh báo/Gợi ý, chốt tờ ----------
  async function loadSheets(path) {
    if (S.dept && S.dept.view === "scene") return;
    try {
      const r = await api("/api/sheets", {file: path});
      if (S.file !== path) return;
      S.sheets = r;
    } catch (e) {
      if (S.file !== path) return;
      S.sheets = {sheets: [], error: e.message};
    }
    renderSheetBar(); renderFinds(); redrawMarks();
    selectPendingSheet();
  }
  function selectPendingSheet() {  // "Xem tờ" từ Bản đồ: chọn tờ khi cả hình vẽ và danh sách tờ đã có
    if (!S.pendingSheet || !S.geo || S.geo.error || !S.sheets || !S.sheets.sheets) return;
    const sid = S.pendingSheet;
    S.pendingSheet = null;
    if (S.sheets.sheets.some((s) => s.id === sid)) selectSheet(sid);
  }

  const curSheet = () => (S.sheets && S.sheetSel ? S.sheets.sheets.find((s) => s.id === S.sheetSel) || null : null);
  const itemsInSheet = (f, sid) => (sid ? f.items.filter((it) => !(it.sheets || []).length || it.sheets.includes(sid)) : f.items);
  const findingWide = (f) => f.items.every((it) => !(it.sheets || []).length);
  const countItems = (items) => items.reduce((n, it) => n + Math.max(1, Number(it.count) || 1), 0);
  function visibleFinding(f) {
    if (f.tier === "hint" && !S.showHints) return false;
    return !S.sheetSel || itemsInSheet(f, S.sheetSel).length > 0;
  }
  function ackOf(f, sid) {
    const a = (S.audits[f.std] || {}).acks || {};
    return a[`${f.std}|${f.rule_id}|${sid || "*"}`] || (sid ? a[`${f.std}|${f.rule_id}|*`] : null) || null;
  }
  // Đếm theo bậc cho một tờ (null = cả bản vẽ). Máy chủ kiểm lại khi chốt (gate.evaluate), đây chỉ để hiển thị.
  function sheetGate(sid) {
    const g = {block: 0, warn: 0, warnOpen: 0, hint: 0};
    for (const f of S.findings) {
      if (f.st !== "open") continue;
      const n = countItems(itemsInSheet(f, sid));
      if (!n || (sid && !itemsInSheet(f, sid).length)) continue;
      g[f.tier] = (g[f.tier] || 0) + n;
      if (f.tier === "warn" && !ackOf(f, sid)) g.warnOpen += n;
    }
    const req = Object.values(S.audits).some((r) => r.gate_require_ack !== false);
    g.canLock = g.block === 0 && (!req || g.warnOpen === 0);
    return g;
  }

  function tierPill(f) {
    if (f.st === "fixed") return null;
    if (f.tier === "block") return pill("err sm", "Chặn chốt tờ", "lock");
    if (f.tier === "hint") return pill("neu sm", "Gợi ý");
    return null;
  }

  function ackRow(f) {
    if (f.tier !== "warn" || f.st !== "open") return null;
    const sid = S.sheetSel;
    const a = ackOf(f, sid);
    const scope = sid ? "tờ này" : "cả bản vẽ";
    if (a) return el("div", {class: "f-ack"}, pill("ok sm", a.kind === "skip" ? "Đã bỏ qua" : "Đã xem", "check"),
      a.reason ? el("span", {class: "muted", text: "Lý do: " + a.reason}) : null,
      el("button", {class: "link", type: "button", onclick: (e) => { e.stopPropagation(); doAck(f, null); }}, "Hoàn tác"));
    return el("div", {class: "f-ack"},
      el("button", {class: "btn-s btn-sm", type: "button", title: `Đánh dấu đã xem cảnh báo này cho ${scope}`,
        onclick: (e) => { e.stopPropagation(); doAck(f, "seen"); }}, icon("check"), "Đã xem"),
      el("button", {class: "btn-s btn-sm", type: "button", title: `Bỏ qua cảnh báo này cho ${scope} (cần lý do)`,
        onclick: (e) => { e.stopPropagation(); doAck(f, "skip"); }}, "Bỏ qua…"));
  }

  async function doAck(f, kind) {
    const sid = S.sheetSel || "*";
    let reason = "";
    if (kind === "skip") {
      const ta = el("textarea", {class: "ack-reason", rows: "3", maxlength: "300", "aria-label": "Lý do bỏ qua",
        placeholder: "Ví dụ: layer này theo quy ước riêng của khách, đã thống nhất."});
      setTimeout(() => ta.focus(), 30);
      const ok = await confirmDialog({title: `Bỏ qua ${f.rule_id} cho ${sid === "*" ? "cả bản vẽ" : "tờ này"}?`,
        body: ["Lý do được lưu trên máy này để trưởng phòng xem lại và để đo tỉ lệ báo sai của luật.", ta], yes: "Bỏ qua"});
      if (!ok) return;
      reason = ta.value.trim();
    }
    try {
      const r = await api("/api/findings/ack", {file: S.file, standard: f.std, rule_id: f.rule_id, sheet: sid,
        kind: kind || "seen", reason, undo: kind === null});
      const acks = (S.audits[f.std] || {}).acks;
      if (acks) { if (r.acked) acks[r.key] = {kind: r.kind, reason}; else delete acks[r.key]; }
      renderFinds(); renderSheetBar();
    } catch (e) { fail(e); }
  }

  function renderSheetBar() {
    const bar = $("sheetBar");
    if (!bar) return;
    const sh = S.sheets;
    if (!S.file || !sh || !sh.sheets || !sh.sheets.length || (S.dept && S.dept.view === "scene")) { bar.hidden = true; bar.replaceChildren(); return; }
    bar.hidden = false;
    const scanned = Object.keys(S.audits).length > 0;
    const chip = (id, name, sub, st, title) => el("button", {type: "button", class: "sh-chip" + (S.sheetSel === id ? " on" : "") + (st ? " st-" + st : ""),
      "aria-pressed": S.sheetSel === id ? "true" : "false", title: title || name, onclick: () => selectSheet(id)},
      el("span", {class: "sh-n", text: name}), sub ? el("span", {class: "sh-sub", text: sub}) : null);
    const kids = [chip(null, "Cả bản vẽ", `${sh.sheets.length} tờ · ${sh.locked || 0} đã chốt`, "")];
    for (const s of sh.sheets) {
      const g = scanned ? sheetGate(s.id) : null;
      let st = "", sub = s.stale ? "đổi sau khi chốt" : (scanned ? "" : "chưa quét");
      if (s.status === "locked") { st = "locked"; sub = "Đã chốt"; }
      else if (g) { st = g.block ? "block" : g.warnOpen ? "warn" : "ready"; sub = g.block ? `${g.block} lỗi chặn` : g.warnOpen ? `${g.warnOpen} cần xem` : "sẵn sàng chốt"; }
      const label = s.name + (s.title ? " · " + s.title : "");
      const extra = [s.paper, s.scale ? "1:" + s.scale : null, s.kind === "layout" ? "layout" : "khung trong Model"].filter(Boolean).join(" · ");
      kids.push(chip(s.id, label, sub, st, label + (extra ? " (" + extra + ")" : "")));
    }
    const j = sh.junk || {};
    const nj = (j.outside ? j.outside.count : 0) + (j.stray ? j.stray.count : 0);
    if (nj || (j.empty_layers || []).length || (j.unused_blocks || []).length)
      kids.push(el("button", {type: "button", class: "sh-chip junk", onclick: showJunk, title: "Ứng viên rác: chỉ là gợi ý để xem, cad-guard không tự xoá"},
        el("span", {class: "sh-n", text: "Ứng viên rác"}), el("span", {class: "sh-sub", text: `${fmt(nj)} đối tượng · ${(j.empty_layers || []).length} layer · ${(j.unused_blocks || []).length} khối`})));
    const cur = S.sheetSel ? sh.sheets.findIndex((s) => s.id === S.sheetSel) : -1;
    if (cur >= 0 && sh.sheets[cur].kind === "frame")
      kids.push(el("button", {type: "button", class: "sh-chip", title: "Lấy tờ này làm tờ mẫu: học khung tên, trường, tỉ lệ, cỡ chữ (gói luật sheet-layout-v0)",
        onclick: async () => {
          const logo = window.prompt("Đường dẫn tệp logo công ty (PNG/JPG), để trống nếu không có:", "") || "";
          try {
            const r = await api("/api/template/learn", {file: S.file, sheet: cur + 1, logo: logo.trim() || null});
            toast(`Đã học template '${r.template.name}' từ ${sh.sheets[cur].name}. Quét với chuẩn sheet-layout-v0 để kiểm trình bày.`);
          } catch (e) { fail(e); }
        }}, el("span", {class: "sh-n", text: "Học template từ tờ này"}), el("span", {class: "sh-sub", text: "khung tên chuẩn công ty"})));
    const lang = el("select", {"aria-label": "Ngôn ngữ đích", class: "sh-sel"}, el("option", {value: "en", text: "Tiếng Anh"}), el("option", {value: "zh", text: "Tiếng Trung"}));
    kids.push(el("span", {class: "sh-chip"}, lang, el("button", {type: "button", class: "btn-s btn-sm",
      title: "Dịch chữ " + (S.sheetSel ? "tờ đang chọn" : "cả bản vẽ") + "; ngôn ngữ nguồn tự nhận theo nội dung. Xem trước ở tab Thay đổi, ra tệp mới <tên>.<ngôn ngữ>.dxf",
      onclick: async (ev) => {
        ev.target.disabled = true;
        toast("Đang dịch… (LLM đề xuất, code kiểm số/đơn vị/mã)");
        try {
          const r = await api("/api/translate", {file: S.file, to: lang.value, sheet: S.sheetSel || null, engine: S.engine ? S.engine.name : null});
          const rp = r.report;
          toast(`Nguồn: ${rp.source_language.language_name}. ${rp.translated}/${rp.strings} chuỗi có bản dịch, ${rp.untranslated} chưa dịch, ${rp.issue_count} cần xem.`);
          if (r.preview) { S.preview = r.preview; renderChg(); loadChangesets(); }
        } catch (e) { fail(e); }
        ev.target.disabled = false;
      }}, "Dịch")));
    fill(bar, el("span", {class: "sh-lbl", text: "Tờ"}), ...kids);
  }

  function selectSheet(id) {
    S.sheetSel = id;
    S.sel = null;
    const g = S.cmp === "after" && S.geoOut ? S.geoOut : S.geo;
    const s = curSheet();
    if (g && g.viewbox && !g.empty_reason) S.view = s ? (sheetView(g, s) || tightView(g)) : tightView(g);
    renderSheetBar(); renderFinds(); renderSheet();
  }

  function modelToView(g, x, y) {
    const t = g && g.transform;
    if (!t || (S.layout || "Model") !== "Model") return null;
    return [t[0] * x + t[2], t[1] * y + t[3]];
  }
  function sheetRect(g, w) {
    const a = modelToView(g, w[0], w[1]), b2 = modelToView(g, w[2], w[3]);
    if (!a || !b2) return null;
    return [Math.min(a[0], b2[0]), Math.min(a[1], b2[1]), Math.abs(b2[0] - a[0]), Math.abs(b2[1] - a[1])];
  }
  function sheetView(g, s) {
    if (!s.window) return null;
    const r = sheetRect(g, s.window);
    if (!r || !(r[2] > 0) || !(r[3] > 0)) return null;
    const pad = 0.04 * Math.max(r[2], r[3]);
    let [x, y, w, h] = [r[0] - pad, r[1] - pad, r[2] + 2 * pad, r[3] + 2 * pad];
    const ratio = g.viewbox[3] / g.viewbox[2];
    if (h / w > ratio) { const nw = h / ratio; x -= (nw - w) / 2; w = nw; } else { const nh = w * ratio; y -= (nh - h) / 2; h = nh; }
    return [x, y, w, h];
  }

  // Viền tờ trên hình (toạ độ bản vẽ) + nhãn cỡ cố định trên màn; bấm nhãn để chọn tờ.
  function drawSheetFrames(layer, k) {
    const g = S.cmp === "after" && S.geoOut ? S.geoOut : S.geo;
    if (!S.sheets || !S.sheets.sheets || !g) return;
    for (const s of S.sheets.sheets) {
      for (const w of s.windows || []) {
        const r = sheetRect(g, w);
        if (!r) continue;
        const on = S.sheetSel === s.id;
        const grp = svgEl("g", {class: "sh-frame" + (on ? " on" : "") + (s.status === "locked" ? " locked" : ""), role: "button", tabindex: "0",
          "aria-label": `Chọn ${s.name}${s.title ? ": " + s.title : ""}`});
        grp.appendChild(svgEl("rect", {x: r[0], y: r[1], width: r[2], height: r[3]}));
        const t = svgEl("text", {x: r[0] + 6 * k, y: r[1] - 6 * k});
        t.style.fontSize = 12 * k + "px";
        t.textContent = s.name + (s.status === "locked" ? " · đã chốt" : "");
        grp.appendChild(t);
        grp.addEventListener("click", (e) => { e.stopPropagation(); selectSheet(on ? null : s.id); });
        grp.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectSheet(on ? null : s.id); } });
        layer.appendChild(grp);
      }
    }
  }

  function redrawMarks() {
    const svg = $("sheet").querySelector("svg");
    if (svg) drawMarks(svg);
  }

  // Ô chọn tờ trong danh sách lỗi (dùng được cả khi không thấy thanh Tờ, vd. bảng neo trong AutoCAD)
  function sheetPick() {
    const sel = el("select", {class: "sel sh-pick", "aria-label": "Chọn tờ"},
      el("option", {value: "", text: `Cả bản vẽ (${S.sheets.sheets.length} tờ)`, selected: !S.sheetSel}),
      S.sheets.sheets.map((s) => el("option", {value: s.id, selected: S.sheetSel === s.id,
        text: s.name + (s.title ? " · " + s.title : "") + (s.status === "locked" ? " · đã chốt" : "")})));
    sel.addEventListener("change", () => selectSheet(sel.value || null));
    return sel;
  }

  function sheetPanel() {
    if (!S.sheets || !S.sheets.sheets || !S.sheets.sheets.length) return null;
    const s = curSheet();
    if (!s) return el("div", {class: "sh-panel"}, el("div", {class: "sh-ph"}, b(`Bản vẽ có ${S.sheets.sheets.length} tờ`)), sheetPick(),
      el("div", {class: "muted", text: "Chọn một tờ để xem lỗi của riêng tờ đó và chốt tờ. Lỗi bậc Chặn phải sửa; cảnh báo cần bấm Đã xem hoặc Bỏ qua."}));
    const g = sheetGate(s.id);
    const locked = s.status === "locked";
    const meta = [s.paper, s.scale ? "1:" + s.scale : null, `${fmt(s.entity_count)} đối tượng`, s.title_source === "text-decoded" ? "tiêu đề giải mã từ chữ TCVN3/VNI" : null].filter(Boolean).join(" · ");
    const status = locked ? pill("ok", "Đã chốt", "lock")
      : g.block ? pill("err", `${g.block} lỗi chặn`, "x") : g.warnOpen ? pill("warn", `${g.warnOpen} cảnh báo cần xem`, "alert") : pill("ok", "Sẵn sàng chốt", "check");
    const scanned = Object.keys(S.audits).length > 0;
    const btn = locked
      ? el("button", {class: "btn-s btn-sm", type: "button", onclick: () => unlockSheet(s)}, "Mở lại tờ")
      : el("button", {class: "btn-p btn-sm", type: "button", disabled: !scanned || !g.canLock,
          title: !scanned ? "Quét bản vẽ trước" : g.canLock ? "Chốt tờ này" : "Còn lỗi chặn hoặc cảnh báo chưa xác nhận", onclick: () => lockSheet(s)}, icon("lock"), "Chốt tờ");
    return el("div", {class: "sh-panel"}, sheetPick(),
      el("div", {class: "sh-ph"}, b(s.name + (s.title ? ": " + s.title : "")), status),
      el("div", {class: "muted", text: meta}),
      s.stale ? el("div", {class: "muted", text: "Tờ đã chốt trước đây nhưng nội dung đã đổi: cần chốt lại."}) : null,
      el("div", {class: "sh-actions"}, btn, el("button", {class: "link", type: "button", onclick: () => selectSheet(null)}, "Xem cả bản vẽ")));
  }

  async function lockSheet(s) {
    const ok = await confirmDialog({title: `Chốt ${s.name}?`, body: [
      "Tờ chốt nghĩa là tờ này đã qua kiểm theo " + deptStd().join(" + ") + ": không còn lỗi bậc Chặn, cảnh báo đã được xem.",
      "Nếu bản vẽ đổi nội dung trong tờ sau khi chốt, tờ tự mở lại."], yes: "Chốt tờ"});
    if (!ok) return;
    try {
      await api("/api/sheets/lock", {file: S.file, sheet: s.id, standards: deptStd(), confirm: true});
      toast(`Đã chốt ${s.name}.`);
      await loadSheets(S.file);
    } catch (e) { fail(e); }
  }

  async function unlockSheet(s) {
    try {
      await api("/api/sheets/unlock", {file: S.file, sheet: s.id});
      toast(`Đã mở lại ${s.name}.`);
      await loadSheets(S.file);
    } catch (e) { fail(e); }
  }

  function showJunk() {
    const j = (S.sheets || {}).junk || {};
    const li = (t) => el("li", {text: t});
    const rows = [];
    if (j.outside && j.outside.count) rows.push(li(`${fmt(j.outside.count)} đối tượng nằm ngoài mọi tờ (không được in).`));
    if (j.stray && j.stray.count) rows.push(li(`${fmt(j.stray.count)} đối tượng lạc rất xa vùng vẽ chính (làm lệch "Vừa khung" trong CAD).`));
    if ((j.empty_layers || []).length) rows.push(li(`${j.empty_layers.length} layer rỗng: ${j.empty_layers.slice(0, 12).join(", ")}${j.empty_layers.length > 12 ? "…" : ""}`));
    if ((j.unused_blocks || []).length) rows.push(li(`${j.unused_blocks.length} khối không dùng: ${j.unused_blocks.slice(0, 12).join(", ")}${j.unused_blocks.length > 12 ? "…" : ""}`));
    const handles = [...((j.outside || {}).handles || []), ...((j.stray || {}).handles || [])].slice(0, 200);
    confirmDialog({title: "Ứng viên rác", body: [el("ul", {}, rows),
      "Đây chỉ là gợi ý để xem lại; cad-guard không tự xoá. Dọn rác (xoá layer rỗng, khối thừa) đi qua tab Thay đổi: xem trước, xác nhận, ghi ra tệp mới."],
      yes: handles.length ? "Tới trong AutoCAD" : "Đóng", no: "Đóng"}).then((go) => {
      if (go && handles.length) showInAutocad({handles, items: []});
    });
  }

  // ---------- tới đối tượng trong AutoCAD (ghi .cadguard/goto.txt; M3 đưa thẳng AutoCAD tới qua COM) ----------
  function acadTarget(f) {
    if (f.handles && f.handles.length) return {handles: f.handles.slice(0, 200), layers: []};
    const layers = [...new Set(f.items.map((it) => it.layer).filter(Boolean))];
    return layers.length ? {handles: [], layers: layers.slice(0, 100)} : null;
  }

  async function showInAutocad(f) {
    const t = acadTarget(f);
    if (!t || !S.file) return;
    try {
      const r = await api("/api/autocad/show", {file: S.file, handles: t.handles, layers: t.layers});
      if (r.sent) toast("Đã chuyển sang AutoCAD và chọn đối tượng." + (r.truncated ? " (Nhóm lớn: chỉ lấy phần đầu.)" : ""));
      else {
        if (r.toi_command && navigator.clipboard) navigator.clipboard.writeText(r.toi_command).catch(() => {});
        toast((r.message ? r.message + " " : "") + "Trong AutoCAD gõ CGDEN rồi Enter để tới đối tượng.");
      }
    } catch (e) { fail(e); }
  }

  async function showExplain(ruleId, standard) {
    try {
      const r = await api(`/api/explain?rule=${encodeURIComponent(ruleId)}&standard=${encodeURIComponent(standard)}`);
      openRuleDrawer(r, standard);
    } catch (e) { fail(e); }
  }

  // ---------- tab Thay đổi: đề xuất -> xem trước -> duyệt (tệp mới) -> hoàn tác ----------
  const KIND_VI = {layers: "layer", text_styles: "kiểu chữ", dim_styles: "kiểu kích thước", blocks: "khối"};
  function opDiff(op) {
    const list = (x) => [].concat(x || []).slice(0, 4).join(", ") + ([].concat(x || []).length > 4 ? "…" : "");
    switch (op.op) {
      case "merge_layers": return [`layer ${list(op.sources)}`, `layer ${op.target || "(chọn layer đích)"}`];
      case "move_to_layer": return [`đối tượng trên layer ${list((op.filter && op.filter.layers) || ["0"])} (không gian mô hình)`, `layer ${op.target || "(chọn layer đích)"}`];
      case "set_bylayer": return ["màu / độ dày nét gán riêng từng đối tượng", "ByLayer (theo layer)"];
      case "replace_text_style": return [`kiểu chữ ${list(op.from)}`, `kiểu chữ ${op.to || "(chọn kiểu chữ)"}`];
      case "replace_dim_style": return [`kiểu kích thước ${list(op.from)}`, `kiểu kích thước ${op.to || "(chọn)"}`];
      case "clear_dim_text_override": return ["chữ kích thước ghi đè bằng tay", "số đo tự động (<>)"];
      case "purge_unused": return [`${op.names && op.names.length ? list(op.names) : (op.kinds || []).map((k) => KIND_VI[k] || k).join(", ")} không dùng`, "xoá định nghĩa (không xoá hình)"];
      default: return [op.op, ""];
    }
  }

  function suggestStd() {
    for (const [std, r] of Object.entries(S.audits)) if (r.fixable_rules.length) return std;
    return deptStd()[0];
  }

  async function loadSuggest() {
    if (!S.file) return;
    const std = suggestStd();
    fill($("chgList"), emptyBox("Đang tìm thao tác phù hợp…"));
    $("chgFoot").hidden = true;
    try {
      S.suggest = await api("/api/changeset/suggest", {file: S.file, standard: std});
      S.suggestStd = std;
      for (const o of S.suggest.ops) o.on = !!o.checked;
      S.preview = null;
      renderChg();
      renderSuggestions();
    } catch (e) { fill($("chgList"), emptyBox("Không gợi ý được", e.message)); }
  }

  function renderChg() {
    const list = $("chgList"), foot = $("chgFoot");
    foot.hidden = true;
    const pending = S.suggest && !S.applied ? S.suggest.ops.filter((o) => o.on).length : 0;
    $("cntC").textContent = S.applied ? "✓" : String(pending);
    if (S.applied) return renderApplied();
    if (S.preview) return renderPreview();
    if (S.bulk) return renderBulk();
    if (S.dept && S.dept.view === "scene" && !S.suggest) { fill(list, emptyBox("Chưa có thay đổi", "Màn 3D chỉ xem. Các nút Chuyển Unicode, Dịch, Sửa hàng loạt vẫn dùng được: bản xem trước hiện ở đây."), changesetList()); return; }
    if (!S.suggest) {
      const fx = S.findings.filter((f) => f.fixable).length;
      fill(list, emptyBox("Chưa có thay đổi nào", "Khi bạn (hoặc trợ lý) đề xuất sửa, từng thay đổi hiện ở đây để bạn xem trước và duyệt.", el("br"), "Bản vẽ gốc không bị chạm tới.",
        S.file && fx ? [el("br"), el("br"), el("button", {class: "btn-p", type: "button", onclick: loadSuggest}, icon("gear"), `Đề xuất sửa ${fx} nhóm tự sửa được`)] : null),
      changesetList());
      return;
    }
    const s = S.suggest;
    const cards = s.ops.map((o) => {
      const cb = el("input", {type: "checkbox", id: "cb-" + o.key});
      cb.checked = o.on;
      const [from, to] = opDiff(o.op);
      const plus = el("div", {class: "p", text: "+ " + to});
      cb.addEventListener("change", () => { o.on = cb.checked; renderChgCount(); });
      const choices = Object.entries(o.choices || {}).map(([field, values]) => {
        const sel = el("select", {class: "sel", id: `ch-${o.key}-${field}`, "aria-label": field === "to" ? "Kiểu chữ đích" : "Layer đích"},
          el("option", {value: "", text: "— chọn —"}), values.map((v) => el("option", {value: v, text: v})));
        sel.value = o.op[field] || "";
        sel.addEventListener("change", () => { o.op[field] = sel.value; plus.textContent = "+ " + opDiff(o.op)[1]; if (sel.value) { cb.checked = true; o.on = true; renderChgCount(); } });
        return el("div", {class: "choice"}, el("label", {for: sel.id, text: field === "to" ? "Đổi sang" : "Layer đích"}), sel);
      });
      return el("div", {class: "op"},
        el("label", {for: cb.id}, cb, el("span", {}, b(o.title), el("br"), el("span", {class: "f-rule", text: `${o.rule_id} · ${o.op.op}`}),
          el("span", {class: "f-d", text: o.description}),
          el("span", {class: "diff"}, el("div", {class: "m", text: "− " + from}), plus))),
        choices);
    });
    const notes = s.notes.map((n) => el("div", {class: "f-card"}, el("div", {class: "f-top"}, pill("neu sm", n.rule_id), icon("hand")), el("div", {class: "f-d", text: n.message})));
    fill(list, el("div", {class: "safe"}, icon("shield"), el("span", {}, "Thao tác chỉ nằm trong từ vựng cố định (không xoá đối tượng hình học). ",
      s.protected_patterns ? `Hồ sơ công ty bảo vệ ${s.protected_patterns} mẫu layer.` : "")),
    s.ops.length ? cards : emptyBox("Không có thao tác sửa tự động", "Các phát hiện còn lại cần sửa trong phần mềm CAD."),
    notes.length ? [el("div", {class: "sub-h", text: "Cần người sửa"}), notes] : null, changesetList());
    renderChgFoot();
  }

  function renderChgCount() {
    const n = S.suggest ? S.suggest.ops.filter((o) => o.on).length : 0;
    $("cntC").textContent = String(n);
    const btn = $("previewBtn");
    if (btn) { btn.disabled = !n; fill(btn, icon("search"), `Xem trước ${n} thay đổi`); }
  }

  function renderChgFoot() {
    const foot = $("chgFoot");
    if (!S.suggest || !S.suggest.ops.length) { foot.hidden = true; return; }
    const n = S.suggest.ops.filter((o) => o.on).length;
    fill(foot, el("div", {class: "safe"}, icon("check"), el("span", {}, "Chưa ghi gì. Xem trước là chạy khô trong bộ nhớ; khi duyệt, kết quả lưu thành ", b("tệp mới"), ", bản gốc không bị sửa.")),
      el("div", {class: "bar-act"},
        el("button", {class: "btn-p", type: "button", id: "previewBtn", disabled: !n, onclick: doPreview}, icon("search"), `Xem trước ${n} thay đổi`),
        el("button", {class: "btn-s", type: "button", onclick: () => { S.suggest = null; renderChg(); renderSuggestions(); say("ai", "Đã bỏ đề xuất. Bản vẽ không thay đổi gì."); }}, "Bỏ đề xuất")));
    foot.hidden = false;
  }

  function selectedOps() {
    const ops = [];
    for (const o of S.suggest.ops) {
      if (!o.on) continue;
      for (const field of Object.keys(o.choices || {})) if (!o.op[field]) throw new Error(`Chọn giá trị cho “${o.title}” trước khi xem trước.`);
      ops.push(JSON.parse(JSON.stringify(o.op)));
    }
    if (!ops.length) throw new Error("Chưa chọn thay đổi nào.");
    return ops;
  }

  async function doPreview() {
    let ops;
    try { ops = selectedOps(); } catch (e) { fail(e); return; }
    const btn = $("previewBtn");
    if (btn) btn.disabled = true;
    try {
      S.preview = await api("/api/changeset/propose", {file: S.file, standard: S.suggestStd, ops});
      toolCard("cadguard.propose_changeset", `{ "file": "${S.file}", "ops": ${ops.length}, "dry_run": true }`, "", `${S.preview.ops ? S.preview.ops.length : ops.length} thao tác · chưa ghi tệp nào`);
      renderChg();
      renderSuggestions();
      loadChangesets();
    } catch (e) { fail(e); if (btn) btn.disabled = false; }
  }

  function checksList(checks) {
    return el("ul", {class: "checks"}, (checks || []).map((c) => el("li", {class: c.ok ? "" : "bad"}, icon(c.ok ? "check" : "x"), el("span", {text: c.message || c.id}))));
  }

  function renderPreview() {
    const pv = S.preview;
    const regressed = pv.rules_regressed || 0;
    const ok = pv.ok && !regressed;
    const ops = (pv.ops || []).map((r) => el("li", {text: `${r.op}: ${fmt(r.affected)} mục` + (r.skipped_protected ? ` (bỏ qua ${r.skipped_protected} trên layer bảo vệ)` : "")}));
    const rr = pv.rules || {};
    fill($("chgList"),
      el("div", {class: "pv " + (ok ? "result-ok" : "result-bad")},
        el("h3", {}, "Xem trước ", el("span", {class: "f-rule", text: pv.changeset_id})),
        el("p", {}, ok ? pill("ok", "Đạt kiểm", "check") : pill("err", "Không đạt", "x"), " ", pv.summary_vi || ""),
        kv([["Tệp gốc", pv.source && pv.source.path], ["Chuẩn", `${pv.standard} ${pv.standard_version || ""}`], ["Thay đổi", pv.diff_summary_vi],
          ["Luật hết lỗi", (rr.resolved || []).join(", ") || "không"], ["Luật giảm", (rr.improved || []).join(", ") || "không"],
          ["Luật xuất hiện mới", (rr.regressed || []).join(", ") || "không"]]),
        el("div", {class: "f-d"}, b("Theo thao tác:"), el("ul", {}, ops)),
        el("details", {}, el("summary", {class: "muted", text: "Các mục tự kiểm"}), checksList(pv.checks))),
      changesetList());
    const foot = $("chgFoot");
    fill(foot, el("div", {class: "safe"}, icon("check"), el("span", {text: "Chưa ghi bản vẽ nào. Duyệt sẽ ghi ra tệp mới cạnh tệp gốc, tự mở lại và chạy lại luật; không đạt thì không tạo tệp."})),
      el("div", {class: "bar-act"},
        el("button", {class: "btn-p", type: "button", id: "okBtn", disabled: !ok, onclick: doApply}, icon("check"), "Duyệt & lưu tệp mới"),
        el("button", {class: "btn-s", type: "button", onclick: () => { S.preview = null; renderChg(); renderSuggestions(); }}, "Quay lại")));
    foot.hidden = false;
  }

  async function doApply() {
    const pv = S.preview;
    const ok = await confirmDialog({title: "Duyệt và lưu tệp mới?",
      body: [`Ghi ra TỆP MỚI cạnh “${pv.source.path}” (tên có đuôi .cg-….dxf). Tệp gốc giữ nguyên, không bị ghi.`,
        "cad-guard mở lại tệp mới và chạy lại luật; không đạt thì không tạo tệp. Bỏ được bất cứ lúc nào (hoàn tác)."],
      yes: "Duyệt và lưu", no: "Chưa"});
    if (!ok) return;
    const btn = $("okBtn");
    if (btn) btn.disabled = true;
    say("me", "Duyệt và lưu");
    let r;
    try { r = await api("/api/changeset/apply", {changeset_id: pv.changeset_id, confirm: true}); } catch (e) { fail(e); if (btn) btn.disabled = false; return; }
    S.applied = {cid: r.changeset_id, output: r.output.path, source: r.source.path, validation: r.validation || {}};
    S.preview = null; S.suggest = null; S.cmp = "after";
    toolCard("cadguard.apply_changeset", `{ "changeset": "${r.changeset_id}", "out": "${r.output.path}" }`, "", "đã ghi tệp mới");
    toolCard("cadguard.validate_output", `{ "file": "${r.output.path}" }`, "", (r.validation && r.validation.summary_vi) || "đã kiểm");
    toast(`Đã lưu ${r.output.path} · bản gốc không đổi`);
    await loadFiles();
    await recheckApplied();
    const left = S.findings.filter((f) => f.st === "open").length;
    sayRich([el("p", {}, "Đã lưu ", b(r.output.path), ". Mình đã mở lại tệp mới và chạy lại luật: ", (r.validation && r.validation.ok) ? "không hỏng gì." : "có mục kiểm không đạt, xem tab Thay đổi.",
      ` Còn `, b(`${left} nhóm phát hiện`), " cần người xử lý."), el("div", {class: "src", text: "Kết quả công cụ cad-guard (tất định), không qua mô hình AI."})]);
    renderAll();
    loadChangesets();
  }

  async function recheckApplied() {
    const out = S.applied.output;
    try {
      S.geoOut = await fetchView(out, () => S.applied && S.applied.output === out, null);
    } catch (_) { S.geoOut = null; }
    S.view = null;
    const remain = new Set();
    const counts = {E: 0, W: 0, I: 0};
    for (const std of deptStd()) {
      try {
        const r = await api("/api/audit", {file: out, standard: std, dept: S.dept.id});
        for (const g of r.groups) for (const rule of g.rules) remain.add(std + "|" + rule.rule_id);
        for (const k of ["E", "W", "I"]) counts[k] += r.counts[k];
      } catch (_) { /* giữ nguyên */ }
    }
    S.stat[out] = counts;
    for (const f of S.findings) f.st = remain.has(f.std + "|" + f.rule_id) ? "open" : "fixed";
    $("cmp").hidden = false; $("cmpLabel").hidden = false;
    for (const x of $$("#cmp button")) x.setAttribute("aria-pressed", x.dataset.v === "after" ? "true" : "false");
    $("cvTitle").textContent = out;
  }

  function renderApplied() {
    const a = S.applied;
    const v = a.validation || {};
    fill($("chgList"),
      el("div", {class: "op"}, el("div", {class: "bar-act"}, pill("ok", "Đã lưu", "check"), b(a.output)),
        el("p", {class: "f-d", text: `Bản gốc ${a.source} giữ nguyên. Bạn có thể bỏ bản mới nếu thấy chưa ổn.`})),
      el("div", {class: "op"}, b("Đã tự kiểm sau khi lưu"), checksList(v.checks)),
      changesetList());
    const foot = $("chgFoot");
    fill(foot, el("div", {class: "bar-act"},
      el("button", {class: "btn-s", type: "button", onclick: () => openFile(a.output, {scan: true})}, icon("file"), "Mở tệp mới"),
      el("button", {class: "btn-s", type: "button", onclick: () => doUndo(a.cid, a.output)}, icon("undo"), "Bỏ bản mới (hoàn tác)")));
    foot.hidden = false;
  }

  async function doUndo(cid, outPath) {
    const ok = await confirmDialog({title: `Bỏ bản ${outPath || "mới"}?`,
      body: ["Tệp mới này sẽ bị xoá. Bản gốc không bị ảnh hưởng.", "Nếu tệp mới đã bị sửa sau khi lưu (mã băm khác) thì cad-guard từ chối xoá."],
      yes: "Bỏ bản mới", no: "Giữ lại", danger: true});
    if (!ok) return;
    try {
      const r = await api("/api/changeset/undo", {changeset_id: cid, confirm: true});
      toast("Đã bỏ " + r.removed);
      if (S.applied && S.applied.cid === cid) {
        S.applied = null; S.geoOut = null; S.cmp = "after"; S.view = null;
        for (const f of S.findings) f.st = "open";
        $("cmp").hidden = true; $("cmpLabel").hidden = true;
        $("cvTitle").textContent = S.file || "";
        say("ai", `Đã bỏ bản mới. Mọi thứ quay về như lúc vừa quét; bản gốc ${S.file} không bị đụng tới.`);
      }
      delete S.stat[r.removed];
      if (S.file === r.removed) { S.file = null; resetDrawing(true); }
      await loadFiles();
      renderAll();
      loadChangesets();
    } catch (e) { fail(e); }
  }

  async function loadChangesets() {
    if (!hasProject()) return;
    try { S.changesets = (await api("/api/changesets")).changesets; } catch (_) { return; }
    const box = $("csList");
    if (box) fill(box, ...changesetItems());
  }

  function changesetItems() {
    const list = S.changesets.filter((c) => !S.file || c.source === S.file || c.source === parentOf(S.file));
    if (!list.length) return [el("p", {class: "muted small", text: "Chưa có changeset nào cho bản vẽ này."})];
    return list.slice(0, 20).map((c) => {
      const a = c.applied;
      const state = !a ? pill("neu sm", "chưa áp dụng") : a.undone_at ? pill("neu sm", "đã hoàn tác") : pill("ok sm", "đã áp dụng");
      return el("div", {class: "f-card"},
        el("div", {class: "f-top"}, el("span", {class: "f-rule", text: c.id}), state,
          c.created_by === "agent" ? pill("info sm", "trợ lý đề xuất") : pill("neu sm", "bạn đề xuất"),
          c.ok === false ? pill("err sm", "xem trước không đạt") : null),
        el("div", {class: "f-d", text: `${c.standard} · ${c.ops} thao tác · ${when(c.created_at)}`}),
        a && !a.undone_at && a.output ? el("div", {class: "f-d", text: "Tệp mới: " + a.output.path}) : null,
        el("div", {class: "bar-act mt8"},
          !a ? el("button", {class: "btn-s btn-sm", type: "button", onclick: () => openChangeset(c.id)}, "Xem trước & duyệt") : null,
          a && !a.undone_at ? el("button", {class: "btn-s btn-sm", type: "button", onclick: () => doUndo(c.id, a.output && a.output.path)}, icon("undo"), "Hoàn tác") : null));
    });
  }

  function changesetList() {
    if (!S.file) return null;
    return [el("div", {class: "sub-h", text: "Các changeset của bản vẽ này"}), el("div", {id: "csList", class: "list-in"}, ...changesetItems())];
  }

  async function openChangeset(cid) {
    try {
      const c = await api("/api/changeset?id=" + encodeURIComponent(cid));
      if (!c.preview) { toast("Changeset không có phần xem trước."); return; }
      if (S.file !== c.source.path) await openFile(c.source.path, {scan: false, intro: false});
      S.preview = {...c.preview, changeset_id: c.id};
      rightTab("chg");
      renderChg();
    } catch (e) { fail(e); }
  }

  function renderAll() { renderFiles(); renderFinds(); renderChg(); renderSheet(); renderSuggestions(); renderWorkSide(); }

  // ---------- trò chuyện ----------
  function logAdd(node) { const log = $("log"); log.appendChild(node); log.scrollTop = log.scrollHeight; return node; }
  function say(who, text) {
    if (who === "err") return logAdd(el("div", {class: "msg err", text}));
    return logAdd(el("div", {class: "msg " + who, text}));
  }
  function sayRich(nodes) { return logAdd(el("div", {class: "msg ai rich"}, nodes)); }
  function showTyping() { return logAdd(el("div", {class: "typing"}, el("i"), el("i"), el("i"), " Đang xử lý")); }
  function toolCard(name, args, ms, out) {
    return logAdd(el("details", {class: "tool"}, el("summary", {}, el("span", {class: "ok"}, icon("check")), el("code", {text: name}), el("span", {class: "spacer"}), el("span", {text: ms || ""})),
      el("pre", {text: `${args}\n→ ${out}`})));
  }

  function introChat() {
    fill($("log"));
    S.history = [];
    if (!S.file) return;
    const stds = deptStd();
    sayRich([el("p", {}, "Xin chào, phòng ", b(S.dept.name), ". Mình đang xem ", b(S.file), ". ",
      stds.length ? ["Mình quét theo chuẩn ", b(stds.join(" + ")), ", giải thích và đề xuất sửa. Mọi sửa đổi đều ghi ra ", b("tệp mới"), " sau khi bạn duyệt."]
        : "Phòng này hiện chỉ xem 3D dựng từ bản vẽ (chỉ xem, không sửa).")]);
  }

  function renderSuggestions() {
    const s = [];
    const nx = S.dept ? nextNames(S.dept) : [];
    const scanned = Object.keys(S.audits).length > 0;
    const firstRule = S.findings.find((f) => f.st === "open");
    const needRule = S.findings.find((f) => f.st === "open" && !f.fixable);
    if (S.file && S.dept && S.dept.view !== "scene") {
      if (!scanned) s.push(["Quét bản vẽ này", () => doScan(false), true], ["Bản vẽ này có gì?", doAbout]);
      else if (S.applied) {
        s.push([`Soạn gói bàn giao cho ${nx.join(" và ") || "xưởng"}`, doHandoverNote, true], ["Quét lại bản mới", () => openFile(S.applied.output, {scan: true})]);
        if (needRule) s.push([`Giải thích lỗi ${needRule.rule_id}`, () => doExplain(needRule)]);
      } else if (S.suggest || S.preview) {
        s.push(["Mở tab Thay đổi", () => rightTab("chg"), true]);
        if (firstRule) s.push([`Giải thích lỗi ${firstRule.rule_id}`, () => doExplain(firstRule)]);
      } else {
        if (S.findings.some((f) => f.fixable)) s.push(["Sửa các lỗi tự sửa được", doPropose, true]);
        if (firstRule) s.push([`Giải thích lỗi ${firstRule.rule_id}`, () => doExplain(firstRule)]);
        s.push([`Soạn gói bàn giao cho ${nx.join(" và ") || "xưởng"}`, doHandoverNote, !S.findings.some((f) => f.fixable)]);
      }
    } else if (S.file) s.push(["Bản vẽ này có gì?", doAbout]);
    fill($("sug"), ...s.map(([t, fn, p]) => el("button", {type: "button", class: p ? "primary" : "", onclick: () => { if (S.busy) return; if (t !== "Quét bản vẽ này") say("me", t); fn(); }}, t)));
  }

  async function doAbout() {
    try {
      const r = await api("/api/summary", {file: S.file});
      toolCard("cadguard.get_model_summary", `{ "file": "${S.file}" }`, "", "đã lấy tóm tắt (có trần kích thước)");
      const top = Object.entries(r.entities_by_type || {}).slice(0, 4).map(([k, v]) => `${fmt(v)} ${k}`).join(", ");
      const units = {4: "mm", 5: "cm", 6: "m", 1: "inch", 0: "không đặt đơn vị"}[r.insunits] || `mã ${r.insunits}`;
      sayRich([el("p", {}, "Đây là bản vẽ ", b(`DXF ${r.dxf_version || "?"}`), `, đơn vị ${units}, ${fmt(r.layer_count)} layer, ${fmt(r.block_count)} khối dùng.`),
        el("p", {text: `Đối tượng nhiều nhất: ${top || "không có"}. Có ${(r.layouts || []).length} layout.`}),
        el("div", {class: "src", text: "Kết quả công cụ cad-guard (tất định), không qua mô hình AI."})]);
    } catch (e) { say("err", e.message); }
    renderSuggestions();
  }

  async function doExplain(f) {
    try {
      const r = await api(`/api/explain?rule=${encodeURIComponent(f.rule_id)}&standard=${encodeURIComponent(f.std)}`);
      toolCard("cadguard.explain_rule", `{ "rule": "${f.rule_id}" }`, "", "đã lấy mô tả luật và tham số");
      const params = Object.entries(r.rule_params || {}).map(([k, v]) => `${k} = ${JSON.stringify(v)}`).join("; ");
      sayRich([el("p", {}, b(`${r.id} · ${r.title}.`)),
        el("p", {}, `Mức `, b(SEV[r.severity] ? SEV[r.severity][1].toLowerCase() : r.severity), `. Bản vẽ này có ${fmt(f.count)} chỗ vi phạm. `,
          f.fixable ? "Có thao tác sửa an toàn trong từ vựng cố định (tab Thay đổi)." : "Chưa có thao tác sửa tự động: cần sửa trong phần mềm CAD."),
        params ? el("p", {text: "Tham số đang áp: " + params}) : null,
        el("div", {class: "src", text: `Căn cứ: standards/${f.std}.yaml · ${r.id}` + (r.source ? ` · nguồn ${r.source}` : "")}),
        el("button", {class: "btn-s btn-sm", type: "button", onclick: () => openRuleDrawer(r, f.std)}, "Xem đầy đủ")]);
    } catch (e) { say("err", e.message); }
  }

  async function doPropose() {
    rightTab("chg");
    await loadSuggest();
    if (!S.suggest) return;
    const n = S.suggest.ops.length;
    const need = S.findings.filter((f) => f.st === "open" && !f.fixable);
    toolCard("cadguard.suggest_ops", `{ "file": "${S.file}", "standard": "${S.suggestStd}" }`, "", `${n} thao tác gợi ý · chưa ghi tệp nào`);
    sayRich([el("p", {}, "Mình đề xuất ", b(`${n} thay đổi`), " và ", b("chưa ghi gì"), ". Hãy xem tab ", b("Thay đổi"), ", bỏ tick việc nào bạn chưa muốn, bấm Xem trước rồi duyệt."),
      need.length ? el("p", {}, "Những việc mình ", b("không tự làm"), ": ", need.slice(0, 4).map((f) => f.title.toLowerCase()).join("; "), need.length > 4 ? "…" : "", ".") : null,
      el("div", {class: "src", text: "Thao tác gợi ý do cad-guard sinh tất định từ phát hiện, không qua mô hình AI."})]);
  }

  function handoverLines() {
    const lines = [];
    const res = Object.values(S.audits);
    const open = S.findings.filter((f) => f.st === "open");
    const e = open.filter((f) => f.severity === "E");
    lines.push(`Bản vẽ: ${S.applied ? S.applied.output + " (bản đã sửa, tệp mới)" : S.file}`);
    lines.push(`Kiểm theo: ${res.map((r) => `${r.standard} ${r.version}`).join(", ")}` + (S.session.profile ? ` · hồ sơ ${S.session.profile.name} ${S.session.profile.version}` : ""));
    lines.push(`Còn lại: ${e.length} nhóm lỗi mức E, ${open.length - e.length} nhóm cảnh báo/gợi ý`);
    const fixed = S.findings.filter((f) => f.st === "fixed");
    if (fixed.length) lines.push(`Đã sửa trong tệp mới: ${fixed.map((f) => f.rule_id).join(", ")}`);
    for (const f of open.slice(0, 6)) lines.push(`${f.rule_id} (${SEV[f.severity][1]}): ${f.title} · ${f.count} chỗ`);
    return {lines, blocked: e.length > 0};
  }

  function doHandoverNote() {
    if (!Object.keys(S.audits).length) { say("ai", "Hãy quét bản vẽ trước, mình mới soạn được ghi chú bàn giao từ kết quả kiểm."); return; }
    const nx = nextNames(S.dept);
    const {lines, blocked} = handoverLines();
    toolCard("cadguard.get_handover_data", `{ "file": "${S.file}" }`, "", "dữ liệu bàn giao có cấu trúc");
    const copy = el("button", {class: "btn-s btn-sm", type: "button", onclick: async () => {
      try { await navigator.clipboard.writeText(lines.join("\n")); toast("Đã sao chép ghi chú bàn giao"); } catch (_) { toast("Không sao chép được; hãy chọn chữ và Ctrl+C."); }
    }}, icon("copy"), "Sao chép");
    const target = S.applied ? S.applied.output : S.file;
    const mark = el("button", {class: "btn-p btn-sm", type: "button", disabled: blocked, onclick: () => markHandover(target)},
      nx.length ? `Đánh dấu sẵn sàng giao cho ${nx.join(" và ")}` : "Đánh dấu sẵn sàng xuất cho xưởng");
    sayRich([el("p", {}, "Đây là ", b(`ghi chú bàn giao cho ${nx.join(" và ") || "xưởng"}`), ", tạo từ dữ liệu có cấu trúc của bản vẽ:"),
      el("div", {class: "note-card"}, el("div", {class: "lbl"}, icon("info"), "Sinh tự động từ dữ liệu, không phải văn bản tự do của mô hình"),
        el("ul", {}, lines.map((t) => el("li", {text: t})),
          blocked ? el("li", {class: "warnli"}, icon("alert", "i14"), " Còn lỗi mức E: chưa nên bàn giao") : null),
        el("div", {class: "bar-act"}, copy, mark)),
      el("div", {class: "src", text: "Đánh dấu chỉ ghi vào lịch sử dự án trên máy này; cad-guard không gửi tệp đi đâu."})]);
  }

  // ----- engine -----
  async function loadEngines(refresh) {
    try {
      const r = await api("/api/engines" + (refresh ? "?refresh=1" : ""));
      S.engines = r.engines; S.groups = r.groups; S.maxCost = r.max_cost_usd;
      const saved = sessionStorage.getItem("cg-engine");
      const usable = (e) => e.available && !e.needs_model;
      const pick = S.engines.find((e) => e.name === saved && usable(e)) || S.engines.find((e) => e.name === r.default_engine && usable(e))
        || S.engines.find(usable);
      S.engine = pick || null;
      renderEngineMenu();
      if (refresh) $("refreshNote").textContent = "Đã kiểm lại lúc " + new Date().toLocaleTimeString("vi-VN");
    } catch (e) { fail(e); }
  }

  function renderEngineMenu() {
    const e = S.engine;
    $("engineName").textContent = e ? e.title.replace(/ \(.*$/, "").replace(/ — .*/, "") : "chưa có";
    const anon = S.session ? S.session.anonymize : true;
    fill($("chatHead"), icon("bot"), el("span", {}, e ? ["Đang dùng ", b(e.title), anon ? " · dự án NDA: chỉ thấy kết quả đã ẩn danh" : " · nội bộ: thấy nội dung bản vẽ"]
      : "Chưa có trợ lý dùng được: cài/đăng nhập một CLI hoặc nhập khoá API ở màn Kết nối AI."));
    $("sendBtn").disabled = !e || S.busy;
    const items = [];
    for (const g of S.groups) {
      items.push(el("div", {class: "grp", text: g.title}));
      for (const x of S.engines.filter((y) => y.mode === g.mode)) {
        const exp = !x.available && x.installed === true && /Thử nghiệm/.test(x.reason || "");
        items.push(menuItem(e && x.name === e.name, x.title, x.available ? (x.status || "dùng được") + (x.model ? ` · ${x.model}` : "")
          : exp ? "Bấm để bật (đang ở chế độ thử nghiệm)" : x.reason,
          async () => {
            if (exp) {
              try { await api("/api/ai/settings", {codex_experimental: true}); await loadEngines(false); }
              catch (err) { fail(err); return; }
              x = S.engines.find((y) => y.name === x.name) || x;
              if (!x.available) { toast(x.reason || "Chưa dùng được."); return; }
            }
            S.engine = x; sessionStorage.setItem("cg-engine", x.name); renderEngineMenu(); toast("Trợ lý: " + x.title);
          }, !x.available && !exp));
      }
    }
    items.push(menuItem(false, "Cấu hình kết nối AI…", "Đăng nhập CLI, nhập khoá API, chọn trợ lý mặc định", () => go("connect")));
    fill($("engineMenu"), ...items);
    renderCost(null);
  }

  function usageText(u) {
    if (!u) return "";
    const cost = u.cost_usd === null || u.cost_usd === undefined ? "chi phí không rõ"
      : `~${Number(u.cost_usd).toLocaleString("vi-VN", {maximumFractionDigits: 4})} USD` + (u.cost_estimated ? " (ước tính)" : "");
    return `${fmt(u.input_tokens)} token vào · ${fmt(u.output_tokens)} ra · ${cost}`;
  }
  function addUsage(total, u) {
    for (const k of ["input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"]) total[k] = (total[k] || 0) + (u[k] || 0);
    if (u.cost_usd !== null && u.cost_usd !== undefined) total.cost_usd = (total.cost_usd || 0) + u.cost_usd;
    total.cost_estimated = total.cost_estimated || u.cost_estimated;
  }
  function renderCost(turn) {
    const su = S.sessionUsage;
    const used = su.cost_usd ? Number(su.cost_usd).toLocaleString("vi-VN", {maximumFractionDigits: 4}) : "0";
    $("capUsed").textContent = `Phiên này đã dùng ~${used} USD`;
    if (!su.input_tokens && !turn) { $("costLine").textContent = ""; return; }
    $("costLine").textContent = (turn ? "Lượt này: " + usageText(turn) + " — " : "") + "Cả phiên: " + usageText(su)
      + (S.engine && S.engine.mode === "cli" ? " (gói thuê bao: số USD là ước tính)" : "");
  }

  async function sendChat(ev) {
    ev.preventDefault();
    if (S.busy) return;
    const text = $("inp").value.trim();
    if (!text) return;
    const e = S.engine;
    if (!e) { toast("Chưa có trợ lý dùng được. Vào Kết nối AI để cấu hình."); return; }
    if (e.needs_model) { toast("Engine này cần tên mô hình: đặt ở màn Kết nối AI."); return; }
    $("inp").value = "";
    S.history.push({role: "user", content: text});
    say("me", text);
    const ai = el("div", {class: "msg ai"});
    const typing = showTyping();
    let aiAdded = false, answer = "", proposed = false;
    const tools = {};
    const turn = {input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_write_tokens: 0, cost_usd: null};
    setBusy(true);
    const ensureAi = () => { if (!aiAdded) { typing.before(ai); aiAdded = true; } };
    const handle = (m) => {
      switch (m.type) {
        case "start": S.run = m.run_id; break;
        case "text": ensureAi(); ai.textContent += m.text || ""; break;
        case "tool_call": {
          const pre = el("pre", {text: "Tham số: " + JSON.stringify(m.arguments, null, 2)});
          const st = el("span", {class: "run", text: "đang chạy…"});
          const d = el("details", {class: "tool"}, el("summary", {}, el("span", {class: "ok"}, icon("gear")), el("code", {text: m.name}), el("span", {class: "spacer"}), st), pre);
          tools[m.id || m.name] = {st, pre};
          typing.before(d);
          break;
        }
        case "tool_result": {
          const t = tools[m.id || m.name];
          const txt = "→ " + (m.content || "");
          if (t) { t.st.textContent = m.is_error ? "lỗi" : "xong"; t.pre.textContent += "\n" + txt; }
          if (m.name && m.name.endsWith("propose_changeset") && !m.is_error) proposed = true;
          break;
        }
        case "usage": addUsage(turn, m.usage || {}); renderCost(turn); break;
        case "error": typing.before(el("div", {class: "msg err", text: m.message || "Lỗi."})); break;
        case "stopped": typing.before(el("div", {class: "msg note", text: m.message})); break;
        case "done": if (m.text) { ensureAi(); ai.textContent = m.text; answer = m.text; } else answer = ai.textContent; break;
        case "summary": if (m.cancelled) { answer = ""; typing.before(el("div", {class: "msg note", text: "Đã dừng lượt này (câu trả lời dở không đưa vào lịch sử)."})); } break;
        default: break;
      }
      $("log").scrollTop = $("log").scrollHeight;
    };
    try {
      const r = await fetch("/api/chat", {method: "POST", cache: "no-store",
        headers: {"X-CadGuard-Token": TOKEN, "Content-Type": "application/json"},
        body: JSON.stringify({engine: e.name, model: null, messages: S.history, standard: chatStd(), allow_propose: $("allowPropose").checked})});
      if (!r.ok) {
        let msg = "Lỗi máy chủ " + r.status;
        try { msg = (await r.json()).error || msg; } catch (_) { /* giữ msg */ }
        if (r.status === 401) $("tokenBanner").hidden = false;
        throw new Error(msg);
      }
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const {value, done} = await reader.read();
        if (done) break;
        buf += dec.decode(value, {stream: true});
        let nl;
        while ((nl = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, nl).trim();
          buf = buf.slice(nl + 1);
          if (line) { try { handle(JSON.parse(line)); } catch (_) { /* dòng hỏng: bỏ */ } }
        }
      }
    } catch (err) { typing.before(el("div", {class: "msg err", text: err.message})); }
    typing.remove();
    addUsage(S.sessionUsage, turn);
    renderCost(turn);
    if (answer) S.history.push({role: "assistant", content: answer}); else S.history.pop();
    if (proposed) {
      say("note", "Trợ lý đã đề xuất một changeset (chưa ghi bản vẽ). Xem ở tab “Thay đổi”, kiểm phần xem trước rồi tự quyết duyệt.");
      loadChangesets();
    }
    S.run = null;
    setBusy(false);
  }

  function setBusy(v) {
    S.busy = v;
    $("sendBtn").disabled = v || !S.engine;
    $("sendBtn").hidden = v;
    $("stopBtn").hidden = !v;
    if (v) $("stopBtn").focus(); else $("inp").focus();
  }

  async function stopChat() {
    if (!S.run) return;
    $("stopBtn").disabled = true;
    try { await api("/api/chat/stop", {run_id: S.run}); } catch (e) { fail(e); }
    $("stopBtn").disabled = false;
  }

  // ---------- LUẬT ÁP DỤNG ----------
  async function loadRules() {
    if (!hasProject()) return;
    const sel = $("ruleStd");
    if (!sel.options.length) fill(sel, el("option", {value: "", text: "Tất cả chuẩn"}), S.session.standards.map((n) => el("option", {value: n, text: n})));
    if (!S.rules) {
      S.rules = {};
      try {
        for (const n of S.session.standards) S.rules[n] = await api("/api/rules?standard=" + encodeURIComponent(n));
      } catch (e) { fail(e); }
    }
    renderRules();
  }

  function openCatalog(o) {
    S.ruleFilter = {dept: o.dept || "", q: o.rule || "", kind: "", sev: ""};
    $("rq").value = S.ruleFilter.q;
    $("fKind").value = ""; $("fSev").value = "";
    $("ruleStd").value = "";
    go("rules");
  }

  function ruleRows() {
    const out = [];
    for (const [std, data] of Object.entries(S.rules || {})) for (const r of data.rules) out.push({...r, std, version: data.version});
    return out;
  }

  function renderRules() {
    if (!S.rules) return;
    const F = S.ruleFilter;
    const stdSel = $("ruleStd").value;
    const deps = S.session.departments;
    const deptsOf = (std) => deps.filter((d) => d.standards.includes(std));
    const all = ruleRows().filter((r) => (!stdSel || r.std === stdSel) && (r.implemented || F.kind === "todo"));
    fill($("srcline"), pill("ok", "Sửa được, không cần tài khoản"),
      el("span", {}, Object.values(S.rules).map((d, i) => [i ? " · " : "", "Chuẩn ", b(`${d.standard} ${d.version}`)])),
      el("span", {}, "Hồ sơ công ty: ", S.session.profile ? b(`${S.session.profile.name} ${S.session.profile.version}`) : "không dùng"),
      el("span", {}, "Danh mục sinh từ tệp: ", Object.keys(S.rules).map((n, i) => [i ? " + " : "", el("code", {text: `standards/${n}.yaml`})]), " + ", el("code", {text: "departments.json"})));
    const card = (d) => {
      const L = all.filter((r) => d.standards.includes(r.std));
      const run = L.filter((r) => r.implemented && r.enabled).length, nc = L.filter((r) => !r.implemented).length, off = L.length - run - nc, n = L.length || 1;
      const bar = el("div", {class: "bar2", "aria-hidden": "true"}, el("i"), el("i"), el("i"));
      const [i1, i2, i3] = bar.children;
      i1.style.width = (run / n * 100) + "%"; i1.style.background = "var(--ok)";
      i2.style.width = (off / n * 100) + "%"; i2.style.background = "var(--warn)";
      i3.style.width = (nc / n * 100) + "%"; i3.style.background = "var(--border-strong)";
      return el("button", {class: "cov", type: "button", "aria-pressed": F.dept === d.id ? "true" : "false", onclick: () => { F.dept = F.dept === d.id ? "" : d.id; renderRules(); }},
        el("div", {class: "nm", text: d.name}), el("div", {class: "big", text: `${L.length} luật`}), bar,
        el("div", {class: "sub", text: d.standards.length ? `${run} đang chạy · ${off} tắt · ${nc} chưa cài code` : "Chưa có chuẩn (đang phát triển)"}));
    };
    const todo = ruleRows().filter((r) => (!stdSel || r.std === stdSel) && !r.implemented).length;
    const covs = $("covs");
    covs.classList.toggle("c-auto", true);
    fill(covs, ...deps.map(card), el("button", {class: "cov gap", type: "button", "aria-pressed": F.kind === "todo" ? "true" : "false",
      onclick: () => { F.kind = F.kind === "todo" ? "" : "todo"; $("fKind").value = F.kind; renderRules(); }},
    el("div", {class: "nm", text: "Chưa cài code"}), el("div", {class: "big", text: `${todo} luật`}),
    el("div", {class: "sub", text: "Có trong chuẩn nhưng chưa chạy, chưa chặn gì. Bấm để xem."})));
    const q = F.q.trim().toLowerCase();
    const rows = all.filter((r) => {
      if (F.dept && !(deptById(F.dept) || {standards: []}).standards.includes(r.std)) return false;
      if (q && !(r.id.toLowerCase().includes(q) || r.title.toLowerCase().includes(q))) return false;
      if (F.sev && r.severity !== F.sev) return false;
      if (F.kind === "run") return r.implemented && r.enabled;
      if (F.kind === "todo") return !r.implemented;
      if (F.kind === "off") return r.enabled_default && !r.enabled;
      if (F.kind === "changed") return r.params_changed.length > 0 || r.severity !== r.severity_default;
      return true;
    });
    const paramNodes = (r) => {
      const keys = Object.keys(r.params_default || {});
      if (!keys.length) return el("span", {class: "meta", text: "không có tham số"});
      return keys.slice(0, 4).map((k) => {
        const d0 = JSON.stringify(r.params_default[k]), v = JSON.stringify(r.params_effective[k]);
        return el("div", {class: "prm"}, k + ": ", r.params_changed.includes(k) ? el("span", {class: "chg", text: `${d0} → ${v}`}) : d0);
      }).concat(keys.length > 4 ? [el("div", {class: "meta", text: `+${keys.length - 4} tham số`})] : []);
    };
    fill($("rbody"), ...(rows.length ? rows.map((r) => {
      const sv = SEV[r.severity] || ["neu", r.severity];
      const ds = deptsOf(r.std);
      const st = [!r.implemented ? pill("neu sm", "Chưa cài code") : !r.enabled ? pill("warn sm", r.enabled_default ? "Đã tắt" : "Tắt") : pill("ok sm", "Đang chạy", "check")];
      if (r.params_changed.length) st.push(pill("edit sm", "Đã chỉnh tham số"));
      if (r.severity !== r.severity_default) st.push(pill("edit sm", `Mức ${r.severity_default} → ${r.severity}`));
      if (r.implemented && !r.measured) st.push(pill("neu sm", "Chưa đo"));
      if (r.fix_ops.length) st.push(pill("info sm", "Có thao tác sửa"));
      return el("tr", {class: "row" + (r.implemented && r.enabled ? "" : " off"), onclick: (e) => { if (!e.target.closest("button")) showExplain(r.id, r.std); }},
        el("td", {}, el("button", {class: "code", type: "button", "aria-label": "Mở chi tiết luật " + r.id, onclick: () => showExplain(r.id, r.std)}, r.id),
          el("div", {class: "mt6"}, pill(sv[0] + " sm", sv[1]))),
        el("td", {}, el("div", {class: "ttl", text: r.title}), el("div", {class: "meta", text: `${r.source || "—"} · ${r.std} ${r.version} · ${r.kind === "deterministic" ? "tất định" : r.kind} · rủi ro báo sai ${r.false_positive_risk}`})),
        el("td", {}, el("div", {class: "stack"}, ds.length ? ds.map((d) => pill("neu sm", d.name)) : el("span", {class: "none", text: "Chưa gắn"}))),
        el("td", {}, paramNodes(r)),
        el("td", {}, el("div", {class: "stack"}, st)));
    }) : [el("tr", {}, el("td", {colspan: "5"}, emptyBox("Không có luật nào khớp bộ lọc", "Thử bỏ bớt bộ lọc.")))]));
    $("rfoot").textContent = `Hiển thị ${rows.length} / ${all.length} luật. Bấm một luật để bật/tắt, đổi mức độ hoặc ngưỡng (dự án này hoặc mọi dự án trên máy). Luật chưa cài code ẩn mặc định.`;
    fill($("vhist"), ...Object.values(S.rules).map((d) => el("li", {}, el("time", {text: d.version}), el("span", {}, b(d.standard), " · ", d.description || `${d.counts.total} luật, ${d.counts.implemented} đã có code`))),
      S.session.profile ? el("li", {}, el("time", {text: S.session.profile.version}), el("span", {}, b(`Hồ sơ ${S.session.profile.name}`), ` · áp cho ${S.session.profile.standard}`)) : null);
  }

  function openRuleDrawer(r, std) {
    const d = $("drawer");
    const sv = SEV[r.severity] || ["neu", r.severity];
    const why = r.implemented
      ? "Chạy bằng code tất định trên mô hình bản vẽ. Đúng/sai do luật quyết, không do AI."
      : "Đã có trong chuẩn nhưng chưa có code nên chưa chạy và chưa chặn gì.";
    const params = Object.entries(r.rule_params || {});
    const close = el("button", {class: "iconbtn", type: "button", id: "drClose", "aria-label": "Đóng chi tiết luật", onclick: closeDrawer}, icon("x"));
    fill(d,
      el("div", {class: "dr-h"}, el("div", {class: "grow1"},
        el("div", {class: "bar-act"}, el("span", {class: "f-rule", text: r.id}), pill(sv[0], sv[1]), r.implemented ? pill("ok", "Đang chạy") : pill("neu", "Chưa cài code"), r.enabled ? null : pill("warn", "Tắt")),
        el("h2", {id: "drTitle", text: r.title})), close),
      el("div", {class: "dr-b"},
        el("h3", {text: "Luật nói gì"}), el("p", {text: why}),
        el("p", {}, el("button", {class: "btn-p btn-sm", type: "button", onclick: () => askAI(explainPrompt(r.id, r.title, std, ""))}, "Giải thích chuyên sâu bằng AI"),
          el("span", {class: "ai-note", text: " Trợ lý đọc bản vẽ đang mở, giải thích tầm quan trọng, hậu quả, cách sửa."})),
        kv([["Nguồn", r.source], ["Thuộc chuẩn", std], ["Loại", r.kind === "deterministic" ? "tất định" : r.kind], ["Rủi ro báo sai", r.false_positive_risk],
          ["Đọc gì", Array.isArray(r.reads) ? r.reads.join(", ") : r.reads], ["Hồ sơ công ty", r.profile ? `${r.profile.name} ${r.profile.version}` : "không áp"]]),
        el("h3", {text: "Tham số đang áp"}),
        params.length ? kv(params.map(([k, v]) => [k, JSON.stringify(v)])) : el("p", {text: "Không có tham số."}),
        r.implemented ? ruleEditor(r.id, std) : null,
        r.fix_ops && r.fix_ops.length ? [el("h3", {text: "Thao tác sửa có sẵn"}), el("p", {text: r.fix_ops.join(", ")})] : null,
        r.description_md ? [el("h3", {text: "Trong tài liệu chuẩn"}), el("pre", {text: r.description_md})] : null),
      el("div", {class: "dr-f"}, el("span", {class: "spacer"}), el("button", {class: "btn-s", type: "button", onclick: closeDrawer}, "Đóng")));
    d.classList.add("on");
    close.focus();
  }
  function closeDrawer() { const d = $("drawer"); d.classList.remove("on"); }

  // Sửa luật trên giao diện, không tài khoản: bật/tắt, mức độ, tham số; phạm vi dự án hoặc mọi dự án trên máy.
  function ruleRow(id, std) {
    const data = (S.rules || {})[std];
    return data ? data.rules.find((x) => x.id === id) : null;
  }
  async function saveRule(std, id, changes, scope, reset) {
    try {
      const res = await api(reset ? "/api/rules/reset" : "/api/rules/update", reset ? {standard: std, rule_id: id, scope} : {standard: std, rule_id: id, changes, scope});
      S.rules = S.rules || {};
      S.rules[std] = res.table;
      toast(reset ? `Đã đưa ${id} về mặc định. Lần quét sau áp dụng.` : `Đã lưu ${id}. Lần quét sau áp dụng.`);
      if (S.screen === "rules") renderRules();
      showExplain(id, std);
      return true;
    } catch (e) { fail(e); return false; }
  }
  function ruleEditor(id, std) {
    const row = ruleRow(id, std);
    if (!row) {
      if (S.session && S.session.standards) loadRulesQuiet().then(() => { if (ruleRow(id, std)) showExplain(id, std); });
      return el("p", {class: "meta", text: "Đang tải cài đặt luật…"});
    }
    const scopeSel = el("select", {"aria-label": "Phạm vi áp dụng"},
      el("option", {value: "project", text: "Dự án này"}), el("option", {value: "machine", text: "Mọi dự án trên máy"}));
    const en = el("input", {type: "checkbox", id: "reEn"}); en.checked = row.enabled;
    const sev = el("select", {id: "reSev", "aria-label": "Mức độ"}, ["E", "W", "I"].map((k) => el("option", {value: k, text: `${k} · ${SEV[k][1]}`})));
    sev.value = row.severity;
    const inputs = {};
    const prm = Object.entries(row.params_default || {}).map(([k, d0]) => {
      const cur = row.params_effective[k];
      let inp;
      if (typeof d0 === "boolean") { inp = el("input", {type: "checkbox"}); inp.checked = !!cur; }
      else if (typeof d0 === "number") { inp = el("input", {type: "number", step: "any", value: String(cur)}); }
      else if (Array.isArray(d0)) { inp = el("textarea", {rows: "2"}); inp.value = (cur || []).join("\n"); }
      else { inp = el("input", {type: "text", value: String(cur ?? "")}); }
      inputs[k] = [inp, d0];
      return el("label", {class: "prm"}, el("span", {}, k, el("span", {class: "meta", text: ` (mặc định ${JSON.stringify(d0)})`})), inp);
    });
    const read = () => {
      const params = {};
      for (const [k, [inp, d0]] of Object.entries(inputs)) {
        let v;
        if (typeof d0 === "boolean") v = inp.checked;
        else if (typeof d0 === "number") { v = Number(inp.value); if (Number.isInteger(d0) && !Number.isInteger(v)) v = Math.round(v); }
        else if (Array.isArray(d0)) v = inp.value.split(/\n/).map((s) => s.trim()).filter(Boolean);
        else v = inp.value;
        params[k] = JSON.stringify(v) === JSON.stringify(d0) ? null : v;
      }
      return {enabled: en.checked === row.enabled_default ? null : en.checked, severity: sev.value === row.severity_default ? null : sev.value, params};
    };
    const set = row.settings || {};
    const where = [Object.keys(set.machine || {}).length ? "máy" : "", Object.keys(set.project || {}).length ? "dự án" : ""].filter(Boolean).join(" + ");
    return [el("h3", {text: "Sửa luật"}),
      el("p", {class: "meta", text: "Không cần tài khoản. Lưu vào cài đặt của dự án hoặc của máy; tệp chuẩn gốc không đổi nên luôn về mặc định được. " + (where ? `Đang có cài đặt riêng ở: ${where}.` : "Đang dùng mặc định.")}),
      row.measured ? null : el("p", {class: "meta"}, pill("neu sm", "Chưa đo"), " Độ chính xác của luật chưa được đo trên bản vẽ thật."),
      el("div", {class: "re-grid"},
        el("label", {for: "reEn", class: "prm"}, en, " Bật luật"),
        el("label", {class: "prm"}, el("span", {text: "Mức độ"}), sev),
        ...prm,
        el("label", {class: "prm"}, el("span", {text: "Áp cho"}), scopeSel)),
      el("div", {class: "bar-act mt6"},
        el("button", {class: "btn-p btn-sm", type: "button", onclick: () => saveRule(std, id, read(), scopeSel.value, false)}, "Lưu"),
        el("button", {class: "btn-s btn-sm", type: "button", onclick: () => saveRule(std, id, null, scopeSel.value, true)}, "Về mặc định"))];
  }
  async function loadRulesQuiet() {
    if (S.rules) return;
    S.rules = {};
    try { for (const n of S.session.standards) S.rules[n] = await api("/api/rules?standard=" + encodeURIComponent(n)); } catch (e) { /* bỏ qua */ }
  }
  async function disableRule(id, std) {
    await loadRulesQuiet();
    await saveRule(std, id, {enabled: false}, "project", false);
  }

  // ---------- KẾT NỐI AI ----------
  const PROV_TITLE = {anthropic: "Anthropic", openai: "OpenAI", gemini: "Google Gemini", openrouter: "OpenRouter", ollama: "Ollama (trên máy)"};
  const ACCT = {business: "Doanh nghiệp (Gemini Enterprise / Google Cloud)", "api-key": "Khoá API (GEMINI_API_KEY)"};

  async function loadConnect() {
    try {
      const [ai] = await Promise.all([api("/api/ai/settings"), loadEngines(false)]);
      S.ai = ai;
    } catch (e) { fail(e); return; }
    renderConnect();
  }

  async function saveAi(patch, okMsg) {
    try {
      S.ai = await api("/api/ai/settings", patch);
      if (okMsg) toast(okMsg);
      await loadEngines(false);
      renderConnect();
      return true;
    } catch (e) { fail(e); return false; }
  }

  function cliCard(e) {
    const ai = S.ai;
    const cmd = ai.login_commands[e.name];
    const st = e.installed === false ? ["neu", "Chưa cài", "x"] : e.installed === null ? ["neu", "Chưa kiểm", "info"]
      : e.logged_in === true ? ["ok", "Đã đăng nhập", "check"] : e.logged_in === false ? ["warn", "Cần đăng nhập", "alert"] : ["info", "Đã cài, chưa rõ đăng nhập", "info"];
    const res = el("p", {class: "res"});
    const loginBtn = el("button", {class: "btn-s btn-sm", type: "button", disabled: e.installed !== true || (e.name === "agy-cli" && ai.agy_account !== "business"),
      onclick: async () => {
        try {
          const r = await api("/api/ai/cli/login", {engine: e.name});
          res.className = "res ok"; res.textContent = r.note;
        } catch (err) { res.className = "res bad"; res.textContent = err.message; }
      }}, icon("key"), "Đăng nhập");
    const extra = [];
    if (e.name === "codex-cli") {
      const cb = el("input", {type: "checkbox", id: "sw-codex"});
      cb.checked = !!ai.codex_experimental || !!(ai.cli_flags && ai.cli_flags.experimental);
      cb.disabled = !!(ai.cli_flags && ai.cli_flags.experimental);
      cb.addEventListener("change", async () => {
        if (cb.checked) {
          const ok = await confirmDialog({title: "Bật chế độ thử nghiệm cho Codex?",
            body: ["Điều khoản của OpenAI cho ứng dụng bên thứ ba khởi chạy Codex bằng đăng nhập ChatGPT của bạn CHƯA RÕ (không cho phép, cũng không cấm bằng văn bản).",
              "Chỉ bật khi bạn tự chấp nhận rủi ro. Với công ty, nên dùng khoá API của tổ chức (OpenAI) ở phần dưới."],
            yes: "Tôi hiểu, bật thử nghiệm", no: "Không bật"});
          if (!ok) { cb.checked = false; return; }
        }
        saveAi({codex_experimental: cb.checked}, cb.checked ? "Đã bật thử nghiệm Codex" : "Đã tắt thử nghiệm Codex");
      });
      extra.push(el("label", {class: "sw"}, cb, el("span", {text: "Bật chế độ thử nghiệm" + (cb.disabled ? " (đã bật bằng --experimental)" : "")})),
        el("div", {class: "warnbox", text: "Thử nghiệm: điều khoản dùng đăng nhập ChatGPT cho ứng dụng bên thứ ba chưa rõ."}));
    }
    if (e.name === "agy-cli") {
      const sel = el("select", {class: "sel", id: "sel-agy", "aria-label": "Loại tài khoản Antigravity"},
        el("option", {value: "", text: "— chọn loại tài khoản —"}),
        el("option", {value: "business", text: ACCT.business}), el("option", {value: "api-key", text: ACCT["api-key"]}),
        el("option", {value: "personal", text: "Tài khoản Google cá nhân"}));
      sel.value = ai.agy_account || "";
      const why = el("div", {class: "warnbox", hidden: true});
      sel.addEventListener("change", () => {
        if (sel.value === "personal") {
          why.hidden = false;
          why.textContent = "Không được phép: FAQ Antigravity nói bọc agy trong ứng dụng bên thứ ba không được hỗ trợ với tài khoản cá nhân; điều khoản mục 6 có thể dẫn tới khoá tài khoản. Hãy dùng tài khoản doanh nghiệp hoặc khoá API.";
          sel.value = ai.agy_account || "";
          return;
        }
        why.hidden = true;
        saveAi({agy_account: sel.value || null}, "Đã lưu loại tài khoản Antigravity");
      });
      extra.push(el("div", {class: "row"}, el("label", {class: "lbl", for: "sel-agy", text: "Loại tài khoản"}), sel), why);
      if (ai.agy_account === "api-key") extra.push(el("p", {class: "ds", text: "Khoá API: đặt GEMINI_API_KEY và \"modelProvider\": \"gemini\" trong cấu hình agy; không cần bấm Đăng nhập."}));
    }
    return el("div", {class: "card prov" + (e.available ? "" : " off")},
      el("div", {class: "hd"}, el("span", {class: "nm", text: e.title.replace(/ \(.*$/, "").replace(/ — .*/, "")}), pill(st[0], st[1], st[2])),
      el("p", {class: "ds"}, e.installed === false ? ai.install_docs[e.name] + " (chỉ hiện hướng dẫn; cad-guard không tải gì.)"
        : [e.version ? `Phiên bản: ${e.version}. ` : "", e.available ? "Dùng được trong trò chuyện." : e.reason, e.hint && !e.available ? " " + e.hint : ""]),
      el("p", {class: "ds"}, "Lệnh đăng nhập chính thức: ", el("code", {text: cmd}), ". Cửa sổ đăng nhập là của chính CLI; cad-guard không đọc đầu ra hay token."),
      extra,
      el("div", {class: "row"}, loginBtn, el("button", {class: "btn-s btn-sm", type: "button", onclick: () => loadEngines(true).then(renderConnect)}, icon("refresh"), "Kiểm lại")),
      res,
      el("details", {}, el("summary", {text: "Điều khoản (tóm tắt)"}), el("p", {class: "terms", text: e.terms})));
  }

  function apiCard(e) {
    const ai = S.ai;
    const name = e.name;
    const k = ai.keys[name];
    const isOR = name === "openrouter", isOllama = name === "ollama";
    const orOn = !!ai.allow_openrouter || !!(ai.cli_flags && ai.cli_flags.allow_openrouter);
    const res = el("p", {class: "res"});
    const show = (ok, msg) => { res.className = "res " + (ok ? "ok" : "bad"); res.textContent = msg; };
    const st = isOllama ? ["neu", "Cục bộ, không cần khoá", "info"] : !k ? ["neu", "—", null]
      : k.source === "keyring" ? ["ok", "Đã có khoá (lưu trong kho khoá hệ điều hành)", "check"]
        : k.source === "env" ? ["info", `Có khoá (biến môi trường ${k.env_var})`, "check"] : ["neu", "Chưa nhập khoá", "x"];
    const nodes = [el("div", {class: "hd"}, el("span", {class: "nm", text: PROV_TITLE[name] || e.title}), pill(st[0], st[1], st[2]))];
    if (isOR) {
      const cb = el("input", {type: "checkbox", id: "sw-or"});
      cb.checked = orOn;
      cb.disabled = !!(ai.cli_flags && ai.cli_flags.allow_openrouter);
      cb.addEventListener("change", async () => {
        if (cb.checked) {
          const ok = await confirmDialog({title: "Bật OpenRouter?", body: ["OpenRouter là bên trung gian thứ ba: dữ liệu (đã ẩn danh) đi qua OpenRouter rồi mới tới nhà cung cấp mô hình.", "Chỉ bật khi khách đã đồng ý."], yes: "Bật OpenRouter", no: "Không bật"});
          if (!ok) { cb.checked = false; return; }
        }
        saveAi({allow_openrouter: cb.checked}, cb.checked ? "Đã bật OpenRouter" : "Đã tắt OpenRouter");
      });
      nodes.push(el("label", {class: "sw"}, cb, el("span", {text: "Cho phép OpenRouter (bên trung gian thứ ba, mặc định tắt)"})));
    }
    if (isOllama) {
      const url = el("input", {type: "text", id: "ollama-url", autocomplete: "off", spellcheck: "false", "aria-label": "Địa chỉ Ollama"});
      url.value = ai.ollama_base_url || "";
      nodes.push(el("p", {class: "ds", text: "Chạy trên máy: dữ liệu không rời máy (Bậc L). Chất lượng gọi công cụ/tiếng Việt tuỳ mô hình."}),
        el("form", {class: "row", onsubmit: (ev) => { ev.preventDefault(); saveAi({ollama_base_url: url.value.trim()}, "Đã lưu địa chỉ Ollama"); }},
          el("label", {class: "lbl", for: "ollama-url", text: "Địa chỉ"}), url, el("button", {class: "btn-s btn-sm", type: "submit"}, "Lưu")));
    } else {
      const inp = el("input", {type: "password", id: "key-" + name, autocomplete: "off", spellcheck: "false", placeholder: k && k.has_key ? "Dán khoá mới để thay" : "Dán khoá API",
        "aria-label": "Khoá API " + (PROV_TITLE[name] || name), disabled: (isOR && !orOn) || !ai.keyring_available});
      const save = async (ev) => {
        ev.preventDefault();
        const v = inp.value;
        inp.value = "";
        if (!v.trim()) { show(false, "Chưa dán khoá."); return; }
        try { await api("/api/ai/key", {provider: name, key: v}); show(true, "Đã lưu khoá vào kho khoá hệ điều hành."); await refreshKeys(); }
        catch (err) { show(false, err.message); }
      };
      nodes.push(el("form", {class: "row", onsubmit: save}, inp, el("button", {class: "btn-s btn-sm", type: "submit", disabled: inp.disabled}, k && k.has_key ? "Đổi" : "Lưu")));
    }
    const model = el("input", {type: "text", id: "model-" + name, autocomplete: "off", spellcheck: "false", "aria-label": "Mô hình mặc định " + name,
      placeholder: e.needs_model ? "bắt buộc: tên mô hình" : "mặc định của nhà cung cấp"});
    model.value = (ai.models && ai.models[name]) || "";
    nodes.push(el("form", {class: "row", onsubmit: (ev) => { ev.preventDefault(); saveAi({models: {[name]: model.value.trim() || null}}, "Đã lưu mô hình mặc định"); }},
      el("label", {class: "lbl", for: model.id, text: "Mô hình"}), model, el("button", {class: "btn-s btn-sm", type: "submit"}, "Lưu")));
    const testBtn = el("button", {class: "btn-s btn-sm", type: "button", disabled: (isOR && !orOn) || (!isOllama && !(k && k.has_key)),
      onclick: async () => {
        testBtn.disabled = true; show(true, "Đang kiểm…");
        try { const r = await api("/api/ai/key/test", {provider: name}); show(r.ok, r.message); } catch (err) { show(false, err.message); }
        testBtn.disabled = false;
      }}, icon("check"), "Kiểm tra");
    const delBtn = !isOllama ? el("button", {class: "btn-s btn-sm", type: "button", disabled: !(k && k.source === "keyring"),
      onclick: async () => {
        const ok = await confirmDialog({title: `Xoá khoá ${PROV_TITLE[name]}?`, body: ["Khoá bị xoá khỏi kho khoá của hệ điều hành trên máy này."], yes: "Xoá khoá", danger: true});
        if (!ok) return;
        try { await api("/api/ai/key/delete", {provider: name}); show(true, "Đã xoá khoá."); await refreshKeys(); } catch (err) { show(false, err.message); }
      }}, icon("trash"), "Xoá") : null;
    nodes.push(el("div", {class: "row"}, testBtn, delBtn, el("span", {class: "muted small", text: "Kiểm tra: gọi danh sách mô hình, không tốn token."})), res);
    if (!e.available && e.reason && !isOR) nodes.push(el("p", {class: "ds", text: e.reason}));
    nodes.push(el("details", {}, el("summary", {text: "Điều khoản (tóm tắt)"}), el("p", {class: "terms", text: e.terms})));
    return el("div", {class: "card prov" + (e.available ? "" : " off")}, nodes);
  }

  async function refreshKeys() {
    try { S.ai = await api("/api/ai/settings"); } catch (_) { /* giữ */ }
    await loadEngines(false);
    renderConnect();
  }

  function renderConnect() {
    const ai = S.ai;
    if (!ai) return;
    fill($("cliCards"), ...S.engines.filter((e) => e.mode === "cli").map(cliCard));
    fill($("keyringNote"), ai.keyring_available ? null : el("div", {class: "callout warn"}, icon("alert"),
      el("div", {}, b("Máy này chưa có kho khoá cho cad-guard."), " Cài bằng ", el("code", {text: "pip install cadguard[keyring]"}),
        " rồi mở lại ứng dụng. cad-guard không bao giờ ghi khoá ra tệp, nên chưa có kho khoá thì không nhận khoá (biến môi trường vẫn dùng được).")));
    fill($("apiCards"), ...S.engines.filter((e) => e.mode === "api").map(apiCard));
    const def = $("defEngine");
    fill(def, el("option", {value: "", text: "Tự chọn engine đầu tiên dùng được"}), S.engines.map((e) => el("option", {value: e.name, text: e.title + (e.available ? "" : " (chưa dùng được)")})));
    def.value = ai.default_engine || "";
    const anon = S.session ? S.session.anonymize : true;
    const forced = S.session && S.session.anonymize_forced;
    const setPriv = async (v) => {
      try { const r = await api("/api/project/privacy", {anonymize: v}); S.session = r.session; renderSession(); renderConnect(); toast(v ? "Đã bật ẩn danh cho dự án này." : "Đã chuyển dự án sang chế độ nội bộ."); }
      catch (err) { fail(err); renderConnect(); }
    };
    const tier = (checked, t, d, extra, val) => el("label", {class: val === undefined || forced ? "dis" : ""}, el("input", {type: "radio", name: "tier", disabled: val === undefined || forced || !S.session || !S.session.project, checked: !!checked,
      onchange: val === undefined ? null : () => setPriv(val)}),
      el("span", {}, el("span", {class: "t"}, t, extra || null), el("br"), el("span", {class: "d", text: d})));
    fill($("tiers"),
      tier(false, "Bậc 0 · Không dùng AI", "Chỉ chạy bộ luật. Không cần làm gì: không chọn trợ lý / không gửi câu hỏi thì không có gì rời máy."),
      tier(!anon, "Nội bộ · Trợ lý thấy nội dung bản vẽ", "Mặc định cho công cụ nội bộ: trợ lý đọc tên layer, khối, chữ để hiểu, nhận xét, dịch. Kết quả luật vẫn do code tính.", pill("info pill-mid", "Mặc định"), false),
      tier(anon, "Ẩn danh Bậc 1 · Dự án có NDA", "Chỉ gửi kết quả đã ẩn danh (mã thay tên, che chữ). Lưu theo dự án; chức năng dịch bị khoá." + (forced ? " Đang bị ép bằng cờ dòng lệnh." : ""), null, true),
      tier(false, "Bậc L · Chỉ mô hình chạy trên máy", "Chọn Ollama làm trợ lý: dữ liệu không rời máy. Chất lượng thấp hơn mô hình lớn."));
    $("cap").value = String(ai.max_cost_usd);
    renderCost(null);
  }

  // ---------- CÔNG CỤ cho bản vẽ đang mở: Unicode, Dịch, Học template ----------
  function showPreview(pv) {
    S.preview = pv; S.applied = null; S.bulk = null;  // thao tác mới: bản xem trước mới luôn được hiện
    if (S.showDiscussion) S.showDiscussion();
    renderChg(); loadChangesets(); rightTab("chg");
  }
  async function toolUnicode() {
    if (!S.file) { toast("Mở một bản vẽ trước."); return; }
    S.lastPropose = toolUnicode;
    const b = busy("Đang chuẩn bị chuyển Unicode…", "Bản vẽ lớn mất khoảng 10–30 giây. Chưa ghi gì vào bản vẽ.");
    try { showPreview(await api("/api/changeset/propose", {file: S.file, standard: "design-hygiene-v0", ops: [{op: "convert_unicode"}]})); toast("Đã có bản xem trước ở tab Thay đổi."); }
    catch (e) { fail(e, "Chuyển Unicode"); }
    b.done();
  }
  async function toolTranslate(lang, btn, mode) {
    if (!S.file) { toast("Mở một bản vẽ trước."); return; }
    if (btn) btn.disabled = true;
    S.lastPropose = () => toolTranslate(lang, btn);
    const bz = busy("Đang dịch…", "AI đề xuất bản dịch, CAD Guard kiểm số/đơn vị/mã. Bản vẽ lớn có thể mất vài phút; muốn nhanh hãy chọn một tờ ở thanh Tờ rồi bấm Dịch.");
    try {
      const r = await api("/api/translate", {file: S.file, to: lang, sheet: S.sheetSel || null, mode: mode || "copy", engine: S.engine ? S.engine.name : null});
      const rp = r.report;
      const summary = `Ngôn ngữ gốc: ${rp.source_language.language_name}. Có bản dịch ${rp.translated}/${rp.strings} chuỗi, chưa dịch ${rp.untranslated}, cần xem ${rp.issue_count}.`;
      if (!rp.llm || rp.untranslated > rp.translated) {
        notice({kind: "err", title: rp.llm ? "Nhiều chuỗi chưa dịch được" : "Chưa có trợ lý AI nên chỉ dịch theo bảng thuật ngữ", msg: summary,
          hint: {why: rp.llm ? "Trợ lý AI trả lỗi hoặc quá giờ ở một số lượt (thường do hết lượt dùng hoặc mạng)." : "Dịch câu chữ tự do cần một trợ lý AI đã đăng nhập; bảng thuật ngữ chỉ có các từ cố định.",
            steps: ["Mở Kết nối AI, kiểm trợ lý đang chọn còn dùng được.", "Chọn một tờ ở thanh Tờ rồi bấm Dịch lại (ít chữ, nhanh, ít lỗi hơn).", "Bản xem trước vẫn dùng được: chuỗi chưa dịch giữ nguyên chữ gốc."],
            actions: [{id: "connect", label: "Mở Kết nối AI"}, {id: "changes", label: "Xem bản xem trước"}]}});
      } else toast(summary);
      if (r.preview) showPreview(r.preview);
    } catch (e) { fail(e, "Dịch bản vẽ"); }
    bz.done();
    if (btn) btn.disabled = false;
  }
  async function toolTemplate() {
    const sh = S.sheets;
    const i = sh && S.sheetSel ? sh.sheets.findIndex((s) => s.id === S.sheetSel) : -1;
    if (i < 0 || sh.sheets[i].kind !== "frame") { toast("Bấm chọn một tờ mẫu (khung tên đẹp nhất) ở thanh Tờ phía trên bản vẽ, rồi bấm lại Học template."); return; }
    const logo = window.prompt("Đường dẫn tệp logo công ty (PNG/JPG), để trống nếu không có:", "") || "";
    try {
      const r = await api("/api/template/learn", {file: S.file, sheet: i + 1, logo: logo.trim() || null});
      toast(`Đã học template '${r.template.name}' từ ${sh.sheets[i].name}. Chọn phòng 'Trình bày hồ sơ' rồi quét để kiểm trình bày.`);
    } catch (e) { fail(e); }
  }

  async function toolBulk() {
    if (!S.file) { toast("Mở một bản vẽ trước."); return; }
    S.lastPropose = toolBulk;
    const b = busy("Đang gom các lỗi tự sửa được…", "Chạy khô trong bộ nhớ, chưa ghi gì. Bản vẽ lớn mất khoảng 20–40 giây.");
    let p;
    try { p = await api("/api/fix/bulk/plan", {file: S.file, dept: S.dept && S.dept.id}); }
    catch (e) { b.done(); fail(e, "Sửa hàng loạt"); return; }
    b.done();
    S.bulk = p;
    if (S.showDiscussion) S.showDiscussion();
    rightTab("chg");
    renderBulk();
  }
  function renderBulk() {
    const p = S.bulk, list = $("chgList"), foot = $("chgFoot");
    if (!p) return;
    const pv = p.preview;
    const li = (o, extra) => el("li", {}, b(o.title), " ", el("span", {class: "f-rule", text: o.rule_id}), extra ? el("div", {class: "f-d", text: extra}) : null);
    fill(list,
      el("div", {class: "safe"}, icon("shield"), el("span", {}, "Sửa hàng loạt: ", b("luôn sao lưu bản vẽ gốc trước"), ", kết quả ghi ra ", b("tệp mới"), ", hoàn tác được.")),
      pv ? el("div", {class: "f-card"}, el("b", {text: pv.ok ? "Xem trước ĐẠT" : "Xem trước KHÔNG ĐẠT"}), el("div", {class: "f-d", text: pv.summary_vi}),
        el("div", {class: "f-d", text: pv.diff_summary_vi || ""})) : emptyBox("Không có lỗi nào sửa tự động được", "Các mục dưới đây cần người sửa trong CAD hoặc chọn giá trị."),
      p.picked.length ? [el("div", {class: "sub-h", text: `Sẽ sửa (${p.picked.length})`}), el("ol", {class: "bulk-list"}, p.picked.map((o) => li(o)))] : null,
      p.skipped.length ? [el("div", {class: "sub-h", text: `Chưa sửa tự động (${p.skipped.length}): làm tiếp ở tab Thay đổi`}), el("ul", {class: "bulk-list"}, p.skipped.map((o) => li(o, o.why_skipped)))] : null,
      p.manual.length ? [el("div", {class: "sub-h", text: `Cần người sửa trong CAD (${p.manual.length})`}), el("ul", {class: "bulk-list"}, p.manual.map((n) => el("li", {}, el("span", {class: "f-rule", text: n.rule_id}), " ", n.message)))] : null);
    const cb = el("input", {type: "checkbox", id: "bulkBackup", checked: true, disabled: true});
    fill(foot, el("label", {for: "bulkBackup", class: "safe"}, cb, el("span", {}, " Tạo bản sao lưu bản vẽ gốc vào thư mục ", b(".cadguard/backups"), " của dự án (bắt buộc).")),
      el("div", {class: "bar-act"},
        el("button", {class: "btn-p", type: "button", id: "bulkGo", disabled: !(pv && pv.ok), onclick: doBulk}, icon("check"), `Sao lưu & sửa ${p.picked.length} mục`),
        el("button", {class: "btn-s", type: "button", onclick: () => { S.bulk = null; foot.hidden = true; renderChg(); }}, "Bỏ"),
        el("button", {class: "btn-s", type: "button", title: "Làm như trên cho mọi bản vẽ gốc trong dự án, mỗi tệp một bản sao lưu và một tệp mới", onclick: doBulkFolder}, "Sửa cả thư mục…")));
    foot.hidden = false;
  }
  async function doBulkFolder() {
    const n = S.files.filter((f) => !f.is_output).length;
    const ok = await confirmDialog({title: `Sửa hàng loạt ${n} bản vẽ trong dự án?`,
      body: ["Với từng bản vẽ gốc: gom lỗi tự sửa được, chạy thử; ĐẠT thì sao lưu bản gốc vào .cadguard/backups rồi ghi TỆP MỚI. Không đạt thì bỏ qua tệp đó.",
        "Tệp gốc không bị ghi. Mỗi tệp mới hoàn tác được ở tab Thay đổi. Bản vẽ lớn mất khoảng 1 phút mỗi tệp; bạn vẫn dùng ứng dụng bình thường trong lúc chạy."],
      yes: "Sao lưu và sửa cả thư mục", no: "Chưa"});
    if (!ok) return;
    let job;
    try { job = await api("/api/fix/bulk/folder", {dept: S.dept && S.dept.id, confirm: true, backup: true}); }
    catch (e) { fail(e, "Sửa cả thư mục"); return; }
    const n0 = notice({kind: "busy", title: "Đang sửa cả thư mục…", msg: `0/${job.total} tệp`});
    const msg = n0.querySelector(".n-msg");
    while (job.state === "running") {
      await new Promise((r) => setTimeout(r, 2000));
      try { job = await api("/api/fix/bulk/folder/status", {job: job.id}); } catch (e) { n0.remove(); fail(e, "Sửa cả thư mục"); return; }
      if (msg) msg.textContent = `${job.done}/${job.total} tệp` + (job.current ? ` · đang làm ${job.current}` : "");
    }
    n0.remove();
    const fixed = job.results.filter((r) => r.status === "đã sửa").length;
    const errs = job.results.filter((r) => r.status === "lỗi").length;
    notice({kind: errs ? "err" : "ok", title: `Đã sửa ${fixed}/${job.total} bản vẽ`,
      msg: job.results.map((r) => `${r.file}: ${r.status}${r.output ? " → " + r.output : ""}${r.error ? " (" + r.error + ")" : ""}`).join(" · "),
      hint: errs ? {why: "Một số tệp gặp lỗi; tệp gốc của chúng không bị đổi.", steps: ["Mở từng tệp lỗi, bấm Sửa hàng loạt để xem chi tiết."], actions: []} : null});
    await loadFiles();
    loadChangesets();
  }
  async function doBulk() {
    const pv = S.bulk && S.bulk.preview;
    if (!pv) return;
    const ok = await confirmDialog({title: "Sao lưu và sửa hàng loạt?",
      body: [`1. Sao nguyên tệp “${pv.source.path}” vào .cadguard/backups (bản sao lưu).`, `2. Sửa ${S.bulk.picked.length} mục, ghi ra TỆP MỚI; tệp gốc giữ nguyên.`,
        "3. Mở lại tệp mới và kiểm; không đạt thì không tạo tệp."], yes: "Sao lưu và sửa", no: "Chưa"});
    if (!ok) return;
    $("bulkGo").disabled = true;
    const bz = busy("Đang sao lưu và sửa…", "Bản vẽ lớn mất khoảng 30–60 giây.");
    let r;
    try { r = await api("/api/fix/bulk/apply", {changeset_id: pv.changeset_id, confirm: true, backup: true}); }
    catch (e) { bz.done(); fail(e, "Sửa hàng loạt"); $("bulkGo").disabled = false; return; }
    bz.done();
    S.bulk = null;
    S.applied = {cid: r.changeset_id, output: r.output.path, source: r.source.path, validation: r.validation || {}};
    S.preview = null; S.suggest = null; S.cmp = "after";
    notice({kind: "ok", title: "Đã sửa hàng loạt", msg: `Tệp mới: ${r.output.path}. Bản sao lưu: ${r.backup.path}. Tệp gốc không đổi.`});
    await loadFiles();
    await recheckApplied();
    renderAll();
    loadChangesets();
  }

  // ---------- BẢN ĐỒ BẢN VẼ (đồ thị tri thức cg.drawing-graph/1 + cổng sẵn sàng) ----------
  function leaveMap() {
    S.mapOn = false;
    if (S.dept && S.dept.view === "scene") { load3d(S.file); return; }
    renderSheet();
  }
  const MAP_ACTIONS = {
    unicode: () => toolUnicode(),
    bulk: () => toolBulk(),
    open3d: (a) => load3d(S.file, a.item),
    construction: () => openConstruction(),
    sheet: (a) => {
      if (S.dept && S.dept.view === "scene") {  // phòng 3D không có màn tờ: chuyển sang phòng có xem tờ rồi mở đúng tờ
        const to = deptById("ky-thuat") || (S.session ? S.session.departments.find((x) => x.view !== "scene") : null);
        if (!to) { toast("Không có phòng xem tờ."); return; }
        S.mapOn = false; S.pendingSheet = a.sheet || null;
        setDept(to.id);
        toast("Đã chuyển sang phòng Kỹ thuật để xem tờ.");
        return;
      }
      leaveMap();
      if (a.sheet) selectSheet(a.sheet);
    },
  };
  async function loadMap(refresh) {
    if (!S.file) { toast("Mở một bản vẽ trước."); return; }
    const path = S.file;
    S.mapOn = true;
    if (S.v3d) { S.v3d.stop(); S.v3d = null; }
    $("viewTag").textContent = "Bản đồ bản vẽ"; $("viewTag").hidden = false;
    fill($("sheet"), emptyBox("Đang lập bản đồ bản vẽ…", "Đọc tờ, hình, hạng mục, khối, vật liệu (tất định, không dùng AI). Bản vẽ lớn mất vài giây."));
    let g;
    try { g = await api("/api/graph", {file: path, refresh: !!refresh}); }
    catch (e) { fail(e, "Lập bản đồ bản vẽ"); leaveMap(); return; }
    if (S.file !== path || !S.mapOn) return;
    renderMap(g);
  }
  function renderMap(g) {
    const s = g.stats;
    const label = {ok: "Đủ", partial: "Chưa đủ", blocked: "Chưa mở"};
    const actBtn = (a) => {
      if (!a || !MAP_ACTIONS[a.id]) return null;
      const txt = {unicode: "Chuyển Unicode", bulk: "Sửa hàng loạt", open3d: "Mở 3D hạng mục", sheet: "Xem tờ", construction: "Kết cấu xưởng"}[a.id];
      return el("button", {class: "btn-s btn-sm", type: "button", onclick: () => MAP_ACTIONS[a.id](a)}, txt);
    };
    const gates = g.gates.map((gt) => el("div", {class: "gate " + gt.status},
      el("div", {class: "g-head"}, b(gt.title), el("span", {class: "chip", text: `${label[gt.status]} ${gt.done}/${gt.total}`})),
      el("div", {class: "bar"}, (() => { const i = el("i"); i.style.width = `${gt.total ? Math.round(100 * gt.done / gt.total) : 0}%`; return i; })()),
      el("div", {class: "f-d", text: gt.note}),
      gt.task_count ? el("details", {open: gt.status !== "ok" && gt.task_count <= 6},
        el("summary", {text: `${gt.task_count} việc cần làm`}),
        gt.tasks.map((t) => el("div", {class: "task"},
          el("div", {}, b(t.title), " · ", t.where),
          el("div", {class: "t-why", text: "Vì sao: " + t.why}),
          el("div", {text: "Sửa nhanh: " + t.fix_here}),
          t.fix_cad && t.fix_cad !== "—" ? el("div", {text: "Trong AutoCAD: " + t.fix_cad}) : null,
          el("div", {class: "t-act"}, actBtn(t.action)))),
        gt.task_count > gt.tasks.length ? el("div", {class: "f-d", text: `… và ${gt.task_count - gt.tasks.length} việc khác.`}) : null) : null));
    const head = el("tr", {}, ["Hạng mục", "Tờ", "Mặt bằng / đứng / cắt", "Khối", "Vật liệu được ghi chú", "Dựng 3D", ""].map((t) => el("th", {text: t})));
    const rows = g.items.map((r) => el("tr", {},
      el("td", {}, b(r.name), el("div", {class: "f-d", text: r.id})), el("td", {text: String(r.sheets)}),
      el("td", {text: `${r.plans} / ${r.elevations} / ${r.sections}`}), el("td", {text: String(r.modules)}),
      el("td", {text: r.materials.join(", ") || "—"}), el("td", {text: r.status + (r.gaps ? ` (${r.gaps} phần thiếu)` : "")}),
      el("td", {}, el("button", {class: "btn-s btn-sm", type: "button", onclick: () => load3d(S.file, r.id)}, "Xem 3D"))));
    const mats = g.nodes.filter((n) => n.type === "material").sort((a, c) => c.attrs.mentions - a.attrs.mentions);
    fill($("sheet"), el("div", {class: "map"},
      el("div", {class: "bar-act"},
        el("button", {class: "btn-s btn-sm", type: "button", onclick: leaveMap}, "← Quay lại bản vẽ"),
        el("button", {class: "btn-s btn-sm", type: "button", onclick: () => loadMap(true)}, "Lập lại bản đồ"),
        el("button", {class: "btn-p btn-sm", type: "button", onclick: toolBulk}, "Sửa hàng loạt")),
      el("div", {class: "m-stats", text: `${s.sheets} tờ · ${s.views} hình (${s.views_typed_pct}% có loại; ${s.fragments} mảnh lẻ bỏ qua) · ${s.items} hạng mục · ${s.modules} khối · ${s.materials} loại vật liệu được ghi chú${g.cached ? " · bản đã lưu" : ""}`}),
      el("h3", {text: "Sẵn sàng cho các bước tiếp theo"}),
      el("div", {class: "gates"}, gates),
      el("h3", {text: "Đề xuất bổ sung (chờ bạn xác nhận)"}),
      el("div", {class: "f-d", text: "Phần code chưa đọc được: loại hình chưa tiêu đề, ghép mặt đứng–mặt bằng, vật liệu theo bộ phận, hạng mục không phải đồ nội thất. Mỗi đề xuất đã qua bước kiểm bằng chứng; chỉ thành dữ liệu khi bạn bấm Đồng ý. Bản vẽ không bị sửa."}),
      el("div", {class: "bar-act"},
        el("button", {class: "btn-s btn-sm", type: "button", onclick: () => suggestGraph(false)}, "Đề xuất bằng code"),
        el("button", {class: "btn-p btn-sm", type: "button", onclick: () => suggestGraph(true)}, "Đề xuất thêm bằng AI")),
      el("div", {id: "graphProps", class: "props"}, el("div", {class: "f-d", text: "Đang tải đề xuất…"})),
      el("h3", {text: "Hạng mục"}),
      el("table", {class: "tblmap"}, head, rows),
      mats.length ? [el("h3", {text: "Vật liệu được ghi chú"}), el("div", {class: "matchips"},
        mats.map((m) => el("span", {title: m.attrs.samples.join("\n")}, `${m.label} · ${m.attrs.mentions}`)))] : null,
      el("p", {class: "f-d", text: "Bản đồ do code đọc từ bản vẽ (tất định). Bước sau: trợ lý AI đề xuất phần code chưa đọc được (hình chưa có tiêu đề, ghép mặt đứng–mặt bằng, gán vật liệu) để bạn xác nhận."})));
    $("cvInfo").textContent = `Bản đồ · ${s.nodes} nút · ${s.edges} quan hệ`;
    loadProps();
  }

  // ---------- P2: đề xuất bổ sung bản đồ (code + AI, qua harness, người dùng xác nhận) ----------
  const PROP_KIND = {view_kind: "Loại hình", link_views: "Ghép mặt đứng – mặt bằng", item_material: "Vật liệu theo bộ phận",
    item_scope: "Phạm vi hạng mục", issue: "Nhận xét"};
  const VIEW_KIND_VI = {plan: "mặt bằng", elevation: "mặt đứng", section: "mặt cắt", detail: "chi tiết", ceiling: "mặt bằng trần", image: "ảnh/phối cảnh"};
  function propText(p) {
    const v = p.value;
    if (p.kind === "view_kind") return `${p.target_label} → ${VIEW_KIND_VI[v.kind] || v.kind}${v.title ? ` (“${v.title}”)` : ""}`;
    if (p.kind === "link_views") return `${p.target_label} ↔ ${p.value_label}`;
    if (p.kind === "item_material") return `${p.target_label}: ${v.component ? v.component + " — " : ""}${v.material}${v.spec ? ` (AI đọc: ${v.spec})` : ""}`;
    if (p.kind === "item_scope") return `${p.target_label}: ${v.scope === "architecture" ? "hồ sơ kiến trúc, bỏ khỏi dựng 3D/bóc tách" : "đồ nội thất"}`;
    return `${p.target_label}: ${v.message}`;
  }
  async function loadProps() {
    const box = $("graphProps");
    if (!box || !S.file) return;
    let r;
    try { r = await api("/api/graph/proposals", {file: S.file}); } catch (e) { fill(box, el("div", {class: "f-d", text: e.message})); return; }
    if (!$("graphProps")) return;
    S.props = r;
    renderProps();
  }
  function renderProps() {
    const box = $("graphProps"), r = S.props;
    if (!box || !r) return;
    if (!r.items.length) {
      fill(box, el("div", {class: "f-d", text: r.updated ? "Chưa có đề xuất nào cho bản vẽ này." : "Chưa chạy đề xuất. Bấm “Đề xuất bằng code” (vài giây, không dùng AI)."}));
      return;
    }
    const pend = r.items.filter((p) => p.status === "proposed");
    const sure = pend.filter((p) => p.confidence >= 0.75 && !(p.flags || []).length);
    const runs = (r.runs || []).filter((x) => !x.ok).map((x) => `${x.agent}: ${x.error}`);
    const card = (p) => el("div", {class: "prop " + p.status},
      el("div", {class: "p-head"}, b(PROP_KIND[p.kind] || p.kind),
        el("span", {class: "p-src", text: `${(p.sources || []).map((s) => s === "code" ? "code" : "AI").join(" + ")} · tin cậy ${Math.round(p.confidence * 100)}%` +
          (p.status === "confirmed" ? " · đã đồng ý" : p.status === "dismissed" ? " · đã bỏ" : "")})),
      el("div", {text: propText(p)}),
      el("div", {class: "f-d", text: "Vì sao: " + p.reason + ((p.evidence || []).length ? ` · ${p.evidence.length} bằng chứng trên bản vẽ` : "")}),
      (p.flags || []).map((f) => el("div", {class: "p-flag", text: "⚠ " + f})),
      p.status === "proposed" ? el("div", {class: "p-act"},
        el("button", {class: "btn-p btn-sm", type: "button", onclick: () => decideProp(p, true)}, "Đồng ý"),
        el("button", {class: "btn-s btn-sm", type: "button", onclick: () => decideProp(p, false)}, "Bỏ")) : null);
    fill(box,
      el("div", {class: "f-d", text: `${r.counts.proposed} chờ xác nhận · ${r.counts.confirmed} đã đồng ý · ${r.counts.dismissed} đã bỏ` +
        (r.rejected.length ? ` · ${r.rejected.length} đề xuất bị bước kiểm loại (thiếu bằng chứng)` : "")}),
      runs.length ? el("div", {class: "p-flag", text: "Một số lượt AI lỗi: " + runs.join("; ")}) : null,
      sure.length > 1 ? el("div", {class: "bar-act"}, el("button", {class: "btn-s btn-sm", type: "button", onclick: () => acceptMany(sure)},
        `Đồng ý ${sure.length} đề xuất chắc chắn (tin cậy ≥ 75%, không cảnh báo)`)) : null,
      pend.map(card), r.items.filter((p) => p.status !== "proposed").slice(0, 30).map(card));
  }
  async function decideProp(p, accept) {
    try { await api("/api/graph/decide", {file: S.file, id: p.id, accept}); }
    catch (e) { fail(e, accept ? "Đồng ý đề xuất" : "Bỏ đề xuất"); return; }
    toast(accept ? "Đã ghi vào bản đồ. Bản vẽ không bị sửa." : "Đã bỏ đề xuất.");
    await loadMap(false);
  }
  async function acceptMany(list) {
    const ok = await confirmDialog({title: `Đồng ý ${list.length} đề xuất?`,
      body: ["Chỉ các đề xuất tin cậy ≥ 75% và không có cảnh báo. Ghi vào bản đồ bản vẽ (và phần bổ sung 3D nếu là ghép hình); bản vẽ không bị sửa.",
        "Bỏ được từng mục sau (xoá trong .cadguard/graph nếu cần làm lại)."], yes: "Đồng ý tất cả", no: "Chưa"});
    if (!ok) return;
    const bz = busy(`Đang ghi ${list.length} đề xuất…`, "");
    for (const p of list) {
      try { await api("/api/graph/decide", {file: S.file, id: p.id, accept: true}); } catch (e) { bz.done(); fail(e, "Đồng ý đề xuất"); return; }
    }
    bz.done();
    toast(`Đã đồng ý ${list.length} đề xuất.`);
    await loadMap(false);
  }
  // Chuẩn hoá trước khi dựng 3D: code đọc mặt cắt, AI đọc kích thước/ghi chú; đề xuất qua kiểm bằng chứng, người xác nhận.
  async function runSceneAI(path, item, ai) {
    const bz = busy(ai ? "AI đang đọc bản vẽ của hạng mục…" : "Đang tìm số thiếu bằng code…",
      ai ? "Mỗi số AI đề xuất phải dẫn đúng kích thước/chữ trên bản vẽ; số không có bằng chứng bị loại." : "");
    let job;
    try { job = await api("/api/scene/ai", {file: path, item, ai, engine: S.engine ? S.engine.name : null}); } catch (e) { bz.done(); fail(e, "Chuẩn hoá dữ liệu 3D"); return; }
    if (job.note) toast(job.note);
    while (job.state === "running") {
      await new Promise((res) => setTimeout(res, 2000));
      try { job = await api("/api/scene/ai/status", {job: job.id}); } catch (e) { bz.done(); fail(e, "Chuẩn hoá dữ liệu 3D"); return; }
    }
    bz.done();
    if (job.state === "error") { fail(new Error(job.error || "Lỗi khi chuẩn hoá."), "Chuẩn hoá dữ liệu 3D"); return; }
    toast(job.accepted ? `Có ${job.accepted} đề xuất chờ bạn xác nhận ở đầu màn 3D.` :
      `Không tìm được số nào có bằng chứng trên bản vẽ${job.rejected.length ? ` (${job.rejected.length} đề xuất bị loại vì không có bằng chứng)` : ""}. Hãy nhập tay.`);
    if (S.file === path) load3d(path, item);
  }
  async function suggestGraph(ai) {
    if (!S.file) return;
    const path = S.file;
    const bz = busy(ai ? "Đang nhờ AI đề xuất…" : "Đang tìm đề xuất bằng code…",
      ai ? "4 việc: loại hình, ghép hình, vật liệu, soát nhất quán. Có thể mất vài phút; bạn vẫn dùng ứng dụng bình thường." : "");
    let job;
    try { job = await api("/api/graph/suggest", {file: path, ai, engine: S.engine ? S.engine.name : null}); } catch (e) { bz.done(); fail(e, "Đề xuất bổ sung"); return; }
    if (job.note) toast(job.note);
    const msg = document.querySelector("#notices .notice.busy .n-msg");
    while (job.state === "running") {
      await new Promise((res) => setTimeout(res, 2000));
      try { job = await api("/api/graph/suggest/status", {job: job.id}); } catch (e) { bz.done(); fail(e, "Đề xuất bổ sung"); return; }
      if (msg && job.agent) msg.textContent = `Đang làm: ${{views: "loại hình", links: "ghép hình", materials: "vật liệu", review: "soát nhất quán"}[job.agent] || job.agent}`;
    }
    bz.done();
    if (job.state === "error") { fail(new Error(job.error || "Lỗi khi đề xuất."), "Đề xuất bổ sung"); return; }
    if (S.file === path && S.mapOn) loadProps();
  }

  // ---------- GIẢI THÍCH CHUYÊN SÂU BẰNG AI ----------
  function askAI(text) {
    if (!S.engine) { toast("Chưa có trợ lý dùng được: vào Kết nối AI để đăng nhập một CLI hoặc nhập khoá API."); go("connect"); return; }
    closeDrawer();
    if (S.screen !== "work") go("work");
    if (S.showDiscussion) S.showDiscussion();
    rightTab("chat");
    $("inp").value = text;
    $("form").requestSubmit();
  }
  function explainPrompt(ruleId, title, std, details) {
    return `Giải thích CHUYÊN SÂU lỗi ${ruleId} (${title}, chuẩn ${std})` + (S.file ? ` trên bản vẽ đang mở ${S.file}` : "") + ` cho người làm thiết kế nội thất:\n`
      + "1) Luật này kiểm cái gì, vì sao quan trọng với thiết kế, sản xuất, thi công, in ấn và bàn giao hồ sơ.\n"
      + "2) Hậu quả cụ thể nếu bỏ qua (ví dụ thực tế trong xưởng/công trình).\n"
      + "3) Mức độ nghiêm trọng THỰC TẾ ở bản vẽ này: dùng công cụ audit/query_model để xem các chỗ bị lỗi"
      + (details ? ` (CAD Guard báo: ${details})` : "") + ".\n"
      + "4) Cách sửa từng bước trong AutoCAD, và thao tác sửa an toàn của CAD Guard nếu có.\n"
      + "5) Khi nào có thể chấp nhận bỏ qua lỗi này. Ghi rõ đâu là nhận xét của AI; kết luận đúng/sai vẫn theo kết quả luật.";
  }

  // ---------- CÀI ĐẶT (một lần mỗi máy) ----------
  async function loadSetup() {
    try { renderSetup((await api("/api/setup")).steps); } catch (e) { fail(e); }
  }
  function renderSetup(steps) {
    S.setupSteps = steps;
    fill($("setupList"), ...steps.map((s) => {
      const res = el("span", {class: "meta"});
      const run = async (remove, btn) => {
        btn.disabled = true;
        res.textContent = remove ? "Đang gỡ…" : "Đang cài…";
        try { renderSetup((await api("/api/setup/run", {step: s.id, remove})).steps); toast(remove ? `Đã gỡ: ${s.title}` : `Xong: ${s.title}`); }
        catch (e) { res.textContent = e.message; btn.disabled = false; }
      };
      const install = el("button", {class: "btn-p btn-sm", type: "button", disabled: s.available === false,
        onclick: (e) => run(false, e.currentTarget)}, s.done ? "Cài lại" : "Cài");
      const remove = el("button", {class: "btn-s btn-sm", type: "button", onclick: (e) => run(true, e.currentTarget)}, "Gỡ");
      return el("div", {class: "card setup-row" + (s.done ? " done" : "")},
        el("div", {class: "setup-ic"}, s.done ? pill("ok", "Đã xong", "check") : pill("warn", "Chưa", "alert")),
        el("div", {class: "grow1"}, el("div", {class: "ttl", text: s.title}), el("div", {class: "meta", text: s.why}),
          el("div", {class: "meta", text: s.detail}), res),
        el("div", {class: "bar-act"}, install, s.done ? remove : null));
    }));
  }

  // ---------- hồ sơ công ty ----------
  function openProfileModal() {
    const p = S.session.profile;
    $("mpCur").textContent = p ? `${p.name} ${p.version} (viết cho ${p.standard})` : "không dùng (mặc định của chuẩn)";
    $("mpPick").disabled = !S.session.dialog_available;
    $("mProfile").classList.add("on");
    $("mpClose").focus();
  }
  async function setProfile(path) {
    try {
      const r = await api("/api/project/profile", {path});
      S.session = r.session;
      $("mProfile").classList.remove("on");
      renderSession(); renderWorkSide(); S.rules = null;
      toast(path ? "Đã áp hồ sơ công ty cho dự án này" : "Đã bỏ hồ sơ công ty");
      if (S.file) openFile(S.file, {scan: Object.keys(S.audits).length > 0});
    } catch (e) { fail(e); }
  }

  // ---------- khởi động ----------
  async function boot() {
    initIcons(document);
    applyTheme(localStorage.getItem("cg-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
    $("themeBtn").addEventListener("click", () => applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark"));
    for (const t of $$(".nav [data-go]")) {
      t.addEventListener("click", () => go(t.dataset.go));
      t.addEventListener("keydown", (e) => {
        const tabs = $$(".nav [data-go]").filter((x) => !x.disabled);
        const i = tabs.indexOf(t);
        if (e.key === "ArrowRight") { e.preventDefault(); const n = tabs[(i + 1) % tabs.length]; n.focus(); go(n.dataset.go); }
        if (e.key === "ArrowLeft") { e.preventDefault(); const n = tabs[(i - 1 + tabs.length) % tabs.length]; n.focus(); go(n.dataset.go); }
      });
    }
    for (const t of $$("#rightTabs [role=tab]")) t.addEventListener("click", () => rightTab(t.dataset.p));
    $("projBtn").addEventListener("click", () => go("project"));
    $("deptBtn").addEventListener("click", toggleMenu("deptBtn", "deptMenu"));
    $("engineBtn").addEventListener("click", toggleMenu("engineBtn", "engineMenu"));
    document.addEventListener("click", closeMenus);
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      closeMenus();
      if ($("mProfile").classList.contains("on")) $("mProfile").classList.remove("on");
      else if ($("drawer").classList.contains("on")) closeDrawer();
    });
    $("pickBtn").addEventListener("click", pickProject);
    $("pathForm").addEventListener("submit", (e) => { e.preventDefault(); const v = $("pathIn").value.trim(); if (v) openProject(v); });
    $("stdLink").addEventListener("click", () => openCatalog({dept: S.dept.id}));
    $("profileBtn").addEventListener("click", openProfileModal);
    $("mpClose").addEventListener("click", () => $("mProfile").classList.remove("on"));
    $("mpNone").addEventListener("click", () => setProfile(null));
    $("mpPick").addEventListener("click", async () => {
      try {
        const r = await api("/api/project/profile/pick", {});
        if (r.unavailable) toast("Không mở được hộp thoại: hãy dán đường dẫn tệp.");
        else if (r.path) setProfile(r.path);
      } catch (e) { fail(e); }
    });
    $("mpForm").addEventListener("submit", (e) => { e.preventDefault(); const v = $("mpPath").value.trim(); if (v) setProfile(v); });
    $("scanAll").addEventListener("click", scanAll);
    $("layoutSel").addEventListener("change",()=>{S.layout=$("layoutSel").value;S.geo=null;S.view=null;loadGeometry(S.file);});
    const syncPanels=()=>{const hf=document.body.classList.contains("hide-files"),hd=document.body.classList.contains("hide-discussion");
      $("toggleFiles").textContent=hf?"Hiện tệp":"Ẩn tệp";$("toggleDiscussion").textContent=hd?"Hiện thảo luận":"Ẩn thảo luận";
      $("toggleDiscussion").classList.toggle("btn-attn",hd);
      try{localStorage.setItem("cg-hide",JSON.stringify({hf,hd}));}catch(e){}};
    const togglePanel=(kind)=>{const mobile=window.matchMedia("(max-width:900px)").matches;document.body.classList.toggle((mobile?"show-":"hide-")+kind);syncPanels();};
    S.showDiscussion=()=>{document.body.classList.remove("hide-discussion");document.body.classList.add("show-discussion");syncPanels();};
    try{const h=JSON.parse(localStorage.getItem("cg-hide")||"{}");if(h.hf)document.body.classList.add("hide-files");if(h.hd)document.body.classList.add("hide-discussion");}catch(e){}
    $("reopenDiscussion").addEventListener("click",()=>S.showDiscussion());
    $("toggleFiles").addEventListener("click",()=>togglePanel("files"));
    $("toggleDiscussion").addEventListener("click",()=>togglePanel("discussion"));
    $("closeFiles").addEventListener("click",()=>{document.body.classList.remove("show-files");document.body.classList.add("hide-files");syncPanels();});
    $("closeDiscussion").addEventListener("click",()=>{document.body.classList.remove("show-discussion");document.body.classList.add("hide-discussion");syncPanels();});
    syncPanels();
    $("toolUnicode").addEventListener("click", toolUnicode);
    $("toolTranslate").addEventListener("click", (e) => toolTranslate($("toolLang").value, e.currentTarget, $("toolMode") ? $("toolMode").value : "copy"));
    $("toolTemplate").addEventListener("click", toolTemplate);
    $("toolBulk").addEventListener("click", toolBulk);
    $("toolMap").addEventListener("click", () => loadMap(false));
    for (const x of $$("#t3Mode button")) x.addEventListener("click", () => { S.mode3d = x.dataset.v; seg("t3Mode", S.mode3d); if (S.r3d && !S.mapOn) render3d2(S.file, S.r3d, true); });
    for (const x of $$("#t3Body button")) x.addEventListener("click", () => setBody3d(x.dataset.v));
    $("t3Construct").addEventListener("click", () => openConstruction());
    $("t3Drafting").addEventListener("click", () => openDrafting());
    $("zoomIn").addEventListener("click", () => (S.v3d ? S.v3d.zoom(1.25) : zoomButton(0.8)));
    $("zoomOut").addEventListener("click", () => (S.v3d ? S.v3d.zoom(0.8) : zoomButton(1.25)));
    $("zoomFit").addEventListener("click", () => (S.v3d ? S.v3d.zoom(0) : zoomButton(0)));
    for (const btn of $$("#cmp button")) btn.addEventListener("click", () => {
      S.cmp = btn.dataset.v; S.view = null;
      for (const x of $$("#cmp button")) x.setAttribute("aria-pressed", x === btn ? "true" : "false");
      $("cvTitle").textContent = S.cmp === "after" && S.applied ? S.applied.output : S.file;
      renderSheet(); renderFiles();
    });
    $("ruleStd").addEventListener("change", renderRules);
    $("rq").addEventListener("input", () => { S.ruleFilter.q = $("rq").value; renderRules(); });
    $("fKind").addEventListener("change", () => { S.ruleFilter.kind = $("fKind").value; renderRules(); });
    $("fSev").addEventListener("change", () => { S.ruleFilter.sev = $("fSev").value; renderRules(); });
    $("form").addEventListener("submit", sendChat);
    $("stopBtn").addEventListener("click", stopChat);
    $("clearBtn").addEventListener("click", () => { if (!S.busy) introChat(); });
    $("refreshEngines").addEventListener("click", async () => { await loadEngines(true); renderConnect(); });
    $("defEngine").addEventListener("change", () => saveAi({default_engine: $("defEngine").value || null}, "Đã lưu trợ lý mặc định"));
    $("capForm").addEventListener("submit", (e) => {
      e.preventDefault();
      const v = Number(String($("cap").value).replace(",", ".").replace(/[^0-9.]/g, ""));
      if (!(v > 0)) { toast("Nhập số USD, ví dụ 2 hoặc 0,5."); return; }
      saveAi({max_cost_usd: v}, "Đã lưu giới hạn chi phí");
    });
    if (!TOKEN) { $("tokenBanner").hidden = false; return; }
    try { S.session = await api("/api/session"); } catch (e) { fail(e); return; }
    renderSession();
    renderWorkSide();
    renderFinds(); renderChg(); renderSheet();
    loadEngines(false);
    if (hasProject()) {
      await loadFiles();
      loadChangesets();
      if (PANEL) await openPanel(); else if (OPEN_DWG) await openFromAutocad(); else go("home");
    } else go("project");
  }

  async function openFromAutocad() {
    go("work");
    const dwg = (sessionStorage.getItem("cg-dwg") || "").toLowerCase();
    sessionStorage.removeItem("cg-dwg");
    const stem = (p) => p.split("/").pop().replace(/\.dxf$/i, "").toLowerCase();
    const hit = dwg ? S.files.find((f) => stem(f.path) === dwg && !f.is_output) : null;
    if (hit) await openFile(hit.path, {scan: true});
    else { go("home"); toast("Chưa thấy bản DXF của bản vẽ này. Trong AutoCAD gõ lại CADGUARD."); }
  }

  // Chế độ bảng neo trong AutoCAD: chỉ cột phải (Lỗi, Trợ lý, Hướng dẫn), tự mở DXF trùng tên bản vẽ đang mở.
  async function openPanel() {
    document.body.classList.add("acad-panel");
    go("work");
    const dwg = (sessionStorage.getItem("cg-dwg") || "").toLowerCase();
    const stem = (p) => p.split("/").pop().replace(/\.dxf$/i, "").toLowerCase();
    const hit = dwg ? S.files.find((f) => stem(f.path) === dwg && !f.is_output) : null;
    if (hit) { await openFile(hit.path, {scan: true, intro: false}); rightTab("finds"); }
    else {
      rightTab("help");
      toast(dwg ? "Chưa có DXF của bản vẽ này trong thư mục làm việc: gõ CGXUAT trong AutoCAD rồi mở lại bảng (CGBANG)."
        : "Mở một bản vẽ trong AutoCAD rồi gõ CGBANG.");
    }
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
