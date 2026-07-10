// Behavioral AXI4-Lite master — single-beat + 1 outstanding read + 1 outstanding write
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_lane_helpers.vh"

module verif_axi_lite_master #(
  parameter int ADDR_WIDTH = 32,
  parameter int DATA_WIDTH = 32,
  parameter int MAX_OUTSTANDING = 1
)(
  input         ACLK,
  input         ARESETn,
  output reg        ARVALID,
  input             ARREADY,
  output reg [ADDR_WIDTH-1:0] ARADDR,
  output reg [2:0]  ARSIZE,
  output reg [2:0]  ARPROT,
  input             RVALID,
  output reg        RREADY,
  input  [DATA_WIDTH-1:0] RDATA,
  input  [1:0]  RRESP,
  output reg        AWVALID,
  input             AWREADY,
  output reg [ADDR_WIDTH-1:0] AWADDR,
  output reg [2:0]  AWSIZE,
  output reg [2:0]  AWPROT,
  output reg        WVALID,
  input             WREADY,
  output reg [DATA_WIDTH-1:0] WDATA,
  output reg [DATA_WIDTH/8-1:0] WSTRB,
  input             BVALID,
  output reg        BREADY,
  input  [1:0]  BRESP,
  output reg        snoop_valid,
  output reg        snoop_wr,
  output reg [31:0] snoop_addr,
  output reg [31:0] snoop_data
);


  localparam int STRB_WIDTH = DATA_WIDTH / 8;
  `VERIF_BUS_LANE_FUNCS(DATA_WIDTH)

  // Lite has no IDs — one read slot and one write slot (may overlap)
  reg        r_slot_busy;
  reg        r_slot_ar_done;
  reg        r_slot_done;
  reg [31:0] r_slot_addr;
  reg [2:0]  r_slot_size;
  reg [31:0] r_slot_data;
  reg [1:0]  r_slot_resp;
  reg        r_flush;
  reg        r_hold_ready;

  reg        w_slot_busy;
  reg        w_slot_done;
  reg [31:0] w_slot_addr;
  reg [31:0] w_slot_data;
  reg [2:0]  w_slot_size;
  reg [1:0]  w_slot_resp;

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

  task os_reset_slots;
    begin
      r_slot_busy = 1'b0;
      r_slot_ar_done = 1'b0;
      r_slot_done = 1'b0;
      w_slot_busy = 1'b0;
      w_slot_done = 1'b0;
    end
  endtask

  initial begin
    ARVALID = 1'b0;
    ARADDR = 32'h0;
    ARSIZE = 3'b010;
    ARPROT = 3'b010;
    RREADY = 1'b0;
    AWVALID = 1'b0;
    AWADDR = 32'h0;
    AWSIZE = 3'b010;
    AWPROT = 3'b010;
    WVALID = 1'b0;
    WDATA = 32'h0;
    WSTRB = 4'h0;
    BREADY = 1'b0;
    snoop_valid = 1'b0;
    snoop_wr = 1'b0;
    snoop_addr = 32'h0;
    snoop_data = 32'h0;
    os_reset_slots();
  end

  // R channel — hold RREADY until RVALID falls after handshake
  always @(*) begin
    RREADY = r_hold_ready || r_flush
             || (r_slot_busy && r_slot_ar_done && !r_slot_done);
  end

  always @(posedge ACLK or negedge ARESETn) begin
    if (!ARESETn) begin
      os_reset_slots();
      r_flush <= 1'b0;
      r_hold_ready <= 1'b0;
    end else begin
      if (r_hold_ready && !RVALID)
        r_hold_ready <= 1'b0;
      else if (RVALID && RREADY) begin
        if (r_slot_busy && r_slot_ar_done && !r_slot_done) begin
          r_slot_data <= lane_prdata(RDATA, r_slot_addr, r_slot_size);
          r_slot_resp <= (RRESP != 2'b00) ? 2'd2 : 2'd0;
          r_slot_done <= 1'b1;
          r_slot_ar_done <= 1'b0;
          r_hold_ready <= 1'b1;
        end
      end
    end
  end

  // B channel — accept write response while outstanding
  always @(posedge ACLK or negedge ARESETn) begin
    if (!ARESETn) begin
      BREADY <= 1'b0;
    end else begin
      BREADY <= (w_slot_busy && !w_slot_done);
      if (BVALID && BREADY) begin
        w_slot_resp <= (BRESP != 2'b00) ? 2'd2 : 2'd0;
        w_slot_done <= 1'b1;
      end
    end
  end

  task axi_idle;
    begin
      ARVALID = 1'b0;
      AWVALID = 1'b0;
      WVALID  = 1'b0;
      WSTRB   = {STRB_WIDTH{1'b0}};
    end
  endtask

  task axi_drain_r_channel;
    integer guard;
    begin
      guard = 0;
      r_flush = 1'b1;
      while (RVALID && guard < 8) begin
        @(posedge ACLK);
        guard = guard + 1;
      end
      r_flush = 1'b0;
    end
  endtask

  // --- Outstanding read API (single slot, handle always 0) ---
  task bus_read_issue;
    input  [31:0] addr;
    input  [2:0]  size;
    output integer handle;
    output        ok;
    integer guard;
    begin
      handle = 0;
      ok = !r_slot_busy;
      if (!ok) begin
        $display("[axi_lite_os] bus_read_issue: outstanding read slot busy (MAX=%0d)", MAX_OUTSTANDING);
      end else begin
        r_slot_busy = 1'b1;
        r_slot_ar_done = 1'b0;
        r_slot_done = 1'b0;
        r_slot_addr = addr;
        r_slot_size = size;
        axi_idle();
        @(posedge ACLK);
        ARADDR = addr;
        ARSIZE = axsize_for_bytes(size);
        ARPROT = 3'b010;
        ARVALID = 1'b1;
        guard = 0;
        do begin
          @(posedge ACLK);
          `VERIF_BUS_WAIT_TICK(guard, "axi_lite bus_read_issue ARREADY")
        end while (!ARREADY);
        r_slot_ar_done = 1'b1;
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
      done = r_slot_done;
      data = r_slot_data;
      resp = r_slot_resp;
    end
  endtask

  task bus_read_wait;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    integer guard;
    begin
      guard = 0;
      while (!r_slot_done) begin
        @(posedge ACLK);
        `VERIF_BUS_WAIT_TICK(guard, "axi_lite bus_read_wait")
      end
      data = r_slot_data;
      resp = r_slot_resp;
      r_slot_ar_done = 1'b0;
      r_slot_done = 1'b0;
      r_slot_busy = 1'b0;
      axi_drain_r_channel();
      snoop_valid = 1'b1;
      snoop_wr = 1'b0;
      snoop_addr = r_slot_addr;
      snoop_data = data;
      @(posedge ACLK);
      snoop_valid = 1'b0;
    end
  endtask

  task bus_read_outstanding_count;
    output integer n;
    begin
      n = (r_slot_busy && !r_slot_done) ? 1 : 0;
    end
  endtask

  // --- Outstanding write API (single slot, handle always 0) ---
  task bus_write_issue;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output integer handle;
    output        ok;
    integer guard;
    begin
      handle = 0;
      ok = !w_slot_busy;
      if (!ok) begin
        $display("[axi_lite_os] bus_write_issue: outstanding write slot busy (MAX=%0d)", MAX_OUTSTANDING);
      end else begin
        w_slot_busy = 1'b1;
        w_slot_done = 1'b0;
        w_slot_addr = addr;
        w_slot_data = data;
        w_slot_size = size;
        axi_idle();
        @(posedge ACLK);
        AWADDR = addr;
        AWSIZE = axsize_for_bytes(size);
        AWPROT = 3'b010;
        AWVALID = 1'b1;
        WDATA = lane_pwdata(data, addr, size);
        WSTRB = lane_wstrb(addr, size);
        WVALID = 1'b1;
        guard = 0;
        do begin
          @(posedge ACLK);
          `VERIF_BUS_WAIT_TICK(guard, "axi_lite bus_write_issue AWREADY")
        end while (!AWREADY);
        guard = 0;
        do begin
          @(posedge ACLK);
          `VERIF_BUS_WAIT_TICK(guard, "axi_lite bus_write_issue WREADY")
        end while (!WREADY);
        AWVALID = 1'b0;
        WVALID = 1'b0;
        @(posedge ACLK);
      end
    end
  endtask

  task bus_write_poll;
    input  integer handle;
    output [1:0] resp;
    output       done;
    begin
      done = w_slot_done;
      resp = w_slot_resp;
    end
  endtask

  task bus_write_wait;
    input  integer handle;
    output [1:0] resp;
    integer guard;
    begin
      guard = 0;
      while (!w_slot_done) begin
        @(posedge ACLK);
        `VERIF_BUS_WAIT_TICK(guard, "axi_lite bus_write_wait")
      end
      resp = w_slot_resp;
      w_slot_busy = 1'b0;
      w_slot_done = 1'b0;
      snoop_valid = 1'b1;
      snoop_wr = 1'b1;
      snoop_addr = w_slot_addr;
      snoop_data = w_slot_data;
      @(posedge ACLK);
      snoop_valid = 1'b0;
    end
  endtask

  task bus_write_outstanding_count;
    output integer n;
    begin
      n = (w_slot_busy && !w_slot_done) ? 1 : 0;
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
    reg [31:0] drain_data;
    reg [1:0]  drain_resp;
    integer guard;
    begin
      guard = 0;
      while (r_slot_busy && guard < 256) begin
        if (r_slot_done)
          bus_read_wait(h, drain_data, drain_resp);
        else begin
          @(posedge ACLK);
          guard = guard + 1;
        end
      end
      if (r_slot_busy) begin
        if (r_slot_done)
          bus_read_wait(h, drain_data, drain_resp);
        else
          os_reset_slots();
      end
      axi_idle();
      axi_drain_r_channel();
      @(posedge ACLK);
      bus_read_issue(addr, size, h, ok);
      if (!ok) begin
        data = 32'h0;
        resp = 2'd2;
      end else begin
        bus_read_wait(h, data, resp);
      end
    end
  endtask

  task bus_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    integer h;
    reg ok;
    integer guard;
    begin
      guard = 0;
      while (w_slot_busy && guard < 256) begin
        if (w_slot_done) begin
          w_slot_busy = 1'b0;
          w_slot_done = 1'b0;
        end else begin
          @(posedge ACLK);
          guard = guard + 1;
        end
      end
      if (w_slot_busy)
        os_reset_slots();
      bus_write_issue(addr, data, size, h, ok);
      if (!ok)
        resp = 2'd2;
      else
        bus_write_wait(h, resp);
    end
  endtask

endmodule