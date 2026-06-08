#!/usr/bin/env python3
"""
DQL Explorer Server - Interactive HTML UI powered 100% by the pure Python Lark DQL engine.

Run:
    python demo/dql_explorer_server.py

Then open http://localhost:8765 in your browser.

Features:
- Real-time DQL queries using tools.dql_python (python-full engine)
- B-mode port expansion toggle
- Load your own JSON design data
- Search history
- Clean, modern UI similar to professional hierarchy explorers
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# Make sure we can import our engine
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from tools.dql_python import query_dql, matches_dql
    from tools.dql_python.parser import parse_dql, ast_to_dict
except ImportError:
    print("ERROR: Could not import tools.dql_python. Run from project root.")
    sys.exit(1)

PORT = 8765
DEFAULT_DATASETS = {
    "tiny": ROOT / "demo_data" / "tiny_soc.json",
    "large": ROOT / "demo_data" / "large_soc_1000.json",
}

# In-memory current dataset (can be replaced via UI)
CURRENT_INSTANCES = []
CURRENT_DATASET_NAME = "tiny"


def load_dataset(name: str = "tiny"):
    global CURRENT_INSTANCES, CURRENT_DATASET_NAME
    path = DEFAULT_DATASETS.get(name, DEFAULT_DATASETS["tiny"])
    if path.exists():
        data = json.loads(path.read_text())
        if isinstance(data, dict) and "instances" in data:
            data = data["instances"]
        CURRENT_INSTANCES = data if isinstance(data, list) else []
        CURRENT_DATASET_NAME = name
        print(f"Loaded dataset '{name}' with {len(CURRENT_INSTANCES)} instances")
    else:
        CURRENT_INSTANCES = []
        CURRENT_DATASET_NAME = name
        print(f"Dataset '{name}' not found")


class DQLHandler(BaseHTTPRequestHandler):
    def _send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, html: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        global CURRENT_INSTANCES
        path = urlparse(self.path).path

        # Serve the original rich JS explorer, but with Python engine injected
        if path == "/" or path == "/index.html" or path == "/hierarchy_explorer.html":
            self.serve_original_explorer_with_python_engine()
            return

        if path == "/data":
            self._send_json({"instances": CURRENT_INSTANCES, "count": len(CURRENT_INSTANCES)})
            return

        if path == "/debug/ast":
            q = parse_qs(urlparse(self.path).query).get("q", [""])[0]
            try:
                from tools.dql_python.parser import parse_dql, ast_to_dict
                ast = parse_dql(q)
                self._send_json({"ok": True, "ast": ast_to_dict(ast)})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)})
            return

        # Serve static data files (large_soc_1000.json, instances.json, etc.)
        # This fixes the "Test dataset 로드 실패 HTTP 404" issue
        if path.startswith("/demo_data/"):
            self.serve_static_file(path)
            return

        # Also support direct access to common data files at root for compatibility
        if path in ("/instances.json", "/large_soc_1000.json", "/modules.json"):
            self.serve_static_file("/demo_data" + path)
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        global CURRENT_INSTANCES, CURRENT_DATASET_NAME
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"

        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if path == "/query":
            query = payload.get("query", "").strip()
            port_mode = bool(payload.get("port_mode", False))

            try:
                results = query_dql(query, CURRENT_INSTANCES, port_mode=port_mode)
                self._send_json({
                    "ok": True,
                    "query": query,
                    "port_mode": port_mode,
                    "count": len(results),
                    "results": results
                })
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=400)
            return

        if path == "/load":
            # Accept new dataset
            new_data = payload.get("instances")
            if isinstance(new_data, list):
                CURRENT_INSTANCES = new_data
                CURRENT_DATASET_NAME = payload.get("name", "custom")
                self._send_json({"ok": True, "loaded": len(new_data), "name": CURRENT_DATASET_NAME})
            else:
                self._send_json({"ok": False, "error": "instances must be a list"}, status=400)
            return

        if path == "/dataset":
            name = payload.get("name", "tiny")
            load_dataset(name)
            self._send_json({
                "ok": True,
                "name": CURRENT_DATASET_NAME,
                "count": len(CURRENT_INSTANCES)
            })
            return

        # === New API for original hierarchy_explorer.html to use our Python engine ===
        if path == "/api/matches":
            # For single instance matching (used by original JS matchesDQL)
            query = payload.get("query", "")
            context = payload.get("context", {})
            try:
                # Convert to our internal instance format
                inst = {
                    "name": context.get("name", ""),
                    "module": context.get("moduleName", ""),
                    "ports": context.get("ports", []),
                    "file": context.get("filepath", ""),
                }
                result = matches_dql(query, inst)
                self._send_json({"ok": True, "result": result})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=400)
            return

        if path == "/api/query":
            # Full query with optional B-mode (port expansion)
            query = payload.get("query", "")
            port_mode = bool(payload.get("port_mode", False))
            try:
                results = query_dql(query, CURRENT_INSTANCES, port_mode=port_mode)
                self._send_json({
                    "ok": True,
                    "query": query,
                    "port_mode": port_mode,
                    "count": len(results),
                    "results": results
                })
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=400)
            return

        if path == "/api/datasets":
            self._send_json({
                "ok": True,
                "datasets": [
                    {"name": "tiny", "count": 8, "label": "Tiny Demo"},
                    {"name": "large", "count": len(CURRENT_INSTANCES) if CURRENT_DATASET_NAME == "large" else 1039, "label": "Large (1000+)"},
                ],
                "current": CURRENT_DATASET_NAME
            })
            return

        self.send_error(404, "Not Found")

    def serve_original_explorer_with_python_engine(self):
        """Redirect to our pure-Python replica that matches the JS UI look (no original JS DQL at all)."""
        # For now, serve our high-fidelity Python-only replica instead of the original HTML
        self._send_html(self._build_html())

    def serve_static_file(self, web_path: str):
        """Safely serve files from demo_data/ directory."""
        # web_path example: /demo_data/large_soc_1000.json
        relative_path = web_path.lstrip('/')
        file_path = ROOT / relative_path

        # Security: only allow files inside demo_data/
        try:
            file_path = file_path.resolve()
            demo_data_dir = (ROOT / "demo_data").resolve()
            if not str(file_path).startswith(str(demo_data_dir)):
                self.send_error(403, "Forbidden")
                return
        except Exception:
            self.send_error(404, "Not Found")
            return

        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "Not Found")
            return

        try:
            content = file_path.read_bytes()
            # Simple content type detection
            if file_path.suffix == ".json":
                content_type = "application/json"
            elif file_path.suffix in (".html", ".htm"):
                content_type = "text/html"
            else:
                content_type = "application/octet-stream"

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")

    def _build_html(self) -> str:
        """Modern, self-contained explorer UI (Tailwind via CDN for beauty)."""
        return """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DQL Explorer — Python Lark Engine</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; }
        .result-row:hover { background-color: #f8fafc; }
        .hierarchy { font-family: ui-monospace, monospace; }
        .port { background-color: #fef3c7; padding: 1px 6px; border-radius: 3px; font-size: 0.75rem; }
    </style>
</head>
<body class="bg-[#0f172a] text-[#e2e8f0]">
<div class="h-screen flex flex-col">
    <!-- Top bar matching screenshot style -->
    <div class="flex items-center gap-3 mb-3">
        <div class="font-semibold text-xl">SoC Hierarchy Explorer</div>
        
        <input id="query" value='module ~ "uart" AND port ~ "irq"' 
               class="flex-1 bg-[#1e293b] border border-[#475569] rounded px-3 py-1.5 text-sm mono focus:outline-none">
        
        <button onclick="runQuery()" class="bg-[#3b82f6] hover:bg-[#2563eb] px-4 py-1.5 rounded text-sm font-medium">Search</button>
        <button onclick="clearSearch()" class="bg-[#334155] hover:bg-[#475569] px-3 py-1.5 rounded text-sm">Clear</button>
        <button onclick="saveJSON()" class="bg-[#334155] hover:bg-[#475569] px-3 py-1.5 rounded text-sm">Save JSON</button>
        <button onclick="showLoadModal()" class="bg-[#334155] hover:bg-[#475569] px-3 py-1.5 rounded text-sm">Open as JSON</button>
        
        <button onclick="switchDataset('large')" 
                class="bg-[#166534] hover:bg-[#15803d] px-3 py-1.5 rounded text-sm flex items-center gap-1">
            Load Large Test (1000+)
            <span id="count-badge" class="bg-[#15803d] text-xs px-1.5 rounded">1039</span>
        </button>
    </div>

    <!-- History chips -->
    <div class="mb-3 flex gap-2 text-sm" id="history"></div>

    <!-- Main layout with left Hierarchy Tree -->
    <div class="flex flex-1 gap-2 overflow-hidden">
        <!-- LEFT: Hierarchy Explorer (as requested) -->
        <div class="w-80 bg-[#1e293b] border border-[#334155] rounded flex flex-col">
            <div class="px-3 py-1 text-sm font-medium border-b border-[#334155]">Hierarchy (Explorer View)</div>
            <div id="hierarchy-tree" class="flex-1 overflow-auto p-2 text-sm"></div>
        </div>

        <!-- CENTER + RIGHT (existing results + source) -->
        <div class="flex-1 flex gap-2">
    <div class="bg-white border border-slate-200 rounded-xl p-5 shadow-sm mb-4">
        <div class="flex gap-3 items-end flex-wrap">
            <!-- Query -->
            <div class="flex-1 min-w-[320px]">
                <label class="block text-xs font-medium text-slate-600 mb-1">DQL Query (JIRA JQL style)</label>
                <input id="query" type="text" 
                       class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500 font-mono text-sm"
                       placeholder='module ~ "uart*" AND port ~ "irq"' 
                       value='module ~ "uart*" AND port ~ "irq"'>
            </div>

            <!-- B-mode -->
            <div class="flex items-center gap-2 pb-1">
                <input type="checkbox" id="port_mode" class="w-4 h-4 accent-indigo-600">
                <label for="port_mode" class="text-sm text-slate-700 select-none">B-mode (port expansion)</label>
            </div>

            <button onclick="runQuery()" 
                    class="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white rounded-lg text-sm font-medium transition">
                Run Query
            </button>

            <button onclick="loadDefaultData()" 
                    class="px-4 py-2.5 border border-slate-300 hover:bg-slate-100 rounded-lg text-sm">
                Load Default
            </button>
            <button onclick="switchDataset('large')" 
                    class="px-4 py-2.5 bg-emerald-700 hover:bg-emerald-600 rounded-lg text-sm text-white">
                Load Large Test (1000+)
            </button>
        </div>

        <!-- History -->
        <div class="mt-3 text-xs text-slate-500">
            History: <span id="history" class="text-indigo-600"></span>
        </div>
    </div>

    <!-- Data info + Dataset selector (closer to original JS explorer) -->
    <div class="flex items-center gap-4 mb-4 text-sm flex-wrap">
        <div class="px-3 py-1 bg-white border border-slate-200 rounded-lg text-slate-600">
            Loaded: <span id="data_count" class="font-semibold text-slate-900">0</span> instances
            <span id="current_dataset" class="ml-2 px-2 py-0.5 text-xs rounded bg-slate-200 text-slate-700"></span>
        </div>

        <div class="flex gap-2">
            <button onclick="switchDataset('tiny')" 
                    class="px-3 py-1 text-sm border border-slate-300 hover:bg-slate-100 rounded">Tiny</button>
            <button onclick="switchDataset('large')" 
                    class="px-3 py-1 text-sm border border-slate-300 hover:bg-slate-100 rounded font-medium">Large (1000+)</button>
            <button onclick="showLoadModal()" 
                    class="px-3 py-1 text-sm border border-slate-300 hover:bg-slate-100 rounded">Load JSON...</button>
        </div>
    </div>

    <!-- Results + Detail (closer to original JS explorer layout) -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <!-- Results -->
        <div class="lg:col-span-2 bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            <div class="px-5 py-3 border-b border-slate-200 flex items-center justify-between bg-slate-50">
                <div class="font-medium text-slate-700 flex items-center gap-2">
                    Results <span id="result_count" class="text-slate-400 font-normal"></span>
                    <span id="bmode_badge" class="hidden text-[10px] px-2 py-0.5 rounded bg-emerald-100 text-emerald-700">B-MODE</span>
                </div>
            </div>
            <div id="results_table" class="overflow-auto max-h-[520px] text-sm"></div>
        </div>

        <!-- Detail / Source pane (simulating original JS explorer) -->
        <div class="bg-white border border-slate-200 rounded-xl shadow-sm">
            <div class="px-4 py-2 border-b bg-slate-50 text-sm font-medium text-slate-600">Detail / Source View</div>
            <div id="detail_pane" class="p-4 text-sm text-slate-500 min-h-[200px]">
                Click a B-mode result row to see details.<br>
                Goal: Show full source code here with the selected port highlighted (matching original JS explorer).
            </div>
        </div>
    </div>

    <div class="mt-6 text-[10px] text-slate-400">
        Engine: tools/dql_python (Lark) — targeting full equivalence with original JS hierarchy_explorer.html.<br>
        Fields: <b>inst</b> (instance/hierarchy name), <b>module</b>, <b>file</b>, <b>port</b>. Use <code>inst ~ "pattern"</code> to search by instance name.
    </div>
</div>

<!-- Load Modal -->
<div id="load_modal" onclick="hideLoadModal()" class="hidden fixed inset-0 bg-black/40 flex items-center justify-center">
    <div onclick="event.stopImmediatePropagation()" class="bg-white rounded-xl p-6 w-[460px]">
        <h3 class="font-semibold mb-3">Load Your Design Data (JSON array of instances)</h3>
        <textarea id="json_input" class="w-full h-40 font-mono text-xs border border-slate-300 rounded p-3" 
                  placeholder='[{"name":"soc.uart0", "module":"uart", "ports":["clk","irq"]}, ...]'></textarea>
        <div class="flex gap-2 mt-3">
            <button onclick="loadFromTextarea()" class="flex-1 py-2 bg-indigo-600 text-white rounded">Load</button>
            <button onclick="hideLoadModal()" class="flex-1 py-2 border border-slate-300 rounded">Cancel</button>
        </div>
    </div>
</div>

<script>
let searchHistory = [];

function updateHistory() {
    const el = document.getElementById('history');
    el.innerHTML = searchHistory.slice(-5).reverse().map(q => 
        `<span onclick="useHistory('${q}')" class="cursor-pointer hover:underline">${q}</span>`
    ).join(' • ');
}

function useHistory(q) {
    document.getElementById('query').value = q;
    runQuery();
}

async function runQuery() {
    const query = document.getElementById('query').value.trim();
    const portMode = document.getElementById('port_mode').checked;

    if (!query && !confirm("Empty query will return all instances. Continue?")) return;

    try {
        const res = await fetch('/query', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ query, port_mode: portMode })
        });
        const data = await res.json();

        if (!data.ok) {
            alert("Error: " + data.error);
            return;
        }

        renderResults(data.results, portMode);

        // history
        if (query && !searchHistory.includes(query)) {
            searchHistory.push(query);
            if (searchHistory.length > 8) searchHistory.shift();
            updateHistory();
        }
    } catch (e) {
        alert("Request failed: " + e);
    }
}

function renderResults(results, isPortMode) {
    const container = document.getElementById('results_table');
    const countEl = document.getElementById('result_count');
    countEl.textContent = `(${results.length})`;

    const badge = document.getElementById('bmode_badge');
    if (badge) badge.classList.toggle('hidden', !isPortMode);

    if (results.length === 0) {
        container.innerHTML = `<div class="p-8 text-center text-slate-400">No matches</div>`;
        return;
    }

    let html = `<table class="w-full text-sm">
        <thead>
            <tr class="bg-slate-100 text-left text-xs font-medium text-slate-600">
                <th class="px-4 py-2">Hierarchy</th>
                <th class="px-3 py-2">Module</th>
                <th class="px-3 py-2">File</th>
                <th class="px-3 py-2">Matched Port</th>
            </tr>
        </thead><tbody>`;

    results.forEach((r, idx) => {
        const hierarchy = r.hierarchy || r.name || r.module || '(unknown)';
        const isPortRow = !!r._port || (hierarchy.includes('.') && isPortMode);
        const mod = r.module || '';
        const file = (r.file || '').split('/').pop() || '';
        const matchedP = r._port || (isPortRow ? hierarchy.split('.').pop() : '');

        html += `
            <tr onclick="selectResult(${idx}, ${JSON.stringify(r).replace(/"/g, '&quot;')})"
                class="result-row border-t border-slate-200 hover:bg-indigo-50 cursor-pointer ${isPortRow ? 'bg-amber-50' : ''}">
                <td class="px-4 py-2 font-medium hierarchy text-slate-800">${hierarchy}</td>
                <td class="px-3 py-2 font-mono text-xs text-slate-600">${mod}</td>
                <td class="px-3 py-2 text-xs text-slate-500 truncate max-w-[180px]">${file}</td>
                <td class="px-3 py-2">
                    ${matchedP ? `<span class="inline-block px-2 py-0.5 text-xs rounded bg-emerald-100 text-emerald-700 font-medium">${matchedP}</span>` : '-'}
                </td>
            </tr>`;
    });

    html += '</tbody></table>';
    container.innerHTML = html;

    // Store results for selection
    window.currentResults = results;
}

function selectResult(index, result) {
    const detail = document.getElementById('detail_pane');
    if (!detail) return;

    const h = result.hierarchy || result.name || result.module;
    const mod = result.module || '';
    const ports = (result.ports || []).join(', ');

    detail.innerHTML = `
        <div class="p-4 border border-slate-200 rounded-lg bg-white">
            <div class="text-xs text-slate-500 mb-1">SELECTED</div>
            <div class="font-semibold text-lg mb-2">${h}</div>
            <div class="grid grid-cols-2 gap-x-4 text-sm">
                <div><span class="text-slate-500">Module:</span> <span class="font-mono">${mod}</span></div>
                <div><span class="text-slate-500">File:</span> <span class="text-xs">${result.file || '-'}</span></div>
            </div>
            <div class="mt-3">
                <div class="text-xs text-slate-500 mb-1">Ports</div>
                <div class="flex flex-wrap gap-1 text-xs">
                    ${(result.ports || []).map(p => 
                        `<span class="px-2 py-0.5 rounded ${p === result._port ? 'bg-emerald-200 font-medium' : 'bg-slate-100'}">${p}</span>`
                    ).join('')}
                </div>
            </div>
            <div class="mt-3 text-[10px] text-slate-400">Click another row to inspect. In real JS explorer this would highlight in the source view.</div>
        </div>
    `;
}

async function loadDefaultData() {
    const res = await fetch('/data');
    const data = await res.json();
    window.CURRENT_COUNT = data.count;
    document.getElementById('data_count').textContent = data.count;
    updateDatasetBadge();

    // Run a default interesting query
    document.getElementById('query').value = 'inst ~ "*uart*" AND port ~ "irq"';
    document.getElementById('port_mode').checked = true;
    await runQuery();
}

async function switchDataset(name) {
    const res = await fetch('/dataset', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name })
    });
    const data = await res.json();
    if (data.ok) {
        document.getElementById('data_count').textContent = data.count;
        updateDatasetBadge(data.name);
        // Re-run current query or default
        await runQuery();
    }
}

function updateDatasetBadge(name) {
    const el = document.getElementById('current_dataset');
    if (el) {
        const n = name || (window.currentDatasetName || 'tiny');
        el.textContent = n === 'large' ? 'Large (1000+)' : (n === 'tiny' ? 'Tiny' : n);
        window.currentDatasetName = n;
    }
}

function showLoadModal() {
    document.getElementById('load_modal').classList.remove('hidden');
    document.getElementById('load_modal').classList.add('flex');
}

function hideLoadModal() {
    document.getElementById('load_modal').classList.remove('flex');
    document.getElementById('load_modal').classList.add('hidden');
}

async function loadFromTextarea() {
    const text = document.getElementById('json_input').value.trim();
    try {
        const instances = JSON.parse(text);
        if (!Array.isArray(instances)) throw new Error("Must be JSON array");
        
        const res = await fetch('/load', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ instances })
        });
        const data = await res.json();
        if (data.ok) {
            hideLoadModal();
            document.getElementById('data_count').textContent = data.loaded;
            alert(`Loaded ${data.loaded} instances. Run a query to see results.`);
        } else {
            alert("Load failed: " + data.error);
        }
    } catch (e) {
        alert("Invalid JSON: " + e.message);
    }
}

function buildTree(instances) {
    const root = {};
    instances.forEach(inst => {
        const name = inst.name || '';
        const parts = name.split('.');
        let node = root;
        parts.forEach((part, idx) => {
            if (!node[part]) {
                node[part] = { children: {}, full: parts.slice(0, idx+1).join('.') };
            }
            node = node[part].children;
        });
    });
    return root;
}

function renderTree(node, container, path = '') {
    container.innerHTML = '';
    const ul = document.createElement('ul');
    ul.style.listStyle = 'none';
    ul.style.paddingLeft = '0';

    function add(obj, parent, currentPath) {
        Object.keys(obj).sort().forEach(key => {
            const li = document.createElement('li');
            const full = currentPath ? currentPath + '.' + key : key;
            li.textContent = key;
            li.style.padding = '1px 4px';
            li.style.cursor = 'pointer';
            li.dataset.path = full;

            const hasKids = Object.keys(obj[key].children).length > 0;
            if (hasKids) li.style.fontWeight = '500';

            li.onclick = (e) => {
                e.stopImmediatePropagation();
                if (hasKids) {
                    const kids = li.querySelector('ul');
                    if (kids) kids.style.display = kids.style.display === 'none' ? '' : 'none';
                } else {
                    filterResultsToPath(full);
                }
            };

            parent.appendChild(li);

            if (hasKids) {
                const childUl = document.createElement('ul');
                childUl.style.display = 'none';
                childUl.style.paddingLeft = '14px';
                add(obj[key].children, childUl, full);
                li.appendChild(childUl);
            }
        });
    }
    add(node, ul, '');
    container.appendChild(ul);
}

function filterResultsToPath(path) {
    const filtered = currentResults.filter(r => (r.name || '').startsWith(path));
    const c = document.getElementById('results');
    c.innerHTML = filtered.map(r => `<div class="px-2 py-1 border-b border-[#334155]">${r.name}</div>`).join('');
}

async function init() {
    await loadDefaultData();
    updateHistory();

    // Build left hierarchy tree
    const res = await fetch('/data');
    const d = await res.json();
    const tree = buildTree(d.instances || []);
    renderTree(tree, document.getElementById('hierarchy-tree'));

    setTimeout(() => {
        const q = document.getElementById('query');
        if (q.value) runQuery();
    }, 300);
}

window.onload = init;
</script>
</body>
</html>"""


def run_server():
    load_dataset("tiny")
    server = HTTPServer(("", PORT), DQLHandler)
    print(f"\n✅ DQL Explorer ready — Original UI + Python Lark Engine")
    print(f"   Open in browser: http://localhost:{PORT}")
    print(f"   This serves the original hierarchy_explorer.html with Python backend.")
    print(f"   Available datasets: tiny / large (1000+)")
    print(f"   Current data   : {len(CURRENT_INSTANCES)} instances\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")


if __name__ == "__main__":
    run_server()
