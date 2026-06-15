# CHECK — can_fd

## PASS 조건
- `verdict_can_fd.json`: `status == PASS`
- CAN-FD block UVM sim 완료
- sim.log: UVM_ERROR == 0

## FAIL 시 확인
- `runs/{run_id}/can_fd.log`
- `runs/{run_id}/verdict_can_fd.json`