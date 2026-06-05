// Leaf: ddr5_ctrl
module ddr5_ctrl (
    input  logic clk,
    input  logic rst_n,
inout logic [63:0] dq
);
    `include "orion_cfg.svh"
    logic [31:0] scratch;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) scratch <= 32'h0;
        else scratch <= scratch + 1'b1;
    end
endmodule
