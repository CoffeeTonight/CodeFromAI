# General Harness Procedure (고정 절차)

## Loop (과제마다 동일)

```
DISCOVER → ADAPT → INSTRUMENT → VERIFY → REPORT
     ↑                                    |
     └────────── FAIL analysis ───────────┘
```

## Step 1 — DISCOVER (환경 분석)

1. EDA tool detection (vcs, xrun, iverilog)
2. Compile entry (Makefile, filelist, top)
3. Sim launch command
4. Register sources (*.h, *.rdl, excel)
5. Memory map location
6. FW toolchain + load method
7. Log paths + existing pass/fail patterns

**Output:** `environment_manifest.yaml` (scanner 자동 + human confirm)

## Step 2 — ADAPT (능동적 환경 수정)

- `verif_log.h` + sink adapter 복사/생성
- Generated FW를 `artifacts.fw_out`에 배치
- Makefile에 `verif` 타깃 추가 (기존 flow 보존)
- `main.c` hook 또는 TB `$readmemh` 연결
- manifest에 실제 경로 반영

**원칙:** 기존 설계자 flow를 덮어쓰지 않음. additive only.

## Step 3 — INSTRUMENT (FW 목적 맞게 수정)

- VIM (verification intents) 로드
- intent별 C 코드 생성 (SFR read, SRAM R/W)
- VLP 로그 삽입 (`VERIF PASS/FAIL/SUMMARY`)
- compile → fix until FW builds

## Step 4 — VERIFY (Tier 게이트)

| Tier | 조건 | 실행 |
|------|------|------|
| 0 | manifest 존재 | compile + short sim |
| 1 | T0 PASS | FW env_sanity |
| 2 | T1 PASS | smoke intents |
| 3 | T2 PASS | full VIM |

## Step 5 — REPORT

- `verif_report.json`: tier results, VLP parse, logs
- FAIL 시: tier rollback + FW patch suggestion

## VLP Contract

```
VERIF PASS <test_id> <detail>
VERIF FAIL <test_id> <detail> expect=0x.. got=0x..
VERIF SUMMARY pass=N fail=M total=T result=PASS|FAIL
```

Parser는 `result=PASS` / `VERIF FAIL` 로 판정.