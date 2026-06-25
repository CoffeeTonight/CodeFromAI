# VerifCPU Verilog Model (iverilog)

**독립 패키지** — `verif_cpu_verilog/` 디렉터리만 복사해도 campaign 빌드·시뮬이 동작합니다.  
(`firmware/campaign`, `tools/probe_icodes.py` 포함. `verif_cpu_project` 불필요.)

공식 검증 게이트는 **iverilog 시뮬레이션 + VCD 후처리**입니다.  
Python 모델은 동일 TB 흐름을 따르는 cross-check reference이며, PASS/FAIL의 authoritative source는 이 디렉터리입니다.

## 빠른 시작

```bash
# 전체 파이프라인 (생성 → 시뮬 → VCD 검증)
./example.sh

# 또는 Makefile 직접 호출
make full_campaign    # = verify (권장)
```

성공 시 체크리스트 **43/43 PASS**, `vcd_marker = 0xDEADDEAD`.

## 사전 요구사항

| 도구 | 용도 |
|------|------|
| `iverilog` (≥ -g2012) | RTL 컴파일 |
| `vvp` | 시뮬 실행 |
| `python3` + `pip` | 생성 스크립트, `verify_vcd.py` |
| `riscv64-unknown-elf-gcc` 등 | VCPU/icode C 펌웨어 빌드 (`firmware/campaign`) |

```bash
# Debian/Ubuntu 예시
sudo apt install iverilog python3 python3-pip
# RISC-V 툴체인은 보드/환경에 맞게 설치

# Python 의존성 (example.sh / make config 가 자동 설치함)
python3 -m pip install -r requirements.txt   # tinyrv, PyYAML
```

## 디렉터리 구조

```
verif_cpu_verilog/
├── rtl/                  # verif_cpu_core, unified pool, SoC, agent
├── tb/                   # tb_full_campaign.v (메인), tb_soc_dut.v, …
├── include/              # 생성된 .vh (수동 편집 금지 항목 多)
├── firmware/
│   ├── campaign/         # VCPU/icode 빌드 + manifest (SSOT)
│   └── *.hex             # merge 산출 + harness 고정 hex
├── tools/                # verify_vcd.py, probe_icodes.py, integration_studio/
├── outputs/              # integration_studio 생성물 (생성됨)
├── logs/                 # 시뮬 로그 (생성됨, .gitignore)
├── sim_build/            # .vvp / .vcd (생성됨)
├── example.sh
└── Makefile
```

펌웨어·매니페스트 소스는 **`firmware/campaign/`** (이 패키지 안에 포함) 에 있습니다.

## 아키텍처 요약

| 구성요소 | 역할 |
|----------|------|
| **SCPU0 `verif_agent_master`** | Phase 게이트, `init_done` poll, manifest hint 주입 (C FW 없음) |
| **SCPU1–N `verif_cpu_core`** | VCPU — Phase A/B/C RV32 펌웨어 (`campaign_slots.yaml` → `cpus.mk`) |
| **N× `verif_agent_slave`** | SoC tap snoop, icode slot 검증 (최대 `max_slots`, active만 campaign 실행) |
| **`verif_cpu_unified_pool`** | VCPU FW + icode pool (≤256 KiB → readmemh embed) |
| **`simple_soc`** | 17-step `soc_init_seq`, SFR/SRAM/UART peripheral |

블록 다이어그램·최근 검증 스냅샷: [architecture_example.md](architecture_example.md)

## VCPU 특수 명령어 (custom-0)

VCPU는 **RV32I subset** (ALU·shift·branch·jump·lw/sw·lui/auipc) + **검증 전용 custom 명령**을 실행합니다. `slli`/`srli`/`srai`, `blt`/`bge`/`bltu`/`bgeu`, `auipc` 등이 포함됩니다 (lb/h 등 일부 load/store 폭은 미지원). 펌웨어 작성자는 C 매크로만 쓰면 되고, RTL은 `opcode 0x0B` (custom-0) + `funct7` selector로 디코드합니다.

| 참고 파일 | 내용 |
|-----------|------|
| `firmware/campaign/include/verif_insns.h` | 펌웨어 매크로 **SSOT** (`vstop`, `vsync`, …) |
| `include/verif_cpu_defs.vh` | selector 상수, wave/sync 상태 정의 |
| `firmware/campaign/cpu_*/phase_*.c` | 캠페인 실사용 예제 |

### 인코딩 규칙

모든 매크로는 `_ENC_CUSTOM(sel, rd, rs1, rs2)`로 한 워드를 만듭니다 (`firmware/campaign/include/verif_insns.h`가 **SSOT**).

- **selector** → `funct7` (7비트)
- **레지스터 번호** → `rd` / `rs1` / `rs2` (각 5비트)
- `rs1==0`일 때 primary operand는 **`rd` 필드**를 사용합니다 (`vforce(20,21)` → rd=20, rs2=21)
- 즉시값 id 전용 매크로는 `rd`에 id를 넣습니다 (`vsync(10)` → `rd=10`)

**콘솔 vs 펌웨어 인자 순서**

| 명령 | 펌웨어 매크로 (레지스터 번호) | `console_cmd` (리터럴 값) |
|------|------------------------------|---------------------------|
| `vhw_force` | `(addr_r, hier_r, val_r)` | `(hier, addr, value)` |
| `vhw_release` | `(addr_r, hier_r)` | `(hier, addr)` |
| `hw_force_set` (platform) | — | `(hier, addr, value)` |

펌웨어는 `_ENC_CUSTOM` 필드 배치를 따르고, 콘솔은 `hw_force_set(hier, addr, value)` task 인자 순서를 그대로 씁니다.

펌웨어에 삽입:

```c
#include "verif_insns.h"   // campaign 펌웨어
#include "soc_regs.h"      // SFR_CTRL 등 주소 상수
```

RV32I 인라인 매크로 (`rv_*`): `rv_addi`, `rv_lui`, **`rv_auipc`**, `rv_lw`/`rv_sw`, `rv_add`/`rv_sub`, `rv_beq`, `rv_jal`/`rv_jalr` 등 — `verif_insns.h` SSOT.
`rv_auipc(rd, imm20)` → `x[rd] = pc + (imm20 << 12)`.

### 명령 요약표

| 매크로 | sel | 설명 |
|--------|-----|------|
| `vstop()` | `0x00` | 이 VCPU의 시뮬 스텝 종료 요청 |
| `vwdt_set_rs1(r)` | `0x01` | WDT 한도 = `x[r]` (step 수) |
| `vdummy_on/off()` | `0x02`/`0x03` | 버스 read를 `0xDEADDEAD`로 대체 |
| `vwdt_pet()` | `0x04` | WDT 카운터·fired 플래그 클리어 |
| `vtrace_enter/exit/log` | `0x10`–`0x12` | `SCPUx_FN >` 콜스택 트레이스 |
| `vsync(id)` | `0x13` | 멀티-CPU sync barrier |
| `vassert_id(id)` | `0x14` | 검증 assert (pass/fail 카운트) |
| `vforce` / `vrelease` | `0x15`/`0x16` | CPU **로컬** 레지스터 force |
| `vwave(cmd, arg)` | `0x17` | per-CPU wave 샘플 기록 |
| `vhw_force` / `vhw_release` | `0x18`/`0x19` | **hierarchy + 버스주소** HW read force |

---

### 1. 실행 제어 — `vstop`, Phase 진입

각 Phase 펌웨어는 고정 오프셋(`.phase_a` `@0x000`, `.phase_b` `@0x100`, …)에 배치됩니다. Phase 끝에서 **`vstop()`** 을 호출해 TB가 다음 단계로 넘어갈 수 있게 합니다.

```c
// common/phase_a.c — SoC init 후 종료
vtrace_enter(0xA0);
load_soc_addr(10, SFR_CTRL);
rv_sw(11, 10, 0);          // peripheral write
vtrace_exit(0xA0);
vstop();                     // TB: request_sim_stop → Phase A 완료
```

`vstop` 없이 루프만 돌면 TB `run_cpu_core`가 max_steps까지 기다립니다.

---

### 2. WDT — `vwdt_set_rs1`, `vwdt_pet`

WDT는 **step마다** 카운트합니다. 한도에 도달하면 recovery(리셋 + txn replay + dummy 진입)가 트리거됩니다.

```c
rv_addi(1, 0, 8);            // 8 step 한도
vwdt_set_rs1(1);             // wdt_timeout = x1
// ... 버스 접근 없이 루프만 돌면 hang ...
vwdt_pet();                  // 정상 경로에서 watchdog 해제
```

UART 캠페인(`cpu_uart/uart_fw.c`)은 hang 구간에서 recovery를, recover 구간에서 `vwdt_pet` + `vassert`로 복구를 검증합니다.

---

### 3. 더미 모드 — `vdummy_on` / `vdummy_off`

의심 주소·recovery 이후 **버스 read 결과를 `0xDEADDEAD`로 통일**할 때 씁니다. write는 recorder에 남고, read만 더미 값을 받습니다.

```c
vdummy_on();
load_soc_addr(10, SFR_XZ_PORT);
rv_lw(11, 10, 0);           // → 0xDEADDEAD (실제 SoC 값 아님)
vdummy_off();                // 정상 read 복귀
```

Phase C SFR는 DEADDEAD/X/Z 검증과 함께 사용합니다.

---

### 4. 함수 트레이스 — `vtrace_*`

펌웨어가 직접 `SCPU1_FN > func_16 enter` 형태 로그를 냅니다. id는 5비트(`0x00`–`0x1F`)만 인코딩됩니다.

```c
vtrace_enter(0xA0);
vtrace_log(0xA1);            // 임의 메시지 id
vtrace_exit(0xA0);             // enter와 쌍 맞추기 (mismatch 시 경고)
```

---

### 5. Assert — `vassert_id` / `vassert_rs1`

조건 레지스터가 0이 아니면 PASS, 0이면 FAIL 카운트를 올립니다.

- `vassert_id(id)` — **x1**을 조건으로 검사 (`rs1==0` → RTL/Python 모두 x1 fallback)
- `vassert_rs1(rs1, id)` — 임의 레지스터를 조건으로 검사

```c
rv_xor(13, 11, 12);          // 기대값과 비교
rv_addi(1, 0, 0);
rv_beq(13, 1, 8);            // equal이면 skip
rv_addi(1, 0, 1);            // fail path
vassert_id(40);              // x1!=0 이면 PASS 카운트++
/* 또는 */ vassert_rs1(1, 40);
```

`assert_pass` / `assert_fail`는 TB 체크리스트에서 집계됩니다.

---

### 6. 로컬 force — `vforce` / `vrelease`

**CPU 내부 x레지스터**를 시뮬레이터가 강제합니다. SoC 버스와 무관합니다.

```c
rv_addi(20, 0, 1);           // target = x20
rv_addi(21, 0, 0x55);        // value  = x21
vforce(20, 21);              // x20 읽기 → 0x55, 쓰기 무시
rv_addi(22, 0, 0);
rv_add(22, 22, 20);          // x22 = 0x55 확인
vrelease(20);                // 강제 해제
```

`target >= 32`이면 CPU 로컬 mem shadow에 기록되지만, 일반 펌웨어는 레지스터 쌍 `(rd, rs2)` 패턴을 씁니다.

---

### 7. HW force — `vhw_force` / `vhw_release` (hierarchy)

**SoC 버스 read를 가로채는** 전역 force 테이블(`u_hw_force`)입니다. 엔트리 키는 **`(hier_id, bus_addr)`** 입니다.

| 항목 | 설명 |
|------|------|
| `hier_id` | VCPU `hierarchy_id`와 일치해야 hit (캠페인: SCPU1=`0x10`, SCPU2=`0x20`, SCPU3=`0x30`) |
| `bus_addr` | `load_soc_addr`로 만든 물리 주소 (예: `SFR_CTRL` = `0x4000_0000`) |
| wildcard | `hier_id = 0xFFFF_FFFF` → 모든 hierarchy에 적용 |

인코딩 (`verif_insns.h` SSOT): **`vhw_force(addr_r, hier_r, val_r)`** → `rd`=주소 레지스터, `rs1`=hier 레지스터, `rs2`=값 레지스터.

```c
load_soc_addr(10, SFR_CTRL); // x10 = 0x40000000
rv_addi(14, 0, 0x10);        // Hier10 — SFR VCPU hierarchy
rv_lui(16, 0x5);             // force value 0x5000
vhw_force(10, 14, 16);       // (hier=0x10, addr=0x40000000, val=0x5000) 등록

rv_lw(11, 10, 0);            // SoC 대신 0x5000 반환
// ... vassert로 검증 ...

vhw_release(10, 14);         // 엔트리 삭제
rv_lw(11, 10, 0);            // 실제 SFR_CTRL 값 (예: 0x1)
```

UCLI 콘솔은 **리터럴 (hier, addr, value)** 순서입니다 (`console_cmd` 예제 참고).

시뮬 로그 예:

```
[HWForce] set hier=0x00000010 addr=0x40000000 val=0x00005000
SCPU1 > [HWForce] READ 0x40000000 => 0x00005000 (hier=0x00000010)
[HWForce] release hier=0x00000010 addr=0x40000000
```

**`vforce`와 혼동하지 말 것**

| | `vforce` | `vhw_force` |
|---|----------|-------------|
| 범위 | 이 CPU의 x레지스터 | 버스 주소 + hierarchy |
| 버스 트랜잭션 | 없음 | `lw`가 force 값을 받음 |
| 테이블 | CPU 내부 | TB `u_hw_force` (공유) |

---

### 8. 멀티-CPU sync — `vsync`

`vsync(id)`는 **barrier 참여**입니다. TB가 먼저 `sync_configure(id, participant_mask)`를 호출해야 합니다.

**캠페인 parallel barrier** (`@0x380`, id=`10`, mask=`0x7` = SCPU1+2+3):

```c
// cpu_sfr/sync_barrier.c (SRAM/UART 동일 패턴)
vsync(CAMPAIGN_SYNC_BARRIER_ID);  // id=10, 3 CPU 모두 도착할 때까지 대기
load_soc_addr(10, SFR_CTRL);
rv_lw(11, 10, 0);                 // barrier 해제 후 버스 접근
vassert_id(50);
vstop();
```

**solo marker** (`expected[id]==0`): TB configure 없이 호출하면 대기 없이 통과합니다. Phase C에서 `vsync(1)` / `vsync(2)` / `vsync(3)` 이 이 용도입니다.

TB 측 흐름 (`gen_tb_campaign.py` 생성):

1. `u_sync.sync_configure(8'd10, 64'd7)`
2. `start_cpus_parallel(0x380)` — 3 CPU 동시 PC
3. `run_cpus_parallel(800)` — `SYNC_WAIT` 중 `sync_poll`로 resume

---

### 9. Wave 덤프 — `vwave`

per-CPU wave 버퍼에 PC/레지스터 샘플을 쌓고, Phase 끝 `wave_export_vcd`로 파일을 냅니다.

| `cmd` | 의미 |
|-------|------|
| `0` (`WAVE_CMD_OFF`) | 기록 중지 |
| `1` (`WAVE_CMD_ON`) | 기록 시작 |
| `2` (`WAVE_CMD_DUMP_ALL`) | 모든 scope |
| `3` (`WAVE_CMD_DUMP_SCOPE`) | `arg` = hierarchy id (예: `0x10` → `Hier10`) |

```c
vwave(1, 0);        // ON
vwave(3, 0x10);     // Hier10 scope만
// ... 실행 ...
vwave(0, 0);        // OFF
```

---

### 10. EDA interactive 콘솔 (VCS / Xcelium)

**iverilog `vvp`는 batch 전용** — Ctrl+C는 프로세스 종료이며, 시뮬 중 `call` 콘솔이 없습니다. Interactive 디버그는 VCS/Xcelium을 사용합니다.

1. `+console_pause`로 VCPU setup 직후 `$stop`
2. UCLI에서 TB task 호출

```tcl
# 도움말
call tb_full_campaign.console_help()

# SCPU1 (cid=1) 상태 / 1 step
call tb_full_campaign.console_cmd(4'd1, "status", 0, 0, 0)
call tb_full_campaign.console_cmd(4'd1, "step", 0, 0, 0)

# custom 명령 (펌웨어와 동일 효과)
call tb_full_campaign.console_cmd(4'd1, "vsync", 32'd10, 0, 0)
call tb_full_campaign.console_cmd(4'd1, "vhw_force", 32'h10, 32'h40000000, 32'h5000)
call tb_full_campaign.console_cmd(4'd1, "vhw_release", 32'h10, 32'h40000000, 0)

# barrier / HW force 테이블 (플랫폼)
call tb_full_campaign.console_sync_cmd("sync_configure", 32'd10, 32'd7, 0)
call tb_full_campaign.console_sync_cmd("hw_force_set", 32'h10, 32'h40000000, 32'h5000)
call tb_full_campaign.console_sync_cmd("hw_force_status", 0, 0, 0)

run    # 캠페인 계속
```

`cid=0`이면 모든 active VCPU에 동일 명령을 브로드캐스트합니다. 스크립트 예: `scripts/vcs/console_probe.tcl`.

콘솔 명령 전체 목록은 시뮬 정지 후 `console_help` 출력을 따릅니다 (`stall`, `resume`, `bus_write`, `wdt_pet`, …).

---

### 11. 새 명령 추가 시 체크리스트

1. `verif_cpu_defs.vh` — `VSEL_*` 상수
2. `include/verif_cpu_custom.vh` — `exec_custom` case
3. `verif_insns.h` — C 매크로
4. (선택) `cpu_console_dispatch` — EDA 콘솔 문자열
5. `gen_tb_campaign.py` — 캠페인 시나리오·체크에 반영
6. `make full_campaign` — regression

## SCPU 개수 — 파라미터 하나로 조정

**슬롯 개수**는 숫자 파라미터 **`CAMPAIGN_NUM_SCPU`** 하나로 정합니다 (SCPU1..N, SCPU0 master 제외).

### 방법 1 — Verilog 파라미터 파일 (권장)

`include/campaign_params.vh` 한 줄만 수정:

```verilog
`define CAMPAIGN_NUM_SCPU 60   // 원하는 숫자 (1..256)
```

### 방법 2 — example.sh / make (파일 수정 없이)

```bash
./example.sh gen 64          # SCPU1..64 슬롯으로 생성
./example.sh all 64        # 생성 + 시뮬
make -C firmware/campaign config NUM_SCPU=40
```

`make config`가 manifest·pool·generate loop·`campaign_scale.vh`를 전부 이 숫자에 맞게 재생성합니다.

**어떤 슬롯이 실제 campaign을 도는지**는 `firmware/campaign/campaign_slots.yaml`의 `active:` 목록으로 정합니다.  
`CAMPAIGN_NUM_SCPU`보다 큰 `cpu_id`는 에러, 목록에 없는 1..N 슬롯은 **reserved(idle)** — campaign TB에서는 phase 미실행, manifest/connect VH에는 bus 포트 기록 가능.

## 외부 SoC — AMBA bus 레이아웃 (SCPU1부터 순서대로)

플래그 **작성 순서 = cpu_id 오름차순 배치** (낮은 id가 앞쪽 버스 타입).

```bash
# 64슬롯: SCPU1–62 AXI4-Lite, 63 AHB-Lite, 64 APB3
./example.sh gen --axi 62 --ahb 1 --apb 1

# 순서 바꾸면 배치도 바뀜 (SCPU1=APB3, …)
./example.sh gen --apb 1 --axi 62 --ahb 1
```

### `--apb` / `--ahb` / `--axi` 기본값 (shorthand)

| CLI | canonical | 용도 |
|-----|-----------|------|
| `--apb` | **apb3** | SFR/UART 등 주변 레지스터 |
| `--ahb` | **ahb_lite** | AHB-Lite slave |
| `--axi` | **axi4lite** | AXI4-Lite 레지스터 포트 |

세대·프로파일이 다르면 명시: `--apb4`, `--ahb5`, `--axi4`, `--axi5`, `--axi3` 등.  
전체 목록: `firmware/campaign/amba_bus_registry.py` (SSOT).

생성물: manifest `bus_type`/`bus_port`, `include/verif_soc_bus_connect.vh`, `include/campaign_params.vh`, `include/campaign_scale.vh`.

`BUS_LAYOUT`를 한 번 적용하면 `firmware/campaign/.bus_layout_stamp`에 저장되어, 이후 `make icodes` 등이 `config`를 다시 돌려도 **reserved 슬롯의 bus 배치가 유지**됩니다. 초기화: `make clean-artifacts`.

```bash
# 60슬롯: SCPU1–58 AXI4-Lite, 59 AHB-Lite, 60 APB3 (active 3은 yaml bus 유지)
./example.sh gen --axi 58 --ahb 1 --apb 1

make -C firmware/campaign bus_connect    # manifest 기준 connect VH (active + reserved)
make -C firmware/campaign bus_connect_yaml   # soc_hierarchy_example.yaml (chip top 전용)
make soc-bus-all                         # 11종 bridge smoke + VCD
make soc-bus-vcd                         # bridge VCD 파형 자동 검증
python3 tools/verify_amba_bus_vcd.py sim_build/tb_soc_bus_all.vcd
```

**connect VH 용도 분리** — 같은 `verif_soc_bus_connect.vh` 파일이지만 **재생성 소스가 다릅니다.**

| 타깃 | 재생성 명령 | 슬롯 예 |
|------|-------------|---------|
| `make soc-manifest` | `bus_connect` (manifest) | active 3 (SFR/SRAM/UART) |
| `make soc-manifest-scale` | `config-scale` 내 `bus_connect` | BUS_LAYOUT 60 |
| `make chip-top-example` | `bus_connect_yaml` | yaml 4 (SFR/SRAM/UART/DMA) |

섞지 않으면 manifest vs chip-top 충돌을 줄일 수 있습니다.

**Agent/LLM 통합 가이드:** [vcpu_skill.md](vcpu_skill.md) — manifest 계약, bridge 배선, **펌웨어/icode 작성 조건**(phase 오프셋, `soc_regs.h`, `targets[]`), chip_top generate 패턴.

## 생성 파이프라인 (수동 단계)

`example.sh gen` 과 동일한 순서입니다.

```bash
cd firmware/campaign

make config        # CAMPAIGN_NUM_SCPU → manifest, cpus.mk, campaign_scale.vh
make soc_init      # → ../../include/soc_init_seq.vh, campaign_soc_platform.vh
make manifest      # campaign_manifest.vh (+ Python campaign_manifest.py)
make icodes        # icode_pool.bin, icode_map.vh, tb_full_campaign_gen.vh
make all           # SFR/SRAM/UART .bin + merge → unified.hex
```

### 생성물 매핑

| 입력 | 스크립트 | Verilog 산출 |
|------|----------|--------------|
| `include/soc_init_seq.h` | `gen_soc_init.py` | `include/soc_init_seq.vh`, `campaign_soc_platform.vh` |
| `include/campaign_manifest.h` | `gen_campaign_manifest.py` | `include/campaign_manifest.vh` |
| `icodes/**/*.c` | `build_icode_pool.py` | `include/icode_map.vh`, `icode_bind.vh`, `tb_full_campaign_gen.vh`, `tb_soc_manifest_*.vh`, `tb_soc_manifest_scale_*.vh` |
| `soc_hierarchy_example.yaml` | `gen_soc_bus_connect.py`, `gen_soc_cell_rtl.py` | `verif_soc_bus_connect.vh`, `rtl/verif_vcpu_soc_cell.v` |
| `cpus.mk` + `.bin` | `merge_campaign.py` | `firmware/full_campaign_unified.hex` |

`tb_full_campaign_gen.vh` 는 **자동 생성**입니다. Phase 매크로·`exec_icode_on_cpu`·체크리스트 문자열을 바꾸려면 `gen_tb_campaign.py` 또는 manifest/cpus.mk를 수정하세요.

## 시뮬레이션 타깃

```bash
make full_campaign   # ★ 공식 캠페인 (fw 빌드 + TB + VCD gate)
make verify          # full_campaign 별칭
make all             # verify 와 동일

make fw              # 펌웨어만 재빌드 (iverilog 생략)
make basic           # 코어 smoke
make rv32i           # RV32I 데모 TB
make harness         # verification harness TB
make soc             # simple_soc DUT TB
make soc-bus         # APB3 + AHB-Lite bridge smoke
make soc-bus-all     # APB/AHB/AXI bridge smoke (11 checks) + VCD
make soc-bus-vcd     # 위 + verify_amba_bus_vcd.py
make soc-manifest       # CONNECT_SLV* integration TB — active 3셀 (23 checks)
make soc-manifest-scale # flat N셀 BUS_LAYOUT compile + active 3 campaign (26 checks)
make chip-top-example   # chip_top: orchestrator + agent + bus R/W (16 checks)
make clean           # sim_build/ 삭제
make clean-artifacts # gen/sim 산출 전부 (fw build/hex/hdr, generated .vh, filelists, scripts)
```

### 검증 게이트 요약

| 타깃 | 체크 | 비고 |
|------|------|------|
| `make full_campaign` | 43/43 + VCD | 공식 regression |
| `make soc-bus-all` | 11/11 + VCD | APB2–5, AHB/AHB5/full, AXI-Lite/3/4/5 |
| `make soc-manifest` | 23/23 | real bridge, 3 active slaves |
| `make soc-manifest-scale` | 26/26 | 60 `g_slv*` + active 3 Phase A/B/C |
| `make chip-top-example` | 16/16 | yaml 4 hierarchy + DMA |

외부 SoC (AXI/AHB/APB) 통합: [howto_integrate2yourSoC.md](howto_integrate2yourSoC.md) (예제→내 SoC 절차), [howto_integrate.md](howto_integrate.md) §11–12 (신호 상세), [vcpu_skill.md](vcpu_skill.md)

### 60슬롯 scale integration

```bash
# layout 적용 + connect/cell 재생성 (기본: axi4lite:58, ahb_lite:1, apb3:1)
make config-scale

# 또는 example.sh (동일 stamp 저장)
./example.sh gen --axi 58 --ahb 1 --apb 1

# 60셀 flat fabric 컴파일 + active 3 campaign
make soc-manifest-scale
```

환경변수로 layout 변경:

```bash
make config-scale NUM_SCPU_SCALE=64 BUS_LAYOUT_SCALE="axi4lite:62,ahb_lite:1,apb3:1"
make soc-manifest-scale
```

### `full_campaign` 내부 동작

1. `make -C firmware/campaign all`
2. `iverilog` → `sim_build/tb_full_campaign.vvp`
3. `vvp` 실행 → `sim_build/tb_full_campaign.vcd`
4. per-CPU VCD → `logs/full_campaign/SCPU{1,2,3}.vcd`
5. `python3 tools/verify_vcd.py` 로 main + CPU VCD 검증

## VCD 확인

```bash
# 메인 캠페인 웨이브
gtkwave sim_build/tb_full_campaign.vcd

# per-CPU 계층 덤프
gtkwave logs/full_campaign/SCPU1.vcd
```

`verify_vcd.py` 가 확인하는 항목:

- `vcd_marker` 최종값 `0xDEADDEAD`
- `orch_reset_count >= 4` (phase + icode inter-reset)
- agent `verify_pass` 합계 = 6
- `0xDEADDEAD` 파형 샘플 존재 (X/Z/dummy/recovery)

수동 검증:

```bash
python3 tools/verify_vcd.py sim_build/tb_full_campaign.vcd \
  logs/full_campaign/SCPU1.vcd
```

## 체크리스트 (43항목)

`tb_full_campaign_gen.vh`의 `CAMPAIGN_EXECUTE`가 생성하는 `check_eq` 기준 (주요 묶음):

| 묶음 | 검증 내용 |
|------|-----------|
| Pool / Phase A | icode embed, SoC 17-step init, agent snoop, vwdt/vtrace |
| Phase B | master `init_done`, multi-slot collect |
| Sync parallel | 3-CPU `vsync` barrier @ `0x380`, parallel bus |
| Console | stall / bus_write / resume |
| Phase C SFR | RV32 ISA, `vforce`, `vhw_force`, `vwave`, DEADDEAD/X/Z |
| Phase C SRAM | JAL/JALR, solo `vsync` |
| Icode platform | RV32 exec, map bus ×6, inter-reset, PASS=6 |
| UART WDT | hang → recovery → DEADDEAD, solo `vsync` |
| VCD | main + per-CPU export |

시뮬 로그에서 `Checklist: 43 passed / 0 failed` 를 확인합니다. 세부 문자열은 `include/tb_full_campaign_gen.vh` (자동 생성)을 참고하세요.

## 설정 변경 시 주의

| 변경 위치 | 후속 작업 |
|-----------|-----------|
| `firmware/campaign/include/soc_platform.h` | `make soc_init` |
| `campaign_manifest.h` / `cpus.mk` | `make manifest` + `make icodes` + `make all` |
| `NUM_SCPU` / `BUS_LAYOUT` | `make config-scale` 또는 `./example.sh gen --axi N …` → `make bus_connect` |
| icode C 소스 | `make icodes` (자동으로 `gen_tb` 재실행) |
| RTL/TB 수동 편집 | `make clean && make full_campaign` |
| layout 초기화 (3셀만 wired) | `make clean-artifacts` 후 `make -C firmware/campaign config` |

## 문제 해결

| 증상 | 조치 |
|------|------|
| `missing *.bin` | `make -C firmware/campaign all` |
| `gen_tb` / `icode_map` 없음 | `make icodes` |
| iverilog 없음 | `apt install iverilog` |
| RISC-V gcc 없음 | `CROSS_COMPILE` 환경변수 또는 툴체인 설치 |
| VCD gate FAIL | 시뮬 로그의 `[FAIL]` 항목 확인 후 GTKWave로 해당 신호 추적 |

## 관련 문서

- [vcpu_skill.md](vcpu_skill.md) — **Agentic LLM용** 과제 SoC 통합 스킬 (manifest, bus, top wiring)
- [howto_integrate2yourSoC.md](howto_integrate2yourSoC.md) — 기본 예제 PASS 후 **내 SoC** 이식 절차
- [howto_integrate.md](howto_integrate.md) — AXI/AMBA 신호·매크로 상세
- [architecture_example.md](architecture_example.md) — SoC/VCPU/Agent 블록 다이어그램
- `firmware/campaign/amba_bus_registry.py` — bus 타입·CLI·RTL·connect 매크로 SSOT (`rtl_status`: `done` / `smoke` / `manifest_only`)
- `tools/probe_icodes.py` — icode bus 주소 probe (`requirements.txt` → `tinyrv`)