// Behavioral AXI4-Lite master — single-beat + 1 outstanding read + 1 outstanding write
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_lane_helpers.vh"
`include "verif_bus_size_helpers.vh"

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


  // tool: cap_multi_os=1 cap_split_rw=1 (single outstanding R and W)
  localparam int STRB_WIDTH = DATA_WIDTH / 8;
  `VERIF_BUS_LANE_FUNCS(DATA_WIDTH)
  `VERIF_BUS_SIZE_FUNCS_COMPAT

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
      r_flush = 1'b0;
      r_hold_ready = 1'b0;
      ARVALID = 1'b0;
      AWVALID = 1'b0;
      WVALID  = 1'b0;
      BREADY  = 1'b0;
    end else begin
      if (r_hold_ready && !RVALID)
        r_hold_ready = 1'b0;
      else if (RVALID && RREADY) begin
        if (r_slot_busy && r_slot_ar_done && !r_slot_done) begin
          r_slot_data = lane_prdata(RDATA, r_slot_addr, r_slot_size);
          case (RRESP)
            2'b00, 2'b01: r_slot_resp = 2'd0;
            2'b10:        r_slot_resp = 2'd2;
            default:      r_slot_resp = 2'd3;  // DECERR
          endcase
          r_slot_done = 1'b1;
          r_slot_ar_done = 1'b0;
          r_hold_ready = 1'b1;
        end
      end
    end
  end

  // B channel — only complete when a write slot is waiting
  always @(posedge ACLK or negedge ARESETn) begin
    if (!ARESETn) begin
      BREADY <= 1'b0;
    end else begin
      BREADY <= (w_slot_busy && !w_slot_done);
      if (BVALID && BREADY && w_slot_busy && !w_slot_done) begin
        case (BRESP)
          2'b00, 2'b01: w_slot_resp <= 2'd0;
          2'b10:        w_slot_resp <= 2'd2;
          default:      w_slot_resp <= 2'd3;
        endcase
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
      r_hold_ready = 1'b0;
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
      if (!`VERIF_BUS_SIZE_OK(size) || `VERIF_BUS_OS_UNALIGNED(addr, size)) begin
        handle = -1;
        ok = 1'b0;
        $display("[axi_lite_os] bus_read_issue: bad size/align size=%0d @0x%08h", size, addr);
      end else begin
      if (r_slot_busy) begin
        handle = -1;
        ok = 1'b0;
        $display("[axi_lite_os] bus_read_issue: outstanding read slot busy (MAX=%0d)", MAX_OUTSTANDING);
      end else begin
        handle = 0;
        ok = 1'b1;
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
    end
  endtask

  task bus_read_poll;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    output        done;
    begin
      if (handle != 0 || !r_slot_busy) begin
        done = 1'b0;
        data = 32'h0;
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        done = r_slot_done;
        data = r_slot_data;
        resp = r_slot_resp;
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
      if (handle != 0 || !r_slot_busy) begin
        data = 32'hDEADDEAD;
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        guard = 0;
        abort = 1'b0;
        while (!r_slot_done && !abort) begin
          @(posedge ACLK);
          `VERIF_BUS_OS_WAIT_OR_RST(guard, "axi_lite bus_read_wait",
                                   ARESETn, r_slot_busy, abort)
        end
        if (abort || !r_slot_done) begin
          data = 32'hDEADDEAD;
          resp = `VERIF_BUS_RESP_SOFT;
          r_slot_ar_done = 1'b0;
          r_slot_done = 1'b0;
          r_slot_busy = 1'b0;
          r_hold_ready = 1'b0;
        end else begin
          data = r_slot_data;
          resp = r_slot_resp;
          r_slot_ar_done = 1'b0;
          r_slot_done = 1'b0;
          r_slot_busy = 1'b0;
          axi_drain_r_channel();
          r_hold_ready = 1'b0;
          snoop_valid = 1'b1;
          snoop_wr = 1'b0;
          snoop_addr = r_slot_addr;
          snoop_data = data;
          @(posedge ACLK);
          snoop_valid = 1'b0;
        end
      end
    end
  endtask

  task bus_read_outstanding_count;
    output integer n;
    begin
      n = r_slot_busy ? 1 : 0;
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
      if (!`VERIF_BUS_SIZE_OK(size) || `VERIF_BUS_OS_UNALIGNED(addr, size)) begin
        handle = -1;
        ok = 1'b0;
        $display("[axi_lite_os] bus_write_issue: bad size/align size=%0d @0x%08h", size, addr);
      end else begin
      if (w_slot_busy) begin
        handle = -1;
        ok = 1'b0;
        $display("[axi_lite_os] bus_write_issue: outstanding write slot busy (MAX=%0d)", MAX_OUTSTANDING);
      end else begin
        handle = 0;
        ok = 1'b1;
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
        begin : _aw_w_hs
          reg aw_done, w_done;
          aw_done = 1'b0;
          w_done = 1'b0;
          guard = 0;
          while (!aw_done || !w_done) begin
            @(posedge ACLK);
            `VERIF_BUS_WAIT_TICK(guard, "axi_lite bus_write_issue AW/W")
            if (!aw_done && AWVALID && AWREADY) begin
              AWVALID = 1'b0;
              aw_done = 1'b1;
            end
            if (!w_done && WVALID && WREADY) begin
              WVALID = 1'b0;
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
      if (handle != 0 || !w_slot_busy) begin
        done = 1'b0;
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        done = w_slot_done;
        resp = w_slot_resp;
      end
    end
  endtask

  task bus_write_wait;
    input  integer handle;
    output [1:0] resp;
    integer guard;
    reg abort;
    begin
      if (handle != 0 || !w_slot_busy) begin
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        guard = 0;
        abort = 1'b0;
        while (!w_slot_done && !abort) begin
          @(posedge ACLK);
          `VERIF_BUS_OS_WAIT_OR_RST(guard, "axi_lite bus_write_wait",
                                   ARESETn, w_slot_busy, abort)
        end
        if (abort || !w_slot_done) begin
          resp = `VERIF_BUS_RESP_SOFT;
          w_slot_busy = 1'b0;
          w_slot_done = 1'b0;
        end else begin
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
      end
    end
  endtask

  task bus_write_outstanding_count;
    output integer n;
    begin
      n = w_slot_busy ? 1 : 0;
    end
  endtask

  // Blocking single-beat + split half across word
  // Blocking 1beat: never steal/reap an outstanding OS slot (CPU owns open handles)
  task bus_read_1beat;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    integer h;
    reg ok;
    begin
      if (r_slot_busy) begin
        data = 32'h0;
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        axi_idle();
        axi_drain_r_channel();
        @(posedge ACLK);
        bus_read_issue(addr, size, h, ok);
        if (!ok) begin
          data = 32'h0;
          resp = `VERIF_BUS_RESP_SOFT;
        end else
          bus_read_wait(h, data, resp);
      end
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
      if (w_slot_busy) begin
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        bus_write_issue(addr, data, size, h, ok);
        if (!ok)
          resp = `VERIF_BUS_RESP_SOFT;
        else
          bus_write_wait(h, resp);
      end
    end
  endtask

  `include "verif_bus_split_rw.vh"
  `VERIF_BUS_DEFINE_SPLIT_RW(bus_read_1beat, bus_write_1beat)

endmodule