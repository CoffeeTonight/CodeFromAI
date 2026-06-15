# MILESTONE — c-compile (sanity)

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
| M1 | 선택 | filelist 골격 smoke (env bring-up) |
| M2 | **필수·개시** | Block RTL drop 후 첫 sanity 게이트 |
| M3 | **필수** | SoC 통합 중 **매 tag** 선행 |
| M4 | **필수** | Sign-off 전까지 tag마다 유지 |

## 실행 주기
- **M2~M4**: git tag 갱신(4일)마다 반드시 실행
- 현재 과제: **M3 (SoC Integration & System DV)** — tag `v1.0.1`