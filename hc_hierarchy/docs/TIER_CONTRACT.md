# Tier indexing contract (v1)

**Version:** `tier_contract_version=1` (meta key on every index build)

## Purpose

Stop endless “elab fix” loops on duplicate-heavy RTL by fixing **what success means** per corpus type.

## Modes

| `--elab-deep` | Strategy | Success criteria |
|---------------|----------|------------------|
| `hybrid` (default on large/multi-def) | Tier P path materialization + pruned slang closure | `hierarchy_source=path_elab_hybrid`, instance count ≈ path (~991 on synthetic) |
| `shallow` | Pruned closure slang only | `shallow_elab_succeeded=1`, small instance count (closure) |
| `closure` | Full pruned sources in slang (no path augment) | May fail if duplicate module names in closure |
| `auto` | Heuristic → usually `hybrid` when sources > 64 or multi-def in closure | Same as chosen mode |

**Tier P only** (no `--elaborate`): structural AST + flatten; no slang elaboration.

## Won’t fix (v1)

- Full slang elaboration on **991-file / 74 duplicate module names** corpus (use hybrid).
- VHDL, UPF, SDF, struct-member hierarchy nodes.
- Full macro expansion AST (tagging + `macro_instance_count` only).
- Multi-define DB variants: use `--variants NAME=K=V` (same DB, `instances.variant` column); `0`/`false` undefines for `` `ifdef ``.

## Compile context (code)

All slang parses use `PyslangCompileContext`:

- **full** — cached preprocessed `.f` (`filelist_path` set).
- **pruned** — `source_files` only, `filelist_path=None` (never reload full 991 list during closure elab).

## Instance identity (code)

Child instances resolve `module_ref` via `resolve_instance_module_ref()` (edge file, parent file, sibling index under multi-def).

## Verification

```bash
bash scripts/verify_phase27.sh          # fast gate (phase27+28)
pytest tests/phase28/ -q                # module_ref + macro
# optional slow:
HCH_SKIP_SYNTH_INDEX=0 bash scripts/verify_phase27.sh
```

## v2 backlog (not v1)

- ifdef multi-variant single workflow (B7)
- GUI define/macro-aware highlight
- DQL OR+AND planner tuning
- Exotic filelist (`+ntb`, work lib A7)