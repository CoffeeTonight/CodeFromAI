# MILESTONE — slave_rw (simulation) — VERIF-CPU-SOC

## SoC 개발 4단계

| 마일스톤 | 실행 | 비고 |
|----------|------|------|
| M2 | **권장·개시** | sanity PASS 후 slave bus R/W smoke (single) |
| M3 | **필수** | burst bridge + 멀티-CPU sync parallel bus |
| M4 | **필수** | full_campaign 회귀에 slave R/W 포함 |

현재 과제: **M2** — sanity 후 **single / burst / cpu_sync** 3-tier R/W gate

상세: **slave_rw.md**