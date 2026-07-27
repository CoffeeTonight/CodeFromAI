# SOUAL — 세션 불변 지침 (soc-verify-agent)

어떤 Grok/에이전트 세션이든 이 파일 규칙을 지킨다.  
관련 작업 문서: `goal.md`, `plan.md`, `execute.md`, `fail.md` (repo 루트).

---

## 1. 업무 본질 (1순위)

> **주어진 검증 환경에 오류가 있는지, 토이 복제로 빨리 잡는다.**

- 1순위: **detect** (flow 복기 → 최소 토이 → 초고속 smoke)
- 2순위: apply / settle / heavy gate
- 토이 = 복사 제품이 아니라 **오류 탐지기**

성공 1차: `CLEAN_L0` 또는 `ERRORS_L0` + 원인 목록 (수십 초 이내 목표).  
토이 PASS만 하고 실환경 미적용이 detect 실패는 아님. settle 실패와 혼동 금지.

---

## 2. 매 작업 루프 (필수)

| 순서 | 문서 | 할 일 |
|------|------|--------|
| 1 | `goal.md` | 목적·비목적·성공 기준 확인/갱신 |
| 2 | `plan.md` | 단계·TAT 예산·범위 (L0/L1/L2) |
| 3 | `execute.md` | 이번 회차 코딩·실행 로그 (시간/과정/기대 산출물) |
| 4 | 코딩·디버깅 | 아래 코딩·로그 규칙 |
| 5 | `fail.md` | 발견한 오류·원인·수정·재발 방지 **매회 추가** |

다음 회차 설계·디버깅 전 **`fail.md`를 반드시 참고**한다.

---

## 3. 코딩 규칙

- **간결한 코드.** 추상화· indirection 최소화.
- **코멘트는 필수적인 것만** (비자명 계약, 함정). 장황한 서술 금지.
- 드라이브바이 리팩터·무관 파일 편집 금지.
- `__CFI` 수정 전 백업 스냅샷 (가능하면 `cfa_snapshot_backup` / 수동 tar).

---

## 4. 디버깅·로그 규칙

디버깅은 **코드에 심은 로그**를 보고 한다. 로그에 반드시:

1. **시간** — 경과 `elapsed_s` 또는 phase timestamp  
2. **핵심 과정** — phase id (`resolve` / `scaffold` / `gate` / …)  
3. **기대 출력물** — 예상 파일·verdict·exit code  

형식 예:

```text
[detect] t=+0.12s phase=scaffold expected=projects/TOY-*/ops/sanity/oss_smoke.py
[detect] t=+1.50s phase=gate expected=verdict_oss_smoke.json status=PASS
```

추측으로 고치지 말고, 로그·산출물·`fail.md` 이력을 근거로 고친다.

---

## 5. 탐지 범위 (혼동 금지)

| Level | 내용 | 기본 |
|-------|------|------|
| **L0** | 경로·구조·툴·ops 계약·flow 복기 smoke | **detect 기본** |
| L1 | 선택 gen/dry-run 한 스텝 | opt-in |
| L2 | heavy c-compile / full sim | detect 아님 |

`PASS`/`CLEAN_L0` ≠ 전체 환경 무오류. 반드시 레벨을 결과에 명시.

---

## 6. 명령 우선순위

```bash
# 1순위 — 빠른 오류 탐지
soc-verify --root . agent detect --from <PROJECT>

# 2순위 — 적용·정착
soc-verify --root . agent bootcamp --from <PROJECT> --apply
soc-verify --root . agent settle --from <PROJECT>
```

---

## 7. 세션 시작 체크

1. `soual.md` (이 파일) 읽기  
2. `goal.md` / 최근 `fail.md` 확인  
3. 목적 밖 작업이면 먼저 goal/plan 갱신  
4. 끝나면 execute.md + fail.md 갱신  

이 과정을 어기면 안 된다.
