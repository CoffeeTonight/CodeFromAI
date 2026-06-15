# CHECK — {{group_name}}

> **User-authored.** 과제·스타일마다 내용이 달라진다.  
> **MD = 무엇을 어떻게 판정할지** (원칙·PASS/FAIL 기준).  
> **ops/{stage}/{group}.py = 어떻게 실행할지** (crystallize된 Python). MD에 적힌 한 가지 명령어에 ops를 묶지 말 것.

## 게이트 원칙 (이 섹션은 이식 가능 — 환경에 맞게 구체화)
- 선행 게이트·의존 산출물 (`manifest.yaml` `depends_on`)
- **log 기반 판정**: `runs/{run_id}/{{group_name}}.log`에서 EDA/C 표준 error 표식 탐지 (exit code만으로 PASS 금지)
- 산출물 존재·무결성 (경로·스탬프는 과제별로 정의)
- (stage/group별 추가 원칙: fw 연동, coverage threshold, …)

## PASS 조건
- `verdict_{{group_name}}.json`: `status == PASS`
- log 스캔: error 키워드 없음 + (과제가 정의한) 성공 마커 있음
- (과제별 기준 추가)

## FAIL 시 확인
- `runs/{run_id}/{{group_name}}.log`
- `runs/{run_id}/verdict_{{group_name}}.json`
- 선행 게이트 verdict·`cache.yaml` tag/clone

## 이 과제 참고 구현 (선택 — 예시일 뿐, ops가 다를 수 있음)
<!-- 다른 DV 환경(VCS/Xcelium/회사 래퍼/Makefile)이면 LLM이 MD 원칙에 맞게 ops를 새로 crystallize -->
- (예: 사용 도구, 대표 log 마커, 산출물 경로)