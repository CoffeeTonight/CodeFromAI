// Behavioral AXI3/4/5 full master — single-beat INCR + optional multiple outstanding
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_lane_helpers.vh"

module verif_axi_full_master #(
  parameter int ADDR_WIDTH = 32,
  parameter int DATA_WIDTH = 32,
  parameter int AXI_PROT = 4,
  parameter int ID_WIDTH = 4,
  parameter int ID_BASE = 0,
  parameter int MAX_OUTSTANDING = 4
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

  localparam int STRB_WIDTH = DATA_WIDTH / 8;
  `VERIF_BUS_LANE_FUNCS(DATA_WIDTH)
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

  reg        w_slot_busy   [0:MAX_OUTSTANDING-1];
  reg        w_slot_done   [0:MAX_OUTSTANDING-1];
  reg [31:0] w_slot_addr   [0:MAX_OUTSTANDING-1];
  reg [31:0] w_slot_data   [0:MAX_OUTSTANDING-1];
  reg [1:0]  w_slot_resp   [0:MAX_OUTSTANDING-1];

  integer gi;

  function [2:0] axsize_for_bytes;
    input [2:0] sz;
    begin
      case (sz)
        3'd1: axsize_for_bytes = 3'b000;
        3'd2: axsize_for_bytes = 3'b001;
        default: axsize_for_bytes = 3'b010;
      endcase
    end
  endfunction

  function integer os_r_inflight;
    integer n;
    integer i;
    begin
      n = 0;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (r_slot_busy[i] && !r_slot_done[i])
          n = n + 1;
      os_r_inflight = n;
    end
  endfunction

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
        if (w_slot_busy[i] && !w_slot_done[i])
          n = n + 1;
      os_w_inflight = n;
    end
  endfunction

  function integer os_w_need_bready;
    integer n;
    integer i;
    begin
      n = 0;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (w_slot_busy[i])
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
        2'b10: axi_resp_code = 2'd2;
        2'b11: axi_resp_code = 2'd3;
        default: axi_resp_code = 2'd2;
      endcase
    end
  endfunction

  task os_reset_slots;
    integer i;
    begin
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1) begin
        r_slot_busy[i] = 1'b0;
        r_slot_ar_done[i] = 1'b0;
        r_slot_done[i] = 1'b0;
        w_slot_busy[i] = 1'b0;
        w_slot_done[i] = 1'b0;
      end
    end
  endtask

  reg        snoop_pending;
  reg        snoop_pending_wr;
  reg [31:0] snoop_pending_addr;
  reg [31:0] snoop_pending_data;

  initial begin
    ARID = 0; ARADDR = 0; ARLEN = 0; ARSIZE = 3'b010; ARBURST = BURST_INCR;
    ARPROT = 3'b010; ARLOCK = 1'b0; ARQOS = 0; ARREGION = 0; ARVALID = 0; RREADY = 0;
    AWID = 0; AWADDR = 0; AWLEN = 0; AWSIZE = 3'b010; AWBURST = BURST_INCR;
    AWPROT = 3'b010; AWLOCK = 1'b0; AWQOS = 0; AWREGION = 0; AWATOP = 0; AWVALID = 0;
    WID = 0; WDATA = 0; WSTRB = 0; WLAST = 0; WVALID = 0; BREADY = 0;
    snoop_valid = 0; snoop_wr = 0; snoop_addr = 0; snoop_data = 0;
    snoop_pending = 0;
    os_reset_slots();
  end

  // One-cycle snoop pulse (no #delay tasks inside clocked always)
  always @(posedge ACLK or negedge ARESETn) begin
    if (!ARESETn) begin
      snoop_valid <= 1'b0;
      snoop_wr    <= 1'b0;
      snoop_addr  <= 32'h0;
      snoop_data  <= 32'h0;
      snoop_pending <= 1'b0;
    end else if (snoop_pending) begin
      snoop_wr    <= snoop_pending_wr;
      snoop_addr  <= snoop_pending_addr;
      snoop_data  <= snoop_pending_data;
      snoop_valid <= 1'b1;
      snoop_pending <= 1'b0;
    end else begin
      snoop_valid <= 1'b0;
    end
  end

  // R channel — accept beats while reads are outstanding
  always @(posedge ACLK or negedge ARESETn) begin
    integer slot;
    if (!ARESETn) begin
      RREADY <= 1'b0;
    end else begin
      // Hold RREADY through RVALID until handshake completes (drains orphan/skid beats)
      RREADY <= (os_r_need_rready() > 0) || RVALID;
      if (RVALID && RREADY && RLAST) begin
        slot = rid_to_slot(RID);
        if (slot >= 0) begin
          r_slot_data[slot] = lane_prdata(RDATA, r_slot_addr[slot], r_slot_size[slot]);
          r_slot_resp[slot] = axi_resp_code(RRESP);
          r_slot_done[slot] = 1'b1;
          r_slot_ar_done[slot] = 1'b0;
          r_slot_busy[slot] = 1'b0;
          snoop_pending_wr   <= 1'b0;
          snoop_pending_addr <= r_slot_addr[slot];
          snoop_pending_data <= r_slot_data[slot];
          snoop_pending    <= 1'b1;
        end
      end
    end
  end

  // B channel — accept write responses while outstanding
  always @(posedge ACLK or negedge ARESETn) begin
    integer slot;
    if (!ARESETn) begin
      BREADY <= 1'b0;
    end else begin
      BREADY <= (os_w_need_bready() > 0) || BVALID;
      if (BVALID && BREADY) begin
        slot = bid_to_slot(BID);
        if (slot >= 0) begin
          w_slot_resp[slot] = axi_resp_code(BRESP);
          w_slot_done[slot] = 1'b1;
          w_slot_busy[slot] = 1'b0;
          snoop_pending_wr   <= 1'b1;
          snoop_pending_addr <= w_slot_addr[slot];
          snoop_pending_data <= w_slot_data[slot];
          snoop_pending    <= 1'b1;
        end
      end
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
      handle = alloc_r_slot();
      ok = (handle >= 0);
      if (!ok) begin
        $display("[axi_os] bus_read_issue: outstanding full (MAX=%0d)", MAX_OUTSTANDING);
      end else begin
        r_slot_busy[handle] = 1'b1;
        r_slot_ar_done[handle] = 1'b0;
        r_slot_done[handle] = 1'b0;
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
  endtask

  task bus_read_poll;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    output        done;
    begin
      done = r_slot_done[handle];
      data = r_slot_data[handle];
      resp = r_slot_resp[handle];
    end
  endtask

  task bus_read_wait;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    integer guard;
    begin
      guard = 0;
      while (!r_slot_done[handle]) begin
        @(posedge ACLK);
        `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_read_wait")
      end
      data = r_slot_data[handle];
      resp = r_slot_resp[handle];
      r_slot_busy[handle] = 1'b0;
      r_slot_ar_done[handle] = 1'b0;
      r_slot_done[handle] = 1'b0;
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
        guard = 0;
        do begin
          @(posedge ACLK);
          `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_write_issue AWREADY")
        end while (!AWREADY);
        guard = 0;
        do begin
          @(posedge ACLK);
          `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_write_issue WREADY")
        end while (!WREADY);
        AWVALID = 1'b0;
        WVALID = 1'b0;
        WLAST = 1'b0;
        @(posedge ACLK);
      end
    end
  endtask

  task bus_write_poll;
    input  integer handle;
    output [1:0] resp;
    output       done;
    begin
      done = w_slot_done[handle];
      resp = w_slot_resp[handle];
    end
  endtask

  task bus_write_wait;
    input  integer handle;
    output [1:0] resp;
    integer guard;
    begin
      guard = 0;
      while (!w_slot_done[handle]) begin
        @(posedge ACLK);
        `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_write_wait")
      end
      resp = w_slot_resp[handle];
      w_slot_busy[handle] = 1'b0;
      w_slot_done[handle] = 1'b0;
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
        guard = 0;
        do begin
          @(posedge ACLK);
          `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_read_incr RVALID")
        end while (!RVALID);
        resp = RRESP;
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
        @(posedge ACLK);
      end
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
      resp0 = 2'd2;
      resp1 = 2'd2;
      ok = 1'b0;
      bus_read_issue(addr0, size, h0, ok0);
      bus_read_issue(addr1, size, h1, ok1);
      ok = ok0 && ok1;
      if (ok) begin
        bus_read_wait(h0, data0, resp0);
        bus_read_wait(h1, data1, resp1);
      end
    end
  endtask

  // Blocking API — issue + wait (backward compatible)
  task bus_read;
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
        resp = 2'd2;
      end else
        bus_read_wait(h, data, resp);
    end
  endtask

  task bus_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    integer h;
    reg ok;
    begin
      bus_write_issue(addr, data, size, h, ok);
      if (!ok)
        resp = 2'd2;
      else
        bus_write_wait(h, resp);
    end
  endtask

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
      h = alloc_w_slot();
      ok = (h >= 0);
      resp = 2'd2;
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
        guard = 0;
        do begin
          @(posedge ACLK);
          `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_write_atop AWREADY")
        end while (!AWREADY);
        guard = 0;
        do begin
          @(posedge ACLK);
          `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_write_atop WREADY")
        end while (!WREADY);
        AWVALID = 1'b0;
        WVALID = 1'b0;
        WLAST = 1'b0;
        AWATOP = 6'd0;
        @(posedge ACLK);
        bus_write_wait(h, resp);
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
    begin
      resp = 2'd2;
      had_slverr = 1'b0;
      had_decerr = 1'b0;
      nbeats = awlen + 1;
      axi_idle();
      @(posedge ACLK);
      AWID = {ID_WIDTH{1'b0}};
      AWADDR = addr;
      AWLEN = awlen;
      AWSIZE = axsize_for_bytes(size);
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
        WDATA = lane_pwdata(wdata, addr + (beat * 4), size);
        WSTRB = lane_wstrb(addr + (beat * 4), size);
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
      BREADY = 1'b1;
      guard = 0;
      do begin
        @(posedge ACLK);
        `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_write_incr BVALID")
      end while (!BVALID);
      resp = BRESP;
      if (BRESP == 2'b10)
        had_slverr = 1'b1;
      if (BRESP == 2'b11)
        had_decerr = 1'b1;
      @(posedge ACLK);
      BREADY = 1'b0;
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
      resp = 2'd2;
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
      RREADY = 1'b1;
      guard = 0;
      do begin
        @(posedge ACLK);
        `VERIF_BUS_WAIT_TICK(guard, "axi_full bus_read_locked RVALID")
      end while (!RVALID);
      data = RDATA;
      resp = RRESP;
      @(posedge ACLK);
      RREADY = 1'b0;
      axi_idle();
    end
  endtask

endmodule