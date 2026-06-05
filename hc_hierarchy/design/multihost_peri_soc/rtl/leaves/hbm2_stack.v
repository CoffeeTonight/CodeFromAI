// Leaf: hbm2_stack
module hbm2_stack (
    input  logic clk,
    input  logic rst_n,
inout logic [127:0] hbm_dq
);
    `include "orion_cfg.svh"
    logic [31:0] scratch;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) scratch <= 32'h0;
        else scratch <= scratch + 1'b1;
    end
endmodule
