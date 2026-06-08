module level8 #(
    parameter int PIN = 64,
    parameter int BAR = 42   // target for defparam from top
)();
    level7 #(
        .PIN( (((PIN + 9) * 2) / (PIN % 3 + 2)) + (PIN / 5) )
    ) u_l7 ();
endmodule
