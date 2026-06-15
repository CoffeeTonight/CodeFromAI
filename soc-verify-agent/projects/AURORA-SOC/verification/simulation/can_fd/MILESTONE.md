# MILESTONE — can_fd (simulation)

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
| M1 | — | CAN-FD VPlan |
| M2 | **시작** | Block Unit DV — Automotive MCU 핵심 IP |
| M3 | **필수** | SoC 통합·interconnect context |
| M4 | 유지 | Sign-off block coverage |

## 실행 주기
- **M2**: 블록 UVM smoke (`due: 2026-02-01`)
- **M3**: chip-level 재검증
- 과제 완료: **M4 (2026-05-28)**