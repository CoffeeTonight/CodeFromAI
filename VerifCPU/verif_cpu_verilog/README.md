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

성공 시 체크리스트 **25/25 PASS**, `vcd_marker = 0xDEADDEAD`.

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
├── tools/                # verify_vcd.py, probe_icodes.py
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
| `make full_campaign` | 25/25 + VCD | 공식 regression |
| `make soc-bus-all` | 11/11 + VCD | APB2–5, AHB/AHB5/full, AXI-Lite/3/4/5 |
| `make soc-manifest` | 23/23 | real bridge, 3 active slaves |
| `make soc-manifest-scale` | 26/26 | 60 `g_slv*` + active 3 Phase A/B/C |
| `make chip-top-example` | 16/16 | yaml 4 hierarchy + DMA |

외부 SoC (AXI/AHB/APB) 통합: [howto_integrate.md](howto_integrate.md) §11–12, [vcpu_skill.md](vcpu_skill.md)

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

## 체크리스트 (25항목)

`tb_full_campaign.v` + `tb_full_campaign_gen.vh` 기준:

1. Icode pool embedded (readmemh)
2. Phase A SoC init (17-step)
3. Master SoC init_done poll
4. Phase B multi-slots (2 per agent)
5. Console stall/resume
6. SFR assertions pass / bus activity
7. SRAM assertions pass
8. Icode RV32 exec (SFR/SRAM/UART slot0)
9. Icode map bus ×6
10. Icode inter-reset / multi-icode rounds / PASS=6
11. UART WDT hang + recovery + DEADDEAD path
12. VCD export

시뮬 로그에서 `[PASS]` / `Checklist: 25 passed` 를 확인합니다.

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
- [howto_integrate.md](howto_integrate.md) — AXI/AMBA 상세 절차
- [architecture_example.md](architecture_example.md) — SoC/VCPU/Agent 블록 다이어그램
- `firmware/campaign/amba_bus_registry.py` — bus 타입·CLI·RTL·connect 매크로 SSOT (`rtl_status`: `done` / `smoke` / `manifest_only`)
- `tools/probe_icodes.py` — icode bus 주소 probe (`requirements.txt` → `tinyrv`)