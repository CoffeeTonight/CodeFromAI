// Comprehensive test file for generate constructs (for hierarchy/unrolling purposes)
// Covers most common real-world patterns used in large SoCs

module all_generate_cases #(
    parameter int NUM_LANES = 4,
    parameter bit ENABLE_ECC = 1,
    parameter int MODE = 2
)(
    input logic clk
);

    // 1. Basic generate for with genvar
    generate
        for (genvar i = 0; i < NUM_LANES; i = i + 1) begin : lane
            cpu_core #(
                .CORE_ID(i)
            ) u_core (
                .clk(clk)
            );
        end
    endgenerate

    // 2. generate if / else
    generate
        if (ENABLE_ECC) begin : ecc_path
            cpu_core #(.CORE_ID(100)) u_ecc (.clk(clk));
        end else begin : no_ecc_path
            cpu_core #(.CORE_ID(200)) u_no_ecc (.clk(clk));
        end
    endgenerate

    // 3. generate case
    generate
        case (MODE)
            0: begin : mode0
                cpu_core #(.CORE_ID(300)) u_mode0 (.clk(clk));
            end
            1, 2: begin : mode12
                cpu_core #(.CORE_ID(400)) u_mode12 (.clk(clk));
            end
            default: begin : mode_def
                cpu_core #(.CORE_ID(500)) u_def (.clk(clk));
            end
        endcase
    endgenerate

    // 4. Nested generate (for inside if)
    generate
        if (NUM_LANES > 2) begin : big_cluster
            for (genvar j = 0; j < 2; j = j + 1) begin : sub
                cpu_core #(.CORE_ID(600 + j)) u_nested (.clk(clk));
            end
        end
    endgenerate

    // 5. Array of instances (not generate, but very similar effect for hierarchy)
    cpu_core array_cores [0:1] (
        .clk(clk)
    );

    // 6. Generate with localparam
    generate
        for (genvar k = 0; k < 2; k = k + 1) begin : localp
            localparam int ID = 700 + k;
            cpu_core #(.CORE_ID(ID)) u_local (.clk(clk));
        end
    endgenerate

    // 7. Empty generate (edge case)
    generate
    endgenerate

    // 8. Generate containing only non-instance constructs (should not produce hierarchy instances)
    generate
        if (1) begin : constants
            localparam int FOO = 123;
        end
    endgenerate

endmodule
