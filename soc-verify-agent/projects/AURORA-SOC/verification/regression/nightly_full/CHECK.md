# CHECK — nightly_full

## PASS 조건
- `verdict_nightly_full.json`: `status == PASS`
- 전체 regression suite 완료, critical test PASS
- coverage merge: block·top 목표치 충족 (release gate 기준)

## FAIL 시 확인
- `runs/{run_id}/nightly_full.log`
- `runs/{run_id}/coverage_report/`
- 선행 sanity·simulation verdict PASS 여부