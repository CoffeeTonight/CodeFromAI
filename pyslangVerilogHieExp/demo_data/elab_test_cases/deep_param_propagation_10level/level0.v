module level0 #(
    parameter int FINAL_P = 1,
    parameter int LIDX = 0
)();
    generate
        for (genvar k = 0; k < FINAL_P; k = k + 1) begin : u_final
        end
    endgenerate
endmodule
