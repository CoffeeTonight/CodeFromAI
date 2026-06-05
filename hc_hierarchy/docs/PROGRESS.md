# hc_hierarchy — Progress Reports

## 2026-06-02 — Phase 0–4 complete (pyslang)

### Done

| Phase | Status | Notes |
|-------|--------|-------|
| **0** | PASS | `pyslang` engine check, parse `top_module.v` |
| **1a** | PASS | Syntax `HierarchyInstantiation` extract |
| **1b** | PASS | `+define+` via `parseCommandLine` / temp `.f` |
| **1c** | PASS | ANSI ports from `header.ports` (direction + name) |
| **2** | PASS | `ingest_filelist()` — nested `-f`, `/* */` comments |
| **3** | PASS | `build_index_from_filelist` → SQLite, `hch-index` CLI |
| **4** | PASS | DQL subset `module ~ "pat"` → SQL, `hch-query` |

**Tests**: `python3 -m pytest tests/` → **7 passed**

### Key files

- `src/hch/engine/pyslang_parse.py` — defines, incdir, command line
- `src/hch/ingest/pyslang_extract.py` — ports + instances
- `src/hch/ingest/ingest.py` — unified ingest
- `src/hch/index/loader.py` — DB build
- `src/hch/query/dql/planner.py` — minimal DQL

### Verify

```bash
cd hc_hierarchy
./scripts/verify_phase4.sh
pip install -e ".[engine,dev]"
hch-index /path/to/filelist.f -o design.hch.db --top top_module
hch-query -d design.hch.db -q 'module ~ "middle*"'
```

### Known limits (Tier P)

- `generate` not flattened (Phase 6)
- filelist: missing refs logged (`mid_module.v`, `uvm.f`) — ingest uses resolved sources only
- DQL: `AND`, `path ~`, `node_count` partial

## 2026-06-02 — synthetic_deep_rtl + Phase 5–6

### Done

| Item | Notes |
|------|-------|
| **Copy** | `design/synthetic_deep_rtl/` from rvast `demo_data/synthetic_deep_rtl` (8.1MB, 1016 .v) |
| **Fix** | `scripts/fix_synthetic_ports.py` — literal `\\n` in ports |
| **Portable FL** | `scripts/make_portable_filelist.py` → `top_deep_soc.hc.f` |
| **Added** | `rtl/deep_soc_top.v` (7 instances), `quick.hc.f`, `extras/gen_ifdef_generate/` |
| **Phase 6** | `pyslang_elab.py` + `hch-index --elaborate` |
| **Phase 5** | `hch-gui` lazy tree + DQL table (PySide6 extra) |
| **Tests** | `tests/phase5/` — quick ingest ≥50 mods, elab generate paths |

**Tests (fast)**: 10 passed, 1 slow deselected (`test_synthetic_full_filelist_module_count`)

### Commands

```bash
hch-index design/synthetic_deep_rtl/quick.hc.f -o quick.hch.db --top deep_soc_top
hch-index design/extras/gen_ifdef_generate/filelist.f -o gen.hch.db --top top_soc --elaborate
hch-gui -d quick.hch.db   # needs pip install -e '.[gui]'
pytest -m slow tests/phase5   # full ~1000 module filelist
```

## 2026-06-02 — Phase 7 checkpoint / resume

### Done

| Item | Notes |
|------|------|
| **Batched index** | `build_index_batched()` — N sources per pyslang call |
| **Checkpoint** | `meta.checkpoint_files` JSON list, resume skips done |
| **inst_json** | Module instance edges persisted for resume + flatten |
| **CLI** | `--batch-size 64 --resume --force` |
| **Script** | `scripts/index_synthetic_full.sh` |
| **filelist fix** | `+libext+`, `-v/-y` ignored; nested `-F` relative to .f dir |
| **Tests** | `tests/phase7/` PASS |

**Fast tests**: 12 passed (`pytest -m "not slow"`)

### Full synthetic index

```bash
./scripts/index_synthetic_full.sh   # or hch-index ... --batch-size 64 --resume
pytest -m slow tests/phase5::test_synthetic_full_filelist_sources_and_index
```

Note: ~992 **source files**, ~76 **unique module names** (generator reuses types).

### 2026-06-02 — pyslang goal completion (hc_hierarchy only)

| Item | Notes |
|------|-------|
| **Per-file paths** | `ingest._ingest_trees_with_sources` — tree ↔ source file zip |
| **Ports** | `ImplicitNonAnsiPort` + `PortDeclaration.declarators` in `pyslang_extract.py` |
| **SQLite** | `instances.port_json`; `export_instance_dicts()` for DQL JSON |
| **Tier E** | `--elaborate` fills file + ports from `ModuleRecord` |
| **CLI** | `hch-index --export-json instances.json` |
| **Design path** | `hch.paths.design_dir()` + `design/HDLforAST` symlink |
| **Tests** | `tests/test_hierarchy_fields.py` — hierarchy/module/file/ports |
| **DQL doc** | [docs/DQL_RULES.md](DQL_RULES.md) |
| **Batch verify** | `fixtures/dql_batch_*.txt`, `verify_batch_dql.sh`, `verify_batch_dql_full.sh` |
| **Full batch** | 991 sources → 8 instances (top-level flatten only); 8/8 DQL queries OK |

### Next

See [REMAINING.md](REMAINING.md) — **P0: deep hierarchy flatten on full synthetic**