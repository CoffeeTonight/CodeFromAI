## 검증 결과

`make full_campaign` (iverilog + VCD) **PASS**

| 항목 | 결과 |
|---|---|
| Checklist | **43 passed / 0 failed** |
| Agents icode | PASS=6, FAIL=0 |
| `vcd_marker` | `0xDEADDEAD` |
| Master init_done poll | `@0x40000018` poll 0 — PASS |
| VCD | `sim_build/tb_full_campaign.vcd` (115,419 B) |

---

## Block Diagram — SoC · VCPU · Agent 설계 관계

### 1) 최상위 (tb_full_campaign)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        tb_full_campaign  (Testbench)                        │
│                                                                             │
│  ┌──────────────────┐     phase / reset_pulse / boot_fw_offset             │
│  │ verif_orchestrator│──────────────────────────────┐                       │
│  │     u_orch        │                              │                       │
│  └──────────────────┘                              ▼                       │
│                                              ┌───────────────┐               │
│  ┌──────────────────┐  init_done poll       │ Slave Agents  │               │
│  │ verif_agent_master│  (param: ADDR/MASK)  │  x3 (g_ag)   │               │
│  │  SCPU0  (MSTR)    │──────────────────────│ behavior only │               │
│  │  FW 없음          │  Phase B: bus hint   │ SCPU1/2/3     │               │
│  └────────┬─────────┘                       └───────┬───────┘               │
│           │                                         │ snoop tap[0..2]       │
│           │ TB: decode_read (manifest)              │                       │
│           ▼                                         ▼                       │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │                    simple_soc  (DUT SoC model)               │           │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐                  │           │
│  │  │ u_sfr   │    │ u_sram  │    │ u_uart  │  ← SoC peripherals│           │
│  │  │0x4000_  │    │0x8000_  │    │0xC000_  │    (not VCPUs)    │           │
│  │  │ 0000    │    │ 0000    │    │ 0000    │                  │           │
│  │  └───┬─────┘    └───┬─────┘    └───┬─────┘                  │           │
│  │      │tap0          │tap1          │tap2                     │           │
│  │      └──────── decode_read/write ──┴──────────────────────────│           │
│  │                    run_init() ← soc_init_seq.h (17 steps)    │           │
│  │                    SFR_STATUS[31]=INIT_DONE @ 0x4000_0018     │           │
│  └──────────────────────────▲────────────────────────────────────┘           │
│                             │ bus master (RV32 load/store)                   │
│  ┌──────────────────────────┴────────────────────────────────────┐           │
│  │              verif_soc_bus  (adapter)                          │           │
│  └──────────────────────────▲────────────────────────────────────┘           │
│                             │ USE_SOC_BUS=1                                  │
│  ┌──────────────────────────┴────────────────────────────────────┐           │
│  │           VCPUs  x3  (verif_cpu_core, g_cpu)  ← 실제 RV32 코어  │           │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                      │           │
│  │  │ SCPU1    │  │ SCPU2    │  │ SCPU3    │                      │           │
│  │  │ SFR FW   │  │ SRAM FW  │  │ UART FW  │                      │           │
│  │  │ cpus.mk  │  │ cpus.mk  │  │ cpus.mk  │                      │           │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘                      │           │
│  └───────┼─────────────┼─────────────┼────────────────────────────┘           │
│          │             │             │ pool_read_word (fetch)                 │
│          └─────────────┴─────────────┴──────────────┐                          │
│                                                     ▼                          │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │           verif_cpu_unified_pool  (u_pool)                    │           │
│  │  ┌──────────── VCPU FW regions (8KiB each) ────────────────┐  │           │
│  │  │ word 0x0000: CPU1/SFR  │ 0x4000: CPU2/SRAM │ 0x8000: UART│  │           │
│  │  └─────────────────────────────────────────────────────────┘  │           │
│  │  ┌──────────── icode pool (50 slots x 4KiB) ──────────────┐  │           │
│  │  │ word 0xC000: icode_pool.bin (probe + manifest icodes)   │  │           │
│  │  │ ≤256KiB → readmemh embed  │  >256KiB → lazy file+4KiB pg │  │           │
│  │  └─────────────────────────────────────────────────────────┘  │           │
│  └─────────────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 2) 역할 구분 — “같은 ID, 다른 모듈”

```
  ID    모듈                    역할                         FW
 ─────  ──────────────────────  ───────────────────────────  ──────────────
 SCPU0  verif_agent_master      Phase gate, init_done poll,  없음
                                 manifest hint 주입

 SCPU1  verif_cpu_core (VCPU)   RV32 실행, SoC bus master    SFR.bin
        verif_agent_slave       tap0 snoop, icode 검증        없음

 SCPU2  verif_cpu_core (VCPU)   RV32 실행                    SRAM.bin
        verif_agent_slave       tap1 snoop                     없음

 SCPU3  verif_cpu_core (VCPU)   RV32 실행, WDT recovery      UART.bin
        verif_agent_slave       tap2 snoop                     없음
```

VCPU와 Agent는 **cpu_id로 짝**이지만 **별도 RTL 인스턴스**입니다. VCPU는 SoC에 bus transaction을 날리고, Agent는 그 transaction을 tap에서 **관찰·검증**합니다.

---

### 3) SoC 내부 (simple_soc)

```
                    decode_read / decode_write
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   addr 0x4000_0000      0x8000_0000          0xC000_0000
        │                     │                     │
   ┌────▼────┐          ┌────▼────┐          ┌────▼────┐
   │  SFR    │          │  SRAM   │          │  UART   │
   │ 4KiB    │          │ 64KiB   │          │ 4KiB    │
   │ SFR_CTRL│          │ MARKER  │          │ BAUD    │
   │ STATUS  │◄─ init_done (bit31)
   └────┬────┘          └────┬────┘          └────┬────┘
        │ pulse_snoop        │                    │
        └──────── tap[0] ────┴──── tap[1] ────────┴── tap[2]
                              │
                    verif_agent_slave (각 tap 1:1)
```

SoC 안에는 **애플리케이션 CPU 코어가 없습니다**. SFR/SRAM/UART는 **검증 대상 peripheral slave**이고, VCPU는 SoC **바깥**에서 붙는 bus master입니다.

---

### 4) Unified Pool 메모리 맵

```
  byte offset (pool word << 2)
  ┌──────────────────────────────────────────────────────────┐
  0x00000   CPU1 VCPU FW  (SFR)     8 KiB   OFF_A/B/C ...
  0x10000   CPU2 VCPU FW  (SRAM)    8 KiB
  0x20000   CPU3 VCPU FW  (UART)    8 KiB
  ...
  0x30000   (VCPU image end ~ 0x22000)
  0x30000 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
  0xC0000   icode pool base (word 0xC000)
            ├ slot+0x1000: check_sfr_ctrl
            ├ slot+0x2000: check_sfr_mask
            ├ ...
            └ 50 icodes × 4KiB spacing
```

---

### 5) Phase 흐름 (시점 관계)

```
Phase A (INIT)
  orch.phase_release(INIT)
  u_soc.run_init()          ← TB가 SoC 레지스터 직접 init (17-step)
  agent.run_phase_a()       ← tap에서 init bus txn snoop
  VCPU run OFF_A            ← 각 CPU phase_a.c (vstop)

Phase B (COLLECT)  ─── Master gate ───
  Master poll INIT_DONE @ soc_platform.h ADDR (parameter)
  orch.phase_release(COLLECT)
  Master inject bus_read hints (manifest)
  agent.run_phase_b()       ← hint 주소 slot 수집
  VCPU run OFF_B

Phase C (VERIFY)
  VCPU run OFF_C            ← full ISA / JAL/JALR
  exec_icode_on_cpu()       ← pool에서 icode RV32 실행
  agent.run_phase_c()       ← slot별 expect 비교
  icode inter-reset (orch)
```

---

### 6) 설정 파일 → RTL 연결

```
cpus.mk              → VCPU 개수/ID/pool_word → gen_tb_campaign.vh
campaign_manifest.h  → Agent tap/slot/icode   → campaign_manifest.vh
soc_platform.h       → Master INIT_DONE param  → campaign_soc_platform.vh
icodes/**/*.c        → icode pool               → icode_map.json + pool.bin
cpu_*/ + Makefile    → SFR/SRAM/UART.bin        → merge → unified.hex
```

---

**한 줄 요약:** `simple_soc`는 **검증 대상 peripheral SoC**이고, **VCPU 3개**는 그 SoC에 붙는 **RV32 bus master**이며, **Master/Slave Agent**는 FW 없는 **검증 오케스트레이션 레이어**입니다. FW·icode는 **unified pool** 한곳에 모이고, Master는 **parameterized init_done 주소**로 SoC ready를 확인한 뒤 Phase B로 넘어갑니다.