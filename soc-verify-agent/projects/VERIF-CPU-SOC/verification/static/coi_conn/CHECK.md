# CHECK — coi_conn (static)

> **검증 명세 전문:** [`coi_conn.md`](./coi_conn.md) — ops crystallize·LLM은 동일 폴더의 `coi_conn.md`를 우선 읽는다.

## PASS (요약)
- `verdict_coi_conn.json`: `status == PASS`
- scan_inst 배치 결과 TSV: **2~3개 check** 모두 `expected_connected`와 `connected` 일치
- `coi_conn.log` 스캔: tool/Python error 없음

## FAIL (요약)
- endpoint/hierarchy 오류 (`errors` 열)
- expected vs actual `connected` 불일치
- check 수 < 2 또는 명세 누락

상세·전체 입력 케이스: **coi_conn.md** + **conn_example.json**