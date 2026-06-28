# VERIF-CPU-SOC 검증 요약 — tag `main`

생성일: **2026-06-28**  
프로젝트: **VERIF-CPU-SOC** · 마일스톤 **M2** (Block RTL & Unit DV)

## Gate 한눈표

| stage / group | 판정 | run_id | 상세 보고서 |
|---------------|------|--------|-------------|
| static / `coi_conn` | **PASS** | `reproduce-main-20260628-064247` | [Static COI connectivity (chip_top)](static_coi_conn.md) |
| simulation / `slave_rw` | **PASS** | `reproduce-main-20260628-064247` | [Simulation slave R/W (single / burst / cpu_sync)](simulation_slave_rw.md) |

## 빠른 링크

- [보고서 허브 README](../../README.md)
- [tag 입력 manifest](../../../inputs/tags/main/manifest.yaml)
- [검증 명세 (coi_conn)](../../../verification/static/coi_conn/coi_conn.md)
- [검증 명세 (slave_rw)](../../../verification/simulation/slave_rw/slave_rw.md)

## 재현 (전체 파이프라인)

검증 순서 그대로 실행 — [`scripts/verification_sequence.yaml`](../../../scripts/verification_sequence.yaml):

```bash
cd <soc-verify-agent>/projects/VERIF-CPU-SOC
chmod +x scripts/*.sh
./scripts/run_VERIF-CPU-SOC_verification_sequence.sh
```

단계별 (파일명 = 검증 제목):

```bash
# Step 1: Sanity — VerifCPU c-compile & elab
./scripts/01_sanity_VerifCPU_c-compile_and_elab.sh
# Step 2: Static COI connectivity (chip_top)
./scripts/02_static_COI_connectivity_chip_top.sh
# Step 3: Simulation slave R/W (single / burst / cpu_sync)
./scripts/03_simulation_slave_R_W_single_burst_cpu_sync.sh
./scripts/99_generate_verification_reports.sh
```

→ [`scripts/README.md`](../../../scripts/README.md)

## 다음 tag 시

1. `inputs/tags/{새tag}/` 에 주간/SFR 문서 + `manifest.yaml`
2. `./scripts/run_VERIF-CPU-SOC_verification_sequence.sh` 실행 후 `reports/index.yaml` 의 `run_id` 갱신
3. `./scripts/99_generate_verification_reports.sh`
