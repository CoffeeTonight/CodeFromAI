# CHECK — oss_smoke

## PASS 조건
- `verdict_oss_smoke.json`: status == PASS
- OSS RTL root (`example.sh` + required artifacts) 존재

## FAIL 시 확인
- `runs/{run_id}/verdict_oss_smoke.json`
- `meta/toy_gate.yaml`, `cache.yaml`, `discovered.yaml`
