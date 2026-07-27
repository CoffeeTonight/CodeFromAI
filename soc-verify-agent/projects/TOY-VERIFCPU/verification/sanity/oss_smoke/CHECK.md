# CHECK — oss_smoke

> Flow-replay paradigm: **cpu_fw**

## PASS 조건
- `verdict_oss_smoke.json`: status == PASS
- RTL root (`example.sh` + flow-derived structure artifacts) 존재
- paradigm **cpu_fw**: structure under firmware/ + example.sh; optional hex/bin deliverables recorded from flow replay
- gen entry: `./example.sh gen`
- flow summary: paradigm=cpu_fw steps=3 tools=['python', 'iverilog', 'vvp', 'make', 'example.sh', 'verilator', 'xcelium', 'vcs'] structure_ok=7 deliverables_present=6; top: ./example.sh gen → make elab/sim; need fw hex/bin or gen path

## FAIL 시 확인
- `runs/{run_id}/verdict_oss_smoke.json`
- `meta/toy_gate.yaml` (top_commands, tools, paradigm)
- `cache.yaml`, `discovered.yaml`
