const $ = (sel) => document.querySelector(sel);

async function apiGet(path) {
  const r = await fetch(path);
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

async function apiPost(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

let selectedPath = null;
let lastQueryText = "";
let lastMeta = null;
let highlightTerms = [];
let helpPayload = null;
let helpActiveTab = "examples";

function setQueryStatus(text, ok = false) {
  const el = $("#query-status");
  el.textContent = text;
  el.classList.toggle("ok", ok);
}

function basename(fp) {
  if (!fp) return "";
  const i = Math.max(fp.lastIndexOf("/"), fp.lastIndexOf("\\"));
  return i >= 0 ? fp.slice(i + 1) : fp;
}

function formatMetaPanel(m) {
  const lines = [];
  if (m.defines && typeof m.defines === "object") {
    const defs = Object.entries(m.defines)
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
    lines.push(`defines: ${defs || "(none)"}`);
  }
  if (m.elab_succeeded !== undefined) {
    lines.push(`elab_succeeded: ${m.elab_succeeded}`);
  }
  if (Array.isArray(m.unresolved_modules) && m.unresolved_modules.length) {
    lines.push(`unresolved: ${m.unresolved_modules.join(", ")}`);
  }
  if (Array.isArray(m.warnings) && m.warnings.length) {
    for (const w of m.warnings.slice(0, 12)) {
      lines.push(`warning: ${w}`);
    }
    if (m.warnings.length > 12) {
      lines.push(`… +${m.warnings.length - 12} more`);
    }
  }
  if (m.hierarchy_source) {
    lines.push(`hierarchy_source: ${m.hierarchy_source}`);
  }
  if (m.top_inference) {
    lines.push(`top_inference: ${m.top_inference}`);
  }
  if (Array.isArray(m.top_modules_all) && m.top_modules_all.length > 1) {
    lines.push(`all_tops: ${m.top_modules_all.join(", ")}`);
  }
  if (m.missing_file_count > 0) {
    lines.push(`missing_rtl_files: ${m.missing_file_count}`);
  }
  if (m.path_hierarchy_used !== undefined) {
    lines.push(`path_hierarchy_used: ${m.path_hierarchy_used}`);
  }
  if (m.elab_partial === "1" || m.elab_partial === 1) {
    lines.push("elab_partial: 1");
  }
  if (m.elab_instance_cap_hit === "1") {
    lines.push(`elab_instance_cap_hit: 1 (cap=${m.elab_instance_cap || "?"})`);
  }
  if (m.preprocess_libs_in_driver === "1") {
    lines.push("preprocess_libs_in_driver: 1");
  }
  if (m.ifdef_variant_diff && typeof m.ifdef_variant_diff === "object") {
    const d = m.ifdef_variant_diff;
    lines.push(
      `ifdef diff: +${(d.only_alt || []).length} -${(d.only_base || []).length} common=${(d.common || []).length}`
    );
  }
  return lines.join("\n") || "No extra metadata.";
}

async function loadMeta() {
  const m = await apiGet("/api/meta");
  lastMeta = m;
  const tier = m.tier || "?";
  const eng = m.engine || "?";
  const ic = m.instance_count ?? "?";
  const mc = m.module_count ?? "?";
  const hs = m.hierarchy_source ? ` · ${m.hierarchy_source}` : "";
  const db = basename(m.database || "");
  let extra = "";
  const unr = m.unresolved_modules;
  if (Array.isArray(unr) && unr.length) {
    extra += ` · ${unr.length} unresolved`;
  }
  const warns = m.warnings;
  if (Array.isArray(warns) && warns.length) {
    extra += ` · ${warns.length} warnings`;
  }
  if (m.missing_file_count > 0) {
    extra += ` · ${m.missing_file_count} missing RTL`;
  }
  $("#meta-bar").textContent =
    `${db} · ${ic} instances · ${mc} modules · tier ${tier} · ${eng}${hs}${extra}`;
  $("#meta-panel").textContent = formatMetaPanel(m);
  renderMissingFilesList(m.missing_files || []);
}

function findTreeRow(fullPath) {
  if (!fullPath) return null;
  return document.querySelector(
    `.tree-row[data-path="${CSS.escape(fullPath)}"]`
  );
}

function makeTreeRow(node) {
  const row = document.createElement("div");
  row.className = "tree-row";
  row.dataset.path = node.full_path;

  const toggle = document.createElement("span");
  toggle.className = "tree-toggle" + (node.has_children ? "" : " empty");
  toggle.textContent = node.has_children ? "▸" : "";
  toggle.title = node.has_children ? "Expand / collapse" : "";

  const label = document.createElement("span");
  label.className = "tree-label";
  label.textContent = node.leaf || node.full_path;
  label.title = node.full_path;

  const mod = document.createElement("span");
  mod.className = "tree-mod";
  mod.textContent = node.module;

  row.append(toggle, label, mod);
  return row;
}

function collapseTreeRow(row) {
  const nodeEl = row?.closest(".tree-node");
  if (!nodeEl) return;
  row.dataset.open = "0";
  const toggle = row.querySelector(".tree-toggle:not(.empty)");
  if (toggle) toggle.textContent = "▸";
  const ch = nodeEl.querySelector(":scope > .tree-children");
  if (ch) ch.remove();
}

function collapseEntireTree() {
  // Collapse roots only — removes entire subtrees from the DOM.
  document
    .querySelectorAll("#tree > .tree-node > .tree-row[data-open='1']")
    .forEach((row) => collapseTreeRow(row));
}

async function openTreeRow(row, parentPath) {
  const nodeEl = row.closest(".tree-node");
  if (!nodeEl || row.dataset.open === "1") return;
  row.dataset.open = "1";
  const toggle = row.querySelector(".tree-toggle:not(.empty)");
  if (toggle) toggle.textContent = "▾";
  if (!nodeEl.querySelector(":scope > .tree-children")) {
    nodeEl.appendChild(await fetchTreeChildren(nodeEl, parentPath));
  }
}

function bindTreeRow(row, node) {
  const toggle = row.querySelector(".tree-toggle:not(.empty)");
  const label = row.querySelector(".tree-label");
  const mod = row.querySelector(".tree-mod");

  if (toggle) {
    toggle.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      if (row.dataset.open === "1") {
        collapseTreeRow(row);
      } else {
        await openTreeRow(row, node.full_path);
      }
    });
  }

  const select = (ev) => {
    ev.stopPropagation();
    selectInstance(node.full_path, node.filepath, node.ports, { syncTree: false });
  };
  label.addEventListener("click", select);
  mod.addEventListener("click", select);
}

async function fetchTreeChildren(container, parentPath) {
  const data = await apiGet(
    "/api/tree/children" +
      (parentPath ? `?parent=${encodeURIComponent(parentPath)}` : "")
  );
  const wrap = document.createElement("div");
  wrap.className = "tree-children";
  for (const child of data.children) {
    const nodeEl = document.createElement("div");
    nodeEl.className = "tree-node";
    const row = makeTreeRow(child);
    nodeEl.appendChild(row);
    bindTreeRow(row, child);
    wrap.appendChild(nodeEl);
  }
  return wrap;
}

async function expandTreeLevels(maxDepth) {
  const n = Number.parseInt(String(maxDepth), 10);
  if (!Number.isFinite(n) || n < 0) return;
  if (!document.querySelector("#tree .tree-row")) {
    await loadTreeRoots();
  }
  collapseEntireTree();
  if (n === 0) return;
  for (let level = 0; level < n; level += 1) {
    const rows = Array.from(
      document.querySelectorAll("#tree .tree-row")
    ).filter(
      (row) =>
        row.querySelector(".tree-toggle:not(.empty)") && row.dataset.open !== "1"
    );
    if (!rows.length) break;
    for (const row of rows) {
      await openTreeRow(row, row.dataset.path);
    }
  }
}

async function loadTreeRoots() {
  const tree = $("#tree");
  tree.innerHTML = "";
  const data = await apiGet("/api/tree/children");
  for (const node of data.children) {
    const nodeEl = document.createElement("div");
    nodeEl.className = "tree-node";
    const row = makeTreeRow(node);
    nodeEl.appendChild(row);
    bindTreeRow(row, node);
    tree.appendChild(nodeEl);
  }
}

function highlightSelection() {
  document.querySelectorAll(".tree-row.selected").forEach((el) => {
    el.classList.remove("selected");
  });
  document.querySelectorAll("#results-body tr.selected").forEach((el) => {
    el.classList.remove("selected");
  });
  if (!selectedPath) return;
  const tr = document.querySelector(`#results-body tr[data-path="${CSS.escape(selectedPath)}"]`);
  if (tr) tr.classList.add("selected");
  document.querySelectorAll(".tree-row").forEach((row) => {
    if (row.dataset.path === selectedPath) row.classList.add("selected");
  });
}

function escapeRegExp(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function renderSourceContent(text, terms) {
  const view = $("#source-view");
  const unique = [...new Set((terms || []).filter((t) => t && t.length > 1))].slice(0, 24);
  if (!unique.length) {
    const code = document.createElement("code");
    code.textContent = text;
    view.innerHTML = "";
    view.appendChild(code);
    return;
  }
  const frag = document.createDocumentFragment();
  const lines = text.split("\n");
  for (const line of lines) {
    const span = document.createElement("span");
    span.className = "src-line";
    const hitLine = unique.some((t) => line.includes(t));
    if (hitLine) span.classList.add("hl-line");
    let html = escapeHtml(line);
    for (const t of unique.sort((a, b) => b.length - a.length)) {
      html = html.replace(
        new RegExp(escapeRegExp(t), "g"),
        `<mark class="hl-term">${escapeHtml(t)}</mark>`
      );
    }
    span.innerHTML = html || " ";
    frag.appendChild(span);
    frag.appendChild(document.createTextNode("\n"));
  }
  view.innerHTML = "";
  view.appendChild(frag);
}

async function revealTreePath(fullPath) {
  if (!fullPath) return;
  const parts = fullPath.split(".");
  if (parts.length < 1) return;
  if (!findTreeRow(parts[0])) {
    await loadTreeRoots();
  }
  for (let depth = 1; depth < parts.length; depth += 1) {
    const parentPath = parts.slice(0, depth).join(".");
    const row = findTreeRow(parentPath);
    if (!row) continue;
    await openTreeRow(row, parentPath);
  }
  highlightSelection();
  const target = document.querySelector(
    `.tree-row[data-path="${CSS.escape(fullPath)}"]`
  );
  if (target) target.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

async function selectInstance(fullPath, filepath, ports, opts = {}) {
  selectedPath = fullPath;
  const terms = [
    fullPath.split(".").pop(),
    ...(ports || []),
    ...highlightTerms,
  ];
  if (opts.syncTree !== false) {
    await revealTreePath(fullPath);
  } else {
    highlightSelection();
  }
  showPorts(ports || []);
  let srcPath = filepath || "";
  try {
    const detail = await apiGet(`/api/instance?path=${encodeURIComponent(fullPath)}`);
    const allPorts = detail.ports?.length ? detail.ports : ports || [];
    if (detail.filepath) srcPath = detail.filepath;
    if (allPorts.length) showPorts(allPorts);
    await loadSource(srcPath, [...terms, ...allPorts]);
  } catch (_) {
    await loadSource(srcPath, terms);
  }
}

function showPorts(ports) {
  const box = $("#ports-box");
  const list = $("#ports-list");
  list.innerHTML = "";
  if (!ports.length) {
    box.classList.add("hidden");
    return;
  }
  box.classList.remove("hidden");
  for (const p of ports) {
    const li = document.createElement("li");
    li.textContent = p;
    list.appendChild(li);
  }
}

function setSourcePathDisplay(filepath, missing) {
  const pathEl = $("#source-path");
  pathEl.textContent = filepath || "(no source file)";
  pathEl.classList.toggle("source-missing", Boolean(missing));
}

function showMissingSource(filepath, message) {
  const view = $("#source-view");
  setSourcePathDisplay(filepath, true);
  view.innerHTML = `<code class="source-missing-msg">${escapeHtml(message)}</code>`;
}

function renderMissingFilesList(files) {
  const box = $("#missing-files-box");
  const list = $("#missing-files-list");
  list.innerHTML = "";
  if (!files?.length) {
    box.classList.add("hidden");
    return;
  }
  box.classList.remove("hidden");
  for (const fp of files) {
    const li = document.createElement("li");
    li.className = "missing-file-item";
    li.textContent = fp;
    li.title = fp;
    list.appendChild(li);
  }
}

async function loadSource(filepath, terms = []) {
  const view = $("#source-view");
  const fp = (filepath || "").trim();
  if (!fp) {
    showMissingSource("", "No source file linked to this instance");
    return;
  }
  setSourcePathDisplay(fp, false);
  view.innerHTML = '<code class="muted">Loading…</code>';
  const hl = [...new Set(terms.filter(Boolean))].join(",");
  const url =
    `/api/source?file=${encodeURIComponent(fp)}` +
    (hl ? `&highlight=${encodeURIComponent(hl)}` : "");
  try {
    const data = await apiGet(url);
    if (data.missing) {
      showMissingSource(data.filepath || fp, data.error || "Source file not found");
      return;
    }
    setSourcePathDisplay(data.filepath || fp, false);
    const useTerms = data.highlights?.length ? data.highlights : terms;
    renderSourceContent(data.content, useTerms);
    if (data.truncated) {
      view.appendChild(
        Object.assign(document.createElement("div"), {
          className: "muted",
          textContent: `… truncated (${data.size} bytes total)`,
        })
      );
    }
  } catch (e) {
    showMissingSource(fp, e.message || "Failed to load source");
  }
}

function renderResults(rows) {
  const body = $("#results-body");
  body.innerHTML = "";
  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.dataset.path = r.full_path;
    const inst = r.inst || (r.full_path ? r.full_path.split(".").pop() : "");
    tr.innerHTML = `
      <td class="col-path" title="${escapeHtml(r.full_path)}">${escapeHtml(r.full_path)}</td>
      <td class="col-inst" title="${escapeHtml(inst)}">${escapeHtml(inst)}</td>
      <td>${escapeHtml(r.module)}</td>
      <td>${r.depth}</td>
      <td class="col-file" title="${escapeHtml(r.filepath)}">${escapeHtml(basename(r.filepath))}</td>
    `;
    tr.addEventListener("click", () => {
      highlightTerms = (r.ports || []).slice();
      if (r.port_name) highlightTerms.push(r.port_name);
      selectInstance(r.full_path, r.filepath, r.ports, { syncTree: true });
    });
    body.appendChild(tr);
  }
  highlightSelection();
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function showTextExport(text) {
  lastQueryText = text;
  const box = $("#text-export");
  if (!text) {
    box.classList.add("hidden");
    box.textContent = "";
    return;
  }
  box.textContent = text;
  box.classList.remove("hidden");
}

async function runDql() {
  const q = $("#dql-input").value.trim();
  if (!q) return;
  setQueryStatus("Running…");
  try {
    const data = await apiPost("/api/query", { q, format: "text" });
    renderResults(data.rows);
    showTextExport(data.text || "");
    const extra = data.truncated ? " (truncated)" : "";
    setQueryStatus(`${data.count} hit${data.count === 1 ? "" : "s"}${extra}`, true);
  } catch (e) {
    setQueryStatus(e.message);
    showTextExport("");
  }
}

async function fetchQueryText(format = "text") {
  const q = $("#dql-input").value.trim();
  if (!q) return "";
  const url = `/api/query/text?q=${encodeURIComponent(q)}&format=${encodeURIComponent(format)}`;
  const r = await fetch(url);
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.error || r.statusText);
  }
  return r.text();
}

async function copyResultsText() {
  try {
    const text = lastQueryText || (await fetchQueryText("text"));
    await navigator.clipboard.writeText(text);
    setQueryStatus("Copied text", true);
  } catch (e) {
    setQueryStatus(e.message);
  }
}

function substituteTop(query, topModule) {
  const top = (topModule || "").trim();
  return String(query || "").replaceAll("{{TOP}}", top || "top_module");
}

function renderHelpTextBody(text) {
  const pre = document.createElement("pre");
  pre.className = "help-pre";
  pre.textContent = text || "";
  return pre;
}

function renderExampleGroups(groups, topModule) {
  const wrap = document.createElement("div");
  wrap.className = "help-examples";

  const note = document.createElement("p");
  note.className = "help-note";
  note.textContent =
    "예시를 클릭하면 DQL 입력창에 채워집니다. Run(Enter)으로 실행하세요. " +
    (topModule
      ? `이 DB top: ${topModule}`
      : "top module 미확인 — {{TOP}} 자리에 실제 top 이름을 넣으세요.");
  wrap.appendChild(note);

  const instNote = document.createElement("pre");
  instNote.className = "help-pre help-warn";
  instNote.textContent =
    "⚠ inst = leaf 이름만 (점 없음).  inst ~ \"*t*.*\" → 0건\n" +
    "   path ~ \"*t*.*\" → 경로 패턴 검색";
  wrap.appendChild(instNote);

  for (const group of groups || []) {
    const section = document.createElement("section");
    section.className = "help-example-group";

    const h3 = document.createElement("h3");
    h3.textContent = group.title || "";
    section.appendChild(h3);

    if (group.hint) {
      const hint = document.createElement("p");
      hint.className = "help-hint";
      hint.textContent = group.hint;
      section.appendChild(hint);
    }

    const list = document.createElement("div");
    list.className = "help-example-list";

    for (const ex of group.examples || []) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "help-example-btn" + (ex.cli_only ? " cli-only" : "");
      const q = substituteTop(ex.query, topModule);
      btn.dataset.query = q;
      btn.dataset.cliOnly = ex.cli_only ? "1" : "0";

      const label = document.createElement("span");
      label.className = "ex-label";
      label.textContent = ex.label || q;

      const code = document.createElement("code");
      code.className = "ex-query";
      code.textContent = q;

      btn.append(label, code);
      if (ex.note) {
        const n = document.createElement("span");
        n.className = "ex-note";
        n.textContent = ex.note;
        btn.appendChild(n);
      }

      btn.addEventListener("click", () => {
        if (ex.cli_only) {
          navigator.clipboard.writeText(q).then(
            () => setQueryStatus("CLI 명령 복사됨", true),
            () => setQueryStatus("복사 실패")
          );
          return;
        }
        $("#dql-input").value = q;
        closeHelpDialog();
        $("#dql-input").focus();
        setQueryStatus(`예시 적용: ${ex.label || q}`, true);
      });
      list.appendChild(btn);
    }
    section.appendChild(list);
    wrap.appendChild(section);
  }
  return wrap;
}

function renderHelpPanels(payload) {
  const tabs = $("#help-tabs");
  const panels = $("#help-panels");
  tabs.innerHTML = "";
  panels.innerHTML = "";

  const topModule = payload.top_module || "";
  $("#help-top-hint").textContent = topModule
    ? `top module: ${topModule}`
    : "";

  for (const sec of payload.sections || []) {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = "help-tab";
    tab.dataset.tab = sec.id;
    tab.textContent = sec.title;
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", sec.id === helpActiveTab ? "true" : "false");
    if (sec.id === helpActiveTab) tab.classList.add("active");
    tab.addEventListener("click", () => selectHelpTab(sec.id));
    tabs.appendChild(tab);

    const panel = document.createElement("div");
    panel.className = "help-panel";
    panel.dataset.tab = sec.id;
    panel.setAttribute("role", "tabpanel");
    if (sec.id !== helpActiveTab) panel.classList.add("hidden");

    if (sec.id === "examples") {
      panel.appendChild(renderExampleGroups(payload.example_groups, topModule));
    } else {
      panel.appendChild(renderHelpTextBody(sec.body));
    }
    panels.appendChild(panel);
  }
}

function selectHelpTab(tabId) {
  helpActiveTab = tabId;
  document.querySelectorAll(".help-tab").forEach((el) => {
    const on = el.dataset.tab === tabId;
    el.classList.toggle("active", on);
    el.setAttribute("aria-selected", on ? "true" : "false");
  });
  document.querySelectorAll(".help-panel").forEach((el) => {
    el.classList.toggle("hidden", el.dataset.tab !== tabId);
  });
}

async function loadHelpPayload() {
  if (helpPayload) return helpPayload;
  helpPayload = await apiGet("/api/help");
  return helpPayload;
}

function openHelpDialog(tabId = "examples") {
  helpActiveTab = tabId;
  const dlg = $("#help-dialog");
  const backdrop = $("#help-backdrop");
  loadHelpPayload()
    .then((payload) => {
      renderHelpPanels(payload);
      backdrop.classList.remove("hidden");
      backdrop.setAttribute("aria-hidden", "false");
      if (typeof dlg.showModal === "function") {
        dlg.showModal();
      } else {
        dlg.setAttribute("open", "open");
        dlg.classList.add("open");
      }
    })
    .catch((e) => setQueryStatus(`도움말 로드 실패: ${e.message}`));
}

function closeHelpDialog() {
  const dlg = $("#help-dialog");
  const backdrop = $("#help-backdrop");
  backdrop.classList.add("hidden");
  backdrop.setAttribute("aria-hidden", "true");
  if (typeof dlg.close === "function" && dlg.open) {
    dlg.close();
  } else {
    dlg.removeAttribute("open");
    dlg.classList.remove("open");
  }
}

function downloadResultsText() {
  const text = lastQueryText;
  if (!text) {
    setQueryStatus("Run a query first");
    return;
  }
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "hch-query-results.txt";
  a.click();
  URL.revokeObjectURL(a.href);
  setQueryStatus("Downloaded .txt", true);
}

function init() {
  $("#btn-meta-toggle").addEventListener("click", () => {
    $("#meta-panel").classList.toggle("hidden");
  });
  for (const id of ["btn-help", "btn-dql-help", "btn-help-footer"]) {
    $(`#${id}`)?.addEventListener("click", () => openHelpDialog("examples"));
  }
  $("#btn-help-close")?.addEventListener("click", closeHelpDialog);
  $("#btn-help-close2")?.addEventListener("click", closeHelpDialog);
  $("#help-backdrop")?.addEventListener("click", closeHelpDialog);
  $("#help-dialog")?.addEventListener("cancel", (ev) => {
    ev.preventDefault();
    closeHelpDialog();
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "F1") {
      ev.preventDefault();
      const dlg = $("#help-dialog");
      const open =
        dlg?.open || dlg?.classList?.contains("open") || dlg?.hasAttribute("open");
      if (open) closeHelpDialog();
      else openHelpDialog("examples");
    }
  });
  $("#btn-run-dql").addEventListener("click", runDql);
  $("#dql-input").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") runDql();
  });
  $("#btn-reload-tree").addEventListener("click", () => loadTreeRoots());
  $("#btn-expand-tree").addEventListener("click", () => {
    expandTreeLevels($("#tree-expand-depth").value).catch((e) => {
      $("#tree").innerHTML = `<div class="muted" style="padding:1rem">${escapeHtml(e.message)}</div>`;
    });
  });
  $("#tree-expand-depth").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") $("#btn-expand-tree").click();
  });
  $("#btn-export-text").addEventListener("click", copyResultsText);
  $("#btn-download-text").addEventListener("click", downloadResultsText);

  loadMeta().catch((e) => {
    $("#meta-bar").textContent = `Error: ${e.message}`;
  });
  loadTreeRoots().catch((e) => {
    $("#tree").innerHTML = `<div class="muted" style="padding:1rem">${escapeHtml(e.message)}</div>`;
  });
}

init();