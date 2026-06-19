# MILESTONE — c-compile (sanity) — VERIF-CPU-SOC

## SoC 개발 4단계

| 마일스톤 | 기간 | 산업계 단계 | 설계·DV 목표 |
|----------|------|-------------|--------------|
| M1 | 2025-10-01 ~ 2025-11-30 | Architecture & Verification Planning | VPlan, TB 아키텍처, DV 환경 |
| M2 | 2025-12-01 ~ 2026-02-15 | Block RTL & Unit DV | IP RTL 통합, 블록 UVM, sanity |
| M3 | 2026-02-16 ~ 2026-05-15 | SoC Integration & System DV | 칩 레벨 sim, 회귀·coverage |
| M4 | 2026-05-16 ~ 2026-06-30 | DV Sign-off & Tape-out | Coverage closure, release gate |

## 이 검증 실행 마일스톤

| 마일스톤 | 실행 | 비고 |
|----------|------|------|
| M1 | 선택 | filelist·gen 스크립트 smoke |
| M2 | **필수·개시** | VerifCPU drop 후 첫 sanity — **gen + iverilog_elab** |
| M3 | **필수** | SoC 통합 중 **매 tag** 선행 |
| M4 | **필수** | Sign-off 전까지 tag마다 유지 |

## 실행 주기
- **M2~M4**: git tag 갱신(4일)마다 반드시 실행
- 현재 과제: **M2 (Block RTL & Unit DV)** — tag `main`, RTL `~/tools/__CFI/VerifCPU/verif_cpu_verilog`