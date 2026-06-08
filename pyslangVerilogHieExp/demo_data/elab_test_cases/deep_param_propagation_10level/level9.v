module level9 #(
    parameter int PIN = 64
)();
    level8 #(
        .PIN( ((TOP_P / 4) + (TOP_P % 5)) * 2 + 7 )
    ) u_l8 ();
endmodule
