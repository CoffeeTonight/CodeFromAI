# EDA Tool 사용법 (eda_tool)

socverif-harness가 지원·탐지하는 EDA 도구, 헤더/FW/VCD, Makefile 타깃, harness CLI 통합 사용법을 정리한다.

## 1. 지원 EDA 시그니처

| Vendor | Simulator | 탐지 패턴 (eda_stage) | 전형 compile | 전형 sim |
|--------|-----------|----------------------|--------------|----------|
| Synopsys | VCS | `vcs`, `verdi`, `simv` | `make compile` / `vcs -f` | `make sim` / `./simv` |
| Cadence | Xcelium | `xrun`, `xcelium`, `xmelab` | `xrun -compile` | `xrun -R` |
| Siemens | Questa | `vsim`, `questa`, `vlog -` | `make compile` | `make sim` |
| Opensource | iverilog | `iverilog`, `vvp` | `iverilog -o *.vvp` | `vvp *.vvp` |

**탐지:** `python3 -m socverif.cli discover <root>` → `environment_manifest.yaml`의 `eda.vendor` / `eda.simulator`.

**상용 EDA (VCS/Xcelium/Questa):** harness는 Makefile/스크립트 **시그니처 탐지**와 문서화된 compile/sim 패턴을 제공한다. 라이선스·바이너리가 없는 환경에서는 `synthetic_vcs_style` 래퍼 + `iverilog` toy로 대체 검증한다. vendor 바이너리가 있으면 discover된 `compile_cmd`/`sim_cmd`를 그대로 사용.

**주의:** Makefile 변수명 `VLOG`만으로 Questa 오탐하지 않도록 가중치 스코어링 사용 (`alt_soc` 참고).

## 2. Makefile 타깃 규약 (GenericAdapter)

| 타깃 패턴 | Tier | 용도 |
|-----------|------|------|
| `compile`, `build`, `elab` | — | compile_cmd |
| `sim`, `run`, `basic`, `sanity` | 0 | RTL sanity |
| `sim-tier1`, `env_sanity` | 1 | env sanity |
| `sim-tier2`, `smoke` | 2 | smoke |
| `sim-tier3`, `prepared` | 3 | full intents |

**예 (minimal_soc):**

```bash
cd envs/minimal_soc
make compile          # iverilog → sim_build/sim.vvp
make sim              # vvp tier0
make sim-tier2        # SFR/SRAM smoke (VERIF_TIER2)
```

## 3. Shell script 전용 환경 (script_only_soc)

Makefile 없이 `scripts/compile.sh` + `scripts/run_sim.sh`만 있는 경우:

```bash
python3 -m socverif.cli discover envs/script_only_soc
python3 -m socverif.cli loop envs/script_only_soc --max-tier 0
```

`script_stage`가 `compile`/`run` 역할을 분류한다.

## 4. Register header 처리

1. **탐지:** `*regs*.h`, `soc_regs.h`, `mmio_map.h` 등 (`structure_stage`)
2. **파싱:** `fw_gen.parse_reg_header()` — `#define SYM 0x...` 매크로 추출
3. **instrument:**

```bash
python3 -m socverif.cli instrument envs/minimal_soc
# → generated/verif/verif_log.h, verif_tests.c, verif_env_sanity.c
```

4. **헤더 컴파일:** FW 빌드 시 `-I include` + header path를 manifest `register_sources.primary.path`에 반영

## 5. FW 생성·컴파일·디버깅

| 단계 | 명령/산출물 |
|------|------------|
| VLP 헤더 | `generated/verif/verif_log.h` (`VERIF PASS/FAIL/SUMMARY`) |
| 테스트 생성 | `fw_gen.generate_verif_tests(header, out_dir)` |
| env_sanity | `instrument_env_sanity()` → `verif_env_sanity.c` |
| 컴파일 | `make fw` / `make fw-compile-tier2` (`envs/common/fw_rules.mk`, host gcc `-DHOST_VERIF`) |
| 실행 | `make sim-tier1` / `sim-tier2` → `verif_run_all()` stdout → `sim_logs/tierN.log` |
| 디버깅 | sim log에서 `VERIF FAIL` / `expect=` / `got=` 검색; `grep VERIF sim_logs/*.log` |

**VLP 계약:**

```
VERIF PASS <test_id> <detail>
VERIF FAIL <test_id> <detail> expect=0x.. got=0x..
VERIF SUMMARY pass=N fail=M total=T result=PASS|FAIL
```

## 6. VCD dump 신호 선택

| 원칙 | 설명 |
|------|------|
| 최소 덤프 | 실패 버스 트랜잭션 전후 1~2 클럭 + 관련 SFR/SRAM 인터페이스 |
| 계층 | tier별 `sim_logs/tier<N>.vcd`; `$dumpvars(1, u_dut.<signals>)` 선택적 덤프 |
| 성능 | 전 칩 full dump 금지 — TAT·디스크 폭증 |
| 위치 | TB `initial` 블록; log dir은 `sim_logs/` 또는 `logs/` |

**minimal_soc 예:**

```verilog
initial begin
`ifdef VERIF_TIER2
  $dumpfile("sim_logs/tier2.vcd");
  $dumpvars(1, u_dut.bus_addr, u_dut.bus_rdata);
`else
  $dumpfile("sim_logs/tier0.vcd");
  $dumpvars(1, u_dut.clk, u_dut.rst_n);
`endif
end
```

**sim 로그 (single-writer):** toy Makefile은 `envs/common/sim_rules.mk`의 `SIM_RUN` 매크로 사용 — `vvp -l` + `tee` 동시 쓰기 금지. 명령 생성: `python3 -m socverif.sim_log run <vvp> <log>`.

## 7. RTL compile / simulation / debugging

### iverilog (toy 기본)

```bash
iverilog -g2012 -I rtl -I tb -o sim_build/sim.vvp rtl/*.v tb/*.v
vvp sim_build/sim.vvp -l sim_logs/tier0.log
```

### VCS 스타일 (synthetic_vcs_style)

```bash
bash envs/synthetic_vcs_style/scripts/vcs/compile.sh   # 래퍼 스크립트
make -C envs/synthetic_vcs_style sim
```

### 디버깅 루프

1. sim log tail 확인 (`runner` → `log_tail`, `verif_report.json`)
2. VCD: `gtkwave sim_logs/tb.vcd` (로컬)
3. FAIL 패턴: `FATAL`, `UVM_FATAL`, `VERIF FAIL`
4. `weakness_mining` (report) 제안 따르기

## 8. Per-round harness 추적 (portable hunk)

Grok 세션 없이도 round **source_paths**·preflight가 동작하도록 **로컬 hunk**를 사용한다.

| 우선순위 | 소스 | 설정 |
|----------|------|------|
| 1 | 환경변수 | `SOCVERIF_GOAL_HUNK=/path/to/hunk_records.jsonl` |
| 2 | 로컬 (권장) | `.socverif/hunk_records.jsonl` — `record_goal_round.sh`가 매 라운드 append |
| 3 | 레거시 | goal session `hunk_records.jsonl` (있을 때만 fallback) |

```bash
# 라운드 시작 — 반드시 소스 수정 전에 snapshot (honest per-round delta)
bash scripts/begin_goal_round.sh

# 라운드 중 단일 파일 변경 기록 (LLM iteration)
bash scripts/note_round_path.sh socverif/cli.py

# 라운드 종료 시 (orchestrator가 자동 호출)
python3 -m socverif.hunk_tracking append --from-file round_changed_paths.txt

# per-round path log — round_paths.jsonl (sole FINAL source)
python3 -m socverif.round_paths list-only --since-file .socverif/round_start_ts
bash scripts/final_response_paths.sh   # FINAL_RESPONSE may cite ONLY these paths
bash scripts/emit_final_response.sh    # gate-only template or path list
bash scripts/preflight_final_claims.sh
bash scripts/sync_classifier_evidence.sh   # CHANGED_FILES for classifier

# cumulative preflight (legacy round_delta)
python3 -m socverif.round_delta --since-file .socverif/round_start_ts --min-new 1
SOCVERIF_REQUIRE_HUNK=1 python3 -m socverif.hunk_tracking check
```

## 9. Harness CLI 통합

| 명령 | 용도 |
|------|------|
| `discover <root>` | 환경 스캔 → manifest |
| `inspect <root> [--json]` | manifest 미리보기 |
| `instrument <root>` | VLP FW 생성 |
| `run <root> [--max-tier N]` | tier 실행 → `verif_report.json` |
| `loop <root>` | discover+instrument+run 반복 |
| `toy-create <user_root>` | 사용자 SoC env에서 short-TAT toy scaffold 생성 |
| `python3 -m socverif.verify_report .` | 구조화 PASS 게이트 |

**Self-harness (harness 자기 검증):**

```bash
bash scripts/self_verify_pr.sh       # tier 0-1
bash scripts/self_verify_nightly.sh  # tier 0-2 + reference envs
```

산출물: `.socverif/scratch/environment_manifest.yaml`, `verif_report.json`

## 10. Pass/Fail 프로토콜

| protocol | 판정 |
|----------|------|
| `exit_code` | sim_rc == 0 |
| `log_pattern` | pass_patterns 매칭 + rc==0 |
| `vlp` | VERIF SUMMARY result=PASS |
| `composite` | rc + log + VLP 조합 |

## 11. Workspace delivery + classifier evidence

Goal verification uses **tools work layout** (`/home/user/tools/socverif-harness-work/`) — scratch·goal·outer mirror (not `/tmp`):

```bash
source scripts/resolve_goal_env.sh
# Full deliverable tree CFA → $GROK_WORKSPACE_ROOT/socverif-harness/
python3 -m socverif.classifier_evidence sync-tree --cfa-harness . --scratch "$SCRATCH"

# CHANGED_FILES + patch = round_paths only (honest delta)
bash scripts/sync_classifier_evidence.sh
```

`run_goal_verification.sh` sets `SOCVERIF_VERIFY_FROM_WORKSPACE=1` (default): sync-tree then `cd` workspace harness before toy loops / unittest.

## 12. 관련 문서

- `docs/soc_validation_flow.md` — 실행 지침 (본 문서를 단계별로 참조)
- `docs/success_flow.md` / `docs/failed_flow.md` — 성공·실패 기록
- `docs/03_harness_procedure.md` — DISCOVER→ADAPT→INSTRUMENT→VERIFY