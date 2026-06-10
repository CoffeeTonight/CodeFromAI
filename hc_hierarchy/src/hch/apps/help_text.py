"""Shared CLI --help epilogs and GUI help dialog content."""

from __future__ import annotations

from textwrap import dedent

OVERVIEW = dedent(
    """
    hc_hierarchy — Verilog/SystemVerilog RTL hierarchy indexer + DQL search

    Workflow:
      1. hch-index   filelist.f → SQLite .hch.db
      2. hch-query   DQL search (CLI batch supported)
      3. hch-web / hch-gui   open DB: tree, search, source view
      4. hch-deepen  on-demand pyslang expand for shallow / skim branches

    Environment variables:
      HCH_INDEX_CWD        EDA run directory for -F filelists (or --index-cwd)
      HCH_BLACKBOX_PATH    Comma-separated RTL path substrings to blackbox (see hch-index --help)
      REPO, SOC_RTL…       expand $VAR / ${VAR} in filelists (export in shell)
      HCH_SKIP_SYNTH_INDEX=1   skip large synthetic index in verify scripts

    Docs: README.md, docs/DQL_RULES.md, docs/INDEXING.md
    """
).strip()

DQL_HELP = dedent(
    """
    DQL (Design Query Language) — shared by hch-query, GUI, and web UI

    Syntax:
      <field> <operator> "<value>"  [ AND | OR ... ]  [ NOT ... ]  [ ( ... ) ]

    Common fields:
      path, hierarchy   full hierarchy path (dot-separated)   top.u_cpu.u_uart
      inst, instance    leaf name (no dots); glob (~) also matches module type
      module            RTL module type name                    uart_16550
      module_ref        unique definition key (filepath::module)
      file, filepath    source file path
      port              port name
      depth             hierarchy depth (root=0)
      node_count        number of '.' in full_path
      parent            parent path (instances.parent_path)
      kind, module_kind module / interface / program / package
      child_kind        flat instance kind (module, unresolved, primitive, …)
      parse_tier, tier  full | skim | shallow_cap (conditional depth / text-skim)
      from_macro        macro-expanded instance tag
      in_generate       inside generate block
      via_bind          instance created via bind
      param             parameter JSON
      port_path         full_path.port_name (use with expand_ports)

    Operators:
      ~     glob (* = any string, ? = one char)
      ^=    prefix (path ^= "soc.cpu" → soc.cpu%)
      =     exact match
      !=    not equal
      IN    list (port IN ("clk","rst"))
      < <= > >=   on depth, node_count

    Post-filter keywords (in query string):
      lastnode        keep rows that are not strict descendants of other hits
      expand_ports    one row per port (port_path)

    Bare pattern (field omitted):
      u_ecc*   →  inst ~ "u_ecc*"

    inst vs path:
      inst searches leaf names only — no dots in inst names.
        inst ~ "*t*.*"   → usually 0 hits
        path ~ "*t*.*"   → path pattern with a child level

    Examples:
      path ~ "top_module.u_middle*"
      path ^= "soc.cpu" AND module ~ "uart*"
      inst ~ "u_*" AND depth >= 2
      parent ^= "top.u_arr"
      module_ref ~ "*cpu_cluster*"
      parse_tier = skim
      parse_tier = shallow_cap
      child_kind = unresolved
      file ~ "*vendor_ip*" AND module ~ "aes*"
      expand_ports AND port ~ "irq"
      lastnode AND path ^= "soc.cpu"

    Batch (hch-query):
      hch-query -d design.hch.db queries.txt -o results.tsv
      hch-query -d design.hch.db -q 'path ~ "top*"' --text
      hch-query -d design.hch.db -q 'inst ~ "u_*"' --format plain
    """
).strip()

INDEX_HELP = dedent(
    """
    hch-index — build SQLite .hch.db from a .f filelist

    Basic:
      hch-index path/to/top.f -o project.hch.db --top soc_top \\
        --index-cwd path/to/eda_run_dir

    Filelist:
      -f / -F nested filelists, +define+, +incdir+, -y/-v
      -F resolves paths from --index-cwd (or HCH_INDEX_CWD)
      $REPO/rtl/a.v — expand from shell environment
      unset variables stay literal → Source not found

    IP / kit blackbox (vendor IP, design-kit RTL — skip full parse):
      --blackbox-path SUBSTR   Repeatable path substring match on resolved RTL paths
      HCH_BLACKBOX_PATH        Comma-separated substrings (merged with --blackbox-path)
      Example:
        hch-index chip.f -o chip.hch.db --top soc_top \\
          --blackbox-path vendor_ip \\
          --blackbox-path third_party/dk_rtl \\
          -j 32
        export HCH_BLACKBOX_PATH=vendor_ip,encrypted_ip
        hch-index chip.f -o chip.hch.db --top soc_top
      Behavior:
        Matched .v/.sv files: module header scan only → blackbox stub (ports from header)
        pyslang full parse skipped on those files (faster index, no vendor body needed)
        Parent instances that instantiate blackbox modules are still indexed
        Internal hierarchy inside blackboxed modules is not expanded
      DB meta: kit_blackbox_patterns_json, kit_blackbox_source_count, kit_blackbox_module_count
      DQL: find blackboxed RTL via file path, e.g. file ~ "*vendor_ip*"

    Tier:
      (default)      Tier P — AST parse, generate literal unroll
      --elaborate    Tier E — slang elaboration

    --elab-deep (Tier E, large / duplicate RTL):
      auto     heuristic (usually hybrid)
      hybrid   path hierarchy + shallow slang (recommended for duplicate SoC)
      shallow  pruned closure only (debug)
      closure  full pruned slang (may fail on duplicates)
      --path-hierarchy auto|on|off   synthetic soc_top/u_* directory layout
      --elab-instance-cap N          Tier E instance cap (default 50000)
      --no-elab-fast                 Tier E: parse full filelist (disable closure-fast)

    Performance (large filelists, Tier P):
      -j, --jobs N       Parallel parse workers (0=auto CPU count; default 0)
      --batch-size N     Sources per batch (0=all at once; enables checkpoint when >0)
      --resume           Continue from checkpoint (default on; use --no-resume to disable)
      --force            Ignore checkpoint and rebuild module/instance tables

    Parse / hierarchy depth (requires --top):
      --max-depth N            Uniform cap: 0=top only, 1=children, 2=grandchildren, …
      --depth-anchor GLOB      Full-depth path glob (repeatable): '*_top*', '*_grp*', '*_log*'
      --depth-shallow N        Below non-anchor paths, parse only N descendant levels (default 2)
      Combine: anchors get full depth (--max-depth caps anchors if set); others get --depth-shallow
      Shallow-zone files use fast text-skim (no pyslang) unless --no-skim-parse
      --tops A,B,C             Multiple flatten roots (comma-separated; overrides single --top)
      Web/GUI tree: gold=text-skim, orange=depth cap (more RTL below, not indexed yet)

    On-demand deepen (after shallow / skim index):
      hch-deepen -d chip.hch.db --under soc_top.u_periph --full
      hch-deepen -d chip.hch.db --under soc_top.u_periph --depth 3
      Web tree: + button on gold/orange rows
      GUI: Tree → Deepen Branch (Ctrl+D) or right-click on gold/orange row

    Variants & diagnostics:
      --variant NAME=DEFINE,...       Repeatable; multiple ifdef variants in one DB
      --variant-compare A,B           Diff instance paths between variants
      --variant-dir DIR               Also write one .hch.db per variant
      --ifdef-compare                 Compare filelist defines vs --ifdef-alt
      --ifdef-alt USE_ALT=1,...       Extra defines for --ifdef-compare
      --filelist-diff OTHER.f         Store filelist_diff_json meta
      --export-json PATH              Write DQL-ready instances JSON after indexing

    Progress:
      Phase messages + sources N/M on stderr (auto batch when 48+ sources)
      Large designs: milestones, heartbeat during long steps
      Summary: Started / Finished / Elapsed (also stored in DB meta)
      --quiet to suppress progress
    """
).strip()

INDEX_HELP_EPILOG = f"\n{INDEX_HELP}\n"

DEEPEN_HELP = dedent(
    """
    hch-deepen — on-demand pyslang expand for shallow / text-skim branches

    Re-parses RTL under a materialized instance path and updates the .hch.db in place.
    Use after hch-index with --depth-anchor / text-skim when you need full hierarchy
    under a specific branch without re-indexing the whole chip.

    Basic (full subtree below PATH):
      hch-deepen -d chip.hch.db --under soc_top.u_periph --full

    Additional levels only (instead of full subtree):
      hch-deepen -d chip.hch.db --under soc_top.u_periph --depth 3

    Notes:
      PATH must exist in the index (materialized full_path)
      Requires completed index (meta indexing_complete=1) and original filelist in DB meta
      Upgraded modules get parse_tier=full; path recorded in meta deepened_paths_json
      Re-flattens entire hierarchy after deepen (other branches unchanged)
      -j N  parallel pyslang workers (0=auto)

    UI equivalents:
      hch-web: + button on gold (skim) or orange (shallow_cap) tree rows
      hch-gui: Tree → Deepen Branch (Ctrl+D) on gold/orange row

    Related hch-index options:
      --depth-anchor, --depth-shallow, --no-skim-parse, --blackbox-path
    """
).strip()

DEEPEN_HELP_EPILOG = f"\n{DEEPEN_HELP}\n"

QUERY_HELP = dedent(
    """
    hch-query — run DQL against .hch.db (single query or batch)

    Single:
      hch-query -d design.hch.db -q 'path ~ "top_module.u_middle*"'
      hch-query -d design.hch.db -q 'module ~ "ecc*"' -o hits.tsv
      hch-query -d design.hch.db -q 'inst ~ "u_*"' --text
      hch-query -d design.hch.db -q 'parse_tier = skim' -o skim.tsv

    Batch (queries.txt):
      hch-query -d design.hch.db queries.txt -o results.tsv
      one query per line, # for comments

    Output:
      --format tsv   tab table (default)
      --format text  TSV with # query header per block
      --format plain readable blocks
      --text         shortcut for --format text
      --batch-summary TSV   per-query status (query, status, row_count)
    """
).strip()

QUERY_HELP_EPILOG = f"\n{DQL_HELP}\n\n{QUERY_HELP}\n"

WEB_HELP = dedent(
    """
    hch-web — browser UI (read-only SQLite index + DQL + deepen API)

      hch-web -d design.hch.db
      hch-web -d design.hch.db --host 127.0.0.1 --port 8765
      hch-web -d design.hch.db --no-browser

    Layout: hierarchy tree | DQL + results | source viewer
    Tree colors: gold=text-skim, orange=depth cap — click + to deepen branch
    Meta panel (ⓘ): tier, hierarchy_source, defines, blackbox counts, warnings
    DQL syntax matches hch-query.
    Default browser open: on desktop; off in PRoot/chroot (use --browser / --no-browser)
    """
).strip()

WEB_HELP_EPILOG = f"\n{WEB_HELP}\n\n{DQL_HELP}\n"

GUI_HELP = dedent(
    """
    hch-gui — PySide6 desktop UI (explorer + on-demand deepen)

      pip install -e ".[gui]"
      hch-gui -d design.hch.db

    Layout: tree | DQL + results table
    Tree colors: gold=text-skim, orange=depth cap (more RTL below, not indexed yet)
    Deepen shallow branch: select gold/orange row → Tree → Deepen Branch (Ctrl+D)
      or right-click → Deepen branch (pyslang, full subtree)
    CLI equivalent: hch-deepen -d design.hch.db --under PATH --full
    File menu: Save query results (Ctrl+S), Copy (Ctrl+Shift+C)
    Help menu: DQL, indexing, batch query guides
    """
).strip()

GUI_HELP_EPILOG = f"\n{GUI_HELP}\n\n{DQL_HELP}\n"


def gui_help_sections() -> list[tuple[str, str]]:
    return [
        ("Overview", OVERVIEW),
        ("DQL", DQL_HELP),
        ("Indexing (hch-index)", INDEX_HELP),
        ("Deepen (hch-deepen)", DEEPEN_HELP),
        ("Batch query (hch-query)", QUERY_HELP),
        ("Web UI (hch-web)", WEB_HELP),
        ("GUI (hch-gui)", GUI_HELP),
    ]


ABOUT_TEXT = dedent(
    """
    hc_hierarchy v0.1
    pyslang-based Verilog/SystemVerilog hierarchy indexer + DQL

    CLI: hch-index, hch-query, hch-deepen, hch-web, hch-gui
    """
).strip()

WEB_UI_HELP = dedent(
    """
    Web UI

    1. Hierarchy (left)
       Click nodes to view source and ports; expand/collapse lazy tree
       Expand levels + Apply: expand N levels from roots
       Gold/orange rows: text-skim or depth cap — click + to deepen (pyslang)

    2. DQL (center)
       Enter query, Run (or Enter); click rows to sync tree and source
       Text: copy results; ↓: save to path via server API

    3. Source (right)
       RTL for selected instance; ports; missing file list

    4. Meta (ⓘ in header)
       Index metadata: tier, hierarchy_source, defines, blackbox counts, warnings

    F1 or ? opens help.
    """
).strip()

INST_VS_PATH_NOTE = dedent(
    """
    inst vs path

    inst / instance  →  leaf name only (u_uart). No dots.
    path / hierarchy →  full path (soc.cpu.u_uart).

    Wrong:  inst ~ "*t*.*"     → usually 0 hits
    Right:  path ~ "*t*.*"
            inst ~ "*uart*"
            path ^= "top.cpu"
    """
).strip()


def web_dql_example_groups() -> list[dict]:
    return [
        {
            "id": "path",
            "title": "Path (path)",
            "hint": "Full hierarchy path; levels separated by dots.",
            "examples": [
                {
                    "label": "One level under top",
                    "query": 'path ^= "{{TOP}}."',
                    "note": "{{TOP}} = this DB top module",
                },
                {
                    "label": "Top and all descendants",
                    "query": 'path ^= "{{TOP}}"',
                },
                {
                    "label": "Path contains cpu",
                    "query": 'path ~ "*cpu*"',
                },
                {
                    "label": "Contains t and has child level",
                    "query": 'path ~ "*t*.*"',
                    "note": "use path, not inst",
                },
                {
                    "label": "Depth >= 2",
                    "query": 'node_count >= 2 AND path ^= "{{TOP}}"',
                },
                {
                    "label": "Under specific parent",
                    "query": 'parent ^= "{{TOP}}.u_middle"',
                },
            ],
        },
        {
            "id": "inst",
            "title": "Instance name (inst)",
            "hint": "Leaf name only; use path for dotted patterns.",
            "examples": [
                {"label": "Starts with u_", "query": 'inst ~ "u_*"'},
                {"label": "Name contains uart", "query": 'inst ~ "*uart*"'},
                {"label": "Exact u_middle", "query": 'inst = "u_middle"'},
                {"label": "Direct child of top", "query": 'inst ~ "u_*" AND depth = 1'},
                {
                    "label": "Bare pattern",
                    "query": "u_ecc*",
                    "note": 'same as inst ~ "u_ecc*"',
                },
            ],
        },
        {
            "id": "module",
            "title": "Module & file",
            "examples": [
                {"label": "Module uart*", "query": 'module ~ "uart*"'},
                {"label": "Module ecc_top", "query": 'module = "ecc_top"'},
                {"label": "File path contains rtl", "query": 'file ~ "*rtl*"'},
                {"label": "Basename top_verify.v", "query": 'file ~ "*top_verify.v"'},
                {"label": "module_ref", "query": 'module_ref ~ "*cpu*"'},
                {"label": "Blackboxed vendor IP path", "query": 'file ~ "*vendor_ip*"'},
            ],
        },
        {
            "id": "port",
            "title": "Ports",
            "examples": [
                {"label": "Has clk port", "query": 'port ~ "clk"'},
                {"label": "clk or rst", "query": 'port IN ("clk", "rst", "rst_n")'},
                {"label": "One row per port", "query": 'expand_ports AND port ~ "irq"'},
                {"label": "port_path prefix", "query": 'port_path ^= "{{TOP}}.u_"'},
            ],
        },
        {
            "id": "advanced",
            "title": "Advanced",
            "examples": [
                {"label": "Leaf under prefix", "query": 'lastnode AND path ^= "{{TOP}}.cpu"'},
                {"label": "Path + module", "query": 'path ^= "{{TOP}}" AND module ~ "uart*"'},
                {"label": "Text-skim instances", "query": 'parse_tier = skim'},
                {"label": "Depth-capped instances", "query": 'parse_tier = shallow_cap'},
                {"label": "In generate", "query": 'in_generate = "1"'},
                {"label": "From macro", "query": 'from_macro = "1"'},
                {"label": "NOT example", "query": 'path ^= "{{TOP}}" AND NOT module ~ "*tb*"'},
            ],
        },
        {
            "id": "cli",
            "title": "CLI batch (hch-query)",
            "hint": "Same DQL; one query per line in queries.txt",
            "examples": [
                {
                    "label": "Single query (terminal)",
                    "query": 'hch-query -d design.hch.db -q \'path ~ "top*"\'',
                    "cli_only": True,
                },
                {
                    "label": "Batch file",
                    "query": "hch-query -d design.hch.db queries.txt -o hits.tsv",
                    "cli_only": True,
                },
            ],
        },
    ]


def web_help_sections() -> list[dict]:
    return [
        {"id": "ui", "title": "Web UI", "body": WEB_UI_HELP},
        {"id": "inst_path", "title": "inst vs path", "body": INST_VS_PATH_NOTE},
        {"id": "dql", "title": "DQL", "body": DQL_HELP},
        {"id": "examples", "title": "Examples", "body": ""},
        {"id": "index", "title": "Indexing", "body": INDEX_HELP},
        {"id": "deepen", "title": "Deepen", "body": DEEPEN_HELP},
        {"id": "query", "title": "Batch query", "body": QUERY_HELP},
        {"id": "overview", "title": "Overview", "body": OVERVIEW},
    ]


def web_help_payload() -> dict:
    return {
        "version": "1",
        "about": ABOUT_TEXT,
        "inst_vs_path": INST_VS_PATH_NOTE,
        "sections": web_help_sections(),
        "example_groups": web_dql_example_groups(),
    }