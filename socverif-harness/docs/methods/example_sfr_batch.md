# example_sfr_batch — 사용자 검증방법 예시

본 파일은 `{검증방법name}.md` 병합 패턴의 toy용 예시이다. 실제 사용자 방법은 동일 형식으로 `docs/methods/`에 추가한다.

## 적용 단계

`soc_validation_flow.md` §4 C코드 수정

## 절차

1. 동일 SFR에 대한 bit field 변경은 **한 번의 read → mask → write**로 배치한다.
2. tier 2 smoke에서 `VERIF PASS` 1회만 기록한다.
3. toy (`envs/toy_mimic_soc`)에서만 먼저 실행한다.

## PASS 기준

- VLP `VERIF SUMMARY`에 FAIL=0
- `verif_report.json` → `all_passed: true`

## soc_validation_flow 병합 예

```markdown
### 4.4 사용자 방법: SFR batch (example_sfr_batch.md)
- unrelated bit field 개별 RMW 금지 (§4.2와 동일 강화)
```