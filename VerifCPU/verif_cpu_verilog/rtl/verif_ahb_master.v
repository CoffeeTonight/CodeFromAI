// Behavioral AHB full master — single-beat INCR with true address/data pipeline OS
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_lane_helpers.vh"
`include "verif_bus_size_helpers.vh"

module verif_ahb_master #(
  parameter int ADDR_WIDTH = 32,
  parameter int DATA_WIDTH = 32,
  parameter int MAX_OUTSTANDING = 4
)(
  input         HCLK,
  input         HRESETn,
  output reg [ADDR_WIDTH-1:0] HADDR,
  output reg [2:0]  HSIZE,
  output reg [1:0]  HTRANS,
  output reg [2:0]  HBURST,
  output reg [3:0]  HPROT,
  output reg        HMASTLOCK,
  output reg        HWRITE,
  output reg [DATA_WIDTH-1:0] HWDATA,
  output reg        HNONSEC,
  output reg        HEXCL,
  input             HEXOK,
  input  [DATA_WIDTH-1:0] HRDATA,
  input         HREADY,
  input  [1:0]  HRESP,
  output reg        snoop_valid,
  output reg        snoop_wr,
  output reg [31:0] snoop_addr,
  output reg [31:0] snoop_data
);

  // tool: cap_multi_os=1 cap_split_rw=1 cap_blocking_os=0
  localparam int STRB_WIDTH = DATA_WIDTH / 8;
  `VERIF_BUS_LANE_FUNCS(DATA_WIDTH)
  `VERIF_BUS_SIZE_FUNCS_COMPAT
  localparam HTRANS_IDLE   = 2'b00;
  localparam HTRANS_NONSEQ = 2'b10;
  localparam HBURST_INCR   = 3'b001;

  // Slots: issued → addr accepted (in_dphase) → done (data HREADY)
  reg        slot_busy    [0:MAX_OUTSTANDING-1];
  reg        slot_pending [0:MAX_OUTSTANDING-1];  // wait address accept
  reg        slot_dphase  [0:MAX_OUTSTANDING-1];  // in data phase
  reg        slot_done    [0:MAX_OUTSTANDING-1];
  reg        slot_is_wr   [0:MAX_OUTSTANDING-1];
  reg [31:0] slot_addr    [0:MAX_OUTSTANDING-1];
  reg [31:0] slot_wdata   [0:MAX_OUTSTANDING-1];
  reg [2:0]  slot_size    [0:MAX_OUTSTANDING-1];
  reg [31:0] slot_rdata   [0:MAX_OUTSTANDING-1];
  reg [1:0]  slot_resp    [0:MAX_OUTSTANDING-1];
  reg [31:0] slot_order   [0:MAX_OUTSTANDING-1];
  reg [31:0] complete_order;
  reg [31:0] issue_next;
  reg        dphase_active;
  reg [31:0] dphase_slot;

  // Snoop queue (sim agent taps; depth 8 — overflow drops oldest, snq_drop_count++)
  localparam int SNQ_DEPTH = 8;
  reg        snq_v [0:SNQ_DEPTH-1];
  reg        snq_wr [0:SNQ_DEPTH-1];
  reg [31:0] snq_a [0:SNQ_DEPTH-1];
  reg [31:0] snq_d [0:SNQ_DEPTH-1];
  integer    snq_n;

  // Occupied (issued not reaped) — include done-but-unreaped
  function integer os_r_inflight;
    integer n, i;
    begin
      n = 0;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (slot_busy[i] && !slot_is_wr[i])
          n = n + 1;
      os_r_inflight = n;
    end
  endfunction

  function integer os_w_inflight;
    integer n, i;
    begin
      n = 0;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (slot_busy[i] && slot_is_wr[i])
          n = n + 1;
      os_w_inflight = n;
    end
  endfunction

  function integer alloc_slot;
    integer i;
    begin
      alloc_slot = -1;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (!slot_busy[i]) begin
          alloc_slot = i;
          i = MAX_OUTSTANDING;
        end
    end
  endfunction

  function integer fifo_head_pending;
    integer i;
    begin
      fifo_head_pending = -1;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (slot_pending[i] && slot_order[i] == complete_order) begin
          fifo_head_pending = i;
          i = MAX_OUTSTANDING;
        end
    end
  endfunction

  task os_reset_slots;
    integer i;
    begin
      complete_order = 0;
      issue_next = 0;
      dphase_active = 1'b0;
      dphase_slot = 0;
      snq_n = 0;
      for (i = 0; i < SNQ_DEPTH; i = i + 1)
        snq_v[i] = 1'b0;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1) begin
        slot_busy[i] = 1'b0;
        slot_pending[i] = 1'b0;
        slot_dphase[i] = 1'b0;
        slot_done[i] = 1'b0;
        slot_is_wr[i] = 1'b0;
      end
    end
  endtask

  integer snq_drop_count;
  task snq_push;
    input        wr;
    input [31:0] a;
    input [31:0] d;
    integer i;
    begin
      if (snq_n < SNQ_DEPTH) begin
        snq_wr[snq_n] = wr;
        snq_a[snq_n]  = a;
        snq_d[snq_n]  = d;
        snq_v[snq_n]  = 1'b1;
        snq_n = snq_n + 1;
      end else begin
        snq_drop_count = snq_drop_count + 1;
        for (i = 0; i < SNQ_DEPTH - 1; i = i + 1) begin
          snq_wr[i] = snq_wr[i + 1];
          snq_a[i]  = snq_a[i + 1];
          snq_d[i]  = snq_d[i + 1];
          snq_v[i]  = snq_v[i + 1];
        end
        snq_wr[SNQ_DEPTH - 1] = wr;
        snq_a[SNQ_DEPTH - 1]  = a;
        snq_d[SNQ_DEPTH - 1]  = d;
        snq_v[SNQ_DEPTH - 1]  = 1'b1;
      end
    end
  endtask

  task finish_dphase_slot;
    input integer cap;
    begin
      // Sample immediately on HREADY edge (registered HREADY from prior NBA).
      // Do NOT #1 here: that samples after this edge's slave NBA which clears
      // ERROR→OKAY and reintroduces false-OK (lite #1 is for task wait loops).
      if (!slot_is_wr[cap])
        slot_rdata[cap] = lane_prdata(HRDATA, slot_addr[cap], slot_size[cap]);
      slot_resp[cap] = (HRESP != 2'b00) ? 2'd2 : 2'd0;
      slot_done[cap] = 1'b1;
      slot_dphase[cap] = 1'b0;
      snq_push(slot_is_wr[cap], slot_addr[cap],
               slot_is_wr[cap] ? slot_wdata[cap] : slot_rdata[cap]);
    end
  endtask

  initial begin
    HADDR = 32'h0;
    HSIZE = 3'b010;
    HTRANS = HTRANS_IDLE;
    HBURST = HBURST_INCR;
    HPROT = 4'b0011;
    HMASTLOCK = 1'b0;
    HWRITE = 1'b0;
    HWDATA = 32'h0;
    HNONSEC = 1'b1;
    HEXCL = 1'b0;
    snoop_valid = 1'b0;
    snoop_wr = 1'b0;
    snoop_addr = 32'h0;
    snoop_data = 32'h0;
    snq_drop_count = 0;
    os_reset_slots();
  end

  // Data-phase complete first, then accept new address (AHB pipeline)
  always @(posedge HCLK or negedge HRESETn) begin
    integer slot;
    integer si;
    if (!HRESETn) begin
      os_reset_slots();
      snoop_valid <= 1'b0;
      HTRANS <= HTRANS_IDLE;
      HWRITE <= 1'b0;
      HWDATA <= {DATA_WIDTH{1'b0}};
    end else begin
      if (HREADY) begin
        // 1) Complete active data phase on this ready edge
        if (dphase_active) begin
          finish_dphase_slot(dphase_slot);
          dphase_active = 1'b0;
        end
        // 2) Accept address of NONSEQ → enters data phase next ready
        if (HTRANS == HTRANS_NONSEQ) begin
          slot = fifo_head_pending();
          if (slot >= 0) begin
            slot_pending[slot] = 1'b0;
            slot_dphase[slot] = 1'b1;
            dphase_slot = slot;
            dphase_active = 1'b1;
            complete_order = complete_order + 1;
            // NBA: prior write may complete this same HREADY edge; slaves sample
            // HWDATA before NBA, so next-beat data must not appear mid-edge (blocking =).
            if (slot_is_wr[slot])
              HWDATA <= lane_pwdata(slot_wdata[slot], slot_addr[slot],
                                    slot_size[slot]);
          end
        end
      end
      // Drain one snoop pulse per cycle (shift queue)
      if (snq_n > 0 && snq_v[0]) begin
        snoop_valid <= 1'b1;
        snoop_wr    <= snq_wr[0];
        snoop_addr  <= snq_a[0];
        snoop_data  <= snq_d[0];
        for (si = 0; si < SNQ_DEPTH - 1; si = si + 1) begin
          snq_v[si]  = snq_v[si + 1];
          snq_wr[si] = snq_wr[si + 1];
          snq_a[si]  = snq_a[si + 1];
          snq_d[si]  = snq_d[si + 1];
        end
        snq_v[SNQ_DEPTH - 1] = 1'b0;
        snq_n = snq_n - 1;
      end else
        snoop_valid <= 1'b0;
    end
  end

  task ahb_idle;
    begin
      // NBA: same nets driven from always @(posedge HCLK) — avoid blocking/NBA races
      HTRANS <= HTRANS_IDLE;
      if (!(dphase_active && slot_is_wr[dphase_slot])) begin
        HWRITE <= 1'b0;
        HWDATA <= 32'h0;
      end
      HEXCL <= 1'b0;
    end
  endtask

  task ahb_drive_common;
    input [31:0] addr;
    input [2:0]  size;
    begin
      HBURST = HBURST_INCR;
      HPROT = 4'b0011;
      HMASTLOCK = 1'b0;
      HNONSEC = 1'b1;
      HEXCL = 1'b0;
      HADDR = addr;
      HSIZE = hsize_for_bytes(size);
    end
  endtask

  // Issue: drive address phase only; data completes in always @ HREADY
  task ahb_xfer_issue;
    input        is_wr;
    input [31:0] addr;
    input [31:0] wdata;
    input [2:0]  size;
    output integer handle;
    output        ok;
    integer guard;
    begin
      if (!`VERIF_BUS_SIZE_OK(size) || `VERIF_BUS_OS_UNALIGNED(addr, size)) begin
        handle = -1;
        ok = 1'b0;
        $display("[ahb_os] xfer_issue: bad size/align size=%0d @0x%08h", size, addr);
      end else begin
      handle = alloc_slot();
      ok = (handle >= 0);
      if (!ok) begin
        $display("[ahb_os] xfer_issue: outstanding full (MAX=%0d)", MAX_OUTSTANDING);
      end else begin
        slot_busy[handle] = 1'b1;
        slot_pending[handle] = 1'b0;
        slot_dphase[handle] = 1'b0;
        slot_done[handle] = 1'b0;
        slot_is_wr[handle] = is_wr;
        slot_addr[handle] = addr;
        slot_wdata[handle] = wdata;
        slot_size[handle] = size;
        slot_order[handle] = issue_next;
        issue_next = issue_next + 1;

        // Wait until bus can accept a new address (no wait on prior data-only)
        guard = 0;
        while (!HREADY) begin
          @(posedge HCLK);
          `VERIF_BUS_WAIT_TICK(guard, "ahb_full bus_xfer_issue pre HREADY")
        end
        @(posedge HCLK);
        ahb_drive_common(addr, size);
        // NBA for bus outputs shared with always @(posedge) (no blocking/NBA mix)
        HWRITE <= is_wr;
        // Do NOT assign HWDATA here — always installs write data with NBA on NONSEQ accept.
        HTRANS <= HTRANS_NONSEQ;
        slot_pending[handle] = 1'b1;
        // Wait for address accept (pending cleared by always on HREADY+NONSEQ)
        guard = 0;
        while (slot_pending[handle]) begin
          @(posedge HCLK);
          `VERIF_BUS_WAIT_TICK(guard, "ahb_full bus_xfer_issue addr accept")
        end
        // Idle address bus; HWDATA for writes set by always on accept (NBA)
        HTRANS <= HTRANS_IDLE;
        // Do NOT wait for slot_done — true outstanding
      end
      end
    end
  endtask

  task bus_read_issue;
    input  [31:0] addr;
    input  [2:0]  size;
    output integer handle;
    output        ok;
    begin
      ahb_xfer_issue(1'b0, addr, 32'h0, size, handle, ok);
    end
  endtask

  task bus_read_poll;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    output        done;
    begin
      if (handle < 0 || handle >= MAX_OUTSTANDING ||
          !slot_busy[handle] || slot_is_wr[handle]) begin
        done = 1'b0;
        data = 32'h0;
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        done = slot_done[handle];
        data = slot_rdata[handle];
        resp = slot_resp[handle];
      end
    end
  endtask

  task bus_read_wait;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    integer guard;
    reg abort;
    begin
      if (handle < 0 || handle >= MAX_OUTSTANDING ||
          !slot_busy[handle] || slot_is_wr[handle]) begin
        data = 32'hDEADDEAD;
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        guard = 0;
        abort = 1'b0;
        while (!slot_done[handle] && !abort) begin
          @(posedge HCLK);
          `VERIF_BUS_OS_WAIT_OR_RST(guard, "ahb_full bus_read_wait",
                                   HRESETn, slot_busy[handle], abort)
        end
        if (abort || !slot_done[handle]) begin
          data = 32'hDEADDEAD;
          resp = `VERIF_BUS_RESP_SOFT;
          slot_busy[handle] = 1'b0;
          slot_pending[handle] = 1'b0;
          slot_dphase[handle] = 1'b0;
          slot_done[handle] = 1'b0;
        end else begin
          data = slot_rdata[handle];
          resp = slot_resp[handle];
          slot_busy[handle] = 1'b0;
          slot_pending[handle] = 1'b0;
          slot_dphase[handle] = 1'b0;
          slot_done[handle] = 1'b0;
        end
      end
    end
  endtask

  task bus_read_outstanding_count;
    output integer n;
    begin n = os_r_inflight(); end
  endtask

  task bus_write_issue;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output integer handle;
    output        ok;
    begin
      ahb_xfer_issue(1'b1, addr, data, size, handle, ok);
    end
  endtask

  task bus_write_poll;
    input  integer handle;
    output [1:0] resp;
    output       done;
    begin
      if (handle < 0 || handle >= MAX_OUTSTANDING ||
          !slot_busy[handle] || !slot_is_wr[handle]) begin
        done = 1'b0;
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        done = slot_done[handle];
        resp = slot_resp[handle];
      end
    end
  endtask

  task bus_write_wait;
    input  integer handle;
    output [1:0] resp;
    integer guard;
    reg abort;
    begin
      if (handle < 0 || handle >= MAX_OUTSTANDING ||
          !slot_busy[handle] || !slot_is_wr[handle]) begin
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        guard = 0;
        abort = 1'b0;
        while (!slot_done[handle] && !abort) begin
          @(posedge HCLK);
          `VERIF_BUS_OS_WAIT_OR_RST(guard, "ahb_full bus_write_wait",
                                   HRESETn, slot_busy[handle], abort)
        end
        if (abort || !slot_done[handle]) begin
          resp = `VERIF_BUS_RESP_SOFT;
          slot_busy[handle] = 1'b0;
          slot_pending[handle] = 1'b0;
          slot_dphase[handle] = 1'b0;
          slot_done[handle] = 1'b0;
        end else begin
          resp = slot_resp[handle];
          slot_busy[handle] = 1'b0;
          slot_pending[handle] = 1'b0;
          slot_dphase[handle] = 1'b0;
          slot_done[handle] = 1'b0;
        end
      end
    end
  endtask

  task bus_write_outstanding_count;
    output integer n;
    begin n = os_w_inflight(); end
  endtask

  task bus_read_1beat;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    integer h;
    reg ok;
    begin
      bus_read_issue(addr, size, h, ok);
      if (!ok) begin
        data = 32'h0;
        resp = `VERIF_BUS_RESP_SOFT;
      end else
        bus_read_wait(h, data, resp);
    end
  endtask

  task bus_write_1beat;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    integer h;
    reg ok;
    begin
      bus_write_issue(addr, data, size, h, ok);
      if (!ok)
        resp = `VERIF_BUS_RESP_SOFT;
      else
        bus_write_wait(h, resp);
    end
  endtask

  `include "verif_bus_split_rw.vh"
  `VERIF_BUS_DEFINE_SPLIT_RW(bus_read_1beat, bus_write_1beat)

endmodule
