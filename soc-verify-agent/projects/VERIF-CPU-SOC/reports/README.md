# VERIF-CPU-SOC — 검증 결과 보고서

사용자·DV 담당자가 **한 곳에서** tag별 gate PASS/FAIL과 근거를 볼 수 있는 허브입니다.

## 어디를 보면 되나

| 경로 | 내용 |
|------|------|
| [`by_tag/{tag}/SUMMARY.md`](./by_tag/main/SUMMARY.md) | **한눈 요약** — 현재 tag 전체 gate 표 |
| `by_tag/{tag}/{stage}_{group}.md` | gate별 상세 보고서 |
| [`index.yaml`](./index.yaml) | tag ↔ run_id ↔ 보고서 경로 (기계 판독) |
| `runs/{run_id}/verdict_*.json` | 원본 판정 (ops 생성) |

현재 tag: **`main`** (`cache.yaml` → `tag.value`)

## 검증 재현 (필수)

스크립트 **파일명 = 검증 제목**. gate 옵션 없이 **고정 순서**만 실행합니다.

→ **[`scripts/README.md`](../scripts/README.md)** (사용법 + **스크립트 생성 규칙**)  
→ 순서 SSOT: [`scripts/verification_sequence.yaml`](../scripts/verification_sequence.yaml)

```bash
cd projects/VERIF-CPU-SOC
chmod +x scripts/*.sh
./scripts/run_VERIF-CPU-SOC_verification_sequence.sh
```

Step 1 → 2 → 3 순서:

| Step | 스크립트 | 검증 제목 |
|------|----------|-----------|
| 1 | `01_sanity_VerifCPU_c-compile_and_elab.sh` | Sanity — VerifCPU c-compile & elab |
| 2 | `02_static_COI_connectivity_chip_top.sh` | Static COI connectivity (chip_top) |
| 3 | `03_simulation_slave_R_W_single_burst_cpu_sync.sh` | Simulation slave R/W (single / burst / cpu_sync) |
| — | `99_generate_verification_reports.sh` | 보고서 MD 생성 |

## 보고서 갱신

새 run 후 `index.yaml`의 `run_id`를 최신 run으로 바꾼 뒤:

```bash
./scripts/99_generate_verification_reports.sh
# 또는
python3 ops/report/generate_reports.py --project .
```

`by_tag/{tag}/` MD가 재생성됩니다.

## tag별 사용자 입력

매주·매 tag마다 바뀌는 문서(SFR 설계, 배포 노트 등)는 **`inputs/tags/{tag}/`** 에 둡니다.  
보고서의 “입력 산출물” 절에서 manifest를 참조합니다.

→ [`../inputs/README.md`](../inputs/README.md)