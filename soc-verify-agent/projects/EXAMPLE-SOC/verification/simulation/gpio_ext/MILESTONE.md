# MILESTONE — gpio_ext (simulation)

## SoC 개발 4단계 — EXAMPLE-SOC

| 마일스톤 | 기간 | 산업계 단계 | 설계·DV 목표 |
|----------|------|-------------|--------------|
| M1 | 2025-10-01 ~ 2025-11-30 | Architecture & Verification Planning | VPlan, TB 아키텍처, DV 환경 |
| M2 | 2025-12-01 ~ 2026-02-15 | Block RTL & Unit DV | IP RTL 통합, 블록 UVM, sanity |
| M3 | 2026-02-16 ~ 2026-05-15 | SoC Integration & System DV | 칩 레벨 sim, 회귀·coverage |
| M4 | 2026-05-16 ~ 2026-06-30 | DV Sign-off & Tape-out | Coverage closure, release gate |

## 이 검증 실행 마일스톤

| 마일스톤 | 실행 | 비고 |
|----------|------|------|
| M1 | — | GPIO block VPlan만 |
| M2 | **시작** | Block RTL & Unit DV — GPIO UVM smoke |
| M3 | **필수** | SoC 통합·chip-level context 재검증 |
| M4 | 유지 | Sign-off 전 block coverage hardening |

## 실행 주기
- **M2**: 블록 동결 후 최초 PASS
- **M3**: 마일스톤 창 내 1회 이상 + tag 변경 시 재실행
- 현재 과제: **M3** — `due: 2026-06-20`