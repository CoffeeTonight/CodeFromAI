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
| `python3` | 생성 스크립트, `verify_vcd.py` |
| `riscv64-unknown-elf-gcc` 등 | VCPU/icode C 펌웨어 빌드 (`firmware/campaign`) |

```bash
# Debian/Ubuntu 예시
sudo apt install iverilog python3
# RISC-V 툴체인은 보드/환경에 맞게 설치
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
| **SCPU1–3 `verif_cpu_core`** | VCPU — Phase A/B/C RV32 펌웨어 (`cpus.mk`) |
| **3× `verif_agent_slave`** | SoC tap snoop, icode slot 검증 |
| **`verif_cpu_unified_pool`** | VCPU FW + icode pool (≤256 KiB → readmemh embed) |
| **`simple_soc`** | 17-step `soc_init_seq`, SFR/SRAM/UART peripheral |

블록 다이어그램·최근 검증 스냅샷: [architecture_example.md](architecture_example.md)

## 생성 파이프라인 (수동 단계)

`example.sh gen` 과 동일한 순서입니다.

```bash
cd firmware/campaign

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
| `icodes/**/*.c` | `build_icode_pool.py` | `include/icode_map.vh`, `icode_bind.vh`, `tb_full_campaign_gen.vh` |
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
make clean           # sim_build/ 삭제
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
| icode C 소스 | `make icodes` (자동으로 `gen_tb` 재실행) |
| RTL/TB 수동 편집 | `make clean && make full_campaign` |

## 문제 해결

| 증상 | 조치 |
|------|------|
| `missing *.bin` | `make -C firmware/campaign all` |
| `gen_tb` / `icode_map` 없음 | `make icodes` |
| iverilog 없음 | `apt install iverilog` |
| RISC-V gcc 없음 | `CROSS_COMPILE` 환경변수 또는 툴체인 설치 |
| VCD gate FAIL | 시뮬 로그의 `[FAIL]` 항목 확인 후 GTKWave로 해당 신호 추적 |

## 관련 문서

- [architecture_example.md](architecture_example.md) — SoC/VCPU/Agent 블록 다이어그램
- `firmware/campaign/` — 펌웨어·icode 소스 및 빌드
- `tools/probe_icodes.py` — icode bus 주소 probe (tinyrv; python_model 선택)