/* cad-guard app — JS thuần, không thư viện, không tài nguyên ngoài.
 * An toàn: mọi dữ liệu chèn bằng textContent/createElement (không chèn chuỗi HTML); mọi API gửi header X-CadGuard-Token.
 */
"use strict";
(() => {
  // ---------- biểu tượng (SVG dựng bằng DOM) ----------
  const ICONS = {
    shield: [["path", "M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"], ["path", "M9 12l2 2 4-4"]],
    pen: [["path", "M4 20h4L19 9l-4-4L4 16z"], ["path", "M13.5 6.5l4 4"]],
    list: [["path", "M9 6h11M9 12h11M9 18h11"], ["path", "M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2"]],
    plug: [["path", "M9 7V3M15 7V3M7 7h10v4a5 5 0 01-10 0zM12 16v5"]],
    lock: [["rect", {x: 5, y: 11, width: 14, height: 9, rx: 2}], ["path", "M8 11V8a4 4 0 018 0v3"]],
    doc: [["path", "M6 3h9l4 4v14H6z"], ["path", "M14 3v5h5M9 13h6M9 17h6"]],
    building: [["path", "M3 21h18M5 21V8l7-5 7 5v13M9 21v-6h6v6"]],
    moon: [["path", "M20 14.5A8 8 0 019.5 4 8 8 0 1020 14.5z"]],
    sun: [["circle", {cx: 12, cy: 12, r: 4}], ["path", "M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"]],
    search: [["circle", {cx: 11, cy: 11, r: 7}], ["path", "M21 21l-4.3-4.3"]],
    file: [["path", "M6 3h9l4 4v14H6z"], ["path", "M14 3v5h5"]],
    send: [["path", "M4 12l16-8-6 16-3-7z"]],
    stop: [["rect", {x: 6, y: 6, width: 12, height: 12, rx: 2}]],
    info: [["circle", {cx: 12, cy: 12, r: 9}], ["path", "M12 11v5M12 8h.01"]],
    check: [["path", "M5 12l5 5 9-10"]],
    x: [["path", "M6 6l12 12M18 6L6 18"]],
    warn: [["path", "M12 3l10 18H2z"], ["path", "M12 10v5M12 18h.01"]],
    refresh: [["path", "M20 11a8 8 0 10-2.3 5.7M20 4v7h-7"]],
    tool: [["path", "M14.7 6.3a4 4 0 00-5.4 5.4L4 17l3 3 5.3-5.3a4 4 0 005.4-5.4l-2.5 2.5-2.5-2.5z"]],
    undo: [["path", "M9 14L4 9l5-5"], ["path", "M4 9h10a6 6 0 010 12h-3"]],
  };
  // Không ghi URL nào trong mã: lấy namespace SVG từ phần tử <svg id="svgns"> do trình phân tích HTML tạo.
  const SVGNS = document.getElementById("svgns").namespaceURI;
  function icon(name) {
    const svg = document.createElementNS(SVGNS, "svg");
    svg.setAttribute("class", "i");
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
    append(node, kids);
    return node;
  }
  // replaceChildren() biến null thành chữ "null": luôn thay con qua append (bỏ null/false).
  function fill(node, ...kids) {
    node.replaceChildren();
    return append(node, kids);
  }
  function append(node, kids) {
    for (const kid of kids.flat(Infinity)) {
      if (kid === null || kid === undefined || kid === false) continue;
      node.appendChild(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return node;
  }
  const $ = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat("vi-VN");
  const fmt = (n) => nf.format(Number(n) || 0);
  const pill = (cls, text, ic) => el("span", {class: "pill " + cls}, ic ? icon(ic) : null, text);
  const SEV = {E: ["err", "Lỗi"], W: ["warn", "Cảnh báo"], I: ["info", "Thông tin"]};

  function toast(msg) {
    const t = $("toast");
    t.textContent = msg;
    t.classList.add("on");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => t.classList.remove("on"), 4200);
  }

  // ---------- mã phiên ----------
  const qs = new URLSearchParams(location.search);
  let TOKEN = qs.get("t") || sessionStorage.getItem("cg-token") || "";
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
    if (!r.ok) throw new Error((data && data.error) || ("Lỗi máy chủ " + r.status));
    return data;
  }

  // ---------- trạng thái ----------
  const S = {
    session: null, dept: null, standard: null, files: [], file: null, audit: null, scan: {},
    suggest: null, preview: null, changesets: [],
    mode: "audit", sevFilter: "", layerFilter: "", activeCluster: "",
    preview2d: null, scene3d: null, reviewNotes: [], handover: null,
    cam3d: "iso", xray3d: false, views3d: {front: "", side: "", top: ""}, supp3d: {},
    vp: {zoom: 1, panX: 0, panY: 0, dragging: false, startX: 0, startY: 0, focusBox: null},
    engines: [], groups: [], engine: null, history: [], run: null, busy: false,
    sessionUsage: {input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_write_tokens: 0, cost_usd: null},
  };

  // ---------- giao diện chung ----------
  function initIcons(root) {
    for (const span of root.querySelectorAll("[data-icon]")) {
      span.replaceWith(icon(span.getAttribute("data-icon")));
    }
  }

  function setupTablist(container, onSelect) {
    const tabs = [...container.querySelectorAll('[role="tab"]')];
    const select = (tab, focus) => {
      for (const t of tabs) {
        const on = t === tab;
        t.setAttribute("aria-selected", on ? "true" : "false");
        t.tabIndex = on ? 0 : -1;
      }
      if (focus) tab.focus();
      onSelect(tab);
    };
    for (const t of tabs) {
      t.addEventListener("click", () => select(t, false));
      t.addEventListener("keydown", (e) => {
        const i = tabs.indexOf(t);
        if (e.key === "ArrowRight") { e.preventDefault(); select(tabs[(i + 1) % tabs.length], true); }
        if (e.key === "ArrowLeft") { e.preventDefault(); select(tabs[(i - 1 + tabs.length) % tabs.length], true); }
      });
    }
    return (name) => {
      const t = tabs.find((x) => x.dataset.go === name || x.dataset.p === name || x.dataset.mode === name);
      if (t) select(t, false);
    };
  }

  function confirmDialog({title, body, yes, danger}) {
    return new Promise((resolve) => {
      const bg = $("modal");
      $("mTitle").textContent = title;
      const text = $("mText");
      fill(text, ...body.map((p) => (p instanceof Node ? p : el("p", {text: p}))));
      const y = $("mYes"), n = $("mNo");
      y.textContent = yes || "Đồng ý";
      y.className = danger ? "btn-d" : "btn-p";
      const prev = document.activeElement;
      bg.classList.add("on");
      y.focus();
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

  function openDrawer(title, nodes) {
    $("drTitle").textContent = title;
    fill($("drBody"), ...nodes);
    $("drawer").classList.add("on");
    $("drClose").focus();
  }
  function closeDrawer() { $("drawer").classList.remove("on"); }

  function kv(pairs) {
    const dl = el("dl", {class: "kv"});
    for (const [k, v] of pairs) {
      if (v === null || v === undefined || v === "") continue;
      dl.append(el("dt", {text: k}), el("dd", {}, v instanceof Node ? v : String(v)));
    }
    return dl;
  }

  // ---------- phiên, phòng, giao diện sáng/tối ----------
  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    fill($("themeBtn"), icon(t === "dark" ? "sun" : "moon"));
    localStorage.setItem("cg-theme", t);
  }

  function profileLabel(std) {
    const p = S.session && S.session.profile;
    if (!p) return "Mặc định của chuẩn (không có hồ sơ)";
    if (std && p.standard !== std) return `${p.name} ${p.version} (viết cho ${p.standard}, không áp cho chuẩn này)`;
    return `${p.name} ${p.version}`;
  }

  function renderSession() {
    const s = S.session;
    $("wsName").textContent = "Thư mục: " + s.workspace_name;
    $("dataMode").textContent = s.anonymize ? "Ẩn danh Bậc 1 (mặc định)" : "KHÔNG ẩn danh";
    $("dataChip").classList.toggle("danger", !s.anonymize);
    $("dataChip").title = s.anonymize
      ? "Trợ lý chỉ thấy mã băm (F_…, L_…), không thấy tên layer/tệp/chữ."
      : "Đã khởi động với --no-anonymize: trợ lý thấy tên layer/tệp/chữ thật.";
    if (!s.anonymize) {
      const b = $("anonBanner");
      b.textContent = "Cảnh báo: ẩn danh đã TẮT (khởi động với --no-anonymize). Trợ lý thấy tên layer, tên tệp và chữ thật trong bản vẽ. Chỉ dùng khi khách đã đồng ý; muốn bật lại thì khởi động lại không có cờ này.";
      b.hidden = false;
    }
    $("profileName").textContent = s.profile ? `${s.profile.name} ${s.profile.version}` : "không có";
    const sel = $("deptSel");
    fill(sel, ...s.departments.map((d) => el("option", {value: d.id, text: d.name})));
    const saved = sessionStorage.getItem("cg-dept");
    S.dept = s.departments.find((d) => d.id === saved) || s.departments.find((d) => d.id === s.default) || s.departments[0];
    sel.value = S.dept.id;
    fill($("ruleStd"), ...s.standards.map((n) => el("option", {value: n, text: n})));
    applyDept();
  }

  function applyDept() {
    const d = S.dept;
    S.standard = d.standard_ok ? d.standard : (S.session.standards[0] || null);
    $("stdName").textContent = S.standard + (d.standard_ok ? "" : " (chuẩn của phòng không có, dùng tạm)");
    $("stdProfile").textContent = profileLabel(S.standard);
    $("ruleStd").value = S.standard;
    S.scan = {};
    $("handoff").hidden = true;
    renderFiles();
    if (S.file) openFile(S.file);
    if (!$("s-rules").hidden && $("s-rules").classList.contains("on")) loadRules();
  }

  // ---------- danh sách bản vẽ ----------
  async function loadFiles() {
    try {
      const r = await api("/api/drawings");
      S.files = r.drawings;
      renderFiles();
    } catch (e) { toast(e.message); }
  }

  function countsPills(c) {
    if (!c) return [];
    const out = [];
    if (c.E) out.push(pill("err sm", `${c.E} E`));
    if (c.W) out.push(pill("warn sm", `${c.W} W`));
    if (c.I) out.push(pill("info sm", `${c.I} I`));
    if (!c.E && !c.W && !c.I) out.push(pill("ok sm", "Sạch"));
    return out;
  }

  function renderFiles() {
    const box = $("files");
    if (!S.files.length) {
      fill(box, el("div", {class: "empty"}, el("b", {text: "Chưa có tệp DXF"}), "Thư mục làm việc không có tệp .dxf nào."));
      return;
    }
    fill(box, ...S.files.map((f) => {
      const scan = S.scan[f.path];
      const b = el("button", {class: "file", type: "button", "aria-current": f.path === S.file ? "true" : "false", onclick: () => openFile(f.path)},
        el("span", {class: "n"}, icon("file"), f.path),
        el("span", {class: "m"},
          f.is_output ? pill("info sm", "bản mới (cad-guard)") : null,
          `${fmt(Math.round(f.size_bytes / 1024))} KB`,
          scan && scan.counts ? countsPills(scan.counts) : null,
          scan && scan.error ? pill("neu sm", "không đọc được") : null));
      return el("div", {role: "listitem"}, b);
    }));
  }

  async function scanAll() {
    const btn = $("scanAll");
    btn.disabled = true;
    try {
      const r = await api("/api/audit_all", {standard: S.standard});
      S.scan = {};
      for (const x of r.results) S.scan[x.path] = x;
      renderFiles();
      const next = S.session.departments.find((d) => d.id === S.dept.next);
      const h = $("handoff");
      fill(h, el("b", {text: `${r.ready}/${r.total} bản không có lỗi mức E`}), el("br"),
        next ? `Sẵn sàng bàn giao sang phòng ${next.name} (theo ${r.standard}).` : `Sẵn sàng xuất cho xưởng (theo ${r.standard}).`);
      h.hidden = false;
    } catch (e) { toast(e.message); }
    btn.disabled = false;
  }

  // ---------- một bản vẽ: kiểm + 2D + 3D + Review ----------
  let centerTab = null;
  let modeTab = null;
  async function openFile(path) {
    S.file = path;
    S.suggest = null;
    S.preview = null;
    S.preview2d = null;
    S.scene3d = null;
    S.activeCluster = "";
    S.layerFilter = "";
    S.vp.zoom = 1;
    S.vp.panX = 0;
    S.vp.panY = 0;
    S.vp.focusBox = null;
    renderFiles();
    $("cvTitle").textContent = path;
    $("cvInfo").hidden = true;
    fill($("finds"), el("div", {class: "empty"}, "Đang kiểm…"));
    fill($("chgList"), emptyChg());
    $("chgFoot").hidden = true;
    fill($("sumList"), );
    try {
      const [r, p2d, sc3d, rv] = await Promise.all([
        api("/api/audit", {file: path, standard: S.standard}),
        api("/api/preview", {file: path, standard: S.standard}).catch(() => null),
        api("/api/scene", {file: path, supplement: S.supp3d, views: S.views3d}).catch(() => null),
        api("/api/review/notes?file=" + encodeURIComponent(path)).catch(() => ({notes: []})),
      ]);
      if (S.file !== path) return;
      S.audit = r;
      S.preview2d = p2d;
      S.scene3d = sc3d;
      S.reviewNotes = (rv && rv.notes) || [];
      S.scan[path] = {path, counts: r.counts, ok: r.counts.E === 0};
      updateQuickStats(r.counts);
      populateLayerSelect(p2d);
      renderClusterBar();
      renderFiles();
      renderAudit();
      renderViewport();
      renderScenePane();
      renderReviewPane();
    } catch (e) {
      fill($("finds"), el("div", {class: "empty"}, el("b", {text: "Không kiểm được"}), e.message));
    }
    renderHistory();
  }

  function updateQuickStats(counts) {
    const c = counts || {E: 0, W: 0, I: 0};
    $("statE").textContent = String(c.E || 0);
    $("statW").textContent = String(c.W || 0);
    $("statI").textContent = String(c.I || 0);
  }

  function renderAudit() {
    const a = S.audit;
    if (!a) return;
    const total = a.counts.E + a.counts.W + a.counts.I;
    $("cntF").textContent = String(total);
    $("cntF").classList.toggle("hot", a.counts.E > 0);
    $("cvInfo").textContent = `${a.standard} ${a.version}` + (a.profile ? ` · hồ sơ ${a.profile.name} ${a.profile.version}` : "");
    $("cvInfo").hidden = false;
    const out = [];
    out.push(el("div", {class: "bar-act"}, countsPills(a.counts), el("span", {class: "muted", text: `${a.rules_run} luật đã chạy`}),
      S.sevFilter ? pill("info sm", `Đang lọc mức: ${S.sevFilter}`) : null,
      el("span", {class: "spacer"}),
      a.fixable_rules.length ? el("button", {class: "btn-p btn-sm", type: "button", onclick: () => { S.suggest = null; S.preview = null; switchStudioMode("diff"); }}, icon("tool"), "Đề xuất sửa") : null));
    if (a.records_capped) out.push(el("div", {class: "msg note", text: "Tệp rất lớn: danh sách đối tượng bị cắt ở trần bộ nhớ; số liệu tổng vẫn đủ."}));
    if (!total) out.push(el("div", {class: "empty"}, el("b", {text: "Không có phát hiện nào"}), `Bản vẽ đạt các luật đang chạy của ${a.standard}.`));
    for (const g of a.groups) {
      if (S.sevFilter && g.severity !== S.sevFilter) continue;
      if (!g.rules.length) continue;
      out.push(el("div", {class: "sev-h"}, pill(SEV[g.severity][0], `${g.label} (${g.severity})`), el("span", {class: "muted", text: `${g.rules.length} luật`})));
      for (const r of g.rules) {
        const fixable = a.fixable_rules.includes(r.rule_id);
        out.push(el("div", {class: "f-card"},
          el("div", {class: "f-top"},
            el("button", {class: "f-rule link", type: "button", title: "Giải thích luật", onclick: () => showExplain(r.rule_id, a.standard)}, r.rule_id),
            pill(SEV[r.severity][0] + " sm", SEV[r.severity][1]),
            r.count > 1 ? pill("neu sm", `${fmt(r.count)} chỗ`) : null,
            fixable ? pill("ok sm", "có thao tác sửa") : null,
            el("span", {class: "spacer"}),
            el("button", {class: "btn-s btn-xs", type: "button", onclick: () => focusRuleOnCanvas(r.rule_id)}, "Zoom vùng lỗi")),
          el("div", {class: "f-title", text: r.title}),
          el("div", {class: "f-d"}, el("ul", {}, r.items.map((it) => el("li", {},
            it.message,
            it.layer ? el("span", {class: "muted", text: ` · layer ${it.layer}`}) : null,
            it.layout ? el("span", {class: "muted", text: ` · ${it.layout}`}) : null,
            it.handles && it.handles.length ? el("span", {class: "muted", text: ` · handle ${it.handles.join(", ")}`}) : null)))),
          el("div", {class: "f-meta"},
            el("button", {class: "f-link", type: "button", onclick: () => showExplain(r.rule_id, a.standard)}, "Giải thích luật này"),
            " · ",
            el("button", {class: "f-link", type: "button", onclick: () => askAiAboutRule(r.rule_id, r.title)}, "Hỏi Trợ lý cách sửa"))));
      }
    }
    if (a.skipped.length) {
      out.push(el("details", {class: "skipped"}, el("summary", {text: `${a.skipped.length} luật bỏ qua (thiếu dữ liệu)`}),
        el("ul", {}, a.skipped.map((s) => el("li", {}, el("b", {text: s.rule_id + ": "}), s.reason)))));
    }
    if (a.truncated) out.push(el("div", {class: "muted", text: "Danh sách phát hiện đã bị cắt bớt."}));
    fill($("finds"), ...out);
  }

  async function showExplain(ruleId, standard) {
    try {
      const r = await api(`/api/explain?rule=${encodeURIComponent(ruleId)}&standard=${encodeURIComponent(standard)}`);
      const nodes = [
        el("p", {}, pill(SEV[r.severity] ? SEV[r.severity][0] : "neu", SEV[r.severity] ? SEV[r.severity][1] : r.severity), " ",
          r.enabled ? pill("ok", "Đang bật") : pill("neu", "Tắt"), " ", r.implemented ? null : pill("neu", "Chưa cài code")),
        kv([["Chuẩn", standard], ["Loại", r.kind === "deterministic" ? "tất định" : r.kind], ["Rủi ro báo sai", r.false_positive_risk],
          ["Đọc gì", r.reads], ["Nguồn", r.source], ["Hồ sơ công ty", r.profile ? `${r.profile.name} ${r.profile.version}` : "không áp"]]),
        el("h3", {text: "Tham số đang áp"}),
        el("pre", {class: "json", text: JSON.stringify(r.rule_params || {}, null, 2)}),
      ];
      if (r.fix_ops && r.fix_ops.length) nodes.push(el("h3", {text: "Thao tác sửa có sẵn"}), el("p", {text: r.fix_ops.join(", ")}));
      if (r.description_md) nodes.push(el("h3", {text: "Trong tài liệu chuẩn"}), el("pre", {class: "json", text: r.description_md}));
      openDrawer(`${r.id} — ${r.title}`, nodes);
    } catch (e) { toast(e.message); }
  }

  // ---------- đề xuất sửa -> xem trước -> áp dụng -> hoàn tác ----------
  function emptyChg() {
    return el("div", {class: "empty"}, el("b", {text: "Chưa có đề xuất"}),
      "Bấm “Đề xuất sửa” ở tab Lỗi: cad-guard gợi ý thao tác theo từ vựng cố định; bạn chọn, xem trước, rồi tự quyết áp dụng.");
  }

  async function loadSuggest() {
    if (!S.file) return;
    fill($("chgList"), el("div", {class: "empty"}, "Đang tìm thao tác phù hợp…"));
    $("chgFoot").hidden = true;
    try {
      S.suggest = await api("/api/changeset/suggest", {file: S.file, standard: S.standard});
      S.preview = null;
      renderSuggest();
    } catch (e) { fill($("chgList"), el("div", {class: "empty"}, el("b", {text: "Không gợi ý được"}), e.message)); }
  }

  function renderSuggest() {
    const s = S.suggest;
    const out = [el("div", {class: "safe"}, icon("shield"), el("span", {},
      "Thao tác chỉ nằm trong từ vựng cố định (không xoá đối tượng hình học). Xem trước là chạy khô trong bộ nhớ, ",
      el("b", {text: "chưa ghi gì"}), ". Áp dụng ghi ra tệp mới, tệp gốc giữ nguyên."))];
    if (!s.ops.length) out.push(el("div", {class: "empty"}, el("b", {text: "Không có thao tác sửa tự động"}), "Các phát hiện còn lại cần sửa trong phần mềm CAD."));
    for (const o of s.ops) {
      const cb = el("input", {type: "checkbox", id: "cb-" + o.key});
      cb.checked = !!o.checked;
      const choiceNodes = Object.entries(o.choices || {}).map(([field, values]) => {
        const sel = el("select", {class: "sel", id: `ch-${o.key}-${field}`, "data-field": field},
          el("option", {value: "", text: "— chọn —"}), values.map((v) => el("option", {value: v, text: v})));
        sel.value = o.op[field] || "";
        sel.addEventListener("change", () => { if (sel.value) cb.checked = true; });
        return el("div", {class: "choice"}, el("label", {for: sel.id, text: field === "to" ? "Đổi sang kiểu chữ" : "Layer đích"}), sel);
      });
      out.push(el("div", {class: "op", "data-key": o.key},
        el("label", {for: cb.id}, cb, el("span", {},
          el("span", {class: "f-top"}, el("b", {text: o.title}), pill("neu sm", o.rule_id), el("span", {class: "opname", text: o.op.op})),
          el("span", {class: "f-d", text: o.description}))),
        choiceNodes,
        el("details", {}, el("summary", {class: "muted", text: "Thao tác dạng JSON"}), el("pre", {text: JSON.stringify(o.op, null, 2)}))));
    }
    for (const n of s.notes) out.push(el("div", {class: "f-card"}, el("div", {class: "f-top"}, pill("neu sm", n.rule_id)), el("div", {class: "f-d", text: n.message})));
    fill($("chgList"), ...out);
    const foot = $("chgFoot");
    fill(foot, el("div", {class: "bar-act"},
      el("span", {class: "muted", text: s.protected_patterns ? `Hồ sơ công ty bảo vệ ${s.protected_patterns} mẫu layer: thao tác bỏ qua đối tượng trên các layer đó.` : "Không có layer bảo vệ từ hồ sơ công ty."}),
      el("span", {class: "spacer"}),
      el("button", {class: "btn-p", type: "button", id: "previewBtn", disabled: !s.ops.length, onclick: doPreview}, icon("search"), "Xem trước")));
    foot.hidden = false;
  }

  function selectedOps() {
    const ops = [];
    for (const o of S.suggest.ops) {
      if (!$("cb-" + o.key).checked) continue;
      const op = JSON.parse(JSON.stringify(o.op));
      for (const field of Object.keys(o.choices || {})) {
        const v = $(`ch-${o.key}-${field}`).value;
        if (!v) throw new Error(`Chọn giá trị cho “${o.title}” trước khi xem trước.`);
        op[field] = v;
      }
      ops.push(op);
    }
    if (!ops.length) throw new Error("Chưa chọn thao tác nào.");
    return ops;
  }

  async function doPreview() {
    let ops;
    try { ops = selectedOps(); } catch (e) { toast(e.message); return; }
    const btn = $("previewBtn");
    btn.disabled = true;
    try {
      S.preview = await api("/api/changeset/propose", {file: S.file, standard: S.standard, ops});
      renderPreview(S.preview, null);
      loadChangesets();
    } catch (e) { toast(e.message); btn.disabled = false; }
  }

  function rulesBlock(rules) {
    const list = (arr) => (arr && arr.length ? arr.join(", ") : "không");
    return kv([["Luật hết", list(rules.resolved)], ["Luật giảm", list(rules.improved)],
      ["Luật xuất hiện mới/tăng", list(rules.regressed)],
      ["Trước → sau", Object.keys(rules.before || {}).map((k) => `${k}: ${rules.before[k]} → ${(rules.after || {})[k] || 0}`).join("; ") || "—"]]);
  }

  function checksBlock(checks) {
    return el("ul", {class: "checks"}, (checks || []).map((c) => el("li", {class: c.ok ? "ok" : "bad"}, icon(c.ok ? "check" : "x"), el("span", {}, el("b", {text: c.id + ": "}), c.message))));
  }

  function renderPreview(pv, applied) {
    const ops = (pv.ops || []).map((r) => `${r.index}. ${r.op}: ${fmt(r.affected)} mục` + (r.skipped_protected ? ` (bỏ qua ${r.skipped_protected} trên layer bảo vệ)` : ""));
    const regressed = pv.rules_regressed || (pv.rules && pv.rules.rules_regressed) || 0;
    const card = el("div", {class: "pv " + (pv.ok && !regressed ? "result-ok" : "result-bad")},
      el("h3", {text: "Xem trước changeset " + pv.changeset_id}),
      el("p", {}, pv.ok && !regressed ? pill("ok", "Đạt kiểm", "check") : pill("err", "Không đạt", "x"), " ", el("span", {text: pv.summary_vi || ""})),
      kv([["Tệp gốc", pv.source && pv.source.path], ["Chuẩn", `${pv.standard} ${pv.standard_version || ""}`],
        ["Hồ sơ", pv.profile ? `${pv.profile.name} ${pv.profile.version}` : "không"], ["Thay đổi", pv.diff_summary_vi]]),
      el("div", {class: "f-d"}, el("b", {text: "Theo thao tác:"}), el("ul", {}, ops.map((t) => el("li", {text: t})))),
      pv.rules ? rulesBlock(pv.rules) : null,
      el("details", {}, el("summary", {class: "muted", text: "Các mục kiểm"}), checksBlock(pv.checks)));
    fill($("chgList"), card);
    const foot = $("chgFoot");
    if (applied) { renderApplied(applied, pv); return; }
    const canApply = pv.ok && !regressed;
    fill(foot, 
      el("div", {class: "safe"}, icon("shield"), el("span", {text: "Chưa ghi bản vẽ nào. Áp dụng sẽ ghi ra tệp mới cạnh tệp gốc, tự kiểm lại; không đạt thì không tạo tệp."})),
      el("div", {class: "bar-act"},
        el("button", {class: "btn-s", type: "button", onclick: () => { if (S.suggest) renderSuggest(); else fill($("chgList"), emptyChg()); }}, "Quay lại"),
        el("span", {class: "spacer"}),
        el("button", {class: "btn-p", type: "button", id: "applyBtn", disabled: !canApply, onclick: () => doApply(pv)}, icon("check"), "Áp dụng (ghi ra tệp mới)")));
    foot.hidden = false;
  }

  async function doApply(pv) {
    const ok = await confirmDialog({
      title: `Áp dụng changeset ${pv.changeset_id}?`,
      body: [`Ghi ra TỆP MỚI cạnh “${pv.source.path}” (tên có đuôi .cg-…dxf). Tệp gốc giữ nguyên, không bị ghi.`,
        "cad-guard kiểm lại tệp mới; không đạt thì không tạo tệp. Hoàn tác được (xoá tệp mới)."],
      yes: "Áp dụng",
    });
    if (!ok) return;
    const btn = $("applyBtn");
    if (btn) btn.disabled = true;
    try {
      const r = await api("/api/changeset/apply", {changeset_id: pv.changeset_id, confirm: true});
      toast("Đã ghi tệp mới: " + r.output.path);
      renderApplied(r, pv);
      loadFiles();
      loadChangesets();
    } catch (e) { toast(e.message); if (btn) btn.disabled = false; }
  }

  function renderApplied(r, pv) {
    const v = r.validation || {};
    const card = el("div", {class: "pv " + (v.ok ? "result-ok" : "result-bad")},
      el("h3", {text: "Đã áp dụng " + r.changeset_id}),
      kv([["Tệp mới", r.output && r.output.path], ["Mã băm tệp mới", r.output && r.output.sha256 ? r.output.sha256.slice(0, 16) + "…" : ""],
        ["Tệp gốc", (r.source && r.source.path) + " (không đổi)"], ["Thời điểm", r.applied_at], ["Kiểm lại", v.summary_vi]]),
      el("details", {open: true}, el("summary", {class: "muted", text: "Kết quả kiểm tệp ra (validate)"}), checksBlock(v.checks)));
    fill($("chgList"), card);
    const foot = $("chgFoot");
    fill(foot, el("div", {class: "bar-act"},
      r.output ? el("button", {class: "btn-s", type: "button", onclick: () => openFile(r.output.path)}, icon("file"), "Mở tệp mới") : null,
      el("span", {class: "spacer"}),
      el("button", {class: "btn-d", type: "button", id: "undoBtn", onclick: () => doUndo(r.changeset_id, r.output && r.output.path)}, icon("undo"), "Hoàn tác (xoá tệp mới)")));
    foot.hidden = false;
  }

  async function doUndo(cid, outPath) {
    const ok = await confirmDialog({
      title: `Hoàn tác ${cid}?`,
      body: [`Xoá tệp mới “${outPath || "?"}” do changeset này tạo. Tệp gốc không bị ảnh hưởng.`,
        "Nếu tệp mới đã bị sửa sau khi áp dụng (mã băm khác) thì cad-guard từ chối xoá."],
      yes: "Xoá tệp mới", danger: true,
    });
    if (!ok) return;
    try {
      const r = await api("/api/changeset/undo", {changeset_id: cid, confirm: true});
      toast("Đã hoàn tác: xoá " + r.removed);
      fill($("chgList"), el("div", {class: "pv result-ok"}, el("h3", {text: "Đã hoàn tác " + r.changeset_id}),
        kv([["Đã xoá", r.removed], ["Thời điểm", r.undone_at]])));
      $("chgFoot").hidden = true;
      if (S.file === outPath) S.file = null;
      await loadFiles();
      loadChangesets();
    } catch (e) { toast(e.message); }
  }

  // ---------- lịch sử changeset ----------
  async function loadChangesets() {
    try {
      const r = await api("/api/changesets");
      S.changesets = r.changesets;
      renderHistory();
    } catch (e) { /* im lặng: tab Thay đổi chỉ là phụ */ }
  }

  function renderHistory() {
    const pending = S.changesets.filter((c) => !c.applied).length;
    $("cntC").textContent = String(pending);
    const list = S.changesets;
    if (!list.length) {
      fill($("histList"), el("div", {class: "empty"}, el("b", {text: "Chưa có changeset"}), "Changeset bạn hoặc trợ lý đề xuất sẽ hiện ở đây."));
      return;
    }
    fill($("histList"), ...list.map((c) => {
      const a = c.applied;
      const state = !a ? pill("neu sm", "chưa áp dụng") : a.undone_at ? pill("neu sm", "đã hoàn tác") : pill("ok sm", "đã áp dụng");
      return el("div", {class: "f-card"},
        el("div", {class: "f-top"}, el("span", {class: "f-rule", text: c.id}), state,
          c.created_by === "agent" ? pill("info sm", "trợ lý đề xuất") : pill("neu sm", "bạn đề xuất"),
          c.ok === false ? pill("err sm", "xem trước không đạt") : null),
        el("div", {class: "f-d", text: `${c.source} · ${c.standard} · ${c.ops} thao tác · ${c.created_at}`}),
        c.summary_vi ? el("div", {class: "f-d", text: c.summary_vi}) : null,
        a && !a.undone_at && a.output ? el("div", {class: "f-d", text: "Tệp mới: " + a.output.path}) : null,
        el("div", {class: "bar-act mt8"},
          el("button", {class: "btn-s btn-sm", type: "button", onclick: () => openChangeset(c.id)}, "Xem trước / áp dụng"),
          a && !a.undone_at ? el("button", {class: "btn-s btn-sm", type: "button", onclick: () => doUndo(c.id, a.output && a.output.path)}, icon("undo"), "Hoàn tác") : null));
    }));
  }

  async function openChangeset(cid) {
    try {
      const c = await api("/api/changeset?id=" + encodeURIComponent(cid));
      if (!c.preview) { toast("Changeset không có phần xem trước."); return; }
      selectCenter("chg");
      if (c.applied && !c.applied.undone_at) {
        renderApplied({changeset_id: c.id, output: c.applied.output, source: c.source, applied_at: c.applied.applied_at, validation: c.applied.validation}, c.preview);
      } else if (c.applied) {
        renderPreview(c.preview, null);
        $("applyBtn").disabled = true;
        toast("Changeset này đã áp dụng rồi hoàn tác; muốn làm lại hãy đề xuất mới.");
      } else {
        renderPreview(c.preview, null);
      }
    } catch (e) { toast(e.message); }
  }

  // ---------- tóm tắt mô hình ----------
  async function loadSummary() {
    if (!S.file) { fill($("sumList"), el("div", {class: "empty", text: "Chọn một bản vẽ."})); return; }
    try {
      const r = await api("/api/summary", {file: S.file});
      const obj = (o) => Object.entries(o || {}).map(([k, v]) => `${k}: ${fmt(v)}`).join(" · ") || "—";
      fill($("sumList"), el("div", {class: "pv"}, el("h3", {text: "Tóm tắt mô hình bản vẽ"}),
        kv([["Phiên bản DXF", r.dxf_version], ["Đơn vị (INSUNITS)", r.insunits], ["Số layer", fmt(r.layer_count)], ["Số khối dùng", fmt(r.block_count)],
          ["Đối tượng theo loại", obj(r.entities_by_type)], ["Đối tượng theo không gian", obj(r.entities_by_space)],
          ["Kiểu chữ dùng", obj(r.text_styles)],
          ["Layout", (r.layouts || []).map((l) => `${l.name} (${l.paper_w_mm || "?"}×${l.paper_h_mm || "?"} mm, ${l.viewport_count} khung nhìn)`).join("; ") || "—"]]),
        r.truncated ? el("p", {class: "muted", text: "Danh sách đã bị cắt bớt."}) : null));
    } catch (e) { fill($("sumList"), el("div", {class: "empty", text: e.message})); }
  }

  function selectCenter(name) { centerTab(name); }

  // ---------- trợ lý ----------
  async function loadEngines(refresh) {
    try {
      const r = await api("/api/engines" + (refresh ? "?refresh=1" : ""));
      S.engines = r.engines;
      S.groups = r.groups;
      renderEngineSelect();
      renderConnect();
      if (refresh) $("refreshNote").textContent = "Đã kiểm lại lúc " + new Date().toLocaleTimeString("vi-VN");
    } catch (e) { toast(e.message); }
  }

  function renderEngineSelect() {
    const sel = $("engineSel");
    const saved = sessionStorage.getItem("cg-engine");
    fill(sel, ...S.groups.map((g) => el("optgroup", {label: g.title},
      S.engines.filter((e) => e.mode === g.mode).map((e) => el("option", {value: e.name, disabled: !e.available,
        text: e.title + (e.available ? "" : " — " + e.reason)})))));
    const pick = S.engines.find((e) => e.name === saved && e.available) || S.engines.find((e) => e.available);
    if (pick) sel.value = pick.name;
    S.engine = pick || null;
    renderEngineCard();
  }

  function engineCost(e) {
    if (!e) return "";
    if (e.mode === "cli") return "Chi phí: tính vào gói/tài khoản CLI của bạn. Số USD hiện ở đây là ước tính của CLI, với gói thuê bao không phải tiền bị trừ.";
    if (e.name === "ollama") return "Chi phí: không có cước API (mô hình chạy trên máy).";
    return "Chi phí: tính theo token vào tài khoản API của bạn; cad-guard ước tính khi biết giá.";
  }

  function engineDataFlow(e) {
    const anon = S.session && S.session.anonymize;
    const what = anon ? "Trợ lý chỉ thấy kết quả công cụ đã ẩn danh (mã F_…, L_…), không thấy tệp DXF." : "Ẩn danh đã TẮT: trợ lý thấy tên thật.";
    if (!e) return what;
    if (e.name === "ollama") return what + " Dữ liệu ở lại máy.";
    if (e.mode === "cli") return what + " Đi tới nhà cung cấp của CLI theo điều khoản tài khoản của bạn.";
    if (e.default_off) return what + " Đi qua bên trung gian thứ ba rồi tới nhà cung cấp mô hình.";
    return what + " Đi thẳng tới nhà cung cấp API đã chọn.";
  }

  function renderEngineCard() {
    const e = S.engine;
    const card = $("engCard");
    if (!e) {
      fill(card, el("div", {class: "t"}, pill("neu", "Chưa có trợ lý dùng được")),
        el("div", {text: "Cài và đăng nhập một CLI (vd. Claude Code), hoặc đặt khoá API bằng `cadguard keys set …`, rồi vào tab Kết nối AI bấm Kiểm lại."}));
      $("modelRow").hidden = true;
      $("chatHead").textContent = "Chưa chọn trợ lý";
      $("sendBtn").disabled = true;
      return;
    }
    $("sendBtn").disabled = S.busy;
    fill(card, 
      el("div", {class: "t"}, e.mode === "cli" ? pill("info sm", "Hạn mức tài khoản (CLI)") : pill("ok sm", "API — khoá của bạn"),
        e.experimental ? pill("warn sm", "thử nghiệm") : null, el("span", {text: e.status})),
      el("div", {text: engineCost(e)}),
      el("div", {class: "terms", text: "Điều khoản: " + e.terms}));
    const mi = $("modelIn");
    $("modelRow").hidden = false;
    mi.placeholder = e.mode === "cli" ? "mặc định của CLI" : (e.needs_model ? "bắt buộc: tên mô hình" : "mặc định");
    mi.value = sessionStorage.getItem("cg-model-" + e.name) || e.model || "";
    fill($("chatHead"), icon("lock"), el("span", {text: engineDataFlow(e)}));
  }

  function usageText(u) {
    if (!u) return "";
    const cost = u.cost_usd === null || u.cost_usd === undefined ? "chi phí không rõ"
      : `~${Number(u.cost_usd).toLocaleString("vi-VN", {maximumFractionDigits: 4})} USD` + (u.cost_estimated ? " (ước tính)" : "");
    return `${fmt(u.input_tokens)} token vào · ${fmt(u.output_tokens)} ra` +
      (u.cache_read_tokens ? ` · ${fmt(u.cache_read_tokens)} đọc cache` : "") + ` · ${cost}`;
  }
  function addUsage(total, u) {
    for (const k of ["input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"]) total[k] = (total[k] || 0) + (u[k] || 0);
    if (u.cost_usd !== null && u.cost_usd !== undefined) total.cost_usd = (total.cost_usd || 0) + u.cost_usd;
    total.cost_estimated = total.cost_estimated || u.cost_estimated;
  }
  function renderCost(turn) {
    const parts = [];
    if (turn) parts.push("Lượt này: " + usageText(turn));
    parts.push("Cả phiên: " + usageText(S.sessionUsage));
    if (S.engine && S.engine.mode === "cli") parts.push("(gói thuê bao: số USD là ước tính, không phải tiền bị trừ)");
    $("costLine").textContent = parts.join(" — ");
  }

  function logAdd(node) {
    const log = $("log");
    log.appendChild(node);
    log.scrollTop = log.scrollHeight;
    return node;
  }

  async function sendChat(ev) {
    ev.preventDefault();
    if (S.busy) return;
    const text = $("inp").value.trim();
    if (!text) return;
    const e = S.engine;
    if (!e) { toast("Chưa có trợ lý dùng được."); return; }
    const model = $("modelIn").value.trim();
    if (e.needs_model && !model) { toast("Engine này cần tên mô hình."); $("modelIn").focus(); return; }
    if (model) sessionStorage.setItem("cg-model-" + e.name, model);
    $("inp").value = "";
    S.history.push({role: "user", content: text});
    logAdd(el("div", {class: "msg me", text}));
    const ai = el("div", {class: "msg ai"});
    const typing = logAdd(el("div", {class: "typing", text: "Trợ lý đang trả lời…"}));
    let aiAdded = false;
    const tools = {};
    const turn = {input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_write_tokens: 0, cost_usd: null};
    let answer = "";
    let proposed = false;
    setBusy(true);
    const ensureAi = () => { if (!aiAdded) { typing.before(ai); aiAdded = true; } };
    const handle = (m) => {
      switch (m.type) {
        case "start": S.run = m.run_id; break;
        case "text": ensureAi(); ai.textContent += m.text || ""; break;
        case "tool_call": {
          const pre = el("pre", {text: "Tham số: " + JSON.stringify(m.arguments, null, 2)});
          const st = el("span", {class: "muted", text: "đang chạy…"});
          const d = el("details", {class: "tool"}, el("summary", {}, icon("tool"), el("span", {text: "Công cụ " + m.name}), st), pre);
          tools[m.id || m.name] = {d, st, pre};
          typing.before(d);
          break;
        }
        case "tool_result": {
          const t = tools[m.id || m.name];
          const txt = "Kết quả: " + (m.content || "");
          if (t) { t.st.textContent = m.is_error ? "lỗi" : "xong"; t.pre.textContent += "\n\n" + txt; }
          else typing.before(el("details", {class: "tool"}, el("summary", {}, icon("tool"), "Kết quả " + (m.name || "")), el("pre", {text: txt})));
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
        body: JSON.stringify({engine: e.name, model: model || null, messages: S.history, standard: S.standard,
          allow_propose: $("allowPropose").checked})});
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
    } catch (err) {
      typing.before(el("div", {class: "msg err", text: err.message}));
    }
    typing.remove();
    addUsage(S.sessionUsage, turn);
    renderCost(turn);
    if (answer) S.history.push({role: "assistant", content: answer});
    else S.history.pop();
    if (proposed) {
      logAdd(el("div", {class: "msg note", text: "Trợ lý đã đề xuất một changeset (chưa ghi bản vẽ). Xem ở tab “Thay đổi”, kiểm phần xem trước rồi tự quyết áp dụng."}));
      loadChangesets();
    }
    S.run = null;
    setBusy(false);
  }

  function setBusy(b) {
    S.busy = b;
    $("sendBtn").disabled = b || !S.engine;
    $("stopBtn").hidden = !b;
    $("engineSel").disabled = b;
    if (b) $("stopBtn").focus(); else $("inp").focus();
  }

  async function stopChat() {
    if (!S.run) return;
    $("stopBtn").disabled = true;
    try { await api("/api/chat/stop", {run_id: S.run}); } catch (e) { toast(e.message); }
    $("stopBtn").disabled = false;
  }

  // ---------- Kết nối AI ----------
  function renderConnect() {
    const card = (e) => el("div", {class: "card prov" + (e.available ? "" : " off")},
      el("div", {class: "hd"}, el("span", {class: "nm", text: e.title}),
        e.available ? pill("ok", "Dùng được", "check") : pill("neu", e.reason)),
      el("p", {class: "ds"}, el("b", {text: "Trạng thái: "}), e.status || "—", e.model ? ` · mô hình mặc định: ${e.model}` : (e.mode === "api" ? " · chưa đặt mô hình mặc định" : "")),
      e.hint ? el("p", {class: "ds"}, el("b", {text: "Cách bật: "}), e.hint) : null,
      e.mode === "api" && e.name !== "ollama" ? el("p", {class: "ds"}, "Khoá: ", el("code", {text: `cadguard keys set ${e.name}`}), " trong terminal (không nhập ở đây).") : null,
      el("p", {class: "terms", text: "Điều khoản: " + e.terms}));
    fill($("cliCards"), ...S.engines.filter((e) => e.mode === "cli").map(card));
    fill($("apiCards"), ...S.engines.filter((e) => e.mode !== "cli").map(card));
    const anon = S.session.anonymize;
    fill($("dataCard"), 
      el("p", {}, anon ? pill("ok", "Ẩn danh Bậc 1 (mặc định)", "lock") : pill("err", "KHÔNG ẩn danh (--no-anonymize)", "warn")),
      el("p", {text: anon
        ? "Trợ lý chỉ thấy kết quả công cụ đã ẩn danh: mã phiên F_… (tệp), L_… (layer), B_… (khối), S_… (kiểu chữ), Y_… (layout); chữ trong bản vẽ bị che. Không gửi tệp DXF, không gửi đường dẫn tuyệt đối."
        : "Ẩn danh đã tắt bằng cờ dòng lệnh: trợ lý thấy tên layer, tên tệp và chữ thật. Muốn bật lại: dừng và chạy lại `cadguard app` không có --no-anonymize."}),
      el("p", {text: "Lịch sử trò chuyện chỉ nằm trong trang này (bộ nhớ trình duyệt), không ghi ra đĩa. Màn hình người dùng (danh sách lỗi, xem trước) dùng tên thật vì không rời máy."}));
  }

  // ---------- Luật áp dụng ----------
  let RULES = null;
  async function loadRules() {
    const std = $("ruleStd").value || S.standard;
    try {
      RULES = await api("/api/rules?standard=" + encodeURIComponent(std));
      renderRules();
    } catch (e) { toast(e.message); }
  }

  function paramText(defs, eff, changed) {
    const keys = Object.keys(defs || {});
    if (!keys.length) return [el("span", {class: "muted", text: "không có tham số"})];
    return keys.map((k) => {
      const d = JSON.stringify(defs[k]);
      const v = JSON.stringify(eff[k]);
      return el("div", {class: "prm"}, k + ": ", changed.includes(k) ? el("span", {class: "chg", text: `${d} → ${v}`}) : d);
    });
  }

  function renderRules() {
    const r = RULES;
    fill($("srcline"), 
      el("span", {}, "Chuẩn ", el("code", {text: `${r.standard} ${r.version}`})),
      el("span", {}, "Hồ sơ công ty: ", r.profile ? el("b", {text: `${r.profile.name} ${r.profile.version}`}) : "không áp"),
      r.profile_note ? pill("warn", r.profile_note) : null,
      r.globals_changed.length ? el("span", {}, "Tham số chung đã chỉnh: ", r.globals_changed.join(", ")) : null);
    const c = r.counts;
    const cov = (nm, big, sub) => el("div", {class: "cov"}, el("div", {class: "nm", text: nm}), el("div", {class: "big", text: String(big)}), el("div", {class: "sub", text: sub}));
    fill($("covs"), cov("Luật trong chuẩn", c.total, `${c.implemented} đã có code`), cov("Đang chạy", c.running, "đã cài và đang bật"),
      cov("Tắt bởi hồ sơ", c.disabled_by_profile, "hồ sơ công ty tắt"), cov("Tham số đã chỉnh", c.params_changed, "khác mặc định của chuẩn"));
    const q = $("rq").value.trim().toLowerCase();
    const k = $("fKind").value;
    const rows = r.rules.filter((x) => {
      if (q && !(x.id.toLowerCase().includes(q) || x.title.toLowerCase().includes(q))) return false;
      if (k === "run") return x.implemented && x.enabled;
      if (k === "off") return x.enabled_default && !x.enabled;
      if (k === "changed") return x.params_changed.length > 0;
      if (k === "todo") return !x.implemented;
      return true;
    });
    fill($("rbody"), ...rows.map((x) => {
      const state = !x.implemented ? pill("neu sm", "Chưa cài code") : !x.enabled ? pill("warn sm", x.enabled_default ? "Tắt bởi hồ sơ" : "Tắt") : pill("ok sm", "Đang chạy");
      return el("tr", {class: x.implemented && x.enabled ? "" : "off"},
        el("td", {}, el("button", {class: "code", type: "button", onclick: () => showExplain(x.id, r.standard)}, x.id)),
        el("td", {}, el("div", {class: "ttl", text: x.title}),
          el("div", {class: "meta", text: [x.kind === "deterministic" ? "tất định" : x.kind, "rủi ro báo sai " + x.false_positive_risk, x.fix_ops.length ? "có thao tác sửa" : null].filter(Boolean).join(" · ")})),
        el("td", {}, pill((SEV[x.severity] || ["neu"])[0] + " sm", x.severity)),
        el("td", {}, state),
        el("td", {}, paramText(x.params_default, x.params_effective, x.params_changed)));
    }));
    $("rfoot").textContent = `${rows.length}/${r.rules.length} luật. Chỉ đọc: muốn đổi ngưỡng cho công ty thì sửa hồ sơ công ty (YAML) rồi khởi động lại; đổi luật/ngưỡng của chuẩn là tạo phiên bản chuẩn mới.`;
  }

  // ---------- Unified Studio: 4 Chế độ, Khung nhìn 2D/3D, Review & Skill Chips ----------
  const MODE_LABELS = {
    audit: ["Chế độ 1: Kiểm lỗi 2D (Audit)", "Audit & AI"],
    diff: ["Chế độ 2: So sánh & Đề xuất ChangeSet", "Diff & ChangeSet"],
    scene: ["Chế độ 3: Không gian 3D & Cụm hình chiếu", "3D Scene & Gaps"],
    review: ["Chế độ 4: Duyệt bản vẽ & Ghi chú bàn giao", "Review & Handover"],
  };

  function switchStudioMode(mode) {
    S.mode = mode;
    if (modeTab) modeTab(mode);
    const [stageLbl, rightLbl] = MODE_LABELS[mode] || MODE_LABELS.audit;
    $("stageModeLabel").textContent = stageLbl;
    $("rightModeBadge").textContent = rightLbl;
    $("zoom2dBar").hidden = mode === "scene";
    $("tools3dBar").hidden = mode !== "scene";
    for (const p of ["finds", "chg", "hist", "sum", "scene", "review"]) {
      const node = $("p-" + p);
      if (node) node.classList.remove("on");
    }
    if (mode === "audit") {
      $("p-finds").classList.add("on");
    } else if (mode === "diff") {
      $("p-chg").classList.add("on");
      if (S.file && !S.suggest && !S.preview) loadSuggest();
    } else if (mode === "scene") {
      $("p-scene").classList.add("on");
      renderScenePane();
    } else if (mode === "review") {
      $("p-review").classList.add("on");
      renderReviewPane();
    }
    renderViewport();
  }

  function populateLayerSelect(p2d) {
    const sel = $("layerFilterSel");
    if (!sel) return;
    const layers = (p2d && p2d.layers) || [];
    fill(sel,
      el("option", {value: "", text: `Tất cả layer (${layers.length})`}),
      ...layers.map((la) => el("option", {value: la.name, text: `${la.name} (${la.count})`})));
    sel.value = S.layerFilter || "";
  }

  function renderClusterBar() {
    const bar = $("clusterBar");
    if (!bar) return;
    const clusters = (S.preview2d && S.preview2d.clusters) || [];
    if (!clusters.length) {
      fill(bar, el("span", {class: "muted", text: "Khung Model"}));
      return;
    }
    fill(bar,
      el("button", {
        type: "button",
        class: "cluster-btn" + (S.activeCluster === "" ? " on" : ""),
        onclick: () => { S.activeCluster = ""; S.vp.zoom = 1; S.vp.panX = 0; S.vp.panY = 0; S.vp.focusBox = null; renderClusterBar(); renderViewport(); },
        text: "Toàn bộ",
      }),
      ...clusters.slice(0, 8).map((c) => el("button", {
        type: "button",
        class: "cluster-btn" + (S.activeCluster === c.id ? " on" : ""),
        title: `Cụm ${c.id}: ${c.size[0]}×${c.size[1]} mm (${c.entities} đối tượng)`,
        onclick: () => { S.activeCluster = c.id; S.vp.zoom = 1; S.vp.panX = 0; S.vp.panY = 0; S.vp.focusBox = c.bbox; renderClusterBar(); renderViewport(); },
        text: `${c.id} (${c.entities})`,
      })));
  }

  function svgEl(tag, attrs) {
    const node = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v !== null && v !== undefined) node.setAttribute(k, String(v));
    }
    return node;
  }

  function renderViewport() {
    if (S.mode === "scene") {
      render3dViewport();
    } else {
      render2dViewport();
    }
  }

  function render2dViewport() {
    const svg = $("cadCanvas");
    if (!svg) return;
    svg.replaceChildren();
    $("zoomPct").textContent = Math.round(S.vp.zoom * 100) + "%";
    const p2d = S.preview2d;
    if (!p2d || !p2d.entities || !p2d.entities.length) {
      svg.appendChild(svgEl("text", {x: 500, y: 260, fill: "#8E968F", "text-anchor": "middle", "font-size": 15}));
      svg.lastChild.textContent = S.file ? "Đang tải hình học 2D của bản vẽ…" : "Chọn một bản vẽ DXF ở cột trái để hiển thị khung nhìn 2D/3D.";
      return;
    }
    const b = S.vp.focusBox || p2d.bounds || [0, 0, 1000, 700];
    const minX = b[0], minY = b[1], maxX = b[2], maxY = b[3];
    const w = Math.max(10, maxX - minX);
    const h = Math.max(10, maxY - minY);
    const pad = 36;
    const scaleBase = Math.min((1000 - pad * 2) / w, (520 - pad * 2) / h);
    const sc = scaleBase * S.vp.zoom;
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    const tx = (x) => 500 + (x - cx) * sc + S.vp.panX;
    const ty = (y) => 260 - (y - cy) * sc + S.vp.panY;

    // Lưới tọa độ nền
    const gridG = svgEl("g", {stroke: "rgba(255,255,255,0.05)", "stroke-width": 1});
    for (let gx = 0; gx <= 1000; gx += 100) gridG.appendChild(svgEl("line", {x1: gx, y1: 0, x2: gx, y2: 520}));
    for (let gy = 0; gy <= 520; gy += 100) gridG.appendChild(svgEl("line", {x1: 0, y1: gy, x2: 1000, y2: gy}));
    svg.appendChild(gridG);

    // Khung bao các cụm hình chiếu (Artboards)
    const clG = svgEl("g", {});
    for (const c of p2d.clusters || []) {
      const x1 = tx(c.bbox[0]), y1 = ty(c.bbox[3]);
      const cw = Math.max(4, (c.bbox[2] - c.bbox[0]) * sc);
      const ch = Math.max(4, (c.bbox[3] - c.bbox[1]) * sc);
      clG.appendChild(svgEl("rect", {
        x: x1, y: y1, width: cw, height: ch,
        fill: S.activeCluster === c.id ? "rgba(63,191,174,0.06)" : "none",
        stroke: "rgba(63,191,174,0.35)", "stroke-dasharray": "5,4", "stroke-width": 1,
      }));
      const lbl = svgEl("text", {x: x1 + 4, y: y1 - 4, fill: "#63D0C1", "font-size": 11, "font-weight": "bold"});
      lbl.textContent = `${c.id} (${c.size[0]}×${c.size[1]} mm)`;
      clG.appendChild(lbl);
    }
    svg.appendChild(clG);

    // Các đối tượng hình học 2D
    const entG = svgEl("g", {});
    for (const e of p2d.entities) {
      if (S.layerFilter && e.layer !== S.layerFilter) continue;
      const stroke = e.layer === "0" ? "#F3CF7A" : (e.layer.includes("WALL") ? "#E9ECEA" : "#63D0C1");
      if (e.t === "LINE" && e.pts && e.pts.length >= 2) {
        entG.appendChild(svgEl("line", {
          x1: tx(e.pts[0][0]), y1: ty(e.pts[0][1]),
          x2: tx(e.pts[1][0]), y2: ty(e.pts[1][1]),
          stroke, "stroke-width": 1.35,
        }));
      } else if (e.t === "LWPOLYLINE" && e.pts && e.pts.length >= 2) {
        const pts = e.pts.map((p) => `${tx(p[0]).toFixed(1)},${ty(p[1]).toFixed(1)}`).join(" ");
        entG.appendChild(svgEl(e.closed ? "polygon" : "polyline", {
          points: pts, fill: e.closed ? "rgba(63,191,174,0.08)" : "none",
          stroke, "stroke-width": 1.35,
        }));
      } else if (e.t === "CIRCLE" && e.c) {
        entG.appendChild(svgEl("circle", {
          cx: tx(e.c[0]), cy: ty(e.c[1]), r: Math.max(2, (e.r || 5) * sc),
          fill: "none", stroke, "stroke-width": 1.2,
        }));
      } else if (e.t === "TEXT" && e.pos) {
        const t = svgEl("text", {x: tx(e.pos[0]), y: ty(e.pos[1]), fill: "#DDF0EC", "font-size": 10});
        t.textContent = e.text;
        entG.appendChild(t);
      } else if (e.t === "INSERT" && e.pos) {
        const ix = tx(e.pos[0]), iy = ty(e.pos[1]);
        entG.appendChild(svgEl("rect", {x: ix - 5, y: iy - 5, width: 10, height: 10, fill: "rgba(224,176,74,0.25)", stroke: "#E0B04A"}));
      }
    }
    svg.appendChild(entG);

    // Đánh dấu toạ độ lỗi (Finding Bounding Boxes)
    const errG = svgEl("g", {});
    for (const m of p2d.markers || []) {
      if (S.sevFilter && m.severity !== S.sevFilter) continue;
      const x1 = tx(m.bbox[0]) - 6, y1 = ty(m.bbox[3]) - 6;
      const mw = Math.max(18, (m.bbox[2] - m.bbox[0]) * sc + 12);
      const mh = Math.max(18, (m.bbox[3] - m.bbox[1]) * sc + 12);
      const col = m.severity === "E" ? "#F0766A" : (m.severity === "W" ? "#E0B04A" : "#A9CBF4");
      const rect = svgEl("rect", {
        x: x1, y: y1, width: mw, height: mh, rx: 4,
        fill: m.severity === "E" ? "rgba(240,118,106,0.16)" : "rgba(224,176,74,0.12)",
        stroke: col, "stroke-width": 1.8, "stroke-dasharray": "4,2",
      });
      errG.appendChild(rect);
      const tag = svgEl("text", {x: x1 + 3, y: Math.max(12, y1 - 3), fill: col, "font-size": 10.5, "font-weight": "bold"});
      tag.textContent = `${m.rule_id}`;
      errG.appendChild(tag);
    }
    svg.appendChild(errG);

    // Đánh dấu ghim Review (Chế độ 4)
    if (S.mode === "review" && S.reviewNotes.length) {
      const rvG = svgEl("g", {});
      S.reviewNotes.forEach((n, idx) => {
        const px = n.pos ? tx(n.pos[0]) : 80 + idx * 42;
        const py = n.pos ? ty(n.pos[1]) : 45;
        rvG.appendChild(svgEl("circle", {cx: px, cy: py, r: 10, fill: n.resolved ? "#2E7D4F" : "#C0392B", stroke: "#fff", "stroke-width": 1.5}));
        const txNode = svgEl("text", {x: px, y: py + 4, fill: "#fff", "font-size": 10, "font-weight": "bold", "text-anchor": "middle"});
        txNode.textContent = String(idx + 1);
        rvG.appendChild(txNode);
      });
      svg.appendChild(rvG);
    }
  }

  function render3dViewport() {
    const svg = $("cadCanvas");
    if (!svg) return;
    svg.replaceChildren();
    const sc3d = S.scene3d;
    const boxes = (sc3d && sc3d.boxes) || [];
    if (!boxes.length) {
      const msg = svgEl("text", {x: 500, y: 250, fill: "#A8B0AA", "text-anchor": "middle", "font-size": 14.5});
      msg.textContent = S.file
        ? "Bản vẽ này chưa đủ thông số chiều cao 3D hoặc hình chiếu (xem mục Phần thiếu bên dưới để gán cụm C1/C2/C3 hoặc nhập W/D/H)."
        : "Chọn một bản vẽ ở cột trái để dựng cảnh 3D.";
      svg.appendChild(msg);
      return;
    }
    // Phép chiếu trục đo / góc nhìn 3D (Iso / Front / Top / Side)
    const cam = S.cam3d || "iso";
    const proj = (x, y, z) => {
      if (cam === "front") return [x, -z];
      if (cam === "top") return [x, -y];
      if (cam === "side") return [y, -z];
      const rad = Math.PI / 6;
      return [(x - y) * Math.cos(rad), -(x + y) * Math.sin(rad) * 0.55 - z * 0.85];
    };
    const pts2d = [];
    for (const b of boxes) {
      for (const [bx, by] of b.base) {
        pts2d.push(proj(bx, by, b.z0), proj(bx, by, b.z1));
      }
    }
    const xs = pts2d.map((p) => p[0]), ys = pts2d.map((p) => p[1]);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const w = Math.max(10, maxX - minX), h = Math.max(10, maxY - minY);
    const scale = Math.min(860 / w, 430 / h) * S.vp.zoom;
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
    const mapPt = (x, y, z) => {
      const [px, py] = proj(x, y, z);
      return [500 + (px - cx) * scale + S.vp.panX, 265 + (py - cy) * scale + S.vp.panY];
    };

    const g = svgEl("g", {});
    for (const b of boxes) {
      const isWall = b.material === "wall";
      const fillCol = S.xray3d
        ? "rgba(63,191,174,0.10)"
        : (isWall ? "rgba(215,218,214,0.45)" : "rgba(219,178,125,0.78)");
      const strokeCol = S.xray3d ? "#63D0C1" : (isWall ? "#8E968F" : "#7A4B00");
      const bot = b.base.map(([x, y]) => mapPt(x, y, b.z0));
      const top = b.base.map(([x, y]) => mapPt(x, y, b.z1));
      const polyPts = (arr) => arr.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
      g.appendChild(svgEl("polygon", {points: polyPts(bot), fill: fillCol, stroke: strokeCol, "stroke-width": 1}));
      for (let i = 0; i < bot.length; i++) {
        const j = (i + 1) % bot.length;
        g.appendChild(svgEl("polygon", {
          points: polyPts([bot[i], bot[j], top[j], top[i]]),
          fill: fillCol, stroke: strokeCol, "stroke-width": S.xray3d ? 1.1 : 1.3,
        }));
      }
      g.appendChild(svgEl("polygon", {points: polyPts(top), fill: fillCol, stroke: strokeCol, "stroke-width": 1.4}));
    }
    svg.appendChild(g);
  }

  function focusRuleOnCanvas(ruleId) {
    const p2d = S.preview2d;
    if (!p2d || !p2d.markers) return;
    const m = p2d.markers.find((x) => x.rule_id === ruleId) || p2d.markers[0];
    if (!m) {
      toast("Luật này áp dụng cấp toàn bản vẽ, không gắn tọa độ cục bộ.");
      return;
    }
    const pad = 120;
    S.vp.focusBox = [m.bbox[0] - pad, m.bbox[1] - pad, m.bbox[2] + pad, m.bbox[3] + pad];
    S.vp.zoom = 1.25;
    S.vp.panX = 0;
    S.vp.panY = 0;
    renderViewport();
    const ov = $("vpOverlay");
    ov.textContent = `Đang focus lỗi ${m.rule_id}: ${m.message}`;
    ov.hidden = false;
  }

  async function renderScenePane() {
    const box = $("sceneList");
    if (!box) return;
    if (!S.file) {
      fill(box, el("div", {class: "empty", text: "Chọn một bản vẽ để xem cấu trúc 3D và các phần thiếu."}));
      return;
    }
    const sc3d = S.scene3d;
    if (!sc3d || !sc3d.scene) {
      fill(box, el("div", {class: "empty", text: "Đang dựng cảnh 3D…"}));
      return;
    }
    const sc = sc3d.scene;
    const clusters = sc3d.clusters || [];
    const viewRow = el("div", {class: "pv"},
      el("h3", {text: "Dựng 3D tất định (cg.scene/1) & Gán cụm hình chiếu"}),
      kv([
        ["Số tường 3D", fmt((sc.walls || []).length)],
        ["Số mô-đun tủ (FN_MOD*)", fmt((sc.modules || []).length)],
        ["Số tấm ván (Panels)", fmt((sc.panels || []).length)],
        ["Phần thiếu thông số (Gaps)", fmt((sc.gaps || []).length)],
      ]),
      clusters.length ? el("div", {class: "bar-act mt8"},
        el("span", {class: "muted", text: "Gán cụm hình chiếu:"}),
        ...["front", "side", "top"].map((vk) => {
          const sel = el("select", {class: "sel sel-sm"},
            el("option", {value: "", text: vk === "front" ? "Mặt đứng: theo layer" : (vk === "side" ? "Mặt bên: theo layer" : "Mặt bằng: theo layer")}),
            ...clusters.map((c) => el("option", {value: c.id, text: `${c.id} (${c.size[0]}×${c.size[1]})`})));
          sel.value = S.views3d[vk] || "";
          sel.addEventListener("change", async () => {
            S.views3d[vk] = sel.value;
            S.scene3d = await api("/api/scene", {file: S.file, supplement: S.supp3d, views: S.views3d});
            renderViewport();
            renderScenePane();
          });
          return sel;
        })) : null);

    const gapCards = (sc.gaps || []).map((g) => el("div", {class: "f-card"},
      el("div", {class: "f-top"}, pill("warn sm", g.kind), el("b", {text: g.id})),
      el("div", {class: "f-d", text: g.message}),
      ...(g.fields || []).map((f) => {
        const inp = el("input", {
          class: "num-in", type: "text", placeholder: `${f.label} (${f.unit || "mm"})`,
          value: S.supp3d[f.key] || "",
        });
        const btn = el("button", {
          class: "btn-p btn-xs", type: "button",
          onclick: async () => {
            S.supp3d[f.key] = inp.value.trim();
            S.scene3d = await api("/api/scene", {file: S.file, supplement: S.supp3d, views: S.views3d});
            renderViewport();
            renderScenePane();
            toast("Đã cập nhật thông số bổ sung và dựng lại 3D.");
          },
          text: "Cập nhật 3D",
        });
        return el("div", {class: "bar-act mt6"}, el("span", {class: "muted", text: f.label + ":"}), inp, btn);
      })));

    fill(box,
      viewRow,
      ...(sc.notes || []).map((n) => el("div", {class: "msg note", text: n})),
      gapCards.length ? el("div", {class: "sev-h"}, pill("warn", `Phần thiếu cần bổ sung (${gapCards.length})`)) : pill("ok", "Đủ thông số dựng hình 3D"),
      ...gapCards);
  }

  async function renderReviewPane() {
    const box = $("reviewList");
    if (!box) return;
    if (!S.file) {
      fill(box, el("div", {class: "empty", text: "Chọn một bản vẽ để xem và ghi chú bàn giao."}));
      return;
    }
    const msgIn = el("textarea", {rows: 2, class: "num-in wfull", placeholder: "Nhập ghi chú duyệt bản vẽ hoặc dặn dò cho bộ phận nhận bàn giao…"});
    const authorIn = el("input", {type: "text", class: "num-in", placeholder: "Người ghi (vd: Trưởng nhóm KT)", value: "Kỹ thuật"});
    const sevSel = el("select", {class: "sel"},
      el("option", {value: "I", text: "Thông tin bàn giao (I)"}),
      el("option", {value: "W", text: "Lưu ý kiểm tra (W)"}),
      el("option", {value: "E", text: "Yêu cầu sửa trước bàn giao (E)"}));
    const addBtn = el("button", {
      class: "btn-p btn-sm", type: "button",
      onclick: async () => {
        const text = msgIn.value.trim();
        if (!text) { toast("Hãy nhập nội dung ghi chú."); return; }
        try {
          const r = await api("/api/review/add", {
            file: S.file,
            message: text,
            author: authorIn.value.trim() || "Kỹ thuật",
            severity: sevSel.value,
            department: S.dept ? S.dept.id : "ky-thuat",
          });
          S.reviewNotes = r.notes || [];
          msgIn.value = "";
          renderReviewPane();
          renderViewport();
          toast("Đã lưu ghi chú bàn giao.");
        } catch (e) { toast(e.message); }
      },
      text: "Thêm ghi chú bàn giao",
    });
    const exportHoBtn = el("button", {
      class: "btn-s btn-sm", type: "button",
      onclick: showHandoverSummary,
      text: "Xuất Biên bản Bàn giao",
    });

    const notesNodes = S.reviewNotes.length
      ? S.reviewNotes.map((n) => el("div", {class: "rv-note" + (n.resolved ? " done" : "")},
          el("div", {class: "f-top"},
            el("b", {text: n.id}),
            pill((SEV[n.severity] || ["info"])[0] + " sm", n.severity),
            el("span", {class: "muted", text: `${n.author} · ${n.created_at}`}),
            el("span", {class: "spacer"}),
            el("button", {
              class: "btn-s btn-xs", type: "button",
              onclick: async () => {
                await api("/api/review/resolve", {id: n.id, resolved: !n.resolved});
                const rv = await api("/api/review/notes?file=" + encodeURIComponent(S.file));
                S.reviewNotes = rv.notes || [];
                renderReviewPane();
                renderViewport();
              },
              text: n.resolved ? "Mở lại" : "Đánh dấu xong",
            })),
          el("div", {class: "f-d", text: n.message})))
      : [el("div", {class: "empty", text: "Chưa có ghi chú bàn giao nào cho bản vẽ này."})];

    fill(box,
      el("div", {class: "rv-form"},
        el("b", {text: "Tạo ghi chú duyệt & bàn giao liên phòng"}),
        msgIn,
        el("div", {class: "rv-row"}, authorIn, sevSel, el("span", {class: "spacer"}), exportHoBtn, addBtn)),
      ...notesNodes);
  }

  async function showHandoverSummary() {
    if (!S.file) { toast("Hãy chọn một bản vẽ trước."); return; }
    try {
      const ho = await api("/api/review/handover", {
        file: S.file,
        standard: S.standard,
        department: S.dept ? S.dept.id : null,
      });
      openDrawer("Biên bản Bàn giao Bản vẽ", [
        el("p", {}, ho.ready ? pill("ok", "ĐẠT — Sẵn sàng bàn giao", "check") : pill("err", "CHẶN — Còn lỗi mức E", "warn")),
        kv([
          ["Bản vẽ", ho.file],
          ["Chuyển giao", `${ho.department} → ${ho.next_department}`],
          ["Chuẩn áp dụng", ho.standard],
          ["Số ghi chú", `${ho.notes_count} (${ho.unresolved_notes} mục chưa đóng)`],
        ]),
        el("h3", {text: "Nội dung biên bản bàn giao"}),
        el("pre", {class: "json", text: ho.handover_text}),
      ]);
    } catch (e) { toast(e.message); }
  }

  function askAiAboutRule(ruleId, title) {
    const prompt = `Giải thích lỗi ${ruleId} (${title}) trong bản vẽ ${S.file || "đang mở"} và hướng dẫn cách khắc phục cụ thể.`;
    $("inp").value = prompt;
    $("inp").focus();
  }

  const SKILL_PROMPTS = {
    "khao-sat-ban-ve": "Hãy khảo sát tổng quan bản vẽ đang mở (phiên bản DXF, đơn vị, số layer, khối, kiểu chữ, layout) và nhận xét mức độ sạch của bản vẽ.",
    "kiem-va-giai-thich-loi": "Hãy kiểm tra bản vẽ đang mở theo chuẩn hiện tại, liệt kê các lỗi mức E quan trọng nhất và giải thích nguyên nhân kèm cách sửa.",
    "don-ban-ve": "Hãy phân tích các lỗi vệ sinh bản vẽ (layer dư, kiểu chữ, màu/nét cứng) và đề xuất một changeset dọn bản vẽ an toàn.",
    "ghi-chu-ban-giao": "Hãy tổng hợp tình trạng bản vẽ đang mở và soạn giúp tôi ghi chú bàn giao ngắn gọn, rõ ràng cho phòng tiếp theo.",
  };

  function bindSkillChips() {
    const box = $("skillChips");
    if (!box) return;
    for (const btn of box.querySelectorAll("[data-skill]")) {
      btn.addEventListener("click", () => {
        const sk = btn.getAttribute("data-skill");
        if (sk === "don-ban-ve") $("allowPropose").checked = true;
        $("inp").value = SKILL_PROMPTS[sk] || "";
        $("inp").focus();
      });
    }
  }

  async function openVisualQaSnapshot() {
    if (!S.file) { toast("Hãy chọn một bản vẽ trước khi chụp trạng thái Visual QA."); return; }
    try {
      const ws = await api("/api/workspace/state", {
        file: S.file,
        standard: S.standard,
        department: S.dept ? S.dept.id : null,
        mode: S.mode,
      });
      openDrawer("Visual QA & Hợp đồng Phiên (WorkspaceState)", [
        el("p", {}, pill("ok", "cg.workspace/1", "check"), " ", el("span", {text: `Chế độ đang mở: ${S.mode.toUpperCase()}`})),
        kv([
          ["Thư mục", ws.workspace_name],
          ["Bản vẽ đang mở", ws.active_file],
          ["Phòng", ws.department],
          ["Chuẩn", ws.standard],
          ["Chế độ dữ liệu AI", ws.anonymize ? "Ẩn danh Bậc 1" : "Không ẩn danh"],
        ]),
        el("h3", {text: "Ảnh chụp Hợp đồng Dữ liệu (WorkspaceState JSON)"}),
        el("pre", {class: "json", text: JSON.stringify(ws, null, 2)}),
      ]);
    } catch (e) { toast(e.message); }
  }

  function bindViewportEvents() {
    const svg = $("cadCanvas");
    if (!svg) return;
    svg.addEventListener("mousedown", (e) => {
      S.vp.dragging = true;
      S.vp.startX = e.clientX - S.vp.panX;
      S.vp.startY = e.clientY - S.vp.panY;
    });
    window.addEventListener("mousemove", (e) => {
      if (!S.vp.dragging) return;
      S.vp.panX = e.clientX - S.vp.startX;
      S.vp.panY = e.clientY - S.vp.startY;
      renderViewport();
    });
    window.addEventListener("mouseup", () => { S.vp.dragging = false; });
    svg.addEventListener("wheel", (e) => {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.15 : 0.87;
      S.vp.zoom = Math.max(0.25, Math.min(8, S.vp.zoom * factor));
      renderViewport();
    }, {passive: false});

    $("zoomInBtn").addEventListener("click", () => { S.vp.zoom = Math.min(8, S.vp.zoom * 1.25); renderViewport(); });
    $("zoomOutBtn").addEventListener("click", () => { S.vp.zoom = Math.max(0.25, S.vp.zoom / 1.25); renderViewport(); });
    $("zoomFitBtn").addEventListener("click", () => {
      S.vp.zoom = 1; S.vp.panX = 0; S.vp.panY = 0; S.vp.focusBox = null;
      $("vpOverlay").hidden = true;
      renderViewport();
    });
    $("zoomErrBtn").addEventListener("click", () => {
      const m = S.preview2d && S.preview2d.markers && S.preview2d.markers[0];
      if (m) focusRuleOnCanvas(m.rule_id);
      else toast("Bản vẽ không có điểm lỗi cục bộ nào để phóng tới.");
    });
    $("layerFilterSel").addEventListener("change", () => {
      S.layerFilter = $("layerFilterSel").value;
      renderViewport();
    });
    for (const b of $("tools3dBar").querySelectorAll("[data-cam]")) {
      b.addEventListener("click", () => { S.cam3d = b.getAttribute("data-cam"); renderViewport(); });
    }
    $("xray3dBtn").addEventListener("click", () => {
      S.xray3d = !S.xray3d;
      $("xray3dBtn").textContent = "Nhìn xuyên: " + (S.xray3d ? "Bật" : "Tắt");
      renderViewport();
    });
    $("dlGlbBtn").addEventListener("click", async () => {
      if (!S.file) return;
      try {
        const r = await fetch("/api/scene/glb?file=" + encodeURIComponent(S.file), {headers: {"X-CadGuard-Token": TOKEN}});
        if (!r.ok) throw new Error("Không xuất được GLB.");
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const a = el("a", {href: url, download: S.file.replace(/\.dxf$/i, ".glb")});
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } catch (e) { toast(e.message); }
    });
    for (const btn of $("quickStats").querySelectorAll("[data-sev]")) {
      btn.addEventListener("click", () => {
        S.sevFilter = btn.getAttribute("data-sev") || "";
        for (const x of $("quickStats").querySelectorAll(".stat-pill")) x.classList.toggle("on", x === btn);
        renderAudit();
        renderViewport();
      });
    }
    $("qaSnapBtn").addEventListener("click", openVisualQaSnapshot);
  }

  // ---------- khởi động ----------
  async function boot() {
    initIcons(document);
    applyTheme(localStorage.getItem("cg-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
    $("themeBtn").addEventListener("click", () => applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark"));
    const screens = {work: $("s-work"), rules: $("s-rules"), connect: $("s-connect")};
    const goScreen = setupTablist(document.querySelector(".nav"), (tab) => {
      for (const [k, s] of Object.entries(screens)) s.classList.toggle("on", k === tab.dataset.go);
      if (tab.dataset.go === "rules") loadRules();
    });
    modeTab = setupTablist($("modeTabs"), (tab) => {
      switchStudioMode(tab.dataset.mode);
    });
    centerTab = setupTablist($("centerTabs"), (tab) => {
      for (const p of ["finds", "chg", "hist", "sum", "scene", "review"]) {
        const node = $("p-" + p);
        if (node) node.classList.toggle("on", p === tab.dataset.p);
      }
      if (tab.dataset.p === "sum") loadSummary();
      if (tab.dataset.p === "hist") loadChangesets();
      if (tab.dataset.p === "chg" && S.file && !S.suggest && !S.preview) loadSuggest();
    });
    bindViewportEvents();
    bindSkillChips();
    $("stdLink").addEventListener("click", () => goScreen("rules"));
    $("deptSel").addEventListener("change", () => {
      S.dept = S.session.departments.find((d) => d.id === $("deptSel").value);
      sessionStorage.setItem("cg-dept", S.dept.id);
      applyDept();
    });
    $("scanAll").addEventListener("click", scanAll);
    $("ruleStd").addEventListener("change", loadRules);
    $("rq").addEventListener("input", () => RULES && renderRules());
    $("fKind").addEventListener("change", () => RULES && renderRules());
    $("drClose").addEventListener("click", closeDrawer);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && $("drawer").classList.contains("on")) closeDrawer(); });
    $("engineSel").addEventListener("change", () => {
      S.engine = S.engines.find((x) => x.name === $("engineSel").value) || null;
      if (S.engine) sessionStorage.setItem("cg-engine", S.engine.name);
      renderEngineCard();
      renderCost(null);
    });
    $("form").addEventListener("submit", sendChat);
    $("inp").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("form").requestSubmit(); }
    });
    $("stopBtn").addEventListener("click", stopChat);
    $("clearBtn").addEventListener("click", () => { if (!S.busy) { S.history = []; fill($("log"), ); } });
    $("refreshEngines").addEventListener("click", () => loadEngines(true));
    if (!TOKEN) { $("tokenBanner").hidden = false; return; }
    try {
      S.session = await api("/api/session");
    } catch (e) { toast(e.message); return; }
    renderSession();
    renderCost(null);
    await Promise.all([loadFiles(), loadEngines(false), loadChangesets()]);
  }

  document.addEventListener("DOMContentLoaded", boot);
})();

