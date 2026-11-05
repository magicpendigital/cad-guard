"use strict";
(() => {
  const $ = (id) => document.getElementById(id),
    NS = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "svg",
    ).namespaceURI;
  const local = location.pathname === "/review.html",
    token = sessionStorage.getItem("cg-token") || "";
  let state,
    pack,
    item = 0,
    view,
    meta,
    full,
    vb,
    anchor = null,
    agent = null,
    refreshTimer;
  const status = {
    review: "Cần rà soát",
    "client-approved": "Khách đã chốt",
    "production-ready": "Sẵn sàng sản xuất",
  };
  const role = {
    owner: "Quản trị cục bộ",
    designer: "Thiết kế",
    customer: "Khách",
    technical: "Kỹ thuật",
  };
  const id = () => crypto.randomUUID().replaceAll("-", "");
  function node(tag, props = {}, ...children) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else if (k === "checked") n.checked = v;
      else n.setAttribute(k, v);
    }
    n.append(...children);
    return n;
  }
  function say(message) {
    $("notice").textContent = message;
  }
  function fail(e) {
    $("error").hidden = false;
    $("error").textContent = e.message;
  }
  async function request(path, body) {
    const h = {};
    if (local) h["X-CadGuard-Token"] = token;
    else if (state) h["X-Review-CSRF"] = state.csrf;
    const opts = { headers: h, cache: "no-store" };
    if (body !== undefined) {
      opts.method = "POST";
      h["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const r = await fetch(path, opts);
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "Chưa kết nối được máy chủ.");
    return data;
  }
  async function call(action, body = {}) {
    return request("/api/review/action", { action, ...body });
  }
  async function run(fn) {
    $("error").hidden = true;
    try {
      return await fn();
    } catch (e) {
      fail(e);
    }
  }
  async function refresh() {
    state = await request("/api/review/state");
    $("identity").textContent =
      role[state.role] + (local ? "" : " · " + state.actor);
    $("back").hidden = !local;
    $("admin").hidden = !local;
    renderPackages();
    if (local) renderAdmin();
  }
  function renderPackages() {
    $("packageList").replaceChildren(
      ...state.packages.map((p) =>
        node("button", {
          type: "button",
          class: "package" + (pack?.id === p.id ? " current" : ""),
          text:
            p.name +
            " · v" +
            p.revision +
            " · " +
            status[p.status] +
            (p.current ? "" : " · bản cũ"),
          onclick: () => run(() => load(p.id)),
        }),
      ),
    );
  }
  function renderAdmin() {
    $("serverNote").textContent = state.gateway_running
      ? "Cổng rà soát của dự án đang chạy. Cần kiểm qua điện thoại bật Tailscale trước khi gửi khách."
      : "Cổng rà soát của dự án chưa chạy. Dùng scripts/share.py start; máy chủ phải đang hoạt động.";
    $("members").replaceChildren(
      ...state.members.map((m) =>
        node(
          "div",
          { class: "card" },
          node("span", {
            text:
              m.login +
              " · " +
              role[m.role] +
              (m.active ? "" : " · đã thu hồi"),
          }),
          node("button", {
            type: "button",
            text: m.active ? "Thu hồi" : "Cấp lại",
            onclick: () =>
              run(async () => {
                await call("member", {
                  login: m.login,
                  role: m.role,
                  active: !m.active,
                });
                await refresh();
              }),
          }),
        ),
      ),
    );
    const selected = [...$("customers").selectedOptions].map((o) => o.value);
    $("customers").replaceChildren(
      ...state.members
        .filter((m) => m.active && m.role === "customer")
        .map((m) => {
          const o = node("option", { value: m.login, text: m.login });
          o.selected = selected.includes(m.login);
          return o;
        }),
    );
    const prev = $("previous").value;
    $("previous").replaceChildren(
      node("option", { value: "", text: "Bộ hồ sơ mới" }),
      ...state.packages
        .filter((p) => p.current)
        .map((p) =>
          node("option", { value: p.id, text: p.name + " · v" + p.revision }),
        ),
    );
    $("previous").value = prev;
    if (!$("drawings").childElementCount)
      for (const d of state.drawings) {
        const check = node("input", { type: "checkbox", value: d.path }),
          layouts = node(
            "select",
            { multiple: "", "aria-label": "Layout của " + d.path },
            node("option", { value: "Model", text: "Model" }),
          );
        layouts.options[0].selected = true;
        check.addEventListener("change", () => {
          if (check.checked)
            run(async () => {
              let r;
              do {
                r = await request("/api/preview", { file: d.path, wait: 3 });
              } while (r.status === "pending" && check.checked);
              if (r.status === "ready") {
                layouts.replaceChildren(
                  ...r.layouts.map((n) =>
                    node("option", { value: n, text: n }),
                  ),
                );
                layouts.options[0].selected = true;
              } else say(r.reason || "Chưa dựng được preview.");
            });
        });
        $("drawings").append(
          node(
            "div",
            { class: "publish-file" },
            node("label", {}, check, document.createTextNode(d.path)),
            layouts,
          ),
        );
      }
    if (!$("origin").value) $("origin").value = state.origin || "";
  }
  async function load(pid) {
    const drafts = new Map(
      [...document.querySelectorAll("#notes article")].map((n) => [
        n.id,
        n.querySelector("textarea")?.value || "",
      ]),
    );
    pack = await call("get", { id: pid });
    item = Math.min(item, pack.items.length - 1);
    $("title").textContent =
      pack.name +
      " · v" +
      pack.revision +
      " · " +
      status[pack.status] +
      (pack.current ? "" : " · PHIÊN BẢN CŨ");
    $("items").replaceChildren(
      ...pack.items.map((it, i) =>
        node("option", { value: i, text: it.name + " · " + it.layout }),
      ),
    );
    $("items").value = item;
    renderNotes();
    for (const [key, value] of drafts) {
      const n = document.getElementById(key)?.querySelector("textarea");
      if (n) n.value = value;
    }
    renderPackages();
    await showDrawing();
    const technical = ["owner", "technical"].includes(state.role);
    $("approve").hidden = state.role !== "customer" || !pack.current;
    $("audit").hidden = !technical || !pack.current;
    $("release").hidden = !technical || !pack.current;
    $("export").hidden =
      !technical || pack.status !== "production-ready" || !pack.current;
    renderReports();
    $("history").textContent = JSON.stringify(
      { confirmations: pack.approvals, events: pack.history },
      null,
      2,
    );
    $("warnings").replaceChildren(
      ...(pack.warnings || []).map((w) =>
        node(
          "label",
          { text: w.text },
          node("textarea", {
            "data-warning": w.id,
            placeholder: "Quyết định xử lý / lý do chấp nhận cảnh báo",
          }),
        ),
      ),
    );
    document.body.classList.remove("show-packages");
  }
  function renderReports() {
    const reports = pack.reports || [],
      hasErrors = reports.some((r) => r.totals.E > 0 || r.internal_errors),
      open = pack.notes.some((n) => n.status === "open");
    $("gateMessage").textContent = !pack.current
      ? "Đây là phiên bản cũ; hãy mở bộ hồ sơ mới nhất."
      : pack.status === "production-ready"
        ? "Kỹ thuật đã duyệt bàn giao đúng phiên bản này."
        : pack.status !== "client-approved"
          ? "Chờ khách được chỉ định chốt thiết kế sau khi xử lý trao đổi."
          : !reports.length
            ? "Khách đã chốt. Kỹ thuật cần quét bộ hồ sơ trước khi duyệt bàn giao."
            : hasErrors
              ? "Còn lỗi E hoặc lỗi bộ kiểm. Xem kết quả bên dưới, sửa trong CAD và công bố phiên bản mới."
              : open
                ? "Còn ghi chú chưa xử lý."
                : "Đủ bước kiểm cơ bản; kỹ thuật cần quyết định từng cảnh báo W và xác nhận bàn giao.";
    $("release").disabled =
      !pack.current ||
      pack.status !== "client-approved" ||
      !reports.length ||
      hasErrors ||
      open;
    $("approve").disabled = pack.approvals.some(
      (a) =>
        a.actor === state.actor &&
        a.kind === "client" &&
        a.epoch === pack.epoch,
    );
    $("reports").replaceChildren(
      ...reports.map((r) =>
        node(
          "details",
          { class: "card" },
          node("summary", {
            text:
              r.files[0].file +
              " · " +
              r.standard.name +
              " · " +
              r.totals.E +
              " lỗi E, " +
              r.totals.W +
              " cảnh báo W",
          }),
          ...r.files[0].findings.map((f) =>
            node("p", {
              text: f.severity + " · " + f.rule_id + ": " + f.message,
            }),
          ),
          ...r.files[0].skipped.map((f) =>
            node("p", { text: "Bỏ qua " + f.rule + ": " + f.reason }),
          ),
        ),
      ),
    );
  }
  async function mutate(action, extra = {}) {
    if (!pack) throw new Error("Chọn bộ hồ sơ trước.");
    await call(action, {
      id: pack.id,
      version: pack.version,
      request_id: id(),
      ...extra,
    });
    await refresh();
    await load(pack.id);
  }
  function svgNode(tag, attrs) {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    return n;
  }
  function safeCopy(src, dst, depth = 0) {
    if (depth > 4) return;
    for (const ch of src.children) {
      if (!["g", "path"].includes(ch.localName)) continue;
      const n = svgNode(ch.localName, {});
      for (const a of ch.attributes) {
        const ok = {
          d: /^[MLQCZmlqcz0-9 .\-]*$/,
          class: /^dxf-(g|s|f|hs|hf)$/,
          stroke: /^(none|currentColor)$/,
          fill: /^(none|currentColor)$/,
          "stroke-opacity": /^[01](\.\d{1,3})?$/,
          "fill-opacity": /^[01](\.\d{1,3})?$/,
          "fill-rule": /^evenodd$/,
          "stroke-linecap": /^round$/,
          "stroke-linejoin": /^round$/,
        }[a.name];
        if (ok?.test(a.value)) n.setAttribute(a.name, a.value);
      }
      safeCopy(ch, n, depth + 1);
      dst.append(n);
    }
  }
  async function showDrawing() {
    if (!pack) return;
    const r = await call("view", { id: pack.id, item });
    meta = r.meta;
    full = meta.viewbox.slice();
    vb = full.slice();
    view = svgNode("svg", {
      viewBox: vb.join(" "),
      role: "img",
      "aria-label": pack.items[item].name,
    });
    safeCopy(
      new DOMParser().parseFromString(r.svg, "image/svg+xml").documentElement,
      view,
    );
    drawNotes();
    $("canvas").replaceChildren(view);
    $("limitations").textContent = meta.limitations;
    interactions();
  }
  function toSvg(coords) {
    const [sx, sy, tx, ty] = meta.transform;
    return coords.map((v, i) => v * (i % 2 ? sy : sx) + (i % 2 ? ty : tx));
  }
  function toModel(coords) {
    const [sx, sy, tx, ty] = meta.transform;
    return coords.map((v, i) => (v - (i % 2 ? ty : tx)) / (i % 2 ? sy : sx));
  }
  function drawNotes() {
    for (const n of pack.notes) {
      if (!n.anchor || n.anchor.item !== item) continue;
      const a = n.anchor,
        c = toSvg(a.coords);
      let mark;
      if (a.kind === "point")
        mark = svgNode("circle", {
          cx: c[0],
          cy: c[1],
          r: Math.max(full[2], full[3]) / 120,
        });
      else
        mark = svgNode("rect", {
          x: Math.min(c[0], c[2]),
          y: Math.min(c[1], c[3]),
          width: Math.abs(c[2] - c[0]),
          height: Math.abs(c[3] - c[1]),
        });
      mark.setAttribute("class", "annotation");
      mark.setAttribute("tabindex", "0");
      mark.setAttribute("role", "button");
      mark.setAttribute("aria-label", n.text);
      mark.addEventListener("click", () => focusNote(n));
      mark.addEventListener("keydown", (e) => {
        if (e.key === "Enter") focusNote(n);
      });
      view.append(mark);
    }
  }
  function focusNote(n) {
    document.body.classList.add("show-notes");
    $("n-" + n.id)?.scrollIntoView({ block: "nearest" });
    if (n.anchor && n.anchor.item === item) {
      const c = toSvg(n.anchor.coords),
        w = full[2] / 4,
        h = (w * full[3]) / full[2];
      vb = [c[0] - w / 2, c[1] - h / 2, w, h];
      updateView();
    }
  }
  function updateView() {
    view?.setAttribute("viewBox", vb.join(" "));
  }
  function zoom(f) {
    if (!vb) return;
    const w = Math.max(full[2] / 2000, Math.min(full[2] * 4, vb[2] * f)),
      h = (w * vb[3]) / vb[2];
    vb = [vb[0] + (vb[2] - w) / 2, vb[1] + (vb[3] - h) / 2, w, h];
    updateView();
  }
  function pointer(e) {
    const rect = view.getBoundingClientRect(),
      s = Math.max(vb[2] / rect.width, vb[3] / rect.height);
    return [
      vb[0] - (rect.width * s - vb[2]) / 2 + (e.clientX - rect.left) * s,
      vb[1] - (rect.height * s - vb[3]) / 2 + (e.clientY - rect.top) * s,
      s,
    ];
  }
  function interactions() {
    const points = new Map();
    let drag = null,
      pinch = 0,
      selection;
    view.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        zoom(e.deltaY < 0 ? 0.8 : 1.25);
      },
      { passive: false },
    );
    view.addEventListener("pointerdown", (e) => {
      if (e.target.classList.contains("annotation")) return;
      points.set(e.pointerId, [e.clientX, e.clientY]);
      view.setPointerCapture(e.pointerId);
      if (points.size === 2) {
        const p = [...points.values()];
        pinch = Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]);
        drag = null;
        return;
      }
      const p = pointer(e);
      drag = {
        screen: [e.clientX, e.clientY],
        start: p.slice(0, 2),
        v: vb.slice(),
      };
    });
    view.addEventListener("pointermove", (e) => {
      if (points.has(e.pointerId))
        points.set(e.pointerId, [e.clientX, e.clientY]);
      if (points.size === 2) {
        const p = [...points.values()],
          d = Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]);
        if (d && pinch) zoom(pinch / d);
        pinch = d;
        return;
      }
      if (!drag) return;
      const p = pointer(e);
      if ($("tool").value === "pan") {
        vb = [
          drag.v[0] - (e.clientX - drag.screen[0]) * p[2],
          drag.v[1] - (e.clientY - drag.screen[1]) * p[2],
          drag.v[2],
          drag.v[3],
        ];
        updateView();
      } else if ($("tool").value === "rect") {
        selection?.remove();
        selection = svgNode("rect", {
          x: Math.min(p[0], drag.start[0]),
          y: Math.min(p[1], drag.start[1]),
          width: Math.abs(p[0] - drag.start[0]),
          height: Math.abs(p[1] - drag.start[1]),
          class: "selection",
        });
        view.append(selection);
      }
    });
    const end = (e) => {
      points.delete(e.pointerId);
      pinch = 0;
      if (drag && $("tool").value !== "pan") {
        const p = pointer(e),
          kind = $("tool").value;
        anchor = {
          kind,
          item,
          coords: toModel(
            kind === "point"
              ? p.slice(0, 2)
              : [...drag.start, ...p.slice(0, 2)],
          ),
        };
        $("anchorText").textContent =
          "Đã gắn " +
          (kind === "point" ? "ghim" : "vùng") +
          " vào " +
          pack.items[item].name +
          " · " +
          pack.items[item].layout;
        document.body.classList.add("show-notes");
        $("noteText").focus();
      }
      drag = null;
    };
    view.addEventListener("pointerup", end);
    view.addEventListener("pointercancel", () => {
      drag = null;
      points.clear();
      pinch = 0;
    });
  }
  function renderNotes() {
    const customer = state.role === "customer",
      designer = ["owner", "designer"].includes(state.role);
    $("visibility").disabled = customer;
    if (customer) $("visibility").value = "shared";
    $("noteForm").hidden = !pack.current;
    $("notes").replaceChildren(
      ...pack.notes.map((n) => {
        const actions = node("div", { class: "actions" });
        if (n.anchor)
          actions.append(
            node("button", {
              type: "button",
              text: "Đến vị trí",
              onclick: () =>
                run(async () => {
                  if (item !== n.anchor.item) {
                    item = n.anchor.item;
                    $("items").value = item;
                    await showDrawing();
                  }
                  focusNote(n);
                }),
            }),
          );
        if (!customer && pack.current)
          actions.append(
            node("button", {
              type: "button",
              text: n.status === "open" ? "Đã xử lý" : "Mở lại",
              onclick: () =>
                run(() =>
                  mutate(n.status === "open" ? "resolve" : "reopen", {
                    note: n.id,
                  }),
                ),
            }),
          );
        if (designer && pack.current)
          actions.append(
            node("button", {
              type: "button",
              text: "Trao đổi với Agent",
              onclick: () => run(() => openAgent(n)),
            }),
          );
        const card = node(
          "article",
          { id: "n-" + n.id, class: "card " + n.status },
          node("b", {
            text:
              (n.visibility === "internal" ? "Nội bộ" : "Với khách") +
              " · " +
              (n.status === "open" ? "Mở" : "Đã xử lý"),
          }),
          node("p", { text: n.text }),
          node("small", {
            text:
              n.actor +
              " · " +
              n.at +
              (n.assignee ? " · giao " + n.assignee : ""),
          }),
          ...n.replies.map((r) =>
            node("p", { class: "reply", text: r.actor + ": " + r.text }),
          ),
          actions,
        );
        if (pack.current) {
          const input = node("textarea", {
              "aria-label": "Trả lời ghi chú",
              maxlength: 4000,
            }),
            form = node(
              "form",
              {
                onsubmit: (e) => {
                  e.preventDefault();
                  run(() => mutate("reply", { note: n.id, text: input.value }));
                },
              },
              input,
              node("button", { text: "Trả lời" }),
            );
          card.append(form);
          if (!customer) {
            const assign = node("input", {
              type: "email",
              "aria-label": "Người phụ trách",
              placeholder: "Email người phụ trách",
              value: n.assignee || "",
            });
            card.append(
              node(
                "form",
                {
                  onsubmit: (e) => {
                    e.preventDefault();
                    run(() =>
                      mutate("assign", { note: n.id, assignee: assign.value }),
                    );
                  },
                },
                assign,
                node("button", { text: "Phân công" }),
              ),
            );
          }
        }
        return card;
      }),
    );
  }
  async function openAgent(n) {
    agent = await call("agent-open", { id: pack.id, note: n.id, item });
    $("agent").hidden = false;
    $("consent").checked = false;
    $("agentContext").textContent = JSON.stringify(agent.context, null, 2);
    $("agentInfo").textContent = agent.note;
    $("agentReply").textContent = "";
    $("agent").scrollIntoView({ block: "nearest" });
  }
  function link() {
    if (!state.origin || !pack)
      throw new Error("Chưa cấu hình địa chỉ Tailscale hoặc chưa chọn hồ sơ.");
    return state.origin + "/r/" + pack.id;
  }
  $("refresh").addEventListener("click", () =>
    run(async () => {
      await refresh();
      if (pack) await load(pack.id);
    }),
  );
  $("listToggle").addEventListener("click", () =>
    document.body.classList.toggle("show-packages"),
  );
  $("notesToggle").addEventListener("click", () =>
    document.body.classList.toggle("show-notes"),
  );
  $("items").addEventListener("change", () =>
    run(async () => {
      item = Number($("items").value);
      anchor = null;
      await showDrawing();
    }),
  );
  $("zoomIn").addEventListener("click", () => zoom(0.8));
  $("zoomOut").addEventListener("click", () => zoom(1.25));
  $("fit").addEventListener("click", () => {
    if (!full) return;
    vb = full.slice();
    updateView();
  });
  $("clearAnchor").addEventListener("click", () => {
    anchor = null;
    $("anchorText").textContent = "Ghi chú chung";
  });
  $("centerAnchor").addEventListener("click", () => {
    if (!vb) return;
    anchor = {
      kind: "point",
      item,
      coords: toModel([vb[0] + vb[2] / 2, vb[1] + vb[3] / 2]),
    };
    $("anchorText").textContent = "Đã ghim tại tâm khung nhìn hiện tại.";
    $("noteText").focus();
  });
  $("noteForm").addEventListener("submit", (e) => {
    e.preventDefault();
    run(async () => {
      await mutate("note", {
        text: $("noteText").value,
        visibility: $("visibility").value,
        anchor,
        assignee: $("assignee").value,
      });
      $("noteText").value = "";
      anchor = null;
      $("anchorText").textContent = "Ghi chú chung";
    });
  });
  $("memberForm").addEventListener("submit", (e) => {
    e.preventDefault();
    run(async () => {
      await call("member", {
        login: $("memberLogin").value,
        role: $("memberRole").value,
        active: true,
      });
      await refresh();
    });
  });
  $("publishForm").addEventListener("submit", (e) => {
    e.preventDefault();
    run(async () => {
      const entries = [];
      for (const row of $("drawings").children) {
        const check = row.querySelector("input");
        if (check.checked)
          for (const opt of row.querySelector("select").selectedOptions)
            entries.push({ file: check.value, layout: opt.value });
      }
      const button = e.submitter;
      button.disabled = true;
      say(
        "Đang dựng snapshot và công bố; mỗi bản vẽ có thể mất tối đa 60 giây.",
      );
      try {
        const p = await call("publish", {
          name: $("packageName").value,
          previous: $("previous").value || null,
          customers: [...$("customers").selectedOptions].map((x) => x.value),
          items: entries,
          cad_checked: $("cadChecked").checked,
          request_id: id(),
        });
        await refresh();
        await load(p.id);
        say("Đã công bố phiên bản bất biến.");
      } finally {
        button.disabled = false;
      }
    });
  });
  $("originForm").addEventListener("submit", (e) => {
    e.preventDefault();
    run(async () => {
      await call("origin", { origin: $("origin").value });
      await refresh();
      say(
        "Đã lưu địa chỉ; hãy kiểm cổng review và Tailscale Serve trước khi gửi khách.",
      );
    });
  });
  $("copyLink").addEventListener("click", () =>
    run(async () => {
      const url = link();
      try {
        await navigator.clipboard.writeText(url);
        say("Đã sao chép link nội bộ.");
      } catch (_) {
        say(url);
      }
    }),
  );
  $("qrToggle").addEventListener("click", () =>
    run(async () => {
      const url = link();
      if ($("qr").hidden) {
        const data = await call("qr", { id: pack.id });
        $("qr").src = URL.createObjectURL(
          new Blob([Uint8Array.from(atob(data.png), (c) => c.charCodeAt(0))], {
            type: "image/png",
          }),
        );
      }
      $("qr").hidden = !$("qr").hidden;
    }),
  );
  $("approve").addEventListener("click", () => {
    if (
      confirm(
        "Chốt toàn bộ hồ sơ v" +
          pack.revision +
          "? Đây là xác nhận thiết kế; kỹ thuật duyệt bàn giao riêng.",
      )
    )
      run(() => mutate("approve"));
  });
  $("audit").addEventListener("click", () => run(() => mutate("audit")));
  $("release").addEventListener("click", () => {
    if (confirm("Xác nhận kỹ thuật duyệt bàn giao sản xuất bộ hồ sơ này?"))
      run(() =>
        mutate("release", {
          warnings: Object.fromEntries(
            [...document.querySelectorAll("[data-warning]")].map((n) => [
              n.dataset.warning,
              n.value,
            ]),
          ),
        }),
      );
  });
  $("export").addEventListener("click", () =>
    run(async () => {
      const r = await call("export", { id: pack.id }),
        data = Uint8Array.from(atob(r.download), (c) => c.charCodeAt(0)),
        url = URL.createObjectURL(
          new Blob([data], { type: "application/zip" }),
        ),
        a = node("a", {
          href: url,
          download: "ho-so-v" + pack.revision + ".zip",
        });
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }),
  );
  $("consent").addEventListener("change", () =>
    run(async () => {
      await call("agent-consent", {
        id: pack.id,
        session: agent.session,
        context_hash: agent.context_hash,
        consent: $("consent").checked,
      });
    }),
  );
  $("revoke").addEventListener("click", () =>
    run(async () => {
      await call("agent-consent", {
        id: pack.id,
        session: agent.session,
        consent: false,
      });
      $("consent").checked = false;
      say(
        "Đã thu hồi; lượt gửi tiếp theo bị chặn. Dữ liệu đã gửi trước đó không thu hồi được.",
      );
    }),
  );
  $("agentForm").addEventListener("submit", (e) => {
    e.preventDefault();
    run(async () => {
      if (!$("consent").checked)
        throw new Error("Xem dữ liệu và đồng ý theo phiên trước.");
      const r = await call("agent-ask", {
        id: pack.id,
        session: agent.session,
        message: $("agentMessage").value,
      });
      $("agentReply").textContent = (r.reply || r.error || "") + "\n" + r.note;
    });
  });
  $("copyAgent").addEventListener("click", () => {
    $("visibility").value = "internal";
    $("noteText").value = $("agentReply").textContent;
    $("noteText").focus();
  });
  run(async () => {
    await refresh();
    const pid = local
      ? new URLSearchParams(location.search).get("id")
      : location.pathname.split("/")[2];
    if (pid) await load(pid);
    else if (state.packages.length) await load(state.packages[0].id);
    else {
      say(
        local
          ? "Thêm thành viên rồi công bố bộ hồ sơ để bắt đầu."
          : "Chưa có bộ hồ sơ được chia sẻ cho bạn.",
      );
      document.body.classList.add("show-packages");
    }
  });
  refreshTimer = setInterval(() => {
    if (!pack || document.hidden) return;
    call("get", { id: pack.id })
      .then((p) => {
        if (p.version !== pack.version || p.current !== pack.current)
          say(
            "Có cập nhật từ người khác. Bấm Tải lại để xem; nội dung đang nhập được giữ.",
          );
      })
      .catch((e) => {
        fail(e);
        if (/quyền/.test(e.message))
          for (const n of document.querySelectorAll(
            "button,textarea,input,select",
          ))
            n.disabled = true;
      });
  }, 5000);
})();
