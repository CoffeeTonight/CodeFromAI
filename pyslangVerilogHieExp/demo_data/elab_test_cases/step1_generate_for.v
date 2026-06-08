// Step 1: 가장 기본적인 generate-for + parameter
// 목표: unroller가 generate-for + genvar parameter를 제대로 처리하는지 검증

module step1_generate_for #(
    parameter int NUM_CORES = 4
)(
    input logic clk,
    input logic rst_n
);

    generate
        for (genvar i = 0; i < NUM_CORES; i = i + 1) begin : u_core
            core #(
                .CORE_ID(i)
            ) core_inst (
                .clk(clk),
                .rst_n(rst_n)
            );
        end
    endgenerate

endmodule