`include "chain_l2.svh"

module param_stack_l5 #(
    parameter int DEPTH = 5,
    parameter int W = `ORION_CHAIN_W,
    parameter int INHERIT = `ORION_INHERIT_ID,
    parameter string TAG = "L5"
) (
    input  logic clk,
    input  logic rst_n,
    output logic [7:0] status
);
    param_stack_l4 #(
        .W(W - `ORION_CHAIN_STEP),
        .INHERIT(INHERIT + DEPTH),
        .TAG({TAG, ".param_stack_l4"})
    ) u_down (
        .clk(clk),
        .rst_n(rst_n),
        .status(status)
    );
endmodule
