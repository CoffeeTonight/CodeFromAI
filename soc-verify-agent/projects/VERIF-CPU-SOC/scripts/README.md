# VERIF-CPU-SOC — 검증 재현 스크립트

**파일명 = 검증 제목.** gate 옵션 없이 **정해진 순서**만 실행합니다.

이 문서는 **사용법**과 **스크립트 생성 규칙**(에이전트·개발자)의 SSOT입니다.  
`reports/index.yaml` → `verification_sequence.readme` 가 여기를 가리킵니다.

**사용자 절차서:** [`../USER-PROCEDURE.md`](../USER-PROCEDURE.md)  
LLM 전체 미션(처음→끝): [`../../../templates/obsidian/MISSION_VERIF-CPU-SOC.md`](../../../templates/obsidian/MISSION_VERIF-CPU-SOC.md)

---

## 선행 — VerifCPU RTL (S0)

```bash
./bootstrap_verifcpu_workspace.sh
```

- 기본: **`~/tools/__CFI/VerifCPU/verif_cpu_verilog`** (`discovered.yaml` `local_clone_path`)
- `cache.yaml` `clone.path` = `~/tools/__CFI` · `rtl_subdir` = `VerifCPU/verif_cpu_verilog`
- 원격 clone 필요 시에만 `workspace/{tag}/` ( `git_url` )
- intake `rtl.rtl_root_override` 가 있으면 ops가 그 경로 우선

통합 intake / gate crystallize:

```bash
python3 crystallize_gate_from_intake.py    # coi_conn + slave_rw overrides ← intake
python3 expand_agent_runbook.py --intake inputs/tags/main/deployment/customer_soc_intake.example.yaml
```

---

## 스크립트 생성 규칙 (에이전트/개발자)

검증을 실제로 수행한 뒤, 사용자가 **동일 순서로 재현**할 수 있게 `scripts/`를 만든다.

### 원칙

| 규칙 | 설명 |
|------|------|
| **파일명 = 검증 제목** | `02_static_COI_connectivity_chip_top.sh` 처럼 번호+stage+제목이 파일명에 드러나야 함 |
| **gate 옵션 금지** | `./script.sh coi_conn` 같은 분기·인자 없음. “이 gate만” 돌리려면 해당 step 스크립트를 직접 실행 |
| **순서 SSOT** | `verification_sequence.yaml` + 오케스트레이터가 유일한 전체 순서 정의 |
| **검증 순서 = 호출 순서** | 실제로 검증했던 step 순서대로 오케스트레이터가 `bash` 호출 |
| **ops만 실행** | step 스크립트는 `ops/{stage}/{group}.py` 를 `--project` / `--run-dir` 로 호출 |

### 디렉터리 구조

```
scripts/
├── README.md                                      # 이 파일 (사용법 + 생성 규칙)
├── verification_sequence.yaml                     # step 목록 SSOT
├── run_VERIF-CPU-SOC_verification_sequence.sh     # 전체 순서 오케스트레이터 (인자 없음)
├── _common.sh                                     # PROJECT_DIR, TAG, run_gate, log
├── _run_gate.sh                                   # init_run_dir, show_verdict
├── 01_{stage}_{검증제목_슬러그}.sh                 # step 스크립트
├── 02_...
├── 03_...
└── 99_generate_verification_reports.sh            # reports/index.yaml → MD 갱신
```

### step 스크립트 파일명

```
{NN}_{stage}_{검증_제목_슬러그}.sh
```

- `NN`: 검증 수행 순서 (`01`, `02`, …). `99_` 는 보고서 전용.
- `stage`: `sanity`, `static`, `simulation`, `regression` 등
- 슬러그: 공백→`_`, 소문자·하이픈 유지, **제목을 읽을 수 있게** (축약만 하지 말 것)

`VERIFICATION_TITLE`, `RUN_DIR_SUFFIX`, 파일명 슬러그는 **동일 문자열**을 쓴다.

### step 스크립트 골격

```bash
#!/usr/bin/env bash
# Step N — {검증 제목}
set -euo pipefail
source "$(dirname "$0")/_common.sh"

VERIFICATION_TITLE="{검증 제목}"
STEP="0N"
RUN_DIR_SUFFIX="0N_{stage}_{슬러그}"

source "$(dirname "$0")/_run_gate.sh"
require_cmd python3
init_run_dir "${RUN_DIR_SUFFIX}"

run_gate "${VERIFICATION_TITLE}" \
  python3 "${PROJECT_DIR}/ops/{stage}/{group}.py" \
    --project "${PROJECT_DIR}" \
    --run-dir "${RUN_DIR}"

show_verdict "${RUN_DIR}/verdict_{group}.json"
```

선행 도구·override 복사 등은 **해당 step에만** 넣는다 (예: Step 2 `hier-walk`, `inputs/tags/{tag}/overrides/`).

### verification_sequence.yaml

검증을 **실제로 돌린 순서**와 1:1로 `steps` 를 작성한다.

```yaml
steps:
  - step: 1
    verification_title: "…"      # 사람이 읽는 제목
    script: 01_….sh             # scripts/ 아래 파일명
    stage: sanity
    group: c-compile
```

gate를 추가하면: step 스크립트 생성 → yaml에 append → 오케스트레이터에 `bash` 한 줄 추가.

### 오케스트레이터

- 파일명: `run_{PROJECT_ID}_verification_sequence.sh`
- **인자·분기 없음** — yaml 순서대로 step만 `bash` 호출, 마지막에 `99_`
- `RUN_ID_PREFIX` 환경변수만 허용 (step별 `RUN_ID` 자동 부여)

### 보고서 연동

`reports/index.yaml`:

```yaml
verification_sequence:
  yaml: scripts/verification_sequence.yaml
  orchestrator: scripts/run_VERIF-CPU-SOC_verification_sequence.sh
  reports_script: scripts/99_generate_verification_reports.sh
  readme: scripts/README.md
```

- gate 항목에 `reproduce_script` / `prerequisite_script` **넣지 않음**
- `ops/report/generate_reports.py` 가 sequence yaml에서 step·스크립트 경로를 읽어 보고서에 삽입

### 하지 말 것

- `reproduce_main.sh` + gate 이름 인자
- gate별 단독 래퍼만 있고 전체 순서 오케스트레이터가 없는 구조
- 스크립트 파일명에 검증 제목이 안 보이는 축약 (`static_coi_conn.sh` 등)

---

## 전체 실행 (권장)

검증을 수행했던 **순서 그대로** 3단계 + 보고서:

```bash
cd /home/user/Desktop/soc-verify-agent/projects/VERIF-CPU-SOC
chmod +x scripts/*.sh
./scripts/run_VERIF-CPU-SOC_verification_sequence.sh
```

## 실행 순서 (고정)

| Step | 스크립트 (파일명에 검증 제목 포함) | 검증 제목 |
|------|-----------------------------------|-----------|
| 1 | `01_sanity_VerifCPU_c-compile_and_elab.sh` | Sanity — VerifCPU c-compile & elab |
| 2 | `02_static_COI_connectivity_chip_top.sh` | Static COI connectivity (chip_top) |
| 3 | `03_simulation_slave_R_W_single_burst_cpu_sync.sh` | Simulation slave R/W (single / burst / cpu_sync) |
| — | `99_generate_verification_reports.sh` | 보고서 MD 생성 |

순서 SSOT: [`verification_sequence.yaml`](./verification_sequence.yaml)

## 단계만 단독 실행

전체 순서의 일부만 다시 돌릴 때 (Step 1 선행 권장):

```bash
./scripts/01_sanity_VerifCPU_c-compile_and_elab.sh
./scripts/02_static_COI_connectivity_chip_top.sh
./scripts/03_simulation_slave_R_W_single_burst_cpu_sync.sh
```

`RUN_ID`를 직접 지정할 수 있습니다:

```bash
RUN_ID=my-run-step2 ./scripts/02_static_COI_connectivity_chip_top.sh
```

## 사전 요구

| 항목 | 용도 |
|------|------|
| `python3` | ops |
| `iverilog`, `vvp`, RISC-V gcc | VerifCPU |
| `hier-walk` | Step 2 — `pip install -e ~/tools/__CFI/hierwalk` |
| RTL clone root | `cache.yaml` → `clone.path` (`~/tools/__CFI`) + `rtl_subdir` |

## 산출물

`runs/{RUN_ID}/` — 기본 `RUN_ID`는 `verify-{tag}-{날짜}-{step접미사}` 형식.

## 보고서

`run_VERIF-CPU-SOC_verification_sequence.sh` 마지막에 `99_` 가 SUMMARY를 갱신합니다.  
`reports/index.yaml`의 `run_id`를 새 run에 맞게 수정한 뒤 `99_` 를 다시 실행하면 보고서에 반영됩니다.