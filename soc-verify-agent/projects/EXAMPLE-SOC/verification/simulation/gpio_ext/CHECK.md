# CHECK — gpio_ext

> Materialized from SKILL.md (skill_materialize).

## PASS 조건
- verdict_gpio_ext.json: status == PASS
- sim.log: UVM_ERROR == 0 (when real sim enabled)
- Gate script writes `verdict_gpio_ext.json` with PASS
- Log scan shows no blocking error markers

## FAIL 시 확인
- `runs/{run_id}/verdict_gpio_ext.json`
- runs/{run_id}/gpio_ext.log
- runs/{run_id}/verdict_gpio_ext.json
- Inspect compile/sim logs under `runs/{run_id}/`
- Use RESPOND steps; env issues route to bridge loop
