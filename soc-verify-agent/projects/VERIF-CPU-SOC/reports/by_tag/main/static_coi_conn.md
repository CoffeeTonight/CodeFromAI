# 보고서 — static / coi_conn

> tag **`main`** · run `coi-conn-test` · 생성일 2026-06-14

## 요약

| 항목 | 값 |
|------|-----|
| **판정** | **PASS** |
| 마일스톤 | M2 |
| 스크립트 | `coi_conn.py` v0.2.0 |
| 명세 | [`verification/static/coi_conn/coi_conn.md`](../../../verification/static/coi_conn/coi_conn.md) |

## 목적

RTL elaboration 기준 **2~3건 COI(connectivity)** — endpoint 쌍이 설계 의도대로 연결/비연결인지 `scan_inst`로 확인.

## check 결과

| check_id | connected (TSV) | errors |
|----------|-----------------|--------|
| `sfr_clk_to_sram_clk` | True | — |
| `sfr_paddr_to_sram_haddr` | False | — |
| `orch_to_pool` | False | — |

## 근거

- scan_inst OK — 3 checks matched expected_connected
- checks: coi_conn_checks.json

## 산출물

| 파일 | 경로 |
|------|------|
| verdict | `runs/coi-conn-test/verdict_coi_conn.json` |
| log | `runs/coi-conn-test/coi_conn.log` |
| TSV | `runs/coi-conn-test/coi_conn.tsv` |
| checks | `verification/static/coi_conn/coi_conn_checks.json` |

## 사용자 입력 (이 tag)

[`inputs/tags/main/manifest.yaml`](../../../inputs/tags/main/manifest.yaml) — SFR/주간 배포 문서 등록 시 endpoint·filelist 갱신 근거로 사용.

## 재현 방법 (스크립트)

스크립트 **파일명 = 검증 제목**. gate 옵션 없이 **고정 순서**로만 실행합니다.

### 전체 순서 (권장)

```bash
cd <soc-verify-agent>/projects/VERIF-CPU-SOC
chmod +x scripts/*.sh
./scripts/run_VERIF-CPU-SOC_verification_sequence.sh
```

- 순서 SSOT: [`scripts/verification_sequence.yaml`](../../../scripts/verification_sequence.yaml)

### 이 gate (Step 2)

**Static COI connectivity (chip_top)** — `./scripts/02_static_COI_connectivity_chip_top.sh`

```bash
# Step 2만 (이전 step 선행 권장)
RUN_ID=my-run ./scripts/02_static_COI_connectivity_chip_top.sh
```

- 재현 가이드: [`scripts/README.md`](../../../scripts/README.md)
- 보고서 갱신: `./scripts/99_generate_verification_reports.sh` (`reports/index.yaml` run_id 수정 후)

