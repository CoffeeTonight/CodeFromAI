# CHECK — oss_smoke

> Flow-replay paradigm: **cpu_fw**

## PASS 조건
- `verdict_oss_smoke.json`: status == PASS
- RTL root (`Makefile` + flow-derived structure artifacts) 존재
- paradigm **cpu_fw**: structure under firmware/ + example.sh; optional hex/bin deliverables recorded from flow replay
- gen entry: `./example.sh gen`
- flow summary: paradigm=cpu_fw steps=0 tools=['iverilog', 'vvp', 'verilator', 'make', 'c_compiler', 'python'] structure_ok=2 deliverables_present=0; top: ./example.sh gen → make elab/sim; need fw hex/bin or gen path

## FAIL 시 확인
- `runs/{run_id}/verdict_oss_smoke.json`
- `meta/toy_gate.yaml` (top_commands, tools, paradigm)
- `cache.yaml`, `discovered.yaml`
