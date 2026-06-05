# Indexing tiers and partial elaboration

**Contract (v1):** `docs/TIER_CONTRACT.md` — modes, won't-fix, verification.

## Tier P (default)

```bash
hch-index design/project.f -o project.hch.db --top soc_top
```

- Structural parse + filelist `+define+`
- `generate` **for** loops with literal bounds: unrolled in Tier P (e.g. `gen_loop[0]`, `gen_loop[1]`)
- Wide or unresolved instance arrays — Tier P caps at 64 elements; use `--elaborate` for exact paths
- Complex `while` generate — Tier P unrolls simple `i < N`; else `--elaborate`
- Instance arrays: `u[0:1]` → `u[0]`, `u[1]` edges when bounds are literals

## Tier E (`--elaborate`)

```bash
hch-index design/extras/gen_ifdef_generate/filelist.f -o gen.hch.db --top top_soc --elaborate
```

- Full `runFullCompilation` via pyslang
- Paths include generate blocks and array indices, e.g. `top_soc.gen_blk.gen_loop[0].u_cell`
- On failure: **no exception** — empty/elab fallback to Tier P flatten, meta records:
  - `elab_succeeded=0`
  - `warnings_json` — compiler diagnostics
  - `elab_fallback=tier_p` when flatten used

## Meta keys (GUI / `/api/meta`)

| Key | Meaning |
|-----|---------|
| `defines_json` | Preprocessor defines from filelist |
| `unresolved_modules_json` | Child module names without a definition in index |
| `warnings_json` | Elab/ingest warnings |
| `elab_succeeded` | `1` if Tier E compile OK |
| `tier` | `P` or `E` |
| `hierarchy_source` | `ast`, `path`, `elab`, or `tier_p_fallback` |
| `path_hierarchy_used` | `1` when synthetic `u_*` path layout was used |
| `tier_p_generate_unrolled` | `0` on Tier P (generate not loop-unrolled) |
| `generate_instance_count` | Instances tagged inside `generate` |
| `bind_directive_count` | `bind` directives seen in RTL |
| `library_blackbox_count` | Modules from `-y`/`-v` library scan only |
| `preprocess_libs_in_driver` | `1` when `-y`/`-v` passed to slang preprocessing |
| `library_y_count` / `library_v_count` | Filelist library entries |
| `parse_error_count` / `parse_warning_count` | Slang parse diagnostics |
| `macro_instance_count` | Instances tagged `from_macro` |
| `path_hierarchy_mode` | `auto`, `on`, or `off` (CLI `--path-hierarchy`) |
| `top_modules_json` | Comma tops from `--tops` |
| `ifdef_variant_diff_json` | Instance-set diff when `--ifdef-compare` |
| `elab_partial` | `1` if Tier E failed but instances collected |
| `elab_instance_cap` / `elab_instance_cap_hit` | Cap and truncation flag |
| `path_augmented` | `1` when synthetic path layout used |
| `defparam_count` | Hierarchical defparam assignments merged into module `parameters` |
| `primitive_count` | Primitive gate instances / `module_kind=primitive` stubs |
| `port_connection_edge_count` | Instance edges with named port connections |
| `unsupported_filelist_opts_json` | Skipped filelist tokens (e.g. `+ntb*`) |
| `slang_options_json` | Forwarded options (`+libdir`, `+librescan`, `-sverilog`, …) |
| `filelist_diff_json` | Source/lib/define diff when `--filelist-diff OTHER.f` |
| `flatten_cycle_warning` | `1` if flatten hit a cycle or visit cap |
| `parse_tier_badge` | API convenience: `Tier P · ast` (see `/api/meta`) |
| `tier_e_param_merge` | `1` when Tier E flat rows merged elab + Tier P parameters |
| `elab_param_instance_count` | Flat instances with non-empty `param_json` after `--elaborate` |
| `flat_param_instance_count` | Same for Tier P flatten (structural index) |
| `tier_e_bind_merge` | `1` when Tier E index merges missing hierarchical bind rows from Tier P |
| `tier_e_bind_merge_added` | Count of bind flat rows appended after elaboration |
| `macro_definition_count` | `` `define `` directives seen at compilation-unit scope |
| `while_generate_placeholder_count` | `while` generate blocks indexed as a single `label[0]` slice (Tier P) |
| `while_generate_unroll_count` | `while (i < N)` loops unrolled when *N* is constant |
| `parametric_array_expand_count` | Instance array elements expanded from parameter bounds |
| `variant_db_manifest_json` | Map variant name → `.hch.db` path when `--variant-dir` is used |
| `variant_split_dir` | Output directory for per-variant databases |
| `flatten_warnings_json` | JSON array of flatten issues (cycles, visit cap, unresolved modules) |
| `generate_unreachable_edge_count` | Instances in const-fold-dead generate branches (not in flat index) |
| `generate_ambiguous_instance_count` | Instances under ambiguous generate `if` (both branches walked) |
| `filelist_top_modules_json` | Top module names from `-top` / `+top+` in the `.f` file |
| `work_library` | `-work` library name from filelist (light mapping) |
| `library_cell_map_json` | Module name → library `.v` path for `-y`/`-v` stubs |
| `package_module_count` / `package_symbol_count` | Indexed packages and extracted symbols |
| `multi_def_modules_json` | Module names with multiple definition file paths |
| `parse_errors_json` | Per-source parse status / error counts |
| `inst_tags_json` (per instance row) | `in_generate`, `via_bind`, `generate_path`, `generate_branch`, `is_unresolved` |
| `child_kind` (instances table) | Flat row kind: `module`, `unresolved`, `modport`, `primitive`, … |

Tier E stores **resolved** parameter values from elaboration (`body.parameters`); Tier P `#(.W(16))` overrides are merged when elab omits a name (partial elab / missing body).

## Large SoCs

Full-chip elaboration often fails (missing libs). Use Tier P for search, or elaborate a **small filelist** / single top only.