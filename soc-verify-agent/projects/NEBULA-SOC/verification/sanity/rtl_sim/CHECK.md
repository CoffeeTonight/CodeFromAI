# CHECK — rtl_sim (sanity)

## PASS 조건
- `verdict_rtl_sim.json`: `status == PASS`
- c-compile PASS 이후 minimal RTL simulation 완료
- sim.log: UVM_ERROR/FATAL == 0 (TB smoke 기준)

## FAIL 시 확인
- `runs/{run_id}/rtl_sim.log`
- 선행 `c-compile` verdict PASS 여부