# hc_hierarchy — maintenance scope (v1 closed)

**Indexing v1 is feature-complete.**

- 사용자용 요약: **[../README.md](../README.md)** (현황·기능·취약점·사용법)
- 다른 세션 handoff: **[../this_prompt.md](../this_prompt.md)**
- 계약: **`docs/TIER_CONTRACT.md`**

## v1 shipped (2026-06)

- Filelist `-F` / `--index-cwd`, slang preprocess cache
- Tier E: shallow pruned closure, hybrid `path_elab_hybrid`, `config_for_pruned_elab` / `PyslangCompileContext`
- Parse: per-file `parse_errors_json`; generate `ifdef` + defines
- Identity: `modules.module_ref`, `instances.module_ref`, `resolve_instance_module_ref`
- `choose_hierarchy_mode()` single router
- Verification: `scripts/verify_phase27.sh` (phase27+28)

## v2 backlog (do not block v1 releases)

| Item | Notes |
|------|--------|
| B7 | Multi-variant ifdef — **partial**: `--variants` + `ifdef_variant_mode=multi_row` (one DB) |
| B6 deep | Full macro expansion AST |
| A2 / A7 | Exotic filelist, work libraries |
| GUI | define/macro-aware source highlight |
| DQL | OR + heavy AND planner tuning |
| CI | Optional slow synthetic full index |

## 의도적 미포함

- VHDL, UPF, SDF
- struct 멤버 hierarchy 노드
- 991-file full slang elab on duplicate corpus

## 검증

```bash
bash scripts/verify_phase27.sh
pytest tests/phase28/ tests/phase27/ -m "not slow" -q
```