"""Detailed CLI and JSON configuration help text."""

from __future__ import annotations

HELP_DESCRIPTION = """\
scan-inst — regex-based Verilog instance scan and structural connectivity.

Modes (pick one; default is hierarchy dump):
  hierarchy          Flat instance list TSV (default)
  find-top           Top-module candidates
  search             Instance / path search
  check-connect      Single endpoint-pair connectivity
  check-connect-batch  Many pairs; JSON or text pairs file
  fanin-cone / fanout-cone  COI cone debug (FF/port/blackbox boundaries)

Use --config RUN.json to supply all options from one file. CLI flags override JSON.
See --help-config, --help-connect, and --help-cone for JSON field reference."""

HELP_EPILOG = """\
examples:
  scan-inst design.f --top SOC_TOP -o instances.tsv
  scan-inst design.f --find-top -o tops.tsv
  scan-inst design.f --top top --search "u_ecc*,idx" -o hits.tsv
  scan-inst design.f --top top --check-connect top.clk top.u0.clk
  scan-inst design.f --top top --check-connect-batch checks.json -o conn.tsv
  scan-inst --config run.json -o out.tsv
  scan-inst --config run.json --no-cache --define DEBUG=1

JSON help:
  scan-inst --help-config     full run JSON (--config)
  scan-inst --help-connect    connectivity batch JSON only
  scan-inst --help-cone       fanin/fanout cone mode
  scan-inst --help-stress     random RTL connectivity stress / pytest

environment:
  SCAN_INST_CACHE_DIR         index/elab cache root
  SCAN_INST_IGNORE_PATH       default --ignore-path patterns (comma-separated)
  SCAN_INST_IGNORE_MODULE     default --ignore-module names (comma-separated)
  SCAN_INST_IGNORE_FILELIST   default --ignore-filelist patterns (comma-separated)
  SCAN_INST_NO_INCLUDE_WARM   skip include warm before parallel preprocess
  SCAN_INST_INCLUDE_WARM_MAX  max includes to warm (default 200; 0 = no limit)
  SCAN_INST_LOW_MEMORY_AUTO   auto fused index above N sources (default 1500; 0=off)
  HCH_INDEX_CWD               default --index-cwd for -F filelists"""

CONFIG_HELP = """\
scan-inst run JSON (--config / -c)
==================================

All CLI options can be expressed in one JSON object. Relative paths are resolved
against the directory containing the JSON file.

Required
--------
  filelist (string)
      Top Verilog filelist (.f). Same as the positional argument.

Mode (optional; inferred when omitted)
--------------------------------------
  mode (string)
      hierarchy | find-top | search | check-connect | check-connect-batch | cone
  find-top (bool)             Same as --find-top
  all-tops (bool)             Same as --all-tops

Elaboration / filelist
----------------------
  top (string)                Top module; auto-pick when exactly one candidate
  defines (object | array)    Extra +define macros.
                              Object: {"USE_PCIE": "1", "DEBUG": "1"}
                              Array:  ["USE_PCIE=1", "DEBUG"]
  index-cwd (string)          EDA cwd for -F nested filelists (--index-cwd)
  max-depth (int)             Max instance elaboration depth (--max-depth)

Output / logging
----------------
  output (string)             TSV path; "-" for stdout (default: "-")
  quiet (bool)                Suppress stderr progress (--quiet)
  log-file (string)           Append run report to this path (--log-file)
  no-log-file (bool)          Disable default run log (--no-log-file)

Search mode
-----------
  search (string)             Instance name patterns; comma-separated globs
  search-path (string)        Hierarchy path glob (leaf port verified in RTL)
  search-subtree (bool)       Include instances under matched hierarchies
  search-module (bool)        Also match module type names

Connectivity — single
---------------------
  check-connect (array | object)
      Two endpoints: ["top.a", "top.b"] or {"a": "...", "b": "..."}
  connect-trace (bool)        TSV hops + terminal path report (--connect-trace)
  connect-log (bool)          Alias for connect-trace (JSON/scripts)
  include-ff (bool)           Traverse always_ff D->Q edges (--include-ff)
  ff-barrier (bool)           Inverse of include-ff (include_ff = !ff_barrier)
  strict-generate (bool)      Strict generate folding for connectivity
  over-approximate-if (bool|null)
                              if/generate over-approximation policy

Cone mode (COI debug)
---------------------
  fanin-cone (string)         Endpoint for fanin cone (--fanin-cone)
  fanout-cone (string)        Endpoint for fanout cone (--fanout-cone)
  cone-graph (string)         Optional Graphviz DOT path (--cone-graph)
  over-approximate-if (bool|null)
                              Same policy as connectivity (default: true)

  Boundaries (stop + collect):
    fanout: always_ff D (ff-sink), module outputs (port-out), blackboxes
    fanin:  always_ff Q (ff-driver), module inputs (port-in), blackboxes

  Terminal report lists flip-flops, ports, and blackboxes; TSV lists boundaries.
  Uses a separate index path — does not slow default --check-connect.

Example (fanout from a net)
---------------------------
{
  "filelist": "design.f",
  "mode": "cone",
  "top": "top",
  "fanout-cone": "top.u_mid.din",
  "output": "cone.tsv"
}

Connectivity — batch
--------------------
  connect (object)            Inline checks + connect options (preferred in run JSON)
  check-connect-batch (string | object)
      Path to pairs/checks file, OR inline same shape as connect

  connect / check-connect-batch object fields:
      checks (array)          Required. Items: [a,b] or {"id","a","b"}
      pairs, connections      Aliases for checks
      top, defines            Per-batch overrides (merged with run-level)
      include-ff, connect-trace, trace, strict-generate, over-approximate-if

  Batch output TSV columns:
      check_id, endpoint_a, endpoint_b, connected, mode, note, errors, hops

  Missing hierarchy/port: fails before COI search; errors column lists evidence
  (nearest path, elab roots, child instances, declared ports, etc.).

Ignore rules
------------
  ignore-path (string | array)       RTL path globs (--ignore-path)
  ignore-path-file (string | array)  External ignore lists (--ignore-path-file)
  ignore-module (string | array)     Module names (--ignore-module)
  ignore-filelist (string | array)   Listing .f names/paths (--ignore-filelist)

Cache / parallelism
-------------------
  jobs (int)                  Parallel index workers; 0=auto CPU count
  j (int)                     Alias for jobs
  job (int)                   Alias for jobs (typo-tolerant)
  low-memory (bool)           Fused per-file build (less RAM, slower cold index)
  cache-dir (string)          Disk cache directory
  no-cache (bool)             Disable index/elab cache
  refresh-cache (bool)        Force index rebuild

CLI override rule
-----------------
When both --config and CLI flags are present, explicit CLI flags win over JSON.

Example (hierarchy)
-------------------
{
  "filelist": "design.f",
  "top": "SOC_TOP",
  "output": "instances.tsv",
  "defines": {"USE_PCIE": "1"},
  "jobs": 4
}

Example (search)
----------------
{
  "filelist": "design.f",
  "mode": "search",
  "top": "hc_verify_top",
  "search": "idx,ecc",
  "search-module": true,
  "output": "hits.tsv"
}

Example (connectivity batch, inline)
------------------------------------
{
  "filelist": "filelist.f",
  "mode": "check-connect-batch",
  "top": "stress_top",
  "no-cache": true,
  "defines": {"STRESS_USE_IN": "1"},
  "include-ff": true,
  "output": "connect.tsv",
  "connect": {
    "checks": [
      {"id": "clk", "a": "top.clk", "b": "top.u0.clk"},
      {"id": "bad", "a": "top.u_missing.clk", "b": "top.clk"}
    ]
  }
}

Bundled example:
  examples/stress_seed42/stress_42_d8.run.json
"""

CONNECT_HELP = """\
scan-inst connectivity batch JSON
=================================

Used with --check-connect-batch FILE, or inline as "connect" in run JSON.

Minimal (pairs only)
--------------------
[
  ["top.clk", "top.u0.clk"],
  ["top.rst_n", "top.u1.clk"]
]

Object with checks
------------------
{
  "top": "stress_top",
  "defines": {"STRESS_USE_IN": "1"},
  "include-ff": true,
  "connect-trace": false,
  "strict-generate": false,
  "checks": [
    {"id": "port_port", "a": "top.probe_in", "b": "top.u_spine.probe_out"},
    {"id": "missing", "a": "top.u_nope.x", "b": "top.clk"}
  ]
}

Check item aliases
------------------
  Endpoints: a/b, from/to, src/dst, endpoint_a/endpoint_b
  Id:        id or name (optional; appears in check_id column)

Options
-------
  top                 Elaboration top when not set on CLI / run JSON
  jobs (int)          Parallel index workers (same as run JSON; 0=auto)
  j / job / workers   Aliases for jobs
  ignore-path         RTL folder patterns; matched on resolved absolute paths
                      (filelist sources and every `include` target)
  ignore-filelist     Listing .f patterns; RTL listed by a matching filelist is
                      skipped (immediate listing + provenance chain)
  no-cache            Disable index/elab disk cache
  refresh-cache       Force index rebuild
  defines             Merged into compile defines (also used at index build
                      when loaded via --config)
  include-ff (bool)   Allow paths through always_ff (default: comb-only)
  ff-barrier (bool)   Shorthand for include_ff = !ff_barrier
  connect-trace       TSV hops + readable path report on terminal (alias: trace)
  connect-log         Same as connect-trace (alias for JSON)
  strict-generate     Strict generate-region folding
  over-approximate-if bool or null

Path evidence kinds (hops / connect-log)
----------------------------------------
  intra-module    assign/alias/ff within one module
  child-down      parent net -> child instance port
  child-hier      hierarchical reference into child
  parent-up       child port -> parent via instance port map
  parent-hier-ref child port -> parent via hier ref in parent

Text pairs file (non-JSON)
--------------------------
  One pair per line; tab or whitespace separated; # comments allowed:
    top.clk\\ttop.u0.clk
    top.rst_n top.u1.clk

Output
------
  TSV with header:
    check_id  endpoint_a  endpoint_b  connected  mode  note  errors  hops

Error policy
------------
  Unknown hierarchy or port: check fails immediately (connected=false) with
  errors describing why (path stops at X, elab roots, child instances, etc.).

Bundled example:
  examples/stress_seed42/stress_42_d8.connect.json
"""

CONE_HELP = """\
scan-inst fanin / fanout cone mode
==================================

Standalone COI (cone of influence) traversal for debug: list all flip-flops,
ports, and blackboxes reached from an endpoint. Does not change --check-connect
performance (separate module index with FF endpoint scan).

CLI
---
  scan-inst design.f --top top --fanout-cone top.u_mid.din -o cone.tsv
  scan-inst design.f --top top --fanin-cone top.u_mid.qout -o cone.tsv
  scan-inst design.f --top top --fanout-cone top.sig --cone-graph cone.dot

Run JSON (--config)
-------------------
{
  "filelist": "design.f",
  "top": "top",
  "mode": "cone",
  "fanout-cone": "top.u_mid.din",
  "output": "cone.tsv",
  "cone-graph": "cone.dot"
}

Use fanin-cone OR fanout-cone (not both). Endpoint syntax matches connectivity:
hierarchy path with optional .port (e.g. top.clk, top.u_child.din).

Boundaries
----------
  ff-sink     always_ff D input (fanout stops here)
  ff-driver   always_ff Q output (fanin stops here)
  port-out    module output port (fanout)
  port-in     module input port (fanin)
  blackbox    opaque / no-body instance

Output
------
  TSV: boundary rows (kind, scope, net, module, detail) + # comment stats
  Terminal: grouped report (stderr when -o -, else stdout) — same pattern as
            --connect-trace path reports.

See also: scan-inst --help-config (cone fields in run JSON)
"""

STRESS_HELP = """\
scan-inst random connectivity stress tests
==========================================

Random deep-hierarchy RTL is generated and checked for port-port, port-inst,
and cross-hierarchy connectivity. Use this to benchmark or regression-test
the connectivity engine.

Generate RTL + JSON artifacts (one seed)
----------------------------------------
  python -m scan_inst.stress_gen --seed 42 --standard --out-dir DIR

  Writes: RTL, filelist.f, *.connect.json, *.run.json
  Profiles:
    --standard     linear depth~10 branch~5 single-file (faster)
    (default)      zigzag extreme depth~20 branch~8 multi-file

Run scan-inst on generated artifacts
------------------------------------
  scan-inst --config DIR/stress_42_d8.run.json -o connect.tsv
  # or
  scan-inst DIR/filelist.f --check-connect-batch DIR/stress_42_d8.connect.json

Random benchmark (N trials, prints timing table)
------------------------------------------------
  python -m scan_inst.stress_gen --trials 10
  python -m scan_inst.stress_gen --trials 10 --standard
  python -m scan_inst.stress_gen --seed 99 --depth 20 --branch-factor 8

Single-trial report (no --out-dir)
----------------------------------
  python -m scan_inst.stress_gen --seed 42 --standard

pytest (CI / regression)
------------------------
  pytest tests/test_stress_connectivity.py -q
  pytest -m stress -q              # marked slow batch trials (see pyproject.toml)
  pytest tests/test_connectivity.py -q

Bundled fixed-seed example:
  examples/stress_seed42/
"""


def print_config_help() -> None:
    print(CONFIG_HELP)


def print_connect_help() -> None:
    print(CONNECT_HELP)


def print_cone_help() -> None:
    print(CONE_HELP)


def print_stress_help() -> None:
    print(STRESS_HELP)