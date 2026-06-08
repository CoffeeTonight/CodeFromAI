// demo_data/elab_test_cases/execution_lane.v
// B 단계용: 더 깊은 계층 + generate-for 중첩 예제

module execution_lane #(
    parameter int LANE_ID = 0
)(
    input  logic clk,
    input  logic rst_n
);
    // dummy
endmodule

module cpu_core #(
    parameter int CORE_ID = 0,
    parameter int NUM_LANES = 2
)(
    input  logic clk,
    input  logic rst_n
);

    generate
        for (genvar j = 0; j < NUM_LANES; j = j + 1) begin : u_lane
            execution_lane #(
                .LANE_ID(j)
            ) lane_inst (
                .clk(clk),
                .rst_n(rst_n)
            );
        end
    endgenerate

endmodule