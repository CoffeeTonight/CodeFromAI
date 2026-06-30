# VerifCPU Verilog — 외부 SoC AXI 통합 How-To

이 문서는 **검증용 `simple_soc`가 아닌, 실제 과제 SoC AXI bus**에 VerifCPU를 붙이는 절차를 설명합니다.

대상 독자: SoC 주소맵·interconnect를 알고 있고, master 1 + slave CPU N(예: 100)을 검증 블록으로 올리려는 RTL/검증 엔지니어.

---

## 0. 전제 — 지금 모델과 실칩의 차이

| 항목 | Campaign TB (`simple_soc`) | 실제 과제 SoC |
|------|---------------------------|---------------|
| SoC | `simple_soc.decode_read/write` task | 과제 `axi_interconnect` + slave IP |
| CPU bus | `verif_soc_bus` → task 호출 | `verif_axi_lite_master` **핀** → `Sxx_AXI_*` |
| Agent snoop | `u_soc.stxn_valid[TAP]` | bus monitor → `tap_valid[tap_id]` |
| 연결 | TB 내부 고정 | **과제 top + manifest + 생성 VH** |

Campaign TB는 위 구조의 **동작 검증용 축약 모델**입니다. 실칩 통합은 아래 절차를 따릅니다.

---

## 1. 용어 정리

| 이름 | 의미 | 예 |
|------|------|-----|
| **cpu_id** | SCPU 번호. orchestrator reset, pool, 로그에 사용 | slave: `1..100`, master: `0` |
| **tap_id** | Agent가 snoop하는 **관찰 채널 번호**. AXI 포트 번호와 다를 수 있음 | `37` → `tap_valid[37]` |
| **axi_mst_port** | 이 CPU bridge가 붙는 **과제 interconnect slave 포트 이름** | `S37_AXI` |
| **bus_addr** | VCPU/icode가 access하는 **절대 주소** | `0x4A000000` |
| **hierarchy_id** | VCD/로그 scope용 **내부 레지스터**. 외부 wire 없음 | `cpu_set_hierarchy(37)` |

### cpu_id와 tap_id를 같게 해도 되나?

**Slave CPU끼리는 같게 맞춰도 됩니다** (권장: `cpu_id == tap_id`, `1..N`).

- **Master만 예외**: `cpu_id = 0`, tap 없음 (init_done poll, manifest hint만)
- Campaign 3-slave 예는 역사적으로 `tap_id = cpu_id - 1` (0-base tap) — 프로젝트 전체에서 **한 규칙만** 고정할 것

### AXI 포트 번호 ≠ tap_id (주의)

`S37_AXI`와 `tap_id=37`이 우연히 같을 수는 있지만, **같다고 가정하지 마세요.** manifest에 각각 적습니다.

---

## 2. SoC hierarchy에서 뽑아야 할 정보

과제 문서·주소맵·interconnect diagram을 보고 **slave 1개당** 아래를 확정한 뒤,  
**`firmware/campaign/campaign_slots.yaml` `active[]`에만** 기록합니다 (`campaign_slots_GUIDE.md`).

intake `slaves[]` / `soc_hierarchy_*.yaml` / `soc_integration_ports.yaml` 은 **편집하지 않습니다** (`make discover` 파생).

```
slave_name     : "DMA_CH3"
cpu_id         : 37
tap_id         : 37          (agent snoop 채널)
axi_mst_port   : "S37_AXI"   (interconnect에 붙는 포트 이름)
addr_base      : 0x4A000000
addr_size      : 0x00001000
pool_word      : 0x....       (unified pool 내 VCPU FW 위치)
targets[]      : { bus_addr, expect, icode_name }
```

검증 타깃(`targets`)은 Phase B hint / Phase C icode가 access할 레지스터입니다.  
지금 campaign의 `campaign_manifest.h`가 3-slave 버전의 single source of truth입니다.

---

## 3. 전체 절차 (흐름도)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. SoC AXI hierarchy 파악 (주소맵, S00..S99, slave 구간)         │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. campaign_slots.yaml 작성 (사람·LLM이 편집하는 유일한 입력)     │
│    active[] + chip + master → make discover                     │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. 펌웨어 + icode 빌드                                          │
│    make -C firmware/campaign icodes / SFR.. / merge             │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. probe — icode 첫 bus txn addr/op가 manifest와 일치하는지 확인  │
│    → icode_map.vh / icode_map.json                              │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. generate                                                     │
│    campaign_manifest.vh, tb_full_campaign_gen.vh                │
│    verif_soc_bus_connect.vh  ← 과제 포트명 + bus_type 배선      │
│    verif_vcpu_soc_cell.v, tb_soc_manifest_gen.vh (integration)  │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. 과제 top / verif top                                         │
│    generate N slave + include connect.vh + tap 배열 bus         │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. 시뮬 — Phase A init → init_done poll → Phase B/C → icode      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. 신호 종류 — CPU마다 뭘 연결해야 하나

| 신호 그룹 | slave 1개당 | top에서 손으로? | 방법 |
|-----------|------------|-----------------|------|
| **AMBA master** (APB/AHB/AXI) | bus_type당 1세트 | ✗ 자동 생성 | `verif_soc_bus_connect.vh` |
| **Agent snoop** 4개 | `valid, wr, addr, data` | △ 배열 인덱스 1줄 | `tap_valid[tap_id]` |
| **Orchestrator** | 공통 | ✗ broadcast | `orch_reset`, `phase`, `boot_fw` |
| **hierarchy_id** | 값만 다름 | ✗ 외부 wire 없음 | `initial cpu_set_hierarchy(id)` |
| **Unified pool** | region assign | setup task | `cpu_attach_pool_region` + `pool_assign_region` |

**Fetch 플래그 (이름 주의):** `USE_SHARED_POOL=0`이어도 campaign/chip TB는 `USE_SOC_BUS=1` 또는 셀 `USE_MANIFEST_SOC_BUS=1` + Makefile `VERIF_POOL_HUB=tb_*.u_pool`로 unified pool fetch를 씁니다. `USE_SHARED_POOL=1`은 `tb_verification_harness` 전용입니다.

**핵심:** AXI만 무겁고, 나머지는 배열·broadcast·initial로 처리합니다.  
CPU 100개여도 **사람이 매일 top wiring을 100번 쓰지 않도록** manifest + generate가 담당합니다.

---

## 5. 단계별 상세

### 5.1 manifest 작성

3-slave campaign 예 (`campaign_manifest.h`):

```c
static const manifest_slave_t MANIFEST_SLAVES[] = {
    { "SFR",  1, 0, POOL_WORD_SLOT0, 2 },
    { "SRAM", 2, 1, POOL_WORD_SLOT1, 2 },
    { "UART", 3, 2, POOL_WORD_SLOT2, 2 },
};
```

실칩 100-slave 확장 시 **컬럼 추가**:

```c
typedef struct {
    const char *name;
    uint8_t     cpu_id;
    uint8_t     tap_id;
    const char *axi_mst_port;   // "S37_AXI"
    uint32_t    addr_base;
    uint32_t    addr_size;
    uint32_t    pool_word;
    uint8_t     target_count;
} manifest_slave_t;
```

slave 37 한 줄 예:

```c
{ "DMA_CH3", 37, 37, "S37_AXI", 0x4A000000, 0x1000, POOL_WORD(37), 1 },
```

타깃:

```c
static const manifest_target_t MANIFEST_DMA_CH3_TARGETS[] = {
    { 0x4A000000, 0x00000001u, "check_dma_ctrl" },
};
```

편집 후:

```bash
cd firmware/campaign
make manifest    # → ../../include/campaign_manifest.vh
make soc_init    # → init_done 주소 등
```

### 5.2 icode + probe

```bash
make icodes      # icode_pool.bin, icode_map.vh, tb_full_campaign_gen.vh
```

`icode_map.json` 항목 예:

```json
{
  "name": "check_dma_ctrl",
  "pool_ptr": 4096,
  "bus_addr": 1241513984,
  "bus_op": "R",
  "tap_port": 37
}
```

`bus_addr` / `tap_port`가 manifest와 다르면 probe 단계에서 실패합니다.  
**SoC hierarchy 오타를 시뮬 전에 잡는 관문**입니다.

### 5.3 Bus connect VH 생성 (과제 포트명 + bus_type)

`gen_soc_bus_connect.py`가 manifest / `soc_hierarchy_example.yaml`의 `bus_port`·`bus_type`을 읽어 아래를 생성합니다.

파일: `verif_cpu_verilog/include/verif_soc_bus_connect.vh`

```verilog
// Auto-generated — do not edit

`define CONNECT_AXI_LITE(SOC, MST) \
  assign SOC``_arvalid = MST``_arvalid; \
  assign SOC``_arready = MST``_arready; \
  assign SOC``_araddr  = MST``_araddr;  \
  assign SOC``_arsize  = MST``_arsize;  \
  assign SOC``_rvalid  = MST``_rvalid;  \
  assign SOC``_rready  = MST``_rready;  \
  assign SOC``_rdata   = MST``_rdata;   \
  assign SOC``_rresp   = MST``_rresp;   \
  assign SOC``_awvalid = MST``_awvalid; \
  assign SOC``_awready = MST``_awready; \
  assign SOC``_awaddr  = MST``_awaddr;  \
  assign SOC``_awsize  = MST``_awsize;  \
  assign SOC``_wvalid  = MST``_wvalid;  \
  assign SOC``_wready  = MST``_wready;  \
  assign SOC``_wdata   = MST``_wdata;   \
  assign SOC``_wstrb   = MST``_wstrb;   \
  assign SOC``_bvalid  = MST``_bvalid;  \
  assign SOC``_bready  = MST``_bready; \
  assign SOC``_bresp   = MST``_bresp

// slave 37 — manifest: bus_port = "S37_AXI", bus_type = axi4lite
`define CONNECT_SLV37_AXI4LITE `CONNECT_AXI_LITE(S37_AXI, g_slv36.u_bus)
```

과제 top에서 (iverilog XMR 호환 — **flat** `g_slv{cpu_id-1}`):

```verilog
`include "verif_soc_bus_connect.vh"
generate
  begin : g_slv36
    verif_vcpu_soc_cell_axi4lite #(.CPU_ID(37)) u_bus ( ... );
  end
endgenerate
`CONNECT_SLV37_AXI4LITE
```

**Integration TB** (`make soc-manifest`): `tb/tb_soc_manifest.v`가 위 패턴을 3-slave로 재현합니다 (Phase A/B/C, **23 checks**).  
생성 RTL: `tb_soc_manifest_defs.vh`, `tb_soc_manifest_gen.vh`, `tb_soc_manifest_decode.vh` (주소 decode), `verif_manifest_soc_bus_*.vh`.

**Scale integration TB** (`make soc-manifest-scale`): `tb/tb_soc_manifest_scale.v` — manifest `BUS_LAYOUT`로 wired된 **N개 flat `g_slv*`** 컴파일 + active 3 campaign (**26 checks**).  
생성 RTL: `tb_soc_manifest_scale_defs.vh`, `tb_soc_manifest_scale_gen.vh`, `verif_manifest_scale_soc_bus_*.vh`.  
layout은 `make config-scale` 또는 `./example.sh gen --axi 58 --ahb 1 --apb 1` 후 `.bus_layout_stamp`로 유지됩니다.

**Chip top 예시** (`make chip-top-example`): `chip_top_example.v` + 생성 VH — yaml 3 active slave, orchestrator/agent, bus wr/rd **12 checks**.

### 5.4 RTL 블록 — slave 1개 최소 예 (CPU 37)

#### 과제 SoC (이미 존재)

```verilog
axi_interconnect u_soc_ic (
  .ACLK    (soc_aclk),
  .ARESETN (soc_aresetn),
  .S37_AXI_arvalid (s37_axi_arvalid),
  .S37_AXI_arready (s37_axi_arready),
  .S37_AXI_araddr  (s37_axi_araddr),
  // ... AW, W, R, B 전 채널
  .Mxx_AXI_*       ( /* DMA slave 등 */ )
);
```

#### VerifCPU SoC cell (repo 제공)

`rtl/verif_vcpu_soc_cell.v` (생성: `make -C firmware/campaign soc_cell`) — bus_type별 모듈:

- `verif_vcpu_soc_cell_apb3`, `_ahb_lite`, `_axi4lite`, … (11종)
- 각 cell = `u_bridge` (AMBA master) + `u_cpu` (`USE_MANIFEST_SOC_BUS=1`)

코어 bus 분기:

```verilog
// Campaign TB: USE_SOC_BUS=1 → simple_soc task bus
// Integration / chip: USE_MANIFEST_SOC_BUS=1 → g_slvN.u_bus.u_bridge.bus_read/write
```

#### Agent + snoop

SoC monitor(또는 `axi_snoop_tap`)가 slave 37 구간 txn을 출력:

```verilog
wire        tap37_valid;
wire        tap37_wr;
wire [31:0] tap37_addr;
wire [31:0] tap37_data;
```

#### Orchestrator (전 CPU 공통)

```verilog
wire        orch_reset;
wire [1:0]  orch_phase;
wire [31:0] orch_boot_fw;
```

#### 인스턴스 (slave 37 — flat `g_slv36`)

```verilog
generate
  begin : g_slv36
    verif_vcpu_soc_cell_axi4lite #(.CPU_ID(37)) u_bus (
      .ACLK(soc_aclk), .ARESETn(soc_aresetn),
      .ARVALID(), .ARADDR(), .ARSIZE(), .RREADY(),
      .AWVALID(), .AWADDR(), .AWSIZE(), .WVALID(), .WDATA(), .WSTRB(), .BREADY(),
      .ARREADY(), .RVALID(), .RDATA(), .RRESP(),
      .AWREADY(), .WREADY(), .BVALID(), .BRESP(),
      .snoop_valid(g_slv_snoop_v[36]), .snoop_wr(g_slv_snoop_wr[36]),
      .snoop_addr(g_slv_snoop_addr[36]), .snoop_data(g_slv_snoop_data[36])
    );
  end
endgenerate

`ifdef CONNECT_SLV37_AXI4LITE
  `CONNECT_SLV37_AXI4LITE;   // from verif_soc_bus_connect.vh
`endif
```

`chip_top_example_gen.vh` / `gen_tb_campaign.py`가 `soc_hierarchy_example.yaml`에서 위 패턴을 자동 생성합니다.

#### 데이터 흐름 (CPU 37만)

```
Master Phase B
  → manifest hint: bus_addr = 0x4A000000
       ↓
VCPU37 FW/icode
  → m_axi → S37_AXI → interconnect → DMA slave
       ↓
Monitor tap37
  → agent37 (TAP_PORT=37) Phase B collect / Phase C verify
```

### 5.5 Master (SCPU0) — slave와 다름

| 항목 | Master |
|------|--------|
| cpu_id | `0` |
| tap_id | 없음 |
| AXI | **read 전용 1포트** (init_done poll) 또는 TB master 공유 |
| 역할 | `init_done` poll, manifest hint 주입, `phase_release` |

`campaign_soc_platform.vh`:

```verilog
`define CAMPAIGN_SOC_INIT_DONE_ADDR  32'h40000018
`define CAMPAIGN_SOC_INIT_DONE_MASK  32'h80000000
`define CAMPAIGN_SOC_INIT_DONE_VALUE 32'h80000000
```

실칩 init_done 주소가 다르면 `soc_platform.h` 수정 → `make soc_init`.

### 5.6 Phase 실행 순서 (campaign과 동일)

1. **Phase A** — SoC init (`soc_init_seq.vh` 17-step, TB/PS AXI write)
2. **VCPU Phase A** — 각 CPU FW `OFF_A` 실행
3. **Agent Phase A** — tap에서 init txn snoop 카운트
4. **init_done poll** — Master AXI read @ `INIT_DONE_ADDR`
5. **Phase B** — Master hint → bus read → Agent slot 수집
6. **Phase C** — VCPU full FW + icode RV32 exec + multi-slot agent verify
7. **VCD** — `vcd_marker = 0xDEADDEAD`

---

## 6. N slave로 확장 (flat `g_slvN` 패턴)

iverilog XMR 제약 때문에 **배열 인덱스 `g_slv[i]` 대신 flat 블록명 `g_slv{cpu_id-1}`** 을 씁니다.  
`gen_tb_campaign.py` / `gen_soc_bus_connect.py`가 manifest·yaml에서 자동 생성합니다.

### 6.1 snoop / agent 배열 (최대 `CAMPAIGN_MAX_SLOTS`)

```verilog
localparam MAX_GI = `CAMPAIGN_MAX_SLOTS;  // e.g. 64 or 100

wire [MAX_GI-1:0]        g_slv_snoop_v;
wire [MAX_GI-1:0]        g_slv_snoop_wr;
wire [31:0] g_slv_snoop_addr [0:MAX_GI-1];
wire [31:0] g_slv_snoop_data [0:MAX_GI-1];

wire [31:0] sl_slot_count [0:MAX_GI-1];
wire [31:0] sl_pass       [0:MAX_GI-1];
wire [31:0] sl_fail       [0:MAX_GI-1];
wire [31:0] sl_txns       [0:MAX_GI-1];
```

`cpu_id=37` → 블록 `g_slv36`, snoop/agent 배열 인덱스 `[36]`.

### 6.2 셀 + agent (생성물: `chip_top_example_gen.vh` / `tb_soc_manifest_gen.vh`)

```verilog
generate
  begin : g_slv0    // cpu_id=1, SFR
    verif_vcpu_soc_cell_apb3 #(.CPU_ID(1)) u_bus (
      .PCLK(soc_clk), .PRESETn(soc_rstn),
      .PADDR(), .PSEL(), /* … APB … */
      .snoop_valid(g_slv_snoop_v[0]), .snoop_wr(g_slv_snoop_wr[0]),
      .snoop_addr(g_slv_snoop_addr[0]), .snoop_data(g_slv_snoop_data[0])
    );
  end
  begin : g_slv36   // cpu_id=37, DMA — 비연속 gi OK
    verif_vcpu_soc_cell_axi4lite #(.CPU_ID(37)) u_bus ( /* … */ );
  end
endgenerate

verif_agent_slave #(.CPU_ID(1), .CPU_NAME("SFR"), .TAP_PORT(0)) u_ag_1 (
  .phase(orch_phase), .boot_fw_offset(orch_boot_fw), .reset_pulse(orch_reset),
  .txn_valid(g_slv_snoop_v[0]), .txn_is_write(g_slv_snoop_wr[0]),
  .txn_addr(g_slv_snoop_addr[0]), .txn_data(g_slv_snoop_data[0]),
  .slot_count(sl_slot_count[0]), .verify_pass(sl_pass[0]), ...
);
```

셀 내부 계약: **`u_bus.u_bridge`** = AMBA master, **`u_bus.u_cpu`** = VCPU (`USE_MANIFEST_SOC_BUS=1`).

### 6.3 CONNECT 매크로 (생성물: `verif_soc_bus_connect.vh`)

```verilog
`include "verif_soc_bus_connect.vh"

`ifdef CONNECT_SLV01_APB3
  `CONNECT_SLV01_APB3;   // S01_APB ↔ g_slv0.u_bus
`endif
`ifdef CONNECT_SLV37_AXI4LITE
  `CONNECT_SLV37_AXI4LITE;  // S37_AXI ↔ g_slv36.u_bus
`endif
// 또는
`APPLY_ALL_SOC_BUS_CONNECTS
```

**generate는 인스턴스만 자동화합니다. 과제 SoC `Sxx_AXI` / `Mxx_AHB` 배선은 manifest·yaml 기반 VH가 담당합니다.**

### 6.4 주소 decode (선택, 생성물: `chip_top_decode.vh` / `tb_soc_manifest_decode.vh`)

Master/agent가 peripheral에 접근할 때 yaml `addr_base`/`addr_size`로 `g_slvN.u_bus.u_bridge`에 라우팅합니다.

### 6.5 외부 포트 수를 줄이고 싶다면 (선택)

CPU 100 × SoC 포트 100이 부담이면 **검증 블록 내부 arbiter** 뒤 SoC에는 **slave port 1개**만 노출하는 아키텍처도 가능합니다.  
이 경우 동시 bus master는 arbitration 순서를 따릅니다. 문법이 아니라 **시스템 설계 선택**입니다.

---

## 7. hierarchy 신호 — 일일이 명시할 필요 없음

`hierarchy_id`는 `verif_cpu_core` **내부 레지스터**입니다 (`cpu_set_hierarchy` task).

- SoC에 별도 wire로 빼지 않음
- VCD scope / 로그 prefix (`Hier%02h`) 용도
- **bus 라우팅·tap 선택과 무관**

검증 대상에 AXI를 보내는 데 필요한 것은:

1. 올바른 **`bus_addr`** (manifest / icode)
2. 올바른 **AXI master 포트** (`axi_mst_port` → connect VH)
3. Agent **tap_id** (snoop 채널)

---

## 8. 체크리스트 (통합 전 확인)

- [ ] manifest `addr_base`..`addr_base+size`가 SoC 주소맵과 일치
- [ ] `tap_id`가 monitor 채널과 1:1
- [ ] `axi_mst_port` 문자열이 과제 interconnect RTL 포트명과 일치
- [ ] probe 후 `icode_map`의 `bus_addr` / `tap_port`가 manifest와 일치
- [ ] `cpu_id` 중복 없음, master는 `0`만
- [ ] `INIT_DONE_ADDR`가 실 SoC 레지스터와 일치 (`make soc_init`)
- [ ] connect VH 재생성 후 과제 top `include` 갱신

---

## 9. Campaign TB와의 대응 (참고)

| Campaign (3 slave) | 실칩 (N slave) |
|--------------------|----------------|
| `simple_soc` | 과제 `axi_interconnect` |
| `verif_soc_bus` task | `verif_axi_lite_master` + connect VH |
| `stxn_valid[TAP]` | `tap_valid[tap_id]` |
| `campaign_manifest.h` | `soc_hierarchy` manifest (확장) |
| `gen_tb_campaign.py` | + `gen_soc_bus_connect.py`, `tb_soc_manifest_gen.vh` |
| `make soc-manifest` | CONNECT_SLV* + real bridges (Phase A/B/C, 23 checks) |
| `make soc-manifest-scale` | flat N-slave BUS_LAYOUT compile + active 3 (26 checks) |
| `make chip-top-example` | orchestrator + agent + bridge bus R/W (12 checks) |

Campaign에서 `make full_campaign` PASS는 RTL/펌웨어/phase 흐름이 맞다는 뜻이지, 과제 배선을 대신해 주지는 않습니다.  
**manifest → generate → include** 절차로 과제 top에 이식합니다.

---

## 10. 관련 파일

| 경로 | 역할 |
|------|------|
| `firmware/campaign/include/campaign_manifest.h` | manifest SSOT (이 패키지 내) |
| `firmware/campaign/include/soc_platform.h` | init_done 주소 |
| `include/campaign_manifest.vh` | 생성 — master hint macro |
| `include/icode_map.vh` | 생성 — icode ptr / bus check |
| `include/tb_full_campaign_gen.vh` | 생성 — CPU/agent generate |
| `include/verif_soc_bus_connect.vh` | 생성 — 과제 AMBA 배선 (`CONNECT_SLVxx`) |
| `rtl/verif_vcpu_soc_cell.v` | 생성 — VCPU + bridge per bus_type |
| `include/tb_soc_manifest_defs.vh` | 생성 — manifest pool/슬롯 매크로 |
| `include/tb_soc_manifest_gen.vh` | 생성 — `g_slv0..N` cells + agents |
| `include/tb_soc_manifest_scale_*.vh` | 생성 — 60-slot flat fabric + CONNECT |
| `tb/tb_soc_manifest.v` | Integration TB (`make soc-manifest`) |
| `tb/tb_soc_manifest_scale.v` | Scale integration TB (`make soc-manifest-scale`) |
| `firmware/campaign/.bus_layout_stamp` | BUS_LAYOUT / NUM_SCPU 영속 (생성됨) |
| `rtl/verif_cpu_core.v` | VCPU 코어 |
| `rtl/verif_agent.v` | master / slave agent |
| `README.md` | campaign TB 빌드·시뮬 |
| `architecture_and_verification.md` | 블록 다이어그램 + 검증 스냅샷 |

---

## 11. Bus bridge RTL (repo 포함)

| bus_type | Bridge module | Agent snoop |
|----------|---------------|-------------|
| `task` | `simple_soc` / `verif_soc_bus` (campaign TB) | `u_soc.stxn_*[tap]` |
| `apb` | `rtl/verif_apb_master.v` | `snoop_valid/wr/addr/data` |
| `ahb` | `rtl/verif_ahb_lite_master.v` | 동일 |
| `axi` | `rtl/verif_axi_lite_master.v` | 동일 |

Bridge는 **`bus_read` / `bus_write` task** API를 제공합니다 (`verif_soc_bus`와 동일 시맨틱).  
VCPU core 앞단에서 `verif_soc_bus` 대신 bridge task를 호출하도록 top을 구성합니다.

스모크 테스트:

```bash
make soc-bus    # tb_soc_bus_bridge — APB + AHB read
```

---

## 12. AHB / APB 통합 절차

### 12.1 Manifest에 bus_type 추가

`campaign_slots.yaml` (campaign) 또는 `soc_hierarchy_example.yaml` (실칩 예시):

```yaml
- name: SFR
  cpu_id: 1
  tap_port: 0
  bus_type: apb          # axi | ahb | apb
  bus_port: S01_APB      # 과제 interconnect 포트 prefix
```

- **Campaign TB** (`./example.sh gen`): `bus_type` 생략 시 `task` → `simple_soc` (변경 없음)
- **실칩**: `bus_type` + `bus_port` 채움

### 12.2 Connect VH 생성

```bash
cd firmware/campaign
make config                              # manifest 갱신
make bus_connect                         # include/verif_soc_bus_connect.vh
make bus_connect_yaml                    # soc_hierarchy_example.yaml 기준 예시
```

생성물: `include/verif_soc_bus_connect.vh`

```verilog
`include "verif_soc_bus_connect.vh"
`define CONNECT_SLV01_APB3  // S01_APB ↔ g_slv0.u_bus
`CONNECT_SLV01_APB;
// 또는
`APPLY_ALL_SOC_BUS_CONNECTS
```

### 12.3 Slave 1개 인스턴스 패턴 (권장: soc cell)

```verilog
generate
  begin : g_slv0   // cpu_id=1
    verif_vcpu_soc_cell_apb3 #(.CPU_ID(1)) u_bus (
      .PCLK(soc_pclk), .PRESETn(soc_presetn),
      // PADDR/PSEL/... ↔ 과제 S01_APB_* via `CONNECT_SLV01_APB3`
      .snoop_valid(tap_valid[0]), .snoop_wr(tap_wr[0]),
      .snoop_addr(tap_addr[0]), .snoop_data(tap_data[0])
    );
  end
endgenerate
`CONNECT_SLV01_APB3
```

`u_bus` 이름은 connect VH 계약 — 변경 금지. AHB/AXI는 `verif_vcpu_soc_cell_ahb_lite` / `_axi4lite` 등으로 교체.

### 12.4 정리

| 질문 | 답 |
|------|-----|
| Campaign `simple_soc` 영향? | 없음 (`bus_type: task`) |
| AHB/APB 가능? | ✅ bridge + `gen_soc_bus_connect.py` |
| Agent 변경? | 없음 — snoop 4신호만 연결 |
| tap_id vs bus_port? | 별개 — manifest에 각각 기록 |

Campaign TB(`simple_soc`)는 그대로 두고, 과제 top에서 bridge + connect VH로 구성합니다.