// Behavioral APB2 master — optional PREADY stretch with timeout guard
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_lane_helpers.vh"

module verif_apb2_master #(
  parameter int ADDR_WIDTH = 32,
  parameter int DATA_WIDTH = 32
)(
  input         PCLK,
  input         PRESETn,
  output reg [ADDR_WIDTH-1:0] PADDR,
  output reg        PSEL,
  output reg        PENABLE,
  output reg        PWRITE,
  output reg [DATA_WIDTH-1:0] PWDATA,
  input  [DATA_WIDTH-1:0] PRDATA,
  input         PREADY,
  output reg        snoop_valid,
  output reg        snoop_wr,
  output reg [31:0] snoop_addr,
  output reg [31:0] snoop_data
);

  // tool: cap_blocking_os=1 cap_split_rw=1 cap_multi_os=0
  localparam int STRB_WIDTH = DATA_WIDTH / 8;
  `VERIF_BUS_LANE_FUNCS(DATA_WIDTH)
  initial begin
    PADDR = 32'h0;
    PSEL = 1'b0;
    PENABLE = 1'b0;
    PWRITE = 1'b0;
    PWDATA = 32'h0;
    snoop_valid = 1'b0;
    snoop_wr = 1'b0;
    snoop_addr = 32'h0;
    snoop_data = 32'h0;
  end

  task apb_idle;
    begin
      PSEL = 1'b0;
      PENABLE = 1'b0;
      PWRITE = 1'b0;
      PWDATA = 32'h0;
    end
  endtask

  task apb_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    integer guard;
    begin
      resp = 2'd0;
      data = 32'h0;
      apb_idle();
      @(posedge PCLK);
      PADDR = addr;
      PWRITE = 1'b0;
      PWDATA = 32'h0;
      PSEL = 1'b1;
      PENABLE = 1'b0;
      @(posedge PCLK);
      PENABLE = 1'b1;
      guard = 0;
      do begin
        @(posedge PCLK);
        `VERIF_BUS_WAIT_TICK(guard, "apb2 bus_read PREADY")
      end while (!PREADY);
      #1;
      data = lane_prdata(PRDATA, addr, size);
      apb_idle();
      snoop_valid = 1'b1;
      snoop_wr = 1'b0;
      snoop_addr = addr;
      snoop_data = data;
      @(posedge PCLK);
      snoop_valid = 1'b0;
    end
  endtask

  // APB2 has no PSTRB — narrow stores are RMW so slave full-word write is safe
  task apb_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    integer guard;
    reg [31:0] oldw;
    reg [31:0] merged;
    reg [31:0] waddr;
    reg [1:0]  rtmp;
    begin
      resp = 2'd0;
      waddr = {addr[31:2], 2'b00};
      if (size == 3'd4 && addr[1:0] == 2'b00)
        merged = data;
      else begin
        apb_read(waddr, 3'd4, oldw, rtmp);
        if (rtmp != 2'd0) begin
          resp = rtmp;
        end else begin
          merged = oldw;
          case (size)
            3'd1: begin
              case (addr[1:0])
                2'd0: merged[7:0]   = data[7:0];
                2'd1: merged[15:8]  = data[7:0];
                2'd2: merged[23:16] = data[7:0];
                default: merged[31:24] = data[7:0];
              endcase
            end
            3'd2: begin
              if (addr[1:0] == 2'd0)
                merged[15:0] = data[15:0];
              else if (addr[1:0] == 2'd2)
                merged[31:16] = data[15:0];
              else if (addr[1:0] == 2'd1) begin
                merged[15:8] = data[7:0];
                merged[23:16] = data[15:8];
              end else begin
                // half @ +3: low byte this word, high byte next word
                merged[31:24] = data[7:0];
              end
            end
            default: merged = data;
          endcase
        end
      end
      if (resp == 2'd0) begin
        apb_idle();
        @(posedge PCLK);
        PADDR = waddr;
        PWRITE = 1'b1;
        PWDATA = merged;
        PSEL = 1'b1;
        PENABLE = 1'b0;
        @(posedge PCLK);
        PENABLE = 1'b1;
        guard = 0;
        do begin
          @(posedge PCLK);
          `VERIF_BUS_WAIT_TICK(guard, "apb2 bus_write PREADY")
        end while (!PREADY);
        #1;
        apb_idle();
        // half @ +3: also RMW next word for data[15:8]
        if (size == 3'd2 && addr[1:0] == 2'd3) begin
          apb_read(waddr + 32'd4, 3'd4, oldw, rtmp);
          if (rtmp == 2'd0) begin
            merged = oldw;
            merged[7:0] = data[15:8];
            @(posedge PCLK);
            PADDR = waddr + 32'd4;
            PWRITE = 1'b1;
            PWDATA = merged;
            PSEL = 1'b1;
            PENABLE = 1'b0;
            @(posedge PCLK);
            PENABLE = 1'b1;
            guard = 0;
            do begin
              @(posedge PCLK);
              `VERIF_BUS_WAIT_TICK(guard, "apb2 bus_write next-word PREADY")
            end while (!PREADY);
            #1;
            apb_idle();
          end else
            resp = rtmp;
        end
        snoop_valid = 1'b1;
        snoop_wr = 1'b1;
        snoop_addr = addr;
        snoop_data = data;
        @(posedge PCLK);
        snoop_valid = 1'b0;
      end
    end
  endtask

  `include "verif_bus_split_rw.vh"
  `VERIF_BUS_DEFINE_SPLIT_RW(apb_read, apb_write)

  `include "verif_bus_os_blocking_tasks.vh"
  `VERIF_BUS_OS_BLOCKING_IMPL

  always @(negedge PRESETn) begin
    bus_reset();
    apb_idle();
  end

endmodule