// Behavioral AHB full master — single-beat INCR + optional multiple outstanding (FIFO order)
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_lane_helpers.vh"

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


  localparam int STRB_WIDTH = DATA_WIDTH / 8;
  `VERIF_BUS_LANE_FUNCS(DATA_WIDTH)
  localparam HTRANS_IDLE   = 2'b00;
  localparam HTRANS_NONSEQ = 2'b10;
  localparam HBURST_INCR   = 3'b001;

  // Unified outstanding slots — AHB has no IDs; responses in strict FIFO issue order
  reg        slot_busy    [0:MAX_OUTSTANDING-1];
  reg        slot_pending [0:MAX_OUTSTANDING-1];
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
  reg [31:0] cap_slot_reg;
  reg        cap_valid;

  function [2:0] hsize_for_bytes;
    input [2:0] sz;
    begin
      case (sz)
        3'd1: hsize_for_bytes = 3'b000;
        3'd2: hsize_for_bytes = 3'b001;
        default: hsize_for_bytes = 3'b010;
      endcase
    end
  endfunction

  function integer os_r_inflight;
    integer n;
    integer i;
    begin
      n = 0;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (slot_busy[i] && !slot_done[i] && !slot_is_wr[i])
          n = n + 1;
      os_r_inflight = n;
    end
  endfunction

  function integer os_w_inflight;
    integer n;
    integer i;
    begin
      n = 0;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (slot_busy[i] && !slot_done[i] && slot_is_wr[i])
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

  function integer fifo_head;
    integer i;
    begin
      fifo_head = -1;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (slot_pending[i] && slot_order[i] == complete_order) begin
          fifo_head = i;
          i = MAX_OUTSTANDING;
        end
    end
  endfunction

  task os_reset_slots;
    integer i;
    begin
      complete_order = 0;
      issue_next = 0;
      cap_valid = 1'b0;
      cap_slot_reg = 0;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1) begin
        slot_busy[i] = 1'b0;
        slot_pending[i] = 1'b0;
        slot_done[i] = 1'b0;
        slot_is_wr[i] = 1'b0;
      end
    end
  endtask

  task hready_finish_slot;
    input integer cap;
    begin
      if (!slot_is_wr[cap])
        slot_rdata[cap] = lane_prdata(HRDATA, slot_addr[cap], slot_size[cap]);
      slot_resp[cap] = (HRESP != 2'b00) ? 2'd2 : 2'd0;
      slot_done[cap] = 1'b1;
      slot_busy[cap] = 1'b0;
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
    os_reset_slots();
  end

  // HREADY capture — FIFO bookkeeping on posedge; data sampled after NBA (#1 in issue)
  always @(posedge HCLK or negedge HRESETn) begin
    integer slot;
    if (!HRESETn) begin
      cap_valid <= 1'b0;
      os_reset_slots();
    end else if (HREADY && HTRANS == HTRANS_NONSEQ) begin
      slot = fifo_head();
      if (slot >= 0) begin
        cap_slot_reg <= slot;
        cap_valid <= 1'b1;
        slot_pending[slot] <= 1'b0;
        complete_order <= complete_order + 1;
      end
    end
  end

  task ahb_idle;
    begin
      HTRANS = HTRANS_IDLE;
      HWRITE = 1'b0;
      HWDATA = 32'h0;
      HEXCL = 1'b0;
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

  task ahb_xfer_issue;
    input        is_wr;
    input [31:0] addr;
    input [31:0] wdata;
    input [2:0]  size;
    output integer handle;
    output        ok;
    integer guard;
    begin
      handle = alloc_slot();
      ok = (handle >= 0);
      if (!ok) begin
        $display("[ahb_os] xfer_issue: outstanding full (MAX=%0d)", MAX_OUTSTANDING);
      end else begin
        slot_busy[handle] = 1'b1;
        slot_pending[handle] = 1'b0;
        slot_done[handle] = 1'b0;
        slot_is_wr[handle] = is_wr;
        slot_addr[handle] = addr;
        slot_wdata[handle] = wdata;
        slot_size[handle] = size;
        slot_order[handle] = issue_next;
        issue_next = issue_next + 1;
        ahb_idle();
        @(posedge HCLK);
        ahb_drive_common(addr, size);
        HWRITE = is_wr;
        HWDATA = is_wr ? lane_pwdata(wdata, addr, size) : 32'h0;
        HTRANS = HTRANS_NONSEQ;
        slot_pending[handle] = 1'b1;
        @(posedge HCLK);
        guard = 0;
        do begin
          @(posedge HCLK);
          `VERIF_BUS_WAIT_TICK(guard, "ahb_full bus_xfer_issue HREADY")
        end while (!HREADY);
        #1;
        hready_finish_slot(handle);
        cap_valid = 1'b0;
        ahb_idle();
      end
    end
  endtask

  // --- Outstanding read API ---
  task bus_read_issue;
    input  [31:0] addr;
    input  [2:0]  size;
    output integer handle;
    output        ok;
    begin
      ahb_xfer_issue(1'b0, addr, 32'h0, size, handle, ok);
      if (!ok)
        $display("[ahb_os] bus_read_issue: outstanding full (MAX=%0d)", MAX_OUTSTANDING);
    end
  endtask

  task bus_read_poll;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    output        done;
    begin
      done = slot_done[handle];
      data = slot_rdata[handle];
      resp = slot_resp[handle];
    end
  endtask

  task bus_read_wait;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    integer guard;
    begin
      guard = 0;
      while (!slot_done[handle]) begin
        @(posedge HCLK);
        `VERIF_BUS_WAIT_TICK(guard, "ahb_full bus_read_wait")
      end
      data = slot_rdata[handle];
      resp = slot_resp[handle];
      slot_busy[handle] = 1'b0;
      slot_pending[handle] = 1'b0;
      slot_done[handle] = 1'b0;
      snoop_valid = 1'b1;
      snoop_wr = 1'b0;
      snoop_addr = slot_addr[handle];
      snoop_data = data;
      @(posedge HCLK);
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
    begin
      ahb_xfer_issue(1'b1, addr, data, size, handle, ok);
      if (!ok)
        $display("[ahb_os] bus_write_issue: outstanding full (MAX=%0d)", MAX_OUTSTANDING);
    end
  endtask

  task bus_write_poll;
    input  integer handle;
    output [1:0] resp;
    output       done;
    begin
      done = slot_done[handle];
      resp = slot_resp[handle];
    end
  endtask

  task bus_write_wait;
    input  integer handle;
    output [1:0] resp;
    integer guard;
    begin
      guard = 0;
      while (!slot_done[handle]) begin
        @(posedge HCLK);
        `VERIF_BUS_WAIT_TICK(guard, "ahb_full bus_write_wait")
      end
      resp = slot_resp[handle];
      slot_busy[handle] = 1'b0;
      slot_pending[handle] = 1'b0;
      slot_done[handle] = 1'b0;
      snoop_valid = 1'b1;
      snoop_wr = 1'b1;
      snoop_addr = slot_addr[handle];
      snoop_data = slot_wdata[handle];
      @(posedge HCLK);
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