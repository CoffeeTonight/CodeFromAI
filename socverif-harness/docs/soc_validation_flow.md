# SoC 검증 절차 (soc_validation_flow)

**실행 지침:** 본 문서가 SoC 검증의 중앙 가이드라인이다. 단계별로 `eda_tool.md`를 참조하고, 사용자가 추가한 `{검증방법name}.md`를 본 flow에 병합·적용한 뒤 이 문서 순서대로 실행한다.

## 0. Toy mimic 원칙 (필수)

**무조건 사용자의 전체 SoC 환경을 직접 검증 시도하지 않는다.**

1. 사용자 SoC 검증 환경의 **레이아웃·EDA·타깃 이름·로그 패턴**만 추출
2. 동일 구조의 **아주 간단한 toy project** 생성:

```bash
# harness가 toy scaffold 생성 (header 복사 + .socverif/toy_mimic.yaml)
python3 -m socverif.cli toy-create <user_soc_root> --name my_chip_toy
python3 -m socverif.cli loop envs/my_chip_toy --max-tier 2
```

**목표 산출물:** `envs/toy_mimic_soc/` 또는 `toy-create` 출력; 참고: `minimal_soc`, `alt_soc`
3. **TAT가 대단히 짧은** (<30s/toy) **LLM이 돌릴수있는** 환경에서 반복
4. toy에서 **사용자 검증 환경의 실행 성공법** 획득 후, 필요 시 실환경으로 확장

### TAT tier (용도별 — 혼동 금지)

| TAT tier | 대표 명령 | 실측 TAT | 용도 |
|----------|-----------|----------|------|
| **toy loop** | `cli loop envs/toy_mimic_soc --max-tier 2` | **~1–3s** | LLM 매 iteration — **기본 반복 단위** |
| **PR gate** | `bash scripts/self_verify_pr.sh` | **~60s** | 빠른 self-harness (tier 0–1) |
| **nightly** | `bash scripts/self_verify_nightly.sh` | **~75s** | reference envs 포함 (tier 0–2) |
| **goal orchestrator** | `bash scripts/run_goal_verification.sh` | **~3min** | CI/goal acceptance — toy 반복과 별도 |

**원칙:** LLM은 toy loop tier에서 수정·재실행하고, PR/nightly/goal orchestrator는 주기적 게이트로만 사용한다.

```bash
# toy mimic 예 (toy-first gate — non-toy env는 --allow-full-soc 필요)
python3 -m socverif.cli loop envs/toy_mimic_soc --max-tier 2
python3 -m socverif.cli loop envs/minimal_soc --max-tier 2
python3 -m socverif.cli loop envs/alt_soc --max-tier 1
```

**코드 강제:** `socverif/toy_policy.py` — toy가 아닌 경로는 `discover`/`instrument`/`inspect`/`run`/`loop` 시 exit 2 (self-harness root 제외). 우회: `--allow-full-soc`.

## 1. 사용자 검증방법 통합

사용자가 `docs/methods/{검증방법name}.md` (또는 프로젝트 루트)를 추가하면:

1. `{검증방법name}.md`의 절차·명령·PASS 기준을 읽는다
2. 본 `soc_validation_flow.md`의 해당 단계(§2~§8)에 **병합**한다
3. toy project에만 먼저 적용·실행한다
4. 성공 시 `success_flow.md`에 기록; 실패 시 `failed_flow.md`에 파훼법 기록

**병합 예시:**

```markdown
# docs/methods/custom_sfr_burst.md  → soc_validation_flow §3 C코드 수정에 추가
- SFR burst write 시 word-aligned만 허용
```

## 2. DISCOVER → ADAPT (환경 분석)

```bash
python3 -m socverif.cli discover <toy_root>
python3 -m socverif.cli inspect <toy_root> --json
```

확인: `eda.simulator`, `tiers[]`, `register_sources`, `pass_fail.protocol`  
상세: `eda_tool.md` §1~§3

## 3. 헤더 컴파일 (header 컴파일)

| 단계 | 작업 |
|------|------|
| 1 | `include/soc_regs.h` 등 register header 탐지 |
| 2 | `#define` 주소·오프셋 파싱 (`fw_gen.parse_reg_header`) |
| 3 | FW/TB compile 시 `-I include` 추가 |
| 4 | header 변경 후 **재-discover** 또는 manifest 수동 갱신 |

**검증:** header 심볼로 MMIO read smoke (tier 2)

## 4. 목적에 맞는 C코드 수정 (C코드 수정)

### 4.1 일반 원칙

- 검증 intent 1개당 함수 1개 + `VERIF PASS/FAIL` 로그
- volatile pointer cast로 MMIO 접근: `*(volatile uint32_t *)ADDR`
- 실패 시 `expect` / `got` hex 출력

### 4.2 성능 규칙 — **SFR내 bit field 개별 접근 금지**

**상관 관계없는 SFR 내 bit field를 개별 read-modify-write로 반복 접근하지 않는다.**

| 금지 | 권장 |
|------|------|
| `reg |= (1<<3); reg |= (1<<7);` (동일 SFR 2회 RMW) | 한 번 read → 필요한 bit만 mask → 한 번 write |
| unrelated field를 건드리는 부분 쓰기 | 전체 word 단위 접근 또는 shadow register |
| 루프 내 매 iteration SFR bit toggle | 배치 쓰기 + summary VLP 1회 |

**이유:** bus transaction 수 증가 → sim TAT 증가 → LLM 반복 비용 증가

### 4.3 생성 FW 수정 + compile (fw compile)

```bash
python3 -m socverif.cli instrument <toy_root>
# generated/verif/verif_tests.c — instrument가 header에서 생성
make -C <toy_root> fw-compile-tier2   # gcc -DHOST_VERIF
make -C <toy_root> sim-tier2            # ./sim_build/verif_t2 → VERIF SUMMARY in log
```

tier 1/2 smoke는 **TB `$display`가 아닌** `verif_run_all()` C 실행 경로를 사용한다 (`envs/common/fw_rules.mk`).

### 4.4 사용자 방법: SFR batch (`example_sfr_batch.md`)

`docs/methods/example_sfr_batch.md`에서 병합된 절차 (다른 `{검증방법name}.md`도 동일 패턴):

1. 동일 SFR bit field 변경은 **한 번의 read → mask → write**로 배치 (§4.2 강화)
2. tier 2 smoke에서 `VERIF PASS` 1회만 기록
3. **toy** (`envs/toy_mimic_soc`)에서만 먼저 실행
4. PASS: VLP `VERIF SUMMARY` FAIL=0, `verif_report.json` → `all_passed: true`

**병합 검증:**

```bash
python3 -m socverif.user_methods --json   # 모든 docs/methods/*.md가 본 flow에 인용됐는지
bash scripts/docs_check.sh                # USER_METHODS_CHECK_PASS
```

## 5. FW compile 및 디버깅법 (fw compile)

| 단계 | 명령/확인 |
|------|----------|
| compile | `manifest.firmware.build_cmd` 또는 프로젝트 Makefile `fw` 타깃 |
| link | TB `$readmemh` 또는 DPI로 FW 이미지 로드 |
| 실행 | sim 후 log에서 `VERIF SUMMARY` |
| 디버깅 | `grep -E 'VERIF (PASS|FAIL)' sim_logs/*.log` |
| 실패 | `failed_flow.md` 패턴 검색 → 동일 rc/메시지 재발 방지 |

## 6. vcd dump할 신호 정하는 법 (VCD dump할 신호)

1. **목적 정의:** 어떤 버스 트랜잭션/SFR write를 검증하는가?
2. **최소 신호:** `clk`, `rst_n`, 실패한 `bus_*` 또는 `sfr_*`
3. **TB 설정:**

```verilog
// tier별 파일 + 선택적 DUT 신호만 (minimal_soc / toy_mimic_soc 패턴)
`ifdef VERIF_TIER2
  $dumpfile("sim_logs/tier2.vcd");
  $dumpvars(1, u_dut.bus_addr, u_dut.bus_rdata, u_dut.bus_ready);
`elsif VERIF_TIER1
  $dumpfile("sim_logs/tier1.vcd");
  $dumpvars(1, u_dut.clk, u_dut.rst_n, u_dut.bus_valid);
`else
  $dumpfile("sim_logs/tier0.vcd");
  $dumpvars(1, u_dut.clk, u_dut.rst_n);
`endif
```

4. **금지:** `$dumpvars(0, tb_<top>)` 전체 계층 dump, 무관 SFR bit-field 개별 접근과 동일하게 TAT·용량 폭증
5. **재현:** tier N sim → `sim_logs/tierN.log` + `sim_logs/tierN.vcd` 쌍으로 보관 (동일 tier 인덱스)

## 7. RTL compile / simulation / debugging

### 7.1 Compile

```bash
make compile          # 또는 discover된 compile_cmd
# iverilog: -g2012 -I rtl -I tb -o sim_build/*.vvp
```

### 7.2 Simulation

```bash
make sim              # tier 0
make sim-tier2        # smoke
# 또는: python3 -m socverif.cli run <toy> --max-tier 2
```

### 7.3 Debugging

| 증상 | 조치 |
|------|------|
| compile error | filelist, include path, timescale |
| sim hang | TB `$finish`, timeout in runner |
| VLP FAIL | C/RTL expected 값, reset sequence |
| rc!=0 | log tail + `weakness_mining` |

상세 EDA별 명령: `eda_tool.md` §6~§7

## 8. 재검증 진행법

```
FAIL 발생
  → weakness_mining / failed_flow.md 확인
  → toy에서 수정 (헤더/FW/RTL/TB)
  → python3 -m socverif.cli loop <toy> --max-tier <N>
  → PASS 시 success_flow.md 기록
  → self-harness: bash scripts/self_verify_pr.sh
  → nightly: bash scripts/self_verify_nightly.sh
```

**Self-harness 반복 (능력 획득까지):** toy에서 실행 성공법을 얻을 때까지 아래 사이클을 **반복**한다 (`begin_goal_round` → 수정 → `note_round_path`). 한 번 PASS로 끝내지 않는다.

```bash
# 1) toy loop — LLM 기본 단위 (~1–3s), 동일 명령 3회 연속 PASS 권장
for i in 1 2 3; do
  python3 -m socverif.cli loop envs/toy_mimic_soc --max-tier 2
done

# 2) capability gate — repeat until PASS (OBJECTIVE: until)
source scripts/resolve_goal_env.sh
SCRATCH="$SCRATCH/until" bash scripts/self_harness_until.sh
# → SELF_HARNESS_UNTIL_PASS (each attempt runs acquire: streak>=3 + probe + toy-create)

# 3) goal orchestrator — workspace_delta + preflight_final_claims + plan_contract defects=[]
bash scripts/run_goal_verification.sh   # SCRATCH=/home/user/tools/socverif-harness-work/goal/implementer
```

`verify_goal.sh`는 `SOCVERIF_TOY_LOOP_REPEAT`(기본 **3**)만큼 `toy_mimic_soc` loop를 매 streak 라운드마다 실행한다. OBJECTIVE **until** 은 `self_harness_until.sh`가 acquire **PASS** 할 때까지 반복한다 (`SOCVERIF_UNTIL_MAX=0` 기본 = 무제한, 안전상한 `SOCVERIF_UNTIL_WALL_SEC=3600`). 라운드는 **반드시** `bash scripts/begin_goal_round.sh`(snapshot 선캡처) → 소스 수정 → 각 파일마다 `note_round_path` 순서로 진행한다. FINAL/delivery는 **source 경로만** (`docs/`, `socverif/`, `scripts/`, `tests/`, `envs/` — `.socverif/scratch`·`DELIVERY_BUNDLE.json` 등 runtime metadata 제외). goal session `verification_evidence.json`의 `source_paths`와 scratch `round_changed_paths.txt`가 일치해야 한다. 실패 시 `failed_flow.md` 파훼법 적용 후 toy부터 재시작.

**검증 계약 (plan.md):** 아래를 `{SCRATCH}`에 캡처하며 한 번에 실행할 수 있다.

```bash
source scripts/resolve_goal_env.sh   # SCRATCH + SOCVERIF_GOAL_ROOT under /home/user/tools/socverif-harness-work/
bash scripts/run_goal_verification.sh
```

필수 관측: `docs_check` PASS, `PREFLIGHT_FINAL_CLAIMS` ok (또는 gate-only count=0), `self_verify_pr`/`nightly`×2 PASS, `minimal_soc` loop `--max-tier 2` 시 `verif_report.json`의 `max_tier=2`·`tiers_run=3`, `SELF_HARNESS_CAPABILITY_ACQUIRED streak=3`, unittest OK, toy Makefile에 `tee -a` 없음.

## 9. Tier 게이트 요약

| Tier | 이름 | toy에서의 의미 |
|------|------|----------------|
| 0 | rtl_sanity | compile + sim boot |
| 1 | env_sanity | VLP env_sanity |
| 2 | smoke | SFR read + SRAM R/W |
| 3 | prepared | full intent |

## 10. 문서 맵

| 문서 | 역할 |
|------|------|
| `eda_tool.md` | 도구·명령 레퍼런스 |
| `soc_validation_flow.md` | **본 문서 — 실행 지침** |
| `{검증방법name}.md` | 사용자 추가 → §1 병합 |
| `success_flow.md` | 성공 절차·소요 시간 |
| `failed_flow.md` | 실패·파훼법 |