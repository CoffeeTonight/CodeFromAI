# slave_rw — simulation SoC slave read/write verification

> **User-authored 검증 명세** (`slave_rw` 그룹).  
> MD = **무엇을** 검증할지. `ops/simulation/slave_rw.py` = **compile + 3-tier sim** crystallize.

## 게이트 원칙

**목적**: VerifCPU SoC reference에서 **slave peripheral R/W**가 버스·펌웨어·sync 경로별로 정상 동작하는지 iverilog로 확인한다.

| 항목 | 원칙 |
|------|------|
| RTL SSOT | `~/tools/CodeFromAI/VerifCPU/verif_cpu_verilog` (또는 tag workspace `VerifCPU/verif_cpu_verilog`) |
| 선행 | `depends_on: [sanity]` — c-compile `./example.sh gen` + `tb_full_campaign.vvp` |
| tier | **single** → **burst** → **cpu_sync** (순서 고정, 각각 compile/sim log 마커) |
| 판정 | **log 스캔** (exit code만 PASS 금지). EDA/C error 표식 + checklist 실패 0 + tier 성공 마커 |
| fw 정책 | cpu_sync만 c-compile 펌웨어 사용; sim 중 C 재빌드 금지 |

### VerifCPU README 핵심 (반드시 참고)

| 문서 | 용도 |
|------|------|
| `README.md` | custom insn (`vsync`, `vhw_force`), sync barrier, Makefile 타깃, 43-check 캠페인 |
| `howto_integrate.md` | chip_top / manifest integration, bridge 배선 |
| `vcpu_skill.md` | manifest 계약, `soc_regs.h`, BUS_LAYOUT, chip-top 16-check |
| `firmware/campaign/include/verif_insns.h` | 펌웨어 매크로 SSOT |
| `firmware/campaign/include/soc_regs.h` | slave 주소 (`SFR_CTRL`, `SRAM_MARKER`, `UART_BAUD`, …) |

---

## Slave 맵 (chip-top yaml 4-cell)

| Slave | 버스 | BASE | TB single 패턴 | Agent slot |
|-------|------|------|----------------|------------|
| SFR | APB3 | `0x4000_0000` | `0x0000_CAFE` | `g_slv0` / `u_ag_1` |
| SRAM | AHB-Lite | `0x8000_0000` | `0x1234_5678` | `g_slv1` / `u_ag_2` |
| UART | AXI4 | `0xC000_0000` | `0x0000_00A5` | `g_slv2` / `u_ag_3` |
| DMA | AXI4 | `0x4A00_0000` | `0xDEAD_BEEF` | `g_slv36` / `u_ag_37` |

decode: `include/chip_top_decode.vh` (gen) — `chip_decode_write` / `chip_decode_read` → real bridge.

---

## 3-tier R/W 시나리오

### Tier 1 — `sim_single` (firmware single-beat R/W on 3 slaves)

**타깃 (crystallize)**: `make soc` → `vvp sim_build/tb_soc_dut.vvp`

`simple_soc` + 17-step init + VCPU 펌웨어가 SFR/SRAM/UART에 **single `rv_sw` / `rv_lw`** 수행.

```c
// firmware/campaign/common/phase_a.c — Phase A single write (all active CPUs)
load_soc_addr(10, SFR_CTRL);
rv_addi(11, 0, 1);
rv_sw(11, 10, 0);
```

Phase C에서 slave별 icode read 검증 (`tb_soc_dut.v`):

| Slave | 주소 | 기대값 |
|-------|------|--------|
| SFR | `SFR_CTRL` | manifest target |
| SRAM | `SRAM_MARKER` | `0xDEADBEEF` |
| UART | `UART_BAUD` | `0x00000080` |

**성공 마커**: `[SUCCESS] SoC verification campaign completed`, `TOTAL: PASS=3 FAIL=0`

#### Optional — chip-top TB-direct 4-slave (DMA 포함)

README `make chip-top-example` (**16 checks**) — `chip_bus_wr_rd` on SFR/SRAM/UART/DMA.

**전제**: `CAMPAIGN_NUM_SCPU ≥ 37` (`soc_hierarchy_example.yaml` DMA `cpu_id: 37`) + chip_top TB에 `u_sync` 바인딩.  
현재 `CAMPAIGN_MAX_SLOTS=3` 기본 gen에서는 compile 실패할 수 있음 → 확장 시:

```bash
make -C firmware/campaign config NUM_SCPU=40
make -C firmware/campaign bus_connect_yaml icodes
make chip-top-example
```

### Tier 2 — `sim_burst` (AMBA bridge burst-capable smoke)

**타깃**: `make soc-bus-all` — **11 checks** + VCD gate

- APB2/3/4/5, AHB-Lite, AHB5-Lite, AHB full, AXI4-Lite, **AXI3/4/5 full** (burst-capable master)
- 현재 TB는 **single-beat `bus_read`** smoke이나, full AXI/AHB master 경로로 **burst 트랜잭션 준비** 검증
- VCD: `python3 tools/verify_amba_bus_vcd.py sim_build/tb_soc_bus_all.vcd`

향후 multi-beat burst R/W 확장 시 `tb_soc_bus_all.v` 또는 전용 icode/TB 추가.

### Tier 3 — `sim_cpu_sync` (멀티-CPU vsync + parallel bus R/W)

**타깃**: `vvp sim_build/tb_full_campaign.vvp` (sim-only, c-compile fw)

**흐름** (`README.md` §8, `tb_full_campaign_gen.vh`):

1. TB `u_sync.sync_configure(8'd10, 64'd7)` — SCPU1+2+3 참여
2. `start_cpus_parallel(0x380)` — 3 CPU 동시 PC (`OFF_SYNC_BARRIER`)
3. 각 CPU `sync_barrier.c`:

```c
// firmware/campaign/cpu_sfr/sync_barrier.c (SRAM/UART 동일 패턴)
vsync(CAMPAIGN_SYNC_BARRIER_ID);  // id=10
load_soc_addr(10, SFR_CTRL);
rv_lw(11, 10, 0);                 // barrier 해제 후 bus read
vassert_id(50);
```

| CPU | slave | sync 후 bus | check (gen VH) |
|-----|-------|-------------|----------------|
| SCPU1 (SFR) | APB SFR | `rv_lw` @ `SFR_CTRL` | `Sync parallel bus SFR`, `SFR vsync hits` |
| SCPU2 (SRAM) | AHB SRAM | `rv_lw` @ `SRAM_MARKER` | `Sync parallel bus SRAM`, `SRAM vsync hits` |
| SCPU3 (UART) | AXI UART | `rv_lw` @ `UART_BAUD` | `Sync parallel bus UART`, `UART vsync solo` |

전체 캠페인: **43/43** + VCD (`make full_campaign`). slave_rw gate는 **sync parallel bus** 마커 + checklist 43/0에 집중.

---

## Compile 경로 (crystallize)

**환경**:

```bash
export RTL_ROOT="$PWD"   # discovered clone + rtl_subdir
cd "$RTL_ROOT"
```

### 선행 — sanity c-compile (필수)

```bash
./example.sh gen
make sim_build/tb_full_campaign.vvp
```

산출: `firmware/*.hex`, `include/tb_full_campaign_gen.vh`, `include/chip_top_decode.vh` (via icodes), …

### slave_rw compile (ops가 추가 실행)

```bash
# Tier 1 compile (simple_soc)
make sim_build/tb_soc_dut.vvp

# Tier 2 compile (burst bridge)
make sim_build/tb_soc_bus_all.vvp
```

> `make soc` / `make soc-bus-all` 은 내부 `fw` 재빌드를 호출할 수 있음.  
> **원칙 준수**: ops는 **vvp compile target만** invoke하고 sim은 `vvp` 직접 실행.  
> cpu_sync는 c-compile 산출 `tb_full_campaign.vvp` 재사용.

### slave_rw sim (ops 3-tier)

```bash
# Tier 1 — single R/W (SFR/SRAM/UART firmware)
vvp sim_build/tb_soc_dut.vvp

# Tier 2 — burst bridge
vvp sim_build/tb_soc_bus_all.vvp
python3 tools/verify_amba_bus_vcd.py sim_build/tb_soc_bus_all.vcd

# Tier 3 — cpu sync (c-compile fw, 재빌드 없음)
vvp sim_build/tb_full_campaign.vvp
```

---

## PASS / FAIL (공통)

- `verdict_slave_rw.json`: `status == PASS`
- `runs/{run_id}/slave_rw.log` — Python/traceback/EDA error 없음
- tier별 checklist **failed = 0** + 아래 마커:

| tier | 필수 log 마커 |
|------|----------------|
| sim_single | `[SUCCESS] SoC verification campaign completed`, `TOTAL: PASS=3 FAIL=0` |
| sim_burst | `[SUCCESS] All AMBA bridge variants OK`, `Checklist: 11 passed / 0 failed` |
| sim_cpu_sync | `Sync parallel bus SFR`, `Sync parallel bus SRAM`, `Sync parallel bus UART`, `Checklist: 43 passed / 0 failed` |

cpu_sync tier 추가 금지 표식 (있으면 FAIL):

- `make -C firmware/campaign all`
- `Compiling icodes`

---

## FAIL 시 (방향)

- `RESPOND.md` — tier별 디버그
- README §문제 해결 — `missing *.bin` → c-compile
- EDA interactive: `+console_pause`, `console_sync_cmd("sync_configure", …)` (VCS/Xcelium)

---

## 시나리오 카탈로그

전체 tier·주소·펌웨어 참조: [`slave_rw_scenarios.json`](./slave_rw_scenarios.json)

gate 실행 시 ops는 위 JSON을 참고하되, **판정은 log 마커**로 수행한다.

---

## soc-verify-agent 실행

```bash
cd /home/user/Desktop/soc-verify-agent
python3 projects/VERIF-CPU-SOC/ops/simulation/slave_rw.py \
  --project projects/VERIF-CPU-SOC \
  --run-dir projects/VERIF-CPU-SOC/runs/slave-rw-test
```

선행: sanity `c-compile` PASS (`runs/*/verdict_c-compile.json`).