// VerifCPU external SoC bus protocol helpers
//
// Behavioral AMBA bridge model (non-synth). Completion contract:
//   issue → queue; poll → complete once / peek; wait → reap (clear done/slot)
// OS stubs share this contract:
//   verif_bus_os_blocking_tasks.vh | verif_soc_bus.v | verif_cpu_bus.v
// True OS masters: axi_full/lite, ahb_master, chi (slot_done + wait reaps).
//
// Frozen residuals (WONTFIX for this model — not open bugs):
//   - AHB full master: single-beat NONSEQ OS (not multi-beat HBURST engine)
//   - AXI bus_*_issue: ARLEN=0 aligned; unaligned via blocking bus_read/write split
//   - Pure poll without wait: slot/done not reaped (call wait to harvest)
//   - AXI snq ring depth 8 may drop oldest (snq_drop_count)
//   - CONNECT AHB: single-slave HREADY=HREADYOUT loopback
//   - ASB/NIU/AXIS stubs: smoke-only (no full protocol)
//   - CPU bus fault: poison + problem_addrs, not full trap ISA
//
`ifndef VERIF_BUS_DEFS_VH
`define VERIF_BUS_DEFS_VH

`ifndef VERIF_BUS_WAIT_MAX_CYCLES
  `define VERIF_BUS_WAIT_MAX_CYCLES 4096
`endif

// bus_* task resp codes (behavioral model)
//   0 = OKAY, 1 = soft (no outstanding / free handle), 2 = SLVERR, 3 = DECERR
`define VERIF_BUS_RESP_OK    2'd0
`define VERIF_BUS_RESP_SOFT  2'd1
`define VERIF_BUS_RESP_SLV   2'd2
`define VERIF_BUS_RESP_DEC   2'd3

// CPU core OS handle table depth (must cover MAX_OUTSTANDING on masters)
`ifndef VERIF_CPU_OS_HANDLE_MAX
  `define VERIF_CPU_OS_HANDLE_MAX 32
`endif

// Legal AMBA byte-count size for this model (not AxSIZE encoding).
`define VERIF_BUS_SIZE_OK(SIZE) \
  (((SIZE) == 3'd1) || ((SIZE) == 3'd2) || ((SIZE) == 3'd4))

// OS issue alignment: multi-byte must not cross word without split (use bus_read/write).
// ADDR must be a simple identifier/net (not a general expression) — part-select on (expr) is illegal.
`define VERIF_BUS_OS_UNALIGNED(ADDR, SIZE) \
  ((((SIZE) == 3'd2) && (ADDR[1:0] == 2'd3)) || \
   (((SIZE) == 3'd4) && (ADDR[1:0] != 2'd0)))

// Non-wrapping span in [0, LIMIT): true if size bytes from addr fit.
// Avoids 32-bit wrap false-accept (e.g. addr=0xFFFFFFFE, size=4).
`define VERIF_BUS_SPAN_OK(ADDR, SIZE, LIMIT) \
  (((SIZE) != 0) && ((ADDR) < (LIMIT)) && (((LIMIT) - (ADDR)) >= (SIZE)))

// Relative span in [BASE, BASE+MEMSIZE): true if size bytes from addr fit.
`define VERIF_BUS_REL_SPAN_OK(ADDR, SIZE, BASE, MEMSIZE) \
  (((SIZE) != 0) && ((ADDR) >= (BASE)) && \
   (((ADDR) - (BASE)) < (MEMSIZE)) && \
   (((MEMSIZE) - ((ADDR) - (BASE))) >= (SIZE)))

// Increment guard inside bus task wait loops; call after each @(posedge clk).
`define VERIF_BUS_WAIT_TICK(guard, tag) \
  begin \
    guard = guard + 1; \
    if (guard > `VERIF_BUS_WAIT_MAX_CYCLES) \
      $fatal(1, "[bus] %0s: handshake timeout after %0d cycles", tag, guard); \
  end

// OS wait abort: mid-transfer reset or slot reaped by async reset → SOFT, no hang.
// Use inside a named begin/end after @(posedge clk); sets abort=1 when live drops.
`define VERIF_BUS_OS_WAIT_OR_RST(guard, tag, rst_n, still_live, abort) \
  begin \
    if (!(rst_n) || !(still_live)) \
      abort = 1'b1; \
    else begin \
      abort = 1'b0; \
      `VERIF_BUS_WAIT_TICK(guard, tag) \
    end \
  end

`define VERIF_BUS_TASK      0
`define VERIF_BUS_NONE      1
`define VERIF_BUS_AXI4LITE  2
`define VERIF_BUS_AHB_LITE  3
`define VERIF_BUS_APB3      4
// Legacy aliases (manifest / YAML shorthand)
`define VERIF_BUS_AXI  `VERIF_BUS_AXI4LITE
`define VERIF_BUS_AHB  `VERIF_BUS_AHB_LITE
`define VERIF_BUS_APB  `VERIF_BUS_APB3
// Implemented AMBA bridge kinds (see amba_bus_registry.py + verif_vcpu_soc_cell.v)
`define VERIF_BUS_APB2      10
`define VERIF_BUS_APB4      11
`define VERIF_BUS_APB5      12
`define VERIF_BUS_AHB5_LITE 13
`define VERIF_BUS_AHB_FULL  14
`define VERIF_BUS_AXI3FULL  15
`define VERIF_BUS_AXI4FULL  16
`define VERIF_BUS_AXI5FULL  17
// Planned / manifest-only
`define VERIF_BUS_AXIS      20
`define VERIF_BUS_NIU       21

// Capability tags (tool/docs; grep-friendly). Not synthesizable config bits.
// cap_blocking_os=1  — OS via live/done poll-once stubs
// cap_multi_os=1     — true multi-outstanding slots (wait reaps)
// cap_split_rw=1     — blocking bus_read/write split unaligned
// cap_smoke_only=1   — incomplete protocol (ASB/NIU/AXIS stubs)
`define VERIF_BUS_CAP_BLOCKING_OS  "cap_blocking_os=1"
`define VERIF_BUS_CAP_MULTI_OS     "cap_multi_os=1"
`define VERIF_BUS_CAP_SPLIT_RW     "cap_split_rw=1"
`define VERIF_BUS_CAP_SMOKE_ONLY   "cap_smoke_only=1"

// Agent snoop bundle pulse — pass reg identifiers for valid/wr/addr/data
`define VERIF_SNOOP_PULSE(V, WR, ADDR, DATA, IS_WR, A, D) \
  begin \
    WR = IS_WR; \
    ADDR = A; \
    DATA = D; \
    V = 1'b1; \
    #1 V = 1'b0; \
  end

`endif