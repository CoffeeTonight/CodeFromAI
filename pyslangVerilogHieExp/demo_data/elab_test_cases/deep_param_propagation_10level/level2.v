module level2 #(
    parameter int PIN = 64
)();
    level1 #(
        .PIN( ((PIN * 4 + 9) / (PIN % 5 + 3)) + ((PIN / 2) * (PIN % 3 + 1)) )
    ) u_l1 ();
endmodule
