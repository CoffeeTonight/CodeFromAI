# RESPOND — coi_conn (static)

> 원칙·상세: **coi_conn.md**

## hierarchy / endpoint 오류 (`errors` 열)
1. `scan-inst <filelist> --top <TOP> -o instances.tsv` 로 `full_path` 재확인
2. gen 헤더·define 누락 → c-compile `./example.sh gen` 선행
3. connect JSON `a`/`b` 수정 후 재실행

## expected_connected 불일치
1. 설계 의도 재확인 (통합 vs 의도적 분리)
2. `include_ff`, `over-approximate-if` 정책 조정 (coi_conn.md 원칙 유지 범위)
3. `--connect-trace`로 `hops`·터미널 리포트 검토

## scan_inst / ops 불일치
1. CHECK·**coi_conn.md** 게이트 원칙 유지
2. `pip install -e ~/tools/__CFI/scan_inst` 및 PATH 확인
3. 과제 filelist/top에 맞게 `ops/static/coi_conn.py` crystallize

## INFO_GAP
- check 정의·expected 미기록 → `coi_conn_checks.json` 보완
- endpoint/mode 모름 → `conn_example.json` 카탈로그 + `instances.tsv` 재스캔
- run별 override: `runs/{run_id}/coi_conn_checks.json`