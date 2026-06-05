# SV grammar enhancement plan (5 items)

Work root: `hc_hierarchy`. Verify after each item.

| # | Item | Deliverable | Verification |
|---|------|-------------|--------------|
| 1 | Tier E generate + instance array paths | `ElaborationResult`, path golden, `inst_leaf` with `[n]` | `pytest tests/phase6/test_tier_e_hierarchy.py` |
| 2 | ifdef variant golden | `compare_instance_sets()`, index meta | `pytest tests/phase6/test_ifdef_variant.py` |
| 3 | Parameter in index + DQL | `param_overrides`, `param ~` | `pytest tests/phase6/test_param_dql.py` |
| 4 | Interface vs module kind | `module_kind`, DQL `kind` | `pytest tests/phase6/test_interface_kind.py` |
| 5 | Unresolved / elaboration warnings | `warnings_json`, `unresolved_modules_json` | `pytest tests/phase6/test_unresolved_warnings.py` |

Batch: `pytest tests/phase6/ -q`

## Status (2026-06-02)

| # | Status | Notes |
|---|--------|-------|
| 1 | done | `ElaborationResult`, `inst_name` keeps `[n]`, golden in `test_tier_e_hierarchy.py` |
| 2 | done | `ifdef_variant.py`, `test_ifdef_variant.py` |
| 3 | done | `_parse_param_overrides`, DQL `param ~`, `test_param_dql.py` |
| 4 | done | `module_kind`, fixture `design/extras/sv_interface/`, DQL `kind =` |
| 5 | done | `unresolved_modules_json`, `warnings_json`, `elab_succeeded` meta |