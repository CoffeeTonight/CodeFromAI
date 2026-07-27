// Behavioral APB3 master — task API for VerifCPU bus_read/bus_write adapters
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_lane_helpers.vh"

module verif_apb_master #(
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
  output reg [DATA_WIDTH/8-1:0] PSTRB,
  input  [DATA_WIDTH-1:0] PRDATA,
  input         PREADY,
  input         PSLVERR,
  output reg        snoop_valid,
  output reg        snoop_wr,
  output reg [31:0] snoop_addr,
  output reg [31:0] snoop_data
);


  localparam int STRB_WIDTH = DATA_WIDTH / 8;
  `VERIF_BUS_LANE_FUNCS(DATA_WIDTH)
  initial begin
    PADDR = 32'h0;
    PSEL = 1'b0;
    PENABLE = 1'b0;
    PWRITE = 1'b0;
    PWDATA = 32'h0;
    PSTRB = {STRB_WIDTH{1'b0}};
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
      PSTRB = {STRB_WIDTH{1'b0}};
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
      PSTRB = {STRB_WIDTH{1'b0}};
      PSEL = 1'b1;
      PENABLE = 1'b0;
      @(posedge PCLK);
      PENABLE = 1'b1;
      guard = 0;
      do begin
        @(posedge PCLK);
        `VERIF_BUS_WAIT_TICK(guard, "apb3 bus_read PREADY")
      end while (!PREADY);
      #1;
      data = lane_prdata(PRDATA, addr, size);
      resp = PSLVERR ? 2'd2 : 2'd0;
      apb_idle();  // drop PSEL/PENABLE before snoop wait (avoid double ACCESS)
      snoop_valid = 1'b1;
      snoop_wr = 1'b0;
      snoop_addr = addr;
      snoop_data = data;
      @(posedge PCLK);
      snoop_valid = 1'b0;
    end
  endtask

  task apb_write;
    input [31:0] addr;
    input [31:0] data;
    input [2:0]  size;
    output [1:0] resp;
    integer guard;
    begin
      resp = 2'd0;
      apb_idle();
      @(posedge PCLK);
      PADDR = addr;
      PWRITE = 1'b1;
      PWDATA = lane_pwdata(data, addr, size);
      PSTRB = lane_wstrb(addr, size);
      PSEL = 1'b1;
      PENABLE = 1'b0;
      @(posedge PCLK);
      PENABLE = 1'b1;
      guard = 0;
      do begin
        @(posedge PCLK);
        `VERIF_BUS_WAIT_TICK(guard, "apb3 bus_write PREADY")
      end while (!PREADY);
      #1;
      resp = PSLVERR ? 2'd2 : 2'd0;
      apb_idle();
      snoop_valid = 1'b1;
      snoop_wr = 1'b1;
      snoop_addr = addr;
      snoop_data = data;
      @(posedge PCLK);
      snoop_valid = 1'b0;
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