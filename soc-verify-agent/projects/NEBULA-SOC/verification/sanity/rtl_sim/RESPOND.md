# RESPOND — rtl_sim (sanity)

## sim FAIL (compile OK)
1. TB smoke testbench·plusargs 확인
2. clock/reset sequence 최소 시나리오 재현
3. 첫 UVM_ERROR 라인 grep → env vs RTL 분류

## c-compile 미완
1. **rtl_sim 실행 금지** — c-compile 먼저 PASS
2. manifest `depends_on: [c-compile]` 준수