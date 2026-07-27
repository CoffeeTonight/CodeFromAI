# CHECK — oss_smoke

> Flow-replay paradigm: **rtl_sim**

## PASS 조건
- `verdict_oss_smoke.json`: status == PASS
- RTL root (`README.md` + flow-derived structure artifacts) 존재
- flow summary: paradigm=rtl_sim steps=0 tools=[] structure_ok=2 deliverables_present=0; top: RTL sim/elab flow

## FAIL 시 확인
- `runs/{run_id}/verdict_oss_smoke.json`
- `meta/toy_gate.yaml` (top_commands, tools, paradigm)
- `cache.yaml`, `discovered.yaml`
