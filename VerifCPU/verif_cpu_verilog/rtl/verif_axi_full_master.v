// Behavioral AXI3/4/5 full master — single-beat INCR + optional multiple outstanding
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_lane_helpers.vh"

module verif_axi_full_master #(
  parameter int ADDR_WIDTH = 32,
  parameter int DATA_WIDTH = 32,
  parameter int AXI_PROT = 4,
  parameter int ID_WIDTH = 4,
  parameter int MAX_OUTSTANDING = 4
)(
  input         ACLK,
  input         ARESETn,
  output reg [ID_WIDTH-1:0] ARID,
  output reg [ADDR_WIDTH-1:0] ARADDR,
  output reg [7:0]  ARLEN,
  output reg [2:0]  ARSIZE,
  output reg [1:0]  ARBURST,
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
        if (r_slot_busy[i] && r_slot_ar_done[i] && !r_slot_done[i])
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
        if (r_slot_busy[i] && r_slot_ar_done[i] && !r_slot_done[i] && id == i) begin
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
        if (w_slot_busy[i] && !w_slot_done[i] && id == i) begin
          bid_to_slot = i;
          i = MAX_OUTSTANDING;
        end
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

  initial begin
    ARID = 0; ARADDR = 0; ARLEN = 0; ARSIZE = 3'b010; ARBURST = BURST_INCR;
    ARQOS = 0; ARREGION = 0; ARVALID = 0; RREADY = 0;
    AWID = 0; AWADDR = 0; AWLEN = 0; AWSIZE = 3'b010; AWBURST = BURST_INCR;
    AWQOS = 0; AWREGION = 0; AWATOP = 0; AWVALID = 0;
    WID = 0; WDATA = 0; WSTRB = 0; WLAST = 0; WVALID = 0; BREADY = 0;
    snoop_valid = 0; snoop_wr = 0; snoop_addr = 0; snoop_data = 0;
    os_reset_slots();
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
          r_slot_resp[slot] = (RRESP != 2'b00) ? 2'd2 : 2'd0;
          r_slot_done[slot] = 1'b1;
          r_slot_ar_done[slot] = 1'b0;
          r_slot_busy[slot] = 1'b0;
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
          w_slot_resp[slot] = (BRESP != 2'b00) ? 2'd2 : 2'd0;
          w_slot_done[slot] = 1'b1;
          w_slot_busy[slot] = 1'b0;
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
        ARID = handle;
        ARADDR = addr;
        ARLEN = 8'd0;
        ARSIZE = axsize_for_bytes(size);
        ARBURST = BURST_INCR;
        ARQOS = 4'd0;
        ARREGION = 4'd0;
        ARVALID = 1'b1;
        guard = 0;
        while (!ARREADY) begin
          @(posedge ACLK);
          guard = guard + 1;
          if (guard > 64) begin
            r_slot_busy[handle] = 1'b0;
            ok = 1'b0;
            axi_idle();
            disable bus_read_issue;
          end
        end
        ARVALID = 1'b0;
        @(posedge ACLK);
        r_slot_ar_done[handle] = 1'b1;
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
    begin
      while (!r_slot_done[handle])
        @(posedge ACLK);
      data = r_slot_data[handle];
      resp = r_slot_resp[handle];
      r_slot_busy[handle] = 1'b0;
      r_slot_ar_done[handle] = 1'b0;
      r_slot_done[handle] = 1'b0;
      snoop_valid = 1'b1;
      snoop_wr = 1'b0;
      snoop_addr = r_slot_addr[handle];
      snoop_data = data;
      @(posedge ACLK);
      snoop_valid = 1'b0;
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
        AWID = handle;
        AWADDR = addr;
        AWLEN = 8'd0;
        AWSIZE = axsize_for_bytes(size);
        AWBURST = BURST_INCR;
        AWQOS = 4'd0;
        AWREGION = 4'd0;
        AWATOP = 6'd0;
        AWVALID = 1'b1;
        WDATA = lane_pwdata(data, addr, size);
        WSTRB = lane_wstrb(addr, size);
        WLAST = 1'b1;
        WVALID = 1'b1;
        if (AXI_PROT == 3)
          WID = handle;
        guard = 0;
        while (!AWREADY) begin
          @(posedge ACLK);
          guard = guard + 1;
          if (guard > 64) begin
            w_slot_busy[handle] = 1'b0;
            ok = 1'b0;
            axi_idle();
            disable bus_write_issue;
          end
        end
        guard = 0;
        while (!WREADY) begin
          @(posedge ACLK);
          guard = guard + 1;
          if (guard > 64) begin
            w_slot_busy[handle] = 1'b0;
            ok = 1'b0;
            axi_idle();
            disable bus_write_issue;
          end
        end
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
    begin
      while (!w_slot_done[handle])
        @(posedge ACLK);
      resp = w_slot_resp[handle];
      w_slot_busy[handle] = 1'b0;
      w_slot_done[handle] = 1'b0;
      snoop_valid = 1'b1;
      snoop_wr = 1'b1;
      snoop_addr = w_slot_addr[handle];
      snoop_data = w_slot_data[handle];
      @(posedge ACLK);
      snoop_valid = 1'b0;
    end
  endtask

  task bus_write_outstanding_count;
    output integer n;
    begin n = os_w_inflight(); end
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

endmodule