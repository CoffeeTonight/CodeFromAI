// Minimal SoC — SFR + SRAM behavioral model for harness PoC

`timescale 1ns/1ps

module periph_soc (
  input  wire        clk,
  input  wire        rst_n,
  input  wire        bus_valid,
  input  wire        bus_wr,
  input  wire [31:0] bus_addr,
  input  wire [31:0] bus_wdata,
  output reg  [31:0] bus_rdata,
  output reg         bus_ready
);

  localparam SFR_BASE  = 32'h4000_0000;
  localparam SFR_SIZE  = 32'h0000_0100;
  localparam SRAM_BASE = 32'h8000_0000;
  localparam SRAM_SIZE = 32'h0001_0000;

  reg [31:0] sfr_ctrl;
  reg [31:0] sfr_cfg;
  reg [31:0] sfr_status;
  reg [31:0] sram_mem [0:1023];

  integer i;
  initial begin
    sfr_ctrl   = 32'h0000_0001;
    sfr_cfg    = 32'h0000_00FF;
    sfr_status = 32'h0;
    sram_mem[0] = 32'hDEAD_BEEF;
    sram_mem[1] = 32'hCAFE_BABE;
    for (i = 2; i < 1024; i = i + 1)
      sram_mem[i] = 32'h0;
  end

  function in_region;
    input [31:0] addr;
    input [31:0] base;
    input [31:0] size;
    begin
      in_region = (addr >= base) && (addr < base + size);
    end
  endfunction

  always @(posedge clk) begin
    bus_ready <= 1'b0;
    bus_rdata <= 32'h0;
    if (!rst_n) begin
      sfr_ctrl   <= 32'h0000_0001;
      sfr_cfg    <= 32'h0000_00FF;
    end else if (bus_valid) begin
      bus_ready <= 1'b1;
      if (in_region(bus_addr, SFR_BASE, SFR_SIZE)) begin
        case (bus_addr - SFR_BASE)
          32'h00: begin
            if (bus_wr) sfr_ctrl <= bus_wdata;
            else bus_rdata <= sfr_ctrl;
          end
          32'h04: begin
            if (bus_wr) sfr_cfg <= bus_wdata;
            else bus_rdata <= sfr_cfg;
          end
          32'h08: begin
            if (bus_wr) sfr_status <= bus_wdata;
            else bus_rdata <= sfr_status;
          end
          default: bus_rdata <= 32'h0;
        endcase
      end else if (in_region(bus_addr, SRAM_BASE, SRAM_SIZE)) begin
        if (bus_wr)
          sram_mem[(bus_addr - SRAM_BASE) >> 2] <= bus_wdata;
        else
          bus_rdata <= sram_mem[(bus_addr - SRAM_BASE) >> 2];
      end else begin
        bus_rdata <= 32'hBADD_CAFE;
      end
    end
  end

endmodule