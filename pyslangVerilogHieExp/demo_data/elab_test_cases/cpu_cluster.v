// Realistic generate-for example: CPU cluster with multiple cores
// This is a very common pattern in real SoCs

module cpu_cluster #(
    parameter int NUM_CORES = 8
)(
    input  logic clk,
    input  logic rst_n,
    output logic [31:0] cluster_result
);

    logic [31:0] core_results [NUM_CORES-1:0];

    generate
        for (genvar i = 0; i < NUM_CORES; i = i + 1) begin : u_core
            // Each core gets a unique ID via parameter
            cpu_core #(
                .CORE_ID(i),
                .IS_LEADER(i == 0)
            ) core_inst (
                .clk(clk),
                .rst_n(rst_n),
                .result(core_results[i])
            );

            // generate if: leader only gets extra controller
            if (i == 0) begin : gen_leader
                leader_controller u_leader_ctrl (
                    .clk(clk),
                    .rst_n(rst_n)
                );
            end
        end
    endgenerate

    // Simple reduction (for hierarchy testing, not functional)
    assign cluster_result = core_results[0] | core_results[1] | core_results[2] | core_results[3];

endmodule

module leader_controller (
    input logic clk,
    input logic rst_n
);
    // Dummy leader-only module for hierarchy testing
endmodule
