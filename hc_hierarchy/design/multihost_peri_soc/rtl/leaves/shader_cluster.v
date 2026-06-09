// Leaf: shader_cluster
module shader_cluster (
    input  logic clk,
    input  logic rst_n,
output logic shader_done
);
    `include "orion_cfg.svh"
    logic [31:0] scratch;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) scratch <= 32'h0;
        else scratch <= scratch + 1'b1;
    end
endmodule
