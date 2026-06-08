module level3 #(
    parameter int PIN = 64
)();
    level2 #(
        .PIN( ((((((PIN + 7) / (PIN % 2 + 1)) * 3) + 5) % 19) + (PIN / 3)) * 2 )
    ) u_l2 ();
endmodule
