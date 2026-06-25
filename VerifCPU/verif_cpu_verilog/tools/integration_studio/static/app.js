const state = {
  config: null,
  cpus: [],
  selectedId: null,
  hierarchy: {},
  busSignalsCache: {},
};

const BUS_TYPE_OPTIONS = [
  ["apb", "apb → apb3"],
  ["ahb", "ahb → ahb_lite"],
  ["axi", "axi → axi4lite"],
  ["apb2", "APB2"],
  ["apb3", "APB3"],
  ["apb4", "APB4"],
  ["apb5", "APB5"],
  ["ahb_lite", "AHB-Lite"],
  ["ahb5_lite", "AHB5-Lite"],
  ["ahb", "AHB full"],
  ["axi4lite", "AXI4-Lite"],
  ["axi3full", "AXI3 full"],
  ["axi4full", "AXI4 full"],
  ["axi5full", "AXI5 full"],
];

const $ = (sel) => document.querySelector(sel);

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok && !data.error) data.error = res.statusText;
  return data;
}

function defaultBusPort(cpu) {
  const id = cpu.cpu_id;
  const bt = (cpu.bus_type || "axi").toLowerCase();
  if (bt.includes("apb")) return `S${String(id).padStart(2, "0")}_APB`;
  if (bt.includes("ahb")) return `M${String(id).padStart(2, "0")}_AHB`;
  return `S${String(id).padStart(2, "0")}_AXI`;
}

function defaultAddrBase(cpu) {
  const samples = {
    1: "0x40000000",
    2: "0x80000000",
    3: "0xC0000000",
    37: "0x4A000000",
  };
  return samples[cpu.cpu_id] || "0x00000000";
}

function hierarchyEntry(cpu) {
  if (state.hierarchy[cpu.cpu_id]) return state.hierarchy[cpu.cpu_id];
  return {
    name: cpu.name,
    cpu_id: cpu.cpu_id,
    tap_port: cpu.tap_port ?? cpu.cpu_id - 1,
    bus_type: cpu.bus_type || "axi",
    bus_port: cpu.bus_port || defaultBusPort(cpu),
    addr_base: defaultAddrBase(cpu),
    addr_size: "0x1000",
    wired: cpu.enabled !== false && cpu.bus_type !== "task",
    signal_map: {},
  };
}

function populateBusTypeSelect() {
  const sel = $("#bus-type-select");
  sel.innerHTML = "";
  for (const [value, label] of BUS_TYPE_OPTIONS) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    sel.appendChild(opt);
  }
}

async function fetchBusSignals(busType, prefix) {
  const key = `${busType}::${prefix}`;
  if (state.busSignalsCache[key]) return state.busSignalsCache[key];
  const q = new URLSearchParams({ bus_type: busType, prefix: prefix || "" });
  const data = await api(`/api/bus-signals?${q}`);
  if (data.ok) state.busSignalsCache[key] = data;
  return data;
}

function readSignalMapFromTable() {
  const map = {};
  for (const inp of document.querySelectorAll("#sig-tbody input[data-suffix]")) {
    map[inp.dataset.suffix] = inp.value.trim();
  }
  return map;
}

function renderSignalTable(data, signalMap = {}) {
  const tbody = $("#sig-tbody");
  const meta = $("#bus-signals-meta");
  tbody.innerHTML = "";
  if (!data?.ok) {
    meta.textContent = data?.error || "unsupported bus";
    tbody.innerHTML = `<tr><td colspan="5" class="empty">${data?.error || "No signals"}</td></tr>`;
    return;
  }
  meta.textContent = `${data.bus_label} · ${data.signal_count} signals · prefix=${data.prefix || "(none)"}`;
  for (const sig of data.signals) {
    const tr = document.createElement("tr");
    const socVal = signalMap[sig.suffix] || sig.default_soc;
    tr.innerHTML = `
      <td class="grp">${sig.group}</td>
      <td class="suffix" title="${sig.note || ""}">${sig.suffix}</td>
      <td>${sig.width}</td>
      <td class="dir">${sig.dir_label}</td>
      <td><input class="soc-input" data-suffix="${sig.suffix}" value="${socVal}" placeholder="${sig.default_soc}" title="VerifCPU port: ${sig.verif_port}" /></td>
    `;
    tbody.appendChild(tr);
  }
}

async function refreshBusSignals(preserveMap = true, prevPrefix = null) {
  const form = $("#hier-form");
  if (!form || form.classList.contains("hidden")) return;
  const busType = form.bus_type.value;
  const prefix = form.bus_port.value.trim();
  const cpuId = Number(form.cpu_id.value);
  let signalMap = {};
  if (preserveMap) {
    signalMap = readSignalMapFromTable();
    if (!Object.keys(signalMap).length && state.hierarchy[cpuId]?.signal_map) {
      signalMap = { ...state.hierarchy[cpuId].signal_map };
    }
  }
  const data = await fetchBusSignals(busType, prefix);
  if (preserveMap && prevPrefix != null && prevPrefix !== prefix) {
    const oldKey = `${busType}::${prevPrefix}`;
    const oldData = state.busSignalsCache[oldKey];
    if (oldData?.ok && data.ok) {
      const merged = {};
      for (const sig of data.signals) {
        const oldSig = oldData.signals.find((s) => s.suffix === sig.suffix);
        const cur = signalMap[sig.suffix];
        if (cur && oldSig && cur !== oldSig.default_soc) {
          merged[sig.suffix] = cur;
        } else {
          merged[sig.suffix] = sig.default_soc;
        }
      }
      signalMap = merged;
    }
  }
  renderSignalTable(data, signalMap);
  form.bus_port.dataset.lastPrefix = prefix;
}

function saveFormToHierarchy() {
  const form = $("#hier-form");
  if (!form || form.classList.contains("hidden")) return;
  const fd = new FormData(form);
  const cpuId = Number(fd.get("cpu_id"));
  state.hierarchy[cpuId] = {
    name: fd.get("name"),
    cpu_id: cpuId,
    tap_port: Number(fd.get("tap_port")),
    bus_type: fd.get("bus_type"),
    bus_port: fd.get("bus_port"),
    addr_base: fd.get("addr_base"),
    addr_size: fd.get("addr_size"),
    wired: fd.get("wired") === "on",
    signal_map: readSignalMapFromTable(),
  };
}

function fillForm(cpu) {
  const h = hierarchyEntry(cpu);
  const form = $("#hier-form");
  form.classList.remove("hidden");
  form.name.value = h.name;
  form.cpu_id.value = h.cpu_id;
  form.tap_port.value = h.tap_port;
  form.bus_type.value = h.bus_type;
  form.bus_port.value = h.bus_port;
  form.addr_base.value = h.addr_base;
  form.addr_size.value = h.addr_size;
  form.wired.checked = h.wired;
  $("#editor-title").textContent = `Hierarchy — ${cpu.name} (cpu_id=${cpu.cpu_id})`;
  $("#editor-hint").textContent =
    "bus_port prefix + 아래 SoC signal 이름이 interconnect RTL과 일치해야 합니다.";
  $("#btn-generate").disabled = false;
  $("#btn-refresh-preview").disabled = false;
  refreshBusSignals(true);
}

function wiredSlaves() {
  return Object.values(state.hierarchy).filter((s) => s.wired && s.bus_port);
}

function payload() {
  return {
    soc_name: $("#soc-name").value || state.config?.default_soc_name || "my_chip",
    module_name: $("#module-name").value || state.config?.default_module_name || "tb_dut_fabric",
    slaves: wiredSlaves(),
    include_agents: false,
  };
}

function renderCpuList() {
  const ul = $("#cpu-list");
  ul.innerHTML = "";
  if (!state.cpus.length) {
    ul.innerHTML = '<li class="sub" style="cursor:default">Run Gen first.</li>';
    return;
  }
  for (const cpu of state.cpus) {
    const li = document.createElement("li");
    li.dataset.id = cpu.cpu_id;
    if (state.selectedId === cpu.cpu_id) li.classList.add("active");
    const role = cpu.role === "mvcpu" ? "mvcpu" : "scpu";
    li.innerHTML = `
      <div class="role ${role}">${role}</div>
      <div class="title">${cpu.name}</div>
      <div class="sub">id=${cpu.cpu_id} tap=${cpu.tap_port} ${cpu.bus_type || "?"} ${cpu.bus_port || ""}</div>
    `;
    li.addEventListener("click", () => {
      saveFormToHierarchy();
      state.selectedId = cpu.cpu_id;
      renderCpuList();
      fillForm(cpu);
    });
    ul.appendChild(li);
  }
}

async function loadConfig() {
  state.config = await api("/api/config");
  $("#rtl-pill").textContent = `rtl: ${state.config.rtl_root}`;
  $("#out-pill").textContent = `out: ${state.config.output_dir}`;
  $("#soc-name").value = state.config.default_soc_name || "";
  $("#module-name").value = state.config.default_module_name || "";
}

async function loadCpus() {
  const data = await api("/api/cpus");
  if (!data.ok) return;
  const cpus = [];
  if (data.manifest?.master) cpus.push(data.manifest.master);
  const slaves = data.manifest?.enabled_slaves || [];
  for (const s of slaves) cpus.push(s);
  state.cpus = cpus;
  for (const c of cpus) {
    if (!state.hierarchy[c.cpu_id]) state.hierarchy[c.cpu_id] = hierarchyEntry(c);
  }
  renderCpuList();
}

async function runGen() {
  const btn = $("#btn-gen");
  const log = $("#gen-log");
  btn.disabled = true;
  log.textContent = "Running example.sh gen …";
  const body = {
    axi: Number($("#opt-axi").value),
    ahb: Number($("#opt-ahb").value),
    apb: Number($("#opt-apb").value),
  };
  const n = $("#opt-num-scpu").value.trim();
  if (n) body.num_scpu = Number(n);
  const data = await api("/api/gen", { method: "POST", body: JSON.stringify(body) });
  log.textContent = (data.log || data.error || "done").slice(-4000);
  btn.disabled = false;
  if (data.ok) {
    state.hierarchy = {};
    if (data.manifest) {
      const cpus = [];
      if (data.manifest.master) cpus.push(data.manifest.master);
      for (const s of data.manifest.enabled_slaves || []) cpus.push(s);
      state.cpus = cpus;
      for (const c of cpus) state.hierarchy[c.cpu_id] = hierarchyEntry(c);
    } else {
      await loadCpus();
    }
    renderCpuList();
    if (state.cpus.length) {
      state.selectedId = state.cpus[0].cpu_id;
      fillForm(state.cpus[0]);
    }
  }
}

async function refreshPreview() {
  saveFormToHierarchy();
  const data = await api("/api/preview", { method: "POST", body: JSON.stringify(payload()) });
  if (data.ok) {
    $("#preview-code").textContent = data.verilog;
  } else {
    $("#preview-code").textContent = `// Error: ${data.error}`;
  }
}

async function generateTbDut() {
  saveFormToHierarchy();
  const data = await api("/api/generate-tb-dut", { method: "POST", body: JSON.stringify(payload()) });
  if (data.ok) {
    $("#preview-code").textContent = data.verilog;
    $("#gen-log").textContent = `Wrote ${data.path}`;
  } else {
    $("#gen-log").textContent = data.error || "generate failed";
  }
}

function bindFormAutosave() {
  const form = $("#hier-form");
  form.addEventListener("input", (ev) => {
    const t = ev.target;
    if (t.name === "bus_type") {
      saveFormToHierarchy();
      refreshBusSignals(false);
    } else if (t.name === "bus_port") {
      const prev = t.dataset.lastPrefix || "";
      saveFormToHierarchy();
      refreshBusSignals(true, prev);
    } else {
      saveFormToHierarchy();
    }
    clearTimeout(bindFormAutosave._t);
    bindFormAutosave._t = setTimeout(refreshPreview, 400);
  });
  $("#sig-tbody").addEventListener("input", () => {
    saveFormToHierarchy();
    clearTimeout(bindFormAutosave._t);
    bindFormAutosave._t = setTimeout(refreshPreview, 400);
  });
}

async function init() {
  populateBusTypeSelect();
  await loadConfig();
  await loadCpus();
  $("#btn-gen").addEventListener("click", runGen);
  $("#btn-refresh-preview").addEventListener("click", refreshPreview);
  $("#btn-generate").addEventListener("click", generateTbDut);
  bindFormAutosave();
}

init().catch((err) => {
  $("#gen-log").textContent = String(err);
});