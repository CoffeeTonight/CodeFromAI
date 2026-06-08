module level4 #(
    parameter int PIN = 64
)();
    level3 #(
        .PIN( ((PIN * 2 + 17) / (PIN % 6 + 2)) + (PIN / 4 * 3) )
    ) u_l3 ();
endmodule
