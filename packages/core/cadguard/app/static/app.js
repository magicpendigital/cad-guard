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
    return (name) => { const t = tabs.find((x) => x.dataset.go === name || x.dataset.p === name); if (t) select(t, false); };
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

  // ---------- một bản vẽ: kiểm ----------
  let centerTab = null;
  async function openFile(path) {
    S.file = path;
    S.suggest = null;
    S.preview = null;
    renderFiles();
    $("cvTitle").textContent = path;
    $("cvInfo").hidden = true;
    fill($("finds"), el("div", {class: "empty"}, "Đang kiểm…"));
    fill($("chgList"), emptyChg());
    $("chgFoot").hidden = true;
    fill($("sumList"), );
    try {
      const r = await api("/api/audit", {file: path, standard: S.standard});
      if (S.file !== path) return;
      S.audit = r;
      S.scan[path] = {path, counts: r.counts, ok: r.counts.E === 0};
      renderFiles();
      renderAudit();
    } catch (e) {
      fill($("finds"), el("div", {class: "empty"}, el("b", {text: "Không kiểm được"}), e.message));
    }
    renderHistory();
  }

  function renderAudit() {
    const a = S.audit;
    const total = a.counts.E + a.counts.W + a.counts.I;
    $("cntF").textContent = String(total);
    $("cntF").classList.toggle("hot", a.counts.E > 0);
    $("cvInfo").textContent = `${a.standard} ${a.version}` + (a.profile ? ` · hồ sơ ${a.profile.name} ${a.profile.version}` : "");
    $("cvInfo").hidden = false;
    const out = [];
    out.push(el("div", {class: "bar-act"}, countsPills(a.counts), el("span", {class: "muted", text: `${a.rules_run} luật đã chạy`}),
      el("span", {class: "spacer"}),
      a.fixable_rules.length ? el("button", {class: "btn-p btn-sm", type: "button", onclick: () => { S.suggest = null; S.preview = null; selectCenter("chg"); }}, icon("tool"), "Đề xuất sửa") : null));
    if (a.records_capped) out.push(el("div", {class: "msg note", text: "Tệp rất lớn: danh sách đối tượng bị cắt ở trần bộ nhớ; số liệu tổng vẫn đủ."}));
    if (!total) out.push(el("div", {class: "empty"}, el("b", {text: "Không có phát hiện nào"}), `Bản vẽ đạt các luật đang chạy của ${a.standard}.`));
    for (const g of a.groups) {
      if (!g.rules.length) continue;
      out.push(el("div", {class: "sev-h"}, pill(SEV[g.severity][0], `${g.label} (${g.severity})`), el("span", {class: "muted", text: `${g.rules.length} luật`})));
      for (const r of g.rules) {
        const fixable = a.fixable_rules.includes(r.rule_id);
        out.push(el("div", {class: "f-card"},
          el("div", {class: "f-top"},
            el("button", {class: "f-rule link", type: "button", title: "Giải thích luật", onclick: () => showExplain(r.rule_id, a.standard)}, r.rule_id),
            pill(SEV[r.severity][0] + " sm", SEV[r.severity][1]),
            r.count > 1 ? pill("neu sm", `${fmt(r.count)} chỗ`) : null,
            fixable ? pill("ok sm", "có thao tác sửa") : null),
          el("div", {class: "f-title", text: r.title}),
          el("div", {class: "f-d"}, el("ul", {}, r.items.map((it) => el("li", {},
            it.message,
            it.layer ? el("span", {class: "muted", text: ` · layer ${it.layer}`}) : null,
            it.layout ? el("span", {class: "muted", text: ` · ${it.layout}`}) : null,
            it.handles && it.handles.length ? el("span", {class: "muted", text: ` · handle ${it.handles.join(", ")}`}) : null)))),
          el("div", {class: "f-meta"}, el("button", {class: "f-link", type: "button", onclick: () => showExplain(r.rule_id, a.standard)}, "Giải thích luật này"))));
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
    centerTab = setupTablist($("centerTabs"), (tab) => {
      for (const p of ["finds", "chg", "hist", "sum"]) $("p-" + p).classList.toggle("on", p === tab.dataset.p);
      if (tab.dataset.p === "sum") loadSummary();
      if (tab.dataset.p === "hist") loadChangesets();
      if (tab.dataset.p === "chg" && S.file && !S.suggest && !S.preview) loadSuggest();
    });
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
