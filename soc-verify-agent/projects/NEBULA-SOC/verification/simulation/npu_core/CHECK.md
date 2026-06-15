# CHECK — npu_core

## PASS 조건
- `verdict_npu_core.json`: `status == PASS`
- NPU core block UVM sim 완료
- sim.log: UVM_ERROR == 0

## FAIL 시 확인
- `runs/{run_id}/npu_core.log`
- `runs/{run_id}/verdict_npu_core.json`