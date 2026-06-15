# RESPOND — c-compile (sanity)

## compile FAIL
1. tag clone 경로·filelist 경로 확인 (`meta.yaml` / discovered)
2. include path·define 매크로 diff 검토
3. license/queue 환경 변수 점검

## elaboration FAIL
1. 최상위 모듈명·bind/instance 누락 확인
2. tag diff에서 신규 RTL·blackbox 추가 여부 검토
3. spec 미정 → INFO_GAP 후 `questions_pending.md`