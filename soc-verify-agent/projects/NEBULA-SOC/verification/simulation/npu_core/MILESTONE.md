# MILESTONE — npu_core (simulation)

## SoC 개발 4단계 — NEBULA-SOC

| 마일스톤 | 기간 | 산업계 단계 | 설계·DV 목표 |
|----------|------|-------------|--------------|
| M1 | 2025-10-01 ~ 2025-11-30 | Architecture & Verification Planning | VPlan, TB 아키텍처, DV 환경 |
| M2 | 2025-12-01 ~ 2026-02-15 | Block RTL & Unit DV | IP RTL 통합, 블록 UVM, sanity |
| M3 | 2026-02-16 ~ 2026-05-15 | SoC Integration & System DV | 칩 레벨 sim, 회귀·coverage |
| M4 | 2026-05-16 ~ 2026-06-30 | DV Sign-off & Tape-out | Coverage closure, release gate |

## 이 검증 실행 마일스톤

| 마일스톤 | 실행 | 비고 |
|----------|------|------|
| M1 | — | NPU VPlan·TB 아키텍처만 |
| M2 | **시작 예정** | Block Unit DV — `due: 2026-02-10`, M2 말 블록 동결 목표 |
| M3 | **필수** | SoC 통합·NPU subsystem context |
| M4 | 유지 | Sign-off coverage |

## 실행 주기
- **M2 후반**: 블록 UVM smoke 최초 (sanity PASS 선행)
- **M3**: chip-level 재검증
- 현재 과제: **M2** — npu_core `status: scheduled`