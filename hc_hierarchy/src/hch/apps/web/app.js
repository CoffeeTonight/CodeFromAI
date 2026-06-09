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