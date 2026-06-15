# CHECK — gpio_ext

## PASS 조건
- `verdict_gpio_ext.json`: `status == PASS`
- sim.log: UVM_ERROR == 0 (when real sim enabled)

## FAIL 시 확인
- `runs/{run_id}/gpio_ext.log`
- `runs/{run_id}/verdict_gpio_ext.json`