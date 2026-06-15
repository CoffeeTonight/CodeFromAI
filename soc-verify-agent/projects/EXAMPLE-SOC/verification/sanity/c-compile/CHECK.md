# CHECK — c-compile (sanity)

## PASS 조건
- `verdict_c-compile.json`: `status == PASS`
- RTL filelist 로드 및 C-compile(compile+elaboration) 성공
- 최상위 모듈 elaboration error 0

## FAIL 시 확인
- `runs/{run_id}/c-compile.log`
- `cache.yaml`의 `tag.value`·clone 경로 일치 여부