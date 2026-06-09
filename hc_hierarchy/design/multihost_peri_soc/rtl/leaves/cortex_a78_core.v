// Leaf: cortex_a78_core
module cortex_a78_core (
    input  logic clk,
    input  logic rst_n,
output logic [3:0] pmu_irq
);
    `include "orion_cfg.svh"
    logic [31:0] scratch;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) scratch <= 32'h0;
        else scratch <= scratch + 1'b1;
    end
endmodule
