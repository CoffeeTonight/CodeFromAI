// Behavioral APB3 master — task API for VerifCPU bus_read/bus_write adapters
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_lane_helpers.vh"

module verif_apb_master (
  input         PCLK,
  input         PRESETn,
  output reg [31:0] PADDR,
  output reg        PSEL,
  output reg        PENABLE,
  output reg        PWRITE,
  output reg [31:0] PWDATA,
  output reg [3:0]  PSTRB,
  input  [31:0] PRDATA,
  input         PREADY,
  input         PSLVERR,
  output reg        snoop_valid,
  output reg        snoop_wr,
  output reg [31:0] snoop_addr,
  output reg [31:0] snoop_data
);

  initial begin
    PADDR = 32'h0;
    PSEL = 1'b0;
    PENABLE = 1'b0;
    PWRITE = 1'b0;
    PWDATA = 32'h0;
    PSTRB = 4'h0;
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
      PSTRB = 4'h0;
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
      PSTRB = 4'h0;
      PSEL = 1'b1;
      PENABLE = 1'b0;
      @(posedge PCLK);
      PENABLE = 1'b1;
      @(posedge PCLK);
      guard = 0;
      while (!PREADY) begin
        @(posedge PCLK);
        guard = guard + 1;
        if (guard > 64) begin
          resp = 2'd2;
          apb_idle();
          disable apb_read;
        end
      end
      #1;
      data = lane_prdata(PRDATA, addr, size);
      resp = PSLVERR ? 2'd2 : 2'd0;
      snoop_valid = 1'b1;
      snoop_wr = 1'b0;
      snoop_addr = addr;
      snoop_data = data;
      @(posedge PCLK);
      snoop_valid = 1'b0;
      apb_idle();
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
      @(posedge PCLK);
      guard = 0;
      while (!PREADY) begin
        @(posedge PCLK);
        guard = guard + 1;
        if (guard > 64) begin
          resp = 2'd2;
          apb_idle();
          disable apb_write;
        end
      end
      #1;
      resp = PSLVERR ? 2'd2 : 2'd0;
      snoop_valid = 1'b1;
      snoop_wr = 1'b1;
      snoop_addr = addr;
      snoop_data = data;
      @(posedge PCLK);
      snoop_valid = 1'b0;
      apb_idle();
    end
  endtask

  // VerifCPU adapter API (matches verif_soc_bus task names)
  task bus_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    begin
      apb_read(addr, size, data, resp);
    end
  endtask

  task bus_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    begin
      apb_write(addr, data, size, resp);
    end
  endtask

endmodule