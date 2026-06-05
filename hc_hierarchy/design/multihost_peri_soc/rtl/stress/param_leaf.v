`include "chain_l2.svh"
module param_leaf #(
    parameter int W = `ORION_CHAIN_W,
    parameter int INHERIT = `ORION_INHERIT_ID,
    parameter string TAG = "leaf"
) (
    input  logic clk,
    input  logic rst_n,
    output logic [7:0] status
);
    assign status = W[7:0] ^ INHERIT[7:0];
endmodule
