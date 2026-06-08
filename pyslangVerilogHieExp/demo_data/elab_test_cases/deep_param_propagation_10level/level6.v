module level6 #(
    parameter int PIN = 64
)();
    level5 #(
        .PIN( ((PIN + 13) / 2 * (PIN % 5 + 1)) + ((PIN / 3) * 4) )
    ) u_l5 ();
endmodule
