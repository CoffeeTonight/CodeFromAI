# MILESTONE — nightly_full (regression)

## SoC 개발 4단계 — AURORA-SOC (완료)

| 마일스톤 | 기간 | 산업계 단계 | 설계·DV 목표 |
|----------|------|-------------|--------------|
| M1 | 2025-10-01 ~ 2025-11-30 | Architecture & Verification Planning | VPlan, TB 아키텍처, DV 환경 |
| M2 | 2025-12-01 ~ 2026-02-15 | Block RTL & Unit DV | IP RTL 통합, 블록 UVM, sanity |
| M3 | 2026-02-16 ~ 2026-05-15 | SoC Integration & System DV | 칩 레벨 sim, 회귀·coverage |
| M4 | 2026-05-16 ~ 2026-06-30 | DV Sign-off & Tape-out | Coverage closure, release gate |

## 이 검증 실행 마일스톤

| 마일스톤 | 실행 | 비고 |
|----------|------|------|
| M1 ~ M2 | — | block TB 수렴 전 |
| M3 | **pilot** | SoC Integration — nightly regress·coverage merge 시작 |
| M4 | **필수** | DV Sign-off release gate — **최종 PASS** |

## 실행 주기
- **M3**: pilot nightly + coverage trend
- **M4**: 매일/nightly 필수, `due: 2026-05-20` 기준 PASS
- 과제 완료: **M4 DV Sign-off (2026-05-28)**