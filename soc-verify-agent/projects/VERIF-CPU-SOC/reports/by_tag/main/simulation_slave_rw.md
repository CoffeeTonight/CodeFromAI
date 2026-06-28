# 보고서 — simulation / slave_rw

> tag **`main`** · run `reproduce-main-20260628-064247` · 생성일 2026-06-28

## 요약

| 항목 | 값 |
|------|-----|
| **판정** | **PASS** |
| 마일스톤 | M2 |
| 스크립트 | `slave_rw.py` v0.4.0 |
| log 무결성 | OK (exit= 스캔, vvp tail, tier 마커) |
| 명세 | [`verification/simulation/slave_rw/slave_rw.md`](../../../verification/simulation/slave_rw/slave_rw.md) |

## 3-tier R/W

| tier | 결과 |
|------|------|
| `sim_single` | PASS |
| `sim_burst` | PASS |
| `sim_cpu_sync` | PASS |

| tier | 내용 |
|------|------|
| sim_single | simple_soc — SFR/SRAM/UART firmware single R/W |
| sim_burst | AMBA bridge smoke (11 checks) + VCD |
| sim_cpu_sync | full_campaign — 3-CPU `vsync` + parallel bus R/W |

## 근거

- log scan: no error keywords, all cmd exit=0, no truncated blocks, success markers present
- all tiers PASS: sim_single, sim_burst, sim_cpu_sync
- fw unchanged (5 c-compile artifacts)

## 산출물

| 파일 | 경로 |
|------|------|
| verdict | `runs/reproduce-main-20260628-064247/verdict_slave_rw.json` |
| log | `runs/reproduce-main-20260628-064247/slave_rw.log` |

## 선행 조건

- sanity `c-compile` PASS (동일 tag workspace)
- c-compile 펌웨어 sim 중 미변조

## 사용자 입력 (이 tag)

SFR 주소·주간 RTL 변경은 [`inputs/tags/main/manifest.yaml`](../../../inputs/tags/main/manifest.yaml) 에 등록.

## 재현 방법 (스크립트)

스크립트 **파일명 = 검증 제목**. gate 옵션 없이 **고정 순서**로만 실행합니다.

### 전체 순서 (권장)

```bash
cd <soc-verify-agent>/projects/VERIF-CPU-SOC
chmod +x scripts/*.sh
./scripts/run_VERIF-CPU-SOC_verification_sequence.sh
```

- 순서 SSOT: [`scripts/verification_sequence.yaml`](../../../scripts/verification_sequence.yaml)

### 이 gate (Step 3)

**Simulation slave R/W (single / burst / cpu_sync)** — `./scripts/03_simulation_slave_R_W_single_burst_cpu_sync.sh`

```bash
# Step 3만 (이전 step 선행 권장)
RUN_ID=my-run ./scripts/03_simulation_slave_R_W_single_burst_cpu_sync.sh
```

- 재현 가이드: [`scripts/README.md`](../../../scripts/README.md)
- 보고서 갱신: `./scripts/99_generate_verification_reports.sh` (`reports/index.yaml` run_id 수정 후)

