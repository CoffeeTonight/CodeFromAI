// Partial bus access helpers — byte/half lane placement for AMBA bridge masters
// Instantiate per module: `VERIF_BUS_LANE_FUNCS(DATA_WIDTH)
`ifndef VERIF_BUS_LANE_HELPERS_VH
`define VERIF_BUS_LANE_HELPERS_VH

`define VERIF_BUS_LANE_FUNCS(DW) \
  function [DW-1:0] lane_pwdata; \
    input [31:0] data; \
    input [31:0] addr; \
    input [2:0]  size; \
    reg [DW-1:0] result; \
    integer sh; \
    begin \
      result = {DW{1'b0}}; \
      case (size) \
        3'd1: begin sh = addr[1:0] * 8; result[sh +: 8] = data[7:0]; end \
        3'd2: begin sh = addr[1:0] * 8; result[sh +: 16] = data[15:0]; end \
        default: begin \
          if (DW > 32) sh = addr[2] * 32; \
          else sh = 0; \
          result[sh +: 32] = data; \
        end \
      endcase \
      lane_pwdata = result; \
    end \
  endfunction \
  function [31:0] lane_prdata; \
    input [DW-1:0] raw; \
    input [31:0]   addr; \
    input [2:0]    size; \
    integer sh; \
    begin \
      case (size) \
        3'd1: begin \
          sh = addr[1:0] * 8; \
          lane_prdata = {{24{raw[sh+7]}}, raw[sh +: 8]}; \
        end \
        3'd2: begin \
          sh = addr[1:0] * 8; \
          lane_prdata = {{16{raw[sh+15]}}, raw[sh +: 16]}; \
        end \
        default: begin \
          if (DW > 32) sh = addr[2] * 32; \
          else sh = 0; \
          lane_prdata = raw[sh +: 32]; \
        end \
      endcase \
    end \
  endfunction \
  function [(DW/8)-1:0] lane_wstrb; \
    input [31:0] addr; \
    input [2:0]  size; \
    reg [(DW/8)-1:0] base; \
    integer sh; \
    begin \
      case (size) \
        3'd1: base = {{((DW/8)-1){1'b0}}, 1'b1}; \
        3'd2: base = {{((DW/8)-2){1'b0}}, 2'b11}; \
        default: base = {((DW/8)){1'b1}}; \
      endcase \
      sh = (DW > 32) ? addr[2:0] : addr[1:0]; \
      lane_wstrb = base << sh; \
    end \
  endfunction

`endif