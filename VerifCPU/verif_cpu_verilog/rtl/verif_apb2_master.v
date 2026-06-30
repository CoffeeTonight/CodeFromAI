// Behavioral APB2 master — fixed 2-cycle access, no PREADY/PSLVERR/PSTRB
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_lane_helpers.vh"

module verif_apb2_master (
  input         PCLK,
  input         PRESETn,
  output reg [31:0] PADDR,
  output reg        PSEL,
  output reg        PENABLE,
  output reg        PWRITE,
  output reg [31:0] PWDATA,
  input  [31:0] PRDATA,
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
    snoop_valid = 1'b0;
    snoop_wr = 1'b0;
    snoop_addr = 32'h0;
    snoop_data = 32'h0;
  end

  task apb_idle;
    begin
      PSEL = 1'b0;
      PENABLE = 1'b0;
    end
  endtask

  task apb_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    begin
      resp = 2'd0;
      data = 32'h0;
      @(posedge PCLK);
      PADDR = addr;
      PWRITE = 1'b0;
      PWDATA = 32'h0;
      PSEL = 1'b1;
      PENABLE = 1'b0;
      @(posedge PCLK);
      PENABLE = 1'b1;
      @(posedge PCLK);
      #1;
      data = lane_prdata(PRDATA, addr, size);
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
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    begin
      resp = 2'd0;
      @(posedge PCLK);
      PADDR = addr;
      PWRITE = 1'b1;
      PWDATA = lane_pwdata(data, addr, size);
      PSEL = 1'b1;
      PENABLE = 1'b0;
      @(posedge PCLK);
      PENABLE = 1'b1;
      @(posedge PCLK);
      snoop_valid = 1'b1;
      snoop_wr = 1'b1;
      snoop_addr = addr;
      snoop_data = data;
      @(posedge PCLK);
      snoop_valid = 1'b0;
      apb_idle();
    end
  endtask

  task bus_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    begin apb_read(addr, size, data, resp); end
  endtask

  task bus_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    begin apb_write(addr, data, size, resp); end
  endtask

endmodule