`include "chain_l2.svh"
`include "param_leaf.v"

module param_stack_l1 #(
    parameter int DEPTH = 1,
    parameter int W = `ORION_CHAIN_W,
    parameter int INHERIT = `ORION_INHERIT_ID,
    parameter string TAG = "L1"
) (
    input  logic clk,
    input  logic rst_n,
    output logic [7:0] status
);
    param_leaf #(
        .W(W - `ORION_CHAIN_STEP),
        .INHERIT(INHERIT + DEPTH),
        .TAG({TAG, ".param_leaf"})
    ) u_down (
        .clk(clk),
        .rst_n(rst_n),
        .status(status)
    );
endmodule
