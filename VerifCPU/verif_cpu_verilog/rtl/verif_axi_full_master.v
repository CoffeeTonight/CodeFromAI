// Behavioral AXI3/4/5 full master — single-beat INCR + optional multiple outstanding
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_lane_helpers.vh"
`include "verif_bus_size_helpers.vh"

module verif_axi_full_master #(
  parameter int ADDR_WIDTH = 32,
  parameter int DATA_WIDTH = 32,
  parameter int AXI_PROT = 4,
  parameter int ID_WIDTH = 4,
  parameter int ID_BASE = 0,
  parameter int MAX_OUTSTANDING = 4,
  // Snoop queue depth; overflow drops oldest and bumps snq_drop_count
  parameter int SNQ_DEPTH = 8
)(
  input         ACLK,
  input         ARESETn,
  output reg [ID_WIDTH-1:0] ARID,
  output reg [ADDR_WIDTH-1:0] ARADDR,
  output reg [7:0]  ARLEN,
  output reg [2:0]  ARSIZE,
  output reg [1:0]  ARBURST,
  output reg [2:0]  ARPROT,
  output reg        ARLOCK,   // AXI3 lock — tied 0 (AXI4+ uses AWATOP exclusive)
  output reg [3:0]  ARQOS,
  output reg [3:0]  ARREGION,
  output reg        ARVALID,
  input             ARREADY,
  input  [ID_WIDTH-1:0] RID,
  input  [DATA_WIDTH-1:0] RDATA,
  input  [1:0]  RRESP,
  input             RLAST,
  input             RVALID,
  output reg        RREADY,
  output reg [ID_WIDTH-1:0] AWID,
  output reg [ADDR_WIDTH-1:0] AWADDR,
  output reg [7:0]  AWLEN,
  output reg [2:0]  AWSIZE,
  output reg [1:0]  AWBURST,
  output reg [2:0]  AWPROT,
  output reg        AWLOCK,   // AXI3 lock — tied 0
  output reg [3:0]  AWQOS,
  output reg [3:0]  AWREGION,
  output reg [5:0]  AWATOP,
  output reg        AWVALID,
  input             AWREADY,
  output reg [ID_WIDTH-1:0] WID,
  output reg [DATA_WIDTH-1:0] WDATA,
  output reg [DATA_WIDTH/8-1:0] WSTRB,
  output reg        WLAST,
  output reg        WVALID,
  input             WREADY,
  input  [ID_WIDTH-1:0] BID,
  input  [1:0]  BRESP,
  input             BVALID,
  output reg        BREADY,
  output reg        snoop_valid,
  output reg        snoop_wr,
  output reg [31:0] snoop_addr,
  output reg [31:0] snoop_data
);

  // tool: cap_multi_os=1 cap_split_rw=1 cap_smoke_burst=1
  localparam int STRB_WIDTH = DATA_WIDTH / 8;
  `VERIF_BUS_LANE_FUNCS(DATA_WIDTH)
  `VERIF_BUS_SIZE_FUNCS_COMPAT
  localparam BURST_INCR = 2'b01;
  localparam BURST_WRAP = 2'b10;

  // Outstanding read slots — handle == AXI ID == slot index
  reg        r_slot_busy   [0:MAX_OUTSTANDING-1];
  reg        r_slot_ar_done [0:MAX_OUTSTANDING-1];
  reg        r_slot_done   [0:MAX_OUTSTANDING-1];
  reg [31:0] r_slot_addr   [0:MAX_OUTSTANDING-1];
  reg [2:0]  r_slot_size   [0:MAX_OUTSTANDING-1];
  reg [31:0] r_slot_data   [0:MAX_OUTSTANDING-1];
  reg [1:0]  r_slot_resp   [0:MAX_OUTSTANDING-1];
  reg [1:0]  r_slot_resp_sticky [0:MAX_OUTSTANDING-1];

  reg        w_slot_busy   [0:MAX_OUTSTANDING-1];
  reg        w_slot_done   [0:MAX_OUTSTANDING-1];
  reg [31:0] w_slot_addr   [0:MAX_OUTSTANDING-1];
  reg [31:0] w_slot_data   [0:MAX_OUTSTANDING-1];
  reg [1:0]  w_slot_resp   [0:MAX_OUTSTANDING-1];

  // Snoop queue — overflow drops oldest, snq_drop_count++
  reg        snq_v [0:SNQ_DEPTH-1];
  reg        snq_wr [0:SNQ_DEPTH-1];
  reg [31:0] snq_a [0:SNQ_DEPTH-1];
  reg [31:0] snq_d [0:SNQ_DEPTH-1];
  integer    snq_n;

  integer gi;

  function [1:0] resp_or_worse;
    input [1:0] a;
    input [1:0] b;
    begin
      // Prefer DECERR(3) > SLVERR(2) > OK(0); EXOKAY maps to 0 already
      if (a == 2'd3 || b == 2'd3)
        resp_or_worse = 2'd3;
      else if (a == 2'd2 || b == 2'd2)
        resp_or_worse = 2'd2;
      else
        resp_or_worse = 2'd0;
    end
  endfunction

  // Ring snoop: never silent-drop; if full, overwrite oldest (still one event lost → count)
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
        // shift drop head, append tail — always keep latest SNQ_DEPTH events
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

  // Occupied slots (issued not yet reaped) — matches blocking OS live||done
  function integer os_r_inflight;
    integer n;
    integer i;
    begin
      n = 0;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (r_slot_busy[i])
          n = n + 1;
      os_r_inflight = n;
    end
  endfunction

  // On-wire only (still need R channel)
  function integer os_r_need_rready;
    integer n;
    integer i;
    begin
      n = 0;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (r_slot_busy[i] && !r_slot_done[i])
          n = n + 1;
      os_r_need_rready = n;
    end
  endfunction

  function integer os_w_inflight;
    integer n;
    integer i;
    begin
      n = 0;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (w_slot_busy[i])
          n = n + 1;
      os_w_inflight = n;
    end
  endfunction

  // On-wire only (still need B channel)
  function integer os_w_need_bready;
    integer n;
    integer i;
    begin
      n = 0;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (w_slot_busy[i] && !w_slot_done[i])
          n = n + 1;
      os_w_need_bready = n;
    end
  endfunction

  function integer alloc_r_slot;
    integer i;
    begin
      alloc_r_slot = -1;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (!r_slot_busy[i]) begin
          alloc_r_slot = i;
          i = MAX_OUTSTANDING;
        end
    end
  endfunction

  function integer alloc_w_slot;
    integer i;
    begin
      alloc_w_slot = -1;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (!w_slot_busy[i]) begin
          alloc_w_slot = i;
          i = MAX_OUTSTANDING;
        end
    end
  endfunction

  function integer rid_to_slot;
    input [ID_WIDTH-1:0] id;
    integer i;
    begin
      rid_to_slot = -1;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (r_slot_busy[i] && !r_slot_done[i] && id == (ID_BASE + i)) begin
          rid_to_slot = i;
          i = MAX_OUTSTANDING;
        end
    end
  endfunction

  function integer bid_to_slot;
    input [ID_WIDTH-1:0] id;
    integer i;
    begin
      bid_to_slot = -1;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (w_slot_busy[i] && !w_slot_done[i] && id == (ID_BASE + i)) begin
          bid_to_slot = i;
          i = MAX_OUTSTANDING;
        end
    end
  endfunction

  function [1:0] axi_resp_code;
    input [1:0] axi_resp;
    begin
      case (axi_resp)
        2'b00: axi_resp_code = 2'd0;
        2'b01: axi_resp_code = 2'd0;  // EXOKAY
        2'b10: axi_resp_code = 2'd2;
        2'b11: axi_resp_code = 2'd3;
        default: axi_resp_code = 2'd2;
      endcase
    end
  endfunction

  task os_reset_slots;
    integer i;
    begin
      snq_n = 0;
      for (i = 0; i < SNQ_DEPTH; i = i + 1)
        snq_v[i] = 1'b0;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1) begin
        r_slot_busy[i] = 1'b0;
        r_slot_ar_done[i] = 1'b0;
        r_slot_done[i] = 1'b0;
        r_slot_resp_sticky[i] = 2'd0;
        w_slot_busy[i] = 1'b0;
        w_slot_done[i] = 1'b0;
      end
    end
  endtask

  // Smoke/burst tasks (incr/locked) hold ready without OS slots — tracked so orphan checks stay clean
  reg        smoke_r_active;
  reg        smoke_b_active;

  initial begin
    ARID = 0; ARADDR = 0; ARLEN = 0; ARSIZE = 3'b010; ARBURST = BURST_INCR;
    ARPROT = 3'b010; ARLOCK = 1'b0; ARQOS = 0; ARREGION = 0; ARVALID = 0; RREADY = 0;
    AWID = 0; AWADDR = 0; AWLEN = 0; AWSIZE = 3'b010; AWBURST = BURST_INCR;
    AWPROT = 3'b010; AWLOCK = 1'b0; AWQOS = 0; AWREGION = 0; AWATOP = 0; AWVALID = 0;
    WID = 0; WDATA = 0; WSTRB = 0; WLAST = 0; WVALID = 0; BREADY = 0;
    snoop_valid = 0; snoop_wr = 0; snoop_addr = 0; snoop_data = 0;
    smoke_r_active = 1'b0;
    smoke_b_active = 1'b0;
    snq_drop_count = 0;
    os_reset_slots();
  end

  // R + B + snoop drain in one always (no push/pop race)
  always @(posedge ACLK or negedge ARESETn) begin
    integer slot;
    integer si;
    reg [1:0] beat_resp;
    if (!ARESETn) begin
      RREADY <= 1'b0;
      BREADY <= 1'b0;
      ARVALID <= 1'b0;
      AWVALID <= 1'b0;
      WVALID  <= 1'b0;
      WLAST   <= 1'b0;
      snoop_valid <= 1'b0;
      snoop_wr    <= 1'b0;
      snoop_addr  <= 32'h0;
      snoop_data  <= 32'h0;
      smoke_r_active = 1'b0;
      smoke_b_active = 1'b0;
      os_reset_slots();
      snq_n = 0;
      for (si = 0; si < SNQ_DEPTH; si = si + 1)
        snq_v[si] = 1'b0;
    end else begin
      // No || RVALID/BVALID drain of unmatched beats
      RREADY <= smoke_r_active || (os_r_need_rready() > 0);
      BREADY <= smoke_b_active || (os_w_need_bready() > 0);
      if (RVALID && RREADY) begin
        slot = rid_to_slot(RID);
        if (slot >= 0) begin
          beat_resp = axi_resp_code(RRESP);
          r_slot_resp_sticky[slot] = resp_or_worse(r_slot_resp_sticky[slot], beat_resp);
          if (RLAST) begin
            r_slot_data[slot] = lane_prdata(RDATA, r_slot_addr[slot], r_slot_size[slot]);
            r_slot_resp[slot] = r_slot_resp_sticky[slot];
            r_slot_done[slot] = 1'b1;
            r_slot_ar_done[slot] = 1'b0;
            snq_push(1'b0, r_slot_addr[slot], r_slot_data[slot]);
          end
        end else if (RLAST && !smoke_r_active && os_r_need_rready() > 0)
          $error("axi_full_master: orphan R channel RID=0x%0h (no matching slot)", RID);
      end
      if (BVALID && BREADY) begin
        slot = bid_to_slot(BID);
        if (slot >= 0) begin
          w_slot_resp[slot] = axi_resp_code(BRESP);
          w_slot_done[slot] = 1'b1;
          snq_push(1'b1, w_slot_addr[slot], w_slot_data[slot]);
        end else if (!smoke_b_active && os_w_need_bready() > 0)
          $error("axi_full_master: orphan B channel BID=0x%0h (no matching slot)", BID);
      end
      // Drain snoop queue: present one event for a full ACLK cycle (valid high for
      // the cycle after NBA), then pop on next edge when still head. Hold addr/data
      // while valid so agents sampling posedge ACLK always see stable payload.
      if (snoop_valid) begin
        // End of present cycle — pop head if it matches what we drove
        if (snq_n > 0 && snq_v[0]) begin
          for (si = 0; si < SNQ_DEPTH - 1; si = si + 1) begin
            snq_v[si]  = snq_v[si + 1];
            snq_wr[si] = snq_wr[si + 1];
            snq_a[si]  = snq_a[si + 1];
            snq_d[si]  = snq_d[si + 1];
          end
          snq_v[SNQ_DEPTH - 1] = 1'b0;
          snq_n = snq_n - 1;
        end
        if (snq_n > 0 && snq_v[0]) begin
          snoop_wr    <= snq_wr[0];
          snoop_addr  <= snq_a[0];
          snoop_data  <= snq_d[0];
          snoop_valid <= 1'b1;
        end else begin
          snoop_valid <= 1'b0;
        end
      end else if (snq_n > 0 && snq_v[0]) begin
        snoop_wr    <= snq_wr[0];
        snoop_addr  <= snq_a[0];
        snoop_data  <= snq_d[0];
        snoop_valid <= 1'b1;
      end else
        snoop_valid <= 1'b0;
    end
  end

  task axi_idle;
    begin
      ARVALID = 1'b0;
      AWVALID = 1'b0;
      WVALID  = 1'b0;
      WSTRB   = {STRB_WIDTH{1'b0}};
      WLAST   = 1'b0;
    end
  endtask

  // --- Outstanding read API ---
  task bus_read_issue;
    input  [31:0] addr;
    input  [2:0]  size;
    output integer handle;
    output        ok;
    integer guard;
    begin
      // Legal size 1/2/4; unaligned multi-byte needs blocking bus_read (split)
      if (!`VERIF_BUS_SIZE_OK(size) || `VERIF_BUS_OS_UNALIGNED(addr, size)) begin
        handle = -1;
        ok = 1'b0;
        $display("[axi_os] bus_read_issue: bad size/align size=%0d @0x%08h", size, addr);
      end else begin
      handle = alloc_r_slot();
      ok = (handle >= 0);
      if (!ok) begin
        $display("[axi_os] bus_read_issue: outstanding full (MAX=%0d)", MAX_OUTSTANDING);
      end else begin
        r_slot_busy[handle] = 1'b1;
        r_slot_ar_done[handle] = 1'b0;
        r_slot_done[handle] = 1'b0;
        r_slot_resp_sticky[handle] = 2'd0;
        r_slot_addr[handle] = addr;
        r_slot_size[handle] = size;
        axi_idle();
        @(posedge ACLK);
        ARID = ID_BASE + handle;
        ARADDR = addr;
        ARLEN = 8'd0;
        ARSIZE = axsize_for_bytes(size);
        ARBURST = BURST_INCR;
        ARPROT = 3'b010;
        ARLOCK = 1'b0;
        ARQOS = 4'd0;
        ARREGION = 4'd0;
        ARVALID = 1'b1;
        guard = 0;
        do begin
          @(posedge ACLK);
          `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_read_issue ARREADY")
        end while (!ARREADY);
        r_slot_ar_done[handle] = 1'b1;
        ARVALID = 1'b0;
        @(posedge ACLK);
      end
      end
    end
  endtask

  task bus_read_poll;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    output        done;
    begin
      if (handle < 0 || handle >= MAX_OUTSTANDING || !r_slot_busy[handle]) begin
        done = 1'b0;
        data = 32'h0;
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        done = r_slot_done[handle];
        data = r_slot_data[handle];
        resp = r_slot_resp[handle];
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
      if (handle < 0 || handle >= MAX_OUTSTANDING || !r_slot_busy[handle]) begin
        data = 32'hDEADDEAD;
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        guard = 0;
        abort = 1'b0;
        while (!r_slot_done[handle] && !abort) begin
          @(posedge ACLK);
          `VERIF_BUS_OS_WAIT_OR_RST(guard, "axi_full bus_read_wait",
                                   ARESETn, r_slot_busy[handle], abort)
        end
        if (abort || !r_slot_done[handle]) begin
          data = 32'hDEADDEAD;
          resp = `VERIF_BUS_RESP_SOFT;
          r_slot_busy[handle] = 1'b0;
          r_slot_ar_done[handle] = 1'b0;
          r_slot_done[handle] = 1'b0;
        end else begin
          data = r_slot_data[handle];
          resp = r_slot_resp[handle];
          r_slot_busy[handle] = 1'b0;
          r_slot_ar_done[handle] = 1'b0;
          r_slot_done[handle] = 1'b0;
        end
      end
    end
  endtask

  task bus_read_outstanding_count;
    output integer n;
    begin n = os_r_inflight(); end
  endtask

  // --- Outstanding write API ---
  task bus_write_issue;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output integer handle;
    output        ok;
    integer guard;
    begin
      if (!`VERIF_BUS_SIZE_OK(size) || `VERIF_BUS_OS_UNALIGNED(addr, size)) begin
        handle = -1;
        ok = 1'b0;
        $display("[axi_os] bus_write_issue: bad size/align size=%0d @0x%08h", size, addr);
      end else begin
      handle = alloc_w_slot();
      ok = (handle >= 0);
      if (!ok) begin
        $display("[axi_os] bus_write_issue: outstanding full (MAX=%0d)", MAX_OUTSTANDING);
      end else begin
        w_slot_busy[handle] = 1'b1;
        w_slot_done[handle] = 1'b0;
        w_slot_addr[handle] = addr;
        w_slot_data[handle] = data;
        axi_idle();
        @(posedge ACLK);
        AWID = ID_BASE + handle;
        AWADDR = addr;
        AWLEN = 8'd0;
        AWSIZE = axsize_for_bytes(size);
        AWBURST = BURST_INCR;
        AWPROT = 3'b010;
        AWLOCK = 1'b0;
        AWQOS = 4'd0;
        AWREGION = 4'd0;
        AWATOP = 6'd0;
        AWVALID = 1'b1;
        WDATA = lane_pwdata(data, addr, size);
        WSTRB = lane_wstrb(addr, size);
        WLAST = 1'b1;
        WVALID = 1'b1;
        if (AXI_PROT == 3)
          WID = ID_BASE + handle;
        // Joint AW/W completion (same-edge AW+W legal; do not re-arm W)
        begin : _aw_w_hs
          reg aw_done, w_done;
          aw_done = 1'b0;
          w_done = 1'b0;
          guard = 0;
          while (!aw_done || !w_done) begin
            @(posedge ACLK);
            `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_write_issue AW/W")
            if (!aw_done && AWVALID && AWREADY) begin
              AWVALID = 1'b0;
              aw_done = 1'b1;
            end
            if (!w_done && WVALID && WREADY) begin
              WVALID = 1'b0;
              WLAST = 1'b0;
              w_done = 1'b1;
            end
          end
        end
        @(posedge ACLK);
      end
      end
    end
  endtask

  task bus_write_poll;
    input  integer handle;
    output [1:0] resp;
    output       done;
    begin
      if (handle < 0 || handle >= MAX_OUTSTANDING || !w_slot_busy[handle]) begin
        done = 1'b0;
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        done = w_slot_done[handle];
        resp = w_slot_resp[handle];
      end
    end
  endtask

  task bus_write_wait;
    input  integer handle;
    output [1:0] resp;
    integer guard;
    reg abort;
    begin
      if (handle < 0 || handle >= MAX_OUTSTANDING || !w_slot_busy[handle]) begin
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        guard = 0;
        abort = 1'b0;
        while (!w_slot_done[handle] && !abort) begin
          @(posedge ACLK);
          `VERIF_BUS_OS_WAIT_OR_RST(guard, "axi_full bus_write_wait",
                                   ARESETn, w_slot_busy[handle], abort)
        end
        if (abort || !w_slot_done[handle]) begin
          resp = `VERIF_BUS_RESP_SOFT;
          w_slot_busy[handle] = 1'b0;
          w_slot_done[handle] = 1'b0;
        end else begin
          resp = w_slot_resp[handle];
          w_slot_busy[handle] = 1'b0;
          w_slot_done[handle] = 1'b0;
        end
      end
    end
  endtask

  task bus_write_outstanding_count;
    output integer n;
    begin n = os_w_inflight(); end
  endtask

  // Blocking INCR/WRAP burst read (smoke — collects up to 4 beats)
  task bus_read_incr;
    input  [31:0] addr;
    input  [7:0]  arlen;
    input  [2:0]  size;
    input  [1:0]  burst;
    output [31:0] data0;
    output [31:0] data1;
    output [31:0] data2;
    output [31:0] data3;
    output [1:0]  resp;
    output integer beat_count;
    output        had_slverr;
    output        had_decerr;
    integer guard;
    reg       got_last;
    begin
      data0 = 32'h0;
      data1 = 32'h0;
      data2 = 32'h0;
      data3 = 32'h0;
      resp = 2'd0;
      beat_count = 0;
      had_slverr = 1'b0;
      had_decerr = 1'b0;
      axi_idle();
      @(posedge ACLK);
      ARID = {ID_WIDTH{1'b0}};
      ARADDR = addr;
      ARLEN = arlen;
      ARSIZE = axsize_for_bytes(size);
      ARBURST = burst;
      ARPROT = 3'b010;
      ARLOCK = 1'b0;
      ARQOS = 4'd0;
      ARREGION = 4'd0;
      ARVALID = 1'b1;
      guard = 0;
      do begin
        @(posedge ACLK);
        `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_read_incr ARREADY")
      end while (!ARREADY);
      ARVALID = 1'b0;
      got_last = 1'b0;
      while (!got_last) begin
        // Raise RREADY only while waiting/sampling this beat (no gap steal)
        smoke_r_active = 1'b1;
        guard = 0;
        do begin
          @(posedge ACLK);
          `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_read_incr RVALID")
        end while (!(RVALID && RREADY));
        resp = axi_resp_code(RRESP);
        if (RRESP == 2'b10)
          had_slverr = 1'b1;
        if (RRESP == 2'b11)
          had_decerr = 1'b1;
        if (beat_count == 0) data0 = RDATA;
        else if (beat_count == 1) data1 = RDATA;
        else if (beat_count == 2) data2 = RDATA;
        else if (beat_count == 3) data3 = RDATA;
        beat_count = beat_count + 1;
        got_last = RLAST;
        smoke_r_active = 1'b0;
        @(posedge ACLK);
      end
      smoke_r_active = 1'b0;
      axi_idle();
    end
  endtask

  task bus_read_dual_outstanding;
    input  [31:0] addr0;
    input  [31:0] addr1;
    input  [2:0]  size;
    output [31:0] data0;
    output [31:0] data1;
    output [1:0]  resp0;
    output [1:0]  resp1;
    output        ok;
    integer h0;
    integer h1;
    reg       ok0;
    reg       ok1;
    begin
      data0 = 32'h0;
      data1 = 32'h0;
      resp0 = `VERIF_BUS_RESP_SOFT;
      resp1 = `VERIF_BUS_RESP_SOFT;
      ok = 1'b0;
      bus_read_issue(addr0, size, h0, ok0);
      bus_read_issue(addr1, size, h1, ok1);
      ok = ok0 && ok1;
      if (ok) begin
        bus_read_wait(h0, data0, resp0);
        bus_read_wait(h1, data1, resp1);
      end else begin
        // Reap any successful issue so slots are not orphaned
        if (ok0)
          bus_read_wait(h0, data0, resp0);
        if (ok1)
          bus_read_wait(h1, data1, resp1);
      end
    end
  endtask

  // Blocking single-beat + split half across word (addr[1:0]==3)
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

  // AXI4 atomic / exclusive store smoke (AWATOP[5:0], e.g. 6'h02 = exclusive store)
  task bus_write_atop;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    input  [5:0]  atop;
    output [1:0]  resp;
    integer h;
    reg       ok;
    integer   guard;
    begin
      resp = `VERIF_BUS_RESP_SOFT;
      if (!`VERIF_BUS_SIZE_OK(size) || `VERIF_BUS_OS_UNALIGNED(addr, size)) begin
        $display("[axi_os] bus_write_atop: bad size/align size=%0d @0x%08h", size, addr);
      end else begin
      h = alloc_w_slot();
      ok = (h >= 0);
      if (!ok) begin
        $display("[axi_os] bus_write_atop: outstanding full (MAX=%0d)", MAX_OUTSTANDING);
      end else begin
        w_slot_busy[h] = 1'b1;
        w_slot_done[h] = 1'b0;
        w_slot_addr[h] = addr;
        w_slot_data[h] = data;
        axi_idle();
        @(posedge ACLK);
        AWID = ID_BASE + h;
        AWADDR = addr;
        AWLEN = 8'd0;
        AWSIZE = axsize_for_bytes(size);
        AWBURST = BURST_INCR;
        AWPROT = 3'b010;
        AWLOCK = 1'b0;
        AWQOS = 4'd0;
        AWREGION = 4'd0;
        AWATOP = atop;
        AWVALID = 1'b1;
        WDATA = lane_pwdata(data, addr, size);
        WSTRB = lane_wstrb(addr, size);
        WLAST = 1'b1;
        WVALID = 1'b1;
        if (AXI_PROT == 3)
          WID = ID_BASE + h;
        begin : _atop_aw_w
          reg aw_done, w_done;
          aw_done = 1'b0;
          w_done = 1'b0;
          guard = 0;
          while (!aw_done || !w_done) begin
            @(posedge ACLK);
            `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_write_atop AW/W")
            if (!aw_done && AWVALID && AWREADY) begin
              AWVALID = 1'b0;
              aw_done = 1'b1;
            end
            if (!w_done && WVALID && WREADY) begin
              WVALID = 1'b0;
              WLAST = 1'b0;
              w_done = 1'b1;
            end
          end
        end
        AWATOP = 6'd0;
        @(posedge ACLK);
        bus_write_wait(h, resp);
      end
      end
    end
  endtask

  task bus_write_exclusive;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    begin
      bus_write_atop(addr, data, size, 6'h02, resp);
    end
  endtask

  // Beat address for INCR / WRAP (matches verif_axi_full_slave_simple.axi_burst_addr)
  function [31:0] axi_wrap_addr;
    input [31:0] base_addr;
    input [7:0]  beat;
    input [7:0]  blen;
    input [1:0]  burst;
    input [2:0]  axsize;
    reg [31:0]   wrap_bytes;
    reg [31:0]   wrap_mask;
    reg [31:0]   align_base;
    reg [31:0]   offset;
    begin
      if (burst == 2'b00)
        axi_wrap_addr = base_addr;  // FIXED
      else if (burst == BURST_WRAP) begin
        wrap_bytes = (blen + 1) << axsize;
        wrap_mask  = wrap_bytes - 1;
        align_base = base_addr & ~wrap_mask;
        offset = (base_addr - align_base) + (beat << axsize);
        if (offset >= wrap_bytes)
          offset = offset - wrap_bytes;
        axi_wrap_addr = align_base + offset;
      end else
        axi_wrap_addr = base_addr + (beat << axsize);  // INCR
    end
  endfunction

  // Blocking INCR/WRAP burst write — pattern_base + beat index per W beat
  task bus_write_incr;
    input  [31:0] addr;
    input  [7:0]  awlen;
    input  [2:0]  size;
    input  [1:0]  burst;
    input  [31:0] pattern_base;
    output [1:0]  resp;
    output        had_slverr;
    output        had_decerr;
    integer       guard;
    integer       beat;
    integer       nbeats;
    reg [31:0]    wdata;
    reg [31:0]    beat_addr;
    reg [2:0]     axsz;
    begin
      resp = `VERIF_BUS_RESP_SOFT;
      had_slverr = 1'b0;
      had_decerr = 1'b0;
      nbeats = awlen + 1;
      axsz = axsize_for_bytes(size);
      axi_idle();
      @(posedge ACLK);
      AWID = {ID_WIDTH{1'b0}};
      AWADDR = addr;
      AWLEN = awlen;
      AWSIZE = axsz;
      AWBURST = burst;
      AWPROT = 3'b010;
      AWLOCK = 1'b0;
      AWQOS = 4'd0;
      AWREGION = 4'd0;
      AWATOP = 6'd0;
      AWVALID = 1'b1;
      guard = 0;
      do begin
        @(posedge ACLK);
        `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_write_incr AWREADY")
      end while (!AWREADY);
      AWVALID = 1'b0;
      @(posedge ACLK);
      beat = 0;
      while (beat < nbeats) begin
        wdata = pattern_base + beat;
        // WRAP must use wrap boundary, not linear INCR offset
        beat_addr = axi_wrap_addr(addr, beat[7:0], awlen, burst, axsz);
        WDATA = lane_pwdata(wdata, beat_addr, size);
        WSTRB = lane_wstrb(beat_addr, size);
        WLAST = (beat == nbeats - 1);
        WVALID = 1'b1;
        if (AXI_PROT == 3)
          WID = {ID_WIDTH{1'b0}};
        guard = 0;
        do begin
          @(posedge ACLK);
          `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_write_incr WREADY")
        end while (!WREADY);
        WVALID = 1'b0;
        WLAST = 1'b0;
        @(posedge ACLK);
        beat = beat + 1;
      end
      smoke_b_active = 1'b1;
      guard = 0;
      do begin
        @(posedge ACLK);
        `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_write_incr BVALID")
      end while (!BVALID);
      resp = axi_resp_code(BRESP);
      if (BRESP == 2'b10)
        had_slverr = 1'b1;
      if (BRESP == 2'b11)
        had_decerr = 1'b1;
      @(posedge ACLK);
      smoke_b_active = 1'b0;
      axi_idle();
    end
  endtask

  // AXI3 lock / exclusive read smoke — ARLOCK driven per request
  task bus_read_locked;
    input  [31:0] addr;
    input  [2:0]  size;
    input         lock_val;
    output [31:0] data;
    output [1:0]  resp;
    integer       guard;
    begin
      data = 32'h0;
      resp = `VERIF_BUS_RESP_SOFT;
      axi_idle();
      @(posedge ACLK);
      ARID = {ID_WIDTH{1'b0}};
      ARADDR = addr;
      ARLEN = 8'd0;
      ARSIZE = axsize_for_bytes(size);
      ARBURST = BURST_INCR;
      ARPROT = 3'b010;
      ARLOCK = lock_val;
      ARQOS = 4'd0;
      ARREGION = 4'd0;
      ARVALID = 1'b1;
      guard = 0;
      do begin
        @(posedge ACLK);
        `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_read_locked ARREADY")
      end while (!ARREADY);
      ARVALID = 1'b0;
      ARLOCK = 1'b0;
      smoke_r_active = 1'b1;
      guard = 0;
      do begin
        @(posedge ACLK);
        `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_read_locked RVALID")
      end while (!(RVALID && RREADY));
      data = RDATA;
      resp = axi_resp_code(RRESP);
      @(posedge ACLK);
      smoke_r_active = 1'b0;
      axi_idle();
    end
  endtask

endmodule