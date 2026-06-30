// Partial bus access helpers — byte/half lane placement for AMBA bridge masters
`ifndef VERIF_BUS_LANE_HELPERS_VH
`define VERIF_BUS_LANE_HELPERS_VH

function [31:0] lane_pwdata;
  input [31:0] data;
  input [31:0] addr;
  input [2:0]  size;
  begin
    case (size)
      3'd1: begin
        case (addr[1:0])
          2'd0: lane_pwdata = {24'h0, data[7:0]};
          2'd1: lane_pwdata = {16'h0, data[7:0], 8'h0};
          2'd2: lane_pwdata = {8'h0, data[7:0], 16'h0};
          default: lane_pwdata = {data[7:0], 24'h0};
        endcase
      end
      3'd2: lane_pwdata = addr[1] ? {16'h0, data[15:0]} : {data[15:0], 16'h0};
      default: lane_pwdata = data;
    endcase
  end
endfunction

function [31:0] lane_prdata;
  input [31:0] raw;
  input [31:0] addr;
  input [2:0]  size;
  begin
    case (size)
      3'd1: begin
        case (addr[1:0])
          2'd0: lane_prdata = {24'h0, raw[7:0]};
          2'd1: lane_prdata = {24'h0, raw[15:8]};
          2'd2: lane_prdata = {24'h0, raw[23:16]};
          default: lane_prdata = {24'h0, raw[31:24]};
        endcase
      end
      3'd2: lane_prdata = addr[1] ? {16'h0, raw[31:16]} : {16'h0, raw[15:0]};
      default: lane_prdata = raw;
    endcase
  end
endfunction

function [3:0] lane_wstrb;
  input [31:0] addr;
  input [2:0]  size;
  reg [3:0] base;
  begin
    case (size)
      3'd1: base = 4'b0001;
      3'd2: base = 4'b0011;
      default: base = 4'b1111;
    endcase
    lane_wstrb = base << addr[1:0];
  end
endfunction

`endif