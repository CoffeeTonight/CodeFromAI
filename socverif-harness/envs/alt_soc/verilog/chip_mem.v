`timescale 1ns/1ps

module chip_mem (
  input  wire        clk,
  input  wire        rst_n,
  input  wire        req,
  input  wire        wen,
  input  wire [31:0] addr,
  input  wire [31:0] wdata,
  output reg  [31:0] rdata,
  output reg         ack
);

  localparam APB_BASE  = 32'h5000_0000;
  localparam SRAM_BASE = 32'h6000_0000;

  reg [31:0] reg_ctrl, reg_cfg, reg_stat;
  reg [31:0] sram [0:255];

  integer k;
  initial begin
    reg_ctrl = 32'h0000_00AB;
    reg_cfg  = 32'h0000_0055;
    reg_stat = 32'h0;
    sram[0]  = 32'h1234_5678;
    sram[1]  = 32'h8765_4321;
    for (k = 2; k < 256; k = k + 1) sram[k] = 0;
  end

  always @(posedge clk) begin
    ack <= 0;
    rdata <= 0;
    if (!rst_n) begin
      reg_ctrl <= 32'h0000_00AB;
      reg_cfg  <= 32'h0000_0055;
    end else if (req) begin
      ack <= 1;
      if (addr >= APB_BASE && addr < APB_BASE + 32'h100) begin
        case (addr - APB_BASE)
          32'h00: begin if (wen) reg_ctrl <= wdata; else rdata <= reg_ctrl; end
          32'h04: begin if (wen) reg_cfg  <= wdata; else rdata <= reg_cfg;  end
          32'h08: begin if (wen) reg_stat <= wdata; else rdata <= reg_stat; end
          default: rdata <= 0;
        endcase
      end else if (addr >= SRAM_BASE && addr < SRAM_BASE + 32'h400) begin
        if (wen) sram[(addr - SRAM_BASE) >> 2] <= wdata;
        else rdata <= sram[(addr - SRAM_BASE) >> 2];
      end else rdata <= 32'hEEEEEEEE;
    end
  end
endmodule