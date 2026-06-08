// demo_data/elab_test_cases/step2_generate_if.v
// generate-if + generate-for 최소 테스트 케이스 (A-2 목표)

module first_unit ();
endmodule

module normal_unit #(
    parameter int INDEX = 0
)();
endmodule

module step2_generate_if #(
    parameter int NUM_UNITS = 4
)();

    generate
        for (genvar i = 0; i < NUM_UNITS; i = i + 1) begin : u_unit
            if (i == 0) begin : gen_first
                first_unit u_first();
            end
            else begin : gen_normal
                normal_unit #(
                    .INDEX(i)
                ) u_normal();
            end
        end
    endgenerate

endmodule