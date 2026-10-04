/* LegalEase front-end (vanilla JS, no build step). All DOM is built with
   textContent/value, never innerHTML, so user text can't inject markup. */
(() => {
  const $ = (id) => document.getElementById(id);
  const state = { templates: [], current: null, doc: null, logoDataUrl: null };

  function el(tag, props = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else if (v !== false && v != null) n.setAttribute(k, v === true ? "" : v);
    }
    kids.flat().forEach((c) => c != null && n.append(c));
    return n;
  }

  function say(node, text, kind) { node.textContent = text || ""; node.className = "msg" + (kind ? " " + kind : ""); }
  async function api(path, opts) {
    const res = await fetch(path, opts);
    if (!res.ok) {
      let msg = `Request failed (${res.status})`;
      try {
        const j = await res.json();
        msg = typeof j.detail === "string" ? j.detail : Array.isArray(j.detail) ? j.detail.map((d) => d.msg).join("; ") : msg;
      } catch (_) { /* non-JSON error */ }
      throw new Error(msg);
    }
    return res;
  }

  // ------------------------------------------------------------- setup
  async function init() {
    try {
      const health = await (await api("/api/health")).json();
      $("aiBadge").textContent = health.ai_enabled ? "AI drafting: on" : "Template mode (no API key)";
      if (!health.ai_enabled) { $("useAi").checked = false; $("useAi").disabled = true; }
      state.templates = await (await api("/api/templates")).json();
      renderCards();
    } catch (e) { say($("formMsg"), e.message, "err"); }
  }

  function renderCards() {
    const box = $("typeCards"); box.replaceChildren();
    state.templates.forEach((t) => box.append(
      el("button", { type: "button", class: "card", onclick: () => selectType(t.key) },
        el("b", { text: t.label }), el("span", { text: t.description }))));
  }

  function selectType(key) {
    state.current = state.templates.find((t) => t.key === key);
    [...$("typeCards").children].forEach((c, i) => c.classList.toggle("sel", state.templates[i].key === key));
    const form = $("docForm"); form.replaceChildren();
    const groups = {};
    state.current.fields.forEach((f) => (groups[f.group || "Details"] ||= []).push(f));
    for (const [g, fields] of Object.entries(groups)) {
      form.append(el("fieldset", {}, el("legend", { text: g }), fields.map(fieldEl)));
    }
    $("generateBtn").disabled = false;
    say($("formMsg"), "");
  }

  function fieldEl(f) {
    const common = { id: "f_" + f.name, name: f.name, placeholder: f.placeholder || null };
    let input;
    if (f.type === "textarea") input = el("textarea", common);
    else if (f.type === "select") input = el("select", { id: common.id, name: f.name }, f.options.map((o) => el("option", { value: o, text: o })));
    else input = el("input", { ...common, type: f.type === "number" ? "text" : f.type, inputmode: f.type === "number" ? "decimal" : null });
    input.value = f.default || "";
    return el("label", {}, el("span", { class: f.required ? "req" : "", text: f.label }), input);
  }

  // ------------------------------------------------------------- generate
  $("generateBtn").addEventListener("click", async () => {
    const data = {};
    state.current.fields.forEach((f) => (data[f.name] = $("f_" + f.name).value));
    const btn = $("generateBtn"); btn.disabled = true; btn.textContent = "Generating…";
    say($("formMsg"), "");
    try {
      const res = await api("/api/generate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_type: state.current.key, data, use_ai: $("useAi").checked }),
      });
      state.doc = await res.json();
      renderPaper();
      say($("previewMsg"), state.doc.generated_by === "ai" ? "Drafted with AI. Review and edit anything below." : "Drafted from template. Review and edit anything below.", "ok");
    } catch (e) { say($("formMsg"), e.message, "err"); }
    finally { btn.disabled = false; btn.textContent = "Generate document"; }
  });

  // ------------------------------------------------------------- editable preview
  function autosize(t) { t.style.height = "auto"; t.style.height = t.scrollHeight + 2 + "px"; }
  function area(value, onChange) {
    const t = el("textarea", { rows: 1 }); t.value = value;
    t.addEventListener("input", () => { onChange(t.value); autosize(t); });
    requestAnimationFrame(() => autosize(t));
    return t;
  }
  function line(value, onChange, cls) {
    const i = el("input", { type: "text", class: cls || null }); i.value = value;
    i.addEventListener("input", () => onChange(i.value));
    return i;
  }

  function renderPaper() {
    const d = state.doc, paper = $("paper"); paper.replaceChildren();
    $("empty").hidden = true; paper.hidden = false;
    document.querySelectorAll(".export-btn").forEach((b) => (b.disabled = false));

    const lh = el("div", { class: "letterhead" });
    const logoNode = el("img", { alt: "Logo", hidden: !state.logoDataUrl, src: state.logoDataUrl || null });
    const co = el("b", { text: $("bCompany").value });
    lh.append(logoNode, co); lh.hidden = !state.logoDataUrl && !$("bCompany").value;
    paper.append(lh);

    paper.append(el("div", { class: "gen", text: d.generated_by === "ai" ? "AI-drafted" : "Template-drafted" }));
    paper.append(line(d.title, (v) => (d.title = v), "doc-title"));
    paper.append(area(d.preamble, (v) => (d.preamble = v)));

    if (d.terms.length) {
      const tb = el("tbody");
      d.terms.forEach((t) => tb.append(el("tr", {},
        el("td", {}, line(t.label, (v) => (t.label = v))), el("td", {}, line(t.value, (v) => (t.value = v))))));
      paper.append(el("table", { class: "terms" }, tb));
    }

    const list = el("div"); paper.append(list);
    const drawClauses = () => {
      list.replaceChildren();
      d.sections.forEach((s, i) => {
        const move = (dx) => { const j = i + dx; if (j < 0 || j >= d.sections.length) return; [d.sections[i], d.sections[j]] = [d.sections[j], d.sections[i]]; drawClauses(); };
        list.append(el("div", { class: "clause" },
          el("div", { class: "tools" },
            el("button", { type: "button", title: "Move up", onclick: () => move(-1), text: "↑" }),
            el("button", { type: "button", title: "Move down", onclick: () => move(1), text: "↓" }),
            el("button", { type: "button", title: "Delete clause", onclick: () => { d.sections.splice(i, 1); drawClauses(); }, text: "✕" })),
          el("div", { class: "head" }, el("span", { class: "num", text: i + 1 + "." }), line(s.heading, (v) => (s.heading = v))),
          area(s.body, (v) => (s.body = v))));
      });
      list.append(el("button", { type: "button", class: "add", text: "+ Add clause", onclick: () => { d.sections.push({ heading: "New Clause", body: "" }); drawClauses(); } }));
    };
    drawClauses();

    if (d.signatories.length) {
      const sigs = el("div", { class: "sigs" });
      d.signatories.forEach((s) => sigs.append(el("div", { class: "sig" }, el("div", { class: "line" }),
        line(s.name, (v) => (s.name = v)), line(s.role, (v) => (s.role = v)))));
      paper.append(sigs);
    }
  }

  // ------------------------------------------------------------- branding
  function branding() {
    return { company_name: $("bCompany").value, logo_data_url: state.logoDataUrl, font: $("bFont").value,
             accent_color: $("bColor").value, footer_text: $("bFooter").value };
  }
  function applyAccent() { document.documentElement.style.setProperty("--accent", $("bColor").value); }
  ["bCompany", "bColor", "bFont", "bFooter"].forEach((id) => $(id).addEventListener("input", () => { applyAccent(); if (state.doc) renderPaper(); }));

  $("bLogo").addEventListener("change", (e) => {
    const f = e.target.files[0];
    if (!f) { state.logoDataUrl = null; $("logoPreview").hidden = true; return; }
    if (!["image/png", "image/jpeg"].includes(f.type) || f.size > 2 * 1024 * 1024) {
      e.target.value = ""; state.logoDataUrl = null; $("logoPreview").hidden = true;
      say($("formMsg"), "Logo must be a PNG or JPEG under 2 MB.", "err"); return;
    }
    const r = new FileReader();
    r.onload = () => {
      state.logoDataUrl = r.result; $("logoPreview").src = r.result; $("logoPreview").hidden = false;
      say($("formMsg"), ""); if (state.doc) renderPaper();
    };
    r.readAsDataURL(f);
  });

  // ------------------------------------------------------------- export
  document.querySelectorAll(".export-btn").forEach((btn) => btn.addEventListener("click", async () => {
    const fmt = btn.dataset.fmt, label = btn.textContent;
    btn.disabled = true; btn.textContent = "…"; say($("previewMsg"), "");
    try {
      const res = await api("/api/export/" + fmt, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document: state.doc, branding: branding() }),
      });
      const blob = await res.blob();
      const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "")?.[1] || "document." + fmt;
      const a = el("a", { href: URL.createObjectURL(blob), download: name });
      document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      say($("previewMsg"), `Downloaded ${name}`, "ok");
    } catch (e) { say($("previewMsg"), e.message, "err"); }
    finally { btn.disabled = false; btn.textContent = label; }
  }));

  init();
})();
