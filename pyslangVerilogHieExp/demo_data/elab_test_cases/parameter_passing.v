// demo_data/elab_test_cases/parameter_passing.v
// C 단계: 상위에서 parameter를 주고 하위 generate에서 사용하는 패턴

module sub_module #(
    parameter int WIDTH = 8,
    parameter int DEPTH = 4
)(
    input logic clk
);
endmodule

module param_passing_top #(
    parameter int TOTAL_WIDTH = 32
)(
    input logic clk
);

    generate
        for (genvar k = 0; k < 4; k = k + 1) begin : u_sub
            sub_module #(
                .WIDTH(TOTAL_WIDTH / 4),
                .DEPTH(k + 1)
            ) inst (
                .clk(clk)
            );
        end
    endgenerate

endmodule