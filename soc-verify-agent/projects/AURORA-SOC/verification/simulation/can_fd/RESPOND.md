# RESPOND — can_fd

## compile FAIL
1. CAN-FD filelist·bind 경로 확인 (`meta.yaml` / discovered)
2. VERBOSE=1 재실행 후 elaboration error 분류
3. env | tool | info 분류

## sim FAIL
1. sim.log 첫 UVM_ERROR grep
2. CAN protocol sequence·timing spec 대조
3. spec 미정 → INFO_GAP, `questions_pending.md` 기록