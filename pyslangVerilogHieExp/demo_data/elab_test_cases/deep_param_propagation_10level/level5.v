module level5 #(
    parameter int PIN = 64
)();
    level4 #(
        .PIN( ((((PIN / 2 + 5) * (PIN % 3 + 2)) / 3) + 8) * (PIN % 4 + 1) )
    ) u_l4 ();
endmodule
