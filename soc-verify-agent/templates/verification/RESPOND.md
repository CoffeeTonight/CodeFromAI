# RESPOND — {{group_name}}

> **User-authored.** FAIL·INFO_GAP 시 **분류·복구 방향**.  
> 고정 스크립트가 환경과 맞지 않으면 **ops 수정 또는 crystallize** — MD 원칙은 유지, 실행 경로만 과제에 맞게 조정.

## Step 1 — Classify
- env / tool / info / spec_gap
- log의 error 표식·첫 실패 라인으로 RTL vs env vs 선행 게이트 구분

## Step 2 — Actions (과제별)
- (복구 절차 — 도구·경로는 이 과제 환경에 맞게 기술)

## ops / 스크립트 불일치 시
1. CHECK.md **게이트 원칙**은 그대로 둔다 (log 판정, 산출물, depends_on)
2. 현재 `ops/{{group_name}}.py`가 원칙을 만족하는지 검토
3. 만족하지 않으면 `crystallize_proposal.md`로 과제 스타일에 맞는 Python 제안 → `ops/` 반영
4. 일회성 셸 예시는 MD **참고 구현**에만 두고, 반복 실행은 ops로 고정