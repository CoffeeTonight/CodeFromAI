#!/usr/bin/env python3
"""
I3C Dual-Bus SoC Educational Simulator
- Runs pure-Python I3C protocol model (no external deps)
- Serves a rich, self-contained HTML5 visualizer via stdlib http.server
- Features: dual waveform canvases, transaction table + interpretation,
  playhead animation, zoom/scrub, SoC diagram, export

Run:
    python3 server.py
Then open the URL shown (usually http://localhost:8088)
"""

from __future__ import annotations
import json
import threading
import webbrowser
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from i3c_model import build_soc_scenario

PORT = 8088
HOST = "127.0.0.1"

# Cache last trace so re-runs from UI are fast and we can serve it statically too
LAST_TRACE = None
TRACE_LOCK = threading.Lock()

HTML_PAGE = r'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>I3C 시뮬레이터 • Dual-Bus SoC</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&amp;family=JetBrains+Mono:wght@400;500&amp;display=swap');
  
  :root { --primary: #3b82f6; }
  
  body { font-family: 'Inter', system_ui, sans-serif; }
  .mono { font-family: 'JetBrains Mono', ui-monospace, monospace; }
  
  .waveform-canvas {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    cursor: crosshair;
  }
  
  .section-title {
    font-size: 0.75rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    font-weight: 600;
    color: #64748b;
  }

  .tx-row {
    transition: all 0.1s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .tx-row:hover { background-color: #1e2937; }
  .tx-row.active {
    background-color: #1e40af;
    color: white;
    font-weight: 500;
  }
  .tx-row.active td { color: #e0e7ff; }

  .sig-high { stroke: #22c55e; stroke-width: 2.5; }
  .sig-low  { stroke: #ef4444; stroke-width: 2.5; }
  
  .playhead {
    stroke: #f59e0b;
    stroke-width: 2.5;
    stroke-dasharray: 6 3;
  }

  .bus-label {
    writing-mode: vertical-rl;
    transform: rotate(180deg);
    font-size: 10px;
    letter-spacing: 1px;
  }

  .legend-dot {
    width: 10px; height: 10px; border-radius: 2px;
  }

  .proto-badge {
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 9999px;
    font-weight: 600;
  }

  .metric {
    font-variant-numeric: tabular-nums;
  }

  .wave-note {
    font-size: 9px;
    fill: #94a3b8;
    font-family: 'JetBrains Mono', monospace;
  }

  .soc-box {
    transition: transform 0.2s ease, box-shadow 0.2s ease;
  }
  .soc-box:hover {
    transform: translateY(-1px);
    box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1);
  }

  .transaction-table {
    font-size: 13px;
  }
  
  .time-ruler {
    font-size: 10px;
    fill: #64748b;
  }

  .i3c-green { color: #22c55e; }
  .i3c-blue  { color: #3b82f6; }
  .i3c-purple { color: #a855f7; }
  .i3c-amber { color: #f59e0b; }
  .i3c-red   { color: #ef4444; }
</style>
</head>
<body class="bg-slate-950 text-slate-200">
  <div class="max-w-[1480px] mx-auto">
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
      <div class="flex items-center gap-x-3">
        <div class="flex items-center gap-x-2">
          <div class="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center">
            <span class="text-white font-bold text-2xl tracking-tighter">I3C</span>
          </div>
          <div>
            <h1 class="text-2xl font-semibold tracking-tight">I3C Protocol Visualizer</h1>
            <p class="text-[11px] text-slate-500 -mt-0.5">MIPI I3C SDR • Dual-Bus SoC Educational Simulator</p>
          </div>
        </div>
        <div class="ml-3 px-3 py-1 bg-slate-900 border border-slate-800 rounded-full text-xs flex items-center gap-x-2">
          <div class="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></div>
          <span class="text-emerald-400 font-medium">Python 모델 기반</span>
        </div>
      </div>

      <div class="flex items-center gap-x-2">
        <button onclick="rerunSimulation()"
                class="flex items-center gap-x-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 active:bg-slate-900 transition-colors border border-slate-700 rounded-xl text-sm font-medium">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.058 11H1M12 3v2m0 16v2m9-9H15m-6 0a8 8 0 01-.936-1.072" />
          </svg>
          <span>재시뮬레이션</span>
        </button>
        
        <button onclick="exportTrace()"
                class="flex items-center gap-x-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 transition-colors border border-slate-700 rounded-xl text-sm font-medium">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 13v6m-3-3h6M6 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4l2 2h6a2 2 0 012 2v3" />
          </svg>
          <span>JSON 내보내기</span>
        </button>

        <button onclick="showHelp()"
                class="px-4 py-2 text-sm font-medium text-slate-400 hover:text-slate-200 transition-colors">도움말</button>
      </div>
    </div>

    <div class="p-6 space-y-6">
      <!-- SoC Topology -->
      <div>
        <div class="section-title mb-2 px-1">SoC Topology</div>
        <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5">
          <div class="flex items-center justify-center gap-x-8">
            <!-- Host -->
            <div class="soc-box bg-slate-950 border border-slate-700 rounded-2xl px-5 py-3 w-40 text-center">
              <div class="text-xs text-slate-400">HOST SoC</div>
              <div class="font-semibold text-lg tracking-tight">Application<br>Processor</div>
              <div class="mt-1 text-[10px] text-blue-400">I3C Master × 2</div>
            </div>

            <!-- Arrow -->
            <div class="text-slate-600">→</div>

            <!-- Bus 0 -->
            <div class="flex flex-col items-center">
              <div class="soc-box bg-slate-800 border border-blue-700/70 rounded-2xl px-4 py-2 text-center w-[170px]">
                <div class="flex items-center justify-center gap-x-1.5">
                  <div class="w-2 h-2 bg-blue-400 rounded-full"></div>
                  <span class="font-semibold text-blue-300 text-sm">I3C Controller 0</span>
                </div>
                <div class="text-[10px] text-blue-400/70">Primary Sensor Bus</div>
              </div>
              <div class="h-5 w-px bg-blue-800"></div>
              <div class="flex gap-x-3">
                <div class="bg-slate-950 border border-blue-700/50 rounded-xl px-3 py-1.5 text-center">
                  <div class="text-[10px] text-blue-400">DA 0x08</div>
                  <div class="text-xs font-medium">TempSensor</div>
                  <div class="text-[10px] text-emerald-400">I3C</div>
                </div>
                <div class="bg-slate-950 border border-blue-700/50 rounded-xl px-3 py-1.5 text-center">
                  <div class="text-[10px] text-blue-400">DA 0x09</div>
                  <div class="text-xs font-medium">IMU_Accel</div>
                  <div class="text-[10px] text-amber-400">Legacy I²C</div>
                </div>
              </div>
            </div>

            <!-- Bus 1 -->
            <div class="flex flex-col items-center">
              <div class="soc-box bg-slate-800 border border-violet-700/70 rounded-2xl px-4 py-2 text-center w-[170px]">
                <div class="flex items-center justify-center gap-x-1.5">
                  <div class="w-2 h-2 bg-violet-400 rounded-full"></div>
                  <span class="font-semibold text-violet-300 text-sm">I3C Controller 1</span>
                </div>
                <div class="text-[10px] text-violet-400/70">Peripheral Bus</div>
              </div>
              <div class="h-5 w-px bg-violet-800"></div>
              <div class="flex gap-x-3">
                <div class="bg-slate-950 border border-violet-700/50 rounded-xl px-3 py-1.5 text-center">
                  <div class="text-[10px] text-violet-400">DA 0x08</div>
                  <div class="text-xs font-medium">PressureSensor</div>
                  <div class="text-[10px] text-emerald-400">I3C</div>
                </div>
                <div class="bg-slate-950 border border-violet-700/50 rounded-xl px-3 py-1.5 text-center">
                  <div class="text-[10px] text-violet-400">DA 0x09</div>
                  <div class="text-xs font-medium">ActuatorCtrl</div>
                  <div class="text-[10px] text-emerald-400">I3C</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Waveforms -->
      <div class="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <!-- Bus 0 Waveform -->
        <div class="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
          <div class="px-4 py-3 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
            <div class="flex items-center gap-x-2">
              <div class="w-3 h-3 bg-blue-400 rounded"></div>
              <div>
                <span class="font-semibold">I3C Bus 0</span>
                <span class="ml-2 text-xs text-slate-400">Primary Sensor Bus</span>
              </div>
            </div>
            <div class="flex items-center gap-x-3 text-xs">
              <div class="flex items-center gap-x-1">
                <span class="text-slate-400">Devices:</span>
                <span id="bus0-devices" class="font-medium text-blue-300 mono">2</span>
              </div>
              <div onclick="zoomWaveform(0, 0.8)" class="cursor-pointer px-2 py-0.5 bg-slate-800 hover:bg-slate-700 rounded text-[10px]">−</div>
              <div onclick="zoomWaveform(0, 1.25)" class="cursor-pointer px-2 py-0.5 bg-slate-800 hover:bg-slate-700 rounded text-[10px]">+</div>
              <div onclick="resetZoom(0)" class="cursor-pointer px-2 py-0.5 bg-slate-800 hover:bg-slate-700 rounded text-[10px]">reset</div>
            </div>
          </div>
          <div class="p-3 bg-[#0b1120]">
            <canvas id="wave0" class="waveform-canvas w-full" height="148" width="720"></canvas>
            <div class="flex justify-between text-[10px] text-slate-500 px-1 mt-1">
              <div>SDA / SCL</div>
              <div id="bus0-time-range" class="mono"></div>
            </div>
          </div>
        </div>

        <!-- Bus 1 Waveform -->
        <div class="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
          <div class="px-4 py-3 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
            <div class="flex items-center gap-x-2">
              <div class="w-3 h-3 bg-violet-400 rounded"></div>
              <div>
                <span class="font-semibold">I3C Bus 1</span>
                <span class="ml-2 text-xs text-slate-400">Peripheral Bus</span>
              </div>
            </div>
            <div class="flex items-center gap-x-3 text-xs">
              <div class="flex items-center gap-x-1">
                <span class="text-slate-400">Devices:</span>
                <span id="bus1-devices" class="font-medium text-violet-300 mono">2</span>
              </div>
              <div onclick="zoomWaveform(1, 0.8)" class="cursor-pointer px-2 py-0.5 bg-slate-800 hover:bg-slate-700 rounded text-[10px]">−</div>
              <div onclick="zoomWaveform(1, 1.25)" class="cursor-pointer px-2 py-0.5 bg-slate-800 hover:bg-slate-700 rounded text-[10px]">+</div>
              <div onclick="resetZoom(1)" class="cursor-pointer px-2 py-0.5 bg-slate-800 hover:bg-slate-700 rounded text-[10px]">reset</div>
            </div>
          </div>
          <div class="p-3 bg-[#0b1120]">
            <canvas id="wave1" class="waveform-canvas w-full" height="148" width="720"></canvas>
            <div class="flex justify-between text-[10px] text-slate-500 px-1 mt-1">
              <div>SDA / SCL</div>
              <div id="bus1-time-range" class="mono"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Playback Controls -->
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-4">
        <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
          <div class="flex items-center gap-x-2">
            <button onclick="togglePlay()" id="play-btn"
                    class="flex items-center justify-center w-11 h-11 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 transition-colors rounded-2xl shadow-inner">
              <svg id="play-icon" xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
              <svg id="pause-icon" xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 hidden" fill="currentColor" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
            </button>
            <button onclick="resetPlayback()" 
                    class="px-3 py-2 text-sm rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700">초기화</button>
          </div>

          <div class="flex-1 min-w-[240px]">
            <input type="range" id="time-scrubber" min="0" max="100" step="0.1" value="0"
                   class="w-full accent-amber-500" oninput="onScrubberInput()">
            <div class="flex justify-between text-[10px] text-slate-500 mt-1 px-0.5">
              <div>0</div>
              <div id="current-time" class="mono font-medium text-amber-400">0</div>
              <div id="max-time" class="mono"></div>
            </div>
          </div>

          <div class="flex items-center gap-x-4 text-sm">
            <div>
              <span class="text-slate-400">Speed</span>
              <select id="speed-select" onchange="updatePlaybackSpeed()" class="bg-slate-950 border border-slate-700 rounded-lg text-xs px-2 py-1 ml-1.5">
                <option value="0.5">0.5×</option>
                <option value="1" selected>1×</option>
                <option value="2">2×</option>
                <option value="4">4×</option>
                <option value="8">8×</option>
              </select>
            </div>
            <div class="text-xs px-3 py-1 bg-slate-800 border border-slate-700 rounded-xl text-slate-300">
              <span id="tx-count">0</span> transactions
            </div>
          </div>
        </div>
      </div>

      <!-- Transactions + Interpretation -->
      <div class="grid grid-cols-1 lg:grid-cols-5 gap-5">
        <!-- Transaction List -->
        <div class="lg:col-span-3 bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
          <div class="px-4 py-3 bg-slate-950/60 border-b border-slate-800 flex items-center justify-between">
            <div class="font-semibold flex items-center gap-x-2">
              <span>Transaction Trace</span>
              <span id="tx-filter-count" class="text-xs bg-slate-800 px-2 py-px rounded text-slate-400 font-normal"></span>
            </div>
            <div class="flex items-center gap-x-2 text-xs">
              <button onclick="filterTransactions('all')" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 active:bg-slate-900" id="filter-all">전체</button>
              <button onclick="filterTransactions(0)" class="px-2.5 py-1 rounded-lg hover:bg-blue-900/60" id="filter-0">Bus 0</button>
              <button onclick="filterTransactions(1)" class="px-2.5 py-1 rounded-lg hover:bg-violet-900/60" id="filter-1">Bus 1</button>
              <button onclick="filterTransactions('HOST_BRIDGE')" class="px-2.5 py-1 rounded-lg hover:bg-amber-900/60 text-amber-300" id="filter-bridge">Bridge</button>
            </div>
          </div>

          <div class="overflow-auto max-h-[380px] transaction-table">
            <table class="w-full">
              <thead class="sticky top-0 bg-slate-900 z-10 text-xs text-slate-400">
                <tr>
                  <th class="text-left pl-4 py-2 w-8">#</th>
                  <th class="text-left py-2">Bus</th>
                  <th class="text-left py-2">Kind</th>
                  <th class="text-left py-2">Details</th>
                  <th class="text-left py-2 pr-4">Time</th>
                </tr>
              </thead>
              <tbody id="tx-tbody" class="text-sm divide-y divide-slate-800"></tbody>
            </table>
          </div>
        </div>

        <!-- Interpretation Panel -->
        <div class="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl flex flex-col">
          <div class="px-4 py-3 bg-slate-950/60 border-b border-slate-800">
            <span class="font-semibold">Transaction Interpretation</span>
          </div>
          <div class="p-4 flex-1 overflow-auto" id="interp-panel">
            <div class="text-slate-400 text-sm italic" id="interp-placeholder">
              트랜잭션을 클릭하면 상세 해석이 여기에 표시됩니다.
            </div>
            <div id="interp-content" class="hidden space-y-3">
              <div>
                <div class="text-xs text-slate-400">TYPE</div>
                <div id="interp-kind" class="font-semibold text-lg"></div>
              </div>
              <div>
                <div class="text-xs text-slate-400">INTERPRETATION</div>
                <div id="interp-text" class="text-sm leading-relaxed text-slate-200"></div>
              </div>
              <div id="interp-bytes-wrap">
                <div class="text-xs text-slate-400">RAW BYTES</div>
                <div id="interp-bytes" class="mono text-xs bg-slate-950 border border-slate-700 p-2 rounded-lg break-all"></div>
              </div>
              <div id="interp-participants-wrap">
                <div class="text-xs text-slate-400">PARTICIPANTS</div>
                <div id="interp-participants" class="text-xs flex flex-wrap gap-1"></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Legend -->
      <div class="text-xs flex flex-wrap items-center gap-x-6 gap-y-2 text-slate-400 px-1">
        <div class="flex items-center gap-x-1.5"><span class="legend-dot bg-emerald-400"></span> START / Sr / STOP</div>
        <div class="flex items-center gap-x-1.5"><span class="legend-dot bg-blue-400"></span> Address Phase</div>
        <div class="flex items-center gap-x-1.5"><span class="legend-dot bg-purple-400"></span> CCC Command</div>
        <div class="flex items-center gap-x-1.5"><span class="legend-dot bg-amber-400"></span> Data / DAA Arbitration</div>
        <div class="flex items-center gap-x-1.5"><span class="legend-dot bg-red-400"></span> SDA driven by Target (read)</div>
        <div class="flex items-center gap-x-1.5"><span class="legend-dot bg-orange-400"></span> IBI</div>
        <div class="ml-auto text-slate-500">Click anywhere on waveform or table rows to seek • Space = Play/Pause</div>
      </div>
    </div>
  </div>

<script>
// ============================================================================
// Global State
// ============================================================================
let TRACE = null;
let currentFilter = 'all';
let currentTime = 0;
let isPlaying = false;
let playbackSpeed = 1.0;
let animationFrame = null;
let lastFrameTime = 0;

let zoomLevels = {0: 1.0, 1: 1.0};
let selectedTxId = null;

const WAVE_WIDTH = 720;
const WAVE_HEIGHT = 148;

// ============================================================================
// Tailwind + Init
// ============================================================================
function initTailwind() {
  document.documentElement.style.setProperty('--accent', '#3b82f6');
}

function setMaxTime(maxT) {
  document.getElementById('max-time').textContent = Math.round(maxT);
  const scrub = document.getElementById('time-scrubber');
  scrub.max = maxT;
}

// ============================================================================
// Drawing helpers
// ============================================================================
function drawWaveform(busId, canvas, waveform, txs, playheadT) {
  const ctx = canvas.getContext('2d', { alpha: true });
  const W = canvas.width = WAVE_WIDTH;
  const H = canvas.height = WAVE_HEIGHT;
  ctx.clearRect(0, 0, W, H);

  if (!waveform || waveform.length === 0) {
    ctx.fillStyle = '#334155';
    ctx.fillText('No waveform data', 20, H/2);
    return;
  }

  const maxT = TRACE.meta.max_t;
  const zoom = zoomLevels[busId] || 1.0;
  const viewEnd = Math.min(maxT, currentTime + (maxT / zoom) * 0.6);
  const viewStart = Math.max(0, viewEnd - (maxT / zoom));

  const scaleX = (t) => ((t - viewStart) / (viewEnd - viewStart)) * W;

  // Background grid
  ctx.strokeStyle = '#1e2937';
  ctx.lineWidth = 1;
  for (let x = 0; x < W; x += 40) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, H);
    ctx.stroke();
  }

  // Horizontal reference lines (for SDA/SCL)
  ctx.strokeStyle = '#334155';
  ctx.beginPath();
  ctx.moveTo(0, H * 0.28); ctx.lineTo(W, H * 0.28);
  ctx.moveTo(0, H * 0.72); ctx.lineTo(W, H * 0.72);
  ctx.stroke();

  // Labels
  ctx.fillStyle = '#64748b';
  ctx.font = '11px JetBrains Mono, monospace';
  ctx.fillText('SCL', 6, H * 0.28 - 6);
  ctx.fillText('SDA', 6, H * 0.72 - 6);

  // Draw signals
  const sclY = H * 0.28;
  const sdaY = H * 0.72;
  const lowOffset = 18;
  const highOffset = -18;

  let lastX = null;
  let lastScl = 1, lastSda = 1;

  ctx.lineWidth = 2.25;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';

  // Two passes: SCL then SDA for cleaner look
  function drawSignal(colorHigh, colorLow, getVal, baseY) {
    ctx.strokeStyle = colorHigh;
    ctx.beginPath();
    let started = false;

    for (let i = 0; i < waveform.length; i++) {
      const ev = waveform[i];
      if (ev.t < viewStart) continue;
      if (ev.t > viewEnd) break;

      const x = scaleX(ev.t);
      const val = getVal(ev);

      if (!started) {
        ctx.moveTo(x, baseY + (val ? highOffset : lowOffset));
        started = true;
        lastX = x;
        continue;
      }

      // Vertical edge
      ctx.lineTo(x, baseY + (lastVal ? highOffset : lowOffset));
      ctx.lineTo(x, baseY + (val ? highOffset : lowOffset));

      lastVal = val;
      lastX = x;
    }
    ctx.stroke();
  }

  let lastVal = 1;
  // SCL (green)
  ctx.strokeStyle = '#22c55e';
  ctx.beginPath();
  lastVal = 1;
  for (let i = 0; i < waveform.length; i++) {
    const ev = waveform[i];
    if (ev.t < viewStart) continue; if (ev.t > viewEnd) break;
    const x = scaleX(ev.t);
    const val = ev.scl;
    if (i === 0 || ev.t < viewStart) ctx.moveTo(x, sclY + (val ? highOffset : lowOffset));
    else {
      ctx.lineTo(x, sclY + (lastVal ? highOffset : lowOffset));
      ctx.lineTo(x, sclY + (val ? highOffset : lowOffset));
    }
    lastVal = val;
  }
  ctx.stroke();

  // SDA (amber / red when target drives)
  ctx.strokeStyle = '#f59e0b';
  ctx.beginPath();
  lastVal = 1;
  for (let i = 0; i < waveform.length; i++) {
    const ev = waveform[i];
    if (ev.t < viewStart) continue; if (ev.t > viewEnd) break;
    const x = scaleX(ev.t);
    const val = ev.sda;
    if (i === 0 || ev.t < viewStart) ctx.moveTo(x, sdaY + (val ? highOffset : lowOffset));
    else {
      ctx.lineTo(x, sdaY + (lastVal ? highOffset : lowOffset));
      ctx.lineTo(x, sdaY + (val ? highOffset : lowOffset));
    }
    lastVal = val;
  }
  ctx.stroke();

  // Draw transaction phase markers
  const busTx = txs.filter(t => t.bus_id === busId);
  ctx.font = '9px JetBrains Mono, monospace';
  
  busTx.forEach(tx => {
    if (tx.start_t > viewEnd || tx.end_t < viewStart) return;

    const x1 = Math.max(0, scaleX(tx.start_t));
    const x2 = Math.min(W, scaleX(tx.end_t));
    
    let color = '#3b82f6';
    let label = tx.kind;

    if (tx.kind === 'DAA') { color = '#a855f7'; label = 'DAA'; }
    else if (tx.kind === 'CCC_BCAST') { color = '#c026ff'; label = 'CCC'; }
    else if (tx.kind === 'CCC_DIRECT') { color = '#7e22ce'; label = 'DIR'; }
    else if (tx.kind === 'PRIVATE_WR') { color = '#eab308'; label = 'WR'; }
    else if (tx.kind === 'PRIVATE_RD') { color = '#f43f5e'; label = 'RD'; }
    else if (tx.kind === 'IBI') { color = '#f97316'; label = 'IBI'; }

    // Phase bar
    ctx.fillStyle = color + '22';
    ctx.fillRect(x1, 4, Math.max(3, x2 - x1), 12);
    ctx.fillStyle = color;
    ctx.fillRect(x1, 4, Math.max(2, x2 - x1), 2);

    // Label
    if (x2 - x1 > 26) {
      ctx.fillStyle = '#e2e8f0';
      ctx.fillText(label, x1 + 3, 13);
    }

    // START / STOP markers
    if (tx.kind.includes('CCC') || tx.kind === 'DAA' || tx.kind === 'PRIVATE') {
      ctx.fillStyle = '#64748b';
      ctx.fillText('S', x1 + 1, H - 8);
    }
  });

  // Playhead
  if (playheadT >= viewStart && playheadT <= viewEnd) {
    const hx = scaleX(playheadT);
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 2.0;
    ctx.setLineDash([5, 3]);
    ctx.beginPath();
    ctx.moveTo(hx, 0);
    ctx.lineTo(hx, H);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Time labels
  ctx.fillStyle = '#475569';
  ctx.font = '9px JetBrains Mono, monospace';
  const step = (viewEnd - viewStart) / 5;
  for (let i = 0; i <= 5; i++) {
    const t = viewStart + step * i;
    const x = scaleX(t);
    ctx.fillText(Math.round(t), x - 12, H - 3);
  }

  // Store for click handling
  canvas._viewStart = viewStart;
  canvas._viewEnd = viewEnd;
  canvas._maxT = maxT;
}

function updateWaveforms(playheadT) {
  if (!TRACE) return;

  const c0 = document.getElementById('wave0');
  const c1 = document.getElementById('wave1');

  drawWaveform(0, c0, TRACE.waveforms[0], TRACE.transactions, playheadT);
  drawWaveform(1, c1, TRACE.waveforms[1], TRACE.transactions, playheadT);

  // Update time range labels
  const maxT = TRACE.meta.max_t;
  const z0 = zoomLevels[0] || 1;
  const z1 = zoomLevels[1] || 1;
  document.getElementById('bus0-time-range').textContent = `~${Math.round(maxT / z0)} ticks`;
  document.getElementById('bus1-time-range').textContent = `~${Math.round(maxT / z1)} ticks`;
}

// ============================================================================
// Transaction Table
// ============================================================================
function renderTransactionTable(filter = 'all') {
  const tbody = document.getElementById('tx-tbody');
  tbody.innerHTML = '';

  if (!TRACE) return;

  let filtered = TRACE.transactions;
  if (filter === 0) filtered = filtered.filter(t => t.bus_id === 0);
  else if (filter === 1) filtered = filtered.filter(t => t.bus_id === 1);
  else if (filter === 'HOST_BRIDGE') filtered = filtered.filter(t => t.kind === 'HOST_BRIDGE');

  document.getElementById('tx-filter-count').textContent = `${filtered.length} / ${TRACE.transactions.length}`;

  filtered.forEach(tx => {
    const tr = document.createElement('tr');
    tr.className = `tx-row cursor-pointer ${selectedTxId === tx.id ? 'active' : ''}`;
    tr.innerHTML = `
      <td class="pl-4 py-1.5 text-xs text-slate-400 mono">${tx.id}</td>
      <td class="py-1.5">
        ${tx.bus_id === -1 ? 
          '<span class="proto-badge bg-amber-400/20 text-amber-300">HOST</span>' :
          tx.bus_id === 0 ? 
          '<span class="proto-badge bg-blue-400/20 text-blue-300">Bus 0</span>' : 
          '<span class="proto-badge bg-violet-400/20 text-violet-300">Bus 1</span>'}
      </td>
      <td class="py-1.5">
        <span class="font-medium text-xs px-2 py-0.5 rounded ${getKindClass(tx.kind)}">${tx.kind}</span>
      </td>
      <td class="py-1.5 pr-2 text-xs text-slate-200">${tx.details || ''}</td>
      <td class="py-1.5 pr-4 text-right mono text-xs text-slate-400">${Math.round(tx.start_t)}</td>
    `;

    tr.onclick = () => {
      selectTransaction(tx);
      seekToTime(tx.start_t - 20);
    };
    tbody.appendChild(tr);
  });
}

function getKindClass(kind) {
  if (kind === 'DAA') return 'bg-purple-500/30 text-purple-300';
  if (kind === 'CCC_BCAST' || kind === 'CCC_DIRECT') return 'bg-violet-500/30 text-violet-300';
  if (kind === 'PRIVATE_WR') return 'bg-yellow-500/30 text-yellow-300';
  if (kind === 'PRIVATE_RD') return 'bg-rose-500/30 text-rose-300';
  if (kind === 'IBI') return 'bg-orange-500/30 text-orange-300';
  if (kind === 'HOST_BRIDGE') return 'bg-amber-400/30 text-amber-300';
  return 'bg-slate-600/40 text-slate-300';
}

function filterTransactions(filter) {
  currentFilter = filter;
  // highlight active filter button
  document.querySelectorAll('[id^="filter-"]').forEach(el => el.classList.remove('bg-slate-700', 'text-white'));
  const activeBtn = document.getElementById('filter-' + (filter === 'all' ? 'all' : (filter === 0 ? '0' : (filter === 1 ? '1' : 'bridge'))));
  if (activeBtn) activeBtn.classList.add('bg-slate-700', 'text-white');
  
  renderTransactionTable(filter);
}

function selectTransaction(tx) {
  selectedTxId = tx.id;
  renderTransactionTable(currentFilter);

  // Show interpretation
  const ph = document.getElementById('interp-placeholder');
  const content = document.getElementById('interp-content');
  ph.classList.add('hidden');
  content.classList.remove('hidden');

  document.getElementById('interp-kind').textContent = tx.kind;
  document.getElementById('interp-text').textContent = tx.interpretation || 'No detailed interpretation available.';

  const bytesWrap = document.getElementById('interp-bytes-wrap');
  const bytesEl = document.getElementById('interp-bytes');
  if (tx.data && tx.data.length > 0) {
    bytesEl.textContent = tx.data.map(b => '0x' + b.toString(16).padStart(2, '0')).join(' ');
    bytesWrap.style.display = '';
  } else {
    bytesWrap.style.display = 'none';
  }

  const partWrap = document.getElementById('interp-participants-wrap');
  const partEl = document.getElementById('interp-participants');
  if (tx.participants && tx.participants.length) {
    partEl.innerHTML = tx.participants.map(p => 
      `<span class="px-2 py-0.5 bg-slate-800 border border-slate-700 rounded text-[10px]">${p}</span>`
    ).join('');
    partWrap.style.display = '';
  } else {
    partWrap.style.display = 'none';
  }
}

// ============================================================================
// Playback & Scrubbing
// ============================================================================
function updatePlaybackUI() {
  const playIcon = document.getElementById('play-icon');
  const pauseIcon = document.getElementById('pause-icon');
  if (isPlaying) {
    playIcon.classList.add('hidden');
    pauseIcon.classList.remove('hidden');
  } else {
    playIcon.classList.remove('hidden');
    pauseIcon.classList.add('hidden');
  }
}

function updateScrubber(t) {
  const scrub = document.getElementById('time-scrubber');
  scrub.value = Math.min(t, parseFloat(scrub.max));
  document.getElementById('current-time').textContent = Math.round(t);
}

function onScrubberInput() {
  if (!TRACE) return;
  const t = parseFloat(document.getElementById('time-scrubber').value);
  seekToTime(t, false);
}

function seekToTime(t, pause = true) {
  if (!TRACE) return;
  if (pause && isPlaying) togglePlay();

  currentTime = Math.max(0, Math.min(TRACE.meta.max_t, t));
  updateScrubber(currentTime);
  updateWaveforms(currentTime);
  highlightActiveTransaction(currentTime);
}

function highlightActiveTransaction(t) {
  if (!TRACE) return;
  // Find the last transaction that has started by time t
  let active = null;
  for (const tx of TRACE.transactions) {
    if (tx.start_t <= t) active = tx;
    else break;
  }
  if (active && active.id !== selectedTxId) {
    selectedTxId = active.id;
    renderTransactionTable(currentFilter);

    // Auto scroll table
    const tbody = document.getElementById('tx-tbody');
    const rows = tbody.querySelectorAll('tr');
    rows.forEach(r => {
      if (r.textContent.includes(` ${active.id} `) || (active.id < 10 && r.textContent.startsWith(active.id + ' '))) {
        r.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    });
  }
}

let playbackStartReal = 0;
let playbackStartSim = 0;

function animationLoop(now) {
  if (!isPlaying || !TRACE) return;

  if (!lastFrameTime) lastFrameTime = now;
  const dt = (now - lastFrameTime) / 1000;
  lastFrameTime = now;

  const maxT = TRACE.meta.max_t;
  currentTime += dt * playbackSpeed * 420;   // tuned speed factor for nice viewing

  if (currentTime >= maxT) {
    currentTime = maxT;
    isPlaying = false;
    updatePlaybackUI();
  }

  updateScrubber(currentTime);
  updateWaveforms(currentTime);
  highlightActiveTransaction(currentTime);

  if (isPlaying) {
    animationFrame = requestAnimationFrame(animationLoop);
  }
}

function togglePlay() {
  if (!TRACE) return;

  isPlaying = !isPlaying;
  updatePlaybackUI();

  if (isPlaying) {
    lastFrameTime = 0;
    playbackStartSim = currentTime;
    animationFrame = requestAnimationFrame(animationLoop);
  } else if (animationFrame) {
    cancelAnimationFrame(animationFrame);
  }
}

function resetPlayback() {
  if (animationFrame) cancelAnimationFrame(animationFrame);
  isPlaying = false;
  updatePlaybackUI();
  currentTime = 0;
  selectedTxId = null;
  document.getElementById('interp-placeholder').classList.remove('hidden');
  document.getElementById('interp-content').classList.add('hidden');
  updateScrubber(0);
  updateWaveforms(0);
  renderTransactionTable(currentFilter);
}

function updatePlaybackSpeed() {
  playbackSpeed = parseFloat(document.getElementById('speed-select').value);
}

function zoomWaveform(busId, factor) {
  zoomLevels[busId] = Math.max(0.25, Math.min(12, (zoomLevels[busId] || 1) * factor));
  updateWaveforms(currentTime);
}

function resetZoom(busId) {
  zoomLevels[busId] = 1.0;
  updateWaveforms(currentTime);
}

// Click on waveform canvas to seek
function attachWaveformClickHandlers() {
  ['wave0', 'wave1'].forEach((id, idx) => {
    const canvas = document.getElementById(id);
    canvas.onclick = (e) => {
      if (!canvas._viewStart) return;
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const ratio = x / rect.width;
      const t = canvas._viewStart + ratio * (canvas._viewEnd - canvas._viewStart);
      seekToTime(t);
    };
  });
}

// Keyboard shortcuts
function attachKeyboard() {
  document.addEventListener('keydown', (e) => {
    if (e.key === ' ' || e.key === 'k') {
      e.preventDefault();
      togglePlay();
    }
    if (e.key === 'ArrowLeft') {
      seekToTime(currentTime - 800);
    }
    if (e.key === 'ArrowRight') {
      seekToTime(currentTime + 800);
    }
    if (e.key.toLowerCase() === 'r') {
      resetPlayback();
    }
    if (e.key.toLowerCase() === 'f') {
      filterTransactions(currentFilter === 'all' ? 0 : (currentFilter === 0 ? 1 : 'all'));
    }
  });
}

// ============================================================================
// Main load + API
// ============================================================================
async function loadTraceFromServer(forceNew = false) {
  const res = await fetch('/simulate' + (forceNew ? '?fresh=1' : ''));
  if (!res.ok) throw new Error('Failed to fetch simulation');
  const data = await res.json();
  return data;
}

async function loadInitialTrace() {
  try {
    TRACE = await loadTraceFromServer(false);
    applyTrace(TRACE);
  } catch (e) {
    // Fallback: embedded demo data (very unlikely to be needed)
    console.warn('Falling back to embedded demo trace');
    TRACE = createFallbackTrace();
    applyTrace(TRACE);
  }
}

function applyTrace(trace) {
  TRACE = trace;

  // Meta
  document.getElementById('tx-count').textContent = trace.transactions.length;
  setMaxTime(trace.meta.max_t);

  // Device counts
  const dev0 = (trace.meta.devices && trace.meta.devices[0]) ? trace.meta.devices[0].length : 2;
  const dev1 = (trace.meta.devices && trace.meta.devices[1]) ? trace.meta.devices[1].length : 2;
  document.getElementById('bus0-devices').textContent = dev0;
  document.getElementById('bus1-devices').textContent = dev1;

  // Reset UI state
  zoomLevels = {0: 1.0, 1: 1.0};
  currentTime = 0;
  selectedTxId = null;
  isPlaying = false;
  updatePlaybackUI();

  // Render everything
  document.getElementById('interp-placeholder').classList.remove('hidden');
  document.getElementById('interp-content').classList.add('hidden');

  updateScrubber(0);
  updateWaveforms(0);
  renderTransactionTable('all');
  filterTransactions('all');
}

async function rerunSimulation() {
  const btns = document.querySelectorAll('button');
  btns.forEach(b => b.disabled = true);

  try {
    TRACE = await loadTraceFromServer(true);
    applyTrace(TRACE);
  } catch (e) {
    alert('시뮬레이션 재실행 실패: ' + e.message);
  } finally {
    btns.forEach(b => b.disabled = false);
  }
}

function exportTrace() {
  if (!TRACE) return;
  const blob = new Blob([JSON.stringify(TRACE, null, 2)], {type: 'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `i3c_trace_${Date.now()}.json`;
  a.click();
}

function showHelp() {
  const help = `
I3C Dual-Bus SoC Simulator

• Python으로 작성된 MIPI I3C SDR 프로토콜 모델
• 하나의 Host에 두 개의 독립 I3C 컨트롤러가 붙은 구조 시뮬레이션
• DAA (동적 주소 할당), CCC 명령, Private Read/Write, IBI, Host Bridge 트랜잭션 포함

조작법
- 파형 클릭 또는 스크러버로 시간 이동
- 트랜잭션 행 클릭 → 해당 시점 이동 + 상세 해석 표시
- Space 또는 K : 재생/일시정지
- ← → : ±800 tick 이동
- R : 처음으로 리셋
- F : Bus 필터 순환
- 재시뮬레이션 버튼으로 새로운 랜덤 데이터로 다시 실행
`.trim();
  alert(help);
}

function createFallbackTrace() {
  // Minimal working fallback (used only if backend completely fails)
  return {
    meta: { max_t: 42000, title: "Fallback Demo", devices: {0: [], 1: []}, buses: [{id:0,name:"Bus 0"},{id:1,name:"Bus 1"}] },
    waveforms: {
      0: Array.from({length: 120}, (_, i) => ({t: i*350, sda: (i%3), scl: (i%2), note: ""})),
      1: Array.from({length: 90}, (_, i) => ({t: i*380, sda: 1-(i%2), scl: (i%3>0), note: ""}))
    },
    transactions: [
      {id:1, bus_id:0, start_t:120, end_t:980, kind:"CCC_BCAST", details:"ENTDAA broadcast", interpretation:"DAA started", participants:["Bus0"]},
      {id:2, bus_id:1, start_t:400, end_t:1300, kind:"DAA", details:"PressureSensor assigned 0x08", interpretation:"Dynamic address assigned", participants:["PressureSensor"]}
    ]
  };
}

// Canvas click + keyboard
function boot() {
  initTailwind();
  attachWaveformClickHandlers();
  attachKeyboard();

  // Speed select default
  document.getElementById('speed-select').value = '1';

  // Initial load
  loadInitialTrace();

  // Make scrubber nicer
  const scrub = document.getElementById('time-scrubber');
  scrub.addEventListener('mousedown', () => { if (isPlaying) togglePlay(); });

  // Easter egg: double click header resets everything
  document.querySelector('h1').addEventListener('dblclick', () => {
    zoomLevels = {0:1,1:1};
    resetPlayback();
  });

  console.log('%c[I3C] Visualizer ready. All simulation runs in Python backend.', 'color:#475569');
}

// Auto boot
window.onload = boot;
</script>
</body>
</html>
'''

class I3CSimHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quiet logging
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))

        elif path == "/simulate":
            global LAST_TRACE
            fresh = "fresh" in parsed.query or "1" in parsed.query

            with TRACE_LOCK:
                if fresh or LAST_TRACE is None:
                    print("[server] Running fresh I3C simulation...")
                    LAST_TRACE = build_soc_scenario()
                trace = LAST_TRACE

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(trace, indent=None, separators=(",", ":")).encode("utf-8"))

        elif path == "/trace.json":
            # Convenience static endpoint (uses last cached run)
            with TRACE_LOCK:
                if LAST_TRACE is None:
                    LAST_TRACE = build_soc_scenario()
                trace = LAST_TRACE
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(trace).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        self.send_response(405)
        self.end_headers()


def run_server():
    global LAST_TRACE

    print("I3C Dual-Bus SoC Simulator")
    print("==========================")
    print("• Generating initial simulation trace (Python model)...")
    LAST_TRACE = build_soc_scenario()
    print(f"  Generated {len(LAST_TRACE['transactions'])} transactions across 2 buses.")

    server = HTTPServer((HOST, PORT), I3CSimHandler)
    url = f"http://{HOST}:{PORT}"

    print(f"\n✓ Server running at: {url}")
    print("  Press Ctrl+C to stop.\n")

    # Open browser in a separate thread so the server can start first
    def open_browser():
        time.sleep(0.65)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    run_server()
