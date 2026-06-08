// Nested generate for deeper testing

module nested_generate #(
    parameter int CLUSTERS = 2,
    parameter int CORES_PER_CLUSTER = 2
)(
    input logic clk
);

    generate
        for (genvar c = 0; c < CLUSTERS; c = c + 1) begin : cluster
            for (genvar i = 0; i < CORES_PER_CLUSTER; i = i + 1) begin : core
                cpu_core #(
                    .CORE_ID(c * CORES_PER_CLUSTER + i)
                ) u_core (
                    .clk(clk)
                );
            end
        end
    endgenerate

endmodule
