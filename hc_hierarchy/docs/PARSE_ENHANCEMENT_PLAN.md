# Parse enhancement plan (4 tracks) — implemented

> **후속 전체 갭·로드맵:** `docs/PARSING_GAP_PLAN.md` (Phase 10–14)

| # | Track | Delivered | Verify |
|---|-------|-----------|--------|
| 1 | generate / ifdef / macro | `InstanceEdge.in_generate`; meta `tier_p_generate_unrolled`, `generate_instance_count`; ifdef golden unchanged | `tests/phase9/test_parse_track1.py` |
| 2 | library (-y/-v) / bind | `FilelistResult.library_*`; `library_scan`; `BindEdge` + `via_bind` instances; meta `library_blackbox_count`, `bind_directive_count` | `tests/phase9/test_parse_track2.py` |
| 3 | multi-def / parametric | `instance_edge_key()` param-aware dedup; multi-file `_definition_paths`; distinct `#()` children in flatten | `tests/phase9/test_parse_track3.py` |
| 4 | hierarchy source meta | `hierarchy_source` (`ast`/`path`/`elab`/`tier_p_fallback`); `path_hierarchy_used`; elab fail never uses path heuristic | `tests/phase9/test_parse_track4.py` |

```bash
./scripts/verify_phase9.sh
# or: PYTHONPATH=src pytest tests/phase9/ -q
```