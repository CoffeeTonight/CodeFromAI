module level10_top #(
    parameter int TOP_P = 128
)();
    `include "common_defines.vh"

    level9 #(
        .PIN( ((TOP_P / 4) + (TOP_P % 5)) * 2 + 7 )
    ) u_l9 ();

    // Test defparam - override deep in the hierarchy
    defparam u_l9.u_l8.u_l7.FINAL_OVERRIDE = `BASE_WIDTH * 5;   // should become 80
    defparam level10_top.u_l9.u_l8.BAR = 999;
endmodule
